#!/usr/bin/env python3
"""
LLM分析器单元测试

测试提示词构建、响应解析和各种分类场景的边界情况
"""

import os
import sys
import unittest
import json
import tempfile
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crypto_news_analyzer.analyzers.llm_analyzer import LLMAnalyzer, LLMResponse, ContentClassifier
from crypto_news_analyzer.analyzers.prompt_manager import PromptManager, DynamicCategoryManager, CategoryConfig
from crypto_news_analyzer.models import ContentItem, AnalysisResult


class TestPromptConstruction(unittest.TestCase):
    """测试提示词构建功能"""
    
    def setUp(self):
        """测试初始化"""
        # 创建临时配置文件
        self.temp_config = {
            "prompt_template": "分析以下内容：\n\n{categories_description}\n\n忽略标准：\n{ignore_criteria}\n\n内容：{content}\n标题：{title}\n来源：{source}\n\n{output_format}",
            "categories": {
                "大户动向": {
                    "description": "大户资金流动和态度变化",
                    "criteria": ["巨鲸资金流入流出", "大户态度变化"],
                    "examples": ["某巨鲸地址转移10000 ETH"],
                    "priority": 1
                },
                "利率事件": {
                    "description": "美联储相关的利率政策事件",
                    "criteria": ["美联储委员发言", "FOMC会议"],
                    "examples": ["鲍威尔发表鹰派言论"],
                    "priority": 1
                }
            },
            "ignore_criteria": [
                "广告和软文",
                "重复信息",
                "情绪发泄"
            ],
            "output_format": "请以JSON格式输出结果",
            "llm_settings": {
                "temperature": 0.1,
                "max_tokens": 1000,
                "model": "gpt-4"
            }
        }
        
        # 创建临时配置文件
        self.temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
        json.dump(self.temp_config, self.temp_file, ensure_ascii=False, indent=2)
        self.temp_file.close()
        
        self.prompt_manager = PromptManager(self.temp_file.name)
    
    def tearDown(self):
        """清理临时文件"""
        os.unlink(self.temp_file.name)
    
    def test_load_prompt_template(self):
        """测试加载提示词模板"""
        template = self.prompt_manager.load_prompt_template()
        
        self.assertIn("{categories_description}", template)
        self.assertIn("{ignore_criteria}", template)
        self.assertIn("{content}", template)
        self.assertIn("{title}", template)
        self.assertIn("{source}", template)
        self.assertIn("{output_format}", template)
    
    def test_load_categories_config(self):
        """测试加载分类配置"""
        categories = self.prompt_manager.load_categories_config()
        
        self.assertIn("大户动向", categories)
        self.assertIn("利率事件", categories)
        
        whale_category = categories["大户动向"]
        self.assertEqual(whale_category.name, "大户动向")
        self.assertEqual(whale_category.description, "大户资金流动和态度变化")
        self.assertIn("巨鲸资金流入流出", whale_category.criteria)
        self.assertIn("某巨鲸地址转移10000 ETH", whale_category.examples)
        self.assertEqual(whale_category.priority, 1)
    
    def test_build_analysis_prompt(self):
        """测试构建分析提示词"""
        content = "某巨鲸地址转移15000个ETH到交易所"
        title = "巨鲸资金转移"
        source = "测试来源"
        
        prompt = self.prompt_manager.build_analysis_prompt(content, title, source)
        
        # 验证提示词包含所有必要信息
        self.assertIn(content, prompt)
        self.assertIn(title, prompt)
        self.assertIn(source, prompt)
        self.assertIn("大户动向", prompt)
        self.assertIn("利率事件", prompt)
        self.assertIn("广告和软文", prompt)
        self.assertIn("请以JSON格式输出结果", prompt)
    
    def test_validate_prompt_template(self):
        """测试提示词模板验证"""
        # 测试有效模板
        valid_template = "分析：{categories_description}{ignore_criteria}{content}{title}{source}{output_format}"
        self.assertTrue(self.prompt_manager.validate_prompt_template(valid_template))
        
        # 测试无效模板（缺少占位符）
        invalid_template = "分析：{content}{title}"
        self.assertFalse(self.prompt_manager.validate_prompt_template(invalid_template))
    
    def test_get_llm_settings(self):
        """测试获取LLM设置"""
        settings = self.prompt_manager.get_llm_settings()
        
        self.assertEqual(settings["temperature"], 0.1)
        self.assertEqual(settings["max_tokens"], 1000)
        # 现在从主配置文件读取，应该是 MiniMax-M2.1
        self.assertEqual(settings["model"], "MiniMax-M2.1")


class TestResponseParsing(unittest.TestCase):
    """测试响应解析功能"""
    
    def setUp(self):
        """测试初始化"""
        self.analyzer = LLMAnalyzer(
            api_key="test_key",
            model="test_model",
            mock_mode=True
        )
    
    def test_parse_valid_json_response(self):
        """测试解析有效的JSON响应"""
        json_response = json.dumps({
            "category": "大户动向",
            "confidence": 0.95,
            "reasoning": "这是典型的巨鲸资金流动事件",
            "should_ignore": False,
            "key_points": ["巨鲸转移", "大额交易"]
        }, ensure_ascii=False)
        
        parsed = self.analyzer.parse_llm_response(json_response)
        
        self.assertEqual(parsed.category, "大户动向")
        self.assertEqual(parsed.confidence, 0.95)
        self.assertEqual(parsed.reasoning, "这是典型的巨鲸资金流动事件")
        self.assertFalse(parsed.should_ignore)
        self.assertEqual(len(parsed.key_points), 2)
        self.assertIn("巨鲸转移", parsed.key_points)
    
    def test_parse_response_with_think_tags(self):
        """测试解析包含<think>标签的响应"""
        response_with_think = """<think>
        这个内容涉及大额资金转移，应该归类为大户动向。
        置信度较高，因为有具体的数额和地址信息。
        </think>
        
        {
            "category": "大户动向",
            "confidence": 0.92,
            "reasoning": "涉及大额ETH转移，符合巨鲸活动特征",
            "should_ignore": false,
            "key_points": ["15000 ETH", "交易所转移"]
        }"""
        
        parsed = self.analyzer.parse_llm_response(response_with_think)
        
        self.assertEqual(parsed.category, "大户动向")
        self.assertEqual(parsed.confidence, 0.92)
        self.assertFalse(parsed.should_ignore)
        self.assertEqual(len(parsed.key_points), 2)
    
    def test_parse_malformed_json_response(self):
        """测试解析格式错误的JSON响应"""
        malformed_json = '{"category": "invalid_category", "confidence": 0.95, "reasoning": "测试"'  # 缺少结束括号
        
        parsed = self.analyzer.parse_llm_response(malformed_json)
        
        # 应该返回默认值而不是抛出异常
        self.assertEqual(parsed.category, "未分类")
        self.assertEqual(parsed.confidence, 0.5)  # 文本解析的默认置信度
        self.assertIsInstance(parsed.reasoning, str)
    
    def test_parse_text_response_fallback(self):
        """测试文本响应的备用解析"""
        text_response = "这个内容属于大户动向类别，因为涉及巨鲸资金转移。应该忽略这类广告内容。"
        
        parsed = self.analyzer.parse_llm_response(text_response)
        
        # 应该能从文本中提取基本信息
        self.assertIsInstance(parsed.category, str)
        self.assertIsInstance(parsed.confidence, float)
        self.assertIsInstance(parsed.reasoning, str)
        self.assertIsInstance(parsed.should_ignore, bool)
    
    def test_clean_response_text(self):
        """测试响应文本清理功能"""
        # 测试移除<think>标签
        response_with_tags = """<think>思考过程</think>{"category": "测试"}"""
        cleaned = self.analyzer._clean_response_text(response_with_tags)
        self.assertEqual(cleaned, '{"category": "测试"}')
        
        # 测试提取JSON对象
        response_with_extra = """这是一些额外文本 {"category": "测试", "confidence": 0.8} 还有更多文本"""
        cleaned = self.analyzer._clean_response_text(response_with_extra)
        self.assertEqual(cleaned, '{"category": "测试", "confidence": 0.8}')


class TestClassificationScenarios(unittest.TestCase):
    """测试各种分类场景"""
    
    def setUp(self):
        """测试初始化"""
        self.analyzer = LLMAnalyzer(
            api_key="test_key",
            model="test_model",
            mock_mode=True
        )
    
    def test_whale_movement_classification(self):
        """测试大户动向分类"""
        content = "巨鲸地址转移15000个ETH到Binance交易所，价值约5000万美元"
        
        result = self.analyzer.analyze_content(content, "巨鲸资金转移", "测试来源")
        
        self.assertEqual(result.category, "大户动向")
        self.assertGreater(result.confidence, 0.8)
        self.assertFalse(result.should_ignore)
        self.assertIsInstance(result.key_points, list)
    
    def test_interest_rate_classification(self):
        """测试利率事件分类"""
        content = "美联储会议纪要显示，多数委员支持在下次会议中考虑降息25个基点"
        
        result = self.analyzer.analyze_content(content, "美联储降息预期", "测试来源")
        
        self.assertEqual(result.category, "利率事件")
        self.assertGreater(result.confidence, 0.8)
        self.assertFalse(result.should_ignore)
    
    def test_security_event_classification(self):
        """测试安全事件分类"""
        content = "DeFi协议遭受重入漏洞攻击，黑客盗取500万美元加密货币"
        
        result = self.analyzer.analyze_content(content, "DeFi协议被黑", "测试来源")
        
        self.assertEqual(result.category, "安全事件")
        self.assertGreater(result.confidence, 0.8)
        self.assertFalse(result.should_ignore)
    
    def test_advertisement_filtering(self):
        """测试广告内容过滤"""
        content = "🚀超高收益率DeFi挖矿项目！立即参与！千载难逢的机会！"
        
        result = self.analyzer.analyze_content(content, "🚀超高收益率项目", "测试来源")
        
        self.assertTrue(result.should_ignore)
        self.assertGreater(result.confidence, 0.8)
    
    def test_uncategorized_content(self):
        """测试未分类内容"""
        content = "今天天气不错，适合出门散步"
        
        result = self.analyzer.analyze_content(content, "天气信息", "测试来源")
        
        self.assertEqual(result.category, "未分类")
        self.assertIsInstance(result.confidence, float)
        self.assertFalse(result.should_ignore)


class TestEdgeCases(unittest.TestCase):
    """测试边界情况"""
    
    def setUp(self):
        """测试初始化"""
        self.analyzer = LLMAnalyzer(
            api_key="test_key",
            model="test_model",
            mock_mode=True
        )
    
    def test_empty_content(self):
        """测试空内容"""
        result = self.analyzer.analyze_content("", "", "")
        
        self.assertIsInstance(result, AnalysisResult)
        self.assertIsInstance(result.category, str)
        self.assertIsInstance(result.confidence, float)
    
    def test_very_long_content(self):
        """测试超长内容"""
        long_content = "这是一个很长的内容。" * 1000  # 创建很长的文本
        
        result = self.analyzer.analyze_content(long_content, "超长内容测试", "测试来源")
        
        self.assertIsInstance(result, AnalysisResult)
        self.assertIsInstance(result.category, str)
    
    def test_special_characters_content(self):
        """测试包含特殊字符的内容"""
        special_content = "测试内容包含特殊字符：@#$%^&*()[]{}|\\:;\"'<>?,./"
        
        result = self.analyzer.analyze_content(special_content, "特殊字符测试", "测试来源")
        
        self.assertIsInstance(result, AnalysisResult)
        self.assertIsInstance(result.category, str)
    
    def test_unicode_content(self):
        """测试Unicode内容"""
        unicode_content = "测试Unicode字符：🚀💰📈🔥⚡️🌟💎🎯"
        
        result = self.analyzer.analyze_content(unicode_content, "Unicode测试", "测试来源")
        
        self.assertIsInstance(result, AnalysisResult)
        self.assertIsInstance(result.category, str)
    
    def test_mixed_language_content(self):
        """测试混合语言内容"""
        mixed_content = "Bitcoin price surged to $50,000 比特币价格飙升至5万美元"
        
        result = self.analyzer.analyze_content(mixed_content, "混合语言测试", "测试来源")
        
        self.assertIsInstance(result, AnalysisResult)
        self.assertIsInstance(result.category, str)
    
    def test_invalid_category_response(self):
        """测试无效分类响应的处理"""
        # 模拟返回无效分类的情况
        with patch.object(self.analyzer, '_call_llm_api') as mock_api:
            mock_api.return_value = json.dumps({
                "category": "无效分类名称",
                "confidence": 0.9,
                "reasoning": "测试",
                "should_ignore": False,
                "key_points": []
            }, ensure_ascii=False)
            
            result = self.analyzer.analyze_content("测试内容", "测试标题", "测试来源")
            
            # 应该被修正为"未分类"
            self.assertEqual(result.category, "未分类")


class TestBatchAnalysis(unittest.TestCase):
    """测试批量分析功能"""
    
    def setUp(self):
        """测试初始化"""
        self.analyzer = LLMAnalyzer(
            api_key="test_key",
            model="test_model",
            mock_mode=True
        )
    
    def test_batch_analyze_multiple_items(self):
        """测试批量分析多个内容项"""
        items = [
            ContentItem(
                id="test_1",
                title="巨鲸转移ETH",
                content="某巨鲸地址转移10000个ETH",
                source_name="测试来源1",
                url="https://example.com/1",
                publish_time=datetime.now(),
                source_type="rss"
            ),
            ContentItem(
                id="test_2",
                title="美联储政策",
                content="美联储暗示可能调整利率政策",
                source_name="测试来源2",
                url="https://example.com/2",
                publish_time=datetime.now(),
                source_type="rss"
            )
        ]
        
        results = self.analyzer.batch_analyze(items)
        
        self.assertEqual(len(results), 2)
        for i, result in enumerate(results):
            self.assertEqual(result.content_id, items[i].id)
            self.assertIsInstance(result.category, str)
            self.assertIsInstance(result.confidence, float)
    
    def test_batch_analyze_empty_list(self):
        """测试批量分析空列表"""
        results = self.analyzer.batch_analyze([])
        
        self.assertEqual(len(results), 0)
        self.assertIsInstance(results, list)


class TestContentClassifier(unittest.TestCase):
    """测试内容分类器"""
    
    def setUp(self):
        """测试初始化"""
        self.analyzer = LLMAnalyzer(
            api_key="test_key",
            model="test_model",
            mock_mode=True
        )
        self.classifier = ContentClassifier(self.analyzer)
    
    def test_classify_item(self):
        """测试分类单个内容项"""
        item = ContentItem(
            id="test_1",
            title="测试标题",
            content="测试内容",
            source_name="测试来源",
            url="https://example.com/test",
            publish_time=datetime.now(),
            source_type="rss"
        )
        
        analysis = AnalysisResult(
            content_id="test_1",
            category="大户动向",
            confidence=0.9,
            reasoning="测试推理",
            should_ignore=False,
            key_points=["测试点"]
        )
        
        category = self.classifier.classify_item(item, analysis)
        
        self.assertEqual(category, "大户动向")
        
        # 验证内容项被正确存储
        category_items = self.classifier.get_category_items("大户动向")
        self.assertEqual(len(category_items), 1)
        self.assertEqual(category_items[0].id, "test_1")
    
    def test_get_category_items(self):
        """测试获取分类内容项"""
        # 先添加一些内容项
        item1 = ContentItem(
            id="test_1", title="测试1", content="内容1",
            source_name="来源1", url="https://example.com/1", publish_time=datetime.now(), source_type="rss"
        )
        item2 = ContentItem(
            id="test_2", title="测试2", content="内容2",
            source_name="来源2", url="https://example.com/2", publish_time=datetime.now(), source_type="rss"
        )
        
        analysis1 = AnalysisResult("test_1", "大户动向", 0.9, "推理1", False, [])
        analysis2 = AnalysisResult("test_2", "大户动向", 0.8, "推理2", False, [])
        
        self.classifier.classify_item(item1, analysis1)
        self.classifier.classify_item(item2, analysis2)
        
        # 测试获取分类内容
        whale_items = self.classifier.get_category_items("大户动向")
        self.assertEqual(len(whale_items), 2)
        
        # 测试获取不存在的分类
        empty_items = self.classifier.get_category_items("不存在的分类")
        self.assertEqual(len(empty_items), 0)
    
    def test_generate_category_summary(self):
        """测试生成分类摘要"""
        # 添加测试内容项
        for i in range(3):
            item = ContentItem(
                id=f"test_{i}",
                title=f"测试标题{i}",
                content=f"测试内容{i}",
                source_name="测试来源",
                url=f"https://example.com/test_{i}",
                publish_time=datetime.now(),
                source_type="rss"
            )
            analysis = AnalysisResult(f"test_{i}", "利率事件", 0.9, "推理", False, [])
            self.classifier.classify_item(item, analysis)
        
        summary = self.classifier.generate_category_summary("利率事件")
        
        self.assertIn("利率事件", summary)
        self.assertIn("(3条)", summary)
        self.assertIn("测试标题0", summary)
        self.assertIn("测试标题1", summary)
        self.assertIn("测试标题2", summary)
    
    def test_clear_classifications(self):
        """测试清空分类结果"""
        # 先添加一些内容
        item = ContentItem(
            id="test_1", title="测试", content="内容",
            source_name="来源", url="https://example.com/test", publish_time=datetime.now(), source_type="rss"
        )
        analysis = AnalysisResult("test_1", "大户动向", 0.9, "推理", False, [])
        self.classifier.classify_item(item, analysis)
        
        # 验证有内容
        self.assertEqual(len(self.classifier.get_category_items("大户动向")), 1)
        
        # 清空分类
        self.classifier.clear_classifications()
        
        # 验证已清空
        self.assertEqual(len(self.classifier.get_category_items("大户动向")), 0)
    
    def test_get_classification_stats(self):
        """测试获取分类统计信息"""
        # 添加不同分类的内容项
        categories = ["大户动向", "利率事件", "安全事件"]
        counts = [2, 3, 1]
        
        for category, count in zip(categories, counts):
            for i in range(count):
                item = ContentItem(
                    id=f"{category}_{i}", title=f"标题{i}", content=f"内容{i}",
                    source_name="来源", url=f"https://example.com/{category}_{i}", publish_time=datetime.now(), source_type="rss"
                )
                analysis = AnalysisResult(f"{category}_{i}", category, 0.9, "推理", False, [])
                self.classifier.classify_item(item, analysis)
        
        stats = self.classifier.get_classification_stats()
        
        self.assertEqual(stats["大户动向"], 2)
        self.assertEqual(stats["利率事件"], 3)
        self.assertEqual(stats["安全事件"], 1)


if __name__ == '__main__':
    # 运行测试
    unittest.main(verbosity=2)