"""LLM-based enrichment for followed intelligence topics."""
from __future__ import annotations

import hashlib
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..config.llm_registry import ModelConfig, ResolvedModelRuntime, resolve_model_runtime
from ..domain.models import IntelligenceTopic, IntelligenceTopicRunLog
from .topics import build_topic_embedding_text

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

logger = logging.getLogger(__name__)

PROMPT_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0.0"
DEFAULT_PROMPT_PATH = Path("prompts/topic_enrichment_prompt.md")

MIN_NEW_EVIDENCE = 3
MAX_EVIDENCE_PER_RUN = 15
INITIAL_MAX_EVIDENCE = 20
RAW_TEXT_MAX_CHARS = 1000
MIN_ENRICH_INTERVAL_HOURS = 24

_prompt_cache: Dict[str, str] = {}


class TopicEnricher:
    def __init__(
        self,
        intelligence_repository: Any,
        search_service: Any = None,
        config: Optional[Dict[str, Any]] = None,
        prompt_path: Path = DEFAULT_PROMPT_PATH,
    ):
        self._repo = intelligence_repository
        self._search = search_service
        self._config = dict(config or {})
        self._enabled = bool(self._config.get("enabled", True))
        self._min_new_evidence = int(self._config.get("min_new_evidence", MIN_NEW_EVIDENCE))
        self._max_evidence_per_run = int(
            self._config.get("max_evidence_per_run", MAX_EVIDENCE_PER_RUN)
        )
        self._initial_max_evidence = int(
            self._config.get("initial_max_evidence", INITIAL_MAX_EVIDENCE)
        )
        self._raw_text_max_chars = int(
            self._config.get("raw_text_max_chars", RAW_TEXT_MAX_CHARS)
        )
        self._min_enrich_interval_hours = int(
            self._config.get("min_enrich_interval_hours", MIN_ENRICH_INTERVAL_HOURS)
        )
        self.prompt_path = Path(prompt_path)
        self._cached_prompt: Optional[str] = None
        self._provider = str(self._config.get("provider", "opencode-go"))
        self._model_name = str(self._config.get("model", "deepseek-v4-pro"))
        self._thinking_level = str(self._config.get("thinking_level", "high"))
        self._conversation_id = self._build_deterministic_conversation_id()
        self.client: Any = None
        api_key = os.getenv("OPENCODE_API_KEY", "").strip()
        if api_key and OpenAI:
            self.client = self._build_client(api_key)

    def _build_deterministic_conversation_id(self) -> str:
        seed = f"topic_enrich:{self._model_name}:{PROMPT_VERSION}"
        return hashlib.sha256(seed.encode()).hexdigest()[:16]

    def _build_client(self, api_key: str):
        if OpenAI is None:
            raise RuntimeError("openai package is not installed")
        runtime = self._resolve_runtime()
        default_headers = dict(runtime.provider.default_headers)
        conversation_header = runtime.provider.conversation_header_name
        if conversation_header:
            default_headers[conversation_header] = self._conversation_id
        kwargs: Dict[str, Any] = {
            "api_key": api_key,
            "base_url": runtime.provider.base_url,
        }
        if default_headers:
            kwargs["default_headers"] = default_headers
        return OpenAI(**kwargs)

    def _resolve_runtime(self) -> ResolvedModelRuntime:
        return resolve_model_runtime(
            ModelConfig(
                provider=self._provider,
                name=self._model_name,
                options={"thinking_level": self._thinking_level},
            )
        )

    def enrich_due_topics(self) -> int:
        if not self._enabled or self.client is None:
            return 0

        topics = self._repo.list_topics(is_active=True, limit=100, offset=0)
        enriched_count = 0
        for topic in topics:
            try:
                if self._should_enrich(topic):
                    self._enrich_topic(topic)
                    enriched_count += 1
            except Exception:
                logger.exception("Topic enrichment failed for %s", topic.id)
                self._write_run_log("enrich", "failed", topic.id, "Enrichment failed")
        return enriched_count

    def _should_enrich(self, topic: IntelligenceTopic) -> bool:
        evidence_limit = (
            self._initial_max_evidence if topic.enriched_at is None else self._max_evidence_per_run
        )
        new_evidence = self._repo.list_new_topic_evidence(
            topic.id, topic.last_evidence_at, evidence_limit
        )
        if not new_evidence:
            return False
        if topic.enriched_at is None:
            return len(new_evidence) >= 1
        hours_since = (
            (datetime.utcnow() - topic.enriched_at.replace(tzinfo=None)).total_seconds() / 3600
            if topic.enriched_at
            else 999
        )
        return len(new_evidence) >= self._min_new_evidence or hours_since >= self._min_enrich_interval_hours

    def _enrich_topic(self, topic: IntelligenceTopic) -> None:
        evidence_limit = (
            self._initial_max_evidence if topic.enriched_at is None else self._max_evidence_per_run
        )
        new_evidence = self._repo.list_new_topic_evidence(
            topic.id, topic.last_evidence_at, evidence_limit
        )
        if not new_evidence:
            return

        prompt = self._load_prompt()
        truncated_evidence: List[Dict[str, Any]] = []
        for ev in new_evidence:
            raw_text = str(ev.get("raw_text") or "")
            truncated = dict(ev)
            truncated["raw_text"] = raw_text[: self._raw_text_max_chars]
            truncated_evidence.append(truncated)

        user_input = json.dumps(
            {
                "current_knowledge": {
                    "name": topic.name,
                    "description": topic.description,
                    "enriched_summary": topic.enriched_summary,
                    "source_channels": topic.source_channels,
                    "methods": topic.methods,
                    "vulnerabilities": topic.vulnerabilities,
                    "latest_findings": topic.latest_findings,
                },
                "new_evidence": [
                    {
                        "display_name": ev.get("display_name"),
                        "entry_type": ev.get("entry_type"),
                        "raw_text": ev.get("raw_text"),
                        "source_type": ev.get("source_type"),
                        "source_url": ev.get("source_url"),
                    }
                    for ev in truncated_evidence
                ],
            },
            ensure_ascii=False,
        )

        response = self.client.chat.completions.create(
            model=self._model_name,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": user_input},
            ],
            max_tokens=4000,
            response_format={"type": "json_object"},
            extra_body=self._build_extra_body(),
        )
        content = response.choices[0].message.content
        result = json.loads(content)

        merged = self._merge_enrichment(topic, result)
        merged.last_evidence_at = max(
            [
                ev.get("observed_at")
                for ev in new_evidence
                if ev.get("observed_at")
            ]
            or [datetime.utcnow()]
        )
        if isinstance(merged.last_evidence_at, str):
            merged.last_evidence_at = datetime.fromisoformat(merged.last_evidence_at)
        merged.enriched_at = datetime.utcnow()
        merged.updated_at = datetime.utcnow()
        self._repo.save_topic(merged)
        self._regenerate_topic_embedding(merged)
        self._write_run_log(
            "enrich", "success", topic.id,
            f"Processed {len(new_evidence)} evidence items",
        )

    def _merge_enrichment(
        self, topic: IntelligenceTopic, result: Dict[str, Any]
    ) -> IntelligenceTopic:
        topic.enriched_summary = str(result.get("enriched_summary", topic.enriched_summary or ""))

        new_channels: List[Dict[str, Any]] = result.get("source_channels") or []
        existing_channels = list(topic.source_channels)
        seen_names = {
            str(ch.get("name", "")).strip().lower() for ch in existing_channels if ch.get("name")
        }
        seen_urls = {
            str(ch.get("url", "")).strip().lower() for ch in existing_channels if ch.get("url")
        }
        for ch in new_channels:
            ch_name = str(ch.get("name", "")).strip().lower()
            ch_url = str(ch.get("url", "")).strip().lower()
            if (ch_name and ch_name in seen_names) or (ch_url and ch_url in seen_urls):
                continue
            if ch_name:
                seen_names.add(ch_name)
            if ch_url:
                seen_urls.add(ch_url)
            existing_channels.append(ch)
        topic.source_channels = existing_channels

        topic.methods = str(result.get("methods", "") or topic.methods or "")
        topic.vulnerabilities = str(
            result.get("vulnerabilities", "") or topic.vulnerabilities or ""
        )

        new_findings: List[str] = result.get("latest_findings") or []
        all_findings = list(topic.latest_findings or [])
        for finding in new_findings:
            finding_str = str(finding).strip()
            if finding_str and finding_str not in all_findings:
                all_findings.append(finding_str)
        topic.latest_findings = all_findings[-20:]
        return topic

    def _regenerate_topic_embedding(self, topic: IntelligenceTopic) -> None:
        if self._search is None:
            return
        try:
            embedding_text = build_topic_embedding_text(topic)
            if not embedding_text:
                return
            embed_service = getattr(self._search, "embedding_service", None)
            if embed_service is None:
                return
            embedding = embed_service.generate_embedding(embedding_text)
            if embedding is None:
                return
            model = str(getattr(embed_service, "model", "") or "").strip()
            if not model:
                return
            self._repo.update_topic_embedding(topic.id, embedding, model)
        except Exception:
            logger.debug("Topic embedding regeneration failed: %s", topic.id, exc_info=True)

    def _load_prompt(self) -> str:
        if self._cached_prompt is not None:
            return self._cached_prompt
        cache_key = str(self.prompt_path.resolve())
        if cache_key in _prompt_cache:
            self._cached_prompt = _prompt_cache[cache_key]
            return self._cached_prompt
        content = self.prompt_path.read_text(encoding="utf-8")
        _prompt_cache[cache_key] = content
        self._cached_prompt = content
        return content

    def _build_extra_body(self) -> Dict[str, Any]:
        if not self._thinking_level or self._thinking_level == "disabled":
            return {}
        if self._provider == "opencode-go" and self._model_name == "deepseek-v4-pro":
            return {"thinking": {"type": "enabled"}}
        return {"thinking": {"type": self._thinking_level}}

    def _write_run_log(
        self,
        run_type: str,
        status: str,
        topic_id: Optional[str],
        message: Optional[str] = None,
    ) -> None:
        try:
            now = datetime.utcnow()
            log_entry = IntelligenceTopicRunLog.create(
                run_type=run_type,
                status=status,
                topic_id=topic_id,
                message=message,
                started_at=now,
                finished_at=now,
            )
            self._repo.save_topic_run_log(log_entry)
        except Exception:
            logger.debug("Failed to write topic run log", exc_info=True)
