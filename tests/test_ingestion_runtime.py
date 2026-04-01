import json
import sys
from types import SimpleNamespace

import pytest

from crypto_news_analyzer.execution_coordinator import MainController
from crypto_news_analyzer import main
from crypto_news_analyzer import api_server


class _StopImmediatelyEvent:
    def __init__(self):
        self._is_set = True

    def set(self):
        self._is_set = True

    def is_set(self):
        return self._is_set

    def wait(self, timeout=None):
        return self._is_set


class _FakeIngestionController:
    def __init__(self):
        self.initialize_ingestion_system_called = False
        self.start_scheduler_called = False

    def initialize_ingestion_system(self):
        self.initialize_ingestion_system_called = True
        return True

    def initialize_system(self):
        raise AssertionError("run_scheduler_only should not call initialize_system in ingestion mode")

    def start_scheduler(self):
        self.start_scheduler_called = True


def test_initialize_ingestion_system_skips_analysis_report_and_telegram(tmp_path):
    config_path = tmp_path / "config.json"
    db_path = tmp_path / "ingestion_runtime.db"

    config_path.write_text(
        json.dumps(
            {
                "execution_interval": 10,
                "time_window_hours": 24,
                "storage": {
                    "retention_days": 30,
                    "max_storage_mb": 1000,
                    "cleanup_frequency": "daily",
                    "database_path": str(db_path),
                },
                "llm_config": {},
                "rss_sources": [],
                "x_sources": [],
                "rest_api_sources": [],
            }
        ),
        encoding="utf-8",
    )

    controller = MainController(str(config_path))
    assert controller.initialize_ingestion_system() is True

    assert controller.ingestion_repository is not None
    assert controller.content_repository is not None
    assert controller.cache_repository is not None

    assert controller.llm_analyzer is None
    assert controller.report_generator is None
    assert controller.telegram_sender is None
    assert controller.command_handler is None
    assert controller.market_snapshot_service is None

    controller.cleanup_resources()


def test_run_scheduler_only_uses_ingestion_initialization_path(monkeypatch):
    fake_controller = _FakeIngestionController()

    monkeypatch.setattr(main, "MainController", lambda config_path: fake_controller)
    monkeypatch.setattr(main.signal, "signal", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(main.threading, "Event", _StopImmediatelyEvent)

    exit_code = main.run_scheduler_only("./config.json")

    assert exit_code == 0
    assert fake_controller.initialize_ingestion_system_called is True
    assert fake_controller.start_scheduler_called is True


def test_run_ingestion_service_delegates_to_scheduler_only(monkeypatch):
    captured = {"config_path": None}

    def _fake_run_scheduler_only(config_path):
        captured["config_path"] = config_path
        return 0

    monkeypatch.setattr(main, "run_scheduler_only", _fake_run_scheduler_only)

    exit_code = main.run_ingestion_service("custom-config.json")

    assert exit_code == 0
    assert captured["config_path"] == "custom-config.json"


def test_run_api_server_isolated_sets_api_only_runtime_and_keeps_services_stopped(monkeypatch):
    captured = {
        "config_path": None,
        "start_services": None,
        "start_scheduler": None,
        "start_command_listener": None,
        "app": None,
        "uvicorn_app": None,
        "host": None,
        "port": None,
    }

    def _fake_create_api_server(
        config_path,
        start_services=True,
        start_scheduler=None,
        start_command_listener=None,
    ):
        app = object()
        captured["config_path"] = config_path
        captured["start_services"] = start_services
        captured["start_scheduler"] = start_scheduler
        captured["start_command_listener"] = start_command_listener
        captured["app"] = app
        return app

    def _fake_uvicorn_run(app, host, port):
        captured["uvicorn_app"] = app
        captured["host"] = host
        captured["port"] = port

    monkeypatch.setattr(api_server, "create_api_server", _fake_create_api_server)
    monkeypatch.setitem(sys.modules, "uvicorn", SimpleNamespace(run=_fake_uvicorn_run))
    monkeypatch.delenv("CRYPTO_NEWS_RUNTIME_MODE", raising=False)

    exit_code = main.run_api_server_isolated("./custom-config.json")

    assert exit_code == 0
    assert captured["config_path"] == "./custom-config.json"
    assert captured["start_services"] is False
    assert captured["start_scheduler"] is None
    assert captured["start_command_listener"] is None
    assert captured["uvicorn_app"] is captured["app"]
    assert captured["host"] == "0.0.0.0"
    assert captured["port"] == 8080
    assert main.os.environ.get("CRYPTO_NEWS_RUNTIME_MODE") == "api-only"


def test_run_analysis_service_starts_telegram_without_scheduler(monkeypatch):
    captured = {
        "config_path": None,
        "start_services": None,
        "start_scheduler": None,
        "start_command_listener": None,
        "app": None,
        "uvicorn_app": None,
        "host": None,
        "port": None,
    }

    def _fake_create_api_server(
        config_path,
        start_services=True,
        start_scheduler=None,
        start_command_listener=None,
    ):
        app = object()
        captured["config_path"] = config_path
        captured["start_services"] = start_services
        captured["start_scheduler"] = start_scheduler
        captured["start_command_listener"] = start_command_listener
        captured["app"] = app
        return app

    def _fake_uvicorn_run(app, host, port):
        captured["uvicorn_app"] = app
        captured["host"] = host
        captured["port"] = port

    monkeypatch.setattr(api_server, "create_api_server", _fake_create_api_server)
    monkeypatch.setitem(sys.modules, "uvicorn", SimpleNamespace(run=_fake_uvicorn_run))
    monkeypatch.delenv("CRYPTO_NEWS_RUNTIME_MODE", raising=False)

    exit_code = main.run_analysis_service("./custom-config.json")

    assert exit_code == 0
    assert captured["config_path"] == "./custom-config.json"
    assert captured["start_services"] is False
    assert captured["start_scheduler"] is False
    assert captured["start_command_listener"] is True
    assert captured["uvicorn_app"] is captured["app"]
    assert captured["host"] == "0.0.0.0"
    assert captured["port"] == 8080
    assert main.os.environ.get("CRYPTO_NEWS_RUNTIME_MODE") == "analysis-service"


@pytest.mark.parametrize("runtime_mode", ["api-only", "analysis-service"])
def test_trigger_manual_execution_rejected_in_public_analysis_runtime(monkeypatch, runtime_mode):
    controller = MainController.__new__(MainController)
    monkeypatch.setenv("CRYPTO_NEWS_RUNTIME_MODE", runtime_mode)

    with pytest.raises(RuntimeError, match="disabled in analysis-service/api-only runtime"):
        controller.trigger_manual_execution(user_id="tester", chat_id="chat-1")
