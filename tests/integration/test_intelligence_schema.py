import os
from pathlib import Path

import pytest

from crypto_news_analyzer.models import StorageConfig
from crypto_news_analyzer.storage.data_manager import DataManager


def test_intelligence_runtime_bootstrap_matches_migration(monkeypatch):
    migration_sql = Path("migrations/postgresql/003_intelligence_schema.sql").read_text(
        encoding="utf-8"
    )
    executed = []

    class FakeCursor:
        rowcount = 1

        def execute(self, query, params=None):
            executed.append((query, params))

        def fetchone(self):
            return None

        def fetchall(self):
            return []

    class FakeConnection:
        def cursor(self):
            return FakeCursor()

        def commit(self):
            return None

        def rollback(self):
            return None

        def close(self):
            return None

    class FakePsycopg:
        def connect(self, *_args, **_kwargs):
            return FakeConnection()

    monkeypatch.setattr("crypto_news_analyzer.storage.data_manager.psycopg", FakePsycopg())
    monkeypatch.setattr("crypto_news_analyzer.storage.data_manager.dict_row", object())

    DataManager(
        StorageConfig(
            backend="postgres",
            database_url="postgresql://user:pass@localhost:5432/db",
            pgvector_dimensions=1536,
        )
    )
    runtime_sql = "\n".join(query for query, _ in executed)

    for fragment in [
        "CREATE EXTENSION IF NOT EXISTS vector",
        "CREATE TABLE IF NOT EXISTS raw_intelligence_items",
        "CREATE TABLE IF NOT EXISTS intelligence_extraction_observations",
        "CREATE TABLE IF NOT EXISTS intelligence_canonical_entries",
        "CREATE TABLE IF NOT EXISTS intelligence_aliases",
        "CREATE TABLE IF NOT EXISTS intelligence_related_candidates",
        "CREATE TABLE IF NOT EXISTS intelligence_crawl_checkpoints",
        "embedding vector(1536)",
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_intelligence_canonical_entries_type_key",
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_intelligence_raw_items_dedupe",
    ]:
        assert fragment in migration_sql
        assert fragment in runtime_sql

    assert "audit" not in migration_sql.lower()
    assert "audit" not in runtime_sql.lower()


@pytest.mark.skipif(not os.getenv("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL not set")
def test_real_postgres_intelligence_schema_bootstraps():
    manager = DataManager(
        StorageConfig(
            backend="postgres",
            database_url=os.environ["TEST_DATABASE_URL"],
            pgvector_dimensions=1536,
        )
    )
    try:
        with manager._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT table_name FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name LIKE '%intelligence%'
                """)
            tables = {row["table_name"] for row in cursor.fetchall()}
            cursor.execute("""
                SELECT udt_name FROM information_schema.columns
                WHERE table_name = 'intelligence_canonical_entries'
                  AND column_name = 'embedding'
                """)
            vector_row = cursor.fetchone()
            cursor.execute("""
                SELECT indexname FROM pg_indexes
                WHERE tablename = 'intelligence_canonical_entries'
                """)
            indexes = {row["indexname"] for row in cursor.fetchall()}

        assert "raw_intelligence_items" in tables
        assert "intelligence_canonical_entries" in tables
        assert vector_row is not None
        assert vector_row["udt_name"] == "vector"
        assert "idx_intelligence_canonical_entries_type_key" in indexes
        assert not any("audit" in table for table in tables)
    finally:
        manager.close()
