"""LLM-based convergence for similar intelligence topics."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from types import ModuleType
from typing import Any, Dict, List, Optional, Tuple, cast

from ..config.llm_registry import ModelConfig, ResolvedModelRuntime, resolve_model_runtime
from ..domain.models import IntelligenceTopic, IntelligenceTopicRunLog
from .topics import build_topic_embedding_text

_openai_module: Optional[ModuleType]
try:
    import openai as _openai_module
except ImportError:
    _openai_module = None

OpenAI: Any = getattr(_openai_module, "OpenAI", None)

logger = logging.getLogger(__name__)

PROMPT_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0.0"
DEFAULT_PROMPT_PATH = Path("prompts/topic_convergence_prompt.md")
DEFAULT_GUIDED_PROMPT_PATH = Path("prompts/topic_guided_convergence_prompt.md")

CONVERGENCE_AUTO_MERGE_THRESHOLD = 0.88
MAX_CONVERGENCE_PAIRS_PER_RUN = 5
GUIDED_TARGET_TOPIC_COUNT = 9

_prompt_cache: Dict[str, str] = {}
_JSON_FENCE_PATTERN = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)


class TopicConverger:
    def __init__(
        self,
        intelligence_repository: Any,
        search_service: Any = None,
        config: Optional[Dict[str, Any]] = None,
        prompt_path: Path = DEFAULT_PROMPT_PATH,
        guided_prompt_path: Path = DEFAULT_GUIDED_PROMPT_PATH,
    ):
        self._repo = intelligence_repository
        self._search = search_service
        self._config = dict(config or {})
        self._similarity_threshold = float(
            self._config.get("convergence_similarity_threshold", CONVERGENCE_AUTO_MERGE_THRESHOLD)
        )
        self._max_pairs_per_run = int(
            self._config.get("max_convergence_pairs_per_run", MAX_CONVERGENCE_PAIRS_PER_RUN)
        )
        self._guided_target_topic_count = int(
            self._config.get("guided_convergence_target_topic_count", GUIDED_TARGET_TOPIC_COUNT)
        )
        self.prompt_path = Path(prompt_path)
        self.guided_prompt_path = Path(guided_prompt_path)
        self._cached_prompt: Optional[str] = None
        self._cached_guided_prompt: Optional[str] = None
        self._provider = str(self._config.get("provider", "opencode-go"))
        self._model_name = str(self._config.get("model", "deepseek-v4-pro"))
        self._thinking_level = str(self._config.get("thinking_level", "high"))
        self._conversation_id = self._build_deterministic_conversation_id()
        self.client: Any = None
        api_key = os.getenv("OPENCODE_API_KEY", "").strip()
        if api_key and OpenAI is not None:
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
            previous_count = int(latest.details.get("active_topic_count_after", current_count))

        if latest and current_count <= previous_count:
            self._write_run_log(
                "converge",
                "skipped",
                None,
                f"No increase: current={current_count}, previous={previous_count}",
                {
                    "active_topic_count_before": previous_count,
                    "active_topic_count_after": current_count,
                },
            )
            return {"merged_count": 0, "skipped": True, "reason": "no_increase"}

        return self._run_convergence(current_count)

    def run_convergence(
        self,
        user_objective: Optional[str] = None,
        target_topic_count: Optional[int] = None,
    ) -> Dict[str, Any]:
        current_count = self._repo.count_topics(is_active=True)
        objective = str(user_objective or "").strip()
        if objective:
            return self._run_guided_convergence(
                current_count=current_count,
                user_objective=objective,
                target_topic_count=target_topic_count,
            )
        return self._run_convergence(current_count)

    def _run_guided_convergence(
        self,
        current_count: int,
        user_objective: str,
        target_topic_count: Optional[int] = None,
    ) -> Dict[str, Any]:
        if self.client is None:
            return {"merged_count": 0, "skipped": True, "reason": "no_client"}

        topics = self._repo.list_topics(is_active=True, limit=200, offset=0)
        if len(topics) < 2:
            self._write_run_log(
                "converge",
                "skipped",
                None,
                "Not enough active topics",
                {
                    "mode": "guided",
                    "user_objective": user_objective,
                    "active_topic_count_after": current_count,
                },
            )
            return {"merged_count": 0, "skipped": True, "reason": "not_enough_topics"}

        target_count = self._normalize_target_topic_count(target_topic_count)
        try:
            plan = self._llm_plan_guided_convergence(topics, user_objective, target_count)
        except Exception:
            logger.exception("Guided topic convergence planning failed")
            self._write_run_log(
                "converge",
                "failed",
                None,
                "Guided convergence planning failed",
                {
                    "mode": "guided",
                    "user_objective": user_objective,
                    "active_topic_count_before": len(topics),
                    "target_topic_count": target_count,
                },
            )
            return {"merged_count": 0, "skipped": True, "reason": "planning_failed"}

        merged_count = 0
        skipped_groups = 0
        merged_topic_ids: set[str] = set()
        topics_by_id = {topic.id: topic for topic in topics}
        groups = plan.get("merge_groups") or []
        for group in groups:
            try:
                merged_in_group = self._apply_guided_merge_group(
                    group=group,
                    topics_by_id=topics_by_id,
                    already_merged=merged_topic_ids,
                    user_objective=user_objective,
                )
                if merged_in_group > 0:
                    merged_count += merged_in_group
                else:
                    skipped_groups += 1
            except Exception:
                logger.exception("Guided topic convergence group failed")
                skipped_groups += 1

        self._write_run_log(
            "converge",
            "success",
            None,
            f"Guided convergence merged {merged_count} topics, skipped {skipped_groups} groups",
            {
                "mode": "guided",
                "user_objective": user_objective,
                "target_topic_count": target_count,
                "active_topic_count_before": len(topics),
                "active_topic_count_after": max(0, current_count - merged_count),
                "merged_count": merged_count,
                "skipped_groups": skipped_groups,
                "plan_reason": plan.get("reason", ""),
            },
        )
        return {
            "merged_count": merged_count,
            "skipped": False,
            "mode": "guided",
            "target_topic_count": target_count,
            "skipped_groups": skipped_groups,
        }

    def _run_convergence(self, current_count: int) -> Dict[str, Any]:
        topics = self._repo.list_topics(is_active=True, limit=200, offset=0)
        if len(topics) < 2:
            self._write_run_log(
                "converge",
                "skipped",
                None,
                "Not enough active topics",
                {"active_topic_count_after": current_count},
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
            "converge",
            "success",
            None,
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
                logger.debug("Topic similarity search failed for %s", topic.id, exc_info=True)
        pairs.sort(key=lambda x: x[2], reverse=True)
        return pairs[: self._max_pairs_per_run]

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
        return self._parse_json_response(response)

    def _llm_plan_guided_convergence(
        self,
        topics: List[IntelligenceTopic],
        user_objective: str,
        target_topic_count: int,
    ) -> Dict[str, Any]:
        prompt = self._load_guided_prompt()
        topic_payload = []
        for topic in topics:
            topic_payload.append(
                {
                    "id": topic.id,
                    "name": topic.name,
                    "description": topic.description,
                    "enriched_summary": topic.enriched_summary,
                    "source_channels": topic.source_channels[:10],
                    "methods": topic.methods,
                    "vulnerabilities": topic.vulnerabilities,
                    "latest_findings": topic.latest_findings[:8],
                    "entry_count": self._repo.count_entries_by_topic(topic.id),
                }
            )
        user_input = json.dumps(
            {
                "user_objective": user_objective,
                "target_topic_count": target_topic_count,
                "current_active_topic_count": len(topics),
                "topics": topic_payload,
            },
            ensure_ascii=False,
        )
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": user_input},
        ]
        response = self.client.chat.completions.create(
            model=self._model_name,
            messages=messages,
            max_tokens=8000,
            response_format={"type": "json_object"},
            extra_body=self._build_extra_body(),
        )
        try:
            return self._parse_json_response(response)
        except ValueError as exc:
            logger.warning("Guided convergence JSON parse failed, retrying: %s", exc)

        retry_messages = messages + [
            {
                "role": "user",
                "content": (
                    "上一次响应不是合法 JSON。请只返回一个严格 JSON 对象，"
                    "不要输出 Markdown、解释文本或代码块。"
                ),
            }
        ]
        retry_response = self.client.chat.completions.create(
            model=self._model_name,
            messages=retry_messages,
            max_tokens=8000,
            response_format={"type": "json_object"},
            extra_body={},
        )
        return self._parse_json_response(retry_response)

    def _parse_json_response(self, response: Any) -> Dict[str, Any]:
        message = response.choices[0].message
        content = getattr(message, "content", "") or ""
        if isinstance(content, list):
            content = "".join(
                str(item.get("text", item)) if isinstance(item, dict) else str(item)
                for item in content
            )
        text = str(content).strip()
        if not text:
            raise ValueError("LLM returned empty message.content")

        match = _JSON_FENCE_PATTERN.search(text)
        if match:
            text = match.group(1).strip()
        elif not text.startswith("{"):
            start = text.find("{")
            end = text.rfind("}")
            if start >= 0 and end > start:
                text = text[start : end + 1]

        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            snippet = text[:500].replace("\n", "\\n")
            raise ValueError(f"LLM returned invalid JSON: {exc}; content={snippet}") from exc
        if not isinstance(parsed, dict):
            raise ValueError("LLM JSON response must be an object")
        return cast(Dict[str, Any], parsed)

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
        keeper.enriched_summary = str(result.get("merged_summary", keeper.enriched_summary or ""))
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

    def _apply_guided_merge_group(
        self,
        group: Dict[str, Any],
        topics_by_id: Dict[str, IntelligenceTopic],
        already_merged: set[str],
        user_objective: str,
    ) -> int:
        raw_ids = group.get("topic_ids") or group.get("merged_topic_ids") or []
        topic_ids = [
            str(topic_id)
            for topic_id in raw_ids
            if str(topic_id) in topics_by_id and str(topic_id) not in already_merged
        ]
        topic_ids = list(dict.fromkeys(topic_ids))
        if len(topic_ids) < 2:
            return 0

        keeper_id = str(group.get("keeper_topic_id") or "").strip()
        if keeper_id not in topic_ids:
            keeper_id = self._choose_guided_keeper(topic_ids, topics_by_id)
        keeper = topics_by_id[keeper_id]
        merged_ids = [topic_id for topic_id in topic_ids if topic_id != keeper_id]

        for topic_id in merged_ids:
            merged = topics_by_id[topic_id]
            entries = self._repo.list_entries_by_topic(merged.id, limit=1000, offset=0)
            for entry in entries:
                self._repo.assign_entry_to_topic(entry.id, keeper.id)
            merged.is_active = False
            merged.updated_at = datetime.utcnow()
            self._repo.save_topic(merged)
            already_merged.add(merged.id)

        keeper.name = str(group.get("merged_name") or keeper.name)
        keeper.description = str(group.get("merged_description") or keeper.description or "")
        keeper.enriched_summary = str(group.get("merged_summary") or keeper.enriched_summary or "")
        keeper.source_channels = group.get("merged_source_channels") or keeper.source_channels
        keeper.methods = str(group.get("merged_methods") or keeper.methods or "")
        keeper.vulnerabilities = str(
            group.get("merged_vulnerabilities") or keeper.vulnerabilities or ""
        )
        keeper.latest_findings = group.get("merged_latest_findings") or keeper.latest_findings
        keeper.updated_at = datetime.utcnow()

        self._repo.save_topic(keeper)
        self._regenerate_topic_embedding(keeper)
        self._write_run_log(
            "converge",
            "success",
            keeper.id,
            f"Guided merge into {keeper.name}",
            {
                "mode": "guided",
                "keeper_id": keeper.id,
                "merged_ids": merged_ids,
                "user_objective": user_objective,
                "reason": group.get("reason", ""),
            },
        )
        return len(merged_ids)

    def _choose_guided_keeper(
        self,
        topic_ids: List[str],
        topics_by_id: Dict[str, IntelligenceTopic],
    ) -> str:
        def sort_key(topic_id: str) -> Tuple[int, datetime]:
            topic = topics_by_id[topic_id]
            created_at = topic.created_at or datetime.min
            return (self._repo.count_entries_by_topic(topic.id), created_at)

        return max(topic_ids, key=sort_key)

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

    def _load_guided_prompt(self) -> str:
        if self._cached_guided_prompt is not None:
            return self._cached_guided_prompt
        cache_key = str(self.guided_prompt_path.resolve())
        if cache_key in _prompt_cache:
            self._cached_guided_prompt = _prompt_cache[cache_key]
            return self._cached_guided_prompt
        content = self.guided_prompt_path.read_text(encoding="utf-8")
        _prompt_cache[cache_key] = content
        self._cached_guided_prompt = content
        return content

    def _normalize_target_topic_count(self, target_topic_count: Optional[int]) -> int:
        value = (
            int(target_topic_count)
            if target_topic_count is not None
            else self._guided_target_topic_count
        )
        return min(20, max(2, value))

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
