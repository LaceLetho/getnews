"""
数据模型定义

定义系统中使用的所有数据结构和类型。
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum


@dataclass
class ContentItem:
    """内容项数据模型"""
    id: str
    title: str
    content: str
    url: str
    publish_time: datetime
    source_name: str
    source_type: str  # "rss" or "x"


@dataclass
class RSSSource:
    """RSS订阅源配置"""
    name: str
    url: str
    description: str


@dataclass
class XSource:
    """X/Twitter信息源配置"""
    name: str
    url: str
    type: str  # "list" or "timeline"


@dataclass
class RESTAPISource:
    """REST API数据源配置"""
    name: str
    endpoint: str
    method: str
    headers: Dict[str, str]
    params: Dict[str, Any]
    response_mapping: Dict[str, str]  # 字段映射配置


@dataclass
class AuthConfig:
    """认证配置"""
    x_ct0: str
    x_auth_token: str
    llm_api_key: str
    telegram_bot_token: str
    telegram_channel_id: str


@dataclass
class StorageConfig:
    """存储配置"""
    retention_days: int = 30
    max_storage_mb: int = 1000
    cleanup_frequency: str = "daily"
    database_path: str = "./data/crypto_news.db"


@dataclass
class AnalysisResult:
    """分析结果"""
    content_id: str
    category: str
    confidence: float
    reasoning: str
    should_ignore: bool
    key_points: List[str]


@dataclass
class CrawlResult:
    """爬取结果"""
    source_name: str
    status: str  # "success" or "error"
    item_count: int
    error_message: Optional[str]


@dataclass
class CrawlStatus:
    """爬取状态"""
    rss_results: List[CrawlResult]
    x_results: List[CrawlResult]
    total_items: int
    execution_time: datetime


# 基础内容分类枚举（可通过配置文件动态扩展）
class ContentCategory(Enum):
    """内容分类类别"""
    WHALE_MOVEMENTS = "大户动向"
    INTEREST_RATE_EVENTS = "利率事件"
    US_REGULATORY_POLICY = "美国政府监管政策"
    SECURITY_EVENTS = "安全事件"
    NEW_PRODUCTS = "新产品"
    MARKET_PHENOMENA = "市场新现象"
    UNCATEGORIZED = "未分类"
    IGNORED = "忽略"