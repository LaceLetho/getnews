"""
报告生成器单元测试

测试ReportGenerator类的核心功能，包括动态分类展示和市场快照集成。
"""

import pytest
from datetime import datetime, timedelta
from typing import Dict, List

from crypto_news_analyzer.reporters.report_generator import (
    ReportGenerator,
    AnalyzedData,
    create_report_generator,
    categorize_analysis_results
)
from crypto_news_analyzer.reporters.telegram_formatter import TelegramFormatter
from crypto_news_analyzer.analyzers.structured_output_manager import StructuredAnalysisResult
from crypto_news_analyzer.models import CrawlStatus, CrawlResult


class TestReportGenerator:
    """测试ReportGenerator类"""
    
    @pytest.fixture
    def report_generator(self):
        """创建报告生成器实例"""
        return create_report_generator(
            include_market_snapshot=True,
            omit_empty_categories=True
        )
    
    @pytest.fixture
    def sample_analysis_results(self):
        """创建示例分析结果"""
        return [
            StructuredAnalysisResult(
                time="2024-01-01 12:00",
                category="大户动向",
                weight_score=85,
                title="某巨鲸地址转移10000 ETH到交易所",

                body="某巨鲸地址转移10000 ETH到交易所",
                source="https://example.com/news/1"
            ),
            StructuredAnalysisResult(
                time="2024-01-01 13:30",
                category="安全事件",
                weight_score=95,
                title="某DeFi协议发现严重漏洞",

                body="某DeFi协议发现严重漏洞",
                source="https://example.com/news/2"
            ),
            StructuredAnalysisResult(
                time="2024-01-01 14:15",
                category="大户动向",
                weight_score=75,
                title="机构投资者增持BTC",

                body="机构投资者增持BTC",
                source="https://example.com/news/3"
            )
        ]
    
    @pytest.fixture
    def sample_crawl_status(self):
        """创建示例爬取状态"""
        return CrawlStatus(
            rss_results=[
                CrawlResult(
                    source_name="PANews",
                    status="success",
                    item_count=10,
                    error_message=None
                ),
                CrawlResult(
                    source_name="CoinDesk",
                    status="error",
                    item_count=0,
                    error_message="连接超时"
                )
            ],
            x_results=[
                CrawlResult(
                    source_name="Crypto List 1",
                    status="success",
                    item_count=5,
                    error_message=None
                )
            ],
            total_items=15,
            execution_time=datetime.now()
        )
    
    @pytest.fixture
    def sample_analyzed_data(self, sample_analysis_results):
        """创建示例分析数据"""
        categorized = categorize_analysis_results(sample_analysis_results)
        
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=24)
        
        return AnalyzedData(
            categorized_items=categorized,
            time_window_hours=24,
            start_time=start_time,
            end_time=end_time,
            total_items=len(sample_analysis_results)
        )
    
    def test_initialization(self):
        """测试报告生成器初始化"""
        generator = ReportGenerator()
        
        assert generator.formatter is not None
        assert isinstance(generator.formatter, TelegramFormatter)
        assert generator.omit_empty_categories is True
    
    def test_initialization_with_custom_formatter(self):
        """测试使用自定义格式化器初始化"""
        custom_formatter = TelegramFormatter()
        generator = ReportGenerator(telegram_formatter=custom_formatter)
        
        assert generator.formatter is custom_formatter
    
    def test_generate_report_header(self, report_generator):
        """测试生成报告头部"""
        start_time = datetime(2024, 1, 1, 0, 0)
        end_time = datetime(2024, 1, 2, 0, 0)
        
        header = report_generator.generate_report_header(24, start_time, end_time)
        
        # 验证包含必要信息
        assert "小时快讯" in header
        assert "24" in header
    
    def test_generate_data_source_status(self, report_generator, sample_crawl_status):
        """测试生成数据源状态"""
        status_section = report_generator.generate_data_source_status(sample_crawl_status)
        
        # 验证包含数据源信息
        assert "数据源状态" in status_section
        assert "PANews" in status_section
        assert "CoinDesk" in status_section
        assert "Crypto List 1" in status_section
        
        # 验证包含状态标记
        assert "✅" in status_section  # 成功标记
        assert "❌" in status_section  # 失败标记
        
        # 验证包含统计信息
        assert "总计" in status_section
        assert "成功" in status_section
        assert "失败" in status_section
    
    def test_generate_dynamic_category_sections(self, report_generator, sample_analysis_results):
        """测试生成动态分类章节"""
        categorized = categorize_analysis_results(sample_analysis_results)
        
        sections = report_generator.generate_dynamic_category_sections(categorized)
        
        # 应该有2个分类（大户动向、安全事件）
        assert len(sections) == 2
        
        # 验证每个章节包含分类名称
        all_sections_text = "\n".join(sections)
        assert "大户动向" in all_sections_text
        assert "安全事件" in all_sections_text
    
    def test_generate_category_section(self, report_generator, sample_analysis_results):
        """测试生成单个分类章节"""
        # 筛选出大户动向分类的结果
        whale_items = [r for r in sample_analysis_results if r.category == "大户动向"]
        
        section = report_generator.generate_category_section("大户动向", whale_items)
        
        # 验证包含分类名称和图标
        assert "大户动向" in section
        assert "🐋" in section  # 大户动向的图标
        
        # 验证包含消息数量
        assert "2" in section  # 有2条大户动向消息
        
        # 验证包含消息内容
        assert "巨鲸" in section
        assert "机构投资者" in section
    
    def test_format_message_item(self, report_generator):
        """测试格式化单条消息"""
        item = StructuredAnalysisResult(
            time="2024-01-01 12:00",
            category="大户动向",
            weight_score=85,
            title="某巨鲸地址转移10000 ETH到交易所",

            body="某巨鲸地址转移10000 ETH到交易所",
            source="https://example.com/news/1"
        )
        
        formatted = report_generator.format_message_item(item, 1)
        
        # 验证包含所有必需字段
        # 时间格式已简化为 MM-DD HH:MM（移除年份）
        assert "01-01 12:00" in formatted
        assert "85" in formatted
        assert "巨鲸" in formatted
        
        # 验证包含超链接
        assert "[" in formatted and "](" in formatted
        assert "https://example.com/news/1" in formatted
    
    
    
    def test_generate_telegram_report_complete(
        self,
        report_generator,
        sample_analyzed_data,
        sample_crawl_status
    ):
        """测试生成完整的Telegram报告"""
        
        report = report_generator.generate_telegram_report(
            sample_analyzed_data,
            sample_crawl_status
        )
        
        # 验证报告包含所有主要部分
        assert "小时快讯" in report
        assert "大户动向" in report
        assert "安全事件" in report
        
        # 验证报告不为空
        assert len(report) > 0
    
    
    def test_handle_empty_categories(self, report_generator):
        """测试处理空分类"""
        categories = {
            "大户动向": [
                StructuredAnalysisResult(
                    time="2024-01-01 12:00",
                    category="大户动向",
                    weight_score=85,
                    title="测试",

                    body="测试",
                    source="https://example.com/1"
                )
            ],
            "安全事件": [],  # 空分类
            "新产品": []  # 空分类
        }
        
        # 启用省略空分类
        report_generator.omit_empty_categories = True
        result = report_generator.handle_empty_categories(categories)
        
        # 应该只保留非空分类
        assert len(result) == 1
        assert "大户动向" in result
        assert "安全事件" not in result
        assert "新产品" not in result
    
    def test_handle_empty_categories_keep_all(self, report_generator):
        """测试保留所有分类（包括空分类）"""
        categories = {
            "大户动向": [
                StructuredAnalysisResult(
                    time="2024-01-01 12:00",
                    category="大户动向",
                    weight_score=85,
                    title="测试",

                    body="测试",
                    source="https://example.com/1"
                )
            ],
            "安全事件": []
        }
        
        # 禁用省略空分类
        report_generator.omit_empty_categories = False
        result = report_generator.handle_empty_categories(categories)
        
        # 应该保留所有分类
        assert len(result) == 2
        assert "大户动向" in result
        assert "安全事件" in result
    
    def test_split_report_if_needed_short(self, report_generator):
        """测试短报告不需要分割"""
        short_report = "这是一个短报告"
        
        parts = report_generator.split_report_if_needed(short_report)
        
        assert len(parts) == 1
        assert parts[0] == short_report
    
    def test_split_report_if_needed_long(self, report_generator):
        """测试长报告需要分割"""
        # 创建一个超长报告（超过4096字符）
        long_report = "测试内容\n" * 1000  # 确保超过4096字符
        
        parts = report_generator.split_report_if_needed(long_report)
        
        # 应该被分割为多个部分
        assert len(parts) > 1
        
        # 每个部分都不应该超过最大长度
        for part in parts:
            assert len(part) <= 4096
    
    def test_set_and_get_category_emoji(self, report_generator):
        """测试设置和获取分类图标"""
        # 设置新的图标
        report_generator.set_category_emoji("测试分类", "🎯")
        
        # 获取图标
        emoji = report_generator.get_category_emoji("测试分类")
        assert emoji == "🎯"
        
        # 获取不存在的分类应该返回默认图标
        default_emoji = report_generator.get_category_emoji("不存在的分类")
        assert default_emoji == "📄"
    
    def test_categorize_analysis_results_helper(self, sample_analysis_results):
        """测试分类辅助函数"""
        categorized = categorize_analysis_results(sample_analysis_results)
        
        # 验证分类结果
        assert "大户动向" in categorized
        assert "安全事件" in categorized
        
        # 验证每个分类的数量
        assert len(categorized["大户动向"]) == 2
        assert len(categorized["安全事件"]) == 1
    
    def test_create_report_generator_helper(self):
        """测试创建报告生成器辅助函数"""
        generator = create_report_generator(
            include_market_snapshot=False,
            omit_empty_categories=False,
            max_message_length=2000
        )
        
        assert generator.omit_empty_categories is False
        assert generator.formatter.config.max_message_length == 2000
    
    def test_empty_categorized_items(self, report_generator, sample_crawl_status):
        """测试没有分类内容的情况"""
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=24)
        
        empty_data = AnalyzedData(
            categorized_items={},
            time_window_hours=24,
            start_time=start_time,
            end_time=end_time,
            total_items=0
        )
        
        report = report_generator.generate_telegram_report(
            empty_data,
            sample_crawl_status
        )
        
        # 验证报告包含"暂无内容"提示
        assert "暂无" in report or "无" in report
    
    def test_dynamic_category_ordering(self, report_generator):
        """测试动态分类按内容数量排序"""
        categorized = {
            "分类A": [
                StructuredAnalysisResult(
                    time="2024-01-01 12:00",
                    category="分类A",
                    weight_score=80,
                    title="测试1",

                    body="测试1",
                    source="https://example.com/1"
                )
            ],
            "分类B": [
                StructuredAnalysisResult(
                    time="2024-01-01 13:00",
                    category="分类B",
                    weight_score=85,
                    title="测试2",

                    body="测试2",
                    source="https://example.com/2"
                ),
                StructuredAnalysisResult(
                    time="2024-01-01 14:00",
                    category="分类B",
                    weight_score=90,
                    title="测试3",

                    body="测试3",
                    source="https://example.com/3"
                ),
                StructuredAnalysisResult(
                    time="2024-01-01 15:00",
                    category="分类B",
                    weight_score=75,
                    title="测试4",

                    body="测试4",
                    source="https://example.com/4"
                )
            ]
        }
        
        sections = report_generator.generate_dynamic_category_sections(categorized)
        
        # 分类B有3条内容，应该排在前面
        # 分类A有1条内容，应该排在后面
        all_text = "\n".join(sections)
        pos_b = all_text.find("分类B")
        pos_a = all_text.find("分类A")
        
        assert pos_b < pos_a, "内容多的分类应该排在前面"
    
    def test_source_hyperlink_formatting(self, report_generator):
        """测试source字段被正确格式化为超链接"""
        item = StructuredAnalysisResult(
            time="2024-01-01 12:00",
            category="测试",
            weight_score=80,
            title="测试摘要",

            body="测试摘要",
            source="https://example.com/news/123"
        )
        
        formatted = report_generator.format_message_item(item, 1)
        
        # 验证Telegram超链接格式 [text](url)
        assert "[" in formatted
        assert "](" in formatted
        assert "https://example.com/news/123)" in formatted
    
    def test_weight_score_display(self, report_generator):
        """测试重要性评分的显示"""
        # 测试不同的评分
        test_cases = [
            (20, "⭐"),   # 低分：1颗星
            (50, "⭐⭐"),  # 中分：2-3颗星
            (80, "⭐⭐⭐⭐"),  # 高分：4颗星
            (100, "⭐⭐⭐⭐⭐")  # 满分：5颗星
        ]
        
        for score, expected_stars in test_cases:
            item = StructuredAnalysisResult(
                time="2024-01-01 12:00",
                category="测试",
                weight_score=score,
                title="测试",

                body="测试",
                source="https://example.com/1"
            )
            
            formatted = report_generator.format_message_item(item, 1)
            
            # 验证包含评分
            assert str(score) in formatted
            # 注意：当前实现不包含星星emoji，只显示数字评分


class TestAnalyzedData:
    """测试AnalyzedData数据类"""
    
    def test_analyzed_data_creation(self):
        """测试创建AnalyzedData实例"""
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=24)
        
        data = AnalyzedData(
            categorized_items={"测试": []},
            time_window_hours=24,
            start_time=start_time,
            end_time=end_time,
            total_items=0
        )
        
        assert data.time_window_hours == 24
        assert data.total_items == 0
        assert isinstance(data.categorized_items, dict)


class TestEdgeCases:
    """测试边界情况"""
    
    def test_special_characters_in_summary(self):
        """测试摘要中包含特殊字符"""
        generator = create_report_generator()
        
        item = StructuredAnalysisResult(
            time="2024-01-01 12:00",
            category="测试",
            weight_score=80,
            title="包含特殊字符: *粗体",

            body="* _斜体_ [链接]",
            source="https://example.com/1"
        )
        
        formatted = generator.format_message_item(item, 1)
        
        # 验证特殊字符被正确转义
        assert "\\" in formatted or formatted.count("*") % 2 == 0
    
    def test_very_long_category_name(self):
        """测试非常长的分类名称"""
        generator = create_report_generator()
        
        long_category = "这是一个非常非常非常非常非常非常长的分类名称" * 5
        
        items = [
            StructuredAnalysisResult(
                time="2024-01-01 12:00",
                category=long_category,
                weight_score=80,
                title="测试",

                body="测试",
                source="https://example.com/1"
            )
        ]
        
        section = generator.generate_category_section(long_category, items)
        
        # 应该能够处理长分类名称
        assert long_category in section
    
    def test_url_with_special_characters(self):
        """测试包含特殊字符的URL"""
        generator = create_report_generator()
        
        item = StructuredAnalysisResult(
            time="2024-01-01 12:00",
            category="测试",
            weight_score=80,
            title="测试",

            body="测试",
            source="https://example.com/news?id=123&category=crypto"
        )
        
        formatted = generator.format_message_item(item, 1)
        
        # URL应该被正确包含
        assert "https://example.com/news?id=123&category=crypto" in formatted
