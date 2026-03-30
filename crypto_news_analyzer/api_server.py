"""
HTTP API服务器

提供HTTP接口用于手动触发分析报告生成。

## TODO: Race Condition in Global Controller Variable

**Issue**: The global `controller` variable can have race conditions when running
with multiple workers (e.g., `uvicorn main:app --workers 4`). Each worker process
has its own memory space, so they don't share the `controller` instance.

**Symptoms**:
- Health check returns different status on different workers
- Multiple analysis executions may run simultaneously across workers
- Resource leaks when processes restart

**Solution Options**:

### Option 1: Use FastAPI Lifespan Events (Recommended)
```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize controller and store in app.state
    app.state.controller = MainController(config_path)
    app.state.controller.initialize_system()
    yield
    # Shutdown: Cleanup resources
    app.state.controller.cleanup_resources()

app = FastAPI(lifespan=lifespan)

# Access controller via request.app.state.controller
@app.post("/analyze")
async def analyze(request: Request, ...):
    controller = request.app.state.controller
    ...
```

### Option 2: Single-Process Deployment
Run with only one worker to avoid inter-process issues:
```bash
uvicorn api_server:app --workers 1
```

### Option 3: External State Store (Advanced)
Use Redis or similar to share controller state across workers:
- Store controller initialization status in Redis
- Use distributed locking (Redis Lock) for analysis execution
- Implement proper leader election if needed

**Recommended Approach**: Option 1 (Lifespan Events) is simplest and most
idiomatic for FastAPI. It ensures proper lifecycle management and works
with single or multiple workers.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import re
import threading
import uuid
from typing import Annotated, Any

from fastapi import FastAPI, HTTPException, Depends, Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field, field_validator
import os
import logging

from .execution_coordinator import MainController

logger = logging.getLogger(__name__)
security = HTTPBearer()
USER_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,128}$")

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
    started_at: str | None = None
    completed_at: str | None = None
    items_processed: int = 0
    error: str | None = None
    result_available: bool = False


class AnalyzeJobResultResponse(BaseModel):
    success: bool
    job_id: str
    status: str
    report: str
    items_processed: int
    time_window_hours: int
    error: str | None = None


class AnalyzeJobRecord(BaseModel):
    job_id: str
    user_id: str
    status: str
    time_window_hours: int
    created_at: str
    started_at: str | None = None
    completed_at: str | None = None
    report: str = ""
    items_processed: int = 0
    error: str | None = None
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

app = FastAPI(title="Crypto News Analyzer API")
controller: MainController | None = None
analyze_jobs: dict[str, AnalyzeJobRecord] = {}
analyze_jobs_lock = threading.Lock()
analyze_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="api-analyze")

def get_analysis_config():
    """获取分析配置"""
    if controller and controller.config_manager:
        return controller.config_manager.get_analysis_config()
    return {"max_analysis_window_hours": 24, "min_analysis_window_hours": 1}

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


def _trim_finished_jobs(max_finished_jobs: int = 100) -> None:
    finished_job_ids = [
        job_id
        for job_id, job in analyze_jobs.items()
        if job.status in {"completed", "failed"}
    ]
    if len(finished_job_ids) <= max_finished_jobs:
        return

    finished_job_ids.sort(key=lambda job_id: analyze_jobs[job_id].completed_at or analyze_jobs[job_id].created_at)
    for job_id in finished_job_ids[:-max_finished_jobs]:
        _ = analyze_jobs.pop(job_id, None)


def get_analyze_job(job_id: str) -> AnalyzeJobRecord:
    with analyze_jobs_lock:
        job = analyze_jobs.get(job_id)

    if job is None:
        raise HTTPException(status_code=404, detail="Analyze job not found")

    return job


def _run_analyze_job(job_id: str) -> None:
    if controller is None:
        with analyze_jobs_lock:
            job = analyze_jobs.get(job_id)
            if job is None:
                return
            job.status = "failed"
            job.completed_at = _utcnow_iso()
            job.error = "System not initialized"
        return

    with analyze_jobs_lock:
        job = analyze_jobs.get(job_id)
        if job is None:
            return
        job.status = "running"
        job.started_at = _utcnow_iso()

    try:
        result = controller.analyze_by_time_window(
            chat_id=job.user_id,
            time_window_hours=job.time_window_hours,
            manual_source="api",
        )
        with analyze_jobs_lock:
            stored_job = analyze_jobs.get(job_id)
            if stored_job is None:
                return
            stored_job.completed_at = _utcnow_iso()
            stored_job.items_processed = result.get("items_processed", 0)
            if result.get("success"):
                stored_job.status = "completed"
                stored_job.report = result.get("report_content", "")
                stored_job.error = None
                stored_job.final_report_messages = list(result.get("final_report_messages", []))
            else:
                stored_job.status = "failed"
                stored_job.error = "; ".join(
                    str(error) for error in result.get("errors", [])
                ) or "Analysis failed"
            _trim_finished_jobs()
    except Exception as exc:
        logger.error(f"Async analyze job failed: {exc}")
        with analyze_jobs_lock:
            stored_job = analyze_jobs.get(job_id)
            if stored_job is None:
                return
            stored_job.status = "failed"
            stored_job.completed_at = _utcnow_iso()
            stored_job.error = str(exc)
            _trim_finished_jobs()


def _persist_completed_api_job_success(job: AnalyzeJobRecord) -> None:
    if controller is None:
        raise HTTPException(status_code=503, detail="System not initialized")

    recipient_key = controller._normalize_manual_recipient_key("api", job.user_id)
    controller._persist_manual_analysis_success(
        recipient_key=recipient_key,
        time_window_hours=job.time_window_hours,
        items_count=job.items_processed,
        final_report_messages=job.final_report_messages,
    )
    job.success_persisted = True


def enqueue_analyze_job(hours: int, user_id: str) -> AnalyzeJobRecord:
    job_id = f"analyze_job_{uuid.uuid4().hex}"
    job = AnalyzeJobRecord(
        job_id=job_id,
        user_id=user_id,
        status="queued",
        time_window_hours=hours,
        created_at=_utcnow_iso(),
    )
    with analyze_jobs_lock:
        analyze_jobs[job_id] = job

    _ = analyze_executor.submit(_run_analyze_job, job_id)
    return job

@app.post("/analyze", response_model=AnalyzeAcceptedResponse, status_code=202)
async def analyze(
    request: AnalyzeRequest,
    response: Response,
    _: Annotated[str, Depends(verify_api_key)]
):
    """
    分析指定时间窗口内的消息并返回Markdown报告

    - hours: 分析最近N小时的消息（必填，必须>0）
    """
    if not controller:
        raise HTTPException(status_code=503, detail="System not initialized")

    analysis_config = get_analysis_config()
    max_hours = analysis_config.get("max_analysis_window_hours", 24)
    min_hours = analysis_config.get("min_analysis_window_hours", 1)

    if request.hours < min_hours:
        raise HTTPException(
            status_code=400,
            detail=f"Hours must be at least {min_hours}"
        )

    hours = min(request.hours, max_hours)

    try:
        job = enqueue_analyze_job(hours, request.user_id)
        status_url, result_url = _job_urls(job.job_id)
        response.headers["Location"] = status_url
        response.headers["Retry-After"] = "2"
        return AnalyzeAcceptedResponse(
            success=True,
            job_id=job.job_id,
            status=job.status,
            time_window_hours=hours,
            status_url=status_url,
            result_url=result_url,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"API analyze enqueue error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/analyze/{job_id}", response_model=AnalyzeJobStatusResponse)
async def get_analyze_job_status(
    job_id: str,
    response: Response,
    _: Annotated[str, Depends(verify_api_key)]
):
    response.headers["Retry-After"] = "2"
    return get_analyze_job(job_id).to_status_response()


@app.get("/analyze/{job_id}/result", response_model=AnalyzeJobResultResponse)
async def get_analyze_job_result(
    job_id: str,
    response: Response,
    _: Annotated[str, Depends(verify_api_key)]
):
    job = get_analyze_job(job_id)

    if job.status in {"queued", "running"}:
        response.headers["Retry-After"] = "2"
        raise HTTPException(status_code=202, detail=f"Analyze job still {job.status}")

    if job.status == "completed" and not job.success_persisted:
        try:
            _persist_completed_api_job_success(job)
        except HTTPException:
            raise
        except Exception as exc:
            logger.error(f"Analyze job success persistence failed: {exc}")
            raise HTTPException(status_code=500, detail=str(exc))

    return job.to_result_response()

@app.get("/health")
async def health_check():
    """健康检查端点"""
    return {"status": "healthy", "initialized": controller is not None}

def create_api_server(
    config_path: str = "./config.json",
    start_services: bool = True,
) -> FastAPI:
    """
    创建并初始化API服务器

    Args:
        config_path: 配置文件路径
        start_services: 是否启动调度器和Telegram监听器（默认为True以兼容现有行为）
                         在Railway拆分架构中，API服务应设为False以隔离副作用

    Returns:
        FastAPI应用实例
    """
    global controller

    if controller is not None:
        logger.info("API server already initialized")
        return app

    controller = MainController(config_path)
    if not controller.initialize_system():
        raise RuntimeError("Failed to initialize system")

    if start_services:
        controller.start_scheduler()

        if controller.command_handler:
            controller.start_command_listener()
            logger.info("Telegram command listener started in API mode")
        else:
            logger.warning("Telegram command handler not configured, listener not started")
    else:
        logger.info("API server initialized without scheduler and command listener (isolated mode)")

    logger.info("API server initialized")
    return app
