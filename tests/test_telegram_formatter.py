"""
Telegram格式化器单元测试

测试TelegramFormatter类的各种格式化功能。
"""

import pytest
from crypto_news_analyzer.reporters.telegram_formatter import (
    TelegramFormatter,
    FormattingConfig,
    create_formatter,
    escape_telegram_text,
    create_telegram_link
)


class TestTelegramFormatter:
    """TelegramFormatter基础功能测试"""
    
    def test_initialization(self):
        """测试初始化"""
        formatter = TelegramFormatter()
        assert formatter is not None
        assert formatter.config is not None
        assert formatter.config.max_message_length == 4096
    
    def test_initialization_with_config(self):
        """测试使用自定义配置初始化"""
        config = FormattingConfig(
            max_message_length=2000,
            preserve_formatting=False,
            optimize_for_mobile=False
        )
        formatter = TelegramFormatter(config)
        assert formatter.config.max_message_length == 2000
        assert formatter.config.preserve_formatting is False
        assert formatter.config.optimize_for_mobile is False


class TestTextFormatting:
    """文本格式化测试"""
    
    def test_format_bold(self):
        """测试粗体格式化"""
        formatter = TelegramFormatter()
        result = formatter.format_bold("重要消息")
        assert result == "*重要消息*"
    
    def test_format_italic(self):
        """测试斜体格式化"""
        formatter = TelegramFormatter()
        result = formatter.format_italic("提示信息")
        assert result == "_提示信息_"
    
    def test_format_code(self):
        """测试代码格式化"""
        formatter = TelegramFormatter()
        result = formatter.format_code("print('hello')")
        assert result == "`print('hello')`"
    
    def test_format_header_level1(self):
        """测试一级标题格式化"""
        formatter = TelegramFormatter()
        result = formatter.format_header("主标题", level=1)
        assert "*主标题*" in result
    
    def test_format_header_level2(self):
        """测试二级标题格式化"""
        formatter = TelegramFormatter()
        result = formatter.format_header("副标题", level=2)
        assert "*副标题*" in result
    
    def test_format_header_level3(self):
        """测试三级标题格式化"""
        formatter = TelegramFormatter()
        result = formatter.format_header("小标题", level=3)
        assert "小标题" in result


class TestHyperlinkFormatting:
    """超链接格式化测试"""
    
    def test_format_hyperlink_basic(self):
        """测试基本超链接格式化"""
        formatter = TelegramFormatter()
        result = formatter.format_hyperlink("点击这里", "https://example.com")
        assert result == "[点击这里](https://example.com)"
    
    def test_format_hyperlink_with_special_chars(self):
        """测试包含特殊字符的超链接"""
        formatter = TelegramFormatter()
        result = formatter.format_hyperlink("查看_详情", "https://example.com/page?id=123")
        # 文本中的特殊字符应该被转义
        assert "[查看\\_详情]" in result
        assert "(https://example.com/page?id=123)" in result
    
    def test_create_telegram_hyperlink_alias(self):
        """测试create_telegram_hyperlink别名方法"""
        formatter = TelegramFormatter()
        result = formatter.create_telegram_hyperlink("链接", "https://test.com")
        assert result == formatter.format_hyperlink("链接", "https://test.com")
    
    def test_create_telegram_link_function(self):
        """测试快捷函数create_telegram_link"""
        result = create_telegram_link("测试", "https://test.com")
        assert "[测试](https://test.com)" == result


class TestSpecialCharacterEscaping:
    """特殊字符转义测试"""
    
    def test_escape_underscore(self):
        """测试下划线转义"""
        formatter = TelegramFormatter()
        result = formatter.escape_special_characters("test_value")
        assert result == "test\\_value"
    
    def test_escape_asterisk(self):
        """测试星号转义"""
        formatter = TelegramFormatter()
        result = formatter.escape_special_characters("test*value")
        assert result == "test\\*value"
    
    def test_escape_brackets(self):
        """测试方括号转义"""
        formatter = TelegramFormatter()
        result = formatter.escape_special_characters("test[value]")
        assert result == "test\\[value\\]"
    
    def test_escape_backtick(self):
        """测试反引号转义"""
        formatter = TelegramFormatter()
        result = formatter.escape_special_characters("test`value")
        assert result == "test\\`value"
    
    def test_escape_multiple_special_chars(self):
        """测试多个特殊字符转义"""
        formatter = TelegramFormatter()
        result = formatter.escape_special_characters("test_value*with[brackets]")
        assert "\\_" in result
        assert "\\*" in result
        assert "\\[" in result
        assert "\\]" in result
    
    def test_escape_already_escaped(self):
        """测试避免重复转义"""
        formatter = TelegramFormatter()
        # 已经转义的字符不应该再次转义
        result = formatter.escape_special_characters("test\\_value")
        # 应该保持原样，不会变成 test\\\\_value
        assert result == "test\\_value"
    
    def test_escape_telegram_text_function(self):
        """测试快捷函数escape_telegram_text"""
        result = escape_telegram_text("test_value")
        assert result == "test\\_value"
    
    def test_no_escape_when_disabled(self):
        """测试禁用转义时的行为"""
        config = FormattingConfig(escape_special_chars=False)
        formatter = TelegramFormatter(config)
        result = formatter.escape_special_characters("test_value*with[brackets]")
        assert result == "test_value*with[brackets]"


class TestListFormatting:
    """列表格式化测试"""
    
    def test_format_list_item_level0(self):
        """测试零级列表项"""
        formatter = TelegramFormatter()
        result = formatter.format_list_item("项目1", level=0)
        assert result == "• 项目1"
    
    def test_format_list_item_level1(self):
        """测试一级列表项"""
        formatter = TelegramFormatter()
        result = formatter.format_list_item("子项目", level=1)
        assert result == "  • 子项目"
    
    def test_format_list_item_level2(self):
        """测试二级列表项"""
        formatter = TelegramFormatter()
        result = formatter.format_list_item("子子项目", level=2)
        assert result == "    • 子子项目"


class TestLineBreakOptimization:
    """换行优化测试"""
    
    def test_optimize_line_breaks_multiple_newlines(self):
        """测试优化多个连续换行"""
        formatter = TelegramFormatter()
        text = "第一行\n\n\n\n第二行"
        result = formatter.optimize_line_breaks(text)
        assert result == "第一行\n\n第二行"
    
    def test_optimize_line_breaks_trailing_spaces(self):
        """测试移除行尾空格"""
        formatter = TelegramFormatter()
        text = "第一行   \n第二行  \n"
        result = formatter.optimize_line_breaks(text)
        assert result == "第一行\n第二行\n"
    
    def test_optimize_line_breaks_leading_spaces(self):
        """测试移除行首空格（非列表项）"""
        formatter = TelegramFormatter()
        text = "   第一行\n  第二行"
        result = formatter.optimize_line_breaks(text)
        assert result == "第一行\n第二行"
    
    def test_optimize_line_breaks_preserve_list_indent(self):
        """测试保留列表项缩进"""
        formatter = TelegramFormatter()
        text = "  • 列表项1\n    • 列表项2"
        result = formatter.optimize_line_breaks(text)
        assert "  • 列表项1" in result
        assert "    • 列表项2" in result
    
    def test_optimize_for_mobile_display_alias(self):
        """测试optimize_for_mobile_display别名方法"""
        formatter = TelegramFormatter()
        text = "第一行\n\n\n第二行"
        result = formatter.optimize_for_mobile_display(text)
        assert result == formatter.optimize_line_breaks(text)
    
    def test_no_optimization_when_disabled(self):
        """测试禁用优化时的行为"""
        config = FormattingConfig(optimize_for_mobile=False)
        formatter = TelegramFormatter(config)
        text = "第一行\n\n\n\n第二行"
        result = formatter.optimize_line_breaks(text)
        assert result == text


class TestMessageSplitting:
    """消息分割测试"""
    
    def test_split_short_message(self):
        """测试短消息不分割"""
        formatter = TelegramFormatter()
        message = "这是一条短消息"
        result = formatter.split_long_message(message)
        assert len(result) == 1
        assert result[0] == message
    
    def test_split_long_message_by_lines(self):
        """测试按行分割长消息"""
        formatter = TelegramFormatter()
        # 创建一个超长消息
        lines = ["第{}行内容".format(i) for i in range(1000)]
        message = "\n".join(lines)
        result = formatter.split_long_message(message)
        assert len(result) > 1
        # 验证所有部分都不超过最大长度
        for part in result:
            assert len(part) <= formatter.config.max_message_length
    
    def test_split_long_message_custom_length(self):
        """测试使用自定义最大长度分割"""
        formatter = TelegramFormatter()
        message = "a" * 1000
        result = formatter.split_long_message(message, max_length=200)
        assert len(result) > 1
        for part in result:
            assert len(part) <= 200
    
    def test_split_preserves_content(self):
        """测试分割后内容完整性"""
        formatter = TelegramFormatter()
        lines = ["第{}行".format(i) for i in range(100)]
        message = "\n".join(lines)
        result = formatter.split_long_message(message)
        # 重新组合应该得到原始内容
        combined = "\n".join(result)
        # 可能会有一些额外的换行，但内容应该都在
        for line in lines:
            assert line in combined
    
    def test_split_very_long_single_line(self):
        """测试分割超长单行"""
        formatter = TelegramFormatter()
        # 创建一个超长的单行（没有换行符）
        message = "这是一个非常长的句子，" * 500
        result = formatter.split_long_message(message)
        assert len(result) > 1
        for part in result:
            assert len(part) <= formatter.config.max_message_length


class TestFormatValidation:
    """格式验证测试"""
    
    def test_validate_correct_format(self):
        """测试验证正确格式"""
        formatter = TelegramFormatter()
        text = "*粗体* _斜体_ [链接](https://example.com)"
        assert formatter.validate_telegram_format(text) is True
    
    def test_validate_unmatched_brackets(self):
        """测试检测不匹配的方括号"""
        formatter = TelegramFormatter()
        text = "[未闭合的方括号"
        assert formatter.validate_telegram_format(text) is False
    
    def test_validate_unmatched_parentheses(self):
        """测试检测不匹配的圆括号"""
        formatter = TelegramFormatter()
        text = "(未闭合的圆括号"
        assert formatter.validate_telegram_format(text) is False
    
    def test_validate_unmatched_bold(self):
        """测试检测不匹配的粗体标记"""
        formatter = TelegramFormatter()
        text = "*未闭合的粗体"
        assert formatter.validate_telegram_format(text) is False
    
    def test_validate_unmatched_italic(self):
        """测试检测不匹配的斜体标记"""
        formatter = TelegramFormatter()
        text = "_未闭合的斜体"
        assert formatter.validate_telegram_format(text) is False
    
    def test_validate_escaped_chars_not_counted(self):
        """测试转义字符不计入匹配检查"""
        formatter = TelegramFormatter()
        text = "这是一个\\*转义的星号\\*"
        # 转义的星号不应该被计入格式标记
        assert formatter.validate_telegram_format(text) is True


class TestComplexFormatting:
    """复杂格式化测试"""
    
    def test_format_message_item(self):
        """测试格式化消息项"""
        formatter = TelegramFormatter()
        result = formatter.format_message_item(
            time="2024-01-01 12:00",
            category="市场动态",
            weight_score=80,
            summary="比特币价格突破新高",
            source_url="https://example.com/news/123"
        )
        assert "2024-01-01 12:00" in result
        assert "市场动态" in result
        assert "80" in result
        assert "比特币价格突破新高" in result
        assert "[查看原文](https://example.com/news/123)" in result
        assert "⭐" in result  # 应该包含星星评分
    
    def test_format_message_item_high_score(self):
        """测试高分消息项的星星数量"""
        formatter = TelegramFormatter()
        result = formatter.format_message_item(
            time="2024-01-01",
            category="重要",
            weight_score=100,
            summary="测试",
            source_url="https://test.com"
        )
        # 100分应该显示5颗星
        assert result.count("⭐") == 5
    
    def test_format_message_item_low_score(self):
        """测试低分消息项的星星数量"""
        formatter = TelegramFormatter()
        result = formatter.format_message_item(
            time="2024-01-01",
            category="普通",
            weight_score=10,
            summary="测试",
            source_url="https://test.com"
        )
        # 10分应该显示1颗星
        assert result.count("⭐") == 1
    
    def test_format_data_source_status_success(self):
        """测试格式化成功的数据源状态"""
        formatter = TelegramFormatter()
        result = formatter.format_data_source_status(
            source_name="RSS源1",
            status="success",
            item_count=10
        )
        assert "✅" in result
        assert "RSS源1" in result
        assert "10 条" in result
    
    def test_format_data_source_status_error(self):
        """测试格式化失败的数据源状态"""
        formatter = TelegramFormatter()
        result = formatter.format_data_source_status(
            source_name="RSS源2",
            status="error",
            item_count=0,
            error_message="连接超时"
        )
        assert "❌" in result
        assert "RSS源2" in result
        assert "失败" in result
        assert "连接超时" in result
    
    def test_format_category_section(self):
        """测试格式化分类章节"""
        formatter = TelegramFormatter()
        result = formatter.format_category_section(
            category_name="大户动向",
            item_count=5,
            emoji="🐋"
        )
        assert "🐋" in result
        assert "大户动向" in result
        assert "5条" in result
    
    def test_format_section_header(self):
        """测试格式化章节标题"""
        formatter = TelegramFormatter()
        result = formatter.format_section_header("市场快照", emoji="📊")
        assert "📊" in result
        assert "*市场快照*" in result


class TestUtilityFunctions:
    """工具函数测试"""
    
    def test_create_formatter(self):
        """测试create_formatter工具函数"""
        formatter = create_formatter(
            max_message_length=2000,
            preserve_formatting=False,
            optimize_for_mobile=False
        )
        assert formatter.config.max_message_length == 2000
        assert formatter.config.preserve_formatting is False
        assert formatter.config.optimize_for_mobile is False
    
    def test_create_formatter_defaults(self):
        """测试create_formatter使用默认值"""
        formatter = create_formatter()
        assert formatter.config.max_message_length == 4096
        assert formatter.config.preserve_formatting is True
        assert formatter.config.optimize_for_mobile is True


class TestEdgeCases:
    """边界情况测试"""
    
    def test_empty_text(self):
        """测试空文本"""
        formatter = TelegramFormatter()
        assert formatter.escape_special_characters("") == ""
        assert formatter.optimize_line_breaks("") == ""
    
    def test_none_handling(self):
        """测试None值处理"""
        formatter = TelegramFormatter()
        # 这些方法应该能处理空字符串，但不应该接受None
        # 如果传入None，应该抛出异常或返回合理的默认值
        with pytest.raises((TypeError, AttributeError)):
            formatter.escape_special_characters(None)
    
    def test_very_long_url(self):
        """测试超长URL"""
        formatter = TelegramFormatter()
        long_url = "https://example.com/" + "a" * 1000
        result = formatter.format_hyperlink("链接", long_url)
        assert long_url in result
    
    def test_unicode_characters(self):
        """测试Unicode字符"""
        formatter = TelegramFormatter()
        text = "测试中文🎉emoji表情符号"
        result = formatter.escape_special_characters(text)
        assert "测试中文" in result
        assert "🎉" in result
        assert "emoji表情符号" in result
    
    def test_mixed_newline_types(self):
        """测试混合换行符类型"""
        formatter = TelegramFormatter()
        text = "第一行\n第二行\r\n第三行\r第四行"
        result = formatter.optimize_line_breaks(text)
        # 应该能处理不同类型的换行符
        assert "第一行" in result
        assert "第二行" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
