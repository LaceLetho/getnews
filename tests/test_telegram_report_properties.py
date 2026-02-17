"""
Telegram报告生成属性测试

使用Hypothesis进行属性测试，验证Telegram报告生成的正确性。
包含以下属性测试：
- 属性 12: Telegram格式适配正确性
- 属性 13: 动态分类展示一致性

**功能: crypto-news-analyzer**
**验证: 需求 7.1-7.18**
"""

import pytest
import re
from datetime import datetime, timedelta
from hypothesis import given, strategies as st, assume, settings
from typing import Dict, List

from crypto_news_analyzer.reporters.report_generator import (
    ReportGenerator,
    AnalyzedData,
    categorize_analysis_results
)
from crypto_news_analyzer.reporters.telegram_formatter import TelegramFormatter
from crypto_news_analyzer.analyzers.structured_output_manager import StructuredAnalysisResult
from crypto_news_analyzer.models import CrawlStatus, CrawlResult


# ============================================================================
# 策略定义：生成测试数据
# ============================================================================

@st.composite
def valid_structured_result(draw):
    """生成有效的结构化分析结果"""
    time_str = datetime.now().strftime('%Y-%m-%d %H:%M')
    category = draw(st.sampled_from([
        "大户动向", "利率事件", "美国政府监管政策", 
        "安全事件", "新产品", "市场新现象"
    ]))
    weight_score = draw(st.integers(min_value=0, max_value=100))
    # 排除可能导致Telegram格式问题的字符：*_[]`()
    summary = draw(st.text(min_size=20, max_size=200, alphabet=st.characters(
        blacklist_categories=('Cs', 'Cc'), blacklist_characters='*_[]`()'
    )))
    source = draw(st.sampled_from([
        "https://example.com/news/1",
        "https://crypto.news/article/123",
        "https://x.com/user/status/456",
        "https://panews.com/flash/789"
    ]))
    
    return StructuredAnalysisResult(
        time=time_str,
        category=category,
        weight_score=weight_score,
        summary=summary,
        source=source
    )


@st.composite
def valid_analysis_results_list(draw):
    """生成有效的分析结果列表"""
    # 生成1-20个分析结果
    count = draw(st.integers(min_value=1, max_value=20))
    results = [draw(valid_structured_result()) for _ in range(count)]
    return results


@st.composite
def valid_categorized_items(draw):
    """生成有效的分类项字典"""
    # 生成1-6个分类
    num_categories = draw(st.integers(min_value=1, max_value=6))
    categories = draw(st.lists(
        st.sampled_from([
            "大户动向", "利率事件", "美国政府监管政策",
            "安全事件", "新产品", "市场新现象"
        ]),
        min_size=num_categories,
        max_size=num_categories,
        unique=True
    ))
    
    categorized = {}
    for category in categories:
        # 每个分类有0-10个项目
        item_count = draw(st.integers(min_value=0, max_value=10))
        items = []
        for _ in range(item_count):
            result = draw(valid_structured_result())
            # 确保分类匹配
            result.category = category
            items.append(result)
        categorized[category] = items
    
    return categorized


@st.composite
def valid_crawl_status(draw):
    """生成有效的爬取状态"""
    # RSS结果
    rss_count = draw(st.integers(min_value=0, max_value=5))
    rss_results = []
    for i in range(rss_count):
        status = draw(st.sampled_from(["success", "error"]))
        item_count = draw(st.integers(min_value=0, max_value=50)) if status == "success" else 0
        error_msg = None if status == "success" else draw(st.sampled_from([
            "连接超时", "解析错误", "认证失败"
        ]))
        rss_results.append(CrawlResult(
            source_name=f"RSS源{i+1}",
            status=status,
            item_count=item_count,
            error_message=error_msg
        ))
    
    # X结果
    x_count = draw(st.integers(min_value=0, max_value=5))
    x_results = []
    for i in range(x_count):
        status = draw(st.sampled_from(["success", "error"]))
        item_count = draw(st.integers(min_value=0, max_value=50)) if status == "success" else 0
        error_msg = None if status == "success" else draw(st.sampled_from([
            "Bird工具错误", "认证失败", "限流"
        ]))
        x_results.append(CrawlResult(
            source_name=f"X源{i+1}",
            status=status,
            item_count=item_count,
            error_message=error_msg
        ))
    
    total_items = sum(r.item_count for r in rss_results + x_results)
    
    return CrawlStatus(
        rss_results=rss_results,
        x_results=x_results,
        total_items=total_items,
        execution_time=datetime.now()
    )


@st.composite
def valid_analyzed_data(draw):
    """生成有效的分析数据"""
    categorized = draw(valid_categorized_items())
    time_window = draw(st.integers(min_value=1, max_value=72))
    
    end_time = datetime.now()
    start_time = end_time - timedelta(hours=time_window)
    
    total_items = sum(len(items) for items in categorized.values())
    
    return AnalyzedData(
        categorized_items=categorized,
        time_window_hours=time_window,
        start_time=start_time,
        end_time=end_time,
        total_items=total_items
    )


@st.composite
def valid_market_snapshot(draw):
    """生成有效的市场快照"""
    snapshot_templates = [
        "当前BTC价格: ${price}\n市场情绪: {sentiment}\n24h交易量: ${volume}B",
        "市场概况：{overview}\n主要趋势：{trend}",
        "加密货币市场当前状态良好，主要币种表现稳定。",
        ""  # 空快照
    ]
    
    template = draw(st.sampled_from(snapshot_templates))
    
    if "{price}" in template:
        price = draw(st.integers(min_value=20000, max_value=100000))
        sentiment = draw(st.sampled_from(["乐观", "谨慎", "悲观"]))
        volume = draw(st.integers(min_value=10, max_value=100))
        return template.format(price=price, sentiment=sentiment, volume=volume)
    elif "{overview}" in template:
        overview = draw(st.sampled_from(["稳定", "波动", "上涨", "下跌"]))
        trend = draw(st.sampled_from(["看涨", "看跌", "震荡"]))
        return template.format(overview=overview, trend=trend)
    else:
        return template


# ============================================================================
# 属性 12: Telegram格式适配正确性
# **验证: 需求 7.1, 7.3, 7.7, 7.9**
# ============================================================================

class TestProperty12TelegramFormatCorrectness:
    """
    属性 12: Telegram格式适配正确性
    
    对于任何生成的报告，应该正确适配Telegram格式，包含报告信息、
    数据源状态、动态分类内容和市场快照，source字段格式化为可点击超链接。
    """
    
    @given(
        analyzed_data=valid_analyzed_data(),
        crawl_status=valid_crawl_status(),
        market_snapshot=valid_market_snapshot()
    )
    @settings(max_examples=100, deadline=None)
    def test_report_contains_all_required_sections(
        self,
        analyzed_data,
        crawl_status,
        market_snapshot
    ):
        """
        **功能: crypto-news-analyzer, 属性 12: Telegram格式适配正确性**
        
        验证生成的报告包含所有必需部分：
        - 报告头部（时间窗口和时间范围）
        - 数据源状态
        - 动态分类内容
        - 市场快照（如果提供）
        """
        generator = ReportGenerator(include_market_snapshot=True)
        
        report = generator.generate_telegram_report(
            analyzed_data,
            crawl_status,
            market_snapshot
        )
        
        # 验证报告不为空
        assert len(report) > 0, "报告不应为空"
        
        # 验证包含报告头部
        assert "加密货币新闻快讯" in report or "新闻快讯" in report, \
            "报告应包含标题"
        assert "数据时间窗口" in report or "时间窗口" in report, \
            "报告应包含时间窗口信息"
        
        # 验证包含数据源状态（如果有数据源）
        if crawl_status.rss_results or crawl_status.x_results:
            assert "数据源状态" in report or "数据源" in report, \
                "报告应包含数据源状态"
        
        # 验证包含市场快照（如果提供且非空）
        if market_snapshot and market_snapshot.strip():
            assert "市场现状快照" in report or "市场快照" in report or "市场" in report, \
                "报告应包含市场快照部分"
    
    @given(
        analyzed_data=valid_analyzed_data(),
        crawl_status=valid_crawl_status()
    )
    @settings(max_examples=100, deadline=None)
    def test_source_fields_formatted_as_hyperlinks(
        self,
        analyzed_data,
        crawl_status
    ):
        """
        **功能: crypto-news-analyzer, 属性 12: Telegram格式适配正确性**
        
        验证source字段被正确格式化为Telegram超链接 [text](url)
        """
        generator = ReportGenerator()
        
        report = generator.generate_telegram_report(
            analyzed_data,
            crawl_status,
            None
        )
        
        # 检查是否有内容项
        has_items = any(len(items) > 0 for items in analyzed_data.categorized_items.values())
        
        if has_items:
            # 验证包含Telegram超链接格式 [text](url)
            hyperlink_pattern = r'\[.*?\]\(https?://.*?\)'
            matches = re.findall(hyperlink_pattern, report)
            
            assert len(matches) > 0, \
                "报告应包含至少一个Telegram格式的超链接"
            
            # 验证超链接格式正确
            for match in matches:
                assert match.startswith('[') and '](' in match and match.endswith(')'), \
                    f"超链接格式不正确: {match}"
    
    @given(
        analyzed_data=valid_analyzed_data(),
        crawl_status=valid_crawl_status()
    )
    @settings(max_examples=100, deadline=None)
    def test_telegram_format_validation(
        self,
        analyzed_data,
        crawl_status
    ):
        """
        **功能: crypto-news-analyzer, 属性 12: Telegram格式适配正确性**
        
        验证生成的报告符合Telegram格式规范（括号匹配、格式标记匹配）
        """
        generator = ReportGenerator()
        formatter = TelegramFormatter()
        
        report = generator.generate_telegram_report(
            analyzed_data,
            crawl_status,
            None
        )
        
        # 使用formatter验证格式
        is_valid = formatter.validate_telegram_format(report)
        
        assert is_valid, \
            "生成的报告应符合Telegram格式规范"
        
        # 额外验证：括号匹配
        assert report.count('[') == report.count(']'), \
            "方括号应该匹配"
        assert report.count('(') == report.count(')'), \
            "圆括号应该匹配"
    
    @given(
        crawl_status=valid_crawl_status()
    )
    @settings(max_examples=100, deadline=None)
    def test_data_source_status_formatting(
        self,
        crawl_status
    ):
        """
        **功能: crypto-news-analyzer, 属性 12: Telegram格式适配正确性**
        
        验证报告不再包含数据源状态部分（已移除此功能）
        """
        generator = ReportGenerator()
        
        # 创建简单的分析数据用于测试
        from crypto_news_analyzer.reporters.report_generator import create_analyzed_data
        from crypto_news_analyzer.analyzers.structured_output_manager import StructuredAnalysisResult
        
        categorized_items = {
            "TestCategory": [
                StructuredAnalysisResult(
                    time="2024-01-01 10:00",
                    category="TestCategory",
                    weight_score=80,
                    title="Test summary",

                    body="Test summary",
                    source="https://example.com"
                )
            ]
        }
        
        analyzed_data = create_analyzed_data(
            categorized_items=categorized_items,
            analysis_results=list(categorized_items["TestCategory"]),
            time_window_hours=24
        )
        
        # 生成报告
        report = generator.generate_telegram_report(analyzed_data, crawl_status)
        
        # 验证报告不包含数据源状态相关内容
        assert "数据源状态" not in report, "报告不应包含数据源状态标题"
        assert "📡" not in report, "报告不应包含数据源状态图标"
        assert "RSS订阅源" not in report, "报告不应包含RSS源状态"
        assert "X/Twitter源" not in report, "报告不应包含X源状态"


# ============================================================================
# 属性 13: 动态分类展示一致性
# **验证: 需求 7.4, 7.5, 7.11**
# ============================================================================

class TestProperty13DynamicCategoryConsistency:
    """
    属性 13: 动态分类展示一致性
    
    对于任何大模型返回的分类结果，报告生成器应该根据实际分类数量
    动态调整报告结构，自动省略空分类。
    """
    
    @given(
        categorized_items=valid_categorized_items()
    )
    @settings(max_examples=100, deadline=None)
    def test_dynamic_category_adjustment(
        self,
        categorized_items
    ):
        """
        **功能: crypto-news-analyzer, 属性 13: 动态分类展示一致性**
        
        验证报告根据实际分类数量动态调整结构
        """
        generator = ReportGenerator(omit_empty_categories=True)
        
        sections = generator.generate_dynamic_category_sections(categorized_items)
        
        # 计算非空分类数量
        non_empty_categories = {
            name: items for name, items in categorized_items.items()
            if items
        }
        
        # 验证生成的章节数量与非空分类数量一致
        if non_empty_categories:
            assert len(sections) == len(non_empty_categories), \
                f"章节数量({len(sections)})应与非空分类数量({len(non_empty_categories)})一致"
        else:
            # 如果没有非空分类，应该有一个"暂无内容"的章节
            assert len(sections) == 1, \
                "没有内容时应该有一个提示章节"
            assert "暂无" in sections[0] or "无" in sections[0], \
                "应包含暂无内容的提示"
    
    @given(
        categorized_items=valid_categorized_items()
    )
    @settings(max_examples=100, deadline=None)
    def test_empty_categories_omitted(
        self,
        categorized_items
    ):
        """
        **功能: crypto-news-analyzer, 属性 13: 动态分类展示一致性**
        
        验证空分类被自动省略（当配置启用时）
        """
        generator = ReportGenerator(omit_empty_categories=True)
        
        # 处理空分类
        processed = generator.handle_empty_categories(categorized_items)
        
        # 验证所有保留的分类都非空
        for category, items in processed.items():
            assert len(items) > 0, \
                f"分类 '{category}' 应该被省略，因为它是空的"
        
        # 验证空分类被移除
        empty_categories = [
            name for name, items in categorized_items.items()
            if not items
        ]
        
        for empty_cat in empty_categories:
            assert empty_cat not in processed, \
                f"空分类 '{empty_cat}' 应该被省略"
    
    @given(
        categorized_items=valid_categorized_items()
    )
    @settings(max_examples=100, deadline=None)
    def test_empty_categories_kept_when_configured(
        self,
        categorized_items
    ):
        """
        **功能: crypto-news-analyzer, 属性 13: 动态分类展示一致性**
        
        验证当配置禁用省略时，空分类被保留
        """
        generator = ReportGenerator(omit_empty_categories=False)
        
        # 处理空分类
        processed = generator.handle_empty_categories(categorized_items)
        
        # 验证所有分类都被保留
        assert len(processed) == len(categorized_items), \
            "禁用省略时，所有分类都应该被保留"
        
        for category in categorized_items.keys():
            assert category in processed, \
                f"分类 '{category}' 应该被保留"
    
    @given(
        categorized_items=valid_categorized_items()
    )
    @settings(max_examples=100, deadline=None)
    def test_category_ordering_by_item_count(
        self,
        categorized_items
    ):
        """
        **功能: crypto-news-analyzer, 属性 13: 动态分类展示一致性**
        
        验证分类按内容数量降序排列
        """
        # 确保至少有2个非空分类
        non_empty = {k: v for k, v in categorized_items.items() if v}
        assume(len(non_empty) >= 2)
        
        generator = ReportGenerator(omit_empty_categories=True)
        
        sections = generator.generate_dynamic_category_sections(categorized_items)
        
        # 提取每个章节的分类名称和内容数量
        category_counts = []
        for section in sections:
            for category, items in categorized_items.items():
                if category in section and items:
                    category_counts.append((category, len(items)))
                    break
        
        # 验证按数量降序排列
        if len(category_counts) >= 2:
            for i in range(len(category_counts) - 1):
                assert category_counts[i][1] >= category_counts[i + 1][1], \
                    f"分类应按内容数量降序排列: {category_counts}"
    
    @given(
        categorized_items=valid_categorized_items()
    )
    @settings(max_examples=100, deadline=None)
    def test_all_categories_present_in_report(
        self,
        categorized_items
    ):
        """
        **功能: crypto-news-analyzer, 属性 13: 动态分类展示一致性**
        
        验证所有非空分类都出现在报告中
        """
        generator = ReportGenerator(omit_empty_categories=True)
        
        sections = generator.generate_dynamic_category_sections(categorized_items)
        all_sections_text = "\n".join(sections)
        
        # 验证所有非空分类都出现在报告中
        for category, items in categorized_items.items():
            if items:  # 只检查非空分类
                assert category in all_sections_text, \
                    f"非空分类 '{category}' 应该出现在报告中"
    
    @given(
        categorized_items=valid_categorized_items()
    )
    @settings(max_examples=100, deadline=None)
    def test_category_item_count_displayed(
        self,
        categorized_items
    ):
        """
        **功能: crypto-news-analyzer, 属性 13: 动态分类展示一致性**
        
        验证每个分类显示正确的项目数量
        """
        generator = ReportGenerator(omit_empty_categories=True)
        
        sections = generator.generate_dynamic_category_sections(categorized_items)
        
        # 验证每个非空分类的数量显示
        for category, items in categorized_items.items():
            if items:
                # 找到对应的章节
                category_section = None
                for section in sections:
                    if category in section:
                        category_section = section
                        break
                
                assert category_section is not None, \
                    f"应该找到分类 '{category}' 的章节"
                
                # 验证数量显示（可能是 "5条" 或 "(5)" 等格式）
                item_count_str = str(len(items))
                assert item_count_str in category_section, \
                    f"分类 '{category}' 的章节应显示项目数量 {len(items)}"
    
    @given(
        results_list=valid_analysis_results_list()
    )
    @settings(max_examples=100, deadline=None)
    def test_categorize_analysis_results_consistency(
        self,
        results_list
    ):
        """
        **功能: crypto-news-analyzer, 属性 13: 动态分类展示一致性**
        
        验证分类辅助函数正确地将结果按分类组织
        """
        categorized = categorize_analysis_results(results_list)
        
        # 验证所有结果都被分类
        total_categorized = sum(len(items) for items in categorized.values())
        assert total_categorized == len(results_list), \
            "所有结果都应该被分类"
        
        # 验证每个结果在正确的分类中
        for result in results_list:
            assert result.category in categorized, \
                f"分类 '{result.category}' 应该存在"
            assert result in categorized[result.category], \
                f"结果应该在分类 '{result.category}' 中"
        
        # 验证没有重复
        all_results = []
        for items in categorized.values():
            all_results.extend(items)
        
        assert len(all_results) == len(results_list), \
            "不应该有重复的结果"


# ============================================================================
# 集成属性测试：完整报告生成
# ============================================================================

class TestIntegratedReportGeneration:
    """集成测试：验证完整报告生成流程"""
    
    @given(
        analyzed_data=valid_analyzed_data(),
        crawl_status=valid_crawl_status(),
        market_snapshot=valid_market_snapshot()
    )
    @settings(max_examples=50, deadline=None)
    def test_complete_report_generation(
        self,
        analyzed_data,
        crawl_status,
        market_snapshot
    ):
        """
        **功能: crypto-news-analyzer, 属性 12+13: 完整报告生成**
        
        验证完整的报告生成流程，包含所有必需部分且格式正确
        """
        generator = ReportGenerator(
            include_market_snapshot=True,
            omit_empty_categories=True
        )
        
        report = generator.generate_telegram_report(
            analyzed_data,
            crawl_status,
            market_snapshot
        )
        
        # 基本验证
        assert len(report) > 0, "报告不应为空"
        assert isinstance(report, str), "报告应该是字符串"
        
        # 格式验证
        formatter = TelegramFormatter()
        assert formatter.validate_telegram_format(report), \
            "报告应符合Telegram格式规范"
        
        # 长度验证（不应超过Telegram单条消息限制太多）
        # 如果超过，应该能够被分割
        if len(report) > 4096:
            parts = generator.split_report_if_needed(report)
            assert len(parts) > 1, "超长报告应该被分割"
            for part in parts:
                assert len(part) <= 4096, "每个部分都不应超过4096字符"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
