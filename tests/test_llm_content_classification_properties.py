"""
LLM内容分类一致性属性测试

使用Hypothesis进行属性测试，验证LLM分析器的内容分类一致性。
**功能: crypto-news-analyzer, 属性 5: 内容分类一致性**
**验证: 需求 5.1, 5.3**
"""

import pytest
import tempfile
import os
import json
from datetime import datetime, timedelta
from pathlib import Path
from hypothesis import given, strategies as st, assume, settings
from typing import List, Dict, Any, Optional

from crypto_news_analyzer.analyzers.llm_analyzer import LLMAnalyzer, ContentClassifier
from crypto_news_analyzer.analyzers.prompt_manager import PromptManager, DynamicCategoryManager
from crypto_news_analyzer.models import ContentItem, AnalysisResult


# 策略定义：生成测试内容
@st.composite
def valid_crypto_content(draw):
    """生成有效的加密货币相关内容"""
    # 定义不同类别的内容模板
    content_templates = {
        "大户动向": [
            "巨鲸地址转移{amount}个ETH到{exchange}交易所",
            "某知名地址在过去24小时内{action}{amount}个比特币",
            "大户资金流{direction}，单笔交易超过{amount}万美元",
            "MicroStrategy宣布{action}比特币，总持仓达到{amount}个BTC"
        ],
        "利率事件": [
            "美联储{official}发表{tone}言论，暗示{direction}利率政策",
            "FOMC会议纪要显示{direction}预期，市场反应{reaction}",
            "通胀数据{trend}，美联储政策预期发生{change}",
            "鲍威尔在Jackson Hole会议上表示{statement}"
        ],
        "美国政府监管政策": [
            "SEC{action}加密货币{product}，市场{reaction}",
            "美国国会{action}加密货币监管法案",
            "CFTC发布{type}指导意见，涉及{scope}",
            "财政部宣布{policy}，影响{target}"
        ],
        "安全事件": [
            "{protocol}协议遭受{attack_type}攻击，损失{amount}万美元",
            "发现{platform}智能合约{vulnerability}漏洞",
            "黑客利用{method}盗取{amount}个{token}",
            "{exchange}交易所暂停提现，疑似遭受{attack}"
        ],
        "新产品": [
            "V神推荐的新{type}解决方案{name}正式上线",
            "知名开发者发布创新{product}，具有{feature}功能",
            "{kol}介绍了革命性的{technology}项目",
            "新的{category}协议{name}获得{endorsement}认可"
        ],
        "市场新现象": [
            "NFT市场出现{trend}交易模式",
            "链上活跃度{change}，{metric}创历史{record}",
            "{defi_metric}锁仓量{trend}，达到{amount}亿美元",
            "加密货币市场出现{pattern}现象"
        ],
        "广告软文": [
            "🚀超高收益率{product}，立即参与！",
            "千载难逢的机会！{project}提供{rate}年化收益率",
            "限时优惠！{platform}注册送{bonus}",
            "不要错过！{token}即将{event}，预期{return}"
        ],
        "一般信息": [
            "今日加密货币市场{trend}",
            "比特币价格{movement}至{price}美元",
            "以太坊网络{status}，gas费用{level}",
            "加密货币总市值{change}，达到{amount}万亿美元"
        ]
    }
    
    # 选择内容类别
    category = draw(st.sampled_from(list(content_templates.keys())))
    template = draw(st.sampled_from(content_templates[category]))
    
    # 生成模板参数
    params = {}
    if "{amount}" in template:
        params["amount"] = draw(st.integers(min_value=1000, max_value=50000))
    if "{exchange}" in template:
        params["exchange"] = draw(st.sampled_from(["Binance", "Coinbase", "Kraken", "OKX"]))
    if "{action}" in template:
        params["action"] = draw(st.sampled_from(["增持", "减持", "转移", "购买", "出售"]))
    if "{direction}" in template:
        params["direction"] = draw(st.sampled_from(["流入", "流出", "加息", "降息", "上涨", "下跌"]))
    if "{official}" in template:
        params["official"] = draw(st.sampled_from(["主席鲍威尔", "副主席", "委员"]))
    if "{tone}" in template:
        params["tone"] = draw(st.sampled_from(["鹰派", "鸽派", "中性"]))
    if "{reaction}" in template:
        params["reaction"] = draw(st.sampled_from(["积极", "消极", "平淡", "强烈"]))
    if "{trend}" in template:
        params["trend"] = draw(st.sampled_from(["上升", "下降", "稳定", "波动"]))
    if "{change}" in template:
        params["change"] = draw(st.sampled_from(["变化", "调整", "转向", "修正"]))
    if "{statement}" in template:
        params["statement"] = draw(st.sampled_from(["将继续观察通胀数据", "政策需要更加灵活", "经济前景存在不确定性"]))
    if "{product}" in template:
        params["product"] = draw(st.sampled_from(["ETF", "期货", "衍生品", "现货"]))
    if "{type}" in template:
        params["type"] = draw(st.sampled_from(["Layer2", "DeFi", "NFT", "跨链"]))
    if "{protocol}" in template:
        params["protocol"] = draw(st.sampled_from(["Uniswap", "Compound", "Aave", "Curve"]))
    if "{attack_type}" in template:
        params["attack_type"] = draw(st.sampled_from(["重入", "闪电贷", "治理", "预言机"]))
    if "{vulnerability}" in template:
        params["vulnerability"] = draw(st.sampled_from(["重入", "整数溢出", "权限", "逻辑"]))
    if "{method}" in template:
        params["method"] = draw(st.sampled_from(["钓鱼攻击", "私钥泄露", "合约漏洞", "社会工程"]))
    if "{token}" in template:
        params["token"] = draw(st.sampled_from(["ETH", "USDC", "USDT", "DAI"]))
    if "{attack}" in template:
        params["attack"] = draw(st.sampled_from(["DDoS攻击", "黑客入侵", "系统故障"]))
    if "{name}" in template:
        params["name"] = draw(st.sampled_from(["Optimism", "Arbitrum", "Polygon", "zkSync"]))
    if "{feature}" in template:
        params["feature"] = draw(st.sampled_from(["零知识证明", "跨链桥接", "自动做市", "流动性挖矿"]))
    if "{kol}" in template:
        params["kol"] = draw(st.sampled_from(["V神", "CZ", "SBF", "知名分析师"]))
    if "{technology}" in template:
        params["technology"] = draw(st.sampled_from(["区块链", "DeFi", "NFT", "元宇宙"]))
    if "{category}" in template:
        params["category"] = draw(st.sampled_from(["借贷", "交易", "保险", "衍生品"]))
    if "{endorsement}" in template:
        params["endorsement"] = draw(st.sampled_from(["社区", "投资者", "开发者", "用户"]))
    if "{defi_metric}" in template:
        params["defi_metric"] = draw(st.sampled_from(["DeFi", "TVL", "流动性"]))
    if "{metric}" in template:
        params["metric"] = draw(st.sampled_from(["交易量", "地址数", "哈希率", "网络费用"]))
    if "{record}" in template:
        params["record"] = draw(st.sampled_from(["新高", "新低", "记录"]))
    if "{pattern}" in template:
        params["pattern"] = draw(st.sampled_from(["去中心化", "机构化", "零售化", "全球化"]))
    if "{project}" in template:
        params["project"] = draw(st.sampled_from(["DeFi项目", "挖矿项目", "质押项目", "流动性项目"]))
    if "{rate}" in template:
        params["rate"] = draw(st.integers(min_value=100, max_value=1000))
    if "{platform}" in template:
        params["platform"] = draw(st.sampled_from(["交易平台", "DeFi平台", "借贷平台"]))
    if "{bonus}" in template:
        params["bonus"] = draw(st.integers(min_value=10, max_value=1000))
    if "{event}" in template:
        params["event"] = draw(st.sampled_from(["上线", "空投", "减半", "升级"]))
    if "{return}" in template:
        params["return"] = draw(st.sampled_from(["10倍收益", "暴涨", "翻倍", "高收益"]))
    if "{movement}" in template:
        params["movement"] = draw(st.sampled_from(["上涨", "下跌", "突破", "回调"]))
    if "{price}" in template:
        params["price"] = draw(st.integers(min_value=20000, max_value=100000))
    if "{status}" in template:
        params["status"] = draw(st.sampled_from(["拥堵", "正常", "升级", "维护"]))
    if "{level}" in template:
        params["level"] = draw(st.sampled_from(["较高", "较低", "正常", "异常"]))
    
    # 填充模板
    try:
        content = template.format(**params)
    except KeyError:
        # 如果有未处理的参数，使用原始模板
        content = template
    
    # 生成标题
    title_templates = [
        "【快讯】{content_preview}",
        "重要消息：{content_preview}",
        "市场动态：{content_preview}",
        "最新资讯：{content_preview}",
        "{content_preview}"
    ]
    title_template = draw(st.sampled_from(title_templates))
    content_preview = content[:20] + "..." if len(content) > 20 else content
    title = title_template.format(content_preview=content_preview)
    
    return {
        "title": title,
        "content": content,
        "expected_category": category,
        "source": draw(st.sampled_from(["RSS源", "X源", "测试源"]))
    }


@st.composite
def content_item_from_crypto_content(draw):
    """从加密货币内容生成ContentItem"""
    crypto_content = draw(valid_crypto_content())
    
    # 生成时间（最近48小时内）
    now = datetime.now()
    hours_ago = draw(st.integers(min_value=0, max_value=48))
    publish_time = now - timedelta(hours=hours_ago)
    
    # 生成唯一URL和ID
    url_id = draw(st.integers(min_value=1, max_value=999999))
    url = f"https://example.com/news/{url_id}"
    
    # 生成唯一ID（包含时间戳避免重复）
    import time
    item_id = f"test_{url_id}_{int(time.time() * 1000000) % 1000000}"
    
    content_item = ContentItem(
        id=item_id,
        title=crypto_content["title"],
        content=crypto_content["content"],
        url=url,
        publish_time=publish_time,
        source_name=crypto_content["source"],
        source_type=draw(st.sampled_from(["rss", "x", "rest_api"]))
    )
    
    return content_item, crypto_content["expected_category"]


class TestLLMContentClassificationProperties:
    """LLM内容分类一致性属性测试"""
    
    def setup_method(self):
        """测试前设置"""
        # 创建临时目录和配置文件
        self.temp_dir = tempfile.mkdtemp()
        self.prompt_config_path = os.path.join(self.temp_dir, "analysis_prompt.json")
        
        # 复制默认配置
        default_config_path = "./prompts/analysis_prompt.json"
        if os.path.exists(default_config_path):
            with open(default_config_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
        else:
            # 如果默认配置不存在，创建基本配置
            config_data = {
                "prompt_template": "分析以下内容：\n标题：{title}\n内容：{content}\n来源：{source}\n\n{categories_description}\n\n{ignore_criteria}\n\n{output_format}",
                "categories": {
                    "大户动向": {
                        "description": "大户资金流动和态度变化",
                        "criteria": ["巨鲸资金流动", "大户态度变化"],
                        "examples": ["巨鲸转移ETH", "机构增持BTC"],
                        "priority": 1
                    },
                    "利率事件": {
                        "description": "美联储相关的利率政策事件",
                        "criteria": ["美联储发言", "FOMC会议"],
                        "examples": ["鲍威尔讲话", "利率决议"],
                        "priority": 1
                    },
                    "美国政府监管政策": {
                        "description": "美国政府对加密货币的监管政策变化",
                        "criteria": ["SEC政策", "监管执法"],
                        "examples": ["SEC批准ETF", "监管法案"],
                        "priority": 1
                    },
                    "安全事件": {
                        "description": "影响较大的安全相关事件",
                        "criteria": ["黑客攻击", "资金被盗"],
                        "examples": ["DeFi被黑", "交易所被盗"],
                        "priority": 1
                    },
                    "新产品": {
                        "description": "KOL提及的真正创新产品",
                        "criteria": ["KOL推荐", "创新项目"],
                        "examples": ["V神推荐", "新协议上线"],
                        "priority": 2
                    },
                    "市场新现象": {
                        "description": "重要的市场新趋势和变化",
                        "criteria": ["新趋势", "链上数据异常"],
                        "examples": ["NFT新模式", "TVL创新高"],
                        "priority": 2
                    }
                },
                "ignore_criteria": [
                    "广告和软文",
                    "重复信息",
                    "情绪发泄",
                    "空洞预测",
                    "立场争论"
                ],
                "output_format": "请输出JSON格式：{\"category\": \"类别\", \"confidence\": 0.85, \"reasoning\": \"理由\", \"should_ignore\": false, \"key_points\": []}",
                "llm_settings": {
                    "temperature": 0.1,
                    "max_tokens": 1000,
                    "model": "gpt-4"
                }
            }
        
        # 保存配置文件
        with open(self.prompt_config_path, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, ensure_ascii=False, indent=2)
        
        # 创建LLM分析器（使用模拟模式）
        self.analyzer = LLMAnalyzer(
            api_key="test_key",
            model="gpt-4",
            prompt_config_path=self.prompt_config_path,
            mock_mode=True  # 使用模拟模式避免实际API调用
        )
        
        # 获取有效分类列表
        self.valid_categories = list(config_data["categories"].keys()) + ["未分类", "忽略"]
    
    def teardown_method(self):
        """测试后清理"""
        if os.path.exists(self.prompt_config_path):
            os.remove(self.prompt_config_path)
        if os.path.exists(self.temp_dir):
            os.rmdir(self.temp_dir)
    
    @given(content_data=content_item_from_crypto_content())
    @settings(max_examples=100, deadline=None)
    def test_content_classification_consistency(self, content_data):
        """
        属性测试：内容分类一致性
        
        **功能: crypto-news-analyzer, 属性 5: 内容分类一致性**
        **验证: 需求 5.1, 5.3**
        
        对于任何输入内容，LLM分析器应该将其分类到六大预定义类别之一，或标记为未分类/忽略
        """
        content_item, expected_category = content_data
        
        # 分析内容
        result = self.analyzer.analyze_content(
            content=content_item.content,
            title=content_item.title,
            source=content_item.source_name,
            content_id=content_item.id
        )
        
        # 验证：结果应该是AnalysisResult对象
        assert isinstance(result, AnalysisResult), "分析结果应该是AnalysisResult对象"
        
        # 验证：分类必须是预定义类别之一
        assert result.category in self.valid_categories, (
            f"分类 '{result.category}' 不在有效分类列表中: {self.valid_categories}"
        )
        
        # 验证：置信度在有效范围内
        assert 0.0 <= result.confidence <= 1.0, (
            f"置信度 {result.confidence} 不在有效范围 [0.0, 1.0] 内"
        )
        
        # 验证：should_ignore是布尔值
        assert isinstance(result.should_ignore, bool), "should_ignore必须是布尔值"
        
        # 验证：key_points是列表
        assert isinstance(result.key_points, list), "key_points必须是列表"
        
        # 验证：reasoning不为空
        assert result.reasoning and result.reasoning.strip(), "reasoning不能为空"
        
        # 验证：content_id正确设置
        assert result.content_id == content_item.id, "content_id应该与输入的content_id匹配"
        
        # 验证：如果标记为忽略，分类应该是"忽略"
        if result.should_ignore:
            assert result.category == "忽略", "标记为忽略的内容分类应该是'忽略'"
        
        # 验证：如果分类是"忽略"，should_ignore应该为True
        if result.category == "忽略":
            assert result.should_ignore, "分类为'忽略'的内容should_ignore应该为True"
    
    @given(
        content_items=st.lists(
            content_item_from_crypto_content(),
            min_size=2,
            max_size=5
        )
    )
    @settings(max_examples=30, deadline=None)
    def test_batch_classification_consistency(self, content_items):
        """
        属性测试：批量分类的一致性
        
        验证批量分析时每个项目都能得到有效分类
        """
        items = [item for item, _ in content_items]
        
        # 批量分析
        results = self.analyzer.batch_analyze(items)
        
        # 验证：结果数量与输入数量一致
        assert len(results) == len(items), (
            f"批量分析结果数量 {len(results)} 与输入数量 {len(items)} 不一致"
        )
        
        # 验证：每个结果都符合分类一致性要求
        for i, result in enumerate(results):
            assert isinstance(result, AnalysisResult), f"第{i}个结果应该是AnalysisResult对象"
            assert result.category in self.valid_categories, (
                f"第{i}个结果的分类 '{result.category}' 不在有效分类列表中"
            )
            assert 0.0 <= result.confidence <= 1.0, (
                f"第{i}个结果的置信度 {result.confidence} 不在有效范围内"
            )
            assert isinstance(result.should_ignore, bool), f"第{i}个结果的should_ignore必须是布尔值"
            assert isinstance(result.key_points, list), f"第{i}个结果的key_points必须是列表"
            assert result.reasoning and result.reasoning.strip(), f"第{i}个结果的reasoning不能为空"
            
            # 验证content_id匹配
            assert result.content_id == items[i].id, f"第{i}个结果的content_id不匹配"
    
    @given(content_data=content_item_from_crypto_content())
    @settings(max_examples=50, deadline=None)
    def test_classification_determinism(self, content_data):
        """
        属性测试：分类的确定性
        
        验证相同内容的多次分析应该产生一致的结果（在模拟模式下）
        """
        content_item, expected_category = content_data
        
        # 多次分析相同内容
        results = []
        for _ in range(3):
            result = self.analyzer.analyze_content(
                content=content_item.content,
                title=content_item.title,
                source=content_item.source_name,
                content_id=content_item.id
            )
            results.append(result)
        
        # 验证：所有结果的分类应该一致
        categories = [result.category for result in results]
        assert len(set(categories)) == 1, (
            f"相同内容的多次分析产生了不同的分类: {categories}"
        )
        
        # 验证：所有结果的should_ignore应该一致
        ignore_flags = [result.should_ignore for result in results]
        assert len(set(ignore_flags)) == 1, (
            f"相同内容的多次分析产生了不同的忽略标记: {ignore_flags}"
        )
        
        # 验证：置信度应该相同或非常接近
        confidences = [result.confidence for result in results]
        max_confidence_diff = max(confidences) - min(confidences)
        assert max_confidence_diff < 0.01, (
            f"相同内容的多次分析置信度差异过大: {confidences}"
        )
    
    @given(
        content_items=st.lists(
            content_item_from_crypto_content(),
            min_size=3,
            max_size=8
        )
    )
    @settings(max_examples=20, deadline=None)
    def test_category_distribution_validity(self, content_items):
        """
        属性测试：分类分布的有效性
        
        验证批量分析的分类分布符合预期
        """
        items = [item for item, _ in content_items]
        
        # 批量分析
        results = self.analyzer.batch_analyze(items)
        
        # 统计分类分布
        category_counts = {}
        for result in results:
            category = result.category
            category_counts[category] = category_counts.get(category, 0) + 1
        
        # 验证：所有分类都是有效的
        for category in category_counts.keys():
            assert category in self.valid_categories, (
                f"发现无效分类: {category}"
            )
        
        # 验证：至少有一个项目被分类（不全是忽略）
        non_ignored_count = sum(
            count for category, count in category_counts.items()
            if category != "忽略"
        )
        assert non_ignored_count > 0, "所有项目都被标记为忽略，这不太可能"
        
        # 验证：分类分布合理（至少不是所有项目都被分类为同一类别，除非项目数很少）
        if len(items) >= 8:  # 只在项目数较多时检查
            max_category_count = max(category_counts.values())
            max_category_ratio = max_category_count / len(items)
            # 放宽限制，因为相似内容被分类到同一类别是正常的
            assert max_category_ratio <= 0.95, (
                f"单一分类占比过高 ({max_category_ratio:.2f})，可能存在分类偏差"
            )
    
    @given(content_data=content_item_from_crypto_content())
    @settings(max_examples=30, deadline=None)
    def test_analysis_result_completeness(self, content_data):
        """
        属性测试：分析结果的完整性
        
        验证分析结果包含所有必需字段且格式正确
        """
        content_item, expected_category = content_data
        
        # 分析内容
        result = self.analyzer.analyze_content(
            content=content_item.content,
            title=content_item.title,
            source=content_item.source_name,
            content_id=content_item.id
        )
        
        # 验证：所有必需字段都存在
        assert hasattr(result, 'content_id'), "缺少content_id字段"
        assert hasattr(result, 'category'), "缺少category字段"
        assert hasattr(result, 'confidence'), "缺少confidence字段"
        assert hasattr(result, 'reasoning'), "缺少reasoning字段"
        assert hasattr(result, 'should_ignore'), "缺少should_ignore字段"
        assert hasattr(result, 'key_points'), "缺少key_points字段"
        
        # 验证：字段类型正确
        assert isinstance(result.content_id, str), "content_id应该是字符串"
        assert isinstance(result.category, str), "category应该是字符串"
        assert isinstance(result.confidence, (int, float)), "confidence应该是数字"
        assert isinstance(result.reasoning, str), "reasoning应该是字符串"
        assert isinstance(result.should_ignore, bool), "should_ignore应该是布尔值"
        assert isinstance(result.key_points, list), "key_points应该是列表"
        
        # 验证：字段内容有效
        assert result.content_id.strip(), "content_id不能为空"
        assert result.category.strip(), "category不能为空"
        assert result.reasoning.strip(), "reasoning不能为空"
        
        # 验证：key_points中的元素都是字符串
        for i, point in enumerate(result.key_points):
            assert isinstance(point, str), f"key_points[{i}]应该是字符串"
            assert point.strip(), f"key_points[{i}]不能为空字符串"
        
        # 验证：结果可以序列化
        try:
            result_dict = result.to_dict()
            assert isinstance(result_dict, dict), "to_dict()应该返回字典"
            
            # 验证序列化后的字典包含所有字段
            required_fields = ['content_id', 'category', 'confidence', 'reasoning', 'should_ignore', 'key_points']
            for field in required_fields:
                assert field in result_dict, f"序列化后缺少字段: {field}"
                
        except Exception as e:
            pytest.fail(f"分析结果序列化失败: {e}")
    
    @given(
        content_items=st.lists(
            content_item_from_crypto_content(),
            min_size=1,
            max_size=3
        )
    )
    @settings(max_examples=15, deadline=None)
    def test_content_classifier_integration(self, content_items):
        """
        属性测试：内容分类器集成的一致性
        
        验证LLMAnalyzer与ContentClassifier的集成工作正常
        """
        items = [item for item, _ in content_items]
        
        # 创建内容分类器
        classifier = ContentClassifier(self.analyzer)
        
        # 分析并分类
        for item in items:
            analysis_result = self.analyzer.analyze_content(
                content=item.content,
                title=item.title,
                source=item.source_name,
                content_id=item.id
            )
            
            # 使用分类器分类
            classified_category = classifier.classify_item(item, analysis_result)
            
            # 验证：分类结果一致
            assert classified_category == analysis_result.category, (
                f"分类器返回的分类 '{classified_category}' 与分析结果的分类 '{analysis_result.category}' 不一致"
            )
            
            # 验证：可以从分类器获取分类项目
            category_items = classifier.get_category_items(classified_category)
            assert item in category_items, "分类后的项目应该能从分类器中获取"
        
        # 验证：分类统计正确
        stats = classifier.get_classification_stats()
        total_classified = sum(stats.values())
        assert total_classified == len(items), (
            f"分类统计总数 {total_classified} 与输入项目数 {len(items)} 不一致"
        )
        
        # 验证：所有分类都是有效的
        for category in stats.keys():
            assert category in self.valid_categories, (
                f"分类统计中发现无效分类: {category}"
            )


if __name__ == "__main__":
    # 运行属性测试
    pytest.main([__file__, "-v", "--tb=short"])