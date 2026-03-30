"""
Shared Domain Contracts

This package defines the shared domain contracts between services in the Railway
split architecture. These contracts must remain stable across service boundaries.

Version: 1.0.0
Compatibility: Backward compatible within major version
"""

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any
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
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else None,
            status=data.get("status", JobStatus.PENDING.value),
            priority=data.get("priority", Priority.NORMAL.value),
            started_at=datetime.fromisoformat(data["started_at"]) if data.get("started_at") else None,
            completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
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
            scheduled_at=datetime.fromisoformat(data["scheduled_at"]) if data.get("scheduled_at") else None,
            status=data.get("status", IngestionJobStatus.PENDING.value),
            started_at=datetime.fromisoformat(data["started_at"]) if data.get("started_at") else None,
            completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
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
