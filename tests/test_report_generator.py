"""
报告生成器单元测试
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock

from crypto_news_analyzer.models import ContentItem, CrawlStatus, CrawlResult, AnalysisResult
from crypto_news_analyzer.reporters import (
    ReportGenerator, 
    AnalyzedData, 
    create_analyzed_data,
    validate_report_data
)


class TestReportGenerator:
    """报告生成器测试类"""
    
    def setup_method(self):
        """测试前置设置"""
        self.generator = ReportGenerator()
        
        # 创建测试数据
        self.test_time = datetime.now()
        self.test_items = [
            ContentItem(
                id="test1",
                title="测试新闻1",
                content="这是一条测试新闻内容",
                url="https://example.com/news1",
                publish_time=self.test_time,
                source_name="测试源1",
                source_type="rss"
            ),
            ContentItem(
                id="test2", 
                title="测试新闻2",
                content="这是另一条测试新闻内容",
                url="https://example.com/news2",
                publish_time=self.test_time - timedelta(hours=1),
                source_name="测试源2",
                source_type="x"
            )
        ]
        
        self.test_analysis_results = {
            "test1": AnalysisResult(
                content_id="test1",
                category="大户动向",
                confidence=0.85,
                reasoning="检测到大户资金流动",
                should_ignore=False,
                key_points=["巨鲸转移", "资金流入"]
            ),
            "test2": AnalysisResult(
                content_id="test2",
                category="市场新现象",
                confidence=0.75,
                reasoning="发现新的市场趋势",
                should_ignore=False,
                key_points=["新趋势", "数据异常"]
            )
        }
        
        self.test_crawl_status = CrawlStatus(
            rss_results=[
                CrawlResult(source_name="测试RSS源", status="success", item_count=1, error_message=None)
            ],
            x_results=[
                CrawlResult(source_name="测试X源", status="success", item_count=1, error_message=None)
            ],
            total_items=2,
            execution_time=self.test_time
        )
    
    def test_generate_header(self):
        """测试报告头部生成"""
        start_time = self.test_time - timedelta(hours=24)
        header = self.generator.generate_header(24, start_time, self.test_time)
        
        assert "# 加密货币新闻分析报告" in header
        assert "24 小时" in header
        assert self.test_time.strftime('%Y-%m-%d %H:%M:%S') in header
        assert start_time.strftime('%Y-%m-%d %H:%M:%S') in header
    
    def test_generate_status_table(self):
        """测试状态表格生成"""
        table = self.generator.generate_status_table(self.test_crawl_status)
        
        assert "## 数据源爬取状态" in table
        assert "测试RSS源" in table
        assert "测试X源" in table
        assert "✅ success" in table
        assert "**2**" in table  # 总数量
    
    def test_generate_category_section_with_items(self):
        """测试有内容的分类部分生成"""
        section = self.generator.generate_category_section(
            "大户动向", "🐋", [self.test_items[0]], self.test_analysis_results
        )
        
        assert "## 🐋 大户动向" in section
        assert "测试新闻1" in section
        assert "https://example.com/news1" in section
        assert "置信度: 0.85" in section
        assert "检测到大户资金流动" in section
    
    def test_generate_category_section_empty(self):
        """测试空分类部分生成"""
        section = self.generator.generate_category_section(
            "安全事件", "🔒", [], {}
        )
        
        assert "## 🔒 安全事件" in section
        assert "*本时间窗口内暂无相关内容*" in section
    
    def test_generate_summary(self):
        """测试总结生成"""
        categorized_items = {
            "大户动向": [self.test_items[0]],
            "市场新现象": [self.test_items[1]],
            "安全事件": []
        }
        
        summary = self.generator.generate_summary(categorized_items)
        
        assert "## 📋 报告总结" in summary
        assert "**2** 条内容" in summary
        assert "**大户动向**: 1 条" in summary
        assert "**市场新现象**: 1 条" in summary
    
    def test_generate_summary_empty(self):
        """测试空内容总结"""
        categorized_items = {"大户动向": [], "安全事件": []}
        
        summary = self.generator.generate_summary(categorized_items)
        
        assert summary is None
    
    def test_generate_full_report(self):
        """测试完整报告生成"""
        categorized_items = {
            "大户动向": [self.test_items[0]],
            "市场新现象": [self.test_items[1]]
        }
        
        analyzed_data = create_analyzed_data(
            categorized_items, 
            self.test_analysis_results, 
            24, 
            self.test_time
        )
        
        report = self.generator.generate_report(analyzed_data, self.test_crawl_status)
        
        # 验证报告包含所有必要部分
        assert "# 加密货币新闻分析报告" in report
        assert "## 数据源爬取状态" in report
        assert "## 🐋 大户动向" in report
        assert "## 📊 市场新现象" in report
        assert "## 📋 报告总结" in report
        assert "测试新闻1" in report
        assert "测试新闻2" in report
    
    def test_split_long_content(self):
        """测试长内容截断"""
        long_content = "这是一个很长的内容 " * 100
        truncated = self.generator._truncate_content(long_content, 50)
        
        assert len(truncated) <= 53  # 50 + "..."
        assert truncated.endswith("...")
    
    def test_error_report_generation(self):
        """测试错误报告生成"""
        error_report = self.generator._generate_error_report(
            "测试错误", self.test_crawl_status
        )
        
        assert "错误报告" in error_report
        assert "测试错误" in error_report
        assert "❌ 报告生成失败" in error_report


class TestAnalyzedData:
    """分析数据测试类"""
    
    def test_create_analyzed_data(self):
        """测试创建分析数据"""
        test_time = datetime.now()
        categorized_items = {"大户动向": []}
        analysis_results = {}
        
        data = create_analyzed_data(
            categorized_items, analysis_results, 24, test_time
        )
        
        assert data.categorized_items == categorized_items
        assert data.analysis_results == analysis_results
        assert data.time_window_hours == 24
        assert data.end_time == test_time
        assert data.start_time == test_time - timedelta(hours=24)
    
    def test_validate_report_data_valid(self):
        """测试有效数据验证"""
        test_time = datetime.now()
        data = AnalyzedData(
            categorized_items={},
            analysis_results={},
            time_window_hours=24,
            start_time=test_time - timedelta(hours=24),
            end_time=test_time
        )
        
        status = CrawlStatus(
            rss_results=[],
            x_results=[],
            total_items=0,
            execution_time=test_time
        )
        
        errors = validate_report_data(data, status)
        assert len(errors) == 0
    
    def test_validate_report_data_invalid(self):
        """测试无效数据验证"""
        test_time = datetime.now()
        data = AnalyzedData(
            categorized_items="invalid",  # 应该是字典
            analysis_results={},
            time_window_hours=-1,  # 应该大于0
            start_time=test_time,  # 应该早于结束时间
            end_time=test_time - timedelta(hours=1)
        )
        
        # 创建一个有效的CrawlStatus，然后手动修改其属性来测试验证
        status = CrawlStatus(
            rss_results=[],
            x_results=[],
            total_items=0,
            execution_time=test_time
        )
        # 手动设置无效值来测试验证函数
        status.rss_results = "invalid"
        
        errors = validate_report_data(data, status)
        assert len(errors) > 0
        assert any("categorized_items必须是字典类型" in error for error in errors)
        assert any("时间窗口必须大于0" in error for error in errors)
        assert any("开始时间必须早于结束时间" in error for error in errors)
        assert any("RSS结果必须是列表类型" in error for error in errors)


if __name__ == "__main__":
    pytest.main([__file__])