"""Tests for static LLM registry validation."""

from typing import Any

import pytest

from crypto_news_analyzer.config.llm_registry import (
    LLMRegistryError,
    validate_llm_config_payload,
)


def build_valid_llm_config() -> dict[str, Any]:
    """Build a valid config per official provider docs.
    
    Only kimi-k2.5 supports request-level thinking_level.
    Grok models and kimi-k2-thinking-turbo do NOT support thinking_level.
    """
    return {
        "model": {
            "provider": "kimi",
            "name": "kimi-k2.5",
            "options": {"thinking_level": "disabled"},
        },
        "fallback_models": [
            {
                "provider": "grok",
                "name": "grok-4-1-fast-reasoning",
                "options": {},  # Grok models do not support thinking_level
            },
            {
                "provider": "kimi",
                "name": "kimi-k2-thinking-turbo",
                "options": {},  # Always-on thinking, no request-level control
            },
        ],
        "market_model": {
            "provider": "grok",
            "name": "grok-4-1-fast-reasoning",
            "options": {},  # Grok models do not support thinking_level
        },
        "temperature": 0.5,
        "max_tokens": 150000,
        "batch_size": 500,
        "market_prompt_path": "./prompts/market_summary_prompt.md",
        "analysis_prompt_path": "./prompts/analysis_prompt.md",
        "min_weight_score": 50,
        "cache_ttl_minutes": 240,
        "cached_messages_hours": 24,
        "enable_debug_logging": False,
    }


def test_valid_config_passes_validation():
    validated = validate_llm_config_payload(build_valid_llm_config())

    assert validated.model.provider == "kimi"
    assert validated.model.name == "kimi-k2.5"
    assert validated.market_model.name == "grok-4-1-fast-reasoning"


def test_invalid_provider_name_fails():
    config = build_valid_llm_config()
    config["model"]["provider"] = "openai"

    with pytest.raises(LLMRegistryError, match="Unsupported LLM provider"):
        validate_llm_config_payload(config)


def test_invalid_model_name_fails():
    config = build_valid_llm_config()
    config["model"]["name"] = "grok-5"

    with pytest.raises(LLMRegistryError, match="Unsupported model"):
        validate_llm_config_payload(config)


def test_legacy_alias_fails_with_migration_message():
    config = build_valid_llm_config()
    config["model"]["name"] = "kimi-for-coding"

    with pytest.raises(LLMRegistryError, match="Migrate to an explicit Kimi model"):
        validate_llm_config_payload(config)


def test_thinking_level_on_unsupported_model_fails():
    config = build_valid_llm_config()
    config["model"] = {
        "provider": "grok",
        "name": "grok-4-1-fast-non-reasoning",
        "options": {"thinking_level": "low"},
    }

    with pytest.raises(LLMRegistryError, match="does not support thinking_level"):
        validate_llm_config_payload(config)


def test_thinking_level_on_supported_model_passes():
    """Only kimi-k2.5 supports request-level thinking_level."""
    config = build_valid_llm_config()
    config["model"] = {
        "provider": "kimi",
        "name": "kimi-k2.5",
        "options": {"thinking_level": "xhigh"},
    }

    validated = validate_llm_config_payload(config)

    assert validated.model.options["thinking_level"] == "xhigh"


def test_thinking_level_on_kimi_k2_thinking_turbo_fails():
    """kimi-k2-thinking-turbo has always-on thinking, no request-level control."""
    config = build_valid_llm_config()
    config["model"] = {
        "provider": "kimi",
        "name": "kimi-k2-thinking-turbo",
        "options": {"thinking_level": "high"},
    }

    with pytest.raises(LLMRegistryError, match="does not support thinking_level"):
        validate_llm_config_payload(config)


def test_thinking_level_on_kimi_k2_turbo_preview_fails():
    """kimi-k2-turbo-preview does not support thinking at all."""
    config = build_valid_llm_config()
    config["model"] = {
        "provider": "kimi",
        "name": "kimi-k2-turbo-preview",
        "options": {"thinking_level": "low"},
    }

    with pytest.raises(LLMRegistryError, match="does not support thinking_level"):
        validate_llm_config_payload(config)


def test_unknown_option_rejected():
    config = build_valid_llm_config()
    config["model"]["options"] = {"temperature_boost": True}

    with pytest.raises(LLMRegistryError, match="unsupported keys"):
        validate_llm_config_payload(config)


def test_fallback_models_ordering_preserved():
    validated = validate_llm_config_payload(build_valid_llm_config())

    assert [model.name for model in validated.fallback_models] == [
        "grok-4-1-fast-reasoning",
        "kimi-k2-thinking-turbo",
    ]


def test_market_model_validated_independently():
    config = build_valid_llm_config()
    config["market_model"] = {
        "provider": "grok",
        "name": "not-a-real-model",
        "options": {},
    }

    with pytest.raises(LLMRegistryError, match="llm_config.market_model"):
        validate_llm_config_payload(config)


def test_opencode_go_analysis_models_validate():
    for model_name in ["glm-5.1", "kimi-k2.5", "mimo-v2-pro"]:
        config = build_valid_llm_config()
        config["model"] = {
            "provider": "opencode-go",
            "name": model_name,
            "options": {},
        }
        config["fallback_models"] = []

        validated = validate_llm_config_payload(config)

        assert validated.model.provider == "opencode-go"
        assert validated.model.name == model_name
        assert validated.model.options == {}


def test_opencode_go_market_model_rejected():
    config = build_valid_llm_config()
    config["market_model"] = {
        "provider": "opencode-go",
        "name": "kimi-k2.5",
        "options": {},
    }

    with pytest.raises(
        LLMRegistryError,
        match="llm_config.market_model.*not supported for market snapshots in phase 1",
    ):
        validate_llm_config_payload(config)


def test_opencode_go_unlisted_go_models_rejected():
    for model_name in ["glm-5", "mimo-v2-omni", "minimax-m2.5", "minimax-m2.7"]:
        config = build_valid_llm_config()
        config["model"] = {
            "provider": "opencode-go",
            "name": model_name,
            "options": {},
        }

        with pytest.raises(LLMRegistryError, match="Unsupported model"):
            validate_llm_config_payload(config)


def test_opencode_go_kimi_k2_5_rejects_thinking_level():
    config = build_valid_llm_config()
    config["model"] = {
        "provider": "opencode-go",
        "name": "kimi-k2.5",
        "options": {"thinking_level": "medium"},
    }

    with pytest.raises(LLMRegistryError, match="does not support thinking_level"):
        validate_llm_config_payload(config)
