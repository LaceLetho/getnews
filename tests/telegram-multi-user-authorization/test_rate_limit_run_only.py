"""
测试速率限制仅应用于/run命令

验证:
- /help 和 /status 命令不受速率限制影响
- 只有 /run 命令受到冷却时间限制
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock
from telegram import Update, User, Chat, Message
from telegram.ext import ContextTypes

from crypto_news_analyzer.reporters.telegram_command_handler import (
    TelegramCommandHandler,
)


@pytest.fixture
def mock_config():
    """创建测试配置"""
    config = Mock()
    config.enabled = True
    config.execution_timeout_minutes = 30
    config.max_concurrent_executions = 1
    config.command_rate_limit = {
        "max_commands_per_hour": 10,
        "cooldown_minutes": 5,
    }
    return config


@pytest.fixture
def handler(mock_config):
    """创建命令处理器实例"""
    with patch.dict('os.environ', {'TELEGRAM_AUTHORIZED_USERS': '123456789'}):
        handler = TelegramCommandHandler(
            bot_token="test_token",
            execution_coordinator=Mock(),
            config=mock_config
        )
        handler.application = Mock()
        handler.application.bot = Mock()
        return handler


@pytest.fixture
def mock_update():
    """创建模拟的Update对象"""
    update = Mock(spec=Update)
    update.effective_user = Mock(spec=User)
    update.effective_user.id = 123456789
    update.effective_user.username = "testuser"
    update.effective_chat = Mock(spec=Chat)
    update.effective_chat.id = 123456789
    update.effective_chat.type = "private"
    update.message = Mock(spec=Message)
    update.message.reply_text = AsyncMock()
    return update


@pytest.mark.asyncio
async def test_help_and_status_not_rate_limited(handler, mock_update):
    """
    测试 /help 和 /status 命令不受速率限制影响
    
    场景:
    1. 连续调用 /help 命令
    2. 立即调用 /status 命令
    3. 验证两个命令都成功执行，没有速率限制错误
    """
    mock_context = Mock(spec=ContextTypes.DEFAULT_TYPE)

    # 调用 /help 命令
    await handler._handle_help_command(mock_update, mock_context)
    
    # 验证 /help 成功执行（检查是否有实际的速率限制错误，而不是帮助文本中的说明）
    assert mock_update.message.reply_text.called
    help_response = mock_update.message.reply_text.call_args[0][0]
    assert "⏱️ 速率限制" not in help_response  # 实际的速率限制错误消息
    assert "命令冷却中" not in help_response

    # 重置 mock
    mock_update.message.reply_text.reset_mock()

    # 立即调用 /status 命令（无需等待）
    await handler._handle_status_command(mock_update, mock_context)
    
    # 验证 /status 成功执行
    assert mock_update.message.reply_text.called
    status_response = mock_update.message.reply_text.call_args[0][0]
    assert "⏱️ 速率限制" not in status_response
    assert "命令冷却中" not in status_response


@pytest.mark.asyncio
async def test_run_command_rate_limited_after_help_status(handler, mock_update):
    """
    测试在调用 /help 和 /status 后，/run 命令仍然受速率限制
    
    场景:
    1. 调用 /help 命令
    2. 调用 /status 命令
    3. 调用 /run 命令（第一次，应该成功）
    4. 立即再次调用 /run 命令（应该被速率限制）
    """
    mock_context = Mock(spec=ContextTypes.DEFAULT_TYPE)

    # 调用 /help
    await handler._handle_help_command(mock_update, mock_context)
    mock_update.message.reply_text.reset_mock()

    # 调用 /status
    await handler._handle_status_command(mock_update, mock_context)
    mock_update.message.reply_text.reset_mock()

    # 第一次调用 /run（应该成功）
    await handler._handle_run_command(mock_update, mock_context)
    assert mock_update.message.reply_text.called
    first_run_response = mock_update.message.reply_text.call_args[0][0]
    assert "⏱️ 速率限制" not in first_run_response
    assert "命令冷却中" not in first_run_response

    # 重置 mock
    mock_update.message.reply_text.reset_mock()

    # 立即第二次调用 /run（应该被速率限制）
    await handler._handle_run_command(mock_update, mock_context)
    assert mock_update.message.reply_text.called
    second_run_response = mock_update.message.reply_text.call_args[0][0]
    assert "⏱️ 速率限制" in second_run_response or "命令冷却中" in second_run_response


@pytest.mark.asyncio
async def test_multiple_help_status_calls_no_rate_limit(handler, mock_update):
    """
    测试多次调用 /help 和 /status 不会触发速率限制
    
    场景:
    1. 连续调用 /help 5次
    2. 连续调用 /status 5次
    3. 验证所有调用都成功，没有速率限制
    """
    mock_context = Mock(spec=ContextTypes.DEFAULT_TYPE)

    # 连续调用 /help 5次
    for i in range(5):
        await handler._handle_help_command(mock_update, mock_context)
        assert mock_update.message.reply_text.called
        response = mock_update.message.reply_text.call_args[0][0]
        assert "⏱️ 速率限制" not in response, f"/help call {i+1} was rate limited"
        assert "命令冷却中" not in response, f"/help call {i+1} was rate limited"
        mock_update.message.reply_text.reset_mock()

    # 连续调用 /status 5次
    for i in range(5):
        await handler._handle_status_command(mock_update, mock_context)
        assert mock_update.message.reply_text.called
        response = mock_update.message.reply_text.call_args[0][0]
        assert "⏱️ 速率限制" not in response, f"/status call {i+1} was rate limited"
        assert "命令冷却中" not in response, f"/status call {i+1} was rate limited"
        mock_update.message.reply_text.reset_mock()


def test_check_rate_limit_only_tracks_run_commands(handler):
    """
    测试 check_rate_limit 方法只跟踪 /run 命令的时间戳
    
    验证:
    - check_rate_limit 更新 last_run_command_time
    - 不影响其他命令的执行
    """
    user_id = "123456789"
    
    # 获取初始状态
    state = handler._rate_limit_states[user_id]
    initial_time = state.last_run_command_time
    
    # 调用 check_rate_limit（模拟 /run 命令）
    allowed, error = handler.check_rate_limit(user_id)
    assert allowed is True
    assert error is None
    
    # 验证 last_run_command_time 被更新
    assert state.last_run_command_time > initial_time
    
    # 立即再次调用应该被限制
    allowed, error = handler.check_rate_limit(user_id)
    assert allowed is False
    assert "命令冷却" in error
