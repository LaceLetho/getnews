"""
主程序入口

系统的主要入口点，负责初始化和协调各个组件。
支持一次性执行模式和定时调度模式。
"""

import sys
import os
import argparse
import logging
from pathlib import Path

from .execution_coordinator import MainController, run_one_time_execution, run_scheduled_mode
from .utils.logging import setup_logging


def main():
    """主函数"""
    # 设置日志系统
    log_level = os.environ.get('LOG_LEVEL', 'INFO')
    setup_logging(log_level=log_level)
    logger = logging.getLogger(__name__)
    
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="加密货币新闻分析工具")
    parser.add_argument("--mode", choices=["once", "schedule"], default="once",
                       help="运行模式: once=一次性执行, schedule=定时调度")
    parser.add_argument("--config", default="./config.json",
                       help="配置文件路径")
    
    args = parser.parse_args()
    
    try:
        logger.info(f"启动加密货币新闻分析系统，模式: {args.mode}")
        
        if args.mode == "once":
            # 一次性执行模式
            exit_code = run_one_time_execution(args.config)
        elif args.mode == "schedule":
            # 定时调度模式
            exit_code = run_scheduled_mode(args.config)
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
    
    try:
        # 设置日志系统
        setup_logging()
        logger = logging.getLogger(__name__)
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