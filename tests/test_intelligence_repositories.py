from datetime import datetime, timedelta
from pathlib import Path
import sqlite3
from typing import Any

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


def _raw_item(
    index: int,
    published_at: datetime,
    source_id: str = "chat-1",
    chat_id: str = "chat-1",
    thread_id: str = "thread-1",
    topic_id: str = "topic-1",
) -> RawIntelligenceItem:
    return RawIntelligenceItem.create(
        source_type="telegram",
        source_id=source_id,
        chat_id=chat_id,
        thread_id=thread_id,
        topic_id=topic_id,
        raw_text=f"raw evidence {index}",
        content_hash=f"raw-evidence-hash-{source_id}-{chat_id}-{thread_id}-{topic_id}-{index}",
        published_at=published_at,
        expires_at=published_at + timedelta(days=30),
    )


def _observation(raw_item: RawIntelligenceItem, index: int) -> ExtractionObservation:
    return ExtractionObservation.create(
        raw_item_id=raw_item.id,
        entry_type=EntryType.CHANNEL.value,
        confidence=0.8,
        model_name="model-a",
        prompt_version="p1",
        schema_version="s1",
        channel_name=f"Alpha {index}",
        channel_urls=["https://t.me/alpha"],
    )


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
        assert loaded.tracking_enabled is True

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
        loaded_checkpoint = repository.get_checkpoint("telegram", "chat-1")
        assert loaded_checkpoint is not None
        assert loaded_checkpoint.checkpoint_data == {"cursor": "100"}
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
            "intelligence_entry_evidence_links",
            "intelligence_aliases",
            "intelligence_related_candidates",
            "intelligence_crawl_checkpoints",
        }.issubset(tables)
        assert {"embedding", "embedding_model", "embedding_updated_at"}.issubset(columns)
        assert {"tracking_enabled", "discovery_presented_at"}.issubset(columns)
        assert "idx_intelligence_canonical_entries_type_key" in indexes
        assert not any("audit" in table for table in tables)
    finally:
        manager.close()


def test_entry_evidence_links_keep_multiple_raw_anchors(tmp_path: Path):
    manager, repository = _build_repository(tmp_path / "intelligence-evidence.db")
    try:
        base_time = datetime(2026, 1, 1, 12, 0, 0)
        raws = [_raw_item(index, base_time + timedelta(minutes=index)) for index in range(3)]
        observations = []
        for index, raw in enumerate(raws):
            repository.save_raw_item(raw)
            observation = _observation(raw, index)
            observations.append(observation)
            repository.save_observation(observation)

        entry = CanonicalIntelligenceEntry.create(
            entry_type=EntryType.CHANNEL.value,
            normalized_key="https://t.me/alpha",
            display_name="Alpha",
            confidence=0.9,
            latest_raw_item_id=raws[0].id,
        )
        repository.save_canonical_entry(entry, observation_id=observations[0].id)
        for raw, observation in zip(raws[1:], observations[1:]):
            entry.latest_raw_item_id = raw.id
            repository.upsert_canonical_entry(entry, observation_id=observation.id)

        anchors = repository.list_entry_evidence_anchors(entry.id, page=1, page_size=10)
        assert [anchor.raw_item_id for anchor in anchors] == [raws[2].id, raws[1].id, raws[0].id]
        assert [anchor.observation_id for anchor in anchors] == [
            observations[2].id,
            observations[1].id,
            observations[0].id,
        ]

        later_observation = _observation(raws[0], 99)
        repository.save_observation(later_observation)
        repository.save_entry_evidence_link(entry.id, later_observation.id, raws[0].id)

        anchors = repository.list_entry_evidence_anchors(entry.id, page=1, page_size=10)
        assert len(anchors) == 3
        assert anchors[-1].observation_id == observations[0].id
    finally:
        manager.close()


def test_entry_evidence_context_window_returns_deterministic_nearby_rows(tmp_path: Path):
    manager, repository = _build_repository(tmp_path / "intelligence-evidence-context.db")
    try:
        base_time = datetime(2026, 1, 1, 12, 0, 0)
        raws = [_raw_item(index, base_time + timedelta(minutes=index)) for index in range(25)]
        for raw in raws:
            repository.save_raw_item(raw)

        observation = _observation(raws[12], 12)
        repository.save_observation(observation)
        entry = CanonicalIntelligenceEntry.create(
            entry_type=EntryType.CHANNEL.value,
            normalized_key="https://t.me/alpha",
            display_name="Alpha",
            latest_raw_item_id=raws[12].id,
        )
        repository.save_canonical_entry(entry, observation_id=observation.id)

        window = repository.get_entry_evidence_context_window(entry.id, raws[12].id)
        assert window is not None
        assert window.anchor.raw_item_id == raws[12].id
        assert [item.id for item in window.items] == [raw.id for raw in raws[2:23]]
    finally:
        manager.close()


def test_entry_evidence_context_window_does_not_cross_conversation_scope(tmp_path: Path):
    manager, repository = _build_repository(tmp_path / "intelligence-evidence-scope.db")
    try:
        base_time = datetime(2026, 1, 1, 12, 0, 0)
        scoped_raws = [_raw_item(index, base_time + timedelta(minutes=index)) for index in range(5)]
        foreign_raws = [
            _raw_item(
                index,
                base_time + timedelta(minutes=index, seconds=30),
                source_id="chat-1",
                chat_id="chat-1",
                thread_id="thread-2",
                topic_id="topic-1",
            )
            for index in range(5)
        ]
        for raw in [*scoped_raws, *foreign_raws]:
            repository.save_raw_item(raw)

        observation = _observation(scoped_raws[2], 2)
        repository.save_observation(observation)
        entry = CanonicalIntelligenceEntry.create(
            entry_type=EntryType.CHANNEL.value,
            normalized_key="https://t.me/alpha",
            display_name="Alpha",
            latest_raw_item_id=scoped_raws[2].id,
        )
        repository.save_canonical_entry(entry, observation_id=observation.id)

        window = repository.get_entry_evidence_context_window(entry.id, scoped_raws[2].id)
        assert window is not None
        assert [item.id for item in window.items] == [raw.id for raw in scoped_raws]
        assert not {item.id for item in window.items}.intersection({raw.id for raw in foreign_raws})
    finally:
        manager.close()


def test_entry_evidence_anchor_pagination_does_not_duplicate_rows(tmp_path: Path):
    manager, repository = _build_repository(tmp_path / "intelligence-evidence-pages.db")
    try:
        base_time = datetime(2026, 1, 1, 12, 0, 0)
        raws = [_raw_item(index, base_time + timedelta(minutes=index)) for index in range(5)]
        observations = []
        entry = CanonicalIntelligenceEntry.create(
            entry_type=EntryType.CHANNEL.value,
            normalized_key="https://t.me/alpha",
            display_name="Alpha",
        )
        for index, raw in enumerate(raws):
            repository.save_raw_item(raw)
            observation = _observation(raw, index)
            observations.append(observation)
            repository.save_observation(observation)
            entry.latest_raw_item_id = raw.id
            repository.upsert_canonical_entry(entry, observation_id=observation.id)

        page_one = repository.list_entry_evidence_anchors(entry.id, page=1, page_size=2)
        page_two = repository.list_entry_evidence_anchors(entry.id, page=2, page_size=2)
        page_three = repository.list_entry_evidence_anchors(entry.id, page=3, page_size=2)

        paged_ids = [anchor.raw_item_id for anchor in [*page_one, *page_two, *page_three]]
        assert paged_ids == [raw.id for raw in reversed(raws)]
        assert len(paged_ids) == len(set(paged_ids))
    finally:
        manager.close()


def test_raw_text_ttl_purge_preserves_evidence_associations(tmp_path: Path):
    manager, repository = _build_repository(tmp_path / "intelligence-evidence-ttl.db")
    try:
        raw = RawIntelligenceItem.create(
            source_type="telegram",
            source_id="chat-1",
            raw_text="expired but still associated",
            content_hash="hash-expired-associated",
            published_at=datetime.utcnow() - timedelta(days=31),
            expires_at=datetime.utcnow() - timedelta(days=1),
        )
        repository.save_raw_item(raw)
        observation = _observation(raw, 1)
        repository.save_observation(observation)
        entry = CanonicalIntelligenceEntry.create(
            entry_type=EntryType.CHANNEL.value,
            normalized_key="https://t.me/alpha",
            display_name="Alpha",
            latest_raw_item_id=raw.id,
        )
        repository.save_canonical_entry(entry, observation_id=observation.id)

        assert repository.purge_raw_text_older_than(datetime.utcnow()) == 1
        loaded_raw = repository.get_raw_item_by_id(raw.id)
        anchors = repository.list_entry_evidence_anchors(entry.id, page=1, page_size=10)
        window = repository.get_entry_evidence_context_window(entry.id, raw.id)

        assert loaded_raw is not None
        assert loaded_raw.raw_text is None
        assert [anchor.raw_item_id for anchor in anchors] == [raw.id]
        assert window is not None
        assert window.anchor.raw_item_id == raw.id
        assert [item.id for item in window.items] == [raw.id]
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
            def __init__(self):
                self.inner: Any = None

            def __enter__(self):
                self.inner = original_get_connection()
                connection = self.inner.__enter__()
                return DictRowConnection(connection)

            def __exit__(self, exc_type, exc, tb):
                return self.inner.__exit__(exc_type, exc, tb)

        setattr(manager, "_get_connection", lambda: DictRowContext())

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
        assert ignored.tracking_enabled is False
        assert ignored.discovery_presented_at is not None

        # List excludes ignored
        visible = repository.list_canonical_entries(entry_type=EntryType.CHANNEL.value)
        assert all(e.id != entry.id for e in visible)

        # Count excludes ignored
        assert repository.count_canonical_entries(entry_type=EntryType.CHANNEL.value) == 0

        # Exact lookups still return ignored
        by_id = repository.get_canonical_entry_by_id(entry.id)
        assert by_id is not None
        assert by_id.is_ignored is True
        assert by_id.tracking_enabled is False
        assert by_id.discovery_presented_at is not None

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
        assert first.tracking_enabled is False
        assert first.discovery_presented_at is not None

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


def test_tracking_scope_defaults_hide_untracked_slang_but_keep_channels(tmp_path: Path):
    manager, repository = _build_repository(tmp_path / "intelligence-tracking-list.db")
    try:
        channel = CanonicalIntelligenceEntry.create(
            entry_type=EntryType.CHANNEL.value,
            normalized_key="https://t.me/tracked-channel",
            display_name="Tracked Channel",
            tracking_enabled=False,
        )
        untracked_slang = CanonicalIntelligenceEntry.create(
            entry_type=EntryType.SLANG.value,
            normalized_key="ngmi",
            display_name="NGMI",
        )
        tracked_slang = CanonicalIntelligenceEntry.create(
            entry_type=EntryType.SLANG.value,
            normalized_key="gm",
            display_name="GM",
            tracking_enabled=True,
        )
        for entry in (channel, untracked_slang, tracked_slang):
            repository.save_canonical_entry(entry)
            assert repository.update_embedding(entry.id, [1.0, 0.0, 0.0], "test-embedding") is True

        default_ids = {entry.id for entry in repository.list_canonical_entries()}
        assert default_ids == {channel.id, tracked_slang.id}
        assert repository.count_canonical_entries() == 2
        assert {entry.id for entry, _ in repository.semantic_search([1.0, 0.0, 0.0], limit=10)} == {
            channel.id,
            tracked_slang.id,
        }
        assert repository.count_semantic_search_candidates([1.0, 0.0, 0.0]) == 2

        all_ids = {entry.id for entry in repository.list_canonical_entries(tracking_scope="all")}
        assert all_ids == {channel.id, untracked_slang.id, tracked_slang.id}
        assert repository.count_canonical_entries(tracking_scope="all") == 3
        assert {
            entry.id
            for entry, _ in repository.semantic_search(
                [1.0, 0.0, 0.0], limit=10, tracking_scope="all"
            )
        } == {channel.id, untracked_slang.id, tracked_slang.id}
        assert (
            repository.count_semantic_search_candidates([1.0, 0.0, 0.0], tracking_scope="all") == 3
        )
    finally:
        manager.close()


def test_discovery_scope_returns_unseen_untracked_slang_once(tmp_path: Path):
    manager, repository = _build_repository(tmp_path / "intelligence-discovery.db")
    try:
        channel = CanonicalIntelligenceEntry.create(
            entry_type=EntryType.CHANNEL.value,
            normalized_key="https://t.me/discovery-channel",
            display_name="Discovery Channel",
        )
        unseen_slang = CanonicalIntelligenceEntry.create(
            entry_type=EntryType.SLANG.value,
            normalized_key="ser",
            display_name="Ser",
        )
        followed_slang = CanonicalIntelligenceEntry.create(
            entry_type=EntryType.SLANG.value,
            normalized_key="anon",
            display_name="Anon",
            tracking_enabled=True,
        )
        ignored_slang = CanonicalIntelligenceEntry.create(
            entry_type=EntryType.SLANG.value,
            normalized_key="rekt",
            display_name="Rekt",
        )
        presented_slang = CanonicalIntelligenceEntry.create(
            entry_type=EntryType.SLANG.value,
            normalized_key="wagmi",
            display_name="WAGMI",
            discovery_presented_at=datetime.utcnow(),
        )
        for entry in (channel, unseen_slang, followed_slang, ignored_slang, presented_slang):
            repository.save_canonical_entry(entry)

        assert repository.ignore_canonical_entry(ignored_slang.id) is not None

        discovery = repository.list_canonical_entries(tracking_scope="discovery")
        assert [entry.id for entry in discovery] == [unseen_slang.id]
        assert repository.count_canonical_entries(tracking_scope="discovery") == 1
        loaded_unseen_slang = repository.get_canonical_entry_by_id(unseen_slang.id)
        assert loaded_unseen_slang is not None
        assert loaded_unseen_slang.discovery_presented_at is None

        assert (
            repository.mark_discovery_presented([unseen_slang.id, channel.id, followed_slang.id])
            == 1
        )
        marked = repository.get_canonical_entry_by_id(unseen_slang.id)
        assert marked is not None
        assert marked.discovery_presented_at is not None
        assert repository.list_canonical_entries(tracking_scope="discovery") == []
        assert repository.mark_discovery_presented([unseen_slang.id]) == 0
    finally:
        manager.close()


def test_follow_unfollow_toggles_tracking_without_altering_ignore_state(tmp_path: Path):
    manager, repository = _build_repository(tmp_path / "intelligence-follow.db")
    try:
        entry = CanonicalIntelligenceEntry.create(
            entry_type=EntryType.SLANG.value,
            normalized_key="based",
            display_name="Based",
        )
        ignored_entry = CanonicalIntelligenceEntry.create(
            entry_type=EntryType.SLANG.value,
            normalized_key="ignored-based",
            display_name="Ignored Based",
        )
        repository.save_canonical_entry(entry)
        repository.save_canonical_entry(ignored_entry)
        ignored = repository.ignore_canonical_entry(ignored_entry.id, ignored_by="tester")
        assert ignored is not None

        followed = repository.follow_canonical_entry(entry.id)
        assert followed is not None
        assert followed.tracking_enabled is True
        assert followed.is_ignored is False
        assert followed.discovery_presented_at is None

        unfollowed = repository.unfollow_canonical_entry(entry.id)
        assert unfollowed is not None
        assert unfollowed.tracking_enabled is False
        assert unfollowed.is_ignored is False
        assert unfollowed.discovery_presented_at is None

        followed_ignored = repository.follow_canonical_entry(ignored_entry.id)
        assert followed_ignored is not None
        assert followed_ignored.is_ignored is True
        assert followed_ignored.ignored_by == "tester"
        assert followed_ignored.discovery_presented_at is not None

        unignored = repository.unignore_canonical_entry(ignored_entry.id)
        assert unignored is not None
        assert unignored.is_ignored is False
        assert unignored.tracking_enabled is True

        unfollowed_ignored = repository.unfollow_canonical_entry(ignored_entry.id)
        assert unfollowed_ignored is not None
        assert unfollowed_ignored.is_ignored is False
        assert unfollowed_ignored.tracking_enabled is False
        assert unfollowed_ignored.discovery_presented_at is not None
    finally:
        manager.close()


def test_existing_sqlite_intelligence_schema_backfills_tracking_state(tmp_path: Path):
    db_path = tmp_path / "legacy-intelligence.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute("""
            CREATE TABLE intelligence_canonical_entries (
                id TEXT PRIMARY KEY,
                entry_type TEXT NOT NULL,
                normalized_key TEXT NOT NULL,
                display_name TEXT NOT NULL,
                explanation TEXT,
                usage_summary TEXT,
                primary_label TEXT,
                secondary_tags TEXT NOT NULL DEFAULT '[]',
                confidence FLOAT NOT NULL DEFAULT 0.0,
                first_seen_at DATETIME,
                last_seen_at DATETIME,
                evidence_count INTEGER NOT NULL DEFAULT 1,
                latest_raw_item_id TEXT,
                prompt_version TEXT,
                model_name TEXT,
                schema_version TEXT,
                is_ignored BOOLEAN NOT NULL DEFAULT FALSE,
                ignored_at DATETIME,
                ignored_by TEXT,
                embedding TEXT,
                embedding_model TEXT,
                embedding_updated_at DATETIME,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.executemany(
            """
            INSERT INTO intelligence_canonical_entries
            (id, entry_type, normalized_key, display_name, is_ignored, ignored_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                ("channel-visible", "channel", "https://t.me/visible", "Visible", False, None),
                ("slang-visible", "slang", "gm", "GM", False, None),
                (
                    "channel-ignored",
                    "channel",
                    "https://t.me/ignored",
                    "Ignored",
                    True,
                    datetime.utcnow().isoformat(),
                ),
            ],
        )

    manager, repository = _build_repository(db_path)
    try:
        channel = repository.get_canonical_entry_by_id("channel-visible")
        slang = repository.get_canonical_entry_by_id("slang-visible")
        ignored = repository.get_canonical_entry_by_id("channel-ignored")

        assert channel is not None
        assert channel.is_ignored is False
        assert channel.tracking_enabled is True
        assert channel.discovery_presented_at is None

        assert slang is not None
        assert slang.is_ignored is False
        assert slang.tracking_enabled is False
        assert slang.discovery_presented_at is None

        assert ignored is not None
        assert ignored.is_ignored is True
        assert ignored.tracking_enabled is False
        assert ignored.discovery_presented_at is not None

        with manager._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE intelligence_canonical_entries SET tracking_enabled = ? WHERE id = ?",
                (True, "slang-visible"),
            )
            cursor.execute(
                "UPDATE intelligence_canonical_entries SET tracking_enabled = ? WHERE id = ?",
                (False, "channel-visible"),
            )
            conn.commit()
    finally:
        manager.close()

    manager, repository = _build_repository(db_path)
    try:
        followed_slang = repository.get_canonical_entry_by_id("slang-visible")
        unfollowed_channel = repository.get_canonical_entry_by_id("channel-visible")

        assert followed_slang is not None
        assert followed_slang.tracking_enabled is True

        assert unfollowed_channel is not None
        assert unfollowed_channel.tracking_enabled is False
    finally:
        manager.close()
