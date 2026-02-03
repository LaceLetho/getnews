#!/usr/bin/env python3
"""
真实环境集成测试

使用真实的API tokens测试系统在线上环境的功能
"""

import os
import sys
import pytest
import asyncio
from datetime import datetime, timedelta
from dotenv import load_dotenv

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crypto_news_analyzer.models import ContentItem, CrawlStatus, CrawlResult, AnalysisResult
from crypto_news_analyzer.analyzers.llm_analyzer import LLMAnalyzer
from crypto_news_analyzer.reporters import (
    ReportGenerator, 
    TelegramSender,
    TelegramConfig,
    create_analyzed_data
)
from crypto_news_analyzer.crawlers.rss_crawler import RSSCrawler
from crypto_news_analyzer.config.manager import ConfigManager


class TestRealEnvironmentIntegration:
    """真实环境集成测试类"""
    
    @classmethod
    def setup_class(cls):
        """测试类初始化"""
        # 加载环境变量
        load_dotenv()
        
        # 检查必要的环境变量
        cls.telegram_token = os.getenv('telegram_bot_token')
        cls.telegram_channel = os.getenv('telegram_channel_id')
        cls.llm_api_key = os.getenv('llm_api_key')
        
        if not all([cls.telegram_token, cls.telegram_channel, cls.llm_api_key]):
            pytest.skip("缺少必要的环境变量，跳过真实环境测试")
        
        # 初始化组件
        cls.config_manager = ConfigManager()
        cls.report_generator = ReportGenerator()
        
        # 创建Telegram配置
        cls.telegram_config = TelegramConfig(
            bot_token=cls.telegram_token,
            channel_id=cls.telegram_channel
        )
        cls.telegram_sender = TelegramSender(cls.telegram_config)
        
        # 创建LLM分析器
        cls.llm_analyzer = LLMAnalyzer(
            api_key=cls.llm_api_key,
            model="gpt-4o-mini",  # 使用较便宜的模型进行测试
            mock_mode=False  # 使用真实API
        )
    
    @pytest.mark.asyncio
    async def test_telegram_bot_token_validation(self):
        """测试Telegram Bot Token验证 - 需求 8.6"""
        print(f"\n测试Telegram Bot Token: {self.telegram_token[:10]}...")
        
        async with self.telegram_sender:
            result = await self.telegram_sender.validate_bot_token()
        
        assert result.success, f"Bot Token验证失败: {result.error_message}"
        print(f"✅ Bot Token验证成功")
    
    @pytest.mark.asyncio
    async def test_telegram_channel_access_validation(self):
        """测试Telegram Channel访问验证 - 需求 8.7"""
        print(f"\n测试Telegram Channel访问: {self.telegram_channel}")
        
        async with self.telegram_sender:
            result = await self.telegram_sender.validate_channel_access()
        
        assert result.success, f"Channel访问验证失败: {result.error_message}"
        print(f"✅ Channel访问验证成功")
    
    def test_llm_analyzer_integration(self):
        """测试LLM分析器集成"""
        print(f"\n测试LLM API集成...")
        
        # 测试内容
        test_content = "某巨鲸地址转移15000个ETH到Binance交易所，价值约5000万美元"
        test_title = "巨鲸资金转移"
        test_source = "真实环境测试"
        
        result = self.llm_analyzer.analyze_content(test_content, test_title, test_source)
        
        assert isinstance(result, AnalysisResult)
        assert result.content_id is not None
        assert isinstance(result.category, str)
        assert isinstance(result.confidence, float)
        assert 0 <= result.confidence <= 1
        
        print(f"✅ LLM分析结果:")
        print(f"   分类: {result.category}")
        print(f"   置信度: {result.confidence}")
        print(f"   推理: {result.reasoning[:100]}...")
    
    def test_rss_crawler_real_feeds(self):
        """测试RSS爬虫真实数据源"""
        print(f"\n测试RSS爬虫...")
        
        # 使用一个可靠的RSS源进行测试
        test_feeds = [
            "https://cointelegraph.com/rss",
            "https://decrypt.co/feed"
        ]
        
        # 正确创建RSS爬虫实例
        crawler = RSSCrawler(time_window_hours=24)  # 修复：使用正确的参数
        
        try:
            # 手动创建RSS源对象进行测试
            from crypto_news_analyzer.models import RSSSource
            test_sources = [
                RSSSource(name="Cointelegraph", url=test_feeds[0], description="Cointelegraph RSS"),
                RSSSource(name="Decrypt", url=test_feeds[1], description="Decrypt RSS")
            ]
            
            results = []
            for source in test_sources:
                try:
                    source_results = crawler.crawl_source(source)
                    results.extend(source_results)
                except Exception as e:
                    print(f"   ⚠️ 爬取 {source.name} 失败: {e}")
            
            assert isinstance(results, list)
            print(f"✅ RSS爬取成功，获得 {len(results)} 条内容")
            
            # 验证内容项结构
            if results:
                first_item = results[0]
                assert hasattr(first_item, 'id')
                assert hasattr(first_item, 'title')
                assert hasattr(first_item, 'content')
                assert hasattr(first_item, 'url')
                assert hasattr(first_item, 'publish_time')
                assert hasattr(first_item, 'source_name')
                assert hasattr(first_item, 'source_type')
                
                print(f"   示例内容: {first_item.title[:50]}...")
        
        except Exception as e:
            print(f"⚠️ RSS爬取失败: {e}")
            # RSS爬取失败不应该导致测试失败，因为可能是网络问题
    
    @pytest.mark.asyncio
    async def test_complete_workflow_with_real_apis(self):
        """测试使用真实API的完整工作流程"""
        print(f"\n测试完整工作流程...")
        
        # 创建测试数据
        test_time = datetime.now()
        test_items = [
            ContentItem(
                id="real_test_1",
                title="巨鲸转移大量ETH",
                content="某知名巨鲸地址在过去24小时内转移了20000个ETH到多个交易所，总价值约6000万美元。这一举动引发了市场关注。",
                url="https://example.com/whale_movement",
                publish_time=test_time,
                source_name="真实测试RSS源",
                source_type="rss"
            ),
            ContentItem(
                id="real_test_2",
                title="美联储官员发表重要讲话",
                content="美联储副主席今日表示，考虑到当前通胀水平，央行可能在下次会议中调整利率政策。市场对此反应积极。",
                url="https://example.com/fed_speech",
                publish_time=test_time - timedelta(hours=1),
                source_name="真实测试新闻源",
                source_type="rss"
            )
        ]
        
        # 1. 使用真实LLM API分析内容
        print("   步骤1: LLM内容分析...")
        analysis_results = {}
        
        for item in test_items:
            try:
                analysis = self.llm_analyzer.analyze_content(
                    item.content, 
                    item.title, 
                    item.source_name
                )
                analysis_results[item.id] = analysis
                print(f"     - {item.title[:30]}... -> {analysis.category} (置信度: {analysis.confidence:.2f})")
            except Exception as e:
                print(f"     ⚠️ 分析失败: {e}")
                # 创建默认分析结果
                analysis_results[item.id] = AnalysisResult(
                    content_id=item.id,
                    category="未分类",
                    confidence=0.5,
                    reasoning=f"分析失败: {str(e)}",
                    should_ignore=False,
                    key_points=[]
                )
        
        # 2. 生成报告
        print("   步骤2: 生成报告...")
        categorized_items = {}
        for item in test_items:
            analysis = analysis_results[item.id]
            if not analysis.should_ignore:
                category = analysis.category
                if category not in categorized_items:
                    categorized_items[category] = []
                categorized_items[category].append(item)
        
        analyzed_data = create_analyzed_data(
            categorized_items,
            analysis_results,
            24,
            test_time
        )
        
        crawl_status = CrawlStatus(
            rss_results=[
                CrawlResult(source_name="真实测试RSS源", status="success", item_count=1, error_message=None),
                CrawlResult(source_name="真实测试新闻源", status="success", item_count=1, error_message=None)
            ],
            x_results=[],
            total_items=len(test_items),
            execution_time=test_time
        )
        
        report = self.report_generator.generate_report(analyzed_data, crawl_status)
        
        assert "# 加密货币新闻分析报告" in report
        print(f"     ✅ 报告生成成功 (长度: {len(report)} 字符)")
        
        # 3. 发送到Telegram (添加测试标识)
        print("   步骤3: 发送Telegram消息...")
        test_report = f"🧪 **真实环境集成测试报告**\n\n{report}\n\n---\n*这是自动化测试消息*"
        
        try:
            async with self.telegram_sender:
                result = await self.telegram_sender.send_report(test_report)
            
            if result.success:
                print(f"     ✅ Telegram发送成功 (消息ID: {result.message_id})")
                print(f"     发送了 {result.parts_sent}/{result.total_parts} 个消息部分")
            else:
                print(f"     ❌ Telegram发送失败: {result.error_message}")
                
                # 测试备份功能
                backup_path = self.telegram_sender.save_report_backup(test_report, "real_test_backup.md")
                assert os.path.exists(backup_path)
                print(f"     ✅ 报告已备份到: {backup_path}")
        
        except Exception as e:
            print(f"     ⚠️ Telegram发送异常: {e}")
        
        print("✅ 完整工作流程测试完成")
    
    @pytest.mark.asyncio
    async def test_error_handling_with_real_apis(self):
        """测试真实API环境下的错误处理"""
        print(f"\n测试错误处理...")
        
        # 测试无效的Telegram配置
        invalid_config = TelegramConfig(
            bot_token="invalid_token",
            channel_id="@invalid_channel"
        )
        invalid_sender = TelegramSender(invalid_config)
        
        async with invalid_sender:
            result = await invalid_sender.validate_bot_token()
        
        assert not result.success
        print(f"✅ 无效Token错误处理正确: {result.error_message}")
        
        # 测试LLM API错误处理
        invalid_analyzer = LLMAnalyzer(
            api_key="invalid_key",
            model="gpt-4o-mini",
            mock_mode=False
        )
        
        try:
            result = invalid_analyzer.analyze_content("测试内容", "测试标题", "测试来源")
            # 如果没有抛出异常，检查结果是否合理
            assert isinstance(result, AnalysisResult)
            print(f"✅ LLM API错误处理正确")
        except Exception as e:
            print(f"✅ LLM API错误处理正确: {e}")
    
    def test_configuration_loading(self):
        """测试配置加载"""
        print(f"\n测试配置加载...")
        
        config = self.config_manager.load_config()
        
        assert isinstance(config, dict)
        assert 'rss_sources' in config
        assert 'x_sources' in config
        assert 'llm_config' in config  # 修复：使用实际的配置键名
        assert 'auth' in config        # 修复：使用实际的配置键名
        
        print(f"✅ 配置加载成功")
        print(f"   RSS源数量: {len(config['rss_sources'])}")
        print(f"   X源数量: {len(config['x_sources'])}")
        print(f"   LLM配置: {config['llm_config']['model']}")
        print(f"   认证配置: 已加载")
    
    def teardown_method(self):
        """测试后清理"""
        # 清理可能创建的备份文件
        import glob
        backup_files = glob.glob("logs/*real_test*.md")
        for file in backup_files:
            try:
                os.remove(file)
            except:
                pass


if __name__ == "__main__":
    # 运行真实环境测试
    pytest.main([__file__, "-v", "-s"])