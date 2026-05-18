"""
Shared Domain Contracts

This package defines the shared domain contracts between services in the Railway
split architecture. These contracts must remain stable across service boundaries.

Version: 1.0.0
Compatibility: Backward compatible within major version
"""

from datetime import datetime
from enum import Enum
from typing import ClassVar, Dict, List, Optional, Any, cast
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


class DataSourcePurpose(str, Enum):
    NEWS = "news"
    INTELLIGENCE = "intelligence"


class CheckpointStatus(str, Enum):
    OK = "ok"
    RATE_LIMITED = "rate_limited"
    ERROR = "error"


class TopicLifecycleStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    ARCHIVED = "archived"


class TopicPromptStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"


class TopicFindingStatus(str, Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    SUPERSEDED = "superseded"


class MergePreviewState(str, Enum):
    PENDING = "pending"
    APPLIED = "applied"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


ACTIVE_INGESTION_JOB_STATUSES = frozenset({"pending", "running"})

_CHECKPOINT_STATUS_VALUES = {item.value for item in CheckpointStatus}
_TOPIC_LIFECYCLE_STATUS_VALUES = {item.value for item in TopicLifecycleStatus}
_TOPIC_PROMPT_STATUS_VALUES = {item.value for item in TopicPromptStatus}
_TOPIC_FINDING_STATUS_VALUES = {item.value for item in TopicFindingStatus}
_MERGE_PREVIEW_STATE_VALUES = {item.value for item in MergePreviewState}
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


def _validate_public_object_list(value: Optional[List[Any]], field_name: str) -> List[Dict[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a list")

    items: List[Dict[str, Any]] = []
    for item in value:
        if isinstance(item, dict):
            normalized = _validate_public_payload(dict(item), field_name)
            if normalized:
                items.append(normalized)
            continue
        text = str(item or "").strip()
        if text:
            items.append({"name": text, "url": "", "type": "unknown"})
    return items


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
    def __init__(self, source_type: str, source_name: str, purpose: str):
        self.purpose = purpose
        self.source_type = source_type
        self.source_name = source_name
        super().__init__(f"Datasource '{purpose}:{source_type}:{source_name}' already exists")


def _normalize_datasource_tags(tags: Optional[List[str]]) -> List[str]:
    normalized_tags = {str(tag).strip().lower() for tag in (tags or []) if str(tag).strip()}
    return sorted(normalized_tags)


@dataclass
class DataSource:
    id: str
    purpose: str
    source_type: str
    name: str
    tags: List[str] = field(default_factory=list)
    config_payload: Dict[str, Any] = field(default_factory=dict)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def __post_init__(self):
        if not self.id:
            raise ValueError("id is required")

        normalized_purpose = str(self.purpose).strip().lower()
        if normalized_purpose not in {item.value for item in DataSourcePurpose}:
            raise ValueError("purpose must be one of: news, intelligence")

        normalized_source_type = str(self.source_type).strip().lower()
        if normalized_source_type not in {item.value for item in DataSourceType}:
            raise ValueError("source_type must be one of: rss, x, rest_api, telegram_group, v2ex")

        normalized_name = str(self.name).strip()
        if not normalized_name:
            raise ValueError("name is required")

        self.purpose = normalized_purpose
        self.source_type = normalized_source_type
        self.name = normalized_name
        self.tags = _normalize_datasource_tags(self.tags)
        self.config_payload = _validate_public_payload(
            dict(self.config_payload or {}), "config_payload"
        )

    @property
    def unique_key(self) -> tuple[str, str, str]:
        return (self.purpose, self.source_type, self.name)

    @classmethod
    def create(
        cls,
        name: str,
        source_type: str,
        purpose: str,
        tags: Optional[List[str]] = None,
        config_payload: Optional[Dict[str, Any]] = None,
    ) -> "DataSource":
        now = datetime.utcnow()
        return cls(
            id=str(uuid.uuid4()),
            purpose=purpose,
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
            "purpose": self.purpose,
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
            purpose=data["purpose"],
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
class IntelligenceTopic:
    id: str
    name: str
    is_active: bool = True
    lifecycle_status: str = TopicLifecycleStatus.ACTIVE.value
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def __post_init__(self):
        if not self.id:
            raise ValueError("id is required")
        self.name = str(self.name).strip()
        if not self.name:
            raise ValueError("name is required")
        self.lifecycle_status = str(self.lifecycle_status).strip().lower()
        if self.lifecycle_status not in _TOPIC_LIFECYCLE_STATUS_VALUES:
            raise ValueError("lifecycle_status must be one of: draft, active, paused, archived")
        self.is_active = bool(self.is_active)
        if self.lifecycle_status in {
            TopicLifecycleStatus.DRAFT.value,
            TopicLifecycleStatus.PAUSED.value,
            TopicLifecycleStatus.ARCHIVED.value,
        }:
            self.is_active = False
        elif self.lifecycle_status == TopicLifecycleStatus.ACTIVE.value:
            self.is_active = True

    @classmethod
    def create(
        cls,
        name: str,
        **kwargs: Any,
    ) -> "IntelligenceTopic":
        now = datetime.utcnow()
        return cls(
            id=str(uuid.uuid4()),
            name=name,
            created_at=now,
            updated_at=now,
            **kwargs,
        )

    def to_dict(self) -> Dict[str, Any]:
        data = dict(self.__dict__)
        for key in ("created_at", "updated_at"):
            data[key] = data[key].isoformat() if data.get(key) else None
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "IntelligenceTopic":
        allowed = {"id", "name", "is_active", "lifecycle_status", "created_at", "updated_at"}
        payload = {key: value for key, value in dict(data).items() if key in allowed}
        for key in ("created_at", "updated_at"):
            payload[key] = _parse_optional_datetime(payload.get(key))
        payload.setdefault(
            "lifecycle_status",
            TopicLifecycleStatus.ACTIVE.value if payload.get("is_active", True) else TopicLifecycleStatus.PAUSED.value,
        )
        return cls(**payload)


@dataclass
class TopicPrompt:
    id: str
    intelligence_topic_id: str
    prompt_version: str
    prompt_text: str
    schema_version: str
    status: str = TopicPromptStatus.DRAFT.value
    created_by: Optional[str] = None
    activated_by: Optional[str] = None
    activation_notes: Optional[str] = None
    audit_history: List[Dict[str, Any]] = field(default_factory=list)
    created_at: Optional[datetime] = None
    activated_at: Optional[datetime] = None
    archived_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def __post_init__(self):
        if not self.id:
            raise ValueError("id is required")
        self.intelligence_topic_id = str(self.intelligence_topic_id).strip()
        if not self.intelligence_topic_id:
            raise ValueError("intelligence_topic_id is required")
        self.prompt_version = str(self.prompt_version).strip()
        if not self.prompt_version:
            raise ValueError("prompt_version is required")
        self.prompt_text = str(self.prompt_text).strip()
        if not self.prompt_text:
            raise ValueError("prompt_text is required")
        self.schema_version = str(self.schema_version).strip()
        if not self.schema_version:
            raise ValueError("schema_version is required")
        self.status = str(self.status).strip().lower()
        if self.status not in _TOPIC_PROMPT_STATUS_VALUES:
            raise ValueError("status must be one of: draft, active, archived")
        self.audit_history = _validate_public_object_list(self.audit_history, "audit_history")

    @classmethod
    def create(cls, intelligence_topic_id: str, prompt_version: str, prompt_text: str, schema_version: str, **kwargs: Any) -> "TopicPrompt":
        now = datetime.utcnow()
        return cls(
            id=str(uuid.uuid4()),
            intelligence_topic_id=intelligence_topic_id,
            prompt_version=prompt_version,
            prompt_text=prompt_text,
            schema_version=schema_version,
            created_at=now,
            updated_at=now,
            **kwargs,
        )

    def to_dict(self) -> Dict[str, Any]:
        data = dict(self.__dict__)
        for key in ("created_at", "activated_at", "archived_at", "updated_at"):
            data[key] = data[key].isoformat() if data.get(key) else None
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TopicPrompt":
        payload = dict(data)
        for key in ("created_at", "activated_at", "archived_at", "updated_at"):
            payload[key] = _parse_optional_datetime(payload.get(key))
        payload["audit_history"] = _validate_public_object_list(payload.get("audit_history", []), "audit_history")
        return cls(**payload)


@dataclass
class TopicFinding:
    id: str
    intelligence_topic_id: str
    prompt_version_id: str
    finding_payload: Dict[str, Any]
    content_hash: str
    status: str = TopicFindingStatus.ACTIVE.value
    citations: List[Dict[str, Any]] = field(default_factory=list)
    source_raw_item_ids: List[str] = field(default_factory=list)
    source_finding_ids: List[str] = field(default_factory=list)
    confidence: float = 0.0
    found_at: Optional[datetime] = None
    archived_at: Optional[datetime] = None
    superseded_by_finding_id: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def __post_init__(self):
        if not self.id:
            raise ValueError("id is required")
        self.intelligence_topic_id = str(self.intelligence_topic_id).strip()
        if not self.intelligence_topic_id:
            raise ValueError("intelligence_topic_id is required")
        self.prompt_version_id = str(self.prompt_version_id).strip()
        if not self.prompt_version_id:
            raise ValueError("prompt_version_id is required")
        self.status = str(self.status).strip().lower()
        if self.status not in _TOPIC_FINDING_STATUS_VALUES:
            raise ValueError("status must be one of: active, archived, superseded")
        self.finding_payload = _validate_public_payload(dict(self.finding_payload or {}), "finding_payload")
        if not self.finding_payload:
            raise ValueError("finding_payload is required")
        self.citations = _validate_public_object_list(self.citations, "citations")
        self.source_raw_item_ids = _validate_json_list(self.source_raw_item_ids, "source_raw_item_ids")
        self.source_finding_ids = _validate_json_list(self.source_finding_ids, "source_finding_ids")
        self.content_hash = str(self.content_hash).strip()
        if not self.content_hash:
            raise ValueError("content_hash is required")
        self.confidence = float(self.confidence)
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0")
        if self.status == TopicFindingStatus.SUPERSEDED.value and not self.superseded_by_finding_id:
            raise ValueError("superseded_by_finding_id is required for superseded findings")

    @classmethod
    def create(cls, intelligence_topic_id: str, prompt_version_id: str, finding_payload: Dict[str, Any], content_hash: str, **kwargs: Any) -> "TopicFinding":
        now = datetime.utcnow()
        return cls(
            id=str(uuid.uuid4()),
            intelligence_topic_id=intelligence_topic_id,
            prompt_version_id=prompt_version_id,
            finding_payload=finding_payload,
            content_hash=content_hash,
            found_at=kwargs.pop("found_at", now),
            created_at=now,
            updated_at=now,
            **kwargs,
        )

    def to_dict(self) -> Dict[str, Any]:
        data = dict(self.__dict__)
        for key in ("found_at", "archived_at", "created_at", "updated_at"):
            data[key] = data[key].isoformat() if data.get(key) else None
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TopicFinding":
        payload = dict(data)
        for key in ("found_at", "archived_at", "created_at", "updated_at"):
            payload[key] = _parse_optional_datetime(payload.get(key))
        return cls(**payload)


@dataclass
class TopicResearchRun:
    id: str
    intelligence_topic_id: str
    status: str
    prompt_version_id: Optional[str] = None
    checkpoint_cursor: Optional[str] = None
    checkpoint_payload: Dict[str, Any] = field(default_factory=dict)
    items_scanned: int = 0
    findings_created: int = 0
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    _ALLOWED_STATUSES: ClassVar[frozenset[str]] = frozenset({"queued", "running", "success", "failed", "cancelled"})

    def __post_init__(self):
        if not self.id:
            raise ValueError("id is required")
        self.intelligence_topic_id = str(self.intelligence_topic_id).strip()
        if not self.intelligence_topic_id:
            raise ValueError("intelligence_topic_id is required")
        self.status = str(self.status).strip().lower()
        if self.status not in self._ALLOWED_STATUSES:
            raise ValueError("status must be one of: queued, running, success, failed, cancelled")
        self.checkpoint_payload = _validate_public_payload(dict(self.checkpoint_payload or {}), "checkpoint_payload")
        self.items_scanned = int(self.items_scanned)
        self.findings_created = int(self.findings_created)

    @classmethod
    def create(cls, intelligence_topic_id: str, status: str = "queued", **kwargs: Any) -> "TopicResearchRun":
        now = datetime.utcnow()
        return cls(id=str(uuid.uuid4()), intelligence_topic_id=intelligence_topic_id, status=status, started_at=kwargs.pop("started_at", now), created_at=now, updated_at=now, **kwargs)

    def to_dict(self) -> Dict[str, Any]:
        data = dict(self.__dict__)
        for key in ("started_at", "finished_at", "created_at", "updated_at"):
            data[key] = data[key].isoformat() if data.get(key) else None
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TopicResearchRun":
        payload = dict(data)
        for key in ("started_at", "finished_at", "created_at", "updated_at"):
            payload[key] = _parse_optional_datetime(payload.get(key))
        return cls(**payload)


@dataclass
class MergePreview:
    id: str
    intelligence_topic_id: str
    source_finding_ids: List[str]
    preview_payload: Dict[str, Any]
    content_hash: str
    expires_at: datetime
    state: str = MergePreviewState.PENDING.value
    created_by: Optional[str] = None
    applied_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def __post_init__(self):
        if not self.id:
            raise ValueError("id is required")
        self.intelligence_topic_id = str(self.intelligence_topic_id).strip()
        if not self.intelligence_topic_id:
            raise ValueError("intelligence_topic_id is required")
        self.source_finding_ids = _validate_json_list(self.source_finding_ids, "source_finding_ids")
        if len(self.source_finding_ids) < 2:
            raise ValueError("source_finding_ids must contain at least two findings")
        self.preview_payload = _validate_public_payload(dict(self.preview_payload or {}), "preview_payload")
        self.content_hash = str(self.content_hash).strip()
        if not self.content_hash:
            raise ValueError("content_hash is required")
        self.expires_at = _parse_optional_datetime(self.expires_at) or datetime.utcnow()
        self.state = str(self.state).strip().lower()
        if self.state not in _MERGE_PREVIEW_STATE_VALUES:
            raise ValueError("state must be one of: pending, applied, expired, cancelled")

    @classmethod
    def create(cls, intelligence_topic_id: str, source_finding_ids: List[str], preview_payload: Dict[str, Any], content_hash: str, expires_at: datetime, **kwargs: Any) -> "MergePreview":
        now = datetime.utcnow()
        return cls(id=str(uuid.uuid4()), intelligence_topic_id=intelligence_topic_id, source_finding_ids=source_finding_ids, preview_payload=preview_payload, content_hash=content_hash, expires_at=expires_at, created_at=now, updated_at=now, **kwargs)

    def to_dict(self) -> Dict[str, Any]:
        data = dict(self.__dict__)
        for key in ("expires_at", "applied_at", "created_at", "updated_at"):
            data[key] = data[key].isoformat() if data.get(key) else None
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MergePreview":
        payload = dict(data)
        for key in ("expires_at", "applied_at", "created_at", "updated_at"):
            payload[key] = _parse_optional_datetime(payload.get(key))
        return cls(**payload)


@dataclass
class FindingArchive:
    finding_id: str
    intelligence_topic_id: str
    archive_reason: Optional[str] = None
    archive_metadata: Dict[str, Any] = field(default_factory=dict)
    superseded_by_finding_id: Optional[str] = None
    archived_by: Optional[str] = None
    archived_at: Optional[datetime] = None

    def __post_init__(self):
        self.finding_id = str(self.finding_id).strip()
        if not self.finding_id:
            raise ValueError("finding_id is required")
        self.intelligence_topic_id = str(self.intelligence_topic_id).strip()
        if not self.intelligence_topic_id:
            raise ValueError("intelligence_topic_id is required")
        self.archive_metadata = _validate_public_payload(dict(self.archive_metadata or {}), "archive_metadata")

    @classmethod
    def create(cls, finding_id: str, intelligence_topic_id: str, **kwargs: Any) -> "FindingArchive":
        return cls(finding_id=finding_id, intelligence_topic_id=intelligence_topic_id, archived_at=kwargs.pop("archived_at", datetime.utcnow()), **kwargs)

    def to_dict(self) -> Dict[str, Any]:
        data = dict(self.__dict__)
        data["archived_at"] = self.archived_at.isoformat() if self.archived_at else None
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FindingArchive":
        payload = dict(data)
        payload["archived_at"] = _parse_optional_datetime(payload.get("archived_at"))
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
