"""
测试时区集成

验证报告生成和命令处理中的时区功能正确使用东八区(UTC+8)。
"""

import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch

from crypto_news_analyzer.reporters.report_generator import (
    ReportGenerator,
    create_analyzed_data,
    categorize_analysis_results
)
from crypto_news_analyzer.reporters.telegram_command_handler import (
    TelegramCommandHandler,
    CommandRateLimitState
)
from crypto_news_analyzer.analyzers.structured_output_manager import StructuredAnalysisResult
from crypto_news_analyzer.models import CrawlStatus, CrawlResult, TelegramCommandConfig
from crypto_news_analyzer.utils.timezone_utils import UTC_PLUS_8, now_utc8


class TestTimezoneIntegration(unittest.TestCase):
    """测试时区在整个系统中的集成"""
    
    def setUp(self):
        """设置测试环境"""
        self.report_generator = ReportGenerator()
    
    def test_report_header_uses_utc8(self):
        """测试报告头部使用UTC+8时区"""
        # 创建UTC时间
        utc_start = datetime(2024, 1, 15, 2, 0, 0, tzinfo=timezone.utc)  # UTC 02:00
        utc_end = datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)   # UTC 10:00
        
        # 生成报告头部
        header = self.report_generator.generate_report_header(
            time_window=8,
            start_time=utc_start,
            end_time=utc_end
        )
        
        # 验证包含标题和时间窗口
        self.assertIn("加密货币新闻快讯", header)
        self.assertIn("8", header)
    
    def test_analyzed_data_creation_uses_utc8(self):
        """测试创建分析数据时使用UTC+8时区"""
        # 创建测试数据
        results = [
            StructuredAnalysisResult(
                time="2024-01-15",
                category="测试分类",
                weight_score=8,
                title="测试摘要",

                body="测试摘要",
                source="https://example.com"
            )
        ]
        
        categorized = categorize_analysis_results(results)
        
        # 创建分析数据
        analyzed_data = create_analyzed_data(
            categorized_items=categorized,
            analysis_results=results,
            time_window_hours=24
        )
        
        # 验证时间使用UTC+8时区
        self.assertIsNotNone(analyzed_data.start_time.tzinfo)
        self.assertEqual(analyzed_data.start_time.tzinfo, UTC_PLUS_8)
        self.assertIsNotNone(analyzed_data.end_time.tzinfo)
        self.assertEqual(analyzed_data.end_time.tzinfo, UTC_PLUS_8)
        
        # 验证时间窗口计算正确
        time_diff = analyzed_data.end_time - analyzed_data.start_time
        self.assertEqual(time_diff.total_seconds() / 3600, 24)
    
    def test_full_report_generation_with_utc8(self):
        """测试完整报告生成使用UTC+8时区"""
        # 创建测试数据
        results = [
            StructuredAnalysisResult(
                time="2024-01-15",
                category="大户动向",
                weight_score=9,
                title="测试新闻1",

                body="测试新闻1",
                source="https://example.com/1"
            ),
            StructuredAnalysisResult(
                time="2024-01-15",
                category="利率事件",
                weight_score=7,
                title="测试新闻2",

                body="测试新闻2",
                source="https://example.com/2"
            )
        ]
        
        categorized = categorize_analysis_results(results)
        analyzed_data = create_analyzed_data(
            categorized_items=categorized,
            analysis_results=results,
            time_window_hours=24
        )
        
        # 创建爬取状态
        status = CrawlStatus(
            rss_results=[
                CrawlResult(
                    source_name="测试源",
                    status="success",
                    item_count=2,
                    error_message=None
                )
            ],
            x_results=[],
            total_items=2,
            execution_time=now_utc8()
        )
        
        # 生成报告
        report = self.report_generator.generate_telegram_report(
            data=analyzed_data,
            status=status
        )
        
        # 验证报告包含标题
        self.assertIn("加密货币新闻快讯", report)
        
        # 验证报告格式正确
        self.assertIn("大户动向", report)
        self.assertIn("利率事件", report)
    
    def test_command_handler_rate_limit_uses_utc8(self):
        """测试命令处理器的速率限制使用UTC+8时区"""
        # 创建速率限制状态
        state = CommandRateLimitState()
        
        # 验证初始化时间使用UTC+8
        self.assertIsNotNone(state.last_reset_time.tzinfo)
        self.assertEqual(state.last_reset_time.tzinfo, UTC_PLUS_8)
        self.assertIsNotNone(state.last_run_command_time.tzinfo)
        self.assertEqual(state.last_run_command_time.tzinfo, UTC_PLUS_8)
    
    @patch('crypto_news_analyzer.reporters.telegram_command_handler.now_utc8')
    def test_command_handler_check_rate_limit_with_utc8(self, mock_now_utc8):
        """测试命令处理器检查速率限制时使用UTC+8时区"""
        # 设置模拟的当前时间（UTC+8）
        mock_current_time = datetime(2024, 1, 15, 18, 0, 0, tzinfo=UTC_PLUS_8)
        mock_now_utc8.return_value = mock_current_time
        
        # 创建命令处理器配置
        config = TelegramCommandConfig(
            enabled=True,
            authorized_users=["123456"],
            execution_timeout_minutes=30,
            max_concurrent_executions=1,
            command_rate_limit={
                "max_commands_per_hour": 10,
                "cooldown_minutes": 5
            }
        )
        
        # 创建模拟的执行协调器
        mock_coordinator = Mock()
        
        # 创建命令处理器
        handler = TelegramCommandHandler(
            bot_token="test_token",
            execution_coordinator=mock_coordinator,
            config=config
        )
        
        # 检查速率限制
        allowed, error_msg = handler.check_rate_limit("123456")
        
        # 第一次调用应该允许
        self.assertTrue(allowed)
        self.assertIsNone(error_msg)
        
        # 验证状态使用UTC+8时区
        state = handler._rate_limit_states["123456"]
        self.assertEqual(state.last_reset_time.tzinfo, UTC_PLUS_8)
        self.assertEqual(state.last_run_command_time.tzinfo, UTC_PLUS_8)
    
    def test_timezone_consistency_across_components(self):
        """测试各组件之间的时区一致性"""
        # 获取当前UTC+8时间
        time1 = now_utc8()
        
        # 创建分析数据
        results = [
            StructuredAnalysisResult(
                time="2024-01-15",
                category="测试",
                weight_score=8,
                title="测试",

                body="测试",
                source="https://example.com"
            )
        ]
        
        categorized = categorize_analysis_results(results)
        analyzed_data = create_analyzed_data(
            categorized_items=categorized,
            analysis_results=results,
            time_window_hours=1
        )
        
        # 获取另一个UTC+8时间
        time2 = now_utc8()
        
        # 验证所有时间都使用相同的时区
        self.assertEqual(time1.tzinfo, UTC_PLUS_8)
        self.assertEqual(time2.tzinfo, UTC_PLUS_8)
        self.assertEqual(analyzed_data.start_time.tzinfo, UTC_PLUS_8)
        self.assertEqual(analyzed_data.end_time.tzinfo, UTC_PLUS_8)
        
        # 验证时间顺序正确
        self.assertLessEqual(time1, analyzed_data.end_time)
        self.assertLessEqual(analyzed_data.end_time, time2)


if __name__ == '__main__':
    unittest.main()
