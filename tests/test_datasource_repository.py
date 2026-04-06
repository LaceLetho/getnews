from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

import pytest

from crypto_news_analyzer.datasource_payloads import (
    DataSourcePayloadValidationError,
    runtime_source_from_record,
    validate_datasource_create_payload,
)
from crypto_news_analyzer.domain.models import DataSource, DataSourceInUseError, IngestionJob
from crypto_news_analyzer.models import RESTAPISource, RSSSource, StorageConfig, XSource
from crypto_news_analyzer.storage.data_manager import DataManager
from crypto_news_analyzer.storage.repositories import SQLiteContentRepository, SQLiteDataSourceRepository


def _build_repository(db_path: Path) -> tuple[DataManager, SQLiteDataSourceRepository]:
    data_manager = DataManager(StorageConfig(database_path=str(db_path)))
    repository = SQLiteDataSourceRepository(data_manager)
    return data_manager, repository


def test_datasource_repository_create_get_and_list_round_trip_config_payload(tmp_path: Path):
    data_manager, repository = _build_repository(tmp_path / "datasource_repository.db")

    try:
        rss_source = DataSource.create(
            name="  CoinDesk  ",
            source_type="rss",
            tags=[" Markets ", "markets", "Layer2"],
            config_payload={
                "name": "CoinDesk",
                "url": "https://www.coindesk.com/arc/outboundfeeds/rss",
                "description": "Industry news",
            },
        )
        x_source = DataSource.create(
            name="Whale Watch",
            source_type="x",
            config_payload={
                "name": "Whale Watch",
                "url": "https://x.com/i/lists/123",
                "type": "list",
            },
        )

        saved_rss = repository.save(rss_source)
        repository.save(x_source)

        loaded = repository.get_by_id(saved_rss.id)
        assert loaded is not None
        assert loaded.name == "CoinDesk"
        assert loaded.tags == ["layer2", "markets"]
        assert loaded.config_payload == rss_source.config_payload

        by_unique_key = repository.get_by_type_and_name("rss", "CoinDesk")
        assert by_unique_key is not None
        assert by_unique_key.id == saved_rss.id

        listed = repository.list()
        assert [(item.source_type, item.name) for item in listed] == [
            ("rss", "CoinDesk"),
            ("x", "Whale Watch"),
        ]
        assert [item.name for item in repository.list(source_type="rss")] == ["CoinDesk"]
    finally:
        data_manager.close()


def test_datasource_repository_create_rejects_duplicate_source_type_and_name(tmp_path: Path):
    data_manager, repository = _build_repository(tmp_path / "datasource_repository_unique.db")

    try:
        repository.save(DataSource.create(name="CoinDesk", source_type="rss"))

        with pytest.raises(ValueError, match="already exists"):
            repository.save(DataSource.create(name="CoinDesk", source_type="rss"))
    finally:
        data_manager.close()


def test_datasource_repository_duplicate_conflict_does_not_replace_existing_row_when_precheck_is_stale(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    data_manager, repository = _build_repository(tmp_path / "datasource_repository_race.db")

    try:
        original = repository.save(
            DataSource.create(
                name="CoinDesk",
                source_type="rss",
                tags=["markets"],
                config_payload={
                    "name": "CoinDesk",
                    "url": "https://example.com/original.xml",
                    "description": "Original feed",
                },
            )
        )
        duplicate = DataSource.create(
            name="CoinDesk",
            source_type="rss",
            tags=["replacement"],
            config_payload={
                "name": "CoinDesk",
                "url": "https://example.com/replacement.xml",
                "description": "Replacement feed",
            },
        )

        monkeypatch.setattr(repository, "get_by_type_and_name", lambda *_args, **_kwargs: None)

        with pytest.raises(ValueError, match="already exists"):
            repository.save(duplicate)

        loaded_original = repository.get_by_id(original.id)
        assert loaded_original is not None
        assert loaded_original.config_payload == {
            "name": "CoinDesk",
            "url": "https://example.com/original.xml",
            "description": "Original feed",
        }
        assert loaded_original.tags == ["markets"]
        assert repository.get_by_id(duplicate.id) is None
    finally:
        data_manager.close()


def test_datasource_repository_delete_removes_row_and_tags(tmp_path: Path):
    data_manager, repository = _build_repository(tmp_path / "datasource_repository_delete.db")

    try:
        datasource = repository.save(
            DataSource.create(
                name="CoinDesk",
                source_type="rss",
                tags=["markets", "macro"],
                config_payload={"name": "CoinDesk", "url": "https://example.com/rss"},
            )
        )

        assert repository.delete(datasource.id) is True
        assert repository.get_by_id(datasource.id) is None
        assert repository.list() == []

        with data_manager._get_connection() as connection:
            cursor = connection.cursor()
            datasource_row = cursor.execute(
                "SELECT COUNT(*) FROM datasources WHERE id = ?",
                (datasource.id,),
            ).fetchone()
            tag_row = cursor.execute(
                "SELECT COUNT(*) FROM datasource_tags WHERE datasource_id = ?",
                (datasource.id,),
            ).fetchone()

        assert datasource_row is not None
        assert tag_row is not None
        datasource_count = datasource_row[0]
        tag_count = tag_row[0]

        assert datasource_count == 0
        assert tag_count == 0
    finally:
        data_manager.close()


def test_datasource_repository_delete_guard_blocks_matching_active_ingestion_jobs(tmp_path: Path):
    data_manager, repository = _build_repository(tmp_path / "datasource_repository_guard.db")

    try:
        datasource = repository.save(DataSource.create(name="CoinDesk", source_type="rss"))
        pending_job = IngestionJob.create(source_type="rss", source_name="CoinDesk")
        data_manager.upsert_ingestion_job(
            job_id=pending_job.id,
            source_type=pending_job.source_type,
            source_name=pending_job.source_name,
            scheduled_at=pending_job.scheduled_at,
            status=pending_job.status,
            metadata=pending_job.metadata,
        )

        with pytest.raises(DataSourceInUseError) as exc_info:
            repository.delete(datasource.id)

        error = exc_info.value
        assert error.source_type == "rss"
        assert error.source_name == "CoinDesk"
        assert error.active_job_ids == [pending_job.id]
    finally:
        data_manager.close()


def test_datasource_repository_delete_guard_ignores_non_active_or_non_matching_jobs(tmp_path: Path):
    data_manager, repository = _build_repository(tmp_path / "datasource_repository_guard_ignore.db")

    try:
        datasource = repository.save(DataSource.create(name="CoinDesk", source_type="rss"))

        completed_job = IngestionJob.create(source_type="rss", source_name="CoinDesk")
        completed_job.status = "completed"
        other_source_job = IngestionJob.create(source_type="x", source_name="CoinDesk")

        for job in (completed_job, other_source_job):
            data_manager.upsert_ingestion_job(
                job_id=job.id,
                source_type=job.source_type,
                source_name=job.source_name,
                scheduled_at=job.scheduled_at,
                status=job.status,
                metadata=job.metadata,
            )

        assert repository.delete(datasource.id) is True
        assert repository.get_by_id(datasource.id) is None
    finally:
        data_manager.close()


def test_content_repository_get_content_items_since_passes_through_optional_max_hours(tmp_path: Path):
    mock_data_manager = Mock()
    repository = SQLiteContentRepository(mock_data_manager)

    from datetime import datetime

    since_time = datetime.utcnow()
    repository.get_content_items_since(since_time=since_time)

    mock_data_manager.get_content_items_since.assert_called_once_with(
        since_time=since_time,
        max_hours=None,
        source_types=None,
        limit=None,
    )


def test_datasource_payload_validation_normalizes_tags_and_translates_runtime_sources():
    rss_payload = validate_datasource_create_payload(
        {
            "source_type": "rss",
            "name": "CoinDesk",
            "tags": [" Markets ", "markets", "Layer2"],
            "config_payload": {
                "name": "CoinDesk",
                "url": "https://www.coindesk.com/arc/outboundfeeds/rss/",
                "description": "Industry news",
            },
        }
    )
    x_payload = validate_datasource_create_payload(
        {
            "source_type": "x",
            "tags": ["Whales", " whales "],
            "config_payload": {
                "name": "Whale Watch",
                "url": "https://x.com/i/lists/1234567890",
                "type": "list",
            },
        }
    )
    rest_api_payload = validate_datasource_create_payload(
        {
            "source_type": "rest_api",
            "config_payload": {
                "name": "Newswire API",
                "endpoint": "https://api.example.com/news",
                "method": "get",
                "headers": {"Accept": "application/json"},
                "params": {"limit": 10},
                "response_mapping": {
                    "title_field": "title",
                    "content_field": "body",
                    "url_field": "url",
                    "time_field": "published_at",
                },
            },
        }
    )

    assert rss_payload.tags == ["layer2", "markets"]
    assert x_payload.tags == ["whales"]
    assert rest_api_payload.config_payload["method"] == "GET"

    rss_runtime = runtime_source_from_record(rss_payload.to_domain_datasource())
    x_runtime = runtime_source_from_record(x_payload)
    rest_api_runtime = runtime_source_from_record(rest_api_payload)

    assert isinstance(rss_runtime, RSSSource)
    assert rss_runtime.description == "Industry news"
    assert isinstance(x_runtime, XSource)
    assert x_runtime.type == "list"
    assert isinstance(rest_api_runtime, RESTAPISource)
    assert rest_api_runtime.method == "GET"


def test_datasource_payload_validation_rejects_unsupported_source_type():
    with pytest.raises(DataSourcePayloadValidationError, match="source_type must be one of"):
        validate_datasource_create_payload(
            {
                "source_type": "webhook",
                "config_payload": {"name": "Webhook feed"},
            }
        )


def test_datasource_payload_validation_rejects_malformed_rss_payload():
    with pytest.raises(DataSourcePayloadValidationError, match=r"rss.url must be a valid http\(s\) URL"):
        validate_datasource_create_payload(
            {
                "source_type": "rss",
                "config_payload": {
                    "name": "CoinDesk",
                    "url": "ftp://www.coindesk.com/rss",
                },
            }
        )


def test_datasource_payload_validation_rejects_malformed_x_payload():
    with pytest.raises(DataSourcePayloadValidationError, match="x.type must be one of"):
        validate_datasource_create_payload(
            {
                "source_type": "x",
                "config_payload": {
                    "name": "Whale Watch",
                    "url": "https://x.com/whalewatch",
                    "type": "search",
                },
            }
        )


def test_datasource_payload_validation_rejects_non_x_domain_for_x_payload():
    with pytest.raises(DataSourcePayloadValidationError, match=r"x.url must be a valid https://x\.com URL"):
        validate_datasource_create_payload(
            {
                "source_type": "x",
                "config_payload": {
                    "name": "Whale Watch",
                    "url": "https://twitter.com/whalewatch",
                    "type": "timeline",
                },
            }
        )


def test_datasource_payload_validation_rejects_malformed_rest_api_payload():
    with pytest.raises(
        DataSourcePayloadValidationError,
        match="rest_api.response_mapping.time_field is required",
    ):
        validate_datasource_create_payload(
            {
                "source_type": "rest_api",
                "config_payload": {
                    "name": "Newswire API",
                    "endpoint": "https://api.example.com/news",
                    "method": "POST",
                    "response_mapping": {
                        "title_field": "title",
                        "content_field": "body",
                        "url_field": "url",
                    },
                },
            }
        )


def test_datasource_payload_validation_rejects_more_than_16_unique_tags():
    with pytest.raises(DataSourcePayloadValidationError, match="more than 16 unique values"):
        validate_datasource_create_payload(
            {
                "source_type": "rss",
                "tags": [f"tag-{index}" for index in range(17)],
                "config_payload": {
                    "name": "CoinDesk",
                    "url": "https://www.coindesk.com/arc/outboundfeeds/rss/",
                },
            }
        )


def test_datasource_payload_validation_rejects_tag_longer_than_32_characters():
    with pytest.raises(DataSourcePayloadValidationError, match="at most 32 characters"):
        validate_datasource_create_payload(
            {
                "source_type": "rss",
                "tags": ["a" * 33],
                "config_payload": {
                    "name": "CoinDesk",
                    "url": "https://www.coindesk.com/arc/outboundfeeds/rss/",
                },
            }
        )
