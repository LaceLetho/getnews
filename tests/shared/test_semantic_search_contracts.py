from types import SimpleNamespace
from typing import Any, cast

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from crypto_news_analyzer.api_server import (
    SEMANTIC_SEARCH_JOB_RESULT_PATH,
    SEMANTIC_SEARCH_JOB_STATUS_PATH,
    SEMANTIC_SEARCH_ROUTE_PATH,
    SEMANTIC_SEARCH_TELEGRAM_COMMAND,
    SemanticSearchRequest,
    ensure_semantic_search_supported,
)
from crypto_news_analyzer.config.manager import ConfigManager
from crypto_news_analyzer.domain.models import SemanticSearchJob
from crypto_news_analyzer.models import SemanticSearchConfig, StorageConfig


def test_semantic_search_config_defaults():
    manager = ConfigManager(config_path="./nonexistent-config.jsonc")
    manager.config_data = {
        "storage": {
            "retention_days": 30,
            "max_storage_mb": 1000,
            "cleanup_frequency": "daily",
            "backend": "sqlite",
            "database_path": "./data/crypto_news.db",
            "pgvector_dimensions": 1536,
        },
        "llm_config": {
            "model": {"provider": "kimi", "name": "kimi-k2.5", "options": {}},
            "fallback_models": [
                {"provider": "grok", "name": "grok-4-1-fast-reasoning", "options": {}}
            ],
            "market_model": {
                "provider": "grok",
                "name": "grok-4-1-fast-reasoning",
                "options": {},
            },
            "temperature": 0.4,
            "max_tokens": 1000,
            "batch_size": 7,
        },
    }

    config = manager.get_semantic_search_config()

    assert config == SemanticSearchConfig(
        query_max_chars=300,
        max_subqueries=4,
        per_subquery_limit=50,
        max_retained_items=200,
        synthesis_batch_size=7,
        synthesis_item_content_max_chars=500,
        embedding_model="text-embedding-3-small",
        embedding_dimensions=1536,
        keyword_search_enabled=True,
        keyword_search_limit=30,
        max_keyword_queries=12,
        enabled=True,
    )
    assert SEMANTIC_SEARCH_ROUTE_PATH == "/semantic-search"
    assert SEMANTIC_SEARCH_JOB_STATUS_PATH == "/semantic-search/{job_id}"
    assert SEMANTIC_SEARCH_JOB_RESULT_PATH == "/semantic-search/{job_id}/result"
    assert SEMANTIC_SEARCH_TELEGRAM_COMMAND == "/semantic_search <hours> <topic>"


@pytest.mark.parametrize("value", ["", "   ", "\n\t  "])
def test_semantic_search_query_validation_rejects_blank_and_whitespace(value: str):
    with pytest.raises(ValidationError):
        _ = SemanticSearchRequest(hours=12, query=value, user_id="operator_01")

    with pytest.raises(ValueError, match="query is required"):
        _ = SemanticSearchJob.create(
            recipient_key="api:operator_01", query=value, time_window_hours=12
        )


def test_semantic_search_validation_rejects_invalid_user_id():
    with pytest.raises(ValidationError, match="user_id must match"):
        _ = SemanticSearchRequest(hours=12, query="btc etf flows", user_id="bad user")


def test_semantic_search_job_contract_uses_frozen_prefix_and_counts():
    job = SemanticSearchJob.create(
        recipient_key="api:operator_01",
        query="btc etf flows",
        normalized_intent="btc etf inflows",
        time_window_hours=24,
    )

    assert job.id.startswith("semantic_search_job_")
    assert job.query == "btc etf flows"
    assert job.normalized_intent == "btc etf inflows"
    assert job.matched_count == 0
    assert job.retained_count == 0


def test_semantic_search_runtime_explicitly_rejects_sqlite():
    manager = ConfigManager(config_path="./nonexistent-config.jsonc")
    manager.config_data = {
        "storage": {
            "retention_days": 30,
            "max_storage_mb": 1000,
            "cleanup_frequency": "daily",
            "backend": "sqlite",
            "database_path": "./data/crypto_news.db",
            "pgvector_dimensions": 1536,
        },
        "llm_config": {
            "model": {"provider": "kimi", "name": "kimi-k2.5", "options": {}},
            "fallback_models": [
                {"provider": "grok", "name": "grok-4-1-fast-reasoning", "options": {}}
            ],
            "market_model": {
                "provider": "grok",
                "name": "grok-4-1-fast-reasoning",
                "options": {},
            },
            "temperature": 0.4,
            "max_tokens": 1000,
            "batch_size": 10,
        },
    }

    with pytest.raises(ValueError, match="SQLite runtime is unsupported"):
        manager.get_semantic_search_config().ensure_supported_for_storage(StorageConfig())

    controller = cast(Any, SimpleNamespace(config_manager=manager))
    with pytest.raises(HTTPException) as exc_info:
        ensure_semantic_search_supported(controller)

    assert exc_info.value.status_code == 503
    assert "SQLite runtime is unsupported" in exc_info.value.detail
