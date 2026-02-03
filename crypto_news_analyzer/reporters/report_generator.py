"""
报告生成器

生成Markdown格式的结构化报告，包含时间窗口信息、数据源状态表格和分类内容。
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import logging
import json
import os

from ..models import ContentItem, CrawlStatus, CrawlResult, AnalysisResult, ContentCategory
from ..analyzers.prompt_manager import DynamicCategoryManager


@dataclass
class AnalyzedData:
    """分析后的数据结构"""
    categorized_items: Dict[str, List[ContentItem]]
    analysis_results: Dict[str, AnalysisResult]
    time_window_hours: int
    start_time: datetime
    end_time: datetime


class ReportGenerator:
    """报告生成器
    
    根据需求7生成结构化的Markdown格式报告：
    - 需求7.1: 生成包含时间窗口信息的报告头部
    - 需求7.2: 生成网站爬取状态表格，显示每个数据源的状态和获取数量
    - 需求7.3: 按配置文件中定义的分类标准组织分析结果
    - 需求7.4: 为每条信息包含原文链接
    - 需求7.5: 生成可选的总结部分
    - 需求7.6: 使用Markdown格式输出报告
    - 需求7.7: 当某个类别没有内容时显示该类别为空
    """
    
    def __init__(self, include_summary: bool = True, prompt_config_path: str = "./prompts/analysis_prompt.json"):
        """初始化报告生成器
        
        Args:
            include_summary: 是否包含总结部分
            prompt_config_path: 提示词配置文件路径
        """
        self.include_summary = include_summary
        self.logger = logging.getLogger(__name__)
        self.category_manager = DynamicCategoryManager(prompt_config_path)
        
        # 默认分类显示配置
        self.default_category_display = {
            "大户动向": {"emoji": "🐋", "order": 1},
            "利率事件": {"emoji": "📈", "order": 2},
            "美国政府监管政策": {"emoji": "🏛️", "order": 3},
            "安全事件": {"emoji": "🔒", "order": 4},
            "新产品": {"emoji": "🚀", "order": 5},
            "市场新现象": {"emoji": "📊", "order": 6},
            "未分类": {"emoji": "❓", "order": 999},
            "忽略": {"emoji": "🚫", "order": 1000}
        }
    
    def generate_report(self, data: AnalyzedData, status: CrawlStatus) -> str:
        """生成完整报告
        
        Args:
            data: 分析后的数据
            status: 爬取状态信息
            
        Returns:
            Markdown格式的报告字符串
        """
        try:
            report_sections = []
            
            # 生成报告头部
            header = self.generate_header(data.time_window_hours, data.start_time, data.end_time)
            report_sections.append(header)
            
            # 生成状态表格
            status_table = self.generate_status_table(status)
            report_sections.append(status_table)
            
            # 生成分类内容
            category_sections = self.generate_category_sections(data.categorized_items, data.analysis_results)
            report_sections.extend(category_sections)
            
            # 生成总结（可选）
            if self.include_summary:
                summary = self.generate_summary(data.categorized_items)
                if summary:
                    report_sections.append(summary)
            
            # 组合所有部分
            full_report = "\n\n".join(report_sections)
            
            self.logger.info(f"成功生成报告，包含 {len(category_sections)} 个分类部分")
            return full_report
            
        except Exception as e:
            self.logger.error(f"生成报告时发生错误: {str(e)}")
            return self._generate_error_report(str(e), status)
    
    def generate_header(self, time_window_hours: int, start_time: datetime, end_time: datetime) -> str:
        """生成报告头部
        
        Args:
            time_window_hours: 时间窗口（小时）
            start_time: 开始时间
            end_time: 结束时间
            
        Returns:
            报告头部的Markdown字符串
        """
        header = f"""# 加密货币新闻分析报告

## 报告信息

- **生成时间**: {end_time.strftime('%Y-%m-%d %H:%M:%S')}
- **数据时间窗口**: {time_window_hours} 小时
- **数据时间范围**: {start_time.strftime('%Y-%m-%d %H:%M:%S')} 至 {end_time.strftime('%Y-%m-%d %H:%M:%S')}"""
        
        return header
    
    def generate_status_table(self, status: CrawlStatus) -> str:
        """生成数据源状态表格
        
        Args:
            status: 爬取状态信息
            
        Returns:
            状态表格的Markdown字符串
        """
        table_lines = [
            "## 数据源爬取状态",
            "",
            "| 数据源类型 | 数据源名称 | 状态 | 获取数量 | 错误信息 |",
            "|-----------|-----------|------|----------|----------|"
        ]
        
        # 添加RSS源状态
        for result in status.rss_results:
            status_icon = "✅" if result.status == "success" else "❌"
            error_msg = result.error_message if result.error_message else "-"
            table_lines.append(
                f"| RSS | {result.source_name} | {status_icon} {result.status} | {result.item_count} | {error_msg} |"
            )
        
        # 添加X源状态
        for result in status.x_results:
            status_icon = "✅" if result.status == "success" else "❌"
            error_msg = result.error_message if result.error_message else "-"
            table_lines.append(
                f"| X/Twitter | {result.source_name} | {status_icon} {result.status} | {result.item_count} | {error_msg} |"
            )
        
        # 添加汇总行
        success_count = status.get_success_count()
        error_count = status.get_error_count()
        total_sources = success_count + error_count
        
        table_lines.extend([
            "|-----------|-----------|------|----------|----------|",
            f"| **汇总** | **{total_sources} 个数据源** | **{success_count} 成功, {error_count} 失败** | **{status.total_items}** | - |"
        ])
        
        return "\n".join(table_lines)
    
    def generate_category_sections(
        self, 
        categorized_items: Dict[str, List[ContentItem]], 
        analysis_results: Dict[str, AnalysisResult]
    ) -> List[str]:
        """生成分类内容部分
        
        Args:
            categorized_items: 按类别分组的内容项
            analysis_results: 分析结果字典
            
        Returns:
            分类部分的Markdown字符串列表
        """
        sections = []
        
        # 从配置文件获取分类信息
        try:
            categories_config = self.category_manager.load_categories()
        except Exception as e:
            self.logger.warning(f"无法加载分类配置，使用默认配置: {e}")
            categories_config = {}
        
        # 获取所有需要显示的分类（包括有内容的和配置中定义的）
        all_categories = set(categorized_items.keys())
        all_categories.update(categories_config.keys())
        all_categories.update(["未分类"])  # 确保包含系统保留分类
        
        # 创建分类显示顺序
        category_order = self._get_category_display_order(all_categories, categories_config)
        
        for category_name, emoji in category_order:
            items = categorized_items.get(category_name, [])
            section = self.generate_category_section(category_name, emoji, items, analysis_results)
            sections.append(section)
        
        return sections
    
    def _get_category_display_order(self, categories: set, categories_config: Dict) -> List[tuple]:
        """获取分类显示顺序
        
        Args:
            categories: 所有分类名称集合
            categories_config: 分类配置字典，值为CategoryConfig对象
            
        Returns:
            (分类名称, 图标) 的有序列表
        """
        category_info = []
        
        for category_name in categories:
            # 跳过被忽略的内容
            if category_name == "忽略":
                continue
                
            # 从配置中获取显示信息
            if category_name in categories_config:
                config = categories_config[category_name]
                # CategoryConfig是dataclass，直接访问属性
                emoji = config.display_emoji if hasattr(config, 'display_emoji') else "📄"
                order = config.display_order if hasattr(config, 'display_order') else config.priority
            else:
                # 使用默认配置
                default_info = self.default_category_display.get(category_name, {})
                emoji = default_info.get("emoji", "📄")
                order = default_info.get("order", 999)
            
            category_info.append((order, category_name, emoji))
        
        # 按显示顺序排序
        category_info.sort(key=lambda x: x[0])
        
        # 返回 (名称, 图标) 元组列表
        return [(name, emoji) for order, name, emoji in category_info]
    
    def generate_category_section(
        self, 
        category_name: str, 
        emoji: str,
        items: List[ContentItem], 
        analysis_results: Dict[str, AnalysisResult]
    ) -> str:
        """生成单个分类部分
        
        Args:
            category_name: 分类名称
            emoji: 分类图标
            items: 该分类的内容项列表
            analysis_results: 分析结果字典
            
        Returns:
            分类部分的Markdown字符串
        """
        section_lines = [
            f"## {emoji} {category_name}",
            ""
        ]
        
        if not items:
            section_lines.extend([
                "*本时间窗口内暂无相关内容*",
                ""
            ])
        else:
            section_lines.append(f"*共 {len(items)} 条相关内容*")
            section_lines.append("")
            
            for i, item in enumerate(items, 1):
                # 获取分析结果
                analysis = analysis_results.get(item.id)
                
                # 生成内容项
                item_section = self._format_content_item(i, item, analysis)
                section_lines.extend(item_section)
                section_lines.append("")  # 添加空行分隔
        
        return "\n".join(section_lines)
    
    def _format_content_item(self, index: int, item: ContentItem, analysis: Optional[AnalysisResult]) -> List[str]:
        """格式化单个内容项
        
        Args:
            index: 序号
            item: 内容项
            analysis: 分析结果
            
        Returns:
            格式化后的行列表
        """
        lines = [
            f"### {index}. {item.title}",
            "",
            f"**来源**: {item.source_name} ({item.source_type.upper()})",
            f"**时间**: {item.publish_time.strftime('%Y-%m-%d %H:%M:%S')}",
            f"**链接**: [查看原文]({item.url})",
            ""
        ]
        
        # 添加内容摘要
        content_preview = self._truncate_content(item.content, 200)
        lines.extend([
            "**内容摘要**:",
            content_preview,
            ""
        ])
        
        # 添加分析结果（如果有）
        if analysis:
            lines.extend([
                "**分析结果**:",
                f"- 置信度: {analysis.confidence:.2f}",
                f"- 分析理由: {analysis.reasoning}"
            ])
            
            if analysis.key_points:
                lines.append("- 关键信息:")
                for point in analysis.key_points:
                    lines.append(f"  - {point}")
            
            lines.append("")
        
        return lines
    
    def _truncate_content(self, content: str, max_length: int) -> str:
        """截断内容到指定长度
        
        Args:
            content: 原始内容
            max_length: 最大长度
            
        Returns:
            截断后的内容
        """
        if len(content) <= max_length:
            return content
        
        # 在单词边界截断
        truncated = content[:max_length]
        last_space = truncated.rfind(' ')
        if last_space > max_length * 0.8:  # 如果最后一个空格位置合理
            truncated = truncated[:last_space]
        
        return truncated + "..."
    
    def generate_summary(self, categorized_items: Dict[str, List[ContentItem]]) -> Optional[str]:
        """生成报告总结
        
        Args:
            categorized_items: 按类别分组的内容项
            
        Returns:
            总结部分的Markdown字符串，如果没有内容则返回None
        """
        total_items = sum(len(items) for items in categorized_items.values())
        
        if total_items == 0:
            return None
        
        summary_lines = [
            "## 📋 报告总结",
            "",
            f"本次分析共处理 **{total_items}** 条内容，分布如下：",
            ""
        ]
        
        # 统计各类别数量
        category_stats = []
        for category, items in categorized_items.items():
            if items and category != "忽略":  # 不统计被忽略的内容
                category_stats.append((category, len(items)))
        
        # 按数量排序
        category_stats.sort(key=lambda x: x[1], reverse=True)
        
        for category, count in category_stats:
            summary_lines.append(f"- **{category}**: {count} 条")
        
        # 添加重点关注提醒
        if category_stats:
            top_category, top_count = category_stats[0]
            if top_count > 0:
                summary_lines.extend([
                    "",
                    f"**重点关注**: 本时间窗口内 **{top_category}** 类别内容较多，建议优先关注。"
                ])
        
        return "\n".join(summary_lines)
    
    def reload_category_config(self) -> None:
        """重新加载分类配置"""
        try:
            self.category_manager.reload_categories()
            self.logger.info("分类配置已重新加载")
        except Exception as e:
            self.logger.error(f"重新加载分类配置失败: {e}")
    
    def update_category_display_config(self, config: Dict[str, Any]) -> None:
        """更新分类显示配置
        
        Args:
            config: 新的显示配置
        """
        if isinstance(config, dict):
            self.default_category_display.update(config)
            self.logger.info("分类显示配置已更新")
    
    def get_available_categories(self) -> List[str]:
        """获取可用的分类列表
        
        Returns:
            分类名称列表
        """
        try:
            categories_config = self.category_manager.load_categories()
            categories = list(categories_config.keys())
            categories.extend(["未分类", "忽略"])
            return list(set(categories))  # 去重
        except Exception as e:
            self.logger.warning(f"获取分类列表失败，使用默认分类: {e}")
            return list(self.default_category_display.keys())
    
    def _generate_error_report(self, error_message: str, status: CrawlStatus) -> str:
        """生成错误报告
        
        Args:
            error_message: 错误信息
            status: 爬取状态
            
        Returns:
            错误报告的Markdown字符串
        """
        current_time = datetime.now()
        
        error_report = f"""# 加密货币新闻分析报告 - 错误报告

## 报告信息

- **生成时间**: {current_time.strftime('%Y-%m-%d %H:%M:%S')}
- **状态**: ❌ 报告生成失败

## 错误信息

```
{error_message}
```

## 数据源状态

{self.generate_status_table(status)}

## 建议

请检查以下可能的问题：
1. 数据格式是否正确
2. 分析结果是否完整
3. 系统配置是否有效
4. 网络连接是否正常

如问题持续，请联系系统管理员。
"""
        
        return error_report


class ReportTemplate:
    """报告模板管理器
    
    支持多种报告模板和自定义格式
    """
    
    @staticmethod
    def get_simple_template() -> str:
        """获取简化模板"""
        return """# 加密货币新闻快讯

**时间**: {timestamp}
**数据窗口**: {time_window} 小时

## 重要内容

{important_items}

## 完整报告

详细内容请查看完整报告。
"""
    
    @staticmethod
    def get_detailed_template() -> str:
        """获取详细模板"""
        return """# 加密货币新闻分析报告

## 执行摘要

{executive_summary}

## 数据源状态

{status_table}

## 分类分析

{category_sections}

## 市场洞察

{market_insights}

## 风险提醒

{risk_alerts}
"""
    
    @staticmethod
    def format_template(template: str, **kwargs) -> str:
        """格式化模板
        
        Args:
            template: 模板字符串
            **kwargs: 模板变量
            
        Returns:
            格式化后的字符串
        """
        try:
            return template.format(**kwargs)
        except KeyError as e:
            logging.warning(f"模板变量缺失: {e}")
            return template


# 工具函数
def create_analyzed_data(
    categorized_items: Dict[str, List[ContentItem]],
    analysis_results: Dict[str, AnalysisResult],
    time_window_hours: int,
    reference_time: Optional[datetime] = None
) -> AnalyzedData:
    """创建分析数据对象
    
    Args:
        categorized_items: 分类后的内容项
        analysis_results: 分析结果
        time_window_hours: 时间窗口
        reference_time: 参考时间，默认为当前时间
        
    Returns:
        AnalyzedData对象
    """
    if reference_time is None:
        reference_time = datetime.now()
    
    start_time = reference_time - timedelta(hours=time_window_hours)
    
    return AnalyzedData(
        categorized_items=categorized_items,
        analysis_results=analysis_results,
        time_window_hours=time_window_hours,
        start_time=start_time,
        end_time=reference_time
    )


def validate_report_data(data: AnalyzedData, status: CrawlStatus) -> List[str]:
    """验证报告数据完整性
    
    Args:
        data: 分析数据
        status: 爬取状态
        
    Returns:
        验证错误列表，空列表表示验证通过
    """
    errors = []
    
    # 验证基本数据
    if not isinstance(data.categorized_items, dict):
        errors.append("categorized_items必须是字典类型")
    
    if not isinstance(data.analysis_results, dict):
        errors.append("analysis_results必须是字典类型")
    
    if data.time_window_hours <= 0:
        errors.append("时间窗口必须大于0")
    
    if data.start_time >= data.end_time:
        errors.append("开始时间必须早于结束时间")
    
    # 验证爬取状态
    if not isinstance(status.rss_results, list):
        errors.append("RSS结果必须是列表类型")
    
    if not isinstance(status.x_results, list):
        errors.append("X结果必须是列表类型")
    
    return errors