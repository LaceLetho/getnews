from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock

from crypto_news_analyzer.config.manager import ConfigManager
from crypto_news_analyzer.domain.models import RawIntelligenceItem
from crypto_news_analyzer.intelligence.pipeline import IntelligencePipeline


def _raw_item(content_hash: str, collected_at: datetime, raw_text: str = "raw"):
    return RawIntelligenceItem(
        id=content_hash,
        source_type="telegram_group",
        source_id="chat-1",
        raw_text=raw_text,
        content_hash=content_hash,
        collected_at=collected_at,
        expires_at=collected_at + timedelta(days=30),
        created_at=collected_at,
    )


class RawRetentionRepository:
    def __init__(self, retention_days: int = 180):
        now = datetime.utcnow()
        self.raw_items = [
            _raw_item("old", now - timedelta(days=retention_days + 1), "old raw text"),
            _raw_item("fresh", now - timedelta(days=retention_days - 1), "fresh raw text"),
        ]
        self.findings = [
            {
                "id": "finding-1",
                "topic_id": "topic-btc-etf-flow",
                "summary": "ETF flow anomaly remains unresolved.",
                "source_refs": [
                    {
                        "raw_item_id": "old",
                        "source_id": "chat-1",
                        "snippet": "old raw text",
                    }
                ],
            }
        ]
        self.last_cutoff = None
        self.saved_items = []

    def save_raw_item(self, item):
        self.saved_items.append(item)

    def get_raw_items_expiring_before(self, cutoff_time):
        self.last_cutoff = cutoff_time
        return [item for item in self.raw_items if item.collected_at < cutoff_time]

    def purge_raw_text_older_than(self, cutoff_time):
        purged = 0
        for item in self.raw_items:
            if item.collected_at < cutoff_time and item.raw_text:
                item.raw_text = None
                purged += 1
        return purged


def _pipeline(repository, retention_days=180):
    extractor = Mock(
        config=SimpleNamespace(
            collection=SimpleNamespace(
                backfill_hours=24,
                raw_message_retention_days=retention_days,
            )
        )
    )
    return IntelligencePipeline(
        data_source_factory=Mock(),
        intelligence_repository=repository,
        extractor=extractor,
        merge_engine=Mock(),
        search_service=Mock(),
    )


def test_default_raw_message_retention_is_180_days_when_unconfigured():
    manager = ConfigManager(config_path="./nonexistent-config.jsonc")
    manager.config_data = {"intelligence_collection": {}}

    config = manager.get_intelligence_config()

    assert config.collection.raw_message_retention_days == 180
    assert config.collection.daily_topic_research_enabled is True
    assert config.collection.daily_topic_research_time_utc == "03:00"


def test_custom_raw_message_retention_value_is_read_from_config():
    manager = ConfigManager(config_path="./nonexistent-config.jsonc")
    manager.config_data = {
        "intelligence_collection": {
            "collection": {
                "raw_message_retention_days": 365,
                "daily_topic_research_enabled": True,
                "daily_topic_research_time_utc": "04:30",
            }
        }
    }

    config = manager.get_intelligence_config()

    assert config.collection.raw_message_retention_days == 365
    assert config.collection.daily_topic_research_time_utc == "04:30"


def test_retention_cleanup_preserves_finding_snippets_and_source_refs():
    repository = RawRetentionRepository()
    pipeline = _pipeline(repository)

    purged = pipeline._run_ttl_cleanup()

    assert purged == 1
    assert repository.raw_items[0].raw_text is None
    assert repository.findings == [
        {
            "id": "finding-1",
            "topic_id": "topic-btc-etf-flow",
            "summary": "ETF flow anomaly remains unresolved.",
            "source_refs": [
                {
                    "raw_item_id": "old",
                    "source_id": "chat-1",
                    "snippet": "old raw text",
                }
            ],
        }
    ]


def test_cleanup_eligibility_uses_collected_at_plus_retention_days():
    retention_days = 365
    repository = RawRetentionRepository(retention_days=retention_days)
    pipeline = _pipeline(repository, retention_days=retention_days)

    purged = pipeline._run_ttl_cleanup()

    assert purged == 1
    assert repository.last_cutoff is not None
    assert datetime.utcnow() - repository.last_cutoff >= timedelta(days=retention_days)
    assert repository.raw_items[0].raw_text is None
    assert repository.raw_items[1].raw_text == "fresh raw text"


def test_saved_raw_items_receive_retention_expires_at_from_collected_at():
    collected_at = datetime.utcnow() - timedelta(hours=2)
    item = _raw_item("new", collected_at)
    repository = RawRetentionRepository(retention_days=365)
    pipeline = _pipeline(repository, retention_days=365)

    pipeline._save_new_items([item])

    assert repository.saved_items == [item]
    assert item.expires_at == collected_at + timedelta(days=365)
