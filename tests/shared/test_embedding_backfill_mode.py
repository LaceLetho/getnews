from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from threading import RLock
import logging
import sys
from typing import Any, Optional, cast

import pytest

from crypto_news_analyzer import main
from crypto_news_analyzer.models import ContentItem
from crypto_news_analyzer.semantic_search import EmbeddingBackfillRunner
from crypto_news_analyzer.utils.errors import UnsupportedBackendError


@dataclass
class _StoredRow:
    id: str
    title: str
    content: str
    url: str
    publish_time: datetime
    source_name: str = "CoinDesk"
    source_type: str = "rss"
    embedding: Optional[str] = None
    embedding_model: Optional[str] = None
    embedding_updated_at: Optional[str] = None


@dataclass
class _StoredIntelRow:
    id: str
    raw_text: str
    collected_at: datetime
    source_type: str = "telegram_group"
    embedding: Optional[list[float]] = None
    embedding_model: Optional[str] = None
    embedding_updated_at: Optional[str] = None


class _FakeCursor:
    def __init__(self, data_manager: "_FakeDataManager"):
        self.data_manager = data_manager
        self.rowcount = 0

    def execute(self, query: str, params: Any = None):
        self.data_manager.executed.append((query, params))

        if "UPDATE content_items" in query:
            embedding_literal, model, updated_at, content_id = params
            row = next(
                (item for item in self.data_manager.rows if item.id == content_id), None
            )
            if row is None or row.embedding is not None:
                self.rowcount = 0
                return

            row.embedding = embedding_literal
            row.embedding_model = model
            row.embedding_updated_at = updated_at
            self.rowcount = 1
            return

        if "UPDATE raw_intelligence_items" in query:
            embedding_literal, model, updated_at, content_id = params
            intel_row = next(
                (item for item in self.data_manager.intel_rows if item.id == content_id),
                None,
            )
            if intel_row is None or intel_row.embedding is not None:
                self.rowcount = 0
                return

            intel_row.embedding = list(embedding_literal)
            intel_row.embedding_model = model
            intel_row.embedding_updated_at = updated_at
            self.rowcount = 1
            return

        self.rowcount = 0


class _FakeConnection:
    def __init__(self, data_manager: "_FakeDataManager"):
        self.data_manager = data_manager

    def cursor(self):
        return _FakeCursor(self.data_manager)

    def commit(self):
        self.data_manager.commit_count += 1


class _FakeDataManager:
    def __init__(
        self,
        rows: list[_StoredRow],
        backend: str = "postgres",
        intel_rows: Optional[list[_StoredIntelRow]] = None,
    ):
        self.rows = rows
        self.intel_rows: list[_StoredIntelRow] = intel_rows or []
        self.backend = backend
        self.executed: list[tuple[str, Any]] = []
        self.commit_count = 0
        self.fetch_exclude_ids: list[list[str]] = []
        self._lock = RLock()

    def get_content_items_missing_embeddings(
        self,
        limit: int,
        exclude_ids: Optional[list[str]] = None,
    ) -> list[ContentItem]:
        self.fetch_exclude_ids.append(list(exclude_ids or []))
        excluded = set(exclude_ids or [])
        candidates = sorted(
            (
                row
                for row in self.rows
                if row.embedding is None and row.id not in excluded
            ),
            key=lambda row: row.publish_time,
            reverse=True,
        )[:limit]
        return [
            ContentItem(
                id=row.id,
                title=row.title,
                content=row.content,
                url=row.url,
                publish_time=row.publish_time,
                source_name=row.source_name,
                source_type=row.source_type,
            )
            for row in candidates
        ]

    @contextmanager
    def _get_connection(self):
        yield _FakeConnection(self)

    @staticmethod
    def _sql(query: str) -> str:
        return query

    @staticmethod
    def _pgvector_literal(embedding: list[float]) -> str:
        return "[" + ",".join(format(float(value), ".15g") for value in embedding) + "]"

    def get_raw_intelligence_items_missing_embeddings(
        self,
        limit: int,
        exclude_ids: Optional[list[str]] = None,
        intelligence_days: int = 7,
    ) -> list[dict[str, Any]]:
        cutoff = datetime.utcnow() - timedelta(days=intelligence_days)
        excluded = set(exclude_ids or [])
        results: list[dict[str, Any]] = []
        for row in self.intel_rows:
            if row.embedding is not None:
                continue
            if row.id in excluded:
                continue
            if not row.raw_text or not row.raw_text.strip():
                continue
            if row.collected_at < cutoff:
                continue
            results.append(
                {
                    "id": row.id,
                    "raw_text": row.raw_text,
                    "collected_at": row.collected_at,
                    "source_type": row.source_type,
                }
            )
        return sorted(
            results, key=lambda r: r["collected_at"], reverse=True
        )[:limit]

    def update_raw_intelligence_item_embedding(
        self, content_id: str, embedding: list[float], model: str
    ) -> bool:
        for row in self.intel_rows:
            if row.id == content_id and row.embedding is None:
                row.embedding = list(embedding)
                row.embedding_model = model
                row.embedding_updated_at = datetime.utcnow().isoformat()
                return True
        return False


class _FakeEmbeddingService:
    def __init__(self, results_by_id: dict[str, Optional[list[float]]]):
        self.enabled = True
        self.model = "text-embedding-3-small"
        self.results_by_id = results_by_id
        self.generated_ids: list[str] = []
        self.generated_batches: list[list[str]] = []
        self.generated_texts: list[str] = []

    def generate_for_content_item(self, item: ContentItem) -> Optional[list[float]]:
        self.generated_ids.append(item.id)
        return self.results_by_id.get(item.id)

    def generate_for_content_items(
        self, items: list[ContentItem]
    ) -> list[Optional[list[float]]]:
        batch_ids = [item.id for item in items]
        self.generated_batches.append(batch_ids)
        self.generated_ids.extend(batch_ids)
        return [self.results_by_id.get(item.id) for item in items]

    def generate_embedding(self, text: str) -> Optional[list[float]]:
        self.generated_texts.append(text)
        return self.results_by_id.get(text)


def test_normalize_runtime_mode_accepts_embedding_backfill():
    logger = logging.getLogger("test")

    normalized = main.normalize_runtime_mode("embedding-backfill", logger)

    assert normalized == "embedding-backfill"


def test_main_accepts_embedding_backfill_batch_size_and_limit(monkeypatch):
    captured: dict[str, Any] = {}

    def _fake_run_embedding_backfill(
        config_path: str, batch_size: int, limit: Optional[int], **kwargs
    ):
        captured["config_path"] = config_path
        captured["batch_size"] = batch_size
        captured["limit"] = limit
        return 0

    monkeypatch.setattr(main, "setup_logging", lambda **_kwargs: None)
    monkeypatch.setattr(main, "run_embedding_backfill", _fake_run_embedding_backfill)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "prog",
            "--mode",
            "embedding-backfill",
            "--config",
            "./custom-config.jsonc",
            "--batch-size",
            "25",
            "--limit",
            "7",
        ],
    )

    with pytest.raises(SystemExit) as exc_info:
        main.main()

    assert exc_info.value.code == 0
    assert captured == {
        "config_path": "./custom-config.jsonc",
        "batch_size": 25,
        "limit": 7,
    }


def test_embedding_backfill_only_updates_rows_missing_embeddings():
    now = datetime.now(timezone.utc)
    data_manager = _FakeDataManager(
        rows=[
            _StoredRow(
                id="content-newest",
                title="Newest",
                content="Body newest",
                url="https://example.com/newest",
                publish_time=now,
            ),
            _StoredRow(
                id="content-older",
                title="Older",
                content="Body older",
                url="https://example.com/older",
                publish_time=now - timedelta(hours=1),
            ),
        ]
    )
    embedding_service = _FakeEmbeddingService(
        {
            "content-newest": [0.1, 0.2, 0.3],
            "content-older": [0.4, 0.5, 0.6],
        }
    )
    runner = EmbeddingBackfillRunner(
        cast(Any, data_manager), cast(Any, embedding_service), batch_size=1
    )

    first_report = runner.run()
    first_generated_ids = list(embedding_service.generated_ids)
    second_report = runner.run()

    assert first_report.rows_embedded == 2
    assert first_report.rows_failed == 0
    assert first_report.batches_processed == 2
    assert second_report.rows_embedded == 0
    assert second_report.rows_examined == 0
    assert embedding_service.generated_ids == first_generated_ids
    assert embedding_service.generated_ids == ["content-newest", "content-older"]
    assert embedding_service.generated_batches == [
        ["content-newest"],
        ["content-older"],
    ]
    assert all(row.embedding is not None for row in data_manager.rows)
    assert data_manager.commit_count == 2


def test_backfill_skips_failed_rows_and_continues(caplog):
    now = datetime.now(timezone.utc)
    data_manager = _FakeDataManager(
        rows=[
            _StoredRow(
                id="content-newest",
                title="Newest",
                content="Body newest",
                url="https://example.com/newest",
                publish_time=now,
            ),
            _StoredRow(
                id="content-older",
                title="Older",
                content="Body older",
                url="https://example.com/older",
                publish_time=now - timedelta(hours=1),
            ),
        ]
    )
    embedding_service = _FakeEmbeddingService(
        {
            "content-newest": None,
            "content-older": [0.4, 0.5, 0.6],
        }
    )
    runner = EmbeddingBackfillRunner(
        cast(Any, data_manager), cast(Any, embedding_service), batch_size=100
    )

    with caplog.at_level(logging.WARNING):
        report = runner.run()

    newest = next(row for row in data_manager.rows if row.id == "content-newest")
    older = next(row for row in data_manager.rows if row.id == "content-older")

    assert report.rows_examined == 2
    assert report.rows_embedded == 1
    assert report.rows_failed == 1
    assert report.batches_processed == 1
    assert newest.embedding is None
    assert older.embedding == "[0.4,0.5,0.6]"
    assert embedding_service.generated_batches == [["content-newest", "content-older"]]
    assert "Embedding生成失败，跳过该行" in caplog.text


def test_backfill_only_excludes_failed_rows_across_batches():
    now = datetime.now(timezone.utc)
    data_manager = _FakeDataManager(
        rows=[
            _StoredRow(
                id="content-failed",
                title="Failed",
                content="Body failed",
                url="https://example.com/failed",
                publish_time=now,
            ),
            _StoredRow(
                id="content-middle",
                title="Middle",
                content="Body middle",
                url="https://example.com/middle",
                publish_time=now - timedelta(minutes=1),
            ),
            _StoredRow(
                id="content-oldest",
                title="Oldest",
                content="Body oldest",
                url="https://example.com/oldest",
                publish_time=now - timedelta(minutes=2),
            ),
        ]
    )
    embedding_service = _FakeEmbeddingService(
        {
            "content-failed": None,
            "content-middle": [0.1, 0.2, 0.3],
            "content-oldest": [0.4, 0.5, 0.6],
        }
    )
    runner = EmbeddingBackfillRunner(
        cast(Any, data_manager), cast(Any, embedding_service), batch_size=1
    )

    report = runner.run()

    assert report.rows_examined == 3
    assert report.rows_embedded == 2
    assert report.rows_failed == 1
    assert embedding_service.generated_ids == [
        "content-failed",
        "content-middle",
        "content-oldest",
    ]
    assert data_manager.fetch_exclude_ids == [
        [],
        ["content-failed"],
        ["content-failed"],
        ["content-failed"],
    ]


def test_backfill_rejects_sqlite_backend_fast():
    data_manager = _FakeDataManager(rows=[], backend="sqlite")
    embedding_service = _FakeEmbeddingService({})

    with pytest.raises(UnsupportedBackendError, match="embedding backfill runtime"):
        EmbeddingBackfillRunner(
            cast(Any, data_manager), cast(Any, embedding_service)
        ).run()


def test_intelligence_backfill_embeds_only_recent_rows():
    now = datetime.utcnow()
    intel_rows = [
        _StoredIntelRow(
            id="intel-recent",
            raw_text="Recent intelligence item text",
            collected_at=now - timedelta(days=1),
        ),
        _StoredIntelRow(
            id="intel-old",
            raw_text="Old intelligence item text",
            collected_at=now - timedelta(days=8),
        ),
    ]
    data_manager = _FakeDataManager(
        rows=[], intel_rows=intel_rows
    )
    embedding_service = _FakeEmbeddingService(
        {
            "Recent intelligence item text": [0.1, 0.2, 0.3],
            "Old intelligence item text": [0.4, 0.5, 0.6],
        }
    )
    runner = EmbeddingBackfillRunner(
        cast(Any, data_manager),
        cast(Any, embedding_service),
        intelligence_days=7,
    )

    report = runner.run()

    recent = next(r for r in intel_rows if r.id == "intel-recent")
    old = next(r for r in intel_rows if r.id == "intel-old")

    assert report.rows_intelligence_embedded == 1
    assert recent.embedding == [0.1, 0.2, 0.3]
    assert old.embedding is None


def test_intelligence_backfill_skips_blank_raw_text():
    now = datetime.utcnow()
    intel_rows = [
        _StoredIntelRow(
            id="intel-blank",
            raw_text="   ",
            collected_at=now - timedelta(days=1),
        ),
        _StoredIntelRow(
            id="intel-valid",
            raw_text="Valid intelligence content",
            collected_at=now - timedelta(days=1),
        ),
    ]
    data_manager = _FakeDataManager(
        rows=[], intel_rows=intel_rows
    )
    embedding_service = _FakeEmbeddingService(
        {
            "Valid intelligence content": [0.5, 0.6, 0.7],
        }
    )
    runner = EmbeddingBackfillRunner(
        cast(Any, data_manager),
        cast(Any, embedding_service),
        intelligence_days=7,
    )

    report = runner.run()

    valid = next(r for r in intel_rows if r.id == "intel-valid")
    blank = next(r for r in intel_rows if r.id == "intel-blank")

    assert report.rows_intelligence_embedded == 1
    assert valid.embedding == [0.5, 0.6, 0.7]
    assert blank.embedding is None


def test_default_backfill_remains_news_only():
    now = datetime.utcnow()
    intel_rows = [
        _StoredIntelRow(
            id="intel-news-only",
            raw_text="Should not be embedded when no intelligence_days",
            collected_at=now - timedelta(days=1),
        ),
    ]
    data_manager = _FakeDataManager(
        rows=[], intel_rows=intel_rows
    )
    embedding_service = _FakeEmbeddingService(
        {
            "Should not be embedded when no intelligence_days": [0.8, 0.9],
        }
    )
    runner = EmbeddingBackfillRunner(
        cast(Any, data_manager),
        cast(Any, embedding_service),
    )

    report = runner.run()

    assert report.rows_intelligence_embedded == 0
    assert report.rows_intelligence_examined == 0
    assert intel_rows[0].embedding is None


def test_intelligence_backfill_report_counts():
    now = datetime.utcnow()
    intel_rows = [
        _StoredIntelRow(
            id="intel-a",
            raw_text="Intel content A",
            collected_at=now - timedelta(days=1),
        ),
        _StoredIntelRow(
            id="intel-b",
            raw_text="Intel content B",
            collected_at=now - timedelta(hours=12),
        ),
    ]
    data_manager = _FakeDataManager(
        rows=[], intel_rows=intel_rows
    )
    embedding_service = _FakeEmbeddingService(
        {
            "Intel content A": [0.1, 0.2],
            "Intel content B": [0.3, 0.4],
        }
    )
    runner = EmbeddingBackfillRunner(
        cast(Any, data_manager),
        cast(Any, embedding_service),
        intelligence_days=7,
    )

    report = runner.run()

    assert report.batches_processed == 0
    assert report.rows_embedded == 0
    assert report.batches_intelligence_processed >= 1
    assert report.rows_intelligence_examined == 2
    assert report.rows_intelligence_embedded == 2
    assert report.rows_intelligence_failed == 0
