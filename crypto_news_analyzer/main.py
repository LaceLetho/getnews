"""
主程序入口

系统的主要入口点，负责初始化和协调各个组件。
支持一次性执行模式和定时调度模式。
"""

import sys
import os
import argparse
import logging
import threading
import signal
from pathlib import Path

from .execution_coordinator import MainController, run_one_time_execution, run_scheduled_mode
from .utils.logging import setup_logging


SUPPORTED_RUNTIME_MODES = (
    "analysis-service",
    "api-only",
    "ingestion",
    "scheduler",
    "schedule",
    "once",
)
DEPRECATED_RUNTIME_MODE_ALIASES = {
    "api-server": "analysis-service",
}
DEFAULT_RUNTIME_MODE = "analysis-service"


def normalize_runtime_mode(mode: str, logger: logging.Logger) -> str:
    normalized_mode = (mode or DEFAULT_RUNTIME_MODE).strip().lower()

    if normalized_mode in DEPRECATED_RUNTIME_MODE_ALIASES:
        mapped_mode = DEPRECATED_RUNTIME_MODE_ALIASES[normalized_mode]
        logger.warning(
            "运行模式 '%s' 已退役，将按拆分服务模式 '%s' 启动",
            normalized_mode,
            mapped_mode,
        )
        return mapped_mode

    if normalized_mode not in SUPPORTED_RUNTIME_MODES:
        raise ValueError(
            f"未知的运行模式: {normalized_mode}。支持的模式: {', '.join(SUPPORTED_RUNTIME_MODES)}"
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
            "api-only=仅API服务(隔离用途), ingestion=仅数据摄取服务, "
            "scheduler=仅启动调度器, schedule=兼容定时调度, once=一次性执行。"
            "已退役的 api-server 会自动映射到 analysis-service"
        ),
    )
    parser.add_argument("--config", default="./config.json",
                       help="配置文件路径")
    
    args = parser.parse_args()
    
    try:
        args.mode = normalize_runtime_mode(args.mode, logger)
        logger.info(f"启动加密货币新闻分析系统，模式: {args.mode}")
        
        if args.mode == "once":
            # 一次性执行模式
            exit_code = run_one_time_execution(args.config)
        elif args.mode == "schedule":
            # 定时调度模式（向后兼容）
            exit_code = run_scheduled_mode(args.config)
        elif args.mode == "scheduler":
            # 仅启动调度器（Railway拆分架构：ingestion服务）
            exit_code = run_scheduler_only(args.config)
        elif args.mode == "analysis-service":
            exit_code = run_analysis_service(args.config)
        elif args.mode == "api-only":
            # 仅API服务模式（Railway拆分架构：analysis服务，无调度器/监听）
            exit_code = run_api_server_isolated(args.config)
        elif args.mode == "ingestion":
            # 仅数据摄取服务（Railway拆分架构：ingestion服务）
            exit_code = run_ingestion_service(args.config)
        else:
            logger.error(f"未知的运行模式: {args.mode}")
            exit_code = 1
        
        logger.info(f"系统退出，状态码: {exit_code}")
        sys.exit(exit_code)
        
    except KeyboardInterrupt:
        logger.info("接收到中断信号，正在退出...")
        sys.exit(0)
    except Exception as e:
        logger.error(f"系统运行异常: {e}")
        sys.exit(1)


def run_api_server(config_path: str = "./config.json") -> int:
    """
    运行HTTP API服务器（向后兼容模式，包含调度器和Telegram监听）

    Args:
        config_path: 配置文件路径

    Returns:
        退出状态码
    """
    import uvicorn
    from .api_server import create_api_server

    logger = logging.getLogger(__name__)
    logger.info("启动API服务器模式（向后兼容，包含调度器和Telegram监听）")

    try:
        os.environ["CRYPTO_NEWS_RUNTIME_MODE"] = "api-server"
        app = create_api_server(config_path, start_services=True)

        # 从环境变量获取配置，或使用默认值
        host = os.environ.get("API_HOST", "0.0.0.0")
        port = int(os.environ.get("API_PORT", "8080"))

        logger.info(f"API服务器启动在 {host}:{port}")
        uvicorn.run(app, host=host, port=port)

        return 0
    except Exception as e:
        logger.error(f"API服务器启动失败: {e}")
        return 1


def run_api_server_isolated(config_path: str = "./config.json") -> int:
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
    logger.info("启动隔离的API服务器模式（Railway analysis服务）")

    try:
        os.environ["CRYPTO_NEWS_RUNTIME_MODE"] = "api-only"
        # start_services=False 确保不启动调度器和Telegram监听
        app = create_api_server(config_path, start_services=False)

        host = os.environ.get("API_HOST", "0.0.0.0")
        port = int(os.environ.get("API_PORT", "8080"))

        logger.info(f"隔离的API服务器启动在 {host}:{port}（无调度器/监听）")
        uvicorn.run(app, host=host, port=port)

        return 0
    except Exception as e:
        logger.error(f"隔离的API服务器启动失败: {e}")
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


def run_scheduler_only(config_path: str = "./config.json") -> int:
    """
    仅运行调度器（Railway拆分架构：ingestion服务）

    此模式仅启动定时调度器，执行数据爬取任务，不提供HTTP API或Telegram监听。
    用于Railway拆分部署中的私有ingestion服务。

    Args:
        config_path: 配置文件路径

    Returns:
        退出状态码
    """
    logger = logging.getLogger(__name__)
    logger.info("启动调度器专用模式（Railway ingestion服务）")

    try:
        os.environ["CRYPTO_NEWS_RUNTIME_MODE"] = "scheduler"
        controller = MainController(config_path)
        if not controller.initialize_ingestion_system():
            logger.error("系统初始化失败")
            return 1

        # 仅启动调度器，不启动API或Telegram监听
        controller.start_scheduler()
        logger.info("调度器已启动，等待任务执行...")

        stop_event = threading.Event()

        def signal_handler(signum, frame):
            logger.info(f"接收到信号 {signum}，正在停止调度器...")
            stop_event.set()

        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)

        # 等待停止信号
        while not stop_event.is_set():
            stop_event.wait(1)

        logger.info("调度器已停止")
        return 0
    except Exception as e:
        logger.error(f"调度器模式启动失败: {e}")
        return 1


def run_ingestion_service(config_path: str = "./config.json") -> int:
    """
    运行数据摄取服务（Railway拆分架构：ingestion服务）

    此模式与scheduler模式相同，仅启动定时数据爬取，不提供分析功能。
    语义上更清晰地表达这是专门的数据摄取服务。

    Args:
        config_path: 配置文件路径

    Returns:
        退出状态码
    """
    logger = logging.getLogger(__name__)
    logger.info("启动数据摄取服务模式（Railway ingestion服务）")
    os.environ["CRYPTO_NEWS_RUNTIME_MODE"] = "ingestion"
    # ingestion模式等同于scheduler模式
    return run_scheduler_only(config_path)


def initialize_system(config_path: str = "./config.json") -> tuple:
    """
    初始化系统（保留向后兼容性）
    
    Args:
        config_path: 配置文件路径
        
    Returns:
        (config_manager, log_manager, error_manager) 元组
        
    Raises:
        ConfigError: 配置初始化失败
    """
    from .config.manager import ConfigManager
    from .utils.logging import get_log_manager
    from .utils.errors import ErrorRecoveryManager, ConfigError
    
    logger = logging.getLogger(__name__)

    try:
        # 设置日志系统
        setup_logging()
        logger.info("开始初始化加密货币新闻分析系统")
        
        # 初始化配置管理器
        config_manager = ConfigManager(config_path)
        config_data = config_manager.load_config()
        logger.info("配置管理器初始化完成")
        
        # 获取日志管理器
        log_manager = get_log_manager()
        
        # 初始化错误恢复管理器
        error_manager = ErrorRecoveryManager()
        logger.info("错误处理框架初始化完成")
        
        logger.info("系统初始化完成")
        return config_manager, log_manager, error_manager
        
    except Exception as e:
        logger.error(f"系统初始化失败: {e}")
        raise ConfigError(f"系统初始化失败: {str(e)}")


if __name__ == "__main__":
    main()
