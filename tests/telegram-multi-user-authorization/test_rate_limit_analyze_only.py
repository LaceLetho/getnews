from unittest.mock import AsyncMock, Mock, patch

import pytest
from telegram import Chat, Message, Update, User
from telegram.ext import ContextTypes

from crypto_news_analyzer.reporters.telegram_command_handler import TelegramCommandHandler


@pytest.fixture
def mock_config():
    config = Mock()
    config.enabled = True
    config.command_rate_limit = {
        "max_commands_per_hour": 10,
        "cooldown_minutes": 5,
    }
    return config


@pytest.fixture
def handler(mock_config):
    with patch.dict("os.environ", {"TELEGRAM_AUTHORIZED_USERS": "123456789"}):
        test_handler = TelegramCommandHandler(
            bot_token="test_token",
            execution_coordinator=Mock(),
            config=mock_config,
        )
        test_handler.application = Mock()
        test_handler.application.bot = Mock()
        return test_handler


@pytest.fixture
def mock_update():
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
    mock_context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    mock_context.args = []

    await handler._handle_help_command(mock_update, mock_context)
    help_response = mock_update.message.reply_text.call_args[0][0]
    assert "⏱️ 速率限制" not in help_response

    mock_update.message.reply_text.reset_mock()

    await handler._handle_status_command(mock_update, mock_context)
    status_response = mock_update.message.reply_text.call_args[0][0]
    assert "⏱️ 速率限制" not in status_response


@pytest.mark.asyncio
async def test_analyze_command_rate_limited_after_first_call(handler, mock_update):
    mock_context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    mock_context.args = []

    with patch.object(handler, "handle_analyze_command", return_value="🔍 开始分析"):
        await handler._handle_analyze_command(mock_update, mock_context)
    first_response = mock_update.message.reply_text.call_args[0][0]
    assert "⏱️ 速率限制" not in first_response

    mock_update.message.reply_text.reset_mock()

    await handler._handle_analyze_command(mock_update, mock_context)
    second_response = mock_update.message.reply_text.call_args[0][0]
    assert "⏱️ 速率限制" in second_response or "命令冷却中" in second_response


def test_check_rate_limit_tracks_analyze_commands(handler):
    user_id = "123456789"
    state = handler._rate_limit_states[user_id]
    initial_time = state.last_analyze_command_time

    allowed, error = handler.check_rate_limit(user_id)
    assert allowed is True
    assert error is None
    assert state.last_analyze_command_time > initial_time

    allowed, error = handler.check_rate_limit(user_id)
    assert allowed is False
    assert "命令冷却" in error
