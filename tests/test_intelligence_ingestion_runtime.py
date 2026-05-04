from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock

from crypto_news_analyzer.domain.models import (
    CanonicalIntelligenceEntry,
    DataSource,
    ExtractionObservation,
    IngestionJob,
    RawIntelligenceItem,
)
from crypto_news_analyzer.execution_coordinator import MainController
from crypto_news_analyzer.intelligence.pipeline import IntelligencePipeline


def _raw(source_type="telegram_group", source_id="chat-1", content_hash="hash-1", external_id=None):
    return RawIntelligenceItem.create(
        source_type=source_type,
        source_id=source_id,
        external_id=external_id,
        raw_text=f"raw {content_hash}",
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

    def list(self, source_type=None):
        return [source for source in self.sources if source_type is None or source.source_type == source_type]


class MemoryIntelligenceRepository:
    def __init__(self, sources):
        self.datasource_repository = MemoryDataSourceRepository(sources)
        self.raw_items = {}
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
        IntelligencePipeline(FakeFactory(crawlers), repository, extractor, merge_engine, search_service),
        repository,
        extractor,
        merge_engine,
        search_service,
    )


def test_first_run_uses_24h_backfill_then_checkpoint_incremental_window():
    source = DataSource.create(
        name="TG Alpha",
        source_type="telegram_group",
        config_payload={"chat_id": "chat-1"},
    )
    item = _raw(content_hash="hash-1")
    pipeline, repository, *_ = _pipeline([source], [FakeCrawler([item]), FakeCrawler([])])

    first = pipeline.run_intelligence_collection_once()
    repository.checkpoints[("telegram_group", "chat-1")].last_crawled_at = datetime.utcnow() - timedelta(
        minutes=30
    )
    second = pipeline.run_intelligence_collection_once()

    assert first["items_new"] == 1
    assert second["items_new"] == 0
    assert pipeline.data_source_factory.calls[0][1] == 24
    assert pipeline.data_source_factory.calls[1][1] == 1


def test_per_source_error_isolated_and_other_sources_continue():
    bad = DataSource.create(name="bad", source_type="telegram_group", config_payload={"chat_id": "bad"})
    good = DataSource.create(name="good", source_type="v2ex", config_payload={"name": "crypto"})
    pipeline, _repository, extractor, _merge, _search = _pipeline(
        [bad, good],
        [FakeCrawler(error=RuntimeError("boom")), FakeCrawler([_raw("v2ex", "crypto", "hash-2")])],
    )

    result = pipeline.run_intelligence_collection_once()

    assert result["success"] is False
    assert len(result["errors"]) == 1
    assert result["items_new"] == 1
    extractor.extract.assert_called_once()


def test_repeated_run_with_same_raw_item_deduplicates_before_extraction():
    source = DataSource.create(
        name="TG Alpha",
        source_type="telegram_group",
        config_payload={"chat_id": "chat-1"},
    )
    item = _raw(content_hash="same")
    pipeline, _repository, extractor, _merge, _search = _pipeline(
        [source],
        [FakeCrawler([item]), FakeCrawler([item])],
    )

    pipeline.run_intelligence_collection_once()
    second = pipeline.run_intelligence_collection_once()

    assert second["items_new"] == 0
    assert extractor.extract.call_count == 1


def test_identical_text_with_different_external_ids_counts_as_new_evidence():
    source = DataSource.create(
        name="TG Alpha",
        source_type="telegram_group",
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


def test_pipeline_creates_related_candidates_after_embedding_search():
    source = DataSource.create(
        name="TG Alpha",
        source_type="telegram_group",
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
            return [(entry, 1.0), (related, 0.82)]

    pipeline = IntelligencePipeline(
        FakeFactory([FakeCrawler([_raw(content_hash="related", external_id="200")])]),
        repository,
        extractor,
        merge_engine,
        SearchService(),
    )

    pipeline.run_intelligence_collection_once()

    merge_engine.create_related_candidates.assert_called_once_with(entry, related, 0.82)


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
    controller.config_manager = SimpleNamespace(get_time_window_hours=lambda: 24)
    controller.ingestion_repository = FakeIngestionRepository()
    controller._history_file = str(tmp_path / "history.json")
    controller._intelligence_pipeline = Mock()
    controller._intelligence_pipeline.run_intelligence_collection_once.return_value = {"errors": []}
    monkeypatch.setattr(controller, "validate_prerequisites", lambda validation_scope: {"valid": True})
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
