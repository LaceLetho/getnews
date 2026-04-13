"""Markdown report builder for semantic search responses."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, List, Sequence

from ..models import ContentItem


def _normalize_publish_time(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


@dataclass(frozen=True)
class ReportSource:
    ref: str
    title: str
    source_name: str
    url: str
    publish_time: datetime


class SemanticSearchReportBuilder:
    """Builds fixed-structure semantic-search markdown reports."""

    def build(
        self,
        *,
        normalized_intent: str,
        original_query: str,
        time_window_hours: int,
        matched_count: int,
        retained_count: int,
        conclusion_lines: Sequence[str],
        signal_lines: Sequence[str],
        sources: Sequence[ReportSource],
        no_match: bool = False,
    ) -> str:
        metadata_lines = [
            f"- 归一化意图: {normalized_intent or '未归一化'}",
            f"- 原始查询: {original_query}",
            f"- 时间窗口: {time_window_hours} 小时",
            f"- 匹配条数: {matched_count}",
            f"- 保留条数: {retained_count}",
        ]
        conclusion_block = self._build_section_lines(
            conclusion_lines,
            fallback="未在指定时间窗口内检索到与主题直接相关的内容。"
            if no_match
            else "未生成核心结论。",
        )
        signal_block = self._build_section_lines(
            signal_lines,
            fallback="暂无可提炼的关键信号。",
        )
        source_block = self._build_sources_block(sources)

        return "\n".join(
            [
                "# 主题检索报告",
                "",
                *metadata_lines,
                "",
                "## 核心结论",
                *conclusion_block,
                "",
                "## 关键信号",
                *signal_block,
                "",
                "## 来源",
                *source_block,
            ]
        ).strip()

    def build_no_match(
        self,
        *,
        normalized_intent: str,
        original_query: str,
        time_window_hours: int,
    ) -> str:
        return self.build(
            normalized_intent=normalized_intent,
            original_query=original_query,
            time_window_hours=time_window_hours,
            matched_count=0,
            retained_count=0,
            conclusion_lines=["未在指定时间窗口内检索到与主题直接相关的内容。"],
            signal_lines=["暂无可提炼的关键信号。"],
            sources=[],
            no_match=True,
        )

    def sources_from_items(
        self, refs_to_items: Iterable[tuple[str, ContentItem]]
    ) -> List[ReportSource]:
        return [
            ReportSource(
                ref=ref,
                title=item.title,
                source_name=item.source_name,
                url=item.url,
                publish_time=item.publish_time,
            )
            for ref, item in refs_to_items
        ]

    def _build_section_lines(self, lines: Sequence[str], fallback: str) -> List[str]:
        normalized = [f"- {line.strip()}" for line in lines if line and line.strip()]
        return normalized or [f"- {fallback}"]

    def _build_sources_block(self, sources: Sequence[ReportSource]) -> List[str]:
        if not sources:
            return ["- 无来源"]

        return [
            (
                f"- [{source.ref}] {source.source_name} | {source.title} | "
                f"{_normalize_publish_time(source.publish_time)} | {source.url}"
            )
            for source in sources
        ]
