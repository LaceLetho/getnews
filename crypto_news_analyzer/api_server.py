# SHARED INFRASTRUCTURE — Single FastAPI app hosting BOTH news routes
# (/analyze, /semantic-search, /datasources) AND intelligence routes (/intelligence/*).
# Domain grouping is by route prefix: news → /analyze, /semantic-search, /datasources;
# intelligence → /intelligence/*.

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
from typing import TYPE_CHECKING, Annotated, Any, Dict, List, Optional, cast
from urllib.parse import urlsplit, urlunsplit, urlparse

from fastapi import BackgroundTasks, FastAPI, HTTPException, Depends, Response, Request
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
    DataSourcePurpose,
    DataSourceTopicAssociationError,
    Priority,
    SafeDataSourceSummary,
    SemanticSearchJob,
    TopicLifecycleStatus,
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
from .domain.repositories import IntelligenceRepository

if TYPE_CHECKING:
    from .intelligence.topic_prompts import TopicPromptWorkflowService
    from .intelligence.topic_findings import TopicFindingMergeService

logger = logging.getLogger(__name__)
security = HTTPBearer()
USER_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
TELEGRAM_WEBHOOK_SECRET_HEADER = "x-telegram-bot-api-secret-token"
SEMANTIC_SEARCH_ROUTE_PATH = "/semantic-search"
SEMANTIC_SEARCH_JOB_STATUS_PATH = "/semantic-search/{job_id}"
SEMANTIC_SEARCH_JOB_RESULT_PATH = "/semantic-search/{job_id}/result"
SEMANTIC_SEARCH_TELEGRAM_COMMAND = "/news_semantic_search <hours> <topic>"


# ── Application State ──────────────────────────────────────────────────


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


# ── Request/Response Models ────────────────────────────────────────────


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
    purpose: str
    source_type: str
    name: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    config_payload: dict[str, Any]


class DataSourceResponseItem(BaseModel):
    id: str
    name: str
    purpose: str
    source_type: str
    tags: list[str]
    config_summary: dict[str, Any]


class DataSourceCreateResponse(BaseModel):
    success: bool
    datasource: DataSourceResponseItem


class DataSourceListResponse(BaseModel):
    success: bool
    datasources: list[DataSourceResponseItem]


class IntelligenceTopicItemResponse(BaseModel):
    id: str
    name: str
    finding_count: int = 0
    updated_at: Optional[str] = None


class IntelligenceTopicListResponse(BaseModel):
    items: list[IntelligenceTopicItemResponse]
    total: int
    page: int
    page_size: int


class TopicCreateDraftRequest(BaseModel):
    theme: str = Field(..., min_length=1, max_length=500)
    source_context: Optional[Dict[str, Any]] = Field(default=None)
    datasource_ids: Optional[List[str]] = Field(default=None)


class TopicReviseRequest(BaseModel):
    feedback: str = Field(..., min_length=1, max_length=5000)


class TopicManualReplaceRequest(BaseModel):
    prompt_text: str = Field(..., min_length=1, max_length=50000)


class TopicConfirmRequest(BaseModel):
    prompt_version_id: str = Field(..., min_length=1)
    activation_notes: Optional[str] = Field(default=None, max_length=2000)


class TopicEditActiveRequest(BaseModel):
    new_prompt_text: str = Field(..., min_length=1, max_length=50000)


class TopicPromptVersionResponse(BaseModel):
    id: str
    intelligence_topic_id: str
    prompt_version: str
    prompt_text: str
    schema_version: str
    status: str
    created_by: Optional[str] = None
    activated_by: Optional[str] = None
    activation_notes: Optional[str] = None
    created_at: Optional[str] = None
    activated_at: Optional[str] = None
    archived_at: Optional[str] = None
    updated_at: Optional[str] = None
    audit_history: List[Dict[str, Any]] = Field(default_factory=list)


class TopicFindingResponse(BaseModel):
    id: str
    intelligence_topic_id: str
    prompt_version_id: str
    finding_payload: Dict[str, Any]
    confidence: float = 0.0
    citations: List[Dict[str, Any]] = Field(default_factory=list)
    source_finding_ids: List[str] = Field(default_factory=list)
    status: str
    found_at: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class TopicDetailResponse(BaseModel):
    topic: Dict[str, Any]
    merge_available: bool = False


class TopicFindingsListResponse(BaseModel):
    findings: List[TopicFindingResponse] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 10


class TopicPromptsResponse(BaseModel):
    current_prompt: Optional[TopicPromptVersionResponse] = None
    prompt_versions: List[TopicPromptVersionResponse] = Field(default_factory=list)


class TopicLifecycleActionResponse(BaseModel):
    success: bool
    topic_id: str
    lifecycle_status: str
    updated_at: Optional[str] = None


class TopicDatasourceSetRequest(BaseModel):
    """Request body for atomic replacement of topic datasource associations."""

    datasource_ids: List[str] = Field(default_factory=list)


class SafeDataSourceSummaryResponse(BaseModel):
    """Safe datasource summary — excludes config_payload entirely."""

    id: str
    source_type: str
    name: str
    tags: List[str] = Field(default_factory=list)


# ── Helper Functions ───────────────────────────────────────────────────


def _datetime_to_iso(value: Optional[datetime]) -> Optional[str]:
    return value.isoformat() if value is not None else None


def _topic_to_dict(topic: Any) -> Dict[str, Any]:
    return {
        "id": str(getattr(topic, "id", "")),
        "name": str(getattr(topic, "name", "")),
        "is_active": bool(getattr(topic, "is_active", True)),
        "updated_at": _datetime_to_iso(getattr(topic, "updated_at", None)),
    }


def _as_naive_utc(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _build_source_display(raw_item: Any) -> str:
    """Build a human-readable source display string from a RawIntelligenceItem."""
    source_type = getattr(raw_item, "source_type", "") or ""
    source_url = getattr(raw_item, "source_url", "") or ""
    chat_id = getattr(raw_item, "chat_id", "") or ""
    thread_id = getattr(raw_item, "thread_id", "") or ""
    topic_id = getattr(raw_item, "topic_id", "") or ""

    if source_type == "telegram_group":
        base = "Telegram群组"
        if chat_id:
            base += f"({chat_id})"
        if thread_id:
            base += f" [thread:{thread_id}]"
        return base

    if source_type == "v2ex":
        base = "V2EX帖子"
        if topic_id:
            base += f"(#{topic_id})"
        return base

    if source_url:
        from urllib.parse import urlparse

        try:
            parsed = urlparse(source_url)
            domain = parsed.netloc or source_url
            return f"{source_type} ({domain})"
        except Exception:
            return f"{source_type} ({source_url})"

    return source_type or "未知"


def _build_source_url_from_raw_item(item: Any) -> Optional[str]:
    source_url = str(getattr(item, "source_url", "") or "").strip()
    source_type = str(getattr(item, "source_type", "") or "").strip()
    external_id = str(getattr(item, "external_id", "") or "").strip()
    chat_id = str(getattr(item, "chat_id", "") or "").strip()
    source_id = str(getattr(item, "source_id", "") or "").strip()

    if source_url:
        if source_type == "telegram_group" and external_id:
            try:
                parsed = urlparse(source_url)
                host = (parsed.netloc or "").lower()
                if host in {"t.me", "telegram.me", "www.t.me", "www.telegram.me"}:
                    parts = [p for p in parsed.path.split("/") if p]
                    if parts:
                        if parts[0] == "c":
                            if len(parts) >= 3:
                                return source_url
                            if len(parts) == 2 and parts[1].isdigit():
                                return f"https://t.me/c/{parts[1]}/{external_id}"
                            return None
                        username = parts[0].lstrip("@")
                        if len(parts) >= 2 and parts[1].isdigit():
                            return source_url
                        return f"https://t.me/{username}/{external_id}"
            except Exception:
                pass
        try:
            parsed = urlparse(source_url)
            if parsed.scheme in {"http", "https"} and parsed.netloc:
                return source_url
        except Exception:
            pass

    if source_type == "telegram_group" and external_id:
        target_id = chat_id or source_id
        if target_id:
            if target_id.startswith("@"):
                username = target_id[1:]
                if 5 <= len(username) <= 32 and all(c.isalnum() or c == "_" for c in username):
                    return f"https://t.me/{username}/{external_id}"
            elif target_id.startswith("-100") and target_id[4:].isdigit():
                return f"https://t.me/c/{target_id[4:]}/{external_id}"
            elif 5 <= len(target_id) <= 32 and all(c.isalnum() or c == "_" for c in target_id):
                return f"https://t.me/{target_id}/{external_id}"

    return source_url if source_url else None


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


def _map_topic_datasource_error(exc: ValueError) -> HTTPException:
    """Map ValueError from topic-datasource repo methods to HTTP status codes.

    - "unknown topic"      → 404
    - "unknown datasource" → 404
    - "not intelligence"   → 400
    - everything else      → 400
    """
    msg = str(exc)
    if "unknown topic" in msg.lower():
        return HTTPException(status_code=404, detail=msg)
    if "unknown datasource" in msg.lower():
        return HTTPException(status_code=404, detail=msg)
    if "not intelligence" in msg.lower() or "not intelligence-purpose" in msg.lower():
        return HTTPException(status_code=400, detail=msg)
    return HTTPException(status_code=400, detail=msg)


def _summary_to_response(s: SafeDataSourceSummary) -> SafeDataSourceSummaryResponse:
    """Convert SafeDataSourceSummary to pydantic response model."""
    return SafeDataSourceSummaryResponse(
        id=s.id,
        source_type=s.source_type,
        name=s.name,
        tags=s.tags,
    )


def _semantic_search_job_urls(job_id: str) -> tuple[str, str]:
    return (
        f"{SEMANTIC_SEARCH_ROUTE_PATH}/{job_id}",
        f"{SEMANTIC_SEARCH_ROUTE_PATH}/{job_id}/result",
    )


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


def _get_topic_prompt_workflow_service(
    controller: MainController,
    repository: IntelligenceRepository,
) -> "TopicPromptWorkflowService":
    from .intelligence.topic_prompts import TopicPromptWorkflowService

    llm_analyzer = getattr(controller, "llm_analyzer", None)
    llm_client = getattr(llm_analyzer, "client", None) if llm_analyzer else None
    model_name = ""
    if llm_analyzer and hasattr(llm_analyzer, "analysis_model_runtime"):
        runtime = llm_analyzer.analysis_model_runtime
        model_name = getattr(runtime, "model_name", "") if runtime else ""

    llm_config_payload = (
        dict(getattr(llm_analyzer, "config", {}) or {})
        if llm_analyzer
        else {}
    )

    return TopicPromptWorkflowService(
        repository=repository,
        llm_client=llm_client,
        model_name=model_name,
        config=llm_config_payload,
    )


def _get_topic_finding_merge_service(
    controller: MainController,
    repository: IntelligenceRepository,
) -> "TopicFindingMergeService":
    from .intelligence.topic_findings import TopicFindingMergeService

    llm_analyzer = getattr(controller, "llm_analyzer", None)
    llm_client = getattr(llm_analyzer, "client", None) if llm_analyzer else None
    model_name = ""
    if llm_analyzer and hasattr(llm_analyzer, "analysis_model_runtime"):
        runtime = llm_analyzer.analysis_model_runtime
        model_name = getattr(runtime, "model_name", "") if runtime else ""

    llm_config_payload = (
        dict(getattr(llm_analyzer, "config", {}) or {})
        if llm_analyzer
        else {}
    )

    return TopicFindingMergeService(
        intelligence_repository=repository,
        llm_client=llm_client,
        model_name=model_name,
        config=llm_config_payload,
    )


def _prompt_to_response(prompt: Any) -> TopicPromptVersionResponse:
    return TopicPromptVersionResponse(
        id=str(getattr(prompt, "id", "")),
        intelligence_topic_id=str(getattr(prompt, "intelligence_topic_id", "")),
        prompt_version=str(getattr(prompt, "prompt_version", "")),
        prompt_text=str(getattr(prompt, "prompt_text", "")),
        schema_version=str(getattr(prompt, "schema_version", "")),
        status=str(getattr(prompt, "status", "draft")),
        created_by=getattr(prompt, "created_by", None),
        activated_by=getattr(prompt, "activated_by", None),
        activation_notes=getattr(prompt, "activation_notes", None),
        created_at=_datetime_to_iso(getattr(prompt, "created_at", None)),
        activated_at=_datetime_to_iso(getattr(prompt, "activated_at", None)),
        archived_at=_datetime_to_iso(getattr(prompt, "archived_at", None)),
        updated_at=_datetime_to_iso(getattr(prompt, "updated_at", None)),
        audit_history=list(getattr(prompt, "audit_history", []) or []),
    )


def _finding_to_response(
    finding: Any, raw_item_url_map: Optional[dict[str, str]] = None
) -> TopicFindingResponse:
    citations = list(getattr(finding, "citations", []) or [])
    url_map = raw_item_url_map or {}
    enriched: list[dict[str, Any]] = []
    for citation in citations:
        cit = dict(citation) if isinstance(citation, dict) else {}
        raw_id = cit.get("message_id", "")
        cit["source_url"] = url_map.get(str(raw_id), "")
        enriched.append(cit)
    return TopicFindingResponse(
        id=str(getattr(finding, "id", "")),
        intelligence_topic_id=str(getattr(finding, "intelligence_topic_id", "")),
        prompt_version_id=str(getattr(finding, "prompt_version_id", "")),
        finding_payload=dict(getattr(finding, "finding_payload", {}) or {}),
        confidence=float(getattr(finding, "confidence", 0.0)),
        citations=enriched,
        source_finding_ids=list(getattr(finding, "source_finding_ids", []) or []),
        status=str(getattr(finding, "status", "active")),
        found_at=_datetime_to_iso(getattr(finding, "found_at", None)),
        created_at=_datetime_to_iso(getattr(finding, "created_at", None)),
        updated_at=_datetime_to_iso(getattr(finding, "updated_at", None)),
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
    payload = dict(getattr(datasource, "config_payload", {}) or {})
    source_type = str(getattr(datasource, "source_type", ""))

    if source_type == "rss":
        return {
            "url": payload.get("url"),
            "description": payload.get("description", ""),
        }

    if source_type == "x":
        return {
            "url": payload.get("url"),
            "type": payload.get("type"),
        }

    if source_type == "rest_api":
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
        id=str(getattr(datasource, "id", "")),
        name=str(getattr(datasource, "name", "")),
        purpose=str(getattr(datasource, "purpose", DataSourcePurpose.INTELLIGENCE.value)),
        source_type=str(getattr(datasource, "source_type", "")),
        tags=list(getattr(datasource, "tags", []) or []),
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


# ── Route Registration: News Domain ────────────────────────────────────


def register_news_routes(app: FastAPI) -> None:
    """Register news domain routes: /analyze, /semantic-search, /datasources."""

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
        purpose: Optional[str] = None,
        source_type: Optional[str] = None,
    ):
        repository = _get_datasource_repository(req)
        if purpose is not None and purpose not in {item.value for item in DataSourcePurpose}:
            raise HTTPException(
                status_code=422, detail="purpose must be one of: news, intelligence"
            )
        try:
            datasource_items = repository.list(purpose=purpose, source_type=source_type)
        except TypeError:
            datasource_items = repository.list()
            if purpose is not None:
                datasource_items = [
                    datasource
                    for datasource in datasource_items
                    if getattr(datasource, "purpose", None) == purpose
                ]
            if source_type is not None:
                datasource_items = [
                    datasource
                    for datasource in datasource_items
                    if getattr(datasource, "source_type", None) == source_type
                ]
        datasources = sorted(
            datasource_items,
            key=lambda datasource: (
                getattr(datasource, "purpose", ""),
                getattr(datasource, "source_type", ""),
                getattr(datasource, "name", ""),
            ),
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
        except DataSourceTopicAssociationError as exc:
            raise HTTPException(
                status_code=409,
                detail=f"Datasource is associated with {exc.topic_count} topic(s)",
            )
        except Exception as exc:
            logger.error(f"Failed to delete datasource {datasource_id}: {exc}")
            raise HTTPException(status_code=500, detail=str(exc))

        if not deleted:
            raise HTTPException(status_code=404, detail="Datasource not found")

        return Response(status_code=204)


# ── Route Registration: Intelligence Domain ────────────────────────────


def register_intelligence_routes(app: FastAPI) -> None:
    """Register intelligence domain routes: /intelligence/*."""

    @app.post("/intelligence/topics", response_model=TopicPromptVersionResponse, status_code=201)
    async def create_topic_draft(
        request_body: TopicCreateDraftRequest,
        req: Request,
        _: Annotated[str, Depends(verify_api_key)],
    ):
        """Create a new intelligence topic with an LLM-generated draft prompt."""
        controller = _get_controller(req)
        repository = _get_intelligence_repository(req)
        service = _get_topic_prompt_workflow_service(controller, repository)
        datasource_ids = request_body.datasource_ids
        if datasource_ids:
            validator = getattr(repository, "_validate_datasource_ids_for_topic", None)
            if callable(validator):
                try:
                    validator(sorted(set(datasource_ids)))
                except ValueError as exc:
                    raise _map_topic_datasource_error(exc)

        try:
            prompt = service.create_draft_topic(
                theme=request_body.theme,
                source_context=request_body.source_context,
                created_by="api",
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc))
        except Exception as exc:
            logger.error(f"Failed to create topic draft: {exc}")
            raise HTTPException(status_code=500, detail=str(exc))

        topic_id = prompt.intelligence_topic_id
        if datasource_ids:
            try:
                repository.add_topic_datasources(topic_id, datasource_ids)
            except ValueError as exc:
                raise _map_topic_datasource_error(exc)

        return _prompt_to_response(prompt)

    @app.post(
        "/intelligence/topics/{topic_id}/revise",
        response_model=TopicPromptVersionResponse,
    )
    async def revise_topic_prompt(
        topic_id: str,
        request_body: TopicReviseRequest,
        req: Request,
        _: Annotated[str, Depends(verify_api_key)],
    ):
        """Revise the most recent prompt for a topic using LLM and user feedback."""
        controller = _get_controller(req)
        repository = _get_intelligence_repository(req)
        service = _get_topic_prompt_workflow_service(controller, repository)

        try:
            prompt = service.revise_prompt(
                topic_id=topic_id,
                feedback=request_body.feedback,
                activated_by="api",
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc))
        except Exception as exc:
            logger.error(f"Failed to revise prompt: {exc}")
            raise HTTPException(status_code=500, detail=str(exc))

        return _prompt_to_response(prompt)

    @app.put(
        "/intelligence/topics/{topic_id}/prompt",
        response_model=TopicPromptVersionResponse,
    )
    async def set_topic_prompt(
        topic_id: str,
        request_body: TopicManualReplaceRequest,
        req: Request,
        _: Annotated[str, Depends(verify_api_key)],
    ):
        """Replace or edit the active prompt (context-aware: edits active if it exists)."""
        controller = _get_controller(req)
        repository = _get_intelligence_repository(req)
        service = _get_topic_prompt_workflow_service(controller, repository)

        try:
            active = repository.get_active_topic_prompt(topic_id)
            if active is not None:
                prompt = service.edit_active_prompt(
                    topic_id=topic_id,
                    new_prompt_text=request_body.prompt_text,
                    created_by="api",
                )
            else:
                prompt = service.replace_prompt_manual(
                    topic_id=topic_id,
                    prompt_text=request_body.prompt_text,
                    created_by="api",
                )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except Exception as exc:
            logger.error(f"Failed to set prompt: {exc}")
            raise HTTPException(status_code=500, detail=str(exc))

        return _prompt_to_response(prompt)

    @app.post(
        "/intelligence/topics/{topic_id}/confirm",
        response_model=TopicPromptVersionResponse,
    )
    async def confirm_topic_prompt(
        topic_id: str,
        request_body: TopicConfirmRequest,
        req: Request,
        _: Annotated[str, Depends(verify_api_key)],
    ):
        """Confirm a draft prompt version, activating it for the topic."""
        controller = _get_controller(req)
        repository = _get_intelligence_repository(req)
        service = _get_topic_prompt_workflow_service(controller, repository)

        try:
            prompt = service.confirm_prompt(
                topic_id=topic_id,
                prompt_version_id=request_body.prompt_version_id,
                activated_by="api",
                activation_notes=request_body.activation_notes,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except Exception as exc:
            logger.error(f"Failed to confirm prompt: {exc}")
            raise HTTPException(status_code=500, detail=str(exc))

        return _prompt_to_response(prompt)

    @app.post(
        "/intelligence/topics/{topic_id}/pause",
        response_model=TopicLifecycleActionResponse,
    )
    async def pause_topic(
        topic_id: str,
        req: Request,
        _: Annotated[str, Depends(verify_api_key)],
    ):
        """Pause a topic, stopping further research runs."""
        repository = _get_intelligence_repository(req)
        topic = repository.get_topic_by_id(topic_id)
        if topic is None:
            raise HTTPException(status_code=404, detail="Topic not found")

        topic.lifecycle_status = TopicLifecycleStatus.PAUSED.value
        topic.updated_at = datetime.now(timezone.utc)
        repository.save_topic(topic)

        return TopicLifecycleActionResponse(
            success=True,
            topic_id=topic_id,
            lifecycle_status=topic.lifecycle_status,
            updated_at=_datetime_to_iso(topic.updated_at),
        )

    @app.post(
        "/intelligence/topics/{topic_id}/archive",
        response_model=TopicLifecycleActionResponse,
    )
    async def archive_topic(
        topic_id: str,
        req: Request,
        _: Annotated[str, Depends(verify_api_key)],
    ):
        """Archive a topic, removing it from active research."""
        repository = _get_intelligence_repository(req)
        topic = repository.get_topic_by_id(topic_id)
        if topic is None:
            raise HTTPException(status_code=404, detail="Topic not found")

        topic.lifecycle_status = TopicLifecycleStatus.ARCHIVED.value
        topic.updated_at = datetime.now(timezone.utc)
        repository.save_topic(topic)

        return TopicLifecycleActionResponse(
            success=True,
            topic_id=topic_id,
            lifecycle_status=topic.lifecycle_status,
            updated_at=_datetime_to_iso(topic.updated_at),
        )

    @app.get("/intelligence/topics", response_model=IntelligenceTopicListResponse)
    async def list_intelligence_topics(
        req: Request,
        _: Annotated[str, Depends(verify_api_key)],
        active_only: bool = True,
        page: int = 1,
        page_size: int = 20,
    ):
        repository = _get_intelligence_repository(req)
        topics = repository.list_topics(
            is_active=True if active_only else None,
            limit=max(1, page_size),
            offset=max(0, page - 1) * max(1, page_size),
        )
        total = repository.count_topics(is_active=True if active_only else None)
        items = []
        for topic in topics:
            findings = repository.list_topic_findings(topic.id) or []
            finding_count = len(findings)
            items.append(
                IntelligenceTopicItemResponse(
                    id=topic.id,
                    name=topic.name,
                    finding_count=finding_count,
                    updated_at=_datetime_to_iso(topic.updated_at),
                )
            )
        return IntelligenceTopicListResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
        )

    @app.get("/intelligence/topics/{topic_id}", response_model=TopicDetailResponse)
    async def get_intelligence_topic_detail(
        topic_id: str,
        req: Request,
        _: Annotated[str, Depends(verify_api_key)],
    ):
        """Return topic metadata and merge availability."""
        repository = _get_intelligence_repository(req)
        topic = repository.get_topic_by_id(topic_id)
        if topic is None:
            raise HTTPException(status_code=404, detail="Topic not found")

        previews = repository.list_merge_previews(topic_id, state="pending", limit=1)
        merge_available = len(previews) > 0

        return TopicDetailResponse(
            topic=_topic_to_dict(topic),
            merge_available=merge_available,
        )

    @app.get(
        "/intelligence/topics/{topic_id}/findings",
        response_model=TopicFindingsListResponse,
    )
    async def get_topic_findings(
        topic_id: str,
        req: Request,
        _: Annotated[str, Depends(verify_api_key)],
        page: int = 1,
        page_size: int = 10,
    ):
        """Return paginated active findings with enriched source URLs."""
        repository = _get_intelligence_repository(req)
        topic = repository.get_topic_by_id(topic_id)
        if topic is None:
            raise HTTPException(status_code=404, detail="Topic not found")

        offset = max(0, page - 1) * max(1, page_size)
        active_findings = repository.list_topic_findings(
            topic_id, status="active", limit=page_size, offset=offset
        )
        total = 0
        if hasattr(repository, "count_topic_findings"):
            total = repository.count_topic_findings(topic_id, status="active")

        raw_item_ids: set[str] = set()
        for finding in active_findings:
            for rid in (getattr(finding, "source_raw_item_ids", []) or []):
                raw_item_ids.add(str(rid))

        raw_item_url_map: dict[str, str] = {}
        if raw_item_ids and hasattr(repository, "get_raw_items_by_ids"):
            raw_items = repository.get_raw_items_by_ids(list(raw_item_ids))
            for item in raw_items:
                url = _build_source_url_from_raw_item(item)
                if url:
                    raw_item_url_map[str(item.id)] = url

        return TopicFindingsListResponse(
            findings=[_finding_to_response(f, raw_item_url_map) for f in active_findings],
            total=total,
            page=page,
            page_size=page_size,
        )

    @app.get(
        "/intelligence/topics/{topic_id}/prompts",
        response_model=TopicPromptsResponse,
    )
    async def get_topic_prompts(
        topic_id: str,
        req: Request,
        _: Annotated[str, Depends(verify_api_key)],
    ):
        """Return prompt versions and current active prompt."""
        repository = _get_intelligence_repository(req)
        topic = repository.get_topic_by_id(topic_id)
        if topic is None:
            raise HTTPException(status_code=404, detail="Topic not found")

        prompt_versions = repository.list_topic_prompts(topic_id, limit=50, offset=0)
        current_prompt = repository.get_active_topic_prompt(topic_id)

        return TopicPromptsResponse(
            prompt_versions=[_prompt_to_response(p) for p in prompt_versions],
            current_prompt=_prompt_to_response(current_prompt) if current_prompt else None,
        )

    # ── Topic-Datasource Association Routes ──────────────────────────────

    @app.get(
        "/intelligence/topics/{topic_id}/datasources",
        response_model=List[SafeDataSourceSummaryResponse],
    )
    async def get_topic_datasources(
        topic_id: str,
        req: Request,
        _: Annotated[str, Depends(verify_api_key)],
    ):
        """Return safe datasource summaries associated with a topic."""
        repository = _get_intelligence_repository(req)
        try:
            summaries = repository.get_topic_datasources(topic_id)
        except ValueError as exc:
            raise _map_topic_datasource_error(exc)
        return [_summary_to_response(s) for s in summaries]

    @app.put(
        "/intelligence/topics/{topic_id}/datasources",
        response_model=List[SafeDataSourceSummaryResponse],
    )
    async def set_topic_datasources(
        topic_id: str,
        request_body: TopicDatasourceSetRequest,
        req: Request,
        _: Annotated[str, Depends(verify_api_key)],
    ):
        """Atomically replace all datasource associations for a topic."""
        repository = _get_intelligence_repository(req)
        try:
            repository.set_topic_datasources(topic_id, request_body.datasource_ids)
            summaries = repository.get_topic_datasources(topic_id)
        except ValueError as exc:
            raise _map_topic_datasource_error(exc)
        return [_summary_to_response(s) for s in summaries]

    @app.post(
        "/intelligence/topics/{topic_id}/datasources/{datasource_id}",
        response_model=List[SafeDataSourceSummaryResponse],
    )
    async def add_topic_datasource(
        topic_id: str,
        datasource_id: str,
        req: Request,
        _: Annotated[str, Depends(verify_api_key)],
    ):
        """Idempotently add a datasource association to a topic."""
        repository = _get_intelligence_repository(req)
        try:
            repository.add_topic_datasources(topic_id, [datasource_id])
            summaries = repository.get_topic_datasources(topic_id)
        except ValueError as exc:
            raise _map_topic_datasource_error(exc)
        return [_summary_to_response(s) for s in summaries]

    @app.delete(
        "/intelligence/topics/{topic_id}/datasources/{datasource_id}",
        response_model=List[SafeDataSourceSummaryResponse],
    )
    async def remove_topic_datasource(
        topic_id: str,
        datasource_id: str,
        req: Request,
        _: Annotated[str, Depends(verify_api_key)],
    ):
        """Idempotently remove a datasource association from a topic."""
        repository = _get_intelligence_repository(req)
        try:
            repository.remove_topic_datasources(topic_id, [datasource_id])
            summaries = repository.get_topic_datasources(topic_id)
        except ValueError as exc:
            raise _map_topic_datasource_error(exc)
        return [_summary_to_response(s) for s in summaries]
# ── Background webhook processing ────────────────────────────────────────


async def _process_webhook_update_background(
    command_handler: Any,
    payload: Dict[str, Any],
    secret_token: Optional[str],
) -> None:
    """Process a Telegram webhook update in the background.

    Runs outside the request-response cycle so the webhook endpoint can
    return 200 OK before long-running handlers (e.g. LLM calls) complete.
    Deduplication by update_id is handled inside handle_webhook_update.
    """
    try:
        await command_handler.handle_webhook_update(payload, secret_token=secret_token)
    except PermissionError:
        logger.warning("Background webhook update rejected: permission denied")
    except RuntimeError as exc:
        logger.error(f"Background webhook update failed: {exc}")
    except Exception:
        logger.exception("Unexpected error in background webhook processing")


# ── Route Registration: Infrastructure ─────────────────────────────────


def register_infrastructure_routes(app: FastAPI) -> None:
    """Register infrastructure routes: /health, /telegram/webhook."""

    @app.get("/health")
    async def health_check(req: Request):
        """健康检查端点"""
        state = _get_app_state(req)
        return {"status": "healthy", "initialized": state.controller is not None}

    @app.post(os.getenv("TELEGRAM_WEBHOOK_PATH", "/telegram/webhook"))
    async def telegram_webhook(req: Request, background_tasks: BackgroundTasks):
        """Telegram webhook endpoint.

        Processes the update in a background task so the webhook returns
        200 OK immediately.  This prevents Telegram from retrying the same
        update when long-running handlers (e.g. LLM merge previews) exceed
        the webhook response timeout.
        """
        command_handler = _get_telegram_command_handler(req)
        payload = await req.json()
        secret_token = req.headers.get(TELEGRAM_WEBHOOK_SECRET_HEADER)

        # Log incoming update type for debugging
        if isinstance(payload, dict) and "message" in payload:
            msg_data = payload["message"]
            chat_id = msg_data.get("chat", {}).get("id", "unknown")
            from_user = msg_data.get("from", {})
            user_info = f"{from_user.get('username', 'unknown')} ({from_user.get('id', 'unknown')})"
            logger.info(
                f"Telegram webhook received update: chat_id={chat_id}, "
                f"user={user_info}, text={msg_data.get('text', '')[:80]}"
            )

        # Validate secret token synchronously so we reject unauthenticated
        # requests immediately.
        expected_secret = command_handler.get_webhook_secret_token()
        if secret_token != expected_secret:
            logger.warning("Telegram webhook rejected: invalid secret token")
            raise HTTPException(status_code=403, detail="Invalid Telegram webhook secret token")

        # Process the update in the background so we can return 200 OK
        # before the handler (which may call LLMs) completes.
        background_tasks.add_task(
            _process_webhook_update_background,
            command_handler,
            payload,
            secret_token,
        )

        return {"ok": True}


# ── App Factory ────────────────────────────────────────────────────────


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

        app_state.intelligence_repository = getattr(controller, "intelligence_repository", None)
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

    # Register routes by domain
    register_news_routes(app)
    register_intelligence_routes(app)
    register_infrastructure_routes(app)

    return app
