from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from crypto_news_analyzer.domain.models import (
    IntelligenceTopic,
    RawIntelligenceItem,
    SafeDataSourceSummary,
)
from crypto_news_analyzer.models import StorageConfig
from crypto_news_analyzer.storage.data_manager import DataManager
from crypto_news_analyzer.storage.repositories import SQLiteIntelligenceRepository


def _build_repo(db_path: Path) -> tuple[DataManager, SQLiteIntelligenceRepository]:
    data_manager = DataManager(StorageConfig(database_path=str(db_path)))
    repository = SQLiteIntelligenceRepository(data_manager)
    return data_manager, repository


def _seed_topic(repo: SQLiteIntelligenceRepository, name: str = "Test Topic") -> IntelligenceTopic:
    topic = IntelligenceTopic.create(name=name)
    repo.save_topic(topic)
    return topic


def _seed_datasource(
    dm: DataManager,
    datasource_id: str,
    purpose: str = "intelligence",
    source_type: str = "telegram_group",
    name: str = "",
    tags: list = None,
) -> None:
    name = name or f"ds-{datasource_id[:8]}"
    dm.upsert_datasource(
        datasource_id=datasource_id,
        purpose=purpose,
        source_type=source_type,
        name=name,
        tags=tags or [],
    )


def _seed_raw_item(
    dm: DataManager,
    item_id: str,
    source_type: str = "telegram_group",
    datasource_id: str = "",
    collected_at: datetime = None,
    raw_text: str = "test message",
) -> str:
    item = RawIntelligenceItem.create(
        source_type=source_type,
        raw_text=raw_text,
        content_hash=f"hash-{item_id}",
        expires_at=datetime.utcnow() + timedelta(days=7),
        datasource_id=datasource_id or None,
    )
    # Override id for deterministic testing
    item.id = item_id
    if collected_at:
        item.collected_at = collected_at
    dm.upsert_raw_intelligence_item(item.to_dict())
    return item_id


# ── get_topic_datasource_ids ────────────────────────────────────────────


def test_get_topic_datasource_ids_returns_empty_when_no_associations(tmp_path: Path):
    dm, repo = _build_repo(tmp_path / "ids_empty.db")
    try:
        topic = _seed_topic(repo)
        result = repo.get_topic_datasource_ids(topic.id)
        assert result == []
    finally:
        dm.close()


def test_get_topic_datasource_ids_returns_ids_in_deterministic_order(tmp_path: Path):
    dm, repo = _build_repo(tmp_path / "ids_order.db")
    try:
        topic = _seed_topic(repo)
        _seed_datasource(dm, "ds-c", purpose="intelligence")
        _seed_datasource(dm, "ds-a", purpose="intelligence")
        _seed_datasource(dm, "ds-b", purpose="intelligence")
        repo.set_topic_datasources(topic.id, ["ds-c", "ds-a", "ds-b"])
        result = repo.get_topic_datasource_ids(topic.id)
        assert result == ["ds-a", "ds-b", "ds-c"]
    finally:
        dm.close()


def test_get_topic_datasource_ids_raises_value_error_on_unknown_topic(tmp_path: Path):
    dm, repo = _build_repo(tmp_path / "ids_unknown.db")
    try:
        with pytest.raises(ValueError, match="unknown topic"):
            repo.get_topic_datasource_ids("nonexistent-topic-id")
    finally:
        dm.close()


# ── set_topic_datasources ───────────────────────────────────────────────


def test_set_topic_datasources_adds_and_replaces(tmp_path: Path):
    dm, repo = _build_repo(tmp_path / "set_add.db")
    try:
        topic = _seed_topic(repo)
        _seed_datasource(dm, "ds-1", purpose="intelligence")
        _seed_datasource(dm, "ds-2", purpose="intelligence")
        _seed_datasource(dm, "ds-3", purpose="intelligence")
        # First set
        repo.set_topic_datasources(topic.id, ["ds-1", "ds-2"])
        assert sorted(repo.get_topic_datasource_ids(topic.id)) == ["ds-1", "ds-2"]
        # Replace
        repo.set_topic_datasources(topic.id, ["ds-3"])
        assert repo.get_topic_datasource_ids(topic.id) == ["ds-3"]
    finally:
        dm.close()


def test_set_topic_datasources_empty_list_clears_all(tmp_path: Path):
    dm, repo = _build_repo(tmp_path / "set_clear.db")
    try:
        topic = _seed_topic(repo)
        _seed_datasource(dm, "ds-1", purpose="intelligence")
        repo.set_topic_datasources(topic.id, ["ds-1"])
        assert len(repo.get_topic_datasource_ids(topic.id)) == 1
        repo.set_topic_datasources(topic.id, [])
        assert repo.get_topic_datasource_ids(topic.id) == []
    finally:
        dm.close()


def test_set_topic_datasources_raises_value_error_on_unknown_topic(tmp_path: Path):
    dm, repo = _build_repo(tmp_path / "set_topic_unknown.db")
    try:
        _seed_datasource(dm, "ds-1", purpose="intelligence")
        with pytest.raises(ValueError, match="unknown topic"):
            repo.set_topic_datasources("nonexistent", ["ds-1"])
    finally:
        dm.close()


def test_set_topic_datasources_validates_datasource_ids_exist(tmp_path: Path):
    dm, repo = _build_repo(tmp_path / "set_ds_unknown.db")
    try:
        topic = _seed_topic(repo)
        _seed_datasource(dm, "ds-valid", purpose="intelligence")
        with pytest.raises(ValueError, match="unknown datasource"):
            repo.set_topic_datasources(topic.id, ["ds-valid", "ds-nonexistent"])
    finally:
        dm.close()


def test_set_topic_datasources_validates_datasource_purpose_is_intelligence(tmp_path: Path):
    dm, repo = _build_repo(tmp_path / "set_ds_news.db")
    try:
        topic = _seed_topic(repo)
        _seed_datasource(dm, "ds-intel", purpose="intelligence")
        _seed_datasource(dm, "ds-news", purpose="news")
        with pytest.raises(ValueError, match="not intelligence-purpose"):
            repo.set_topic_datasources(topic.id, ["ds-intel", "ds-news"])
    finally:
        dm.close()


def test_set_topic_datasources_atomic_no_partial_update_on_invalid_ids(tmp_path: Path):
    dm, repo = _build_repo(tmp_path / "set_atomic.db")
    try:
        topic = _seed_topic(repo)
        _seed_datasource(dm, "ds-1", purpose="intelligence")
        _seed_datasource(dm, "ds-2", purpose="intelligence")
        _seed_datasource(dm, "ds-3", purpose="news")
        # Setup initial state
        repo.set_topic_datasources(topic.id, ["ds-1", "ds-2"])
        assert sorted(repo.get_topic_datasource_ids(topic.id)) == ["ds-1", "ds-2"]
        # Try to set with invalid ID — must fail with NO changes
        with pytest.raises(ValueError, match="not intelligence-purpose"):
            repo.set_topic_datasources(topic.id, ["ds-1", "ds-3"])
        # Verify NO changes were made
        assert sorted(repo.get_topic_datasource_ids(topic.id)) == ["ds-1", "ds-2"]
    finally:
        dm.close()


# ── add_topic_datasources ───────────────────────────────────────────────


def test_add_topic_datasources_adds_new_and_skips_existing(tmp_path: Path):
    dm, repo = _build_repo(tmp_path / "add_idempotent.db")
    try:
        topic = _seed_topic(repo)
        _seed_datasource(dm, "ds-1", purpose="intelligence")
        _seed_datasource(dm, "ds-2", purpose="intelligence")
        repo.add_topic_datasources(topic.id, ["ds-1"])
        assert repo.get_topic_datasource_ids(topic.id) == ["ds-1"]
        # Adding same + new — existing skipped, new added
        repo.add_topic_datasources(topic.id, ["ds-1", "ds-2"])
        assert sorted(repo.get_topic_datasource_ids(topic.id)) == ["ds-1", "ds-2"]
    finally:
        dm.close()


def test_add_topic_datasources_deduplicates_input(tmp_path: Path):
    dm, repo = _build_repo(tmp_path / "add_dedup.db")
    try:
        topic = _seed_topic(repo)
        _seed_datasource(dm, "ds-1", purpose="intelligence")
        repo.add_topic_datasources(topic.id, ["ds-1", "ds-1", "ds-1"])
        assert repo.get_topic_datasource_ids(topic.id) == ["ds-1"]
    finally:
        dm.close()


def test_add_topic_datasources_validates_datasource_ids(tmp_path: Path):
    dm, repo = _build_repo(tmp_path / "add_validate.db")
    try:
        topic = _seed_topic(repo)
        _seed_datasource(dm, "ds-1", purpose="news")
        with pytest.raises(ValueError, match="not intelligence-purpose"):
            repo.add_topic_datasources(topic.id, ["ds-1"])
    finally:
        dm.close()


def test_add_topic_datasources_raises_value_error_on_unknown_topic(tmp_path: Path):
    dm, repo = _build_repo(tmp_path / "add_topic_unknown.db")
    try:
        _seed_datasource(dm, "ds-1", purpose="intelligence")
        with pytest.raises(ValueError, match="unknown topic"):
            repo.add_topic_datasources("nonexistent", ["ds-1"])
    finally:
        dm.close()


def test_add_topic_datasources_empty_list_noop(tmp_path: Path):
    dm, repo = _build_repo(tmp_path / "add_empty.db")
    try:
        topic = _seed_topic(repo)
        repo.add_topic_datasources(topic.id, [])
        assert repo.get_topic_datasource_ids(topic.id) == []
    finally:
        dm.close()


# ── remove_topic_datasources ────────────────────────────────────────────


def test_remove_topic_datasources_removes_associated(tmp_path: Path):
    dm, repo = _build_repo(tmp_path / "remove.db")
    try:
        topic = _seed_topic(repo)
        _seed_datasource(dm, "ds-1", purpose="intelligence")
        _seed_datasource(dm, "ds-2", purpose="intelligence")
        repo.set_topic_datasources(topic.id, ["ds-1", "ds-2"])
        repo.remove_topic_datasources(topic.id, ["ds-1"])
        assert repo.get_topic_datasource_ids(topic.id) == ["ds-2"]
    finally:
        dm.close()


def test_remove_topic_datasources_unknown_datasource_silently_skipped(tmp_path: Path):
    dm, repo = _build_repo(tmp_path / "remove_unknown_ds.db")
    try:
        topic = _seed_topic(repo)
        _seed_datasource(dm, "ds-1", purpose="intelligence")
        repo.set_topic_datasources(topic.id, ["ds-1"])
        # Unknown ID should not raise, should not affect existing associations
        repo.remove_topic_datasources(topic.id, ["ds-nonexistent"])
        assert repo.get_topic_datasource_ids(topic.id) == ["ds-1"]
    finally:
        dm.close()


def test_remove_topic_datasources_empty_list_noop(tmp_path: Path):
    dm, repo = _build_repo(tmp_path / "remove_empty.db")
    try:
        topic = _seed_topic(repo)
        _seed_datasource(dm, "ds-1", purpose="intelligence")
        repo.set_topic_datasources(topic.id, ["ds-1"])
        repo.remove_topic_datasources(topic.id, [])
        assert repo.get_topic_datasource_ids(topic.id) == ["ds-1"]
    finally:
        dm.close()


def test_remove_topic_datasources_deduplicates_input(tmp_path: Path):
    dm, repo = _build_repo(tmp_path / "remove_dedup.db")
    try:
        topic = _seed_topic(repo)
        _seed_datasource(dm, "ds-1", purpose="intelligence")
        repo.set_topic_datasources(topic.id, ["ds-1"])
        repo.remove_topic_datasources(topic.id, ["ds-1", "ds-1", "ds-1"])
        assert repo.get_topic_datasource_ids(topic.id) == []
    finally:
        dm.close()


def test_remove_topic_datasources_raises_value_error_on_unknown_topic(tmp_path: Path):
    dm, repo = _build_repo(tmp_path / "remove_topic_unknown.db")
    try:
        with pytest.raises(ValueError, match="unknown topic"):
            repo.remove_topic_datasources("nonexistent", ["ds-1"])
    finally:
        dm.close()


# ── get_topic_datasources ───────────────────────────────────────────────


def test_get_topic_datasources_returns_safe_summaries_with_tags(tmp_path: Path):
    dm, repo = _build_repo(tmp_path / "get_summaries.db")
    try:
        topic = _seed_topic(repo)
        _seed_datasource(dm, "ds-1", purpose="intelligence", source_type="telegram_group",
                         name="Alpha Chat", tags=["crypto", "alpha"])
        _seed_datasource(dm, "ds-2", purpose="intelligence", source_type="v2ex",
                         name="V2EX Hot", tags=["tech"])
        repo.set_topic_datasources(topic.id, ["ds-1", "ds-2"])
        summaries = repo.get_topic_datasources(topic.id)
        assert len(summaries) == 2
        assert all(isinstance(s, SafeDataSourceSummary) for s in summaries)
        by_id = {s.id: s for s in summaries}
        assert by_id["ds-1"].name == "Alpha Chat"
        assert by_id["ds-1"].source_type == "telegram_group"
        assert by_id["ds-1"].tags == ["alpha", "crypto"]
        assert by_id["ds-2"].name == "V2EX Hot"
        assert by_id["ds-2"].source_type == "v2ex"
        assert by_id["ds-2"].tags == ["tech"]
    finally:
        dm.close()


def test_get_topic_datasources_excludes_config_payload(tmp_path: Path):
    dm, repo = _build_repo(tmp_path / "get_no_config.db")
    try:
        topic = _seed_topic(repo)
        dm.upsert_datasource(
            datasource_id="ds-secret",
            purpose="intelligence",
            source_type="telegram_group",
            name="Secret Chat",
            config_payload={"api_key": "secret123", "chat_id": "-100"},
        )
        repo.set_topic_datasources(topic.id, ["ds-secret"])
        summaries = repo.get_topic_datasources(topic.id)
        assert len(summaries) == 1
        summary = summaries[0]
        assert summary.name == "Secret Chat"
        assert not hasattr(summary, "config_payload")
    finally:
        dm.close()


def test_get_topic_datasources_empty_when_no_associations(tmp_path: Path):
    dm, repo = _build_repo(tmp_path / "get_empty.db")
    try:
        topic = _seed_topic(repo)
        assert repo.get_topic_datasources(topic.id) == []
    finally:
        dm.close()


def test_get_topic_datasources_raises_value_error_on_unknown_topic(tmp_path: Path):
    dm, repo = _build_repo(tmp_path / "get_unknown_topic.db")
    try:
        with pytest.raises(ValueError, match="unknown topic"):
            repo.get_topic_datasources("nonexistent")
    finally:
        dm.close()


# ── get_raw_items_since with datasource_ids filtering ───────────────────


def test_get_raw_items_since_datasource_ids_none_preserves_backward_compat(tmp_path: Path):
    dm, repo = _build_repo(tmp_path / "raw_none.db")
    try:
        topic = _seed_topic(repo)
        now = datetime.utcnow()
        _seed_raw_item(dm, "item-1", datasource_id="ds-a", collected_at=now - timedelta(hours=2))
        _seed_raw_item(dm, "item-2", datasource_id="ds-b", collected_at=now - timedelta(hours=1))
        items = repo.get_raw_items_since(topic.id, now - timedelta(hours=3), 100)
        assert len(items) == 2
    finally:
        dm.close()


def test_get_raw_items_since_filters_by_datasource_ids_in_sql(tmp_path: Path):
    dm, repo = _build_repo(tmp_path / "raw_filter.db")
    try:
        topic = _seed_topic(repo)
        now = datetime.utcnow()
        _seed_raw_item(dm, "item-a1", datasource_id="ds-a", collected_at=now - timedelta(hours=2))
        _seed_raw_item(dm, "item-a2", datasource_id="ds-a", collected_at=now - timedelta(hours=1))
        _seed_raw_item(dm, "item-b1", datasource_id="ds-b", collected_at=now - timedelta(hours=3))
        items = repo.get_raw_items_since(
            topic.id, now - timedelta(hours=5), 100, datasource_ids=["ds-a"]
        )
        assert len(items) == 2
        assert all(item.datasource_id == "ds-a" for item in items)
    finally:
        dm.close()


def test_get_raw_items_since_datasource_ids_filter_before_limit(tmp_path: Path):
    """Verify datasource filtering happens in SQL WHERE before ORDER BY + LIMIT."""
    dm, repo = _build_repo(tmp_path / "raw_before_limit.db")
    try:
        topic = _seed_topic(repo)
        now = datetime.utcnow()
        # Seed 3 items from ds-a and 3 from ds-b — interleaved by time
        for i in range(3):
            _seed_raw_item(
                dm, f"a-{i}", datasource_id="ds-a",
                collected_at=now - timedelta(hours=6 - i),
            )
            _seed_raw_item(
                dm, f"b-{i}", datasource_id="ds-b",
                collected_at=now - timedelta(hours=5 - i),
            )
        # If filtering happens AFTER limit, with limit=2 we might get mixed results.
        # If filtering happens BEFORE limit in SQL, we get exactly 2 ds-a items.
        items = repo.get_raw_items_since(
            topic.id, now - timedelta(hours=10), 2, datasource_ids=["ds-a"]
        )
        assert len(items) == 2
        assert all(item.datasource_id == "ds-a" for item in items)
    finally:
        dm.close()


def test_get_raw_items_since_datasource_ids_empty_list_returns_nothing(tmp_path: Path):
    dm, repo = _build_repo(tmp_path / "raw_empty_ids.db")
    try:
        topic = _seed_topic(repo)
        now = datetime.utcnow()
        _seed_raw_item(dm, "item-1", datasource_id="ds-a", collected_at=now - timedelta(hours=1))
        items = repo.get_raw_items_since(
            topic.id, now - timedelta(hours=5), 100, datasource_ids=[]
        )
        assert items == []
    finally:
        dm.close()


def test_get_raw_items_since_no_cursor_time_with_datasource_filter(tmp_path: Path):
    dm, repo = _build_repo(tmp_path / "raw_no_cursor.db")
    try:
        topic = _seed_topic(repo)
        now = datetime.utcnow()
        _seed_raw_item(dm, "item-a", datasource_id="ds-a", collected_at=now - timedelta(hours=1))
        _seed_raw_item(dm, "item-b", datasource_id="ds-b", collected_at=now - timedelta(hours=2))
        items = repo.get_raw_items_since(
            topic.id, None, 100, datasource_ids=["ds-a"]
        )
        assert len(items) == 1
        assert items[0].id == "item-a"
    finally:
        dm.close()


def test_get_raw_items_since_multiple_datasource_ids(tmp_path: Path):
    dm, repo = _build_repo(tmp_path / "raw_multi_ds.db")
    try:
        topic = _seed_topic(repo)
        now = datetime.utcnow()
        _seed_raw_item(dm, "item-a", datasource_id="ds-a", collected_at=now - timedelta(hours=2))
        _seed_raw_item(dm, "item-b", datasource_id="ds-b", collected_at=now - timedelta(hours=1))
        _seed_raw_item(dm, "item-c", datasource_id="ds-c", collected_at=now - timedelta(hours=3))
        items = repo.get_raw_items_since(
            topic.id, now - timedelta(hours=5), 100, datasource_ids=["ds-a", "ds-b"]
        )
        assert len(items) == 2
        returned_ids = {item.id for item in items}
        assert returned_ids == {"item-a", "item-b"}
    finally:
        dm.close()
