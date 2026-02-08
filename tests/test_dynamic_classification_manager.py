"""
测试动态分类管理器

验证动态分类管理器的核心功能：
- 从大模型响应中提取分类
- 更新分类注册表
- 验证分类一致性
- 统计分类信息
- 处理分类变更
"""

import pytest
from datetime import datetime
from crypto_news_analyzer.analyzers.dynamic_classification_manager import DynamicClassificationManager
from crypto_news_analyzer.analyzers.structured_output_manager import StructuredAnalysisResult


class TestDynamicClassificationManager:
    """测试动态分类管理器"""
    
    def setup_method(self):
        """每个测试方法前的设置"""
        self.manager = DynamicClassificationManager()
    
    def test_initialization(self):
        """测试初始化"""
        assert self.manager is not None
        assert len(self.manager.get_current_categories()) == 0
        assert len(self.manager.get_category_statistics()) == 0
    
    def test_extract_categories_from_response(self):
        """测试从响应中提取分类"""
        # 创建测试数据
        results = [
            StructuredAnalysisResult(
                time="2024-01-01 10:00",
                category="Whale",
                weight_score=80,
                summary="大户转移资金",
                source="https://example.com/1"
            ),
            StructuredAnalysisResult(
                time="2024-01-01 11:00",
                category="Fed",
                weight_score=90,
                summary="美联储政策变化",
                source="https://example.com/2"
            ),
            StructuredAnalysisResult(
                time="2024-01-01 12:00",
                category="Whale",
                weight_score=75,
                summary="另一个大户动向",
                source="https://example.com/3"
            )
        ]
        
        # 提取分类
        categories = self.manager.extract_categories_from_response(results)
        
        # 验证
        assert len(categories) == 2
        assert "Whale" in categories
        assert "Fed" in categories
    
    def test_extract_categories_with_empty_response(self):
        """测试空响应的分类提取"""
        categories = self.manager.extract_categories_from_response([])
        assert len(categories) == 0
    
    def test_extract_categories_with_whitespace(self):
        """测试带空白字符的分类提取"""
        results = [
            StructuredAnalysisResult(
                time="2024-01-01 10:00",
                category="  Whale  ",
                weight_score=80,
                summary="测试",
                source="https://example.com/1"
            ),
            StructuredAnalysisResult(
                time="2024-01-01 11:00",
                category="Whale",
                weight_score=75,
                summary="测试2",
                source="https://example.com/2"
            )
        ]
        
        categories = self.manager.extract_categories_from_response(results)
        
        # 应该去除空白并去重
        assert len(categories) == 1
        assert "Whale" in categories
    
    def test_update_category_registry(self):
        """测试更新分类注册表"""
        # 第一次更新
        categories1 = {"Whale", "Fed"}
        self.manager.update_category_registry(categories1)
        
        assert len(self.manager.get_current_categories()) == 2
        assert "Whale" in self.manager.get_current_categories()
        assert "Fed" in self.manager.get_current_categories()
        
        # 第二次更新（添加新分类）
        categories2 = {"Whale", "Fed", "Regulation"}
        self.manager.update_category_registry(categories2)
        
        assert len(self.manager.get_current_categories()) == 3
        assert "Regulation" in self.manager.get_current_categories()
    
    def test_get_current_categories_sorted(self):
        """测试获取当前分类（排序）"""
        categories = {"Zebra", "Apple", "Banana"}
        self.manager.update_category_registry(categories)
        
        current = self.manager.get_current_categories()
        
        # 应该按字母顺序排序
        assert current == ["Apple", "Banana", "Zebra"]
    
    def test_validate_category_consistency_first_run(self):
        """测试首次运行的一致性验证"""
        categories = {"Whale", "Fed"}
        
        # 首次运行，没有历史数据，应该返回True
        is_consistent = self.manager.validate_category_consistency(categories)
        
        assert is_consistent is True
    
    def test_validate_category_consistency_identical(self):
        """测试完全相同的分类一致性"""
        # 设置初始分类
        categories1 = {"Whale", "Fed", "Regulation"}
        self.manager.update_category_registry(categories1)
        
        # 验证相同的分类
        categories2 = {"Whale", "Fed", "Regulation"}
        is_consistent = self.manager.validate_category_consistency(categories2)
        
        assert is_consistent is True
    
    def test_validate_category_consistency_high_similarity(self):
        """测试高相似度的分类一致性"""
        # 设置初始分类
        categories1 = {"Whale", "Fed", "Regulation", "Security"}
        self.manager.update_category_registry(categories1)
        
        # 验证高相似度的分类（3/4相同）
        categories2 = {"Whale", "Fed", "Regulation"}
        is_consistent = self.manager.validate_category_consistency(categories2)
        
        # Jaccard相似度 = 3/4 = 0.75，低于默认阈值0.8
        assert is_consistent is False
    
    def test_validate_category_consistency_low_similarity(self):
        """测试低相似度的分类一致性"""
        # 设置初始分类
        categories1 = {"Whale", "Fed"}
        self.manager.update_category_registry(categories1)
        
        # 验证完全不同的分类
        categories2 = {"NewProject", "MarketTrend"}
        is_consistent = self.manager.validate_category_consistency(categories2)
        
        assert is_consistent is False
    
    def test_set_consistency_threshold(self):
        """测试设置一致性阈值"""
        self.manager.set_consistency_threshold(0.5)
        
        # 设置初始分类
        categories1 = {"Whale", "Fed", "Regulation", "Security"}
        self.manager.update_category_registry(categories1)
        
        # 验证中等相似度的分类（3/4 = 0.75 > 0.5）
        categories2 = {"Whale", "Fed", "Regulation"}
        is_consistent = self.manager.validate_category_consistency(categories2)
        
        assert is_consistent is True
    
    def test_set_consistency_threshold_invalid(self):
        """测试设置无效的一致性阈值"""
        with pytest.raises(ValueError):
            self.manager.set_consistency_threshold(1.5)
        
        with pytest.raises(ValueError):
            self.manager.set_consistency_threshold(-0.1)
    
    def test_handle_category_changes(self):
        """测试处理分类变更"""
        old_categories = {"Whale", "Fed"}
        new_categories = {"Whale", "Regulation", "Security"}
        
        self.manager.handle_category_changes(old_categories, new_categories)
        
        # 验证历史记录
        history = self.manager.get_category_history()
        assert len(history) > 0
        
        last_change = history[-1]
        assert last_change["type"] == "category_change"
        assert "Fed" in last_change["removed"]
        assert "Regulation" in last_change["added"]
        assert "Security" in last_change["added"]
    
    def test_update_statistics(self):
        """测试更新统计信息"""
        results = [
            StructuredAnalysisResult(
                time="2024-01-01 10:00",
                category="Whale",
                weight_score=80,
                summary="测试1",
                source="https://example.com/1"
            ),
            StructuredAnalysisResult(
                time="2024-01-01 11:00",
                category="Whale",
                weight_score=75,
                summary="测试2",
                source="https://example.com/2"
            ),
            StructuredAnalysisResult(
                time="2024-01-01 12:00",
                category="Fed",
                weight_score=90,
                summary="测试3",
                source="https://example.com/3"
            )
        ]
        
        self.manager.update_statistics(results)
        
        stats = self.manager.get_category_statistics()
        assert stats["Whale"] == 2
        assert stats["Fed"] == 1
    
    def test_get_category_statistics_empty(self):
        """测试获取空统计信息"""
        stats = self.manager.get_category_statistics()
        assert len(stats) == 0
    
    def test_process_analysis_results(self):
        """测试处理分析结果（一站式方法）"""
        results = [
            StructuredAnalysisResult(
                time="2024-01-01 10:00",
                category="Whale",
                weight_score=80,
                summary="测试1",
                source="https://example.com/1"
            ),
            StructuredAnalysisResult(
                time="2024-01-01 11:00",
                category="Fed",
                weight_score=90,
                summary="测试2",
                source="https://example.com/2"
            )
        ]
        
        result = self.manager.process_analysis_results(results)
        
        # 验证返回结果
        assert "categories" in result
        assert "category_count" in result
        assert "is_consistent" in result
        assert "statistics" in result
        
        assert result["category_count"] == 2
        assert "Whale" in result["categories"]
        assert "Fed" in result["categories"]
        assert result["statistics"]["Whale"] == 1
        assert result["statistics"]["Fed"] == 1
    
    def test_process_analysis_results_with_consistency_check(self):
        """测试处理分析结果并验证一致性"""
        # 第一批结果
        results1 = [
            StructuredAnalysisResult(
                time="2024-01-01 10:00",
                category="Whale",
                weight_score=80,
                summary="测试1",
                source="https://example.com/1"
            )
        ]
        
        self.manager.process_analysis_results(results1)
        
        # 第二批结果（相同分类）
        results2 = [
            StructuredAnalysisResult(
                time="2024-01-01 11:00",
                category="Whale",
                weight_score=75,
                summary="测试2",
                source="https://example.com/2"
            )
        ]
        
        result = self.manager.process_analysis_results(results2, validate_consistency=True)
        
        # 应该一致
        assert result["is_consistent"] is True
    
    def test_get_category_history(self):
        """测试获取分类历史"""
        # 更新几次分类
        self.manager.update_category_registry({"Whale", "Fed"})
        self.manager.update_category_registry({"Whale", "Regulation"})
        
        history = self.manager.get_category_history()
        
        assert len(history) == 2
        assert all("timestamp" in h for h in history)
        assert all("categories" in h for h in history)
    
    def test_reset_statistics(self):
        """测试重置统计信息"""
        results = [
            StructuredAnalysisResult(
                time="2024-01-01 10:00",
                category="Whale",
                weight_score=80,
                summary="测试",
                source="https://example.com/1"
            )
        ]
        
        self.manager.update_statistics(results)
        assert len(self.manager.get_category_statistics()) > 0
        
        self.manager.reset_statistics()
        assert len(self.manager.get_category_statistics()) == 0
    
    def test_reset_all(self):
        """测试完全重置"""
        # 添加一些数据
        self.manager.update_category_registry({"Whale", "Fed"})
        results = [
            StructuredAnalysisResult(
                time="2024-01-01 10:00",
                category="Whale",
                weight_score=80,
                summary="测试",
                source="https://example.com/1"
            )
        ]
        self.manager.update_statistics(results)
        
        # 重置
        self.manager.reset_all()
        
        # 验证所有数据已清空
        assert len(self.manager.get_current_categories()) == 0
        assert len(self.manager.get_category_statistics()) == 0
        assert len(self.manager.get_category_history()) == 0
    
    def test_get_summary(self):
        """测试获取状态摘要"""
        results = [
            StructuredAnalysisResult(
                time="2024-01-01 10:00",
                category="Whale",
                weight_score=80,
                summary="测试1",
                source="https://example.com/1"
            ),
            StructuredAnalysisResult(
                time="2024-01-01 11:00",
                category="Fed",
                weight_score=90,
                summary="测试2",
                source="https://example.com/2"
            )
        ]
        
        self.manager.process_analysis_results(results)
        
        summary = self.manager.get_summary()
        
        assert "current_categories" in summary
        assert "category_count" in summary
        assert "total_items_processed" in summary
        assert "statistics" in summary
        assert "history_count" in summary
        assert "consistency_threshold" in summary
        
        assert summary["category_count"] == 2
        assert summary["total_items_processed"] == 2
    
    def test_export_and_import_state(self):
        """测试导出和导入状态"""
        # 创建一些数据
        results = [
            StructuredAnalysisResult(
                time="2024-01-01 10:00",
                category="Whale",
                weight_score=80,
                summary="测试",
                source="https://example.com/1"
            )
        ]
        
        self.manager.process_analysis_results(results)
        self.manager.set_consistency_threshold(0.7)
        
        # 导出状态
        state = self.manager.export_state()
        
        assert "current_categories" in state
        assert "category_stats" in state
        assert "category_history" in state
        assert "consistency_threshold" in state
        assert "export_timestamp" in state
        
        # 创建新管理器并导入状态
        new_manager = DynamicClassificationManager()
        new_manager.import_state(state)
        
        # 验证状态已恢复
        assert new_manager.get_current_categories() == self.manager.get_current_categories()
        assert new_manager.get_category_statistics() == self.manager.get_category_statistics()
        assert len(new_manager.get_category_history()) == len(self.manager.get_category_history())
    
    def test_multiple_batches_consistency(self):
        """测试多批次处理的一致性"""
        # 第一批
        batch1 = [
            StructuredAnalysisResult(
                time="2024-01-01 10:00",
                category="Whale",
                weight_score=80,
                summary="测试1",
                source="https://example.com/1"
            ),
            StructuredAnalysisResult(
                time="2024-01-01 11:00",
                category="Fed",
                weight_score=90,
                summary="测试2",
                source="https://example.com/2"
            )
        ]
        
        result1 = self.manager.process_analysis_results(batch1)
        assert result1["category_count"] == 2
        
        # 第二批（相同分类）
        batch2 = [
            StructuredAnalysisResult(
                time="2024-01-01 12:00",
                category="Whale",
                weight_score=75,
                summary="测试3",
                source="https://example.com/3"
            ),
            StructuredAnalysisResult(
                time="2024-01-01 13:00",
                category="Fed",
                weight_score=85,
                summary="测试4",
                source="https://example.com/4"
            )
        ]
        
        result2 = self.manager.process_analysis_results(batch2, validate_consistency=True)
        assert result2["is_consistent"] is True
        
        # 验证统计累积
        stats = self.manager.get_category_statistics()
        assert stats["Whale"] == 2
        assert stats["Fed"] == 2
    
    def test_category_changes_tracking(self):
        """测试分类变更追踪"""
        # 第一批
        batch1 = [
            StructuredAnalysisResult(
                time="2024-01-01 10:00",
                category="Whale",
                weight_score=80,
                summary="测试1",
                source="https://example.com/1"
            )
        ]
        
        self.manager.process_analysis_results(batch1)
        
        # 第二批（新分类）
        batch2 = [
            StructuredAnalysisResult(
                time="2024-01-01 11:00",
                category="Regulation",
                weight_score=90,
                summary="测试2",
                source="https://example.com/2"
            )
        ]
        
        result = self.manager.process_analysis_results(batch2, validate_consistency=True)
        
        # 应该检测到不一致
        assert result["is_consistent"] is False
        
        # 验证历史记录
        history = self.manager.get_category_history()
        assert len(history) > 0
        
        # 查找分类变更事件
        change_events = [h for h in history if h.get("type") == "category_change"]
        assert len(change_events) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
