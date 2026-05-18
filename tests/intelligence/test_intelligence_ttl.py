from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock

from crypto_news_analyzer.domain.models import RawIntelligenceItem
from crypto_news_analyzer.intelligence.pipeline import IntelligencePipeline


def _raw_item(content_hash, collected_at, raw_text="raw"):
    return RawIntelligenceItem.create(
        source_type="telegram_group",
        source_id="chat-1",
        raw_text=raw_text,
        content_hash=content_hash,
        expires_at=collected_at + timedelta(days=180),
    )


class TTLRepository:
    def __init__(self):
        now = datetime.utcnow()
        self.raw_items = [
            _raw_item("old", now - timedelta(days=181)),
            _raw_item("fresh", now - timedelta(days=179)),
        ]
        self.raw_items[0].collected_at = now - timedelta(days=181)
        self.raw_items[1].collected_at = now - timedelta(days=179)

    def get_raw_items_expiring_before(self, cutoff_time):
        return [item for item in self.raw_items if item.collected_at < cutoff_time]

    def purge_raw_text_older_than(self, cutoff_time):
        purged = 0
        for item in self.raw_items:
            if item.collected_at < cutoff_time and item.raw_text:
                item.raw_text = None
                purged += 1
        return purged


def _pipeline(repository):
    extractor = Mock(
        config=SimpleNamespace(
            collection=SimpleNamespace(backfill_hours=24, raw_message_retention_days=180)
        )
    )
    return IntelligencePipeline(
        data_source_factory=Mock(),
        intelligence_repository=repository,
        extractor=extractor,
        merge_engine=Mock(),
    )


def test_topic_retention_cleanup_purges_only_old_raw_text():
    repository = TTLRepository()
    pipeline = _pipeline(repository)

    purged = pipeline._run_ttl_cleanup()

    assert purged == 1
    assert repository.raw_items[0].raw_text is None
    assert repository.raw_items[1].raw_text == "raw"


def test_ttl_cleanup_logs_purged_count(caplog):
    repository = TTLRepository()
    pipeline = _pipeline(repository)

    with caplog.at_level("INFO"):
        purged = pipeline._run_ttl_cleanup()

    assert purged == 1
    assert "Purged raw_text for 1 retention-eligible intelligence raw items" in caplog.text
