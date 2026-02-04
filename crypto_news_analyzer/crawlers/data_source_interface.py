"""
数据源接口定义

定义所有数据源必须实现的统一接口，支持插件化架构。
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
from datetime import datetime

from ..models import ContentItem, CrawlResult


class DataSourceInterface(ABC):
    """
    数据源统一接口
    
    所有数据源爬取器必须实现此接口，以确保系统的一致性和可扩展性。
    """
    
    @abstractmethod
    def __init__(self, time_window_hours: int, **kwargs):
        """
        初始化数据源
        
        Args:
            time_window_hours: 时间窗口（小时）
            **kwargs: 其他配置参数
        """
        pass
    
    @abstractmethod
    def crawl(self, config: Dict[str, Any]) -> List[ContentItem]:
        """
        爬取数据源内容
        
        Args:
            config: 数据源配置
            
        Returns:
            List[ContentItem]: 爬取到的内容项列表
            
        Raises:
            CrawlerError: 爬取失败时抛出
        """
        pass
    
    @abstractmethod
    def crawl_all_sources(self, sources: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        爬取所有配置的数据源
        
        Args:
            sources: 数据源配置列表
            
        Returns:
            Dict[str, Any]: 包含爬取结果和状态的字典
        """
        pass
    
    @abstractmethod
    def validate_config(self, config: Dict[str, Any]) -> bool:
        """
        验证数据源配置的有效性
        
        Args:
            config: 数据源配置
            
        Returns:
            bool: 配置是否有效
        """
        pass
    
    @abstractmethod
    def get_source_type(self) -> str:
        """
        获取数据源类型标识
        
        Returns:
            str: 数据源类型（如 "rss", "x", "rest_api"）
        """
        pass
    
    def get_supported_config_fields(self) -> List[str]:
        """
        获取支持的配置字段列表
        
        Returns:
            List[str]: 支持的配置字段名称列表
        """
        return []
    
    def get_required_config_fields(self) -> List[str]:
        """
        获取必需的配置字段列表
        
        Returns:
            List[str]: 必需的配置字段名称列表
        """
        return []
    
    def validate_source_availability(self, config: Dict[str, Any]) -> bool:
        """
        验证数据源是否可访问
        
        Args:
            config: 数据源配置
            
        Returns:
            bool: 数据源是否可访问
        """
        return True
    
    def get_source_info(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        获取数据源信息
        
        Args:
            config: 数据源配置
            
        Returns:
            Dict[str, Any]: 数据源信息
        """
        return {
            "type": self.get_source_type(),
            "name": config.get("name", "Unknown"),
            "description": config.get("description", ""),
            "supported_fields": self.get_supported_config_fields(),
            "required_fields": self.get_required_config_fields()
        }
    
    def cleanup(self) -> None:
        """
        清理资源
        
        在数据源使用完毕后调用，用于清理连接、会话等资源。
        """
        pass


class DataSourceError(Exception):
    """数据源相关错误的基类"""
    
    def __init__(self, message: str, source_type: str = "", source_name: str = ""):
        self.message = message
        self.source_type = source_type
        self.source_name = source_name
        super().__init__(self.message)
    
    def __str__(self):
        if self.source_name:
            return f"[{self.source_type}:{self.source_name}] {self.message}"
        elif self.source_type:
            return f"[{self.source_type}] {self.message}"
        else:
            return self.message


class ConfigValidationError(DataSourceError):
    """配置验证错误"""
    pass


class SourceUnavailableError(DataSourceError):
    """数据源不可用错误"""
    pass


class CrawlError(DataSourceError):
    """爬取错误"""
    pass