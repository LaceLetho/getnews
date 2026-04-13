from datetime import datetime
from types import SimpleNamespace
from typing import Optional, cast

import pytest
from fastapi.testclient import TestClient

from crypto_news_analyzer import api_server
from crypto_news_analyzer.domain.models import SemanticSearchJob
from crypto_news_analyzer.models import SemanticSearchConfig, StorageConfig


def _authorized_headers() -> dict[str, str]:
    return {"Authorization": "Bearer test-api-key"}


def _semantic_search_request(
    hours: int = 1,
    query: str = "btc etf flows",
    user_id: str = "operator_01",
) -> dict[str, object]:
    return {"hours": hours, "query": query, "user_id": user_id}


class _InMemorySemanticSearchRepository:
    def __init__(self):
        self.jobs: dict[str, SemanticSearchJob] = {}

    def create_semantic_search_job(self, job: SemanticSearchJob) -> None:
        self.jobs[job.id] = SemanticSearchJob.from_dict(job.to_dict())

    def update_semantic_search_job(self, job: SemanticSearchJob) -> bool:
        if job.id not in self.jobs:
            return False
        self.jobs[job.id] = SemanticSearchJob.from_dict(job.to_dict())
        return True

    def get_by_id(self, job_id: str) -> Optional[SemanticSearchJob]:
        job = self.jobs.get(job_id)
        if job is None:
            return None
        return SemanticSearchJob.from_dict(job.to_dict())

    def get_by_recipient(
        self,
        recipient_key: str,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> list[SemanticSearchJob]:
        rows = [
            SemanticSearchJob.from_dict(job.to_dict())
            for job in self.jobs.values()
            if job.recipient_key == recipient_key
            and (status is None or job.status == status)
        ]
        return rows[:limit]


class _FakeController:
    def __init__(
        self,
        *,
        backend: str = "postgres",
        semantic_search_repository: Optional[_InMemorySemanticSearchRepository] = None,
    ):
        self.analysis_repository = None
        self.datasource_repository = None
        self.semantic_search_repository = semantic_search_repository
        self.command_handler = None
        self.content_repository = object()
        self.embedding_service = SimpleNamespace(enabled=True)
        self.data_manager = None
        self._repositories = (
            {"semantic_search": semantic_search_repository}
            if semantic_search_repository is not None
            else {}
        )

        self.config_manager = SimpleNamespace(
            get_analysis_config=lambda: {
                "max_analysis_window_hours": 24,
                "min_analysis_window_hours": 1,
            },
            get_semantic_search_config=lambda: SemanticSearchConfig(),
            get_storage_config=lambda: StorageConfig(
                backend=backend,
                database_path=":memory:" if backend == "sqlite" else "./unused.db",
                database_url=(
                    "postgresql://postgres:password@localhost:5432/crypto_news"
                    if backend == "postgres"
                    else None
                ),
            ),
            get_auth_config=lambda: SimpleNamespace(
                GROK_API_KEY="grok-key",
                KIMI_API_KEY="kimi-key",
                OPENCODE_API_KEY="opencode-key",
            ),
            config_data={
                "llm_config": {
                    "model": {"provider": "kimi", "name": "kimi-k2.5", "options": {}},
                    "fallback_models": [
                        {
                            "provider": "grok",
                            "name": "grok-4-1-fast-reasoning",
                            "options": {},
                        }
                    ],
                    "market_model": {
                        "provider": "grok",
                        "name": "grok-4-1-fast-reasoning",
                        "options": {},
                    },
                }
            },
        )

    @staticmethod
    def _normalize_manual_recipient_key(manual_source: str, recipient_id: str) -> str:
        return f"{manual_source}:{str(recipient_id).strip()}"

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


class _FakeSemanticSearchService:
    def __init__(
        self,
        *,
        result: Optional[dict[str, object]] = None,
        error: Optional[Exception] = None,
    ):
        self.result = result or {}
        self.error = error
        self.calls: list[dict[str, object]] = []

    def search(self, *, query: str, time_window_hours: int) -> dict[str, object]:
        self.calls.append({"query": query, "time_window_hours": time_window_hours})
        if self.error is not None:
            raise self.error
        return self.result


@pytest.fixture(autouse=True)
def api_key_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("API_KEY", "test-api-key")


def _build_test_app(
    monkeypatch: pytest.MonkeyPatch,
    controller: _FakeController,
):
    monkeypatch.setattr(
        api_server, "MainController", lambda *_args, **_kwargs: controller
    )
    return api_server.create_api_server("./config.json", start_services=False)


def _app_state(client: TestClient) -> api_server.AppState:
    app = cast(object, client.app)
    state = getattr(app, "state")
    return cast(api_server.AppState, getattr(state, "app_state"))


def _make_job(
    *,
    job_id: str,
    status: str,
    query: str = "btc etf flows",
    normalized_intent: str = "btc etf flows",
    matched_count: int = 0,
    retained_count: int = 0,
    report: str = "",
    error_message: Optional[str] = None,
) -> SemanticSearchJob:
    created_at = datetime.fromisoformat("2026-03-26T00:00:00+00:00")
    started_at = (
        datetime.fromisoformat("2026-03-26T00:00:05+00:00")
        if status != "queued"
        else None
    )
    completed_at = (
        datetime.fromisoformat("2026-03-26T00:01:00+00:00")
        if status in {"completed", "failed"}
        else None
    )
    errors = [error_message] if error_message else []
    result = {
        "success": status == "completed",
        "report_content": report,
        "errors": errors,
    }
    return SemanticSearchJob(
        id=job_id,
        recipient_key="api:operator_01",
        query=query,
        normalized_intent=normalized_intent,
        time_window_hours=6,
        created_at=created_at,
        status=status,
        matched_count=matched_count,
        retained_count=retained_count,
        started_at=started_at,
        completed_at=completed_at,
        result=result,
        error_message=error_message,
        source="api",
    )


def test_post_semantic_search_returns_202_and_uses_dedicated_executor(
    monkeypatch: pytest.MonkeyPatch,
):
    repository = _InMemorySemanticSearchRepository()
    app = _build_test_app(
        monkeypatch,
        _FakeController(semantic_search_repository=repository),
    )

    with TestClient(app) as client:
        app_state = _app_state(client)
        analyze_calls: list[tuple[tuple[object, ...], dict[str, object]]] = []
        semantic_calls: list[tuple[tuple[object, ...], dict[str, object]]] = []
        monkeypatch.setattr(
            app_state.analyze_executor,
            "submit",
            lambda *args, **kwargs: analyze_calls.append((args, kwargs)),
        )
        monkeypatch.setattr(
            app_state.semantic_search_executor,
            "submit",
            lambda *args, **kwargs: semantic_calls.append((args, kwargs)),
        )

        response = client.post(
            "/semantic-search",
            headers=_authorized_headers(),
            json=_semantic_search_request(query="  btc etf flows  "),
        )

    assert response.status_code == 202
    payload = response.json()
    assert payload == {
        "success": True,
        "job_id": payload["job_id"],
        "status": "queued",
        "query": "btc etf flows",
        "normalized_intent": "",
        "matched_count": 0,
        "retained_count": 0,
        "time_window_hours": 1,
        "status_url": f"/semantic-search/{payload['job_id']}",
        "result_url": f"/semantic-search/{payload['job_id']}/result",
    }
    assert payload["job_id"].startswith("semantic_search_job_")
    assert response.headers["Location"] == payload["status_url"]
    assert response.headers["Retry-After"] == "5"
    assert analyze_calls == []
    assert len(semantic_calls) == 1
    assert semantic_calls[0][0][0] is api_server._run_semantic_search_job

    stored_job = repository.get_by_id(payload["job_id"])
    assert stored_job is not None
    assert stored_job.status == "queued"
    assert stored_job.query == "btc etf flows"
    assert stored_job.recipient_key == "api:operator_01"


@pytest.mark.parametrize("status", ["queued", "running", "completed", "failed"])
def test_semantic_search_status_endpoint_returns_expected_status(
    monkeypatch: pytest.MonkeyPatch,
    status: str,
):
    repository = _InMemorySemanticSearchRepository()
    repository.create_semantic_search_job(
        _make_job(
            job_id=f"semantic_search_job_{status}",
            status=status,
            normalized_intent="btc spot etf flows",
            matched_count=9,
            retained_count=4,
            error_message="planner failed" if status == "failed" else None,
        )
    )
    app = _build_test_app(
        monkeypatch,
        _FakeController(semantic_search_repository=repository),
    )

    with TestClient(app) as client:
        response = client.get(
            f"/semantic-search/semantic_search_job_{status}",
            headers=_authorized_headers(),
        )

    assert response.status_code == 200
    assert response.json() == {
        "success": status == "completed",
        "job_id": f"semantic_search_job_{status}",
        "status": status,
        "query": "btc etf flows",
        "normalized_intent": "btc spot etf flows",
        "matched_count": 9,
        "retained_count": 4,
        "time_window_hours": 6,
        "created_at": "2026-03-26T00:00:00+00:00",
        "started_at": None if status == "queued" else "2026-03-26T00:00:05+00:00",
        "completed_at": (
            "2026-03-26T00:01:00+00:00" if status in {"completed", "failed"} else None
        ),
        "error": "planner failed" if status == "failed" else None,
        "result_available": status in {"completed", "failed"},
    }


@pytest.mark.parametrize(
    ("status", "report", "error_message", "expected_success"),
    [
        ("completed", "# Semantic report", None, True),
        ("failed", "", "planner failed", False),
    ],
)
def test_semantic_search_result_endpoint_returns_success_and_failure_payloads(
    monkeypatch: pytest.MonkeyPatch,
    status: str,
    report: str,
    error_message: Optional[str],
    expected_success: bool,
):
    repository = _InMemorySemanticSearchRepository()
    repository.create_semantic_search_job(
        _make_job(
            job_id=f"semantic_search_job_result_{status}",
            status=status,
            normalized_intent="btc spot etf flows",
            matched_count=11,
            retained_count=5,
            report=report,
            error_message=error_message,
        )
    )
    app = _build_test_app(
        monkeypatch,
        _FakeController(semantic_search_repository=repository),
    )

    with TestClient(app) as client:
        response = client.get(
            f"/semantic-search/semantic_search_job_result_{status}/result",
            headers=_authorized_headers(),
        )

    assert response.status_code == 200
    assert response.json() == {
        "success": expected_success,
        "job_id": f"semantic_search_job_result_{status}",
        "status": status,
        "query": "btc etf flows",
        "normalized_intent": "btc spot etf flows",
        "matched_count": 11,
        "retained_count": 5,
        "report": report,
        "time_window_hours": 6,
        "error": error_message,
    }


def test_run_semantic_search_job_persists_completed_lifecycle(
    monkeypatch: pytest.MonkeyPatch,
):
    repository = _InMemorySemanticSearchRepository()
    controller = _FakeController(semantic_search_repository=repository)
    service = _FakeSemanticSearchService(
        result={
            "report_content": "# Semantic report",
            "normalized_intent": "bitcoin etf fund flows",
            "matched_count": 12,
            "retained_count": 6,
            "subqueries": ["btc etf flows", "bitcoin etf inflows"],
        }
    )
    app = _build_test_app(monkeypatch, controller)
    monkeypatch.setattr(
        api_server, "_build_semantic_search_service", lambda *_args: service
    )

    with TestClient(app) as client:
        app_state = _app_state(client)
        monkeypatch.setattr(
            app_state.semantic_search_executor, "submit", lambda *_args, **_kwargs: None
        )
        accepted = client.post(
            "/semantic-search",
            headers=_authorized_headers(),
            json=_semantic_search_request(hours=4, query="btc etf flows"),
        )
        job_id = accepted.json()["job_id"]

        api_server._run_semantic_search_job(job_id, app_state)

        status_response = client.get(
            f"/semantic-search/{job_id}", headers=_authorized_headers()
        )
        result_response = client.get(
            f"/semantic-search/{job_id}/result",
            headers=_authorized_headers(),
        )

    assert accepted.status_code == 202
    assert service.calls == [{"query": "btc etf flows", "time_window_hours": 4}]
    assert status_response.json()["status"] == "completed"
    assert status_response.json()["result_available"] is True
    assert result_response.json() == {
        "success": True,
        "job_id": job_id,
        "status": "completed",
        "query": "btc etf flows",
        "normalized_intent": "bitcoin etf fund flows",
        "matched_count": 12,
        "retained_count": 6,
        "report": "# Semantic report",
        "time_window_hours": 4,
        "error": None,
    }


def test_run_semantic_search_job_persists_failed_lifecycle(
    monkeypatch: pytest.MonkeyPatch,
):
    repository = _InMemorySemanticSearchRepository()
    controller = _FakeController(semantic_search_repository=repository)
    service = _FakeSemanticSearchService(error=RuntimeError("planner exploded"))
    app = _build_test_app(monkeypatch, controller)
    monkeypatch.setattr(
        api_server, "_build_semantic_search_service", lambda *_args: service
    )

    with TestClient(app) as client:
        app_state = _app_state(client)
        monkeypatch.setattr(
            app_state.semantic_search_executor, "submit", lambda *_args, **_kwargs: None
        )
        accepted = client.post(
            "/semantic-search",
            headers=_authorized_headers(),
            json=_semantic_search_request(query="btc etf flows"),
        )
        job_id = accepted.json()["job_id"]

        api_server._run_semantic_search_job(job_id, app_state)

        status_response = client.get(
            f"/semantic-search/{job_id}", headers=_authorized_headers()
        )
        result_response = client.get(
            f"/semantic-search/{job_id}/result",
            headers=_authorized_headers(),
        )

    assert accepted.status_code == 202
    assert status_response.json()["status"] == "failed"
    assert status_response.json()["error"] == "planner exploded"
    assert result_response.json() == {
        "success": False,
        "job_id": job_id,
        "status": "failed",
        "query": "btc etf flows",
        "normalized_intent": "",
        "matched_count": 0,
        "retained_count": 0,
        "report": "",
        "time_window_hours": 1,
        "error": "planner exploded",
    }


def test_semantic_search_rejects_blank_query(monkeypatch: pytest.MonkeyPatch):
    repository = _InMemorySemanticSearchRepository()
    app = _build_test_app(
        monkeypatch,
        _FakeController(semantic_search_repository=repository),
    )

    with TestClient(app) as client:
        response = client.post(
            "/semantic-search",
            headers=_authorized_headers(),
            json=_semantic_search_request(query="   "),
        )

    assert response.status_code == 422
    assert any(error["loc"] == ["body", "query"] for error in response.json()["detail"])


def test_semantic_search_returns_503_for_sqlite_backend(
    monkeypatch: pytest.MonkeyPatch,
):
    app = _build_test_app(monkeypatch, _FakeController(backend="sqlite"))

    with TestClient(app) as client:
        response = client.post(
            "/semantic-search",
            headers=_authorized_headers(),
            json=_semantic_search_request(),
        )

    assert response.status_code == 503
    assert response.json() == {"detail": "Semantic search requires postgres backend"}
