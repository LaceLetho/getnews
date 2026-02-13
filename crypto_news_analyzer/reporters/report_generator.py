"""
报告生成器

生成适配Telegram格式的结构化报告，支持动态分类展示和市场快照集成。
"""

import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass

from ..models import CrawlStatus, CrawlResult
from ..analyzers.structured_output_manager import StructuredAnalysisResult
from .telegram_formatter import TelegramFormatter, FormattingConfig
from ..utils.timezone_utils import format_datetime_utc8, now_utc8
from ..analyzers.category_parser import get_category_emoji_map


logger = logging.getLogger(__name__)


@dataclass
class AnalyzedData:
    """分析后的数据容器"""
    categorized_items: Dict[str, List[StructuredAnalysisResult]]
    time_window_hours: int
    start_time: datetime
    end_time: datetime
    total_items: int


class ReportGenerator:
    """
    报告生成器
    
    根据需求7实现Telegram适配的报告生成功能：
    - 需求7.2: 在报告头部包含数据时间窗口和数据时间范围信息
    - 需求7.4: 按大模型返回的分类动态组织各消息大类
    - 需求7.5: 支持动态分类展示，根据大模型返回的类别数量自动调整报告结构
    - 需求7.7: 将source字段格式化为Telegram超链接形式
    - 需求7.11: 某个类别没有内容时在报告中显示该类别为空或完全省略该类别
    - 需求7.14: 为每个消息类别使用适当的Telegram格式化标记
    """
    
    def __init__(
        self,
        telegram_formatter: Optional[TelegramFormatter] = None,
        omit_empty_categories: bool = True,
        prompt_file_path: str = "./prompts/analysis_prompt.md"
    ):
        """
        初始化报告生成器
        
        Args:
            telegram_formatter: Telegram格式化器，如果为None则创建默认实例
            omit_empty_categories: 是否省略空分类
            prompt_file_path: 提示词文件路径，用于解析分类定义
        """
        self.formatter = telegram_formatter or TelegramFormatter()
        self.omit_empty_categories = omit_empty_categories
        self.logger = logging.getLogger(__name__)
        
        # 从提示词文件动态加载分类定义
        try:
            from crypto_news_analyzer.analyzers.category_parser import get_category_parser
            parser = get_category_parser(prompt_file_path)
            self.category_definitions = parser.parse_categories()
            self.logger.info(f"从提示词文件加载了 {len(self.category_definitions)} 个分类定义")
        except Exception as e:
            self.logger.warning(f"无法从提示词文件加载分类定义，使用默认映射: {e}")
            # 后备默认映射（使用英文key）
            self.category_definitions = {}
        
        # 构建英文key到emoji的映射（用于快速查找）
        self.category_emojis = {
            cat.key: cat.emoji for cat in self.category_definitions.values()
        }
        # 同时支持中文名称查找
        self.category_emojis.update({
            cat.name: cat.emoji for cat in self.category_definitions.values()
        })
    
    def generate_telegram_report(
        self,
        data: AnalyzedData,
        status: CrawlStatus
    ) -> str:
        """
        生成适配Telegram格式的完整报告
        
        根据需求7.1-7.15实现完整的报告生成功能。
        
        Args:
            data: 分析后的数据
            status: 爬取状态信息（保留参数以保持向后兼容，但不再使用）
            
        Returns:
            格式化后的Telegram报告文本
        """
        self.logger.info("开始生成Telegram报告")
        
        report_sections = []
        
        # 1. 报告头部（时间窗口和时间范围）
        header = self.generate_report_header(
            data.time_window_hours,
            data.start_time,
            data.end_time
        )
        report_sections.append(header)
        
        # 2. 数据源爬取状态 - 已移除，不再生成此部分
        
        # 3. 动态分类内容部分
        category_sections = self.generate_dynamic_category_sections(
            data.categorized_items
        )
        report_sections.extend(category_sections)
        
        # 合并所有部分
        full_report = "\n\n".join(report_sections)
        
        # 优化移动端显示
        full_report = self.formatter.optimize_for_mobile_display(full_report)
        
        # 验证格式
        if not self.formatter.validate_telegram_format(full_report):
            self.logger.warning("生成的报告格式可能存在问题")
        
        self.logger.info(f"报告生成完成，总长度: {len(full_report)} 字符")
        
        return full_report
    
    def generate_report_header(
        self,
        time_window: int,
        start_time: datetime,
        end_time: datetime
    ) -> str:
        """
        生成报告头部
        
        根据需求7.2实现报告头部信息：
        - 数据时间窗口
        - 数据时间范围
        - 生成时间戳
        
        Args:
            time_window: 时间窗口（小时）
            start_time: 开始时间
            end_time: 结束时间
            
        Returns:
            格式化后的报告头部
        """
        # 格式化标题
        title = self.formatter.format_header("📰 加密货币新闻快讯", level=1)
        
        # 格式化时间信息（使用东八区时间）
        start_str = format_datetime_utc8(start_time, "%Y-%m-%d %H:%M")
        end_str = format_datetime_utc8(end_time, "%Y-%m-%d %H:%M")
        
        time_info = self.formatter.format_time_range(start_str, end_str, time_window)
        
        # 生成时间（使用东八区时间）
        generation_time = format_datetime_utc8(None, "%Y-%m-%d %H:%M:%S")
        gen_time_text = f"🕐 *生成时间*: {self.formatter.escape_special_characters(generation_time)}\n"
        
        return f"{title}\n{time_info}{gen_time_text}"
    
    def generate_data_source_status(self, status: CrawlStatus) -> str:
        """
        生成数据源爬取状态部分
        
        根据需求7.3实现数据源状态展示：
        - 显示每个数据源的状态和获取数量
        - 成功/失败统计
        - 错误信息摘要
        
        Args:
            status: 爬取状态信息
            
        Returns:
            格式化后的状态信息
        """
        section_title = self.formatter.format_section_header("数据源状态", "📡")
        
        status_lines = []
        
        # RSS源状态
        if status.rss_results:
            status_lines.append("*RSS订阅源*:")
            for result in status.rss_results:
                status_line = self.formatter.format_data_source_status(
                    result.source_name,
                    result.status,
                    result.item_count,
                    result.error_message
                )
                status_lines.append(status_line)
        
        # X源状态
        if status.x_results:
            status_lines.append("\n*X/Twitter源*:")
            for result in status.x_results:
                status_line = self.formatter.format_data_source_status(
                    result.source_name,
                    result.status,
                    result.item_count,
                    result.error_message
                )
                status_lines.append(status_line)
        
        # 总计
        success_count = status.get_success_count()
        error_count = status.get_error_count()
        total_count = success_count + error_count
        
        summary = (
            f"\n*总计*: {total_count} 个数据源 "
            f"(✅ {success_count} 成功, ❌ {error_count} 失败)\n"
            f"*获取内容*: {status.total_items} 条"
        )
        
        status_lines.append(summary)
        
        return section_title + "\n".join(status_lines)
    
    def generate_dynamic_category_sections(
        self,
        categorized_items: Dict[str, List[StructuredAnalysisResult]]
    ) -> List[str]:
        """
        生成动态分类内容部分
        
        根据需求7.4、7.5、7.11实现动态分类展示：
        - 按大模型返回的分类动态组织各消息大类
        - 根据实际分类数量自动调整报告结构
        - 自动省略空分类（如果配置启用）
        
        Args:
            categorized_items: 按分类组织的分析结果
            
        Returns:
            分类章节列表
        """
        self.logger.info(f"生成动态分类章节，共 {len(categorized_items)} 个分类")
        
        sections = []
        
        # 处理空分类
        if self.omit_empty_categories:
            categorized_items = self.handle_empty_categories(categorized_items)
        
        # 如果没有任何内容
        if not categorized_items:
            no_content = self.formatter.format_section_header("分析结果", "📊")
            no_content += "\n暂无符合条件的内容。"
            return [no_content]
        
        # 按分类生成章节
        # 排序：按每个分类的内容数量降序
        sorted_categories = sorted(
            categorized_items.items(),
            key=lambda x: len(x[1]),
            reverse=True
        )
        
        for category_name, items in sorted_categories:
            if items or not self.omit_empty_categories:
                section = self.generate_category_section(category_name, items)
                sections.append(section)
        
        return sections
    
    def generate_category_section(
        self,
        category_name: str,
        items: List[StructuredAnalysisResult]
    ) -> str:
        """
        生成单个分类章节
        
        根据需求7.6、7.7、7.14实现分类章节格式化：
        - 包含大模型返回的所有字段（time、category、weight_score、summary、source）
        - 将source字段格式化为Telegram超链接形式
        - 使用适当的Telegram格式化标记
        
        Args:
            category_name: 分类名称（可能是英文key或中文名称）
            items: 该分类下的分析结果列表
            
        Returns:
            格式化后的分类章节
        """
        # 获取分类图标和中文名称
        emoji = self.category_emojis.get(category_name, "📄")
        
        # 尝试将英文key转换为中文名称
        display_name = category_name
        if category_name in self.category_definitions:
            display_name = self.category_definitions[category_name].name
        
        # 分类标题
        section_header = self.formatter.format_category_section(
            display_name,
            len(items),
            emoji
        )
        
        # 如果没有内容
        if not items:
            return section_header + "暂无内容。\n"
        
        # 格式化每条消息
        message_items = []
        for i, item in enumerate(items, 1):
            formatted_item = self.format_message_item(item, i)
            message_items.append(formatted_item)
        
        # 合并
        section_content = section_header + "\n".join(message_items)
        
        return section_content
    
    def format_message_item(
        self,
        item: StructuredAnalysisResult,
        index: int
    ) -> str:
        """
        格式化单条消息项
        
        根据需求7.6和7.7实现消息格式化：
        - 包含所有必需字段
        - source字段转换为Telegram超链接
        
        Args:
            item: 结构化分析结果
            index: 消息序号
            
        Returns:
            格式化后的消息项
        """
        # 使用formatter的format_message_item方法
        formatted = self.formatter.format_message_item(
            time=item.time,
            category=item.category,
            weight_score=item.weight_score,
            summary=item.summary,
            source_url=item.source
        )
        
        # 添加序号
        formatted_with_index = f"\n{index}. {formatted}\n"
        
        return formatted_with_index
    
    
    
    def handle_empty_categories(
        self,
        categories: Dict[str, List[StructuredAnalysisResult]]
    ) -> Dict[str, List[StructuredAnalysisResult]]:
        """
        处理空分类
        
        根据需求7.11实现空分类处理：
        - 如果配置为省略空分类，则移除空分类
        - 否则保留空分类
        
        Args:
            categories: 原始分类字典
            
        Returns:
            处理后的分类字典
        """
        if not self.omit_empty_categories:
            return categories
        
        # 移除空分类
        non_empty_categories = {
            name: items
            for name, items in categories.items()
            if items
        }
        
        removed_count = len(categories) - len(non_empty_categories)
        if removed_count > 0:
            self.logger.info(f"省略了 {removed_count} 个空分类")
        
        return non_empty_categories
    
    def split_report_if_needed(self, report: str) -> List[str]:
        """
        如果报告过长，分割为多个部分
        
        根据需求7.13实现智能消息分割：
        - 智能分割消息并保持内容完整性
        
        Args:
            report: 完整报告
            
        Returns:
            分割后的报告部分列表
        """
        parts = self.formatter.split_long_message(report)
        
        if len(parts) > 1:
            self.logger.info(f"报告被分割为 {len(parts)} 个部分")
            # 保持格式
            parts = self.formatter.preserve_formatting_in_split(parts)
        
        return parts
    
    def create_telegram_hyperlink(self, text: str, url: str) -> str:
        """
        创建Telegram超链接（便捷方法）
        
        Args:
            text: 链接文本
            url: 链接URL
            
        Returns:
            Telegram格式的超链接
        """
        return self.formatter.create_telegram_hyperlink(text, url)
    
    def optimize_for_mobile_display(self, content: str) -> str:
        """
        优化移动端显示（便捷方法）
        
        Args:
            content: 原始内容
            
        Returns:
            优化后的内容
        """
        return self.formatter.optimize_for_mobile_display(content)
    
    def set_category_emoji(self, category: str, emoji: str) -> None:
        """
        设置分类图标
        
        Args:
            category: 分类名称
            emoji: 图标
        """
        self.category_emojis[category] = emoji
        self.logger.debug(f"设置分类 '{category}' 的图标为 '{emoji}'")
    
    def get_category_emoji(self, category: str) -> str:
        """
        获取分类图标
        
        Args:
            category: 分类名称
            
        Returns:
            图标，如果未设置则返回默认图标
        """
        return self.category_emojis.get(category, "📄")


# 工具函数
def create_report_generator(
    include_market_snapshot: bool = True,
    omit_empty_categories: bool = True,
    max_message_length: int = 4096
) -> ReportGenerator:
    """
    创建报告生成器实例
    
    Args:
        include_market_snapshot: 是否包含市场快照（已弃用，保留用于向后兼容）
        omit_empty_categories: 是否省略空分类
        max_message_length: 最大消息长度
        
    Returns:
        ReportGenerator实例
    """
    formatter_config = FormattingConfig(
        max_message_length=max_message_length,
        preserve_formatting=True,
        optimize_for_mobile=True
    )
    
    formatter = TelegramFormatter(formatter_config)
    
    return ReportGenerator(
        telegram_formatter=formatter,
        omit_empty_categories=omit_empty_categories
    )


def categorize_analysis_results(
    results: List[StructuredAnalysisResult]
) -> Dict[str, List[StructuredAnalysisResult]]:
    """
    将分析结果按分类组织
    
    Args:
        results: 分析结果列表
        
    Returns:
        按分类组织的字典
    """
    categorized = {}
    
    for result in results:
        category = result.category
        if category not in categorized:
            categorized[category] = []
        categorized[category].append(result)
    
    return categorized


def create_analyzed_data(
    categorized_items: Dict[str, List[StructuredAnalysisResult]],
    analysis_results: List[StructuredAnalysisResult],
    time_window_hours: int
) -> AnalyzedData:
    """
    创建分析数据对象
    
    Args:
        categorized_items: 按分类组织的分析结果
        analysis_results: 所有分析结果列表
        time_window_hours: 时间窗口（小时）
        
    Returns:
        AnalyzedData对象
    """
    now = now_utc8()
    start_time = now - timedelta(hours=time_window_hours)
    
    return AnalyzedData(
        categorized_items=categorized_items,
        time_window_hours=time_window_hours,
        start_time=start_time,
        end_time=now,
        total_items=len(analysis_results)
    )
