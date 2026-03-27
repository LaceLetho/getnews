"""
LLM分析器缓存集成测试

测试LLM分析器与缓存管理器的集成，验证提示词中的${outdated_news}占位符替换功能。
"""

import os
import sqlite3
import tempfile
from datetime import datetime, timedelta, timezone
from typing import Optional, cast

import pytest

from crypto_news_analyzer.analyzers.llm_analyzer import LLMAnalyzer
from crypto_news_analyzer.storage.cache_manager import SentMessageCacheManager
from crypto_news_analyzer.models import StorageConfig


class TestLLMAnalyzerCacheIntegration:
    """LLM分析器缓存集成测试"""

    temp_dir: str = ""
    db_path: str = ""
    storage_config: StorageConfig = cast(StorageConfig, object())
    cache_manager: SentMessageCacheManager = cast(SentMessageCacheManager, object())
    analyzer: LLMAnalyzer = cast(LLMAnalyzer, object())

    def _insert_cached_message(
        self,
        *,
        title: str,
        sent_at: datetime,
        recipient_key: Optional[str] = None,
        body: str = "报告正文",
        category: str = "Digest",
        time: str = "2024-01-15 10:30",
    ) -> None:
        connection = sqlite3.connect(self.db_path)
        try:
            _ = connection.execute(
                """
                INSERT INTO sent_message_cache
                    (title, body, category, time, sent_at, recipient_key)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    title,
                    body,
                    category,
                    time,
                    sent_at.astimezone(timezone.utc).isoformat(),
                    recipient_key,
                ),
            )
            connection.commit()
        finally:
            connection.close()
    
    def setup_method(self):
        """测试前设置"""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_cache.db")
        self.storage_config = StorageConfig(
            retention_days=30,
            max_storage_mb=1000,
            cleanup_frequency="daily",
            database_path=self.db_path
        )
        self.cache_manager = SentMessageCacheManager(self.storage_config)
        
        # 创建LLM分析器（模拟模式）
        self.analyzer = LLMAnalyzer(
            mock_mode=True,
            cache_manager=self.cache_manager
        )
    
    def teardown_method(self):
        """测试后清理"""
        if hasattr(self, 'cache_manager'):
            self.cache_manager.close()
        
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        
        if os.path.exists(self.temp_dir):
            os.rmdir(self.temp_dir)
    
    def test_analyzer_with_cache_manager(self):
        """测试分析器集成缓存管理器"""
        assert self.analyzer.cache_manager is not None
        assert isinstance(self.analyzer.cache_manager, SentMessageCacheManager)
    
    def test_analyzer_without_cache_manager(self):
        """测试分析器不使用缓存管理器"""
        analyzer = LLMAnalyzer(mock_mode=True)
        assert analyzer.cache_manager is None
    
    def test_analyzer_with_storage_config(self):
        """测试通过storage_config创建缓存管理器"""
        analyzer = LLMAnalyzer(
            mock_mode=True,
            storage_config=self.storage_config
        )
        assert analyzer.cache_manager is not None
    
    def test_get_formatted_cached_messages_empty(self):
        """测试获取空缓存的格式化消息"""
        formatted = self.analyzer._get_formatted_cached_messages()
        assert formatted == "无"
    
    def test_get_formatted_cached_messages_with_data(self):
        """测试获取有数据的格式化消息"""
        # 先缓存一些消息
        messages = [
            {
                'title': '比特币价格突破50000美元',
                'body': '市场情绪高涨',
                'category': 'BlackSwan',
                'time': '2024-01-15 10:30'
            },
            {
                'title': 'SEC批准比特币ETF',
                'body': '监管环境改善',
                'category': 'Regulation',
                'time': '2024-01-15 11:00'
            }
        ]
        self.cache_manager.cache_sent_messages(messages)
        
        formatted = self.analyzer._get_formatted_cached_messages()
        
        assert formatted != "无"
        assert '比特币价格突破50000美元' in formatted
        assert 'SEC批准比特币ETF' in formatted
        assert 'BlackSwan' in formatted
        assert 'Regulation' in formatted
    
    def test_static_system_prompt_no_placeholders_empty_cache(self):
        """测试静态系统提示词不包含占位符（空缓存）"""
        from crypto_news_analyzer.analyzers.market_snapshot_service import MarketSnapshot
        
        # 创建模拟市场快照
        snapshot = MarketSnapshot(
            content="当前市场处于震荡状态",
            timestamp=datetime.now(),
            source="mock",
            quality_score=1.0,
            is_valid=True
        )
        
        system_prompt = self.analyzer._build_static_system_prompt()
        
        # 验证静态系统提示词不包含占位符
        assert "${outdated_news}" not in system_prompt
        assert "${Grok_Summary_Here}" not in system_prompt
    
    def test_scheduled_user_prompt_contains_outdated_news_with_cached_global_data(self):
        from crypto_news_analyzer.analyzers.market_snapshot_service import MarketSnapshot
        from crypto_news_analyzer.models import ContentItem
        
        # 先缓存一些消息
        messages = [
            {
                'title': '比特币价格突破50000美元',
                'body': '市场情绪高涨',
                'category': 'BlackSwan',
                'time': '2024-01-15 10:30'
            },
            {
                'title': 'SEC批准比特币ETF',
                'body': '监管环境改善',
                'category': 'Regulation',
                'time': '2024-01-15 11:00'
            }
        ]
        self.cache_manager.cache_sent_messages(messages)
        
        # 创建模拟市场快照
        snapshot = MarketSnapshot(
            content="当前市场处于震荡状态",
            timestamp=datetime.now(),
            source="mock",
            quality_score=1.0,
            is_valid=True
        )
        
        items = [
            ContentItem(
                id="test1",
                title="新测试新闻",
                content="新测试内容",
                url="https://example.com/new",
                publish_time=datetime.now(),
                source_name="test",
                source_type="rss"
            )
        ]
        
        user_prompt = self.analyzer._build_user_prompt_with_context(
            items,
            snapshot,
            is_scheduled=True,
        )
        
        # 验证用户提示词包含市场快照
        assert "# Current Market Context" in user_prompt
        assert "当前市场处于震荡状态" in user_prompt
        
        # 验证用户提示词包含格式化的缓存消息
        assert "# Outdated News" in user_prompt
        assert "比特币价格突破50000美元" in user_prompt
        assert "SEC批准比特币ETF" in user_prompt
        assert "BlackSwan" in user_prompt
        assert "Regulation" in user_prompt
    
    def test_scheduled_prompt_structure_with_cached_global_data(self):
        from crypto_news_analyzer.analyzers.market_snapshot_service import MarketSnapshot
        from crypto_news_analyzer.models import ContentItem
        
        # 先缓存一些消息
        messages = [
            {
                'title': '某交易所遭受黑客攻击',
                'body': '安全事件影响市场',
                'category': 'Security',
                'time': '2024-01-15 12:00'
            }
        ]
        self.cache_manager.cache_sent_messages(messages)
        
        # 创建模拟市场快照
        snapshot = MarketSnapshot(
            content="当前市场处于震荡状态",
            timestamp=datetime.now(),
            source="mock",
            quality_score=1.0,
            is_valid=True
        )
        
        items = [
            ContentItem(
                id="test1",
                title="新闻标题",
                content="新闻内容",
                url="https://example.com/news",
                publish_time=datetime.now(),
                source_name="test",
                source_type="rss"
            )
        ]
        
        # 构建系统提示词和用户提示词
        system_prompt = self.analyzer._build_static_system_prompt()
        user_prompt = self.analyzer._build_user_prompt_with_context(
            items,
            snapshot,
            is_scheduled=True,
        )
        
        # 验证系统提示词是静态的
        assert "${Grok_Summary_Here}" not in system_prompt
        assert "${outdated_news}" not in system_prompt
        
        # 验证用户提示词包含所有动态内容
        assert "# Current Market Context" in user_prompt
        assert "当前市场处于震荡状态" in user_prompt
        assert "# Outdated News" in user_prompt
        assert "某交易所遭受黑客攻击" in user_prompt
        assert "新闻标题" in user_prompt
    
    def test_analyzer_without_cache_manager_returns_none(self):
        """测试没有缓存管理器时返回'无'"""
        analyzer = LLMAnalyzer(mock_mode=True)
        
        formatted = analyzer._get_formatted_cached_messages()
        assert formatted == "无"
    
    def test_cache_manager_error_handling(self):
        """测试缓存管理器错误处理"""
        # 关闭缓存管理器以模拟错误
        self.cache_manager.close()
        
        # 应该返回"无"而不是抛出异常
        formatted = self.analyzer._get_formatted_cached_messages()
        assert formatted == "无"

    def test_recipient_scoped_cached_titles_isolate_recipients(self):
        anchor_time = datetime(2026, 3, 27, 12, 0, tzinfo=timezone.utc)

        self._insert_cached_message(
            title="API 用户报告 A",
            sent_at=anchor_time - timedelta(hours=2),
            recipient_key="api:42",
        )
        self._insert_cached_message(
            title="Telegram 用户报告 B",
            sent_at=anchor_time - timedelta(hours=1),
            recipient_key="telegram:1001",
        )
        self._insert_cached_message(
            title="Legacy 全局报告",
            sent_at=anchor_time - timedelta(hours=3),
            recipient_key=None,
        )

        assert self.cache_manager.get_recipient_cached_titles(
            recipient_key="api:42",
            anchor_time=anchor_time,
        ) == ["API 用户报告 A"]
        assert self.cache_manager.get_recipient_cached_titles(
            recipient_key="telegram:1001",
            anchor_time=anchor_time,
        ) == ["Telegram 用户报告 B"]

    def test_recipient_scoped_cached_titles_use_inclusive_utc_window(self):
        anchor_time = datetime(2026, 3, 27, 12, 0, tzinfo=timezone.utc)
        window_start = anchor_time - timedelta(hours=48)

        self._insert_cached_message(
            title="窗口起点",
            sent_at=window_start,
            recipient_key="api:42",
        )
        self._insert_cached_message(
            title="窗口终点",
            sent_at=anchor_time,
            recipient_key="api:42",
        )
        self._insert_cached_message(
            title="窗口前一秒",
            sent_at=window_start - timedelta(seconds=1),
            recipient_key="api:42",
        )
        self._insert_cached_message(
            title="窗口后一秒",
            sent_at=anchor_time + timedelta(seconds=1),
            recipient_key="api:42",
        )

        assert self.cache_manager.get_recipient_cached_titles(
            recipient_key="api:42",
            anchor_time=anchor_time,
        ) == ["窗口起点", "窗口终点"]

    def test_recipient_scoped_cached_titles_are_deterministically_ordered(self):
        anchor_time = datetime(2026, 3, 27, 12, 0, tzinfo=timezone.utc)

        self._insert_cached_message(
            title="第三条",
            sent_at=anchor_time - timedelta(hours=1),
            recipient_key="telegram:9001",
        )
        self._insert_cached_message(
            title="第一条",
            sent_at=anchor_time - timedelta(hours=3),
            recipient_key="telegram:9001",
        )
        self._insert_cached_message(
            title="第二条",
            sent_at=anchor_time - timedelta(hours=2),
            recipient_key="telegram:9001",
        )

        assert self.cache_manager.get_recipient_cached_titles(
            recipient_key="telegram:9001",
            anchor_time=anchor_time,
        ) == ["第一条", "第二条", "第三条"]

    def test_cached_prompt_formatting_keeps_legacy_global_rows(self):
        self._insert_cached_message(
            title="旧全局标题",
            sent_at=datetime.now(timezone.utc),
            recipient_key=None,
            category="Legacy",
            time="2026-03-27 12:00",
        )
        self._insert_cached_message(
            title="手动收件人标题",
            sent_at=datetime.now(timezone.utc),
            recipient_key="api:42",
            category="Manual",
            time="2026-03-27 12:05",
        )

        formatted = self.cache_manager.format_cached_messages_for_prompt(hours=24)

        assert formatted == "- [2026-03-27 12:00] [Legacy] 旧全局标题"

    def test_manual_historical_titles_render_in_prompt(self):
        """手动调用时传入historical_titles，应渲染到# Outdated News"""
        from crypto_news_analyzer.analyzers.market_snapshot_service import MarketSnapshot
        from crypto_news_analyzer.models import ContentItem

        snapshot = MarketSnapshot(
            content="当前市场处于震荡状态",
            timestamp=datetime.now(),
            source="mock",
            quality_score=1.0,
            is_valid=True
        )

        items = [
            ContentItem(
                id="test1",
                title="新测试新闻",
                content="新测试内容",
                url="https://example.com/new",
                publish_time=datetime.now(),
                source_name="test",
                source_type="rss"
            )
        ]

        historical_titles = ["历史报告标题A", "历史报告标题B"]

        user_prompt = self.analyzer._build_user_prompt_with_context(
            items,
            snapshot,
            is_scheduled=False,
            historical_titles=historical_titles,
        )

        assert "# Outdated News" in user_prompt
        assert "历史报告标题A" in user_prompt
        assert "历史报告标题B" in user_prompt

    def test_manual_empty_historical_titles_shows_none(self):
        """手动调用时传入空historical_titles列表，应显示'无'"""
        from crypto_news_analyzer.analyzers.market_snapshot_service import MarketSnapshot
        from crypto_news_analyzer.models import ContentItem

        snapshot = MarketSnapshot(
            content="当前市场处于震荡状态",
            timestamp=datetime.now(),
            source="mock",
            quality_score=1.0,
            is_valid=True
        )

        items = [
            ContentItem(
                id="test1",
                title="新测试新闻",
                content="新测试内容",
                url="https://example.com/new",
                publish_time=datetime.now(),
                source_name="test",
                source_type="rss"
            )
        ]

        user_prompt = self.analyzer._build_user_prompt_with_context(
            items,
            snapshot,
            is_scheduled=False,
            historical_titles=[],
        )

        assert "# Outdated News" in user_prompt
        assert "无" in user_prompt

    def test_manual_historical_titles_duplicate_collapse(self):
        """手动调用时传入重复historical_titles，应去重只保留一个"""
        from crypto_news_analyzer.analyzers.market_snapshot_service import MarketSnapshot
        from crypto_news_analyzer.models import ContentItem

        snapshot = MarketSnapshot(
            content="当前市场处于震荡状态",
            timestamp=datetime.now(),
            source="mock",
            quality_score=1.0,
            is_valid=True
        )

        items = [
            ContentItem(
                id="test1",
                title="新测试新闻",
                content="新测试内容",
                url="https://example.com/new",
                publish_time=datetime.now(),
                source_name="test",
                source_type="rss"
            )
        ]

        historical_titles = ["重复标题", "重复标题", "唯一标题", "重复标题"]

        user_prompt = self.analyzer._build_user_prompt_with_context(
            items,
            snapshot,
            is_scheduled=False,
            historical_titles=historical_titles,
        )

        assert "# Outdated News" in user_prompt
        assert "重复标题" in user_prompt
        # 重复标题应该只出现一次
        count = user_prompt.count("重复标题")
        assert count == 1, f"重复标题出现了{count}次，期望1次"
        assert "唯一标题" in user_prompt

    def test_scheduled_outdated_news_unchanged_with_historical_titles(self):
        """is_scheduled=True时仍使用全局缓存，historical_titles被忽略"""
        from crypto_news_analyzer.analyzers.market_snapshot_service import MarketSnapshot
        from crypto_news_analyzer.models import ContentItem

        # 先缓存一些消息
        messages = [
            {
                'title': '全局缓存标题',
                'body': '全局缓存内容',
                'category': 'Global',
                'time': '2024-01-15 10:30'
            }
        ]
        self.cache_manager.cache_sent_messages(messages)

        snapshot = MarketSnapshot(
            content="当前市场处于震荡状态",
            timestamp=datetime.now(),
            source="mock",
            quality_score=1.0,
            is_valid=True
        )

        items = [
            ContentItem(
                id="test1",
                title="新测试新闻",
                content="新测试内容",
                url="https://example.com/new",
                publish_time=datetime.now(),
                source_name="test",
                source_type="rss"
            )
        ]

        # 传入historical_titles但is_scheduled=True，应该使用全局缓存
        user_prompt = self.analyzer._build_user_prompt_with_context(
            items,
            snapshot,
            is_scheduled=True,
            historical_titles=["手动历史标题"],
        )

        assert "# Outdated News" in user_prompt
        assert "全局缓存标题" in user_prompt
        # is_scheduled=True时不应该渲染historical_titles
        assert "手动历史标题" not in user_prompt


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
