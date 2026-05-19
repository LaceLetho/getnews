"""Integration tests for Telegram /topic_* command handlers.

Tests the topic-only intelligence refactor Telegram surface:
topic_create, topic_revise, topic_set_prompt, topic_confirm,
topic_list, topic_detail, topic_merge, topic_pause, topic_archive.
"""

import asyncio
from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

from crypto_news_analyzer.models import TelegramCommandConfig
from crypto_news_analyzer.reporters.telegram_command_handler import TelegramCommandHandler


def _make_handler(**kwargs: Any) -> TelegramCommandHandler:
    coordinator = SimpleNamespace(
        intelligence_repository=None,
        topic_prompt_workflow_service=None,
        topic_finding_merge_service=None,
    )
    handler_kwargs = dict(
        bot_token="test_token",
        execution_coordinator=coordinator,
        config=TelegramCommandConfig(),
        **kwargs,
    )
    return TelegramCommandHandler(**handler_kwargs)


def _make_update(
    user_id: str = "123",
    username: str = "testuser",
    chat_id: str = "456",
    text: str = "/topic_list",
) -> SimpleNamespace:
    message = SimpleNamespace(
        message_id=1,
        chat=SimpleNamespace(id=chat_id),
        text=text,
        reply_text=AsyncMock(),
        chat_id=chat_id,
    )
    return SimpleNamespace(
        effective_user=SimpleNamespace(
            id=user_id, username=username, first_name="Test", is_bot=False
        ),
        effective_chat=SimpleNamespace(id=chat_id),
        effective_message=message,
        message=message,
    )


def _make_callback_update(
    user_id: str = "123",
    username: str = "testuser",
    chat_id: str = "456",
    data: str = "topic:list:p:token:1",
) -> SimpleNamespace:
    message = SimpleNamespace(
        message_id=1,
        chat=SimpleNamespace(id=chat_id),
        reply_text=AsyncMock(),
        edit_text=AsyncMock(),
    )
    callback_query = SimpleNamespace(
        from_user=SimpleNamespace(id=user_id, username=username, first_name="Test"),
        message=message,
        data=data,
        answer=AsyncMock(),
    )
    return SimpleNamespace(callback_query=callback_query)


# --- Topic Create + Confirm Flow ---

def test_topic_create_confirm_flow():
    """Full flow: /topic_create -> /topic_confirm activates a topic."""
    handler = _make_handler()
    handler.is_authorized_user = Mock(return_value=True)
    handler.check_rate_limit = Mock(return_value=(True, None))
    handler._log_command_execution = Mock()

    # Mock the prompt workflow service
    fake_prompt = SimpleNamespace(
        intelligence_topic_id="topic-001",
        prompt_text="Research prompt for Bitcoin ETF flows...",
        prompt_version="1",
    )
    fake_service = Mock()
    fake_service.create_draft_topic.return_value = fake_prompt
    fake_service.confirm_prompt.return_value = fake_prompt

    # Mock repository
    fake_repo = Mock()
    fake_repo.list_topic_prompts.return_value = [
        SimpleNamespace(id="prompt-001", intelligence_topic_id="topic-001")
    ]

    with patch.object(handler, "_get_topic_prompt_workflow_service", return_value=fake_service):
        with patch.object(handler, "_get_intelligence_repository", return_value=fake_repo):
            # Test /topic_create
            update = _make_update(text="/topic_create Bitcoin ETF flow analysis")
            context = SimpleNamespace(args=["Bitcoin", "ETF", "flow", "analysis"])

            asyncio.run(handler._handle_topic_create_command(update, context))

            fake_service.create_draft_topic.assert_called_once()
            args, kwargs = fake_service.create_draft_topic.call_args
            assert kwargs.get("theme") == "Bitcoin ETF flow analysis"

            reply_args = update.message.reply_text.await_args
            assert reply_args is not None
            response_text = reply_args.args[0] if reply_args.args else ""
            assert "topic-001" in response_text
            assert "/topic_revise" in response_text
            assert "/topic_confirm" in response_text

            # Test /topic_confirm
            update2 = _make_update(text="/topic_confirm topic-001")
            context2 = SimpleNamespace(args=["topic-001"])

            asyncio.run(handler._handle_topic_confirm_command(update2, context2))

            fake_service.confirm_prompt.assert_called_once()
            confirm_args, confirm_kwargs = fake_service.confirm_prompt.call_args
            assert confirm_kwargs.get("topic_id") == "topic-001"

            reply2 = update2.message.reply_text.await_args
            assert reply2 is not None
            assert "激活" in str(reply2.args[0] if reply2.args else "")


# --- Topic Detail ---

def test_topic_detail():
    """/topic_detail shows topic info, prompt, and findings."""
    handler = _make_handler()
    handler.is_authorized_user = Mock(return_value=True)
    handler._log_command_execution = Mock()
    handler._get_intelligence_repository = Mock(
        return_value=Mock(
            get_topic_by_id=Mock(
                return_value=SimpleNamespace(
                    id="topic-001",
                    name="BTC ETF",
                )
            ),
            get_active_topic_prompt=Mock(return_value=None),
            list_topic_findings=Mock(return_value=[]),
            count_topic_findings=Mock(return_value=0),
        )
    )

    update = _make_update(text="/topic_detail topic-001")
    asyncio.run(handler._handle_topic_detail_command(update, Mock()))

    reply = update.message.reply_text.await_args
    assert reply is not None
    text = reply.args[0] if reply.args else ""
    assert "BTC ETF" in text


# --- Topic Merge ---

def test_topic_merge():
    """/topic_merge creates merge preview with accept callback button."""
    handler = _make_handler()
    handler.is_authorized_user = Mock(return_value=True)
    handler._log_command_execution = Mock()
    handler._generate_callback_token = Mock(return_value="test_token")
    handler._store_callback_state = Mock()

    fake_preview = SimpleNamespace(
        id="preview-001",
        preview_payload={
            "topic_name": "BTC ETF",
            "merge_summary": "Merged 3 findings about ETF flows...",
            "merged_findings": [{"finding_id": "f1"}, {"finding_id": "f2"}],
        },
        expires_at=datetime.utcnow() + timedelta(hours=24),
    )
    repo = Mock()
    repo.get_active_topic_prompt.return_value = SimpleNamespace(id="prompt-001")

    merge_service = Mock()
    merge_service.create_merge_preview.return_value = fake_preview

    with patch.object(handler, "_get_topic_finding_merge_service", return_value=merge_service):
        with patch.object(handler, "_get_intelligence_repository", return_value=repo):
            # Test without application (text-only reply)
            handler.application = None
            update = _make_update(text="/topic_merge topic-001")
            context = SimpleNamespace(args=["topic-001"])

            asyncio.run(handler._handle_topic_merge_command(update, context))

            merge_service.create_merge_preview.assert_called_once()
            reply = update.message.reply_text.await_args
            assert reply is not None
            text = reply.args[0] if reply.args else ""
            assert "合并预览" in text or "BTC ETF" in text


# --- Topic Pause / Archive ---

def test_topic_pause_archive():
    """/topic_pause and /topic_archive change lifecycle status."""
    handler = _make_handler()
    handler.is_authorized_user = Mock(return_value=True)
    handler._log_command_execution = Mock()

    fake_topic = SimpleNamespace(id="topic-001", name="BTC ETF", lifecycle_status="active")
    repo = Mock()
    repo.get_topic_by_id.return_value = fake_topic
    repo.save_topic = Mock()
    handler._get_intelligence_repository = Mock(return_value=repo)

    # Test pause
    update = _make_update(text="/topic_pause topic-001")
    context = SimpleNamespace(args=["topic-001"])
    asyncio.run(handler._handle_topic_pause_command(update, context))

    assert fake_topic.lifecycle_status == "paused"
    repo.save_topic.assert_called_once_with(fake_topic)

    # Test archive
    update2 = _make_update(text="/topic_archive topic-001")
    context2 = SimpleNamespace(args=["topic-001"])
    asyncio.run(handler._handle_topic_archive_command(update2, context2))

    assert fake_topic.lifecycle_status == "archived"


# --- Intel commands not registered ---

def test_intel_commands_not_registered():
    """Verify no /intel_* commands are registered."""
    handler = _make_handler()
    fake_application = Mock()
    fake_application.add_handler = Mock()

    fake_builder = Mock()
    fake_builder.token.return_value = fake_builder
    fake_builder.updater.return_value = fake_builder
    fake_builder.build.return_value = fake_application

    with patch("telegram.ext.Application.builder", return_value=fake_builder):
        handler._build_application()

    registered_commands: list[str] = []
    for call in fake_application.add_handler.call_args_list:
        handler_obj = call.args[0]
        if hasattr(handler_obj, "commands"):
            registered_commands.extend(str(cmd) for cmd in handler_obj.commands)

    intel_cmds = [cmd for cmd in registered_commands if "intel_" in cmd]
    assert not intel_cmds, f"Intel commands should not be registered: {intel_cmds}"


# --- Unauthorized callback ---

def test_unauthorized_callback():
    """Topic callback queries reject unauthorized users."""
    handler = _make_handler()
    handler.is_authorized_user = Mock(return_value=False)

    update = _make_callback_update(data="topic:merge:accept:token123")
    asyncio.run(handler._handle_topic_callback_query(update, Mock()))

    update.callback_query.answer.assert_awaited_once()
    answer_args = update.callback_query.answer.await_args
    assert answer_args is not None
    assert "未授权" in str(answer_args.args[0] if answer_args.args else "")


# --- Topic revise ---

def test_topic_revise():
    """/topic_revise updates draft prompt via LLM."""
    handler = _make_handler()
    handler.is_authorized_user = Mock(return_value=True)
    handler._log_command_execution = Mock()

    fake_prompt = SimpleNamespace(
        intelligence_topic_id="topic-001",
        prompt_text="Revised prompt...",
        prompt_version="2",
    )
    fake_service = Mock()
    fake_service.revise_prompt.return_value = fake_prompt

    handler._get_topic_prompt_workflow_service = Mock(return_value=fake_service)

    update = _make_update(text="/topic_revise topic-001 add DeFi focus")
    context = SimpleNamespace(args=["topic-001", "add", "DeFi", "focus"])

    asyncio.run(handler._handle_topic_revise_command(update, context))

    fake_service.revise_prompt.assert_called_once()
    args, kwargs = fake_service.revise_prompt.call_args
    assert kwargs["topic_id"] == "topic-001"
    assert kwargs["feedback"] == "add DeFi focus"

    reply = update.message.reply_text.await_args
    assert reply is not None
    assert "后台处理" in str(reply.args[0])


# --- Topic set_prompt ---

def test_topic_set_prompt():
    """/topic_set_prompt manually replaces prompt text."""
    handler = _make_handler()
    handler.is_authorized_user = Mock(return_value=True)
    handler._log_command_execution = Mock()

    fake_prompt = SimpleNamespace(
        intelligence_topic_id="topic-001",
        prompt_text="Manual prompt text",
        prompt_version="3",
    )
    fake_service = Mock()
    fake_service.replace_prompt_manual.return_value = fake_prompt

    handler._get_topic_prompt_workflow_service = Mock(return_value=fake_service)

    update = _make_update(text="/topic_set_prompt topic-001 Manual research prompt")
    context = SimpleNamespace(args=["topic-001", "Manual", "research", "prompt"])

    asyncio.run(handler._handle_topic_set_prompt_command(update, context))

    fake_service.replace_prompt_manual.assert_called_once()
    args, kwargs = fake_service.replace_prompt_manual.call_args
    assert kwargs["topic_id"] == "topic-001"
    assert kwargs["prompt_text"] == "Manual research prompt"

    reply = update.message.reply_text.await_args
    assert reply is not None
    assert "topic-001" in str(reply.args[0])


# --- Topic list ---

def test_topic_list():
    """/topic_list shows paginated topic summary."""
    handler = _make_handler()
    handler.is_authorized_user = Mock(return_value=True)
    handler._log_command_execution = Mock()

    repo = Mock()
    repo.list_topics.return_value = [
        SimpleNamespace(
            id="topic-001",
            name="BTC ETF",
            updated_at=datetime.utcnow(),
        )
    ]
    repo.count_topics.return_value = 1
    repo.list_topic_findings.return_value = [
        SimpleNamespace(id="finding-1", content="BTC ETF approval"),
        SimpleNamespace(id="finding-2", content="ETF inflow"),
        SimpleNamespace(id="finding-3", content="ETF outflow"),
        SimpleNamespace(id="finding-4", content="GBTC discount"),
        SimpleNamespace(id="finding-5", content="ETF volume"),
    ]
    handler._get_intelligence_repository = Mock(return_value=repo)

    update = _make_update(text="/topic_list")
    context = SimpleNamespace(args=[])

    handler.application = None
    asyncio.run(handler._handle_topic_list_command(update, context))

    reply = update.message.reply_text.await_args
    assert reply is not None
    text = str(reply.args[0])
    assert "BTC ETF" in text
