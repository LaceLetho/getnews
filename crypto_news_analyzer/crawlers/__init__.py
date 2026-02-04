"""
爬取器模块

包含各种数据源的爬取器实现，支持插件化架构。
"""

from .rss_crawler import RSSCrawler
from .x_crawler import XCrawler
from .data_source_interface import DataSourceInterface, DataSourceError, ConfigValidationError, SourceUnavailableError, CrawlError
from .data_source_factory import DataSourceFactory, get_data_source_factory, register_builtin_sources
from .rest_api_crawler import RESTAPICrawler
from .rss_crawler_adapter import RSSCrawlerAdapter
from .x_crawler_adapter import XCrawlerAdapter

# 自动注册内置数据源
try:
    register_builtin_sources()
except Exception as e:
    import logging
    logger = logging.getLogger(__name__)
    logger.warning(f"注册内置数据源时出现错误: {str(e)}")

__all__ = [
    # 原有爬取器（向后兼容）
    'RSSCrawler',
    'XCrawler',
    
    # 插件化架构组件
    'DataSourceInterface',
    'DataSourceError',
    'ConfigValidationError', 
    'SourceUnavailableError',
    'CrawlError',
    'DataSourceFactory',
    'get_data_source_factory',
    'register_builtin_sources',
    
    # 新的数据源实现
    'RESTAPICrawler',
    'RSSCrawlerAdapter',
    'XCrawlerAdapter'
]