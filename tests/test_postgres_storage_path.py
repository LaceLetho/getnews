import os
import tempfile
from datetime import datetime, timedelta

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
            "backend": "postgres",
            "database_path": "./ignored.db",
            "database_url": ""
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
