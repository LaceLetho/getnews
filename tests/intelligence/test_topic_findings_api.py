"""Tests for topic finding merge preview and accept workflow."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Any, Dict, List, Optional

import pytest
from fastapi.testclient import TestClient

from crypto_news_analyzer import api_server
from crypto_news_analyzer.domain.models import (
    FindingArchive,
    IntelligenceTopic,
    MergePreview,
    TopicFinding,
    TopicFindingStatus,
    TopicLifecycleStatus,
    TopicPrompt,
)
from crypto_news_analyzer.intelligence.topic_findings import (
    MergePreviewError,
    TopicFindingMergeService,
)
from crypto_news_analyzer.models import StorageConfig


class FakeChatCompletions:
    def __init__(self, payload: Any):
        self.payload = payload
        self.calls: List[Dict[str, Any]] = []

    def create(self, **kwargs: Any) -> SimpleNamespace:
        self.calls.append(kwargs)
        content = self.payload if isinstance(self.payload, str) else json.dumps(self.payload)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


class FakeLLMClient:
    def __init__(self, payload: Any):
        self.completions = FakeChatCompletions(payload)
        self.chat = SimpleNamespace(completions=self.completions)


class InMemoryTopicRepository:
    """In-memory repository supporting topic-only merge workflow tests."""

    def __init__(self):
        self.topics: Dict[str, IntelligenceTopic] = {}
        self.prompts: Dict[str, TopicPrompt] = {}
        self.findings: Dict[str, TopicFinding] = {}
        self.previews: Dict[str, MergePreview] = {}
        self.archives: Dict[str, FindingArchive] = {}

    def save_topic(self, topic: IntelligenceTopic) -> str:
        self.topics[topic.id] = topic
        return topic.id

    def get_topic_by_id(self, topic_id: str) -> Optional[IntelligenceTopic]:
        return self.topics.get(topic_id)

    def get_topic_prompt_by_id(self, prompt_version_id: str) -> Optional[TopicPrompt]:
        return self.prompts.get(prompt_version_id)

    def create_topic_prompt_version(self, prompt: TopicPrompt) -> str:
        self.prompts[prompt.id] = prompt
        return prompt.id

    def create_topic_finding(self, finding: TopicFinding) -> str:
        self.findings[finding.id] = finding
        return finding.id

    def get_topic_finding_by_id(self, finding_id: str) -> Optional[TopicFinding]:
        return self.findings.get(finding_id)

    def list_active_findings(self, topic_id: str) -> List[TopicFinding]:
        return [
            f
            for f in self.findings.values()
            if f.intelligence_topic_id == topic_id and f.status == TopicFindingStatus.ACTIVE.value
        ]

    def archive_finding(
        self, finding_id: str, superseded_by_id: Optional[str] = None
    ) -> Optional[TopicFinding]:
        finding = self.findings.get(finding_id)
        if finding is None:
            return None
        finding.status = TopicFindingStatus.SUPERSEDED.value
        finding.superseded_by_finding_id = superseded_by_id
        finding.archived_at = datetime.utcnow()
        return finding

    def archive_topic_finding(self, archive: FindingArchive) -> None:
        self.archives[archive.finding_id] = archive

    def get_finding_archive(self, finding_id: str) -> Optional[FindingArchive]:
        return self.archives.get(finding_id)

    def create_merge_preview(self, preview: MergePreview) -> str:
        return self.save_merge_preview(preview)

    def save_merge_preview(self, preview: MergePreview) -> str:
        self.previews[preview.id] = preview
        return preview.id

    def get_merge_preview(self, preview_id: str) -> Optional[MergePreview]:
        return self.previews.get(preview_id)

    def get_merge_preview_by_id(self, preview_id: str) -> Optional[MergePreview]:
        return self.get_merge_preview(preview_id)

    def accept_merge_preview(self, preview_id: str) -> bool:
        preview = self.previews.get(preview_id)
        if preview is None:
            return False
        preview.state = "applied"
        preview.applied_at = datetime.utcnow()
        return True

    def reject_merge_preview(self, preview_id: str) -> bool:
        preview = self.previews.get(preview_id)
        if preview is None:
            return False
        preview.state = "cancelled"
        return True

    def list_merge_previews(
        self,
        intelligence_topic_id: str,
        state: Optional[str] = None,
        include_expired: bool = False,
        limit: int = 50,
    ) -> List[MergePreview]:
        results = [
            p for p in self.previews.values() if p.intelligence_topic_id == intelligence_topic_id
        ]
        if state:
            results = [p for p in results if p.state == state]
        if not include_expired:
            now = datetime.utcnow()
            results = [p for p in results if p.expires_at > now]
        return results[:limit]

    def list_topic_prompts(
        self,
        intelligence_topic_id: str,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[TopicPrompt]:
        results = [
            p for p in self.prompts.values() if p.intelligence_topic_id == intelligence_topic_id
        ]
        if status:
            results = [p for p in results if p.status == status]
        results.sort(
            key=lambda p: getattr(p, "created_at", datetime.min) or datetime.min,
            reverse=True,
        )
        return results[offset : offset + limit]

    def list_topic_findings(
        self,
        intelligence_topic_id: str,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[TopicFinding]:
        results = [
            f for f in self.findings.values() if f.intelligence_topic_id == intelligence_topic_id
        ]
        if status:
            results = [f for f in results if f.status == status]
        return results[offset : offset + limit]

    def list_entries_by_topic(self, topic_id: str, limit: int = 100, offset: int = 0) -> List[Any]:
        return []

    def get_active_topic_prompt(self, topic_id: str) -> Optional[TopicPrompt]:
        prompts = self.list_topic_prompts(topic_id, status="active", limit=1)
        return prompts[0] if prompts else None


def _valid_merge_payload() -> Dict[str, Any]:
    return {
        "schema_version": "topic-findings-merge-v1",
        "topic_name": "BTC ETF flow",
        "merge_summary": "BTC ETF 资金流异常合并发现",
        "merged_findings": [
            {
                "finding_id": "mf-1",
                "summary": "BTC ETF 单小时净流入突然放大",
                "detail": "合并后的详细描述",
                "confidence": 0.85,
                "source_finding_ids": ["finding-1", "finding-2"],
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
        "findings_merged_count": 2,
        "findings_new_count": 0,
        "findings_deduplicated_count": 0,
    }


def _make_topic_and_prompt(repo: InMemoryTopicRepository) -> tuple[str, str]:
    topic = IntelligenceTopic.create(name="BTC ETF flow")
    repo.save_topic(topic)
    prompt = TopicPrompt.create(
        intelligence_topic_id=topic.id,
        prompt_version="1",
        prompt_text="研究 BTC ETF 资金流异常",
        schema_version="topic-prompt-generation-v1",
        status="active",
    )
    repo.create_topic_prompt_version(prompt)
    return topic.id, prompt.id


def _make_findings(repo: InMemoryTopicRepository, topic_id: str, prompt_id: str) -> List[str]:
    finding_ids: List[str] = []
    for i in range(3):
        finding = TopicFinding.create(
            intelligence_topic_id=topic_id,
            prompt_version_id=prompt_id,
            finding_payload={"summary": f"finding {i}", "severity": "medium"},
            content_hash=f"hash-{i}",
            citations=[{"message_id": f"raw-{i}", "message_snippet": f"evidence {i}"}],
            source_raw_item_ids=[f"raw-{i}"],
            confidence=0.8,
        )
        finding.id = f"finding-{i}"
        repo.create_topic_finding(finding)
        finding_ids.append(finding.id)
    return finding_ids


def test_merge_preview_creation() -> None:
    repo = InMemoryTopicRepository()
    topic_id, prompt_id = _make_topic_and_prompt(repo)
    source_ids = _make_findings(repo, topic_id, prompt_id)

    llm_client = FakeLLMClient(_valid_merge_payload())
    service = TopicFindingMergeService(
        repo,
        llm_client,
    )
    preview = asyncio.run(service.create_merge_preview(topic_id, prompt_id, created_by="tester"))

    assert preview.intelligence_topic_id == topic_id
    assert sorted(preview.source_finding_ids) == sorted(source_ids)
    assert preview.state == "pending"
    assert preview.expires_at > datetime.utcnow()
    assert preview.expires_at <= datetime.utcnow() + timedelta(hours=24)
    assert preview.content_hash
    assert preview.preview_payload.get("schema_version") == "topic-findings-merge-v1"

    stored = repo.get_merge_preview(preview.id)
    assert stored is not None
    assert stored.source_finding_ids == preview.source_finding_ids
    assert llm_client.completions.calls[0]["model"] == "deepseek-v4-flash"
    assert llm_client.completions.calls[0]["timeout"] == 180.0


def test_merge_preview_uses_env_model_override(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = InMemoryTopicRepository()
    topic_id, prompt_id = _make_topic_and_prompt(repo)
    _make_findings(repo, topic_id, prompt_id)

    monkeypatch.setenv("TOPIC_MERGE_MODEL", "custom-merge-model")
    llm_client = FakeLLMClient(_valid_merge_payload())
    service = TopicFindingMergeService(repo, llm_client, model_name="deepseek-v4-pro")

    asyncio.run(service.create_merge_preview(topic_id, prompt_id, created_by="tester"))

    assert llm_client.completions.calls[0]["model"] == "custom-merge-model"


def test_merge_preview_llm_timeout_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = InMemoryTopicRepository()
    topic_id, prompt_id = _make_topic_and_prompt(repo)
    _make_findings(repo, topic_id, prompt_id)

    monkeypatch.setenv("TOPIC_MERGE_LLM_TIMEOUT_SECONDS", "45")
    llm_client = FakeLLMClient(_valid_merge_payload())
    service = TopicFindingMergeService(repo, llm_client)

    asyncio.run(service.create_merge_preview(topic_id, prompt_id, created_by="tester"))

    assert llm_client.completions.calls[0]["timeout"] == 45.0


def test_merge_accept_archives_exact_sources() -> None:
    repo = InMemoryTopicRepository()
    topic_id, prompt_id = _make_topic_and_prompt(repo)
    source_ids = _make_findings(repo, topic_id, prompt_id)

    service = TopicFindingMergeService(
        repo,
        FakeLLMClient(_valid_merge_payload()),
    )
    preview = asyncio.run(service.create_merge_preview(topic_id, prompt_id))

    merged = service.accept_merge_preview(preview.id, operator="operator-01")

    assert merged.intelligence_topic_id == topic_id
    assert merged.status == TopicFindingStatus.ACTIVE.value
    assert merged.source_finding_ids == source_ids

    for source_id in source_ids:
        archived = repo.get_topic_finding_by_id(source_id)
        assert archived is not None
        assert archived.status == TopicFindingStatus.SUPERSEDED.value
        assert archived.superseded_by_finding_id == merged.id
        archive_record = repo.get_finding_archive(source_id)
        assert archive_record is not None
        assert archive_record.superseded_by_finding_id == merged.id

    updated_preview = repo.get_merge_preview(preview.id)
    assert updated_preview is not None
    assert updated_preview.state == "applied"

    active_after = repo.list_active_findings(topic_id)
    assert len(active_after) == 1
    assert active_after[0].id == merged.id


def test_stale_merge_preview_rejected() -> None:
    repo = InMemoryTopicRepository()
    topic_id, prompt_id = _make_topic_and_prompt(repo)
    source_ids = _make_findings(repo, topic_id, prompt_id)

    service = TopicFindingMergeService(
        repo,
        FakeLLMClient(_valid_merge_payload()),
    )
    preview = asyncio.run(service.create_merge_preview(topic_id, prompt_id))

    new_finding = TopicFinding.create(
        intelligence_topic_id=topic_id,
        prompt_version_id=prompt_id,
        finding_payload={"summary": "new finding", "severity": "high"},
        content_hash="hash-new",
        citations=[{"message_id": "raw-new", "message_snippet": "new evidence"}],
        source_raw_item_ids=["raw-new"],
        confidence=0.9,
    )
    new_finding.id = "finding-new"
    repo.create_topic_finding(new_finding)

    with pytest.raises(MergePreviewError, match="active finding set has changed"):
        service.accept_merge_preview(preview.id)

    for source_id in source_ids:
        finding = repo.get_topic_finding_by_id(source_id)
        assert finding is not None
        assert finding.status == TopicFindingStatus.ACTIVE.value
        assert finding.superseded_by_finding_id is None

    assert repo.get_merge_preview(preview.id).state == "pending"


def test_expired_merge_preview_rejected() -> None:
    repo = InMemoryTopicRepository()
    topic_id, prompt_id = _make_topic_and_prompt(repo)
    _make_findings(repo, topic_id, prompt_id)

    service = TopicFindingMergeService(
        repo,
        FakeLLMClient(_valid_merge_payload()),
    )
    preview = asyncio.run(service.create_merge_preview(topic_id, prompt_id))

    stored = repo.get_merge_preview(preview.id)
    stored.expires_at = datetime.utcnow() - timedelta(hours=1)

    with pytest.raises(MergePreviewError, match="expired"):
        service.accept_merge_preview(preview.id)


def test_reject_merge_preview() -> None:
    repo = InMemoryTopicRepository()
    topic_id, prompt_id = _make_topic_and_prompt(repo)
    _make_findings(repo, topic_id, prompt_id)

    service = TopicFindingMergeService(
        repo,
        FakeLLMClient(_valid_merge_payload()),
    )
    preview = asyncio.run(service.create_merge_preview(topic_id, prompt_id))

    service.reject_merge_preview(preview.id)

    assert repo.get_merge_preview(preview.id).state == "cancelled"


def test_accept_non_pending_preview_fails() -> None:
    repo = InMemoryTopicRepository()
    topic_id, prompt_id = _make_topic_and_prompt(repo)
    _make_findings(repo, topic_id, prompt_id)

    service = TopicFindingMergeService(
        repo,
        FakeLLMClient(_valid_merge_payload()),
    )
    preview = asyncio.run(service.create_merge_preview(topic_id, prompt_id))
    repo.reject_merge_preview(preview.id)

    with pytest.raises(MergePreviewError, match="not pending"):
        service.accept_merge_preview(preview.id)


def test_create_preview_requires_two_findings() -> None:
    repo = InMemoryTopicRepository()
    topic_id, prompt_id = _make_topic_and_prompt(repo)
    finding = TopicFinding.create(
        intelligence_topic_id=topic_id,
        prompt_version_id=prompt_id,
        finding_payload={"summary": "only one", "severity": "medium"},
        content_hash="hash-0",
        citations=[{"message_id": "raw-0", "message_snippet": "evidence"}],
        source_raw_item_ids=["raw-0"],
        confidence=0.8,
    )
    finding.id = "finding-0"
    repo.create_topic_finding(finding)

    service = TopicFindingMergeService(repo, FakeLLMClient(_valid_merge_payload()))
    with pytest.raises(MergePreviewError, match="at least two"):
        asyncio.run(service.create_merge_preview(topic_id, prompt_id))


# ── FastAPI TestClient integration tests ──────────────────────────────


_TOPIC_CREATE_PAYLOAD: Dict[str, Any] = {
    "schema_version": "topic-prompt-generation-v1",
    "topic_name": "BTC ETF Flow",
    "topic_description": "Monitor BTC ETF fund flow anomalies",
    "research_prompt_draft": "Analyze BTC ETF fund flow data",
    "suggested_time_window_hours": 24,
    "confidence": 0.9,
}


class _TopicApiFakeController:
    """Fake controller for topic workflow API tests."""

    def __init__(
        self,
        repository: InMemoryTopicRepository,
        llm_payload: Any = None,
    ) -> None:
        self.intelligence_repository = repository
        self._repositories: dict[str, Any] = {"intelligence": repository}
        self.data_manager = None
        self.analysis_repository = None
        self.datasource_repository = None
        self.semantic_search_repository = None
        self.command_handler = None
        self.llm_analyzer = SimpleNamespace(
            client=FakeLLMClient(llm_payload or _TOPIC_CREATE_PAYLOAD)
        )
        self.storage_config = StorageConfig(backend="sqlite", database_path=":memory:")
        self.config_manager = SimpleNamespace(
            config_data={},
            get_analysis_config=lambda: {
                "max_analysis_window_hours": 24,
                "min_analysis_window_hours": 1,
            },
            get_storage_config=lambda: self.storage_config,
            get_auth_config=lambda: SimpleNamespace(
                GROK_API_KEY="grok-key",
                KIMI_API_KEY="kimi-key",
                OPENCODE_API_KEY="opencode-key",
            ),
        )

    def initialize_system(self) -> bool:
        return True

    def start_scheduler(self) -> None:
        pass

    def stop_scheduler(self) -> None:
        pass

    def start_command_listener(self) -> None:
        pass

    def stop_command_listener(self) -> None:
        pass


def _authorized() -> dict[str, str]:
    return {"Authorization": "Bearer test-api-key"}


@pytest.fixture(autouse=True)
def set_api_key_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("API_KEY", "test-api-key")


def _build_topic_test_app(
    monkeypatch: pytest.MonkeyPatch,
    controller: _TopicApiFakeController,
) -> TestClient:
    monkeypatch.setattr(api_server, "MainController", lambda *_args, **_kwargs: controller)
    app = api_server.create_api_server(
        "./config.jsonc",
        start_services=False,
        start_scheduler=False,
        start_command_listener=False,
    )
    return TestClient(app)


def test_unauthorized_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = InMemoryTopicRepository()
    controller = _TopicApiFakeController(repo)
    with _build_topic_test_app(monkeypatch, controller) as client:
        endpoints = [
            ("get", "/intelligence/topics"),
            ("post", "/intelligence/topics"),
            ("post", "/intelligence/topics/topic-1/revise"),
            ("put", "/intelligence/topics/topic-1/prompt"),
            ("post", "/intelligence/topics/topic-1/confirm"),
            ("post", "/intelligence/topics/topic-1/merge-preview"),
            ("post", "/intelligence/topics/topic-1/merge-accept"),
            ("post", "/intelligence/topics/topic-1/pause"),
            ("post", "/intelligence/topics/topic-1/archive"),
            ("get", "/intelligence/topics/topic-1"),
        ]
        for method, path in endpoints:
            if method == "get":
                resp = client.get(path)
            elif method == "post":
                resp = client.post(path, json={})
            elif method == "put":
                resp = client.put(path, json={})
            assert resp.status_code == 401, f"{method} {path} should reject unauthorized"


def test_old_entries_routes_404(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = InMemoryTopicRepository()
    controller = _TopicApiFakeController(repo)
    with _build_topic_test_app(monkeypatch, controller) as client:
        assert client.get("/intelligence/entries", headers=_authorized()).status_code == 404
        assert client.get("/intelligence/discovery", headers=_authorized()).status_code == 404
        assert client.get("/intelligence/labels", headers=_authorized()).status_code == 404
        assert client.get("/intelligence/search?q=test", headers=_authorized()).status_code == 404
        assert client.get("/intelligence/raw/raw-001", headers=_authorized()).status_code == 404


def test_create_and_confirm_topic_via_api(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = InMemoryTopicRepository()
    controller = _TopicApiFakeController(repo)
    with _build_topic_test_app(monkeypatch, controller) as client:
        create_resp = client.post(
            "/intelligence/topics",
            headers=_authorized(),
            json={"theme": "BTC ETF fund flow analysis"},
        )
        assert create_resp.status_code == 201, create_resp.text
        data = create_resp.json()
        assert data["intelligence_topic_id"]
        assert data["prompt_text"]
        assert data["status"] == "draft"
        topic_id = data["intelligence_topic_id"]
        prompt_id = data["id"]

        confirm_resp = client.post(
            f"/intelligence/topics/{topic_id}/confirm",
            headers=_authorized(),
            json={"prompt_version_id": prompt_id},
        )
        assert confirm_resp.status_code == 200, confirm_resp.text
        confirmed = confirm_resp.json()
        assert confirmed["status"] == "active"


def test_topic_detail_includes_findings(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = InMemoryTopicRepository()
    topic_id, prompt_id = _make_topic_and_prompt(repo)
    finding_ids = _make_findings(repo, topic_id, prompt_id)

    controller = _TopicApiFakeController(repo)
    with _build_topic_test_app(monkeypatch, controller) as client:
        resp = client.get(f"/intelligence/topics/{topic_id}", headers=_authorized())
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["topic"]["id"] == topic_id
        assert len(data["prompt_versions"]) > 0
        assert data["current_prompt"] is not None
        assert len(data["active_findings"]) == len(finding_ids)
        assert data["active_findings"][0]["id"] in finding_ids


def test_merge_preview_via_api(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = InMemoryTopicRepository()
    topic_id, prompt_id = _make_topic_and_prompt(repo)
    _make_findings(repo, topic_id, prompt_id)

    controller = _TopicApiFakeController(repo, _valid_merge_payload())
    with _build_topic_test_app(monkeypatch, controller) as client:
        resp = client.post(
            f"/intelligence/topics/{topic_id}/merge-preview",
            headers=_authorized(),
            json={"prompt_version_id": prompt_id},
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["preview_id"]
        assert data["topic_id"] == topic_id
        assert data["state"] == "pending"
        assert data["expires_at"] is not None


def test_merge_accept_via_api(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = InMemoryTopicRepository()
    topic_id, prompt_id = _make_topic_and_prompt(repo)
    _make_findings(repo, topic_id, prompt_id)

    controller = _TopicApiFakeController(repo, _valid_merge_payload())
    with _build_topic_test_app(monkeypatch, controller) as client:
        preview_resp = client.post(
            f"/intelligence/topics/{topic_id}/merge-preview",
            headers=_authorized(),
            json={"prompt_version_id": prompt_id},
        )
        preview_id = preview_resp.json()["preview_id"]

        accept_resp = client.post(
            f"/intelligence/topics/{topic_id}/merge-accept",
            headers=_authorized(),
            json={"preview_id": preview_id},
        )
        assert accept_resp.status_code == 200, accept_resp.text
        merged = accept_resp.json()
        assert merged["intelligence_topic_id"] == topic_id
        assert merged["status"] == "active"


def test_stale_merge_preview_via_api(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = InMemoryTopicRepository()
    topic_id, prompt_id = _make_topic_and_prompt(repo)
    _make_findings(repo, topic_id, prompt_id)

    controller = _TopicApiFakeController(repo, _valid_merge_payload())
    with _build_topic_test_app(monkeypatch, controller) as client:
        preview_resp = client.post(
            f"/intelligence/topics/{topic_id}/merge-preview",
            headers=_authorized(),
            json={"prompt_version_id": prompt_id},
        )
        preview_id = preview_resp.json()["preview_id"]

        new_f = TopicFinding.create(
            intelligence_topic_id=topic_id,
            prompt_version_id=prompt_id,
            finding_payload={"summary": "new finding", "severity": "high"},
            content_hash="hash-new",
            citations=[{"message_id": "raw-new", "message_snippet": "new evidence"}],
            source_raw_item_ids=["raw-new"],
            confidence=0.9,
        )
        new_f.id = "finding-new"
        repo.create_topic_finding(new_f)

        accept_resp = client.post(
            f"/intelligence/topics/{topic_id}/merge-accept",
            headers=_authorized(),
            json={"preview_id": preview_id},
        )
        assert accept_resp.status_code == 400, accept_resp.text
        assert "changed" in accept_resp.json()["detail"].lower()


def test_merge_accept_missing_preview(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = InMemoryTopicRepository()
    topic_id, _ = _make_topic_and_prompt(repo)
    controller = _TopicApiFakeController(repo)
    with _build_topic_test_app(monkeypatch, controller) as client:
        resp = client.post(
            f"/intelligence/topics/{topic_id}/merge-accept",
            headers=_authorized(),
            json={"preview_id": "nonexistent-preview"},
        )
        assert resp.status_code == 400
        assert "not found" in resp.json()["detail"].lower()


def test_pause_topic(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = InMemoryTopicRepository()
    topic_id, _ = _make_topic_and_prompt(repo)
    # Promote to active first
    active_topics = list(repo.topics.values())
    active_topics[0].lifecycle_status = TopicLifecycleStatus.ACTIVE.value

    controller = _TopicApiFakeController(repo)
    with _build_topic_test_app(monkeypatch, controller) as client:
        resp = client.post(f"/intelligence/topics/{topic_id}/pause", headers=_authorized())
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["success"] is True
        assert data["lifecycle_status"] == "paused"


def test_archive_topic(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = InMemoryTopicRepository()
    topic_id, _ = _make_topic_and_prompt(repo)

    controller = _TopicApiFakeController(repo)
    with _build_topic_test_app(monkeypatch, controller) as client:
        resp = client.post(f"/intelligence/topics/{topic_id}/archive", headers=_authorized())
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["success"] is True
        assert data["lifecycle_status"] == "archived"
