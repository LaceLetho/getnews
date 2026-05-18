"""Topic-only prompt generation and revision services."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator

from ..domain.models import IntelligenceTopic, TopicPrompt
from ..domain.repositories import IntelligenceRepository

PROMPT_GENERATION_SCHEMA_VERSION = "topic-prompt-generation-v1"
PROMPT_REVISION_SCHEMA_VERSION = "topic-prompt-revision-v1"

# Patterns that indicate the generated/revised prompt text is trying to define its
# own output JSON schema — which MUST be stripped because the output format is
# governed by topic_research_prompt.md (schema_version: topic-research-v1).
_OUTPUT_SCHEMA_INDICATORS = (
    # JSON code blocks that look like schema definitions
    (r"```json\s*\{[^`]*?\}\s*```", "json code block"),
    (r"```\s*\{[^`]*?(?:findings|channel_or_actor|source_platform|product_type)[^`]*?\}\s*```", "output schema code block"),
    # Lines that declare output fields not in the standard topic-research-v1 schema
    (r'"channel_or_actor"\s*:', "forbidden field channel_or_actor"),
    (r'"source_platform"\s*:', "forbidden field source_platform"),
    (r'"product_type"\s*:', "forbidden field product_type"),
    (r'"price_range"\s*:', "forbidden field price_range"),
    (r'"acquisition_method_summary"\s*:', "forbidden field acquisition_method_summary"),
    (r'"upstream_hypothesis"\s*:', "forbidden field upstream_hypothesis"),
    (r'"risk_level"\s*:', "forbidden field risk_level"),
    (r'"legitimacy"\s*:', "forbidden field legitimacy"),
    (r'"follow_up"\s*:', "forbidden field follow_up"),
)

logger = logging.getLogger(__name__)


def _topic_prompt_llm_timeout_seconds() -> Optional[float]:
    raw_value = os.getenv("TOPIC_PROMPT_LLM_TIMEOUT_SECONDS", "90").strip()
    if not raw_value:
        return None
    try:
        timeout_seconds = float(raw_value)
    except ValueError:
        logger.warning(
            "Invalid TOPIC_PROMPT_LLM_TIMEOUT_SECONDS=%r; using default 90 seconds",
            raw_value,
        )
        return 90.0
    return timeout_seconds if timeout_seconds > 0 else None


def _topic_prompt_llm_max_retries() -> int:
    raw_value = os.getenv("TOPIC_PROMPT_LLM_MAX_RETRIES", "0").strip()
    if not raw_value:
        return 0
    try:
        return max(0, int(raw_value))
    except ValueError:
        logger.warning("Invalid TOPIC_PROMPT_LLM_MAX_RETRIES=%r; using 0", raw_value)
        return 0


class TopicPromptDraft(BaseModel):
    """Validated LLM response for creating a topic research prompt."""

    schema_version: str = PROMPT_GENERATION_SCHEMA_VERSION
    topic_name: str
    topic_description: str
    research_prompt_draft: str
    suggested_time_window_hours: int = Field(default=24, ge=1)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)

    @field_validator("schema_version")
    @classmethod
    def validate_schema_version(cls, value: str) -> str:
        if value != PROMPT_GENERATION_SCHEMA_VERSION:
            raise ValueError("unexpected topic prompt generation schema version")
        return value

    @field_validator("topic_name", "topic_description", "research_prompt_draft")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise ValueError("field cannot be empty")
        return normalized


class TopicPromptRevision(BaseModel):
    """Validated LLM response for revising a topic research prompt."""

    schema_version: str = PROMPT_REVISION_SCHEMA_VERSION
    topic_name: str
    revised_prompt: str
    version: int = Field(ge=1)
    revision_note: str
    changes_summary: List[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)

    @field_validator("schema_version")
    @classmethod
    def validate_schema_version(cls, value: str) -> str:
        if value != PROMPT_REVISION_SCHEMA_VERSION:
            raise ValueError("unexpected topic prompt revision schema version")
        return value

    @field_validator("topic_name", "revised_prompt", "revision_note")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise ValueError("field cannot be empty")
        return normalized


class _TopicPromptLLMService:
    def __init__(
        self,
        llm_client: Any,
        model_name: str = "",
        prompt_dir: Optional[Path] = None,
    ):
        self.llm_client = llm_client
        self.model_name = model_name
        self.prompt_dir = prompt_dir or Path(__file__).resolve().parents[2] / "prompts"

    def _load_template(self, filename: str) -> str:
        return (self.prompt_dir / filename).read_text(encoding="utf-8")

    def _call_llm(self, system_prompt: str, user_payload: Dict[str, Any]) -> Dict[str, Any]:
        request_client = self.llm_client
        max_retries = _topic_prompt_llm_max_retries()
        with_options = getattr(request_client, "with_options", None)
        if callable(with_options):
            request_client = with_options(max_retries=max_retries)

        completions = getattr(getattr(request_client, "chat", None), "completions", None)
        if completions is not None and hasattr(completions, "create"):
            user_content = json.dumps(user_payload, ensure_ascii=False)
            kwargs: Dict[str, Any] = {
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                "response_format": {"type": "json_object"},
                # Use deepseek-v4-flash with thinking enabled for prompt
                # generation/revision.  Flash is faster than pro while still
                # producing high-quality structured prompts with thinking.
                "model": "deepseek-v4-flash",
                "extra_body": {"thinking": {"type": "enabled"}},
            }
            logger.info(
                "Topic prompt LLM request starting: model=deepseek-v4-flash thinking=enabled max_retries=%s",
                max_retries,
            )
            logger.debug(
                "Topic prompt LLM system prompt (first 500 chars): %s",
                system_prompt[:500],
            )
            logger.debug(
                "Topic prompt LLM user payload: %s",
                user_content[:2000],
            )
            try:
                response = completions.create(**kwargs)
            except Exception:
                logger.exception(
                    "Topic prompt LLM request failed. "
                    "System prompt (full): %s\nUser payload (full): %s",
                    system_prompt,
                    user_content,
                )
                raise
            logger.info("Topic prompt LLM response received")
            content = response.choices[0].message.content
            logger.debug(
                "Topic prompt LLM raw response content (first 2000 chars): %s",
                str(content)[:2000],
            )
        elif hasattr(self.llm_client, "complete"):
            logger.info("Topic prompt LLM using legacy complete() interface")
            content = self.llm_client.complete(system_prompt, user_payload)
            logger.debug(
                "Topic prompt LLM complete() raw response: %s",
                str(content)[:2000],
            )
        else:
            raise TypeError("llm_client must expose chat.completions.create() or complete()")

        if isinstance(content, dict):
            logger.info("Topic prompt LLM returned dict directly")
            return dict(content)

        # Parse JSON string response
        raw_str = str(content)
        try:
            parsed = json.loads(raw_str)
        except json.JSONDecodeError as json_err:
            logger.error(
                "Topic prompt LLM returned invalid JSON. "
                "Raw content (first 2000 chars): %s",
                raw_str[:2000],
            )
            raise ValueError(
                f"LLM returned invalid JSON: {json_err}. "
                f"Raw response (first 500 chars): {raw_str[:500]}"
            ) from json_err

        if not isinstance(parsed, dict):
            logger.error(
                "Topic prompt LLM returned non-dict JSON type=%s value=%r",
                type(parsed).__name__,
                parsed,
            )
            raise ValueError(
                f"LLM returned unexpected JSON type {type(parsed).__name__} "
                f"(expected a JSON object/dict). Value: {parsed!r}"
            )

        logger.info("Topic prompt LLM parsed response successfully")
        return parsed


class TopicPromptGenerator(_TopicPromptLLMService):
    """Generate validated topic prompt drafts from user themes."""

    def generate(
        self,
        user_theme: str,
        source_context: Optional[Dict[str, Any]] = None,
        intelligence_topic_id: str = "draft-topic",
        created_by: Optional[str] = None,
    ) -> TopicPrompt:
        payload = self._call_llm(
            self._load_template("topic_prompt_generation_prompt.md"),
            {"user_theme": user_theme, "source_context": source_context or {}},
        )
        draft = TopicPromptDraft.model_validate(payload)
        sanitized_text, sanitize_warnings = _sanitize_prompt_text(
            draft.research_prompt_draft
        )
        audit_entry = {
            "action": "generated",
            "topic_name": draft.topic_name,
            "topic_description": draft.topic_description,
            "suggested_time_window_hours": draft.suggested_time_window_hours,
            "confidence": draft.confidence,
        }
        if sanitize_warnings:
            audit_entry["sanitize_warnings"] = sanitize_warnings
        return TopicPrompt.create(
            intelligence_topic_id=intelligence_topic_id,
            prompt_version="1",
            prompt_text=sanitized_text,
            schema_version=draft.schema_version,
            created_by=created_by,
            audit_history=[audit_entry],
        )


class TopicPromptReviser(_TopicPromptLLMService):
    """Revise validated topic prompts from user feedback."""

    def revise(
        self,
        existing_prompt: TopicPrompt,
        user_feedback: str,
        expected_version: int,
        activated_by: Optional[str] = None,
    ) -> TopicPrompt:
        """Revise a prompt, producing version `expected_version`.

        The caller is responsible for determining the correct next version
        (typically max_version + 1 from the database).  The LLM is still asked
        to return a version number, but we validate it against `expected_version`
        and override with the server-computed value to prevent duplicates.
        """
        current_version = _parse_prompt_version(existing_prompt.prompt_version)
        logger.info(
            "Revising prompt for topic %s: current_version=%s expected_version=%s "
            "existing_prompt_id=%s existing_status=%s feedback_len=%d",
            existing_prompt.intelligence_topic_id,
            current_version,
            expected_version,
            existing_prompt.id,
            existing_prompt.status,
            len(user_feedback),
        )
        logger.debug(
            "Revision user_feedback: %s",
            user_feedback[:500],
        )
        logger.debug(
            "Existing prompt text (first 1000 chars): %s",
            existing_prompt.prompt_text[:1000],
        )
        if expected_version <= current_version:
            raise ValueError(
                f"expected_version ({expected_version}) must be greater than "
                f"current_version ({current_version})"
            )
        llm_user_payload = {
            "existing_prompt": existing_prompt.prompt_text,
            "user_feedback": user_feedback,
            "version": current_version,
            "expected_version": expected_version,
        }
        logger.info(
            "Calling LLM for prompt revision: topic=%s version=%s->%s",
            existing_prompt.intelligence_topic_id,
            current_version,
            expected_version,
        )
        payload = self._call_llm(
            self._load_template("topic_prompt_revision_prompt.md"),
            llm_user_payload,
        )
        logger.info(
            "LLM revision response received for topic %s: type=%s",
            existing_prompt.intelligence_topic_id,
            type(payload).__name__,
        )
        logger.debug(
            "LLM revision payload keys: %s",
            list(payload.keys()) if isinstance(payload, dict) else "N/A",
        )
        try:
            revision = TopicPromptRevision.model_validate(payload)
        except Exception as validate_err:
            logger.error(
                "Failed to validate LLM revision response for topic %s. "
                "Raw payload (first 2000 chars): %s",
                existing_prompt.intelligence_topic_id,
                json.dumps(payload, ensure_ascii=False, default=str)[:2000],
            )
            raise ValueError(
                f"LLM revision response validation failed: {validate_err}. "
                f"Raw payload keys: {list(payload.keys()) if isinstance(payload, dict) else type(payload).__name__}"
            ) from validate_err

        logger.info(
            "LLM revision validated: topic_name=%r llm_version=%s revision_note=%r confidence=%s",
            revision.topic_name,
            revision.version,
            revision.revision_note[:100] if revision.revision_note else "",
            revision.confidence,
        )
        # The LLM is instructed to return expected_version, but we enforce it
        # server-side to prevent any LLM hallucination from causing duplicates.
        if revision.version != expected_version:
            logger.warning(
                "LLM returned version %s but expected %s; using server-computed version",
                revision.version,
                expected_version,
            )
        sanitized_text, sanitize_warnings = _sanitize_prompt_text(
            revision.revised_prompt
        )
        if sanitize_warnings:
            logger.warning(
                "Prompt revision sanitization warnings for topic %s: %s",
                existing_prompt.intelligence_topic_id,
                sanitize_warnings,
            )
        logger.info(
            "Revision sanitized: original_len=%d sanitized_len=%d",
            len(revision.revised_prompt),
            len(sanitized_text),
        )
        audit_entry = {
            "action": "revised",
            "topic_name": revision.topic_name,
            "revision_note": revision.revision_note,
            "changes_summary": revision.changes_summary,
            "confidence": revision.confidence,
        }
        if sanitize_warnings:
            audit_entry["sanitize_warnings"] = sanitize_warnings
        result = TopicPrompt.create(
            intelligence_topic_id=existing_prompt.intelligence_topic_id,
            prompt_version=str(expected_version),
            prompt_text=sanitized_text,
            schema_version=revision.schema_version,
            created_by=existing_prompt.created_by,
            activated_by=activated_by,
            audit_history=[
                *list(existing_prompt.audit_history or []),
                audit_entry,
            ],
        )
        logger.info(
            "Revision complete: topic=%s new_version=%s new_prompt_id=%s",
            existing_prompt.intelligence_topic_id,
            expected_version,
            result.id,
        )
        return result


def _parse_prompt_version(value: str) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        digits = "".join(ch for ch in str(value or "") if ch.isdigit())
        return int(digits or "0")


def _sanitize_prompt_text(prompt_text: str) -> tuple[str, list[str]]:
    """Strip conflicting output-schema content from a generated/revised prompt.

    Returns (sanitized_text, warnings).  The sanitized text still describes
    *what* to research but no longer embeds its own JSON output format.
    """
    import re as _re

    warnings: list[str] = []
    sanitized = str(prompt_text or "")

    for pattern, label in _OUTPUT_SCHEMA_INDICATORS:
        if _re.search(pattern, sanitized):
            warnings.append(f"Detected {label} in prompt text — will be stripped")
            sanitized = _re.sub(pattern, "", sanitized)

    # Collapse multiple blank lines created by stripping
    sanitized = _re.sub(r"\n{3,}", "\n\n", sanitized)
    sanitized = sanitized.strip()

    if warnings:
        logger.warning(
            "Prompt sanitization stripped %d conflicting schema indicators: %s",
            len(warnings),
            warnings,
        )

    return sanitized, warnings


class TopicPromptWorkflowService:
    """Orchestrate the topic prompt draft, revise, manual replace, confirm workflow."""

    def __init__(
        self,
        repository: IntelligenceRepository,
        llm_client: Any = None,
        model_name: str = "",
        prompt_dir: Optional[Path] = None,
        max_prompt_length: int = 50000,
    ):
        self.repository = repository
        self.llm_client = llm_client
        self.model_name = model_name
        self.prompt_dir = prompt_dir or Path(__file__).resolve().parents[2] / "prompts"
        self.max_prompt_length = max_prompt_length
        self._generator: Optional[TopicPromptGenerator] = None
        self._reviser: Optional[TopicPromptReviser] = None

    def _get_generator(self) -> TopicPromptGenerator:
        if self.llm_client is None:
            raise RuntimeError("llm_client is required for LLM-based operations")
        if self._generator is None:
            self._generator = TopicPromptGenerator(
                self.llm_client, self.model_name, self.prompt_dir
            )
        return self._generator

    def _get_reviser(self) -> TopicPromptReviser:
        if self.llm_client is None:
            raise RuntimeError("llm_client is required for LLM-based operations")
        if self._reviser is None:
            self._reviser = TopicPromptReviser(self.llm_client, self.model_name, self.prompt_dir)
        return self._reviser

    def create_draft_topic(
        self,
        theme: str,
        source_context: Optional[Dict[str, Any]] = None,
        created_by: Optional[str] = None,
    ) -> TopicPrompt:
        """Create a new intelligence topic and generate a draft prompt via LLM."""
        topic = IntelligenceTopic.create(name=theme, lifecycle_status="draft")
        self.repository.save_topic(topic)

        prompt = self._get_generator().generate(
            user_theme=theme,
            source_context=source_context,
            intelligence_topic_id=topic.id,
            created_by=created_by,
        )
        self.repository.create_topic_prompt_version(prompt)
        return prompt

    def revise_prompt(
        self,
        topic_id: str,
        feedback: str,
        activated_by: Optional[str] = None,
    ) -> TopicPrompt:
        """Revise the most recent prompt for a topic using LLM and user feedback.

        The next version number is computed server-side from MAX(prompt_version)
        in the database to prevent duplicate key violations — the LLM is never
        trusted to determine the version on its own.
        """
        logger.info(
            "revise_prompt started: topic_id=%s feedback_len=%d activated_by=%s",
            topic_id,
            len(feedback),
            activated_by,
        )
        prompts = self.repository.list_topic_prompts(topic_id, limit=1)
        if not prompts:
            raise ValueError(f"No prompt found for topic {topic_id}")
        existing = prompts[0]
        logger.info(
            "revise_prompt existing prompt: id=%s version=%s status=%s created_at=%s",
            existing.id,
            existing.prompt_version,
            existing.status,
            existing.created_at,
        )

        # Compute the next version server-side from the actual DB max, not from
        # the "most recent" prompt (which is ordered by timestamp, not version).
        max_version = self.repository.get_max_prompt_version(topic_id)
        expected_version = max_version + 1
        logger.info(
            "revise_prompt version computation: existing_version=%s max_version=%d expected_version=%d",
            existing.prompt_version,
            max_version,
            expected_version,
        )

        revised = self._get_reviser().revise(
            existing, feedback,
            expected_version=expected_version,
            activated_by=activated_by,
        )
        logger.info(
            "revise_prompt saving new version: topic_id=%s new_version=%d new_id=%s",
            topic_id,
            expected_version,
            revised.id,
        )
        self.repository.create_topic_prompt_version(revised)
        logger.info(
            "revise_prompt complete: topic_id=%s new_version=%d",
            topic_id,
            expected_version,
        )
        return revised

    def replace_prompt_manual(
        self,
        topic_id: str,
        prompt_text: str,
        created_by: Optional[str] = None,
    ) -> TopicPrompt:
        """Manually replace the prompt text for a topic, creating a new draft version."""
        normalized = str(prompt_text or "").strip()
        if not normalized:
            raise ValueError("prompt_text cannot be empty")
        if len(normalized) > self.max_prompt_length:
            raise ValueError(
                f"prompt_text exceeds maximum length of {self.max_prompt_length} characters"
            )

        # Use MAX(prompt_version) from DB — not timestamp-ordered query —
        # to guarantee the next version is truly unique.
        max_version = self.repository.get_max_prompt_version(topic_id)
        next_version = max_version + 1

        prompts = self.repository.list_topic_prompts(topic_id, limit=1)
        audit_entry: Dict[str, Any] = {
            "action": "manual_replace",
            "previous_version": prompts[0].prompt_version if prompts else None,
            "note": "Manually replaced prompt text",
        }

        prompt = TopicPrompt.create(
            intelligence_topic_id=topic_id,
            prompt_version=str(next_version),
            prompt_text=normalized,
            schema_version=PROMPT_GENERATION_SCHEMA_VERSION,
            status="draft",
            created_by=created_by,
            audit_history=[
                *(prompts[0].audit_history if prompts else []),
                audit_entry,
            ],
        )
        self.repository.create_topic_prompt_version(prompt)
        return prompt

    def confirm_prompt(
        self,
        topic_id: str,
        prompt_version_id: str,
        activated_by: Optional[str] = None,
        activation_notes: Optional[str] = None,
    ) -> TopicPrompt:
        """Confirm a draft prompt version, archiving any previously active version."""
        prompt = self.repository.get_topic_prompt_by_id(prompt_version_id)
        if prompt is None:
            raise ValueError(f"Prompt {prompt_version_id} not found")
        if prompt.intelligence_topic_id != topic_id:
            raise ValueError("Prompt does not belong to the specified topic")
        if prompt.status != "draft":
            raise ValueError("Only draft prompts can be confirmed")

        current_active = self.repository.get_active_topic_prompt(topic_id)
        if current_active is not None and current_active.id != prompt.id:
            current_active.status = "archived"
            current_active.archived_at = datetime.utcnow()
            current_active.updated_at = datetime.utcnow()
            self.repository.create_topic_prompt_version(current_active)

        prompt.status = "active"
        prompt.activated_by = activated_by
        prompt.activation_notes = activation_notes
        prompt.activated_at = datetime.utcnow()
        prompt.updated_at = datetime.utcnow()
        self.repository.create_topic_prompt_version(prompt)
        return prompt

    def edit_active_prompt(
        self,
        topic_id: str,
        new_prompt_text: str,
        created_by: Optional[str] = None,
    ) -> TopicPrompt:
        """Edit the active prompt, creating a new draft version."""
        active = self.repository.get_active_topic_prompt(topic_id)
        if active is None:
            raise ValueError(f"No active prompt found for topic {topic_id}")

        normalized = str(new_prompt_text or "").strip()
        if not normalized:
            raise ValueError("new_prompt_text cannot be empty")
        if len(normalized) > self.max_prompt_length:
            raise ValueError(
                f"new_prompt_text exceeds maximum length of {self.max_prompt_length} characters"
            )

        # Use MAX(prompt_version) from DB to avoid collisions with existing
        # draft versions that may have higher version numbers than the active one.
        max_version = self.repository.get_max_prompt_version(topic_id)
        next_version = max_version + 1

        audit_entry: Dict[str, Any] = {
            "action": "edited",
            "previous_version": active.prompt_version,
            "note": "Edited active prompt to create new draft",
        }

        prompt = TopicPrompt.create(
            intelligence_topic_id=topic_id,
            prompt_version=str(next_version),
            prompt_text=normalized,
            schema_version=active.schema_version,
            status="draft",
            created_by=created_by,
            audit_history=[*list(active.audit_history or []), audit_entry],
        )
        self.repository.create_topic_prompt_version(prompt)
        return prompt
