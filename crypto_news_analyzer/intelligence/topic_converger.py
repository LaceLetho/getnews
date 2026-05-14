"""LLM-based convergence for similar intelligence topics."""
from __future__ import annotations

import hashlib
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, cast

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
DEFAULT_PROMPT_PATH = Path("prompts/topic_convergence_prompt.md")

CONVERGENCE_AUTO_MERGE_THRESHOLD = 0.88
MAX_CONVERGENCE_PAIRS_PER_RUN = 5

_prompt_cache: Dict[str, str] = {}


class TopicConverger:
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
        self._similarity_threshold = float(
            self._config.get(
                "convergence_similarity_threshold", CONVERGENCE_AUTO_MERGE_THRESHOLD
            )
        )
        self._max_pairs_per_run = int(
            self._config.get("max_convergence_pairs_per_run", MAX_CONVERGENCE_PAIRS_PER_RUN)
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
        seed = f"topic_converge:{self._model_name}:{PROMPT_VERSION}"
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

    def run_daily_if_needed(self) -> Dict[str, Any]:
        if self.client is None:
            return {"merged_count": 0, "skipped": True, "reason": "no_client"}

        latest = self._repo.get_latest_topic_run_log("converge")
        if latest and latest.created_at:
            latest_date = latest.created_at.date() if hasattr(latest.created_at, "date") else None
            if latest_date and latest_date == datetime.utcnow().date():
                return {"merged_count": 0, "skipped": True, "reason": "already_ran_today"}

        current_count = self._repo.count_topics(is_active=True)
        previous_count = current_count
        if latest and latest.details:
            previous_count = int(
                latest.details.get("active_topic_count_after", current_count)
            )

        if latest and current_count <= previous_count:
            self._write_run_log(
                "converge", "skipped", None,
                f"No increase: current={current_count}, previous={previous_count}",
                {"active_topic_count_before": previous_count, "active_topic_count_after": current_count},
            )
            return {"merged_count": 0, "skipped": True, "reason": "no_increase"}

        return self._run_convergence(current_count)

    def run_convergence(self) -> Dict[str, Any]:
        current_count = self._repo.count_topics(is_active=True)
        return self._run_convergence(current_count)

    def _run_convergence(self, current_count: int) -> Dict[str, Any]:
        topics = self._repo.list_topics(is_active=True, limit=200, offset=0)
        if len(topics) < 2:
            self._write_run_log(
                "converge", "skipped", None,
                "Not enough active topics", {"active_topic_count_after": current_count},
            )
            return {"merged_count": 0, "skipped": True, "reason": "not_enough_topics"}

        pairs = self._find_similar_pairs(topics)
        merged_count = 0
        skipped_pairs = 0
        for topic_a, topic_b, similarity in pairs:
            try:
                result = self._llm_confirm_merge(topic_a, topic_b, similarity)
                if result.get("should_merge"):
                    self._merge_topics(topic_a, topic_b, result, similarity)
                    merged_count += 1
                else:
                    skipped_pairs += 1
            except Exception:
                logger.exception("Topic convergence pair failed")
                skipped_pairs += 1

        self._write_run_log(
            "converge", "success", None,
            f"Merged {merged_count} pairs, skipped {skipped_pairs}",
            {
                "active_topic_count_before": len(topics),
                "active_topic_count_after": current_count - merged_count,
                "merged_count": merged_count,
                "skipped_pairs": skipped_pairs,
            },
        )
        return {"merged_count": merged_count, "skipped": False}

    def _find_similar_pairs(
        self, topics: List[IntelligenceTopic]
    ) -> List[Tuple[IntelligenceTopic, IntelligenceTopic, float]]:
        pairs = []
        seen: set = set()
        for i, topic in enumerate(topics):
            if topic.embedding is None:
                continue
            try:
                results = self._repo.semantic_search_topics(
                    topic.embedding, is_active=True, limit=5
                )
                for candidate, score in results:
                    if candidate.id == topic.id:
                        continue
                    if score < self._similarity_threshold:
                        continue
                    pair_key = tuple(sorted([topic.id, candidate.id]))
                    if pair_key in seen:
                        continue
                    seen.add(pair_key)
                    pairs.append((topic, candidate, score))
            except Exception:
                logger.debug(
                    "Topic similarity search failed for %s", topic.id, exc_info=True
                )
        pairs.sort(key=lambda x: x[2], reverse=True)
        return pairs[:self._max_pairs_per_run]

    def _llm_confirm_merge(
        self,
        topic_a: IntelligenceTopic,
        topic_b: IntelligenceTopic,
        similarity: float,
    ) -> Dict[str, Any]:
        prompt = self._load_prompt()
        user_input = json.dumps(
            {
                "similarity": round(similarity, 4),
                "topic_a": {
                    "name": topic_a.name,
                    "description": topic_a.description,
                    "enriched_summary": topic_a.enriched_summary,
                    "source_channels": topic_a.source_channels,
                    "methods": topic_a.methods,
                    "vulnerabilities": topic_a.vulnerabilities,
                    "latest_findings": topic_a.latest_findings,
                    "entry_count": self._repo.count_entries_by_topic(topic_a.id),
                },
                "topic_b": {
                    "name": topic_b.name,
                    "description": topic_b.description,
                    "enriched_summary": topic_b.enriched_summary,
                    "source_channels": topic_b.source_channels,
                    "methods": topic_b.methods,
                    "vulnerabilities": topic_b.vulnerabilities,
                    "latest_findings": topic_b.latest_findings,
                    "entry_count": self._repo.count_entries_by_topic(topic_b.id),
                },
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
        return cast(Dict[str, Any], json.loads(content))

    def _merge_topics(
        self,
        topic_a: IntelligenceTopic,
        topic_b: IntelligenceTopic,
        result: Dict[str, Any],
        similarity: float,
    ) -> None:
        count_a = self._repo.count_entries_by_topic(topic_a.id)
        count_b = self._repo.count_entries_by_topic(topic_b.id)
        keeper, merged = (topic_a, topic_b) if count_a >= count_b else (topic_b, topic_a)

        entries = self._repo.list_entries_by_topic(merged.id, limit=1000, offset=0)
        for entry in entries:
            self._repo.assign_entry_to_topic(entry.id, keeper.id)

        keeper.name = str(result.get("merged_name", keeper.name))
        keeper.description = str(result.get("merged_description", keeper.description or ""))
        keeper.enriched_summary = str(
            result.get("merged_summary", keeper.enriched_summary or "")
        )
        keeper.source_channels = result.get("merged_source_channels") or keeper.source_channels
        keeper.methods = str(result.get("merged_methods", keeper.methods or ""))
        keeper.vulnerabilities = str(
            result.get("merged_vulnerabilities", keeper.vulnerabilities or "")
        )
        keeper.latest_findings = result.get("merged_latest_findings") or keeper.latest_findings
        keeper.updated_at = datetime.utcnow()

        self._repo.save_topic(keeper)
        self._regenerate_topic_embedding(keeper)
        merged.is_active = False
        merged.updated_at = datetime.utcnow()
        self._repo.save_topic(merged)
        self._write_run_log(
            "converge",
            "success",
            keeper.id,
            f"Merged {merged.name} <- {keeper.name}",
            {
                "keeper_id": keeper.id,
                "merged_id": merged.id,
                "similarity": round(similarity, 4),
                "reason": result.get("reason", ""),
            },
        )

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
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        try:
            now = datetime.utcnow()
            log_entry = IntelligenceTopicRunLog.create(
                run_type=run_type,
                status=status,
                topic_id=topic_id,
                message=message,
                details=details or {},
                started_at=now,
                finished_at=now,
            )
            self._repo.save_topic_run_log(log_entry)
        except Exception:
            logger.debug("Failed to write topic run log", exc_info=True)
