"""
报告系统集成测试

测试报告生成和Telegram发送的完整集成流程
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch
import tempfile
import os

from crypto_news_analyzer.models import ContentItem, CrawlStatus, CrawlResult, AnalysisResult
from crypto_news_analyzer.reporters import (
    ReportGenerator, 
    TelegramSender,
    TelegramConfig,
    AnalyzedData,
    create_analyzed_data,
    create_telegram_config
)


class TestReportSystemIntegration:
    """报告系统集成测试类"""
    
    def setup_method(self):
        """测试前置设置"""
        self.generator = ReportGenerator()
        self.telegram_config = TelegramConfig(
            bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
            channel_id="@test_channel"
        )
        self.sender = TelegramSender(self.telegram_config)
        
        # 创建测试数据
        self.test_time = datetime.now()
        self.test_items = [
            ContentItem(
                id="integration_test1",
                title="集成测试新闻1",
                content="这是一条用于集成测试的新闻内容，包含重要的市场信息。",
                url="https://example.com/integration1",
                publish_time=self.test_time,
                source_name="集成测试RSS源",
                source_type="rss"
            ),
            ContentItem(
                id="integration_test2",
                title="集成测试新闻2",
                content="这是另一条集成测试新闻，涉及监管政策变化。",
                url="https://example.com/integration2",
                publish_time=self.test_time - timedelta(hours=2),
                source_name="集成测试X源",
                source_type="x"
            )
        ]
        
        self.test_analysis_results = {
            "integration_test1": AnalysisResult(
                content_id="integration_test1",
                category="大户动向",
                confidence=0.90,
                reasoning="检测到重要的大户资金流动信息",
                should_ignore=False,
                key_points=["巨鲸转移", "市场影响"]
            ),
            "integration_test2": AnalysisResult(
                content_id="integration_test2",
                category="美国政府监管政策",
                confidence=0.85,
                reasoning="涉及重要的监管政策变化",
                should_ignore=False,
                key_points=["政策变化", "合规要求"]
            )
        }
        
        self.test_crawl_status = CrawlStatus(
            rss_results=[
                CrawlResult(source_name="集成测试RSS源", status="success", item_count=1, error_message=None)
            ],
            x_results=[
                CrawlResult(source_name="集成测试X源", status="success", item_count=1, error_message=None)
            ],
            total_items=2,
            execution_time=self.test_time
        )
    
    def test_complete_report_generation_workflow(self):
        """测试完整的报告生成工作流程"""
        # 创建分析数据
        categorized_items = {
            "大户动向": [self.test_items[0]],
            "美国政府监管政策": [self.test_items[1]],
            "安全事件": [],
            "新产品": [],
            "市场新现象": [],
            "利率事件": []
        }
        
        analyzed_data = create_analyzed_data(
            categorized_items,
            self.test_analysis_results,
            24,
            self.test_time
        )
        
        # 生成报告
        report = self.generator.generate_report(analyzed_data, self.test_crawl_status)
        
        # 验证报告完整性
        assert "# 加密货币新闻分析报告" in report
        assert "## 数据源爬取状态" in report
        assert "## 🐋 大户动向" in report
        assert "## 🏛️ 美国政府监管政策" in report
        assert "集成测试新闻1" in report
        assert "集成测试新闻2" in report
        assert "[查看原文](https://example.com/integration1)" in report
        assert "[查看原文](https://example.com/integration2)" in report
        
        # 验证状态表格
        assert "集成测试RSS源" in report
        assert "集成测试X源" in report
        assert "✅ success" in report
        
        # 验证分析结果
        assert "置信度: 0.90" in report
        assert "置信度: 0.85" in report
        assert "检测到重要的大户资金流动信息" in report
        assert "涉及重要的监管政策变化" in report
    
    @pytest.mark.asyncio
    @patch('aiohttp.ClientSession.post')
    async def test_successful_telegram_integration(self, mock_post):
        """测试成功的Telegram集成"""
        # 模拟成功的API响应
        mock_response = AsyncMock()
        mock_response.json.return_value = {
            "ok": True,
            "result": {"message_id": 123, "username": "test_bot"}
        }
        mock_post.return_value.__aenter__.return_value = mock_response
        
        # 生成报告
        categorized_items = {"大户动向": [self.test_items[0]]}
        analyzed_data = create_analyzed_data(
            categorized_items, self.test_analysis_results, 24, self.test_time
        )
        report = self.generator.generate_report(analyzed_data, self.test_crawl_status)
        
        # 发送报告
        async with self.sender:
            result = await self.sender.send_report(report)
        
        assert result.success is True
        assert result.message_id == 123
        assert result.parts_sent >= 1
    
    @pytest.mark.asyncio
    @patch('aiohttp.ClientSession.post')
    async def test_telegram_failure_with_backup(self, mock_post):
        """测试Telegram发送失败时的备份机制 - 需求 8.5"""
        # 模拟失败的API响应
        mock_response = AsyncMock()
        mock_response.json.return_value = {
            "ok": False,
            "description": "Unauthorized: bot token is invalid"
        }
        mock_post.return_value.__aenter__.return_value = mock_response
        
        # 生成报告
        categorized_items = {"大户动向": [self.test_items[0]]}
        analyzed_data = create_analyzed_data(
            categorized_items, self.test_analysis_results, 24, self.test_time
        )
        report = self.generator.generate_report(analyzed_data, self.test_crawl_status)
        
        # 尝试发送报告（应该失败）
        async with self.sender:
            result = await self.sender.send_report(report)
        
        assert result.success is False
        assert "Unauthorized" in result.error_message
        
        # 验证备份功能
        backup_path = self.sender.save_report_backup(report, "test_failure_backup.md")
        assert os.path.exists(backup_path)
        
        # 验证备份内容
        with open(backup_path, 'r', encoding='utf-8') as f:
            backup_content = f.read()
        assert backup_content == report
        
        # 清理测试文件
        os.remove(backup_path)
    
    def test_error_handling_in_report_generation(self):
        """测试报告生成中的错误处理"""
        # 测试无效数据
        invalid_data = AnalyzedData(
            categorized_items="invalid",  # 应该是字典
            analysis_results={},
            time_window_hours=24,
            start_time=self.test_time - timedelta(hours=24),
            end_time=self.test_time
        )
        
        # 应该生成错误报告而不是崩溃
        error_report = self.generator.generate_report(invalid_data, self.test_crawl_status)
        
        assert "错误报告" in error_report
        assert "❌ 报告生成失败" in error_report
        assert "## 数据源爬取状态" in error_report  # 状态表格应该仍然存在
    
    def test_large_report_splitting(self):
        """测试大型报告的分割功能"""
        # 创建大量内容项
        large_items = []
        large_analysis = {}
        
        for i in range(50):  # 创建50个内容项
            item = ContentItem(
                id=f"large_test_{i}",
                title=f"大型测试新闻 {i}",
                content="这是一条很长的测试新闻内容，" * 20,  # 很长的内容
                url=f"https://example.com/large_{i}",
                publish_time=self.test_time - timedelta(minutes=i),
                source_name=f"大型测试源 {i}",
                source_type="rss"
            )
            large_items.append(item)
            
            large_analysis[f"large_test_{i}"] = AnalysisResult(
                content_id=f"large_test_{i}",
                category="大户动向",
                confidence=0.8,
                reasoning=f"大型测试分析 {i}",
                should_ignore=False,
                key_points=[f"关键点 {i}"]
            )
        
        # 生成大型报告
        categorized_items = {"大户动向": large_items}
        analyzed_data = create_analyzed_data(
            categorized_items, large_analysis, 24, self.test_time
        )
        
        large_report = self.generator.generate_report(analyzed_data, self.test_crawl_status)
        
        # 测试消息分割
        message_parts = self.sender.split_long_message(large_report)
        
        # 验证分割结果
        assert len(message_parts) > 1  # 应该被分割成多个部分
        
        for part in message_parts:
            assert len(part) <= self.telegram_config.max_message_length
        
        # 验证所有内容都被包含
        combined_content = "".join(message_parts)
        assert "大型测试新闻 0" in combined_content
        assert "大型测试新闻 49" in combined_content
    
    def test_configuration_validation_integration(self):
        """测试配置验证集成 - 需求 8.6, 8.7"""
        # 测试有效配置
        valid_config = create_telegram_config(
            bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
            channel_id="@valid_channel"
        )
        
        assert valid_config.bot_token == "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
        assert valid_config.channel_id == "@valid_channel"
        
        # 测试无效配置
        from crypto_news_analyzer.reporters.telegram_sender import validate_telegram_credentials
        
        invalid_result = validate_telegram_credentials(
            "invalid_token",
            "invalid_channel"
        )
        
        assert invalid_result["valid"] is False
        assert len(invalid_result["errors"]) > 0
    
    def test_markdown_format_preservation(self):
        """测试Markdown格式保持 - 需求 8.4"""
        # 创建包含各种Markdown元素的报告
        categorized_items = {"大户动向": [self.test_items[0]]}
        analyzed_data = create_analyzed_data(
            categorized_items, self.test_analysis_results, 24, self.test_time
        )
        
        report = self.generator.generate_report(analyzed_data, self.test_crawl_status)
        
        # 格式化为Telegram格式
        formatted_report = self.sender.format_for_telegram(report)
        
        # 验证Markdown元素被保持
        assert formatted_report is not None
        assert len(formatted_report) > 0
        
        # 验证特殊字符被正确处理
        escaped_text = self.sender.escape_markdown("测试*粗体*和_斜体_文本")
        assert "\\*" in escaped_text
        assert "\\_" in escaped_text


class TestReportSystemErrorScenarios:
    """报告系统错误场景测试"""
    
    def setup_method(self):
        """测试前置设置"""
        self.generator = ReportGenerator()
        self.telegram_config = TelegramConfig(
            bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
            channel_id="@test_channel"
        )
    
    def test_empty_data_handling(self):
        """测试空数据处理"""
        empty_data = create_analyzed_data({}, {}, 24)
        empty_status = CrawlStatus([], [], 0, datetime.now())
        
        report = self.generator.generate_report(empty_data, empty_status)
        
        # 应该生成有效报告，即使没有内容
        assert "# 加密货币新闻分析报告" in report
        assert "## 数据源爬取状态" in report
        assert "*本时间窗口内暂无相关内容*" in report
    
    def test_partial_failure_handling(self):
        """测试部分失败处理"""
        # 创建包含成功和失败源的状态
        mixed_status = CrawlStatus(
            rss_results=[
                CrawlResult(source_name="成功RSS源", status="success", item_count=1, error_message=None),
                CrawlResult(source_name="失败RSS源", status="error", item_count=0, error_message="连接超时")
            ],
            x_results=[
                CrawlResult(source_name="失败X源", status="error", item_count=0, error_message="认证失败")
            ],
            total_items=1,
            execution_time=datetime.now()
        )
        
        empty_data = create_analyzed_data({}, {}, 24)
        report = self.generator.generate_report(empty_data, mixed_status)
        
        # 验证错误信息被包含
        assert "成功RSS源" in report
        assert "失败RSS源" in report
        assert "失败X源" in report
        assert "连接超时" in report
        assert "认证失败" in report
        assert "❌ error" in report
        assert "✅ success" in report
    
    @pytest.mark.asyncio
    async def test_network_timeout_handling(self):
        """测试网络超时处理"""
        sender = TelegramSender(self.telegram_config)
        
        # 模拟网络超时
        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_post.side_effect = asyncio.TimeoutError("Request timeout")
            
            async with sender:
                result = await sender.send_report("测试消息")
            
            assert result.success is False
            assert "Request timeout" in result.error_message


if __name__ == "__main__":
    pytest.main([__file__])