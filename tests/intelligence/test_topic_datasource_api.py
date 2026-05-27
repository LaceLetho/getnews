"""Tests for topic-datasource association API endpoints."""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any, Dict, List, Optional

import pytest
from fastapi.testclient import TestClient

from crypto_news_analyzer import api_server
from crypto_news_analyzer.domain.models import (
    DataSource,
    DataSourcePurpose,
    IntelligenceTopic,
    SafeDataSourceSummary,
)
from crypto_news_analyzer.models import StorageConfig


class InMemoryTopicDatasourceRepo:
    """In-memory repository supporting topic CRUD AND topic-datasource association."""

    def __init__(self):
        self.topics: Dict[str, IntelligenceTopic] = {}
        self._topic_ds: Dict[str, set[str]] = {}
        self.datasources: Dict[str, DataSource] = {}
        self.prompts: Dict[str, Any] = {}
        self.findings: Dict[str, Any] = {}
        self.previews: Dict[str, Any] = {}
        self.archives: Dict[str, Any] = {}

    # ── Topic CRUD ────────────────────────────────────────────────────

    def save_topic(self, topic: IntelligenceTopic) -> str:
        self.topics[topic.id] = topic
        return topic.id

    def get_topic_by_id(self, topic_id: str) -> Optional[IntelligenceTopic]:
        return self.topics.get(topic_id)

    def list_topics(
        self,
        is_active: Optional[bool] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> List[IntelligenceTopic]:
        results = list(self.topics.values())
        if is_active is not None:
            results = [t for t in results if t.is_active == is_active]
        return results[offset : offset + limit]

    def count_topics(self, is_active: Optional[bool] = None) -> int:
        topics = list(self.topics.values())
        if is_active is not None:
            topics = [t for t in topics if t.is_active == is_active]
        return len(topics)

    # ── Datasource CRUD (minimal) ────────────────────────────────────

    def get_datasource_by_id(self, ds_id: str) -> Optional[DataSource]:
        return self.datasources.get(ds_id)

    def save_datasource(self, ds: DataSource) -> str:
        self.datasources[ds.id] = ds
        return ds.id

    # ── Topic-Datasource Association ─────────────────────────────────

    def get_topic_datasource_ids(self, topic_id: str) -> List[str]:
        self._validate_topic_exists(topic_id)
        return sorted(self._topic_ds.get(topic_id, set()))

    def set_topic_datasources(self, topic_id: str, datasource_ids: List[str]) -> None:
        self._validate_topic_exists(topic_id)
        normalized = sorted(set(datasource_ids)) if datasource_ids else []
        if normalized:
            self._validate_datasource_ids_for_topic(set(normalized))
        self._topic_ds[topic_id] = set(normalized)

    def add_topic_datasources(self, topic_id: str, datasource_ids: List[str]) -> None:
        self._validate_topic_exists(topic_id)
        normalized: set[str] = set(datasource_ids) if datasource_ids else set()
        if not normalized:
            return
        self._validate_datasource_ids_for_topic(normalized)
        if topic_id not in self._topic_ds:
            self._topic_ds[topic_id] = set()
        self._topic_ds[topic_id] |= normalized

    def remove_topic_datasources(self, topic_id: str, datasource_ids: List[str]) -> None:
        self._validate_topic_exists(topic_id)
        if not datasource_ids:
            return
        current = self._topic_ds.get(topic_id, set())
        self._topic_ds[topic_id] = current - set(datasource_ids)

    def get_topic_datasources(self, topic_id: str) -> List[SafeDataSourceSummary]:
        self._validate_topic_exists(topic_id)
        ds_ids = self._topic_ds.get(topic_id, set())
        results = []
        for ds_id in sorted(ds_ids):
            ds = self.datasources.get(ds_id)
            if ds is not None:
                results.append(
                    SafeDataSourceSummary(
                        id=ds.id,
                        source_type=ds.source_type,
                        name=ds.name,
                        tags=list(ds.tags),
                    )
                )
        return results

    # ── Internal validators ──────────────────────────────────────────

    def _validate_topic_exists(self, topic_id: str) -> None:
        if topic_id not in self.topics:
            raise ValueError(f"unknown topic: {topic_id}")

    def _validate_datasource_ids_for_topic(self, datasource_ids: set[str]) -> None:
        unknown = set(datasource_ids) - set(self.datasources.keys())
        if unknown:
            first = sorted(unknown)[0]
            raise ValueError(f"unknown datasource: {first}")
        for ds_id in datasource_ids:
            ds = self.datasources[ds_id]
            if getattr(ds, "purpose", None) != DataSourcePurpose.INTELLIGENCE.value:
                raise ValueError(f"datasource is not intelligence-purpose: {ds_id}")

    # ── Additional methods required by FakeController/API ────────────

    def get_active_topic_prompt(self, topic_id: str) -> Optional[Any]:
        prompts = [
            p
            for p in self.prompts.values()
            if getattr(p, "intelligence_topic_id", "") == topic_id
            and getattr(p, "status", "") == "active"
        ]
        return prompts[0] if prompts else None

    def list_topic_prompts(
        self,
        intelligence_topic_id: str,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Any]:
        results = [
            p
            for p in self.prompts.values()
            if getattr(p, "intelligence_topic_id", "") == intelligence_topic_id
        ]
        if status:
            results = [p for p in results if getattr(p, "status", "") == status]
        return results[offset : offset + limit]

    def list_active_findings(self, topic_id: str) -> List[Any]:
        return [
            f
            for f in self.findings.values()
            if getattr(f, "intelligence_topic_id", "") == topic_id
            and getattr(f, "status", "") == "active"
        ]

    def list_merge_previews(
        self,
        intelligence_topic_id: str,
        state: Optional[str] = None,
        limit: int = 1,
    ) -> List[Any]:
        return []

    def save_topic_prompt(self, prompt: Any) -> str:
        self.prompts[prompt.id] = prompt
        return prompt.id

    def create_topic_prompt_version(self, prompt: Any) -> str:
        return self.save_topic_prompt(prompt)

    def create_topic_finding(self, finding: Any) -> str:
        self.findings[finding.id] = finding
        return finding.id

    def get_topic_finding_by_id(self, finding_id: str) -> Optional[Any]:
        return self.findings.get(finding_id)


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
        self.with_options_calls: List[Dict[str, Any]] = []

    def with_options(self, **kwargs: Any) -> "FakeLLMClient":
        self.with_options_calls.append(kwargs)
        return self


_TOPIC_CREATE_PAYLOAD: Dict[str, Any] = {
    "schema_version": "topic-prompt-generation-v1",
    "topic_name": "BTC ETF Flow",
    "topic_description": "Monitor BTC ETF fund flow anomalies",
    "research_prompt_draft": "Analyze BTC ETF fund flow data",
    "suggested_time_window_hours": 24,
    "confidence": 0.9,
}


class _TopicApiFakeController:
    def __init__(
        self,
        repository: InMemoryTopicDatasourceRepo,
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


def _make_topic(repo: InMemoryTopicDatasourceRepo, name: str = "BTC ETF flow") -> str:
    topic = IntelligenceTopic.create(name=name)
    repo.save_topic(topic)
    return topic.id


def _make_intelligence_datasource(
    repo: InMemoryTopicDatasourceRepo,
    ds_id: str,
    source_type: str = "telegram_group",
    name: str = "Test DS",
    tags: Optional[List[str]] = None,
) -> DataSource:
    ds = DataSource(
        id=ds_id,
        source_type=source_type,
        name=name,
        purpose=DataSourcePurpose.INTELLIGENCE.value,
        tags=tags or [],
    )
    repo.datasources[ds_id] = ds
    return ds


def _make_news_datasource(
    repo: InMemoryTopicDatasourceRepo,
    ds_id: str,
    source_type: str = "rss",
    name: str = "News DS",
) -> DataSource:
    ds = DataSource(
        id=ds_id,
        source_type=source_type,
        name=name,
        purpose=DataSourcePurpose.NEWS.value,
    )
    repo.datasources[ds_id] = ds
    return ds


# ── Authorization tests ──────────────────────────────────────────────


def test_unauthorized_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = InMemoryTopicDatasourceRepo()
    topic_id = _make_topic(repo)
    controller = _TopicApiFakeController(repo)
    with _build_topic_test_app(monkeypatch, controller) as client:
        endpoints = [
            ("get", f"/intelligence/topics/{topic_id}/datasources"),
            ("put", f"/intelligence/topics/{topic_id}/datasources"),
            ("post", f"/intelligence/topics/{topic_id}/datasources/ds-1"),
            ("delete", f"/intelligence/topics/{topic_id}/datasources/ds-1"),
        ]
        for method, path in endpoints:
            if method == "get":
                resp = client.get(path)
            elif method == "post":
                resp = client.post(path)
            elif method == "put":
                resp = client.put(path, json={})
            elif method == "delete":
                resp = client.delete(path)
            assert resp.status_code == 401, f"{method} {path} should reject unauthorized"


# ── GET /intelligence/topics/{topic_id}/datasources ───────────────────


def test_get_datasources_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = InMemoryTopicDatasourceRepo()
    topic_id = _make_topic(repo)
    controller = _TopicApiFakeController(repo)
    with _build_topic_test_app(monkeypatch, controller) as client:
        resp = client.get(
            f"/intelligence/topics/{topic_id}/datasources",
            headers=_authorized(),
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data == []


def test_get_datasources_unknown_topic_404(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = InMemoryTopicDatasourceRepo()
    controller = _TopicApiFakeController(repo)
    with _build_topic_test_app(monkeypatch, controller) as client:
        resp = client.get(
            "/intelligence/topics/nonexistent/datasources",
            headers=_authorized(),
        )
        assert resp.status_code == 404, resp.text
        assert "unknown topic" in resp.json()["detail"].lower()


def test_get_datasources_with_associations(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = InMemoryTopicDatasourceRepo()
    topic_id = _make_topic(repo)
    ds_a = _make_intelligence_datasource(repo, "ds-a", name="Alpha")
    ds_b = _make_intelligence_datasource(repo, "ds-b", name="Beta", source_type="v2ex")
    repo.add_topic_datasources(topic_id, ["ds-a", "ds-b"])

    controller = _TopicApiFakeController(repo)
    with _build_topic_test_app(monkeypatch, controller) as client:
        resp = client.get(
            f"/intelligence/topics/{topic_id}/datasources",
            headers=_authorized(),
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert len(data) == 2
        for item in data:
            assert "id" in item
            assert "source_type" in item
            assert "name" in item
            assert "tags" in item
            assert "config_payload" not in item
        ids = [d["id"] for d in data]
        assert "ds-a" in ids
        assert "ds-b" in ids


# ── PUT /intelligence/topics/{topic_id}/datasources ───────────────────


def test_put_set_datasources(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = InMemoryTopicDatasourceRepo()
    topic_id = _make_topic(repo)
    _make_intelligence_datasource(repo, "ds-a", name="Alpha")
    _make_intelligence_datasource(repo, "ds-b", name="Beta")

    controller = _TopicApiFakeController(repo)
    with _build_topic_test_app(monkeypatch, controller) as client:
        resp = client.put(
            f"/intelligence/topics/{topic_id}/datasources",
            headers=_authorized(),
            json={"datasource_ids": ["ds-a", "ds-b"]},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert len(data) == 2
        assert {d["id"] for d in data} == {"ds-a", "ds-b"}


def test_put_set_datasources_empty_clears_all(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = InMemoryTopicDatasourceRepo()
    topic_id = _make_topic(repo)
    _make_intelligence_datasource(repo, "ds-a", name="Alpha")
    repo.add_topic_datasources(topic_id, ["ds-a"])

    controller = _TopicApiFakeController(repo)
    with _build_topic_test_app(monkeypatch, controller) as client:
        resp = client.put(
            f"/intelligence/topics/{topic_id}/datasources",
            headers=_authorized(),
            json={"datasource_ids": []},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data == []


def test_put_set_datasources_unknown_topic_404(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = InMemoryTopicDatasourceRepo()
    controller = _TopicApiFakeController(repo)
    with _build_topic_test_app(monkeypatch, controller) as client:
        resp = client.put(
            "/intelligence/topics/nonexistent/datasources",
            headers=_authorized(),
            json={"datasource_ids": ["ds-a"]},
        )
        assert resp.status_code == 404, resp.text
        assert "unknown topic" in resp.json()["detail"].lower()


def test_put_set_datasources_unknown_ds_404(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = InMemoryTopicDatasourceRepo()
    topic_id = _make_topic(repo)
    controller = _TopicApiFakeController(repo)
    with _build_topic_test_app(monkeypatch, controller) as client:
        resp = client.put(
            f"/intelligence/topics/{topic_id}/datasources",
            headers=_authorized(),
            json={"datasource_ids": ["nonexistent"]},
        )
        assert resp.status_code == 404, resp.text
        assert "unknown datasource" in resp.json()["detail"].lower()


def test_put_set_datasources_news_ds_400(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = InMemoryTopicDatasourceRepo()
    topic_id = _make_topic(repo)
    _make_news_datasource(repo, "ds-news", name="News DS")

    controller = _TopicApiFakeController(repo)
    with _build_topic_test_app(monkeypatch, controller) as client:
        resp = client.put(
            f"/intelligence/topics/{topic_id}/datasources",
            headers=_authorized(),
            json={"datasource_ids": ["ds-news"]},
        )
        assert resp.status_code == 400, resp.text
        assert "not intelligence" in resp.json()["detail"].lower()


# ── POST /intelligence/topics/{topic_id}/datasources/{datasource_id} ──


def test_post_add_datasource(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = InMemoryTopicDatasourceRepo()
    topic_id = _make_topic(repo)
    _make_intelligence_datasource(repo, "ds-a", name="Alpha")

    controller = _TopicApiFakeController(repo)
    with _build_topic_test_app(monkeypatch, controller) as client:
        resp = client.post(
            f"/intelligence/topics/{topic_id}/datasources/ds-a",
            headers=_authorized(),
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert len(data) == 1
        assert data[0]["id"] == "ds-a"


def test_post_add_datasource_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = InMemoryTopicDatasourceRepo()
    topic_id = _make_topic(repo)
    _make_intelligence_datasource(repo, "ds-a", name="Alpha")
    repo.add_topic_datasources(topic_id, ["ds-a"])

    controller = _TopicApiFakeController(repo)
    with _build_topic_test_app(monkeypatch, controller) as client:
        resp = client.post(
            f"/intelligence/topics/{topic_id}/datasources/ds-a",
            headers=_authorized(),
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert len(data) == 1  # still just one, no duplicate


def test_post_add_datasource_unknown_topic_404(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = InMemoryTopicDatasourceRepo()
    controller = _TopicApiFakeController(repo)
    with _build_topic_test_app(monkeypatch, controller) as client:
        resp = client.post(
            "/intelligence/topics/nonexistent/datasources/ds-a",
            headers=_authorized(),
        )
        assert resp.status_code == 404, resp.text
        assert "unknown topic" in resp.json()["detail"].lower()


def test_post_add_datasource_unknown_ds_404(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = InMemoryTopicDatasourceRepo()
    topic_id = _make_topic(repo)
    controller = _TopicApiFakeController(repo)
    with _build_topic_test_app(monkeypatch, controller) as client:
        resp = client.post(
            f"/intelligence/topics/{topic_id}/datasources/nonexistent",
            headers=_authorized(),
        )
        assert resp.status_code == 404, resp.text
        assert "unknown datasource" in resp.json()["detail"].lower()


def test_post_add_datasource_news_ds_400(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = InMemoryTopicDatasourceRepo()
    topic_id = _make_topic(repo)
    _make_news_datasource(repo, "ds-news", name="News DS")

    controller = _TopicApiFakeController(repo)
    with _build_topic_test_app(monkeypatch, controller) as client:
        resp = client.post(
            f"/intelligence/topics/{topic_id}/datasources/ds-news",
            headers=_authorized(),
        )
        assert resp.status_code == 400, resp.text
        assert "not intelligence" in resp.json()["detail"].lower()


# ── DELETE /intelligence/topics/{topic_id}/datasources/{datasource_id} ─


def test_delete_remove_datasource(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = InMemoryTopicDatasourceRepo()
    topic_id = _make_topic(repo)
    _make_intelligence_datasource(repo, "ds-a", name="Alpha")
    repo.add_topic_datasources(topic_id, ["ds-a"])

    controller = _TopicApiFakeController(repo)
    with _build_topic_test_app(monkeypatch, controller) as client:
        resp = client.delete(
            f"/intelligence/topics/{topic_id}/datasources/ds-a",
            headers=_authorized(),
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data == []


def test_delete_remove_datasource_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = InMemoryTopicDatasourceRepo()
    topic_id = _make_topic(repo)
    _make_intelligence_datasource(repo, "ds-a", name="Alpha")

    controller = _TopicApiFakeController(repo)
    with _build_topic_test_app(monkeypatch, controller) as client:
        resp = client.delete(
            f"/intelligence/topics/{topic_id}/datasources/ds-a",
            headers=_authorized(),
        )
        assert resp.status_code == 200, resp.text
        assert resp.json() == []


def test_delete_remove_datasource_unknown_topic_404(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = InMemoryTopicDatasourceRepo()
    controller = _TopicApiFakeController(repo)
    with _build_topic_test_app(monkeypatch, controller) as client:
        resp = client.delete(
            "/intelligence/topics/nonexistent/datasources/ds-a",
            headers=_authorized(),
        )
        assert resp.status_code == 404, resp.text
        assert "unknown topic" in resp.json()["detail"].lower()


def test_delete_remove_unknown_datasource_noop(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = InMemoryTopicDatasourceRepo()
    topic_id = _make_topic(repo)
    controller = _TopicApiFakeController(repo)
    with _build_topic_test_app(monkeypatch, controller) as client:
        resp = client.delete(
            f"/intelligence/topics/{topic_id}/datasources/nonexistent",
            headers=_authorized(),
        )
        assert resp.status_code == 200, resp.text
        assert resp.json() == []


# ── POST /intelligence/topics with datasource_ids ─────────────────────


def test_create_topic_with_datasource_ids(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = InMemoryTopicDatasourceRepo()
    _make_intelligence_datasource(repo, "ds-a", name="Alpha")
    _make_intelligence_datasource(repo, "ds-b", name="Beta")
    controller = _TopicApiFakeController(repo)
    with _build_topic_test_app(monkeypatch, controller) as client:
        create_resp = client.post(
            "/intelligence/topics",
            headers=_authorized(),
            json={
                "theme": "BTC ETF fund flow analysis",
                "datasource_ids": ["ds-a", "ds-b"],
            },
        )
        assert create_resp.status_code == 201, create_resp.text
        topic_id = create_resp.json()["intelligence_topic_id"]

        # Verify associations exist
        ds_resp = client.get(
            f"/intelligence/topics/{topic_id}/datasources",
            headers=_authorized(),
        )
        assert ds_resp.status_code == 200, ds_resp.text
        data = ds_resp.json()
        assert len(data) == 2
        assert {d["id"] for d in data} == {"ds-a", "ds-b"}


def test_create_topic_without_datasource_ids(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = InMemoryTopicDatasourceRepo()
    controller = _TopicApiFakeController(repo)
    with _build_topic_test_app(monkeypatch, controller) as client:
        create_resp = client.post(
            "/intelligence/topics",
            headers=_authorized(),
            json={"theme": "BTC ETF fund flow analysis"},
        )
        assert create_resp.status_code == 201, create_resp.text
        topic_id = create_resp.json()["intelligence_topic_id"]

        ds_resp = client.get(
            f"/intelligence/topics/{topic_id}/datasources",
            headers=_authorized(),
        )
        assert ds_resp.status_code == 200, ds_resp.text
        assert ds_resp.json() == []


def test_create_topic_with_empty_datasource_ids(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = InMemoryTopicDatasourceRepo()
    controller = _TopicApiFakeController(repo)
    with _build_topic_test_app(monkeypatch, controller) as client:
        create_resp = client.post(
            "/intelligence/topics",
            headers=_authorized(),
            json={
                "theme": "BTC ETF fund flow analysis",
                "datasource_ids": [],
            },
        )
        assert create_resp.status_code == 201, create_resp.text
        topic_id = create_resp.json()["intelligence_topic_id"]

        ds_resp = client.get(
            f"/intelligence/topics/{topic_id}/datasources",
            headers=_authorized(),
        )
        assert ds_resp.status_code == 200, ds_resp.text
        assert ds_resp.json() == []


def test_create_topic_with_invalid_datasource_id(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = InMemoryTopicDatasourceRepo()
    controller = _TopicApiFakeController(repo)
    with _build_topic_test_app(monkeypatch, controller) as client:
        create_resp = client.post(
            "/intelligence/topics",
            headers=_authorized(),
            json={
                "theme": "BTC ETF fund flow analysis",
                "datasource_ids": ["nonexistent"],
            },
        )
        assert create_resp.status_code == 404, create_resp.text
        assert "unknown datasource" in create_resp.json()["detail"].lower()


def test_create_topic_with_news_datasource_id(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = InMemoryTopicDatasourceRepo()
    _make_news_datasource(repo, "ds-news", name="News DS")
    controller = _TopicApiFakeController(repo)
    with _build_topic_test_app(monkeypatch, controller) as client:
        create_resp = client.post(
            "/intelligence/topics",
            headers=_authorized(),
            json={
                "theme": "BTC ETF fund flow analysis",
                "datasource_ids": ["ds-news"],
            },
        )
        assert create_resp.status_code == 400, create_resp.text
        assert "not intelligence" in create_resp.json()["detail"].lower()


# ── Response safety: no config_payload ───────────────────────────────


def test_responses_never_expose_config_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = InMemoryTopicDatasourceRepo()
    topic_id = _make_topic(repo)
    _make_intelligence_datasource(repo, "ds-a", name="Alpha")
    repo.add_topic_datasources(topic_id, ["ds-a"])

    controller = _TopicApiFakeController(repo)
    with _build_topic_test_app(monkeypatch, controller) as client:
        get_resp = client.get(
            f"/intelligence/topics/{topic_id}/datasources",
            headers=_authorized(),
        )
        for item in get_resp.json():
            assert "config_payload" not in item
