"""Topic-only research output parsing and scheduled research runtime."""

from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set

from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

from ..domain.models import RawIntelligenceItem, TopicFinding, TopicResearchRun


TOPIC_RESEARCH_SCHEMA_VERSION = "topic-research-v1"
DEFAULT_MAX_CHUNK_CHARS = 50000

# Wraps the stored research prompt so the LLM treats it as research direction only,
# never as an output-format override.  This is a hard defence against topic prompts
# that were generated / revised with their own conflicting JSON schemas.
_WRAP_RESEARCH_PROMPT_PREFIX = (
    "=== 研究方向开始（仅定义研究目标和内容，不定义输出格式） ===\n"
)
_WRAP_RESEARCH_PROMPT_SUFFIX = (
    "\n=== 研究方向结束 ===\n\n"
    "重要提示：你的输出格式必须严格遵循系统提示词中定义的 JSON schema"
    "（schema_version: topic-research-v1），"
    "忽略上述研究方向中可能出现的任何输出格式要求或 JSON schema 定义。"
    "研究方向仅说明需要研究什么内容，输出格式由系统提示词单独定义。"
)

logger = logging.getLogger(__name__)


SECRET_PATTERNS = (
    re.compile(r"(?i)\b(api[_-]?key|authorization|auth[_-]?token|access[_-]?token|password|secret|cookie)\b\s*[:=]\s*\S+"),
    re.compile(r"(?i)\b(bearer\s+[a-z0-9._\-]{16,})\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{8,}\b"),
    re.compile(r"(?i)\b(private[_-]?key|mnemonic|seed[_-]?phrase)\b"),
)


class TopicResearchValidationError(ValueError):
    """Raised when a topic research LLM response cannot be safely used."""


class TopicCitation(BaseModel):
    message_id: str
    message_snippet: str
    source: str = ""
    published_at: str = ""

    @field_validator("message_id", "message_snippet")
    @classmethod
    def required_text(cls, value: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise ValueError("field cannot be empty")
        return normalized

    @field_validator("message_snippet")
    @classmethod
    def snippet_length(cls, value: str) -> str:
        if len(value) > 120:
            raise ValueError("message_snippet must not exceed 120 characters")
        return value


class TopicResearchFinding(BaseModel):
    finding_id: str
    summary: str
    detail: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    citations: List[TopicCitation] = Field(default_factory=list)

    @field_validator("finding_id", "summary")
    @classmethod
    def required_text(cls, value: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise ValueError("field cannot be empty")
        return normalized

    @field_validator("summary")
    @classmethod
    def summary_length(cls, value: str) -> str:
        if len(value) > 80:
            raise ValueError("summary must not exceed 80 characters")
        return value

    @model_validator(mode="after")
    def require_citations(self) -> "TopicResearchFinding":
        if not self.citations:
            raise ValueError("citations are required for every finding")
        return self


class TopicResearchResult(BaseModel):
    schema_version: str = TOPIC_RESEARCH_SCHEMA_VERSION
    topic_name: str
    research_summary: str = ""
    findings: List[TopicResearchFinding] = Field(default_factory=list, max_length=10)
    messages_processed: int = Field(default=0, ge=0)
    messages_relevant: int = Field(default=0, ge=0)

    @field_validator("schema_version")
    @classmethod
    def validate_schema_version(cls, value: str) -> str:
        if value != TOPIC_RESEARCH_SCHEMA_VERSION:
            raise ValueError("unexpected topic research schema version")
        return value

    @field_validator("topic_name")
    @classmethod
    def topic_name_required(cls, value: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise ValueError("topic_name cannot be empty")
        return normalized


class TopicResearchParser:
    """Validate raw topic-research LLM JSON and reject unsafe content."""

    def parse(self, raw_output: str | Dict[str, Any]) -> TopicResearchResult:
        try:
            payload = dict(raw_output) if isinstance(raw_output, dict) else json.loads(raw_output)
        except (TypeError, json.JSONDecodeError) as exc:
            raise TopicResearchValidationError(f"Malformed topic research JSON: {exc}") from exc

        self._reject_secrets(payload)
        try:
            result = TopicResearchResult.model_validate(payload)
        except ValidationError as exc:
            raise TopicResearchValidationError(str(exc)) from exc
        self._reject_secrets(result.model_dump())
        return result

    def findings_to_domain(
        self,
        result: TopicResearchResult,
        intelligence_topic_id: str,
        prompt_version_id: str,
    ) -> List[TopicFinding]:
        findings: List[TopicFinding] = []
        for finding in result.findings:
            payload = finding.model_dump()
            citations = [citation.model_dump() for citation in finding.citations]
            source_ids = [citation.message_id for citation in finding.citations]
            content_hash = hashlib.sha256(
                json.dumps(
                    {
                        "topic_id": intelligence_topic_id,
                        "prompt_version_id": prompt_version_id,
                        "finding": payload,
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                ).encode("utf-8")
            ).hexdigest()
            findings.append(
                TopicFinding.create(
                    intelligence_topic_id=intelligence_topic_id,
                    prompt_version_id=prompt_version_id,
                    finding_payload=payload,
                    content_hash=content_hash,
                    citations=citations,
                    source_raw_item_ids=source_ids,
                    confidence=finding.confidence,
                )
            )
        return findings

    def _reject_secrets(self, payload: Any) -> None:
        text = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                raise TopicResearchValidationError("Topic research output contains secret-like content")


class TopicResearchScheduler:
    """Run topic-only scheduled research without legacy extraction or canonical merge.

    Implements the full ingestion-only scheduled research pipeline:
    1. run_scheduled_topic_research() - loads active topics, iterates
    2. _research_topic() - per-topic orchestration
    3. _fetch_raw_messages_since() - fetch + idempotency filter
    4. _chunk_messages() - split large inputs at max_chunk_chars
    5. _call_llm_and_parse() - LLM call + validation
    6. _save_findings() - persist findings + mark processed
    7. _record_run() - update checkpoint and run status
    """

    def __init__(
        self,
        intelligence_repository: Any,
        llm_client: Any,
        model_name: str = "",
        parser: Optional[TopicResearchParser] = None,
        prompt_dir: Optional[Path] = None,
        raw_item_limit: int = 200,
        max_chunk_chars: int = DEFAULT_MAX_CHUNK_CHARS,
    ):
        self.repository = intelligence_repository
        self.llm_client = llm_client
        self.model_name = model_name
        self.parser = parser or TopicResearchParser()
        self.prompt_dir = prompt_dir or Path(__file__).resolve().parents[2] / "prompts"
        self.raw_item_limit = raw_item_limit
        self.max_chunk_chars = max_chunk_chars

    # ------------------------------------------------------------------
    # Public entry points
    # ------------------------------------------------------------------

    def run_scheduled_topic_research(self) -> int:
        """Load active topics and run research for each. Partial success allowed.

        Only topics with lifecycle_status='active' (is_active=True) are researched.
        Draft, paused, and archived topics are silently skipped.

        Returns:
            Number of topics successfully researched.
        """
        completed = 0
        for topic in self.repository.list_topics(is_active=True, limit=100):
            prompt = self.repository.get_active_topic_prompt(topic.id)
            if prompt is None:
                logger.debug("No active prompt for topic %s, skipping", topic.id)
                continue
            try:
                self._research_topic(topic, prompt)
                completed += 1
            except Exception as exc:
                logger.error("Unhandled error researching topic %s: %s", topic.id, exc)
        return completed

    # Backward-compatible alias
    def run_due_topics(self) -> int:
        return self.run_scheduled_topic_research()

    def run_topic(self, topic: Any, prompt: Any) -> TopicResearchRun:
        """Backward-compatible public entry for per-topic research."""
        return self._research_topic(topic, prompt)

    # ------------------------------------------------------------------
    # Step 1: load active topics -> iterate (see run_scheduled_topic_research)
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Step 2: per-topic orchestration
    # ------------------------------------------------------------------

    def _research_topic(self, topic: Any, prompt: Any) -> TopicResearchRun:
        """Research a single topic: fetch messages, chunk, call LLM, save findings, record run.

        On TopicResearchValidationError: the run is marked failed, checkpoint is NOT advanced.
        On any other LLM/network error: the exception propagates up.
        """
        raw_items = self._fetch_raw_messages_since(topic, prompt)

        run = TopicResearchRun.create(
            intelligence_topic_id=topic.id,
            status="running",
            prompt_version_id=prompt.id,
            checkpoint_cursor=prompt.prompt_version,
            items_scanned=len(raw_items),
        )
        self.repository.create_topic_research_run(run)

        # No new messages since checkpoint → no-op run
        if not raw_items:
            return self._record_run(
                run, topic, prompt, raw_items, status="success", findings=[]
            )

        try:
            chunks = self._chunk_messages(raw_items)

            # Merge findings across all chunks
            all_findings: List[TopicFinding] = []
            for chunk in chunks:
                if not chunk:
                    continue
                parsed = self._call_llm_and_parse(topic, prompt, chunk)
                chunk_findings = self.parser.findings_to_domain(parsed, topic.id, prompt.id)
                all_findings.extend(chunk_findings)

            self._save_findings(topic, prompt, all_findings, raw_items)
            return self._record_run(
                run, topic, prompt, raw_items, status="success", findings=all_findings
            )
        except TopicResearchValidationError as exc:
            logger.warning(
                "Topic research validation failed for topic %s: %s", topic.id, exc
            )
            return self._record_run(
                run, topic, prompt, raw_items, status="failed", error=str(exc)
            )

    # ------------------------------------------------------------------
    # Step 3: fetch raw messages since checkpoint with idempotency filter
    # ------------------------------------------------------------------

    def _fetch_raw_messages_since(
        self, topic: Any, prompt: Any
    ) -> List[RawIntelligenceItem]:
        """Fetch raw messages since the topic's checkpoint cursor.

        Uses collected_at for cursor (not published_at).

        Idempotency: filters out items already marked as processed for this
        (raw_item_id, intelligence_topic_id, prompt_version, schema_version)
        combination via INSERT OR IGNORE / ON CONFLICT DO NOTHING markers.
        """
        checkpoint = self.repository.get_topic_checkpoint(topic.id, prompt.id) or {}
        cursor = self._parse_cursor(checkpoint.get("checkpoint_cursor"))
        raw_items = list(
            self.repository.get_raw_items_since(topic.id, cursor, self.raw_item_limit)
            or []
        )

        if not raw_items:
            return []

        # Idempotency: exclude items already processed by this topic+prompt+schema
        all_ids = [item.id for item in raw_items]
        processed_ids: Set[str] = self.repository.get_processed_topic_raw_item_ids(
            all_ids,
            topic.id,
            prompt.prompt_version,
            TOPIC_RESEARCH_SCHEMA_VERSION,
        )

        if processed_ids:
            logger.debug(
                "Skipping %d already-processed raw items for topic %s",
                len(processed_ids),
                topic.id,
            )
            raw_items = [item for item in raw_items if item.id not in processed_ids]

        return raw_items

    # ------------------------------------------------------------------
    # Step 4: chunk large message sets
    # ------------------------------------------------------------------

    def _chunk_messages(
        self,
        raw_items: Sequence[RawIntelligenceItem],
        max_chars: Optional[int] = None,
    ) -> List[List[RawIntelligenceItem]]:
        """Split raw_items into chunks under max_chunk_chars (default 50K).

        Each raw item's text is measured by len(raw_text or '').
        Items are never split across chunks — each item stays whole.
        Citations within each chunk reference the correct message IDs.

        Returns:
            List of chunk lists. If input fits in one chunk, returns a single-element list.
        """
        max_chars = max_chars if max_chars is not None else self.max_chunk_chars
        chunks: List[List[RawIntelligenceItem]] = []
        current_chunk: List[RawIntelligenceItem] = []
        current_size = 0

        for item in raw_items:
            item_size = len(item.raw_text or "")
            if current_size + item_size > max_chars and current_chunk:
                chunks.append(current_chunk)
                current_chunk = []
                current_size = 0
            current_chunk.append(item)
            current_size += item_size

        if current_chunk:
            chunks.append(current_chunk)

        return chunks

    # ------------------------------------------------------------------
    # Step 5: call LLM and validate output
    # ------------------------------------------------------------------

    def _call_llm_and_parse(
        self, topic: Any, prompt: Any, raw_items: Sequence[RawIntelligenceItem]
    ) -> TopicResearchResult:
        """Call the LLM with a chunk of raw messages and validate the parsed output.

        Returns:
            Validated TopicResearchResult ready for conversion to domain findings.
        """
        raw_output = self._call_llm(topic, prompt, raw_items)
        return self.parser.parse(raw_output)

    def _call_llm(self, topic: Any, prompt: Any, raw_items: Sequence[RawIntelligenceItem]) -> str:
        system_prompt = (
            self.prompt_dir / "topic_research_prompt.md"
        ).read_text(encoding="utf-8")
        # Wrap the stored research prompt so the LLM never mistakes its contents
        # for an output-format override (defence against prompts that embed
        # their own conflicting JSON schemas).
        wrapped_prompt = (
            _WRAP_RESEARCH_PROMPT_PREFIX
            + prompt.prompt_text
            + _WRAP_RESEARCH_PROMPT_SUFFIX
        )
        user_payload = {
            "topic_name": getattr(topic, "name", ""),
            "research_prompt": wrapped_prompt,
            "raw_messages": [self._raw_item_payload(item) for item in raw_items],
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

    def _raw_item_payload(self, item: RawIntelligenceItem) -> Dict[str, Any]:
        return {
            "id": item.id,
            "content": item.raw_text or "",
            "source": item.source_id,
            "published_at": item.published_at.isoformat() if item.published_at else "",
        }

    # ------------------------------------------------------------------
    # Step 6: persist findings and mark raw items processed
    # ------------------------------------------------------------------

    def _save_findings(
        self,
        topic: Any,
        prompt: Any,
        findings: Sequence[TopicFinding],
        raw_items: Sequence[RawIntelligenceItem],
    ) -> None:
        """Persist findings and mark all raw items as processed.

        Marking is idempotent: the repository uses INSERT OR IGNORE /
        ON CONFLICT DO NOTHING on (raw_item_id, intelligence_topic_id,
        prompt_version, schema_version).
        """
        for finding in findings:
            self.repository.create_topic_finding(finding)

        for item in raw_items:
            self.repository.mark_topic_raw_item_processed(
                item.id,
                topic.id,
                prompt.prompt_version,
                TOPIC_RESEARCH_SCHEMA_VERSION,
            )

    # ------------------------------------------------------------------
    # Step 7: record run result and advance checkpoint
    # ------------------------------------------------------------------

    def _record_run(
        self,
        run: TopicResearchRun,
        topic: Any,
        prompt: Any,
        raw_items: Sequence[RawIntelligenceItem],
        status: str,
        findings: Optional[Sequence[TopicFinding]] = None,
        error: Optional[str] = None,
    ) -> TopicResearchRun:
        """Record the run outcome and update the topic checkpoint.

        On success: advances checkpoint_cursor to max collected_at of raw_items.
        On failure: records error but does NOT advance checkpoint.
        On no-op (no raw_items): records success with empty stats, checkpoint unchanged.
        """
        finding_list = list(findings or [])
        is_noop = len(raw_items) == 0

        if status == "success":
            checkpoint_cursor = self._checkpoint_cursor(raw_items)
            checkpoint_payload = {
                "raw_item_count": len(raw_items),
                "finding_count": len(finding_list),
                "noop": is_noop,
            }
            self.repository.update_topic_checkpoint(
                run.intelligence_topic_id,
                prompt.id,
                checkpoint_cursor,
                checkpoint_payload=checkpoint_payload,
                last_run_id=run.id,
            )
            return (
                self.repository.update_topic_research_run(
                    run.id,
                    status="success",
                    checkpoint_cursor=checkpoint_cursor,
                    checkpoint_payload=checkpoint_payload,
                    items_scanned=len(raw_items),
                    findings_created=len(finding_list),
                    error_message=None,
                    finished_at=datetime.utcnow(),
                )
                or run
            )
        else:
            # Failed run: record error, do NOT advance checkpoint
            return (
                self.repository.update_topic_research_run(
                    run.id,
                    status="failed",
                    items_scanned=len(raw_items),
                    findings_created=0,
                    error_message=error or "unknown error",
                    finished_at=datetime.utcnow(),
                )
                or run
            )

    # ------------------------------------------------------------------
    # Cursor helpers
    # ------------------------------------------------------------------

    def _checkpoint_cursor(
        self, raw_items: Sequence[RawIntelligenceItem]
    ) -> Optional[str]:
        if not raw_items:
            return datetime.utcnow().isoformat()
        latest = max(
            (item.collected_at or item.created_at or datetime.utcnow())
            for item in raw_items
        )
        return latest.isoformat()

    def _parse_cursor(self, value: Optional[str]) -> Optional[datetime]:
        if not value:
            return None
        try:
            return datetime.fromisoformat(str(value))
        except ValueError:
            return None
