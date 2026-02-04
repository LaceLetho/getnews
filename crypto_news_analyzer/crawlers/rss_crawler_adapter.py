"""
RSS爬取器适配器

将现有的RSSCrawler适配为DataSourceInterface接口，
保持向后兼容性的同时支持新的插件化架构。
"""

from typing import Dict, List, Any
from datetime import datetime

from .data_source_interface import DataSourceInterface, CrawlError, ConfigValidationError
from .rss_crawler import RSSCrawler
from ..models import ContentItem, RSSSource
from ..utils.logging import get_logger


class RSSCrawlerAdapter(DataSourceInterface):
    """
    RSS爬取器适配器
    
    将现有的RSSCrawler包装为符合DataSourceInterface的实现，
    提供统一的接口同时保持原有功能。
    """
    
    def __init__(self, time_window_hours: int, timeout: int = 30):
        """
        初始化RSS爬取器适配器
        
        Args:
            time_window_hours: 时间窗口（小时）
            timeout: 请求超时时间（秒）
        """
        self.time_window_hours = time_window_hours
        self.timeout = timeout
        self.logger = get_logger(__name__)
        
        # 创建底层RSS爬取器实例
        self.rss_crawler = RSSCrawler(time_window_hours=time_window_hours, timeout=timeout)
        
        self.logger.info(f"RSS爬取器适配器初始化完成，时间窗口: {time_window_hours}小时")
    
    def get_source_type(self) -> str:
        """获取数据源类型标识"""
        return "rss"
    
    def get_supported_config_fields(self) -> List[str]:
        """获取支持的配置字段列表"""
        return ["name", "url", "description", "timeout", "user_agent", "headers"]
    
    def get_required_config_fields(self) -> List[str]:
        """获取必需的配置字段列表"""
        return ["name", "url"]
    
    def validate_config(self, config: Dict[str, Any]) -> bool:
        """
        验证RSS配置的有效性
        
        Args:
            config: RSS配置字典
            
        Returns:
            bool: 配置是否有效
            
        Raises:
            ConfigValidationError: 配置验证失败
        """
        try:
            # 检查必需字段
            required_fields = self.get_required_config_fields()
            missing_fields = [field for field in required_fields if field not in config]
            if missing_fields:
                raise ConfigValidationError(
                    f"缺少必需的配置字段: {missing_fields}",
                    source_type=self.get_source_type(),
                    source_name=config.get("name", "Unknown")
                )
            
            # 创建RSSSource对象进行验证
            rss_source = self._config_to_rss_source(config)
            rss_source.validate()  # 这会抛出ValueError如果配置无效
            
            return True
            
        except ValueError as e:
            raise ConfigValidationError(
                str(e),
                source_type=self.get_source_type(),
                source_name=config.get("name", "Unknown")
            ) from e
        except Exception as e:
            raise ConfigValidationError(
                f"配置验证时出现未知错误: {str(e)}",
                source_type=self.get_source_type(),
                source_name=config.get("name", "Unknown")
            ) from e
    
    def validate_source_availability(self, config: Dict[str, Any]) -> bool:
        """
        验证RSS源是否可访问
        
        Args:
            config: RSS配置字典
            
        Returns:
            bool: RSS源是否可访问
        """
        try:
            rss_source = self._config_to_rss_source(config)
            return self.rss_crawler.validate_rss_source(rss_source)
        except Exception as e:
            self.logger.warning(f"RSS源可访问性检查失败: {str(e)}")
            return False
    
    def crawl(self, config: Dict[str, Any]) -> List[ContentItem]:
        """
        爬取单个RSS源
        
        Args:
            config: RSS配置字典
            
        Returns:
            List[ContentItem]: 爬取到的内容项列表
            
        Raises:
            CrawlError: 爬取失败时抛出
        """
        # 验证配置
        self.validate_config(config)
        
        try:
            # 转换配置为RSSSource对象
            rss_source = self._config_to_rss_source(config)
            
            # 使用底层爬取器进行爬取
            items = self.rss_crawler.crawl_source(rss_source)
            
            return items
            
        except Exception as e:
            source_name = config.get("name", "Unknown RSS")
            error_msg = f"爬取RSS源失败 {source_name}: {str(e)}"
            self.logger.error(error_msg)
            raise CrawlError(error_msg, source_type=self.get_source_type(), source_name=source_name) from e
    
    def crawl_all_sources(self, sources: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        爬取所有RSS源
        
        Args:
            sources: RSS配置字典列表
            
        Returns:
            Dict[str, Any]: 包含爬取结果和状态的字典
        """
        try:
            # 转换配置为RSSSource对象列表
            rss_sources = []
            for config in sources:
                self.validate_config(config)
                rss_sources.append(self._config_to_rss_source(config))
            
            # 使用底层爬取器进行批量爬取
            result = self.rss_crawler.crawl_all_sources(rss_sources)
            
            return result
            
        except Exception as e:
            error_msg = f"批量爬取RSS源失败: {str(e)}"
            self.logger.error(error_msg)
            raise CrawlError(error_msg, source_type=self.get_source_type()) from e
    
    def get_source_info(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        获取RSS源信息
        
        Args:
            config: RSS配置字典
            
        Returns:
            Dict[str, Any]: RSS源信息
        """
        base_info = super().get_source_info(config)
        
        # 添加RSS特定信息
        base_info.update({
            "supported_formats": ["RSS 2.0", "Atom"],
            "timeout": self.timeout,
            "features": [
                "多种RSS格式支持",
                "HTML内容清理",
                "时间窗口过滤",
                "错误重试机制",
                "内容去重",
                "自动编码检测"
            ]
        })
        
        # 如果配置有效，尝试获取RSS源详细信息
        try:
            if config and self.validate_config(config):
                rss_source = self._config_to_rss_source(config)
                feed_info = self.rss_crawler.get_feed_info(rss_source)
                base_info["feed_info"] = feed_info
        except Exception as e:
            self.logger.debug(f"获取RSS源详细信息失败: {str(e)}")
        
        return base_info
    
    def _config_to_rss_source(self, config: Dict[str, Any]) -> RSSSource:
        """
        将配置字典转换为RSSSource对象
        
        Args:
            config: RSS配置字典
            
        Returns:
            RSSSource: RSS源对象
        """
        return RSSSource(
            name=config["name"],
            url=config["url"],
            description=config.get("description", "")
        )
    
    def cleanup(self) -> None:
        """清理资源"""
        # RSS爬取器使用requests.Session，需要清理
        if hasattr(self.rss_crawler, 'session'):
            self.rss_crawler.session.close()
        
        self.logger.debug("RSS爬取器适配器资源清理完成")