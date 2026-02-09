"""
Telegram格式化器

适配Telegram消息格式，支持特殊字符转义、格式化语法、超链接和移动端优化。
"""

import re
import logging
from typing import List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class FormattingConfig:
    """格式化配置"""
    max_message_length: int = 4096
    preserve_formatting: bool = True
    optimize_for_mobile: bool = True
    escape_special_chars: bool = True


class TelegramFormatter:
    """Telegram格式化器
    
    根据需求7实现Telegram格式适配功能：
    - 需求7.1: 生成适配Telegram格式的报告，而非纯Markdown格式
    - 需求7.10: 优化Telegram消息格式，确保在移动端的可读性
    - 需求7.12: 支持Telegram的文本格式化语法（粗体、斜体、代码块等）
    - 需求7.13: 智能分割消息并保持内容完整性
    - 需求7.15: 确保超链接在Telegram中正确显示和可点击
    - 需求7.17: 支持Telegram的特殊字符转义，避免格式错误
    """
    
    def __init__(self, config: Optional[FormattingConfig] = None):
        """初始化Telegram格式化器
        
        Args:
            config: 格式化配置，默认使用标准配置
        """
        self.config = config or FormattingConfig()
        self.logger = logging.getLogger(__name__)
        
        # Telegram Markdown V2特殊字符（需要转义）
        self.special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
        
        # Telegram MarkdownV1特殊字符（更简单的转义规则）
        self.markdown_v1_special_chars = ['_', '*', '[', ']', '`']
    
    def format_header(self, title: str, level: int = 1) -> str:
        """格式化标题
        
        Args:
            title: 标题文本
            level: 标题级别（1-3）
            
        Returns:
            格式化后的标题
        """
        if level == 1:
            # 一级标题：粗体 + emoji
            return f"*{self.escape_special_characters(title)}*\n"
        elif level == 2:
            # 二级标题：粗体
            return f"*{self.escape_special_characters(title)}*\n"
        else:
            # 三级标题：普通文本
            return f"{self.escape_special_characters(title)}\n"
    
    def format_bold(self, text: str) -> str:
        """格式化粗体文本
        
        Args:
            text: 文本内容
            
        Returns:
            粗体格式的文本
        """
        escaped_text = self.escape_special_characters(text)
        return f"*{escaped_text}*"
    
    def format_italic(self, text: str) -> str:
        """格式化斜体文本
        
        Args:
            text: 文本内容
            
        Returns:
            斜体格式的文本
        """
        escaped_text = self.escape_special_characters(text)
        return f"_{escaped_text}_"
    
    def format_code(self, text: str) -> str:
        """格式化代码文本
        
        Args:
            text: 代码内容
            
        Returns:
            代码格式的文本
        """
        # 代码块内部不需要转义
        return f"`{text}`"
    
    def format_hyperlink(self, text: str, url: str) -> str:
        """格式化超链接
        
        根据需求7.7和7.15实现超链接格式化：
        - 将source字段格式化为Telegram超链接形式
        - 确保超链接在Telegram中正确显示和可点击
        
        Args:
            text: 链接显示文本
            url: 链接URL
            
        Returns:
            Telegram格式的超链接
        """
        # Telegram Markdown格式: [text](url)
        # 链接文本需要转义，URL不需要转义
        escaped_text = self.escape_special_characters(text)
        return f"[{escaped_text}]({url})"
    
    def format_list_item(self, text: str, level: int = 0) -> str:
        """格式化列表项
        
        Args:
            text: 列表项文本
            level: 缩进级别
            
        Returns:
            格式化后的列表项
        """
        indent = "  " * level
        return f"{indent}• {text}"
    
    def escape_special_characters(self, text: str) -> str:
        """转义Telegram特殊字符
        
        根据需求7.17实现特殊字符转义：
        - 支持Telegram的特殊字符转义，避免格式错误
        
        Args:
            text: 原始文本
            
        Returns:
            转义后的文本
        """
        if not self.config.escape_special_chars:
            return text
        
        # 使用MarkdownV1的简化转义规则（更稳定）
        # 只转义真正会影响格式的字符
        for char in self.markdown_v1_special_chars:
            # 避免重复转义
            if f"\\{char}" not in text:
                text = text.replace(char, f"\\{char}")
        
        return text
    
    def optimize_line_breaks(self, text: str) -> str:
        """优化换行符
        
        根据需求7.10实现移动端优化：
        - 优化Telegram消息格式，确保在移动端的可读性
        
        Args:
            text: 原始文本
            
        Returns:
            优化后的文本
        """
        if not self.config.optimize_for_mobile:
            return text
        
        # 限制连续换行（最多2个）
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        # 移除行尾空格
        text = re.sub(r' +\n', '\n', text)
        
        # 移除行首空格（除了列表缩进）
        lines = text.split('\n')
        optimized_lines = []
        for line in lines:
            if line.strip().startswith('•'):
                # 保留列表项的缩进
                optimized_lines.append(line)
            else:
                # 移除其他行的前导空格
                optimized_lines.append(line.lstrip())
        
        return '\n'.join(optimized_lines)
    
    def validate_telegram_format(self, text: str) -> bool:
        """验证Telegram格式正确性
        
        Args:
            text: 待验证的文本
            
        Returns:
            是否格式正确
        """
        try:
            # 检查括号匹配
            if text.count('[') != text.count(']'):
                self.logger.warning("方括号不匹配")
                return False
            
            if text.count('(') != text.count(')'):
                self.logger.warning("圆括号不匹配")
                return False
            
            # 检查格式标记匹配
            # 统计未转义的*和_
            unescaped_asterisks = len(re.findall(r'(?<!\\)\*', text))
            unescaped_underscores = len(re.findall(r'(?<!\\)_', text))
            
            if unescaped_asterisks % 2 != 0:
                self.logger.warning("粗体标记不匹配")
                return False
            
            if unescaped_underscores % 2 != 0:
                self.logger.warning("斜体标记不匹配")
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"验证格式时发生错误: {str(e)}")
            return False
    
    def split_long_message(self, message: str, max_length: Optional[int] = None) -> List[str]:
        """分割长消息
        
        根据需求7.13实现智能消息分割：
        - 智能分割消息并保持内容完整性
        
        Args:
            message: 原始消息
            max_length: 最大长度，默认使用配置值
            
        Returns:
            分割后的消息列表
        """
        max_len = max_length or self.config.max_message_length
        
        if len(message) <= max_len:
            return [message]
        
        parts = []
        current_part = ""
        lines = message.split('\n')
        
        for line in lines:
            # 检查添加这一行是否会超出长度限制
            test_part = current_part + '\n' + line if current_part else line
            
            if len(test_part) <= max_len:
                current_part = test_part
            else:
                # 如果当前部分不为空，保存它
                if current_part:
                    parts.append(current_part)
                    current_part = line
                else:
                    # 单行就超出限制，需要进一步分割
                    line_parts = self._split_long_line(line, max_len)
                    if line_parts:
                        parts.extend(line_parts[:-1])
                        current_part = line_parts[-1]
        
        # 添加最后一部分
        if current_part:
            parts.append(current_part)
        
        return parts
    
    def preserve_formatting_in_split(self, parts: List[str]) -> List[str]:
        """在分割后保持格式
        
        根据需求7.13实现格式保持：
        - 智能分割消息并保持内容完整性
        
        Args:
            parts: 分割后的消息部分
            
        Returns:
            格式保持的消息部分
        """
        if not self.config.preserve_formatting:
            return parts
        
        preserved_parts = []
        
        for i, part in enumerate(parts):
            # 检查是否有未闭合的格式标记
            preserved_part = part
            
            # 检查粗体标记
            asterisk_count = len(re.findall(r'(?<!\\)\*', part))
            if asterisk_count % 2 != 0:
                # 有未闭合的粗体标记，在末尾添加闭合标记
                preserved_part += '*'
                # 在下一部分开头添加开启标记
                if i + 1 < len(parts):
                    parts[i + 1] = '*' + parts[i + 1]
            
            # 检查斜体标记
            underscore_count = len(re.findall(r'(?<!\\)_', part))
            if underscore_count % 2 != 0:
                # 有未闭合的斜体标记，在末尾添加闭合标记
                preserved_part += '_'
                # 在下一部分开头添加开启标记
                if i + 1 < len(parts):
                    parts[i + 1] = '_' + parts[i + 1]
            
            preserved_parts.append(preserved_part)
        
        return preserved_parts
    
    def _split_long_line(self, line: str, max_length: int) -> List[str]:
        """分割超长行
        
        Args:
            line: 超长行
            max_length: 最大长度
            
        Returns:
            分割后的行列表
        """
        parts = []
        # 留一些缓冲空间
        safe_length = max_length - 100
        
        while len(line) > safe_length:
            # 尝试在合适的位置分割
            split_pos = safe_length
            
            # 寻找最近的空格或标点符号
            for i in range(safe_length - 1, safe_length // 2, -1):
                if line[i] in ' .,;!?，。；！？\n':
                    split_pos = i + 1
                    break
            
            parts.append(line[:split_pos])
            line = line[split_pos:]
        
        if line:
            parts.append(line)
        
        return parts
    
    def create_telegram_hyperlink(self, text: str, url: str) -> str:
        """创建Telegram超链接（别名方法）
        
        这是format_hyperlink的别名，提供更明确的命名。
        
        Args:
            text: 链接显示文本
            url: 链接URL
            
        Returns:
            Telegram格式的超链接
        """
        return self.format_hyperlink(text, url)
    
    def optimize_for_mobile_display(self, content: str) -> str:
        """优化移动端显示（别名方法）
        
        这是optimize_line_breaks的别名，提供更明确的命名。
        
        Args:
            content: 原始内容
            
        Returns:
            优化后的内容
        """
        return self.optimize_line_breaks(content)
    
    def format_section_header(self, title: str, emoji: str = "") -> str:
        """格式化章节标题
        
        Args:
            title: 标题文本
            emoji: 可选的emoji图标
            
        Returns:
            格式化后的章节标题
        """
        if emoji:
            return f"\n{emoji} *{self.escape_special_characters(title)}*\n"
        else:
            return f"\n*{self.escape_special_characters(title)}*\n"
    
    def format_message_item(self, time: str, category: str, weight_score: int, 
                           summary: str, source_url: str) -> str:
        """格式化单条消息项
        
        根据需求7.6和7.7实现消息格式化：
        - 包含大模型返回的所有字段（time、category、weight_score、summary、source）
        - 将source字段格式化为Telegram超链接形式
        
        Args:
            time: 时间
            category: 分类
            weight_score: 重要性评分
            summary: 摘要
            source_url: 来源URL
            
        Returns:
            格式化后的消息项
        """
        
        # 简化时间格式（移除年份）
        simplified_time = time
        if len(time) > 5 and time[4] == '-':  # 格式如 "2024-01-15"
            simplified_time = time[5:]  # 取 "01-15"
        
        # 构建消息项：摘要在前，时间、评分、链接在后面一行
        message = f"{self.escape_special_characters(summary)}\n"
        message += f"{self.escape_special_characters(simplified_time)} | {weight_score} | {self.format_hyperlink('查看原文', source_url)}"
        
        return message
    
    def format_data_source_status(self, source_name: str, status: str, 
                                  item_count: int, error_message: Optional[str] = None) -> str:
        """格式化数据源状态
        
        Args:
            source_name: 数据源名称
            status: 状态（success/error）
            item_count: 获取数量
            error_message: 错误信息（可选）
            
        Returns:
            格式化后的状态信息
        """
        status_emoji = "✅" if status == "success" else "❌"
        
        status_text = f"{status_emoji} {self.escape_special_characters(source_name)}: "
        
        if status == "success":
            status_text += f"{item_count} 条"
        else:
            status_text += "失败"
            if error_message:
                status_text += f" ({self.escape_special_characters(error_message[:50])})"
        
        return status_text
    
    def format_category_section(self, category_name: str, item_count: int, 
                               emoji: str = "📊") -> str:
        """格式化分类章节标题
        
        Args:
            category_name: 分类名称
            item_count: 该分类的消息数量
            emoji: 分类图标
            
        Returns:
            格式化后的分类标题
        """
        return f"\n{emoji} *{self.escape_special_characters(category_name)}* ({item_count}条)\n"
    
    def format_time_range(self, start_time: str, end_time: str, window_hours: int) -> str:
        """格式化时间范围
        
        Args:
            start_time: 开始时间
            end_time: 结束时间
            window_hours: 时间窗口（小时）
            
        Returns:
            格式化后的时间范围
        """
        return (
            f"⏰ *数据时间窗口*: {window_hours}小时\n"
            f"📅 *数据时间范围*: {self.escape_special_characters(start_time)} 至 "
            f"{self.escape_special_characters(end_time)}\n"
        )


# 工具函数
def create_formatter(
    max_message_length: int = 4096,
    preserve_formatting: bool = True,
    optimize_for_mobile: bool = True
) -> TelegramFormatter:
    """创建Telegram格式化器
    
    Args:
        max_message_length: 最大消息长度
        preserve_formatting: 是否保持格式
        optimize_for_mobile: 是否优化移动端显示
        
    Returns:
        TelegramFormatter实例
    """
    config = FormattingConfig(
        max_message_length=max_message_length,
        preserve_formatting=preserve_formatting,
        optimize_for_mobile=optimize_for_mobile
    )
    return TelegramFormatter(config)


def escape_telegram_text(text: str) -> str:
    """转义Telegram文本（快捷函数）
    
    Args:
        text: 原始文本
        
    Returns:
        转义后的文本
    """
    formatter = TelegramFormatter()
    return formatter.escape_special_characters(text)


def create_telegram_link(text: str, url: str) -> str:
    """创建Telegram链接（快捷函数）
    
    Args:
        text: 链接文本
        url: 链接URL
        
    Returns:
        Telegram格式的链接
    """
    formatter = TelegramFormatter()
    return formatter.format_hyperlink(text, url)
