"""
报告生成模块

包含报告生成器、Telegram发送器和相关工具类。
"""

from .report_generator import ReportGenerator, ReportTemplate, AnalyzedData, create_analyzed_data, validate_report_data
from .telegram_sender import (
    TelegramSender, 
    TelegramSenderSync, 
    TelegramConfig, 
    SendResult,
    create_telegram_config,
    validate_telegram_credentials,
    test_telegram_connection
)

__all__ = [
    'ReportGenerator',
    'ReportTemplate', 
    'AnalyzedData',
    'create_analyzed_data',
    'validate_report_data',
    'TelegramSender',
    'TelegramSenderSync',
    'TelegramConfig',
    'SendResult',
    'create_telegram_config',
    'validate_telegram_credentials',
    'test_telegram_connection'
]