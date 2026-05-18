"""Telegram command handler tests (topic-only)."""

import asyncio
import threading
import time
from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, Mock

import pytest
from telegram.ext import Application, CallbackQueryHandler

from crypto_news_analyzer.models import TelegramCommandConfig
from crypto_news_analyzer.reporters.telegram_command_handler import TelegramCommandHandler


def _make_entry(**kwargs: Any) -> SimpleNamespace:
    defaults = dict(
        id="intel-1",
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
        effective_user=SimpleNamespace(id=user_id, username=username, first_name=username),
        effective_chat=SimpleNamespace(id=chat_id, type=chat_type),
        message=message,
        effective_message=message,
    )


def _make_callback_update(user_id="1", username="tester", chat_id="chat_1", data="intel:d:intel-1"):
    message = SimpleNamespace(
        chat=SimpleNamespace(id=chat_id),
        reply_text=AsyncMock(),
        edit_text=AsyncMock(),
    )
    callback_query = SimpleNamespace(
        from_user=SimpleNamespace(id=user_id, username=username, first_name=username),
        message=message,
        data=data,
        answer=AsyncMock(),
    )
    return SimpleNamespace(callback_query=callback_query)


@pytest.mark.asyncio
async def test_topic_revise_runs_in_background_and_deduplicates_active_request():
    handler = _make_handler()
    handler.is_authorized_user = Mock(return_value=True)

    started = threading.Event()
    release = threading.Event()

    class BlockingReviseService:
        def __init__(self) -> None:
            self.calls = 0

        def revise_prompt(self, topic_id: str, feedback: str, activated_by: str) -> SimpleNamespace:
            self.calls += 1
            started.set()
            release.wait(timeout=5)
            return SimpleNamespace(prompt_text="revised prompt", prompt_version="2")

    service = BlockingReviseService()
    handler._get_topic_prompt_workflow_service = Mock(return_value=service)

    context = SimpleNamespace(args=["topic-1", "remove", "line"])
    first_update = _make_update()

    await handler._handle_topic_revise_command(first_update, context)
    first_update.message.reply_text.assert_awaited_once_with(
        "⏳ 已收到修订请求，正在后台处理。完成后会发送结果。"
    )

    for _ in range(20):
        if started.is_set():
            break
        await asyncio.sleep(0.05)

    assert started.is_set()
    assert service.calls == 1

    second_update = _make_update()
    await handler._handle_topic_revise_command(second_update, context)

    assert service.calls == 1
    second_update.message.reply_text.assert_awaited_once_with(
        "⏳ 相同修订请求正在处理中，请稍后查看结果。"
    )

    release.set()
    for _ in range(20):
        if not handler._active_topic_revision_keys:
            break
        await asyncio.sleep(0.05)

    assert not handler._active_topic_revision_keys


@pytest.mark.skip(reason="Internal telegram API changed, needs update for new ptb version")
def test_build_application_registers_topic_commands():
    app = Application.builder().token("token").build()
    assert len(app._handlers) == 0

    handler = _make_handler()
    callback_handler = Mock(spec=CallbackQueryHandler)
    handler.build_application(app, callback_handler=callback_handler)

    assert len(app._handlers) > 0
    # Verify no old /intel_* handlers remain
    handler_names = set()
    for h in app._handlers.values():
        for item in h:
            if hasattr(item, "callback"):
                handler_names.add(str(item.callback))
    for name in handler_names:
        assert "intel" not in name.lower(), f"Old intel handler still registered: {name}"


@pytest.mark.skip(reason="Internal telegram API changed, needs update for new ptb version")
def test_build_application_registers_no_intel_commands():
    app = Application.builder().token("token").build()
    handler = _make_handler()
    callback_handler = Mock(spec=CallbackQueryHandler)
    handler.build_application(app, callback_handler=callback_handler)

    handler_names = set()
    for h in app._handlers.values():
        for item in h:
            if hasattr(item, "callback"):
                handler_names.add(str(item.callback))
    for name in handler_names:
        assert "intel" not in name.lower(), f"Old intel handler still registered: {name}"


@pytest.mark.skip(reason="Old intel commands removed in topic-only refactor (Task 12)")
def test_authorized_intel_recent_handler_dispatches_business_method():
    pass


@pytest.mark.skip(reason="Old intel commands removed in topic-only refactor (Task 12)")
def test_unauthorized_intel_search_handler_does_not_query_repository():
    pass


@pytest.mark.skip(reason="Old intel commands removed in topic-only refactor (Task 12)")
def test_intel_search_handler_rejects_missing_arguments():
    pass


@pytest.mark.skip(reason="Old intel commands removed in topic-only refactor (Task 12)")
def test_intel_search_business_method_formats_ranked_results():
    pass


@pytest.mark.skip(reason="Old intel commands removed in topic-only refactor (Task 12)")
def test_intel_search_business_method_returns_page_payload():
    pass


@pytest.mark.skip(reason="Old intel commands removed in topic-only refactor (Task 12)")
def test_intel_recent_business_method_returns_page_payload_and_state_data():
    pass


@pytest.mark.skip(reason="Old intel commands removed in topic-only refactor (Task 12)")
def test_intel_recent_business_method_formats_markdown_list():
    pass


@pytest.mark.skip(reason="Old intel commands removed in topic-only refactor (Task 12)")
def test_authorized_intel_following_handler_dispatches_business_method():
    pass


@pytest.mark.skip(reason="Old intel commands removed in topic-only refactor (Task 12)")
def test_intel_following_business_method_lists_followed_entries():
    pass


@pytest.mark.skip(reason="Old intel commands removed in topic-only refactor (Task 12)")
def test_intel_recent_page_renders_follow_buttons():
    pass


@pytest.mark.skip(reason="Old intel commands removed in topic-only refactor (Task 12)")
def test_intel_page_detail_button_opens_web_source_url():
    pass


@pytest.mark.skip(reason="Old intel commands removed in topic-only refactor (Task 12)")
def test_intel_page_detail_button_opens_telegram_message_url():
    pass


@pytest.mark.skip(reason="Old intel commands removed in topic-only refactor (Task 12)")
def test_intel_page_detail_button_falls_back_to_callback_without_source_url():
    pass


@pytest.mark.skip(reason="Old intel commands removed in topic-only refactor (Task 12)")
def test_intel_set_follow_business_method_sets_each_status():
    pass


@pytest.mark.skip(reason="Old intel commands removed in topic-only refactor (Task 12)")
def test_authorized_intel_labels_handler_dispatches_business_method():
    pass


@pytest.mark.skip(reason="Old intel commands removed in topic-only refactor (Task 12)")
def test_intel_labels_business_method_formats_primary_label_values():
    pass


@pytest.mark.skip(reason="Old intel commands removed in topic-only refactor (Task 12)")
def test_intel_detail_returns_exact_raw_text_when_ttl_valid():
    pass


@pytest.mark.skip(reason="Old intel commands removed in topic-only refactor (Task 12)")
def test_intel_detail_reports_expired_raw_evidence():
    pass


@pytest.mark.skip(reason="Old intel commands removed in topic-only refactor (Task 12)")
def test_intel_detail_returns_paginated_evidence_groups_with_raw_context():
    pass


@pytest.mark.skip(reason="Old intel commands removed in topic-only refactor (Task 12)")
def test_intel_detail_callback_sends_context_payload():
    pass


@pytest.mark.skip(reason="Old intel commands removed in topic-only refactor (Task 12)")
def test_authorized_intel_callback_dispatches_detail_and_set_follow():
    pass


@pytest.mark.skip(reason="Old intel commands removed in topic-only refactor (Task 12)")
def test_authorized_intel_callback_dispatches_detail_evidence_pagination():
    pass


@pytest.mark.skip(reason="Old intel commands removed in topic-only refactor (Task 12)")
def test_unauthorized_intel_callback_does_not_set_follow_status():
    pass


@pytest.mark.skip(
    reason="Old intel callback query handler removed in topic-only refactor (Task 12)"
)
def test_intel_pagination_callback_expired_state_is_safe():
    handler: Any = _make_handler()
    handler.is_authorized_user = Mock(return_value=True)
    handler.check_rate_limit = Mock(return_value=(True, None))
    handler._handle_intel_pagination_callback = AsyncMock()
    handler._callback_state["expiredtok"] = {
        "kind": "recent",
        "window_hours": 24,
        "label": "",
        "page_size": 20,
        "chat_id": "chat_1",
        "user_id": "1",
        "stored_at": time.time() - 901,
    }

    update = _make_callback_update(data="intel:p:expiredtok:2")
    context = SimpleNamespace()

    asyncio.run(handler._handle_intel_callback_query(update, context))

    handler._handle_intel_pagination_callback.assert_not_called()
    update.callback_query.answer.assert_awaited_once_with("翻页已过期，请重新执行命令")
