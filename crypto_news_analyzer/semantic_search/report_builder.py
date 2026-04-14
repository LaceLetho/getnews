"""Markdown report builder for semantic search responses."""

from __future__ import annotations

from typing import List, Sequence


class SemanticSearchReportBuilder:
    """Builds semantic-search markdown reports for Telegram and API clients."""

    def build(
        self,
        *,
        normalized_intent: str,
        original_query: str,
        time_window_hours: int,
        matched_count: int,
        retained_count: int,
        signal_blocks: Sequence[str],
        no_match: bool = False,
    ) -> str:
        metadata_lines = [
            f"- 归一化意图: {normalized_intent or '未归一化'}",
            f"- 原始查询: {original_query}",
            f"- 时间窗口: {time_window_hours} 小时",
            f"- 匹配条数: {matched_count}",
            f"- 保留条数: {retained_count}",
        ]
        signal_block = self._build_signal_blocks(
            signal_blocks,
            fallback=(
                "现有材料未显示出足够具体的渠道/入口/活动/产品级信号。"
                if no_match
                else "现有材料未显示出足够具体的渠道/入口/活动/产品级信号。"
            ),
        )

        return "\n".join(
            [
                "# 主题检索报告",
                "",
                *metadata_lines,
                "",
                "## 关键信号",
                *signal_block,
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
            signal_blocks=["现有材料未显示出足够具体的渠道/入口/活动/产品级信号。"],
            no_match=True,
        )

    def _build_signal_blocks(self, blocks: Sequence[str], fallback: str) -> List[str]:
        normalized = [block.strip() for block in blocks if block and block.strip()]
        if normalized:
            return self._join_blocks(normalized)
        return self._join_blocks([fallback])

    def _join_blocks(self, blocks: Sequence[str]) -> List[str]:
        lines: List[str] = []
        for index, block in enumerate(blocks):
            if index > 0:
                lines.append("")
            lines.extend(block.splitlines())
        return lines
