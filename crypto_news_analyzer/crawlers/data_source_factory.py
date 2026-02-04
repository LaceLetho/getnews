"""
数据源工厂

支持插件化的数据源管理，便于扩展新的数据源类型。
"""

from typing import Dict, Type, List, Any, Optional
import logging
from datetime import datetime

from .data_source_interface import DataSourceInterface, DataSourceError, ConfigValidationError
from ..utils.logging import get_logger


class DataSourceFactory:
    """
    数据源工厂类
    
    负责管理和创建各种类型的数据源实例，支持动态注册新的数据源类型。
    """
    
    def __init__(self):
        """初始化数据源工厂"""
        self.registered_sources: Dict[str, Type[DataSourceInterface]] = {}
        self.logger = get_logger(__name__)
        self.logger.info("数据源工厂初始化完成")
    
    def register_source(self, source_type: str, source_class: Type[DataSourceInterface]) -> None:
        """
        注册新的数据源类型
        
        Args:
            source_type: 数据源类型标识（如 "rss", "x", "rest_api"）
            source_class: 数据源实现类
            
        Raises:
            ValueError: 如果数据源类型已存在或类不符合接口要求
        """
        if not source_type or not source_type.strip():
            raise ValueError("数据源类型不能为空")
        
        source_type = source_type.strip().lower()
        
        if source_type in self.registered_sources:
            self.logger.warning(f"数据源类型 '{source_type}' 已存在，将被覆盖")
        
        # 验证类是否实现了DataSourceInterface
        if not issubclass(source_class, DataSourceInterface):
            raise ValueError(f"数据源类 {source_class.__name__} 必须实现 DataSourceInterface 接口")
        
        self.registered_sources[source_type] = source_class
        self.logger.info(f"注册数据源类型: {source_type} -> {source_class.__name__}")
    
    def unregister_source(self, source_type: str) -> bool:
        """
        注销数据源类型
        
        Args:
            source_type: 数据源类型标识
            
        Returns:
            bool: 是否成功注销
        """
        source_type = source_type.strip().lower()
        
        if source_type in self.registered_sources:
            del self.registered_sources[source_type]
            self.logger.info(f"注销数据源类型: {source_type}")
            return True
        else:
            self.logger.warning(f"尝试注销不存在的数据源类型: {source_type}")
            return False
    
    def create_source(
        self, 
        source_type: str, 
        time_window_hours: int,
        **kwargs
    ) -> DataSourceInterface:
        """
        创建数据源实例
        
        Args:
            source_type: 数据源类型标识
            time_window_hours: 时间窗口（小时）
            **kwargs: 其他初始化参数
            
        Returns:
            DataSourceInterface: 数据源实例
            
        Raises:
            ValueError: 如果数据源类型未注册
            DataSourceError: 如果创建实例失败
        """
        source_type = source_type.strip().lower()
        
        if source_type not in self.registered_sources:
            available_types = list(self.registered_sources.keys())
            raise ValueError(
                f"未注册的数据源类型: {source_type}. "
                f"可用类型: {available_types}"
            )
        
        source_class = self.registered_sources[source_type]
        
        try:
            self.logger.debug(f"创建数据源实例: {source_type}")
            instance = source_class(time_window_hours=time_window_hours, **kwargs)
            
            # 验证实例确实实现了接口
            if not isinstance(instance, DataSourceInterface):
                raise DataSourceError(
                    f"数据源实例 {source_class.__name__} 未正确实现 DataSourceInterface 接口",
                    source_type=source_type
                )
            
            self.logger.info(f"成功创建数据源实例: {source_type}")
            return instance
            
        except Exception as e:
            error_msg = f"创建数据源实例失败 ({source_type}): {str(e)}"
            self.logger.error(error_msg)
            raise DataSourceError(error_msg, source_type=source_type) from e
    
    def get_available_source_types(self) -> List[str]:
        """
        获取所有可用的数据源类型
        
        Returns:
            List[str]: 数据源类型列表
        """
        return list(self.registered_sources.keys())
    
    def is_source_type_registered(self, source_type: str) -> bool:
        """
        检查数据源类型是否已注册
        
        Args:
            source_type: 数据源类型标识
            
        Returns:
            bool: 是否已注册
        """
        return source_type.strip().lower() in self.registered_sources
    
    def validate_source_config(self, source_type: str, config: Dict[str, Any]) -> bool:
        """
        验证数据源配置的有效性
        
        Args:
            source_type: 数据源类型标识
            config: 数据源配置
            
        Returns:
            bool: 配置是否有效
            
        Raises:
            ValueError: 如果数据源类型未注册
        """
        source_type = source_type.strip().lower()
        
        if source_type not in self.registered_sources:
            raise ValueError(f"未注册的数据源类型: {source_type}")
        
        try:
            # 创建临时实例来验证配置
            temp_instance = self.create_source(source_type, time_window_hours=24)
            result = temp_instance.validate_config(config)
            temp_instance.cleanup()
            return result
            
        except Exception as e:
            self.logger.error(f"验证配置失败 ({source_type}): {str(e)}")
            return False
    
    def get_source_info(self, source_type: str) -> Dict[str, Any]:
        """
        获取数据源类型信息
        
        Args:
            source_type: 数据源类型标识
            
        Returns:
            Dict[str, Any]: 数据源信息
            
        Raises:
            ValueError: 如果数据源类型未注册
        """
        source_type = source_type.strip().lower()
        
        if source_type not in self.registered_sources:
            raise ValueError(f"未注册的数据源类型: {source_type}")
        
        source_class = self.registered_sources[source_type]
        
        try:
            # 创建临时实例来获取信息
            temp_instance = self.create_source(source_type, time_window_hours=24)
            info = temp_instance.get_source_info({})
            temp_instance.cleanup()
            
            # 添加类信息
            info.update({
                "class_name": source_class.__name__,
                "module": source_class.__module__,
                "registered_at": datetime.now().isoformat()
            })
            
            return info
            
        except Exception as e:
            self.logger.error(f"获取数据源信息失败 ({source_type}): {str(e)}")
            return {
                "type": source_type,
                "class_name": source_class.__name__,
                "module": source_class.__module__,
                "error": str(e)
            }
    
    def get_all_sources_info(self) -> Dict[str, Dict[str, Any]]:
        """
        获取所有注册数据源的信息
        
        Returns:
            Dict[str, Dict[str, Any]]: 所有数据源信息
        """
        all_info = {}
        
        for source_type in self.registered_sources:
            try:
                all_info[source_type] = self.get_source_info(source_type)
            except Exception as e:
                self.logger.error(f"获取数据源信息失败 ({source_type}): {str(e)}")
                all_info[source_type] = {
                    "type": source_type,
                    "error": str(e)
                }
        
        return all_info
    
    def validate_all_configs(self, configs: Dict[str, List[Dict[str, Any]]]) -> Dict[str, List[str]]:
        """
        批量验证多个数据源配置
        
        Args:
            configs: 按数据源类型分组的配置字典
            
        Returns:
            Dict[str, List[str]]: 验证错误信息，按数据源类型分组
        """
        validation_errors = {}
        
        for source_type, source_configs in configs.items():
            errors = []
            
            if not self.is_source_type_registered(source_type):
                errors.append(f"未注册的数据源类型: {source_type}")
                validation_errors[source_type] = errors
                continue
            
            for i, config in enumerate(source_configs):
                try:
                    if not self.validate_source_config(source_type, config):
                        errors.append(f"配置 {i+1}: 验证失败")
                except Exception as e:
                    errors.append(f"配置 {i+1}: {str(e)}")
            
            if errors:
                validation_errors[source_type] = errors
        
        return validation_errors
    
    def create_all_sources(
        self, 
        configs: Dict[str, List[Dict[str, Any]]], 
        time_window_hours: int
    ) -> Dict[str, List[DataSourceInterface]]:
        """
        批量创建多个数据源实例
        
        Args:
            configs: 按数据源类型分组的配置字典
            time_window_hours: 时间窗口（小时）
            
        Returns:
            Dict[str, List[DataSourceInterface]]: 创建的数据源实例，按类型分组
            
        Raises:
            DataSourceError: 如果创建过程中出现错误
        """
        created_sources = {}
        
        for source_type, source_configs in configs.items():
            sources = []
            
            for config in source_configs:
                try:
                    source = self.create_source(source_type, time_window_hours)
                    sources.append(source)
                except Exception as e:
                    # 清理已创建的实例
                    for source in sources:
                        try:
                            source.cleanup()
                        except Exception:
                            pass
                    
                    raise DataSourceError(
                        f"创建数据源实例失败 ({source_type}): {str(e)}",
                        source_type=source_type
                    ) from e
            
            created_sources[source_type] = sources
        
        return created_sources
    
    def cleanup_all_sources(self, sources: Dict[str, List[DataSourceInterface]]) -> None:
        """
        清理所有数据源实例
        
        Args:
            sources: 数据源实例字典
        """
        for source_type, source_list in sources.items():
            for source in source_list:
                try:
                    source.cleanup()
                    self.logger.debug(f"清理数据源实例: {source_type}")
                except Exception as e:
                    self.logger.error(f"清理数据源实例失败 ({source_type}): {str(e)}")
    
    def get_factory_stats(self) -> Dict[str, Any]:
        """
        获取工厂统计信息
        
        Returns:
            Dict[str, Any]: 统计信息
        """
        return {
            "registered_types_count": len(self.registered_sources),
            "registered_types": list(self.registered_sources.keys()),
            "factory_created_at": datetime.now().isoformat()
        }


# 全局数据源工厂实例
_global_factory: Optional[DataSourceFactory] = None


def get_data_source_factory() -> DataSourceFactory:
    """
    获取全局数据源工厂实例
    
    Returns:
        DataSourceFactory: 全局工厂实例
    """
    global _global_factory
    
    if _global_factory is None:
        _global_factory = DataSourceFactory()
    
    return _global_factory


def register_builtin_sources() -> None:
    """
    注册内置数据源类型
    
    这个函数会在模块导入时自动调用，注册系统内置的数据源类型。
    """
    factory = get_data_source_factory()
    
    try:
        # 注册RSS数据源
        from .rss_crawler_adapter import RSSCrawlerAdapter
        factory.register_source("rss", RSSCrawlerAdapter)
        
        # 注册X数据源
        from .x_crawler_adapter import XCrawlerAdapter
        factory.register_source("x", XCrawlerAdapter)
        
        # 注册REST API数据源
        from .rest_api_crawler import RESTAPICrawler
        factory.register_source("rest_api", RESTAPICrawler)
        
    except ImportError as e:
        # 如果某些适配器还未实现，记录警告但不中断
        logger = get_logger(__name__)
        logger.warning(f"注册内置数据源时出现导入错误: {str(e)}")