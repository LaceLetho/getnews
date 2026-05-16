"""Topic-only finding merge preview and accept workflow services."""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, ValidationError, field_validator

from ..domain.models import (
    FindingArchive,
    MergePreview,
    MergePreviewState,
    TopicFinding,
    TopicPrompt,
)

logger = logging.getLogger(__name__)

TOPIC_FINDINGS_MERGE_SCHEMA_VERSION = "topic-findings-merge-v1"


class MergedFindingCitation(BaseModel):
    message_id: str = ""
    message_snippet: str = ""
    source: str = ""
    published_at: str = ""


class MergedFindingItem(BaseModel):
    finding_id: str
    summary: str
    detail: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    source_finding_ids: List[str] = Field(default_factory=list)
    citations: List[MergedFindingCitation] = Field(default_factory=list)

    @field_validator("finding_id", "summary")
    @classmethod
    def required_text(cls, value: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise ValueError("field cannot be empty")
        return normalized


class TopicFindingsMergeOutput(BaseModel):
    schema_version: str = TOPIC_FINDINGS_MERGE_SCHEMA_VERSION
    topic_name: str
    merge_summary: str = ""
    merged_findings: List[MergedFindingItem] = Field(default_factory=list)
    findings_merged_count: int = Field(default=0, ge=0)
    findings_new_count: int = Field(default=0, ge=0)
    findings_deduplicated_count: int = Field(default=0, ge=0)

    @field_validator("schema_version")
    @classmethod
    def validate_schema_version(cls, value: str) -> str:
        if value != TOPIC_FINDINGS_MERGE_SCHEMA_VERSION:
            raise ValueError("unexpected topic findings merge schema version")
        return value

    @field_validator("topic_name")
    @classmethod
    def topic_name_required(cls, value: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise ValueError("topic_name cannot be empty")
        return normalized


class MergePreviewError(ValueError):
    """Raised when a merge preview operation cannot be completed."""


class TopicFindingMergeService:
    """Service for creating merge previews and accepting/rejecting them."""

    def __init__(
        self,
        intelligence_repository: Any,
        llm_client: Any,
        model_name: str = "",
        prompt_dir: Optional[Path] = None,
    ):
        self.repository = intelligence_repository
        self.llm_client = llm_client
        self.model_name = model_name
        self.prompt_dir = prompt_dir or Path(__file__).resolve().parents[2] / "prompts"

    def create_merge_preview(
        self,
        topic_id: str,
        prompt_version_id: str,
        created_by: Optional[str] = None,
    ) -> MergePreview:
        """Create a persisted merge preview from active findings + topic prompt context."""
        active_findings = self.repository.list_active_findings(topic_id)
        if len(active_findings) < 2:
            raise MergePreviewError("at least two active findings are required for merge")

        prompt = self.repository.get_topic_prompt_by_id(prompt_version_id)
        if prompt is None:
            raise MergePreviewError("prompt version not found")

        raw_output = self._call_llm(topic_id, prompt, active_findings)
        parsed = self._parse_merge_output(raw_output)

        preview_payload = parsed.model_dump()
        content_hash = hashlib.sha256(
            json.dumps(
                {
                    "topic_id": topic_id,
                    "prompt_version_id": prompt_version_id,
                    "merge_output": preview_payload,
                },
                ensure_ascii=False,
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()

        source_finding_ids = [f.id for f in active_findings]

        preview = MergePreview.create(
            intelligence_topic_id=topic_id,
            source_finding_ids=source_finding_ids,
            preview_payload=preview_payload,
            content_hash=content_hash,
            expires_at=datetime.utcnow() + timedelta(hours=24),
            created_by=created_by,
        )
        self.repository.create_merge_preview(preview)
        return preview

    def accept_merge_preview(
        self,
        preview_id: str,
        expected_topic_id: Optional[str] = None,
        operator: Optional[str] = None,
    ) -> TopicFinding:
        """Accept a merge preview: verify validity, persist merged finding, archive sources."""
        preview = self.repository.get_merge_preview(preview_id)
        if preview is None:
            raise MergePreviewError("merge preview not found")

        if expected_topic_id and preview.intelligence_topic_id != expected_topic_id:
            raise MergePreviewError(
                f"merge preview does not belong to topic {expected_topic_id}"
            )

        if preview.state != MergePreviewState.PENDING.value:
            raise MergePreviewError(f"merge preview is not pending (state={preview.state})")

        if preview.expires_at <= datetime.utcnow():
            self.repository.reject_merge_preview(preview_id)
            raise MergePreviewError("merge preview has expired")

        current_active = self.repository.list_active_findings(preview.intelligence_topic_id)
        current_active_ids = sorted({f.id for f in current_active})
        preview_source_ids = sorted(set(preview.source_finding_ids))
        if current_active_ids != preview_source_ids:
            raise MergePreviewError("active finding set has changed since preview was created")

        # Resolve the correct prompt_version_id from the topic's active prompt
        active_prompt = self.repository.get_active_topic_prompt(preview.intelligence_topic_id)
        prompt_version_id = active_prompt.id if active_prompt else preview.id

        merged_payload = self._build_merged_finding_payload(preview)

        merged_finding = TopicFinding.create(
            intelligence_topic_id=preview.intelligence_topic_id,
            prompt_version_id=prompt_version_id,
            finding_payload=merged_payload,
            content_hash=preview.content_hash,
            confidence=merged_payload.get("confidence", 0.0),
            citations=merged_payload.get("citations", []),
            source_finding_ids=list(preview_source_ids),
        )
        self.repository.create_topic_finding(merged_finding)

        for source_id in preview.source_finding_ids:
            self.repository.archive_finding(source_id, superseded_by_id=merged_finding.id)
            archive = FindingArchive.create(
                finding_id=source_id,
                intelligence_topic_id=preview.intelligence_topic_id,
                archive_reason="superseded",
                superseded_by_finding_id=merged_finding.id,
                archived_by=operator,
            )
            self.repository.archive_topic_finding(archive)

        self._set_preview_applied(preview_id)

        return merged_finding

    def reject_merge_preview(self, preview_id: str) -> None:
        """Reject a merge preview: mark it as cancelled."""
        preview = self.repository.get_merge_preview(preview_id)
        if preview is None:
            raise MergePreviewError("merge preview not found")
        if preview.state != MergePreviewState.PENDING.value:
            raise MergePreviewError(f"cannot reject preview in state {preview.state}")
        self.repository.reject_merge_preview(preview_id)

    def get_merge_preview(self, preview_id: str) -> Optional[MergePreview]:
        """Retrieve a merge preview by ID."""
        return self.repository.get_merge_preview(preview_id)

    def _call_llm(
        self,
        topic_id: str,
        prompt: TopicPrompt,
        active_findings: List[TopicFinding],
    ) -> str:
        system_prompt = (self.prompt_dir / "topic_findings_merge_prompt.md").read_text(
            encoding="utf-8"
        )
        user_payload = {
            "topic_name": getattr(
                self.repository.get_topic_by_id(topic_id), "name", ""
            ),
            "research_prompt": prompt.prompt_text,
            "active_findings": [self._finding_payload(f) for f in active_findings],
        }
        completions = getattr(getattr(self.llm_client, "chat", None), "completions", None)
        if completions is not None and hasattr(completions, "create"):
            kwargs: Dict[str, Any] = {
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
                ],
                "response_format": {"type": "json_object"},
            }
            if self.model_name:
                kwargs["model"] = self.model_name
            response = completions.create(**kwargs)
            return str(response.choices[0].message.content)
        if hasattr(self.llm_client, "complete"):
            return str(self.llm_client.complete(system_prompt, user_payload))
        raise TypeError("llm_client must expose chat.completions.create() or complete()")

    def _finding_payload(self, finding: TopicFinding) -> Dict[str, Any]:
        return {
            "finding_id": finding.id,
            "finding_payload": finding.finding_payload,
            "confidence": finding.confidence,
            "citations": finding.citations,
        }

    def _parse_merge_output(self, raw_output: str) -> TopicFindingsMergeOutput:
        try:
            payload = json.loads(raw_output)
        except (TypeError, json.JSONDecodeError) as exc:
            raise MergePreviewError(f"malformed merge output JSON: {exc}") from exc
        try:
            return TopicFindingsMergeOutput.model_validate(payload)
        except ValidationError as exc:
            raise MergePreviewError(f"invalid merge output structure: {exc}") from exc

    def _build_merged_finding_payload(self, preview: MergePreview) -> Dict[str, Any]:
        """Extract a single merged finding payload from the preview."""
        preview_payload = preview.preview_payload
        merged_findings = preview_payload.get("merged_findings", [])
        merge_summary = preview_payload.get("merge_summary", "")

        if merged_findings:
            first = merged_findings[0]
            return {
                "summary": first.get("summary", merge_summary),
                "detail": first.get("detail", ""),
                "confidence": first.get("confidence", 0.0),
                "citations": first.get("citations", []),
                "source_finding_ids": first.get("source_finding_ids", []),
                "schema_version": preview_payload.get("schema_version", ""),
                "topic_name": preview_payload.get("topic_name", ""),
                "merge_summary": merge_summary,
            }

        return {
            "summary": merge_summary,
            "detail": "",
            "confidence": 0.0,
            "citations": [],
            "source_finding_ids": list(preview.source_finding_ids),
            "schema_version": preview_payload.get("schema_version", ""),
            "topic_name": preview_payload.get("topic_name", ""),
            "merge_summary": merge_summary,
        }

    def _set_preview_applied(self, preview_id: str) -> None:
        self.repository.accept_merge_preview(preview_id)
