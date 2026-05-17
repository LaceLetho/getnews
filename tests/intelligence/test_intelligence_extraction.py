"""Topic prompt service tests replacing legacy extraction tests."""

import json
from types import SimpleNamespace
from typing import Any, Dict, List

from crypto_news_analyzer.intelligence.topic_prompts import (
    PROMPT_GENERATION_SCHEMA_VERSION,
    PROMPT_REVISION_SCHEMA_VERSION,
    TopicPromptGenerator,
    TopicPromptReviser,
)


class FakeChatCompletions:
    def __init__(self, payloads: List[Dict[str, Any]]):
        self.payloads = list(payloads)
        self.calls: List[Dict[str, Any]] = []

    def create(self, **kwargs: Any) -> SimpleNamespace:
        self.calls.append(kwargs)
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content=json.dumps(self.payloads.pop(0), ensure_ascii=False)
                    )
                )
            ]
        )


class FakeLLMClient:
    def __init__(self, payloads: List[Dict[str, Any]]):
        self.completions = FakeChatCompletions(payloads)
        self.chat = SimpleNamespace(completions=self.completions)


def test_topic_prompt_generator_returns_validated_draft() -> None:
    client = FakeLLMClient(
        [
            {
                "schema_version": PROMPT_GENERATION_SCHEMA_VERSION,
                "topic_name": "BTC ETF 资金流",
                "topic_description": "跟踪 BTC ETF 异常净流入和交易影响。",
                "research_prompt_draft": "研究 BTC ETF 资金流异常，输出 findings JSON 和 citations。",
                "suggested_time_window_hours": 24,
                "confidence": 0.91,
            }
        ]
    )

    prompt = TopicPromptGenerator(client, model_name="test-model").generate(
        "BTC ETF flow", intelligence_topic_id="topic-1", created_by="operator"
    )

    assert prompt.intelligence_topic_id == "topic-1"
    assert prompt.prompt_version == "1"
    assert prompt.schema_version == PROMPT_GENERATION_SCHEMA_VERSION
    assert "findings JSON" in prompt.prompt_text
    assert prompt.audit_history[0]["topic_name"] == "BTC ETF 资金流"
    assert client.completions.calls[0]["response_format"] == {"type": "json_object"}


def test_topic_prompt_reviser_increments_version_and_preserves_audit() -> None:
    client = FakeLLMClient(
        [
            {
                "schema_version": PROMPT_REVISION_SCHEMA_VERSION,
                "topic_name": "BTC ETF 资金流",
                "revised_prompt": "仅研究 BTC ETF 净流入突增，保留 findings citations JSON。",
                "version": 2,
                "revision_note": "缩窄到净流入突增。",
                "changes_summary": ["缩窄研究范围"],
                "confidence": 0.86,
            }
        ]
    )
    original = TopicPromptGenerator(
        FakeLLMClient(
            [
                {
                    "schema_version": PROMPT_GENERATION_SCHEMA_VERSION,
                    "topic_name": "BTC ETF 资金流",
                    "topic_description": "跟踪资金流。",
                    "research_prompt_draft": "研究 BTC ETF 资金流，输出 citations。",
                    "suggested_time_window_hours": 24,
                    "confidence": 0.8,
                }
            ]
        )
    ).generate("BTC ETF", intelligence_topic_id="topic-1")

    revised = TopicPromptReviser(client).revise(original, "只看净流入突增")

    assert revised.prompt_version == "2"
    assert revised.schema_version == PROMPT_REVISION_SCHEMA_VERSION
    assert "净流入突增" in revised.prompt_text
    assert revised.audit_history[-1]["changes_summary"] == ["缩窄研究范围"]
