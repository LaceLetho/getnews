"""
日志管理系统

提供统一的日志配置和管理功能。
"""

import logging
import logging.handlers
import os
from pathlib import Path
from typing import Optional
from datetime import datetime


class LogManager:
    """日志管理器"""
    
    def __init__(self, log_dir: str = "./logs"):
        """
        初始化日志管理器
        
        Args:
            log_dir: 日志目录
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._setup_logging()
    
    def _setup_logging(self) -> None:
        """设置日志配置"""
        # 创建根日志器
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)
        
        # 清除现有处理器
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        # 创建格式器
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # 控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)
        
        # 文件处理器 - 应用日志
        app_log_file = self.log_dir / "crypto_news_analyzer.log"
        file_handler = logging.handlers.RotatingFileHandler(
            app_log_file,
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
        
        # 错误日志文件处理器
        error_log_file = self.log_dir / "errors.log"
        error_handler = logging.handlers.RotatingFileHandler(
            error_log_file,
            maxBytes=5*1024*1024,  # 5MB
            backupCount=3,
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(formatter)
        root_logger.addHandler(error_handler)
    
    def setup_logging(self, log_level: str = "INFO") -> None:
        """
        设置日志级别
        
        Args:
            log_level: 日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        """
        level = getattr(logging, log_level.upper(), logging.INFO)
        logging.getLogger().setLevel(level)
    
    def get_logger(self, name: str) -> logging.Logger:
        """
        获取指定名称的日志器
        
        Args:
            name: 日志器名称
            
        Returns:
            日志器实例
        """
        return logging.getLogger(name)
    
    def log_crawl_status(self, status: dict) -> None:
        """
        记录爬取状态
        
        Args:
            status: 爬取状态信息
        """
        logger = self.get_logger("crawl_status")
        logger.info(f"爬取状态: {status}")
    
    def log_analysis_results(self, results: list) -> None:
        """
        记录分析结果
        
        Args:
            results: 分析结果列表
        """
        logger = self.get_logger("analysis")
        logger.info(f"分析完成，处理了 {len(results)} 条内容")
    
    def log_error(self, component: str, error: Exception) -> None:
        """
        记录错误信息
        
        Args:
            component: 组件名称
            error: 异常对象
        """
        logger = self.get_logger(component)
        logger.error(f"组件 {component} 发生错误: {str(error)}", exc_info=True)
    
    def log_execution_summary(self, summary: dict) -> None:
        """
        记录执行摘要
        
        Args:
            summary: 执行摘要信息
        """
        logger = self.get_logger("execution")
        logger.info(f"执行摘要: {summary}")
    
    def create_execution_log(self, execution_id: str) -> logging.Logger:
        """
        为特定执行创建专用日志器
        
        Args:
            execution_id: 执行ID
            
        Returns:
            专用日志器
        """
        logger_name = f"execution.{execution_id}"
        logger = logging.getLogger(logger_name)
        
        # 创建专用文件处理器
        log_file = self.log_dir / f"execution_{execution_id}.log"
        handler = logging.FileHandler(log_file, encoding='utf-8')
        
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
        
        return logger


# 全局日志管理器实例
_log_manager: Optional[LogManager] = None


def get_log_manager() -> LogManager:
    """获取全局日志管理器实例"""
    global _log_manager
    if _log_manager is None:
        _log_manager = LogManager()
    return _log_manager


def setup_logging(log_level: str = "INFO", log_dir: str = "./logs") -> None:
    """
    设置全局日志配置
    
    Args:
        log_level: 日志级别
        log_dir: 日志目录
    """
    global _log_manager
    _log_manager = LogManager(log_dir)
    _log_manager.setup_logging(log_level)


def get_logger(name: str) -> logging.Logger:
    """
    获取指定名称的日志器
    
    Args:
        name: 日志器名称
        
    Returns:
        日志器实例
    """
    log_manager = get_log_manager()
    return log_manager.get_logger(name)