from __future__ import annotations

from typing import Any

import pytest

from crypto_news_analyzer.datasource_payloads import (
    DataSourcePayloadValidationError,
    validate_datasource_create_payload,
)


def test_telegram_group_datasource_payload_validates_chat_target_and_normalizes():
    payload = validate_datasource_create_payload(
        {
            "source_type": "telegram_group",
            "name": "Crypto Alpha",
            "config_payload": {
                "name": "Crypto Alpha",
                "chat_id": -1001234567890,
            },
        }
    )

    assert payload.source_type == "telegram_group"
    assert payload.config_payload == {"name": "Crypto Alpha", "chat_id": -1001234567890}


@pytest.mark.parametrize(
    "config_payload, message",
    [
        (
            {"name": "Crypto Alpha"},
            "telegram_group requires chat_id or chat_username",
        ),
        (
            {
                "name": "Crypto Alpha",
                "chat_username": "@cryptoalpha",
                "api_id": 12345,
            },
            "secret field",
        ),
    ],
)
def test_telegram_group_datasource_payload_rejects_missing_target_and_secret_fields(
    config_payload: dict[str, Any],
    message: str,
):
    with pytest.raises(DataSourcePayloadValidationError, match=message):
        validate_datasource_create_payload(
            {
                "source_type": "telegram_group",
                "name": "Crypto Alpha",
                "config_payload": config_payload,
            }
        )


def test_v2ex_datasource_payload_validates_api_version_and_node_allowlist():
    payload = validate_datasource_create_payload(
        {
            "source_type": "v2ex",
            "name": "V2EX Crypto",
            "config_payload": {
                "name": "V2EX Crypto",
                "api_version": "v2",
                "node_allowlist": [],
                "pat_env_var_name": "V2EX_PAT",
            },
        }
    )

    assert payload.source_type == "v2ex"
    assert payload.config_payload == {
        "name": "V2EX Crypto",
        "api_version": "v2",
        "node_allowlist": [],
        "pat_env_var_name": "V2EX_PAT",
    }


@pytest.mark.parametrize(
    "config_payload, message",
    [
        (
            {
                "name": "V2EX Crypto",
                "crawler_mode": "html",
                "node_allowlist": [],
            },
            "cannot be html",
        ),
        (
            {
                "name": "V2EX Crypto",
                "node_allowlist": [],
                "css_selector": ".topic-list",
            },
            "HTML scraping or CSS selector",
        ),
    ],
)
def test_v2ex_datasource_payload_rejects_html_scraping_fields(
    config_payload: dict[str, Any],
    message: str,
):
    with pytest.raises(DataSourcePayloadValidationError, match=message):
        validate_datasource_create_payload(
            {
                "source_type": "v2ex",
                "name": "V2EX Crypto",
                "config_payload": config_payload,
            }
        )
