"""
HTTP API服务器

提供HTTP接口用于手动触发分析报告生成。
"""

from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional
import os
import logging

from .execution_coordinator import MainController

logger = logging.getLogger(__name__)
security = HTTPBearer()

class AnalyzeRequest(BaseModel):
    hours: int  # 必填，分析最近N小时的消息

class AnalyzeResponse(BaseModel):
    success: bool
    report: str
    items_processed: int
    time_window_hours: int

app = FastAPI(title="Crypto News Analyzer API")
controller: Optional[MainController] = None

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
    
    - hours: 分析最近N小时的消息（必填）
    """
    if not controller:
        raise HTTPException(status_code=503, detail="System not initialized")
    
    # 限制最大24小时
    hours = min(request.hours, 24)
    
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
    
    controller = MainController(config_path)
    if not controller.initialize_system():
        raise RuntimeError("Failed to initialize system")
    
    logger.info("API server initialized")
    return app
