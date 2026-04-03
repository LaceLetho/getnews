import sys
import os
import argparse
import logging
import threading
import signal

from .execution_coordinator import MainController
from .utils.logging import setup_logging


SUPPORTED_RUNTIME_MODES = (
    "analysis-service",
    "api-only",
    "ingestion",
)
DEFAULT_RUNTIME_MODE = "analysis-service"


def normalize_runtime_mode(mode: str, logger: logging.Logger) -> str:
    normalized_mode = (mode or DEFAULT_RUNTIME_MODE).strip().lower()

    if normalized_mode not in SUPPORTED_RUNTIME_MODES:
        raise ValueError(
            f"不支持的运行模式: {normalized_mode}。支持的模式: {', '.join(SUPPORTED_RUNTIME_MODES)}"
        )

    return normalized_mode


def main():
    """主函数"""
    # 设置日志系统
    log_level = os.environ.get('LOG_LEVEL', 'INFO')
    setup_logging(log_level=log_level)
    logger = logging.getLogger(__name__)
    
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="加密货币新闻分析工具")
    parser.add_argument(
        "--mode",
        default=DEFAULT_RUNTIME_MODE,
        help=(
            "运行模式: analysis-service=公网分析服务(API+Telegram，无调度器，生产默认), "
            "api-only=仅API服务(隔离用途), ingestion=仅数据摄取服务。"
        ),
    )
    parser.add_argument("--config", default="./config.json",
                       help="配置文件路径")
    
    args = parser.parse_args()
    
    try:
        args.mode = normalize_runtime_mode(args.mode, logger)
        logger.info(f"启动加密货币新闻分析系统，模式: {args.mode}")
        
        if args.mode == "analysis-service":
            exit_code = run_analysis_service(args.config)
        elif args.mode == "api-only":
            # 仅API服务模式（Railway拆分架构：analysis服务，无调度器/监听）
            exit_code = run_api_only_service(args.config)
        elif args.mode == "ingestion":
            # 仅数据摄取服务（Railway拆分架构：ingestion服务）
            exit_code = run_ingestion_service(args.config)
        else:
            logger.error(f"不支持的运行模式: {args.mode}")
            exit_code = 1
        
        logger.info(f"系统退出，状态码: {exit_code}")
        sys.exit(exit_code)
        
    except KeyboardInterrupt:
        logger.info("接收到中断信号，正在退出...")
        sys.exit(0)
    except Exception as e:
        logger.error(f"系统运行异常: {e}")
        sys.exit(1)


def run_api_only_service(config_path: str = "./config.json") -> int:
    """
    运行隔离的HTTP API服务器（Railway拆分架构：analysis服务）

    此模式仅提供HTTP API端点，不启动调度器或Telegram命令监听。
    用于Railway拆分部署中的公共API服务。

    Args:
        config_path: 配置文件路径

    Returns:
        退出状态码
    """
    import uvicorn
    from .api_server import create_api_server

    logger = logging.getLogger(__name__)
    logger.info("启动 API-only 服务模式（Railway analysis服务）")

    try:
        os.environ["CRYPTO_NEWS_RUNTIME_MODE"] = "api-only"
        # start_services=False 确保不启动调度器和Telegram监听
        app = create_api_server(config_path, start_services=False)

        host = os.environ.get("API_HOST", "0.0.0.0")
        port = int(os.environ.get("API_PORT", "8080"))

        logger.info(f"API-only 服务启动在 {host}:{port}（无调度器/监听）")
        uvicorn.run(app, host=host, port=port)

        return 0
    except Exception as e:
        logger.error(f"API-only 服务启动失败: {e}")
        return 1


def run_analysis_service(config_path: str = "./config.json") -> int:
    """运行公网分析服务（API + Telegram，无调度器）。"""
    import uvicorn
    from .api_server import create_api_server

    logger = logging.getLogger(__name__)
    logger.info("启动公网分析服务模式（API + Telegram，无调度器）")

    try:
        os.environ["CRYPTO_NEWS_RUNTIME_MODE"] = "analysis-service"
        app = create_api_server(
            config_path,
            start_services=False,
            start_scheduler=False,
            start_command_listener=True,
        )

        host = os.environ.get("API_HOST", "0.0.0.0")
        port = int(os.environ.get("API_PORT", "8080"))

        logger.info(f"公网分析服务启动在 {host}:{port}（无调度器）")
        uvicorn.run(app, host=host, port=port)

        return 0
    except Exception as e:
        logger.error(f"公网分析服务启动失败: {e}")
        return 1


def run_ingestion_loop(config_path: str = "./config.json") -> int:
    """
    运行数据摄取循环（Railway拆分架构：ingestion服务）

    此模式仅启动定时摄取任务，执行数据爬取，不提供HTTP API或Telegram监听。
    用于Railway拆分部署中的私有ingestion服务。

    Args:
        config_path: 配置文件路径

    Returns:
        退出状态码
    """
    logger = logging.getLogger(__name__)
    logger.info("启动数据摄取循环模式（Railway ingestion服务）")

    try:
        os.environ["CRYPTO_NEWS_RUNTIME_MODE"] = "ingestion"
        controller = MainController(config_path)
        if not controller.initialize_ingestion_system():
            logger.error("系统初始化失败")
            return 1

        controller.start_scheduler()
        logger.info("数据摄取循环已启动，等待任务执行...")

        stop_event = threading.Event()

        def signal_handler(signum, frame):
            logger.info(f"接收到信号 {signum}，正在停止数据摄取循环...")
            stop_event.set()

        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)

        # 等待停止信号
        while not stop_event.is_set():
            stop_event.wait(1)

        logger.info("数据摄取循环已停止")
        return 0
    except Exception as e:
        logger.error(f"数据摄取循环模式启动失败: {e}")
        return 1


def run_ingestion_service(config_path: str = "./config.json") -> int:
    """
    运行数据摄取服务（Railway拆分架构：ingestion服务）

    此模式仅启动定时数据爬取，不提供分析功能。

    Args:
        config_path: 配置文件路径

    Returns:
        退出状态码
    """
    logger = logging.getLogger(__name__)
    logger.info("启动数据摄取服务模式（Railway ingestion服务）")
    return run_ingestion_loop(config_path)


if __name__ == "__main__":
    main()
