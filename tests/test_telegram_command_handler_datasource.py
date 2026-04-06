import pytest
from typing import Any, Optional, Sequence
from unittest.mock import AsyncMock, Mock, patch

from telegram import Chat, Message, Update, User
from telegram.ext import ContextTypes

from crypto_news_analyzer.datasource_payloads import (
    parse_telegram_datasource_command_json,
    validate_telegram_datasource_create_payload,
)
from crypto_news_analyzer.domain.models import (
    DataSource,
    DataSourceAlreadyExistsError,
    DataSourceInUseError,
)
from crypto_news_analyzer.models import TelegramCommandConfig
from crypto_news_analyzer.reporters.telegram_command_handler import TelegramCommandHandler


def test_telegram_datasource_command_requires_single_json_after_command_syntax():
    with pytest.raises(ValueError, match="请输入 /datasource_add 后紧跟单个 JSON 对象"):
        parse_telegram_datasource_command_json("/datasource_add", "/datasource_add")

    with pytest.raises(ValueError, match="请输入有效的 JSON 对象"):
        parse_telegram_datasource_command_json(
            "/datasource_add name=CoinDesk",
            "/datasource_add",
        )


def test_telegram_datasource_command_secret_rejection_blocks_rest_api_authorization_header():
    with pytest.raises(ValueError, match="rest_api.headers"):
        validate_telegram_datasource_create_payload(
            parse_telegram_datasource_command_json(
                '/datasource_add {"source_type":"rest_api","config_payload":{"name":"Newswire API","endpoint":"https://api.example.com/news","method":"GET","headers":{"Authorization":"Bearer super-secret"},"response_mapping":{"title_field":"title","content_field":"body","url_field":"url","time_field":"published_at"}}}',
                "/datasource_add",
            )
        )


def test_telegram_datasource_command_secret_rejection_blocks_rest_api_inline_auth_block():
    with pytest.raises(ValueError, match="内联提交认证信息"):
        validate_telegram_datasource_create_payload(
            parse_telegram_datasource_command_json(
                '/datasource_add {"source_type":"rest_api","config_payload":{"name":"Newswire API","endpoint":"https://api.example.com/news","method":"POST","auth":{"type":"bearer","token":"super-secret"},"response_mapping":{"title_field":"title","content_field":"body","url_field":"url","time_field":"published_at"}}}',
                "/datasource_add",
            )
        )


def test_telegram_datasource_command_secret_rejection_blocks_rest_api_sensitive_params():
    with pytest.raises(ValueError, match="rest_api.params"):
        validate_telegram_datasource_create_payload(
            parse_telegram_datasource_command_json(
                '/datasource_add {"source_type":"rest_api","config_payload":{"name":"Newswire API","endpoint":"https://api.example.com/news","method":"GET","params":{"api_key":"super-secret"},"response_mapping":{"title_field":"title","content_field":"body","url_field":"url","time_field":"published_at"}}}',
                "/datasource_add",
            )
        )


def test_telegram_datasource_command_secret_rejection_blocks_secret_bearer_value_under_generic_header_key():
    with pytest.raises(ValueError, match="rest_api.headers"):
        validate_telegram_datasource_create_payload(
            parse_telegram_datasource_command_json(
                '/datasource_add {"source_type":"rest_api","config_payload":{"name":"Newswire API","endpoint":"https://api.example.com/news","method":"GET","headers":{"X-Upstream":"Bearer super-secret"},"response_mapping":{"title_field":"title","content_field":"body","url_field":"url","time_field":"published_at"}}}',
                "/datasource_add",
            )
        )


class _DataSourceRepositoryStub:
    def __init__(
        self,
        datasources: Sequence[DataSource],
        delete_error: Optional[Exception] = None,
        save_error: Optional[Exception] = None,
    ):
        self._datasources = list(datasources)
        self.delete_calls: list[str] = []
        self.save_calls: list[DataSource] = []
        self._delete_error = delete_error
        self._save_error = save_error

    def list(self, source_type: Optional[str] = None) -> list[DataSource]:
        if source_type is None:
            return list(self._datasources)
        return [
            datasource for datasource in self._datasources if datasource.source_type == source_type
        ]

    def delete(self, datasource_id: str) -> bool:
        self.delete_calls.append(datasource_id)
        if self._delete_error is not None:
            raise self._delete_error
        for index, datasource in enumerate(self._datasources):
            if datasource.id == datasource_id:
                self._datasources.pop(index)
                return True
        return False

    def save(self, datasource: DataSource) -> DataSource:
        self.save_calls.append(datasource)
        if self._save_error is not None:
            raise self._save_error
        self._datasources.append(datasource)
        return datasource


class _CoordinatorStub:
    def __init__(self, datasources: Optional[Sequence[DataSource]] = None):
        self.datasource_repository = _DataSourceRepositoryStub(datasources or [])


class _ApplicationStub:
    def __init__(self):
        self.added_handlers: list[Any] = []

    def add_handler(self, handler: Any) -> None:
        self.added_handlers.append(handler)


class _ApplicationBuilderStub:
    def __init__(self, application: _ApplicationStub):
        self._application = application

    def token(self, _bot_token: str) -> "_ApplicationBuilderStub":
        return self

    def updater(self, _updater: Any) -> "_ApplicationBuilderStub":
        return self

    def build(self) -> _ApplicationStub:
        return self._application


def _create_handler(datasources: Optional[Sequence[DataSource]] = None) -> TelegramCommandHandler:
    with patch.dict("os.environ", {"TELEGRAM_AUTHORIZED_USERS": "123456789"}):
        return TelegramCommandHandler(
            bot_token="test_token",
            execution_coordinator=_CoordinatorStub(datasources=datasources),
            config=TelegramCommandConfig(),
        )


def _create_mock_update(
    user_id: str,
    username: str,
    chat_type: str,
    chat_id: str,
    text: str = "",
) -> tuple[Update, Any]:
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
    message.text = text
    message.reply_text = AsyncMock()
    update.message = message
    return update, message


def test_datasource_registration_build_application_includes_all_datasource_commands():
    handler = _create_handler()
    application = _ApplicationStub()
    builder = _ApplicationBuilderStub(application)

    with patch(
        "crypto_news_analyzer.reporters.telegram_command_handler.Application.builder",
        return_value=builder,
    ):
        handler._build_application(use_updater=False)

    registered_commands = {
        next(iter(command_handler.commands)) for command_handler in application.added_handlers
    }

    assert {"datasource_list", "datasource_add", "datasource_delete"}.issubset(
        registered_commands
    )


@pytest.mark.asyncio
async def test_datasource_registration_setup_bot_commands_includes_datasource_menu_entries():
    handler = _create_handler()
    handler.application = Mock()
    handler.application.bot = Mock()
    handler.application.bot.set_my_commands = AsyncMock()

    await handler._setup_bot_commands()

    bot_commands = handler.application.bot.set_my_commands.call_args.args[0]
    command_map = {command.command: command.description for command in bot_commands}

    assert command_map["datasource_list"] == "查看数据源列表"
    assert command_map["datasource_add"] == "添加数据源"
    assert command_map["datasource_delete"] == "删除数据源"


@pytest.mark.asyncio
async def test_datasource_list_returns_stable_sorted_normalized_output_for_authorized_user():
    handler = _create_handler(
        datasources=[
            DataSource(
                id="ds-x-1",
                source_type="x",
                name="Whale Watch",
                tags=["Whales", "alpha", " whales "],
                config_payload={"url": "https://x.com/i/lists/1", "type": "list"},
            ),
            DataSource(
                id="ds-rss-2",
                source_type="rss",
                name="Beta Feed",
                tags=[],
                config_payload={"url": "https://example.com/beta.xml", "description": "beta"},
            ),
            DataSource(
                id="ds-rss-1",
                source_type="rss",
                name="Alpha Feed",
                tags=[" Defi ", "btc", "BTC"],
                config_payload={"url": "https://example.com/alpha.xml", "description": "alpha"},
            ),
        ]
    )
    update, message = _create_mock_update("123456789", "tester", "private", "123456789")
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)

    await handler._handle_datasource_list_command(update, context)

    message.reply_text.assert_called_once_with(
        "📚 数据源列表\n\n"
        "共 3 个数据源。\n\n"
        "1. ID: ds-rss-1\n"
        "   类型: rss\n"
        "   名称: Alpha Feed\n"
        "   标签: btc, defi\n\n"
        "2. ID: ds-rss-2\n"
        "   类型: rss\n"
        "   名称: Beta Feed\n"
        "   标签: （无标签）\n\n"
        "3. ID: ds-x-1\n"
        "   类型: x\n"
        "   名称: Whale Watch\n"
        "   标签: alpha, whales"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method_name", "command_name"),
    [
        ("_handle_datasource_list_command", "/datasource_list"),
        ("_handle_datasource_add_command", "/datasource_add"),
        ("_handle_datasource_delete_command", "/datasource_delete"),
    ],
)
async def test_datasource_unauthorized_commands_reuse_existing_denial_behavior(
    method_name: str,
    command_name: str,
) -> None:
    handler = _create_handler()
    update, message = _create_mock_update("999999999", "unauthorized", "private", "999999999")
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)

    with patch.object(handler, "_log_authorization_attempt") as mock_log_auth:
        with patch.object(handler, "_log_command_execution"):
            await getattr(handler, method_name)(update, context)

    message.reply_text.assert_called_once_with("❌ 权限拒绝\n\n您没有权限执行此命令。")
    mock_log_auth.assert_called_once_with(
        command=command_name,
        user_id="999999999",
        username="unauthorized",
        chat_type="private",
        chat_id="999999999",
        authorized=False,
        reason="user not in authorized list",
    )


@pytest.mark.asyncio
async def test_datasource_delete_deletes_by_id_only_and_reports_success() -> None:
    datasource = DataSource(
        id="ds-123",
        source_type="rss",
        name="CoinDesk",
        config_payload={"name": "CoinDesk", "url": "https://example.com/rss"},
    )
    handler = _create_handler()
    repository = _DataSourceRepositoryStub([datasource])
    handler.execution_coordinator.datasource_repository = repository
    update, message = _create_mock_update("123456789", "tester", "private", "123456789")
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.args = ["ds-123"]

    await handler._handle_datasource_delete_command(update, context)

    assert repository.delete_calls == ["ds-123"]
    message.reply_text.assert_called_once_with(
        "✅ 数据源删除成功\n\n已删除数据源 ID: ds-123"
    )


@pytest.mark.asyncio
async def test_datasource_delete_rejects_missing_id_with_usage_error() -> None:
    handler = _create_handler()
    repository = _DataSourceRepositoryStub([])
    handler.execution_coordinator.datasource_repository = repository
    update, message = _create_mock_update("123456789", "tester", "private", "123456789")
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.args = []

    await handler._handle_datasource_delete_command(update, context)

    assert repository.delete_calls == []
    message.reply_text.assert_called_once_with(
        "❌ 参数错误\n\n请输入数据源ID，例如：/datasource_delete ds-123"
    )


@pytest.mark.asyncio
async def test_datasource_delete_returns_not_found_for_unknown_id() -> None:
    handler = _create_handler()
    repository = _DataSourceRepositoryStub([])
    handler.execution_coordinator.datasource_repository = repository
    update, message = _create_mock_update("123456789", "tester", "private", "123456789")
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.args = ["missing-id"]

    await handler._handle_datasource_delete_command(update, context)

    assert repository.delete_calls == ["missing-id"]
    message.reply_text.assert_called_once_with(
        "❌ 未找到数据源\n\n未找到 ID 为 missing-id 的数据源。"
    )


@pytest.mark.asyncio
async def test_datasource_delete_returns_conflict_when_active_ingestion_job_exists() -> None:
    handler = _create_handler()
    repository = _DataSourceRepositoryStub(
        [
            DataSource(
                id="ds-123",
                source_type="rss",
                name="CoinDesk",
                config_payload={"name": "CoinDesk", "url": "https://example.com/rss"},
            )
        ],
        delete_error=DataSourceInUseError(
            source_type="rss",
            source_name="CoinDesk",
            active_job_ids=["job-1", "job-2"],
        ),
    )
    handler.execution_coordinator.datasource_repository = repository
    update, message = _create_mock_update("123456789", "tester", "private", "123456789")
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.args = ["ds-123"]

    await handler._handle_datasource_delete_command(update, context)

    message.reply_text.assert_called_once_with(
        "⚠️ 删除冲突\n\n"
        "数据源 ID ds-123 当前不能删除，因为匹配的入库任务仍处于活跃状态。\n"
        "活跃任务: job-1, job-2"
    )


@pytest.mark.asyncio
async def test_datasource_add_rss_saves_valid_json_payload_and_returns_created_summary() -> None:
    handler = _create_handler()
    repository = _DataSourceRepositoryStub([])
    handler.execution_coordinator.datasource_repository = repository
    update, message = _create_mock_update(
        "123456789",
        "tester",
        "private",
        "123456789",
        text='/datasource_add {"source_type":"rss","tags":[" Markets ","btc","BTC"],"config_payload":{"name":"CoinDesk","url":"https://www.coindesk.com/arc/outboundfeeds/rss/","description":"Industry news"}}',
    )
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)

    await handler._handle_datasource_add_command(update, context)

    assert len(repository.save_calls) == 1
    saved_datasource = repository.save_calls[0]
    assert saved_datasource.source_type == "rss"
    assert saved_datasource.name == "CoinDesk"
    assert saved_datasource.tags == ["btc", "markets"]
    assert saved_datasource.config_payload == {
        "name": "CoinDesk",
        "url": "https://www.coindesk.com/arc/outboundfeeds/rss/",
        "description": "Industry news",
    }
    message.reply_text.assert_called_once_with(
        "✅ 数据源创建成功\n\n"
        f"ID: {saved_datasource.id}\n"
        "类型: rss\n"
        "名称: CoinDesk\n"
        "标签: btc, markets"
    )


@pytest.mark.asyncio
async def test_datasource_add_x_saves_valid_json_payload_and_returns_created_summary() -> None:
    handler = _create_handler()
    repository = _DataSourceRepositoryStub([])
    handler.execution_coordinator.datasource_repository = repository
    update, message = _create_mock_update(
        "123456789",
        "tester",
        "private",
        "123456789",
        text='/datasource_add {"source_type":"x","tags":[" Whales ","whales"],"config_payload":{"name":"Whale Watch","url":"https://x.com/i/lists/1234567890","type":"list"}}',
    )
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)

    await handler._handle_datasource_add_command(update, context)

    assert len(repository.save_calls) == 1
    saved_datasource = repository.save_calls[0]
    assert saved_datasource.source_type == "x"
    assert saved_datasource.name == "Whale Watch"
    assert saved_datasource.tags == ["whales"]
    assert saved_datasource.config_payload == {
        "name": "Whale Watch",
        "url": "https://x.com/i/lists/1234567890",
        "type": "list",
    }
    message.reply_text.assert_called_once_with(
        "✅ 数据源创建成功\n\n"
        f"ID: {saved_datasource.id}\n"
        "类型: x\n"
        "名称: Whale Watch\n"
        "标签: whales"
    )


@pytest.mark.asyncio
async def test_datasource_add_rss_rejects_missing_json_with_single_syntax_error() -> None:
    handler = _create_handler()
    repository = _DataSourceRepositoryStub([])
    handler.execution_coordinator.datasource_repository = repository
    update, message = _create_mock_update(
        "123456789",
        "tester",
        "private",
        "123456789",
        text="/datasource_add",
    )
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)

    await handler._handle_datasource_add_command(update, context)

    assert repository.save_calls == []
    message.reply_text.assert_called_once_with(
        "❌ 参数错误\n\n请输入 /datasource_add 后紧跟单个 JSON 对象。"
    )


@pytest.mark.asyncio
async def test_datasource_add_x_rejects_malformed_json_payload() -> None:
    handler = _create_handler()
    repository = _DataSourceRepositoryStub([])
    handler.execution_coordinator.datasource_repository = repository
    update, message = _create_mock_update(
        "123456789",
        "tester",
        "private",
        "123456789",
        text="/datasource_add name=CoinDesk",
    )
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)

    await handler._handle_datasource_add_command(update, context)

    assert repository.save_calls == []
    message.reply_text.assert_called_once()
    assert "请输入有效的 JSON 对象" in message.reply_text.call_args.args[0]


@pytest.mark.asyncio
async def test_datasource_add_rss_rejects_duplicate_datasource_save_conflict() -> None:
    handler = _create_handler()
    repository = _DataSourceRepositoryStub(
        [],
        save_error=DataSourceAlreadyExistsError("rss", "CoinDesk"),
    )
    handler.execution_coordinator.datasource_repository = repository
    update, message = _create_mock_update(
        "123456789",
        "tester",
        "private",
        "123456789",
        text='/datasource_add {"source_type":"rss","config_payload":{"name":"CoinDesk","url":"https://www.coindesk.com/arc/outboundfeeds/rss/","description":"Industry news"}}',
    )
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)

    await handler._handle_datasource_add_command(update, context)

    assert len(repository.save_calls) == 1
    message.reply_text.assert_called_once_with(
        "⚠️ 数据源已存在\n\n数据源 'rss:CoinDesk' 已存在，不能重复创建。"
    )


@pytest.mark.asyncio
async def test_datasource_add_rss_rejects_duplicate_datasource_save_conflict_legacy_value_error() -> None:
    handler = _create_handler()
    repository = _DataSourceRepositoryStub(
        [],
        save_error=ValueError("datasource uniqueness violation"),
    )
    handler.execution_coordinator.datasource_repository = repository
    update, message = _create_mock_update(
        "123456789",
        "tester",
        "private",
        "123456789",
        text='/datasource_add {"source_type":"rss","config_payload":{"name":"CoinDesk","url":"https://www.coindesk.com/arc/outboundfeeds/rss/","description":"Industry news"}}',
    )
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)

    await handler._handle_datasource_add_command(update, context)

    assert len(repository.save_calls) == 1
    message.reply_text.assert_called_once_with(
        "⚠️ 数据源已存在\n\n数据源 'rss:CoinDesk' 已存在，不能重复创建。"
    )


@pytest.mark.asyncio
async def test_datasource_add_x_rejects_invalid_payload_with_explicit_validation_error() -> None:
    handler = _create_handler()
    repository = _DataSourceRepositoryStub([])
    handler.execution_coordinator.datasource_repository = repository
    update, message = _create_mock_update(
        "123456789",
        "tester",
        "private",
        "123456789",
        text='/datasource_add {"source_type":"x","config_payload":{"name":"Whale Watch","url":"https://x.com/i/lists/1234567890","type":"search"}}',
    )
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)

    await handler._handle_datasource_add_command(update, context)

    assert repository.save_calls == []
    message.reply_text.assert_called_once_with(
        "x.type must be one of: list, timeline"
    )


@pytest.mark.asyncio
async def test_datasource_add_rest_api_saves_valid_json_payload_and_returns_created_summary() -> None:
    handler = _create_handler()
    repository = _DataSourceRepositoryStub([])
    handler.execution_coordinator.datasource_repository = repository
    update, message = _create_mock_update(
        "123456789",
        "tester",
        "private",
        "123456789",
        text='/datasource_add {"source_type":"rest_api","tags":[" news ","api"],"config_payload":{"name":"Newswire API","endpoint":"https://api.example.com/news","method":"GET","headers":{},"params":{},"response_mapping":{"title_field":"title","content_field":"body","url_field":"url","time_field":"published_at"}}}',
    )
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)

    await handler._handle_datasource_add_command(update, context)

    assert len(repository.save_calls) == 1
    saved_datasource = repository.save_calls[0]
    assert saved_datasource.source_type == "rest_api"
    assert saved_datasource.name == "Newswire API"
    assert saved_datasource.tags == ["api", "news"]
    assert saved_datasource.config_payload == {
        "name": "Newswire API",
        "endpoint": "https://api.example.com/news",
        "method": "GET",
        "headers": {},
        "params": {},
        "response_mapping": {
            "title_field": "title",
            "content_field": "body",
            "url_field": "url",
            "time_field": "published_at",
        },
    }
    message.reply_text.assert_called_once_with(
        "✅ 数据源创建成功\n\n"
        f"ID: {saved_datasource.id}\n"
        "类型: rest_api\n"
        "名称: Newswire API\n"
        "标签: api, news"
    )


@pytest.mark.asyncio
async def test_datasource_add_rest_api_rejects_authorization_header() -> None:
    handler = _create_handler()
    repository = _DataSourceRepositoryStub([])
    handler.execution_coordinator.datasource_repository = repository
    update, message = _create_mock_update(
        "123456789",
        "tester",
        "private",
        "123456789",
        text='/datasource_add {"source_type":"rest_api","config_payload":{"name":"Newswire API","endpoint":"https://api.example.com/news","method":"GET","headers":{"Authorization":"Bearer super-secret"},"params":{},"response_mapping":{"title_field":"title","content_field":"body","url_field":"url","time_field":"published_at"}}}',
    )
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)

    await handler._handle_datasource_add_command(update, context)

    assert repository.save_calls == []
    message.reply_text.assert_called_once()
    assert "rest_api.headers" in message.reply_text.call_args.args[0]


@pytest.mark.asyncio
async def test_datasource_add_rest_api_rejects_api_key_in_params() -> None:
    handler = _create_handler()
    repository = _DataSourceRepositoryStub([])
    handler.execution_coordinator.datasource_repository = repository
    update, message = _create_mock_update(
        "123456789",
        "tester",
        "private",
        "123456789",
        text='/datasource_add {"source_type":"rest_api","config_payload":{"name":"Newswire API","endpoint":"https://api.example.com/news","method":"GET","headers":{},"params":{"api_key":"super-secret"},"response_mapping":{"title_field":"title","content_field":"body","url_field":"url","time_field":"published_at"}}}',
    )
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)

    await handler._handle_datasource_add_command(update, context)

    assert repository.save_calls == []
    message.reply_text.assert_called_once()
    assert "rest_api.params" in message.reply_text.call_args.args[0]


@pytest.mark.asyncio
async def test_datasource_add_rest_api_rejects_inline_auth_block() -> None:
    handler = _create_handler()
    repository = _DataSourceRepositoryStub([])
    handler.execution_coordinator.datasource_repository = repository
    update, message = _create_mock_update(
        "123456789",
        "tester",
        "private",
        "123456789",
        text='/datasource_add {"source_type":"rest_api","config_payload":{"name":"Newswire API","endpoint":"https://api.example.com/news","method":"POST","auth":{"type":"bearer","token":"super-secret"},"response_mapping":{"title_field":"title","content_field":"body","url_field":"url","time_field":"published_at"}}}',
    )
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)

    await handler._handle_datasource_add_command(update, context)

    assert repository.save_calls == []
    message.reply_text.assert_called_once()
    assert "内联提交认证信息" in message.reply_text.call_args.args[0]


@pytest.mark.asyncio
async def test_datasource_add_rejects_tags_over_shared_limit() -> None:
    handler = _create_handler()
    repository = _DataSourceRepositoryStub([])
    handler.execution_coordinator.datasource_repository = repository
    update, message = _create_mock_update(
        "123456789",
        "tester",
        "private",
        "123456789",
        text='/datasource_add {"source_type":"rss","tags":["tag-0","tag-1","tag-2","tag-3","tag-4","tag-5","tag-6","tag-7","tag-8","tag-9","tag-10","tag-11","tag-12","tag-13","tag-14","tag-15","tag-16"],"config_payload":{"name":"CoinDesk","url":"https://www.coindesk.com/arc/outboundfeeds/rss/","description":"Industry news"}}',
    )
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)

    await handler._handle_datasource_add_command(update, context)

    assert repository.save_calls == []
    message.reply_text.assert_called_once_with(
        "tags cannot contain more than 16 unique values"
    )


@pytest.mark.asyncio
async def test_datasource_telegram_created_rest_api_visible_in_telegram_list_and_rest_get() -> None:
    handler = _create_handler()
    repository = _DataSourceRepositoryStub([])
    handler.execution_coordinator.datasource_repository = repository

    create_update, create_message = _create_mock_update(
        "123456789",
        "tester",
        "private",
        "123456789",
        text='/datasource_add {"source_type":"rest_api","tags":["crypto","news"],"config_payload":{"name":"Crypto News API","endpoint":"https://api.crypto.com/news","method":"GET","headers":{},"params":{},"response_mapping":{"title_field":"title","content_field":"body","url_field":"url","time_field":"published_at"}}}',
    )
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)

    await handler._handle_datasource_add_command(create_update, context)

    assert len(repository.save_calls) == 1
    saved_datasource = repository.save_calls[0]
    assert saved_datasource.source_type == "rest_api"
    assert saved_datasource.name == "Crypto News API"
    create_message.reply_text.assert_called_once_with(
        "✅ 数据源创建成功\n\n"
        f"ID: {saved_datasource.id}\n"
        "类型: rest_api\n"
        "名称: Crypto News API\n"
        "标签: crypto, news"
    )

    list_update, list_message = _create_mock_update("123456789", "tester", "private", "123456789")
    await handler._handle_datasource_list_command(list_update, context)

    list_message.reply_text.assert_called_once()
    list_response = list_message.reply_text.call_args.args[0]
    assert saved_datasource.id in list_response
    assert "rest_api" in list_response
    assert "Crypto News API" in list_response
    assert "crypto, news" in list_response

    rest_list = repository.list()
    assert len(rest_list) == 1
    rest_datasource = rest_list[0]
    assert rest_datasource.id == saved_datasource.id
    assert rest_datasource.source_type == "rest_api"
    assert rest_datasource.name == "Crypto News API"
    assert rest_datasource.tags == ["crypto", "news"]


@pytest.mark.asyncio
async def test_datasource_setup_bot_commands_does_not_show_development_suffix() -> None:
    handler = _create_handler()
    handler.application = Mock()
    handler.application.bot = Mock()
    handler.application.bot.set_my_commands = AsyncMock()

    await handler._setup_bot_commands()

    bot_commands = handler.application.bot.set_my_commands.call_args.args[0]
    command_map = {command.command: command.description for command in bot_commands}

    assert command_map["datasource_add"] == "添加数据源"
    assert command_map["datasource_delete"] == "删除数据源"
    assert "开发中" not in command_map["datasource_add"]
    assert "开发中" not in command_map["datasource_delete"]
