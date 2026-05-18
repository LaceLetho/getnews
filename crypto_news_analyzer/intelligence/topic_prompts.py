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
            timeout_seconds = _topic_prompt_llm_timeout_seconds()
            kwargs: Dict[str, Any] = {
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
                ],
                "response_format": {"type": "json_object"},
            }
            if timeout_seconds is not None:
                kwargs["timeout"] = timeout_seconds
            if self.model_name:
                kwargs["model"] = self.model_name
            logger.info(
                "Topic prompt LLM request starting: model=%s timeout=%s max_retries=%s",
                self.model_name or "default",
                timeout_seconds,
                max_retries,
            )
            try:
                response = completions.create(**kwargs)
            except Exception:
                logger.exception("Topic prompt LLM request failed")
                raise
            logger.info("Topic prompt LLM response received")
            content = response.choices[0].message.content
        elif hasattr(self.llm_client, "complete"):
            content = self.llm_client.complete(system_prompt, user_payload)
        else:
            raise TypeError("llm_client must expose chat.completions.create() or complete()")

        if isinstance(content, dict):
            return dict(content)
        return json.loads(str(content))


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
        return TopicPrompt.create(
            intelligence_topic_id=intelligence_topic_id,
            prompt_version="1",
            prompt_text=draft.research_prompt_draft,
            schema_version=draft.schema_version,
            created_by=created_by,
            audit_history=[
                {
                    "action": "generated",
                    "topic_name": draft.topic_name,
                    "topic_description": draft.topic_description,
                    "suggested_time_window_hours": draft.suggested_time_window_hours,
                    "confidence": draft.confidence,
                }
            ],
        )


class TopicPromptReviser(_TopicPromptLLMService):
    """Revise validated topic prompts from user feedback."""

    def revise(
        self,
        existing_prompt: TopicPrompt,
        user_feedback: str,
        activated_by: Optional[str] = None,
    ) -> TopicPrompt:
        current_version = _parse_prompt_version(existing_prompt.prompt_version)
        payload = self._call_llm(
            self._load_template("topic_prompt_revision_prompt.md"),
            {
                "existing_prompt": existing_prompt.prompt_text,
                "user_feedback": user_feedback,
                "version": current_version,
            },
        )
        revision = TopicPromptRevision.model_validate(payload)
        if revision.version <= current_version:
            raise ValueError("revised prompt version must increment")
        return TopicPrompt.create(
            intelligence_topic_id=existing_prompt.intelligence_topic_id,
            prompt_version=str(revision.version),
            prompt_text=revision.revised_prompt,
            schema_version=revision.schema_version,
            created_by=existing_prompt.created_by,
            activated_by=activated_by,
            audit_history=[
                *list(existing_prompt.audit_history or []),
                {
                    "action": "revised",
                    "topic_name": revision.topic_name,
                    "revision_note": revision.revision_note,
                    "changes_summary": revision.changes_summary,
                    "confidence": revision.confidence,
                },
            ],
        )


def _parse_prompt_version(value: str) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        digits = "".join(ch for ch in str(value or "") if ch.isdigit())
        return int(digits or "0")


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
        """Revise the most recent prompt for a topic using LLM and user feedback."""
        prompts = self.repository.list_topic_prompts(topic_id, limit=1)
        if not prompts:
            raise ValueError(f"No prompt found for topic {topic_id}")
        existing = prompts[0]

        revised = self._get_reviser().revise(existing, feedback, activated_by=activated_by)
        self.repository.create_topic_prompt_version(revised)
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

        prompts = self.repository.list_topic_prompts(topic_id, limit=1)
        next_version = _parse_prompt_version(prompts[0].prompt_version) + 1 if prompts else 1

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

        current_version = _parse_prompt_version(active.prompt_version)
        next_version = current_version + 1

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
