"""Real PostgreSQL/pgvector integration tests for intelligence storage."""

# pyright: reportPrivateUsage=false, reportUnknownVariableType=false, reportUnknownMemberType=false
# pyright: reportUnusedCallResult=false, reportExplicitAny=false, reportDeprecated=false

from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Optional, cast

import pytest

from crypto_news_analyzer.models import StorageConfig
from crypto_news_analyzer.storage.data_manager import DataManager
from crypto_news_analyzer.storage.repositories import SQLiteIntelligenceRepository
from crypto_news_analyzer.utils.errors import StorageError

pytestmark = pytest.mark.integration

VECTOR_DIMENSIONS = 1536
INTELLIGENCE_TABLES = {
    "raw_intelligence_items",
    "intelligence_extraction_observations",
    "intelligence_canonical_entries",
    "intelligence_aliases",
    "intelligence_related_candidates",
    "intelligence_crawl_checkpoints",
}


@pytest.fixture
def intelligence_manager(test_database_url: str):
    manager = DataManager(
        StorageConfig(
            backend="postgres",
            database_url=test_database_url,
            pgvector_dimensions=VECTOR_DIMENSIONS,
        )
    )
    _truncate_intelligence_tables(manager)
    try:
        yield manager
    finally:
        _truncate_intelligence_tables(manager)
        manager.close()


def test_real_postgres_safety_guard_refuses_non_test_db(
    safe_test_database_url_guard: Callable[[str], None],
):
    with pytest.raises(RuntimeError, match="must contain 'test' or 'ci'"):
        safe_test_database_url_guard("postgresql://user:pass@localhost:5432/crypto_news_prod")

    safe_test_database_url_guard("postgresql://user:pass@localhost:5432/crypto_news_test")
    safe_test_database_url_guard("postgresql://user:pass@localhost:5432/crypto_news_ci")


@pytest.mark.real_postgres
def test_real_postgres_creates_all_intelligence_tables(intelligence_manager: DataManager):
    with intelligence_manager._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name = ANY(%s)
            """,
            (list(INTELLIGENCE_TABLES),),
        )
        table_rows = cast(list[dict[str, Any]], cursor.fetchall())
        tables = {row["table_name"] for row in table_rows}
        cursor.execute("""
            SELECT udt_name FROM information_schema.columns
            WHERE table_name = 'intelligence_canonical_entries'
              AND column_name = 'embedding'
            """)
        vector_column = cast(Optional[dict[str, Any]], cursor.fetchone())

    assert tables == INTELLIGENCE_TABLES
    assert vector_column is not None
    assert vector_column["udt_name"] == "vector"


@pytest.mark.real_postgres
def test_real_postgres_vector_insert_and_search(intelligence_manager: DataManager):
    entries = [
        _canonical_entry("entry-alpha", "alpha", "Alpha", _embedding(0)),
        _canonical_entry("entry-beta", "beta", "Beta", _embedding(1)),
        _canonical_entry("entry-mixed", "mixed", "Mixed", _embedding(0, 1, 0.7)),
    ]
    for entry in entries:
        intelligence_manager.upsert_canonical_intelligence_entry(entry, by_normalized_key=True)

    fetched = intelligence_manager.get_canonical_intelligence_entry_by_normalized_key(
        "channel", "alpha"
    )
    assert fetched is not None
    assert fetched["embedding"][:3] == pytest.approx([1.0, 0.0, 0.0])

    results = intelligence_manager.semantic_search_canonical_intelligence_entries(
        query_embedding=_embedding(0),
        entry_type="channel",
        limit=3,
    )

    assert [entry["id"] for entry, _score in results] == [
        "entry-alpha",
        "entry-mixed",
        "entry-beta",
    ]
    assert results[0][1] > results[1][1] > results[2][1]


@pytest.mark.real_postgres
def test_real_postgres_canonical_upsert_increments_evidence_count(
    intelligence_manager: DataManager,
):
    first = _canonical_entry("entry-upsert-original", "gm", "GM", None, evidence_count=1)
    second = _canonical_entry("entry-upsert-new", "gm", "GM updated", None, evidence_count=2)

    intelligence_manager.upsert_canonical_intelligence_entry(first, by_normalized_key=True)
    intelligence_manager.upsert_canonical_intelligence_entry(second, by_normalized_key=True)

    fetched = intelligence_manager.get_canonical_intelligence_entry_by_normalized_key(
        "channel", "gm"
    )

    assert fetched is not None
    assert fetched["id"] == "entry-upsert-original"
    assert fetched["display_name"] == "GM updated"
    assert fetched["evidence_count"] == 2


@pytest.mark.real_postgres
def test_real_postgres_raw_ttl_purge(intelligence_manager: DataManager):
    repository = SQLiteIntelligenceRepository(intelligence_manager)
    now = datetime.now(timezone.utc)
    old_collected_at = now - timedelta(days=40)
    recent_collected_at = now - timedelta(hours=1)
    cutoff_time = now - timedelta(days=1)

    intelligence_manager.upsert_raw_intelligence_item(
        _raw_item("raw-old", "old raw text", old_collected_at)
    )
    intelligence_manager.upsert_raw_intelligence_item(
        _raw_item("raw-recent", "recent raw text", recent_collected_at)
    )

    purged_count = repository.purge_raw_text_older_than(cutoff_time)

    with intelligence_manager._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, raw_text FROM raw_intelligence_items WHERE id IN (%s, %s)",
            ("raw-old", "raw-recent"),
        )
        rows = cast(list[dict[str, Any]], cursor.fetchall())
        raw_text_by_id = {row["id"]: row["raw_text"] for row in rows}

    assert purged_count == 1
    assert raw_text_by_id["raw-old"] in (None, "")
    assert raw_text_by_id["raw-recent"] == "recent raw text"


@pytest.mark.real_postgres
def test_real_postgres_raw_ttl_purge_preserves_canonical_entries(
    intelligence_manager: DataManager,
):
    repository = SQLiteIntelligenceRepository(intelligence_manager)
    cutoff_time = datetime.now(timezone.utc) - timedelta(days=1)
    intelligence_manager.upsert_raw_intelligence_item(
        _raw_item("raw-canonical", "old canonical evidence", cutoff_time - timedelta(days=1))
    )
    intelligence_manager.upsert_canonical_intelligence_entry(
        {
            **_canonical_entry("canonical-preserved", "alpha", "Alpha", None),
            "latest_raw_item_id": "raw-canonical",
        },
        by_normalized_key=True,
    )

    assert repository.purge_raw_text_older_than(cutoff_time) == 1

    fetched = intelligence_manager.get_canonical_intelligence_entry_by_normalized_key(
        "channel", "alpha"
    )
    with intelligence_manager._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT raw_text FROM raw_intelligence_items WHERE id = %s", ("raw-canonical",))
        raw_row = cast(dict[str, Any], cursor.fetchone())

    assert fetched is not None
    assert fetched["id"] == "canonical-preserved"
    assert fetched["latest_raw_item_id"] == "raw-canonical"
    assert raw_row["raw_text"] in (None, "")


@pytest.mark.real_postgres
def test_real_postgres_related_candidate_constraint(intelligence_manager: DataManager):
    intelligence_manager.upsert_canonical_intelligence_entry(
        _canonical_entry("related-a", "related-a", "Related A", None),
        by_normalized_key=True,
    )
    intelligence_manager.upsert_canonical_intelligence_entry(
        _canonical_entry("related-b", "related-b", "Related B", None),
        by_normalized_key=True,
    )

    with pytest.raises(StorageError):
        with intelligence_manager._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO intelligence_related_candidates
                (entry_id_a, entry_id_b, similarity_score, relationship_type)
                VALUES (%s, %s, %s, %s)
                """,
                ("related-a", "related-b", 0.9, "semantic"),
            )
            cursor.execute(
                """
                INSERT INTO intelligence_related_candidates
                (entry_id_a, entry_id_b, similarity_score, relationship_type)
                VALUES (%s, %s, %s, %s)
                """,
                ("related-a", "related-b", 0.8, "duplicate"),
            )


def _truncate_intelligence_tables(manager: DataManager) -> None:
    with manager._get_connection() as conn:
        conn.cursor().execute("""
            TRUNCATE TABLE
                intelligence_aliases,
                intelligence_canonical_entries,
                intelligence_crawl_checkpoints,
                intelligence_extraction_observations,
                intelligence_related_candidates,
                raw_intelligence_items
            RESTART IDENTITY CASCADE
            """)


def _embedding(
    primary_axis: int, secondary_axis: Optional[int] = None, secondary_value: float = 0.0
):
    embedding = [0.0] * VECTOR_DIMENSIONS
    embedding[primary_axis] = 1.0
    if secondary_axis is not None:
        embedding[primary_axis] = 0.7
        embedding[secondary_axis] = secondary_value
    return embedding


def _canonical_entry(
    entry_id: str,
    normalized_key: str,
    display_name: str,
    embedding: Optional[list[float]],
    evidence_count: int = 1,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    return {
        "id": entry_id,
        "entry_type": "channel",
        "normalized_key": normalized_key,
        "display_name": display_name,
        "explanation": f"Explanation for {display_name}",
        "usage_summary": f"Usage summary for {display_name}",
        "primary_label": "crypto",
        "secondary_tags": ["integration"],
        "confidence": 0.9,
        "first_seen_at": now - timedelta(days=1),
        "last_seen_at": now,
        "evidence_count": evidence_count,
        "latest_raw_item_id": None,
        "prompt_version": "integration-test",
        "model_name": "test-model",
        "schema_version": "v1",
        "embedding": embedding,
        "embedding_model": "test-embedding-model" if embedding else None,
        "embedding_updated_at": now if embedding else None,
        "created_at": now,
        "updated_at": now,
    }


def _raw_item(item_id: str, raw_text: str, collected_at: datetime) -> dict[str, Any]:
    return {
        "id": item_id,
        "source_type": "telegram_group",
        "source_id": "integration-source",
        "external_id": item_id,
        "source_url": f"https://example.com/{item_id}",
        "chat_id": "chat-1",
        "thread_id": None,
        "topic_id": None,
        "raw_text": raw_text,
        "content_hash": f"hash-{item_id}",
        "published_at": collected_at,
        "collected_at": collected_at,
        "expires_at": collected_at + timedelta(days=30),
        "edit_status": None,
        "edit_timestamp": None,
        "created_at": collected_at,
    }
