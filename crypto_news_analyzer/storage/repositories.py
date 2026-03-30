"""
SQLite Repository Implementations

Concrete implementations of domain repository interfaces using SQLite.
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
        """Save or update an AnalysisRequest - will be implemented with new table"""
        # TODO: Implement when migrating to analysis_jobs table (Task 6)
        pass
    
    def get_by_id(self, request_id: str) -> Optional[AnalysisRequest]:
        """Get AnalysisRequest by ID"""
        # TODO: Implement when migrating to analysis_jobs table (Task 6)
        return None
    
    def get_by_recipient(
        self,
        recipient_key: str,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> List[AnalysisRequest]:
        """Get AnalysisRequests for a recipient"""
        # TODO: Implement when migrating to analysis_jobs table (Task 6)
        return []
    
    def get_pending_jobs(
        self,
        limit: int = 10,
        min_priority: int = 1,
    ) -> List[AnalysisRequest]:
        """Get pending jobs sorted by priority"""
        # TODO: Implement when migrating to analysis_jobs table (Task 6)
        return []
    
    def update_status(
        self,
        request_id: str,
        status: str,
        error_message: Optional[str] = None,
    ) -> bool:
        """Update job status"""
        # TODO: Implement when migrating to analysis_jobs table (Task 6)
        return False
    
    def complete_job(
        self,
        request_id: str,
        result: Dict[str, Any],
    ) -> bool:
        """Mark job as completed with result"""
        # TODO: Implement when migrating to analysis_jobs table (Task 6)
        return False
    
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
        # TODO: Implement when migrating to ingestion_jobs table (Task 7)
        pass
    
    def get_by_id(self, job_id: str) -> Optional[IngestionJob]:
        """Get IngestionJob by ID"""
        # TODO: Implement when migrating to ingestion_jobs table (Task 7)
        return None
    
    def get_by_source(
        self,
        source_type: str,
        source_name: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> List[IngestionJob]:
        """Get IngestionJobs for a source"""
        # TODO: Implement when migrating to ingestion_jobs table (Task 7)
        return []
    
    def get_pending_jobs(self, limit: int = 10) -> List[IngestionJob]:
        """Get pending ingestion jobs"""
        # TODO: Implement when migrating to ingestion_jobs table (Task 7)
        return []
    
    def update_status(
        self,
        job_id: str,
        status: str,
        error_message: Optional[str] = None,
    ) -> bool:
        """Update job status"""
        # TODO: Implement when migrating to ingestion_jobs table (Task 7)
        return False
    
    def complete_job(
        self,
        job_id: str,
        items_crawled: int,
        items_new: int,
    ) -> bool:
        """Mark job as completed with statistics"""
        # TODO: Implement when migrating to ingestion_jobs table (Task 7)
        return False
    
    def get_statistics(
        self,
        since: datetime,
        source_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get ingestion statistics"""
        # TODO: Implement when migrating to ingestion_jobs table (Task 7)
        return {
            "total_jobs": 0,
            "completed_jobs": 0,
            "failed_jobs": 0,
            "total_items_crawled": 0,
            "total_items_new": 0,
        }


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
        items = self._data.get_content_items_since(
            since=start_time,
            source_type=source_type,
            source_name=source_name,
        )
        return [item.to_dict() for item in items if item.publish_time <= end_time]
    
    def exists_by_hash(self, content_hash: str) -> bool:
        """Check if content with given hash already exists"""
        return self._data.check_content_hash_exists(content_hash)
    
    def get_count_since(
        self,
        since: datetime,
        source_type: Optional[str] = None,
    ) -> int:
        """Get count of items since timestamp"""
        items = self._data.get_content_items_since(
            since=since,
            source_type=source_type,
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
        return self._cache.cleanup_expired_cache(hours=hours)


class RepositoryFactory:
    """Factory for creating repository instances"""
    
    @staticmethod
    def create_repositories(storage_config: StorageConfig) -> Dict[str, Any]:
        """
        Create all repository instances with shared storage backend
        
        Returns:
            Dictionary with repository instances:
            - analysis: AnalysisRepository
            - ingestion: IngestionRepository
            - content: ContentRepository
            - cache: CacheRepository
        """
        data_manager = DataManager(storage_config)
        cache_manager = SentMessageCacheManager(storage_config)
        
        return {
            "analysis": SQLiteAnalysisRepository(data_manager),
            "ingestion": SQLiteIngestionRepository(data_manager),
            "content": SQLiteContentRepository(data_manager),
            "cache": SQLiteCacheRepository(cache_manager),
            # Keep original managers for backward compatibility during transition
            "_data_manager": data_manager,
            "_cache_manager": cache_manager,
        }
