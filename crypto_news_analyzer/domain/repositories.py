"""
Repository Interfaces - Shared Domain Contracts

Abstract base classes defining the storage operations that can be implemented
by different backends (SQLite, PostgreSQL, etc.).

Version: 1.0.0
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Optional, Dict, Any, Tuple

from .models import (
    AnalysisRequest,
    CanonicalIntelligenceEntry,
    DataSource,
    ExtractionObservation,
    IngestionJob,
    IntelligenceCrawlCheckpoint,
    RawIntelligenceItem,
    SemanticSearchJob,
)


class AnalysisRepository(ABC):
    """
    Abstract repository for AnalysisRequest entities.

    Implementations must handle:
    - Job persistence with status transitions
    - Querying jobs by recipient, status, time range
    - Concurrent access (if applicable)
    """

    @abstractmethod
    def save(self, request: AnalysisRequest) -> None:
        """Save or update an AnalysisRequest"""
        pass

    @abstractmethod
    def get_by_id(self, request_id: str) -> Optional[AnalysisRequest]:
        """Get AnalysisRequest by ID"""
        pass

    @abstractmethod
    def get_by_recipient(
        self,
        recipient_key: str,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> List[AnalysisRequest]:
        """
        Get AnalysisRequests for a recipient

        Args:
            recipient_key: The recipient identifier
            status: Filter by status (optional)
            limit: Maximum results to return
        """
        pass

    @abstractmethod
    def get_pending_jobs(
        self,
        limit: int = 10,
        min_priority: int = 1,
    ) -> List[AnalysisRequest]:
        """
        Get pending jobs sorted by priority and creation time

        Args:
            limit: Maximum jobs to return
            min_priority: Minimum priority level
        """
        pass

    @abstractmethod
    def update_status(
        self,
        request_id: str,
        status: str,
        error_message: Optional[str] = None,
    ) -> bool:
        """
        Update job status

        Args:
            request_id: Job ID
            status: New status value
            error_message: Error message (for failed status)

        Returns:
            True if update succeeded
        """
        pass

    @abstractmethod
    def complete_job(
        self,
        request_id: str,
        result: Dict[str, Any],
    ) -> bool:
        """
        Mark job as completed with result

        Args:
            request_id: Job ID
            result: Analysis result data

        Returns:
            True if update succeeded
        """
        pass

    @abstractmethod
    def get_last_successful_analysis(
        self,
        recipient_key: str,
    ) -> Optional[datetime]:
        """
        Get timestamp of last successful analysis for recipient

        Used for calculating time windows in subsequent analyses.
        """
        pass

    @abstractmethod
    def log_execution(
        self,
        recipient_key: str,
        time_window_hours: int,
        items_count: int,
        success: bool,
        error_message: Optional[str] = None,
    ) -> None:
        pass


class IngestionRepository(ABC):
    """
    Abstract repository for IngestionJob entities.

    Implementations must handle:
    - Job persistence with status transitions
    - Querying jobs by source, status, time range
    - Aggregation for statistics
    """

    @abstractmethod
    def save(self, job: IngestionJob) -> None:
        """Save or update an IngestionJob"""
        pass

    @abstractmethod
    def get_by_id(self, job_id: str) -> Optional[IngestionJob]:
        """Get IngestionJob by ID"""
        pass

    @abstractmethod
    def get_by_source(
        self,
        source_type: str,
        source_name: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> List[IngestionJob]:
        """
        Get IngestionJobs for a source

        Args:
            source_type: Source type ("rss", "x", "api")
            source_name: Specific source name (optional)
            status: Filter by status (optional)
            limit: Maximum results to return
        """
        pass

    @abstractmethod
    def get_pending_jobs(self, limit: int = 10) -> List[IngestionJob]:
        """Get pending ingestion jobs"""
        pass

    @abstractmethod
    def update_status(
        self,
        job_id: str,
        status: str,
        error_message: Optional[str] = None,
    ) -> bool:
        """Update job status"""
        pass

    @abstractmethod
    def complete_job(
        self,
        job_id: str,
        items_crawled: int,
        items_new: int,
    ) -> bool:
        """
        Mark job as completed with statistics

        Args:
            job_id: Job ID
            items_crawled: Total items crawled
            items_new: New (non-duplicate) items
        """
        pass

    @abstractmethod
    def get_statistics(
        self,
        since: datetime,
        source_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get ingestion statistics

        Args:
            since: Start time for statistics
            source_type: Filter by source type (optional)

        Returns:
            Dictionary with statistics:
            - total_jobs
            - completed_jobs
            - failed_jobs
            - total_items_crawled
            - total_items_new
        """
        pass


class ContentRepository(ABC):
    """
    Abstract repository for content items.

    Implementations must handle:
    - Content deduplication (by hash)
    - Time-range queries for analysis
    - Source filtering
    """

    @abstractmethod
    def save(self, content: Dict[str, Any]) -> bool:
        """
        Save content item if not duplicate

        Returns:
            True if saved (not duplicate), False if duplicate
        """
        pass

    @abstractmethod
    def get_by_time_range(
        self,
        start_time: datetime,
        end_time: datetime,
        source_type: Optional[str] = None,
        source_name: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get content items within time range

        Args:
            start_time: Start of time range (inclusive)
            end_time: End of time range (inclusive)
            source_type: Filter by source type (optional)
            source_name: Filter by source name (optional)
        """
        pass

    @abstractmethod
    def exists_by_hash(self, content_hash: str) -> bool:
        """Check if content with given hash already exists"""
        pass

    @abstractmethod
    def get_count_since(
        self,
        since: datetime,
        source_type: Optional[str] = None,
    ) -> int:
        """Get count of items since timestamp"""
        pass

    @abstractmethod
    def save_many(self, items: List[Any]) -> int:
        pass

    @abstractmethod
    def deduplicate(self) -> int:
        pass

    @abstractmethod
    def save_crawl_status(self, crawl_status: Any) -> None:
        pass

    @abstractmethod
    def get_recent_content_items(
        self,
        time_window_hours: Optional[int] = None,
        source_types: Optional[List[str]] = None,
        limit: Optional[int] = None,
    ) -> List[Any]:
        pass

    @abstractmethod
    def get_content_items_since(
        self,
        since_time: datetime,
        max_hours: Optional[int] = None,
        source_types: Optional[List[str]] = None,
        limit: Optional[int] = None,
    ) -> List[Any]:
        pass

    @abstractmethod
    def fetch_rows_missing_embeddings(self, limit: int) -> List[Any]:
        pass

    @abstractmethod
    def persist_embedding(self, content_id: str, embedding: List[float], model: str) -> bool:
        pass

    @abstractmethod
    def semantic_search_by_similarity(
        self,
        query_embedding: List[float],
        since_time: datetime,
        max_hours: int,
        limit: int,
    ) -> List[Tuple[Any, float]]:
        pass

    @abstractmethod
    def semantic_search_by_keywords(
        self,
        keyword_queries: List[str],
        since_time: datetime,
        max_hours: int,
        limit: int,
    ) -> List[Tuple[Any, float]]:
        pass


class SemanticSearchRepository(ABC):
    @abstractmethod
    def create_semantic_search_job(self, job: SemanticSearchJob) -> None:
        pass

    @abstractmethod
    def update_semantic_search_job(self, job: SemanticSearchJob) -> bool:
        pass

    @abstractmethod
    def get_by_id(self, job_id: str) -> Optional[SemanticSearchJob]:
        pass

    @abstractmethod
    def get_by_recipient(
        self,
        recipient_key: str,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> List[SemanticSearchJob]:
        pass


class DataSourceRepository(ABC):
    @abstractmethod
    def save(self, datasource: DataSource) -> DataSource:
        pass

    @abstractmethod
    def get_by_id(self, datasource_id: str) -> Optional[DataSource]:
        pass

    @abstractmethod
    def get_by_type_and_name(self, source_type: str, name: str) -> Optional[DataSource]:
        pass

    @abstractmethod
    def list(self, source_type: Optional[str] = None) -> List[DataSource]:
        pass

    @abstractmethod
    def delete(self, datasource_id: str) -> bool:
        pass


class IntelligenceRepository(ABC):
    @abstractmethod
    def save_raw_item(self, raw_item: RawIntelligenceItem) -> str:
        pass

    @abstractmethod
    def get_raw_items_by_source(
        self, source_type: str, source_id: str, limit: int, offset: int
    ) -> List[RawIntelligenceItem]:
        pass

    @abstractmethod
    def get_raw_items_expiring_before(self, cutoff_time: datetime) -> List[RawIntelligenceItem]:
        pass

    @abstractmethod
    def get_raw_item_by_id(self, raw_item_id: str) -> Optional[RawIntelligenceItem]:
        pass

    @abstractmethod
    def delete_expired_raw_items(self, cutoff_time: datetime) -> int:
        pass

    @abstractmethod
    def purge_raw_text_older_than(self, cutoff_time: datetime) -> int:
        pass

    @abstractmethod
    def save_observation(self, observation: ExtractionObservation) -> str:
        pass

    @abstractmethod
    def get_observations_by_raw_item(self, raw_item_id: str) -> List[ExtractionObservation]:
        pass

    @abstractmethod
    def get_uncanonicalized_observations(self, limit: int) -> List[ExtractionObservation]:
        pass

    @abstractmethod
    def mark_observation_canonicalized(self, observation_id: str) -> bool:
        pass

    @abstractmethod
    def save_canonical_entry(self, entry: CanonicalIntelligenceEntry) -> str:
        pass

    @abstractmethod
    def get_canonical_entry_by_normalized_key(
        self, entry_type: str, normalized_key: str
    ) -> Optional[CanonicalIntelligenceEntry]:
        pass

    @abstractmethod
    def get_canonical_entry_by_id(self, entry_id: str) -> Optional[CanonicalIntelligenceEntry]:
        pass

    @abstractmethod
    def upsert_canonical_entry(self, entry: CanonicalIntelligenceEntry) -> str:
        pass

    @abstractmethod
    def list_canonical_entries(
        self,
        entry_type: Optional[str] = None,
        primary_label: Optional[str] = None,
        window: Optional[datetime] = None,
        page: int = 1,
        page_size: int = 100,
    ) -> List[CanonicalIntelligenceEntry]:
        pass

    @abstractmethod
    def count_canonical_entries(
        self,
        entry_type: Optional[str] = None,
        primary_label: Optional[str] = None,
        window: Optional[datetime] = None,
    ) -> int:
        pass

    @abstractmethod
    def update_embedding(self, entry_id: str, embedding: List[float], model: str) -> bool:
        pass

    @abstractmethod
    def get_entries_missing_embeddings(self, limit: int) -> List[CanonicalIntelligenceEntry]:
        pass

    @abstractmethod
    def semantic_search(
        self,
        query_embedding: List[float],
        entry_type: Optional[str] = None,
        primary_label: Optional[str] = None,
        window: Optional[datetime] = None,
        limit: int = 20,
    ) -> List[Tuple[CanonicalIntelligenceEntry, float]]:
        pass

    @abstractmethod
    def save_related_candidate(
        self,
        entry_id_a: str,
        entry_id_b: str,
        similarity_score: float,
        relationship_type: str,
    ) -> None:
        pass

    @abstractmethod
    def save_checkpoint(self, checkpoint: IntelligenceCrawlCheckpoint) -> None:
        pass

    @abstractmethod
    def get_checkpoint(
        self, source_type: str, source_id: str
    ) -> Optional[IntelligenceCrawlCheckpoint]:
        pass


class CacheRepository(ABC):
    """
    Abstract repository for cached sent messages.

    Used for deduplication across analysis runs.
    """

    @abstractmethod
    def save_sent_message(
        self,
        recipient_key: str,
        title: str,
        body: str,
        category: str,
        sent_at: datetime,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record a sent message for deduplication"""
        pass

    @abstractmethod
    def get_titles_since(
        self,
        recipient_key: str,
        since: datetime,
    ) -> List[str]:
        """
        Get titles of messages sent since timestamp

        Used to build historical_titles for deduplication.
        """
        pass

    @abstractmethod
    def exists_by_title(
        self,
        recipient_key: str,
        title: str,
        since: datetime,
    ) -> bool:
        """Check if message with title was already sent since timestamp"""
        pass

    @abstractmethod
    def cleanup_expired(self, before: datetime) -> int:
        """
        Remove cache entries older than timestamp

        Returns:
            Number of entries removed
        """
        pass

    @abstractmethod
    def cache_sent_messages(
        self,
        messages: List[Dict[str, Any]],
        recipient_key: Optional[str] = None,
    ) -> int:
        pass

    @abstractmethod
    def get_cache_statistics(self) -> Dict[str, Any]:
        pass
