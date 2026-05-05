"""
Token使用情况追踪器

记录最近50次LLM调用的token使用情况，用于优化cache命中率。
"""

import logging
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List, Dict, Any
from ..utils.timezone_utils import now_utc8, format_datetime_utc8


@dataclass
class TokenUsageRecord:
    """单次LLM调用的token使用记录"""
    timestamp: datetime
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cached_tokens: int = 0  # 缓存命中的token数
    conversation_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'timestamp': format_datetime_utc8(self.timestamp),
            'model': self.model,
            'prompt_tokens': self.prompt_tokens,
            'completion_tokens': self.completion_tokens,
            'total_tokens': self.total_tokens,
            'cached_tokens': self.cached_tokens,
            'cache_hit_rate': f"{self.cache_hit_rate:.1%}" if self.prompt_tokens > 0 else "0.0%",
            'conversation_id': self.conversation_id
        }

    @property
    def cache_hit_rate(self) -> float:
        """计算缓存命中率"""
        if self.prompt_tokens == 0:
            return 0.0
        return self.cached_tokens / self.prompt_tokens


class TokenUsageTracker:
    """Token使用情况追踪器"""

    def __init__(self, max_records: int = 50):
        """
        初始化追踪器

        Args:
            max_records: 最多保存的记录数
        """
        self.max_records = max_records
        self.records: deque[TokenUsageRecord] = deque(maxlen=max_records)
        self.logger = logging.getLogger(__name__)

    def record_usage(
        self,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: int,
        cached_tokens: int = 0,
        conversation_id: Optional[str] = None
    ) -> None:
        """
        记录一次LLM调用的token使用情况

        Args:
            model: 模型名称
            prompt_tokens: 提示词token数
            completion_tokens: 完成token数
            total_tokens: 总token数
            cached_tokens: 缓存命中的token数
            conversation_id: 会话ID
        """
        record = TokenUsageRecord(
            timestamp=now_utc8(),
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            cached_tokens=cached_tokens,
            conversation_id=conversation_id
        )
        self.records.append(record)

        self.logger.debug(
            f"记录token使用: model={model}, total={total_tokens}, "
            f"cached={cached_tokens}, hit_rate={record.cache_hit_rate:.1%}"
        )

    def get_recent_records(self, count: Optional[int] = None) -> List[TokenUsageRecord]:
        """
        获取最近的记录

        Args:
            count: 获取的记录数，None表示全部

        Returns:
            记录列表（从新到旧）
        """
        if count is None:
            return list(reversed(self.records))
        return list(reversed(self.records))[:count]

    def get_statistics(self) -> Dict[str, Any]:
        """
        获取统计信息

        Returns:
            统计信息字典
        """
        if not self.records:
            return {
                'total_calls': 0,
                'total_tokens': 0,
                'total_cached_tokens': 0,
                'avg_cache_hit_rate': 0.0,
                'total_prompt_tokens': 0,
                'total_completion_tokens': 0
            }

        total_calls = len(self.records)
        total_tokens = sum(r.total_tokens for r in self.records)
        total_cached = sum(r.cached_tokens for r in self.records)
        total_prompt = sum(r.prompt_tokens for r in self.records)
        total_completion = sum(r.completion_tokens for r in self.records)

        avg_hit_rate = total_cached / total_prompt if total_prompt > 0 else 0.0

        return {
            'total_calls': total_calls,
            'total_tokens': total_tokens,
            'total_cached_tokens': total_cached,
            'avg_cache_hit_rate': avg_hit_rate,
            'total_prompt_tokens': total_prompt,
            'total_completion_tokens': total_completion
        }

    def format_summary(self) -> str:
        """
        格式化摘要信息（用于Telegram显示）

        Returns:
            格式化的摘要文本
        """
        stats = self.get_statistics()

        if stats['total_calls'] == 0:
            return "📊 Token使用统计\n\n暂无记录"

        lines = [
            "📊 Token使用统计",
            "",
            f"总调用次数: {stats['total_calls']}",
            f"总Token数: {stats['total_tokens']:,}",
            f"缓存Token数: {stats['total_cached_tokens']:,}",
            f"平均缓存命中率: {stats['avg_cache_hit_rate']:.1%}",
            f"提示词Token: {stats['total_prompt_tokens']:,}",
            f"完成Token: {stats['total_completion_tokens']:,}",
        ]

        return "\n".join(lines)

    def format_recent_records(self, count: int = 10) -> str:
        """
        格式化最近的记录（用于Telegram显示）

        Args:
            count: 显示的记录数

        Returns:
            格式化的记录文本
        """
        records = self.get_recent_records(count)

        if not records:
            return "暂无记录"

        lines = [f"📝 最近{len(records)}次调用:"]
        lines.append("")

        for i, record in enumerate(records, 1):
            time_str = format_datetime_utc8(record.timestamp, format_str='%m-%d %H:%M')
            lines.append(
                f"{i}. {time_str} | {record.model}\n"
                f"   Total: {record.total_tokens:,} | "
                f"Cached: {record.cached_tokens:,} | "
                f"Hit: {record.cache_hit_rate:.1%}"
            )

        return "\n".join(lines)

    def clear(self) -> None:
        """清除所有记录"""
        self.records.clear()
        self.logger.info("已清除所有token使用记录")
