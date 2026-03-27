import os
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from crypto_news_analyzer import api_server


def _authorized_headers() -> dict[str, str]:
    return {"Authorization": "Bearer test-api-key"}


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

    response = client.post("/analyze", json={"hours": 1})

    assert response.status_code == 401


def test_analyze_returns_service_unavailable_when_controller_missing(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("API_KEY", "test-api-key")
    monkeypatch.setattr(api_server, "controller", None)
    client = TestClient(api_server.app)

    response = client.post("/analyze", headers=_authorized_headers(), json={"hours": 1})

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
    monkeypatch.setattr(
        api_server,
        "enqueue_analyze_job",
        lambda hours: api_server.AnalyzeJobRecord(
            job_id="job-123",
            status="queued",
            time_window_hours=hours,
            created_at="2026-03-26T00:00:00+00:00",
        ),
    )
    client = TestClient(api_server.app)

    response = client.post("/analyze", headers=_authorized_headers(), json={"hours": 72})

    assert response.status_code == 202
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

    response = client.post("/analyze", headers=_authorized_headers(), json={"hours": 1})

    assert response.status_code == 400
    assert response.json() == {"detail": "Hours must be at least 2"}
    mock_controller.analyze_by_time_window.assert_not_called()


def test_analyze_status_returns_job_state(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("API_KEY", "test-api-key")
    monkeypatch.setattr(api_server, "controller", object())
    api_server.analyze_jobs["job-123"] = api_server.AnalyzeJobRecord(
        job_id="job-123",
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
        status="completed",
        time_window_hours=2,
        created_at="2026-03-26T00:00:00+00:00",
        started_at="2026-03-26T00:00:03+00:00",
        completed_at="2026-03-26T00:01:00+00:00",
        report="# Report",
        items_processed=3,
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

    response = client.post("/analyze", headers=_authorized_headers(), json={"hours": 0})

    assert response.status_code == 422
    assert any(
        error["loc"] == ["body", "hours"]
        for error in response.json()["detail"]
    )


def teardown_function():
    api_server.controller = None
    api_server.analyze_jobs.clear()
    _ = os.environ.pop("API_KEY", None)
