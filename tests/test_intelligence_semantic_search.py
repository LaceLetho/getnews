from datetime import datetime, timedelta
from importlib import import_module
from pathlib import Path
from typing import List, Optional

from crypto_news_analyzer.domain.models import (
    CanonicalIntelligenceEntry,
    EntryType,
    PrimaryLabel,
    RawIntelligenceItem,
)
from crypto_news_analyzer.models import StorageConfig
from crypto_news_analyzer.storage.data_manager import DataManager
from crypto_news_analyzer.storage.repositories import SQLiteIntelligenceRepository

IntelligenceSearchService = import_module(
    "crypto_news_analyzer.intelligence.search"
).IntelligenceSearchService


class FakeEmbeddingService:
    def __init__(
        self, embedding: Optional[List[float]] = None, model: str = "test-embedding-model"
    ):
        self.embedding = embedding or [1.0, 0.0, 0.0]
        self.model = model
        self.generated_texts: List[str] = []

    def generate_embedding(self, text: str) -> List[float]:
        self.generated_texts.append(text)
        return list(self.embedding)


def _build_repository(db_path: Path):
    manager = DataManager(StorageConfig(database_path=str(db_path)))
    return manager, SQLiteIntelligenceRepository(manager)


def _build_service(db_path: Path, embedding: Optional[List[float]] = None):
    manager, repository = _build_repository(db_path)
    embedding_service = FakeEmbeddingService(embedding=embedding)
    service = IntelligenceSearchService(
        embedding_service=embedding_service,
        intelligence_repository=repository,
        storage_config=manager.config,
    )
    return manager, repository, embedding_service, service


def test_generate_embedding_concatenates_slang_fields_and_stores_model(tmp_path: Path):
    manager, repository, embedding_service, service = _build_service(tmp_path / "semantic.db")
    try:
        entry = CanonicalIntelligenceEntry.create(
            entry_type=EntryType.SLANG.value,
            normalized_key="diamondhands",
            display_name="diamond hands",
            explanation="Refuses to sell during volatility",
            usage_summary="Used when traders hold through drawdowns",
            aliases=["hodl", "paper hand opposite"],
            primary_label=PrimaryLabel.CRYPTO.value,
            secondary_tags=["trading", "slang"],
            confidence=0.8,
        )
        repository.save_canonical_entry(entry)

        assert service.generate_and_store_embedding(entry) is True

        assert embedding_service.generated_texts == [
            "diamond hands Refuses to sell during volatility "
            "Used when traders hold through drawdowns hodl paper hand opposite crypto trading slang"
        ]
        loaded = repository.get_canonical_entry_by_normalized_key(
            EntryType.SLANG.value,
            "diamondhands",
        )
        assert loaded is not None
        assert loaded.embedding == [1.0, 0.0, 0.0]
        assert loaded.embedding_model == "test-embedding-model"
        assert loaded.embedding_updated_at is not None
    finally:
        manager.close()


def test_semantic_search_filters_by_type_label_and_time_window(tmp_path: Path):
    manager, repository, embedding_service, service = _build_service(tmp_path / "filters.db")
    try:
        now = datetime.utcnow()
        matching = CanonicalIntelligenceEntry.create(
            entry_type=EntryType.SLANG.value,
            normalized_key="gm",
            display_name="gm",
            primary_label=PrimaryLabel.AI.value,
            confidence=0.9,
            last_seen_at=now,
        )
        wrong_type = CanonicalIntelligenceEntry.create(
            entry_type=EntryType.CHANNEL.value,
            normalized_key="example.com/ai",
            display_name="AI Channel",
            primary_label=PrimaryLabel.AI.value,
            confidence=0.9,
            last_seen_at=now,
        )
        wrong_label = CanonicalIntelligenceEntry.create(
            entry_type=EntryType.SLANG.value,
            normalized_key="ape",
            display_name="ape",
            primary_label=PrimaryLabel.CRYPTO.value,
            confidence=0.9,
            last_seen_at=now,
        )
        outside_window = CanonicalIntelligenceEntry.create(
            entry_type=EntryType.SLANG.value,
            normalized_key="oldai",
            display_name="old ai",
            primary_label=PrimaryLabel.AI.value,
            confidence=0.9,
            last_seen_at=now - timedelta(days=10),
        )

        for entry in [matching, wrong_type, wrong_label, outside_window]:
            repository.save_canonical_entry(entry)
            repository.update_embedding(entry.id, [1.0, 0.0, 0.0], "test-embedding-model")

        results = service.semantic_search(
            "AI slang",
            entry_type=EntryType.SLANG.value,
            primary_label=PrimaryLabel.AI.value,
            window_days=2,
            limit=10,
        )

        assert [entry.id for entry, _score in results] == [matching.id]
        assert embedding_service.generated_texts == ["AI slang"]
    finally:
        manager.close()


def test_expired_raw_text_is_not_used_for_entry_embedding(tmp_path: Path):
    manager, repository, embedding_service, service = _build_service(tmp_path / "expired.db")
    try:
        raw = RawIntelligenceItem.create(
            source_type="telegram_group",
            source_id="chat-1",
            raw_text="expired raw evidence must not be embedded",
            content_hash="expired-hash",
            expires_at=datetime.utcnow() - timedelta(days=1),
        )
        repository.save_raw_item(raw)
        entry = CanonicalIntelligenceEntry.create(
            entry_type=EntryType.SLANG.value,
            normalized_key="ct",
            display_name="CT",
            explanation="Crypto Twitter shorthand",
            latest_raw_item_id=raw.id,
            confidence=0.7,
        )
        repository.save_canonical_entry(entry)
        repository.delete_expired_raw_items(datetime.utcnow())

        assert service.generate_and_store_embedding(entry) is True

        assert embedding_service.generated_texts == ["CT Crypto Twitter shorthand"]
        assert "expired raw evidence" not in embedding_service.generated_texts[0]
    finally:
        manager.close()


def test_batch_generate_embeddings_processes_all_entries(tmp_path: Path):
    manager, repository, _embedding_service, service = _build_service(tmp_path / "batch.db")
    try:
        entries = [
            CanonicalIntelligenceEntry.create(
                entry_type=EntryType.SLANG.value,
                normalized_key=f"term-{index}",
                display_name=f"term {index}",
            )
            for index in range(3)
        ]
        for entry in entries:
            repository.save_canonical_entry(entry)

        assert service.batch_generate_embeddings(entries, batch_size=2) == 3
        assert repository.get_entries_missing_embeddings(10) == []
    finally:
        manager.close()
