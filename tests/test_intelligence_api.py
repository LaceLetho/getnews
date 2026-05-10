"""Tests for intelligence HTTP query APIs."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any, List, Optional, Tuple

import pytest
from fastapi.testclient import TestClient

from crypto_news_analyzer import api_server
from crypto_news_analyzer.domain.models import (
    CanonicalIntelligenceEntry,
    EntryType,
    ExtractionObservation,
    IntelligenceCrawlCheckpoint,
    PrimaryLabel,
    RawIntelligenceItem,
)
from crypto_news_analyzer.domain.repositories import (
    IntelligenceEvidenceAnchor,
    IntelligenceRepository,
    IntelligenceRawContextWindow,
)
from crypto_news_analyzer.models import StorageConfig


def _authorized_headers() -> dict[str, str]:
    return {"Authorization": "Bearer test-api-key"}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _make_raw_item(
    raw_item_id: str = "raw-001",
    source_type: str = "telegram_group",
    raw_text: str = "GPT Plus 土区礼品卡渠道 @seller",
    expires_at: Optional[datetime] = None,
    source_url: Optional[str] = "https://t.me/seller",
    published_at: Optional[datetime] = None,
) -> RawIntelligenceItem:
    if expires_at is None:
        expires_at = _utcnow() + timedelta(days=30)
    if published_at is None:
        published_at = _utcnow() - timedelta(hours=2)
    return RawIntelligenceItem(
        id=raw_item_id,
        source_type=source_type,
        raw_text=raw_text,
        content_hash="abc123",
        expires_at=expires_at,
        source_url=source_url,
        published_at=published_at,
        collected_at=_utcnow(),
    )


def _make_observation(
    observation_id: str,
    raw_item_id: str,
    entry_type: str = EntryType.SLANG.value,
) -> ExtractionObservation:
    if entry_type == EntryType.SLANG.value:
        return ExtractionObservation(
            id=observation_id,
            raw_item_id=raw_item_id,
            entry_type=entry_type,
            confidence=0.82,
            model_name="opencode-go/glm-5.1",
            prompt_version="v1.0",
            schema_version="v1.0",
            term="土区礼品卡",
            normalized_term="土区礼品卡",
            created_at=_utcnow(),
        )
    return ExtractionObservation(
        id=observation_id,
        raw_item_id=raw_item_id,
        entry_type=entry_type,
        confidence=0.82,
        model_name="opencode-go/glm-5.1",
        prompt_version="v1.0",
        schema_version="v1.0",
        channel_name="Seller Channel",
        created_at=_utcnow(),
    )


def _make_canonical_entry(
    entry_id: str = "entry-001",
    entry_type: str = EntryType.CHANNEL.value,
    normalized_key: str = "t.me/seller",
    display_name: str = "@seller",
    explanation: str = "GPT Plus subscription channel",
    primary_label: Optional[str] = PrimaryLabel.AI.value,
    confidence: float = 0.85,
    last_seen_at: Optional[datetime] = None,
    evidence_count: int = 3,
    latest_raw_item_id: Optional[str] = "raw-001",
    usage_summary: Optional[str] = None,
    **kwargs: Any,
) -> CanonicalIntelligenceEntry:
    if last_seen_at is None:
        last_seen_at = _utcnow() - timedelta(hours=1)
    create_kwargs: dict[str, Any] = dict(kwargs)
    if usage_summary is not None:
        create_kwargs["usage_summary"] = usage_summary
    if "tracking_enabled" not in create_kwargs:
        create_kwargs["tracking_enabled"] = entry_type == EntryType.CHANNEL.value
    # Use CanonicalIntelligenceEntry directly to set a custom ID
    now = _utcnow()
    return CanonicalIntelligenceEntry(
        id=entry_id,
        entry_type=entry_type,
        normalized_key=normalized_key,
        display_name=display_name,
        explanation=explanation,
        primary_label=primary_label,
        confidence=confidence,
        first_seen_at=_utcnow() - timedelta(days=7),
        last_seen_at=last_seen_at,
        evidence_count=evidence_count,
        latest_raw_item_id=latest_raw_item_id,
        aliases=["gpt plus seller"],
        secondary_tags=["gpt", "subscription"],
        model_name="opencode-go/glm-5.1",
        prompt_version="v1.0",
        schema_version="v1.0",
        created_at=now,
        updated_at=now,
        **create_kwargs,
    )


class _InMemoryIntelligenceRepository(IntelligenceRepository):
    """In-memory intelligence repository for testing."""

    def __init__(self) -> None:
        self.raw_items: dict[str, RawIntelligenceItem] = {}
        self.canonical_entries: dict[str, CanonicalIntelligenceEntry] = {}
        self.observations: dict[str, ExtractionObservation] = {}
        self.checkpoints: dict[tuple[str, str], IntelligenceCrawlCheckpoint] = {}
        self.related_candidates: list[Any] = []
        self.evidence_links: list[tuple[str, str, str]] = []
        self.list_calls: list[dict[str, Any]] = []
        self.count_calls: list[dict[str, Any]] = []
        self.discovery_presented_calls: list[list[str]] = []
        self.context_window_calls: list[tuple[str, str, int, int]] = []
        self.get_by_id_calls: int = 0
        self.search_calls: int = 0

    def save_raw_item(self, raw_item: RawIntelligenceItem) -> str:
        self.raw_items[raw_item.id] = raw_item
        return raw_item.id

    def get_raw_items_by_source(
        self, source_type: str, source_id: str, limit: int, offset: int
    ) -> List[RawIntelligenceItem]:
        return []

    def get_raw_items_expiring_before(self, cutoff_time: datetime) -> List[RawIntelligenceItem]:
        return [
            item
            for item in self.raw_items.values()
            if item.expires_at and item.expires_at < cutoff_time
        ]

    def get_raw_item_by_id(self, raw_item_id: str) -> Optional[RawIntelligenceItem]:
        self.get_by_id_calls += 1
        return self.raw_items.get(raw_item_id)

    def delete_expired_raw_items(self, cutoff_time: datetime) -> int:
        return 0

    def purge_raw_text_older_than(self, cutoff_time: datetime) -> int:
        return 0

    def save_observation(self, observation: ExtractionObservation) -> str:
        self.observations[observation.id] = observation
        return observation.id

    def get_observations_by_raw_item(self, raw_item_id: str) -> List[ExtractionObservation]:
        return []

    def get_raw_item_ids_with_existing_observations(
        self, raw_item_ids: List[str], prompt_version: str
    ) -> set[str]:
        return {
            observation.raw_item_id
            for observation in self.observations.values()
            if observation.raw_item_id in raw_item_ids
            and observation.prompt_version == prompt_version
        }

    def get_uncanonicalized_observations(self, limit: int) -> List[ExtractionObservation]:
        return []

    def mark_observation_canonicalized(self, observation_id: str) -> bool:
        return False

    def save_canonical_entry(
        self, entry: CanonicalIntelligenceEntry, observation_id: Optional[str] = None
    ) -> str:
        self.canonical_entries[entry.id] = entry
        if observation_id and entry.latest_raw_item_id:
            self.save_entry_evidence_link(entry.id, observation_id, entry.latest_raw_item_id)
        return entry.id

    def get_canonical_entry_by_normalized_key(
        self, entry_type: str, normalized_key: str
    ) -> Optional[CanonicalIntelligenceEntry]:
        for entry in self.canonical_entries.values():
            if entry.entry_type == entry_type and entry.normalized_key == normalized_key:
                return entry
        return None

    def get_canonical_entry_by_id(self, entry_id: str) -> Optional[CanonicalIntelligenceEntry]:
        return self.canonical_entries.get(entry_id)

    def upsert_canonical_entry(
        self, entry: CanonicalIntelligenceEntry, observation_id: Optional[str] = None
    ) -> str:
        self.canonical_entries[entry.id] = entry
        if observation_id and entry.latest_raw_item_id:
            self.save_entry_evidence_link(entry.id, observation_id, entry.latest_raw_item_id)
        return entry.id

    def save_entry_evidence_link(
        self, entry_id: str, observation_id: str, raw_item_id: str
    ) -> None:
        link = (entry_id, observation_id, raw_item_id)
        if link not in self.evidence_links:
            self.evidence_links.append(link)

    def list_entry_evidence_anchors(
        self, entry_id: str, page: int = 1, page_size: int = 20
    ) -> List[IntelligenceEvidenceAnchor]:
        anchors: List[IntelligenceEvidenceAnchor] = []
        for linked_entry_id, observation_id, raw_item_id in self.evidence_links:
            if linked_entry_id != entry_id:
                continue
            raw_item = self.raw_items.get(raw_item_id)
            if raw_item is None:
                continue
            observation = self.observations.get(observation_id)
            anchors.append(
                IntelligenceEvidenceAnchor(
                    entry_id=linked_entry_id,
                    observation_id=observation_id,
                    raw_item_id=raw_item_id,
                    observed_at=observation.created_at if observation else None,
                    published_at=raw_item.published_at,
                    collected_at=raw_item.collected_at,
                )
            )
        anchors.sort(
            key=lambda anchor: (
                anchor.published_at or anchor.collected_at,
                anchor.raw_item_id,
            ),
            reverse=True,
        )
        start = (page - 1) * page_size
        return anchors[start : start + page_size]

    def count_entry_evidence_anchors(self, entry_id: str) -> int:
        return sum(
            1 for linked_entry_id, _, _ in self.evidence_links if linked_entry_id == entry_id
        )

    def get_entry_evidence_context_window(
        self, entry_id: str, raw_item_id: str, before: int = 10, after: int = 10
    ) -> Optional[IntelligenceRawContextWindow]:
        self.context_window_calls.append((entry_id, raw_item_id, before, after))
        anchors = [
            anchor
            for anchor in self.list_entry_evidence_anchors(entry_id, page=1, page_size=1000)
            if anchor.raw_item_id == raw_item_id
        ]
        if not anchors:
            return None
        anchor = anchors[0]
        raw_item = self.raw_items.get(raw_item_id)
        if raw_item is None:
            return None
        scoped_items = [
            item
            for item in self.raw_items.values()
            if item.source_type == raw_item.source_type
            and item.source_id == raw_item.source_id
            and item.chat_id == raw_item.chat_id
            and item.thread_id == raw_item.thread_id
            and item.topic_id == raw_item.topic_id
        ]
        scoped_items.sort(
            key=lambda item: (
                item.published_at or item.collected_at,
                item.id,
            )
        )
        anchor_index = next(
            index for index, item in enumerate(scoped_items) if item.id == raw_item_id
        )
        start = max(0, anchor_index - before)
        stop = anchor_index + after + 1
        return IntelligenceRawContextWindow(anchor=anchor, items=scoped_items[start:stop])

    def list_canonical_entries(
        self,
        entry_type: Optional[str] = None,
        primary_label: Optional[str] = None,
        window: Optional[datetime] = None,
        page: int = 1,
        page_size: int = 100,
        tracking_scope: str = "following",
    ) -> List[CanonicalIntelligenceEntry]:
        self.list_calls.append(
            {
                "entry_type": entry_type,
                "primary_label": primary_label,
                "window": window,
                "page": page,
                "page_size": page_size,
                "tracking_scope": tracking_scope,
            }
        )
        entries = [e for e in self.canonical_entries.values() if not e.is_ignored]
        entries = self._apply_tracking_scope(entries, tracking_scope)
        if entry_type:
            entries = [e for e in entries if e.entry_type == entry_type]
        if primary_label:
            entries = [e for e in entries if e.primary_label == primary_label]
        if window:
            entries = [e for e in entries if e.last_seen_at and e.last_seen_at >= window]
        entries.sort(
            key=lambda e: e.last_seen_at or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )
        start = (page - 1) * page_size
        return entries[start : start + page_size]

    def count_canonical_entries(
        self,
        entry_type: Optional[str] = None,
        primary_label: Optional[str] = None,
        window: Optional[datetime] = None,
        tracking_scope: str = "following",
    ) -> int:
        self.count_calls.append(
            {
                "entry_type": entry_type,
                "primary_label": primary_label,
                "window": window,
                "tracking_scope": tracking_scope,
            }
        )
        entries = [e for e in self.canonical_entries.values() if not e.is_ignored]
        entries = self._apply_tracking_scope(entries, tracking_scope)
        if entry_type:
            entries = [e for e in entries if e.entry_type == entry_type]
        if primary_label:
            entries = [e for e in entries if e.primary_label == primary_label]
        if window:
            entries = [e for e in entries if e.last_seen_at and e.last_seen_at >= window]
        return len(entries)

    def _apply_tracking_scope(
        self, entries: List[CanonicalIntelligenceEntry], tracking_scope: str
    ) -> List[CanonicalIntelligenceEntry]:
        if tracking_scope == "following":
            return [
                entry
                for entry in entries
                if entry.entry_type != EntryType.SLANG.value or entry.tracking_enabled
            ]
        if tracking_scope == "discovery":
            return [
                entry
                for entry in entries
                if entry.entry_type == EntryType.SLANG.value
                and not entry.tracking_enabled
                and entry.discovery_presented_at is None
            ]
        return entries

    def follow_canonical_entry(self, entry_id: str) -> Optional[CanonicalIntelligenceEntry]:
        entry = self.canonical_entries.get(entry_id)
        if entry is None:
            return None
        entry.tracking_enabled = True
        return entry

    def unfollow_canonical_entry(self, entry_id: str) -> Optional[CanonicalIntelligenceEntry]:
        entry = self.canonical_entries.get(entry_id)
        if entry is None:
            return None
        entry.tracking_enabled = False
        return entry

    def mark_discovery_presented(self, entry_ids: List[str]) -> int:
        self.discovery_presented_calls.append(list(entry_ids))
        marked = 0
        now = _utcnow()
        for entry_id in dict.fromkeys(entry_ids):
            entry = self.canonical_entries.get(entry_id)
            if (
                entry is not None
                and entry.entry_type == EntryType.SLANG.value
                and not entry.tracking_enabled
                and not entry.is_ignored
                and entry.discovery_presented_at is None
            ):
                entry.discovery_presented_at = now
                marked += 1
        return marked

    def ignore_canonical_entry(
        self, entry_id: str, ignored_by: Optional[str] = None
    ) -> Optional[CanonicalIntelligenceEntry]:
        entry = self.canonical_entries.get(entry_id)
        if entry is None:
            return None
        from datetime import datetime as dt

        entry.is_ignored = True
        entry.ignored_at = dt.utcnow()
        entry.ignored_by = ignored_by
        return entry

    def unignore_canonical_entry(self, entry_id: str) -> Optional[CanonicalIntelligenceEntry]:
        entry = self.canonical_entries.get(entry_id)
        if entry is None:
            return None
        entry.is_ignored = False
        entry.ignored_at = None
        entry.ignored_by = None
        return entry

    def list_ignored_canonical_entries(
        self,
        entry_type: Optional[str] = None,
        primary_label: Optional[str] = None,
        window: Optional[datetime] = None,
        page: int = 0,
        page_size: int = 20,
    ) -> List[CanonicalIntelligenceEntry]:
        entries = [e for e in self.canonical_entries.values() if e.is_ignored]
        if entry_type:
            entries = [e for e in entries if e.entry_type == entry_type]
        if primary_label:
            entries = [e for e in entries if e.primary_label == primary_label]
        if window:
            entries = [e for e in entries if e.last_seen_at and e.last_seen_at >= window]
        entries.sort(
            key=lambda e: e.last_seen_at or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )
        start = page * page_size
        return entries[start : start + page_size]

    def count_ignored_canonical_entries(
        self,
        entry_type: Optional[str] = None,
        primary_label: Optional[str] = None,
        window: Optional[datetime] = None,
    ) -> int:
        entries = [e for e in self.canonical_entries.values() if e.is_ignored]
        if entry_type:
            entries = [e for e in entries if e.entry_type == entry_type]
        if primary_label:
            entries = [e for e in entries if e.primary_label == primary_label]
        if window:
            entries = [e for e in entries if e.last_seen_at and e.last_seen_at >= window]
        return len(entries)

    def update_embedding(self, entry_id: str, embedding: List[float], model: str) -> bool:
        return True

    def get_entries_missing_embeddings(self, limit: int) -> List[CanonicalIntelligenceEntry]:
        return []

    def count_semantic_search_candidates(
        self,
        query_embedding: List[float],
        entry_type: Optional[str] = None,
        primary_label: Optional[str] = None,
        window: Optional[datetime] = None,
        tracking_scope: str = "following",
    ) -> int:
        entries = list(self.canonical_entries.values())
        entries = [e for e in entries if not e.is_ignored]
        entries = self._apply_tracking_scope(entries, tracking_scope)
        if entry_type:
            entries = [e for e in entries if e.entry_type == entry_type]
        if primary_label:
            entries = [e for e in entries if e.primary_label == primary_label]
        if window:
            entries = [e for e in entries if e.last_seen_at and e.last_seen_at >= window]
        return len(entries)

    def semantic_search(
        self,
        query_embedding: List[float],
        entry_type: Optional[str] = None,
        primary_label: Optional[str] = None,
        window: Optional[datetime] = None,
        limit: int = 20,
        offset: int = 0,
        tracking_scope: str = "following",
    ) -> List[Tuple[CanonicalIntelligenceEntry, float]]:
        self.search_calls += 1
        entries = list(self.canonical_entries.values())
        entries = [e for e in entries if not e.is_ignored]
        entries = self._apply_tracking_scope(entries, tracking_scope)
        if entry_type:
            entries = [e for e in entries if e.entry_type == entry_type]
        if primary_label:
            entries = [e for e in entries if e.primary_label == primary_label]
        if window:
            entries = [e for e in entries if e.last_seen_at and e.last_seen_at >= window]
        results: List[Tuple[CanonicalIntelligenceEntry, float]] = [
            (e, e.confidence) for e in entries
        ]
        results.sort(key=lambda x: x[1], reverse=True)
        return results[offset : offset + limit]

    def save_related_candidate(
        self,
        entry_id_a: str,
        entry_id_b: str,
        similarity_score: float,
        relationship_type: str,
    ) -> None:
        self.related_candidates.append(
            (entry_id_a, entry_id_b, similarity_score, relationship_type)
        )

    def save_checkpoint(self, checkpoint: IntelligenceCrawlCheckpoint) -> None:
        self.checkpoints[(checkpoint.source_type, checkpoint.source_id)] = checkpoint

    def get_checkpoint(
        self, source_type: str, source_id: str
    ) -> Optional[IntelligenceCrawlCheckpoint]:
        return self.checkpoints.get((source_type, source_id))


class _FakeEmbeddingService:
    """Fake embedding service that returns fixed embeddings."""

    def __init__(self) -> None:
        self.generate_calls: int = 0

    def generate_embedding(self, text: str) -> list[float]:
        self.generate_calls += 1
        return [0.1] * 128


class _FakeController:
    """Fake controller for intelligence API tests."""

    def __init__(
        self,
        *,
        intelligence_repository: Optional[_InMemoryIntelligenceRepository] = None,
        embedding_service: Optional[_FakeEmbeddingService] = None,
    ) -> None:
        self.intelligence_repository = intelligence_repository
        self.embedding_service = embedding_service or _FakeEmbeddingService()
        self.analysis_repository = None
        self.datasource_repository = None
        self.semantic_search_repository = None
        self.command_handler = None
        self.data_manager = None
        self._repositories: dict[str, Any] = {}
        if intelligence_repository is not None:
            self._repositories["intelligence"] = intelligence_repository

        self.storage_config = StorageConfig(
            backend="sqlite",
            database_path=":memory:",
        )

        self.config_manager = SimpleNamespace(
            get_analysis_config=lambda: {
                "max_analysis_window_hours": 24,
                "min_analysis_window_hours": 1,
            },
            get_storage_config=lambda: self.storage_config,
            get_auth_config=lambda: SimpleNamespace(
                GROK_API_KEY="grok-key",
                KIMI_API_KEY="kimi-key",
                OPENCODE_API_KEY="opencode-key",
            ),
            config_data={},
        )

    @staticmethod
    def _normalize_manual_recipient_key(manual_source: str, recipient_id: str) -> str:
        return f"{manual_source}:{str(recipient_id).strip()}"

    def initialize_system(self) -> bool:
        return True

    def start_scheduler(self) -> None:
        return None

    def stop_scheduler(self) -> None:
        return None

    def start_command_listener(self) -> None:
        return None

    def stop_command_listener(self) -> None:
        return None


@pytest.fixture(autouse=True)
def api_key_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("API_KEY", "test-api-key")


def _build_test_app(
    monkeypatch: pytest.MonkeyPatch,
    controller: _FakeController,
    start_services: bool = False,
):
    """Build a TestClient for the intelligence API. Use as context manager."""
    monkeypatch.setattr(api_server, "MainController", lambda *_args, **_kwargs: controller)
    app = api_server.create_api_server(
        "./config.jsonc",
        start_services=start_services,
        start_scheduler=False,
        start_command_listener=False,
    )
    return TestClient(app)


# ──────────────────────────────────────────────────────────────────────
# Tests: Authentication
# ──────────────────────────────────────────────────────────────────────


def test_intelligence_entries_unauthorized_returns_401(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _InMemoryIntelligenceRepository()
    controller = _FakeController(intelligence_repository=repo)
    with _build_test_app(monkeypatch, controller) as client:
        response = client.get("/intelligence/entries")
    assert response.status_code == 401


def test_intelligence_search_unauthorized_returns_401(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _InMemoryIntelligenceRepository()
    controller = _FakeController(intelligence_repository=repo)
    with _build_test_app(monkeypatch, controller) as client:
        response = client.get("/intelligence/search?q=test")
    assert response.status_code == 401


def test_intelligence_raw_unauthorized_returns_401(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _InMemoryIntelligenceRepository()
    controller = _FakeController(intelligence_repository=repo)
    with _build_test_app(monkeypatch, controller) as client:
        response = client.get("/intelligence/raw/raw-001")
    assert response.status_code == 401


def test_intelligence_labels_unauthorized_returns_401(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _InMemoryIntelligenceRepository()
    controller = _FakeController(intelligence_repository=repo)
    with _build_test_app(monkeypatch, controller) as client:
        response = client.get("/intelligence/labels")
    assert response.status_code == 401


def test_intelligence_ignore_and_unignore_unauthorized_returns_401(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _InMemoryIntelligenceRepository()
    controller = _FakeController(intelligence_repository=repo)
    with _build_test_app(monkeypatch, controller) as client:
        ignore_response = client.post("/intelligence/entries/entry-001/ignore")
        unignore_response = client.post("/intelligence/entries/entry-001/unignore")
    assert ignore_response.status_code == 401
    assert unignore_response.status_code == 401


def test_intelligence_discovery_follow_and_unfollow_unauthorized_returns_401(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _InMemoryIntelligenceRepository()
    controller = _FakeController(intelligence_repository=repo)
    with _build_test_app(monkeypatch, controller) as client:
        discovery_response = client.get("/intelligence/discovery")
        follow_response = client.post("/intelligence/entries/entry-001/follow")
        unfollow_response = client.post("/intelligence/entries/entry-001/unfollow")
    assert discovery_response.status_code == 401
    assert follow_response.status_code == 401
    assert unfollow_response.status_code == 401


# ──────────────────────────────────────────────────────────────────────
# Tests: GET /intelligence/entries
# ──────────────────────────────────────────────────────────────────────


def test_list_entries_returns_paginated_sorted_by_last_seen_desc(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _InMemoryIntelligenceRepository()
    older = _make_canonical_entry(
        entry_id="entry-older",
        display_name="Older Entry",
        last_seen_at=_utcnow() - timedelta(days=5),
    )
    newer = _make_canonical_entry(
        entry_id="entry-newer",
        display_name="Newer Entry",
        last_seen_at=_utcnow() - timedelta(hours=1),
    )
    repo.save_canonical_entry(older)
    repo.save_canonical_entry(newer)

    controller = _FakeController(intelligence_repository=repo)
    with _build_test_app(monkeypatch, controller) as client:
        response = client.get("/intelligence/entries", headers=_authorized_headers())

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert data["page"] == 1
    assert len(data["entries"]) == 2
    assert data["entries"][0]["display_name"] == "Newer Entry"
    assert data["entries"][0]["entry_id"] == "entry-newer"
    assert data["entries"][0]["entry_type"] == EntryType.CHANNEL.value
    assert "last_seen_at" not in data["entries"][0]
    assert data["entries"][1]["display_name"] == "Older Entry"


def test_list_entries_filters_by_entry_type(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _InMemoryIntelligenceRepository()
    channel = _make_canonical_entry(
        entry_id="ch-1", entry_type=EntryType.CHANNEL.value, display_name="Channel"
    )
    slang = _make_canonical_entry(
        entry_id="sl-1",
        entry_type=EntryType.SLANG.value,
        normalized_key="土区礼品卡",
        display_name="土区礼品卡",
        explanation="Turkish region gift card slang",
    )
    repo.save_canonical_entry(channel)
    repo.save_canonical_entry(slang)

    controller = _FakeController(intelligence_repository=repo)
    with _build_test_app(monkeypatch, controller) as client:
        response = client.get(
            "/intelligence/entries?entry_type=slang&tracking_scope=all",
            headers=_authorized_headers(),
        )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["entries"][0]["entry_type"] == "slang"


def test_list_entries_defaults_to_following_tracking_scope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _InMemoryIntelligenceRepository()
    followed_slang = _make_canonical_entry(
        entry_id="sl-followed",
        entry_type=EntryType.SLANG.value,
        normalized_key="followed-slang",
        display_name="Followed Slang",
        tracking_enabled=True,
    )
    untracked_slang = _make_canonical_entry(
        entry_id="sl-untracked",
        entry_type=EntryType.SLANG.value,
        normalized_key="untracked-slang",
        display_name="Untracked Slang",
        tracking_enabled=False,
    )
    untracked_channel = _make_canonical_entry(
        entry_id="channel-untracked",
        entry_type=EntryType.CHANNEL.value,
        normalized_key="channel-untracked",
        display_name="Untracked Channel",
        tracking_enabled=False,
    )
    repo.save_canonical_entry(followed_slang)
    repo.save_canonical_entry(untracked_slang)
    repo.save_canonical_entry(untracked_channel)

    controller = _FakeController(intelligence_repository=repo)
    with _build_test_app(monkeypatch, controller) as client:
        default_response = client.get("/intelligence/entries", headers=_authorized_headers())
        all_response = client.get(
            "/intelligence/entries?tracking_scope=all", headers=_authorized_headers()
        )

    assert default_response.status_code == 200
    assert [item["entry_id"] for item in default_response.json()["entries"]] == [
        "channel-untracked",
        "sl-followed",
    ]
    assert all_response.status_code == 200
    assert {item["entry_id"] for item in all_response.json()["entries"]} == {
        "sl-followed",
        "sl-untracked",
        "channel-untracked",
    }
    assert repo.list_calls[0]["tracking_scope"] == "following"
    assert repo.count_calls[0]["tracking_scope"] == "following"
    assert repo.list_calls[1]["tracking_scope"] == "all"


def test_discovery_returns_unseen_untracked_slang_then_marks_presented(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _InMemoryIntelligenceRepository()
    unseen_slang = _make_canonical_entry(
        entry_id="sl-unseen",
        entry_type=EntryType.SLANG.value,
        normalized_key="unseen-slang",
        display_name="Unseen Slang",
        tracking_enabled=False,
    )
    channel = _make_canonical_entry(entry_id="channel", display_name="Channel")
    followed_slang = _make_canonical_entry(
        entry_id="sl-followed",
        entry_type=EntryType.SLANG.value,
        normalized_key="followed-slang",
        display_name="Followed Slang",
        tracking_enabled=True,
    )
    repo.save_canonical_entry(unseen_slang)
    repo.save_canonical_entry(channel)
    repo.save_canonical_entry(followed_slang)

    controller = _FakeController(intelligence_repository=repo)
    with _build_test_app(monkeypatch, controller) as client:
        first_response = client.get("/intelligence/discovery", headers=_authorized_headers())
        second_response = client.get("/intelligence/discovery", headers=_authorized_headers())

    assert first_response.status_code == 200
    first_data = first_response.json()
    assert first_data["total"] == 1
    assert [item["entry_id"] for item in first_data["entries"]] == ["sl-unseen"]
    assert first_data["entries"][0]["entry_type"] == EntryType.SLANG.value
    assert repo.discovery_presented_calls == [["sl-unseen"], []]
    assert second_response.status_code == 200
    assert second_response.json()["entries"] == []


def test_follow_and_unfollow_toggle_tracking_without_changing_ignore_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _InMemoryIntelligenceRepository()
    entry = _make_canonical_entry(
        entry_id="sl-toggle",
        entry_type=EntryType.SLANG.value,
        normalized_key="toggle-slang",
        display_name="Toggle Slang",
        tracking_enabled=False,
    )
    repo.save_canonical_entry(entry)
    repo.ignore_canonical_entry("sl-toggle", ignored_by="operator-id")

    controller = _FakeController(intelligence_repository=repo)
    with _build_test_app(monkeypatch, controller) as client:
        follow_response = client.post(
            "/intelligence/entries/sl-toggle/follow", headers=_authorized_headers()
        )
        unfollow_response = client.post(
            "/intelligence/entries/sl-toggle/unfollow", headers=_authorized_headers()
        )

    assert follow_response.status_code == 200
    assert follow_response.json() == {
        "success": True,
        "entry_id": "sl-toggle",
        "tracking_enabled": True,
        "is_ignored": True,
    }
    assert unfollow_response.status_code == 200
    assert unfollow_response.json()["tracking_enabled"] is False
    assert repo.canonical_entries["sl-toggle"].is_ignored is True
    assert repo.canonical_entries["sl-toggle"].ignored_by == "operator-id"


def test_list_entries_filters_by_primary_label(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _InMemoryIntelligenceRepository()
    ai_entry = _make_canonical_entry(
        entry_id="ai-1", primary_label=PrimaryLabel.AI.value, display_name="AI Entry"
    )
    crypto_entry = _make_canonical_entry(
        entry_id="cr-1",
        primary_label=PrimaryLabel.CRYPTO.value,
        display_name="Crypto Entry",
        normalized_key="crypto-key",
    )
    repo.save_canonical_entry(ai_entry)
    repo.save_canonical_entry(crypto_entry)

    controller = _FakeController(intelligence_repository=repo)
    with _build_test_app(monkeypatch, controller) as client:
        response = client.get(
            "/intelligence/entries?primary_label=AI", headers=_authorized_headers()
        )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["entries"][0]["primary_label"] == "AI"


def test_list_entries_respects_pagination(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _InMemoryIntelligenceRepository()
    for i in range(5):
        entry = _make_canonical_entry(
            entry_id=f"entry-{i}",
            display_name=f"Entry {i}",
            normalized_key=f"key-{i}",
            last_seen_at=_utcnow() - timedelta(hours=i),
        )
        repo.save_canonical_entry(entry)

    controller = _FakeController(intelligence_repository=repo)
    with _build_test_app(monkeypatch, controller) as client:
        # Page 1, page_size=2
        response = client.get(
            "/intelligence/entries?page=1&page_size=2", headers=_authorized_headers()
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 5
        assert data["page"] == 1
        assert data["page_size"] == 2
        assert len(data["entries"]) == 2

        # Page 2
        response = client.get(
            "/intelligence/entries?page=2&page_size=2", headers=_authorized_headers()
        )
        data = response.json()
        assert len(data["entries"]) == 2

        # Page 3
        response = client.get(
            "/intelligence/entries?page=3&page_size=2", headers=_authorized_headers()
        )
        data = response.json()
        assert len(data["entries"]) == 1


def test_ignore_entry_hides_from_entries_and_labels(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _InMemoryIntelligenceRepository()
    ignored = _make_canonical_entry(
        entry_id="entry-ignored",
        display_name="Ignored Entry",
        normalized_key="ignored-key",
        primary_label=PrimaryLabel.AI.value,
    )
    visible = _make_canonical_entry(
        entry_id="entry-visible",
        display_name="Visible Entry",
        normalized_key="visible-key",
        primary_label=PrimaryLabel.AI.value,
        last_seen_at=_utcnow() - timedelta(minutes=5),
    )
    repo.save_canonical_entry(ignored)
    repo.save_canonical_entry(visible)

    controller = _FakeController(intelligence_repository=repo)
    with _build_test_app(monkeypatch, controller) as client:
        ignore_response = client.post(
            "/intelligence/entries/entry-ignored/ignore",
            headers=_authorized_headers(),
            json={"ignored_by": "operator-id"},
        )
        detail_response = client.get(
            "/intelligence/entries/entry-ignored", headers=_authorized_headers()
        )
        list_response = client.get("/intelligence/entries", headers=_authorized_headers())
        search_response = client.get(
            "/intelligence/search?q=ignored", headers=_authorized_headers()
        )
        labels_response = client.get("/intelligence/labels", headers=_authorized_headers())

    assert ignore_response.status_code == 200
    ignore_data = ignore_response.json()
    assert ignore_data == {
        "success": True,
        "entry_id": "entry-ignored",
        "is_ignored": True,
        "ignored_at": ignore_data["ignored_at"],
        "ignored_by": "operator-id",
    }
    assert detail_response.status_code == 200
    detail_data = detail_response.json()
    assert detail_data["is_ignored"] is True
    assert detail_data["ignored_by"] == "operator-id"
    assert detail_data["ignored_at"] is not None
    assert list_response.status_code == 200
    assert [item["entry_id"] for item in list_response.json()["entries"]] == ["entry-visible"]
    assert search_response.status_code == 200
    assert [item["entry_id"] for item in search_response.json()["results"]] == ["entry-visible"]
    assert labels_response.status_code == 200


def test_ignore_unignore_auth_missing_and_idempotent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _InMemoryIntelligenceRepository()
    entry = _make_canonical_entry(entry_id="entry-idempotent", display_name="Idempotent")
    repo.save_canonical_entry(entry)

    controller = _FakeController(intelligence_repository=repo)
    with _build_test_app(monkeypatch, controller) as client:
        missing_ignore = client.post(
            "/intelligence/entries/nonexistent/ignore", headers=_authorized_headers()
        )
        missing_unignore = client.post(
            "/intelligence/entries/nonexistent/unignore", headers=_authorized_headers()
        )
        unauthorized_ignore = client.post("/intelligence/entries/entry-idempotent/ignore")
        unauthorized_unignore = client.post("/intelligence/entries/entry-idempotent/unignore")
        first_ignore = client.post(
            "/intelligence/entries/entry-idempotent/ignore",
            headers=_authorized_headers(),
            json={"ignored_by": "user-a"},
        )
        second_ignore = client.post(
            "/intelligence/entries/entry-idempotent/ignore",
            headers=_authorized_headers(),
        )
        first_unignore = client.post(
            "/intelligence/entries/entry-idempotent/unignore",
            headers=_authorized_headers(),
        )
        second_unignore = client.post(
            "/intelligence/entries/entry-idempotent/unignore",
            headers=_authorized_headers(),
        )

    assert missing_ignore.status_code == 404
    assert missing_unignore.status_code == 404
    assert unauthorized_ignore.status_code == 401
    assert unauthorized_unignore.status_code == 401
    assert first_ignore.status_code == 200
    assert first_ignore.json()["ignored_by"] == "user-a"
    assert second_ignore.status_code == 200
    assert second_ignore.json()["ignored_by"] == "api"
    assert first_unignore.status_code == 200
    assert first_unignore.json()["is_ignored"] is False
    assert second_unignore.status_code == 200
    assert second_unignore.json()["is_ignored"] is False


# ──────────────────────────────────────────────────────────────────────
# Tests: GET /intelligence/labels
# ──────────────────────────────────────────────────────────────────────


def test_list_intelligence_labels_returns_primary_label_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _InMemoryIntelligenceRepository()
    controller = _FakeController(intelligence_repository=repo)
    with _build_test_app(monkeypatch, controller) as client:
        response = client.get("/intelligence/labels", headers=_authorized_headers())

    assert response.status_code == 200
    data = response.json()
    assert data["labels"] == [{"name": label.name, "value": label.value} for label in PrimaryLabel]


# ──────────────────────────────────────────────────────────────────────
# Tests: GET /intelligence/entries/{entry_id}
# ──────────────────────────────────────────────────────────────────────


def test_get_entry_detail_returns_full_entry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _InMemoryIntelligenceRepository()
    entry = _make_canonical_entry(
        entry_id="entry-full",
        display_name="Full Entry",
        normalized_key="full-key",
        usage_summary="Used for buying GPT Plus",
    )
    repo.save_canonical_entry(entry)

    controller = _FakeController(intelligence_repository=repo)
    with _build_test_app(monkeypatch, controller) as client:
        response = client.get("/intelligence/entries/entry-full", headers=_authorized_headers())

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "entry-full"
    assert data["entry_id"] == "entry-full"
    assert data["display_name"] == "Full Entry"
    assert data["evidence_count"] == 3
    assert data["raw_available"] is False
    assert data["evidence_page"] == 1
    assert data["evidence_page_size"] == 5


def test_get_entry_detail_returns_paginated_evidence_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _InMemoryIntelligenceRepository()
    entry = _make_canonical_entry(
        entry_id="entry-evidence",
        display_name="Evidence Entry",
        normalized_key="evidence-entry",
        evidence_count=6,
        latest_raw_item_id="raw-5",
    )
    repo.save_canonical_entry(entry)
    for index in range(6):
        raw_item = _make_raw_item(
            raw_item_id=f"raw-{index}",
            raw_text=f"raw text {index}",
            source_url=f"https://example.com/{index}",
            published_at=_utcnow() - timedelta(minutes=6 - index),
        )
        repo.save_raw_item(raw_item)
        observation = _make_observation(f"obs-{index}", raw_item.id)
        repo.save_observation(observation)
        repo.save_entry_evidence_link(entry.id, observation.id, raw_item.id)

    controller = _FakeController(intelligence_repository=repo)
    with _build_test_app(monkeypatch, controller) as client:
        first_response = client.get(
            "/intelligence/entries/entry-evidence", headers=_authorized_headers()
        )
        second_response = client.get(
            "/intelligence/entries/entry-evidence?evidence_page=2&evidence_page_size=5",
            headers=_authorized_headers(),
        )

    assert first_response.status_code == 200
    first_data = first_response.json()
    assert first_data["evidence_total"] == 6
    assert first_data["evidence_page"] == 1
    assert first_data["evidence_page_size"] == 5
    assert len(first_data["evidence_groups"]) == 5
    first_anchor_ids = [group["raw_item_id"] for group in first_data["evidence_groups"]]
    assert first_anchor_ids == ["raw-5", "raw-4", "raw-3", "raw-2", "raw-1"]
    first_group = first_data["evidence_groups"][0]
    assert first_group["anchor_raw_item"]["raw_item_id"] == "raw-5"
    assert first_group["anchor_raw_item"]["raw_text"] == "raw text 5"
    assert "raw-5" not in [item["raw_item_id"] for item in first_group["neighboring_raw_items"]]
    assert repo.context_window_calls[0] == ("entry-evidence", "raw-5", 10, 10)

    assert second_response.status_code == 200
    second_data = second_response.json()
    assert second_data["evidence_page"] == 2
    assert [group["raw_item_id"] for group in second_data["evidence_groups"]] == ["raw-0"]
    assert set(first_anchor_ids).isdisjoint(
        {group["raw_item_id"] for group in second_data["evidence_groups"]}
    )


def test_get_entry_detail_preserves_expired_evidence_warning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _InMemoryIntelligenceRepository()
    raw_item = _make_raw_item(
        raw_item_id="raw-purged",
        raw_text="raw text before purge",
        expires_at=_utcnow() + timedelta(days=1),
    )
    raw_item.raw_text = ""
    repo.save_raw_item(raw_item)
    observation = _make_observation("obs-purged", raw_item.id)
    repo.save_observation(observation)
    entry = _make_canonical_entry(
        entry_id="entry-purged",
        display_name="Purged Entry",
        normalized_key="purged-entry",
        evidence_count=1,
        latest_raw_item_id="raw-purged",
    )
    repo.save_canonical_entry(entry)
    repo.save_entry_evidence_link(entry.id, observation.id, raw_item.id)

    controller = _FakeController(intelligence_repository=repo)
    with _build_test_app(monkeypatch, controller) as client:
        response = client.get("/intelligence/entries/entry-purged", headers=_authorized_headers())

    assert response.status_code == 200
    group = response.json()["evidence_groups"][0]
    assert group["anchor_raw_item"]["raw_text"] is None
    assert group["warning"] == "Evidence raw text is unavailable because it has been purged."


def test_ignored_entries_list_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _InMemoryIntelligenceRepository()
    ignored_entry = _make_canonical_entry(
        entry_id="ignored",
        display_name="Ignored List Entry",
        normalized_key="ignored-list-key",
        primary_label=PrimaryLabel.CRYPTO.value,
    )
    visible_entry = _make_canonical_entry(
        entry_id="visible-list",
        display_name="Visible List Entry",
        normalized_key="visible-list-key",
        primary_label=PrimaryLabel.AI.value,
    )
    repo.save_canonical_entry(ignored_entry)
    repo.save_canonical_entry(visible_entry)
    repo.ignore_canonical_entry("ignored", ignored_by="operator-id")

    controller = _FakeController(intelligence_repository=repo)
    with _build_test_app(monkeypatch, controller) as client:
        response = client.get("/intelligence/entries/ignored", headers=_authorized_headers())

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert [item["entry_id"] for item in data["entries"]] == ["ignored"]
    assert data["entries"][0]["is_ignored"] is True
    assert data["entries"][0]["ignored_by"] == "operator-id"
    assert data["entries"][0]["ignored_at"] is not None


def test_get_entry_detail_not_found_returns_404(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _InMemoryIntelligenceRepository()
    controller = _FakeController(intelligence_repository=repo)
    with _build_test_app(monkeypatch, controller) as client:
        response = client.get("/intelligence/entries/nonexistent", headers=_authorized_headers())
    assert response.status_code == 404


# ──────────────────────────────────────────────────────────────────────
# Tests: GET /intelligence/entries/{entry_id}?include_raw=true
# ──────────────────────────────────────────────────────────────────────


def test_include_raw_returns_exact_text_within_ttl(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw_text = "GPT Plus 土区礼品卡渠道 @seller\n联系：https://t.me/seller"
    repo = _InMemoryIntelligenceRepository()

    raw_item = _make_raw_item(
        raw_item_id="raw-001",
        raw_text=raw_text,
        source_url="https://t.me/seller",
    )
    repo.save_raw_item(raw_item)

    entry = _make_canonical_entry(
        entry_id="entry-with-raw",
        latest_raw_item_id="raw-001",
    )
    repo.save_canonical_entry(entry)

    controller = _FakeController(intelligence_repository=repo)
    with _build_test_app(monkeypatch, controller) as client:
        response = client.get(
            "/intelligence/entries/entry-with-raw?include_raw=true",
            headers=_authorized_headers(),
        )

    assert response.status_code == 200
    data = response.json()
    assert data["raw_available"] is True
    assert data["raw_evidence"]["raw_text"] == raw_text
    assert data["raw_evidence"]["source_type"] == "telegram_group"
    assert data["raw_evidence"]["source_url"] == "https://t.me/seller"


def test_include_raw_returns_raw_available_false_when_expired(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw_text = "Expired content that should not be returned"
    repo = _InMemoryIntelligenceRepository()

    raw_item = _make_raw_item(
        raw_item_id="raw-expired",
        raw_text=raw_text,
        expires_at=_utcnow() - timedelta(days=1),
    )
    repo.save_raw_item(raw_item)

    entry = _make_canonical_entry(
        entry_id="entry-expired-raw",
        latest_raw_item_id="raw-expired",
    )
    repo.save_canonical_entry(entry)

    controller = _FakeController(intelligence_repository=repo)
    with _build_test_app(monkeypatch, controller) as client:
        response = client.get(
            "/intelligence/entries/entry-expired-raw?include_raw=true",
            headers=_authorized_headers(),
        )

    assert response.status_code == 200
    data = response.json()
    assert data["raw_available"] is False
    assert data["raw_evidence"] is None


def test_include_raw_false_does_not_query_repository(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _InMemoryIntelligenceRepository()
    entry = _make_canonical_entry(
        entry_id="entry-no-raw",
        latest_raw_item_id="raw-001",
    )
    repo.save_canonical_entry(entry)

    controller = _FakeController(intelligence_repository=repo)
    with _build_test_app(monkeypatch, controller) as client:
        response = client.get(
            "/intelligence/entries/entry-no-raw?include_raw=false",
            headers=_authorized_headers(),
        )

    assert response.status_code == 200
    data = response.json()
    assert data["raw_available"] is False
    # Source info is always fetched from raw item (even with include_raw=false)
    assert repo.get_by_id_calls == 1


def test_include_raw_only_if_entry_has_raw_item_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _InMemoryIntelligenceRepository()
    entry = _make_canonical_entry(
        entry_id="entry-no-raw-link",
        latest_raw_item_id=None,
    )
    repo.save_canonical_entry(entry)

    controller = _FakeController(intelligence_repository=repo)
    with _build_test_app(monkeypatch, controller) as client:
        response = client.get(
            "/intelligence/entries/entry-no-raw-link?include_raw=true",
            headers=_authorized_headers(),
        )

    assert response.status_code == 200
    data = response.json()
    assert data["raw_available"] is False


# ──────────────────────────────────────────────────────────────────────
# Tests: GET /intelligence/search
# ──────────────────────────────────────────────────────────────────────


def test_semantic_search_returns_ranked_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _InMemoryIntelligenceRepository()

    high_conf = _make_canonical_entry(
        entry_id="high-conf",
        display_name="High Confidence",
        normalized_key="high-conf",
        confidence=0.95,
    )
    low_conf = _make_canonical_entry(
        entry_id="low-conf",
        display_name="Low Confidence",
        normalized_key="low-conf",
        confidence=0.5,
    )
    repo.save_canonical_entry(high_conf)
    repo.save_canonical_entry(low_conf)

    embedding_service = _FakeEmbeddingService()
    controller = _FakeController(intelligence_repository=repo, embedding_service=embedding_service)
    with _build_test_app(monkeypatch, controller) as client:
        response = client.get(
            "/intelligence/search?q=GPT%20plus%E8%B4%AD%E4%B9%B0%E6%B8%A0%E9%81%93",
            headers=_authorized_headers(),
        )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert data["results"][0]["display_name"] == "High Confidence"
    assert data["results"][0]["entry_id"] == "high-conf"
    assert data["results"][0]["entry_type"] == EntryType.CHANNEL.value
    assert "last_seen_at" not in data["results"][0]
    assert data["results"][0]["similarity_score"] == 0.95
    assert data["results"][1]["display_name"] == "Low Confidence"


def test_semantic_search_filters_by_entry_type(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _InMemoryIntelligenceRepository()
    channel = _make_canonical_entry(
        entry_id="ch-search",
        entry_type=EntryType.CHANNEL.value,
        display_name="Channel",
    )
    slang = _make_canonical_entry(
        entry_id="sl-search",
        entry_type=EntryType.SLANG.value,
        normalized_key="slang-key",
        display_name="Slang",
    )
    repo.save_canonical_entry(channel)
    repo.save_canonical_entry(slang)

    embedding_service = _FakeEmbeddingService()
    controller = _FakeController(intelligence_repository=repo, embedding_service=embedding_service)
    with _build_test_app(monkeypatch, controller) as client:
        response = client.get(
            "/intelligence/search?q=slang&entry_type=slang&tracking_scope=all",
            headers=_authorized_headers(),
        )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["results"][0]["entry_type"] == "slang"


def test_semantic_search_defaults_to_following_tracking_scope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _InMemoryIntelligenceRepository()
    followed_slang = _make_canonical_entry(
        entry_id="search-followed",
        entry_type=EntryType.SLANG.value,
        normalized_key="search-followed",
        display_name="Search Followed",
        tracking_enabled=True,
        confidence=0.9,
    )
    untracked_slang = _make_canonical_entry(
        entry_id="search-untracked",
        entry_type=EntryType.SLANG.value,
        normalized_key="search-untracked",
        display_name="Search Untracked",
        tracking_enabled=False,
        confidence=0.95,
    )
    untracked_channel = _make_canonical_entry(
        entry_id="search-channel",
        entry_type=EntryType.CHANNEL.value,
        normalized_key="search-channel",
        display_name="Search Channel",
        tracking_enabled=False,
        confidence=0.92,
    )
    repo.save_canonical_entry(followed_slang)
    repo.save_canonical_entry(untracked_slang)
    repo.save_canonical_entry(untracked_channel)

    controller = _FakeController(
        intelligence_repository=repo, embedding_service=_FakeEmbeddingService()
    )
    with _build_test_app(monkeypatch, controller) as client:
        default_response = client.get("/intelligence/search?q=slang", headers=_authorized_headers())
        discovery_response = client.get(
            "/intelligence/search?q=slang&tracking_scope=discovery",
            headers=_authorized_headers(),
        )

    assert default_response.status_code == 200
    assert [item["entry_id"] for item in default_response.json()["results"]] == [
        "search-channel",
        "search-followed",
    ]
    assert discovery_response.status_code == 200
    assert [item["entry_id"] for item in discovery_response.json()["results"]] == [
        "search-untracked"
    ]


def test_semantic_search_excludes_ignored_entries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _InMemoryIntelligenceRepository()

    visible = _make_canonical_entry(
        entry_id="entry-visible",
        display_name="Visible Entry",
        normalized_key="visible-entry",
        confidence=0.9,
    )
    ignored = _make_canonical_entry(
        entry_id="entry-ignored",
        display_name="Ignored Entry",
        normalized_key="ignored-entry",
        confidence=0.99,
    )
    repo.save_canonical_entry(visible)
    repo.save_canonical_entry(ignored)
    repo.ignore_canonical_entry(ignored.id)

    controller = _FakeController(
        intelligence_repository=repo, embedding_service=_FakeEmbeddingService()
    )
    with _build_test_app(monkeypatch, controller) as client:
        response = client.get(
            "/intelligence/search?q=GPT%20plus%E8%B4%AD%E4%B9%B0%E6%B8%A0%E9%81%93",
            headers=_authorized_headers(),
        )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert [item["entry_id"] for item in data["results"]] == ["entry-visible"]


def test_semantic_search_all_ignored_returns_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _InMemoryIntelligenceRepository()

    entry = _make_canonical_entry(
        entry_id="entry-ignored-only",
        display_name="Ignored Only",
        normalized_key="ignored-only",
    )
    repo.save_canonical_entry(entry)
    repo.ignore_canonical_entry(entry.id)

    controller = _FakeController(
        intelligence_repository=repo, embedding_service=_FakeEmbeddingService()
    )
    with _build_test_app(monkeypatch, controller) as client:
        response = client.get(
            "/intelligence/search?q=GPT%20plus%E8%B4%AD%E4%B9%B0%E6%B8%A0%E9%81%93",
            headers=_authorized_headers(),
        )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["results"] == []


def test_semantic_search_respects_hour_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _InMemoryIntelligenceRepository()
    recent = _make_canonical_entry(
        entry_id="recent-search",
        display_name="Recent",
        normalized_key="recent-search",
        last_seen_at=_utcnow() - timedelta(hours=1),
    )
    old = _make_canonical_entry(
        entry_id="old-search",
        display_name="Old",
        normalized_key="old-search",
        last_seen_at=_utcnow() - timedelta(days=2),
    )
    repo.save_canonical_entry(recent)
    repo.save_canonical_entry(old)

    controller = _FakeController(intelligence_repository=repo)
    with _build_test_app(monkeypatch, controller) as client:
        response = client.get(
            "/intelligence/search?q=channel&window=24h",
            headers=_authorized_headers(),
        )

    assert response.status_code == 200
    data = response.json()
    assert [item["entry_id"] for item in data["results"]] == ["recent-search"]


def test_semantic_search_missing_q_param_returns_422(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _InMemoryIntelligenceRepository()
    embedding_service = _FakeEmbeddingService()
    controller = _FakeController(intelligence_repository=repo, embedding_service=embedding_service)
    with _build_test_app(monkeypatch, controller) as client:
        response = client.get("/intelligence/search", headers=_authorized_headers())
    assert response.status_code == 422


# ──────────────────────────────────────────────────────────────────────
# Tests: GET /intelligence/raw/{raw_item_id}
# ──────────────────────────────────────────────────────────────────────


def test_get_raw_item_returns_full_details(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw_text = "Exact raw content with special characters: @#$%^"
    repo = _InMemoryIntelligenceRepository()

    published = _utcnow() - timedelta(hours=3)
    expires = _utcnow() + timedelta(days=27)
    raw_item = _make_raw_item(
        raw_item_id="raw-detail",
        raw_text=raw_text,
        source_type="v2ex",
        source_url="https://www.v2ex.com/t/12345",
        published_at=published,
        expires_at=expires,
    )
    repo.save_raw_item(raw_item)

    controller = _FakeController(intelligence_repository=repo)
    with _build_test_app(monkeypatch, controller) as client:
        response = client.get("/intelligence/raw/raw-detail", headers=_authorized_headers())

    assert response.status_code == 200
    data = response.json()
    assert data["raw_text"] == raw_text
    assert data["source_type"] == "v2ex"
    assert data["source_url"] == "https://www.v2ex.com/t/12345"
    assert data["is_expired"] is False
    assert data["published_at"] is not None
    assert data["expires_at"] is not None


def test_get_raw_item_expired_returns_null_raw_text_and_is_expired_true(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw_text = "Already expired content"
    repo = _InMemoryIntelligenceRepository()

    raw_item = _make_raw_item(
        raw_item_id="raw-expired",
        raw_text=raw_text,
        expires_at=_utcnow() - timedelta(days=1),
    )
    repo.save_raw_item(raw_item)

    controller = _FakeController(intelligence_repository=repo)
    with _build_test_app(monkeypatch, controller) as client:
        response = client.get("/intelligence/raw/raw-expired", headers=_authorized_headers())

    assert response.status_code == 200
    data = response.json()
    assert data["raw_text"] is None
    assert data["is_expired"] is True


def test_get_raw_item_not_found_returns_404(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _InMemoryIntelligenceRepository()
    controller = _FakeController(intelligence_repository=repo)
    with _build_test_app(monkeypatch, controller) as client:
        response = client.get("/intelligence/raw/nonexistent", headers=_authorized_headers())
    assert response.status_code == 404


# ──────────────────────────────────────────────────────────────────────
# Tests: Edge cases
# ──────────────────────────────────────────────────────────────────────


def test_list_entries_empty_repository_returns_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _InMemoryIntelligenceRepository()
    controller = _FakeController(intelligence_repository=repo)
    with _build_test_app(monkeypatch, controller) as client:
        response = client.get("/intelligence/entries", headers=_authorized_headers())

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["entries"] == []


def test_semantic_search_empty_repository_returns_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _InMemoryIntelligenceRepository()
    embedding_service = _FakeEmbeddingService()
    controller = _FakeController(intelligence_repository=repo, embedding_service=embedding_service)
    with _build_test_app(monkeypatch, controller) as client:
        response = client.get("/intelligence/search?q=nothing", headers=_authorized_headers())

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["results"] == []


def test_entries_endpoint_requires_intelligence_repository(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    controller = _FakeController(intelligence_repository=None)
    with _build_test_app(monkeypatch, controller) as client:
        response = client.get("/intelligence/entries", headers=_authorized_headers())
    assert response.status_code == 503


def test_raw_endpoint_requires_intelligence_repository(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    controller = _FakeController(intelligence_repository=None)
    with _build_test_app(monkeypatch, controller) as client:
        response = client.get("/intelligence/raw/raw-001", headers=_authorized_headers())
    assert response.status_code == 503
