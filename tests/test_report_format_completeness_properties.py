"""
报告格式完整性属性测试

使用Hypothesis进行属性测试，验证报告生成器的格式完整性。
**功能: crypto-news-analyzer, 属性 6: 报告格式完整性**
**验证: 需求 7.1, 7.4**
"""

import pytest
import re
from datetime import datetime, timedelta
from hypothesis import given, strategies as st, assume, settings
from typing import Dict, List, Optional, Any

from crypto_news_analyzer.models import ContentItem, CrawlStatus, CrawlResult, AnalysisResult
from crypto_news_analyzer.reporters.report_generator import (
    ReportGenerator, 
    AnalyzedData, 
    create_analyzed_data,
    validate_report_data
)


# 策略定义：生成测试数据
@st.composite
def valid_content_item(draw):
    """生成有效的ContentItem"""
    # 生成唯一ID
    import time
    unique_id = f"test_{draw(st.integers(min_value=1, max_value=999999))}_{int(time.time() * 1000000) % 1000000}"
    
    # 生成时间（最近72小时内）
    now = datetime.now()
    hours_ago = draw(st.integers(min_value=0, max_value=72))
    publish_time = now - timedelta(hours=hours_ago)
    
    # 生成内容
    title = draw(st.text(min_size=5, max_size=100, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd', 'Zs', 'Po'))))
    content = draw(st.text(min_size=10, max_size=500, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd', 'Zs', 'Po'))))
    
    # 确保标题和内容不为空
    assume(title.strip())
    assume(content.strip())
    
    # 生成URL
    url_id = draw(st.integers(min_value=1, max_value=999999))
    url = f"https://example.com/news/{url_id}"
    
    source_name = draw(st.sampled_from(["测试RSS源", "测试X源", "测试API源", "新闻源A", "新闻源B"]))
    source_type = draw(st.sampled_from(["rss", "x", "rest_api"]))
    
    return ContentItem(
        id=unique_id,
        title=title.strip(),
        content=content.strip(),
        url=url,
        publish_time=publish_time,
        source_name=source_name,
        source_type=source_type
    )


@st.composite
def valid_analysis_result(draw, content_id: str):
    """生成有效的AnalysisResult"""
    categories = [
        "大户动向", "利率事件", "美国政府监管政策", 
        "安全事件", "新产品", "市场新现象", "未分类", "忽略"
    ]
    
    category = draw(st.sampled_from(categories))
    confidence = draw(st.floats(min_value=0.0, max_value=1.0))
    reasoning = draw(st.text(min_size=5, max_size=200, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd', 'Zs', 'Po'))))
    should_ignore = draw(st.booleans())
    
    # 如果分类是"忽略"，should_ignore应该为True
    if category == "忽略":
        should_ignore = True
    
    # 生成关键点
    key_points = draw(st.lists(
        st.text(min_size=3, max_size=50, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd', 'Zs', 'Po'))),
        min_size=0,
        max_size=5
    ))
    # 过滤空字符串
    key_points = [point.strip() for point in key_points if point.strip()]
    
    return AnalysisResult(
        content_id=content_id,
        category=category,
        confidence=confidence,
        reasoning=reasoning.strip() if reasoning.strip() else "默认分析理由",
        should_ignore=should_ignore,
        key_points=key_points
    )


@st.composite
def valid_crawl_result(draw):
    """生成有效的CrawlResult"""
    source_name = draw(st.sampled_from(["RSS源A", "RSS源B", "X源A", "X源B", "API源A"]))
    status = draw(st.sampled_from(["success", "error"]))
    item_count = draw(st.integers(min_value=0, max_value=100))
    
    error_message = None
    if status == "error":
        error_messages = [
            "网络连接超时", "RSS解析失败", "认证失败", 
            "API限制", "服务不可用", "数据格式错误"
        ]
        error_message = draw(st.sampled_from(error_messages))
    
    return CrawlResult(
        source_name=source_name,
        status=status,
        item_count=item_count,
        error_message=error_message
    )


@st.composite
def valid_crawl_status(draw):
    """生成有效的CrawlStatus"""
    # 生成RSS结果
    rss_results = draw(st.lists(valid_crawl_result(), min_size=0, max_size=5))
    
    # 生成X结果
    x_results = draw(st.lists(valid_crawl_result(), min_size=0, max_size=5))
    
    # 计算总项目数
    total_items = sum(result.item_count for result in rss_results + x_results)
    
    # 生成执行时间
    execution_time = datetime.now() - timedelta(minutes=draw(st.integers(min_value=0, max_value=60)))
    
    return CrawlStatus(
        rss_results=rss_results,
        x_results=x_results,
        total_items=total_items,
        execution_time=execution_time
    )


@st.composite
def valid_analyzed_data(draw):
    """生成有效的AnalyzedData"""
    # 生成内容项
    content_items = draw(st.lists(valid_content_item(), min_size=0, max_size=20))
    
    # 按类别分组
    categories = [
        "大户动向", "利率事件", "美国政府监管政策", 
        "安全事件", "新产品", "市场新现象", "未分类"
    ]
    
    categorized_items = {}
    analysis_results = {}
    
    for category in categories:
        categorized_items[category] = []
    
    # 随机分配内容项到类别
    for item in content_items:
        category = draw(st.sampled_from(categories))
        categorized_items[category].append(item)
        
        # 生成对应的分析结果
        analysis_result = draw(valid_analysis_result(item.id))
        # 确保分析结果的分类与分组一致
        analysis_result.category = category
        analysis_results[item.id] = analysis_result
    
    # 生成时间窗口
    time_window_hours = draw(st.integers(min_value=1, max_value=72))
    reference_time = datetime.now()
    
    return create_analyzed_data(
        categorized_items=categorized_items,
        analysis_results=analysis_results,
        time_window_hours=time_window_hours,
        reference_time=reference_time
    )


class TestReportFormatCompletenessProperties:
    """报告格式完整性属性测试"""
    
    def setup_method(self):
        """测试前设置"""
        self.generator = ReportGenerator(include_summary=True)
    
    @given(
        analyzed_data=valid_analyzed_data(),
        crawl_status=valid_crawl_status()
    )
    @settings(max_examples=100, deadline=None)
    def test_report_format_completeness(self, analyzed_data, crawl_status):
        """
        属性测试：报告格式完整性
        
        **功能: crypto-news-analyzer, 属性 6: 报告格式完整性**
        **验证: 需求 7.1, 7.4**
        
        对于任何生成的报告，应该包含时间窗口信息的头部、数据源状态表格，以及每条信息的原文链接
        """
        # 生成报告
        report = self.generator.generate_report(analyzed_data, crawl_status)
        
        # 验证：报告不为空
        assert report and report.strip(), "生成的报告不能为空"
        
        # 验证需求7.1：包含时间窗口信息的报告头部
        self._verify_report_header(report, analyzed_data)
        
        # 验证需求7.2：包含数据源状态表格
        self._verify_status_table(report, crawl_status)
        
        # 验证需求7.3：按类别组织分析结果
        self._verify_category_sections(report, analyzed_data)
        
        # 验证需求7.4：每条信息包含原文链接
        self._verify_original_links(report, analyzed_data)
        
        # 验证需求7.6：使用Markdown格式
        self._verify_markdown_format(report, analyzed_data)
        
        # 验证需求7.7：空类别显示为空
        self._verify_empty_categories(report, analyzed_data)
    
    def _verify_report_header(self, report: str, data: AnalyzedData):
        """验证报告头部包含时间窗口信息"""
        # 验证标题存在
        assert "# 加密货币新闻分析报告" in report, "报告应该包含主标题"
        
        # 验证报告信息部分存在
        assert "## 报告信息" in report, "报告应该包含报告信息部分"
        
        # 验证生成时间存在
        assert "**生成时间**:" in report, "报告应该包含生成时间"
        
        # 验证时间窗口信息存在
        time_window_pattern = rf"\*\*数据时间窗口\*\*:\s*{data.time_window_hours}\s*小时"
        assert re.search(time_window_pattern, report), f"报告应该包含时间窗口信息: {data.time_window_hours} 小时"
        
        # 验证时间范围存在
        assert "**数据时间范围**:" in report, "报告应该包含数据时间范围"
        
        # 验证时间格式正确（YYYY-MM-DD HH:MM:SS）
        time_format_pattern = r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}"
        time_matches = re.findall(time_format_pattern, report)
        assert len(time_matches) >= 3, "报告应该包含至少3个时间戳（生成时间、开始时间、结束时间）"
    
    def _verify_status_table(self, report: str, status: CrawlStatus):
        """验证数据源状态表格"""
        # 验证状态表格标题存在
        assert "## 数据源爬取状态" in report, "报告应该包含数据源状态表格标题"
        
        # 验证表格头部存在
        table_headers = ["数据源类型", "数据源名称", "状态", "获取数量", "错误信息"]
        for header in table_headers:
            assert header in report, f"状态表格应该包含列头: {header}"
        
        # 验证表格分隔符存在
        assert "|-----------|-----------|------|----------|----------|" in report, "状态表格应该包含分隔符"
        
        # 验证RSS源状态
        for rss_result in status.rss_results:
            assert rss_result.source_name in report, f"报告应该包含RSS源: {rss_result.source_name}"
            assert "RSS" in report, "报告应该标识RSS数据源类型"
            
            # 验证状态图标
            if rss_result.status == "success":
                assert "✅" in report, "成功状态应该有对应图标"
            else:
                assert "❌" in report, "失败状态应该有对应图标"
            
            # 验证获取数量
            assert str(rss_result.item_count) in report, f"报告应该包含获取数量: {rss_result.item_count}"
        
        # 验证X源状态
        for x_result in status.x_results:
            assert x_result.source_name in report, f"报告应该包含X源: {x_result.source_name}"
            assert "X/Twitter" in report, "报告应该标识X/Twitter数据源类型"
        
        # 验证汇总信息
        assert "**汇总**" in report, "状态表格应该包含汇总行"
        assert str(status.total_items) in report, f"报告应该包含总项目数: {status.total_items}"
        
        success_count = status.get_success_count()
        error_count = status.get_error_count()
        assert f"{success_count} 成功" in report, f"报告应该显示成功数量: {success_count}"
        assert f"{error_count} 失败" in report, f"报告应该显示失败数量: {error_count}"
    
    def _verify_category_sections(self, report: str, data: AnalyzedData):
        """验证分类部分组织"""
        # 定义预期的类别和图标
        expected_categories = [
            ("大户动向", "🐋"),
            ("利率事件", "📈"),
            ("美国政府监管政策", "🏛️"),
            ("安全事件", "🔒"),
            ("新产品", "🚀"),
            ("市场新现象", "📊"),
            ("未分类", "❓")
        ]
        
        # 验证每个类别部分都存在
        for category_name, emoji in expected_categories:
            category_header = f"## {emoji} {category_name}"
            assert category_header in report, f"报告应该包含分类部分: {category_header}"
            
            # 获取该类别的内容项
            items = data.categorized_items.get(category_name, [])
            
            if items:
                # 如果有内容，验证内容数量显示
                count_pattern = rf"\*共 {len(items)} 条相关内容\*"
                assert re.search(count_pattern, report), f"有内容的分类应该显示内容数量: {len(items)}"
                
                # 验证每个内容项都有标题
                for item in items:
                    # 内容项标题应该以数字开头
                    title_pattern = rf"### \d+\. {re.escape(item.title)}"
                    assert re.search(title_pattern, report), f"报告应该包含内容项标题: {item.title}"
            else:
                # 如果没有内容，验证空内容提示
                assert "*本时间窗口内暂无相关内容*" in report, f"空分类 {category_name} 应该显示无内容提示"
    
    def _verify_original_links(self, report: str, data: AnalyzedData):
        """验证每条信息包含原文链接"""
        # 收集所有内容项
        all_items = []
        for items in data.categorized_items.values():
            all_items.extend(items)
        
        # 验证每个内容项都有原文链接
        for item in all_items:
            # 验证链接格式：[查看原文](URL)
            link_pattern = rf"\[查看原文\]\({re.escape(item.url)}\)"
            assert re.search(link_pattern, report), f"报告应该包含原文链接: {item.url}"
            
            # 验证链接部分的标签
            assert "**链接**:" in report, "报告应该包含链接标签"
    
    def _verify_markdown_format(self, report: str, data: AnalyzedData):
        """验证Markdown格式"""
        # 验证标题格式
        assert re.search(r"^# ", report, re.MULTILINE), "报告应该包含一级标题"
        assert re.search(r"^## ", report, re.MULTILINE), "报告应该包含二级标题"
        
        # 只有当有内容项时才验证三级标题
        total_items = sum(len(items) for items in data.categorized_items.values())
        if total_items > 0:
            assert re.search(r"^### ", report, re.MULTILINE), "有内容时报告应该包含三级标题"
        
        # 验证粗体格式
        assert re.search(r"\*\*[^*]+\*\*", report), "报告应该包含粗体文本"
        
        # 验证斜体格式
        assert re.search(r"\*[^*]+\*", report), "报告应该包含斜体文本"
        
        # 验证表格格式
        assert re.search(r"\|.*\|", report), "报告应该包含表格"
        
        # 只有当有内容项时才验证链接格式
        if total_items > 0:
            assert re.search(r"\[.*\]\(.*\)", report), "有内容时报告应该包含链接"
    
    def _verify_empty_categories(self, report: str, data: AnalyzedData):
        """验证空类别显示"""
        for category_name, items in data.categorized_items.items():
            if not items:
                # 空类别应该显示无内容提示
                empty_message = "*本时间窗口内暂无相关内容*"
                
                # 查找该类别部分
                category_patterns = [
                    f"## 🐋 {category_name}",
                    f"## 📈 {category_name}",
                    f"## 🏛️ {category_name}",
                    f"## 🔒 {category_name}",
                    f"## 🚀 {category_name}",
                    f"## 📊 {category_name}",
                    f"## ❓ {category_name}"
                ]
                
                category_found = False
                for pattern in category_patterns:
                    if pattern in report:
                        category_found = True
                        # 在该类别部分之后应该有空内容提示
                        category_index = report.find(pattern)
                        next_section_index = report.find("## ", category_index + len(pattern))
                        if next_section_index == -1:
                            next_section_index = len(report)
                        
                        category_section = report[category_index:next_section_index]
                        assert empty_message in category_section, (
                            f"空分类 {category_name} 应该在其部分中显示无内容提示"
                        )
                        break
                
                if not category_found:
                    # 如果类别部分不存在，这也是可以接受的（可能被优化掉了）
                    pass
    
    @given(
        analyzed_data=valid_analyzed_data(),
        crawl_status=valid_crawl_status()
    )
    @settings(max_examples=50, deadline=None)
    def test_report_content_structure(self, analyzed_data, crawl_status):
        """
        属性测试：报告内容结构完整性
        
        验证报告的整体结构和内容组织符合要求
        """
        report = self.generator.generate_report(analyzed_data, crawl_status)
        
        # 验证报告结构的顺序
        sections = [
            "# 加密货币新闻分析报告",
            "## 报告信息",
            "## 数据源爬取状态",
            "## 🐋 大户动向",
            "## 📈 利率事件",
            "## 🏛️ 美国政府监管政策",
            "## 🔒 安全事件",
            "## 🚀 新产品",
            "## 📊 市场新现象",
            "## ❓ 未分类"
        ]
        
        last_index = -1
        for section in sections:
            current_index = report.find(section)
            if current_index != -1:  # 部分可能不存在（如空分类被省略）
                assert current_index > last_index, f"报告部分顺序错误: {section} 应该在之前部分之后"
                last_index = current_index
        
        # 验证总结部分（如果有内容）
        total_items = sum(len(items) for items in analyzed_data.categorized_items.values())
        if total_items > 0:
            assert "## 📋 报告总结" in report, "有内容时应该包含报告总结"
    
    @given(
        analyzed_data=valid_analyzed_data(),
        crawl_status=valid_crawl_status()
    )
    @settings(max_examples=30, deadline=None)
    def test_report_metadata_completeness(self, analyzed_data, crawl_status):
        """
        属性测试：报告元数据完整性
        
        验证报告包含所有必需的元数据信息
        """
        report = self.generator.generate_report(analyzed_data, crawl_status)
        
        # 验证时间信息
        assert "生成时间" in report, "报告应该包含生成时间"
        assert "数据时间窗口" in report, "报告应该包含时间窗口信息"
        assert "数据时间范围" in report, "报告应该包含时间范围信息"
        
        # 验证数据源信息
        assert "数据源爬取状态" in report, "报告应该包含数据源状态信息"
        
        # 验证内容项元数据
        all_items = []
        for items in analyzed_data.categorized_items.values():
            all_items.extend(items)
        
        for item in all_items:
            # 每个内容项应该包含完整的元数据
            assert "**来源**:" in report, "内容项应该包含来源信息"
            assert "**时间**:" in report, "内容项应该包含时间信息"
            assert "**链接**:" in report, "内容项应该包含链接信息"
            assert "**内容摘要**:" in report, "内容项应该包含内容摘要"
            
            # 验证来源类型标识
            source_type_upper = item.source_type.upper()
            assert source_type_upper in report, f"报告应该包含数据源类型标识: {source_type_upper}"
    
    @given(
        analyzed_data=valid_analyzed_data(),
        crawl_status=valid_crawl_status()
    )
    @settings(max_examples=20, deadline=None)
    def test_report_analysis_integration(self, analyzed_data, crawl_status):
        """
        属性测试：报告分析结果集成完整性
        
        验证分析结果正确集成到报告中
        """
        report = self.generator.generate_report(analyzed_data, crawl_status)
        
        # 验证分析结果信息
        for content_id, analysis in analyzed_data.analysis_results.items():
            if not analysis.should_ignore:  # 只检查未被忽略的内容
                # 验证置信度信息
                confidence_pattern = rf"置信度:\s*{analysis.confidence:.2f}"
                assert re.search(confidence_pattern, report), (
                    f"报告应该包含分析置信度: {analysis.confidence:.2f}"
                )
                
                # 验证分析理由
                if analysis.reasoning:
                    reasoning_pattern = rf"分析理由:\s*{re.escape(analysis.reasoning)}"
                    assert re.search(reasoning_pattern, report), (
                        f"报告应该包含分析理由: {analysis.reasoning}"
                    )
                
                # 验证关键信息点
                if analysis.key_points:
                    assert "关键信息:" in report, "报告应该包含关键信息标签"
                    for point in analysis.key_points:
                        if point.strip():
                            point_pattern = rf"-\s*{re.escape(point)}"
                            assert re.search(point_pattern, report), (
                                f"报告应该包含关键信息点: {point}"
                            )
    
    @given(
        time_window_hours=st.integers(min_value=1, max_value=168),  # 1小时到1周
        item_count=st.integers(min_value=0, max_value=50)
    )
    @settings(max_examples=30, deadline=None)
    def test_report_scalability(self, time_window_hours, item_count):
        """
        属性测试：报告生成的可扩展性
        
        验证不同规模的数据都能生成有效报告
        """
        # 生成指定数量的内容项
        content_items = []
        analysis_results = {}
        
        for i in range(item_count):
            item = ContentItem(
                id=f"test_item_{i}",
                title=f"测试新闻 {i}",
                content=f"这是第 {i} 条测试新闻内容",
                url=f"https://example.com/news/{i}",
                publish_time=datetime.now() - timedelta(hours=i % time_window_hours),
                source_name=f"测试源 {i % 3}",
                source_type=["rss", "x", "rest_api"][i % 3]
            )
            content_items.append(item)
            
            # 生成分析结果
            categories = ["大户动向", "利率事件", "安全事件", "新产品", "市场新现象", "未分类"]
            analysis_results[item.id] = AnalysisResult(
                content_id=item.id,
                category=categories[i % len(categories)],
                confidence=0.5 + (i % 5) * 0.1,
                reasoning=f"测试分析理由 {i}",
                should_ignore=False,
                key_points=[f"关键点 {i}"]
            )
        
        # 按类别分组
        categorized_items = {
            "大户动向": [], "利率事件": [], "美国政府监管政策": [],
            "安全事件": [], "新产品": [], "市场新现象": [], "未分类": []
        }
        
        for item in content_items:
            analysis = analysis_results[item.id]
            categorized_items[analysis.category].append(item)
        
        # 创建分析数据
        analyzed_data = create_analyzed_data(
            categorized_items=categorized_items,
            analysis_results=analysis_results,
            time_window_hours=time_window_hours
        )
        
        # 创建爬取状态
        crawl_status = CrawlStatus(
            rss_results=[CrawlResult("测试RSS源", "success", item_count // 2, None)],
            x_results=[CrawlResult("测试X源", "success", item_count - item_count // 2, None)],
            total_items=item_count,
            execution_time=datetime.now()
        )
        
        # 生成报告
        report = self.generator.generate_report(analyzed_data, crawl_status)
        
        # 验证报告基本结构
        assert report and report.strip(), "即使在不同规模下也应该生成有效报告"
        assert "# 加密货币新闻分析报告" in report, "报告应该包含标题"
        assert f"{time_window_hours} 小时" in report, "报告应该包含正确的时间窗口"
        
        # 验证内容数量统计
        if item_count > 0:
            assert str(item_count) in report, f"报告应该包含正确的内容数量: {item_count}"
        else:
            assert "暂无相关内容" in report, "空报告应该显示无内容提示"


if __name__ == "__main__":
    # 运行属性测试
    pytest.main([__file__, "-v", "--tb=short"])