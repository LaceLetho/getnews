#!/usr/bin/env python3
"""
MiniMax LLM 分析器测试

正式的 MiniMax M2.1 集成测试，用于验证 LLMAnalyzer 功能
"""

import os
import sys
import unittest
import logging
from datetime import datetime
from dotenv import load_dotenv

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crypto_news_analyzer.analyzers.llm_analyzer import LLMAnalyzer
from crypto_news_analyzer.models import ContentItem

# 加载环境变量
load_dotenv()

class TestMiniMaxLLMAnalyzer(unittest.TestCase):
    """MiniMax LLM 分析器测试类"""
    
    @classmethod
    def setUpClass(cls):
        """测试类初始化"""
        # 配置日志
        logging.basicConfig(level=logging.WARNING)
        
        # 获取 API key
        cls.api_key = os.getenv('llm_api_key')
        if not cls.api_key:
            raise unittest.SkipTest("未找到 llm_api_key 环境变量")
    
    def setUp(self):
        """每个测试方法的初始化"""
        self.analyzer = LLMAnalyzer(
            api_key=self.api_key,
            model="MiniMax-M2.1",
            mock_mode=False
        )
    
    def test_whale_movement_analysis(self):
        """测试大户动向分析"""
        content = """
        据报道，一个巨鲸地址在过去24小时内向Binance转移了15000个ETH，
        价值约5000万美元。这笔大额转移引发了市场关注，
        分析师认为可能会对ETH价格产生短期影响。
        """
        
        result = self.analyzer.analyze_content(
            content=content,
            title="巨鲸向Binance转移15000个ETH",
            source="测试来源"
        )
        
        self.assertEqual(result.category, "大户动向")
        self.assertGreater(result.confidence, 0.8)
        self.assertFalse(result.should_ignore)
        self.assertIsInstance(result.key_points, list)
    
    def test_interest_rate_analysis(self):
        """测试利率事件分析"""
        content = """
        美联储最新会议纪要显示，多数委员支持在下次会议中考虑降息25个基点，
        以应对通胀压力的缓解。市场对此反应积极，加密货币价格普遍上涨。
        """
        
        result = self.analyzer.analyze_content(
            content=content,
            title="美联储会议纪要显示降息预期",
            source="测试来源"
        )
        
        self.assertEqual(result.category, "利率事件")
        self.assertGreater(result.confidence, 0.8)
        self.assertFalse(result.should_ignore)
    
    def test_regulatory_policy_analysis(self):
        """测试监管政策分析"""
        content = """
        美国证券交易委员会(SEC)宣布对一个主要的DeFi协议展开正式调查，
        涉嫌违反证券法规。该协议代币价格应声下跌超过20%。
        """
        
        result = self.analyzer.analyze_content(
            content=content,
            title="SEC对DeFi协议展开调查",
            source="测试来源"
        )
        
        self.assertEqual(result.category, "美国政府监管政策")
        self.assertGreater(result.confidence, 0.8)
        self.assertFalse(result.should_ignore)
    
    def test_security_event_analysis(self):
        """测试安全事件分析"""
        content = """
        一个主要的DeFi协议今日遭受重入攻击，黑客利用智能合约漏洞
        盗取了价值500万美元的加密货币。协议团队已暂停合约并展开调查。
        """
        
        result = self.analyzer.analyze_content(
            content=content,
            title="DeFi协议遭受黑客攻击损失500万美元",
            source="测试来源"
        )
        
        self.assertEqual(result.category, "安全事件")
        self.assertGreater(result.confidence, 0.8)
        self.assertFalse(result.should_ignore)
    
    def test_advertisement_filtering(self):
        """测试广告内容过滤"""
        content = """
        🚀超高收益率DeFi挖矿项目，立即参与！
        千载难逢的机会！我们的DeFi项目提供1000%年化收益率，
        现在加入还有额外奖励！立即点击链接参与！
        """
        
        result = self.analyzer.analyze_content(
            content=content,
            title="🚀超高收益率DeFi挖矿项目，立即参与！",
            source="测试来源"
        )
        
        self.assertTrue(result.should_ignore)
        self.assertGreater(result.confidence, 0.8)
    
    def test_batch_analysis(self):
        """测试批量分析功能"""
        test_items = [
            ContentItem(
                id="test_1",
                title="巨鲸转移大额ETH",
                content="某巨鲸地址转移10000个ETH到交易所",
                source_name="测试来源",
                url="https://example.com/1",
                publish_time=datetime.now(),
                source_type="rss"
            ),
            ContentItem(
                id="test_2",
                title="美联储政策变化",
                content="美联储暗示可能在下次会议中调整利率政策",
                source_name="测试来源",
                url="https://example.com/2",
                publish_time=datetime.now(),
                source_type="rss"
            )
        ]
        
        results = self.analyzer.batch_analyze(test_items)
        
        self.assertEqual(len(results), 2)
        for result in results:
            self.assertIsNotNone(result.category)
            self.assertGreater(result.confidence, 0.0)
    
    def test_mock_mode(self):
        """测试模拟模式"""
        mock_analyzer = LLMAnalyzer(
            api_key="fake_key",
            model="MiniMax-M2.1",
            mock_mode=True
        )
        
        result = mock_analyzer.analyze_content(
            content="巨鲸地址转移15000个ETH到Binance交易所",
            title="巨鲸资金转移",
            source="模拟测试"
        )
        
        self.assertIsNotNone(result.category)
        self.assertGreater(result.confidence, 0.0)


class TestMiniMaxLLMAnalyzerIntegration(unittest.TestCase):
    """MiniMax LLM 分析器集成测试"""
    
    @classmethod
    def setUpClass(cls):
        """测试类初始化"""
        cls.api_key = os.getenv('llm_api_key')
        if not cls.api_key:
            raise unittest.SkipTest("未找到 llm_api_key 环境变量")
    
    def test_error_handling(self):
        """测试错误处理"""
        # 使用无效的 API key
        analyzer = LLMAnalyzer(
            api_key="invalid_key",
            model="MiniMax-M2.1",
            mock_mode=False
        )
        
        result = analyzer.analyze_content(
            content="测试内容",
            title="测试标题",
            source="测试来源"
        )
        
        # 应该返回默认结果而不是抛出异常
        self.assertEqual(result.category, "未分类")
        self.assertEqual(result.confidence, 0.0)
        self.assertIn("分析失败", result.reasoning)
    
    def test_json_parsing(self):
        """测试JSON解析功能"""
        analyzer = LLMAnalyzer(
            api_key=self.api_key,
            model="MiniMax-M2.1",
            mock_mode=False
        )
        
        # 测试包含 <think> 标签的响应解析
        test_response = '''<think>
        这是思考过程
        </think>
        
        {
            "category": "大户动向",
            "confidence": 0.95,
            "reasoning": "测试推理",
            "should_ignore": false,
            "key_points": ["测试点1", "测试点2"]
        }'''
        
        parsed = analyzer.parse_llm_response(test_response)
        
        self.assertEqual(parsed.category, "大户动向")
        self.assertEqual(parsed.confidence, 0.95)
        self.assertEqual(parsed.reasoning, "测试推理")
        self.assertFalse(parsed.should_ignore)
        self.assertEqual(len(parsed.key_points), 2)


if __name__ == '__main__':
    # 运行测试
    unittest.main(verbosity=2)