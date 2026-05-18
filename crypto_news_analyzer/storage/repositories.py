# pyright: reportArgumentType=false, reportCallIssue=false
"""
Repository Implementations

Concrete implementations of domain repository interfaces.
These adapters wrap the existing DataManager and CacheManager.
"""

import json
from datetime import datetime
from typing import List, Optional, Dict, Any, Tuple, Set, cast

from ..domain.models import (
    AnalysisRequest,
    DataSource,
    DataSourceAlreadyExistsError,
    DataSourceInUseError,
    IngestionJob,
    IntelligenceCrawlCheckpoint,
    IntelligenceTopic,
    FindingArchive,
    MergePreview,
    RawIntelligenceItem,
    SemanticSearchJob,
    TopicFinding,
    TopicPrompt,
    TopicResearchRun,
)
from ..domain.repositories import (
    AnalysisRepository,
    DataSourceRepository,
    IngestionRepository,
    IntelligenceRepository,
    ContentRepository,
    CacheRepository,
    SemanticSearchRepository,
)
from ..storage.data_manager import DataManager
from ..storage.cache_manager import SentMessageCacheManager
from ..utils.errors import StorageError, UnsupportedBackendError
from ..models import StorageConfig, ContentItem, CrawlStatus


def _parse_optional_datetime(value: Any) -> Optional[datetime]:
    if value is None or isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value))


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

    def log_execution(
        self,
        recipient_key: str,
        time_window_hours: int,
        items_count: int,
        success: bool,
        error_message: Optional[str] = None,
    ) -> None:
        self._data.log_analysis_execution(
            chat_id=recipient_key,
            time_window_hours=time_window_hours,
            items_count=items_count,
            success=success,
            error_message=error_message,
        )


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

    def _unsupported(self, feature: str) -> UnsupportedBackendError:
        return UnsupportedBackendError("sqlite", feature)

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

    def save_many(self, items: List[ContentItem]) -> int:
        return self._data.add_content_items(items)

    def deduplicate(self) -> int:
        return self._data.deduplicate_content()

    def save_crawl_status(self, crawl_status: CrawlStatus) -> None:
        self._data.save_crawl_status(crawl_status)

    def get_recent_content_items(
        self,
        time_window_hours: Optional[int] = None,
        source_types: Optional[List[str]] = None,
        limit: Optional[int] = None,
    ) -> List[ContentItem]:
        return self._data.get_content_items(
            time_window_hours=time_window_hours,
            source_types=source_types,
            limit=limit,
        )

    def get_content_items_since(
        self,
        since_time: datetime,
        max_hours: Optional[int] = None,
        source_types: Optional[List[str]] = None,
        limit: Optional[int] = None,
    ) -> List[ContentItem]:
        return self._data.get_content_items_since(
            since_time=since_time,
            max_hours=cast(int, max_hours),
            source_types=source_types,
            limit=limit,
        )

    def fetch_rows_missing_embeddings(self, limit: int) -> List[ContentItem]:
        raise self._unsupported("semantic search embedding fetch")

    def persist_embedding(self, content_id: str, embedding: List[float], model: str) -> bool:
        raise self._unsupported("semantic search embedding persistence")

    def semantic_search_by_similarity(
        self,
        query_embedding: List[float],
        since_time: datetime,
        max_hours: int,
        limit: int,
    ) -> List[Tuple[ContentItem, float]]:
        raise self._unsupported("semantic search retrieval")

    def semantic_search_by_keywords(
        self,
        keyword_queries: List[str],
        since_time: datetime,
        max_hours: int,
        limit: int,
    ) -> List[Tuple[ContentItem, float]]:
        raise self._unsupported("semantic search keyword retrieval")


class PostgresContentRepository(SQLiteContentRepository):
    """PostgreSQL implementation of ContentRepository semantic APIs."""

    def fetch_rows_missing_embeddings(self, limit: int) -> List[ContentItem]:
        return self._data.get_content_items_missing_embeddings(limit=limit)

    def persist_embedding(self, content_id: str, embedding: List[float], model: str) -> bool:
        return self._data.update_content_embedding(
            content_id=content_id,
            embedding=embedding,
            model=model,
        )

    def semantic_search_by_similarity(
        self,
        query_embedding: List[float],
        since_time: datetime,
        max_hours: int,
        limit: int,
    ) -> List[Tuple[ContentItem, float]]:
        return self._data.semantic_search_similar(
            query_embedding=query_embedding,
            since_time=since_time,
            max_hours=max_hours,
            limit=limit,
        )

    def semantic_search_by_keywords(
        self,
        keyword_queries: List[str],
        since_time: datetime,
        max_hours: int,
        limit: int,
    ) -> List[Tuple[ContentItem, float]]:
        return self._data.semantic_search_keywords(
            keyword_queries=keyword_queries,
            since_time=since_time,
            max_hours=max_hours,
            limit=limit,
        )


class SQLiteSemanticSearchRepository(SemanticSearchRepository):
    def __init__(self, data_manager: DataManager):
        self._data = data_manager

    def _unsupported(self, feature: str) -> UnsupportedBackendError:
        return UnsupportedBackendError("sqlite", feature)

    def create_semantic_search_job(self, job: SemanticSearchJob) -> None:
        raise self._unsupported("semantic search job persistence")

    def update_semantic_search_job(self, job: SemanticSearchJob) -> bool:
        raise self._unsupported("semantic search job persistence")

    def get_by_id(self, job_id: str) -> Optional[SemanticSearchJob]:
        raise self._unsupported("semantic search job persistence")

    def get_by_recipient(
        self,
        recipient_key: str,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> List[SemanticSearchJob]:
        raise self._unsupported("semantic search job persistence")


class PostgresSemanticSearchRepository(SQLiteSemanticSearchRepository):
    def create_semantic_search_job(self, job: SemanticSearchJob) -> None:
        self._data.upsert_semantic_search_job(
            job_id=job.id,
            recipient_key=job.recipient_key,
            query=job.query,
            normalized_intent=job.normalized_intent,
            time_window_hours=job.time_window_hours,
            created_at=job.created_at,
            status=job.status,
            source=job.source,
            matched_count=job.matched_count,
            retained_count=job.retained_count,
            decomposition_json=job.decomposition_json,
            started_at=job.started_at,
            completed_at=job.completed_at,
            result=job.result,
            error_message=job.error_message,
        )

    def update_semantic_search_job(self, job: SemanticSearchJob) -> bool:
        existing = self._data.get_semantic_search_job_by_id(job.id)
        if existing is None:
            return False

        self.create_semantic_search_job(job)
        return True

    def get_by_id(self, job_id: str) -> Optional[SemanticSearchJob]:
        payload = self._data.get_semantic_search_job_by_id(job_id)
        if payload is None:
            return None
        return SemanticSearchJob.from_dict(payload)

    def get_by_recipient(
        self,
        recipient_key: str,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> List[SemanticSearchJob]:
        rows = self._data.get_semantic_search_jobs_by_recipient(
            recipient_key=recipient_key,
            status=status,
            limit=limit,
        )
        return [SemanticSearchJob.from_dict(row) for row in rows]


class SQLiteDataSourceRepository(DataSourceRepository):

    def __init__(self, data_manager: DataManager):
        self._data = data_manager

    def save(self, datasource: DataSource) -> DataSource:
        try:
            self._data.upsert_datasource(
                datasource_id=datasource.id,
                purpose=datasource.purpose,
                source_type=datasource.source_type,
                name=datasource.name,
                config_payload=datasource.config_payload,
                tags=datasource.tags,
                created_at=datasource.created_at,
            )
        except StorageError as exc:
            if self._is_datasource_uniqueness_error(exc):
                raise DataSourceAlreadyExistsError(
                    datasource.source_type,
                    datasource.name,
                    datasource.purpose,
                ) from exc
            raise

        loaded = self.get_by_id(datasource.id)
        if loaded is None:
            raise ValueError(f"datasource save failed: {datasource.id}")
        return loaded

    @staticmethod
    def _is_datasource_uniqueness_error(error: Exception) -> bool:
        message = str(error).lower()
        uniqueness_tokens = (
            "datasources.purpose, datasources.source_type, datasources.name",
            "duplicate key value violates unique constraint",
            "idx_datasources_purpose_source_name",
        )
        return any(token in message for token in uniqueness_tokens)

    def get_by_id(self, datasource_id: str) -> Optional[DataSource]:
        payload = self._data.get_datasource_by_id(datasource_id)
        if payload is None:
            return None
        return DataSource.from_dict(payload)

    def get_by_purpose_type_and_name(
        self, purpose: str, source_type: str, name: str
    ) -> Optional[DataSource]:
        payload = self._data.get_datasource_by_purpose_type_and_name(
            purpose=purpose,
            source_type=source_type,
            name=name,
        )
        if payload is None:
            return None
        return DataSource.from_dict(payload)

    def list(
        self,
        purpose: Optional[str] = None,
        source_type: Optional[str] = None,
    ) -> List[DataSource]:
        rows = self._data.list_datasources(purpose=purpose, source_type=source_type)
        return [DataSource.from_dict(row) for row in rows]

    def delete(self, datasource_id: str) -> bool:
        datasource = self.get_by_id(datasource_id)
        if datasource is None:
            return False

        active_job_ids = self._data.get_active_ingestion_job_ids_for_source(
            source_type=datasource.source_type,
            source_name=datasource.name,
        )
        if active_job_ids:
            raise DataSourceInUseError(
                source_type=datasource.source_type,
                source_name=datasource.name,
                active_job_ids=active_job_ids,
            )

        return self._data.delete_datasource(datasource_id)


class SQLiteIntelligenceRepository(IntelligenceRepository):
    def __init__(self, data_manager: DataManager):
        self._data = data_manager

    def save_raw_item(self, raw_item: RawIntelligenceItem) -> str:
        return self._data.upsert_raw_intelligence_item(raw_item.to_dict())

    def get_raw_items_by_source(
        self, source_type: str, source_id: str, limit: int, offset: int
    ) -> List[RawIntelligenceItem]:
        rows = self._data.get_raw_intelligence_items_by_source(
            source_type, source_id, limit, offset
        )
        return [RawIntelligenceItem.from_dict(row) for row in rows]

    def get_raw_items_expiring_before(self, cutoff_time: datetime) -> List[RawIntelligenceItem]:
        rows = self._data.get_raw_intelligence_items_expiring_before(cutoff_time)
        return [RawIntelligenceItem.from_dict(row) for row in rows]

    def get_raw_item_by_id(self, raw_item_id: str) -> Optional[RawIntelligenceItem]:
        row = self._data.get_raw_intelligence_item_by_id(raw_item_id)
        return RawIntelligenceItem.from_dict(row) if row else None

    def delete_expired_raw_items(self, cutoff_time: datetime) -> int:
        return self._data.delete_expired_raw_intelligence_items(cutoff_time)

    def purge_raw_text_older_than(self, cutoff_time: datetime) -> int:
        return self._data.purge_raw_intelligence_text_older_than(cutoff_time)

    def save_checkpoint(self, checkpoint: IntelligenceCrawlCheckpoint) -> None:
        self._data.upsert_intelligence_checkpoint(checkpoint.to_dict())

    def get_checkpoint(
        self, source_type: str, source_id: str
    ) -> Optional[IntelligenceCrawlCheckpoint]:
        row = self._data.get_intelligence_checkpoint(source_type, source_id)
        return IntelligenceCrawlCheckpoint.from_dict(row) if row else None

    def save_topic(self, topic: IntelligenceTopic) -> str:
        return self._data.upsert_intelligence_topic(topic.to_dict())

    def get_topic_by_id(self, topic_id: str) -> Optional[IntelligenceTopic]:
        row = self._data.get_intelligence_topic_by_id(topic_id)
        return IntelligenceTopic.from_dict(row) if row else None

    def list_topics(
        self,
        is_active: Optional[bool] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[IntelligenceTopic]:
        rows = self._data.list_intelligence_topics(
            is_active=is_active, limit=limit, offset=offset
        )
        return [IntelligenceTopic.from_dict(row) for row in rows]

    def count_topics(self, is_active: Optional[bool] = None) -> int:
        return self._data.count_intelligence_topics(is_active=is_active)

    def create_topic_prompt_version(self, prompt: TopicPrompt) -> str:
        return self.save_topic_prompt(prompt)

    def save_topic_prompt(self, prompt: TopicPrompt) -> str:
        columns = [
            "id",
            "intelligence_topic_id",
            "prompt_version",
            "status",
            "prompt_text",
            "schema_version",
            "created_by",
            "activated_by",
            "activation_notes",
            "audit_history",
            "created_at",
            "activated_at",
            "archived_at",
            "updated_at",
        ]
        payload = prompt.to_dict()
        values = [self._topic_value(payload.get(column), column) for column in columns]
        excluded = "EXCLUDED" if self._data.backend == "postgres" else "excluded"
        assignments = ", ".join(f"{column} = {excluded}.{column}" for column in columns[3:])
        with self._data._lock:
            with self._data._get_connection() as conn:
                conn.cursor().execute(
                    self._data._sql(f"""
                    INSERT INTO intelligence_topic_prompt_versions ({', '.join(columns)})
                    VALUES ({', '.join(['?'] * len(columns))})
                    ON CONFLICT(id) DO UPDATE SET {assignments}
                    """),
                    tuple(values),
                )
                conn.commit()
        return prompt.id

    def get_topic_prompt_by_id(self, prompt_version_id: str) -> Optional[TopicPrompt]:
        with self._data._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                self._data._sql(
                    "SELECT * FROM intelligence_topic_prompt_versions WHERE id = ? LIMIT 1"
                ),
                (prompt_version_id,),
            )
            row = cursor.fetchone()
        return TopicPrompt.from_dict(self._serialize_topic_prompt_row(row)) if row else None

    def get_active_topic_prompt(self, topic_id: str) -> Optional[TopicPrompt]:
        prompts = self.list_topic_prompts(topic_id, status="active", limit=1)
        return prompts[0] if prompts else None

    def list_topic_prompts(
        self,
        intelligence_topic_id: str,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[TopicPrompt]:
        filters = ["intelligence_topic_id = ?"]
        params: List[Any] = [intelligence_topic_id]
        if status:
            filters.append("status = ?")
            params.append(status)
        with self._data._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                self._data._sql(f"""
                SELECT * FROM intelligence_topic_prompt_versions
                WHERE {' AND '.join(filters)}
                ORDER BY activated_at DESC, created_at DESC
                LIMIT ? OFFSET ?
                """),
                (*params, max(1, limit), max(0, offset)),
            )
            return [TopicPrompt.from_dict(self._serialize_topic_prompt_row(row)) for row in cursor.fetchall()]

    def create_topic_finding(self, finding: TopicFinding) -> str:
        return self.save_topic_finding(finding)

    def save_topic_finding(self, finding: TopicFinding) -> str:
        columns = [
            "id",
            "intelligence_topic_id",
            "prompt_version_id",
            "status",
            "finding_payload",
            "citations",
            "source_raw_item_ids",
            "source_finding_ids",
            "content_hash",
            "confidence",
            "found_at",
            "archived_at",
            "superseded_by_finding_id",
            "created_at",
            "updated_at",
        ]
        payload = finding.to_dict()
        existing = self._get_topic_finding_by_content_hash(
            finding.intelligence_topic_id,
            finding.prompt_version_id,
            finding.content_hash,
        )
        if existing is not None:
            return existing.id
        values = [self._topic_value(payload.get(column), column) for column in columns]
        with self._data._lock:
            with self._data._get_connection() as conn:
                conn.cursor().execute(
                    self._data._sql(f"""
                    INSERT INTO intelligence_topic_findings ({', '.join(columns)})
                    VALUES ({', '.join(['?'] * len(columns))})
                    ON CONFLICT(id) DO NOTHING
                    """),
                    tuple(values),
                )
                conn.commit()
        loaded = self._get_topic_finding_by_content_hash(
            finding.intelligence_topic_id,
            finding.prompt_version_id,
            finding.content_hash,
        )
        return loaded.id if loaded else finding.id

    def get_topic_finding_by_id(self, finding_id: str) -> Optional[TopicFinding]:
        with self._data._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                self._data._sql("SELECT * FROM intelligence_topic_findings WHERE id = ? LIMIT 1"),
                (finding_id,),
            )
            row = cursor.fetchone()
        return TopicFinding.from_dict(self._serialize_topic_finding_row(row)) if row else None

    def list_topic_findings(
        self,
        intelligence_topic_id: str,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[TopicFinding]:
        filters = ["intelligence_topic_id = ?"]
        params: List[Any] = [intelligence_topic_id]
        if status:
            filters.append("status = ?")
            params.append(status)
        with self._data._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                self._data._sql(f"""
                SELECT * FROM intelligence_topic_findings
                WHERE {' AND '.join(filters)}
                ORDER BY updated_at DESC, created_at DESC
                LIMIT ? OFFSET ?
                """),
                (*params, max(1, limit), max(0, offset)),
            )
            return [TopicFinding.from_dict(self._serialize_topic_finding_row(row)) for row in cursor.fetchall()]

    def list_active_findings(self, topic_id: str) -> List[TopicFinding]:
        return self.list_topic_findings(topic_id, status="active")

    def archive_finding(
        self, finding_id: str, superseded_by_id: Optional[str] = None
    ) -> Optional[TopicFinding]:
        finding = self.get_topic_finding_by_id(finding_id)
        if finding is None:
            return None
        now = datetime.utcnow().isoformat()
        new_status = "superseded" if superseded_by_id else "archived"
        with self._data._lock:
            with self._data._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    self._data._sql("""
                    UPDATE intelligence_topic_findings
                    SET status = ?, archived_at = ?, superseded_by_finding_id = ?, updated_at = ?
                    WHERE id = ?
                    """),
                    (new_status, now, superseded_by_id, now, finding_id),
                )
                cursor.execute(
                    self._data._sql("""
                    INSERT INTO intelligence_finding_archives
                        (finding_id, intelligence_topic_id, archive_reason, archive_metadata,
                         superseded_by_finding_id, archived_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(finding_id) DO NOTHING
                    """),
                    (
                        finding_id,
                        finding.intelligence_topic_id,
                        new_status,
                        self._json_value({}),
                        superseded_by_id,
                        now,
                    ),
                )
                conn.commit()
        return self.get_topic_finding_by_id(finding_id)

    def mark_topic_raw_item_processed(
        self,
        raw_item_id: str,
        intelligence_topic_id: str,
        prompt_version: str,
        schema_version: str,
        finding_id: Optional[str] = None,
    ) -> None:
        self.mark_raw_items_processed(
            intelligence_topic_id,
            [raw_item_id],
            prompt_version,
            schema_version,
            finding_id=finding_id,
        )

    def mark_raw_items_processed(
        self,
        topic_id: str,
        raw_item_ids: List[str],
        prompt_version: str,
        schema_version: str,
        finding_id: Optional[str] = None,
    ) -> int:
        if not raw_item_ids:
            return 0
        inserted = 0
        with self._data._lock:
            with self._data._get_connection() as conn:
                cursor = conn.cursor()
                for raw_item_id in raw_item_ids:
                    cursor.execute(
                        self._data._sql("""
                        INSERT INTO intelligence_topic_processed_raw_items
                            (raw_item_id, intelligence_topic_id, prompt_version, schema_version, finding_id)
                        VALUES (?, ?, ?, ?, ?)
                        ON CONFLICT(raw_item_id, intelligence_topic_id, prompt_version, schema_version)
                        DO NOTHING
                        """),
                        (raw_item_id, topic_id, prompt_version, schema_version, finding_id),
                    )
                    if cursor.rowcount and cursor.rowcount > 0:
                        inserted += 1
                conn.commit()
        return inserted

    def get_processed_topic_raw_item_ids(
        self,
        raw_item_ids: List[str],
        intelligence_topic_id: str,
        prompt_version: str,
        schema_version: str,
    ) -> Set[str]:
        if not raw_item_ids:
            return set()
        placeholders = ", ".join(["?"] * len(raw_item_ids))
        with self._data._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                self._data._sql(f"""
                SELECT raw_item_id FROM intelligence_topic_processed_raw_items
                WHERE intelligence_topic_id = ?
                  AND prompt_version = ?
                  AND schema_version = ?
                  AND raw_item_id IN ({placeholders})
                """),
                (intelligence_topic_id, prompt_version, schema_version, *raw_item_ids),
            )
            return {str(row["raw_item_id"] if self._data.backend == "postgres" else row[0]) for row in cursor.fetchall()}

    def get_raw_items_since(
        self, topic_id: str, cursor_time: Optional[datetime], limit: int
    ) -> List[RawIntelligenceItem]:
        filters = ["collected_at > ?"] if cursor_time is not None else []
        params: List[Any] = [cursor_time.isoformat()] if cursor_time is not None else []
        with self._data._get_connection() as conn:
            cursor = conn.cursor()
            where = f"WHERE {' AND '.join(filters)}" if filters else ""
            cursor.execute(
                self._data._sql(f"""
                SELECT * FROM raw_intelligence_items
                {where}
                ORDER BY collected_at ASC, id ASC
                LIMIT ?
                """),
                (*params, max(1, limit)),
            )
            return [
                RawIntelligenceItem.from_dict(self._data._serialize_raw_intelligence_item_row(row))
                for row in cursor.fetchall()
            ]

    def create_topic_research_run(self, run: TopicResearchRun) -> str:
        return self.save_topic_research_run(run)

    def save_topic_research_run(self, run: TopicResearchRun) -> str:
        columns = [
            "id",
            "intelligence_topic_id",
            "prompt_version_id",
            "status",
            "checkpoint_cursor",
            "checkpoint_payload",
            "items_scanned",
            "findings_created",
            "error_message",
            "started_at",
            "finished_at",
            "created_at",
            "updated_at",
        ]
        payload = run.to_dict()
        values = [self._topic_value(payload.get(column), column) for column in columns]
        excluded = "EXCLUDED" if self._data.backend == "postgres" else "excluded"
        assignments = ", ".join(f"{column} = {excluded}.{column}" for column in columns[1:])
        with self._data._lock:
            with self._data._get_connection() as conn:
                conn.cursor().execute(
                    self._data._sql(f"""
                    INSERT INTO intelligence_topic_research_runs ({', '.join(columns)})
                    VALUES ({', '.join(['?'] * len(columns))})
                    ON CONFLICT(id) DO UPDATE SET {assignments}
                    """),
                    tuple(values),
                )
                conn.commit()
        return run.id

    def update_topic_research_run(
        self,
        run_id: str,
        status: str,
        checkpoint_cursor: Optional[str] = None,
        checkpoint_payload: Optional[Dict[str, Any]] = None,
        items_scanned: Optional[int] = None,
        findings_created: Optional[int] = None,
        error_message: Optional[str] = None,
        finished_at: Optional[datetime] = None,
    ) -> Optional[TopicResearchRun]:
        existing = self.get_topic_research_run(run_id)
        if existing is None:
            return None
        now = datetime.utcnow()
        finished = finished_at or (now if status in {"success", "failed", "cancelled"} else None)
        with self._data._lock:
            with self._data._get_connection() as conn:
                conn.cursor().execute(
                    self._data._sql("""
                    UPDATE intelligence_topic_research_runs
                    SET status = ?,
                        checkpoint_cursor = COALESCE(?, checkpoint_cursor),
                        checkpoint_payload = ?,
                        items_scanned = COALESCE(?, items_scanned),
                        findings_created = COALESCE(?, findings_created),
                        error_message = ?,
                        finished_at = COALESCE(?, finished_at),
                        updated_at = ?
                    WHERE id = ?
                    """),
                    (
                        status,
                        checkpoint_cursor,
                        self._json_value(checkpoint_payload if checkpoint_payload is not None else existing.checkpoint_payload),
                        items_scanned,
                        findings_created,
                        error_message,
                        finished.isoformat() if finished else None,
                        now.isoformat(),
                        run_id,
                    ),
                )
                conn.commit()
        return self.get_topic_research_run(run_id)

    def get_topic_research_run_by_id(self, run_id: str) -> Optional[TopicResearchRun]:
        return self.get_topic_research_run(run_id)

    def get_topic_research_run(self, run_id: str) -> Optional[TopicResearchRun]:
        with self._data._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                self._data._sql("SELECT * FROM intelligence_topic_research_runs WHERE id = ? LIMIT 1"),
                (run_id,),
            )
            row = cursor.fetchone()
        return TopicResearchRun.from_dict(self._serialize_topic_run_row(row)) if row else None

    def list_topic_research_runs(self, topic_id: str) -> List[TopicResearchRun]:
        with self._data._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                self._data._sql("""
                SELECT * FROM intelligence_topic_research_runs
                WHERE intelligence_topic_id = ?
                ORDER BY created_at DESC
                """),
                (topic_id,),
            )
            return [TopicResearchRun.from_dict(self._serialize_topic_run_row(row)) for row in cursor.fetchall()]

    def get_topic_checkpoint(
        self, topic_id: str, prompt_version_id: Optional[str]
    ) -> Optional[Dict[str, Any]]:
        clause = "prompt_version_id IS NULL" if prompt_version_id is None else "prompt_version_id = ?"
        params: Tuple[Any, ...] = (topic_id,) if prompt_version_id is None else (topic_id, prompt_version_id)
        with self._data._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                self._data._sql(f"""
                SELECT * FROM intelligence_topic_research_checkpoints
                WHERE intelligence_topic_id = ? AND {clause}
                LIMIT 1
                """),
                params,
            )
            row = cursor.fetchone()
        if not row:
            return None
        return self._serialize_checkpoint_row(row)

    def update_topic_checkpoint(
        self,
        topic_id: str,
        prompt_version_id: Optional[str],
        checkpoint_cursor: Optional[str],
        checkpoint_payload: Optional[Dict[str, Any]] = None,
        last_run_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        existing = self.get_topic_checkpoint(topic_id, prompt_version_id)
        now = datetime.utcnow().isoformat()
        if existing is not None:
            with self._data._lock:
                with self._data._get_connection() as conn:
                    conn.cursor().execute(
                        self._data._sql("""
                        UPDATE intelligence_topic_research_checkpoints
                        SET checkpoint_cursor = ?, checkpoint_payload = ?, last_run_id = ?, updated_at = ?
                        WHERE intelligence_topic_id = ?
                          AND (prompt_version_id = ? OR (prompt_version_id IS NULL AND ? IS NULL))
                        """),
                        (
                            checkpoint_cursor,
                            self._json_value(checkpoint_payload or {}),
                            last_run_id,
                            now,
                            topic_id,
                            prompt_version_id,
                            prompt_version_id,
                        ),
                    )
                    conn.commit()
        else:
            with self._data._lock:
                with self._data._get_connection() as conn:
                    conn.cursor().execute(
                        self._data._sql("""
                        INSERT INTO intelligence_topic_research_checkpoints
                            (intelligence_topic_id, prompt_version_id, checkpoint_cursor,
                             checkpoint_payload, last_run_id, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """),
                        (
                            topic_id,
                            prompt_version_id,
                            checkpoint_cursor,
                            self._json_value(checkpoint_payload or {}),
                            last_run_id,
                            now,
                        ),
                    )
                    conn.commit()
        checkpoint = self.get_topic_checkpoint(topic_id, prompt_version_id)
        if checkpoint is None:
            raise StorageError("Topic checkpoint update failed", operation="topic_checkpoint_update")
        return checkpoint

    def create_merge_preview(self, preview: MergePreview) -> str:
        return self.save_merge_preview(preview)

    def save_merge_preview(self, preview: MergePreview) -> str:
        source_ids = self._normalize_source_finding_ids(preview.source_finding_ids)
        existing = self._find_merge_preview_by_sources(preview.intelligence_topic_id, source_ids)
        if existing is not None:
            return existing.id
        columns = [
            "id",
            "intelligence_topic_id",
            "source_finding_ids",
            "preview_payload",
            "content_hash",
            "state",
            "created_by",
            "expires_at",
            "applied_at",
            "created_at",
            "updated_at",
        ]
        payload = preview.to_dict()
        payload["source_finding_ids"] = source_ids
        values = [self._topic_value(payload.get(column), column) for column in columns]
        with self._data._lock:
            with self._data._get_connection() as conn:
                conn.cursor().execute(
                    self._data._sql(f"""
                    INSERT INTO intelligence_topic_merge_previews ({', '.join(columns)})
                    VALUES ({', '.join(['?'] * len(columns))})
                    ON CONFLICT(id) DO NOTHING
                    """),
                    tuple(values),
                )
                conn.commit()
        return preview.id

    def get_merge_preview_by_id(self, preview_id: str) -> Optional[MergePreview]:
        return self.get_merge_preview(preview_id)

    def get_merge_preview(self, preview_id: str) -> Optional[MergePreview]:
        with self._data._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                self._data._sql("SELECT * FROM intelligence_topic_merge_previews WHERE id = ? LIMIT 1"),
                (preview_id,),
            )
            row = cursor.fetchone()
        return MergePreview.from_dict(self._serialize_merge_preview_row(row)) if row else None

    def list_merge_previews(
        self,
        intelligence_topic_id: str,
        state: Optional[str] = None,
        include_expired: bool = False,
        limit: int = 50,
    ) -> List[MergePreview]:
        filters = ["intelligence_topic_id = ?"]
        params: List[Any] = [intelligence_topic_id]
        if state:
            filters.append("state = ?")
            params.append(state)
        if not include_expired:
            filters.append("expires_at > ?")
            params.append(datetime.utcnow().isoformat())
        with self._data._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                self._data._sql(f"""
                SELECT * FROM intelligence_topic_merge_previews
                WHERE {' AND '.join(filters)}
                ORDER BY created_at DESC
                LIMIT ?
                """),
                (*params, max(1, limit)),
            )
            return [MergePreview.from_dict(self._serialize_merge_preview_row(row)) for row in cursor.fetchall()]

    def accept_merge_preview(self, preview_id: str) -> bool:
        preview = self.get_merge_preview(preview_id)
        if preview is None or preview.state != "pending":
            return False
        now = datetime.utcnow()
        if preview.expires_at <= now or not self._merge_preview_sources_are_active(preview):
            self._set_merge_preview_state(preview_id, "expired", None)
            return False
        return self._set_merge_preview_state(preview_id, "applied", now)

    def reject_merge_preview(self, preview_id: str) -> bool:
        return self._set_merge_preview_state(preview_id, "cancelled", None)

    def archive_topic_finding(self, archive: FindingArchive) -> None:
        self.archive_finding(archive.finding_id, archive.superseded_by_finding_id)

    def get_finding_archive(self, finding_id: str) -> Optional[FindingArchive]:
        with self._data._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                self._data._sql("SELECT * FROM intelligence_finding_archives WHERE finding_id = ? LIMIT 1"),
                (finding_id,),
            )
            row = cursor.fetchone()
        return FindingArchive.from_dict(self._serialize_finding_archive_row(row)) if row else None

    def _topic_value(self, value: Any, column: str) -> Any:
        if column in {
            "audit_history",
            "finding_payload",
            "citations",
            "source_raw_item_ids",
            "source_finding_ids",
            "checkpoint_payload",
            "preview_payload",
            "archive_metadata",
        }:
            return self._json_value(value if value is not None else ([] if column in {"audit_history", "citations", "source_raw_item_ids", "source_finding_ids"} else {}))
        if isinstance(value, datetime):
            return value.isoformat()
        return value

    def _json_value(self, value: Any) -> Any:
        if self._data.backend == "postgres":
            return json.dumps(value, ensure_ascii=False)
        return json.dumps(value, ensure_ascii=False)

    def _row_dict(self, row: Any) -> Dict[str, Any]:
        return {key: self._data._dt_out(row[key]) for key in row.keys()}

    def _serialize_topic_prompt_row(self, row: Any) -> Dict[str, Any]:
        data = self._row_dict(row)
        data["audit_history"] = self._data._json_load(data.get("audit_history"), [])
        return data

    def _serialize_topic_finding_row(self, row: Any) -> Dict[str, Any]:
        data = self._row_dict(row)
        for key, default in (
            ("finding_payload", {}),
            ("citations", []),
            ("source_raw_item_ids", []),
            ("source_finding_ids", []),
        ):
            data[key] = self._data._json_load(data.get(key), default)
        return data

    def _serialize_topic_run_row(self, row: Any) -> Dict[str, Any]:
        data = self._row_dict(row)
        data["checkpoint_payload"] = self._data._json_load(data.get("checkpoint_payload"), {})
        return data

    def _serialize_checkpoint_row(self, row: Any) -> Dict[str, Any]:
        data = self._row_dict(row)
        data["checkpoint_payload"] = self._data._json_load(data.get("checkpoint_payload"), {})
        return data

    def _serialize_merge_preview_row(self, row: Any) -> Dict[str, Any]:
        data = self._row_dict(row)
        data["source_finding_ids"] = self._normalize_source_finding_ids(
            self._data._json_load(data.get("source_finding_ids"), [])
        )
        data["preview_payload"] = self._data._json_load(data.get("preview_payload"), {})
        return data

    def _serialize_finding_archive_row(self, row: Any) -> Dict[str, Any]:
        data = self._row_dict(row)
        data["archive_metadata"] = self._data._json_load(data.get("archive_metadata"), {})
        return data

    def _get_topic_finding_by_content_hash(
        self, topic_id: str, prompt_version_id: str, content_hash: str
    ) -> Optional[TopicFinding]:
        with self._data._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                self._data._sql("""
                SELECT * FROM intelligence_topic_findings
                WHERE intelligence_topic_id = ? AND prompt_version_id = ? AND content_hash = ?
                ORDER BY created_at ASC
                LIMIT 1
                """),
                (topic_id, prompt_version_id, content_hash),
            )
            row = cursor.fetchone()
        return TopicFinding.from_dict(self._serialize_topic_finding_row(row)) if row else None

    def _normalize_source_finding_ids(self, source_finding_ids: List[str]) -> List[str]:
        return sorted({str(item).strip() for item in source_finding_ids if str(item).strip()})

    def _find_merge_preview_by_sources(
        self, topic_id: str, source_finding_ids: List[str]
    ) -> Optional[MergePreview]:
        for preview in self.list_merge_previews(topic_id, state="pending", include_expired=True, limit=1000):
            if self._normalize_source_finding_ids(preview.source_finding_ids) == source_finding_ids:
                return preview
        return None

    def _merge_preview_sources_are_active(self, preview: MergePreview) -> bool:
        with self._data._get_connection() as conn:
            cursor = conn.cursor()
            placeholders = ", ".join(["?"] * len(preview.source_finding_ids))
            cursor.execute(
                self._data._sql(f"""
                SELECT id FROM intelligence_topic_findings
                WHERE intelligence_topic_id = ?
                  AND status = 'active'
                  AND id IN ({placeholders})
                """),
                (preview.intelligence_topic_id, *preview.source_finding_ids),
            )
            active_ids = {str(row["id"] if self._data.backend == "postgres" else row[0]) for row in cursor.fetchall()}
        return active_ids == set(preview.source_finding_ids)

    def _set_merge_preview_state(
        self, preview_id: str, state: str, applied_at: Optional[datetime]
    ) -> bool:
        now = datetime.utcnow().isoformat()
        with self._data._lock:
            with self._data._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    self._data._sql("""
                    UPDATE intelligence_topic_merge_previews
                    SET state = ?, applied_at = COALESCE(?, applied_at), updated_at = ?
                    WHERE id = ?
                    """),
                    (state, applied_at.isoformat() if applied_at else None, now, preview_id),
                )
                conn.commit()
                return bool(cursor.rowcount and cursor.rowcount > 0)


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

    def cache_sent_messages(
        self,
        messages: List[Dict[str, Any]],
        recipient_key: Optional[str] = None,
    ) -> int:
        return self._cache.cache_sent_messages(messages, recipient_key=recipient_key)

    def get_cache_statistics(self) -> Dict[str, Any]:
        return self._cache.get_cache_statistics()


class RepositoryFactory:
    """Factory for creating repository instances"""

    @staticmethod
    def create_repositories(
        storage_config: StorageConfig,
        data_manager: Optional[DataManager] = None,
        cache_manager: Optional[SentMessageCacheManager] = None,
    ) -> Dict[str, Any]:
        backend = storage_config.backend
        if data_manager is None:
            data_manager = DataManager(storage_config)
        if cache_manager is None:
            cache_manager = SentMessageCacheManager(storage_config)

        return {
            "analysis": SQLiteAnalysisRepository(data_manager),
            "datasource": SQLiteDataSourceRepository(data_manager),
            "ingestion": SQLiteIngestionRepository(data_manager),
            "intelligence": SQLiteIntelligenceRepository(data_manager),
            "content": (
                PostgresContentRepository(data_manager)
                if backend == "postgres"
                else SQLiteContentRepository(data_manager)
            ),
            "cache": SQLiteCacheRepository(cache_manager),
            "semantic_search": (
                PostgresSemanticSearchRepository(data_manager)
                if backend == "postgres"
                else SQLiteSemanticSearchRepository(data_manager)
            ),
            "_backend": backend,
        }
