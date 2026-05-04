from importlib import import_module
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, List, Optional, cast

import pytest

from crypto_news_analyzer.domain.models import (
    EntryType,
    ExtractionObservation,
    PrimaryLabel,
    RawIntelligenceItem,
)
from crypto_news_analyzer.models import StorageConfig
from crypto_news_analyzer.storage.data_manager import DataManager
from crypto_news_analyzer.storage.repositories import SQLiteIntelligenceRepository

IntelligenceMergeEngine = import_module(
    "crypto_news_analyzer.intelligence.merge"
).IntelligenceMergeEngine


def _build_repository(db_path: Path):
    manager = DataManager(StorageConfig(database_path=str(db_path)))
    return manager, SQLiteIntelligenceRepository(manager)


def _raw(repository: SQLiteIntelligenceRepository, text: str = "raw") -> RawIntelligenceItem:
    raw = RawIntelligenceItem.create(
        source_type="telegram_group",
        source_id="chat-1",
        raw_text=text,
        content_hash=f"hash-{text}-{datetime.utcnow().timestamp()}",
        expires_at=datetime.utcnow() + timedelta(days=30),
    )
    repository.save_raw_item(raw)
    return raw


def _channel_observation(
    repository: SQLiteIntelligenceRepository,
    raw: RawIntelligenceItem,
    *,
    name: str = "Alpha",
    urls: Optional[List[str]] = None,
    handles: Optional[List[str]] = None,
    domains: Optional[List[str]] = None,
    aliases: Optional[List[str]] = None,
    confidence: float = 0.8,
) -> ExtractionObservation:
    observation = ExtractionObservation.create(
        raw_item_id=raw.id,
        entry_type=EntryType.CHANNEL.value,
        confidence=confidence,
        model_name="test-model",
        prompt_version="p1",
        schema_version="s1",
        channel_name=name,
        channel_urls=urls or [],
        channel_handles=handles or [],
        channel_domains=domains or [],
        aliases_or_variants=aliases or [],
        primary_label=PrimaryLabel.CRYPTO.value,
    )
    repository.save_observation(observation)
    return observation


def _slang_observation(
    repository: SQLiteIntelligenceRepository,
    raw: RawIntelligenceItem,
    *,
    term: str,
    normalized_term: str,
    confidence: float = 0.8,
) -> ExtractionObservation:
    observation = ExtractionObservation.create(
        raw_item_id=raw.id,
        entry_type=EntryType.SLANG.value,
        confidence=confidence,
        model_name="test-model",
        prompt_version="p1",
        schema_version="s1",
        term=term,
        normalized_term=normalized_term,
        aliases_or_variants=[term],
        primary_label=PrimaryLabel.OTHER.value,
    )
    repository.save_observation(observation)
    return observation


def test_same_telegram_username_merges_into_one_canonical_entry(tmp_path: Path):
    manager, repository = _build_repository(tmp_path / "merge-handle.db")
    try:
        observations = [
            _channel_observation(repository, _raw(repository, "a"), handles=["@alpha"]),
            _channel_observation(repository, _raw(repository, "b"), handles=["@alpha"]),
        ]

        entries = IntelligenceMergeEngine(repository).canonicalize_observations(observations)
        canonical = repository.list_canonical_entries(entry_type=EntryType.CHANNEL.value)

        assert len(entries) == 2
        assert len(canonical) == 1
        assert canonical[0].normalized_key == "alpha"
        assert canonical[0].evidence_count == 2
        assert repository.get_uncanonicalized_observations(10) == []
    finally:
        manager.close()


def test_same_url_normalizes_and_merges(tmp_path: Path):
    manager, repository = _build_repository(tmp_path / "merge-url.db")
    try:
        observations = [
            _channel_observation(repository, _raw(repository, "a"), urls=["https://t.me/alpha"]),
            _channel_observation(repository, _raw(repository, "b"), urls=["HTTPS://T.ME/Alpha/"]),
        ]

        IntelligenceMergeEngine(repository).canonicalize_observations(observations)
        canonical = repository.list_canonical_entries(entry_type=EntryType.CHANNEL.value)

        assert len(canonical) == 1
        assert canonical[0].normalized_key == "t.me/alpha"
        assert canonical[0].evidence_count == 2
    finally:
        manager.close()


def test_same_slang_term_normalizes_and_merges(tmp_path: Path):
    manager, repository = _build_repository(tmp_path / "merge-slang.db")
    try:
        observations = [
            _slang_observation(
                repository, _raw(repository, "a"), term="土区礼品卡", normalized_term="土区礼品卡"
            ),
            _slang_observation(
                repository, _raw(repository, "b"), term="土区 礼品卡", normalized_term="土区 礼品卡"
            ),
        ]

        IntelligenceMergeEngine(repository).canonicalize_observations(observations)
        canonical = repository.list_canonical_entries(entry_type=EntryType.SLANG.value)

        assert len(canonical) == 1
        assert canonical[0].normalized_key == "土区礼品卡"
        assert canonical[0].evidence_count == 2
    finally:
        manager.close()


def test_different_urls_create_separate_entries(tmp_path: Path):
    manager, repository = _build_repository(tmp_path / "merge-different-url.db")
    try:
        observations = [
            _channel_observation(repository, _raw(repository, "a"), urls=["t.me/alpha"]),
            _channel_observation(repository, _raw(repository, "b"), urls=["t.me/beta"]),
        ]

        IntelligenceMergeEngine(repository).canonicalize_observations(observations)
        canonical = repository.list_canonical_entries(entry_type=EntryType.CHANNEL.value)

        assert {entry.normalized_key for entry in canonical} == {"t.me/alpha", "t.me/beta"}
    finally:
        manager.close()


def test_semantic_similarity_creates_related_candidate_not_merge(tmp_path: Path):
    manager, repository = _build_repository(tmp_path / "merge-related.db")
    try:
        observations = [
            _channel_observation(repository, _raw(repository, "a"), name="Alpha", handles=["alpha"]),
            _channel_observation(repository, _raw(repository, "b"), name="Alpha chat", handles=["alpha_chat"]),
        ]
        engine = IntelligenceMergeEngine(repository)
        engine.canonicalize_observations(observations)
        entries = repository.list_canonical_entries(entry_type=EntryType.CHANNEL.value)

        assert len(entries) == 2
        engine.create_related_candidates(entries[0], entries[1], 0.91)

        with manager._get_connection() as conn:
            rows = cast(
                List[Any],
                conn.cursor().execute("SELECT * FROM intelligence_related_candidates").fetchall(),
            )

        assert len(rows) == 1
        assert rows[0]["relationship_type"] == "semantic_similarity"
        assert repository.list_canonical_entries(entry_type=EntryType.CHANNEL.value)[0].evidence_count == 1
    finally:
        manager.close()


def test_raw_ttl_purge_does_not_delete_canonical_entries(tmp_path: Path):
    manager, repository = _build_repository(tmp_path / "merge-ttl.db")
    try:
        raw = RawIntelligenceItem.create(
            source_type="telegram_group",
            source_id="chat-1",
            raw_text="old",
            content_hash="old-hash",
            expires_at=datetime.utcnow() - timedelta(days=1),
        )
        repository.save_raw_item(raw)
        observation = _channel_observation(repository, raw, handles=["alpha"])
        IntelligenceMergeEngine(repository).canonicalize_observations([observation])

        assert repository.delete_expired_raw_items(datetime.utcnow()) == 1
        canonical = repository.list_canonical_entries(entry_type=EntryType.CHANNEL.value)

        assert len(canonical) == 1
        assert canonical[0].normalized_key == "alpha"
        assert canonical[0].latest_raw_item_id is None
    finally:
        manager.close()


def test_evidence_count_and_confidence_update_on_merge(tmp_path: Path):
    manager, repository = _build_repository(tmp_path / "merge-confidence.db")
    try:
        first = _channel_observation(
            repository, _raw(repository, "a"), handles=["alpha"], confidence=0.8
        )
        second = _channel_observation(
            repository, _raw(repository, "b"), handles=["alpha"], confidence=0.6
        )
        engine = IntelligenceMergeEngine(repository)

        engine.canonicalize_observations([first])
        assert repository.list_canonical_entries()[0].evidence_count == 1
        engine.canonicalize_observations([second])
        canonical = repository.list_canonical_entries()[0]

        assert canonical.evidence_count == 2
        assert canonical.confidence == pytest.approx(0.7)
    finally:
        manager.close()


def test_low_confidence_observation_is_not_auto_canonicalized(tmp_path: Path):
    manager, repository = _build_repository(tmp_path / "merge-low-confidence.db")
    try:
        observation = _channel_observation(
            repository, _raw(repository, "a"), handles=["alpha"], confidence=0.59
        )

        entries = IntelligenceMergeEngine(repository).canonicalize_observations([observation])

        assert entries == []
        assert repository.list_canonical_entries() == []
        assert repository.get_uncanonicalized_observations(10)[0].id == observation.id
    finally:
        manager.close()


def test_aliases_are_deduplicated_case_insensitively(tmp_path: Path):
    manager, repository = _build_repository(tmp_path / "merge-aliases.db")
    try:
        engine = IntelligenceMergeEngine(repository)
        assert engine.merge_aliases(["alpha", "BETA"], ["beta", "gamma"]) == [
            "alpha",
            "beta",
            "gamma",
        ]

        observations = [
            _channel_observation(
                repository, _raw(repository, "a"), handles=["alpha"], aliases=["alpha", "BETA"]
            ),
            _channel_observation(
                repository, _raw(repository, "b"), handles=["alpha"], aliases=["beta", "gamma"]
            ),
        ]

        engine.canonicalize_observations(observations)

        assert repository.list_canonical_entries()[0].aliases == ["alpha", "beta", "gamma"]
    finally:
        manager.close()
