"""
HTTP API服务器

提供HTTP接口用于手动触发分析报告生成。
使用FastAPI Lifespan Events管理controller生命周期，避免全局变量问题。
"""

from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
import re
import uuid
from typing import Annotated, Any, Optional, cast
from urllib.parse import urlsplit, urlunsplit

from fastapi import FastAPI, HTTPException, Depends, Response, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field, field_validator
import os
import logging

from .execution_coordinator import MainController
from .datasource_payloads import (
    DataSourcePayloadValidationError,
    validate_datasource_create_payload,
)
from .domain.models import (
    AnalysisRequest,
    DataSource,
    DataSourceAlreadyExistsError,
    DataSourceInUseError,
    Priority,
    SemanticSearchJob,
)
from .models import SemanticSearchConfig
from .domain.repositories import (
    AnalysisRepository,
    DataSourceRepository,
    SemanticSearchRepository,
)
from .semantic_search.service import SemanticSearchService
from .storage.repositories import (
    PostgresSemanticSearchRepository,
    SQLiteAnalysisRepository,
)
from .intelligence.search import IntelligenceSearchService
from .domain.repositories import IntelligenceRepository

logger = logging.getLogger(__name__)
security = HTTPBearer()
USER_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
TELEGRAM_WEBHOOK_SECRET_HEADER = "x-telegram-bot-api-secret-token"
SEMANTIC_SEARCH_ROUTE_PATH = "/semantic-search"
SEMANTIC_SEARCH_JOB_STATUS_PATH = "/semantic-search/{job_id}"
SEMANTIC_SEARCH_JOB_RESULT_PATH = "/semantic-search/{job_id}/result"
SEMANTIC_SEARCH_TELEGRAM_COMMAND = "/semantic_search <hours> <topic>"


class AppState:
    """Application state container for lifespan management."""

    def __init__(self):
        self.controller: Optional[MainController] = None
        self.analysis_repository: Optional[AnalysisRepository] = None
        self.semantic_search_repository: Optional[SemanticSearchRepository] = None
        self.datasource_repository: Optional[DataSourceRepository] = None
        self.analyze_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="api-analyze")
        self.semantic_search_executor = ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="api-search",
        )
        self.telegram_uses_webhook = False
        self.intelligence_repository: Optional[IntelligenceRepository] = None

    def cleanup(self):
        """Cleanup resources on shutdown."""
        if self.controller:
            try:
                self.controller.stop_scheduler()
                logger.info("Scheduler stopped during cleanup")
            except Exception as e:
                logger.warning(f"Error stopping scheduler: {e}")

            try:
                if self.telegram_uses_webhook and self.controller.command_handler:
                    logger.info("Telegram webhook cleanup will be handled by lifespan shutdown")
                else:
                    self.controller.stop_command_listener()
                    logger.info("Command listener stopped during cleanup")
            except Exception as e:
                logger.warning(f"Error stopping command listener: {e}")

        # Shutdown executor
        if self.analyze_executor:
            self.analyze_executor.shutdown(wait=False)
        if self.semantic_search_executor:
            self.semantic_search_executor.shutdown(wait=False)

        # Clear references
        self.controller = None
        self.analysis_repository = None
        self.semantic_search_repository = None
        self.datasource_repository = None
        self.intelligence_repository = None


class AnalyzeRequest(BaseModel):
    hours: int = Field(..., gt=0, description="分析最近N小时的消息（必填，必须>0）")
    user_id: str = Field(..., description="请求用户标识（必填，仅允许字母、数字、_、-）")

    @field_validator("user_id")
    @classmethod
    def validate_user_id(cls, value: str) -> str:
        normalized_value = value.strip()
        if not USER_ID_PATTERN.fullmatch(normalized_value):
            raise ValueError("user_id must match ^[A-Za-z0-9_-]{1,128}$")
        return normalized_value


class SemanticSearchRequest(BaseModel):
    hours: int = Field(..., gt=0, description="搜索最近N小时的消息（必填，必须>0）")
    query: str = Field(..., description="语义搜索查询（必填，非空白）")
    user_id: str = Field(..., description="请求用户标识（必填，仅允许字母、数字、_、-）")

    @field_validator("query")
    @classmethod
    def validate_query(cls, value: str) -> str:
        return SemanticSearchConfig().validate_query(value)

    @field_validator("user_id")
    @classmethod
    def validate_user_id(cls, value: str) -> str:
        normalized_value = value.strip()
        if not USER_ID_PATTERN.fullmatch(normalized_value):
            raise ValueError("user_id must match ^[A-Za-z0-9_-]{1,128}$")
        return normalized_value


class AnalyzeResponse(BaseModel):
    success: bool
    report: str
    items_processed: int
    time_window_hours: int


class AnalyzeAcceptedResponse(BaseModel):
    success: bool
    job_id: str
    status: str
    time_window_hours: int
    status_url: str
    result_url: str


class AnalyzeJobStatusResponse(BaseModel):
    success: bool
    job_id: str
    status: str
    time_window_hours: int
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    items_processed: int = 0
    error: Optional[str] = None
    result_available: bool = False


class AnalyzeJobResultResponse(BaseModel):
    success: bool
    job_id: str
    status: str
    report: str
    items_processed: int
    time_window_hours: int
    error: Optional[str] = None


class SemanticSearchAcceptedResponse(BaseModel):
    success: bool
    job_id: str
    status: str
    query: str
    normalized_intent: str
    matched_count: int
    retained_count: int
    time_window_hours: int
    status_url: str
    result_url: str


class SemanticSearchJobStatusResponse(BaseModel):
    success: bool
    job_id: str
    status: str
    query: str
    normalized_intent: str
    matched_count: int
    retained_count: int
    time_window_hours: int
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error: Optional[str] = None
    result_available: bool = False


class SemanticSearchJobResultResponse(BaseModel):
    success: bool
    job_id: str
    status: str
    query: str
    normalized_intent: str
    matched_count: int
    retained_count: int
    report: str
    time_window_hours: int
    error: Optional[str] = None


class AnalyzeJobRecord(BaseModel):
    job_id: str
    user_id: str
    status: str
    time_window_hours: int
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    report: str = ""
    items_processed: int = 0
    error: Optional[str] = None
    final_report_messages: list[dict[str, Any]] = Field(default_factory=list)
    success_persisted: bool = False

    def to_status_response(self) -> AnalyzeJobStatusResponse:
        return AnalyzeJobStatusResponse(
            success=self.status == "completed",
            job_id=self.job_id,
            status=self.status,
            time_window_hours=self.time_window_hours,
            created_at=self.created_at,
            started_at=self.started_at,
            completed_at=self.completed_at,
            items_processed=self.items_processed,
            error=self.error,
            result_available=self.status in {"completed", "failed"},
        )

    def to_result_response(self) -> AnalyzeJobResultResponse:
        return AnalyzeJobResultResponse(
            success=self.status == "completed",
            job_id=self.job_id,
            status=self.status,
            report=self.report,
            items_processed=self.items_processed,
            time_window_hours=self.time_window_hours,
            error=self.error,
        )


class SemanticSearchJobRecord(BaseModel):
    job_id: str
    user_id: str
    status: str
    query: str
    normalized_intent: str = ""
    matched_count: int = 0
    retained_count: int = 0
    time_window_hours: int
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    report: str = ""
    error: Optional[str] = None

    def to_status_response(self) -> SemanticSearchJobStatusResponse:
        return SemanticSearchJobStatusResponse(
            success=self.status == "completed",
            job_id=self.job_id,
            status=self.status,
            query=self.query,
            normalized_intent=self.normalized_intent,
            matched_count=self.matched_count,
            retained_count=self.retained_count,
            time_window_hours=self.time_window_hours,
            created_at=self.created_at,
            started_at=self.started_at,
            completed_at=self.completed_at,
            error=self.error,
            result_available=self.status in {"completed", "failed"},
        )

    def to_result_response(self) -> SemanticSearchJobResultResponse:
        return SemanticSearchJobResultResponse(
            success=self.status == "completed",
            job_id=self.job_id,
            status=self.status,
            query=self.query,
            normalized_intent=self.normalized_intent,
            matched_count=self.matched_count,
            retained_count=self.retained_count,
            report=self.report,
            time_window_hours=self.time_window_hours,
            error=self.error,
        )


class DataSourceCreateRequest(BaseModel):
    source_type: str
    name: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    config_payload: dict[str, Any]


class DataSourceResponseItem(BaseModel):
    id: str
    name: str
    source_type: str
    tags: list[str]
    config_summary: dict[str, Any]


class DataSourceCreateResponse(BaseModel):
    success: bool
    datasource: DataSourceResponseItem


class DataSourceListResponse(BaseModel):
    success: bool
    datasources: list[DataSourceResponseItem]


class IntelligenceEntryResponse(BaseModel):
    id: str
    entry_type: str
    normalized_key: str
    display_name: str
    explanation: Optional[str] = None
    usage_summary: Optional[str] = None
    primary_label: Optional[str] = None
    secondary_tags: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    first_seen_at: Optional[str] = None
    last_seen_at: Optional[str] = None
    evidence_count: int = 1
    aliases: list[str] = Field(default_factory=list)
    model_name: Optional[str] = None
    prompt_version: Optional[str] = None
    schema_version: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class IntelligenceListResponse(BaseModel):
    entries: list[IntelligenceEntryResponse]
    total: int
    page: int
    page_size: int


class IntelligenceEntryDetailResponse(BaseModel):
    id: str
    entry_type: str
    normalized_key: str
    display_name: str
    explanation: Optional[str] = None
    usage_summary: Optional[str] = None
    primary_label: Optional[str] = None
    secondary_tags: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    first_seen_at: Optional[str] = None
    last_seen_at: Optional[str] = None
    evidence_count: int = 1
    aliases: list[str] = Field(default_factory=list)
    model_name: Optional[str] = None
    prompt_version: Optional[str] = None
    schema_version: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    raw_available: bool = False
    raw_evidence: Optional[Any] = None


class IntelligenceSearchResultItem(BaseModel):
    id: str
    entry_type: str
    normalized_key: str
    display_name: str
    explanation: Optional[str] = None
    primary_label: Optional[str] = None
    secondary_tags: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    last_seen_at: Optional[str] = None
    evidence_count: int = 1
    similarity_score: float = 0.0


class IntelligenceSearchResponse(BaseModel):
    results: list[IntelligenceSearchResultItem]
    total: int


class IntelligenceRawItemResponse(BaseModel):
    raw_text: Optional[str] = None
    source_type: str
    source_url: Optional[str] = None
    published_at: Optional[str] = None
    expires_at: Optional[str] = None
    is_expired: bool = False


def _canonical_entry_to_response(entry: Any) -> IntelligenceEntryResponse:
    return IntelligenceEntryResponse(
        id=entry.id,
        entry_type=entry.entry_type,
        normalized_key=entry.normalized_key,
        display_name=entry.display_name,
        explanation=entry.explanation,
        usage_summary=getattr(entry, "usage_summary", None),
        primary_label=entry.primary_label,
        secondary_tags=list(entry.secondary_tags),
        confidence=entry.confidence,
        first_seen_at=entry.first_seen_at.isoformat() if entry.first_seen_at else None,
        last_seen_at=entry.last_seen_at.isoformat() if entry.last_seen_at else None,
        evidence_count=entry.evidence_count,
        aliases=list(getattr(entry, "aliases", [])),
        model_name=entry.model_name,
        prompt_version=entry.prompt_version,
        schema_version=entry.schema_version,
        created_at=entry.created_at.isoformat() if entry.created_at else None,
        updated_at=entry.updated_at.isoformat() if entry.updated_at else None,
    )


def _as_naive_utc(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _is_expired(expires_at: Optional[datetime], now: Optional[datetime] = None) -> bool:
    normalized_expires_at = _as_naive_utc(expires_at)
    if normalized_expires_at is None:
        return False
    return normalized_expires_at < (now or datetime.utcnow())


def _get_app_state(request: Request) -> AppState:
    """Get application state from request."""
    return cast(AppState, request.app.state.app_state)


def _get_controller(request: Request) -> MainController:
    """Get controller from app state."""
    state = _get_app_state(request)
    if state.controller is None:
        raise HTTPException(status_code=503, detail="System not initialized")
    return state.controller


def _get_analysis_repository(request: Request) -> AnalysisRepository:
    """Get analysis repository from app state or controller."""
    state = _get_app_state(request)

    if state.analysis_repository is not None:
        return state.analysis_repository

    controller = state.controller
    if (
        controller
        and hasattr(controller, "analysis_repository")
        and controller.analysis_repository is not None
    ):
        state.analysis_repository = controller.analysis_repository
        return cast(AnalysisRepository, state.analysis_repository)

    if controller and hasattr(controller, "data_manager") and controller.data_manager is not None:
        state.analysis_repository = SQLiteAnalysisRepository(controller.data_manager)
        return state.analysis_repository

    raise HTTPException(status_code=503, detail="System not initialized")


def _get_datasource_repository(request: Request) -> DataSourceRepository:
    state = _get_app_state(request)

    if state.datasource_repository is not None:
        return state.datasource_repository

    controller = state.controller
    if controller and hasattr(controller, "datasource_repository"):
        repository = controller.datasource_repository
        if repository is not None:
            state.datasource_repository = repository
            return cast(DataSourceRepository, state.datasource_repository)

    raise HTTPException(status_code=503, detail="System not initialized")

def _get_intelligence_repository(request: Request) -> IntelligenceRepository:
    """Get intelligence repository from app state or controller."""
    state = _get_app_state(request)

    if state.intelligence_repository is not None:
        return state.intelligence_repository

    controller = _get_controller(request)
    intelligence_repository = getattr(controller, "intelligence_repository", None)
    if intelligence_repository is not None:
        state.intelligence_repository = cast(IntelligenceRepository, intelligence_repository)
        return state.intelligence_repository

    raise HTTPException(status_code=503, detail="Intelligence repository not initialized")



def _ensure_semantic_search_http_supported(controller: MainController) -> None:
    try:
        ensure_semantic_search_supported(controller)
    except HTTPException as exc:
        detail = str(exc.detail)
        if exc.status_code == 503 and "unsupported" in detail.lower():
            raise HTTPException(
                status_code=503,
                detail="Semantic search requires postgres backend",
            ) from exc
        raise


def _get_semantic_search_repository(request: Request) -> SemanticSearchRepository:
    state = _get_app_state(request)

    if state.semantic_search_repository is not None:
        return state.semantic_search_repository

    controller = _get_controller(request)
    _ensure_semantic_search_http_supported(controller)

    if hasattr(controller, "semantic_search_repository"):
        repository = getattr(controller, "semantic_search_repository")
        if repository is not None:
            state.semantic_search_repository = cast(SemanticSearchRepository, repository)
            return state.semantic_search_repository

    repositories = getattr(controller, "_repositories", None)
    if isinstance(repositories, dict):
        repository = repositories.get("semantic_search")
        if repository is not None:
            state.semantic_search_repository = cast(SemanticSearchRepository, repository)
            return state.semantic_search_repository

    data_manager = getattr(controller, "data_manager", None)
    if data_manager is not None:
        state.semantic_search_repository = PostgresSemanticSearchRepository(data_manager)
        return state.semantic_search_repository

    raise HTTPException(status_code=503, detail="System not initialized")


def _get_telegram_command_handler(request: Request) -> Any:
    controller = _get_controller(request)
    command_handler = getattr(controller, "command_handler", None)
    if command_handler is None:
        raise HTTPException(status_code=404, detail="Telegram command handler not configured")
    return command_handler


def verify_api_key(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
) -> str:
    """验证API Key"""
    api_key = credentials.credentials
    expected_key = os.environ.get("API_KEY")
    if not expected_key or api_key != expected_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return api_key


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _job_urls(job_id: str) -> tuple[str, str]:
    return (f"/analyze/{job_id}", f"/analyze/{job_id}/result")


def _semantic_search_job_urls(job_id: str) -> tuple[str, str]:
    return (
        f"{SEMANTIC_SEARCH_ROUTE_PATH}/{job_id}",
        f"{SEMANTIC_SEARCH_ROUTE_PATH}/{job_id}/result",
    )


def _datetime_to_iso(value: Optional[datetime]) -> Optional[str]:
    if value is None:
        return None
    return value.isoformat()


def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
    if value is None:
        return None
    return datetime.fromisoformat(value)


def _to_recipient_key(user_id: str, controller: Optional[MainController]) -> str:
    if controller and hasattr(controller, "_normalize_manual_recipient_key"):
        return controller._normalize_manual_recipient_key("api", user_id)
    normalized_user_id = str(user_id).strip()
    return f"api:{normalized_user_id}"


def _to_user_id(recipient_key: str, fallback: str = "") -> str:
    if recipient_key.startswith("api:"):
        return recipient_key.split(":", 1)[1]
    return fallback or recipient_key


def _result_error_message(result: dict[str, Any]) -> Optional[str]:
    if result.get("success"):
        return None
    errors = result.get("errors") or []
    return "; ".join(str(error) for error in errors) or "Analysis failed"


def ensure_semantic_search_supported(controller: MainController) -> None:
    config_manager = controller.config_manager
    if config_manager is None:
        raise HTTPException(status_code=503, detail="System not initialized")

    semantic_search_config = config_manager.get_semantic_search_config()
    storage_config = config_manager.get_storage_config()
    try:
        semantic_search_config.ensure_supported_for_storage(storage_config)
    except ValueError as exc:
        message = str(exc)
        status_code = 503 if "unsupported" in message.lower() else 403
        raise HTTPException(status_code=status_code, detail=message) from exc


def _request_to_job_record(request: AnalysisRequest) -> AnalyzeJobRecord:
    result = request.result or {}
    error_message = request.error_message
    if error_message is None and request.status == "failed":
        error_message = _result_error_message(result)

    return AnalyzeJobRecord(
        job_id=request.id,
        user_id=_to_user_id(request.recipient_key),
        status=request.status,
        time_window_hours=request.time_window_hours,
        created_at=request.created_at.isoformat(),
        started_at=_datetime_to_iso(request.started_at),
        completed_at=_datetime_to_iso(request.completed_at),
        report=str(result.get("report_content", "")),
        items_processed=int(result.get("items_processed", 0)),
        error=error_message,
        final_report_messages=list(result.get("final_report_messages", [])),
        success_persisted=bool(result.get("success_persisted", False)),
    )


def _build_analysis_request_from_job(
    job: AnalyzeJobRecord, controller: Optional[MainController]
) -> AnalysisRequest:
    result: dict[str, Any] = {
        "success": job.status == "completed",
        "report_content": job.report,
        "items_processed": job.items_processed,
        "errors": [job.error] if job.error else [],
        "final_report_messages": list(job.final_report_messages),
        "success_persisted": job.success_persisted,
    }
    return AnalysisRequest(
        id=job.job_id,
        recipient_key=_to_recipient_key(job.user_id, controller),
        time_window_hours=job.time_window_hours,
        created_at=_parse_datetime(job.created_at) or datetime.now(timezone.utc),
        status=job.status,
        priority=Priority.NORMAL.value,
        started_at=_parse_datetime(job.started_at),
        completed_at=_parse_datetime(job.completed_at),
        result=result,
        error_message=job.error,
        source="api",
    )


def _semantic_search_request_to_job_record(
    job: SemanticSearchJob,
) -> SemanticSearchJobRecord:
    result = job.result or {}
    error_message = job.error_message
    if error_message is None and job.status == "failed":
        error_message = _result_error_message(result)

    return SemanticSearchJobRecord(
        job_id=job.id,
        user_id=_to_user_id(job.recipient_key),
        status=job.status,
        query=job.query,
        normalized_intent=job.normalized_intent,
        matched_count=job.matched_count,
        retained_count=job.retained_count,
        time_window_hours=job.time_window_hours,
        created_at=job.created_at.isoformat(),
        started_at=_datetime_to_iso(job.started_at),
        completed_at=_datetime_to_iso(job.completed_at),
        report=str(result.get("report_content", "")),
        error=error_message,
    )


def _build_semantic_search_service(controller: MainController) -> SemanticSearchService:
    config_manager = controller.config_manager
    content_repository = getattr(controller, "content_repository", None)
    embedding_service = getattr(controller, "embedding_service", None)

    if config_manager is None or content_repository is None:
        raise ValueError("semantic search service is unavailable")
    if embedding_service is None:
        raise ValueError("embedding service is unavailable")

    auth_config = config_manager.get_auth_config()
    provider_credentials = {
        "grok": getattr(auth_config, "GROK_API_KEY", ""),
        "kimi": getattr(auth_config, "KIMI_API_KEY", ""),
        "opencode-go": getattr(auth_config, "OPENCODE_API_KEY", ""),
    }

    return SemanticSearchService.from_llm_config_payload(
        content_repository=content_repository,
        embedding_service=embedding_service,
        semantic_search_config=config_manager.get_semantic_search_config(),
        llm_config_payload=dict(config_manager.config_data.get("llm_config", {})),
        provider_credentials=provider_credentials,
    )

def _build_intelligence_search_service(controller: MainController) -> IntelligenceSearchService:
    """Build IntelligenceSearchService on demand for API querying."""
    if controller.config_manager is None:
        raise HTTPException(status_code=503, detail="System not initialized")

    intelligence_repository = getattr(controller, "intelligence_repository", None)
    if intelligence_repository is None:
        raise HTTPException(status_code=503, detail="Intelligence repository not initialized")

    embedding_service = getattr(controller, "embedding_service", None)
    if embedding_service is None:
        raise HTTPException(status_code=503, detail="Embedding service not initialized")

    storage_config = getattr(controller, "storage_config", None)
    if storage_config is None:
        raise HTTPException(status_code=503, detail="Storage config not initialized")

    return IntelligenceSearchService(
        embedding_service=embedding_service,
        intelligence_repository=intelligence_repository,
        storage_config=storage_config,
    )


def _parse_window_param(window_str: Optional[str]) -> Optional[datetime]:
    """Parse a window parameter like "7d", "24h", "30d" into a datetime cutoff."""
    if not window_str or not str(window_str).strip():
        return None
    value = str(window_str).strip().lower()
    match = re.match(r"^(\d+)([dh])$", value)
    if not match:
        return None
    num = int(match.group(1))
    unit = match.group(2)
    if unit == "h":
        return datetime.now(timezone.utc) - timedelta(hours=num)
    return datetime.now(timezone.utc) - timedelta(days=num)



def _run_analyze_job(job_id: str, state: AppState) -> None:
    """Run analyze job with proper error handling."""
    repository = state.analysis_repository
    controller = state.controller

    if repository is None or controller is None:
        logger.error("Cannot run analyze job: system not initialized")
        return

    try:
        request = repository.get_by_id(job_id)
        if request is None:
            logger.error(f"Analyze job {job_id} not found")
            return
        job = _request_to_job_record(request)
    except Exception as exc:
        logger.error(f"Failed to get analyze job {job_id}: {exc}")
        return

    _ = repository.update_status(
        request_id=job_id,
        status="running",
    )

    try:
        result = controller.analyze_by_time_window(
            chat_id=job.user_id,
            time_window_hours=job.time_window_hours,
            manual_source="api",
        )
        _ = repository.complete_job(
            request_id=job_id,
            result=result,
        )
    except Exception as exc:
        logger.error(f"Async analyze job failed: {exc}")
        _ = repository.update_status(
            request_id=job_id,
            status="failed",
            error_message=str(exc),
        )


def _run_semantic_search_job(job_id: str, state: AppState) -> None:
    repository = state.semantic_search_repository
    controller = state.controller

    if repository is None or controller is None:
        logger.error("Cannot run semantic search job: system not initialized")
        return

    try:
        job = repository.get_by_id(job_id)
        if job is None:
            logger.error(f"Semantic search job {job_id} not found")
            return
    except Exception as exc:
        logger.error(f"Failed to get semantic search job {job_id}: {exc}")
        return

    started_at = datetime.now(timezone.utc)
    job.status = "running"
    job.started_at = started_at
    _ = repository.update_semantic_search_job(job)

    try:
        service = _build_semantic_search_service(controller)
        result = service.search(query=job.query, time_window_hours=job.time_window_hours)
        job.status = "completed"
        job.normalized_intent = str(result.get("normalized_intent") or "")
        job.matched_count = int(result.get("matched_count", 0))
        job.retained_count = int(result.get("retained_count", 0))
        job.result = {
            "success": True,
            "report_content": str(result.get("report_content", "")),
            "normalized_intent": job.normalized_intent,
            "matched_count": job.matched_count,
            "retained_count": job.retained_count,
            "subqueries": list(result.get("subqueries") or []),
            "keyword_queries": list(result.get("keyword_queries") or []),
            "errors": [],
        }
        job.error_message = None
    except Exception as exc:
        logger.error(f"Async semantic search job failed: {exc}")
        job.status = "failed"
        job.result = {
            "success": False,
            "report_content": "",
            "normalized_intent": job.normalized_intent,
            "matched_count": job.matched_count,
            "retained_count": job.retained_count,
            "errors": [str(exc)],
        }
        job.error_message = str(exc)
    finally:
        job.completed_at = datetime.now(timezone.utc)
        _ = repository.update_semantic_search_job(job)


def _persist_completed_api_job_success(job: AnalyzeJobRecord, controller: MainController) -> None:
    recipient_key = controller._normalize_manual_recipient_key("api", job.user_id)
    controller._persist_manual_analysis_success(
        recipient_key=recipient_key,
        time_window_hours=job.time_window_hours,
        items_count=job.items_processed,
        final_report_messages=job.final_report_messages,
    )
    job.success_persisted = True


def _build_datasource_config_summary(datasource: DataSource) -> dict[str, Any]:
    payload = dict(datasource.config_payload or {})

    if datasource.source_type == "rss":
        return {
            "url": payload.get("url"),
            "description": payload.get("description", ""),
        }

    if datasource.source_type == "x":
        return {
            "url": payload.get("url"),
            "type": payload.get("type"),
        }

    if datasource.source_type == "rest_api":
        headers = payload.get("headers")
        params = payload.get("params")
        response_mapping = payload.get("response_mapping")

        return {
            "endpoint": _summarize_public_endpoint(payload.get("endpoint")),
            "method": payload.get("method"),
            "response_mapping": (
                dict(response_mapping) if isinstance(response_mapping, dict) else {}
            ),
            "header_count": len(headers) if isinstance(headers, dict) else 0,
            "param_count": len(params) if isinstance(params, dict) else 0,
        }

    return {}


def _summarize_public_endpoint(endpoint: Any) -> Optional[str]:
    if endpoint is None:
        return None

    endpoint_text = str(endpoint)
    try:
        parsed = urlsplit(endpoint_text)
    except ValueError:
        return endpoint_text.split("?", 1)[0].split("#", 1)[0]

    netloc = parsed.hostname or ""
    if parsed.port is not None:
        netloc = f"{netloc}:{parsed.port}"

    return urlunsplit((parsed.scheme, netloc, parsed.path, "", ""))


def _to_datasource_response_item(datasource: DataSource) -> DataSourceResponseItem:
    return DataSourceResponseItem(
        id=datasource.id,
        name=datasource.name,
        source_type=datasource.source_type,
        tags=list(datasource.tags),
        config_summary=_build_datasource_config_summary(datasource),
    )


def enqueue_analyze_job(hours: int, user_id: str, state: AppState) -> AnalyzeJobRecord:
    """Enqueue analyze job."""
    if state.analysis_repository is None:
        raise HTTPException(status_code=503, detail="System not initialized")

    repository = state.analysis_repository
    job_id = f"analyze_job_{uuid.uuid4().hex}"
    job = AnalyzeJobRecord(
        job_id=job_id,
        user_id=user_id,
        status="queued",
        time_window_hours=hours,
        created_at=_utcnow_iso(),
    )

    repository.save(_build_analysis_request_from_job(job, state.controller))

    _ = state.analyze_executor.submit(_run_analyze_job, job_id, state)
    return job


def enqueue_semantic_search_job(
    hours: int,
    query: str,
    user_id: str,
    state: AppState,
) -> SemanticSearchJobRecord:
    if state.semantic_search_repository is None:
        raise HTTPException(status_code=503, detail="System not initialized")

    job = SemanticSearchJob(
        id=f"semantic_search_job_{uuid.uuid4().hex}",
        recipient_key=_to_recipient_key(user_id, state.controller),
        query=query,
        normalized_intent="",
        time_window_hours=hours,
        created_at=datetime.now(timezone.utc),
        status="queued",
        source="api",
    )

    state.semantic_search_repository.create_semantic_search_job(job)
    _ = state.semantic_search_executor.submit(_run_semantic_search_job, job.id, state)
    return _semantic_search_request_to_job_record(job)


def create_api_server(
    config_path: str = "./config.jsonc",
    start_services: bool = True,
    start_scheduler: Optional[bool] = None,
    start_command_listener: Optional[bool] = None,
) -> FastAPI:
    """创建并初始化API服务器。"""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """FastAPI lifespan context manager for proper startup/shutdown."""
        # Startup
        app_state = AppState()
        app.state.app_state = app_state

        controller = MainController(config_path)
        if not controller.initialize_system():
            raise RuntimeError("Failed to initialize system")

        app_state.controller = controller
        app_state.analysis_repository = controller.analysis_repository
        app_state.datasource_repository = controller.datasource_repository
        app_state.semantic_search_repository = getattr(
            controller, "semantic_search_repository", None
        )
        if app_state.semantic_search_repository is None:
            repositories = getattr(controller, "_repositories", None)
            if isinstance(repositories, dict):
                app_state.semantic_search_repository = repositories.get("semantic_search")

        app_state.intelligence_repository = getattr(
            controller, "intelligence_repository", None
        )
        if app_state.intelligence_repository is None:
            repositories = getattr(controller, "_repositories", None)
            if isinstance(repositories, dict):
                app_state.intelligence_repository = cast(
                    IntelligenceRepository, repositories.get("intelligence")
                )

        effective_start_scheduler = start_services if start_scheduler is None else start_scheduler
        effective_start_command_listener = (
            start_services if start_command_listener is None else start_command_listener
        )

        if effective_start_scheduler:
            controller.start_scheduler()
            logger.info("Scheduler started in API runtime")
        else:
            logger.info("Scheduler disabled in API runtime")

        if effective_start_command_listener:
            if controller.command_handler:
                if (
                    hasattr(controller.command_handler, "uses_webhook")
                    and controller.command_handler.uses_webhook()
                ):
                    await controller.command_handler.initialize_webhook()
                    app_state.telegram_uses_webhook = True
                    logger.info("Telegram webhook started in API mode")
                else:
                    controller.start_command_listener()
                    logger.info("Telegram command listener started in API mode")
            else:
                logger.warning("Telegram command handler not configured, listener not started")
        else:
            logger.info("Telegram command listener disabled in API runtime")

        logger.info("API server initialized")
        yield
        # Shutdown
        logger.info("API server shutting down")
        if app_state.telegram_uses_webhook and controller.command_handler:
            try:
                await controller.command_handler.shutdown_webhook()
            except Exception as exc:
                logger.warning(f"Error shutting down Telegram webhook: {exc}")
        app_state.cleanup()

    app = FastAPI(title="Crypto News Analyzer API", lifespan=lifespan)

    @app.post("/analyze", response_model=AnalyzeAcceptedResponse, status_code=202)
    async def analyze(
        request: AnalyzeRequest,
        response: Response,
        _: Annotated[str, Depends(verify_api_key)],
        req: Request,
    ):
        """
        分析指定时间窗口内的消息并返回Markdown报告

        - hours: 分析最近N小时的消息（必填，必须>0）
        """
        controller = _get_controller(req)
        state = _get_app_state(req)

        config_manager = controller.config_manager
        if config_manager is None:
            raise HTTPException(status_code=503, detail="System not initialized")

        analysis_config = config_manager.get_analysis_config()
        max_hours = analysis_config.get("max_analysis_window_hours", 24)
        min_hours = analysis_config.get("min_analysis_window_hours", 1)

        if request.hours < min_hours:
            raise HTTPException(status_code=400, detail=f"Hours must be at least {min_hours}")

        hours = min(request.hours, max_hours)

        try:
            job = enqueue_analyze_job(hours, request.user_id, state)
        except HTTPException:
            raise
        except Exception as exc:
            logger.error(f"Failed to enqueue analyze job: {exc}")
            raise HTTPException(status_code=500, detail=str(exc))

        status_url, result_url = _job_urls(job.job_id)
        response.headers["Location"] = status_url
        response.headers["Retry-After"] = "5"

        return AnalyzeAcceptedResponse(
            success=True,
            job_id=job.job_id,
            status=job.status,
            time_window_hours=hours,
            status_url=status_url,
            result_url=result_url,
        )

    @app.get("/analyze/{job_id}", response_model=AnalyzeJobStatusResponse)
    async def get_job_status(
        job_id: str,
        _: Annotated[str, Depends(verify_api_key)],
        req: Request,
    ):
        """Get analyze job status."""
        repository = _get_analysis_repository(req)

        request_obj = repository.get_by_id(job_id)
        if request_obj is None:
            raise HTTPException(status_code=404, detail="Analyze job not found")

        return _request_to_job_record(request_obj).to_status_response()

    @app.get("/analyze/{job_id}/result", response_model=AnalyzeJobResultResponse)
    async def get_job_result(
        job_id: str,
        _: Annotated[str, Depends(verify_api_key)],
        req: Request,
    ):
        """Get analyze job result."""
        repository = _get_analysis_repository(req)
        controller = _get_controller(req)

        request_obj = repository.get_by_id(job_id)
        if request_obj is None:
            raise HTTPException(status_code=404, detail="Analyze job not found")

        job = _request_to_job_record(request_obj)

        if job.status == "completed" and not job.success_persisted:
            try:
                _persist_completed_api_job_success(job, controller)
                request_obj = _build_analysis_request_from_job(job, controller)
                repository.save(request_obj)
            except Exception as exc:
                logger.error(f"Failed to persist job success: {exc}")
                raise HTTPException(status_code=500, detail=str(exc))

        return job.to_result_response()

    @app.post(
        SEMANTIC_SEARCH_ROUTE_PATH,
        response_model=SemanticSearchAcceptedResponse,
        status_code=202,
    )
    async def semantic_search(
        request: SemanticSearchRequest,
        response: Response,
        _: Annotated[str, Depends(verify_api_key)],
        req: Request,
    ):
        controller = _get_controller(req)
        state = _get_app_state(req)

        config_manager = controller.config_manager
        if config_manager is None:
            raise HTTPException(status_code=503, detail="System not initialized")

        _ensure_semantic_search_http_supported(controller)
        _get_semantic_search_repository(req)

        analysis_config = config_manager.get_analysis_config()
        max_hours = analysis_config.get("max_analysis_window_hours", 24)
        min_hours = analysis_config.get("min_analysis_window_hours", 1)

        if request.hours < min_hours:
            raise HTTPException(status_code=400, detail=f"Hours must be at least {min_hours}")

        hours = min(request.hours, max_hours)

        try:
            job = enqueue_semantic_search_job(hours, request.query, request.user_id, state)
        except HTTPException:
            raise
        except Exception as exc:
            logger.error(f"Failed to enqueue semantic search job: {exc}")
            raise HTTPException(status_code=500, detail=str(exc))

        status_url, result_url = _semantic_search_job_urls(job.job_id)
        response.headers["Location"] = status_url
        response.headers["Retry-After"] = "5"

        return SemanticSearchAcceptedResponse(
            success=True,
            job_id=job.job_id,
            status=job.status,
            query=job.query,
            normalized_intent=job.normalized_intent,
            matched_count=job.matched_count,
            retained_count=job.retained_count,
            time_window_hours=job.time_window_hours,
            status_url=status_url,
            result_url=result_url,
        )

    @app.get(SEMANTIC_SEARCH_JOB_STATUS_PATH, response_model=SemanticSearchJobStatusResponse)
    async def get_semantic_search_job_status(
        job_id: str,
        _: Annotated[str, Depends(verify_api_key)],
        req: Request,
    ):
        repository = _get_semantic_search_repository(req)
        job = repository.get_by_id(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Semantic search job not found")
        return _semantic_search_request_to_job_record(job).to_status_response()

    @app.get(SEMANTIC_SEARCH_JOB_RESULT_PATH, response_model=SemanticSearchJobResultResponse)
    async def get_semantic_search_job_result(
        job_id: str,
        _: Annotated[str, Depends(verify_api_key)],
        req: Request,
    ):
        repository = _get_semantic_search_repository(req)
        job = repository.get_by_id(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Semantic search job not found")
        return _semantic_search_request_to_job_record(job).to_result_response()

    # ── Intelligence query endpoints ──────────────────────────────────────

    @app.get("/intelligence/entries", response_model=IntelligenceListResponse)
    async def list_intelligence_entries(
        req: Request,
        _: Annotated[str, Depends(verify_api_key)],
        window: Optional[str] = None,
        entry_type: Optional[str] = None,
        primary_label: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ):
        """List canonical intelligence entries with pagination."""
        repository = _get_intelligence_repository(req)
        window_cutoff = _parse_window_param(window)

        page = max(1, page)
        page_size = max(1, min(page_size, 100))

        entries = repository.list_canonical_entries(
            entry_type=entry_type if entry_type else None,
            primary_label=primary_label if primary_label else None,
            window=window_cutoff,
            page=page,
            page_size=page_size,
        )
        total = repository.count_canonical_entries(
            entry_type=entry_type if entry_type else None,
            primary_label=primary_label if primary_label else None,
            window=window_cutoff,
        )

        return IntelligenceListResponse(
            entries=[_canonical_entry_to_response(e) for e in entries],
            total=total,
            page=page,
            page_size=page_size,
        )

    @app.get("/intelligence/entries/{entry_id}", response_model=IntelligenceEntryDetailResponse)
    async def get_intelligence_entry_detail(
        entry_id: str,
        req: Request,
        _: Annotated[str, Depends(verify_api_key)],
        include_raw: bool = False,
    ):
        """Get a single intelligence entry by ID with optional raw evidence."""
        repository = _get_intelligence_repository(req)
        entry = repository.get_canonical_entry_by_id(entry_id)
        if entry is None:
            raise HTTPException(status_code=404, detail="Intelligence entry not found")

        response = IntelligenceEntryDetailResponse(
            id=entry.id,
            entry_type=entry.entry_type,
            normalized_key=entry.normalized_key,
            display_name=entry.display_name,
            explanation=entry.explanation,
            usage_summary=getattr(entry, "usage_summary", None),
            primary_label=entry.primary_label,
            secondary_tags=list(entry.secondary_tags),
            confidence=entry.confidence,
            first_seen_at=entry.first_seen_at.isoformat() if entry.first_seen_at else None,
            last_seen_at=entry.last_seen_at.isoformat() if entry.last_seen_at else None,
            evidence_count=entry.evidence_count,
            aliases=list(getattr(entry, "aliases", [])),
            model_name=entry.model_name,
            prompt_version=entry.prompt_version,
            schema_version=entry.schema_version,
            created_at=entry.created_at.isoformat() if entry.created_at else None,
            updated_at=entry.updated_at.isoformat() if entry.updated_at else None,
        )

        if include_raw and entry.latest_raw_item_id:
            raw_item = repository.get_raw_item_by_id(entry.latest_raw_item_id)
            if raw_item:
                is_expired = _is_expired(raw_item.expires_at)
                if not is_expired and raw_item.raw_text:
                    response.raw_available = True
                    response.raw_evidence = {
                        "raw_item_id": raw_item.id,
                        "raw_text": raw_item.raw_text,
                        "source_type": raw_item.source_type,
                        "source_url": raw_item.source_url,
                        "published_at": raw_item.published_at.isoformat() if raw_item.published_at else None,
                        "collected_at": raw_item.collected_at.isoformat() if raw_item.collected_at else None,
                        "expires_at": raw_item.expires_at.isoformat() if raw_item.expires_at else None,
                    }
                else:
                    response.raw_available = False

        return response

    @app.get("/intelligence/search", response_model=IntelligenceSearchResponse)
    async def search_intelligence(
        req: Request,
        _: Annotated[str, Depends(verify_api_key)],
        q: str,
        entry_type: Optional[str] = None,
        primary_label: Optional[str] = None,
        window: Optional[str] = None,
    ):
        """Semantic search across canonical intelligence entries."""
        controller = _get_controller(req)
        service = _build_intelligence_search_service(controller)

        window_cutoff = _parse_window_param(window)

        results = service.semantic_search(
            query_text=q,
            entry_type=entry_type if entry_type else None,
            primary_label=primary_label if primary_label else None,
            window=window_cutoff,
            limit=20,
        )

        return IntelligenceSearchResponse(
            results=[
                IntelligenceSearchResultItem(
                    id=entry.id,
                    entry_type=entry.entry_type,
                    normalized_key=entry.normalized_key,
                    display_name=entry.display_name,
                    explanation=entry.explanation,
                    primary_label=entry.primary_label,
                    secondary_tags=list(entry.secondary_tags),
                    confidence=entry.confidence,
                    last_seen_at=entry.last_seen_at.isoformat() if entry.last_seen_at else None,
                    evidence_count=entry.evidence_count,
                    similarity_score=round(score, 4),
                )
                for entry, score in results
            ],
            total=len(results),
        )

    @app.get("/intelligence/raw/{raw_item_id}", response_model=IntelligenceRawItemResponse)
    async def get_intelligence_raw_item(
        raw_item_id: str,
        req: Request,
        _: Annotated[str, Depends(verify_api_key)],
    ):
        """Get a raw intelligence item by ID."""
        repository = _get_intelligence_repository(req)
        raw_item = repository.get_raw_item_by_id(raw_item_id)
        if raw_item is None:
            raise HTTPException(status_code=404, detail="Raw intelligence item not found")

        is_expired = _is_expired(raw_item.expires_at)
        raw_text = None if is_expired else raw_item.raw_text

        return IntelligenceRawItemResponse(
            raw_text=raw_text,
            source_type=raw_item.source_type,
            source_url=raw_item.source_url,
            published_at=raw_item.published_at.isoformat() if raw_item.published_at else None,
            expires_at=raw_item.expires_at.isoformat() if raw_item.expires_at else None,
            is_expired=is_expired,
        )

    @app.post("/datasources", response_model=DataSourceCreateResponse, status_code=201)
    async def create_datasource(
        request: DataSourceCreateRequest,
        _: Annotated[str, Depends(verify_api_key)],
        req: Request,
    ):
        repository = _get_datasource_repository(req)

        try:
            validated_payload = validate_datasource_create_payload(
                request.model_dump(exclude_none=True)
            )
        except DataSourcePayloadValidationError as exc:
            raise HTTPException(status_code=422, detail=str(exc))

        try:
            saved_datasource = repository.save(validated_payload.to_domain_datasource())
        except DataSourceAlreadyExistsError as exc:
            raise HTTPException(status_code=409, detail=str(exc))
        except Exception as exc:
            logger.error(f"Failed to create datasource: {exc}")
            raise HTTPException(status_code=500, detail=str(exc))

        return DataSourceCreateResponse(
            success=True,
            datasource=_to_datasource_response_item(saved_datasource),
        )

    @app.get("/datasources", response_model=DataSourceListResponse)
    async def list_datasources(
        _: Annotated[str, Depends(verify_api_key)],
        req: Request,
    ):
        repository = _get_datasource_repository(req)
        datasources = sorted(
            repository.list(),
            key=lambda datasource: (datasource.source_type, datasource.name),
        )

        return DataSourceListResponse(
            success=True,
            datasources=[_to_datasource_response_item(datasource) for datasource in datasources],
        )

    @app.delete("/datasources/{datasource_id}", status_code=204)
    async def delete_datasource(
        datasource_id: str,
        _: Annotated[str, Depends(verify_api_key)],
        req: Request,
    ):
        repository = _get_datasource_repository(req)

        try:
            deleted = repository.delete(datasource_id)
        except DataSourceInUseError as exc:
            raise HTTPException(status_code=409, detail=str(exc))
        except Exception as exc:
            logger.error(f"Failed to delete datasource {datasource_id}: {exc}")
            raise HTTPException(status_code=500, detail=str(exc))

        if not deleted:
            raise HTTPException(status_code=404, detail="Datasource not found")

        return Response(status_code=204)

    @app.get("/health")
    async def health_check(req: Request):
        """健康检查端点"""
        state = _get_app_state(req)
        return {"status": "healthy", "initialized": state.controller is not None}

    @app.post(os.getenv("TELEGRAM_WEBHOOK_PATH", "/telegram/webhook"))
    async def telegram_webhook(req: Request):
        """Telegram webhook endpoint."""
        command_handler = _get_telegram_command_handler(req)
        payload = await req.json()
        secret_token = req.headers.get(TELEGRAM_WEBHOOK_SECRET_HEADER)

        try:
            await command_handler.handle_webhook_update(payload, secret_token=secret_token)
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc))
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc))

        return {"ok": True}

    return app
