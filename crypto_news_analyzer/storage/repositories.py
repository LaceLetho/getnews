"""
Repository Implementations

Concrete implementations of domain repository interfaces.
These adapters wrap the existing DataManager and CacheManager.
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

from ..domain.models import AnalysisRequest, IngestionJob, JobStatus, IngestionJobStatus
from ..domain.repositories import (
    AnalysisRepository,
    IngestionRepository,
    ContentRepository,
    CacheRepository,
)
from ..storage.data_manager import DataManager
from ..storage.cache_manager import SentMessageCacheManager
from ..models import StorageConfig


class SQLiteAnalysisRepository(AnalysisRepository):
    """SQLite implementation of AnalysisRepository"""

    def __init__(self, data_manager: DataManager):
        self._data = data_manager

    def save(self, request: AnalysisRequest) -> None:
        self._data.upsert_analysis_job(
            request_id=request.id,
            recipient_key=request.recipient_key,
            time_window_hours=request.time_window_hours,
            created_at=request.created_at,
            status=request.status,
            priority=request.priority,
            source=request.source,
            started_at=request.started_at,
            completed_at=request.completed_at,
            result=request.result,
            error_message=request.error_message,
        )

    def get_by_id(self, request_id: str) -> Optional[AnalysisRequest]:
        payload = self._data.get_analysis_job_by_id(request_id)
        if payload is None:
            return None
        return AnalysisRequest.from_dict(payload)

    def get_by_recipient(
        self,
        recipient_key: str,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> List[AnalysisRequest]:
        rows = self._data.get_analysis_jobs_by_recipient(
            recipient_key=recipient_key,
            status=status,
            limit=limit,
        )
        return [AnalysisRequest.from_dict(row) for row in rows]

    def get_pending_jobs(
        self,
        limit: int = 10,
        min_priority: int = 1,
    ) -> List[AnalysisRequest]:
        rows = self._data.get_pending_analysis_jobs(
            limit=limit,
            min_priority=min_priority,
        )
        return [AnalysisRequest.from_dict(row) for row in rows]

    def update_status(
        self,
        request_id: str,
        status: str,
        error_message: Optional[str] = None,
    ) -> bool:
        return self._data.update_analysis_job_status(
            request_id=request_id,
            status=status,
            error_message=error_message,
        )

    def complete_job(
        self,
        request_id: str,
        result: Dict[str, Any],
    ) -> bool:
        return self._data.complete_analysis_job(
            request_id=request_id,
            result=result,
        )

    def get_last_successful_analysis(
        self,
        recipient_key: str,
    ) -> Optional[datetime]:
        """Get timestamp of last successful analysis for recipient"""
        return self._data.get_last_successful_analysis_time(recipient_key)


class SQLiteIngestionRepository(IngestionRepository):
    """SQLite implementation of IngestionRepository"""

    def __init__(self, data_manager: DataManager):
        self._data = data_manager

    def save(self, job: IngestionJob) -> None:
        """Save or update an IngestionJob"""
        self._data.upsert_ingestion_job(
            job_id=job.id,
            source_type=job.source_type,
            source_name=job.source_name,
            scheduled_at=job.scheduled_at,
            status=job.status,
            started_at=job.started_at,
            completed_at=job.completed_at,
            items_crawled=job.items_crawled,
            items_new=job.items_new,
            error_message=job.error_message,
            metadata=job.metadata,
        )

    def get_by_id(self, job_id: str) -> Optional[IngestionJob]:
        """Get IngestionJob by ID"""
        payload = self._data.get_ingestion_job_by_id(job_id)
        if payload is None:
            return None
        return IngestionJob.from_dict(payload)

    def get_by_source(
        self,
        source_type: str,
        source_name: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> List[IngestionJob]:
        """Get IngestionJobs for a source"""
        rows = self._data.get_ingestion_jobs_by_source(
            source_type=source_type,
            source_name=source_name,
            status=status,
            limit=limit,
        )
        return [IngestionJob.from_dict(row) for row in rows]

    def get_pending_jobs(self, limit: int = 10) -> List[IngestionJob]:
        """Get pending ingestion jobs"""
        rows = self._data.get_pending_ingestion_jobs(limit=limit)
        return [IngestionJob.from_dict(row) for row in rows]

    def update_status(
        self,
        job_id: str,
        status: str,
        error_message: Optional[str] = None,
    ) -> bool:
        """Update job status"""
        return self._data.update_ingestion_job_status(
            job_id=job_id,
            status=status,
            error_message=error_message,
        )

    def complete_job(
        self,
        job_id: str,
        items_crawled: int,
        items_new: int,
    ) -> bool:
        """Mark job as completed with statistics"""
        return self._data.complete_ingestion_job(
            job_id=job_id,
            items_crawled=items_crawled,
            items_new=items_new,
        )

    def get_statistics(
        self,
        since: datetime,
        source_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get ingestion statistics"""
        return self._data.get_ingestion_job_statistics(
            since=since,
            source_type=source_type,
        )


class SQLiteContentRepository(ContentRepository):
    """SQLite implementation of ContentRepository"""

    def __init__(self, data_manager: DataManager):
        self._data = data_manager

    def save(self, content: Dict[str, Any]) -> bool:
        """Save content item if not duplicate"""
        from ..models import ContentItem

        try:
            item = ContentItem.from_dict(content)
            self._data.add_content_items([item])
            return True
        except Exception:
            return False

    def get_by_time_range(
        self,
        start_time: datetime,
        end_time: datetime,
        source_type: Optional[str] = None,
        source_name: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get content items within time range"""
        if start_time.tzinfo is None:
            from datetime import timezone

            start_time = start_time.replace(tzinfo=timezone.utc)
        if end_time.tzinfo is None:
            from datetime import timezone

            end_time = end_time.replace(tzinfo=timezone.utc)

        max_hours = max(1, int((end_time - start_time).total_seconds() // 3600) + 1)
        source_types = [source_type] if source_type else None
        items = self._data.get_content_items_since(
            since_time=start_time,
            max_hours=max_hours,
            source_types=source_types,
        )
        from datetime import timezone

        filtered_items = []
        for item in items:
            item_time = item.publish_time
            if item_time.tzinfo is None:
                item_time = item_time.replace(tzinfo=timezone.utc)
            if item_time <= end_time:
                filtered_items.append(item)
        if source_name:
            filtered_items = [item for item in filtered_items if item.source_name == source_name]
        return [item.to_dict() for item in filtered_items]

    def exists_by_hash(self, content_hash: str) -> bool:
        """Check if content with given hash already exists"""
        return self._data.check_content_hash_exists(content_hash)

    def get_count_since(
        self,
        since: datetime,
        source_type: Optional[str] = None,
    ) -> int:
        """Get count of items since timestamp"""
        source_types = [source_type] if source_type else None
        items = self._data.get_content_items_since(
            since_time=since,
            source_types=source_types,
        )
        return len(items)


class SQLiteCacheRepository(CacheRepository):
    """SQLite implementation of CacheRepository"""

    def __init__(self, cache_manager: SentMessageCacheManager):
        self._cache = cache_manager

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
        message = {
            "title": title,
            "body": body,
            "category": category,
            "time": sent_at.isoformat(),
        }
        if metadata:
            message.update(metadata)

        self._cache.cache_sent_messages([message], recipient_key=recipient_key)

    def get_titles_since(
        self,
        recipient_key: str,
        since: datetime,
    ) -> List[str]:
        """Get titles of messages sent since timestamp"""
        return self._cache.get_recipient_cached_titles(recipient_key, anchor_time=since)

    def exists_by_title(
        self,
        recipient_key: str,
        title: str,
        since: datetime,
    ) -> bool:
        """Check if message with title was already sent since timestamp"""
        titles = self.get_titles_since(recipient_key, since)
        return title in titles

    def cleanup_expired(self, before: datetime) -> int:
        """Remove cache entries older than timestamp"""
        hours = (datetime.utcnow() - before).total_seconds() / 3600
        return self._cache.cleanup_expired_cache(hours=max(0, int(hours)))


class RepositoryFactory:
    """Factory for creating repository instances"""

    @staticmethod
    def create_repositories(
        storage_config: StorageConfig,
        data_manager: Optional[DataManager] = None,
        cache_manager: Optional[SentMessageCacheManager] = None,
    ) -> Dict[str, Any]:
        """
        Create all repository instances with shared storage backend

        Args:
            storage_config: Storage configuration
            data_manager: Optional existing DataManager instance to reuse
            cache_manager: Optional existing SentMessageCacheManager instance to reuse

        Returns:
            Dictionary with repository instances:
            - analysis: AnalysisRepository
            - ingestion: IngestionRepository
            - content: ContentRepository
            - cache: CacheRepository
        """
        backend = storage_config.backend
        if data_manager is None:
            data_manager = DataManager(storage_config)
        if cache_manager is None:
            cache_manager = SentMessageCacheManager(storage_config)

        return {
            "analysis": SQLiteAnalysisRepository(data_manager),
            "ingestion": SQLiteIngestionRepository(data_manager),
            "content": SQLiteContentRepository(data_manager),
            "cache": SQLiteCacheRepository(cache_manager),
            # Keep original managers for backward compatibility during transition
            "_data_manager": data_manager,
            "_cache_manager": cache_manager,
            "_backend": backend,
        }
