"""
报告生成模块

包含Telegram发送器、Telegram格式化器和相关工具类。
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
    'create_telegram_link'
]