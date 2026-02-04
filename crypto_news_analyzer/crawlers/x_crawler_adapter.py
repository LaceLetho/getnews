"""
X/Twitter爬取器适配器

将现有的XCrawler适配为DataSourceInterface接口，
保持向后兼容性的同时支持新的插件化架构。
"""

from typing import Dict, List, Any
from datetime import datetime

from .data_source_interface import DataSourceInterface, CrawlError, ConfigValidationError
from .x_crawler import XCrawler
from ..models import ContentItem, XSource
from ..utils.logging import get_logger


class XCrawlerAdapter(DataSourceInterface):
    """
    X/Twitter爬取器适配器
    
    将现有的XCrawler包装为符合DataSourceInterface的实现，
    提供统一的接口同时保持原有功能。
    """
    
    def __init__(self, time_window_hours: int, ct0: str = "", auth_token: str = ""):
        """
        初始化X爬取器适配器
        
        Args:
            time_window_hours: 时间窗口（小时）
            ct0: X认证参数ct0
            auth_token: X认证令牌
        """
        self.time_window_hours = time_window_hours
        self.ct0 = ct0
        self.auth_token = auth_token
        self.logger = get_logger(__name__)
        
        # 创建底层X爬取器实例（如果有认证信息）
        self.x_crawler = None
        if ct0 and auth_token:
            try:
                self.x_crawler = XCrawler(ct0=ct0, auth_token=auth_token, time_window_hours=time_window_hours)
            except Exception as e:
                self.logger.warning(f"X爬取器初始化失败: {str(e)}")
        
        self.logger.info(f"X爬取器适配器初始化完成，时间窗口: {time_window_hours}小时")
    
    def get_source_type(self) -> str:
        """获取数据源类型标识"""
        return "x"
    
    def get_supported_config_fields(self) -> List[str]:
        """获取支持的配置字段列表"""
        return ["name", "url", "type", "ct0", "auth_token", "description"]
    
    def get_required_config_fields(self) -> List[str]:
        """获取必需的配置字段列表"""
        return ["name", "url", "type"]
    
    def validate_config(self, config: Dict[str, Any]) -> bool:
        """
        验证X配置的有效性
        
        Args:
            config: X配置字典
            
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
            
            # 创建XSource对象进行验证
            x_source = self._config_to_x_source(config)
            x_source.validate()  # 这会抛出ValueError如果配置无效
            
            # 检查认证信息（如果需要）
            if not self._has_auth_info(config):
                self.logger.warning("X配置缺少认证信息，可能无法正常爬取")
            
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
        验证X源是否可访问
        
        Args:
            config: X配置字典
            
        Returns:
            bool: X源是否可访问
        """
        try:
            # 如果没有爬取器实例，尝试创建
            if not self.x_crawler:
                ct0 = config.get("ct0", self.ct0)
                auth_token = config.get("auth_token", self.auth_token)
                
                if not ct0 or not auth_token:
                    self.logger.warning("缺少X认证信息，无法验证可访问性")
                    return False
                
                temp_crawler = XCrawler(ct0=ct0, auth_token=auth_token, time_window_hours=self.time_window_hours)
                result = temp_crawler.authenticate()
                temp_crawler.cleanup()
                return result
            else:
                return self.x_crawler.authenticate()
                
        except Exception as e:
            self.logger.warning(f"X源可访问性检查失败: {str(e)}")
            return False
    
    def crawl(self, config: Dict[str, Any]) -> List[ContentItem]:
        """
        爬取单个X源
        
        Args:
            config: X配置字典
            
        Returns:
            List[ContentItem]: 爬取到的内容项列表
            
        Raises:
            CrawlError: 爬取失败时抛出
        """
        # 验证配置
        self.validate_config(config)
        
        source_name = config.get("name", "Unknown X Source")
        
        try:
            # 确保有爬取器实例
            crawler = self._get_or_create_crawler(config)
            
            # 转换配置为XSource对象
            x_source = self._config_to_x_source(config)
            
            # 根据类型进行爬取
            if x_source.type == "list":
                items = crawler.crawl_list(x_source.url)
            elif x_source.type == "timeline":
                items = crawler.crawl_timeline()
            else:
                raise CrawlError(
                    f"不支持的X源类型: {x_source.type}",
                    source_type=self.get_source_type(),
                    source_name=source_name
                )
            
            return items
            
        except Exception as e:
            error_msg = f"爬取X源失败 {source_name}: {str(e)}"
            self.logger.error(error_msg)
            raise CrawlError(error_msg, source_type=self.get_source_type(), source_name=source_name) from e
    
    def crawl_all_sources(self, sources: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        爬取所有X源
        
        Args:
            sources: X配置字典列表
            
        Returns:
            Dict[str, Any]: 包含爬取结果和状态的字典
        """
        try:
            # 如果没有源或没有认证信息，返回空结果
            if not sources:
                return {
                    'items': [],
                    'results': [],
                    'total_items': 0
                }
            
            # 检查是否有认证信息
            has_auth = any(self._has_auth_info(config) for config in sources)
            if not has_auth and not self.x_crawler:
                self.logger.warning("没有X认证信息，跳过X源爬取")
                return {
                    'items': [],
                    'results': [],
                    'total_items': 0
                }
            
            # 转换配置为XSource对象列表
            x_sources = []
            for config in sources:
                self.validate_config(config)
                x_sources.append(self._config_to_x_source(config))
            
            # 确保有爬取器实例
            crawler = self._get_or_create_crawler(sources[0])  # 使用第一个配置的认证信息
            
            # 使用底层爬取器进行批量爬取
            crawl_results = crawler.crawl_all_sources(x_sources)
            
            # 收集所有内容项
            all_items = []
            for result in crawl_results:
                if result.status == "success":
                    # 注意：原始XCrawler的crawl_all_sources返回CrawlResult列表，不包含items
                    # 需要单独爬取每个源来获取items
                    pass
            
            # 重新组织返回格式以匹配接口
            return {
                'items': all_items,
                'results': crawl_results,
                'total_items': len(all_items)
            }
            
        except Exception as e:
            error_msg = f"批量爬取X源失败: {str(e)}"
            self.logger.error(error_msg)
            raise CrawlError(error_msg, source_type=self.get_source_type()) from e
    
    def get_source_info(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        获取X源信息
        
        Args:
            config: X配置字典
            
        Returns:
            Dict[str, Any]: X源信息
        """
        base_info = super().get_source_info(config)
        
        # 添加X特定信息
        base_info.update({
            "supported_types": ["list", "timeline"],
            "auth_required": True,
            "rate_limited": True,
            "features": [
                "列表和时间线爬取",
                "反封控策略",
                "速率限制管理",
                "会话管理",
                "随机延迟",
                "User-Agent轮换",
                "时间窗口过滤"
            ],
            "rate_limit_info": {
                "min_delay": 2.0,
                "max_delay": 8.0,
                "rate_limit_delay": 900
            }
        })
        
        # 添加认证状态信息
        if self.x_crawler:
            base_info["auth_status"] = "configured"
            base_info["authenticated"] = self.x_crawler.authenticated
        else:
            base_info["auth_status"] = "not_configured"
            base_info["authenticated"] = False
        
        return base_info
    
    def _config_to_x_source(self, config: Dict[str, Any]) -> XSource:
        """
        将配置字典转换为XSource对象
        
        Args:
            config: X配置字典
            
        Returns:
            XSource: X源对象
        """
        return XSource(
            name=config["name"],
            url=config["url"],
            type=config["type"]
        )
    
    def _has_auth_info(self, config: Dict[str, Any]) -> bool:
        """
        检查配置是否包含认证信息
        
        Args:
            config: X配置字典
            
        Returns:
            bool: 是否包含认证信息
        """
        ct0 = config.get("ct0", self.ct0)
        auth_token = config.get("auth_token", self.auth_token)
        return bool(ct0 and auth_token)
    
    def _get_or_create_crawler(self, config: Dict[str, Any]) -> XCrawler:
        """
        获取或创建X爬取器实例
        
        Args:
            config: X配置字典
            
        Returns:
            XCrawler: X爬取器实例
            
        Raises:
            CrawlError: 如果无法创建爬取器
        """
        if self.x_crawler:
            return self.x_crawler
        
        # 尝试从配置获取认证信息
        ct0 = config.get("ct0", self.ct0)
        auth_token = config.get("auth_token", self.auth_token)
        
        if not ct0 or not auth_token:
            raise CrawlError(
                "缺少X认证信息 (ct0 和 auth_token)",
                source_type=self.get_source_type(),
                source_name=config.get("name", "Unknown")
            )
        
        try:
            crawler = XCrawler(ct0=ct0, auth_token=auth_token, time_window_hours=self.time_window_hours)
            return crawler
        except Exception as e:
            raise CrawlError(
                f"创建X爬取器失败: {str(e)}",
                source_type=self.get_source_type(),
                source_name=config.get("name", "Unknown")
            ) from e
    
    def cleanup(self) -> None:
        """清理资源"""
        if self.x_crawler:
            self.x_crawler.cleanup()
        
        self.logger.debug("X爬取器适配器资源清理完成")