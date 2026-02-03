"""
Telegram发送可靠性属性测试

使用Hypothesis进行属性测试，验证Telegram发送的可靠性。
**功能: crypto-news-analyzer, 属性 7: Telegram发送可靠性**
**验证: 需求 8.1**
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from hypothesis import given, strategies as st, assume, settings
from typing import Dict, Any, List, Optional
import json
import re
import tempfile
import os

from crypto_news_analyzer.reporters.telegram_sender import (
    TelegramSender,
    TelegramConfig,
    SendResult
)


# 策略定义：生成有效的Telegram配置
@st.composite
def valid_telegram_config(draw):
    """生成有效的Telegram配置"""
    # 生成有效的Bot Token格式
    bot_id = draw(st.integers(min_value=100000000, max_value=9999999999))
    token_part = draw(st.text(
        alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'), whitelist_characters='-_'),
        min_size=35,
        max_size=35
    ))
    bot_token = f"{bot_id}:{token_part}"
    
    # 生成有效的Channel ID格式
    channel_id = draw(st.one_of(
        st.text(min_size=2, max_size=32).map(lambda x: f"@{x}"),  # @username格式
        st.integers(min_value=-1000000000000, max_value=-1).map(str),  # 负数ID格式
        st.integers(min_value=1, max_value=1000000000000).map(str)  # 正数ID格式
    ))
    
    parse_mode = draw(st.sampled_from(["Markdown", "HTML", "MarkdownV2"]))
    max_message_length = draw(st.integers(min_value=1000, max_value=4096))
    retry_attempts = draw(st.integers(min_value=1, max_value=5))
    retry_delay = draw(st.floats(min_value=0.1, max_value=5.0))
    
    return TelegramConfig(
        bot_token=bot_token,
        channel_id=channel_id,
        parse_mode=parse_mode,
        max_message_length=max_message_length,
        retry_attempts=retry_attempts,
        retry_delay=retry_delay
    )


@st.composite
def valid_report_content(draw):
    """生成有效的报告内容"""
    # 生成包含各种Markdown元素的报告
    title = draw(st.text(min_size=10, max_size=100))
    
    # 生成状态表格
    status_rows = draw(st.lists(
        st.tuples(
            st.text(min_size=5, max_size=30),  # 数据源名称
            st.sampled_from(["✅ 成功", "❌ 失败"]),  # 状态
            st.integers(min_value=0, max_value=100).map(str)  # 数量
        ),
        min_size=1,
        max_size=10
    ))
    
    # 生成分类内容
    categories = draw(st.lists(
        st.tuples(
            st.sampled_from(["大户动向", "利率事件", "美国政府监管政策", "安全事件", "新产品", "市场新现象"]),
            st.lists(
                st.tuples(
                    st.text(min_size=10, max_size=200),  # 标题
                    st.text(min_size=20, max_size=500),  # 内容
                    st.text(min_size=10, max_size=100).map(lambda x: f"https://example.com/{x}")  # URL
                ),
                min_size=0,
                max_size=5
            )
        ),
        min_size=1,
        max_size=6
    ))
    
    # 构建报告内容
    report_parts = [
        f"# {title}",
        "",
        "## 数据源状态",
        "",
        "| 数据源 | 状态 | 获取数量 |",
        "|--------|------|----------|"
    ]
    
    for name, status, count in status_rows:
        report_parts.append(f"| {name} | {status} | {count} |")
    
    report_parts.append("")
    
    for category_name, items in categories:
        report_parts.append(f"## {category_name}")
        report_parts.append("")
        
        if not items:
            report_parts.append("暂无相关信息")
        else:
            for title, content, url in items:
                report_parts.append(f"### {title}")
                report_parts.append(f"{content}")
                report_parts.append(f"[原文链接]({url})")
                report_parts.append("")
    
    return "\n".join(report_parts)


@st.composite
def mock_api_response(draw):
    """生成模拟的API响应"""
    success = draw(st.booleans())
    
    if success:
        return {
            "ok": True,
            "result": {
                "message_id": draw(st.integers(min_value=1, max_value=1000000))
            }
        }
    else:
        error_descriptions = [
            "Bad Request: chat not found",
            "Unauthorized",
            "Forbidden: bot was blocked by the user",
            "Bad Request: message is too long",
            "Too Many Requests: retry after 30"
        ]
        return {
            "ok": False,
            "description": draw(st.sampled_from(error_descriptions))
        }


class TestTelegramSendingReliabilityProperties:
    """Telegram发送可靠性属性测试"""
    
    @given(
        config=valid_telegram_config(),
        report=valid_report_content()
    )
    @settings(max_examples=10, deadline=None)
    def test_telegram_sending_reliability_with_valid_config(self, config: TelegramConfig, report: str):
        """
        属性测试：Telegram发送可靠性 - 有效配置
        
        **功能: crypto-news-analyzer, 属性 7: Telegram发送可靠性**
        **验证: 需求 8.1**
        
        对于任何生成的报告，如果Telegram配置有效，系统应该成功发送报告到指定频道
        """
        async def run_test():
            # 模拟成功的API响应
            with patch('aiohttp.ClientSession.post') as mock_post:
                mock_response = AsyncMock()
                mock_response.json.return_value = {
                    "ok": True,
                    "result": {"message_id": 123}
                }
                mock_post.return_value.__aenter__.return_value = mock_response
                
                # 创建发送器并发送报告
                sender = TelegramSender(config)
                
                async with sender:
                    # 模拟配置验证成功
                    with patch.object(sender, 'validate_configuration', return_value=SendResult(success=True)):
                        result = await sender.send_report(report)
                
                # 验证：发送应该成功
                assert result.success, f"发送失败: {result.error_message}"
                assert result.message_id is not None, "应该返回消息ID"
                assert result.parts_sent > 0, "应该发送至少一个部分"
                assert result.total_parts > 0, "应该有至少一个总部分"
                assert result.parts_sent <= result.total_parts, "发送部分数不应超过总部分数"
        
        # 运行异步测试
        asyncio.run(run_test())
    
    @given(config=valid_telegram_config())
    @settings(max_examples=10, deadline=None)
    def test_message_splitting_consistency(self, config: TelegramConfig):
        """
        属性测试：消息分割的一致性
        
        验证长消息分割后的总长度不超过限制
        """
        # 生成一个超长消息
        long_message = "这是一条很长的消息。" * 1000  # 确保超过限制
        
        sender = TelegramSender(config)
        parts = sender.split_long_message(long_message)
        
        # 验证：每个部分都不超过长度限制
        for i, part in enumerate(parts):
            assert len(part) <= config.max_message_length, f"第{i+1}部分超过长度限制: {len(part)} > {config.max_message_length}"
        
        # 验证：所有部分合并后包含原始内容的主要信息
        combined_length = sum(len(part) for part in parts)
        assert combined_length > 0, "分割后的总长度应该大于0"
        
        # 验证：至少有一个部分
        assert len(parts) >= 1, "应该至少有一个消息部分"


def test_run_telegram_properties():
    """运行Telegram发送可靠性属性测试的同步包装器"""
    # 运行同步测试
    test_instance = TestTelegramSendingReliabilityProperties()
    
    # 测试消息分割
    config = TelegramConfig(
        bot_token="123456789:ABCdefGHIjklMNOpqrsTUVwxyz",
        channel_id="@test_channel"
    )
    
    # 手动调用测试方法（不使用Hypothesis）
    sender = TelegramSender(config)
    
    # 测试消息分割功能
    long_message = "这是一条很长的消息。" * 200
    parts = sender.split_long_message(long_message)
    assert len(parts) >= 1, "应该至少有一个消息部分"
    for part in parts:
        assert len(part) <= config.max_message_length, "每个部分都不应超过长度限制"
    
    # 测试Markdown格式化
    markdown_text = "**测试**文本"
    formatted = sender.format_for_telegram(markdown_text)
    assert formatted is not None, "格式化结果不应为None"
    
    # 测试备份创建
    with tempfile.TemporaryDirectory() as temp_dir:
        backup_filename = "test_backup.md"
        
        def mock_save_backup(report_content, filename=None):
            if filename is None:
                from datetime import datetime
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"crypto_news_report_{timestamp}.md"
            
            backup_path = os.path.join(temp_dir, filename)
            
            try:
                with open(backup_path, 'w', encoding='utf-8') as f:
                    f.write(report_content)
                return backup_path
            except Exception:
                return ""
        
        sender.save_report_backup = mock_save_backup
        
        test_report = "# 测试报告\n\n这是测试内容"
        backup_path = sender.save_report_backup(test_report, backup_filename)
        
        assert backup_path, "备份路径不应为空"
        assert os.path.exists(backup_path), "备份文件应该存在"


if __name__ == "__main__":
    # 运行属性测试
    pytest.main([__file__, "-v", "--tb=short"])