from __future__ import annotations

from typing import Any

from crypto_news_analyzer.config.manager import ConfigManager


def _build_base_config() -> dict[str, Any]:
    return {
        "storage": {
            "retention_days": 30,
            "max_storage_mb": 1000,
            "cleanup_frequency": "daily",
            "backend": "postgres",
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
            "batch_size": 10,
        },
    }


def test_get_intelligence_config_parses_nested_settings(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://postgres:password@host:5432/db")

    manager = ConfigManager(config_path="./nonexistent-config.jsonc")
    manager.config_data = {
        **_build_base_config(),
        "intelligence_collection": {
            "extraction": {
                "provider": "opencode-go",
                "model": "kimi-k2.5",
                "temperature": 0.5,
                "max_tokens": 4000,
            },
            "collection": {
                "interval_minutes": 60,
                "ttl_days": 30,
                "backfill_hours": 24,
                "confidence_threshold": 0.6,
            },
            "sources": {"telegram_groups": ["@cryptoalpha"], "v2ex": {"node_allowlist": []}},
        },
    }

    config = manager.get_intelligence_config()

    assert config.extraction.provider == "opencode-go"
    assert config.extraction.model_name == "kimi-k2.5"
    assert config.extraction.temperature == 0.5
    assert config.extraction.max_tokens == 4000
    assert config.collection.interval_minutes == 60
    assert config.collection.ttl_days == 30
    assert config.collection.backfill_hours == 24
    assert config.collection.confidence_threshold == 0.6
    assert config.sources == {"telegram_groups": ["@cryptoalpha"], "v2ex": {"node_allowlist": []}}


def test_validate_config_rejects_non_opencode_go_intelligence_provider(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://postgres:password@host:5432/db")

    manager = ConfigManager(config_path="./nonexistent-config.jsonc")
    manager.config_data = {
        **_build_base_config(),
        "intelligence_collection": {
            "extraction": {
                "provider": "grok",
                "model": "grok-4-1-fast-reasoning",
                "temperature": 0.5,
                "max_tokens": 4000,
            },
            "collection": {
                "interval_minutes": 60,
                "ttl_days": 30,
                "backfill_hours": 24,
                "confidence_threshold": 0.6,
            },
        },
    }

    assert manager.validate_config(manager.config_data) is False
