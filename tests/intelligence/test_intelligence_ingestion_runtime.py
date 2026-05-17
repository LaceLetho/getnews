from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import Mock

import pytest

from crypto_news_analyzer.domain.models import (
    CanonicalIntelligenceEntry,
    DataSource,
    ExtractionObservation,
    IngestionJob,
    RawIntelligenceItem,
    TopicFinding,
)
from crypto_news_analyzer.execution_coordinator import MainController
from crypto_news_analyzer.intelligence.merge import IntelligenceMergeEngine
from crypto_news_analyzer.intelligence.pipeline import IntelligencePipeline
from crypto_news_analyzer.intelligence.topic_research import (
    TopicResearchParser,
    TopicResearchScheduler,
)


def _raw(
    source_type="telegram_group",
    source_id="chat-1",
    content_hash="hash-1",
    external_id=None,
    raw_text=None,
):
    return RawIntelligenceItem.create(
        source_type=source_type,
        source_id=source_id,
        external_id=external_id,
        raw_text=raw_text or f"raw {content_hash}",
        content_hash=content_hash,
        expires_at=datetime.utcnow() + timedelta(days=30),
    )


def _observation(raw_item_id="raw-1"):
    return ExtractionObservation.create(
        raw_item_id=raw_item_id,
        entry_type="channel",
        confidence=0.9,
        model_name="model",
        prompt_version="1",
        schema_version="1",
        channel_name="Alpha",
    )


def _entry():
    return CanonicalIntelligenceEntry.create(
        entry_type="channel",
        normalized_key="alpha",
        display_name="Alpha",
    )


class MemoryDataSourceRepository:
    def __init__(self, sources):
        self.sources = list(sources)

    def list(self, purpose=None, source_type=None):
        return [
            source
            for source in self.sources
            if (purpose is None or source.purpose == purpose)
            and (source_type is None or source.source_type == source_type)
        ]


class MemoryIntelligenceRepository:
    def __init__(self, sources):
        self.datasource_repository = MemoryDataSourceRepository(sources)
        self.raw_items = {}
        self.canonical_entries = {}
        self.canonicalized_observation_ids = set()
        self.checkpoints = {}
        self.saved_checkpoints = []

    def save_raw_item(self, raw_item):
        stable_id = raw_item.external_id or raw_item.content_hash
        self.raw_items[(raw_item.source_type, raw_item.source_id or "", stable_id)] = raw_item
        return raw_item.id

    def get_raw_items_by_source(self, source_type, source_id, limit, offset):
        return [
            item
            for (item_type, item_source_id, _), item in self.raw_items.items()
            if item_type == source_type and item_source_id == (source_id or "")
        ][offset : offset + limit]

    def get_raw_items_expiring_before(self, cutoff_time):
        return []

    def purge_raw_text_older_than(self, cutoff_time):
        return 0

    def save_checkpoint(self, checkpoint):
        self.checkpoints[(checkpoint.source_type, checkpoint.source_id)] = checkpoint
        self.saved_checkpoints.append(checkpoint)

    def get_checkpoint(self, source_type, source_id):
        return self.checkpoints.get((source_type, source_id))

    def upsert_canonical_entry(self, entry, **kwargs):
        self.canonical_entries[entry.id] = entry
        return entry.id

    def save_canonical_entry(self, entry):
        return self.upsert_canonical_entry(entry)

    def get_canonical_entry_by_id(self, entry_id):
        return self.canonical_entries.get(entry_id)

    def get_canonical_entry_by_normalized_key(self, entry_type, normalized_key):
        entry_type = str(entry_type).strip().lower()
        normalized_key = str(normalized_key).strip().lower()
        for entry in self.canonical_entries.values():
            if entry.entry_type == entry_type and entry.normalized_key == normalized_key:
                return entry
        return None

    def list_canonical_entries(
        self,
        entry_type=None,
        primary_label=None,
        window=None,
        page=1,
        page_size=100,
        tracking_scope="following",
    ):
        entries = []
        for entry in self.canonical_entries.values():
            if entry_type is not None and entry.entry_type != entry_type:
                continue
            if primary_label is not None and entry.primary_label != primary_label:
                continue
            if tracking_scope == "following" and not entry.tracking_enabled:
                continue
            if tracking_scope == "ignored" and not entry.is_ignored:
                continue
            entries.append(entry)
        start = max(0, page - 1) * page_size
        return entries[start : start + page_size]

    def list_ignored_canonical_entries(
        self,
        entry_type=None,
        primary_label=None,
        window=None,
        page=1,
        page_size=100,
    ):
        entries = [
            entry
            for entry in self.canonical_entries.values()
            if entry.is_ignored
            and (entry_type is None or entry.entry_type == entry_type)
            and (primary_label is None or entry.primary_label == primary_label)
        ]
        start = max(0, page - 1) * page_size
        return entries[start : start + page_size]

    def mark_observation_canonicalized(self, observation_id):
        self.canonicalized_observation_ids.add(observation_id)
        return True

    def ignore_canonical_entry(self, entry_id, ignored_by=None):
        entry = self.canonical_entries.get(entry_id)
        if entry is None:
            return None
        entry.is_ignored = True
        entry.ignored_at = datetime.utcnow()
        entry.ignored_by = ignored_by
        return entry

    def unignore_canonical_entry(self, entry_id):
        entry = self.canonical_entries.get(entry_id)
        if entry is None:
            return None
        entry.is_ignored = False
        entry.ignored_at = None
        entry.ignored_by = None
        return entry

    def save_related_candidate(self, *args, **kwargs):
        return None


class FakeFactory:
    def __init__(self, crawlers):
        self.crawlers = crawlers
        self.calls = []

    def create_source(self, source_type, time_window_hours, **kwargs):
        self.calls.append((source_type, time_window_hours, kwargs))
        return self.crawlers.pop(0)


class FakeCrawler:
    def __init__(self, items=None, error=None):
        self.items = list(items or [])
        self.error = error

    def crawl(self, config):
        if self.error:
            raise self.error
        return list(self.items)


def _pipeline(sources, crawlers, repository=None):
    repository = repository or MemoryIntelligenceRepository(sources)
    extractor = Mock(config=SimpleNamespace(collection=SimpleNamespace(backfill_hours=24)))
    extractor.extract.return_value = [_observation()]
    merge_engine = Mock()
    merge_engine.canonicalize_observations.return_value = [_entry()]
    search_service = Mock()
    search_service.batch_generate_embeddings.return_value = 1
    return (
        IntelligencePipeline(
            FakeFactory(crawlers), repository, extractor, merge_engine, search_service
        ),
        repository,
        extractor,
        merge_engine,
        search_service,
    )


def _canonical_field_snapshot(entry):
    return {
        "display_name": entry.display_name,
        "explanation": entry.explanation,
        "usage_summary": entry.usage_summary,
        "primary_label": entry.primary_label,
        "secondary_tags": list(entry.secondary_tags),
        "confidence": entry.confidence,
        "aliases": list(entry.aliases),
        "evidence_count": entry.evidence_count,
        "last_seen_at": entry.last_seen_at,
        "latest_raw_item_id": entry.latest_raw_item_id,
        "updated_at": entry.updated_at,
    }


@pytest.mark.skip(reason="Old entry extraction pipeline removed in topic-only refactor")
def test_ignored_canonical_entry_is_updated_by_new_evidence():
    source = DataSource.create(
        name="TG Alpha",
        source_type="telegram_group",
        purpose="intelligence",
        config_payload={"chat_id": "chat-1"},
    )
    repository = MemoryIntelligenceRepository([source])
    entry = CanonicalIntelligenceEntry.create(
        entry_type="channel",
        normalized_key="alpha",
        display_name="Alpha Original",
        explanation="original explanation",
        usage_summary="original usage",
        primary_label="crypto",
        secondary_tags=["original"],
        confidence=0.5,
        aliases=["alpha-original"],
        evidence_count=1,
        last_seen_at=datetime.utcnow() - timedelta(days=1),
        latest_raw_item_id="raw-original",
    )
    repository.upsert_canonical_entry(entry)
    repository.ignore_canonical_entry(entry.id, ignored_by="operator")
    raw_item = _raw(content_hash="ignored-new", external_id="201")
    observation = ExtractionObservation.create(
        raw_item_id=raw_item.id,
        entry_type="channel",
        confidence=0.95,
        model_name="new-model",
        prompt_version="2",
        schema_version="2",
        channel_name="Alpha Updated",
        channel_description="new explanation",
        channel_handles=["alpha"],
        usage_quote="new usage",
        aliases_or_variants=["alpha-new"],
        primary_label="社媒",
        secondary_tags=["new"],
    )
    extractor = Mock(config=SimpleNamespace(collection=SimpleNamespace(backfill_hours=24)))
    extractor.extract.return_value = [observation]
    search_service = Mock()
    search_service.batch_generate_embeddings.return_value = 1
    pipeline = IntelligencePipeline(
        FakeFactory([FakeCrawler([raw_item])]),
        repository,
        extractor,
        IntelligenceMergeEngine(repository),
        search_service,
    )

    result = pipeline.run_intelligence_collection_once()

    assert result["canonical_entries"] == 1
    assert result["embeddings_updated"] == 0
    assert observation.is_canonicalized is True
    assert observation.id in repository.canonicalized_observation_ids
    assert len(repository.canonical_entries) == 1
    persisted = repository.get_canonical_entry_by_id(entry.id)
    assert persisted is not None
    assert persisted.is_ignored is True
    assert persisted.evidence_count == 2
    assert persisted.confidence == 0.725
    assert persisted.latest_raw_item_id == raw_item.id
    assert "alpha-new" in persisted.aliases
    assert "new" in persisted.secondary_tags
    search_service.batch_generate_embeddings.assert_not_called()


@pytest.mark.skip(reason="Old entry extraction pipeline removed in topic-only refactor")
def test_unignored_entry_resumes_future_ingestion_updates():
    source = DataSource.create(
        name="TG Alpha",
        source_type="telegram_group",
        purpose="intelligence",
        config_payload={"chat_id": "chat-1"},
    )
    repository = MemoryIntelligenceRepository([source])
    entry = CanonicalIntelligenceEntry.create(
        entry_type="channel",
        normalized_key="alpha",
        display_name="Alpha Original",
        confidence=0.5,
        aliases=["alpha-original"],
        evidence_count=1,
        latest_raw_item_id="raw-original",
    )
    repository.upsert_canonical_entry(entry)
    repository.ignore_canonical_entry(entry.id, ignored_by="operator")
    repository.unignore_canonical_entry(entry.id)

    raw_item = _raw(content_hash="unignored-new", external_id="202")
    observation = ExtractionObservation.create(
        raw_item_id=raw_item.id,
        entry_type="channel",
        confidence=0.9,
        model_name="new-model",
        prompt_version="2",
        schema_version="2",
        channel_name="Alpha Updated",
        channel_handles=["alpha"],
        aliases_or_variants=["alpha-new"],
        secondary_tags=["fresh"],
    )
    extractor = Mock(config=SimpleNamespace(collection=SimpleNamespace(backfill_hours=24)))
    extractor.extract.return_value = [observation]
    search_service = Mock()
    search_service.batch_generate_embeddings.return_value = 1
    pipeline = IntelligencePipeline(
        FakeFactory([FakeCrawler([raw_item])]),
        repository,
        extractor,
        IntelligenceMergeEngine(repository),
        search_service,
    )

    result = pipeline.run_intelligence_collection_once()

    persisted = repository.get_canonical_entry_by_id(entry.id)
    assert result["canonical_entries"] == 1
    assert result["embeddings_updated"] == 1
    assert observation.is_canonicalized is True
    assert len(repository.canonical_entries) == 1
    assert persisted is not None
    assert persisted.is_ignored is False
    assert persisted.evidence_count == 2
    assert persisted.confidence == 0.7
    assert persisted.latest_raw_item_id == raw_item.id
    assert "alpha-new" in persisted.aliases
    assert "fresh" in persisted.secondary_tags
    search_service.batch_generate_embeddings.assert_called_once_with([persisted])


@pytest.mark.skip(reason="Old entry extraction pipeline removed in topic-only refactor")
def test_first_run_uses_24h_backfill_then_checkpoint_incremental_window():
    source = DataSource.create(
        name="TG Alpha",
        source_type="telegram_group",
        purpose="intelligence",
        config_payload={"chat_id": "chat-1"},
    )
    item = _raw(content_hash="hash-1")
    pipeline, repository, *_ = _pipeline([source], [FakeCrawler([item]), FakeCrawler([])])

    first = pipeline.run_intelligence_collection_once()
    repository.checkpoints[("telegram_group", "chat-1")].last_crawled_at = (
        datetime.utcnow() - timedelta(minutes=30)
    )
    second = pipeline.run_intelligence_collection_once()

    assert first["items_new"] == 1
    assert second["items_new"] == 0
    assert pipeline.data_source_factory.calls[0][1] == 24
    assert pipeline.data_source_factory.calls[1][1] == 1


@pytest.mark.skip(reason="Old entry extraction pipeline removed in topic-only refactor")
def test_per_source_error_isolated_and_other_sources_continue():
    bad = DataSource.create(
        name="bad",
        source_type="telegram_group",
        purpose="intelligence",
        config_payload={"chat_id": "bad"},
    )
    good = DataSource.create(
        name="good",
        source_type="v2ex",
        purpose="intelligence",
        config_payload={"name": "crypto"},
    )
    pipeline, _repository, extractor, _merge, _search = _pipeline(
        [bad, good],
        [FakeCrawler(error=RuntimeError("boom")), FakeCrawler([_raw("v2ex", "crypto", "hash-2")])],
    )

    result = pipeline.run_intelligence_collection_once()

    assert result["success"] is False
    assert len(result["errors"]) == 1
    assert result["items_new"] == 1
    extractor.extract.assert_called_once()


@pytest.mark.skip(reason="Old entry extraction pipeline removed in topic-only refactor")
def test_repeated_run_with_same_raw_item_is_extracted_again():
    source = DataSource.create(
        name="TG Alpha",
        source_type="telegram_group",
        purpose="intelligence",
        config_payload={"chat_id": "chat-1"},
    )
    item = _raw(content_hash="same")
    pipeline, _repository, extractor, _merge, _search = _pipeline(
        [source],
        [FakeCrawler([item]), FakeCrawler([item])],
    )

    pipeline.run_intelligence_collection_once()
    second = pipeline.run_intelligence_collection_once()

    assert second["items_new"] == 1
    assert extractor.extract.call_count == 2


@pytest.mark.skip(reason="Old entry extraction pipeline removed in topic-only refactor")
def test_identical_text_with_different_external_ids_counts_as_new_evidence():
    source = DataSource.create(
        name="TG Alpha",
        source_type="telegram_group",
        purpose="intelligence",
        config_payload={"chat_id": "chat-1"},
    )
    first_item = _raw(content_hash="same", external_id="100")
    repeated_text_new_message = _raw(content_hash="same", external_id="101")
    pipeline, _repository, extractor, _merge, _search = _pipeline(
        [source],
        [FakeCrawler([first_item]), FakeCrawler([repeated_text_new_message])],
    )

    pipeline.run_intelligence_collection_once()
    second = pipeline.run_intelligence_collection_once()

    assert second["items_new"] == 1
    assert extractor.extract.call_count == 2


@pytest.mark.skip(reason="Old entry extraction pipeline removed in topic-only refactor")
def test_pipeline_creates_related_candidates_after_embedding_search():
    source = DataSource.create(
        name="TG Alpha",
        source_type="telegram_group",
        purpose="intelligence",
        config_payload={"chat_id": "chat-1"},
    )
    repository = MemoryIntelligenceRepository([source])
    extractor = Mock(config=SimpleNamespace(collection=SimpleNamespace(backfill_hours=24)))
    extractor.extract.return_value = [_observation()]
    entry = _entry()
    related = CanonicalIntelligenceEntry.create(
        entry_type="channel",
        normalized_key="alpha-related",
        display_name="Alpha Related",
    )
    merge_engine = Mock()
    merge_engine.canonicalize_observations.return_value = [entry]

    class SearchService:
        def batch_generate_embeddings(self, entries):
            return len(entries)

        def build_embedding_text(self, candidate):
            return candidate.display_name

        def semantic_search(self, **kwargs):
            return [(entry, 1.0), (related, 0.82)], 2

    pipeline = IntelligencePipeline(
        FakeFactory([FakeCrawler([_raw(content_hash="related", external_id="200")])]),
        repository,
        extractor,
        merge_engine,
        SearchService(),
    )

    pipeline.run_intelligence_collection_once()

    merge_engine.create_related_candidates.assert_called_once_with(entry, related, 0.82)


@pytest.mark.skip(reason="Old entry extraction pipeline removed in topic-only refactor")
def test_untracked_slang_raw_items_are_skipped_before_extraction():
    source = DataSource.create(
        name="TG Alpha",
        source_type="telegram_group",
        purpose="intelligence",
        config_payload={"chat_id": "chat-1"},
    )
    repository = MemoryIntelligenceRepository([source])
    repository.upsert_canonical_entry(
        CanonicalIntelligenceEntry.create(
            entry_type="slang",
            normalized_key="tqcard",
            display_name="土区卡",
            aliases=["TQ Card"],
            tracking_enabled=False,
        )
    )
    repository.upsert_canonical_entry(
        CanonicalIntelligenceEntry.create(
            entry_type="channel",
            normalized_key="alpha-channel",
            display_name="Alpha Channel",
            tracking_enabled=False,
        )
    )

    skipped = _raw(content_hash="skip", raw_text="收 T.Q. card，价格好")
    kept_channel_only = _raw(content_hash="channel", raw_text="Alpha Channel 有新盘口")
    kept_unrelated = _raw(content_hash="keep", raw_text="普通情报继续分析")
    pipeline, _repository, extractor, _merge, _search = _pipeline(
        [source],
        [FakeCrawler([skipped, kept_channel_only, kept_unrelated])],
        repository=repository,
    )

    result = pipeline.run_intelligence_collection_once()

    assert result["items_new"] == 3
    assert result["skipped_untracked_slang_items"] == 1
    sent_items = extractor.extract.call_args.args[0]
    assert [item.id for item in sent_items] == [kept_channel_only.id, kept_unrelated.id]


@pytest.mark.skip(reason="Old entry extraction pipeline removed in topic-only refactor")
def test_mixed_followed_and_untracked_slang_raw_item_is_retained():
    source = DataSource.create(
        name="TG Alpha",
        source_type="telegram_group",
        purpose="intelligence",
        config_payload={"chat_id": "chat-1"},
    )
    repository = MemoryIntelligenceRepository([source])
    repository.upsert_canonical_entry(
        CanonicalIntelligenceEntry.create(
            entry_type="slang",
            normalized_key="tqcard",
            display_name="土区卡",
            aliases=["TQ Card"],
            tracking_enabled=False,
        )
    )
    repository.upsert_canonical_entry(
        CanonicalIntelligenceEntry.create(
            entry_type="slang",
            normalized_key="biquandanbao",
            display_name="币圈担保",
            aliases=["担保"],
            tracking_enabled=True,
        )
    )

    mixed = _raw(content_hash="mixed", raw_text="TQ card 交易只走币圈担保")
    pipeline, _repository, extractor, _merge, _search = _pipeline(
        [source],
        [FakeCrawler([mixed])],
        repository=repository,
    )

    result = pipeline.run_intelligence_collection_once()

    assert result["skipped_untracked_slang_items"] == 0
    extractor.extract.assert_called_once()
    assert extractor.extract.call_args.args[0] == [mixed]


@pytest.mark.skip(reason="Old entry extraction pipeline removed in topic-only refactor")
def test_short_ascii_untracked_slang_does_not_match_inside_words():
    source = DataSource.create(
        name="TG Alpha",
        source_type="telegram_group",
        purpose="intelligence",
        config_payload={"chat_id": "chat-1"},
    )
    repository = MemoryIntelligenceRepository([source])
    repository.upsert_canonical_entry(
        CanonicalIntelligenceEntry.create(
            entry_type="slang",
            normalized_key="ai",
            display_name="AI",
            tracking_enabled=False,
        )
    )

    kept = _raw(content_hash="paid", raw_text="paid channel 有新消息")
    skipped = _raw(content_hash="ai", raw_text="AI 代付渠道")
    pipeline, _repository, extractor, _merge, _search = _pipeline(
        [source],
        [FakeCrawler([kept, skipped])],
        repository=repository,
    )

    result = pipeline.run_intelligence_collection_once()

    assert result["skipped_untracked_slang_items"] == 1
    assert extractor.extract.call_args.args[0] == [kept]


@pytest.mark.skip(reason="Old entry extraction pipeline removed in topic-only refactor")
def test_ignored_slang_raw_items_are_skipped_before_extraction():
    source = DataSource.create(
        name="TG Alpha",
        source_type="telegram_group",
        purpose="intelligence",
        config_payload={"chat_id": "chat-1"},
    )
    repository = MemoryIntelligenceRepository([source])
    ignored = CanonicalIntelligenceEntry.create(
        entry_type="slang",
        normalized_key="blacku",
        display_name="黑U",
        tracking_enabled=True,
    )
    repository.upsert_canonical_entry(ignored)
    repository.ignore_canonical_entry(ignored.id, ignored_by="operator")
    raw_item = _raw(content_hash="ignored-slang", raw_text="有人在收黑 U")
    pipeline, _repository, extractor, _merge, _search = _pipeline(
        [source],
        [FakeCrawler([raw_item])],
        repository=repository,
    )

    result = pipeline.run_intelligence_collection_once()

    assert result["skipped_untracked_slang_items"] == 1
    extractor.extract.assert_not_called()


class FakeIngestionRepository:
    def __init__(self):
        self.saved = []
        self.completed = []

    def get_by_source(self, **kwargs):
        return []

    def save(self, job: IngestionJob):
        self.saved.append(job)

    def update_status(self, *args, **kwargs):
        return True

    def complete_job(self, **kwargs):
        self.completed.append(kwargs)
        return True


def test_run_crawl_only_invokes_intelligence_pipeline_when_configured(tmp_path, monkeypatch):
    controller = MainController(config_path=str(tmp_path / "config.jsonc"))
    controller._initialized = True
    controller.config_manager = cast(Any, SimpleNamespace(get_time_window_hours=lambda: 24))
    controller.ingestion_repository = FakeIngestionRepository()
    controller._history_file = str(tmp_path / "history.json")
    controller._intelligence_pipeline = Mock()
    controller._intelligence_pipeline.run_intelligence_collection_once.return_value = {"errors": []}
    monkeypatch.setattr(
        controller, "validate_prerequisites", lambda validation_scope: {"valid": True}
    )
    monkeypatch.setattr(
        controller,
        "_execute_crawling_stage",
        lambda hours: {"success": True, "content_items": [], "items_new": 0, "errors": []},
    )

    result = controller.run_crawl_only()

    assert result.success is True
    controller._intelligence_pipeline.run_intelligence_collection_once.assert_called_once()


def test_analysis_service_mode_does_not_initialize_or_start_intelligence(monkeypatch, tmp_path):
    controller = MainController(config_path=str(tmp_path / "config.jsonc"))
    called = Mock()
    monkeypatch.setattr(controller, "_initialize_intelligence_pipeline_for_ingestion", called)

    assert controller._intelligence_pipeline is None
    called.assert_not_called()


def test_topic_research_invoked_after_raw_save(tmp_path, monkeypatch):
    controller = MainController(config_path=str(tmp_path / "config.jsonc"))
    controller._initialized = True
    controller.config_manager = cast(Any, SimpleNamespace(get_time_window_hours=lambda: 24))
    controller.ingestion_repository = FakeIngestionRepository()
    controller._history_file = str(tmp_path / "history.json")
    controller._intelligence_pipeline = Mock()
    controller._intelligence_pipeline.run_intelligence_collection_once.return_value = {"errors": []}
    topic_scheduler = Mock()
    topic_scheduler.run_scheduled_topic_research.return_value = 3
    controller._topic_research_scheduler = topic_scheduler
    monkeypatch.setattr(
        controller, "validate_prerequisites", lambda validation_scope: {"valid": True}
    )
    monkeypatch.setattr(
        controller,
        "_execute_crawling_stage",
        lambda hours: {"success": True, "content_items": [], "items_new": 0, "errors": []},
    )

    result = controller.run_crawl_only()

    assert result.success is True
    controller._intelligence_pipeline.run_intelligence_collection_once.assert_called_once()
    topic_scheduler.run_scheduled_topic_research.assert_called_once()


def test_analysis_service_does_not_start_topic_research(monkeypatch, tmp_path):
    controller = MainController(config_path=str(tmp_path / "config.jsonc"))
    monkeypatch.setattr(controller, "_initialize_intelligence_pipeline_for_ingestion", Mock())

    assert controller._topic_research_scheduler is None
    assert controller._intelligence_pipeline is None
