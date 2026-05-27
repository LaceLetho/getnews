"""Tests for datasource_id persistence on RawIntelligenceItem during collection (Wave 1 Task 3)."""

from datetime import datetime, timedelta

from crypto_news_analyzer.domain.models import DataSource, RawIntelligenceItem
from crypto_news_analyzer.models import StorageConfig
from crypto_news_analyzer.storage.data_manager import DataManager
from crypto_news_analyzer.storage.repositories import SQLiteIntelligenceRepository


# ---------------------------------------------------------------------------
# Model serialization round-trip
# ---------------------------------------------------------------------------


def test_raw_item_roundtrip_preserves_datasource_id():
    """to_dict() → from_dict() preserves datasource_id when present."""
    item = RawIntelligenceItem.create(
        source_type="telegram_group",
        source_id="-100999",
        external_id="123",
        raw_text="Whale alert",
        content_hash="hash123",
        expires_at=datetime.utcnow() + timedelta(days=30),
        datasource_id="ds-uuid-001",
    )

    d = item.to_dict()
    assert d["datasource_id"] == "ds-uuid-001"

    restored = RawIntelligenceItem.from_dict(d)
    assert restored.datasource_id == "ds-uuid-001"
    assert restored.source_type == item.source_type
    assert restored.source_id == item.source_id


def test_raw_item_roundtrip_preserves_none_datasource_id():
    """to_dict() → from_dict() preserves datasource_id=None for legacy items."""
    item = RawIntelligenceItem.create(
        source_type="v2ex",
        source_id="claude",
        raw_text="Dev topic",
        content_hash="hash456",
        expires_at=datetime.utcnow() + timedelta(days=30),
        # datasource_id omitted — should default to None
    )

    d = item.to_dict()
    assert d["datasource_id"] is None

    restored = RawIntelligenceItem.from_dict(d)
    assert restored.datasource_id is None


# ---------------------------------------------------------------------------
# Storage persistence
# ---------------------------------------------------------------------------


def test_save_raw_item_persists_datasource_id():
    """save_raw_item writes datasource_id when present on the item."""
    manager = DataManager(StorageConfig(database_path=":memory:"))
    repository = SQLiteIntelligenceRepository(manager)
    expires_at = datetime.utcnow() + timedelta(days=30)

    item = RawIntelligenceItem.create(
        source_type="telegram_group",
        source_id="-100999",
        external_id="42",
        raw_text="Test message with datasource",
        content_hash="hash-ds-1",
        expires_at=expires_at,
        datasource_id="ds-abc-001",
    )

    saved_id = repository.save_raw_item(item)
    assert saved_id == item.id

    stored = repository.get_raw_item_by_id(item.id)
    assert stored is not None
    assert stored.datasource_id == "ds-abc-001"
    assert stored.source_type == "telegram_group"
    assert stored.source_id == "-100999"


def test_save_raw_item_handles_none_datasource_id():
    """save_raw_item works when datasource_id is None (legacy compatibility)."""
    manager = DataManager(StorageConfig(database_path=":memory:"))
    repository = SQLiteIntelligenceRepository(manager)
    expires_at = datetime.utcnow() + timedelta(days=30)

    item = RawIntelligenceItem.create(
        source_type="v2ex",
        source_id="claude",
        external_id="99",
        raw_text="Legacy item without datasource",
        content_hash="hash-legacy-1",
        expires_at=expires_at,
        # datasource_id omitted
    )

    saved_id = repository.save_raw_item(item)
    assert saved_id == item.id

    stored = repository.get_raw_item_by_id(item.id)
    assert stored is not None
    assert stored.datasource_id is None
    assert stored.source_type == "v2ex"


def test_save_raw_item_dedup_preserves_datasource_id():
    """Dedup update keeps the datasource_id from the first insert."""
    manager = DataManager(StorageConfig(database_path=":memory:"))
    repository = SQLiteIntelligenceRepository(manager)
    expires_at = datetime.utcnow() + timedelta(days=30)

    first = RawIntelligenceItem.create(
        source_type="telegram_group",
        source_id="-100999",
        external_id="dup-1",
        raw_text="First message",
        content_hash="hash-first",
        expires_at=expires_at,
        datasource_id="ds-first-001",
    )
    duplicate = RawIntelligenceItem.create(
        source_type="telegram_group",
        source_id="-100999",
        external_id="dup-1",
        raw_text="Updated message",
        content_hash="hash-second",
        expires_at=expires_at,
        datasource_id="ds-second-002",
    )

    first_id = repository.save_raw_item(first)
    dup_id = repository.save_raw_item(duplicate)

    assert dup_id == first_id

    stored = repository.get_raw_item_by_id(first_id)
    assert stored is not None
    # ON CONFLICT DO UPDATE overwrites all columns from the second insert
    assert stored.datasource_id == "ds-second-002"
    assert stored.raw_text == "Updated message"


def test_from_dict_with_legacy_row_missing_datasource_id():
    """from_dict() handles rows where datasource_id key is absent (backward compat)."""
    legacy_row = {
        "id": "item-001",
        "source_type": "telegram_group",
        "source_id": "-100999",
        "external_id": "101",
        "source_url": None,
        "chat_id": None,
        "thread_id": None,
        "topic_id": None,
        "raw_text": "Old message",
        "content_hash": "hash-old",
        "published_at": None,
        "collected_at": datetime.utcnow().isoformat(),
        "expires_at": (datetime.utcnow() + timedelta(days=30)).isoformat(),
        "edit_status": None,
        "edit_timestamp": None,
        "created_at": datetime.utcnow().isoformat(),
        # datasource_id absent
    }

    item = RawIntelligenceItem.from_dict(legacy_row)
    assert item.datasource_id is None
    assert item.source_type == "telegram_group"
