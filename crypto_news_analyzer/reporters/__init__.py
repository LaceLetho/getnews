"""
报告生成模块

包含Telegram发送器、Telegram格式化器、报告生成器、Telegram命令处理器和相关工具类。
"""

from .telegram_sender import (
    TelegramSender, 
    TelegramSenderSync, 
    TelegramConfig, 
    SendResult,
    create_telegram_config,
    validate_telegram_credentials,
    test_telegram_connection
)
from .telegram_formatter import (
    TelegramFormatter,
    FormattingConfig,
    create_formatter,
    escape_telegram_text,
    create_telegram_link
)
from .report_generator import (
    ReportGenerator,
    AnalyzedData,
    create_report_generator,
    categorize_analysis_results
)
from .telegram_command_handler import (
    TelegramCommandHandler,
    TelegramCommandHandlerSync,
    create_telegram_command_handler,
    create_default_command_config
)

__all__ = [
    'TelegramSender',
    'TelegramSenderSync',
    'TelegramConfig',
    'SendResult',
    'create_telegram_config',
    'validate_telegram_credentials',
    'test_telegram_connection',
    'TelegramFormatter',
    'FormattingConfig',
    'create_formatter',
    'escape_telegram_text',
    'create_telegram_link',
    'ReportGenerator',
    'AnalyzedData',
    'create_report_generator',
    'categorize_analysis_results',
    'TelegramCommandHandler',
    'TelegramCommandHandlerSync',
    'create_telegram_command_handler',
    'create_default_command_config'
]