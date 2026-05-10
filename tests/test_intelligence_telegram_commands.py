import asyncio
import time
from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

from telegram.ext import Application, CallbackQueryHandler

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
        call.args[0].commands
        for call in fake_application.add_handler.call_args_list
        if hasattr(call.args[0], "commands")
    ]
    assert any("intel_recent" in commands for commands in registered_commands)
    assert any("intel_labels" in commands for commands in registered_commands)
    assert any("intel_search" in commands for commands in registered_commands)
    assert any("intel_detail" in commands for commands in registered_commands)
    assert any("intel_follow" in commands for commands in registered_commands)
    assert any("intel_following" in commands for commands in registered_commands)
    assert any("intel_unfollow" in commands for commands in registered_commands)
    assert any("intel_ignored" in commands for commands in registered_commands)
    assert any("intel_unignore" in commands for commands in registered_commands)
    assert any(
        isinstance(call.args[0], CallbackQueryHandler)
        and getattr(call.args[0], "pattern", None)
        and call.args[0].pattern.pattern == r"^intel:(d|f|uf|i|u|p):"
        for call in fake_application.add_handler.call_args_list
    )


def test_authorized_intel_recent_handler_dispatches_business_method():
    handler: Any = _make_handler()
    handler.is_authorized_user = Mock(return_value=True)
    handler.handle_intel_recent_command = Mock(
        return_value={
            "entries": [_make_entry()],
            "total": 1,
            "page": 1,
            "total_pages": 1,
            "kind": "recent",
            "state_data": {"chat_id": "chat_1", "user_id": "1"},
        }
    )
    handler._send_intel_page = AsyncMock(return_value=[101, 102])
    handler._log_authorization_attempt = Mock()
    handler._log_command_execution = Mock()

    update = _make_update()
    context = SimpleNamespace(args=["24", "账号交易"])

    asyncio.run(handler._handle_intel_recent_command(update, context))

    handler.handle_intel_recent_command.assert_called_once_with(
        "1", "tester", "chat_1", 24, "账号交易", 1, return_markup=True
    )
    handler._send_intel_page.assert_awaited_once()
    send_page_call = handler._send_intel_page.await_args
    assert send_page_call is not None
    assert send_page_call.kwargs["action"] == "follow"
    update.message.reply_text.assert_not_awaited()


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
    service.semantic_search.return_value = (
        [
            (_make_entry(display_name="Seller One", confidence=0.91), 0.873),
            (_make_entry(id="intel-2", display_name="Seller Two", confidence=0.84), 0.811),
        ],
        2,
    )
    handler: Any = _make_handler(
        SimpleNamespace(intelligence_repository=repository, intelligence_search_service=service)
    )

    response = handler.handle_intel_search_command("1", "tester", "chat_1", "GPT plus购买渠道")

    service.semantic_search.assert_called_once_with(
        query_text="GPT plus购买渠道",
        page=1,
        page_size=handler.INTEL_PAGE_SIZE,
        tracking_scope="following",
    )
    assert "Seller One" in response
    assert "Seller Two" in response
    assert "相似度" in response
    assert "intel-1" not in response


def test_intel_search_business_method_returns_page_payload():
    repository = Mock()
    service = Mock()
    service.semantic_search.return_value = (
        [
            (_make_entry(display_name="Seller One", confidence=0.91), 0.873),
            (_make_entry(id="intel-2", display_name="Seller Two", confidence=0.84), 0.811),
        ],
        2,
    )
    handler: Any = _make_handler(
        SimpleNamespace(intelligence_repository=repository, intelligence_search_service=service)
    )

    payload = handler.handle_intel_search_command(
        "1", "tester", "chat_1", "GPT plus购买渠道", return_markup=True
    )

    assert payload["entries"][0].id == "intel-1"
    assert payload["total"] == 2
    assert payload["page"] == 1
    assert payload["kind"] == "search"
    assert payload["state_data"]["query"] == "GPT plus购买渠道"
    service.semantic_search.assert_called_once_with(
        query_text="GPT plus购买渠道",
        page=1,
        page_size=handler.INTEL_PAGE_SIZE,
        tracking_scope="following",
    )


def test_intel_recent_business_method_returns_page_payload_and_state_data():
    repository = Mock()
    repository.list_canonical_entries.return_value = [
        _make_entry(display_name="Seller One", confidence=0.93),
        _make_entry(id="intel-2", display_name="Seller Two", confidence=0.82),
    ]
    repository.count_canonical_entries.return_value = 2
    handler: Any = _make_handler(SimpleNamespace(intelligence_repository=repository))

    payload = handler.handle_intel_recent_command(
        "1", "tester", "chat_1", 24, "账号交易", return_markup=True
    )

    assert payload["entries"][0].id == "intel-1"
    assert payload["total"] == 2
    assert payload["page"] == 1
    assert payload["kind"] == "recent"
    assert payload["state_data"]["kind"] == "recent"
    assert payload["state_data"]["chat_id"] == "chat_1"
    assert payload["state_data"]["user_id"] == "1"
    assert payload["mark_discovery_presented_ids"] == ["intel-1", "intel-2"]
    assert repository.count_canonical_entries.call_args.kwargs["tracking_scope"] == "discovery"
    assert repository.list_canonical_entries.call_args.kwargs["tracking_scope"] == "discovery"
    repository.mark_discovery_presented.assert_not_called()
    assert handler._callback_state == {}


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
    repository.mark_discovery_presented.assert_called_once_with(["intel-1", "intel-2"])
    assert "Seller One" in response
    assert "intel-1" not in response
    assert "channel" in response
    assert "账号交易" in response
    assert "0.93" in response
    assert "最后出现" not in response
    assert "共 2 条" in response


def test_authorized_intel_following_handler_dispatches_business_method():
    handler: Any = _make_handler()
    handler.is_authorized_user = Mock(return_value=True)
    handler.handle_intel_following_command = Mock(
        return_value={
            "entries": [_make_entry()],
            "total": 1,
            "page": 1,
            "total_pages": 1,
            "kind": "following",
            "state_data": {"chat_id": "chat_1", "user_id": "1"},
        }
    )
    handler._send_intel_page = AsyncMock(return_value=[101, 102])
    handler._log_authorization_attempt = Mock()
    handler._log_command_execution = Mock()

    update = _make_update()
    context = SimpleNamespace(args=["100", "支付"])

    asyncio.run(handler._handle_intel_following_command(update, context))

    handler.handle_intel_following_command.assert_called_once_with(
        "1", "tester", "chat_1", 100, "支付", 1, return_markup=True
    )
    handler._send_intel_page.assert_awaited_once()
    send_page_call = handler._send_intel_page.await_args
    assert send_page_call is not None
    assert send_page_call.kwargs["action"] == "unfollow"
    update.message.reply_text.assert_not_awaited()


def test_intel_following_business_method_lists_followed_entries():
    repository = Mock()
    repository.list_canonical_entries.return_value = [
        _make_entry(display_name="Seller One", confidence=0.93),
        _make_entry(id="intel-2", display_name="Seller Two", confidence=0.82),
    ]
    repository.count_canonical_entries.return_value = 2
    handler: Any = _make_handler(SimpleNamespace(intelligence_repository=repository))

    payload = handler.handle_intel_following_command(
        "1", "tester", "chat_1", 100, "支付", return_markup=True
    )

    assert payload["entries"][0].id == "intel-1"
    assert payload["total"] == 2
    assert payload["kind"] == "following"
    assert payload["state_data"]["kind"] == "following"
    assert repository.count_canonical_entries.call_args.kwargs["tracking_scope"] == "following"
    assert repository.list_canonical_entries.call_args.kwargs["tracking_scope"] == "following"
    repository.mark_discovery_presented.assert_not_called()


def test_intel_recent_page_renders_follow_buttons():
    handler: Any = _make_handler()
    bot = SimpleNamespace(
        send_message=AsyncMock(
            side_effect=[
                SimpleNamespace(message_id=101),
                SimpleNamespace(message_id=102),
            ]
        )
    )
    handler.application = SimpleNamespace(bot=bot)

    asyncio.run(
        handler._send_intel_page(
            chat_id="chat_1",
            entries=[_make_entry()],
            page=1,
            total_pages=1,
            total=1,
            kind="recent",
            state_data={"kind": "recent", "chat_id": "chat_1", "user_id": "1"},
            action="follow",
        )
    )

    markup = bot.send_message.await_args_list[0].kwargs["reply_markup"]
    assert markup.inline_keyboard[0][1].text == "关注"
    assert markup.inline_keyboard[0][1].callback_data == "intel:f:intel-1"


def test_intel_follow_and_unfollow_business_methods_keep_ignore_state_separate():
    repository = Mock()
    repository.follow_canonical_entry.return_value = _make_entry(display_name="Seller One")
    repository.unfollow_canonical_entry.return_value = _make_entry(display_name="Seller One")
    handler: Any = _make_handler(SimpleNamespace(intelligence_repository=repository))

    follow_response = handler.handle_intel_follow_command("1", "tester", "chat_1", "intel-1")
    unfollow_response = handler.handle_intel_unfollow_command("1", "tester", "chat_1", "intel-1")

    repository.follow_canonical_entry.assert_called_once_with("intel-1")
    repository.unfollow_canonical_entry.assert_called_once_with("intel-1")
    repository.ignore_canonical_entry.assert_not_called()
    repository.unignore_canonical_entry.assert_not_called()
    assert "已关注：Seller One" in follow_response
    assert "已取消关注：Seller One" in unfollow_response


def test_intel_ignored_business_method_returns_restore_page_payload():
    repository = Mock()
    repository.count_ignored_canonical_entries.return_value = 2
    repository.list_ignored_canonical_entries.return_value = [
        _make_entry(display_name="Ignored One", confidence=0.77),
        _make_entry(id="intel-2", display_name="Ignored Two", confidence=0.66),
    ]
    handler: Any = _make_handler(SimpleNamespace(intelligence_repository=repository))

    payload = handler.handle_intel_ignored_command("1", "tester", "chat_1", 1, return_markup=True)

    repository.list_ignored_canonical_entries.assert_called_once_with(
        page=0, page_size=handler.INTEL_PAGE_SIZE
    )
    assert payload["entries"][0].id == "intel-1"
    assert payload["total"] == 2
    assert payload["kind"] == "ignored"
    assert payload["state_data"]["kind"] == "ignored"


def test_intel_unignore_business_method_restores_entry():
    repository = Mock()
    repository.unignore_canonical_entry.return_value = _make_entry(display_name="Ignored One")
    handler: Any = _make_handler(SimpleNamespace(intelligence_repository=repository))

    response = handler.handle_intel_unignore_command("1", "tester", "chat_1", "intel-1")

    repository.unignore_canonical_entry.assert_called_once_with("intel-1")
    assert "已恢复：Ignored One" in response


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
    update.message.reply_text.assert_awaited_once_with("🏷️ *可搜索情报标签*", parse_mode="Markdown")


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


def test_intel_detail_returns_paginated_evidence_groups_with_raw_context():
    anchor = SimpleNamespace(
        entry_id="intel-1",
        observation_id="obs-1",
        raw_item_id="raw-anchor",
        observed_at=datetime.utcnow(),
        published_at=datetime.utcnow(),
        collected_at=datetime.utcnow(),
    )
    anchor_raw = _make_raw_item(id="raw-anchor", raw_text="锚点原文")
    before_raw = _make_raw_item(id="raw-before", raw_text="上文")
    after_raw = _make_raw_item(id="raw-after", raw_text="下文")
    repository = Mock()
    repository.get_canonical_entry_by_id.return_value = _make_entry(latest_raw_item_id=None)
    repository.count_entry_evidence_anchors.return_value = 6
    repository.list_entry_evidence_anchors.return_value = [anchor]
    repository.get_entry_evidence_context_window.return_value = SimpleNamespace(
        items=[before_raw, anchor_raw, after_raw]
    )
    repository.get_raw_item_by_id.return_value = anchor_raw
    handler: Any = _make_handler(SimpleNamespace(intelligence_repository=repository))

    payload = handler.handle_intel_detail_command(
        "1", "tester", "chat_1", "intel-1", return_markup=True
    )

    assert payload["state_data"]["kind"] == "detail"
    assert payload["page"] == 1
    assert payload["total_pages"] == 2
    assert "证据组" in payload["text"]
    assert "锚点原文" in payload["text"]
    assert "上文" in payload["text"]
    assert "下文" in payload["text"]
    repository.list_entry_evidence_anchors.assert_called_once_with(
        entry_id="intel-1", page=1, page_size=handler.INTEL_EVIDENCE_PAGE_SIZE
    )
    repository.get_entry_evidence_context_window.assert_called_once_with(
        entry_id="intel-1", raw_item_id="raw-anchor", before=10, after=10
    )


def test_authorized_intel_callback_dispatches_detail_and_ignore():
    handler: Any = _make_handler()
    handler.is_authorized_user = Mock(return_value=True)
    handler.check_rate_limit = Mock(return_value=(True, None))
    handler._handle_intel_detail_callback = AsyncMock(return_value="已显示详情")
    handler._handle_intel_ignore_callback = AsyncMock(return_value="已忽略：Seller One")
    handler._handle_intel_follow_callback = AsyncMock(return_value="已关注：Seller One")
    handler._handle_intel_unfollow_callback = AsyncMock(return_value="已取消关注：Seller One")

    detail_update = _make_callback_update(data="intel:d:intel-1")
    ignore_update = _make_callback_update(data="intel:i:intel-1")
    follow_update = _make_callback_update(data="intel:f:intel-1")
    unfollow_update = _make_callback_update(data="intel:uf:intel-1")
    context = SimpleNamespace()

    asyncio.run(handler._handle_intel_callback_query(detail_update, context))
    asyncio.run(handler._handle_intel_callback_query(ignore_update, context))
    asyncio.run(handler._handle_intel_callback_query(follow_update, context))
    asyncio.run(handler._handle_intel_callback_query(unfollow_update, context))

    handler._handle_intel_detail_callback.assert_awaited_once_with(
        detail_update.callback_query, "1", "tester", "chat_1", "intel-1"
    )
    handler._handle_intel_ignore_callback.assert_awaited_once_with(
        ignore_update.callback_query, "1", "tester", "chat_1", "intel-1"
    )
    handler._handle_intel_follow_callback.assert_awaited_once_with(
        follow_update.callback_query, "1", "tester", "chat_1", "intel-1"
    )
    handler._handle_intel_unfollow_callback.assert_awaited_once_with(
        unfollow_update.callback_query, "1", "tester", "chat_1", "intel-1"
    )
    detail_update.callback_query.answer.assert_awaited_once_with("已显示详情")
    ignore_update.callback_query.answer.assert_awaited_once_with("已忽略：Seller One")
    follow_update.callback_query.answer.assert_awaited_once_with("已关注：Seller One")
    unfollow_update.callback_query.answer.assert_awaited_once_with("已取消关注：Seller One")


def test_authorized_intel_callback_dispatches_pagination_for_ignored_lists():
    handler: Any = _make_handler()
    handler.is_authorized_user = Mock(return_value=True)
    handler.check_rate_limit = Mock(return_value=(True, None))
    handler.handle_intel_ignored_command = Mock(
        return_value={
            "entries": [_make_entry(display_name="Ignored One")],
            "total": 1,
            "page": 2,
            "total_pages": 2,
            "kind": "ignored",
            "state_data": {"kind": "ignored", "chat_id": "chat_1", "user_id": "1"},
        }
    )
    handler._send_intel_page = AsyncMock(return_value=[201, 202])
    bot = SimpleNamespace(delete_message=AsyncMock())
    handler.application = SimpleNamespace(bot=bot)

    update = _make_callback_update(data="intel:p:tok123:2")
    handler._callback_state["tok123"] = {
        "kind": "ignored",
        "page_size": handler.INTEL_PAGE_SIZE,
        "chat_id": "chat_1",
        "user_id": "1",
        "sent_message_ids": [101, 102],
        "stored_at": time.time(),
    }
    context = SimpleNamespace()

    asyncio.run(handler._handle_intel_callback_query(update, context))

    handler.handle_intel_ignored_command.assert_called_once_with(
        "1", "tester", "chat_1", 2, return_markup=True
    )
    assert bot.delete_message.await_count == 2
    handler._send_intel_page.assert_awaited_once()
    update.callback_query.message.edit_text.assert_not_awaited()


def test_authorized_intel_callback_dispatches_detail_evidence_pagination():
    handler: Any = _make_handler()
    handler.is_authorized_user = Mock(return_value=True)
    handler.check_rate_limit = Mock(return_value=(True, None))
    handler.handle_intel_detail_command = Mock(
        return_value={
            "text": "证据组 第 2/2 页",
            "entry_id": "intel-1",
            "page": 2,
            "total_pages": 2,
            "total": 6,
            "state_data": {
                "kind": "detail",
                "entry_id": "intel-1",
                "chat_id": "chat_1",
                "user_id": "1",
            },
        }
    )
    handler._send_intel_detail_payload = AsyncMock()
    bot = SimpleNamespace(delete_message=AsyncMock())
    handler.application = SimpleNamespace(bot=bot)

    update = _make_callback_update(data="intel:p:detailtok:2")
    handler._callback_state["detailtok"] = {
        "kind": "detail",
        "entry_id": "intel-1",
        "page_size": handler.INTEL_EVIDENCE_PAGE_SIZE,
        "chat_id": "chat_1",
        "user_id": "1",
        "sent_message_ids": [301],
        "stored_at": time.time(),
    }
    context = SimpleNamespace()

    asyncio.run(handler._handle_intel_callback_query(update, context))

    handler.handle_intel_detail_command.assert_called_once_with(
        "1",
        "tester",
        "chat_1",
        "intel-1",
        include_raw=False,
        evidence_page=2,
        return_markup=True,
    )
    bot.delete_message.assert_awaited_once()
    handler._send_intel_detail_payload.assert_awaited_once()
    update.callback_query.answer.assert_awaited_once_with("已更新详情")


def test_unauthorized_intel_callback_does_not_ignore_entry():
    handler: Any = _make_handler()
    handler.is_authorized_user = Mock(return_value=False)
    handler.check_rate_limit = Mock()
    handler._handle_intel_ignore_callback = AsyncMock()

    update = _make_callback_update(data="intel:i:intel-1")
    context = SimpleNamespace()

    asyncio.run(handler._handle_intel_callback_query(update, context))

    handler.check_rate_limit.assert_not_called()
    handler._handle_intel_ignore_callback.assert_not_called()
    update.callback_query.answer.assert_awaited_once_with("未授权")


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


def test_intel_unignore_handler_dispatches_business_method():
    handler: Any = _make_handler()
    handler.is_authorized_user = Mock(return_value=True)
    handler.handle_intel_unignore_command = Mock(return_value="已恢复：Seller One")
    handler._log_authorization_attempt = Mock()
    handler._log_command_execution = Mock()

    update = _make_update()
    context = SimpleNamespace(args=["intel-1"])

    asyncio.run(handler._handle_intel_unignore_command(update, context))

    handler.handle_intel_unignore_command.assert_called_once_with(
        "1", "tester", "chat_1", "intel-1"
    )
    update.message.reply_text.assert_awaited_once_with("已恢复：Seller One", parse_mode="Markdown")
