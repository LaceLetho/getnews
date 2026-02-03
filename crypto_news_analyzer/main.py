"""
主程序入口

系统的主要入口点，负责初始化和协调各个组件。
"""

import sys
import logging
from pathlib import Path

from .config.manager import ConfigManager
from .utils.logging import setup_logging, get_log_manager
from .utils.errors import ErrorRecoveryManager, ConfigError


def initialize_system(config_path: str = "./config.json") -> tuple:
    """
    初始化系统
    
    Args:
        config_path: 配置文件路径
        
    Returns:
        (config_manager, log_manager, error_manager) 元组
        
    Raises:
        ConfigError: 配置初始化失败
    """
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


def main():
    """主函数"""
    try:
        config_manager, log_manager, error_manager = initialize_system()
        logger = logging.getLogger(__name__)
        
        # 验证配置
        config_data = config_manager.config_data
        auth_config = config_manager.get_auth_config()
        
        # 检查必需的认证信息
        if not auth_config.llm_api_key:
            logger.warning("LLM API密钥未配置")
        
        if not auth_config.telegram_bot_token:
            logger.warning("Telegram Bot Token未配置")
        
        logger.info("系统启动完成，配置验证通过")
        
    except Exception as e:
        print(f"系统启动失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()