from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock
import json
import os
import tempfile

import pytest

from crypto_news_analyzer.domain.models import IngestionJob, IngestionJobStatus
from crypto_news_analyzer.execution_coordinator import MainController
from crypto_news_analyzer.models import StorageConfig
from crypto_news_analyzer.storage.data_manager import DataManager
from crypto_news_analyzer.storage.repositories import SQLiteIngestionRepository


@pytest.fixture
def temp_config_file():
    config_data = {
        "execution_interval": 10,
        "time_window_hours": 24,
        "storage": {
            "retention_days": 30,
            "max_storage_mb": 1000,
            "cleanup_frequency": "daily",
            "database_path": ":memory:",
        },
        "llm_config": {
            "model": "MiniMax-M2.1",
            "temperature": 0.1,
            "max_tokens": 1000,
            "prompt_config_path": "./prompts/analysis_prompt.json",
            "batch_size": 10,
        },
        "rss_sources": [],
        "x_sources": [],
        "rest_api_sources": [],
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(config_data, f)
        temp_path = f.name

    try:
        yield temp_path
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)


def _build_ingestion_repository(db_path: Path) -> tuple[DataManager, SQLiteIngestionRepository]:
    data_manager = DataManager(StorageConfig(database_path=str(db_path)))
    repository = SQLiteIngestionRepository(data_manager)
    return data_manager, repository


def _build_controller_with_ingestion_repo(config_path: str, ingestion_repo: SQLiteIngestionRepository):
    controller = MainController(config_path)
    controller._initialized = True
    controller.ingestion_repository = ingestion_repo
    controller.config_manager = Mock()
    controller.config_manager.get_time_window_hours.return_value = 24
    controller.validate_prerequisites = Mock(return_value={"valid": True, "errors": [], "warnings": []})
    controller._save_execution_history = Mock()
    return controller


def test_sqlite_ingestion_repository_persists_lifecycle_and_statistics(tmp_path: Path):
    data_manager, repository = _build_ingestion_repository(tmp_path / "ingestion_repo.db")
    try:
        job = IngestionJob.create(source_type="scheduler", source_name="crawl_only")
        repository.save(job)

        loaded = repository.get_by_id(job.id)
        assert loaded is not None
        assert loaded.status == IngestionJobStatus.PENDING.value

        assert repository.update_status(job.id, IngestionJobStatus.RUNNING.value)
        running_jobs = repository.get_pending_jobs(limit=10)
        assert any(item.id == job.id and item.status == IngestionJobStatus.RUNNING.value for item in running_jobs)

        assert repository.complete_job(job.id, items_crawled=10, items_new=7)
        completed = repository.get_by_id(job.id)
        assert completed is not None
        assert completed.status == IngestionJobStatus.COMPLETED.value
        assert completed.items_crawled == 10
        assert completed.items_new == 7

        failed_job = IngestionJob.create(source_type="scheduler", source_name="crawl_only")
        repository.save(failed_job)
        assert repository.update_status(
            failed_job.id,
            IngestionJobStatus.FAILED.value,
            error_message="forced failure",
        )

        from_source = repository.get_by_source(
            source_type="scheduler",
            source_name="crawl_only",
            limit=10,
        )
        assert len(from_source) >= 2

        stats = repository.get_statistics(since=datetime.now() - timedelta(hours=1), source_type="scheduler")
        assert stats["total_jobs"] >= 2
        assert stats["completed_jobs"] >= 1
        assert stats["failed_jobs"] >= 1
        assert stats["total_items_crawled"] >= 10
        assert stats["total_items_new"] >= 7
    finally:
        data_manager.close()


def test_run_crawl_only_persists_completed_ingestion_job(temp_config_file, tmp_path: Path):
    data_manager, repository = _build_ingestion_repository(tmp_path / "ingestion_success.db")
    try:
        controller = _build_controller_with_ingestion_repo(temp_config_file, repository)
        controller._execute_crawling_stage = Mock(
            return_value={
                "success": True,
                "content_items": [object(), object(), object()],
                "crawl_status": object(),
                "items_new": 2,
                "errors": [],
            }
        )

        result = controller.run_crawl_only(trigger_type="manual", trigger_user="tester")

        assert result.success is True
        jobs = repository.get_by_source(
            source_type="scheduler",
            source_name="crawl_only",
            limit=5,
        )
        assert jobs
        assert jobs[0].status == IngestionJobStatus.COMPLETED.value
        assert jobs[0].items_crawled == 3
        assert jobs[0].items_new == 2
    finally:
        data_manager.close()


def test_run_crawl_only_persists_failed_ingestion_job_with_error(temp_config_file, tmp_path: Path):
    data_manager, repository = _build_ingestion_repository(tmp_path / "ingestion_failed.db")
    try:
        controller = _build_controller_with_ingestion_repo(temp_config_file, repository)
        controller._execute_crawling_stage = Mock(
            return_value={
                "success": False,
                "content_items": [],
                "crawl_status": None,
                "items_new": 0,
                "errors": ["forced crawl failure"],
            }
        )

        result = controller.run_crawl_only()

        assert result.success is False
        jobs = repository.get_by_source(
            source_type="scheduler",
            source_name="crawl_only",
            limit=5,
        )
        assert jobs
        assert jobs[0].status == IngestionJobStatus.FAILED.value
        assert "forced crawl failure" in (jobs[0].error_message or "")
    finally:
        data_manager.close()


def test_run_crawl_only_skips_when_persisted_running_job_exists(temp_config_file, tmp_path: Path):
    data_manager, repository = _build_ingestion_repository(tmp_path / "ingestion_skip.db")
    try:
        active_job = IngestionJob.create(source_type="scheduler", source_name="crawl_only")
        repository.save(active_job)
        repository.update_status(active_job.id, IngestionJobStatus.RUNNING.value)

        controller = _build_controller_with_ingestion_repo(temp_config_file, repository)
        controller._execute_crawling_stage = Mock()

        result = controller.run_crawl_only()

        assert result.success is True
        controller._execute_crawling_stage.assert_not_called()

        jobs = repository.get_by_source(
            source_type="scheduler",
            source_name="crawl_only",
            limit=10,
        )
        statuses = [job.status for job in jobs]
        assert IngestionJobStatus.RUNNING.value in statuses
        assert IngestionJobStatus.SKIPPED.value in statuses
    finally:
        data_manager.close()
