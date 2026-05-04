from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock

from crypto_news_analyzer.domain.models import CanonicalIntelligenceEntry, RawIntelligenceItem
from crypto_news_analyzer.intelligence.pipeline import IntelligencePipeline


def _raw_item(content_hash, expires_at, raw_text="raw"):
    return RawIntelligenceItem.create(
        source_type="telegram_group",
        source_id="chat-1",
        raw_text=raw_text,
        content_hash=content_hash,
        expires_at=expires_at,
    )


class TTLRepository:
    def __init__(self):
        self.raw_items = [
            _raw_item("old", datetime.utcnow() - timedelta(days=1)),
            _raw_item("fresh", datetime.utcnow() + timedelta(days=1)),
        ]
        self.canonical_entries = [
            CanonicalIntelligenceEntry.create(
                entry_type="channel",
                normalized_key="alpha",
                display_name="Alpha",
            )
        ]

    def get_raw_items_expiring_before(self, cutoff_time):
        return [item for item in self.raw_items if item.expires_at < cutoff_time]

    def purge_raw_text_older_than(self, cutoff_time):
        purged = 0
        for item in self.raw_items:
            if item.expires_at < cutoff_time and item.raw_text:
                item.raw_text = None
                purged += 1
        return purged


def _pipeline(repository):
    extractor = Mock(config=SimpleNamespace(collection=SimpleNamespace(backfill_hours=24)))
    return IntelligencePipeline(
        data_source_factory=Mock(),
        intelligence_repository=repository,
        extractor=extractor,
        merge_engine=Mock(),
        search_service=Mock(),
    )


def test_ttl_cleanup_purges_only_expired_raw_text_and_keeps_canonical_entries():
    repository = TTLRepository()
    pipeline = _pipeline(repository)
    canonical_ids = [entry.id for entry in repository.canonical_entries]

    purged = pipeline._run_ttl_cleanup()

    assert purged == 1
    assert repository.raw_items[0].raw_text is None
    assert repository.raw_items[1].raw_text == "raw"
    assert [entry.id for entry in repository.canonical_entries] == canonical_ids


def test_ttl_cleanup_logs_purged_count(caplog):
    repository = TTLRepository()
    pipeline = _pipeline(repository)

    with caplog.at_level("INFO"):
        purged = pipeline._run_ttl_cleanup()

    assert purged == 1
    assert "Purged raw_text for 1 expired intelligence raw items" in caplog.text
