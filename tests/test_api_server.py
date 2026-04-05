from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, TypedDict, cast
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from crypto_news_analyzer import api_server
from crypto_news_analyzer.domain.models import AnalysisRequest
from crypto_news_analyzer.models import StorageConfig
from crypto_news_analyzer.storage.data_manager import DataManager
from crypto_news_analyzer.storage.repositories import SQLiteAnalysisRepository


class _LoggedRow(TypedDict):
    chat_id: str
    time_window_hours: int
    items_count: int
    success: bool
    error_message: Optional[str]
    execution_time: datetime


class _CachedMessage(TypedDict):
    title: str
    body: str
    category: str
    time: str
    recipient_key: Optional[str]
    sent_at: datetime


def _authorized_headers() -> dict[str, str]:
    return {"Authorization": "Bearer test-api-key"}


def _analyze_request(hours: int = 1, user_id: str = "user-123") -> dict[str, object]:
    return {"hours": hours, "user_id": user_id}


class _FakeDataManager:
    def __init__(self):
        self.logged_rows: list[_LoggedRow] = []

    def log_analysis_execution(
        self,
        chat_id: str,
        time_window_hours: int,
        items_count: int,
        success: bool,
        error_message: Optional[str] = None,
    ) -> None:
        self.logged_rows.append(
            {
                "chat_id": chat_id,
                "time_window_hours": time_window_hours,
                "items_count": items_count,
                "success": success,
                "error_message": error_message,
                "execution_time": datetime.now(timezone.utc),
            }
        )

    def get_last_successful_analysis_time(self, chat_id: str) -> Optional[datetime]:
        for row in reversed(self.logged_rows):
            if row["chat_id"] == chat_id and row["success"]:
                return row["execution_time"]
        return None


class _FakeCacheManager:
    def __init__(self):
        self.cached_messages: list[_CachedMessage] = []

    def cache_sent_messages(
        self,
        messages: list[dict[str, object]],
        recipient_key: Optional[str] = None,
    ) -> int:
        sent_at = datetime.now(timezone.utc)
        for message in messages:
            self.cached_messages.append(
                {
                    "title": cast(str, message["title"]),
                    "body": cast(str, message["body"]),
                    "category": cast(str, message["category"]),
                    "time": cast(str, message["time"]),
                    "recipient_key": recipient_key,
                    "sent_at": sent_at,
                }
            )
        return len(messages)

    def get_recipient_cached_titles(self, recipient_key: str, anchor_time: datetime) -> list[str]:
        window_start = anchor_time - timedelta(hours=48)
        return [
            str(message["title"])
            for message in self.cached_messages
            if message["recipient_key"] == recipient_key
            and window_start <= message["sent_at"] <= anchor_time
        ]


class _FakeCommandHandler:
    def __init__(self, uses_webhook: bool = False):
        self._uses_webhook = uses_webhook
        self.initialize_webhook_called = False
        self.shutdown_webhook_called = False
        self.handled_updates: list[dict[str, object]] = []
        self.last_secret_token: Optional[str] = None

    def uses_webhook(self) -> bool:
        return self._uses_webhook

    async def initialize_webhook(self) -> str:
        self.initialize_webhook_called = True
        return "https://example.com/telegram/webhook"

    async def shutdown_webhook(self) -> None:
        self.shutdown_webhook_called = True

    async def handle_webhook_update(
        self,
        update_data: dict[str, object],
        secret_token: Optional[str] = None,
    ) -> None:
        if secret_token != "expected-secret":
            raise PermissionError("Invalid Telegram webhook secret token")
        self.last_secret_token = secret_token
        self.handled_updates.append(update_data)


class _FakeController:
    def __init__(
        self,
        analysis_repository: Optional[SQLiteAnalysisRepository] = None,
        command_handler: Optional[object] = None,
    ):
        self.analysis_repository = analysis_repository
        self.command_handler = command_handler
        self.data_manager = _FakeDataManager()
        self.cache_manager = _FakeCacheManager()
        self.analyze_calls: list[dict[str, object]] = []
        self.failed_user_ids: set[str] = set()

        self.config_manager = Mock()
        self.config_manager.get_analysis_config.return_value = {
            "max_analysis_window_hours": 24,
            "min_analysis_window_hours": 1,
        }

        self.initialize_system_called = False
        self.start_scheduler_called = False
        self.stop_scheduler_called = False
        self.start_command_listener_called = False
        self.stop_command_listener_called = False

    @staticmethod
    def _normalize_manual_recipient_key(manual_source: str, recipient_id: str) -> str:
        return f"{manual_source}:{str(recipient_id).strip()}"

    def initialize_system(self) -> bool:
        self.initialize_system_called = True
        return True

    def start_scheduler(self) -> None:
        self.start_scheduler_called = True

    def stop_scheduler(self) -> None:
        self.stop_scheduler_called = True

    def start_command_listener(self) -> None:
        self.start_command_listener_called = True

    def stop_command_listener(self) -> None:
        self.stop_command_listener_called = True

    def _record_manual_analysis_success(
        self,
        recipient_key: str,
        time_window_hours: int,
        items_count: int,
    ) -> None:
        self.data_manager.log_analysis_execution(
            chat_id=recipient_key,
            time_window_hours=time_window_hours,
            items_count=items_count,
            success=True,
        )

    def _persist_manual_analysis_success(
        self,
        recipient_key: str,
        time_window_hours: int,
        items_count: int,
        final_report_messages: Optional[list[dict[str, object]]] = None,
    ) -> None:
        if final_report_messages:
            self.cache_manager.cache_sent_messages(
                final_report_messages,
                recipient_key=recipient_key,
            )

        self._record_manual_analysis_success(
            recipient_key=recipient_key,
            time_window_hours=time_window_hours,
            items_count=items_count,
        )

    def analyze_by_time_window(
        self,
        chat_id: str,
        time_window_hours: int,
        manual_source: str = "telegram",
    ) -> dict[str, object]:
        recipient_key = self._normalize_manual_recipient_key(manual_source, chat_id)
        anchor_time = self.data_manager.get_last_successful_analysis_time(recipient_key)
        historical_titles = (
            self.cache_manager.get_recipient_cached_titles(recipient_key, anchor_time)
            if anchor_time is not None
            else []
        )
        self.analyze_calls.append(
            {
                "chat_id": chat_id,
                "manual_source": manual_source,
                "historical_titles": historical_titles,
            }
        )

        if chat_id in self.failed_user_ids:
            self.data_manager.log_analysis_execution(
                chat_id=recipient_key,
                time_window_hours=time_window_hours,
                items_count=0,
                success=False,
                error_message=f"forced failure for {chat_id}",
            )
            return {
                "success": False,
                "report_content": "",
                "items_processed": 0,
                "errors": [f"forced failure for {chat_id}"],
                "final_report_messages": [],
            }

        call_count = sum(1 for call in self.analyze_calls if call["chat_id"] == chat_id)
        title = f"title-{chat_id}-run-{call_count}"
        return {
            "success": True,
            "report_content": f"# Report {chat_id} run {call_count}",
            "items_processed": 1,
            "errors": [],
            "final_report_messages": [
                {
                    "title": title,
                    "body": f"body-{title}",
                    "category": "Test Category",
                    "time": "Fri, 27 Mar 2026 00:00:00 +0000",
                }
            ],
        }


@pytest.fixture(autouse=True)
def api_key_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("API_KEY", "test-api-key")


@pytest.fixture
def db_analysis_repository(tmp_path: Path):
    db_path = tmp_path / "api_server_jobs.db"
    data_manager = DataManager(StorageConfig(database_path=str(db_path)))
    repository = SQLiteAnalysisRepository(data_manager)
    yield {"repo": repository, "db_path": db_path, "manager": data_manager}
    data_manager.close()


def _build_test_app(
    monkeypatch: pytest.MonkeyPatch,
    controller: _FakeController,
    start_services: bool = False,
    start_scheduler: Optional[bool] = None,
    start_command_listener: Optional[bool] = None,
):
    monkeypatch.setattr(api_server, "MainController", lambda *_args, **_kwargs: controller)
    return api_server.create_api_server(
        "./config.json",
        start_services=start_services,
        start_scheduler=start_scheduler,
        start_command_listener=start_command_listener,
    )


def _enqueue_and_run_job(
    client: TestClient,
    user_id: str,
    monkeypatch: pytest.MonkeyPatch,
) -> str:
    app_state = client.app.state.app_state
    monkeypatch.setattr(app_state.analyze_executor, "submit", lambda *_args, **_kwargs: None)
    response = client.post(
        "/analyze",
        headers=_authorized_headers(),
        json=_analyze_request(hours=1, user_id=user_id),
    )
    assert response.status_code == 202
    job_id = response.json()["job_id"]
    api_server._run_analyze_job(job_id, app_state)
    return job_id


def test_health_check_reports_initialized_state(monkeypatch: pytest.MonkeyPatch):
    app = _build_test_app(monkeypatch, _FakeController())

    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy", "initialized": True}


def test_analyze_requires_valid_api_key(monkeypatch: pytest.MonkeyPatch):
    app = _build_test_app(monkeypatch, _FakeController())

    with TestClient(app) as client:
        response = client.post("/analyze", json=_analyze_request(hours=1))

    assert response.status_code == 401


def test_analyze_returns_service_unavailable_when_controller_missing(
    monkeypatch: pytest.MonkeyPatch,
):
    app = _build_test_app(monkeypatch, _FakeController())

    with TestClient(app) as client:
        client.app.state.app_state.controller = None
        response = client.post(
            "/analyze",
            headers=_authorized_headers(),
            json=_analyze_request(hours=1),
        )

    assert response.status_code == 503
    assert response.json() == {"detail": "System not initialized"}


def test_analyze_caps_requested_window_and_enqueues_job(monkeypatch: pytest.MonkeyPatch):
    app = _build_test_app(monkeypatch, _FakeController())
    captured: dict[str, object] = {}

    def _fake_enqueue(hours: int, user_id: str, state: api_server.AppState) -> api_server.AnalyzeJobRecord:
        captured["hours"] = hours
        captured["user_id"] = user_id
        captured["controller_matches_state"] = state.controller is not None
        return api_server.AnalyzeJobRecord(
            job_id="job-123",
            user_id=user_id,
            status="queued",
            time_window_hours=hours,
            created_at="2026-03-26T00:00:00+00:00",
        )

    monkeypatch.setattr(api_server, "enqueue_analyze_job", _fake_enqueue)

    with TestClient(app) as client:
        response = client.post(
            "/analyze",
            headers=_authorized_headers(),
            json=_analyze_request(hours=72, user_id="  user_123  "),
        )

    assert response.status_code == 202
    assert captured == {
        "hours": 24,
        "user_id": "user_123",
        "controller_matches_state": True,
    }
    assert response.json() == {
        "success": True,
        "job_id": "job-123",
        "status": "queued",
        "time_window_hours": 24,
        "status_url": "/analyze/job-123",
        "result_url": "/analyze/job-123/result",
    }


def test_analyze_rejects_request_below_min_window(monkeypatch: pytest.MonkeyPatch):
    fake_controller = _FakeController()
    fake_controller.config_manager.get_analysis_config.return_value = {
        "max_analysis_window_hours": 24,
        "min_analysis_window_hours": 2,
    }
    app = _build_test_app(monkeypatch, fake_controller)

    with TestClient(app) as client:
        response = client.post(
            "/analyze",
            headers=_authorized_headers(),
            json=_analyze_request(hours=1),
        )

    assert response.status_code == 400
    assert response.json() == {"detail": "Hours must be at least 2"}


def test_analyze_status_returns_job_state(
    monkeypatch: pytest.MonkeyPatch,
    db_analysis_repository,
):
    repo = cast(SQLiteAnalysisRepository, db_analysis_repository["repo"])
    repo.save(
        AnalysisRequest(
            id="job-123",
            recipient_key="api:user-123",
            time_window_hours=6,
            created_at=datetime.fromisoformat("2026-03-26T00:00:00+00:00"),
            status="running",
            started_at=datetime.fromisoformat("2026-03-26T00:00:03+00:00"),
            source="api",
        )
    )

    app = _build_test_app(monkeypatch, _FakeController(analysis_repository=repo))
    with TestClient(app) as client:
        response = client.get("/analyze/job-123", headers=_authorized_headers())

    assert response.status_code == 200
    assert response.json() == {
        "success": False,
        "job_id": "job-123",
        "status": "running",
        "time_window_hours": 6,
        "created_at": "2026-03-26T00:00:00+00:00",
        "started_at": "2026-03-26T00:00:03+00:00",
        "completed_at": None,
        "items_processed": 0,
        "error": None,
        "result_available": False,
    }


def test_analyze_result_returns_queued_payload(
    monkeypatch: pytest.MonkeyPatch,
    db_analysis_repository,
):
    repo = cast(SQLiteAnalysisRepository, db_analysis_repository["repo"])
    repo.save(
        AnalysisRequest(
            id="job-123",
            recipient_key="api:user-123",
            time_window_hours=2,
            created_at=datetime.fromisoformat("2026-03-26T00:00:00+00:00"),
            status="queued",
            source="api",
        )
    )
    app = _build_test_app(monkeypatch, _FakeController(analysis_repository=repo))

    with TestClient(app) as client:
        response = client.get("/analyze/job-123/result", headers=_authorized_headers())

    assert response.status_code == 200
    assert response.json() == {
        "success": False,
        "job_id": "job-123",
        "status": "queued",
        "report": "",
        "items_processed": 0,
        "time_window_hours": 2,
        "error": None,
    }


def test_analyze_result_returns_completed_payload(
    monkeypatch: pytest.MonkeyPatch,
    db_analysis_repository,
):
    repo = cast(SQLiteAnalysisRepository, db_analysis_repository["repo"])
    repo.save(
        AnalysisRequest(
            id="job-123",
            recipient_key="api:user-123",
            time_window_hours=2,
            created_at=datetime.fromisoformat("2026-03-26T00:00:00+00:00"),
            status="completed",
            started_at=datetime.fromisoformat("2026-03-26T00:00:03+00:00"),
            completed_at=datetime.fromisoformat("2026-03-26T00:01:00+00:00"),
            result={
                "success": True,
                "report_content": "# Report",
                "items_processed": 3,
                "errors": [],
                "final_report_messages": [],
                "success_persisted": True,
            },
            source="api",
        )
    )
    app = _build_test_app(monkeypatch, _FakeController(analysis_repository=repo))

    with TestClient(app) as client:
        response = client.get("/analyze/job-123/result", headers=_authorized_headers())

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "job_id": "job-123",
        "status": "completed",
        "report": "# Report",
        "items_processed": 3,
        "time_window_hours": 2,
        "error": None,
    }


@pytest.mark.parametrize("user_id", ["", "   ", "has space", "user!", "中文", "a" * 129])
def test_analyze_user_id_invalid_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
    user_id: str,
):
    app = _build_test_app(monkeypatch, _FakeController())

    with TestClient(app) as client:
        response = client.post(
            "/analyze",
            headers=_authorized_headers(),
            json=_analyze_request(hours=1, user_id=user_id),
        )

    assert response.status_code == 422
    assert any(error["loc"] == ["body", "user_id"] for error in response.json()["detail"])


def test_analyze_user_id_same_user_reuses_its_own_dedup_context(
    monkeypatch: pytest.MonkeyPatch,
    db_analysis_repository,
):
    repo = cast(SQLiteAnalysisRepository, db_analysis_repository["repo"])
    fake_controller = _FakeController(analysis_repository=repo)
    app = _build_test_app(monkeypatch, fake_controller)

    with TestClient(app) as client:
        first_job_id = _enqueue_and_run_job(client, "same-user", monkeypatch)
        first_result = client.get(f"/analyze/{first_job_id}/result", headers=_authorized_headers())
        assert first_result.status_code == 200

        second_job_id = _enqueue_and_run_job(client, "same-user", monkeypatch)

        assert fake_controller.analyze_calls[0]["chat_id"] == "same-user"
        assert fake_controller.analyze_calls[0]["manual_source"] == "api"
        assert fake_controller.analyze_calls[0]["historical_titles"] == []
        assert fake_controller.analyze_calls[1]["historical_titles"] == ["title-same-user-run-1"]

        second_result = client.get(f"/analyze/{second_job_id}/result", headers=_authorized_headers())
        assert second_result.status_code == 200


def test_analyze_user_id_different_users_remain_isolated(
    monkeypatch: pytest.MonkeyPatch,
    db_analysis_repository,
):
    repo = cast(SQLiteAnalysisRepository, db_analysis_repository["repo"])
    fake_controller = _FakeController(analysis_repository=repo)
    app = _build_test_app(monkeypatch, fake_controller)

    with TestClient(app) as client:
        first_job_id = _enqueue_and_run_job(client, "user-a", monkeypatch)
        first_result = client.get(f"/analyze/{first_job_id}/result", headers=_authorized_headers())
        assert first_result.status_code == 200

        second_job_id = _enqueue_and_run_job(client, "user-b", monkeypatch)

        assert fake_controller.analyze_calls[0]["historical_titles"] == []
        assert fake_controller.analyze_calls[1]["historical_titles"] == []

        second_result = client.get(f"/analyze/{second_job_id}/result", headers=_authorized_headers())
        assert second_result.status_code == 200
        assert [message["recipient_key"] for message in fake_controller.cache_manager.cached_messages] == [
            "api:user-a",
            "api:user-b",
        ]


def test_analyze_user_id_failed_job_does_not_write_success_history_or_cache(
    monkeypatch: pytest.MonkeyPatch,
    db_analysis_repository,
):
    repo = cast(SQLiteAnalysisRepository, db_analysis_repository["repo"])
    fake_controller = _FakeController(analysis_repository=repo)
    fake_controller.failed_user_ids.add("broken-user")
    app = _build_test_app(monkeypatch, fake_controller)

    with TestClient(app) as client:
        failed_job_id = _enqueue_and_run_job(client, "broken-user", monkeypatch)
        failed_result = client.get(f"/analyze/{failed_job_id}/result", headers=_authorized_headers())

    assert failed_result.status_code == 200
    assert failed_result.json()["success"] is False
    assert fake_controller.cache_manager.cached_messages == []
    assert [row["success"] for row in fake_controller.data_manager.logged_rows] == [False]


def test_analyze_job_persists_across_repository_reinitialization(
    monkeypatch: pytest.MonkeyPatch,
    db_analysis_repository,
):
    repo = cast(SQLiteAnalysisRepository, db_analysis_repository["repo"])
    fake_controller = _FakeController(analysis_repository=repo)
    app = _build_test_app(monkeypatch, fake_controller)

    with TestClient(app) as client:
        app_state = client.app.state.app_state
        monkeypatch.setattr(app_state.analyze_executor, "submit", lambda *_args, **_kwargs: None)

        accepted = client.post(
            "/analyze",
            headers=_authorized_headers(),
            json=_analyze_request(hours=1, user_id="persist-user"),
        )
        assert accepted.status_code == 202
        job_id = accepted.json()["job_id"]

        db_path = cast(Path, db_analysis_repository["db_path"])
        restart_manager = DataManager(StorageConfig(database_path=str(db_path)))
        restart_repo = SQLiteAnalysisRepository(restart_manager)
        client.app.state.app_state.analysis_repository = restart_repo

        status_response = client.get(f"/analyze/{job_id}", headers=_authorized_headers())
        assert status_response.status_code == 200
        assert status_response.json()["job_id"] == job_id
        assert status_response.json()["status"] == "queued"

        api_server._run_analyze_job(job_id, client.app.state.app_state)
        result_response = client.get(f"/analyze/{job_id}/result", headers=_authorized_headers())
        assert result_response.status_code == 200
        assert result_response.json()["success"] is True

        restart_manager.close()


def test_create_api_server_lifespan_starts_requested_services_and_cleans_up(
    monkeypatch: pytest.MonkeyPatch,
):
    fake_controller = _FakeController(command_handler=_FakeCommandHandler())
    app = _build_test_app(
        monkeypatch,
        fake_controller,
        start_services=False,
        start_scheduler=False,
        start_command_listener=True,
    )

    with TestClient(app):
        pass

    assert fake_controller.initialize_system_called is True
    assert fake_controller.start_scheduler_called is False
    assert fake_controller.start_command_listener_called is True
    assert fake_controller.stop_scheduler_called is True
    assert fake_controller.stop_command_listener_called is True


def test_create_api_server_lifespan_keeps_scheduler_and_listener_disabled_when_start_services_false(
    monkeypatch: pytest.MonkeyPatch,
):
    fake_controller = _FakeController(command_handler=_FakeCommandHandler())
    app = _build_test_app(
        monkeypatch,
        fake_controller,
        start_services=False,
    )

    with TestClient(app):
        pass

    assert fake_controller.initialize_system_called is True
    assert fake_controller.start_scheduler_called is False
    assert fake_controller.start_command_listener_called is False
    assert fake_controller.stop_scheduler_called is True
    assert fake_controller.stop_command_listener_called is True


def test_create_api_server_lifespan_prefers_telegram_webhook_when_available(
    monkeypatch: pytest.MonkeyPatch,
):
    fake_handler = _FakeCommandHandler(uses_webhook=True)
    fake_controller = _FakeController(command_handler=fake_handler)
    app = _build_test_app(
        monkeypatch,
        fake_controller,
        start_services=False,
        start_scheduler=False,
        start_command_listener=True,
    )

    with TestClient(app):
        pass

    assert fake_controller.initialize_system_called is True
    assert fake_controller.start_command_listener_called is False
    assert fake_handler.initialize_webhook_called is True
    assert fake_handler.shutdown_webhook_called is True
    assert fake_controller.stop_command_listener_called is False


def test_telegram_webhook_endpoint_passes_update_to_handler(
    monkeypatch: pytest.MonkeyPatch,
):
    fake_handler = _FakeCommandHandler(uses_webhook=True)
    fake_controller = _FakeController(command_handler=fake_handler)
    monkeypatch.setenv("TELEGRAM_WEBHOOK_PATH", "/telegram/webhook")
    app = _build_test_app(monkeypatch, fake_controller)

    with TestClient(app) as client:
        response = client.post(
            "/telegram/webhook",
            headers={"X-Telegram-Bot-Api-Secret-Token": "expected-secret"},
            json={"update_id": 123},
        )

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert fake_handler.handled_updates == [{"update_id": 123}]
    assert fake_handler.last_secret_token == "expected-secret"


def test_telegram_webhook_endpoint_rejects_invalid_secret(
    monkeypatch: pytest.MonkeyPatch,
):
    fake_handler = _FakeCommandHandler(uses_webhook=True)
    fake_controller = _FakeController(command_handler=fake_handler)
    monkeypatch.setenv("TELEGRAM_WEBHOOK_PATH", "/telegram/webhook")
    app = _build_test_app(monkeypatch, fake_controller)

    with TestClient(app) as client:
        response = client.post(
            "/telegram/webhook",
            headers={"X-Telegram-Bot-Api-Secret-Token": "wrong-secret"},
            json={"update_id": 123},
        )

    assert response.status_code == 403
    assert response.json() == {"detail": "Invalid Telegram webhook secret token"}
