"""Topic research parsing tests replacing legacy canonical merge tests."""

import pytest
from typing import Any, Dict

from crypto_news_analyzer.intelligence.topic_research import (
    TOPIC_RESEARCH_SCHEMA_VERSION,
    TopicResearchParser,
    TopicResearchValidationError,
)


def _payload() -> Dict[str, Any]:
    return {
        "schema_version": TOPIC_RESEARCH_SCHEMA_VERSION,
        "topic_name": "BTC ETF flow",
        "research_summary": "One relevant finding.",
        "findings": [
            {
                "finding_id": "f-1",
                "summary": "BTC ETF 净流入短时放大",
                "detail": "消息直接提到净流入放大。",
                "confidence": 0.82,
                "citations": [
                    {
                        "message_id": "raw-1",
                        "message_snippet": "BTC ETF 单小时净流入突然放大",
                        "source": "chat-1",
                        "published_at": "",
                    }
                ],
            }
        ],
        "messages_processed": 1,
        "messages_relevant": 1,
    }


def test_topic_research_parser_extracts_findings_with_citations() -> None:
    result = TopicResearchParser().parse(_payload())

    assert result.schema_version == TOPIC_RESEARCH_SCHEMA_VERSION
    assert result.findings[0].finding_id == "f-1"
    assert result.findings[0].citations[0].message_id == "raw-1"


def test_topic_research_parser_rejects_findings_without_citations() -> None:
    payload = _payload()
    payload["findings"][0]["citations"] = []

    with pytest.raises(TopicResearchValidationError):
        TopicResearchParser().parse(payload)


def test_topic_research_parser_rejects_secret_like_output() -> None:
    payload = _payload()
    payload["research_summary"] = "authorization: Bearer secret-token-123456789"

    with pytest.raises(TopicResearchValidationError):
        TopicResearchParser().parse(payload)
