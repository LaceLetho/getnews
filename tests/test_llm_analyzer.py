"""
LLM分析器测试

测试四步分析流程的实现。
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
from crypto_news_analyzer.analyzers.llm_analyzer import LLMAnalyzer
from crypto_news_analyzer.analyzers.market_snapshot_service import MarketSnapshot
from crypto_news_analyzer.analyzers.structured_output_manager import (
    StructuredAnalysisResult,
    BatchAnalysisResult
)
from crypto_news_analyzer.models import ContentItem


@pytest.fixture
def mock_content_items():
    """创建模拟内容项"""
    return [
        ContentItem(
            id="test1",
            title="比特币突破50000美元",
            content="比特币价格今日突破50000美元大关，创下新高。",
            url="https://example.com/news/1",
            publish_time=datetime(2024, 1, 1, 12, 0),
            source_name="测试源1",
            source_type="rss"
        ),
        ContentItem(
            id="test2",
            title="以太坊升级完成",
            content="以太坊成功完成最新升级，网络性能显著提升。",
            url="https://example.com/news/2",
            publish_time=datetime(2024, 1, 1, 13, 0),
            source_name="测试源2",
            source_type="x"
        ),
        ContentItem(
            id="test3",
            title="SEC批准比特币ETF",
            content="美国证券交易委员会批准首个比特币现货ETF。",
            url="https://example.com/news/3",
            publish_time=datetime(2024, 1, 1, 14, 0),
            source_name="测试源3",
            source_type="rss"
        )
    ]


@pytest.fixture
def mock_market_snapshot():
    """创建模拟市场快照"""
    return MarketSnapshot(
        content="当前市场处于上涨趋势，投资者情绪乐观。",
        timestamp=datetime(2024, 1, 1, 10, 0),
        source="mock",
        quality_score=0.85,
        is_valid=True
    )


class TestLLMAnalyzer:
    """LLM分析器测试类"""
    
    def test_initialization_mock_mode(self):
        """测试模拟模式初始化"""
        analyzer = LLMAnalyzer(mock_mode=True)
        
        assert analyzer.mock_mode is True
        assert analyzer.market_snapshot_service is not None
        assert analyzer.structured_output_manager is not None
    
    def test_initialization_with_api_keys(self):
        """测试使用API密钥初始化"""
        analyzer = LLMAnalyzer(
            api_key="test_api_key",
            GROK_API_KEY="test_grok_key",
            mock_mode=False
        )
        
        assert analyzer.api_key == "test_api_key"
        assert analyzer.GROK_API_KEY == "test_grok_key"
    
    def test_get_market_snapshot_mock_mode(self):
        """测试获取市场快照（模拟模式）"""
        analyzer = LLMAnalyzer(mock_mode=True)
        
        snapshot = analyzer.get_market_snapshot(use_cached=False)
        
        assert snapshot is not None
        assert snapshot.source == "mock"
        assert snapshot.is_valid is True
        assert len(snapshot.content) > 0
    
    def test_get_market_snapshot_caching(self):
        """测试市场快照缓存"""
        analyzer = LLMAnalyzer(mock_mode=True)
        
        # 第一次获取
        snapshot1 = analyzer.get_market_snapshot(use_cached=False)
        
        # 第二次获取（使用缓存）
        snapshot2 = analyzer.get_market_snapshot(use_cached=True)
        
        # 应该是同一个对象
        assert snapshot1 is snapshot2
    
    def test_merge_prompts_with_snapshot(self, mock_market_snapshot):
        """测试合并提示词"""
        analyzer = LLMAnalyzer(mock_mode=True)
        
        system_prompt = analyzer.merge_prompts_with_snapshot(mock_market_snapshot)
        
        assert system_prompt is not None
        assert len(system_prompt) > 0
        assert mock_market_snapshot.content in system_prompt
        assert "${Grok_Summary_Here}" not in system_prompt
    
    def test_build_user_prompt(self, mock_content_items):
        """测试构建用户提示词"""
        analyzer = LLMAnalyzer(mock_mode=True)
        
        user_prompt = analyzer.build_user_prompt(mock_content_items)
        
        assert user_prompt is not None
        assert len(user_prompt) > 0
        assert "比特币突破50000美元" in user_prompt
        assert "以太坊升级完成" in user_prompt
        assert "SEC批准比特币ETF" in user_prompt
    
    def test_analyze_content_batch_mock_mode(self, mock_content_items):
        """测试批量分析（模拟模式）"""
        analyzer = LLMAnalyzer(mock_mode=True)
        
        results = analyzer.analyze_content_batch(mock_content_items)
        
        assert isinstance(results, list)
        # 模拟模式会过滤部分内容
        assert len(results) <= len(mock_content_items)
        
        # 验证结果格式
        for result in results:
            assert isinstance(result, StructuredAnalysisResult)
            assert result.time is not None
            assert result.category is not None
            assert 0 <= result.weight_score <= 100
            assert result.summary is not None
            assert result.source is not None
    
    def test_analyze_content_batch_empty_list(self):
        """测试批量分析空列表"""
        analyzer = LLMAnalyzer(mock_mode=True)
        
        results = analyzer.analyze_content_batch([])
        
        assert results == []
    
    def test_get_dynamic_categories(self):
        """测试提取动态分类"""
        analyzer = LLMAnalyzer(mock_mode=True)
        
        mock_results = [
            StructuredAnalysisResult(
                time="2024-01-01 12:00",
                category="Whale",
                weight_score=85,
                title="测试1",

                body="测试1",
                source="https://example.com/1"
            ),
            StructuredAnalysisResult(
                time="2024-01-01 13:00",
                category="Fed",
                weight_score=90,
                title="测试2",

                body="测试2",
                source="https://example.com/2"
            ),
            StructuredAnalysisResult(
                time="2024-01-01 14:00",
                category="Whale",
                weight_score=75,
                title="测试3",

                body="测试3",
                source="https://example.com/3"
            )
        ]
        
        categories = analyzer.get_dynamic_categories(mock_results)
        
        assert isinstance(categories, list)
        assert len(categories) == 2
        assert "Whale" in categories
        assert "Fed" in categories
    
    def test_should_ignore_content(self):
        """测试内容过滤"""
        analyzer = LLMAnalyzer(mock_mode=True)
        
        # 空内容应该被忽略
        assert analyzer.should_ignore_content("") is True
        assert analyzer.should_ignore_content("   ") is True
        
        # 太短的内容应该被忽略
        assert analyzer.should_ignore_content("短") is True
        
        # 正常内容不应该被忽略
        assert analyzer.should_ignore_content("这是一条正常的新闻内容，包含足够的信息。") is False
    
    def test_clear_cache(self):
        """测试清除缓存"""
        analyzer = LLMAnalyzer(mock_mode=True)
        
        # 获取快照以创建缓存
        analyzer.get_market_snapshot(use_cached=False)
        
        # 验证缓存存在
        cache_info = analyzer.get_cache_info()
        assert cache_info["has_cached_snapshot"] is True
        
        # 清除缓存
        analyzer.clear_cache()
        
        # 验证缓存已清除
        cache_info = analyzer.get_cache_info()
        assert cache_info["has_cached_snapshot"] is False
    
    def test_get_cache_info(self):
        """测试获取缓存信息"""
        analyzer = LLMAnalyzer(mock_mode=True)
        
        # 初始状态
        cache_info = analyzer.get_cache_info()
        assert cache_info["has_cached_snapshot"] is False
        assert cache_info["has_cached_prompt"] is False
        
        # 获取快照后
        snapshot = analyzer.get_market_snapshot(use_cached=False)
        cache_info = analyzer.get_cache_info()
        assert cache_info["has_cached_snapshot"] is True
        assert cache_info["snapshot_source"] == "mock"
    
    def test_update_config(self):
        """测试更新配置"""
        analyzer = LLMAnalyzer(mock_mode=True)
        
        # 初始值
        assert analyzer.temperature == 0.1
        assert analyzer.batch_size == 10
        
        # 更新配置
        analyzer.update_config(
            temperature=0.5,
            batch_size=20,
            max_tokens=2000
        )
        
        # 验证更新
        assert analyzer.temperature == 0.5
        assert analyzer.batch_size == 20
        assert analyzer.max_tokens == 2000
    
    def test_handle_empty_batch_response(self):
        """测试处理空批次响应"""
        analyzer = LLMAnalyzer(mock_mode=True)
        
        results = analyzer.handle_empty_batch_response()
        
        assert results == []
    
    def test_classify_content_dynamic_mock_mode(self):
        """测试动态分类单条内容（模拟模式）"""
        analyzer = LLMAnalyzer(mock_mode=True)
        
        result = analyzer.classify_content_dynamic(
            content="比特币价格突破新高",
            market_context="市场处于上涨趋势"
        )
        
        assert isinstance(result, StructuredAnalysisResult)
        assert result.category is not None
        assert 0 <= result.weight_score <= 100
    
    def test_batch_processing_with_multiple_batches(self, mock_content_items):
        """测试多批次处理"""
        analyzer = LLMAnalyzer(mock_mode=True, batch_size=2)
        
        # 创建更多内容项以触发多批次处理
        items = mock_content_items * 3  # 9个项目，批次大小为2
        
        results = analyzer.analyze_content_batch(items)
        
        assert isinstance(results, list)
        # 验证结果数量合理
        assert len(results) <= len(items)


class TestLLMAnalyzerIntegration:
    """LLM分析器集成测试"""
    
    def test_four_step_workflow_mock_mode(self, mock_content_items):
        """测试四步工作流（模拟模式）"""
        analyzer = LLMAnalyzer(mock_mode=True)
        
        # 第一步：获取市场快照
        snapshot = analyzer.get_market_snapshot(use_cached=False)
        assert snapshot is not None
        assert snapshot.is_valid is True
        
        # 第二步：合并提示词
        system_prompt = analyzer.merge_prompts_with_snapshot(snapshot)
        assert system_prompt is not None
        assert snapshot.content in system_prompt
        
        # 第三步和第四步：批量分析
        results = analyzer.analyze_content_batch(mock_content_items, use_cached_snapshot=True)
        assert isinstance(results, list)
        
        # 验证结果
        for result in results:
            assert isinstance(result, StructuredAnalysisResult)
            assert result.category is not None
            assert 0 <= result.weight_score <= 100
    
    def test_dynamic_category_extraction(self, mock_content_items):
        """测试动态分类提取"""
        analyzer = LLMAnalyzer(mock_mode=True)
        
        # 分析内容
        results = analyzer.analyze_content_batch(mock_content_items)
        
        # 提取分类
        categories = analyzer.get_dynamic_categories(results)
        
        # 验证分类是动态的（不硬编码）
        assert isinstance(categories, list)
        assert len(categories) > 0
        
        # 验证所有结果的分类都在提取的分类列表中
        for result in results:
            assert result.category in categories


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
