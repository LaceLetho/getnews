from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Optional
from unittest.mock import Mock

import pytest

from crypto_news_analyzer.crawlers.data_source_factory import get_data_source_factory
from crypto_news_analyzer.crawlers.telegram_intelligence_crawler import TelegramIntelligenceCrawler
from crypto_news_analyzer.domain.models import CheckpointStatus, IntelligenceCrawlCheckpoint


class FakeStringSession:
    def __init__(self, value):
        self.value = value


class FakeFloodWaitError(Exception):
    def __init__(self, seconds):
        self.seconds = seconds
        super().__init__(f"wait {seconds}")


class FakeAsyncMessages:
    def __init__(self, messages, error_after=None):
        self.messages = list(messages)
        self.error_after = error_after
        self.index = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.error_after is not None and self.index >= self.error_after:
            raise FakeFloodWaitError(17)
        if self.index >= len(self.messages):
            raise StopAsyncIteration
        message = self.messages[self.index]
        self.index += 1
        return message


class FakeTelegramClient:
    instances = []
    messages = []
    error_after: Optional[int] = None

    def __init__(self, session, api_id, api_hash):
        self.session = session
        self.api_id = api_id
        self.api_hash = api_hash
        self.iter_calls = []
        self.started = False
        self.disconnected = False
        self.list_dialogs = Mock(side_effect=AssertionError("must not enumerate dialogs"))
        FakeTelegramClient.instances.append(self)

    async def start(self):
        self.started = True

    def iter_messages(self, entity, **kwargs):
        self.iter_calls.append((entity, kwargs))
        return FakeAsyncMessages(FakeTelegramClient.messages, FakeTelegramClient.error_after)

    async def disconnect(self):
        self.disconnected = True


class MemoryCheckpointRepository:
    def __init__(self, checkpoint=None):
        self.checkpoint = checkpoint
        self.saved = []

    def get_checkpoint(self, source_type, source_id):
        assert source_type == "telegram_group"
        return self.checkpoint

    def save_checkpoint(self, checkpoint):
        self.saved.append(checkpoint)
        self.checkpoint = checkpoint


@pytest.fixture(autouse=True)
def reset_fake_client(monkeypatch):
    FakeTelegramClient.instances = []
    FakeTelegramClient.messages = []
    FakeTelegramClient.error_after = None
    monkeypatch.setenv("TELEGRAM_API_ID", "12345")
    monkeypatch.setenv("TELEGRAM_API_HASH", "hash-from-env")
    monkeypatch.setenv("TELEGRAM_STRING_SESSION", "session-from-env")
    monkeypatch.setattr(
        TelegramIntelligenceCrawler,
        "_load_telethon_modules",
        lambda self: (FakeTelegramClient, FakeStringSession, FakeFloodWaitError),
    )


def _message(message_id, text, published_at=None):
    return SimpleNamespace(
        id=message_id,
        message=text,
        date=published_at or datetime.utcnow() - timedelta(minutes=5),
    )


def test_first_run_fetches_only_configured_chat_with_24h_cutoff_and_preserves_raw_text():
    raw_text = "Alpha callout:  keep spacing & symbols 🚀\nunchanged"
    FakeTelegramClient.messages = [_message(41, raw_text)]
    repository = MemoryCheckpointRepository()
    crawler = TelegramIntelligenceCrawler(time_window_hours=24, intelligence_repository=repository)

    items = crawler.crawl({"name": "Alpha", "chat_username": "@alpha", "limit": 10})

    assert len(items) == 1
    assert items[0].source_type == "telegram_group"
    assert items[0].source_id == "@alpha"
    assert items[0].chat_id == "@alpha"
    assert items[0].external_id == "41"
    assert items[0].raw_text == raw_text
    assert items[0].expires_at > datetime.utcnow() + timedelta(days=29)

    client = FakeTelegramClient.instances[0]
    assert client.started is True
    assert client.disconnected is True
    assert client.iter_calls[0][0] == "@alpha"
    kwargs = client.iter_calls[0][1]
    assert kwargs["limit"] == 10
    assert "offset_date" not in kwargs
    client.list_dialogs.assert_not_called()

    assert repository.saved[-1].source_type == "telegram_group"
    assert repository.saved[-1].source_id == "@alpha"
    assert repository.saved[-1].last_external_id == "41"
    assert repository.saved[-1].status == CheckpointStatus.OK.value


def test_first_run_stops_when_messages_are_older_than_24h_cutoff():
    FakeTelegramClient.messages = [
        _message(42, "fresh", datetime.utcnow() - timedelta(hours=1)),
        _message(41, "old", datetime.utcnow() - timedelta(days=2)),
        _message(40, "older", datetime.utcnow() - timedelta(days=3)),
    ]
    repository = MemoryCheckpointRepository()
    crawler = TelegramIntelligenceCrawler(time_window_hours=24, intelligence_repository=repository)

    items = crawler.crawl({"name": "Alpha", "chat_username": "@alpha"})

    assert [item.raw_text for item in items] == ["fresh"]


def test_incremental_run_resumes_from_checkpoint_external_id():
    checkpoint = IntelligenceCrawlCheckpoint.create(
        source_type="telegram_group",
        source_id="-100123",
        last_crawled_at=datetime.utcnow() - timedelta(hours=1),
        last_external_id="100",
    )
    repository = MemoryCheckpointRepository(checkpoint)
    FakeTelegramClient.messages = [_message(101, "new message")]
    crawler = TelegramIntelligenceCrawler(time_window_hours=24, intelligence_repository=repository)

    items = crawler.crawl({"name": "Alpha", "chat_id": -100123})

    assert [item.external_id for item in items] == ["101"]
    client = FakeTelegramClient.instances[0]
    assert client.iter_calls[0][0] == -100123
    assert client.iter_calls[0][1]["min_id"] == 100
    assert "offset_date" not in client.iter_calls[0][1]
    assert repository.saved[-1].source_id == "-100123"
    assert repository.saved[-1].last_external_id == "101"


def test_flood_wait_returns_partial_results_and_marks_checkpoint_rate_limited():
    FakeTelegramClient.messages = [_message(7, "partial raw text"), _message(8, "not reached")]
    FakeTelegramClient.error_after = 1
    repository = MemoryCheckpointRepository()
    crawler = TelegramIntelligenceCrawler(time_window_hours=24, intelligence_repository=repository)

    items = crawler.crawl({"name": "Alpha", "chat_username": "@alpha"})

    assert [item.raw_text for item in items] == ["partial raw text"]
    saved = repository.saved[-1]
    assert saved.status == CheckpointStatus.RATE_LIMITED.value
    assert saved.last_external_id == "7"
    assert saved.error_message == "FloodWait: 17 seconds"


def test_validate_config_requires_explicit_chat_identifier():
    crawler = TelegramIntelligenceCrawler(time_window_hours=24)

    with pytest.raises(Exception, match="chat_id or chat_username"):
        crawler.validate_config({"name": "missing"})


def test_crawl_all_sources_reports_status_per_source():
    FakeTelegramClient.messages = [_message(1, "one")]
    repository = MemoryCheckpointRepository()
    crawler = TelegramIntelligenceCrawler(time_window_hours=24, intelligence_repository=repository)

    result = crawler.crawl_all_sources([{"name": "Alpha", "chat_username": "@alpha"}])

    assert result["total_items"] == 1
    assert result["results"] == [
        {"source_id": "@alpha", "status": CheckpointStatus.OK.value, "items_count": 1}
    ]


def test_factory_registers_telegram_group_source_type():
    factory = get_data_source_factory()

    assert factory.is_source_type_registered("telegram_group") is True
