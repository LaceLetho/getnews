"""
Shared Domain Contracts

This package defines the shared domain contracts between services in the Railway
split architecture. These contracts must remain stable across service boundaries.

Version: 1.0.0
Compatibility: Backward compatible within major version
"""

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any, cast
from dataclasses import dataclass, field
import uuid


class JobStatus(str, Enum):
    """Analysis job status values - FROZEN"""

    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class IngestionJobStatus(str, Enum):
    """Ingestion job status values - FROZEN"""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"  # When deduplicated


class Priority(int, Enum):
    """Job priority levels - FROZEN"""

    LOW = 1
    NORMAL = 5
    HIGH = 10
    CRITICAL = 20


class DataSourceType(str, Enum):
    RSS = "rss"
    X = "x"
    REST_API = "rest_api"
    TELEGRAM_GROUP = "telegram_group"
    V2EX = "v2ex"


class EntryType(str, Enum):
    CHANNEL = "channel"
    SLANG = "slang"


class PrimaryLabel(str, Enum):
    AI = "AI"
    CRYPTO = "crypto"
    DARK_WEB = "暗网"
    ACCOUNT_TRADING = "账号交易"
    PAYMENT = "支付"
    GAME = "游戏"
    ECOMMERCE = "电商"
    SOCIAL_MEDIA = "社媒"
    DEVELOPER_TOOLS = "开发者工具"
    OTHER = "其他"


class CheckpointStatus(str, Enum):
    OK = "ok"
    RATE_LIMITED = "rate_limited"
    ERROR = "error"


ACTIVE_INGESTION_JOB_STATUSES = frozenset({"pending", "running"})

_ENTRY_TYPE_VALUES = {item.value for item in EntryType}
_PRIMARY_LABEL_VALUES = {item.value for item in PrimaryLabel}
_CHECKPOINT_STATUS_VALUES = {item.value for item in CheckpointStatus}
_FORBIDDEN_SECRET_KEYS = {
    "stringsession",
    "string_session",
    "session",
    "v2ex_pat",
    "pat",
    "api_key",
    "apikey",
    "authorization",
    "auth_token",
    "access_token",
    "api_id",
    "api_hash",
    "phone",
    "secret",
}


def _parse_optional_datetime(value: Any) -> Optional[datetime]:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value))


def _validate_json_list(value: Optional[List[str]], field_name: str) -> List[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a list")
    return [str(item).strip() for item in value if str(item).strip()]


def _validate_public_payload(payload: Dict[str, Any], field_name: str) -> Dict[str, Any]:
    normalized = dict(payload or {})
    forbidden = sorted(
        key for key in normalized.keys() if str(key).strip().lower() in _FORBIDDEN_SECRET_KEYS
    )
    if forbidden:
        raise ValueError(f"{field_name} cannot contain private credential fields")
    return normalized


class DataSourceInUseError(ValueError):
    def __init__(
        self, source_type: str, source_name: str, active_job_ids: Optional[List[str]] = None
    ):
        self.source_type = source_type
        self.source_name = source_name
        self.active_job_ids = list(active_job_ids or [])
        super().__init__(
            f"Cannot delete datasource '{source_type}:{source_name}' while matching ingestion jobs are active"
        )


class DataSourceAlreadyExistsError(ValueError):
    def __init__(self, source_type: str, source_name: str):
        self.source_type = source_type
        self.source_name = source_name
        super().__init__(f"Datasource '{source_type}:{source_name}' already exists")


def _normalize_datasource_tags(tags: Optional[List[str]]) -> List[str]:
    normalized_tags = {str(tag).strip().lower() for tag in (tags or []) if str(tag).strip()}
    return sorted(normalized_tags)


@dataclass
class DataSource:
    id: str
    source_type: str
    name: str
    tags: List[str] = field(default_factory=list)
    config_payload: Dict[str, Any] = field(default_factory=dict)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def __post_init__(self):
        if not self.id:
            raise ValueError("id is required")

        normalized_source_type = str(self.source_type).strip().lower()
        if normalized_source_type not in {item.value for item in DataSourceType}:
            raise ValueError("source_type must be one of: rss, x, rest_api, telegram_group, v2ex")

        normalized_name = str(self.name).strip()
        if not normalized_name:
            raise ValueError("name is required")

        self.source_type = normalized_source_type
        self.name = normalized_name
        self.tags = _normalize_datasource_tags(self.tags)
        self.config_payload = _validate_public_payload(
            dict(self.config_payload or {}), "config_payload"
        )

    @property
    def unique_key(self) -> tuple[str, str]:
        return (self.source_type, self.name)

    @classmethod
    def create(
        cls,
        name: str,
        source_type: str,
        tags: Optional[List[str]] = None,
        config_payload: Optional[Dict[str, Any]] = None,
    ) -> "DataSource":
        now = datetime.utcnow()
        return cls(
            id=str(uuid.uuid4()),
            source_type=source_type,
            name=name,
            tags=tags or [],
            config_payload=config_payload or {},
            created_at=now,
            updated_at=now,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "source_type": self.source_type,
            "name": self.name,
            "tags": list(self.tags),
            "config_payload": dict(self.config_payload),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DataSource":
        return cls(
            id=data["id"],
            source_type=data["source_type"],
            name=data["name"],
            tags=data.get("tags", []),
            config_payload=data.get("config_payload", {}),
            created_at=(
                datetime.fromisoformat(data["created_at"]) if data.get("created_at") else None
            ),
            updated_at=(
                datetime.fromisoformat(data["updated_at"]) if data.get("updated_at") else None
            ),
        )


@dataclass
class AnalysisRequest:
    """
    Analysis request model - SHARED CONTRACT

    This model is used for:
    1. API service receiving analysis requests
    2. Ingestion service creating analysis jobs
    3. Database persistence of analysis jobs

    Version: 1.0.0

    Required fields:
    - id: Unique identifier (UUID)
    - recipient_key: Target recipient (e.g., "api:user-123", "telegram:chat-456")
    - time_window_hours: Analysis time window
    - created_at: Creation timestamp (UTC)
    - status: Job status
    - priority: Job priority for queue ordering

    Optional fields:
    - started_at: When job started execution
    - completed_at: When job finished
    - result: Analysis result data
    - error_message: Error details if failed
    - source: Source of request ("api", "telegram", "scheduler")
    """

    id: str
    recipient_key: str
    time_window_hours: int
    created_at: datetime
    status: str = field(default=JobStatus.PENDING.value)
    priority: int = field(default=Priority.NORMAL.value)

    # Optional fields
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    source: str = field(default="api")

    def __post_init__(self):
        if not self.id:
            raise ValueError("id is required")
        if not self.recipient_key:
            raise ValueError("recipient_key is required")
        if self.time_window_hours <= 0:
            raise ValueError("time_window_hours must be positive")
        if not self.created_at:
            raise ValueError("created_at is required")

    @classmethod
    def create(
        cls,
        recipient_key: str,
        time_window_hours: int,
        source: str = "api",
        priority: int = Priority.NORMAL.value,
    ) -> "AnalysisRequest":
        """Factory method to create a new AnalysisRequest with auto-generated ID"""
        return cls(
            id=str(uuid.uuid4()),
            recipient_key=recipient_key,
            time_window_hours=time_window_hours,
            created_at=datetime.utcnow(),
            status=JobStatus.PENDING.value,
            priority=priority,
            source=source,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary"""
        return {
            "id": self.id,
            "recipient_key": self.recipient_key,
            "time_window_hours": self.time_window_hours,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "status": self.status,
            "priority": self.priority,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "result": self.result,
            "error_message": self.error_message,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AnalysisRequest":
        """Deserialize from dictionary"""
        return cls(
            id=data["id"],
            recipient_key=data["recipient_key"],
            time_window_hours=data["time_window_hours"],
            created_at=cast(
                datetime,
                datetime.fromisoformat(data["created_at"]) if data.get("created_at") else None,
            ),
            status=data.get("status", JobStatus.PENDING.value),
            priority=data.get("priority", Priority.NORMAL.value),
            started_at=(
                datetime.fromisoformat(data["started_at"]) if data.get("started_at") else None
            ),
            completed_at=(
                datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None
            ),
            result=data.get("result"),
            error_message=data.get("error_message"),
            source=data.get("source", "api"),
        )


@dataclass
class SemanticSearchJob:
    """Semantic search job model - SHARED CONTRACT."""

    id: str
    recipient_key: str
    query: str
    normalized_intent: str
    time_window_hours: int
    created_at: datetime
    status: str = field(default=JobStatus.PENDING.value)
    priority: int = field(default=Priority.NORMAL.value)
    matched_count: int = 0
    retained_count: int = 0
    decomposition_json: Optional[Dict[str, Any]] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    source: str = field(default="api")

    def __post_init__(self):
        if not self.id:
            raise ValueError("id is required")
        if not self.id.startswith("semantic_search_job_"):
            raise ValueError("id must start with semantic_search_job_")
        if not self.recipient_key:
            raise ValueError("recipient_key is required")
        normalized_query = str(self.query).strip()
        if not normalized_query:
            raise ValueError("query is required")
        if self.time_window_hours <= 0:
            raise ValueError("time_window_hours must be positive")
        if not self.created_at:
            raise ValueError("created_at is required")
        if self.matched_count < 0:
            raise ValueError("matched_count cannot be negative")
        if self.retained_count < 0:
            raise ValueError("retained_count cannot be negative")

        self.query = normalized_query
        self.normalized_intent = str(self.normalized_intent or "").strip()

    @classmethod
    def create(
        cls,
        recipient_key: str,
        query: str,
        time_window_hours: int,
        normalized_intent: str = "",
        source: str = "api",
        priority: int = Priority.NORMAL.value,
    ) -> "SemanticSearchJob":
        return cls(
            id=f"semantic_search_job_{uuid.uuid4().hex}",
            recipient_key=recipient_key,
            query=query,
            normalized_intent=normalized_intent,
            time_window_hours=time_window_hours,
            created_at=datetime.utcnow(),
            status=JobStatus.PENDING.value,
            priority=priority,
            source=source,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "recipient_key": self.recipient_key,
            "query": self.query,
            "normalized_intent": self.normalized_intent,
            "time_window_hours": self.time_window_hours,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "status": self.status,
            "priority": self.priority,
            "matched_count": self.matched_count,
            "retained_count": self.retained_count,
            "decomposition_json": self.decomposition_json,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "result": self.result,
            "error_message": self.error_message,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SemanticSearchJob":
        return cls(
            id=data["id"],
            recipient_key=data["recipient_key"],
            query=data["query"],
            normalized_intent=data.get("normalized_intent", ""),
            time_window_hours=data["time_window_hours"],
            created_at=cast(
                datetime,
                datetime.fromisoformat(data["created_at"]) if data.get("created_at") else None,
            ),
            status=data.get("status", JobStatus.PENDING.value),
            priority=data.get("priority", Priority.NORMAL.value),
            matched_count=data.get("matched_count", 0),
            retained_count=data.get("retained_count", 0),
            decomposition_json=data.get("decomposition_json"),
            started_at=(
                datetime.fromisoformat(data["started_at"]) if data.get("started_at") else None
            ),
            completed_at=(
                datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None
            ),
            result=data.get("result"),
            error_message=data.get("error_message"),
            source=data.get("source", "api"),
        )


@dataclass
class IngestionJob:
    """
    Ingestion job model - SHARED CONTRACT

    This model is used for:
    1. Scheduler creating periodic crawl jobs
    2. Ingestion service tracking crawl execution
    3. Database persistence of ingestion history

    Version: 1.0.0

    Required fields:
    - id: Unique identifier (UUID)
    - source_type: Type of source ("rss", "x", "api")
    - source_name: Name of the specific source
    - scheduled_at: When job was scheduled
    - status: Job status

    Optional fields:
    - started_at: When job started execution
    - completed_at: When job finished
    - items_crawled: Number of items crawled
    - items_new: Number of new (non-duplicate) items
    - error_message: Error details if failed
    - metadata: Additional job metadata
    """

    id: str
    source_type: str  # "rss", "x", "api"
    source_name: str
    scheduled_at: datetime
    status: str = field(default=IngestionJobStatus.PENDING.value)

    # Optional fields
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    items_crawled: int = field(default=0)
    items_new: int = field(default=0)
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.id:
            raise ValueError("id is required")
        if not self.source_type:
            raise ValueError("source_type is required")
        if not self.source_name:
            raise ValueError("source_name is required")
        if not self.scheduled_at:
            raise ValueError("scheduled_at is required")
        if self.items_crawled < 0:
            raise ValueError("items_crawled cannot be negative")
        if self.items_new < 0:
            raise ValueError("items_new cannot be negative")

    @classmethod
    def create(
        cls,
        source_type: str,
        source_name: str,
    ) -> "IngestionJob":
        """Factory method to create a new IngestionJob with auto-generated ID"""
        return cls(
            id=str(uuid.uuid4()),
            source_type=source_type,
            source_name=source_name,
            scheduled_at=datetime.utcnow(),
            status=IngestionJobStatus.PENDING.value,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary"""
        return {
            "id": self.id,
            "source_type": self.source_type,
            "source_name": self.source_name,
            "scheduled_at": self.scheduled_at.isoformat() if self.scheduled_at else None,
            "status": self.status,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "items_crawled": self.items_crawled,
            "items_new": self.items_new,
            "error_message": self.error_message,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "IngestionJob":
        """Deserialize from dictionary"""
        return cls(
            id=data["id"],
            source_type=data["source_type"],
            source_name=data["source_name"],
            scheduled_at=cast(
                datetime,
                datetime.fromisoformat(data["scheduled_at"]) if data.get("scheduled_at") else None,
            ),
            status=data.get("status", IngestionJobStatus.PENDING.value),
            started_at=(
                datetime.fromisoformat(data["started_at"]) if data.get("started_at") else None
            ),
            completed_at=(
                datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None
            ),
            items_crawled=data.get("items_crawled", 0),
            items_new=data.get("items_new", 0),
            error_message=data.get("error_message"),
            metadata=data.get("metadata", {}),
        )


@dataclass
class AnalysisResult:
    """
    Analysis result data - SHARED CONTRACT

    This model represents the output of an analysis job.
    Stored as JSON in AnalysisRequest.result field.

    Version: 1.0.0
    """

    success: bool
    items_processed: int
    report_content: str
    final_report_messages: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    categories_found: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary"""
        return {
            "success": self.success,
            "items_processed": self.items_processed,
            "report_content": self.report_content,
            "final_report_messages": self.final_report_messages,
            "errors": self.errors,
            "categories_found": self.categories_found,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AnalysisResult":
        """Deserialize from dictionary"""
        return cls(
            success=data["success"],
            items_processed=data["items_processed"],
            report_content=data["report_content"],
            final_report_messages=data.get("final_report_messages", []),
            errors=data.get("errors", []),
            categories_found=data.get("categories_found", {}),
        )


@dataclass
class RawIntelligenceItem:
    id: str
    source_type: str
    raw_text: Optional[str]
    content_hash: str
    expires_at: datetime
    source_id: Optional[str] = None
    external_id: Optional[str] = None
    source_url: Optional[str] = None
    chat_id: Optional[str] = None
    thread_id: Optional[str] = None
    topic_id: Optional[str] = None
    published_at: Optional[datetime] = None
    collected_at: datetime = field(default_factory=datetime.utcnow)
    edit_status: Optional[str] = None
    edit_timestamp: Optional[datetime] = None
    created_at: Optional[datetime] = None

    def __post_init__(self):
        if not self.id:
            raise ValueError("id is required")
        self.source_type = str(self.source_type).strip().lower()
        if not self.source_type:
            raise ValueError("source_type is required")
        if self.raw_text is not None:
            if not str(self.raw_text).strip():
                raise ValueError("raw_text is required")
            self.raw_text = str(self.raw_text)
        self.content_hash = str(self.content_hash).strip()
        if not self.content_hash:
            raise ValueError("content_hash is required")
        if not self.expires_at:
            raise ValueError("expires_at is required")
        if not self.collected_at:
            raise ValueError("collected_at is required")

    @classmethod
    def create(
        cls,
        source_type: str,
        raw_text: str,
        content_hash: str,
        expires_at: datetime,
        source_id: Optional[str] = None,
        external_id: Optional[str] = None,
        source_url: Optional[str] = None,
        chat_id: Optional[str] = None,
        thread_id: Optional[str] = None,
        topic_id: Optional[str] = None,
        published_at: Optional[datetime] = None,
        edit_status: Optional[str] = None,
        edit_timestamp: Optional[datetime] = None,
    ) -> "RawIntelligenceItem":
        now = datetime.utcnow()
        return cls(
            id=str(uuid.uuid4()),
            source_type=source_type,
            source_id=source_id,
            external_id=external_id,
            source_url=source_url,
            chat_id=chat_id,
            thread_id=thread_id,
            topic_id=topic_id,
            raw_text=raw_text,
            content_hash=content_hash,
            published_at=published_at,
            collected_at=now,
            expires_at=expires_at,
            edit_status=edit_status,
            edit_timestamp=edit_timestamp,
            created_at=now,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "source_type": self.source_type,
            "source_id": self.source_id,
            "external_id": self.external_id,
            "source_url": self.source_url,
            "chat_id": self.chat_id,
            "thread_id": self.thread_id,
            "topic_id": self.topic_id,
            "raw_text": self.raw_text,
            "content_hash": self.content_hash,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "collected_at": self.collected_at.isoformat() if self.collected_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "edit_status": self.edit_status,
            "edit_timestamp": self.edit_timestamp.isoformat() if self.edit_timestamp else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RawIntelligenceItem":
        return cls(
            id=data["id"],
            source_type=data["source_type"],
            source_id=data.get("source_id"),
            external_id=data.get("external_id"),
            source_url=data.get("source_url"),
            chat_id=data.get("chat_id"),
            thread_id=data.get("thread_id"),
            topic_id=data.get("topic_id"),
            raw_text=data.get("raw_text"),
            content_hash=data["content_hash"],
            published_at=_parse_optional_datetime(data.get("published_at")),
            collected_at=cast(datetime, _parse_optional_datetime(data.get("collected_at"))),
            expires_at=cast(datetime, _parse_optional_datetime(data.get("expires_at"))),
            edit_status=data.get("edit_status"),
            edit_timestamp=_parse_optional_datetime(data.get("edit_timestamp")),
            created_at=_parse_optional_datetime(data.get("created_at")),
        )


@dataclass
class ExtractionObservation:
    id: str
    raw_item_id: str
    entry_type: str
    confidence: float
    model_name: str
    prompt_version: str
    schema_version: str
    channel_name: Optional[str] = None
    channel_description: Optional[str] = None
    channel_urls: List[str] = field(default_factory=list)
    channel_handles: List[str] = field(default_factory=list)
    channel_domains: List[str] = field(default_factory=list)
    term: Optional[str] = None
    normalized_term: Optional[str] = None
    literal_meaning: Optional[str] = None
    contextual_meaning: Optional[str] = None
    usage_example_raw_item_id: Optional[str] = None
    usage_quote: Optional[str] = None
    aliases_or_variants: List[str] = field(default_factory=list)
    detected_language: Optional[str] = None
    primary_label: Optional[str] = None
    secondary_tags: List[str] = field(default_factory=list)
    is_canonicalized: bool = False
    created_at: Optional[datetime] = None

    def __post_init__(self):
        if not self.id:
            raise ValueError("id is required")
        if not self.raw_item_id:
            raise ValueError("raw_item_id is required")
        self.entry_type = str(self.entry_type).strip().lower()
        if self.entry_type not in _ENTRY_TYPE_VALUES:
            raise ValueError("entry_type must be one of: channel, slang")
        if self.primary_label and self.primary_label not in _PRIMARY_LABEL_VALUES:
            raise ValueError("primary_label is invalid")
        if not 0.0 <= float(self.confidence) <= 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0")
        self.confidence = float(self.confidence)
        for field_name in ("model_name", "prompt_version", "schema_version"):
            if not str(getattr(self, field_name) or "").strip():
                raise ValueError(f"{field_name} is required")
            setattr(self, field_name, str(getattr(self, field_name)).strip())
        if self.entry_type == EntryType.CHANNEL.value and not (
            self.channel_name or self.channel_urls or self.channel_handles or self.channel_domains
        ):
            raise ValueError("channel observation requires channel_name, urls, handles, or domains")
        if self.entry_type == EntryType.SLANG.value:
            if not str(self.term or "").strip():
                raise ValueError("slang observation requires term")
            if not str(self.normalized_term or "").strip():
                raise ValueError("slang observation requires normalized_term")
        self.channel_urls = _validate_json_list(self.channel_urls, "channel_urls")
        self.channel_handles = _validate_json_list(self.channel_handles, "channel_handles")
        self.channel_domains = _validate_json_list(self.channel_domains, "channel_domains")
        self.aliases_or_variants = _validate_json_list(
            self.aliases_or_variants, "aliases_or_variants"
        )
        self.secondary_tags = _validate_json_list(self.secondary_tags, "secondary_tags")

    @classmethod
    def create(
        cls,
        raw_item_id: str,
        entry_type: str,
        confidence: float,
        model_name: str,
        prompt_version: str,
        schema_version: str,
        **kwargs: Any,
    ) -> "ExtractionObservation":
        return cls(
            id=str(uuid.uuid4()),
            raw_item_id=raw_item_id,
            entry_type=entry_type,
            confidence=confidence,
            model_name=model_name,
            prompt_version=prompt_version,
            schema_version=schema_version,
            created_at=datetime.utcnow(),
            **kwargs,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            **self.__dict__,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExtractionObservation":
        payload = dict(data)
        payload["created_at"] = _parse_optional_datetime(payload.get("created_at"))
        return cls(**payload)


@dataclass
class CanonicalIntelligenceEntry:
    id: str
    entry_type: str
    normalized_key: str
    display_name: str
    confidence: float = 0.0
    explanation: Optional[str] = None
    usage_summary: Optional[str] = None
    primary_label: Optional[str] = None
    secondary_tags: List[str] = field(default_factory=list)
    first_seen_at: Optional[datetime] = None
    last_seen_at: Optional[datetime] = None
    evidence_count: int = 1
    latest_raw_item_id: Optional[str] = None
    prompt_version: Optional[str] = None
    model_name: Optional[str] = None
    schema_version: Optional[str] = None
    embedding: Optional[List[float]] = None
    embedding_model: Optional[str] = None
    embedding_updated_at: Optional[datetime] = None
    aliases: List[str] = field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def __post_init__(self):
        if not self.id:
            raise ValueError("id is required")
        self.entry_type = str(self.entry_type).strip().lower()
        if self.entry_type not in _ENTRY_TYPE_VALUES:
            raise ValueError("entry_type must be one of: channel, slang")
        self.normalized_key = str(self.normalized_key).strip().lower()
        if not self.normalized_key:
            raise ValueError("normalized_key is required")
        self.display_name = str(self.display_name).strip()
        if not self.display_name:
            raise ValueError("display_name is required")
        if self.primary_label and self.primary_label not in _PRIMARY_LABEL_VALUES:
            raise ValueError("primary_label is invalid")
        if not 0.0 <= float(self.confidence) <= 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0")
        self.confidence = float(self.confidence)
        if self.evidence_count < 0:
            raise ValueError("evidence_count cannot be negative")
        self.secondary_tags = _validate_json_list(self.secondary_tags, "secondary_tags")
        self.aliases = _validate_json_list(self.aliases, "aliases")
        if self.embedding is not None:
            self.embedding = [float(value) for value in self.embedding]

    @classmethod
    def create(
        cls,
        entry_type: str,
        normalized_key: str,
        display_name: str,
        **kwargs: Any,
    ) -> "CanonicalIntelligenceEntry":
        now = datetime.utcnow()
        return cls(
            id=str(uuid.uuid4()),
            entry_type=entry_type,
            normalized_key=normalized_key,
            display_name=display_name,
            created_at=now,
            updated_at=now,
            **kwargs,
        )

    def to_dict(self) -> Dict[str, Any]:
        data = dict(self.__dict__)
        for key in (
            "first_seen_at",
            "last_seen_at",
            "embedding_updated_at",
            "created_at",
            "updated_at",
        ):
            data[key] = data[key].isoformat() if data.get(key) else None
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CanonicalIntelligenceEntry":
        payload = dict(data)
        for key in (
            "first_seen_at",
            "last_seen_at",
            "embedding_updated_at",
            "created_at",
            "updated_at",
        ):
            payload[key] = _parse_optional_datetime(payload.get(key))
        return cls(**payload)


@dataclass
class IntelligenceCrawlCheckpoint:
    source_type: str
    source_id: str
    last_crawled_at: Optional[datetime] = None
    last_external_id: Optional[str] = None
    checkpoint_data: Dict[str, Any] = field(default_factory=dict)
    status: Optional[str] = CheckpointStatus.OK.value
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def __post_init__(self):
        self.source_type = str(self.source_type).strip().lower()
        self.source_id = str(self.source_id).strip()
        if not self.source_type:
            raise ValueError("source_type is required")
        if not self.source_id:
            raise ValueError("source_id is required")
        if self.status is not None and self.status not in _CHECKPOINT_STATUS_VALUES:
            raise ValueError("status must be one of: ok, rate_limited, error")
        self.checkpoint_data = _validate_public_payload(
            dict(self.checkpoint_data or {}), "checkpoint_data"
        )

    @classmethod
    def create(
        cls,
        source_type: str,
        source_id: str,
        checkpoint_data: Optional[Dict[str, Any]] = None,
        status: str = CheckpointStatus.OK.value,
        **kwargs: Any,
    ) -> "IntelligenceCrawlCheckpoint":
        now = datetime.utcnow()
        return cls(
            source_type=source_type,
            source_id=source_id,
            checkpoint_data=checkpoint_data or {},
            status=status,
            created_at=now,
            updated_at=now,
            **kwargs,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_type": self.source_type,
            "source_id": self.source_id,
            "last_crawled_at": self.last_crawled_at.isoformat() if self.last_crawled_at else None,
            "last_external_id": self.last_external_id,
            "checkpoint_data": dict(self.checkpoint_data),
            "status": self.status,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "IntelligenceCrawlCheckpoint":
        return cls(
            source_type=data["source_type"],
            source_id=data["source_id"],
            last_crawled_at=_parse_optional_datetime(data.get("last_crawled_at")),
            last_external_id=data.get("last_external_id"),
            checkpoint_data=data.get("checkpoint_data", {}),
            status=data.get("status"),
            error_message=data.get("error_message"),
            created_at=_parse_optional_datetime(data.get("created_at")),
            updated_at=_parse_optional_datetime(data.get("updated_at")),
        )
