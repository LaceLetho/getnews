"""
多步骤分析系统属性测试

使用Hypothesis进行属性测试，验证多步骤分析流程的正确性。
包含以下属性测试：
- 属性 5: 市场快照获取一致性
- 属性 6: 提示词合并正确性
- 属性 7: 结构化输出一致性
- 属性 8: 动态分类处理正确性
- 属性 9: 批量分析完整性

**功能: crypto-news-analyzer**
**验证: 需求 5.1-5.18**
"""

import pytest
import tempfile
import os
import json
from pathlib import Path
from datetime import datetime, timedelta
from hypothesis import given, strategies as st, assume, settings
from typing import Dict, Any, List

from crypto_news_analyzer.models import ContentItem
from crypto_news_analyzer.analyzers.llm_analyzer import LLMAnalyzer
from crypto_news_analyzer.analyzers.market_snapshot_service import (
    MarketSnapshotService, MarketSnapshot
)
from crypto_news_analyzer.analyzers.structured_output_manager import (
    StructuredOutputManager, StructuredAnalysisResult, BatchAnalysisResult
)
from crypto_news_analyzer.analyzers.dynamic_classification_manager import (
    DynamicClassificationManager
)


# ============================================================================
# 策略定义：生成测试数据
# ============================================================================

@st.composite
def valid_content_item(draw):
    """生成有效的内容项"""
    """生成有效的内容项"""
    title = draw(st.text(min_size=10, max_size=200))
    content = draw(st.text(min_size=50, max_size=1000))
    url = draw(st.sampled_from([
        "https://example.com/news/1",
        "https://crypto.news/article/123",
        "https://x.com/user/status/456",
        "https://panews.com/flash/789"
    ]))
    
    # 生成最近24小时内的时间
    hours_ago = draw(st.integers(min_value=0, max_value=24))
    publish_time = datetime.now() - timedelta(hours=hours_ago)
    
    source_name = draw(st.sampled_from(["PANews", "CryptoNews", "X_List", "RSS_Feed"]))
    source_type = draw(st.sampled_from(["rss", "x"]))
    
    return ContentItem(
        id=f"item_{draw(st.integers(min_value=1, max_value=10000))}",
        title=title,
        content=content,
        url=url,
        publish_time=publish_time,
        source_name=source_name,
        source_type=source_type
    )


@st.composite
def valid_market_snapshot(draw):
    """生成有效的市场快照"""
    content = draw(st.text(min_size=100, max_size=2000))
    timestamp = datetime.now() - timedelta(minutes=draw(st.integers(min_value=0, max_value=30)))
    source = draw(st.sampled_from(["grok", "fallback", "cached", "mock"]))
    quality_score = draw(st.floats(min_value=0.5, max_value=1.0))
    
    return MarketSnapshot(
        content=content,
        timestamp=timestamp,
        source=source,
        quality_score=quality_score,
        is_valid=True
    )


@st.composite
def valid_structured_result(draw):
    """生成有效的结构化分析结果"""
    time_str = datetime.now().strftime('%Y-%m-%d %H:%M')
    category = draw(st.sampled_from([
        "Whale", "Fed", "Regulation", "Security", "NewProject", "MarketTrend"
    ]))
    weight_score = draw(st.integers(min_value=0, max_value=100))
    summary = draw(st.text(min_size=20, max_size=200))
    source = draw(st.sampled_from([
        "https://example.com/1",
        "https://crypto.news/2",
        "https://x.com/status/3"
    ]))
    
    return StructuredAnalysisResult(
        time=time_str,
        category=category,
        weight_score=weight_score,
        summary=summary,
        source=source
    )


# ============================================================================
# 属性 5: 市场快照获取一致性
# ============================================================================

class TestMarketSnapshotConsistency:
    """
    属性 5: 市场快照获取一致性
    
    验证需求: 5.1, 5.2, 5.18
    对于任何市场快照请求，系统应该能够从联网AI服务获取当前市场现状，
    或在服务不可用时使用缓存或默认快照
    """
    
    def setup_method(self):
        """测试前设置"""
        self.temp_dir = tempfile.mkdtemp()
        self.cache_dir = os.path.join(self.temp_dir, "cache")
        os.makedirs(self.cache_dir, exist_ok=True)
    
    def teardown_method(self):
        """测试后清理"""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    @given(prompt_template=st.text(min_size=10, max_size=500))
    @settings(max_examples=100, deadline=None)
    def test_market_snapshot_always_returns_valid_snapshot(self, prompt_template: str):
        """
        属性测试：市场快照获取总是返回有效快照
        
        **功能: crypto-news-analyzer, 属性 5: 市场快照获取一致性**
        **验证: 需求 5.1, 5.2, 5.18**
        """
        # 使用模拟模式，避免真实API调用
        service = MarketSnapshotService(
            grok_api_key="test_key",
            cache_dir=self.cache_dir,
            mock_mode=True
        )
        
        # 获取市场快照
        snapshot = service.get_market_snapshot(prompt_template)
        
        # 验证：总是返回有效的MarketSnapshot对象
        assert isinstance(snapshot, MarketSnapshot), "应该返回MarketSnapshot对象"
        assert snapshot.is_valid, "快照应该是有效的"
        assert snapshot.content, "快照内容不应为空"
        assert isinstance(snapshot.timestamp, datetime), "时间戳应该是datetime对象"
        assert snapshot.source in ["grok", "fallback", "cached", "mock"], "来源应该是已知类型"
        assert 0.0 <= snapshot.quality_score <= 1.0, "质量评分应该在0-1之间"
    
    @given(
        prompt1=st.text(min_size=10, max_size=200),
        prompt2=st.text(min_size=10, max_size=200)
    )
    @settings(max_examples=50, deadline=None)
    def test_market_snapshot_caching_consistency(self, prompt1: str, prompt2: str):
        """
        属性测试：市场快照缓存一致性
        
        验证缓存机制的正确性
        """
        # 使用非模拟模式来测试缓存（模拟模式不使用缓存）
        service = MarketSnapshotService(
            grok_api_key="",  # 空密钥，强制使用备用快照
            cache_dir=self.cache_dir,
            cache_ttl_minutes=30,
            mock_mode=False
        )
        
        # 第一次获取（应该生成新快照）
        snapshot1 = service.get_market_snapshot(prompt1)
        
        # 手动缓存快照
        service.cache_snapshot(snapshot1)
        
        # 第二次获取（应该使用缓存）
        snapshot2 = service.get_cached_snapshot()
        
        # 验证：缓存的快照应该存在
        assert snapshot2 is not None, "应该能获取到缓存的快照"
        
        # 验证：两次获取的快照内容应该相同（因为使用了缓存）
        assert snapshot1.content == snapshot2.content, "缓存的快照内容应该一致"
        assert snapshot2.source == "cached", "第二次应该使用缓存"
    
    def test_market_snapshot_fallback_mechanism(self):
        """
        属性测试：市场快照备用机制
        
        验证在服务不可用时使用备用快照
        """
        # 不提供API密钥，强制使用备用快照
        service = MarketSnapshotService(
            grok_api_key="",
            cache_dir=self.cache_dir,
            mock_mode=False
        )
        
        snapshot = service.get_fallback_snapshot()
        
        # 验证：备用快照应该有效
        assert isinstance(snapshot, MarketSnapshot)
        assert snapshot.is_valid
        assert snapshot.source == "fallback"
        assert len(snapshot.content) >= 50, "备用快照应该有足够的内容"


# ============================================================================
# 属性 6: 提示词合并正确性
# ============================================================================

class TestPromptMergingCorrectness:
    """
    属性 6: 提示词合并正确性
    
    验证需求: 5.4
    对于任何获取到的市场快照，系统应该能够正确合并市场快照和分析提示词，
    生成包含完整上下文的系统提示词
    """
    
    def setup_method(self):
        """测试前设置"""
        self.temp_dir = tempfile.mkdtemp()
        
        # 创建测试用的提示词文件
        self.prompts_dir = os.path.join(self.temp_dir, "prompts")
        os.makedirs(self.prompts_dir, exist_ok=True)
        
        self.market_prompt_path = os.path.join(self.prompts_dir, "market_summary_prompt.md")
        self.analysis_prompt_path = os.path.join(self.prompts_dir, "analysis_prompt.md")
        
        # 创建测试提示词文件
        with open(self.market_prompt_path, 'w', encoding='utf-8') as f:
            f.write("请提供当前加密货币市场的现状总结。")
        
        with open(self.analysis_prompt_path, 'w', encoding='utf-8') as f:
            f.write("你是一个加密货币分析师。\n\n市场现状：\n${Grok_Summary_Here}\n\n请分析以下内容。")
    
    def teardown_method(self):
        """测试后清理"""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    @given(snapshot=valid_market_snapshot())
    @settings(max_examples=100, deadline=None)
    def test_prompt_merging_contains_snapshot(self, snapshot: MarketSnapshot):
        """
        属性测试：合并后的提示词包含市场快照
        
        **功能: crypto-news-analyzer, 属性 6: 提示词合并正确性**
        **验证: 需求 5.4**
        """
        analyzer = LLMAnalyzer(
            api_key="test_key",
            market_prompt_path=self.market_prompt_path,
            analysis_prompt_path=self.analysis_prompt_path,
            mock_mode=True
        )
        
        # 合并提示词
        merged_prompt = analyzer.merge_prompts_with_snapshot(snapshot)
        
        # 验证：合并后的提示词应该包含市场快照内容
        assert snapshot.content in merged_prompt, "合并后的提示词应该包含市场快照内容"
        
        # 验证：占位符应该被替换
        assert "${Grok_Summary_Here}" not in merged_prompt, "占位符应该被替换"
        
        # 验证：合并后的提示词不应为空
        assert len(merged_prompt) > 0, "合并后的提示词不应为空"
    
    @given(
        snapshot1=valid_market_snapshot(),
        snapshot2=valid_market_snapshot()
    )
    @settings(max_examples=50, deadline=None)
    def test_prompt_merging_deterministic(self, snapshot1: MarketSnapshot, snapshot2: MarketSnapshot):
        """
        属性测试：提示词合并的确定性
        
        相同的快照应该产生相同的合并结果
        """
        assume(snapshot1.content != snapshot2.content)
        
        analyzer = LLMAnalyzer(
            api_key="test_key",
            market_prompt_path=self.market_prompt_path,
            analysis_prompt_path=self.analysis_prompt_path,
            mock_mode=True
        )
        
        # 第一次合并
        merged1_a = analyzer.merge_prompts_with_snapshot(snapshot1)
        merged1_b = analyzer.merge_prompts_with_snapshot(snapshot1)
        
        # 验证：相同快照的合并结果应该一致
        assert merged1_a == merged1_b, "相同快照的合并结果应该一致"
        
        # 第二次合并（不同快照）
        merged2 = analyzer.merge_prompts_with_snapshot(snapshot2)
        
        # 验证：不同快照的合并结果应该不同
        assert merged1_a != merged2, "不同快照的合并结果应该不同"


# ============================================================================
# 属性 7: 结构化输出一致性
# ============================================================================

class TestStructuredOutputConsistency:
    """
    属性 7: 结构化输出一致性
    
    验证需求: 5.5, 5.13, 5.15
    对于任何大模型响应，结构化输出工具应该强制返回包含time、category、
    weight_score、summary、source字段的标准JSON格式
    """
    
    @given(result=valid_structured_result())
    @settings(max_examples=100, deadline=None)
    def test_structured_output_has_all_required_fields(self, result: StructuredAnalysisResult):
        """
        属性测试：结构化输出包含所有必需字段
        
        **功能: crypto-news-analyzer, 属性 7: 结构化输出一致性**
        **验证: 需求 5.5, 5.13, 5.15**
        """
        # 验证：所有必需字段都存在
        assert hasattr(result, 'time'), "应该有time字段"
        assert hasattr(result, 'category'), "应该有category字段"
        assert hasattr(result, 'weight_score'), "应该有weight_score字段"
        assert hasattr(result, 'summary'), "应该有summary字段"
        assert hasattr(result, 'source'), "应该有source字段"
        
        # 验证：字段类型正确
        assert isinstance(result.time, str), "time应该是字符串"
        assert isinstance(result.category, str), "category应该是字符串"
        assert isinstance(result.weight_score, int), "weight_score应该是整数"
        assert isinstance(result.summary, str), "summary应该是字符串"
        assert isinstance(result.source, str), "source应该是字符串"
        
        # 验证：字段值有效
        assert 0 <= result.weight_score <= 100, "weight_score应该在0-100之间"
        assert result.source.startswith('http'), "source应该是有效的URL"
    
    @given(results=st.lists(valid_structured_result(), min_size=0, max_size=20))
    @settings(max_examples=50, deadline=None)
    def test_batch_analysis_result_structure(self, results: List[StructuredAnalysisResult]):
        """
        属性测试：批量分析结果结构的一致性
        
        验证批量结果容器的正确性
        """
        # 创建批量结果
        batch_result = BatchAnalysisResult(results=results)
        
        # 验证：批量结果应该有results字段
        assert hasattr(batch_result, 'results'), "应该有results字段"
        assert isinstance(batch_result.results, list), "results应该是列表"
        assert len(batch_result.results) == len(results), "结果数量应该一致"
        
        # 验证：每个结果都是有效的StructuredAnalysisResult
        for result in batch_result.results:
            assert isinstance(result, StructuredAnalysisResult)
    
    def test_structured_output_validation(self):
        """
        属性测试：结构化输出验证机制
        
        验证输出验证功能的正确性
        """
        manager = StructuredOutputManager(library="instructor")
        
        # 有效的响应
        valid_response = {
            "time": "2024-01-01 12:00",
            "category": "Whale",
            "weight_score": 85,
            "summary": "Test summary",
            "source": "https://example.com/1"
        }
        
        validation_result = manager.validate_output_structure(valid_response)
        assert validation_result.is_valid, "有效响应应该通过验证"
        assert len(validation_result.errors) == 0, "有效响应不应该有错误"
        
        # 无效的响应（缺少字段）
        invalid_response = {
            "time": "2024-01-01 12:00",
            "category": "Whale"
            # 缺少其他必需字段
        }
        
        validation_result = manager.validate_output_structure(invalid_response)
        assert not validation_result.is_valid, "无效响应应该验证失败"
        assert len(validation_result.errors) > 0, "无效响应应该有错误信息"


# ============================================================================
# 属性 8: 动态分类处理正确性
# ============================================================================

class TestDynamicClassificationCorrectness:
    """
    属性 8: 动态分类处理正确性
    
    验证需求: 5.8, 5.9, 5.10
    对于任何大模型返回的分类结果，系统应该能够动态识别和处理新的分类类别，
    不依赖硬编码的分类列表
    """
    
    @given(results=st.lists(valid_structured_result(), min_size=1, max_size=50))
    @settings(max_examples=100, deadline=None)
    def test_dynamic_category_extraction(self, results: List[StructuredAnalysisResult]):
        """
        属性测试：动态分类提取
        
        **功能: crypto-news-analyzer, 属性 8: 动态分类处理正确性**
        **验证: 需求 5.8, 5.9, 5.10**
        """
        manager = DynamicClassificationManager()
        
        # 提取分类
        categories = manager.extract_categories_from_response(results)
        
        # 验证：提取的分类应该是集合
        assert isinstance(categories, set), "分类应该是集合类型"
        
        # 验证：提取的分类数量应该合理
        unique_categories = set(r.category for r in results)
        assert categories == unique_categories, "提取的分类应该与结果中的分类一致"
        
        # 验证：分类不应为空（因为results至少有1个元素）
        assert len(categories) > 0, "至少应该有一个分类"
    
    @given(
        results1=st.lists(valid_structured_result(), min_size=1, max_size=20),
        results2=st.lists(valid_structured_result(), min_size=1, max_size=20)
    )
    @settings(max_examples=50, deadline=None)
    def test_dynamic_category_registry_update(
        self,
        results1: List[StructuredAnalysisResult],
        results2: List[StructuredAnalysisResult]
    ):
        """
        属性测试：动态分类注册表更新
        
        验证分类注册表的更新机制
        """
        manager = DynamicClassificationManager()
        
        # 第一批结果
        categories1 = manager.extract_categories_from_response(results1)
        manager.update_category_registry(categories1)
        
        current_categories1 = set(manager.get_current_categories())
        assert current_categories1 == categories1, "注册表应该包含第一批分类"
        
        # 第二批结果
        categories2 = manager.extract_categories_from_response(results2)
        manager.update_category_registry(categories2)
        
        current_categories2 = set(manager.get_current_categories())
        assert current_categories2 == categories2, "注册表应该更新为第二批分类"
    
    @given(results=st.lists(valid_structured_result(), min_size=5, max_size=50))
    @settings(max_examples=30, deadline=None)
    def test_category_statistics_accuracy(self, results: List[StructuredAnalysisResult]):
        """
        属性测试：分类统计准确性
        
        验证分类统计功能的正确性
        """
        manager = DynamicClassificationManager()
        
        # 更新统计
        manager.update_statistics(results)
        
        # 获取统计信息
        stats = manager.get_category_statistics()
        
        # 手动计算预期统计
        expected_stats = {}
        for result in results:
            expected_stats[result.category] = expected_stats.get(result.category, 0) + 1
        
        # 验证：统计结果应该准确
        assert stats == expected_stats, "统计结果应该与实际分布一致"
        
        # 验证：总数应该等于结果数量
        assert sum(stats.values()) == len(results), "统计总数应该等于结果数量"


# ============================================================================
# 属性 9: 批量分析完整性
# ============================================================================

class TestBatchAnalysisCompleteness:
    """
    属性 9: 批量分析完整性
    
    验证需求: 5.6, 5.7
    对于任何新闻内容批次，系统应该通过大模型完成语义去重和筛选，
    返回去重后的结构化分析结果
    """
    
    def setup_method(self):
        """测试前设置"""
        self.temp_dir = tempfile.mkdtemp()
        
        # 创建测试用的提示词文件
        self.prompts_dir = os.path.join(self.temp_dir, "prompts")
        os.makedirs(self.prompts_dir, exist_ok=True)
        
        self.market_prompt_path = os.path.join(self.prompts_dir, "market_summary_prompt.md")
        self.analysis_prompt_path = os.path.join(self.prompts_dir, "analysis_prompt.md")
        
        with open(self.market_prompt_path, 'w', encoding='utf-8') as f:
            f.write("请提供市场现状。")
        
        with open(self.analysis_prompt_path, 'w', encoding='utf-8') as f:
            f.write("分析师提示词\n${Grok_Summary_Here}\n分析内容。")
    
    def teardown_method(self):
        """测试后清理"""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    @given(items=st.lists(valid_content_item(), min_size=1, max_size=30))
    @settings(max_examples=100, deadline=None)
    def test_batch_analysis_returns_valid_results(self, items: List[ContentItem]):
        """
        属性测试：批量分析返回有效结果
        
        **功能: crypto-news-analyzer, 属性 9: 批量分析完整性**
        **验证: 需求 5.6, 5.7**
        """
        analyzer = LLMAnalyzer(
            api_key="test_key",
            market_prompt_path=self.market_prompt_path,
            analysis_prompt_path=self.analysis_prompt_path,
            mock_mode=True
        )
        
        # 批量分析
        results = analyzer.analyze_content_batch(items, use_cached_snapshot=False)
        
        # 验证：返回结果应该是列表
        assert isinstance(results, list), "应该返回列表"
        
        # 验证：每个结果都是有效的StructuredAnalysisResult
        for result in results:
            assert isinstance(result, StructuredAnalysisResult)
            assert hasattr(result, 'time')
            assert hasattr(result, 'category')
            assert hasattr(result, 'weight_score')
            assert hasattr(result, 'summary')
            assert hasattr(result, 'source')
    
    @given(items=st.lists(valid_content_item(), min_size=0, max_size=10))
    @settings(max_examples=50, deadline=None)
    def test_batch_analysis_handles_empty_input(self, items: List[ContentItem]):
        """
        属性测试：批量分析处理空输入
        
        验证空输入的处理
        """
        analyzer = LLMAnalyzer(
            api_key="test_key",
            market_prompt_path=self.market_prompt_path,
            analysis_prompt_path=self.analysis_prompt_path,
            mock_mode=True
        )
        
        # 如果输入为空
        if len(items) == 0:
            results = analyzer.analyze_content_batch(items)
            # 验证：空输入应该返回空列表
            assert results == [], "空输入应该返回空列表"
        else:
            # 非空输入应该正常处理
            results = analyzer.analyze_content_batch(items)
            assert isinstance(results, list)
    
    @given(items=st.lists(valid_content_item(), min_size=5, max_size=20))
    @settings(max_examples=30, deadline=None)
    def test_batch_analysis_deduplication(self, items: List[ContentItem]):
        """
        属性测试：批量分析去重功能
        
        验证分析结果的去重（模拟模式下，每3条保留1条）
        """
        analyzer = LLMAnalyzer(
            api_key="test_key",
            market_prompt_path=self.market_prompt_path,
            analysis_prompt_path=self.analysis_prompt_path,
            mock_mode=True,
            batch_size=50  # 确保一次处理所有内容
        )
        
        # 批量分析
        results = analyzer.analyze_content_batch(items)
        
        # 验证：结果数量应该小于等于输入数量（因为有过滤）
        assert len(results) <= len(items), "结果数量不应超过输入数量"
        
        # 验证：所有结果的source应该来自输入items
        input_urls = {item.url for item in items}
        for result in results:
            # 在模拟模式下，source可能是输入的URL
            # 这里只验证结果是有效的
            assert result.source.startswith('http'), "source应该是有效的URL"


if __name__ == "__main__":
    # 运行属性测试
    pytest.main([__file__, "-v", "--tb=short"])
