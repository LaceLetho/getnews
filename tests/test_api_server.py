import os
from datetime import datetime, timedelta, timezone
from typing import TypedDict, cast
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from crypto_news_analyzer import api_server


class _LoggedRow(TypedDict):
    chat_id: str
    time_window_hours: int
    items_count: int
    success: bool
    error_message: str | None
    execution_time: datetime


class _CachedMessage(TypedDict):
    title: str
    body: str
    category: str
    time: str
    recipient_key: str | None
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
        error_message: str | None = None,
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

    def get_last_successful_analysis_time(self, chat_id: str) -> datetime | None:
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
        recipient_key: str | None = None,
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


class _FakeController:
    def __init__(self):
        self.data_manager = _FakeDataManager()
        self.cache_manager = _FakeCacheManager()
        self.analyze_calls: list[dict[str, object]] = []
        self.failed_user_ids: set[str] = set()
        self.config_manager = Mock()
        self.config_manager.get_analysis_config.return_value = {
            "max_analysis_window_hours": 24,
            "min_analysis_window_hours": 1,
        }

    @staticmethod
    def _normalize_manual_recipient_key(manual_source: str, recipient_id: str) -> str:
        return f"{manual_source}:{str(recipient_id).strip()}"

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
        final_report_messages: list[dict[str, object]] | None = None,
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


def _enqueue_and_run_job(client: TestClient, user_id: str, monkeypatch: pytest.MonkeyPatch) -> str:
    monkeypatch.setattr(api_server.analyze_executor, "submit", lambda *args, **kwargs: None)
    response = client.post(
        "/analyze",
        headers=_authorized_headers(),
        json=_analyze_request(hours=1, user_id=user_id),
    )
    assert response.status_code == 202
    job_id = response.json()["job_id"]
    api_server._run_analyze_job(job_id)
    return job_id


def test_health_check_reports_initialized_state(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(api_server, "controller", object())
    client = TestClient(api_server.app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy", "initialized": True}


def test_analyze_requires_valid_api_key(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("API_KEY", "test-api-key")
    monkeypatch.setattr(api_server, "controller", object())
    client = TestClient(api_server.app)

    response = client.post("/analyze", json=_analyze_request(hours=1))

    assert response.status_code == 401


def test_analyze_returns_service_unavailable_when_controller_missing(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("API_KEY", "test-api-key")
    monkeypatch.setattr(api_server, "controller", None)
    client = TestClient(api_server.app)

    response = client.post(
        "/analyze",
        headers=_authorized_headers(),
        json=_analyze_request(hours=1),
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "System not initialized"}


def test_analyze_caps_requested_window_and_enqueues_job(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("API_KEY", "test-api-key")

    mock_controller = Mock()
    mock_controller.config_manager = Mock()
    mock_controller.config_manager.get_analysis_config.return_value = {
        "max_analysis_window_hours": 24,
        "min_analysis_window_hours": 1,
    }

    monkeypatch.setattr(api_server, "controller", mock_controller)
    captured: dict[str, object] = {}

    def _fake_enqueue(hours: int, user_id: str) -> api_server.AnalyzeJobRecord:
        captured["hours"] = hours
        captured["user_id"] = user_id
        return api_server.AnalyzeJobRecord(
            job_id="job-123",
            user_id=user_id,
            status="queued",
            time_window_hours=hours,
            created_at="2026-03-26T00:00:00+00:00",
        )

    monkeypatch.setattr(api_server, "enqueue_analyze_job", _fake_enqueue)
    client = TestClient(api_server.app)

    response = client.post(
        "/analyze",
        headers=_authorized_headers(),
        json=_analyze_request(hours=72, user_id="  user_123  "),
    )

    assert response.status_code == 202
    assert captured == {"hours": 24, "user_id": "user_123"}
    assert response.json() == {
        "success": True,
        "job_id": "job-123",
        "status": "queued",
        "time_window_hours": 24,
        "status_url": "/analyze/job-123",
        "result_url": "/analyze/job-123/result",
    }


def test_analyze_rejects_request_below_min_window(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("API_KEY", "test-api-key")

    mock_controller = Mock()
    mock_controller.config_manager = Mock()
    mock_controller.config_manager.get_analysis_config.return_value = {
        "max_analysis_window_hours": 24,
        "min_analysis_window_hours": 2,
    }

    monkeypatch.setattr(api_server, "controller", mock_controller)
    client = TestClient(api_server.app)

    response = client.post(
        "/analyze",
        headers=_authorized_headers(),
        json=_analyze_request(hours=1),
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Hours must be at least 2"}
    mock_controller.analyze_by_time_window.assert_not_called()


def test_analyze_status_returns_job_state(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("API_KEY", "test-api-key")
    monkeypatch.setattr(api_server, "controller", object())
    api_server.analyze_jobs["job-123"] = api_server.AnalyzeJobRecord(
        job_id="job-123",
        user_id="user-123",
        status="running",
        time_window_hours=6,
        created_at="2026-03-26T00:00:00+00:00",
        started_at="2026-03-26T00:00:03+00:00",
    )
    client = TestClient(api_server.app)

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


def test_analyze_result_returns_pending_status(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("API_KEY", "test-api-key")
    monkeypatch.setattr(api_server, "controller", object())
    api_server.analyze_jobs["job-123"] = api_server.AnalyzeJobRecord(
        job_id="job-123",
        user_id="user-123",
        status="queued",
        time_window_hours=2,
        created_at="2026-03-26T00:00:00+00:00",
    )
    client = TestClient(api_server.app)

    response = client.get("/analyze/job-123/result", headers=_authorized_headers())

    assert response.status_code == 202
    assert response.json() == {"detail": "Analyze job still queued"}


def test_analyze_result_returns_completed_payload(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("API_KEY", "test-api-key")
    monkeypatch.setattr(api_server, "controller", object())
    api_server.analyze_jobs["job-123"] = api_server.AnalyzeJobRecord(
        job_id="job-123",
        user_id="user-123",
        status="completed",
        time_window_hours=2,
        created_at="2026-03-26T00:00:00+00:00",
        started_at="2026-03-26T00:00:03+00:00",
        completed_at="2026-03-26T00:01:00+00:00",
        report="# Report",
        items_processed=3,
        success_persisted=True,
    )
    client = TestClient(api_server.app)

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


def test_analyze_validates_positive_hours(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("API_KEY", "test-api-key")
    monkeypatch.setattr(api_server, "controller", object())
    client = TestClient(api_server.app)

    response = client.post(
        "/analyze",
        headers=_authorized_headers(),
        json=_analyze_request(hours=0),
    )

    assert response.status_code == 422
    assert any(
        error["loc"] == ["body", "hours"]
        for error in response.json()["detail"]
    )


def test_analyze_user_id_missing_is_rejected(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("API_KEY", "test-api-key")
    monkeypatch.setattr(api_server, "controller", object())
    client = TestClient(api_server.app)

    response = client.post("/analyze", headers=_authorized_headers(), json={"hours": 1})

    assert response.status_code == 422
    assert any(error["loc"] == ["body", "user_id"] for error in response.json()["detail"])


@pytest.mark.parametrize(
    "user_id",
    ["", "   ", "has space", "user!", "中文", "a" * 129],
)
def test_analyze_user_id_invalid_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
    user_id: str,
):
    monkeypatch.setenv("API_KEY", "test-api-key")
    monkeypatch.setattr(api_server, "controller", object())
    client = TestClient(api_server.app)

    response = client.post(
        "/analyze",
        headers=_authorized_headers(),
        json=_analyze_request(hours=1, user_id=user_id),
    )

    assert response.status_code == 422
    assert any(error["loc"] == ["body", "user_id"] for error in response.json()["detail"])


def test_analyze_user_id_same_user_reuses_its_own_dedup_context(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("API_KEY", "test-api-key")
    fake_controller = _FakeController()
    monkeypatch.setattr(api_server, "controller", fake_controller)
    client = TestClient(api_server.app)

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


def test_analyze_user_id_different_users_remain_isolated(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("API_KEY", "test-api-key")
    fake_controller = _FakeController()
    monkeypatch.setattr(api_server, "controller", fake_controller)
    client = TestClient(api_server.app)

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
):
    monkeypatch.setenv("API_KEY", "test-api-key")
    fake_controller = _FakeController()
    fake_controller.failed_user_ids.add("broken-user")
    monkeypatch.setattr(api_server, "controller", fake_controller)
    client = TestClient(api_server.app)

    failed_job_id = _enqueue_and_run_job(client, "broken-user", monkeypatch)
    failed_result = client.get(f"/analyze/{failed_job_id}/result", headers=_authorized_headers())

    assert failed_result.status_code == 200
    assert failed_result.json()["success"] is False
    assert fake_controller.cache_manager.cached_messages == []
    assert [row["success"] for row in fake_controller.data_manager.logged_rows] == [False]


def teardown_function():
    api_server.controller = None
    api_server.analyze_jobs.clear()
    _ = os.environ.pop("API_KEY", None)
