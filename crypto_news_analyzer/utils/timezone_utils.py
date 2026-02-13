"""
时区工具模块

提供统一的时区处理功能，确保所有Telegram消息使用东八区(UTC+8)时区。
"""

from datetime import datetime, timezone, timedelta
from typing import Optional
from email.utils import parsedate_to_datetime


# 东八区时区对象
UTC_PLUS_8 = timezone(timedelta(hours=8))


def now_utc8() -> datetime:
    """
    获取当前东八区时间
    
    Returns:
        当前东八区时间（带时区信息）
    """
    return datetime.now(UTC_PLUS_8)


def parse_rfc2822_to_utc8(time_str: str) -> Optional[datetime]:
    """
    解析RFC 2822格式的时间字符串并转换为东八区时间
    
    Args:
        time_str: RFC 2822格式的时间字符串（如 'Mon, 15 Jan 2024 14:30:00 +0000'）
        
    Returns:
        转换后的东八区datetime对象，解析失败返回None
    """
    try:
        # 使用email.utils.parsedate_to_datetime解析RFC 2822格式
        dt = parsedate_to_datetime(time_str)
        # 转换为东八区
        return dt.astimezone(UTC_PLUS_8)
    except Exception:
        return None


def format_rfc2822_to_utc8_string(
    time_str: str,
    format_str: str = "%m-%d %H:%M"
) -> str:
    """
    解析RFC 2822格式时间并格式化为东八区时间字符串
    
    Args:
        time_str: RFC 2822格式的时间字符串
        format_str: 输出格式字符串
        
    Returns:
        格式化后的东八区时间字符串，解析失败返回原字符串
    """
    dt = parse_rfc2822_to_utc8(time_str)
    if dt:
        return dt.strftime(format_str)
    return time_str


def format_datetime_utc8(
    dt: Optional[datetime] = None,
    format_str: str = "%Y-%m-%d %H:%M:%S"
) -> str:
    """
    格式化datetime为东八区时间字符串
    
    Args:
        dt: datetime对象，如果为None则使用当前时间
        format_str: 时间格式字符串
        
    Returns:
        格式化后的时间字符串
    """
    if dt is None:
        dt = now_utc8()
    elif dt.tzinfo is None:
        # 如果没有时区信息，假设为本地时间并转换为UTC+8
        dt = dt.replace(tzinfo=timezone.utc).astimezone(UTC_PLUS_8)
    else:
        # 转换为UTC+8
        dt = dt.astimezone(UTC_PLUS_8)
    
    return dt.strftime(format_str)


def format_datetime_short_utc8(dt: Optional[datetime] = None) -> str:
    """
    格式化datetime为短格式东八区时间字符串（不含年份）
    
    Args:
        dt: datetime对象，如果为None则使用当前时间
        
    Returns:
        格式化后的时间字符串，格式为 "MM-DD HH:MM"
    """
    return format_datetime_utc8(dt, "%m-%d %H:%M")


def format_datetime_full_utc8(dt: Optional[datetime] = None) -> str:
    """
    格式化datetime为完整格式东八区时间字符串
    
    Args:
        dt: datetime对象，如果为None则使用当前时间
        
    Returns:
        格式化后的时间字符串，格式为 "YYYY-MM-DD HH:MM:SS"
    """
    return format_datetime_utc8(dt, "%Y-%m-%d %H:%M:%S")


def convert_to_utc8(dt: datetime) -> datetime:
    """
    将datetime对象转换为东八区时间
    
    Args:
        dt: datetime对象
        
    Returns:
        转换后的东八区时间（带时区信息）
    """
    if dt.tzinfo is None:
        # 如果没有时区信息，假设为本地时间
        dt = dt.replace(tzinfo=timezone.utc).astimezone(UTC_PLUS_8)
    else:
        # 转换为UTC+8
        dt = dt.astimezone(UTC_PLUS_8)
    
    return dt
