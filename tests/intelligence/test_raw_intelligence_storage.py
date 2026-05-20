from datetime import datetime, timedelta

from crypto_news_analyzer.domain.models import RawIntelligenceItem
from crypto_news_analyzer.models import StorageConfig
from crypto_news_analyzer.storage.data_manager import DataManager
from crypto_news_analyzer.storage.repositories import SQLiteIntelligenceRepository


def test_save_raw_item_is_idempotent_for_external_dedupe_key() -> None:
    manager = DataManager(StorageConfig(database_path=":memory:"))
    repository = SQLiteIntelligenceRepository(manager)
    expires_at = datetime.utcnow() + timedelta(days=1)

    first = RawIntelligenceItem.create(
        source_type="v2ex",
        source_id="claude",
        external_id="1214245",
        raw_text="original topic text",
        content_hash="hash-1",
        expires_at=expires_at,
    )
    duplicate = RawIntelligenceItem.create(
        source_type="v2ex",
        source_id="claude",
        external_id="1214245",
        raw_text="updated topic text",
        content_hash="hash-2",
        expires_at=expires_at,
    )

    first_id = repository.save_raw_item(first)
    duplicate_id = repository.save_raw_item(duplicate)

    assert duplicate_id == first_id
    stored = repository.get_raw_item_by_id(first_id)
    assert stored is not None
    assert stored.id == first.id
    assert stored.raw_text == "updated topic text"
    assert stored.content_hash == "hash-2"
    assert repository.get_raw_items_by_source("v2ex", "claude", limit=10, offset=0) == [stored]
