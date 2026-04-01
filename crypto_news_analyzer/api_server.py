"""
HTTP API服务器

提供HTTP接口用于手动触发分析报告生成。
使用FastAPI Lifespan Events管理controller生命周期，避免全局变量问题。
"""

from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from datetime import datetime, timezone
import re
import uuid
from typing import Annotated, Any, Optional, Union, cast

from fastapi import FastAPI, HTTPException, Depends, Response, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field, field_validator
import os
import logging

from .execution_coordinator import MainController
from .domain.models import AnalysisRequest, Priority
from .domain.repositories import AnalysisRepository
from .storage.repositories import SQLiteAnalysisRepository

logger = logging.getLogger(__name__)
security = HTTPBearer()
USER_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,128}$")


class AppState:
    """Application state container for lifespan management."""

    def __init__(self):
        self.controller: Optional[MainController] = None
        self.analysis_repository: Optional[AnalysisRepository] = None
        self.analyze_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="api-analyze")

    def cleanup(self):
        """Cleanup resources on shutdown."""
        if self.controller:
            try:
                self.controller.stop_scheduler()
                logger.info("Scheduler stopped during cleanup")
            except Exception as e:
                logger.warning(f"Error stopping scheduler: {e}")

            try:
                self.controller.stop_command_listener()
                logger.info("Command listener stopped during cleanup")
            except Exception as e:
                logger.warning(f"Error stopping command listener: {e}")

        # Shutdown executor
        if self.analyze_executor:
            self.analyze_executor.shutdown(wait=False)

        # Clear references
        self.controller = None
        self.analysis_repository = None


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
    if controller and hasattr(controller, "analysis_repository") and controller.analysis_repository is not None:
        state.analysis_repository = controller.analysis_repository
        return state.analysis_repository

    if controller and hasattr(controller, "data_manager") and controller.data_manager is not None:
        state.analysis_repository = SQLiteAnalysisRepository(controller.data_manager)
        return state.analysis_repository

    raise HTTPException(status_code=503, detail="System not initialized")


def verify_api_key(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)]
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


def _build_analysis_request_from_job(job: AnalyzeJobRecord, controller: Optional[MainController]) -> AnalysisRequest:
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


def _persist_completed_api_job_success(job: AnalyzeJobRecord, controller: MainController) -> None:
    recipient_key = controller._normalize_manual_recipient_key("api", job.user_id)
    controller._persist_manual_analysis_success(
        recipient_key=recipient_key,
        time_window_hours=job.time_window_hours,
        items_count=job.items_processed,
        final_report_messages=job.final_report_messages,
    )
    job.success_persisted = True


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


def create_api_server(
    config_path: str = "./config.json",
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
            raise HTTPException(
                status_code=400,
                detail=f"Hours must be at least {min_hours}"
            )

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

    @app.get("/health")
    async def health_check(req: Request):
        """健康检查端点"""
        state = _get_app_state(req)
        return {"status": "healthy", "initialized": state.controller is not None}

    return app
