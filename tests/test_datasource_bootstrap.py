import json
import sqlite3
from pathlib import Path
from unittest.mock import Mock

from crypto_news_analyzer.domain.models import DataSource
from crypto_news_analyzer.execution_coordinator import MainController
from crypto_news_analyzer.models import StorageConfig
from crypto_news_analyzer.storage.data_manager import DataManager
from crypto_news_analyzer.storage.repositories import SQLiteDataSourceRepository


class _FakeCursor:
    def __init__(self, executed):
        self.executed = executed
        self.rowcount = 1

    def execute(self, query, params=None):
        self.executed.append((query, params))

    def fetchone(self):
        return None

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


def _fetch_sqlite_columns(connection: sqlite3.Connection, table_name: str) -> dict[str, dict[str, object]]:
    return {
        row[1]: {
            "type": row[2],
            "notnull": row[3],
            "default": row[4],
            "pk": row[5],
        }
        for row in connection.execute(f"PRAGMA table_info({table_name})")
    }


def _fetch_sqlite_indexes(connection: sqlite3.Connection, table_name: str) -> dict[str, dict[str, object]]:
    return {
        row[1]: {
            "unique": row[2],
            "origin": row[3],
            "partial": row[4],
        }
        for row in connection.execute(f"PRAGMA index_list({table_name})")
    }


def _create_pre_datasource_schema(db_path: Path) -> None:
    connection = sqlite3.connect(db_path)
    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            CREATE TABLE content_items (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                url TEXT UNIQUE NOT NULL,
                publish_time DATETIME NOT NULL,
                source_name TEXT NOT NULL,
                source_type TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE crawl_status (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                execution_time DATETIME NOT NULL,
                total_items INTEGER NOT NULL,
                rss_results TEXT NOT NULL,
                x_results TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE analysis_execution_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id TEXT NOT NULL,
                execution_time DATETIME NOT NULL,
                time_window_hours INTEGER NOT NULL,
                items_count INTEGER NOT NULL,
                success BOOLEAN NOT NULL,
                error_message TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE analysis_jobs (
                id TEXT PRIMARY KEY,
                recipient_key TEXT NOT NULL,
                time_window_hours INTEGER NOT NULL,
                created_at DATETIME NOT NULL,
                status TEXT NOT NULL,
                priority INTEGER NOT NULL DEFAULT 5,
                started_at DATETIME,
                completed_at DATETIME,
                result TEXT,
                error_message TEXT,
                source TEXT NOT NULL DEFAULT 'api'
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE ingestion_jobs (
                id TEXT PRIMARY KEY,
                source_type TEXT NOT NULL,
                source_name TEXT NOT NULL,
                scheduled_at DATETIME NOT NULL,
                status TEXT NOT NULL,
                started_at DATETIME,
                completed_at DATETIME,
                items_crawled INTEGER NOT NULL DEFAULT 0,
                items_new INTEGER NOT NULL DEFAULT 0,
                error_message TEXT,
                metadata TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        cursor.execute(
            """
            INSERT INTO content_items (
                id, title, content, url, publish_time, source_name, source_type, content_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "item-1",
                "existing title",
                "existing content",
                "https://example.com/existing",
                "2026-04-01T00:00:00",
                "CoinDesk",
                "rss",
                "hash-1",
            ),
        )
        cursor.execute(
            """
            INSERT INTO ingestion_jobs (
                id, source_type, source_name, scheduled_at, status
            ) VALUES (?, ?, ?, ?, ?)
            """,
            ("job-1", "rss", "CoinDesk", "2026-04-01T01:00:00", "completed"),
        )
        connection.commit()
    finally:
        connection.close()


def _fetch_count(cursor, query: str, params=()):
    row = cursor.execute(query, params).fetchone()
    assert row is not None
    return row[0]


def _build_bootstrap_config(database_path: Path) -> dict[str, object]:
    return {
        "storage": {
            "retention_days": 30,
            "max_storage_mb": 1000,
            "cleanup_frequency": "daily",
            "backend": "sqlite",
            "database_path": str(database_path),
        },
        "llm_config": {
            "model": "test-model",
        },
        "rss_sources": [
            {
                "name": "CoinDesk",
                "url": "https://www.coindesk.com/arc/outboundfeeds/rss",
                "description": "Industry news",
            }
        ],
        "x_sources": [
            {
                "name": "Whale Watch",
                "url": "https://x.com/i/lists/123",
                "type": "list",
            }
        ],
        "rest_api_sources": [
            {
                "name": "News API",
                "endpoint": "https://example.com/news",
                "method": "GET",
                "headers": {"Authorization": "Bearer token"},
                "params": {"limit": 10},
                "response_mapping": {
                    "title_field": "title",
                    "content_field": "content",
                    "url_field": "url",
                    "time_field": "published_at",
                },
            }
        ],
    }


def _write_bootstrap_config(
    config_path: Path,
    database_path: Path,
    datasource_mode: str = "configured",
) -> None:
    config_payload = _build_bootstrap_config(database_path)

    if datasource_mode == "empty_arrays":
        config_payload["rss_sources"] = []
        config_payload["x_sources"] = []
        config_payload["rest_api_sources"] = []
    elif datasource_mode == "omitted_arrays":
        config_payload.pop("rss_sources")
        config_payload.pop("x_sources")
        config_payload.pop("rest_api_sources")
    elif datasource_mode != "configured":
        raise ValueError(f"unsupported datasource_mode: {datasource_mode}")

    config_path.write_text(
        json.dumps(config_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _load_bootstrapped_datasources(database_path: Path):
    data_manager = DataManager(StorageConfig(database_path=str(database_path)))
    repository = SQLiteDataSourceRepository(data_manager)
    return data_manager, repository


def test_datasource_schema_sqlite_bootstrap_creates_expected_tables_indexes_and_constraints(tmp_path: Path):
    db_path = tmp_path / "datasource_schema.db"
    manager = DataManager(StorageConfig(database_path=str(db_path)))

    try:
        connection = sqlite3.connect(db_path)
        try:
            tables = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            assert "datasources" in tables
            assert "datasource_tags" in tables

            datasource_columns = _fetch_sqlite_columns(connection, "datasources")
            assert datasource_columns["id"]["pk"] == 1
            assert datasource_columns["source_type"]["type"] == "TEXT"
            assert datasource_columns["name"]["type"] == "TEXT"
            assert datasource_columns["config_payload"]["type"] == "TEXT"
            assert datasource_columns["config_payload"]["notnull"] == 1
            assert datasource_columns["created_at"]["type"] == "DATETIME"

            datasource_indexes = _fetch_sqlite_indexes(connection, "datasources")
            assert datasource_indexes["idx_datasources_source_name"]["unique"] == 1
            assert "idx_datasources_created_at" in datasource_indexes

            tag_columns = _fetch_sqlite_columns(connection, "datasource_tags")
            assert tag_columns["datasource_id"]["type"] == "TEXT"
            assert tag_columns["tag"]["type"] == "TEXT"

            tag_indexes = _fetch_sqlite_indexes(connection, "datasource_tags")
            assert "idx_datasource_tags_tag" in tag_indexes
            assert any(index_info["origin"] == "pk" for index_info in tag_indexes.values())

            foreign_keys = connection.execute(
                "PRAGMA foreign_key_list(datasource_tags)"
            ).fetchall()
            assert foreign_keys == [(0, 0, "datasources", "datasource_id", "id", "NO ACTION", "CASCADE", "NONE")]
        finally:
            connection.close()

        with manager._get_connection() as managed_connection:
            cursor = managed_connection.cursor()
            cursor.execute(
                "INSERT INTO datasources (id, source_type, name, config_payload) VALUES (?, ?, ?, ?)",
                ("ds-1", "rss", "CoinDesk", '{"url":"https://example.com/rss"}'),
            )
            cursor.execute(
                "INSERT INTO datasource_tags (datasource_id, tag) VALUES (?, ?)",
                ("ds-1", "markets"),
            )
            managed_connection.commit()

            try:
                cursor.execute(
                    "INSERT INTO datasources (id, source_type, name, config_payload) VALUES (?, ?, ?, ?)",
                    ("ds-2", "rss", "CoinDesk", "{}"),
                )
            except sqlite3.IntegrityError:
                pass
            else:
                raise AssertionError("expected unique constraint on datasources(source_type, name)")

            try:
                cursor.execute(
                    "INSERT INTO datasource_tags (datasource_id, tag) VALUES (?, ?)",
                    ("ds-1", "markets"),
                )
            except sqlite3.IntegrityError:
                pass
            else:
                raise AssertionError("expected unique tag rows per datasource")
    finally:
        manager.close()


def test_datasource_schema_sqlite_delete_cascades_only_to_tags(tmp_path: Path):
    db_path = tmp_path / "datasource_cascade.db"
    manager = DataManager(StorageConfig(database_path=str(db_path)))

    try:
        with manager._get_connection() as connection:
            cursor = connection.cursor()
            cursor.execute(
                "INSERT INTO datasources (id, source_type, name, config_payload) VALUES (?, ?, ?, ?)",
                ("ds-1", "rss", "CoinDesk", "{}"),
            )
            cursor.execute(
                "INSERT INTO datasource_tags (datasource_id, tag) VALUES (?, ?)",
                ("ds-1", "markets"),
            )
            cursor.execute(
                "INSERT INTO ingestion_jobs (id, source_type, source_name, scheduled_at, status) VALUES (?, ?, ?, ?, ?)",
                ("job-1", "rss", "CoinDesk", "2026-04-01T01:00:00", "completed"),
            )
            connection.commit()

            cursor.execute("DELETE FROM datasources WHERE id = ?", ("ds-1",))
            connection.commit()

            remaining_tags = _fetch_count(cursor, "SELECT COUNT(*) FROM datasource_tags")
            remaining_jobs = _fetch_count(cursor, "SELECT COUNT(*) FROM ingestion_jobs")

            assert remaining_tags == 0
            assert remaining_jobs == 1
    finally:
        manager.close()


def test_datasource_schema_postgres_bootstrap_executes_expected_ddl(monkeypatch):
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

    datasource_table_queries = [query for query, _ in executed if "CREATE TABLE IF NOT EXISTS datasources" in query]
    tag_table_queries = [query for query, _ in executed if "CREATE TABLE IF NOT EXISTS datasource_tags" in query]

    assert datasource_table_queries
    assert "config_payload JSONB NOT NULL DEFAULT '{}'::jsonb" in datasource_table_queries[0]
    assert "created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP" in datasource_table_queries[0]

    assert tag_table_queries
    assert "PRIMARY KEY (datasource_id, tag)" in tag_table_queries[0]
    assert "REFERENCES datasources (id) ON DELETE CASCADE" in tag_table_queries[0]

    assert any("CREATE UNIQUE INDEX IF NOT EXISTS idx_datasources_source_name" in query for query, _ in executed)
    assert any("ON datasources (source_type, name)" in query for query, _ in executed)
    assert any("CREATE INDEX IF NOT EXISTS idx_datasources_created_at" in query for query, _ in executed)
    assert any("CREATE INDEX IF NOT EXISTS idx_datasource_tags_tag" in query for query, _ in executed)

    manager.close()


def test_datasource_schema_postgres_migration_is_additive_only():
    migration_sql = Path("migrations/postgresql/002_datasource_schema.sql").read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS datasources" in migration_sql
    assert "CREATE TABLE IF NOT EXISTS datasource_tags" in migration_sql
    assert "config_payload JSONB NOT NULL DEFAULT '{}'::jsonb" in migration_sql
    assert "REFERENCES datasources (id) ON DELETE CASCADE" in migration_sql
    assert "CREATE UNIQUE INDEX IF NOT EXISTS idx_datasources_source_name" in migration_sql
    assert "CREATE INDEX IF NOT EXISTS idx_datasource_tags_tag" in migration_sql

    forbidden_tokens = [
        "INSERT INTO content_items",
        "INSERT INTO ingestion_jobs",
        "ALTER TABLE content_items",
        "ALTER TABLE analysis_jobs",
        "ALTER TABLE ingestion_jobs",
        "TRUNCATE content_items",
        "TRUNCATE ingestion_jobs",
    ]
    assert not any(token in migration_sql for token in forbidden_tokens)


def test_datasource_no_historical_backfill_when_bootstrapping_existing_sqlite_db(tmp_path: Path):
    db_path = tmp_path / "existing_pre_datasource.db"
    _create_pre_datasource_schema(db_path)

    manager = DataManager(StorageConfig(database_path=str(db_path)))

    try:
        connection = sqlite3.connect(db_path)
        try:
            cursor = connection.cursor()
            historical_content_rows = _fetch_count(cursor, "SELECT COUNT(*) FROM content_items")
            historical_job_rows = _fetch_count(cursor, "SELECT COUNT(*) FROM ingestion_jobs")
            datasource_rows = _fetch_count(cursor, "SELECT COUNT(*) FROM datasources")
            datasource_tag_rows = _fetch_count(cursor, "SELECT COUNT(*) FROM datasource_tags")

            assert historical_content_rows == 1
            assert historical_job_rows == 1
            assert datasource_rows == 0
            assert datasource_tag_rows == 0
        finally:
            connection.close()
    finally:
        manager.close()


def test_datasource_bootstrap_imports_config_rows_when_storage_is_empty(tmp_path: Path):
    config_path = tmp_path / "config.json"
    database_path = tmp_path / "bootstrap_empty.db"
    _write_bootstrap_config(config_path, database_path)

    controller = MainController(str(config_path))
    assert controller.initialize_ingestion_system() is True

    data_manager, repository = _load_bootstrapped_datasources(database_path)
    try:
        rows = repository.list()

        assert [(row.source_type, row.name) for row in rows] == [
            ("rest_api", "News API"),
            ("rss", "CoinDesk"),
            ("x", "Whale Watch"),
        ]
        rss_source = repository.get_by_type_and_name("rss", "CoinDesk")
        x_source = repository.get_by_type_and_name("x", "Whale Watch")
        rest_api_source = repository.get_by_type_and_name("rest_api", "News API")

        assert rss_source is not None
        assert x_source is not None
        assert rest_api_source is not None
        assert rss_source.config_payload == {
            "name": "CoinDesk",
            "url": "https://www.coindesk.com/arc/outboundfeeds/rss",
            "description": "Industry news",
        }
        assert x_source.config_payload == {
            "name": "Whale Watch",
            "url": "https://x.com/i/lists/123",
            "type": "list",
        }
        assert rest_api_source.config_payload["endpoint"] == "https://example.com/news"
    finally:
        data_manager.close()
        controller.cleanup_resources()


def test_datasource_bootstrap_is_idempotent_on_second_initialization(tmp_path: Path):
    config_path = tmp_path / "config.json"
    database_path = tmp_path / "bootstrap_idempotent.db"
    _write_bootstrap_config(config_path, database_path)

    first_controller = MainController(str(config_path))
    second_controller = MainController(str(config_path))

    assert first_controller.initialize_ingestion_system() is True
    assert second_controller.initialize_ingestion_system() is True

    data_manager, repository = _load_bootstrapped_datasources(database_path)
    try:
        rows = repository.list()
        assert len(rows) == 3
        assert data_manager.get_datasource_count() == 3
    finally:
        data_manager.close()
        first_controller.cleanup_resources()
        second_controller.cleanup_resources()


def test_datasource_bootstrap_skip_non_empty_table_preserves_existing_rows(tmp_path: Path):
    config_path = tmp_path / "config.json"
    database_path = tmp_path / "bootstrap_skip_non_empty.db"
    _write_bootstrap_config(config_path, database_path)

    data_manager = DataManager(StorageConfig(database_path=str(database_path)))
    repository = SQLiteDataSourceRepository(data_manager)
    existing = repository.save(
        DataSource.create(
            name="Operator Feed",
            source_type="rss",
            config_payload={"name": "Operator Feed", "url": "https://example.com/operator"},
        )
    )
    data_manager.close()

    controller = MainController(str(config_path))
    assert controller.initialize_ingestion_system() is True

    reloaded_manager, reloaded_repository = _load_bootstrapped_datasources(database_path)
    try:
        rows = reloaded_repository.list()
        assert [(row.source_type, row.name) for row in rows] == [("rss", "Operator Feed")]
        loaded = reloaded_repository.get_by_id(existing.id)
        assert loaded is not None
        assert loaded.config_payload == {
            "name": "Operator Feed",
            "url": "https://example.com/operator",
        }
    finally:
        reloaded_manager.close()
        controller.cleanup_resources()


def test_runtime_loading_uses_repository_backed_datasource_rows_after_bootstrap(tmp_path: Path):
    config_path = tmp_path / "config.json"
    database_path = tmp_path / "runtime_loading.db"
    _write_bootstrap_config(config_path, database_path)

    controller = MainController(str(config_path))
    assert controller.initialize_ingestion_system() is True

    config_manager = controller.config_manager
    assert config_manager is not None

    config_manager.config_data["rss_sources"] = []
    config_manager.config_data["x_sources"] = []
    config_manager.config_data["rest_api_sources"] = []

    try:
        rss_sources = config_manager.get_rss_sources()
        x_sources = config_manager.get_x_sources()
        rest_api_sources = config_manager.get_rest_api_sources()

        assert [source.to_dict() for source in rss_sources] == [
            {
                "name": "CoinDesk",
                "url": "https://www.coindesk.com/arc/outboundfeeds/rss",
                "description": "Industry news",
            }
        ]
        assert [source.to_dict() for source in x_sources] == [
            {
                "name": "Whale Watch",
                "url": "https://x.com/i/lists/123",
                "type": "list",
            }
        ]
        assert [source.to_dict() for source in rest_api_sources] == [
            {
                "name": "News API",
                "endpoint": "https://example.com/news",
                "method": "GET",
                "headers": {"Authorization": "Bearer token"},
                "params": {"limit": 10},
                "response_mapping": {
                    "title_field": "title",
                    "content_field": "content",
                    "url_field": "url",
                    "time_field": "published_at",
                },
            }
        ]
    finally:
        controller.cleanup_resources()


def test_empty_config_arrays_runtime_loading_reads_seeded_repository_rows(tmp_path: Path):
    config_path = tmp_path / "config.json"
    database_path = tmp_path / "empty_arrays_runtime_loading.db"
    _write_bootstrap_config(config_path, database_path)

    first_controller = MainController(str(config_path))
    assert first_controller.initialize_ingestion_system() is True
    first_controller.cleanup_resources()

    _write_bootstrap_config(config_path, database_path, datasource_mode="empty_arrays")

    second_controller = MainController(str(config_path))
    assert second_controller.initialize_ingestion_system() is True

    try:
        config_manager = second_controller.config_manager
        assert config_manager is not None

        assert [source.name for source in config_manager.get_rss_sources()] == ["CoinDesk"]
        assert [source.name for source in config_manager.get_x_sources()] == ["Whale Watch"]
        assert [source.name for source in config_manager.get_rest_api_sources()] == ["News API"]
    finally:
        second_controller.cleanup_resources()


def test_empty_config_arrays_runtime_loading_reads_seeded_repository_rows_when_keys_omitted(tmp_path: Path):
    config_path = tmp_path / "config.json"
    database_path = tmp_path / "omitted_arrays_runtime_loading.db"
    _write_bootstrap_config(config_path, database_path)

    first_controller = MainController(str(config_path))
    assert first_controller.initialize_ingestion_system() is True
    first_controller.cleanup_resources()

    _write_bootstrap_config(config_path, database_path, datasource_mode="omitted_arrays")

    second_controller = MainController(str(config_path))
    assert second_controller.initialize_ingestion_system() is True

    try:
        config_manager = second_controller.config_manager
        assert config_manager is not None

        assert [source.name for source in config_manager.get_rss_sources()] == ["CoinDesk"]
        assert [source.name for source in config_manager.get_x_sources()] == ["Whale Watch"]
        assert [source.name for source in config_manager.get_rest_api_sources()] == ["News API"]
    finally:
        second_controller.cleanup_resources()


def test_crawling_stage_runtime_includes_rest_api_sources_alongside_rss_and_x(
    tmp_path: Path,
    monkeypatch,
):
    config_path = tmp_path / "config.json"
    database_path = tmp_path / "runtime_crawl.db"
    _write_bootstrap_config(config_path, database_path)

    monkeypatch.setenv("X_CT0", "ct0-token")
    monkeypatch.setenv("X_AUTH_TOKEN", "auth-token")

    controller = MainController(str(config_path))
    assert controller.initialize_ingestion_system() is True

    captured_calls: list[tuple[str, str]] = []

    class _Factory:
        def create_source(self, source_type: str, time_window_hours: int, **_kwargs):
            crawler = Mock()

            def _crawl(payload):
                captured_calls.append((source_type, payload["name"]))
                return []

            crawler.crawl.side_effect = _crawl
            return crawler

    monkeypatch.setattr(
        "crypto_news_analyzer.execution_coordinator.get_data_source_factory",
        lambda: _Factory(),
    )

    try:
        result = controller._execute_crawling_stage(time_window_hours=6)

        assert result["success"] is True
        assert captured_calls == [
            ("rss", "CoinDesk"),
            ("x", "Whale Watch"),
            ("rest_api", "News API"),
        ]
    finally:
        controller.cleanup_resources()
