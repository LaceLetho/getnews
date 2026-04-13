from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Optional
import logging

import pytest

from crypto_news_analyzer.domain.models import SemanticSearchJob
from crypto_news_analyzer.models import ContentItem, StorageConfig
from crypto_news_analyzer.storage.data_manager import DataManager
from crypto_news_analyzer.storage.repositories import (
    PostgresContentRepository,
    SQLiteContentRepository,
    SQLiteSemanticSearchRepository,
)
from crypto_news_analyzer.utils.errors import UnsupportedBackendError


class _FakeCursor:
    def __init__(
        self,
        executed: list[tuple[str, Any]],
        fetchone_resolver: Optional[Callable[[str, Any], Any]] = None,
        fetchall_resolver: Optional[Callable[[str, Any], list[Any]]] = None,
        rowcount_resolver: Optional[Callable[[str, Any], int]] = None,
    ):
        self.executed = executed
        self.rowcount = 1
        self._fetchone_resolver = fetchone_resolver
        self._fetchall_resolver = fetchall_resolver
        self._rowcount_resolver = rowcount_resolver
        self._last_query: Optional[str] = None
        self._last_params: Any = None

    def execute(self, query, params=None):
        self.executed.append((query, params))
        self._last_query = query
        self._last_params = params
        if self._rowcount_resolver is not None:
            self.rowcount = self._rowcount_resolver(query, params)

    def fetchone(self):
        if self._fetchone_resolver is not None and self._last_query is not None:
            return self._fetchone_resolver(self._last_query, self._last_params)
        return None

    def fetchall(self):
        if self._fetchall_resolver is not None and self._last_query is not None:
            return self._fetchall_resolver(self._last_query, self._last_params)
        return []


class _FakeConnection:
    def __init__(
        self,
        executed: list[tuple[str, Any]],
        fetchone_resolver: Optional[Callable[[str, Any], Any]] = None,
        fetchall_resolver: Optional[Callable[[str, Any], list[Any]]] = None,
        rowcount_resolver: Optional[Callable[[str, Any], int]] = None,
    ):
        self._executed = executed
        self._fetchone_resolver = fetchone_resolver
        self._fetchall_resolver = fetchall_resolver
        self._rowcount_resolver = rowcount_resolver

    def cursor(self):
        return _FakeCursor(
            self._executed,
            fetchone_resolver=self._fetchone_resolver,
            fetchall_resolver=self._fetchall_resolver,
            rowcount_resolver=self._rowcount_resolver,
        )

    def commit(self):
        return None

    def rollback(self):
        return None

    def close(self):
        return None


class _FakePsycopg:
    def __init__(
        self,
        executed: list[tuple[str, Any]],
        fetchone_resolver: Optional[Callable[[str, Any], Any]] = None,
        fetchall_resolver: Optional[Callable[[str, Any], list[Any]]] = None,
        rowcount_resolver: Optional[Callable[[str, Any], int]] = None,
    ):
        self.executed = executed
        self._fetchone_resolver = fetchone_resolver
        self._fetchall_resolver = fetchall_resolver
        self._rowcount_resolver = rowcount_resolver

    def connect(self, *_args, **_kwargs):
        return _FakeConnection(
            self.executed,
            fetchone_resolver=self._fetchone_resolver,
            fetchall_resolver=self._fetchall_resolver,
            rowcount_resolver=self._rowcount_resolver,
        )


class _FakeEmbeddingService:
    def __init__(self, embedding: Optional[list[float]]):
        self.enabled = True
        self.model = "text-embedding-3-small"
        self.embedding = embedding
        self.inputs: list[str] = []

    def generate_for_content_item(self, item):
        self.inputs.append(f"{item.title}\n\n{item.content}")
        return self.embedding


def test_postgres_semantic_search_schema_bootstrap_matches_migration(monkeypatch):
    migration_sql = Path("migrations/postgresql/001_init.sql").read_text(encoding="utf-8")
    executed: list[tuple[str, Any]] = []
    fake_psycopg = _FakePsycopg(executed)

    monkeypatch.setattr("crypto_news_analyzer.storage.data_manager.psycopg", fake_psycopg)
    monkeypatch.setattr("crypto_news_analyzer.storage.data_manager.dict_row", object())

    _ = DataManager(
        StorageConfig(
            backend="postgres",
            database_url="postgresql://user:pass@localhost:5432/db",
            pgvector_dimensions=1536,
        )
    )

    runtime_sql = "\n".join(query for query, _ in executed)

    assert "CREATE TABLE IF NOT EXISTS semantic_search_jobs" in migration_sql
    assert "CREATE TABLE IF NOT EXISTS semantic_search_jobs" in runtime_sql
    assert "embedding_model TEXT" in migration_sql
    assert "embedding_updated_at TIMESTAMPTZ" in migration_sql
    assert "embedding_model TEXT" in runtime_sql
    assert "embedding_updated_at TIMESTAMPTZ" in runtime_sql

    for required_fragment in [
        "query TEXT NOT NULL",
        "normalized_intent TEXT NOT NULL DEFAULT ''",
        "matched_count INTEGER NOT NULL DEFAULT 0",
        "retained_count INTEGER NOT NULL DEFAULT 0",
        "decomposition_json JSONB",
        "result TEXT",
        "error_message TEXT",
        "source TEXT NOT NULL DEFAULT 'api'",
        "CREATE INDEX IF NOT EXISTS idx_semantic_search_jobs_recipient",
        "CREATE INDEX IF NOT EXISTS idx_semantic_search_jobs_status",
    ]:
        assert required_fragment in migration_sql
        assert required_fragment in runtime_sql

    assert "ivfflat" not in migration_sql.lower()
    assert "hnsw" not in migration_sql.lower()
    assert "ivfflat" not in runtime_sql.lower()
    assert "hnsw" not in runtime_sql.lower()


def test_semantic_search_job_round_trip_uses_dedicated_table(tmp_path):
    manager = DataManager(StorageConfig(database_path=str(tmp_path / "semantic-search.db")))
    created_at = datetime.utcnow()

    manager.upsert_analysis_job(
        request_id="analysis-job-1",
        recipient_key="api:operator_01",
        time_window_hours=24,
        created_at=created_at,
        status="pending",
        priority=5,
        source="api",
    )
    manager.upsert_semantic_search_job(
        job_id="semantic_search_job_round_trip",
        recipient_key="api:operator_01",
        query="btc etf flows",
        normalized_intent="btc etf inflows",
        time_window_hours=24,
        created_at=created_at,
        status="completed",
        matched_count=12,
        retained_count=4,
        decomposition_json={"subqueries": ["btc etf", "flows"]},
        result={"success": True, "report_content": "summary"},
        source="api",
    )

    analysis_job = manager.get_analysis_job_by_id("analysis-job-1")
    semantic_job = manager.get_semantic_search_job_by_id("semantic_search_job_round_trip")
    semantic_jobs = manager.get_semantic_search_jobs_by_recipient("api:operator_01")

    assert analysis_job is not None
    assert analysis_job["id"] == "analysis-job-1"
    assert analysis_job["time_window_hours"] == 24

    assert semantic_job is not None
    assert semantic_job["id"] == "semantic_search_job_round_trip"
    assert semantic_job["query"] == "btc etf flows"
    assert semantic_job["normalized_intent"] == "btc etf inflows"
    assert semantic_job["matched_count"] == 12
    assert semantic_job["retained_count"] == 4
    assert semantic_job["decomposition_json"] == {"subqueries": ["btc etf", "flows"]}
    assert semantic_job["result"] == {"success": True, "report_content": "summary"}
    assert [job["id"] for job in semantic_jobs] == ["semantic_search_job_round_trip"]

    with manager._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(content_items)")
        content_columns = {row[1] for row in cursor.fetchall()}
        cursor.execute("PRAGMA table_info(semantic_search_jobs)")
        semantic_columns = {row[1] for row in cursor.fetchall()}

    assert {"embedding_model", "embedding_updated_at"}.issubset(content_columns)
    assert {
        "id",
        "recipient_key",
        "query",
        "normalized_intent",
        "time_window_hours",
        "status",
        "matched_count",
        "retained_count",
        "decomposition_json",
        "result",
        "error_message",
        "created_at",
        "started_at",
        "completed_at",
        "source",
    }.issubset(semantic_columns)


def test_semantic_search_retrieval_applies_time_window_and_per_subquery_cap(monkeypatch):
    executed: list[tuple[str, Any]] = []
    since_time = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
    expected_end_time = since_time + timedelta(hours=24)

    def _fetchall_resolver(query: str, _params: Any) -> list[Any]:
        if "1 - (embedding <=> CAST(" not in query:
            return []
        return [
            {
                "id": "content-1",
                "title": "BTC ETF inflows accelerate",
                "content": "Institutional demand remained strong.",
                "url": "https://example.com/btc-etf",
                "publish_time": "2026-01-01T12:30:00+00:00",
                "source_name": "CoinDesk",
                "source_type": "rss",
                "similarity": 0.97,
            },
            {
                "id": "content-2",
                "title": "Spot ETF demand lifts BTC market structure",
                "content": "Flows remained positive through the session.",
                "url": "https://example.com/btc-market-structure",
                "publish_time": "2026-01-01T11:15:00+00:00",
                "source_name": "The Block",
                "source_type": "rss",
                "similarity": 0.91,
            },
        ]

    fake_psycopg = _FakePsycopg(executed, fetchall_resolver=_fetchall_resolver)
    monkeypatch.setattr("crypto_news_analyzer.storage.data_manager.psycopg", fake_psycopg)
    monkeypatch.setattr("crypto_news_analyzer.storage.data_manager.dict_row", object())

    manager = DataManager(
        StorageConfig(
            backend="postgres",
            database_url="postgresql://user:pass@localhost:5432/db",
            pgvector_dimensions=3,
        )
    )
    repository = PostgresContentRepository(manager)

    rows = repository.semantic_search_by_similarity(
        query_embedding=[0.1, 0.2, 0.3],
        since_time=since_time,
        max_hours=24,
        limit=200,
    )

    assert [(item.id, score) for item, score in rows] == [
        ("content-1", 0.97),
        ("content-2", 0.91),
    ]
    assert rows[0][0].source_name == "CoinDesk"
    assert rows[0][0].url == "https://example.com/btc-etf"
    assert rows[0][0].publish_time == datetime(2026, 1, 1, 12, 30)

    retrieval_query, params = next(
        (query, params)
        for query, params in executed
        if "1 - (embedding <=> CAST(" in query
    )
    assert "embedding IS NOT NULL" in retrieval_query
    assert "publish_time >= %s" in retrieval_query
    assert "publish_time <= %s" in retrieval_query
    assert "ORDER BY similarity DESC, publish_time DESC" in retrieval_query
    assert params == (
        "[0.1,0.2,0.3]",
        since_time.isoformat(),
        expected_end_time.isoformat(),
        50,
    )


def test_semantic_search_repository_rejects_sqlite_backend_unsupported_backend(tmp_path):
    manager = DataManager(StorageConfig(database_path=str(tmp_path / "semantic-search.db")))
    content_repository = SQLiteContentRepository(manager)
    semantic_repository = SQLiteSemanticSearchRepository(manager)

    with pytest.raises(UnsupportedBackendError) as content_exc:
        content_repository.semantic_search_by_similarity(
            query_embedding=[0.1, 0.2, 0.3],
            since_time=datetime.now(timezone.utc) - timedelta(hours=1),
            max_hours=24,
            limit=25,
        )

    assert content_exc.value.details["operation"] == "unsupported_backend"
    assert content_exc.value.details["backend"] == "sqlite"
    assert content_exc.value.details["feature"] == "semantic search retrieval"

    with pytest.raises(UnsupportedBackendError) as job_exc:
        semantic_repository.create_semantic_search_job(
            SemanticSearchJob.create(
                recipient_key="api:operator_01",
                query="btc etf flows",
                time_window_hours=24,
            )
        )

    assert job_exc.value.details["operation"] == "unsupported_backend"
    assert job_exc.value.details["feature"] == "semantic search job persistence"


def test_incremental_embedding_updates_only_new_postgres_rows(monkeypatch):
    executed: list[tuple[str, Any]] = []
    inserted_urls: set[str] = set()

    def _rowcount_resolver(query: str, params: Any) -> int:
        if "INSERT INTO content_items" in query:
            url = params[3]
            if url in inserted_urls:
                return 0
            inserted_urls.add(url)
            return 1
        if "UPDATE content_items" in query:
            return 1
        return 1

    fake_psycopg = _FakePsycopg(executed, rowcount_resolver=_rowcount_resolver)
    monkeypatch.setattr("crypto_news_analyzer.storage.data_manager.psycopg", fake_psycopg)
    monkeypatch.setattr("crypto_news_analyzer.storage.data_manager.dict_row", object())

    manager = DataManager(
        StorageConfig(
            backend="postgres",
            database_url="postgresql://user:pass@localhost:5432/db",
            pgvector_dimensions=3,
        )
    )
    embedding_service = _FakeEmbeddingService([0.1, 0.2, 0.3])
    manager.set_embedding_service(embedding_service)
    monkeypatch.setattr(
        manager,
        "_schedule_incremental_embeddings",
        lambda items: manager._generate_and_persist_embeddings(items),
    )

    item = _build_content_item("content-1", "https://example.com/article")
    duplicate = _build_content_item("content-2", "https://example.com/article")

    added_count = manager.add_content_items([item, duplicate])

    assert added_count == 1
    assert embedding_service.inputs == ["Embedding title\n\nEmbedding body"]

    update_query, update_params = next(
        (query, params)
        for query, params in executed
        if "UPDATE content_items" in query
    )
    assert "embedding_model = %s" in update_query
    assert update_params[0] == "[0.1,0.2,0.3]"
    assert update_params[1] == "text-embedding-3-small"
    assert update_params[3] == "content-1"


def test_incremental_embedding_failure_logs_warning_and_keeps_null_embedding(monkeypatch, caplog):
    executed: list[tuple[str, Any]] = []

    fake_psycopg = _FakePsycopg(executed)
    monkeypatch.setattr("crypto_news_analyzer.storage.data_manager.psycopg", fake_psycopg)
    monkeypatch.setattr("crypto_news_analyzer.storage.data_manager.dict_row", object())

    manager = DataManager(
        StorageConfig(
            backend="postgres",
            database_url="postgresql://user:pass@localhost:5432/db",
            pgvector_dimensions=3,
        )
    )
    manager.set_embedding_service(_FakeEmbeddingService(None))
    monkeypatch.setattr(
        manager,
        "_schedule_incremental_embeddings",
        lambda items: manager._generate_and_persist_embeddings(items),
    )

    with caplog.at_level(logging.WARNING):
        added_count = manager.add_content_items([_build_content_item("content-3", "https://example.com/new")])

    assert added_count == 1
    assert "保留NULL embedding" in caplog.text
    assert not any("UPDATE content_items" in query for query, _ in executed)


def _build_content_item(content_id: str, url: str) -> ContentItem:
    return ContentItem(
        id=content_id,
        title="Embedding title",
        content="Embedding body",
        url=url,
        publish_time=datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc),
        source_name="CoinDesk",
        source_type="rss",
    )
