"""
数据源工厂和插件系统测试

测试数据源工厂的基本功能和插件化架构。
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime
from typing import Dict, List, Any

from crypto_news_analyzer.crawlers import (
    DataSourceFactory,
    DataSourceInterface,
    DataSourceError,
    ConfigValidationError,
    get_data_source_factory,
    RESTAPICrawler,
    RSSCrawlerAdapter,
    XCrawlerAdapter
)
from crypto_news_analyzer.models import ContentItem, create_content_item_from_raw


class MockDataSource(DataSourceInterface):
    """用于测试的模拟数据源"""
    
    def __init__(self, time_window_hours: int, **kwargs):
        self.time_window_hours = time_window_hours
        self.test_param = kwargs.get('test_param', 'default')
    
    def get_source_type(self) -> str:
        return "mock"
    
    def get_supported_config_fields(self) -> List[str]:
        return ["name", "url", "test_param"]
    
    def get_required_config_fields(self) -> List[str]:
        return ["name", "url"]
    
    def validate_config(self, config: Dict[str, Any]) -> bool:
        required = self.get_required_config_fields()
        missing = [f for f in required if f not in config]
        if missing:
            raise ConfigValidationError(f"缺少字段: {missing}", "mock", config.get("name", ""))
        return True
    
    def crawl(self, config: Dict[str, Any]) -> List[ContentItem]:
        return [
            create_content_item_from_raw(
                title="Mock Title",
                content="Mock Content",
                url="https://mock.example.com/1",
                publish_time=datetime.now(),
                source_name=config.get("name", "Mock"),
                source_type="mock"
            )
        ]
    
    def crawl_all_sources(self, sources: List[Dict[str, Any]]) -> Dict[str, Any]:
        all_items = []
        results = []
        
        for source in sources:
            items = self.crawl(source)
            all_items.extend(items)
            results.append({
                "source_name": source.get("name", "Mock"),
                "status": "success",
                "item_count": len(items),
                "error_message": None
            })
        
        return {
            'items': all_items,
            'results': results,
            'total_items': len(all_items)
        }
    
    def cleanup(self) -> None:
        pass


class TestDataSourceFactory:
    """数据源工厂测试"""
    
    def test_factory_initialization(self):
        """测试工厂初始化"""
        factory = DataSourceFactory()
        assert factory is not None
        assert isinstance(factory.registered_sources, dict)
        assert len(factory.registered_sources) == 0
    
    def test_register_source(self):
        """测试注册数据源"""
        factory = DataSourceFactory()
        
        # 注册模拟数据源
        factory.register_source("mock", MockDataSource)
        
        assert "mock" in factory.registered_sources
        assert factory.registered_sources["mock"] == MockDataSource
        assert factory.is_source_type_registered("mock")
    
    def test_register_source_invalid_class(self):
        """测试注册无效的数据源类"""
        factory = DataSourceFactory()
        
        class InvalidSource:
            pass
        
        with pytest.raises(ValueError, match="必须实现 DataSourceInterface 接口"):
            factory.register_source("invalid", InvalidSource)
    
    def test_register_source_empty_type(self):
        """测试注册空类型名称"""
        factory = DataSourceFactory()
        
        with pytest.raises(ValueError, match="数据源类型不能为空"):
            factory.register_source("", MockDataSource)
    
    def test_unregister_source(self):
        """测试注销数据源"""
        factory = DataSourceFactory()
        factory.register_source("mock", MockDataSource)
        
        # 注销存在的数据源
        result = factory.unregister_source("mock")
        assert result is True
        assert not factory.is_source_type_registered("mock")
        
        # 注销不存在的数据源
        result = factory.unregister_source("nonexistent")
        assert result is False
    
    def test_create_source(self):
        """测试创建数据源实例"""
        factory = DataSourceFactory()
        factory.register_source("mock", MockDataSource)
        
        # 创建数据源实例
        source = factory.create_source("mock", time_window_hours=24, test_param="custom")
        
        assert isinstance(source, MockDataSource)
        assert source.time_window_hours == 24
        assert source.test_param == "custom"
    
    def test_create_source_unregistered_type(self):
        """测试创建未注册的数据源类型"""
        factory = DataSourceFactory()
        
        with pytest.raises(ValueError, match="未注册的数据源类型"):
            factory.create_source("nonexistent", time_window_hours=24)
    
    def test_get_available_source_types(self):
        """测试获取可用数据源类型"""
        factory = DataSourceFactory()
        
        # 空工厂
        assert factory.get_available_source_types() == []
        
        # 注册数据源后
        factory.register_source("mock1", MockDataSource)
        factory.register_source("mock2", MockDataSource)
        
        types = factory.get_available_source_types()
        assert "mock1" in types
        assert "mock2" in types
        assert len(types) == 2
    
    def test_validate_source_config(self):
        """测试配置验证"""
        factory = DataSourceFactory()
        factory.register_source("mock", MockDataSource)
        
        # 有效配置
        valid_config = {"name": "Test", "url": "https://example.com"}
        assert factory.validate_source_config("mock", valid_config) is True
        
        # 无效配置
        invalid_config = {"name": "Test"}  # 缺少url
        assert factory.validate_source_config("mock", invalid_config) is False
    
    def test_validate_source_config_unregistered_type(self):
        """测试验证未注册类型的配置"""
        factory = DataSourceFactory()
        
        with pytest.raises(ValueError, match="未注册的数据源类型"):
            factory.validate_source_config("nonexistent", {})
    
    def test_get_source_info(self):
        """测试获取数据源信息"""
        factory = DataSourceFactory()
        factory.register_source("mock", MockDataSource)
        
        info = factory.get_source_info("mock")
        
        assert info["type"] == "mock"
        assert info["class_name"] == "MockDataSource"
        assert "supported_fields" in info
        assert "required_fields" in info
    
    def test_get_all_sources_info(self):
        """测试获取所有数据源信息"""
        factory = DataSourceFactory()
        factory.register_source("mock1", MockDataSource)
        factory.register_source("mock2", MockDataSource)
        
        all_info = factory.get_all_sources_info()
        
        assert "mock1" in all_info
        assert "mock2" in all_info
        assert len(all_info) == 2
    
    def test_validate_all_configs(self):
        """测试批量配置验证"""
        factory = DataSourceFactory()
        factory.register_source("mock", MockDataSource)
        
        configs = {
            "mock": [
                {"name": "Valid", "url": "https://example.com"},
                {"name": "Invalid"}  # 缺少url
            ]
        }
        
        errors = factory.validate_all_configs(configs)
        
        assert "mock" in errors
        assert len(errors["mock"]) == 1
        assert "配置 2" in errors["mock"][0]
    
    def test_create_all_sources(self):
        """测试批量创建数据源"""
        factory = DataSourceFactory()
        factory.register_source("mock", MockDataSource)
        
        configs = {
            "mock": [
                {"name": "Source1", "url": "https://example1.com"},
                {"name": "Source2", "url": "https://example2.com"}
            ]
        }
        
        sources = factory.create_all_sources(configs, time_window_hours=24)
        
        assert "mock" in sources
        assert len(sources["mock"]) == 2
        assert all(isinstance(s, MockDataSource) for s in sources["mock"])
        
        # 清理
        factory.cleanup_all_sources(sources)
    
    def test_cleanup_all_sources(self):
        """测试批量清理数据源"""
        factory = DataSourceFactory()
        factory.register_source("mock", MockDataSource)
        
        # 创建一些数据源
        source1 = factory.create_source("mock", time_window_hours=24)
        source2 = factory.create_source("mock", time_window_hours=24)
        
        sources = {"mock": [source1, source2]}
        
        # 清理应该不抛出异常
        factory.cleanup_all_sources(sources)
    
    def test_get_factory_stats(self):
        """测试获取工厂统计信息"""
        factory = DataSourceFactory()
        factory.register_source("mock1", MockDataSource)
        factory.register_source("mock2", MockDataSource)
        
        stats = factory.get_factory_stats()
        
        assert stats["registered_types_count"] == 2
        assert "mock1" in stats["registered_types"]
        assert "mock2" in stats["registered_types"]
        assert "factory_created_at" in stats


class TestGlobalFactory:
    """全局工厂测试"""
    
    def test_get_global_factory(self):
        """测试获取全局工厂实例"""
        factory1 = get_data_source_factory()
        factory2 = get_data_source_factory()
        
        # 应该返回同一个实例
        assert factory1 is factory2
    
    def test_builtin_sources_registered(self):
        """测试内置数据源已注册"""
        factory = get_data_source_factory()
        
        # 检查内置数据源类型
        available_types = factory.get_available_source_types()
        
        assert "rss" in available_types
        assert "x" in available_types
        assert "rest_api" in available_types
    
    def test_builtin_source_creation(self):
        """测试创建内置数据源"""
        factory = get_data_source_factory()
        
        # 测试创建RSS数据源
        rss_source = factory.create_source("rss", time_window_hours=24)
        assert isinstance(rss_source, RSSCrawlerAdapter)
        rss_source.cleanup()
        
        # 测试创建X数据源
        x_source = factory.create_source("x", time_window_hours=24)
        assert isinstance(x_source, XCrawlerAdapter)
        x_source.cleanup()
        
        # 测试创建REST API数据源
        api_source = factory.create_source("rest_api", time_window_hours=24)
        assert isinstance(api_source, RESTAPICrawler)
        api_source.cleanup()


class TestDataSourceInterface:
    """数据源接口测试"""
    
    def test_mock_source_implementation(self):
        """测试模拟数据源实现"""
        source = MockDataSource(time_window_hours=24)
        
        assert source.get_source_type() == "mock"
        assert "name" in source.get_supported_config_fields()
        assert "name" in source.get_required_config_fields()
    
    def test_mock_source_config_validation(self):
        """测试模拟数据源配置验证"""
        source = MockDataSource(time_window_hours=24)
        
        # 有效配置
        valid_config = {"name": "Test", "url": "https://example.com"}
        assert source.validate_config(valid_config) is True
        
        # 无效配置
        invalid_config = {"name": "Test"}
        with pytest.raises(ConfigValidationError):
            source.validate_config(invalid_config)
    
    def test_mock_source_crawling(self):
        """测试模拟数据源爬取"""
        source = MockDataSource(time_window_hours=24)
        
        config = {"name": "Test Source", "url": "https://example.com"}
        items = source.crawl(config)
        
        assert len(items) == 1
        assert items[0].title == "Mock Title"
        assert items[0].source_type == "mock"
    
    def test_mock_source_batch_crawling(self):
        """测试模拟数据源批量爬取"""
        source = MockDataSource(time_window_hours=24)
        
        configs = [
            {"name": "Source1", "url": "https://example1.com"},
            {"name": "Source2", "url": "https://example2.com"}
        ]
        
        result = source.crawl_all_sources(configs)
        
        assert result["total_items"] == 2
        assert len(result["results"]) == 2
        assert all(r["status"] == "success" for r in result["results"])


if __name__ == "__main__":
    pytest.main([__file__])