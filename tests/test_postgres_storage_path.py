import os
import tempfile
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

import pytest

from crypto_news_analyzer.config.manager import ConfigManager
from crypto_news_analyzer.models import StorageConfig, create_content_item_from_raw
from crypto_news_analyzer.storage.data_manager import DataManager
from crypto_news_analyzer.storage.repositories import SQLiteContentRepository


class _FakeCursor:
    def __init__(self, executed):
        self.executed = executed
        self.rowcount = 1
        self._fetchone_value = None

    def execute(self, query, params=None):
        self.executed.append((query, params))
        if "SELECT 1 FROM content_items" in query:
            self._fetchone_value = {"exists": 1}

    def fetchone(self):
        return self._fetchone_value

    def fetchall(self):
        return []


class _FakeConnection:
    def __init__(self, executed):
        self._executed = executed

    def cursor(self):
        return _FakeCursor(self._executed)

    def commit(self):
        return None

    def rollback(self):
        return None

    def close(self):
        return None


class _FakePsycopg:
    def __init__(self, executed):
        self.executed = executed

    def connect(self, *_args, **_kwargs):
        return _FakeConnection(self.executed)


def test_data_manager_postgres_initialization_runs_vector_setup(monkeypatch):
    executed = []
    fake_psycopg = _FakePsycopg(executed)

    monkeypatch.setattr("crypto_news_analyzer.storage.data_manager.psycopg", fake_psycopg)
    monkeypatch.setattr("crypto_news_analyzer.storage.data_manager.dict_row", object())

    manager = DataManager(
        StorageConfig(
            backend="postgres",
            database_url="postgresql://user:pass@localhost:5432/db",
            pgvector_dimensions=1536,
        )
    )

    assert any("CREATE EXTENSION IF NOT EXISTS vector" in query for query, _ in executed)
    assert any("embedding vector(1536)" in query for query, _ in executed)

    item = create_content_item_from_raw(
        title="t1",
        content="c1",
        url="https://example.com/1",
        publish_time=datetime.utcnow(),
        source_name="s1",
        source_type="rss",
    )
    manager.add_content_items([item])

    assert any("ON CONFLICT (url) DO NOTHING" in query for query, _ in executed)
    assert manager.check_content_hash_exists(item.generate_content_hash()) is True


def test_config_manager_supports_postgres_via_env_database_url(tmp_path, monkeypatch):
    config_path = tmp_path / "config.json"
    config_path.write_text(
        """
        {
          "storage": {
            "retention_days": 30,
            "max_storage_mb": 1000,
            "cleanup_frequency": "daily",
            "backend": "postgres"
          },
          "llm_config": {"model": "gpt-4"}
        }
        """,
        encoding="utf-8",
    )

    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/db")
    manager = ConfigManager(str(config_path))
    config = manager.load_config()
    assert manager.validate_config(config)

    storage = manager.get_storage_config()
    assert storage.backend == "postgres"
    assert storage.database_url == "postgresql://user:pass@localhost:5432/db"


def test_content_repository_time_range_and_hash_exists_path():
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = os.path.join(temp_dir, "repo_test.db")
        storage = StorageConfig(database_path=db_path)
        manager = DataManager(storage)
        repo = SQLiteContentRepository(manager)

        now = datetime.utcnow()
        older = now - timedelta(hours=3)
        newer = now - timedelta(hours=1)

        repo.save(
            create_content_item_from_raw(
                title="older",
                content="older",
                url="https://example.com/older",
                publish_time=older,
                source_name="source-a",
                source_type="rss",
            ).to_dict()
        )
        repo.save(
            create_content_item_from_raw(
                title="newer",
                content="newer",
                url="https://example.com/newer",
                publish_time=newer,
                source_name="source-b",
                source_type="rss",
            ).to_dict()
        )

        results = repo.get_by_time_range(
            start_time=now - timedelta(hours=2),
            end_time=now,
            source_type="rss",
            source_name="source-b",
        )
        assert len(results) == 1
        assert results[0]["title"] == "newer"

        hash_value = create_content_item_from_raw(
            title="newer",
            content="newer",
            url="https://example.com/newer",
            publish_time=newer,
            source_name="source-b",
            source_type="rss",
        ).generate_content_hash()
        assert repo.exists_by_hash(hash_value) is True


class _ReadCursor:
    def __init__(self, *, row=None, rows=None):
        self._row = row
        self._rows = rows or []

    def execute(self, _query, _params=None):
        return None

    def fetchone(self):
        return self._row

    def fetchall(self):
        return self._rows


class _ReadConnection:
    def __init__(self, cursor):
        self._cursor = cursor

    def cursor(self):
        return self._cursor

    def commit(self):
        return None

    def rollback(self):
        return None

    def close(self):
        return None


@contextmanager
def _stub_connection(cursor):
    yield _ReadConnection(cursor)


def _build_time_value(native_time: datetime, as_string: bool):
    return native_time.isoformat() if as_string else native_time


class _DeduplicateCursor:
    def __init__(self):
        self.executed = []
        self.rowcount = 0
        self._fetchall_calls = 0

    def execute(self, query, params=None):
        self.executed.append((query, params))
        if "DELETE FROM content_items" in query:
            self.rowcount = 1
        else:
            self.rowcount = 0

    def fetchall(self):
        self._fetchall_calls += 1
        if self._fetchall_calls == 1:
            return [{"content_hash": "hash-1"}]
        return []


def test_deduplicate_content_uses_portable_having_clause():
    manager = DataManager(StorageConfig(database_path=":memory:"))
    cursor = _DeduplicateCursor()
    manager._get_connection = lambda: _stub_connection(cursor)

    deleted = manager.deduplicate_content()

    assert deleted == 1
    select_query, _ = cursor.executed[0]
    assert "HAVING COUNT(*) > 1" in select_query
    assert "HAVING count > 1" not in select_query


@pytest.mark.parametrize("as_string", [True, False])
def test_get_content_items_accepts_str_and_datetime_publish_time(as_string):
    manager = DataManager(StorageConfig(database_path=":memory:"))
    aware_publish_time = datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc)
    cursor = _ReadCursor(
        rows=[
            {
                "id": "item-1",
                "title": "title",
                "content": "content",
                "url": "https://example.com/item-1",
                "publish_time": _build_time_value(aware_publish_time, as_string),
                "source_name": "source",
                "source_type": "rss",
            }
        ]
    )
    manager._get_connection = lambda: _stub_connection(cursor)

    items = manager.get_content_items()
    assert len(items) == 1
    assert isinstance(items[0].publish_time, datetime)
    assert items[0].publish_time.tzinfo is None


@pytest.mark.parametrize("as_string", [True, False])
def test_get_content_items_since_accepts_str_and_datetime_publish_time(as_string):
    manager = DataManager(StorageConfig(database_path=":memory:"))
    native_publish_time = datetime(2026, 3, 1, 0, 0)
    cursor = _ReadCursor(
        rows=[
            {
                "id": "item-2",
                "title": "title",
                "content": "content",
                "url": "https://example.com/item-2",
                "publish_time": _build_time_value(native_publish_time, as_string),
                "source_name": "source",
                "source_type": "x",
            }
        ]
    )
    manager._get_connection = lambda: _stub_connection(cursor)

    items = manager.get_content_items_since(
        since_time=datetime(2026, 2, 28, 0, 0, tzinfo=timezone.utc)
    )
    assert len(items) == 1
    assert items[0].publish_time == native_publish_time


@pytest.mark.parametrize("as_string", [True, False])
def test_get_latest_crawl_status_accepts_str_and_datetime_execution_time(as_string):
    manager = DataManager(StorageConfig(database_path=":memory:"))
    execution_time = datetime(2026, 3, 2, 8, 30)
    cursor = _ReadCursor(
        row={
            "rss_results": "[]",
            "x_results": "[]",
            "total_items": 0,
            "execution_time": _build_time_value(execution_time, as_string),
        }
    )
    manager._get_connection = lambda: _stub_connection(cursor)

    status = manager.get_latest_crawl_status()
    assert status is not None
    assert status.execution_time == execution_time


@pytest.mark.parametrize("as_string", [True, False])
def test_get_latest_message_time_accepts_str_and_datetime(as_string):
    manager = DataManager(StorageConfig(database_path=":memory:"))
    latest_time = datetime(2026, 3, 3, 10, 15)
    cursor = _ReadCursor(row={"latest_time": _build_time_value(latest_time, as_string)})
    manager._get_connection = lambda: _stub_connection(cursor)

    result = manager.get_latest_message_time(source_name="source", source_type="x")
    assert result == latest_time


@pytest.mark.parametrize("as_string", [True, False])
def test_get_last_successful_analysis_time_accepts_str_and_datetime(as_string):
    manager = DataManager(StorageConfig(database_path=":memory:"))
    execution_time = datetime(2026, 3, 4, 9, 0)
    cursor = _ReadCursor(row={"execution_time": _build_time_value(execution_time, as_string)})
    manager._get_connection = lambda: _stub_connection(cursor)

    result = manager.get_last_successful_analysis_time(chat_id="telegram:123")
    assert result == execution_time
