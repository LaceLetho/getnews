import sys
import os
import argparse
import logging
import threading
import signal
from typing import Optional

from .execution_coordinator import MainController
from .semantic_search import run_embedding_backfill_once
from .utils.errors import UnsupportedBackendError
from .utils.logging import setup_logging

SUPPORTED_RUNTIME_MODES = (
    "analysis-service",
    "api-only",
    "ingestion",
    "embedding-backfill",
)
DEFAULT_RUNTIME_MODE = "analysis-service"


def normalize_runtime_mode(mode: str, logger: logging.Logger) -> str:
    normalized_mode = (mode or DEFAULT_RUNTIME_MODE).strip().lower()

    if normalized_mode not in SUPPORTED_RUNTIME_MODES:
        raise ValueError(
            f"不支持的运行模式: {normalized_mode}。支持的模式: {', '.join(SUPPORTED_RUNTIME_MODES)}"
        )

    return normalized_mode


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="加密货币新闻分析工具")
    parser.add_argument(
        "--mode",
        default=DEFAULT_RUNTIME_MODE,
        help=(
            "运行模式: analysis-service=公网分析服务(API+Telegram，无调度器，生产默认), "
            "api-only=仅API服务(隔离用途), ingestion=仅数据摄取服务, "
            "embedding-backfill=一次性历史Embedding回填。"
        ),
    )
    parser.add_argument("--config", default="./config.jsonc", help="配置文件路径")
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="embedding-backfill模式下每批处理的文章数量",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="embedding-backfill模式下最多处理的缺失Embedding文章数量",
    )
    parser.add_argument(
        "--include-intelligence",
        action="store_true",
        default=False,
        help="embedding-backfill模式下同时回填raw_intelligence_items的Embedding",
    )
    parser.add_argument(
        "--intelligence-days",
        type=int,
        default=7,
        help="embedding-backfill模式下只回填N天内收集的intelligence记录（默认7天）",
    )
    return parser


def main():
    """主函数"""
    # 设置日志系统
    log_level = os.environ.get("LOG_LEVEL", "INFO")
    setup_logging(log_level=log_level)
    logger = logging.getLogger(__name__)

    # 解析命令行参数
    parser = build_argument_parser()
    args = parser.parse_args()

    try:
        args.mode = normalize_runtime_mode(args.mode, logger)
        logger.info(f"启动加密货币新闻分析系统，模式: {args.mode}")

        if args.mode == "analysis-service":
            exit_code = run_analysis_service(args.config)
        elif args.mode == "api-only":
            exit_code = run_api_only_service(args.config)
        elif args.mode == "ingestion":
            exit_code = run_ingestion_loop(args.config)
        elif args.mode == "embedding-backfill":
            exit_code = run_embedding_backfill(
                args.config,
                batch_size=args.batch_size,
                limit=args.limit,
                intelligence_days=(
                    args.intelligence_days if args.include_intelligence else None
                ),
            )
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


def _run_api_service(config_path: str, enable_telegram: bool, mode: str) -> int:
    import uvicorn
    from .api_server import create_api_server

    logger = logging.getLogger(__name__)
    logger.info("启动 %s 服务模式", mode)

    try:
        os.environ["CRYPTO_NEWS_RUNTIME_MODE"] = mode
        app = create_api_server(
            config_path,
            enable_scheduler=False,
            enable_telegram=enable_telegram,
        )

        host = os.environ.get("API_HOST", "0.0.0.0")
        port = int(os.environ.get("API_PORT", "8080"))

        telegram_state = "启用Telegram" if enable_telegram else "无Telegram监听"
        logger.info("%s 服务启动在 %s:%s（无调度器，%s）", mode, host, port, telegram_state)
        uvicorn.run(app, host=host, port=port)

        return 0
    except Exception as e:
        logger.error("%s 服务启动失败: %s", mode, e)
        return 1


def run_api_only_service(config_path: str = "./config.jsonc") -> int:
    return _run_api_service(config_path, enable_telegram=False, mode="api-only")


def run_analysis_service(config_path: str = "./config.jsonc") -> int:
    """运行公网分析服务（API + Telegram，无调度器）。"""
    return _run_api_service(config_path, enable_telegram=True, mode="analysis-service")


def run_ingestion_loop(config_path: str = "./config.jsonc") -> int:
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


def run_embedding_backfill(
    config_path: str = "./config.jsonc",
    batch_size: int = 100,
    limit: Optional[int] = None,
    intelligence_days: Optional[int] = None,
) -> int:
    """运行一次性历史Embedding回填任务。"""
    logger = logging.getLogger(__name__)
    logger.info(
        "启动历史Embedding回填模式，batch_size=%s limit=%s intelligence_days=%s",
        batch_size,
        limit,
        intelligence_days,
    )

    try:
        os.environ["CRYPTO_NEWS_RUNTIME_MODE"] = "embedding-backfill"
        run_embedding_backfill_once(
            config_path=config_path,
            batch_size=batch_size,
            limit=limit,
            intelligence_days=intelligence_days,
        )
        return 0
    except UnsupportedBackendError as exc:
        logger.error(f"Embedding回填仅支持PostgreSQL后端: {exc}")
        return 1
    except Exception as exc:
        logger.error(f"Embedding回填失败: {exc}")
        return 1


if __name__ == "__main__":
    main()
