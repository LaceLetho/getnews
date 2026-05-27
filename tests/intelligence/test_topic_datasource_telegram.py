"""Integration tests for Telegram /topic_sources* command handlers.

Tests topic-datasource association commands:
/topic_sources, /topic_sources_set, /topic_sources_add, /topic_sources_remove.
"""

import asyncio
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock, patch

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
    text: str = "/topic_sources topic-001",
) -> SimpleNamespace:
    from unittest.mock import AsyncMock

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


def _make_datasource(
    ds_id: str = "ds-001",
    source_type: str = "telegram_group",
    name: str = "Test Group",
    tags: list = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=ds_id,
        source_type=source_type,
        name=name,
        tags=tags or ["intel", "alpha"],
    )


# --- /topic_sources (view) ---


def test_topic_sources_no_args_shows_usage():
    handler = _make_handler()
    handler.is_authorized_user = Mock(return_value=True)
    handler.check_rate_limit = Mock(return_value=(True, None))
    handler._log_command_execution = Mock()

    update = _make_update(text="/topic_sources")
    context = SimpleNamespace(args=[])

    asyncio.run(handler._handle_topic_sources_command(update, context))

    reply = update.message.reply_text.await_args.args[0]
    assert "用法" in reply
    assert "topic_id" in reply


def test_topic_sources_topic_not_found():
    handler = _make_handler()
    handler.is_authorized_user = Mock(return_value=True)
    handler.check_rate_limit = Mock(return_value=(True, None))
    handler._log_command_execution = Mock()

    repo = Mock()
    repo.get_topic_datasources.side_effect = ValueError("topic does not exist")
    handler._get_intelligence_repository = Mock(return_value=repo)

    update = _make_update(text="/topic_sources topic-unknown")
    context = SimpleNamespace(args=["topic-unknown"])

    asyncio.run(handler._handle_topic_sources_command(update, context))

    reply = update.message.reply_text.await_args.args[0]
    assert "topic-unknown" in reply
    assert "未找到" in reply


def test_topic_sources_empty_warns_skip_research():
    handler = _make_handler()
    handler.is_authorized_user = Mock(return_value=True)
    handler.check_rate_limit = Mock(return_value=(True, None))
    handler._log_command_execution = Mock()

    repo = Mock()
    repo.get_topic_datasources.return_value = []
    handler._get_intelligence_repository = Mock(return_value=repo)

    update = _make_update(text="/topic_sources topic-001")
    context = SimpleNamespace(args=["topic-001"])

    asyncio.run(handler._handle_topic_sources_command(update, context))

    reply = update.message.reply_text.await_args.args[0]
    assert "topic-001" in reply
    assert "没有关联数据源" in reply
    assert "scheduled research will skip it" in reply


def test_topic_sources_shows_datasources():
    handler = _make_handler()
    handler.is_authorized_user = Mock(return_value=True)
    handler.check_rate_limit = Mock(return_value=(True, None))
    handler._log_command_execution = Mock()

    ds1 = _make_datasource("ds-001", "telegram_group", "Alpha Chat", ["intel", "alpha"])
    ds2 = _make_datasource("ds-002", "v2ex", "V2EX Node", ["crypto"])
    repo = Mock()
    repo.get_topic_datasources.return_value = [ds1, ds2]
    handler._get_intelligence_repository = Mock(return_value=repo)

    update = _make_update(text="/topic_sources topic-001")
    context = SimpleNamespace(args=["topic-001"])

    asyncio.run(handler._handle_topic_sources_command(update, context))

    reply = update.message.reply_text.await_args.args[0]
    assert "topic-001" in reply
    assert "ds-001" in reply
    assert "ds-002" in reply
    assert "Alpha Chat" in reply
    assert "V2EX Node" in reply
    assert "intel" in reply
    assert "crypto" in reply
    assert "2" in reply  # count


def test_topic_sources_truncates_many_tags():
    handler = _make_handler()
    handler.is_authorized_user = Mock(return_value=True)
    handler.check_rate_limit = Mock(return_value=(True, None))
    handler._log_command_execution = Mock()

    ds = _make_datasource("ds-001", "rss", "Feed", ["a", "b", "c", "d", "e"])
    repo = Mock()
    repo.get_topic_datasources.return_value = [ds]
    handler._get_intelligence_repository = Mock(return_value=repo)

    update = _make_update(text="/topic_sources topic-001")
    context = SimpleNamespace(args=["topic-001"])

    asyncio.run(handler._handle_topic_sources_command(update, context))

    reply = update.message.reply_text.await_args.args[0]
    # Should show 3 tags + "+2"
    assert "a" in reply
    assert "b" in reply
    assert "c" in reply
    assert "+2" in reply


def test_topic_sources_unauthorized():
    handler = _make_handler()
    handler.is_authorized_user = Mock(return_value=False)

    update = _make_update(text="/topic_sources topic-001")
    context = SimpleNamespace(args=["topic-001"])

    asyncio.run(handler._handle_topic_sources_command(update, context))

    reply = update.message.reply_text.await_args.args[0]
    assert "权限拒绝" in reply


# --- /topic_sources_set ---


def test_topic_sources_set_no_args_shows_usage():
    handler = _make_handler()
    handler.is_authorized_user = Mock(return_value=True)
    handler.check_rate_limit = Mock(return_value=(True, None))
    handler._log_command_execution = Mock()

    update = _make_update(text="/topic_sources_set")
    context = SimpleNamespace(args=[])

    asyncio.run(handler._handle_topic_sources_set_command(update, context))

    reply = update.message.reply_text.await_args.args[0]
    assert "用法" in reply


def test_topic_sources_set_none_clears_all():
    handler = _make_handler()
    handler.is_authorized_user = Mock(return_value=True)
    handler.check_rate_limit = Mock(return_value=(True, None))
    handler._log_command_execution = Mock()

    repo = Mock()
    repo.set_topic_datasources.return_value = None
    handler._get_intelligence_repository = Mock(return_value=repo)

    update = _make_update(text="/topic_sources_set topic-001 none")
    context = SimpleNamespace(args=["topic-001", "none"])

    asyncio.run(handler._handle_topic_sources_set_command(update, context))

    repo.set_topic_datasources.assert_called_once_with("topic-001", [])
    reply = update.message.reply_text.await_args.args[0]
    assert "已清除" in reply
    assert "topic-001" in reply
    assert "scheduled research will skip it" in reply


def test_topic_sources_set_replaces_ids():
    handler = _make_handler()
    handler.is_authorized_user = Mock(return_value=True)
    handler.check_rate_limit = Mock(return_value=(True, None))
    handler._log_command_execution = Mock()

    repo = Mock()
    repo.set_topic_datasources.return_value = None
    repo.get_topic_datasources.return_value = [
        _make_datasource("ds-xxx", "telegram_group", "Group XXX", ["intel"]),
        _make_datasource("ds-yyy", "v2ex", "V2EX YYY", ["alpha"]),
    ]
    handler._get_intelligence_repository = Mock(return_value=repo)

    update = _make_update(text="/topic_sources_set topic-001 ds-xxx ds-yyy")
    context = SimpleNamespace(args=["topic-001", "ds-xxx", "ds-yyy"])

    asyncio.run(handler._handle_topic_sources_set_command(update, context))

    repo.set_topic_datasources.assert_called_once_with("topic-001", ["ds-xxx", "ds-yyy"])
    reply = update.message.reply_text.await_args.args[0]
    assert "已设置" in reply
    assert "topic-001" in reply
    assert "ds-xxx" in reply
    assert "ds-yyy" in reply
    assert "Group XXX" in reply
    assert "V2EX YYY" in reply


def test_topic_sources_set_deduplicates_ids():
    handler = _make_handler()
    handler.is_authorized_user = Mock(return_value=True)
    handler.check_rate_limit = Mock(return_value=(True, None))
    handler._log_command_execution = Mock()

    repo = Mock()
    repo.set_topic_datasources.return_value = None
    handler._get_intelligence_repository = Mock(return_value=repo)

    update = _make_update(text="/topic_sources_set topic-001 ds-xxx ds-xxx ds-yyy")
    context = SimpleNamespace(args=["topic-001", "ds-xxx", "ds-xxx", "ds-yyy"])

    asyncio.run(handler._handle_topic_sources_set_command(update, context))

    repo.set_topic_datasources.assert_called_once_with("topic-001", ["ds-xxx", "ds-yyy"])


def test_topic_sources_set_topic_not_found():
    handler = _make_handler()
    handler.is_authorized_user = Mock(return_value=True)
    handler.check_rate_limit = Mock(return_value=(True, None))
    handler._log_command_execution = Mock()

    repo = Mock()
    repo.set_topic_datasources.side_effect = ValueError("topic does not exist")
    handler._get_intelligence_repository = Mock(return_value=repo)

    update = _make_update(text="/topic_sources_set topic-unknown ds-xxx")
    context = SimpleNamespace(args=["topic-unknown", "ds-xxx"])

    asyncio.run(handler._handle_topic_sources_set_command(update, context))

    reply = update.message.reply_text.await_args.args[0]
    assert "topic-unknown" in reply
    assert "未找到" in reply


def test_topic_sources_set_unknown_datasource():
    handler = _make_handler()
    handler.is_authorized_user = Mock(return_value=True)
    handler.check_rate_limit = Mock(return_value=(True, None))
    handler._log_command_execution = Mock()

    repo = Mock()
    repo.set_topic_datasources.side_effect = ValueError("unknown datasource: ds-bad")
    handler._get_intelligence_repository = Mock(return_value=repo)

    update = _make_update(text="/topic_sources_set topic-001 ds-bad")
    context = SimpleNamespace(args=["topic-001", "ds-bad"])

    asyncio.run(handler._handle_topic_sources_set_command(update, context))

    reply = update.message.reply_text.await_args.args[0]
    assert "数据源未找到" in reply
    assert "ds-bad" in reply


def test_topic_sources_set_non_intelligence_datasource():
    handler = _make_handler()
    handler.is_authorized_user = Mock(return_value=True)
    handler.check_rate_limit = Mock(return_value=(True, None))
    handler._log_command_execution = Mock()

    repo = Mock()
    repo.set_topic_datasources.side_effect = ValueError(
        "datasource is not intelligence-purpose: ds-news-001"
    )
    handler._get_intelligence_repository = Mock(return_value=repo)

    update = _make_update(text="/topic_sources_set topic-001 ds-news-001")
    context = SimpleNamespace(args=["topic-001", "ds-news-001"])

    asyncio.run(handler._handle_topic_sources_set_command(update, context))

    reply = update.message.reply_text.await_args.args[0]
    assert "不是情报类型" in reply
    assert "ds-news-001" in reply


# --- /topic_sources_add ---


def test_topic_sources_add_no_args_shows_usage():
    handler = _make_handler()
    handler.is_authorized_user = Mock(return_value=True)
    handler.check_rate_limit = Mock(return_value=(True, None))
    handler._log_command_execution = Mock()

    update = _make_update(text="/topic_sources_add")
    context = SimpleNamespace(args=[])

    asyncio.run(handler._handle_topic_sources_add_command(update, context))

    reply = update.message.reply_text.await_args.args[0]
    assert "用法" in reply


def test_topic_sources_add_ids():
    handler = _make_handler()
    handler.is_authorized_user = Mock(return_value=True)
    handler.check_rate_limit = Mock(return_value=(True, None))
    handler._log_command_execution = Mock()

    repo = Mock()
    repo.add_topic_datasources.return_value = None
    repo.get_topic_datasources.return_value = [
        _make_datasource("ds-xxx", "telegram_group", "Group XXX", ["intel"]),
        _make_datasource("ds-yyy", "v2ex", "V2EX YYY", ["alpha"]),
    ]
    handler._get_intelligence_repository = Mock(return_value=repo)

    update = _make_update(text="/topic_sources_add topic-001 ds-xxx ds-yyy")
    context = SimpleNamespace(args=["topic-001", "ds-xxx", "ds-yyy"])

    asyncio.run(handler._handle_topic_sources_add_command(update, context))

    repo.add_topic_datasources.assert_called_once_with("topic-001", ["ds-xxx", "ds-yyy"])
    reply = update.message.reply_text.await_args.args[0]
    assert "已关联" in reply
    assert "topic-001" in reply
    assert "ds-xxx" in reply
    assert "ds-yyy" in reply
    assert "Group XXX" in reply
    assert "V2EX YYY" in reply


def test_topic_sources_add_topic_not_found():
    handler = _make_handler()
    handler.is_authorized_user = Mock(return_value=True)
    handler.check_rate_limit = Mock(return_value=(True, None))
    handler._log_command_execution = Mock()

    repo = Mock()
    repo.add_topic_datasources.side_effect = ValueError("topic does not exist")
    handler._get_intelligence_repository = Mock(return_value=repo)

    update = _make_update(text="/topic_sources_add topic-unknown ds-xxx")
    context = SimpleNamespace(args=["topic-unknown", "ds-xxx"])

    asyncio.run(handler._handle_topic_sources_add_command(update, context))

    reply = update.message.reply_text.await_args.args[0]
    assert "topic-unknown" in reply
    assert "未找到" in reply


def test_topic_sources_add_unknown_datasource():
    handler = _make_handler()
    handler.is_authorized_user = Mock(return_value=True)
    handler.check_rate_limit = Mock(return_value=(True, None))
    handler._log_command_execution = Mock()

    repo = Mock()
    repo.add_topic_datasources.side_effect = ValueError("unknown datasource: ds-bad")
    handler._get_intelligence_repository = Mock(return_value=repo)

    update = _make_update(text="/topic_sources_add topic-001 ds-bad")
    context = SimpleNamespace(args=["topic-001", "ds-bad"])

    asyncio.run(handler._handle_topic_sources_add_command(update, context))

    reply = update.message.reply_text.await_args.args[0]
    assert "数据源未找到" in reply
    assert "ds-bad" in reply


def test_topic_sources_add_non_intelligence_datasource():
    handler = _make_handler()
    handler.is_authorized_user = Mock(return_value=True)
    handler.check_rate_limit = Mock(return_value=(True, None))
    handler._log_command_execution = Mock()

    repo = Mock()
    repo.add_topic_datasources.side_effect = ValueError(
        "datasource is not intelligence-purpose: ds-news-001"
    )
    handler._get_intelligence_repository = Mock(return_value=repo)

    update = _make_update(text="/topic_sources_add topic-001 ds-news-001")
    context = SimpleNamespace(args=["topic-001", "ds-news-001"])

    asyncio.run(handler._handle_topic_sources_add_command(update, context))

    reply = update.message.reply_text.await_args.args[0]
    assert "不是情报类型" in reply
    assert "ds-news-001" in reply


# --- /topic_sources_remove ---


def test_topic_sources_remove_no_args_shows_usage():
    handler = _make_handler()
    handler.is_authorized_user = Mock(return_value=True)
    handler.check_rate_limit = Mock(return_value=(True, None))
    handler._log_command_execution = Mock()

    update = _make_update(text="/topic_sources_remove")
    context = SimpleNamespace(args=[])

    asyncio.run(handler._handle_topic_sources_remove_command(update, context))

    reply = update.message.reply_text.await_args.args[0]
    assert "用法" in reply


def test_topic_sources_remove_ids():
    handler = _make_handler()
    handler.is_authorized_user = Mock(return_value=True)
    handler.check_rate_limit = Mock(return_value=(True, None))
    handler._log_command_execution = Mock()

    repo = Mock()
    repo.remove_topic_datasources.return_value = None
    repo.get_topic_datasources.return_value = [
        _make_datasource("ds-xxx", "telegram_group", "Group XXX", ["intel"]),
        _make_datasource("ds-yyy", "v2ex", "V2EX YYY", ["alpha"]),
    ]
    handler._get_intelligence_repository = Mock(return_value=repo)

    update = _make_update(text="/topic_sources_remove topic-001 ds-xxx ds-yyy")
    context = SimpleNamespace(args=["topic-001", "ds-xxx", "ds-yyy"])

    asyncio.run(handler._handle_topic_sources_remove_command(update, context))

    repo.remove_topic_datasources.assert_called_once_with(
        "topic-001", ["ds-xxx", "ds-yyy"]
    )
    reply = update.message.reply_text.await_args.args[0]
    assert "已从" in reply
    assert "topic-001" in reply
    assert "ds-xxx" in reply
    assert "ds-yyy" in reply
    assert "Group XXX" in reply
    assert "V2EX YYY" in reply


def test_topic_sources_remove_topic_not_found():
    handler = _make_handler()
    handler.is_authorized_user = Mock(return_value=True)
    handler.check_rate_limit = Mock(return_value=(True, None))
    handler._log_command_execution = Mock()

    repo = Mock()
    repo.remove_topic_datasources.side_effect = ValueError("topic does not exist")
    handler._get_intelligence_repository = Mock(return_value=repo)

    update = _make_update(text="/topic_sources_remove topic-unknown ds-xxx")
    context = SimpleNamespace(args=["topic-unknown", "ds-xxx"])

    asyncio.run(handler._handle_topic_sources_remove_command(update, context))

    reply = update.message.reply_text.await_args.args[0]
    assert "topic-unknown" in reply
    assert "未找到" in reply


# --- Rate limit / auth ---


def test_topic_sources_set_unauthorized():
    handler = _make_handler()
    handler.is_authorized_user = Mock(return_value=False)

    update = _make_update(text="/topic_sources_set topic-001 ds-xxx")
    context = SimpleNamespace(args=["topic-001", "ds-xxx"])

    asyncio.run(handler._handle_topic_sources_set_command(update, context))

    reply = update.message.reply_text.await_args.args[0]
    assert "权限拒绝" in reply


def test_topic_sources_set_rate_limited():
    handler = _make_handler()
    handler.is_authorized_user = Mock(return_value=True)
    handler.check_rate_limit = Mock(return_value=(False, "Too many requests"))

    update = _make_update(text="/topic_sources_set topic-001 ds-xxx")
    context = SimpleNamespace(args=["topic-001", "ds-xxx"])

    asyncio.run(handler._handle_topic_sources_set_command(update, context))

    reply = update.message.reply_text.await_args.args[0]
    assert "速率限制" in reply


# --- Help text ---


def test_help_includes_topic_sources_commands():
    handler = _make_handler()
    handler._authorized_users = {}
    handler._log_command_execution = Mock()

    help_text = handler.handle_help_command("123")

    assert "/topic_sources" in help_text
    assert "/topic_sources_set" in help_text
    assert "/topic_sources_add" in help_text
    assert "/topic_sources_remove" in help_text
