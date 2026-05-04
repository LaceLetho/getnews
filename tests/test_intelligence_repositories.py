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
