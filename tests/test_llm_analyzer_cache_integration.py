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
                'summary': '比特币价格突破50000美元',
                'category': 'MarketTrend',
                'time': '2024-01-15 10:30'
            },
            {
                'summary': 'SEC批准比特币ETF',
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
    
    def test_merge_prompts_replaces_outdated_news_empty(self):
        """测试合并提示词时替换${outdated_news}占位符（空缓存）"""
        from crypto_news_analyzer.analyzers.market_snapshot_service import MarketSnapshot
        
        # 创建模拟市场快照
        snapshot = MarketSnapshot(
            content="当前市场处于震荡状态",
            timestamp=datetime.now(),
            source="mock",
            quality_score=1.0,
            is_valid=True
        )
        
        system_prompt = self.analyzer.merge_prompts_with_snapshot(snapshot)
        
        # 验证${outdated_news}被替换为"无"
        assert "${outdated_news}" not in system_prompt
        assert "# Outdated News\n无" in system_prompt
    
    def test_merge_prompts_replaces_outdated_news_with_data(self):
        """测试合并提示词时替换${outdated_news}占位符（有缓存数据）"""
        from crypto_news_analyzer.analyzers.market_snapshot_service import MarketSnapshot
        
        # 先缓存一些消息
        messages = [
            {
                'summary': '比特币价格突破50000美元',
                'category': 'MarketTrend',
                'time': '2024-01-15 10:30'
            },
            {
                'summary': 'SEC批准比特币ETF',
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
        
        system_prompt = self.analyzer.merge_prompts_with_snapshot(snapshot)
        
        # 验证${outdated_news}被替换为格式化的缓存消息
        assert "${outdated_news}" not in system_prompt
        assert "比特币价格突破50000美元" in system_prompt
        assert "SEC批准比特币ETF" in system_prompt
        assert "MarketTrend" in system_prompt
        assert "Regulation" in system_prompt
        
        # 验证格式正确
        assert "- [2024-01-15 10:30] [MarketTrend]" in system_prompt
        assert "- [2024-01-15 11:00] [Regulation]" in system_prompt
    
    def test_build_system_prompt_with_cache(self):
        """测试build_system_prompt方法集成缓存"""
        from crypto_news_analyzer.analyzers.market_snapshot_service import MarketSnapshot
        
        # 先缓存一些消息
        messages = [
            {
                'summary': '某交易所遭受黑客攻击',
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
        
        system_prompt = self.analyzer.build_system_prompt(snapshot)
        
        # 验证两个占位符都被替换
        assert "${Grok_Summary_Here}" not in system_prompt
        assert "${outdated_news}" not in system_prompt
        assert "当前市场处于震荡状态" in system_prompt
        assert "某交易所遭受黑客攻击" in system_prompt
    
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
