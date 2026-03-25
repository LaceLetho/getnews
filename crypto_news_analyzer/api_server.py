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

from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from typing import Optional
from datetime import timezone
import os
import logging

from .execution_coordinator import MainController

logger = logging.getLogger(__name__)
security = HTTPBearer()

class AnalyzeRequest(BaseModel):
    hours: int = Field(..., gt=0, description="分析最近N小时的消息（必填，必须>0）")

class AnalyzeResponse(BaseModel):
    success: bool
    report: str
    items_processed: int
    time_window_hours: int

app = FastAPI(title="Crypto News Analyzer API")
controller: Optional[MainController] = None

def get_analysis_config():
    """获取分析配置"""
    if controller and controller.config_manager:
        return controller.config_manager.get_analysis_config()
    return {"max_analysis_window_hours": 24, "min_analysis_window_hours": 1}

def verify_api_key(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """验证API Key"""
    api_key = credentials.credentials
    expected_key = os.environ.get("API_KEY")
    if not expected_key or api_key != expected_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return api_key

@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze(
    request: AnalyzeRequest,
    api_key: str = Depends(verify_api_key)
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
        result = controller.analyze_by_time_window("api", hours)

        if result["success"]:
            return AnalyzeResponse(
                success=True,
                report=result.get("report_content", ""),
                items_processed=result.get("items_processed", 0),
                time_window_hours=hours
            )
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Analysis failed: {result.get('errors', [])}"
            )
    except Exception as e:
        logger.error(f"API analyze error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    """健康检查端点"""
    return {"status": "healthy", "initialized": controller is not None}

def create_api_server(config_path: str = "./config.json") -> FastAPI:
    """
    创建并初始化API服务器
    
    Args:
        config_path: 配置文件路径
        
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

    controller.start_scheduler()

    if controller.command_handler:
        controller.start_command_listener()
        logger.info("Telegram command listener started in API mode")
    else:
        logger.warning("Telegram command handler not configured, listener not started")

    logger.info("API server initialized")
    return app
