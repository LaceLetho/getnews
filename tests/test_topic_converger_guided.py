"""Tests for user-objective guided topic convergence."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Optional

from crypto_news_analyzer.domain.models import IntelligenceTopic
from crypto_news_analyzer.intelligence.topic_converger import TopicConverger


class _FakeChatCompletions:
    def __init__(self, payloads: list[Any]) -> None:
        self.payloads = payloads
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        payload = self.payloads[min(len(self.calls) - 1, len(self.payloads) - 1)]
        content = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


class _FakeClient:
    def __init__(self, payload: dict[str, Any] | list[Any]) -> None:
        payloads = payload if isinstance(payload, list) else [payload]
        self.chat = SimpleNamespace(completions=_FakeChatCompletions(payloads))


class _FakeRepository:
    def __init__(self) -> None:
        now = datetime.utcnow()
        self.topics = {
            "t1": IntelligenceTopic(
                id="t1",
                name="速刷号",
                description="批量生成账号",
                created_at=now,
                updated_at=now,
            ),
            "t2": IntelligenceTopic(
                id="t2",
                name="注册机",
                description="批量注册工具",
                created_at=now,
                updated_at=now,
            ),
            "t3": IntelligenceTopic(
                id="t3",
                name="plus json",
                description="Plus 账号凭证交易格式",
                created_at=now,
                updated_at=now,
            ),
        }
        self.entries = {
            "t1": [SimpleNamespace(id="e1")],
            "t2": [SimpleNamespace(id="e2")],
            "t3": [SimpleNamespace(id="e3")],
        }
        self.logs: list[Any] = []

    def count_topics(self, is_active: Optional[bool] = None) -> int:
        topics = self.list_topics(is_active=is_active, limit=100, offset=0)
        return len(topics)

    def list_topics(
        self, is_active: Optional[bool] = None, limit: int = 100, offset: int = 0
    ) -> list[IntelligenceTopic]:
        topics = list(self.topics.values())
        if is_active is not None:
            topics = [topic for topic in topics if topic.is_active is is_active]
        return topics[offset : offset + limit]

    def count_entries_by_topic(self, topic_id: str) -> int:
        return len(self.entries.get(topic_id, []))

    def list_entries_by_topic(self, topic_id: str, limit: int = 100, offset: int = 0) -> list[Any]:
        return self.entries.get(topic_id, [])[offset : offset + limit]

    def assign_entry_to_topic(self, entry_id: str, topic_id: str) -> Any:
        for old_topic_id, entries in list(self.entries.items()):
            for entry in list(entries):
                if entry.id == entry_id:
                    entries.remove(entry)
                    self.entries.setdefault(topic_id, []).append(entry)
                    return entry
        return None

    def save_topic(self, topic: IntelligenceTopic) -> str:
        self.topics[topic.id] = topic
        return topic.id

    def save_topic_run_log(self, log: Any) -> str:
        self.logs.append(log)
        return log.id


def test_guided_convergence_merges_llm_topic_group() -> None:
    repo = _FakeRepository()
    payload = {
        "reason": "按 GPT Plus 非官方购买链路收敛",
        "merge_groups": [
            {
                "reason": "都描述账号生产和 Plus 凭证供应链",
                "keeper_topic_id": "t1",
                "topic_ids": ["t1", "t2", "t3"],
                "merged_name": "GPT/Claude 非官方会员购买渠道",
                "merged_description": "追踪会员账号供应、批量注册和凭证交易链路",
                "merged_summary": "速刷号、注册机和 plus json 属于同一账号供应链侧面。",
                "merged_source_channels": [],
                "merged_methods": "按账号生产、凭证流转和下游分销跟踪。",
                "merged_vulnerabilities": "",
                "merged_latest_findings": ["注册机与 plus json 可作为供应链关联信号"],
            }
        ],
        "keep_topic_ids": [],
    }
    converger = TopicConverger(
        intelligence_repository=repo,
        prompt_path=Path("prompts/topic_convergence_prompt.md"),
        guided_prompt_path=Path("prompts/topic_guided_convergence_prompt.md"),
    )
    converger.client = _FakeClient(payload)

    result = converger.run_convergence(
        user_objective="关注GPT/Claude会员的非官方购买渠道",
        target_topic_count=9,
    )

    assert result["mode"] == "guided"
    assert result["merged_count"] == 2
    assert repo.topics["t1"].name == "GPT/Claude 非官方会员购买渠道"
    assert repo.topics["t2"].is_active is False
    assert repo.topics["t3"].is_active is False
    assert [entry.id for entry in repo.entries["t1"]] == ["e1", "e2", "e3"]
    assert any(log.details.get("mode") == "guided" for log in repo.logs)


def test_guided_convergence_retries_empty_llm_content() -> None:
    repo = _FakeRepository()
    payload = {
        "reason": "retry success",
        "merge_groups": [
            {
                "reason": "同一链路",
                "keeper_topic_id": "t1",
                "topic_ids": ["t1", "t2"],
                "merged_name": "会员账号供应链",
                "merged_description": "账号供应链",
                "merged_summary": "注册机并入速刷号。",
                "merged_source_channels": [],
                "merged_methods": "",
                "merged_vulnerabilities": "",
                "merged_latest_findings": [],
            }
        ],
        "keep_topic_ids": ["t3"],
    }
    converger = TopicConverger(
        intelligence_repository=repo,
        prompt_path=Path("prompts/topic_convergence_prompt.md"),
        guided_prompt_path=Path("prompts/topic_guided_convergence_prompt.md"),
    )
    client = _FakeClient(["", payload])
    converger.client = client

    result = converger.run_convergence(user_objective="关注会员渠道", target_topic_count=9)

    assert result["merged_count"] == 1
    assert len(client.chat.completions.calls) == 2
    assert client.chat.completions.calls[1]["extra_body"] == {}


def test_guided_convergence_falls_back_when_llm_returns_empty_content() -> None:
    repo = _FakeRepository()
    converger = TopicConverger(
        intelligence_repository=repo,
        prompt_path=Path("prompts/topic_convergence_prompt.md"),
        guided_prompt_path=Path("prompts/topic_guided_convergence_prompt.md"),
    )
    client = _FakeClient(["", ""])
    converger.client = client

    result = converger.run_convergence(
        user_objective="关注GPT/Claude会员的非官方购买渠道，挖掘渠道源头、系统漏洞、套利机会",
        target_topic_count=9,
    )

    assert result["fallback"] is True
    assert result["merged_count"] == 2
    assert repo.topics["t1"].name == "GPT/Claude 非官方会员购买渠道"
    assert repo.topics["t2"].is_active is False
    assert repo.topics["t3"].is_active is False
    assert any(log.details.get("fallback") is True for log in repo.logs)
