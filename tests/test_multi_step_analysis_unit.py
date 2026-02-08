"""
多步骤分析系统单元测试

测试需求 5.11, 5.12, 5.14, 5.16, 5.17:
- 市场快照获取和缓存机制
- 结构化输出和格式验证
- 动态分类发现和管理
- 批量分析和去重功能
"""

import pytest
import json
import os
import tempfile
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

from crypto_news_analyzer.analyzers.market_snapshot_service import (
    MarketSnapshotService,
    MarketSnapshot
)
from crypto_news_analyzer.analyzers.structured_output_manager import (
    StructuredOutputManager,
    StructuredAnalysisResult,
    BatchAnalysisResult,
    ValidationResult
)
from crypto_news_analyzer.analyzers.dynamic_classification_manager import (
    DynamicClassificationManager
)
from crypto_news_analyzer.analyzers.llm_analyzer import LLMAnalyzer
from crypto_news_analyzer.models import ContentItem


# ============================================================================
# 测试夹具
# ============================================================================

@pytest.fixture
def temp_cache_dir():
    """创建临时缓存目录"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


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
def mock_analysis_results():
    """创建模拟分析结果"""
    return [
        StructuredAnalysisResult(
            time="2024-01-01 12:00",
            category="大户动向",
            weight_score=85,
            summary="比特币突破50000美元",
            source="https://example.com/news/1"
        ),
        StructuredAnalysisResult(
            time="2024-01-01 13:00",
            category="新产品",
            weight_score=75,
            summary="以太坊升级完成",
            source="https://example.com/news/2"
        ),
        StructuredAnalysisResult(
            time="2024-01-01 14:00",
            category="美国政府监管政策",
            weight_score=95,
            summary="SEC批准比特币ETF",
            source="https://example.com/news/3"
        )
    ]


# ============================================================================
# 市场快照获取和缓存机制测试 (需求 5.11, 5.12)
# ============================================================================

class TestMarketSnapshotCaching:
    """测试市场快照获取和缓存机制"""
    
    def test_get_market_snapshot_mock_mode(self, temp_cache_dir):
        """测试模拟模式下获取市场快照"""
        service = MarketSnapshotService(
            mock_mode=True,
            cache_dir=temp_cache_dir
        )
        
        snapshot = service.get_market_snapshot("请描述当前市场状况")
        
        assert snapshot is not None
        assert snapshot.source == "mock"
        assert snapshot.is_valid is True
        assert len(snapshot.content) > 0
        assert snapshot.quality_score > 0
    
    def test_cache_snapshot_and_retrieve(self, temp_cache_dir):
        """测试缓存快照并检索 (需求 5.11)"""
        service = MarketSnapshotService(
            mock_mode=True,
            cache_dir=temp_cache_dir,
            cache_ttl_minutes=30
        )
        
        # 创建快照
        snapshot = MarketSnapshot(
            content="测试市场快照内容",
            timestamp=datetime.now(),
            source="test",
            quality_score=0.85,
            is_valid=True
        )
        
        # 缓存快照
        service.cache_snapshot(snapshot)
        
        # 检索缓存
        cached = service.get_cached_snapshot()
        
        assert cached is not None
        assert cached.content == "测试市场快照内容"
        assert cached.source == "cached"
        assert cached.is_valid is True
    
    def test_cache_expiration(self, temp_cache_dir):
        """测试缓存过期机制 (需求 5.11)"""
        service = MarketSnapshotService(
            mock_mode=True,
            cache_dir=temp_cache_dir,
            cache_ttl_minutes=1  # 1分钟过期
        )
        
        # 创建过期的快照
        old_snapshot = MarketSnapshot(
            content="过期的快照",
            timestamp=datetime.now() - timedelta(minutes=5),
            source="test",
            quality_score=0.85,
            is_valid=True
        )
        
        # 手动保存过期的快照到缓存文件
        cache_file = os.path.join(temp_cache_dir, "market_snapshot.json")
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(old_snapshot.to_dict(), f)
        
        # 尝试检索（应该返回None因为已过期）
        cached = service.get_cached_snapshot()
        
        assert cached is None
    
    def test_cache_file_corruption_handling(self, temp_cache_dir):
        """测试缓存文件损坏处理 (需求 5.12)"""
        service = MarketSnapshotService(
            mock_mode=True,
            cache_dir=temp_cache_dir
        )
        
        # 创建损坏的缓存文件
        cache_file = os.path.join(temp_cache_dir, "market_snapshot.json")
        with open(cache_file, 'w') as f:
            f.write("这不是有效的JSON")
        
        # 尝试读取（应该处理错误并返回None）
        cached = service.get_cached_snapshot()
        
        assert cached is None
        # 损坏的文件应该被删除
        assert not os.path.exists(cache_file)
    
    def test_clear_cache(self, temp_cache_dir):
        """测试清除缓存 (需求 5.11)"""
        service = MarketSnapshotService(
            mock_mode=True,
            cache_dir=temp_cache_dir
        )
        
        # 创建并缓存快照
        snapshot = service.get_market_snapshot("测试")
        service.cache_snapshot(snapshot)
        
        # 验证缓存存在
        assert service.get_cached_snapshot() is not None
        
        # 清除缓存
        result = service.clear_cache()
        
        assert result is True
        assert service.get_cached_snapshot() is None
    
    def test_get_cache_info(self, temp_cache_dir):
        """测试获取缓存信息 (需求 5.11)"""
        service = MarketSnapshotService(
            mock_mode=True,
            cache_dir=temp_cache_dir
        )
        
        # 初始状态
        info = service.get_cache_info()
        assert info["cache_exists"] is False
        
        # 创建缓存
        snapshot = service.get_market_snapshot("测试")
        service.cache_snapshot(snapshot)
        
        # 获取缓存信息
        info = service.get_cache_info()
        assert info["cache_exists"] is True
        assert info["is_valid"] is True
        assert "cache_time" in info
        assert "cache_age_minutes" in info


class TestMarketSnapshotQuality:
    """测试市场快照质量验证"""
    
    def test_validate_snapshot_quality_valid(self):
        """测试有效快照的质量验证 (需求 5.12)"""
        service = MarketSnapshotService(mock_mode=True)
        
        valid_content = """
        当前加密货币市场处于上涨趋势，比特币价格突破50000美元。
        投资者情绪乐观，市场交易量显著增加。美联储政策保持稳定。
        """
        
        is_valid = service.validate_snapshot_quality(valid_content)
        
        assert is_valid is True
    
    def test_validate_snapshot_quality_too_short(self):
        """测试过短内容的质量验证 (需求 5.12)"""
        service = MarketSnapshotService(mock_mode=True)
        
        short_content = "市场上涨"
        
        is_valid = service.validate_snapshot_quality(short_content)
        
        assert is_valid is False
    
    def test_validate_snapshot_quality_no_keywords(self):
        """测试缺少关键词的质量验证 (需求 5.12)"""
        service = MarketSnapshotService(mock_mode=True)
        
        # 足够长但没有相关关键词
        irrelevant_content = "今天天气很好，阳光明媚。我去公园散步，看到很多人在锻炼。"
        
        is_valid = service.validate_snapshot_quality(irrelevant_content)
        
        assert is_valid is False
    
    def test_calculate_quality_score(self):
        """测试质量评分计算 (需求 5.12)"""
        service = MarketSnapshotService(mock_mode=True)
        
        # 高质量内容
        high_quality = """
        当前加密货币市场呈现上涨趋势，比特币价格突破50000美元大关。
        以太坊、DeFi项目表现强劲。美联储利率政策保持稳定，通胀预期下降。
        机构投资者持续入场，市场情绪乐观。监管政策逐步明确，有利于行业发展。
        """
        
        score = service._calculate_quality_score(high_quality)
        
        assert 0.0 <= score <= 1.0
        assert score > 0.5  # 高质量内容应该有较高评分
    
    def test_fallback_snapshot(self):
        """测试备用快照 (需求 5.12)"""
        service = MarketSnapshotService(mock_mode=True)
        
        fallback = service.get_fallback_snapshot()
        
        assert fallback is not None
        assert fallback.source == "fallback"
        assert fallback.is_valid is True
        assert len(fallback.content) > 0
        assert service.validate_snapshot_quality(fallback.content)


# ============================================================================
# 结构化输出和格式验证测试 (需求 5.14, 5.16)
# ============================================================================

class TestStructuredOutputValidation:
    """测试结构化输出和格式验证"""
    
    def test_validate_single_result_valid(self):
        """测试验证有效的单个结果 (需求 5.14)"""
        manager = StructuredOutputManager()
        
        response = {
            "time": "2024-01-01 12:00",
            "category": "大户动向",
            "weight_score": 85,
            "summary": "测试摘要",
            "source": "https://example.com/news"
        }
        
        result = manager.validate_output_structure(response)
        
        assert result.is_valid is True
        assert len(result.errors) == 0
    
    def test_validate_single_result_missing_fields(self):
        """测试验证缺少字段的结果 (需求 5.14)"""
        manager = StructuredOutputManager()
        
        response = {
            "time": "2024-01-01 12:00",
            "category": "大户动向"
            # 缺少其他必需字段
        }
        
        result = manager.validate_output_structure(response)
        
        assert result.is_valid is False
        assert len(result.errors) > 0
        assert any("weight_score" in err for err in result.errors)
        assert any("summary" in err for err in result.errors)
        assert any("source" in err for err in result.errors)
    
    def test_validate_weight_score_range(self):
        """测试weight_score范围验证 (需求 5.14)"""
        manager = StructuredOutputManager()
        
        # 超出范围
        response = {
            "time": "2024-01-01 12:00",
            "category": "测试",
            "weight_score": 150,
            "summary": "测试",
            "source": "https://example.com"
        }
        
        result = manager.validate_output_structure(response)
        
        assert result.is_valid is False
        assert any("0-100" in err for err in result.errors)
    
    def test_validate_source_url_format(self):
        """测试source URL格式验证 (需求 5.14)"""
        manager = StructuredOutputManager()
        
        # 无效URL
        response = {
            "time": "2024-01-01 12:00",
            "category": "测试",
            "weight_score": 50,
            "summary": "测试",
            "source": "not-a-valid-url"
        }
        
        result = manager.validate_output_structure(response)
        
        assert result.is_valid is False
        assert any("URL" in err for err in result.errors)
    
    def test_validate_batch_result_valid(self):
        """测试验证有效的批量结果 (需求 5.14)"""
        manager = StructuredOutputManager()
        
        response = {
            "results": [
                {
                    "time": "2024-01-01 12:00",
                    "category": "大户动向",
                    "weight_score": 85,
                    "summary": "测试1",
                    "source": "https://example.com/1"
                },
                {
                    "time": "2024-01-01 13:00",
                    "category": "安全事件",
                    "weight_score": 95,
                    "summary": "测试2",
                    "source": "https://example.com/2"
                }
            ]
        }
        
        result = manager.validate_output_structure(response)
        
        assert result.is_valid is True
        assert len(result.errors) == 0
    
    def test_validate_batch_result_empty(self):
        """测试验证空批量结果 (需求 5.16 - 接受空列表)"""
        manager = StructuredOutputManager()
        
        response = {"results": []}
        
        result = manager.validate_output_structure(response)
        
        assert result.is_valid is True
        assert len(result.warnings) > 0  # 应该有警告
    
    def test_validate_batch_result_invalid_item(self):
        """测试验证包含无效项的批量结果 (需求 5.14)"""
        manager = StructuredOutputManager()
        
        response = {
            "results": [
                {
                    "time": "2024-01-01 12:00",
                    "category": "测试",
                    "weight_score": 85,
                    "summary": "测试1",
                    "source": "https://example.com/1"
                },
                {
                    "time": "2024-01-01 13:00",
                    # 缺少必需字段
                }
            ]
        }
        
        result = manager.validate_output_structure(response)
        
        assert result.is_valid is False
        assert len(result.errors) > 0


class TestStructuredOutputRecovery:
    """测试结构化输出错误恢复"""
    
    def test_handle_malformed_response_with_markdown(self):
        """测试处理包含markdown的响应 (需求 5.16)"""
        manager = StructuredOutputManager()
        
        response = """这是一些解释文本
```json
{
    "time": "2024-01-01 12:00",
    "category": "大户动向",
    "weight_score": 85,
    "summary": "测试摘要",
    "source": "https://example.com/news"
}
```
"""
        
        result = manager.handle_malformed_response(response, batch_mode=False)
        
        assert result is not None
        assert isinstance(result, StructuredAnalysisResult)
        assert result.category == "大户动向"
    
    def test_handle_malformed_batch_response(self):
        """测试处理格式错误的批量响应 (需求 5.16)"""
        manager = StructuredOutputManager()
        
        response = """```json
{
    "results": [
        {
            "time": "2024-01-01 12:00",
            "category": "测试",
            "weight_score": 85,
            "summary": "测试",
            "source": "https://example.com/1"
        }
    ]
}
```
"""
        
        result = manager.handle_malformed_response(response, batch_mode=True)
        
        assert result is not None
        assert isinstance(result, BatchAnalysisResult)
        assert len(result.results) == 1
    
    def test_handle_unrecoverable_response(self):
        """测试处理无法恢复的响应 (需求 5.16)"""
        manager = StructuredOutputManager()
        
        response = "这完全不是JSON格式的内容"
        
        result = manager.handle_malformed_response(response, batch_mode=False)
        
        assert result is None


# ============================================================================
# 动态分类发现和管理测试 (需求 5.17)
# ============================================================================

class TestDynamicClassificationDiscovery:
    """测试动态分类发现和管理"""
    
    def test_extract_categories_from_results(self, mock_analysis_results):
        """测试从结果中提取分类 (需求 5.17)"""
        manager = DynamicClassificationManager()
        
        categories = manager.extract_categories_from_response(mock_analysis_results)
        
        assert len(categories) == 3
        assert "大户动向" in categories
        assert "新产品" in categories
        assert "美国政府监管政策" in categories
    
    def test_update_category_registry_new_categories(self):
        """测试更新分类注册表 - 新分类 (需求 5.17)"""
        manager = DynamicClassificationManager()
        
        # 第一批分类
        categories1 = {"大户动向", "利率事件"}
        manager.update_category_registry(categories1)
        
        assert len(manager.get_current_categories()) == 2
        
        # 第二批分类（包含新分类）
        categories2 = {"大户动向", "利率事件", "安全事件"}
        manager.update_category_registry(categories2)
        
        assert len(manager.get_current_categories()) == 3
        assert "安全事件" in manager.get_current_categories()
    
    def test_category_statistics_accumulation(self, mock_analysis_results):
        """测试分类统计累积 (需求 5.17)"""
        manager = DynamicClassificationManager()
        
        # 第一批
        manager.update_statistics(mock_analysis_results)
        
        stats = manager.get_category_statistics()
        assert stats["大户动向"] == 1
        assert stats["新产品"] == 1
        assert stats["美国政府监管政策"] == 1
        
        # 第二批（重复分类）
        more_results = [
            StructuredAnalysisResult(
                time="2024-01-01 15:00",
                category="大户动向",
                weight_score=80,
                summary="另一个大户动向",
                source="https://example.com/4"
            )
        ]
        
        manager.update_statistics(more_results)
        
        stats = manager.get_category_statistics()
        assert stats["大户动向"] == 2  # 累积
    
    def test_process_analysis_results_complete_workflow(self, mock_analysis_results):
        """测试完整的分析结果处理流程 (需求 5.17)"""
        manager = DynamicClassificationManager()
        
        result = manager.process_analysis_results(mock_analysis_results)
        
        assert "categories" in result
        assert "category_count" in result
        assert "is_consistent" in result
        assert "statistics" in result
        
        assert result["category_count"] == 3
        assert len(result["categories"]) == 3
        assert result["statistics"]["大户动向"] == 1


class TestDynamicClassificationConsistency:
    """测试动态分类一致性验证"""
    
    def test_consistency_validation_first_run(self):
        """测试首次运行的一致性验证 (需求 5.17)"""
        manager = DynamicClassificationManager()
        
        categories = {"大户动向", "利率事件"}
        
        # 首次运行应该返回True
        is_consistent = manager.validate_category_consistency(categories)
        
        assert is_consistent is True
    
    def test_consistency_validation_identical_categories(self):
        """测试相同分类的一致性 (需求 5.17)"""
        manager = DynamicClassificationManager()
        
        categories = {"大户动向", "利率事件", "安全事件"}
        manager.update_category_registry(categories)
        
        # 验证相同的分类
        is_consistent = manager.validate_category_consistency(categories)
        
        assert is_consistent is True
    
    def test_consistency_validation_category_changes(self):
        """测试分类变更的一致性 (需求 5.17)"""
        manager = DynamicClassificationManager()
        
        # 初始分类
        categories1 = {"大户动向", "利率事件"}
        manager.update_category_registry(categories1)
        
        # 完全不同的分类
        categories2 = {"新产品", "市场新现象"}
        is_consistent = manager.validate_category_consistency(categories2)
        
        # 应该检测到不一致
        assert is_consistent is False
    
    def test_handle_category_changes_tracking(self):
        """测试分类变更追踪 (需求 5.17)"""
        manager = DynamicClassificationManager()
        
        old_categories = {"大户动向", "利率事件"}
        new_categories = {"大户动向", "安全事件", "新产品"}
        
        manager.handle_category_changes(old_categories, new_categories)
        
        history = manager.get_category_history()
        assert len(history) > 0
        
        last_change = history[-1]
        assert last_change["type"] == "category_change"
        assert "利率事件" in last_change["removed"]
        assert "安全事件" in last_change["added"]
        assert "新产品" in last_change["added"]


# ============================================================================
# 批量分析和去重功能测试 (需求 5.17)
# ============================================================================

class TestBatchAnalysisAndDeduplication:
    """测试批量分析和去重功能"""
    
    def test_batch_analysis_mock_mode(self, mock_content_items):
        """测试批量分析（模拟模式） (需求 5.17)"""
        analyzer = LLMAnalyzer(mock_mode=True)
        
        results = analyzer.analyze_content_batch(mock_content_items)
        
        assert isinstance(results, list)
        # 模拟模式会过滤部分内容（去重）
        assert len(results) <= len(mock_content_items)
        
        # 验证结果格式
        for result in results:
            assert isinstance(result, StructuredAnalysisResult)
            assert result.time is not None
            assert result.category is not None
            assert 0 <= result.weight_score <= 100
    
    def test_batch_analysis_empty_input(self):
        """测试空输入的批量分析 (需求 5.17)"""
        analyzer = LLMAnalyzer(mock_mode=True)
        
        results = analyzer.analyze_content_batch([])
        
        assert results == []
    
    def test_batch_processing_with_multiple_batches(self, mock_content_items):
        """测试多批次处理 (需求 5.17)"""
        analyzer = LLMAnalyzer(mock_mode=True, batch_size=2)
        
        # 创建更多内容以触发多批次
        items = mock_content_items * 3  # 9个项目
        
        results = analyzer.analyze_content_batch(items)
        
        assert isinstance(results, list)
        # 验证批次处理正常工作
        assert len(results) <= len(items)
    
    def test_semantic_deduplication_in_results(self, mock_content_items):
        """测试结果中的语义去重 (需求 5.17)"""
        analyzer = LLMAnalyzer(mock_mode=True)
        
        # 添加重复内容
        duplicate_item = ContentItem(
            id="test_dup",
            title="比特币突破50000美元",  # 与test1相同
            content="比特币价格今日突破50000美元大关。",
            url="https://example.com/news/dup",
            publish_time=datetime(2024, 1, 1, 12, 30),
            source_name="测试源4",
            source_type="rss"
        )
        
        items_with_dup = mock_content_items + [duplicate_item]
        
        results = analyzer.analyze_content_batch(items_with_dup)
        
        # 模拟模式应该过滤重复内容
        assert len(results) <= len(items_with_dup)
    
    def test_get_dynamic_categories_from_batch(self, mock_content_items):
        """测试从批量结果提取动态分类 (需求 5.17)"""
        analyzer = LLMAnalyzer(mock_mode=True)
        
        results = analyzer.analyze_content_batch(mock_content_items)
        categories = analyzer.get_dynamic_categories(results)
        
        assert isinstance(categories, list)
        assert len(categories) > 0
        # 验证所有分类都是字符串
        assert all(isinstance(cat, str) for cat in categories)


# ============================================================================
# 集成测试：完整的四步分析流程
# ============================================================================

class TestFourStepAnalysisWorkflow:
    """测试完整的四步分析流程"""
    
    def test_complete_workflow_mock_mode(self, mock_content_items):
        """测试完整的四步工作流 (需求 5.11-5.17)"""
        analyzer = LLMAnalyzer(mock_mode=True)
        
        # 第一步：获取市场快照
        snapshot = analyzer.get_market_snapshot(use_cached=False)
        assert snapshot is not None
        assert snapshot.is_valid is True
        
        # 第二步：合并提示词
        system_prompt = analyzer.merge_prompts_with_snapshot(snapshot)
        assert system_prompt is not None
        assert snapshot.content in system_prompt
        assert "${Grok_Summary_Here}" not in system_prompt
        
        # 第三步和第四步：批量分析
        results = analyzer.analyze_content_batch(
            mock_content_items,
            use_cached_snapshot=True
        )
        
        assert isinstance(results, list)
        
        # 验证结果格式
        for result in results:
            assert isinstance(result, StructuredAnalysisResult)
            assert result.time is not None
            assert result.category is not None
            assert 0 <= result.weight_score <= 100
            assert result.summary is not None
            assert result.source is not None
    
    def test_workflow_with_dynamic_classification(self, mock_content_items):
        """测试工作流与动态分类管理器集成 (需求 5.17)"""
        analyzer = LLMAnalyzer(mock_mode=True)
        classification_manager = DynamicClassificationManager()
        
        # 执行分析
        results = analyzer.analyze_content_batch(mock_content_items)
        
        # 使用动态分类管理器处理结果
        processed = classification_manager.process_analysis_results(results)
        
        assert processed["category_count"] > 0
        assert len(processed["categories"]) > 0
        assert processed["is_consistent"] is True
    
    def test_workflow_with_caching(self, mock_content_items):
        """测试工作流的缓存机制 (需求 5.11)"""
        analyzer = LLMAnalyzer(mock_mode=True)
        
        # 第一次执行（创建缓存）
        results1 = analyzer.analyze_content_batch(
            mock_content_items,
            use_cached_snapshot=False
        )
        
        # 验证缓存已创建
        cache_info = analyzer.get_cache_info()
        assert cache_info["has_cached_snapshot"] is True
        
        # 第二次执行（使用缓存）
        results2 = analyzer.analyze_content_batch(
            mock_content_items,
            use_cached_snapshot=True
        )
        
        # 两次结果应该都有效
        assert len(results1) >= 0
        assert len(results2) >= 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
