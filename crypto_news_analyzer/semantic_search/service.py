"""Semantic-search orchestration service."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Sequence

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

from crypto_news_analyzer.config.llm_registry import (
    LLMConfig,
    ModelConfig,
    ResolvedModelRuntime,
    resolve_model_runtime,
)
from crypto_news_analyzer.domain.repositories import ContentRepository
from crypto_news_analyzer.models import ContentItem, SemanticSearchConfig
from crypto_news_analyzer.semantic_search.embedding_service import EmbeddingService

if TYPE_CHECKING:
    from crypto_news_analyzer.semantic_search.report_builder import (
        SemanticSearchReportBuilder,
    )


@dataclass
class SemanticSearchMatch:
    item: ContentItem
    best_similarity: float
    matched_subqueries: List[str] = field(default_factory=list)


class SemanticSearchService:
    """Orchestrates semantic search planning, retrieval, and compact synthesis."""

    def __init__(
        self,
        *,
        content_repository: ContentRepository,
        embedding_service: EmbeddingService,
        semantic_search_config: SemanticSearchConfig,
        llm_config: LLMConfig,
        provider_credentials: Optional[Dict[str, str]] = None,
        client: Optional[Any] = None,
        model_runtime: Optional[ResolvedModelRuntime] = None,
        report_builder: Optional["SemanticSearchReportBuilder"] = None,
        query_planner_prompt_path: str = "./prompts/semantic_search_query_planner.md",
        report_prompt_path: str = "./prompts/semantic_search_report.md",
    ):
        self.content_repository = content_repository
        self.embedding_service = embedding_service
        self.semantic_search_config = semantic_search_config
        self.llm_config = llm_config
        self.model_runtime = model_runtime or resolve_model_runtime(llm_config.model)
        self.provider_credentials = {
            "grok": "",
            "kimi": "",
            "opencode-go": "",
        }
        for provider, value in (provider_credentials or {}).items():
            self.provider_credentials[provider] = (value or "").strip()

        self.query_planner_prompt_path = Path(query_planner_prompt_path)
        self.report_prompt_path = Path(report_prompt_path)
        if report_builder is None:
            from crypto_news_analyzer.semantic_search.report_builder import (
                SemanticSearchReportBuilder,
            )

            report_builder = SemanticSearchReportBuilder()
        self.report_builder = report_builder
        self.logger = logging.getLogger(__name__)
        self.client = client
        if self.client is None:
            api_key = self.provider_credentials.get(
                self.model_runtime.provider_name, ""
            )
            if api_key and OpenAI is not None:
                self.client = self._build_client(self.model_runtime, api_key)

    @classmethod
    def from_llm_config_payload(
        cls,
        *,
        content_repository: ContentRepository,
        embedding_service: EmbeddingService,
        semantic_search_config: SemanticSearchConfig,
        llm_config_payload: Dict[str, Any],
        provider_credentials: Optional[Dict[str, str]] = None,
        client: Optional[Any] = None,
        report_builder: Optional["SemanticSearchReportBuilder"] = None,
        query_planner_prompt_path: str = "./prompts/semantic_search_query_planner.md",
        report_prompt_path: str = "./prompts/semantic_search_report.md",
    ) -> "SemanticSearchService":
        model = llm_config_payload.get("model", {})
        fallback_models = llm_config_payload.get("fallback_models", [])
        market_model = llm_config_payload.get("market_model", model)
        llm_config = LLMConfig(
            model=ModelConfig(**model),
            fallback_models=[ModelConfig(**item) for item in fallback_models],
            market_model=ModelConfig(**market_model),
            temperature=llm_config_payload.get("temperature", 0.5),
            max_tokens=llm_config_payload.get("max_tokens", 4000),
            batch_size=llm_config_payload.get("batch_size", 10),
            market_prompt_path=llm_config_payload.get(
                "market_prompt_path", "./prompts/market_summary_prompt.md"
            ),
            analysis_prompt_path=llm_config_payload.get(
                "analysis_prompt_path", "./prompts/analysis_prompt.md"
            ),
            min_weight_score=llm_config_payload.get("min_weight_score", 50),
            cache_ttl_minutes=llm_config_payload.get("cache_ttl_minutes", 240),
            cached_messages_hours=llm_config_payload.get("cached_messages_hours", 24),
            enable_debug_logging=llm_config_payload.get("enable_debug_logging", False),
        )
        return cls(
            content_repository=content_repository,
            embedding_service=embedding_service,
            semantic_search_config=semantic_search_config,
            llm_config=llm_config,
            provider_credentials=provider_credentials,
            client=client,
            report_builder=report_builder,
            query_planner_prompt_path=query_planner_prompt_path,
            report_prompt_path=report_prompt_path,
        )

    def search(self, *, query: str, time_window_hours: int) -> Dict[str, Any]:
        validated_query = self._validate_request(
            query=query, time_window_hours=time_window_hours
        )
        normalized_intent, subqueries = self._plan_subqueries(validated_query)
        since_time = datetime.now(timezone.utc) - timedelta(hours=time_window_hours)

        merged_matches = self._retrieve_matches(
            subqueries=subqueries, since_time=since_time, max_hours=time_window_hours
        )
        ranked_matches = self._rank_matches(merged_matches)
        matched_count = len(ranked_matches)
        retained_matches = ranked_matches[
            : self.semantic_search_config.max_retained_items
        ]
        retained_count = len(retained_matches)

        if not retained_matches:
            report_content = self.report_builder.build_no_match(
                normalized_intent=normalized_intent,
                original_query=validated_query,
                time_window_hours=time_window_hours,
            )
            return {
                "success": True,
                "report_content": report_content,
                "normalized_intent": normalized_intent,
                "matched_count": 0,
                "retained_count": 0,
                "subqueries": subqueries,
            }

        batch_summaries = self._summarize_in_batches(
            query=validated_query,
            normalized_intent=normalized_intent,
            retained_matches=retained_matches,
            time_window_hours=time_window_hours,
        )
        report_content = self._reduce_to_report(
            query=validated_query,
            normalized_intent=normalized_intent,
            time_window_hours=time_window_hours,
            matched_count=matched_count,
            retained_count=retained_count,
            retained_matches=retained_matches,
            batch_summaries=batch_summaries,
        )
        return {
            "success": True,
            "report_content": report_content,
            "normalized_intent": normalized_intent,
            "matched_count": matched_count,
            "retained_count": retained_count,
            "subqueries": subqueries,
        }

    def _validate_request(self, *, query: str, time_window_hours: int) -> str:
        normalized_query = str(query or "").strip()
        if not normalized_query:
            raise ValueError("query is required")
        if len(normalized_query) > self.semantic_search_config.query_max_chars:
            raise ValueError(
                f"query exceeds max length {self.semantic_search_config.query_max_chars}"
            )
        if time_window_hours <= 0:
            raise ValueError("time_window_hours must be positive")
        if not self.embedding_service.enabled:
            raise ValueError("embedding service is unavailable")
        return normalized_query

    def _plan_subqueries(self, query: str) -> tuple[str, List[str]]:
        normalized_intent = query
        subqueries = [query]

        try:
            prompt = self._load_prompt(self.query_planner_prompt_path)
            user_prompt = prompt.replace("{{QUERY}}", query).replace(
                "{{MAX_SUBQUERIES}}", str(self.semantic_search_config.max_subqueries)
            )
            response_text = self._llm_complete(
                [
                    {
                        "role": "system",
                        "content": "你是语义检索查询规划器，只输出JSON。",
                    },
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
            )
            planned_payload = json.loads(response_text)
            normalized_intent = (
                str(planned_payload.get("normalized_intent") or query).strip() or query
            )
            planned_subqueries = planned_payload.get("subqueries") or []
            if isinstance(planned_subqueries, list):
                subqueries = [
                    str(item).strip()
                    for item in planned_subqueries
                    if str(item).strip()
                ]
        except Exception as exc:
            self.logger.warning("语义搜索查询规划失败，回退原始查询: %s", exc)

        final_subqueries = self._dedupe_subqueries(query=query, candidates=subqueries)
        return normalized_intent, final_subqueries

    def _dedupe_subqueries(self, *, query: str, candidates: Sequence[str]) -> List[str]:
        unique: List[str] = []
        seen = set()

        for candidate in [query, *candidates]:
            normalized = str(candidate or "").strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            unique.append(normalized)
            if len(unique) >= self.semantic_search_config.max_subqueries:
                break

        if query not in seen:
            unique = [query, *unique[: self.semantic_search_config.max_subqueries - 1]]

        return unique[: self.semantic_search_config.max_subqueries]

    def _retrieve_matches(
        self,
        *,
        subqueries: Sequence[str],
        since_time: datetime,
        max_hours: int,
    ) -> Dict[str, SemanticSearchMatch]:
        merged: Dict[str, SemanticSearchMatch] = {}

        for subquery in subqueries:
            embedding = self.embedding_service.generate_embedding(subquery)
            if embedding is None:
                self.logger.warning("子查询Embedding生成失败，跳过: %s", subquery)
                continue

            rows = self.content_repository.semantic_search_by_similarity(
                query_embedding=embedding,
                since_time=since_time,
                max_hours=max_hours,
                limit=self.semantic_search_config.per_subquery_limit,
            )
            for item, similarity in rows:
                existing = merged.get(item.id)
                if existing is None:
                    merged[item.id] = SemanticSearchMatch(
                        item=item,
                        best_similarity=float(similarity),
                        matched_subqueries=[subquery],
                    )
                    continue

                existing.best_similarity = max(
                    existing.best_similarity, float(similarity)
                )
                if subquery not in existing.matched_subqueries:
                    existing.matched_subqueries.append(subquery)

        return merged

    def _rank_matches(
        self, matches: Dict[str, SemanticSearchMatch]
    ) -> List[SemanticSearchMatch]:
        def _publish_time(match: SemanticSearchMatch) -> datetime:
            publish_time = match.item.publish_time
            if publish_time.tzinfo is None:
                return publish_time.replace(tzinfo=timezone.utc)
            return publish_time.astimezone(timezone.utc)

        return sorted(
            matches.values(),
            key=lambda match: (match.best_similarity, _publish_time(match)),
            reverse=True,
        )

    def _summarize_in_batches(
        self,
        *,
        query: str,
        normalized_intent: str,
        retained_matches: Sequence[SemanticSearchMatch],
        time_window_hours: int,
    ) -> List[str]:
        summaries: List[str] = []
        batch_size = self.semantic_search_config.synthesis_batch_size

        for index in range(0, len(retained_matches), batch_size):
            batch = retained_matches[index : index + batch_size]
            self.logger.info(
                "处理语义搜索摘要批次 %s，包含 %s 条内容",
                index // batch_size + 1,
                len(batch),
            )
            batch_prompt = self._build_batch_prompt(
                query=query,
                normalized_intent=normalized_intent,
                time_window_hours=time_window_hours,
                batch=batch,
            )
            try:
                summaries.append(
                    self._llm_complete(
                        [
                            {"role": "system", "content": "你是语义检索批次摘要助手。"},
                            {"role": "user", "content": batch_prompt},
                        ]
                    ).strip()
                )
            except Exception as exc:
                self.logger.warning("语义搜索批次摘要失败，使用降级摘要: %s", exc)
                summaries.append(self._build_fallback_batch_summary(batch))

        return summaries

    def _reduce_to_report(
        self,
        *,
        query: str,
        normalized_intent: str,
        time_window_hours: int,
        matched_count: int,
        retained_count: int,
        retained_matches: Sequence[SemanticSearchMatch],
        batch_summaries: Sequence[str],
    ) -> str:
        source_refs = [
            (f"S{index}", match.item)
            for index, match in enumerate(retained_matches, start=1)
        ]
        sources = self.report_builder.sources_from_items(source_refs)
        draft_report = ""

        try:
            prompt = self._load_prompt(self.report_prompt_path)
            user_prompt = self._build_report_prompt(
                prompt_template=prompt,
                query=query,
                normalized_intent=normalized_intent,
                time_window_hours=time_window_hours,
                matched_count=matched_count,
                retained_count=retained_count,
                batch_summaries=batch_summaries,
                retained_matches=retained_matches,
            )
            draft_report = self._llm_complete(
                [
                    {"role": "system", "content": "你是语义检索综合报告助手。"},
                    {"role": "user", "content": user_prompt},
                ]
            )
        except Exception as exc:
            self.logger.warning("语义搜索最终归纳失败，使用降级报告: %s", exc)
            draft_report = self._build_fallback_final_summary(retained_matches)

        conclusion_lines, signal_lines = self._extract_sections(draft_report)
        return self.report_builder.build(
            normalized_intent=normalized_intent,
            original_query=query,
            time_window_hours=time_window_hours,
            matched_count=matched_count,
            retained_count=retained_count,
            conclusion_lines=conclusion_lines,
            signal_lines=signal_lines,
            sources=sources,
        )

    def _build_batch_prompt(
        self,
        *,
        query: str,
        normalized_intent: str,
        time_window_hours: int,
        batch: Sequence[SemanticSearchMatch],
    ) -> str:
        lines = [
            f"主题: {query}",
            f"归一化意图: {normalized_intent}",
            f"时间窗口: {time_window_hours} 小时",
            "请提炼该批次内容的关键事实、重复信号、分歧点，并保留来源引用标记。",
            "",
        ]
        for index, match in enumerate(batch, start=1):
            lines.extend(
                [
                    f"[{index}] 标题: {match.item.title}",
                    f"[{index}] 内容: {match.item.content}",
                    f"[{index}] 来源: {match.item.source_name} | {match.item.url}",
                    f"[{index}] 发布时间: {match.item.publish_time.isoformat()}",
                    f"[{index}] 相似度: {match.best_similarity:.4f}",
                    f"[{index}] 命中子查询: {', '.join(match.matched_subqueries)}",
                    "",
                ]
            )
        return "\n".join(lines).strip()

    def _build_report_prompt(
        self,
        *,
        prompt_template: str,
        query: str,
        normalized_intent: str,
        time_window_hours: int,
        matched_count: int,
        retained_count: int,
        batch_summaries: Sequence[str],
        retained_matches: Sequence[SemanticSearchMatch],
    ) -> str:
        source_lines = []
        for index, match in enumerate(retained_matches, start=1):
            source_lines.append(
                (
                    f"[S{index}] {match.item.source_name} | {match.item.title} | "
                    f"{match.item.url} | {match.item.publish_time.isoformat()} | score={match.best_similarity:.4f}"
                )
            )
        return (
            prompt_template.replace("{{QUERY}}", query)
            .replace("{{NORMALIZED_INTENT}}", normalized_intent)
            .replace("{{TIME_WINDOW_HOURS}}", str(time_window_hours))
            .replace("{{MATCHED_COUNT}}", str(matched_count))
            .replace("{{RETAINED_COUNT}}", str(retained_count))
            .replace(
                "{{BATCH_SUMMARIES}}", "\n\n".join(batch_summaries).strip() or "无"
            )
            .replace("{{SOURCES}}", "\n".join(source_lines).strip() or "无")
        )

    def _extract_sections(self, draft_report: str) -> tuple[List[str], List[str]]:
        conclusions: List[str] = []
        signals: List[str] = []
        current: Optional[List[str]] = None

        for raw_line in draft_report.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("## 核心结论"):
                current = conclusions
                continue
            if line.startswith("## 关键信号"):
                current = signals
                continue
            if line.startswith("## 来源"):
                current = None
                continue
            if current is None:
                continue
            normalized = line[2:].strip() if line.startswith(("- ", "* ")) else line
            if normalized:
                current.append(normalized)

        if not conclusions and draft_report.strip():
            first_nonempty_line = next(
                (line.strip() for line in draft_report.splitlines() if line.strip()), ""
            )
            if first_nonempty_line:
                conclusions.append(first_nonempty_line)

        return conclusions, signals

    def _build_fallback_batch_summary(
        self, batch: Sequence[SemanticSearchMatch]
    ) -> str:
        return "\n".join(
            f"- {match.item.title} [{match.item.source_name}] ({match.item.url})"
            for match in batch[:5]
        )

    def _build_fallback_final_summary(
        self, retained_matches: Sequence[SemanticSearchMatch]
    ) -> str:
        top_matches = list(retained_matches[:5])
        conclusion_lines = [
            f"- {match.item.title} [S{index}]"
            for index, match in enumerate(top_matches, start=1)
        ]
        signal_lines = [
            f"- {match.item.source_name} 在 {match.item.publish_time.isoformat()} 提到：{match.item.title} [S{index}]"
            for index, match in enumerate(top_matches, start=1)
        ]
        return "\n".join(
            ["## 核心结论", *conclusion_lines, "", "## 关键信号", *signal_lines]
        )

    def _load_prompt(self, path: Path) -> str:
        return path.read_text(encoding="utf-8")

    def _llm_complete(
        self,
        messages: Sequence[Dict[str, str]],
        response_format: Optional[Dict[str, str]] = None,
    ) -> str:
        if self.client is None:
            raise RuntimeError("LLM client is unavailable")

        params: Dict[str, Any] = {
            "model": self.model_runtime.name,
            "messages": list(messages),
            "temperature": self.llm_config.temperature,
            "max_tokens": self.llm_config.max_tokens,
        }
        if response_format is not None:
            params["response_format"] = response_format

        response = self.client.chat.completions.create(**params)
        return str(response.choices[0].message.content or "")

    def _build_client(self, runtime: ResolvedModelRuntime, api_key: str):
        if OpenAI is None:
            raise RuntimeError("openai package is not installed")

        default_headers = dict(runtime.provider.default_headers)

        client_kwargs: Dict[str, Any] = {
            "api_key": api_key,
            "base_url": runtime.provider.base_url,
        }
        if default_headers:
            client_kwargs["default_headers"] = default_headers
        return OpenAI(**client_kwargs)
