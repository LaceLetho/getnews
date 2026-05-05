import asyncio
from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

from telegram.ext import Application

from crypto_news_analyzer.domain.models import PrimaryLabel
from crypto_news_analyzer.models import TelegramCommandConfig
from crypto_news_analyzer.reporters.telegram_command_handler import TelegramCommandHandler


def _make_entry(**kwargs: Any) -> SimpleNamespace:
    defaults = dict(
        id="intel-1",
        entry_type="channel",
        normalized_key="seller-1",
        display_name="Seller One",
        explanation="购买渠道",
        usage_summary=None,
        primary_label="账号交易",
        secondary_tags=["btc"],
        confidence=0.93,
        first_seen_at=datetime.utcnow() - timedelta(days=2),
        last_seen_at=datetime.utcnow() - timedelta(hours=1),
        evidence_count=7,
        latest_raw_item_id="raw-1",
        prompt_version="v1",
        model_name="gpt",
        schema_version="1",
        aliases=["seller"],
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def _make_raw_item(**kwargs: Any) -> SimpleNamespace:
    defaults = dict(
        id="raw-1",
        source_type="telegram_group",
        raw_text="原始证据文本\n保持原样",
        source_url="https://t.me/example",
        published_at=datetime.utcnow() - timedelta(hours=2),
        collected_at=datetime.utcnow() - timedelta(hours=1, minutes=30),
        expires_at=datetime.utcnow() + timedelta(days=1),
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def _make_handler(coordinator: Any = None) -> Any:
    return TelegramCommandHandler(
        bot_token="token",
        execution_coordinator=coordinator or SimpleNamespace(),
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
        effective_message=message,
    )


def test_build_application_registers_intelligence_commands():
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
    assert any("intel_recent" in commands for commands in registered_commands)
    assert any("intel_labels" in commands for commands in registered_commands)
    assert any("intel_search" in commands for commands in registered_commands)
    assert any("intel_detail" in commands for commands in registered_commands)


def test_authorized_intel_recent_handler_dispatches_business_method():
    handler: Any = _make_handler()
    handler.is_authorized_user = Mock(return_value=True)
    handler.handle_intel_recent_command = Mock(return_value="📌 *最近情报条目*")
    handler._log_authorization_attempt = Mock()
    handler._log_command_execution = Mock()

    update = _make_update()
    context = SimpleNamespace(args=["24", "账号交易"])

    asyncio.run(handler._handle_intel_recent_command(update, context))

    handler.handle_intel_recent_command.assert_called_once_with(
        "1", "tester", "chat_1", 24, "账号交易", 1
    )
    update.message.reply_text.assert_awaited_once_with(
        "📌 *最近情报条目*", parse_mode="Markdown"
    )


def test_unauthorized_intel_search_handler_does_not_query_repository():
    handler: Any = _make_handler()
    handler.is_authorized_user = Mock(return_value=False)
    handler.handle_intel_search_command = Mock()
    handler._log_authorization_attempt = Mock()
    handler._log_command_execution = Mock()

    update = _make_update()
    context = SimpleNamespace(args=["GPT", "plus购买渠道"])

    asyncio.run(handler._handle_intel_search_command(update, context))

    handler.handle_intel_search_command.assert_not_called()
    update.message.reply_text.assert_awaited_once()
    assert "权限拒绝" in update.message.reply_text.await_args.args[0]


def test_intel_search_handler_rejects_missing_arguments():
    handler: Any = _make_handler()
    handler.is_authorized_user = Mock(return_value=True)
    handler.handle_intel_search_command = Mock()
    handler.check_rate_limit = Mock(return_value=(True, None))
    handler._log_authorization_attempt = Mock()
    handler._log_command_execution = Mock()

    update = _make_update()
    context = SimpleNamespace(args=[])

    asyncio.run(handler._handle_intel_search_command(update, context))

    handler.handle_intel_search_command.assert_not_called()
    assert "/intel_search <query>" in update.message.reply_text.await_args.args[0]


def test_intel_search_business_method_formats_ranked_results():
    repository = Mock()
    service = Mock()
    service.semantic_search.return_value = [
        (_make_entry(display_name="Seller One", confidence=0.91), 0.873),
        (_make_entry(id="intel-2", display_name="Seller Two", confidence=0.84), 0.811),
    ]
    handler: Any = _make_handler(
        SimpleNamespace(
            intelligence_repository=repository, intelligence_search_service=service
        )
    )

    response = handler.handle_intel_search_command("1", "tester", "chat_1", "GPT plus购买渠道")

    service.semantic_search.assert_called_once_with(query_text="GPT plus购买渠道", limit=10)
    assert "Seller One" in response
    assert "Seller Two" in response
    assert "相似度" in response


def test_intel_recent_business_method_formats_markdown_list():
    repository = Mock()
    repository.list_canonical_entries.return_value = [
        _make_entry(display_name="Seller One", confidence=0.93),
        _make_entry(id="intel-2", display_name="Seller Two", confidence=0.82),
    ]
    repository.count_canonical_entries.return_value = 2
    handler: Any = _make_handler(SimpleNamespace(intelligence_repository=repository))

    response = handler.handle_intel_recent_command("1", "tester", "chat_1", 24, "账号交易")

    repository.list_canonical_entries.assert_called_once()
    assert "Seller One" in response
    assert "intel-1" in response
    assert "channel" in response
    assert "账号交易" in response
    assert "0.93" in response
    assert "最后出现" not in response
    assert "共 2 条" in response


def test_authorized_intel_labels_handler_dispatches_business_method():
    handler: Any = _make_handler()
    handler.is_authorized_user = Mock(return_value=True)
    handler.handle_intel_labels_command = Mock(return_value="🏷️ *可搜索情报标签*")
    handler._log_authorization_attempt = Mock()
    handler._log_command_execution = Mock()

    update = _make_update()
    context = SimpleNamespace(args=[])

    asyncio.run(handler._handle_intel_labels_command(update, context))

    handler.handle_intel_labels_command.assert_called_once_with("1", "tester", "chat_1")
    update.message.reply_text.assert_awaited_once_with(
        "🏷️ *可搜索情报标签*", parse_mode="Markdown"
    )


def test_intel_labels_business_method_formats_primary_label_values():
    handler: Any = _make_handler()
    handler._log_command_execution = Mock()

    response = handler.handle_intel_labels_command("1", "tester", "chat_1")

    for label in PrimaryLabel:
        assert label.value in response
    assert "`crypto` (CRYPTO)" in response
    assert "/intel_recent 24 支付" in response


def test_intel_detail_returns_exact_raw_text_when_ttl_valid():
    raw_text = "原始证据文本\n保持原样"
    repository = Mock()
    repository.get_canonical_entry_by_id.return_value = _make_entry()
    repository.get_raw_item_by_id.return_value = _make_raw_item(raw_text=raw_text)
    handler: Any = _make_handler(SimpleNamespace(intelligence_repository=repository))

    response = handler.handle_intel_detail_command(
        "1", "tester", "chat_1", "intel-1", include_raw=True
    )

    assert raw_text in response
    assert "raw evidence expired" not in response
    assert raw_text not in handler.command_history[-1].response_message
    assert "omitted from command history" in handler.command_history[-1].response_message


def test_intel_detail_reports_expired_raw_evidence():
    repository = Mock()
    repository.get_canonical_entry_by_id.return_value = _make_entry()
    repository.get_raw_item_by_id.return_value = _make_raw_item(
        expires_at=datetime.utcnow() - timedelta(seconds=1)
    )
    handler: Any = _make_handler(SimpleNamespace(intelligence_repository=repository))

    response = handler.handle_intel_detail_command(
        "1", "tester", "chat_1", "intel-1", include_raw=True
    )

    assert "raw evidence expired" in response
    assert "Seller One" in response
