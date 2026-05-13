from importlib import import_module
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, List, Optional, cast

import pytest

from crypto_news_analyzer.domain.models import (
    CanonicalIntelligenceEntry,
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
    literal_meaning: Optional[str] = None,
    contextual_meaning: Optional[str] = None,
    aliases: Optional[List[str]] = None,
    primary_label: str = PrimaryLabel.OTHER.value,
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
        literal_meaning=literal_meaning,
        contextual_meaning=contextual_meaning,
        aliases_or_variants=aliases or [term],
        primary_label=primary_label,
    )
    repository.save_observation(observation)
    return observation


def _slang_entry(
    repository: SQLiteIntelligenceRepository,
    *,
    normalized_key: str,
    display_name: str,
    primary_label: str = PrimaryLabel.OTHER.value,
    aliases: Optional[List[str]] = None,
    tracking_enabled: bool = False,
):
    entry = CanonicalIntelligenceEntry.create(
        entry_type=EntryType.SLANG.value,
        normalized_key=normalized_key,
        display_name=display_name,
        explanation="same meaning",
        usage_summary="same usage",
        primary_label=primary_label,
        confidence=0.8,
        aliases=aliases or [display_name],
        tracking_enabled=tracking_enabled,
    )
    repository.save_canonical_entry(entry)
    return entry


class FakeSemanticSearchService:
    def __init__(self, results: Optional[List[Any]] = None, should_fail: bool = False):
        self.results = results or []
        self.should_fail = should_fail
        self.query_texts: List[str] = []
        self.calls: List[dict[str, Any]] = []

    def semantic_search(self, **kwargs: Any):
        self.calls.append(kwargs)
        self.query_texts.append(str(kwargs.get("query_text") or ""))
        if self.should_fail:
            raise RuntimeError("embedding unavailable")
        return self.results, len(self.results)


def test_same_telegram_username_merges_into_one_canonical_entry(tmp_path: Path):
    manager, repository = _build_repository(tmp_path / "merge-handle.db")
    try:
        observations = [
            _channel_observation(repository, _raw(repository, "a"), handles=["@alpha"]),
            _channel_observation(repository, _raw(repository, "b"), handles=["@alpha"]),
        ]

        entries = IntelligenceMergeEngine(repository).canonicalize_observations(observations)
        canonical = repository.list_canonical_entries(
            entry_type=EntryType.CHANNEL.value, tracking_scope="all"
        )

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
        canonical = repository.list_canonical_entries(
            entry_type=EntryType.CHANNEL.value, tracking_scope="all"
        )

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
        canonical = repository.list_canonical_entries(
            entry_type=EntryType.SLANG.value, tracking_scope="all"
        )

        assert len(canonical) == 1
        assert canonical[0].normalized_key == "土区礼品卡"
        assert canonical[0].evidence_count == 2
    finally:
        manager.close()


def test_synonymous_slang_semantic_match_auto_merges_without_duplicate(tmp_path: Path):
    manager, repository = _build_repository(tmp_path / "merge-slang-semantic.db")
    try:
        existing = _slang_entry(
            repository,
            normalized_key="diamondhands",
            display_name="diamond hands",
            primary_label=PrimaryLabel.CRYPTO.value,
            aliases=["diamond hands"],
            tracking_enabled=True,
        )
        observation = _slang_observation(
            repository,
            _raw(repository, "semantic"),
            term="钻石手",
            normalized_term="钻石手",
            literal_meaning="diamond hand",
            contextual_meaning="refuses to sell during volatility",
            aliases=["钻石手", "diamond hand"],
            primary_label=PrimaryLabel.CRYPTO.value,
        )
        search_service = FakeSemanticSearchService(results=[(existing, 0.93)])

        entries = IntelligenceMergeEngine(
            repository, search_service=search_service
        ).canonicalize_observations([observation])
        canonical = repository.list_canonical_entries(
            entry_type=EntryType.SLANG.value, tracking_scope="all"
        )

        assert len(entries) == 1
        assert len(canonical) == 1
        assert canonical[0].id == existing.id
        assert canonical[0].evidence_count == 2
        assert canonical[0].tracking_enabled is True
        assert canonical[0].aliases == ["diamond hand", "diamond hands", "钻石手"]
        assert search_service.query_texts == [
            "钻石手 diamond hand refuses to sell during volatility 钻石手 diamond hand crypto"
        ]
    finally:
        manager.close()


def test_untracked_slang_semantic_match_auto_merges_without_duplicate(tmp_path: Path):
    manager, repository = _build_repository(tmp_path / "merge-untracked-slang-semantic.db")
    try:
        existing = _slang_entry(
            repository,
            normalized_key="diamondhands",
            display_name="diamond hands",
            primary_label=PrimaryLabel.CRYPTO.value,
            aliases=["diamond hands"],
            tracking_enabled=False,
        )
        observation = _slang_observation(
            repository,
            _raw(repository, "untracked semantic"),
            term="钻石手",
            normalized_term="钻石手",
            literal_meaning="diamond hand",
            contextual_meaning="refuses to sell during volatility",
            aliases=["钻石手", "diamond hand"],
            primary_label=PrimaryLabel.CRYPTO.value,
        )
        search_service = FakeSemanticSearchService(results=[(existing, 0.93)])

        entries = IntelligenceMergeEngine(
            repository, search_service=search_service
        ).canonicalize_observations([observation])
        canonical = repository.list_canonical_entries(
            entry_type=EntryType.SLANG.value, tracking_scope="all"
        )

        assert len(entries) == 1
        assert len(canonical) == 1
        assert canonical[0].id == existing.id
        assert canonical[0].evidence_count == 2
        assert canonical[0].tracking_enabled is False
        assert search_service.calls[0]["tracking_scope"] == "all"
    finally:
        manager.close()


def test_untracked_slang_alias_match_merges_without_duplicate(tmp_path: Path):
    manager, repository = _build_repository(tmp_path / "merge-untracked-slang-alias.db")
    try:
        existing = _slang_entry(
            repository,
            normalized_key="diamondhands",
            display_name="diamond hands",
            primary_label=PrimaryLabel.CRYPTO.value,
            aliases=["diamond hands"],
            tracking_enabled=False,
        )
        observation = _slang_observation(
            repository,
            _raw(repository, "untracked alias"),
            term="diamond hand",
            normalized_term="diamond hand",
            aliases=["diamond hands"],
            primary_label=PrimaryLabel.CRYPTO.value,
        )

        IntelligenceMergeEngine(repository).canonicalize_observations([observation])
        canonical = repository.list_canonical_entries(
            entry_type=EntryType.SLANG.value, tracking_scope="all"
        )

        assert len(canonical) == 1
        assert canonical[0].id == existing.id
        assert canonical[0].evidence_count == 2
    finally:
        manager.close()


@pytest.mark.parametrize(
    ("candidate_score", "candidate_label", "ignored", "candidate_type"),
    [
        (0.91, PrimaryLabel.CRYPTO.value, False, EntryType.SLANG.value),
        (0.93, PrimaryLabel.OTHER.value, False, EntryType.SLANG.value),
        (0.93, PrimaryLabel.CRYPTO.value, True, EntryType.SLANG.value),
        (0.93, PrimaryLabel.CRYPTO.value, False, EntryType.CHANNEL.value),
    ],
)
def test_non_qualifying_semantic_candidates_do_not_auto_merge(
    tmp_path: Path,
    candidate_score: float,
    candidate_label: str,
    ignored: bool,
    candidate_type: str,
):
    manager, repository = _build_repository(tmp_path / f"merge-slang-guard-{candidate_type}.db")
    try:
        if candidate_type == EntryType.CHANNEL.value:
            candidate = CanonicalIntelligenceEntry.create(
                entry_type=EntryType.CHANNEL.value,
                normalized_key="t.me/diamondhands",
                display_name="Diamond Hands Channel",
                primary_label=candidate_label,
            )
            repository.save_canonical_entry(candidate)
        else:
            candidate = _slang_entry(
                repository,
                normalized_key="diamondhands",
                display_name="diamond hands",
                primary_label=candidate_label,
            )
        if ignored:
            ignored_candidate = repository.ignore_canonical_entry(
                candidate.id, ignored_by="operator"
            )
            assert ignored_candidate is not None
            candidate = ignored_candidate

        observation = _slang_observation(
            repository,
            _raw(repository, "guard"),
            term="钻石手",
            normalized_term="钻石手",
            contextual_meaning="refuses to sell during volatility",
            primary_label=PrimaryLabel.CRYPTO.value,
        )
        search_service = FakeSemanticSearchService(results=[(candidate, candidate_score)])

        IntelligenceMergeEngine(
            repository, search_service=search_service
        ).canonicalize_observations([observation])
        slang_entries = repository.list_canonical_entries(
            entry_type=EntryType.SLANG.value, tracking_scope="all"
        )
        if ignored:
            candidate_after_merge = repository.get_canonical_entry_by_id(candidate.id)
            assert candidate_after_merge is not None
            assert candidate_after_merge.evidence_count == 2
            return

        should_merge = (
            candidate_type == EntryType.SLANG.value
            and candidate_score >= 0.92
            and candidate_label == PrimaryLabel.CRYPTO.value
        )
        expected_count = 1 if should_merge or candidate_type == EntryType.CHANNEL.value else 2
        assert len(slang_entries) == expected_count
        assert any(entry.normalized_key == "钻石手" for entry in slang_entries) is not should_merge
    finally:
        manager.close()


def test_semantic_slang_lookup_fallback_creates_separate_entry_on_embedding_failure(
    tmp_path: Path,
):
    manager, repository = _build_repository(tmp_path / "merge-slang-fallback.db")
    try:
        existing = _slang_entry(
            repository,
            normalized_key="diamondhands",
            display_name="diamond hands",
            primary_label=PrimaryLabel.CRYPTO.value,
        )
        observation = _slang_observation(
            repository,
            _raw(repository, "fallback"),
            term="钻石手",
            normalized_term="钻石手",
            contextual_meaning="refuses to sell during volatility",
            primary_label=PrimaryLabel.CRYPTO.value,
        )
        search_service = FakeSemanticSearchService(results=[(existing, 0.99)], should_fail=True)

        IntelligenceMergeEngine(
            repository, search_service=search_service
        ).canonicalize_observations([observation])
        canonical = repository.list_canonical_entries(
            entry_type=EntryType.SLANG.value, tracking_scope="all"
        )

        assert {entry.normalized_key for entry in canonical} == {"diamondhands", "钻石手"}
        assert repository.get_uncanonicalized_observations(10) == []
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
        canonical = repository.list_canonical_entries(
            entry_type=EntryType.CHANNEL.value, tracking_scope="all"
        )

        assert {entry.normalized_key for entry in canonical} == {"t.me/alpha", "t.me/beta"}
    finally:
        manager.close()


def test_semantic_similarity_creates_related_candidate_not_merge(tmp_path: Path):
    manager, repository = _build_repository(tmp_path / "merge-related.db")
    try:
        observations = [
            _channel_observation(
                repository, _raw(repository, "a"), name="Alpha", handles=["alpha"]
            ),
            _channel_observation(
                repository, _raw(repository, "b"), name="Alpha chat", handles=["alpha_chat"]
            ),
        ]
        engine = IntelligenceMergeEngine(repository)
        engine.canonicalize_observations(observations)
        entries = repository.list_canonical_entries(
            entry_type=EntryType.CHANNEL.value, tracking_scope="all"
        )

        assert len(entries) == 2
        engine.create_related_candidates(entries[0], entries[1], 0.91)

        with manager._get_connection() as conn:
            rows = cast(
                List[Any],
                conn.cursor().execute("SELECT * FROM intelligence_related_candidates").fetchall(),
            )

        assert len(rows) == 1
        assert rows[0]["relationship_type"] == "semantic_similarity"
        assert (
            repository.list_canonical_entries(
                entry_type=EntryType.CHANNEL.value, tracking_scope="all"
            )[0].evidence_count
            == 1
        )
    finally:
        manager.close()


def test_channel_semantic_similarity_never_auto_merges_exact_only_channels(tmp_path: Path):
    manager, repository = _build_repository(tmp_path / "merge-channel-exact-only.db")
    try:
        existing = CanonicalIntelligenceEntry.create(
            entry_type=EntryType.CHANNEL.value,
            normalized_key="alpha",
            display_name="Alpha Trading",
            primary_label=PrimaryLabel.CRYPTO.value,
            aliases=["Alpha Signals"],
        )
        repository.save_canonical_entry(existing)
        observation = _channel_observation(
            repository,
            _raw(repository, "near channel"),
            name="Alpha Signals Chat",
            handles=["alpha_signals_chat"],
            aliases=["Alpha Signals"],
        )
        search_service = FakeSemanticSearchService(results=[(existing, 0.99)])

        IntelligenceMergeEngine(
            repository, search_service=search_service
        ).canonicalize_observations([observation])
        canonical = repository.list_canonical_entries(
            entry_type=EntryType.CHANNEL.value, tracking_scope="all"
        )

        assert {entry.normalized_key for entry in canonical} == {"alpha", "alpha_signals_chat"}
        assert all(entry.evidence_count == 1 for entry in canonical)
        assert search_service.query_texts == []
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
        canonical = repository.list_canonical_entries(
            entry_type=EntryType.CHANNEL.value, tracking_scope="all"
        )

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
        assert repository.list_canonical_entries(tracking_scope="all")[0].evidence_count == 1
        engine.canonicalize_observations([second])
        canonical = repository.list_canonical_entries(tracking_scope="all")[0]

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
        assert repository.list_canonical_entries(tracking_scope="all") == []
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

        assert repository.list_canonical_entries(tracking_scope="all")[0].aliases == [
            "alpha",
            "beta",
            "gamma",
        ]
    finally:
        manager.close()
