"""Cross-cutting security guardrails for intelligence query surfaces (topic-only)."""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Optional, cast
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import FastAPI
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from crypto_news_analyzer import api_server
from crypto_news_analyzer.datasource_payloads import (
    DataSourcePayloadValidationError,
    validate_datasource_create_payload,
)
from crypto_news_analyzer.domain import models as domain_models
from crypto_news_analyzer.domain import repositories as domain_repositories
from crypto_news_analyzer.domain.models import DataSource
from crypto_news_analyzer.reporters.telegram_command_handler import TelegramCommandHandler
from crypto_news_analyzer.storage import repositories as storage_repositories
from crypto_news_analyzer.models import StorageConfig, TelegramCommandConfig

REPO_ROOT = Path(__file__).resolve().parents[1]
SECRET_SENTINELS = (
    "StringSession_SENTINEL_do_not_leak",
    "V2EX_PAT_SENTINEL_do_not_leak",
    "API_KEY_SENTINEL_do_not_leak",
    "PASSWORD_SENTINEL_do_not_leak",
    "TOKEN_SENTINEL_do_not_leak",
)


class _FakeIntelligenceRepository:
    def list_topic_prompts(self, *_args: Any, **_kwargs: Any) -> list[Any]:
        return []

    def list_topic_run_logs(self, *_args: Any, **_kwargs: Any) -> list[Any]:
        return []

    def list_canonical_entries(self, *_args: Any, **_kwargs: Any) -> list[Any]:
        return []

    def count_canonical_entries(self, *_args: Any, **_kwargs: Any) -> int:
        return 0

    def get_canonical_entry_by_id(self, _entry_id: str) -> None:
        return None


class _FakeDatasourceRepository:
    def __init__(self, datasources: list[Any]) -> None:
        self.datasources = datasources

    def list(self) -> list[Any]:
        return list(self.datasources)

    def save(self, datasource: DataSource) -> DataSource:
        self.datasources.append(datasource)
        return datasource

    def delete(self, _datasource_id: str) -> bool:
        return False


class _FakeController:
    def __init__(
        self,
        *,
        intelligence_repository: Optional[_FakeIntelligenceRepository] = None,
        datasource_repository: Optional[_FakeDatasourceRepository] = None,
    ) -> None:
        self.intelligence_repository = intelligence_repository or _FakeIntelligenceRepository()
        self.datasource_repository = datasource_repository
        self.analysis_repository = None
        self.semantic_search_repository = None
        self.command_handler = None
        self.data_manager = None
        self.embedding_service = SimpleNamespace(generate_embedding=lambda _text: [0.1] * 8)
        self.storage_config = StorageConfig(backend="sqlite", database_path=":memory:")
        self.config_manager = SimpleNamespace(
            get_storage_config=lambda: self.storage_config,
            get_auth_config=lambda: SimpleNamespace(
                GROK_API_KEY="",
                KIMI_API_KEY="",
                OPENCODE_API_KEY="",
            ),
            config_data={},
        )

    def initialize_system(self) -> bool:
        return True

    def start_scheduler(self) -> None:
        return None

    def stop_scheduler(self) -> None:
        return None

    def start_command_listener(self) -> None:
        return None

    def stop_command_listener(self) -> None:
        return None


def _build_client(monkeypatch: pytest.MonkeyPatch, controller: _FakeController) -> TestClient:
    monkeypatch.setattr(api_server, "MainController", lambda *_args, **_kwargs: controller)
    app = api_server.create_api_server(
        "./config.jsonc",
        start_services=False,
        start_scheduler=False,
        start_command_listener=False,
    )
    return TestClient(app)


def _authorized_headers() -> dict[str, str]:
    return {"Authorization": "Bearer test-api-key"}


def _make_handler(coordinator: Any = None) -> TelegramCommandHandler:
    return TelegramCommandHandler(
        bot_token="telegram-token",
        execution_coordinator=coordinator or SimpleNamespace(),
        config=TelegramCommandConfig(enabled=True),
    )


def _make_update() -> SimpleNamespace:
    message = SimpleNamespace(reply_text=AsyncMock())
    return SimpleNamespace(
        effective_user=SimpleNamespace(id="999", username="intruder", first_name="Intruder"),
        effective_chat=SimpleNamespace(id="chat-999", type="private"),
        message=message,
        effective_message=message,
    )


def _route_has_api_key_dependency(route: APIRoute) -> bool:
    return any(
        dependency.call is api_server.verify_api_key for dependency in route.dependant.dependencies
    )


@pytest.fixture(autouse=True)
def api_key_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("API_KEY", "test-api-key")


def test_all_intelligence_api_routes_require_bearer_auth(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Topic-only intelligence routes still require auth."""
    controller = _FakeController()
    with _build_client(monkeypatch, controller) as client:
        app = cast(FastAPI, client.app)
        intelligence_routes = [
            route
            for route in app.routes
            if isinstance(route, APIRoute) and route.path.startswith("/intelligence/")
        ]
        for route in intelligence_routes:
            response = client.request(route.methods.pop() if route.methods else "GET", route.path)
            assert response.status_code == 401, f"{route.path} must reject missing auth"


def test_datasource_secrets_not_exposed(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO)

    with pytest.raises(DataSourcePayloadValidationError):
        validate_datasource_create_payload(
            {
                "purpose": "intelligence",
                "source_type": "telegram_group",
                "config_payload": {
                    "name": "TG Alpha",
                    "chat_username": "@alpha",
                    "string_session": SECRET_SENTINELS[0],
                },
            }
        )
    with pytest.raises(DataSourcePayloadValidationError):
        validate_datasource_create_payload(
            {
                "source_type": "v2ex",
                "purpose": "intelligence",
                "config_payload": {
                    "name": "V2EX Alpha",
                    "api_version": "v2",
                    "node_allowlist": [],
                    "personal_access_token": SECRET_SENTINELS[1],
                },
            }
        )

    secret_datasources = [
        DataSource.create(
            name="REST API",
            source_type="rest_api",
            purpose="intelligence",
            config_payload={
                "name": "REST API",
                "endpoint": f"https://api.example.com/items?api_key={SECRET_SENTINELS[2]}",
                "method": "GET",
                "headers": {
                    "Authorization": f"Bearer {SECRET_SENTINELS[4]}",
                    "X-Password": SECRET_SENTINELS[3],
                },
                "params": {"token": SECRET_SENTINELS[4]},
                "response_mapping": {
                    "title_field": "title",
                    "content_field": "content",
                    "url_field": "url",
                    "time_field": "published_at",
                },
            },
        ),
        SimpleNamespace(
            id="telegram-leaky-row",
            name="Telegram Group",
            source_type="telegram_group",
            tags=[],
            config_payload={"string_session": SECRET_SENTINELS[0]},
        ),
        SimpleNamespace(
            id="v2ex-leaky-row",
            name="V2EX",
            source_type="v2ex",
            tags=[],
            config_payload={"pat": SECRET_SENTINELS[1]},
        ),
    ]
    controller = _FakeController(
        datasource_repository=_FakeDatasourceRepository(secret_datasources)
    )

    with _build_client(monkeypatch, controller) as client:
        response = client.get("/datasources", headers=_authorized_headers())

    assert response.status_code == 200
    serialized_response = json.dumps(response.json(), ensure_ascii=False)
    for secret in SECRET_SENTINELS:
        assert secret not in serialized_response
        assert secret not in caplog.text

    rest_summary = next(
        datasource["config_summary"]
        for datasource in response.json()["datasources"]
        if datasource["source_type"] == "rest_api"
    )
    assert rest_summary["header_count"] == 2
    assert rest_summary["param_count"] == 1
    assert "api_key" not in rest_summary["endpoint"].lower()

    handler = _make_handler(controller)
    telegram_lines = handler._format_datasource_lines(secret_datasources[0], 1)
    telegram_summary = "\n".join(telegram_lines)
    assert SECRET_SENTINELS[2] not in telegram_summary
    assert "api_key" not in telegram_summary.lower()


def test_no_intelligence_query_audit_artifacts_exist(monkeypatch: pytest.MonkeyPatch) -> None:
    modules = (domain_models, domain_repositories, storage_repositories, api_server)
    named_artifacts = []
    for module in modules:
        for name, member in inspect.getmembers(module):
            if name.startswith("__"):
                continue
            if inspect.isclass(member) or inspect.isfunction(member):
                lowered = name.lower()
                if "intelligence" in lowered and "audit" in lowered:
                    named_artifacts.append(f"{module.__name__}.{name}")

    controller = _FakeController()
    with _build_client(monkeypatch, controller) as client:
        app = cast(FastAPI, client.app)
        audit_routes = [
            route.path
            for route in app.routes
            if isinstance(route, APIRoute)
            and "intelligence" in route.path.lower()
            and "audit" in route.path.lower()
        ]

    sql_sources = (
        REPO_ROOT / "crypto_news_analyzer" / "storage" / "data_manager.py",
        REPO_ROOT / "migrations" / "postgresql" / "003_intelligence_schema.sql",
    )
    audit_table_hits = []
    for source in sql_sources:
        if not source.exists():
            continue
        for line_number, line in enumerate(source.read_text(encoding="utf-8").splitlines(), 1):
            lowered = line.lower()
            if "intelligence" in lowered and "audit" in lowered:
                audit_table_hits.append(f"{source.relative_to(REPO_ROOT)}:{line_number}: {line}")

    assert not named_artifacts
    assert not audit_routes
    assert not audit_table_hits


def test_captured_logs_do_not_contain_session_or_pat_values(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO)
    handler = _make_handler()

    handler._log_authorization_attempt(
        command="/topic_create",
        user_id="999",
        username="intruder",
        chat_type="private",
        chat_id="chat-999",
        authorized=False,
        reason="user not in authorized list",
    )
    with pytest.raises(DataSourcePayloadValidationError):
        validate_datasource_create_payload(
            {
                "purpose": "intelligence",
                "source_type": "telegram_group",
                "config_payload": {
                    "name": "TG Alpha",
                    "chat_id": -1001,
                    "session": SECRET_SENTINELS[0],
                },
            }
        )

    assert "Authorization attempt" in caplog.text
    assert SECRET_SENTINELS[0] not in caplog.text
    assert SECRET_SENTINELS[1] not in caplog.text


def test_env_template_contains_no_real_secrets() -> None:
    """Verify .env.template uses placeholder values only — no real secrets leaked."""
    import re

    env_template_path = REPO_ROOT / ".env.template"
    assert env_template_path.exists(), ".env.template missing"

    template_text = env_template_path.read_text(encoding="utf-8")

    # Keys whose values are known defaults (not secrets) — skip these
    _ALLOWED_DEFAULT_KEYS = frozenset(
        {
            "DATABASE_URL",
            "CONFIG_PATH",
            "LOG_LEVEL",
            "API_HOST",
            "API_PORT",
            "TELEGRAM_CHANNEL_ID",
            "EXECUTION_INTERVAL",
            "TIME_WINDOW_HOURS",
        }
    )

    # Scan uncommented key=value lines that don't use "your_*_here" placeholders
    # and aren't in the allowed defaults list
    violations: list[str] = []
    for line_number, raw_line in enumerate(template_text.splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, rest = line.partition("=")
        key = key.strip()
        value = rest.strip()
        if not value:
            continue
        if "your_" in value.lower():
            continue
        if key.upper() in _ALLOWED_DEFAULT_KEYS:
            continue
        # If a key contains KEY, TOKEN, SECRET, SESSION, PAT, AUTH, PASSWORD, or PASS
        # and the value isn't a placeholder, it's a potential secret leak
        secret_indicator_keys = {
            "KEY",
            "TOKEN",
            "SECRET",
            "SESSION",
            "PAT",
            "AUTH",
            "PASSWORD",
            "PASS",
        }
        if any(indicator in key.upper() for indicator in secret_indicator_keys):
            violations.append(f"  line {line_number}: {key}={value}")

    if violations:
        pytest.fail(
            f".env.template contains {len(violations)} potential secret value(s). "
            f"Use 'your_xxx_here' placeholder or #-comment out the line:\n" + "\n".join(violations)
        )

    # Check for real Telethon string session patterns (start with "1B" or "1A" and are long)
    session_pattern = re.compile(r"^\s*(?:TELEGRAM_STRING_SESSION)\s*=\s*1[A-Za-z0-9+/=_-]{20,}")
    for line_number, raw_line in enumerate(template_text.splitlines(), 1):
        if session_pattern.search(raw_line):
            pytest.fail(
                f".env.template line {line_number} appears to contain a real "
                f"Telethon string session. Replace with placeholder or comment it out."
            )

    # Check for real V2EX PAT pattern (long token string as uncommented value)
    pat_pattern = re.compile(r"^\s*V2EX_PAT\s*=\s*[A-Za-z0-9]{20,}")
    for line_number, raw_line in enumerate(template_text.splitlines(), 1):
        if pat_pattern.search(raw_line):
            pytest.fail(
                f".env.template line {line_number} appears to contain a real "
                f"V2EX PAT. Replace with placeholder or comment it out."
            )
