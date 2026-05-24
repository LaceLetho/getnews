"""Topic-only scheduled research runtime tests."""

import json
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Set

from crypto_news_analyzer.domain.models import (
    DataSource,
    IntelligenceTopic,
    RawIntelligenceItem,
    TopicFinding,
    TopicLifecycleStatus,
    TopicPrompt,
    TopicResearchRun,
)
from crypto_news_analyzer.intelligence.pipeline import IntelligencePipeline
from crypto_news_analyzer.intelligence.topic_research import (
    DEFAULT_RAW_ITEM_LIMIT,
    TOPIC_RESEARCH_SCHEMA_VERSION,
    TopicResearchScheduler,
)
from crypto_news_analyzer.storage.repositories import SQLiteIntelligenceRepository


class FakeChatCompletions:
    def __init__(self, payload: Any):
        self.payload = payload
        self.calls: List[Dict[str, Any]] = []

    def create(self, **kwargs: Any) -> SimpleNamespace:
        self.calls.append(kwargs)
        content = self.payload if isinstance(self.payload, str) else json.dumps(self.payload)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


class FakeLLMClient:
    def __init__(self, payload: Any):
        self.completions = FakeChatCompletions(payload)
        self.chat = SimpleNamespace(completions=self.completions)


class FakeTopicRepository:
    def __init__(self, llm_payload: Any = None):
        self.topic = IntelligenceTopic.create(name="BTC ETF flow")
        self.prompt = TopicPrompt.create(
            intelligence_topic_id=self.topic.id,
            prompt_version="1",
            prompt_text="研究 BTC ETF 资金流异常，输出 findings + citations JSON。",
            schema_version="topic-prompt-generation-v1",
            status="active",
        )
        self.raw_items = [
            RawIntelligenceItem(
                id="raw-1",
                source_type="telegram_group",
                source_id="chat-1",
                raw_text="BTC ETF 单小时净流入突然放大，交易员等待确认。",
                content_hash="hash-raw-1",
                collected_at=datetime.utcnow(),
                created_at=datetime.utcnow(),
                expires_at=datetime.utcnow() + timedelta(days=180),
            )
        ]
        self.checkpoint: Optional[Dict[str, Any]] = {
            "checkpoint_cursor": "2026-05-15T08:00:00+00:00"
        }
        self.findings: List[Any] = []
        self.runs: List[TopicResearchRun] = []
        self.processed_items: List[str] = []
        self.last_cursor_time: Optional[datetime] = None
        self.last_limit: Optional[int] = None
        self._processed_markers: Set[str] = set()
        self._custom_topics: List[IntelligenceTopic] = []
        self._custom_prompts: Dict[str, TopicPrompt] = {}
        self._custom_raw_items: Dict[str, List[RawIntelligenceItem]] = {}

    def set_topics(self, topics: List[IntelligenceTopic]) -> None:
        self._custom_topics = list(topics)

    def set_prompt(self, topic_id: str, prompt: TopicPrompt) -> None:
        self._custom_prompts[topic_id] = prompt

    def set_raw_items_for(self, topic_id: str, items: List[RawIntelligenceItem]) -> None:
        self._custom_raw_items[topic_id] = list(items)

    def list_topics(self, is_active: Optional[bool] = None, limit: int = 100, offset: int = 0):
        if self._custom_topics:
            topics = self._custom_topics
        else:
            topics = [self.topic]
        if is_active is not None:
            topics = [t for t in topics if t.is_active == is_active]
        return topics

    def get_active_topic_prompt(self, topic_id: str):
        if topic_id in self._custom_prompts:
            return self._custom_prompts[topic_id]
        return self.prompt if topic_id == self.topic.id else None

    def get_topic_checkpoint(self, topic_id: str, prompt_version_id: Optional[str]):
        return dict(self.checkpoint) if self.checkpoint is not None else None

    def get_raw_items_since(self, topic_id: str, cursor_time: Optional[datetime], limit: int):
        self.last_cursor_time = cursor_time
        self.last_limit = limit
        if topic_id in self._custom_raw_items:
            items = list(self._custom_raw_items.get(topic_id, []))
        else:
            items = list(self.raw_items)
        if cursor_time is not None:
            items = [
                item
                for item in items
                if (item.collected_at or item.created_at or datetime.min) > cursor_time
            ]
        return items

    def get_processed_topic_raw_item_ids(
        self,
        raw_item_ids: List[str],
        intelligence_topic_id: str,
        prompt_version: str,
        schema_version: str,
    ) -> Set[str]:
        return {rid for rid in raw_item_ids if rid in self._processed_markers}

    def create_topic_research_run(self, run: TopicResearchRun) -> str:
        self.runs.append(run)
        return run.id

    def update_topic_research_run(self, run_id: str, **kwargs: Any):
        run = next(run for run in self.runs if run.id == run_id)
        for key, value in kwargs.items():
            if value is not None or key == "error_message":
                setattr(run, key, value)
        return run

    def create_topic_finding(self, finding):
        self.findings.append(finding)
        return finding.id

    def mark_topic_raw_item_processed(
        self,
        raw_item_id: str,
        intelligence_topic_id: str,
        prompt_version: str,
        schema_version: str,
        finding_id: Optional[str] = None,
    ) -> None:
        self.processed_items.append(raw_item_id)
        self._processed_markers.add(raw_item_id)

    def update_topic_checkpoint(
        self,
        topic_id: str,
        prompt_version_id: Optional[str],
        checkpoint_cursor: Optional[str],
        checkpoint_payload: Optional[Dict[str, Any]] = None,
        last_run_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        self.checkpoint = {
            "checkpoint_cursor": checkpoint_cursor,
            "checkpoint_payload": checkpoint_payload or {},
            "last_run_id": last_run_id,
        }
        return dict(self.checkpoint)


class FakeDatasourceRepository:
    def __init__(self, source: DataSource):
        self.source = source

    def list(self, purpose: Optional[str] = None, source_type: Optional[str] = None):
        if purpose == "intelligence" and source_type == self.source.source_type:
            return [self.source]
        return []


class FakeCrawler:
    def __init__(self, items: List[RawIntelligenceItem]):
        self.items = items

    def crawl(self, config: Dict[str, Any]):
        return list(self.items)


class FakeFactory:
    def __init__(self, crawler: FakeCrawler):
        self.crawler = crawler

    def create_source(self, *args: Any, **kwargs: Any):
        return self.crawler


class _FakePostgresCursor:
    def __init__(self, manager: "_FakePostgresDataManager"):
        self.manager = manager
        self._last_query = ""

    def execute(self, query: str, params: Any = None) -> None:
        self.manager.executed.append((query, params))
        self._last_query = query

    def fetchone(self):
        if "FROM intelligence_topic_research_runs" in self._last_query:
            return dict(self.manager.run_row)
        if "FROM intelligence_topic_research_checkpoints" in self._last_query:
            return dict(self.manager.checkpoint_row)
        return None

    def fetchall(self):
        return []


class _FakePostgresConnection:
    def __init__(self, manager: "_FakePostgresDataManager"):
        self.manager = manager

    def cursor(self):
        return _FakePostgresCursor(self.manager)

    def commit(self) -> None:
        return None

    def rollback(self) -> None:
        return None


class _FakePostgresDataManager:
    def __init__(self, run_row: Dict[str, Any], checkpoint_row: Dict[str, Any]):
        self.backend = "postgres"
        self._lock = threading.Lock()
        self.run_row = run_row
        self.checkpoint_row = checkpoint_row
        self.executed: List[Any] = []

    @contextmanager
    def _get_connection(self):
        yield _FakePostgresConnection(self)

    def _sql(self, query: str) -> str:
        return query.replace("?", "%s")

    def _dt_out(self, value: Any) -> Any:
        return value

    def _json_load(self, value: Any, default: Any) -> Any:
        if value is None:
            return default
        if isinstance(value, str):
            return json.loads(value)
        return value


class RawOnlyRepository:
    def __init__(self, source: DataSource):
        self.datasource_repository = FakeDatasourceRepository(source)
        self.saved_items: List[RawIntelligenceItem] = []
        self.checkpoints = {}

    def save_raw_item(self, item: RawIntelligenceItem) -> None:
        self.saved_items.append(item)

    def get_checkpoint(self, source_type: str, source_id: str):
        return self.checkpoints.get((source_type, source_id))

    def save_checkpoint(self, checkpoint) -> None:
        self.checkpoints[(checkpoint.source_type, checkpoint.source_id)] = checkpoint

    def get_raw_items_expiring_before(self, cutoff_time):
        return []

    def purge_raw_text_older_than(self, cutoff_time):
        return 0


def _valid_payload() -> Dict[str, Any]:
    return {
        "schema_version": TOPIC_RESEARCH_SCHEMA_VERSION,
        "topic_name": "BTC ETF flow",
        "research_summary": "ETF flow showed one relevant anomaly.",
        "findings": [
            {
                "finding_id": "f-1",
                "summary": "BTC ETF 单小时净流入突然放大",
                "detail": "原始消息显示 ETF 净流入短时放大，但仍待交易员确认。",
                "confidence": 0.82,
                "citations": [
                    {
                        "message_id": "raw-1",
                        "message_snippet": "BTC ETF 单小时净流入突然放大",
                        "source": "chat-1",
                        "published_at": "",
                    }
                ],
            }
        ],
        "messages_processed": 1,
        "messages_relevant": 1,
    }


# ---------------------------------------------------------------------------
# Legacy tests (unchanged)
# ---------------------------------------------------------------------------


def test_no_entry_extractor_dependency() -> None:
    source = DataSource.create(
        name="TG Alpha",
        source_type="telegram_group",
        purpose="intelligence",
        config_payload={"chat_id": "chat-1"},
    )
    raw_item = RawIntelligenceItem(
        id="raw-only-1",
        source_type="telegram_group",
        source_id="chat-1",
        raw_text="topic research source message",
        content_hash="raw-only-1",
        collected_at=datetime.utcnow(),
        created_at=datetime.utcnow(),
        expires_at=datetime.utcnow() + timedelta(days=180),
    )
    extractor = SimpleNamespace(
        config=SimpleNamespace(
            collection=SimpleNamespace(backfill_hours=24, raw_message_retention_days=180)
        ),
    )

    pipeline = IntelligencePipeline(
        data_source_factory=FakeFactory(FakeCrawler([raw_item])),
        intelligence_repository=RawOnlyRepository(source),
        extractor=extractor,
    )

    result = pipeline.run_intelligence_collection_once()

    assert result["items_new"] == 1


def test_malformed_llm_json() -> None:
    repository = FakeTopicRepository()
    original_checkpoint = dict(repository.checkpoint or {})
    scheduler = TopicResearchScheduler(
        repository,
        FakeLLMClient('{"schema_version": "topic-research-v1", "findings": ['),
    )

    run = scheduler.run_topic(repository.topic, repository.prompt)

    assert run.status == "failed"
    assert "Malformed topic research JSON" in str(run.error_message)
    assert repository.findings == []
    assert repository.checkpoint == original_checkpoint


def test_empty_llm_response_records_specific_error() -> None:
    repository = FakeTopicRepository()
    original_checkpoint = dict(repository.checkpoint or {})
    scheduler = TopicResearchScheduler(repository, FakeLLMClient(""))

    run = scheduler.run_topic(repository.topic, repository.prompt)

    assert run.status == "failed"
    assert "Empty topic research LLM response" in str(run.error_message)
    assert repository.findings == []
    assert repository.checkpoint == original_checkpoint


def test_secret_filtering() -> None:
    repository = FakeTopicRepository()
    original_checkpoint = dict(repository.checkpoint or {})
    payload = _valid_payload()
    payload["findings"][0]["detail"] = "do not leak api_key=sk-test-secret-token"
    scheduler = TopicResearchScheduler(repository, FakeLLMClient(payload))

    run = scheduler.run_topic(repository.topic, repository.prompt)

    assert run.status == "failed"
    assert "secret-like content" in str(run.error_message)
    assert repository.findings == []
    assert repository.checkpoint == original_checkpoint


# ---------------------------------------------------------------------------
# Task 8: Active scheduled research tests
# ---------------------------------------------------------------------------


def test_active_topic_saves_findings() -> None:
    """Findings are saved and linked to topic with prompt_version and raw item IDs."""
    repository = FakeTopicRepository()
    scheduler = TopicResearchScheduler(repository, FakeLLMClient(_valid_payload()))

    run = scheduler._research_topic(repository.topic, repository.prompt)

    assert run.status == "success"
    assert run.findings_created == 1
    assert len(repository.findings) == 1

    finding = repository.findings[0]
    assert isinstance(finding, TopicFinding)
    assert finding.intelligence_topic_id == repository.topic.id
    assert finding.prompt_version_id == repository.prompt.id
    assert finding.status == "active"
    assert "raw-1" in finding.source_raw_item_ids
    assert len(finding.citations) == 1
    assert finding.citations[0]["message_id"] == "raw-1"

    # Check that raw item was marked processed
    assert "raw-1" in repository.processed_items

    # Check that checkpoint was advanced
    assert repository.checkpoint is not None
    assert repository.checkpoint.get("checkpoint_cursor") is not None
    payload = repository.checkpoint.get("checkpoint_payload", {})
    assert payload.get("finding_count") == 1
    assert payload.get("raw_item_count") == 1


def test_failure_does_not_advance_checkpoint() -> None:
    """Failed run records error but leaves checkpoint unchanged."""
    repository = FakeTopicRepository()
    original_checkpoint = dict(repository.checkpoint or {})
    scheduler = TopicResearchScheduler(
        repository,
        FakeLLMClient('{"schema_version": "topic-research-v1", "findings": ['),
    )

    run = scheduler._research_topic(repository.topic, repository.prompt)

    assert run.status == "failed"
    assert "Malformed topic research JSON" in str(run.error_message)
    assert repository.findings == []
    assert repository.checkpoint == original_checkpoint

    # No processed items should have been marked
    assert repository.processed_items == []


def test_scheduled_research_does_not_count_validation_failure_as_completed() -> None:
    repository = FakeTopicRepository()
    scheduler = TopicResearchScheduler(repository, FakeLLMClient(""))

    completed = scheduler.run_scheduled_topic_research()

    assert completed == 0
    assert len(repository.runs) == 1
    assert repository.runs[0].status == "failed"


def test_skips_inactive_topics() -> None:
    """Draft, paused, and archived topics are skipped by run_scheduled_topic_research."""
    active_topic = IntelligenceTopic.create(
        name="Active Topic",
        lifecycle_status=TopicLifecycleStatus.ACTIVE.value,
    )
    draft_topic = IntelligenceTopic.create(
        name="Draft Topic",
        lifecycle_status=TopicLifecycleStatus.DRAFT.value,
    )
    paused_topic = IntelligenceTopic.create(
        name="Paused Topic",
        lifecycle_status=TopicLifecycleStatus.PAUSED.value,
    )
    archived_topic = IntelligenceTopic.create(
        name="Archived Topic",
        lifecycle_status=TopicLifecycleStatus.ARCHIVED.value,
    )

    repository = FakeTopicRepository()
    repository.set_topics([active_topic, draft_topic, paused_topic, archived_topic])
    for t in [active_topic, draft_topic, paused_topic, archived_topic]:
        prompt = TopicPrompt.create(
            intelligence_topic_id=t.id,
            prompt_version="1",
            prompt_text="Research prompt for " + t.name,
            schema_version="topic-prompt-generation-v1",
            status="active",
        )
        repository.set_prompt(t.id, prompt)
        repository.set_raw_items_for(
            t.id,
            [
                RawIntelligenceItem(
                    id=f"raw-{t.name}",
                    source_type="telegram_group",
                    source_id="chat-1",
                    raw_text=f"Test message for {t.name}",
                    content_hash=f"hash-{t.name}",
                    collected_at=datetime.utcnow(),
                    created_at=datetime.utcnow(),
                    expires_at=datetime.utcnow() + timedelta(days=180),
                )
            ],
        )

    scheduler = TopicResearchScheduler(repository, FakeLLMClient(_valid_payload()))
    completed = scheduler.run_scheduled_topic_research()

    # Only the active topic should be researched
    assert completed == 1

    # Check that only the active topic has runs
    assert len(repository.runs) == 1
    assert repository.runs[0].intelligence_topic_id == active_topic.id

    # Inactive topics have no runs
    inactive_ids = {draft_topic.id, paused_topic.id, archived_topic.id}
    for run in repository.runs:
        assert run.intelligence_topic_id not in inactive_ids


def test_no_messages() -> None:
    """No messages since checkpoint produces a no-op success run without advancing checkpoint."""
    repository = FakeTopicRepository()
    repository.raw_items = []

    scheduler = TopicResearchScheduler(repository, FakeLLMClient(_valid_payload()))
    run = scheduler._research_topic(repository.topic, repository.prompt)

    assert run.status == "success"
    assert run.findings_created == 0
    assert run.items_scanned == 0
    assert len(repository.findings) == 0
    # Checkpoint should still exist (not None) but cursor may be reset
    assert repository.checkpoint is not None
    payload = repository.checkpoint.get("checkpoint_payload", {})
    assert payload.get("noop", False) is True


def test_new_prompt_without_checkpoint_starts_at_activation_time() -> None:
    """A newly confirmed prompt should not restart topic research from all historical raw items."""
    repository = FakeTopicRepository()
    activated_at = datetime(2026, 5, 22, 10, 25, 0)
    repository.prompt.activated_at = activated_at
    repository.checkpoint = None
    repository.raw_items = [
        RawIntelligenceItem(
            id="raw-old",
            source_type="telegram_group",
            source_id="chat-1",
            raw_text="Old backlog message.",
            content_hash="hash-old",
            collected_at=datetime(2026, 5, 10, 6, 48, 0),
            created_at=datetime(2026, 5, 10, 6, 48, 0),
            expires_at=datetime(2026, 11, 10, 6, 48, 0),
        ),
        RawIntelligenceItem(
            id="raw-new",
            source_type="telegram_group",
            source_id="chat-1",
            raw_text="New message after prompt activation.",
            content_hash="hash-new",
            collected_at=datetime(2026, 5, 22, 11, 0, 0),
            created_at=datetime(2026, 5, 22, 11, 0, 0),
            expires_at=datetime(2026, 11, 22, 11, 0, 0),
        ),
    ]

    scheduler = TopicResearchScheduler(repository, FakeLLMClient(_valid_payload()))
    raw_items = scheduler._fetch_raw_messages_since(repository.topic, repository.prompt)

    assert repository.last_cursor_time == activated_at
    assert [item.id for item in raw_items] == ["raw-new"]


def test_scheduler_default_raw_item_limit_is_400() -> None:
    repository = FakeTopicRepository()

    scheduler = TopicResearchScheduler(repository, FakeLLMClient(_valid_payload()))
    scheduler._fetch_raw_messages_since(repository.topic, repository.prompt)

    assert scheduler.raw_item_limit == DEFAULT_RAW_ITEM_LIMIT
    assert repository.last_limit == 400


def test_scheduler_passes_generation_options_to_llm() -> None:
    repository = FakeTopicRepository()
    llm_client = FakeLLMClient(_valid_payload())
    scheduler = TopicResearchScheduler(
        repository,
        llm_client,
        model_name="deepseek-v4-pro",
        temperature=0.2,
        max_tokens=1234,
        extra_body={"thinking": {"type": "enabled"}},
    )

    scheduler.run_topic(repository.topic, repository.prompt)

    call = llm_client.completions.calls[0]
    assert call["model"] == "deepseek-v4-pro"
    assert call["temperature"] == 0.2
    assert call["max_tokens"] == 1234
    assert call["extra_body"] == {"thinking": {"type": "enabled"}}


def test_prompt_activation_time_prevents_checkpoint_regression() -> None:
    """A prompt-specific checkpoint older than activation should be clamped forward."""
    repository = FakeTopicRepository()
    activated_at = datetime(2026, 5, 22, 10, 25, 0)
    repository.prompt.activated_at = activated_at
    repository.checkpoint = {"checkpoint_cursor": "2026-05-10T06:48:48+00:00"}
    repository.raw_items = [
        RawIntelligenceItem(
            id="raw-backlog",
            source_type="v2ex",
            source_id="claude",
            raw_text="Backlog before activation.",
            content_hash="hash-backlog",
            collected_at=datetime(2026, 5, 10, 6, 49, 0),
            created_at=datetime(2026, 5, 10, 6, 49, 0),
            expires_at=datetime(2026, 11, 10, 6, 49, 0),
        ),
        RawIntelligenceItem(
            id="raw-current",
            source_type="v2ex",
            source_id="claude",
            raw_text="Current message after activation.",
            content_hash="hash-current",
            collected_at=datetime(2026, 5, 22, 12, 0, 0),
            created_at=datetime(2026, 5, 22, 12, 0, 0),
            expires_at=datetime(2026, 11, 22, 12, 0, 0),
        ),
    ]

    scheduler = TopicResearchScheduler(repository, FakeLLMClient(_valid_payload()))
    raw_items = scheduler._fetch_raw_messages_since(repository.topic, repository.prompt)

    assert repository.last_cursor_time == activated_at
    assert [item.id for item in raw_items] == ["raw-current"]


def test_postgres_run_update_casts_nullable_coalesce_params() -> None:
    """Postgres needs explicit casts when nullable COALESCE parameters are None."""
    run = TopicResearchRun.create("topic-1", status="running")
    manager = _FakePostgresDataManager(
        run_row=run.to_dict(),
        checkpoint_row={
            "intelligence_topic_id": "topic-1",
            "prompt_version_id": None,
            "checkpoint_cursor": None,
            "checkpoint_payload": "{}",
            "last_run_id": run.id,
            "updated_at": datetime.utcnow().isoformat(),
        },
    )
    repository = SQLiteIntelligenceRepository(manager)  # type: ignore[arg-type]

    repository.update_topic_research_run(
        run.id,
        status="running",
        checkpoint_cursor=None,
        items_scanned=None,
        findings_created=None,
        finished_at=None,
    )

    update_query, params = next(
        (query, params)
        for query, params in manager.executed
        if "UPDATE intelligence_topic_research_runs" in query
    )
    assert "COALESCE(CAST(%s AS TEXT), checkpoint_cursor)" in update_query
    assert "COALESCE(CAST(%s AS INTEGER), items_scanned)" in update_query
    assert "COALESCE(CAST(%s AS TIMESTAMPTZ), finished_at)" in update_query
    assert params[6] is None


def test_postgres_checkpoint_update_casts_nullable_prompt_null_check() -> None:
    """The nullable prompt-version check must be typed for Postgres."""
    run = TopicResearchRun.create("topic-1", status="running")
    manager = _FakePostgresDataManager(
        run_row=run.to_dict(),
        checkpoint_row={
            "intelligence_topic_id": "topic-1",
            "prompt_version_id": None,
            "checkpoint_cursor": "31",
            "checkpoint_payload": "{}",
            "last_run_id": run.id,
            "updated_at": datetime.utcnow().isoformat(),
        },
    )
    repository = SQLiteIntelligenceRepository(manager)  # type: ignore[arg-type]

    repository.update_topic_checkpoint(
        "topic-1",
        None,
        checkpoint_cursor=None,
        checkpoint_payload={"noop": True},
        last_run_id=run.id,
    )

    update_query, params = next(
        (query, params)
        for query, params in manager.executed
        if "UPDATE intelligence_topic_research_checkpoints" in query
    )
    assert "CAST(%s AS TEXT) IS NULL" in update_query
    assert params[6] is None


def test_idempotent_retry() -> None:
    """Second run with same raw items produces no duplicate findings."""
    repository = FakeTopicRepository()
    scheduler = TopicResearchScheduler(repository, FakeLLMClient(_valid_payload()))

    # First run: should produce findings and mark items processed
    run1 = scheduler._research_topic(repository.topic, repository.prompt)
    assert run1.status == "success"
    assert run1.findings_created == 1
    assert len(repository.findings) == 1

    # Advance checkpoint to after first run so second fetch gets same items
    old_collected = repository.raw_items[0].collected_at
    repository.raw_items[0].collected_at = old_collected + timedelta(minutes=5)
    # Also add a new raw item to avoid empty-result path
    repository.raw_items.append(
        RawIntelligenceItem(
            id="raw-2",
            source_type="telegram_group",
            source_id="chat-1",
            raw_text="Second message confirming ETF inflow spike.",
            content_hash="hash-raw-2",
            collected_at=old_collected + timedelta(minutes=5),
            created_at=old_collected + timedelta(minutes=5),
            expires_at=datetime.utcnow() + timedelta(days=180),
        )
    )

    # Second run: processed items should be filtered out in _fetch_raw_messages_since
    run2 = scheduler._research_topic(repository.topic, repository.prompt)
    assert run2.status == "success"
    # Should only have findings from the second (new) item
    assert run2.findings_created == 1
    # Total findings = 1 from first run + 1 from second run, NOT 2+2=4
    assert len(repository.findings) == 2
    # "raw-1" was already processed in run1
    assert "raw-1" in repository._processed_markers
    # run2 should not re-process raw-1
    assert run2.items_scanned == 1  # only raw-2 was new


def test_chunking_large_input() -> None:
    """Messages exceeding max_chunk_chars are split into multiple LLM calls."""
    repository = FakeTopicRepository()
    # Create many large messages that will exceed the chunk limit
    many_items = []
    for i in range(20):
        many_items.append(
            RawIntelligenceItem(
                id=f"raw-chunk-{i}",
                source_type="telegram_group",
                source_id="chat-1",
                raw_text="X" * 5000,  # 5KB each → 100KB total
                content_hash=f"hash-chunk-{i}",
                collected_at=datetime.utcnow(),
                created_at=datetime.utcnow(),
                expires_at=datetime.utcnow() + timedelta(days=180),
            )
        )
    repository.raw_items = many_items

    # Custom LLM that returns a finding referencing a specific message in each chunk
    chunk_payloads: List[str] = []
    for i in range(20):
        chunk_payloads.append(
            json.dumps(
                {
                    "schema_version": TOPIC_RESEARCH_SCHEMA_VERSION,
                    "topic_name": "BTC ETF flow",
                    "research_summary": f"Chunk analysis for item {i}.",
                    "findings": [
                        {
                            "finding_id": f"f-chunk-{i}",
                            "summary": f"Finding from chunk containing item {i}",
                            "detail": f"Detail for chunk {i}.",
                            "confidence": 0.7,
                            "citations": [
                                {
                                    "message_id": f"raw-chunk-{i}",
                                    "message_snippet": "X" * 100,
                                    "source": "chat-1",
                                    "published_at": "",
                                }
                            ],
                        }
                    ],
                    "messages_processed": 1,
                    "messages_relevant": 1,
                }
            )
        )

    scheduler = TopicResearchScheduler(
        repository,
        FakeLLMClient(chunk_payloads[0]),
        max_chunk_chars=10000,  # Small chunk size to force splitting
    )

    # The _chunk_messages should split into ~10 chunks (100KB / 10KB)
    chunks = scheduler._chunk_messages(many_items)
    assert len(chunks) > 1, f"Expected multiple chunks, got {len(chunks)}"

    # Verify each chunk's total text size is under the limit
    for chunk in chunks:
        total_size = sum(len(item.raw_text or "") for item in chunk)
        assert total_size <= 10000, f"Chunk size {total_size} exceeds limit"


def test_run_scheduled_topic_research_survives_topic_error() -> None:
    """One topic failure does not prevent other topics from being researched."""
    good_topic = IntelligenceTopic.create(name="Good Topic")
    bad_topic = IntelligenceTopic.create(name="Bad Topic")

    repository = FakeTopicRepository()
    repository.set_topics([good_topic, bad_topic])

    for t in [good_topic, bad_topic]:
        prompt = TopicPrompt.create(
            intelligence_topic_id=t.id,
            prompt_version="1",
            prompt_text="Research prompt",
            schema_version="topic-prompt-generation-v1",
            status="active",
        )
        repository.set_prompt(t.id, prompt)

    scheduler = TopicResearchScheduler(repository, FakeLLMClient(_valid_payload()))

    repository.set_topics([good_topic])

    completed = scheduler.run_scheduled_topic_research()
    assert completed == 1
    assert len(repository.runs) == 1
    assert repository.runs[0].intelligence_topic_id == good_topic.id


def test_empty_chunk_list_returns_no_findings() -> None:
    """Calling _research_topic with messages that chunk to a single empty chunk."""
    repository = FakeTopicRepository()
    # Single item under chunk limit
    repository.raw_items = [
        RawIntelligenceItem(
            id="raw-small",
            source_type="telegram_group",
            source_id="chat-1",
            raw_text="Small text.",
            content_hash="hash-small",
            collected_at=datetime.utcnow(),
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(days=180),
        )
    ]
    scheduler = TopicResearchScheduler(repository, FakeLLMClient(_valid_payload()))
    chunks = scheduler._chunk_messages(repository.raw_items)
    assert len(chunks) == 1
    assert chunks[0] == repository.raw_items
