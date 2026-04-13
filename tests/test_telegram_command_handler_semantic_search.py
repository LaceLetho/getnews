import asyncio
from types import SimpleNamespace
from typing import Any, Dict
from unittest.mock import AsyncMock, Mock, patch

from telegram import BotCommand
from telegram.ext import Application

from crypto_news_analyzer.models import TelegramCommandConfig
from crypto_news_analyzer.reporters.telegram_command_handler import (
    TelegramCommandHandler,
)


class _SemanticSearchCoordinatorStub:
    def __init__(self, search_result: Dict[str, Any]):
        self.semantic_search_service = Mock()
        self.semantic_search_service.search.return_value = search_result
        self.telegram_sender = Mock()
        self.telegram_sender.send_report_to_chat.return_value = Mock(
            success=True,
            error_message=None,
        )


class _SemanticSearchCoordinatorGetterStub:
    def __init__(self, search_result: Dict[str, Any]):
        self._service = Mock()
        self._service.search.return_value = search_result
        self.telegram_sender = Mock()
        self.telegram_sender.send_report_to_chat.return_value = Mock(
            success=True,
            error_message=None,
        )

    def get_semantic_search_service(self):
        return self._service


def _make_handler(coordinator: Any = None):
    return TelegramCommandHandler(
        bot_token="token",
        execution_coordinator=coordinator
        or _SemanticSearchCoordinatorStub(
            {
                "success": True,
                "report_content": "# report",
                "execution_id": "semantic-1",
                "errors": [],
            }
        ),
        config=TelegramCommandConfig(),
    )


def _make_update(user_id="1", username="tester", chat_id="chat_1", chat_type="private"):
    message = SimpleNamespace(reply_text=AsyncMock())
    return SimpleNamespace(
        effective_user=SimpleNamespace(
            id=user_id, username=username, first_name=username
        ),
        effective_chat=SimpleNamespace(id=chat_id, type=chat_type),
        message=message,
    )


def test_build_application_registers_semantic_search_command():
    handler: Any = _make_handler()
    fake_application = Mock()
    fake_application.add_handler = Mock()

    fake_builder = Mock()
    fake_builder.token.return_value = fake_builder
    fake_builder.updater.return_value = fake_builder
    fake_builder.build.return_value = fake_application

    with patch.object(Application, "builder", return_value=fake_builder):
        handler._build_application()

    registered_commands = [
        call.args[0].commands for call in fake_application.add_handler.call_args_list
    ]
    assert any("semantic_search" in commands for commands in registered_commands)


def test_setup_bot_commands_includes_semantic_search():
    handler: Any = _make_handler()
    handler.application = SimpleNamespace(
        bot=SimpleNamespace(set_my_commands=AsyncMock())
    )

    asyncio.run(handler._setup_bot_commands())

    sent_commands = handler.application.bot.set_my_commands.await_args.args[0]
    assert (
        BotCommand("semantic_search", "语义搜索，如/semantic_search 24 BTC adoption")
        in sent_commands
    )


def test_help_text_includes_semantic_search_usage():
    handler: Any = _make_handler()

    help_text = handler.handle_help_command("1")

    assert "/semantic_search <hours> <topic>" in help_text
    assert "hours 为必填参数" in help_text


def test_semantic_search_handler_rejects_missing_arguments():
    handler: Any = _make_handler()
    handler.is_authorized_user = Mock(return_value=True)
    handler.check_rate_limit = Mock(return_value=(True, None))
    handler.handle_semantic_search_command = Mock()
    handler._log_authorization_attempt = Mock()
    handler._log_command_execution = Mock()

    update = _make_update()
    context = SimpleNamespace(args=["24"])

    asyncio.run(handler._handle_semantic_search_command(update, context))

    handler.handle_semantic_search_command.assert_not_called()
    update.message.reply_text.assert_awaited_once()
    assert (
        "/semantic_search <hours> <topic>"
        in update.message.reply_text.await_args.args[0]
    )


def test_semantic_search_handler_rejects_invalid_hours_and_blank_topic():
    handler: Any = _make_handler()
    handler.is_authorized_user = Mock(return_value=True)
    handler.check_rate_limit = Mock(return_value=(True, None))
    handler.handle_semantic_search_command = Mock()
    handler._log_authorization_attempt = Mock()
    handler._log_command_execution = Mock()

    update = _make_update()

    asyncio.run(
        handler._handle_semantic_search_command(
            update, SimpleNamespace(args=["abc", "BTC"])
        )
    )
    assert "有效的小时数" in update.message.reply_text.await_args.args[0]

    update_blank_topic = _make_update()
    asyncio.run(
        handler._handle_semantic_search_command(
            update_blank_topic, SimpleNamespace(args=["24", "   "])
        )
    )
    assert (
        "/semantic_search <hours> <topic>"
        in update_blank_topic.message.reply_text.await_args.args[0]
    )


def test_semantic_search_handler_parses_topic_and_dispatches_business_method():
    handler: Any = _make_handler()
    handler.is_authorized_user = Mock(return_value=True)
    handler.check_rate_limit = Mock(return_value=(True, None))
    handler.handle_semantic_search_command = Mock(return_value="🔎 开始语义搜索")
    handler._log_authorization_attempt = Mock()
    handler._log_command_execution = Mock()

    update = _make_update()
    context = SimpleNamespace(args=["24", "BTC", "adoption"])

    asyncio.run(handler._handle_semantic_search_command(update, context))

    handler.handle_semantic_search_command.assert_called_once_with(
        "1", "tester", "chat_1", 24, "BTC adoption"
    )
    update.message.reply_text.assert_awaited_once_with(
        "🔎 开始语义搜索", parse_mode="Markdown"
    )


def test_semantic_search_background_flow_sends_report_to_chat():
    coordinator = _SemanticSearchCoordinatorStub(
        {
            "success": True,
            "report_content": "# semantic report",
            "execution_id": "semantic-1",
            "errors": [],
        }
    )
    handler: Any = _make_handler(coordinator)
    handler._send_message_sync = Mock()
    handler._log_command_execution = Mock()

    handler._execute_semantic_search_and_notify(
        user_id="1",
        username="tester",
        chat_id="chat_1",
        hours=24,
        topic="BTC adoption",
        semantic_search_service=coordinator.semantic_search_service,
    )

    coordinator.semantic_search_service.search.assert_called_once_with(
        query="BTC adoption", time_window_hours=24
    )
    coordinator.telegram_sender.send_report_to_chat.assert_called_once_with(
        "# semantic report", "chat_1"
    )
    handler._send_message_sync.assert_not_called()


def test_get_semantic_search_service_uses_coordinator_getter_when_attribute_missing():
    coordinator = _SemanticSearchCoordinatorGetterStub(
        {
            "success": True,
            "report_content": "# semantic report",
            "execution_id": "semantic-1",
            "errors": [],
        }
    )
    handler: Any = _make_handler(coordinator)

    assert handler._get_semantic_search_service() is coordinator._service


def test_semantic_search_background_flow_sends_no_match_message():
    coordinator = _SemanticSearchCoordinatorStub(
        {
            "success": True,
            "report_content": "",
            "execution_id": "semantic-1",
            "errors": [],
        }
    )
    handler: Any = _make_handler(coordinator)
    sent_messages = []
    handler._send_message_sync = lambda _chat_id, message: sent_messages.append(message)
    handler._log_command_execution = Mock()

    handler._execute_semantic_search_and_notify(
        user_id="1",
        username="tester",
        chat_id="chat_1",
        hours=24,
        topic="BTC adoption",
        semantic_search_service=coordinator.semantic_search_service,
    )

    coordinator.telegram_sender.send_report_to_chat.assert_not_called()
    assert sent_messages
    assert "暂无符合条件的新内容" in sent_messages[0]
    assert "BTC adoption" in sent_messages[0]


def test_initialize_webhook_caches_running_event_loop():
    handler: Any = _make_handler()
    fake_application = SimpleNamespace(
        initialize=AsyncMock(),
        start=AsyncMock(),
        bot=SimpleNamespace(
            set_my_commands=AsyncMock(),
            set_webhook=AsyncMock(),
        ),
    )
    handler._build_application = Mock(return_value=fake_application)
    handler._resolve_all_usernames = AsyncMock()
    handler._setup_bot_commands = AsyncMock()
    handler.get_webhook_url = Mock(return_value="https://example.com/telegram/webhook")
    handler.get_webhook_path = Mock(return_value="/telegram/webhook")
    handler.get_webhook_secret_token = Mock(return_value="secret")

    asyncio.run(handler.initialize_webhook())

    assert handler._event_loop is not None
    assert handler._event_loop.is_running() is False
