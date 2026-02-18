"""
LLM分析器缓存集成测试

测试LLM分析器与缓存管理器的集成，验证提示词中的${outdated_news}占位符替换功能。
"""

import pytest
import tempfile
import os
from datetime import datetime
from pathlib import Path

from crypto_news_analyzer.analyzers.llm_analyzer import LLMAnalyzer
from crypto_news_analyzer.storage.cache_manager import SentMessageCacheManager
from crypto_news_analyzer.models import StorageConfig


class TestLLMAnalyzerCacheIntegration:
    """LLM分析器缓存集成测试"""
    
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
                'category': 'MarketTrend',
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
        assert 'MarketTrend' in formatted
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
    
    def test_user_prompt_contains_outdated_news_with_data(self):
        """测试用户提示词包含Outdated News部分（有缓存数据）"""
        from crypto_news_analyzer.analyzers.market_snapshot_service import MarketSnapshot
        from crypto_news_analyzer.models import ContentItem
        
        # 先缓存一些消息
        messages = [
            {
                'title': '比特币价格突破50000美元',
                'body': '市场情绪高涨',
                'category': 'MarketTrend',
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
        
        user_prompt = self.analyzer._build_user_prompt_with_context(items, snapshot)
        
        # 验证用户提示词包含市场快照
        assert "# Current Market Context" in user_prompt
        assert "当前市场处于震荡状态" in user_prompt
        
        # 验证用户提示词包含格式化的缓存消息
        assert "# Outdated News" in user_prompt
        assert "比特币价格突破50000美元" in user_prompt
        assert "SEC批准比特币ETF" in user_prompt
        assert "MarketTrend" in user_prompt
        assert "Regulation" in user_prompt
    
    def test_complete_prompt_structure_with_cache(self):
        """测试完整的提示词结构（系统提示词 + 用户提示词）"""
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
        user_prompt = self.analyzer._build_user_prompt_with_context(items, snapshot)
        
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


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
