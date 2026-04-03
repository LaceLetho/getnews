from unittest.mock import AsyncMock, Mock, patch

import pytest
from telegram import Chat, Message, Update, User
from telegram.ext import ContextTypes

from crypto_news_analyzer.models import ChatContext
from crypto_news_analyzer.reporters.telegram_command_handler import TelegramCommandHandler


@pytest.fixture
def mock_config():
    config = Mock()
    config.enabled = True
    config.command_rate_limit = {"max_commands_per_hour": 10, "cooldown_minutes": 5}
    return config


@pytest.fixture
def mock_coordinator():
    coordinator = Mock()
    coordinator.get_execution_status.return_value = {
        "status": "idle",
        "current_execution": None,
    }
    return coordinator


@pytest.fixture
def handler(mock_config, mock_coordinator):
    with patch.dict("os.environ", {"TELEGRAM_AUTHORIZED_USERS": "123456789"}):
        test_handler = TelegramCommandHandler(
            bot_token="test_token",
            execution_coordinator=mock_coordinator,
            config=mock_config,
        )
        test_handler.application = Mock()
        test_handler.application.bot = Mock()
        return test_handler


def create_mock_update(user_id: str, username: str, chat_type: str, chat_id: str) -> Update:
    update = Mock(spec=Update)

    user = Mock(spec=User)
    user.id = int(user_id)
    user.username = username
    user.first_name = username
    update.effective_user = user

    chat = Mock(spec=Chat)
    chat.id = int(chat_id)
    chat.type = chat_type
    update.effective_chat = chat

    message = Mock(spec=Message)
    message.reply_text = AsyncMock()
    update.message = message
    return update


@pytest.mark.asyncio
async def test_handle_analyze_command_extracts_chat_context(handler):
    update = create_mock_update("123456789", "testuser", "private", "123456789")
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.args = []

    with patch.object(handler, "_extract_chat_context") as mock_extract:
        mock_extract.return_value = ChatContext(
            user_id="123456789",
            username="testuser",
            chat_id="123456789",
            chat_type="private",
            is_private=True,
            is_group=False,
        )
        with patch.object(handler, "is_authorized_user", return_value=True):
            with patch.object(handler, "check_rate_limit", return_value=(True, None)):
                with patch.object(handler, "handle_analyze_command", return_value="✅ 分析已启动"):
                    await handler._handle_analyze_command(update, context)

    mock_extract.assert_called_once_with(update)


@pytest.mark.asyncio
async def test_handle_analyze_command_logs_authorization_success(handler):
    update = create_mock_update("123456789", "testuser", "group", "-100123456789")
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.args = []

    with patch.object(handler, "is_authorized_user", return_value=True):
        with patch.object(handler, "check_rate_limit", return_value=(True, None)):
            with patch.object(handler, "handle_analyze_command", return_value="✅ 分析已启动"):
                with patch.object(handler, "_log_authorization_attempt") as mock_log_auth:
                    await handler._handle_analyze_command(update, context)

    mock_log_auth.assert_called_once_with(
        command="/analyze",
        user_id="123456789",
        username="testuser",
        chat_type="group",
        chat_id="-100123456789",
        authorized=True,
    )


@pytest.mark.asyncio
async def test_handle_analyze_command_rejects_unauthorized_user(handler):
    update = create_mock_update("999999999", "unauthorized", "private", "999999999")
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.args = []

    with patch.object(handler, "is_authorized_user", return_value=False):
        await handler._handle_analyze_command(update, context)

    update.message.reply_text.assert_called_once_with("❌ 权限拒绝\n\n您没有权限执行此命令。")


@pytest.mark.asyncio
async def test_handle_analyze_command_reports_rate_limit(handler):
    update = create_mock_update("123456789", "testuser", "private", "123456789")
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.args = []

    with patch.object(handler, "is_authorized_user", return_value=True):
        with patch.object(handler, "check_rate_limit", return_value=(False, "命令冷却中")):
            await handler._handle_analyze_command(update, context)

    sent = update.message.reply_text.call_args[0][0]
    assert "⏱️ 速率限制" in sent
    assert "命令冷却中" in sent
