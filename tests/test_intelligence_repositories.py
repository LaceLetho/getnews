from datetime import datetime, timedelta
from pathlib import Path

from crypto_news_analyzer.domain.repositories import IntelligenceRepository
from crypto_news_analyzer.domain.models import (
    CanonicalIntelligenceEntry,
    EntryType,
    ExtractionObservation,
    IntelligenceCrawlCheckpoint,
    RawIntelligenceItem,
)
from crypto_news_analyzer.models import StorageConfig
from crypto_news_analyzer.storage.data_manager import DataManager
from crypto_news_analyzer.storage.repositories import SQLiteIntelligenceRepository


def _build_repository(db_path: Path):
    manager = DataManager(StorageConfig(database_path=str(db_path)))
    return manager, SQLiteIntelligenceRepository(manager)


def test_intelligence_repository_implements_contract_and_round_trips(tmp_path: Path):
    manager, repository = _build_repository(tmp_path / "intelligence.db")
    assert isinstance(repository, IntelligenceRepository)

    try:
        raw = RawIntelligenceItem.create(
            source_type="telegram",
            source_id="chat-1",
            raw_text="alpha channel says gm",
            content_hash="hash-1",
            expires_at=datetime.utcnow() + timedelta(days=30),
        )
        assert repository.save_raw_item(raw) == raw.id
        assert repository.get_raw_items_by_source("telegram", "chat-1", 10, 0)[0].id == raw.id

        observation = ExtractionObservation.create(
            raw_item_id=raw.id,
            entry_type=EntryType.CHANNEL.value,
            confidence=0.8,
            model_name="model-a",
            prompt_version="p1",
            schema_version="s1",
            channel_name="Alpha",
            channel_urls=["https://t.me/alpha"],
        )
        assert repository.save_observation(observation) == observation.id
        assert repository.get_observations_by_raw_item(raw.id)[0].id == observation.id
        assert repository.get_raw_item_ids_with_existing_observations([raw.id], "p1") == {raw.id}
        assert repository.get_raw_item_ids_with_existing_observations([raw.id], "other") == set()
        assert repository.get_raw_item_ids_with_existing_observations([], "p1") == set()
        assert repository.get_uncanonicalized_observations(10)[0].id == observation.id
        assert repository.mark_observation_canonicalized(observation.id) is True
        assert repository.get_uncanonicalized_observations(10) == []

        entry = CanonicalIntelligenceEntry.create(
            entry_type=EntryType.CHANNEL.value,
            normalized_key="https://t.me/alpha",
            display_name="Alpha",
            confidence=0.9,
            latest_raw_item_id=raw.id,
            aliases=["alpha"],
        )
        assert repository.save_canonical_entry(entry) == entry.id
        loaded = repository.get_canonical_entry_by_normalized_key(
            EntryType.CHANNEL.value, "https://t.me/alpha"
        )
        assert loaded is not None
        assert loaded.aliases == ["alpha"]

        entry.display_name = "Alpha Updated"
        assert repository.upsert_canonical_entry(entry) == entry.id
        assert (
            repository.list_canonical_entries(entry_type=EntryType.CHANNEL.value)[0].display_name
            == "Alpha Updated"
        )

        assert repository.update_embedding(entry.id, [1.0, 0.0, 0.0], "test-embedding") is True
        assert repository.get_entries_missing_embeddings(10) == []
        assert repository.semantic_search([1.0, 0.0, 0.0], limit=1)[0][0].id == entry.id

        other = CanonicalIntelligenceEntry.create(
            entry_type=EntryType.CHANNEL.value,
            normalized_key="https://t.me/beta",
            display_name="Beta",
        )
        repository.save_canonical_entry(other)
        repository.save_related_candidate(entry.id, other.id, 0.77, "semantic_similarity")

        checkpoint = IntelligenceCrawlCheckpoint.create(
            source_type="telegram",
            source_id="chat-1",
            checkpoint_data={"cursor": "100"},
        )
        repository.save_checkpoint(checkpoint)
        assert repository.get_checkpoint("telegram", "chat-1").checkpoint_data == {"cursor": "100"}
    finally:
        manager.close()


def test_raw_item_ttl_cleanup_and_text_purge(tmp_path: Path):
    manager, repository = _build_repository(tmp_path / "intelligence-ttl.db")
    try:
        old = RawIntelligenceItem.create(
            source_type="telegram",
            source_id="chat-1",
            raw_text="old",
            content_hash="old-hash",
            expires_at=datetime.utcnow() - timedelta(days=1),
        )
        fresh = RawIntelligenceItem.create(
            source_type="telegram",
            source_id="chat-1",
            raw_text="fresh",
            content_hash="fresh-hash",
            expires_at=datetime.utcnow() + timedelta(days=1),
        )
        repository.save_raw_item(old)
        repository.save_raw_item(fresh)

        expiring = repository.get_raw_items_expiring_before(datetime.utcnow())
        assert [item.id for item in expiring] == [old.id]
        assert repository.delete_expired_raw_items(datetime.utcnow()) == 1
        assert [
            item.id for item in repository.get_raw_items_by_source("telegram", "chat-1", 10, 0)
        ] == [fresh.id]
    finally:
        manager.close()


def test_intelligence_schema_created_without_audit_tables(tmp_path: Path):
    manager = DataManager(StorageConfig(database_path=str(tmp_path / "schema.db")))
    try:
        with manager._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
            tables = {row[0] for row in cursor.fetchall()}
            cursor.execute("PRAGMA table_info(intelligence_canonical_entries)")
            columns = {row[1] for row in cursor.fetchall()}
            cursor.execute("PRAGMA index_list(intelligence_canonical_entries)")
            indexes = {row[1] for row in cursor.fetchall()}

        assert {
            "raw_intelligence_items",
            "intelligence_extraction_observations",
            "intelligence_canonical_entries",
            "intelligence_aliases",
            "intelligence_related_candidates",
            "intelligence_crawl_checkpoints",
        }.issubset(tables)
        assert {"embedding", "embedding_model", "embedding_updated_at"}.issubset(columns)
        assert "idx_intelligence_canonical_entries_type_key" in indexes
        assert not any("audit" in table for table in tables)
    finally:
        manager.close()


def test_existing_observation_lookup_handles_dict_rows(tmp_path: Path):
    manager = DataManager(StorageConfig(database_path=str(tmp_path / "dict-row.db")))
    try:
        raw = RawIntelligenceItem.create(
            source_type="telegram",
            source_id="chat-1",
            raw_text="alpha",
            content_hash="hash-dict",
            expires_at=datetime.utcnow() + timedelta(days=30),
        )
        observation = ExtractionObservation.create(
            raw_item_id=raw.id,
            entry_type=EntryType.CHANNEL.value,
            confidence=0.8,
            model_name="model-a",
            prompt_version="p1",
            schema_version="s1",
            channel_name="Alpha",
        )
        manager.upsert_raw_intelligence_item(raw.to_dict())
        manager.upsert_intelligence_observation(observation.to_dict())

        original_get_connection = manager._get_connection

        class DictRowCursor:
            def __init__(self, cursor):
                self.cursor = cursor

            def execute(self, *args, **kwargs):
                return self.cursor.execute(*args, **kwargs)

            def fetchall(self):
                rows = self.cursor.fetchall()
                return [dict(row) for row in rows]

        class DictRowConnection:
            def __init__(self, connection):
                self.connection = connection

            def cursor(self):
                return DictRowCursor(self.connection.cursor())

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        class DictRowContext:
            def __enter__(self):
                self.inner = original_get_connection()
                connection = self.inner.__enter__()
                return DictRowConnection(connection)

            def __exit__(self, exc_type, exc, tb):
                return self.inner.__exit__(exc_type, exc, tb)

        manager._get_connection = lambda: DictRowContext()

        assert manager.get_raw_item_ids_with_existing_observations([raw.id], "p1") == {raw.id}
    finally:
        manager.close()


def test_intelligence_repository_ignore_lifecycle(tmp_path: Path):
    manager, repository = _build_repository(tmp_path / "intelligence-ignore.db")
    try:
        raw = RawIntelligenceItem.create(
            source_type="telegram",
            source_id="chat-1",
            raw_text="ignore me",
            content_hash="hash-ignore",
            expires_at=datetime.utcnow() + timedelta(days=30),
        )
        repository.save_raw_item(raw)

        entry = CanonicalIntelligenceEntry.create(
            entry_type=EntryType.CHANNEL.value,
            normalized_key="https://t.me/ignoreme",
            display_name="Ignore Me",
        )
        repository.save_canonical_entry(entry)

        # Default: not ignored
        loaded = repository.get_canonical_entry_by_id(entry.id)
        assert loaded is not None
        assert loaded.is_ignored is False
        assert loaded.ignored_at is None
        assert loaded.ignored_by is None

        # Ignore
        ignored = repository.ignore_canonical_entry(entry.id, ignored_by="telegram:123")
        assert ignored is not None
        assert ignored.is_ignored is True
        assert ignored.ignored_at is not None
        assert ignored.ignored_by == "telegram:123"

        # List excludes ignored
        visible = repository.list_canonical_entries(entry_type=EntryType.CHANNEL.value)
        assert all(e.id != entry.id for e in visible)

        # Count excludes ignored
        assert repository.count_canonical_entries(entry_type=EntryType.CHANNEL.value) == 0

        # Exact lookups still return ignored
        by_id = repository.get_canonical_entry_by_id(entry.id)
        assert by_id is not None
        assert by_id.is_ignored is True

        by_key = repository.get_canonical_entry_by_normalized_key(
            EntryType.CHANNEL.value, "https://t.me/ignoreme"
        )
        assert by_key is not None
        assert by_key.is_ignored is True

        # Unignore
        unignored = repository.unignore_canonical_entry(entry.id)
        assert unignored is not None
        assert unignored.is_ignored is False
        assert unignored.ignored_at is None
        assert unignored.ignored_by is None

        # List includes again
        visible_again = repository.list_canonical_entries(entry_type=EntryType.CHANNEL.value)
        assert any(e.id == entry.id for e in visible_again)

        # List ignored is empty after unignore
        assert repository.list_ignored_canonical_entries() == []
        assert repository.count_ignored_canonical_entries() == 0

    finally:
        manager.close()


def test_intelligence_repository_ignore_missing_and_idempotent(tmp_path: Path):
    manager, repository = _build_repository(tmp_path / "intelligence-ignore-idem.db")
    try:
        # Ignore missing ID
        assert repository.ignore_canonical_entry("nonexistent-id") is None

        # Unignore missing ID
        assert repository.unignore_canonical_entry("nonexistent-id") is None

        # Create entry for idempotent tests
        raw = RawIntelligenceItem.create(
            source_type="telegram",
            source_id="chat-1",
            raw_text="idempotent",
            content_hash="hash-idem",
            expires_at=datetime.utcnow() + timedelta(days=30),
        )
        repository.save_raw_item(raw)

        entry = CanonicalIntelligenceEntry.create(
            entry_type=EntryType.SLANG.value,
            normalized_key="test-term",
            display_name="Test Term",
        )
        repository.save_canonical_entry(entry)

        # Ignore, then ignore again (idempotent)
        first = repository.ignore_canonical_entry(entry.id, ignored_by="user-a")
        assert first is not None
        assert first.is_ignored is True
        assert first.ignored_by == "user-a"
        assert first.ignored_at is not None

        second = repository.ignore_canonical_entry(entry.id, ignored_by="user-b")
        assert second is not None
        assert second.is_ignored is True
        # ignored_by is overwritten (latest caller wins)
        assert second.ignored_by == "user-b"

        # Unignore, then unignore again (idempotent)
        first_un = repository.unignore_canonical_entry(entry.id)
        assert first_un is not None
        assert first_un.is_ignored is False
        assert first_un.ignored_at is None
        assert first_un.ignored_by is None

        second_un = repository.unignore_canonical_entry(entry.id)
        assert second_un is not None
        assert second_un.is_ignored is False
        assert second_un.ignored_at is None
        assert second_un.ignored_by is None

    finally:
        manager.close()

