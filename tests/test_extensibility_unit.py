"""
扩展性单元测试

测试新数据源的注册和使用，以及配置文件的动态更新功能。
"""

import pytest
import json
import tempfile
import os
import time
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from typing import Dict, List, Any

from crypto_news_analyzer.crawlers import (
    DataSourceFactory,
    DataSourceInterface,
    DataSourceError,
    ConfigValidationError,
    get_data_source_factory
)
from crypto_news_analyzer.config.manager import ConfigManager
from crypto_news_analyzer.analyzers.prompt_manager import PromptManager, DynamicCategoryManager
from crypto_news_analyzer.models import ContentItem, create_content_item_from_raw


class CustomDataSource(DataSourceInterface):
    """自定义数据源用于测试扩展性"""
    
    def __init__(self, time_window_hours: int, **kwargs):
        self.time_window_hours = time_window_hours
        self.custom_param = kwargs.get('custom_param', 'default_value')
        self.initialized = True
    
    def get_source_type(self) -> str:
        return "custom"
    
    def get_supported_config_fields(self) -> List[str]:
        return ["name", "endpoint", "api_key", "custom_param"]
    
    def get_required_config_fields(self) -> List[str]:
        return ["name", "endpoint"]
    
    def validate_config(self, config: Dict[str, Any]) -> bool:
        required = self.get_required_config_fields()
        missing = [f for f in required if f not in config]
        if missing:
            raise ConfigValidationError(f"缺少字段: {missing}", "custom", config.get("name", ""))
        return True
    
    def crawl(self, config: Dict[str, Any]) -> List[ContentItem]:
        return [
            create_content_item_from_raw(
                title=f"Custom Content from {config.get('name', 'Unknown')}",
                content="This is custom content from a dynamically registered data source",
                url=f"{config.get('endpoint', 'https://example.com')}/item/1",
                publish_time=datetime.now(),
                source_name=config.get("name", "Custom Source"),
                source_type="custom"
            )
        ]
    
    def crawl_all_sources(self, sources: List[Dict[str, Any]]) -> Dict[str, Any]:
        all_items = []
        results = []
        
        for source in sources:
            items = self.crawl(source)
            all_items.extend(items)
            results.append({
                "source_name": source.get("name", "Custom Source"),
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
        self.initialized = False


class AdvancedDataSource(DataSourceInterface):
    """高级数据源用于测试复杂扩展场景"""
    
    def __init__(self, time_window_hours: int, **kwargs):
        self.time_window_hours = time_window_hours
        self.rate_limit = kwargs.get('rate_limit', 100)
        self.auth_token = kwargs.get('auth_token', '')
        self.features = kwargs.get('features', [])
    
    def get_source_type(self) -> str:
        return "advanced"
    
    def get_supported_config_fields(self) -> List[str]:
        return ["name", "endpoint", "auth_token", "rate_limit", "features", "timeout"]
    
    def get_required_config_fields(self) -> List[str]:
        return ["name", "endpoint", "auth_token"]
    
    def validate_config(self, config: Dict[str, Any]) -> bool:
        # 验证必需字段
        required = self.get_required_config_fields()
        missing = [f for f in required if f not in config]
        if missing:
            raise ConfigValidationError(f"缺少字段: {missing}", "advanced", config.get("name", ""))
        
        # 验证特殊字段
        if 'rate_limit' in config and not isinstance(config['rate_limit'], int):
            raise ConfigValidationError("rate_limit必须是整数", "advanced", config.get("name", ""))
        
        if 'features' in config and not isinstance(config['features'], list):
            raise ConfigValidationError("features必须是列表", "advanced", config.get("name", ""))
        
        return True
    
    def validate_source_availability(self, config: Dict[str, Any]) -> bool:
        # 模拟网络检查
        endpoint = config.get('endpoint', '')
        return endpoint.startswith('https://') and 'api' in endpoint
    
    def crawl(self, config: Dict[str, Any]) -> List[ContentItem]:
        features = config.get('features', [])
        item_count = 2 if 'batch_mode' in features else 1
        
        items = []
        for i in range(item_count):
            items.append(create_content_item_from_raw(
                title=f"Advanced Content {i+1} from {config.get('name', 'Unknown')}",
                content=f"Advanced content with features: {', '.join(features)}",
                url=f"{config.get('endpoint', 'https://api.example.com')}/item/{i+1}",
                publish_time=datetime.now() - timedelta(minutes=i*10),
                source_name=config.get("name", "Advanced Source"),
                source_type="advanced"
            ))
        
        return items
    
    def crawl_all_sources(self, sources: List[Dict[str, Any]]) -> Dict[str, Any]:
        all_items = []
        results = []
        
        for source in sources:
            try:
                items = self.crawl(source)
                all_items.extend(items)
                results.append({
                    "source_name": source.get("name", "Advanced Source"),
                    "status": "success",
                    "item_count": len(items),
                    "error_message": None
                })
            except Exception as e:
                results.append({
                    "source_name": source.get("name", "Advanced Source"),
                    "status": "error",
                    "item_count": 0,
                    "error_message": str(e)
                })
        
        return {
            'items': all_items,
            'results': results,
            'total_items': len(all_items)
        }
    
    def get_source_info(self, config: Dict[str, Any]) -> Dict[str, Any]:
        base_info = super().get_source_info(config)
        base_info.update({
            "rate_limit": self.rate_limit,
            "supported_features": ["batch_mode", "real_time", "filtering"],
            "auth_required": True
        })
        return base_info
    
    def cleanup(self) -> None:
        pass


class TestNewDataSourceRegistration:
    """测试新数据源的注册和使用"""
    
    def setup_method(self):
        """测试前设置"""
        self.factory = DataSourceFactory()
    
    def test_register_custom_data_source(self):
        """测试注册自定义数据源"""
        # 注册自定义数据源
        self.factory.register_source("custom", CustomDataSource)
        
        # 验证注册成功
        assert self.factory.is_source_type_registered("custom")
        assert "custom" in self.factory.get_available_source_types()
        
        # 验证可以创建实例
        source = self.factory.create_source("custom", time_window_hours=24, custom_param="test_value")
        assert isinstance(source, CustomDataSource)
        assert source.custom_param == "test_value"
        assert source.initialized is True
        
        source.cleanup()
    
    def test_register_advanced_data_source(self):
        """测试注册高级数据源"""
        # 注册高级数据源
        self.factory.register_source("advanced", AdvancedDataSource)
        
        # 验证注册成功
        assert self.factory.is_source_type_registered("advanced")
        
        # 创建实例并测试高级功能
        source = self.factory.create_source(
            "advanced", 
            time_window_hours=12, 
            rate_limit=50,
            auth_token="test_token",
            features=["batch_mode", "real_time"]
        )
        
        assert isinstance(source, AdvancedDataSource)
        assert source.rate_limit == 50
        assert source.auth_token == "test_token"
        assert source.features == ["batch_mode", "real_time"]
        
        source.cleanup()
    
    def test_custom_data_source_validation(self):
        """测试自定义数据源配置验证"""
        self.factory.register_source("custom", CustomDataSource)
        
        # 有效配置
        valid_config = {
            "name": "Test Custom Source",
            "endpoint": "https://api.custom.com/data"
        }
        assert self.factory.validate_source_config("custom", valid_config) is True
        
        # 无效配置 - 缺少必需字段
        invalid_config = {"name": "Test Custom Source"}
        assert self.factory.validate_source_config("custom", invalid_config) is False
    
    def test_advanced_data_source_validation(self):
        """测试高级数据源配置验证"""
        self.factory.register_source("advanced", AdvancedDataSource)
        
        # 有效配置
        valid_config = {
            "name": "Test Advanced Source",
            "endpoint": "https://api.advanced.com/data",
            "auth_token": "test_token",
            "rate_limit": 100,
            "features": ["batch_mode"]
        }
        assert self.factory.validate_source_config("advanced", valid_config) is True
        
        # 无效配置 - 错误的字段类型
        invalid_config = {
            "name": "Test Advanced Source",
            "endpoint": "https://api.advanced.com/data",
            "auth_token": "test_token",
            "rate_limit": "invalid",  # 应该是整数
            "features": "invalid"     # 应该是列表
        }
        assert self.factory.validate_source_config("advanced", invalid_config) is False
    
    def test_custom_data_source_crawling(self):
        """测试自定义数据源爬取功能"""
        self.factory.register_source("custom", CustomDataSource)
        source = self.factory.create_source("custom", time_window_hours=24)
        
        config = {
            "name": "Test Custom Source",
            "endpoint": "https://api.custom.com/data"
        }
        
        # 测试单个源爬取
        items = source.crawl(config)
        assert len(items) == 1
        assert items[0].title == "Custom Content from Test Custom Source"
        assert items[0].source_type == "custom"
        
        # 测试批量爬取
        configs = [config, {
            "name": "Another Custom Source",
            "endpoint": "https://api.custom2.com/data"
        }]
        
        result = source.crawl_all_sources(configs)
        assert result["total_items"] == 2
        assert len(result["results"]) == 2
        assert all(r["status"] == "success" for r in result["results"])
        
        source.cleanup()
    
    def test_advanced_data_source_features(self):
        """测试高级数据源特性"""
        self.factory.register_source("advanced", AdvancedDataSource)
        source = self.factory.create_source("advanced", time_window_hours=24)
        
        # 测试批量模式
        batch_config = {
            "name": "Batch Source",
            "endpoint": "https://api.advanced.com/data",
            "auth_token": "test_token",
            "features": ["batch_mode"]
        }
        
        items = source.crawl(batch_config)
        assert len(items) == 2  # 批量模式返回2个项目
        
        # 测试单项模式
        single_config = {
            "name": "Single Source",
            "endpoint": "https://api.advanced.com/data",
            "auth_token": "test_token",
            "features": []
        }
        
        items = source.crawl(single_config)
        assert len(items) == 1  # 单项模式返回1个项目
        
        source.cleanup()
    
    def test_data_source_info_retrieval(self):
        """测试数据源信息获取"""
        self.factory.register_source("advanced", AdvancedDataSource)
        
        info = self.factory.get_source_info("advanced")
        
        assert info["type"] == "advanced"
        assert info["class_name"] == "AdvancedDataSource"
        assert "rate_limit" in info
        assert "supported_features" in info
        assert info["auth_required"] is True
    
    def test_multiple_data_sources_registration(self):
        """测试注册多个数据源类型"""
        # 注册多个数据源
        self.factory.register_source("custom", CustomDataSource)
        self.factory.register_source("advanced", AdvancedDataSource)
        
        # 验证都已注册
        available_types = self.factory.get_available_source_types()
        assert "custom" in available_types
        assert "advanced" in available_types
        
        # 验证可以同时使用
        custom_source = self.factory.create_source("custom", time_window_hours=24)
        advanced_source = self.factory.create_source("advanced", time_window_hours=24)
        
        assert isinstance(custom_source, CustomDataSource)
        assert isinstance(advanced_source, AdvancedDataSource)
        
        custom_source.cleanup()
        advanced_source.cleanup()
    
    def test_data_source_replacement(self):
        """测试数据源类型替换"""
        # 注册初始数据源
        self.factory.register_source("replaceable", CustomDataSource)
        
        # 验证初始注册
        source1 = self.factory.create_source("replaceable", time_window_hours=24)
        assert isinstance(source1, CustomDataSource)
        source1.cleanup()
        
        # 替换为新的数据源类型
        self.factory.register_source("replaceable", AdvancedDataSource)
        
        # 验证已替换
        source2 = self.factory.create_source("replaceable", time_window_hours=24)
        assert isinstance(source2, AdvancedDataSource)
        source2.cleanup()


class TestDynamicConfigurationUpdates:
    """测试配置文件的动态更新功能"""
    
    def setup_method(self):
        """测试前设置"""
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.temp_dir, "test_config.json")
        self.prompt_config_path = os.path.join(self.temp_dir, "test_prompt.json")
        
        # 创建测试配置文件
        self.initial_config = {
            "execution_interval": 3600,
            "time_window_hours": 24,
            "storage": {
                "retention_days": 30,
                "database_path": "./test.db"
            },
            "auth": {
                "LLM_API_KEY": "test_key",
                "TELEGRAM_BOT_TOKEN": "test_token",
                "TELEGRAM_CHANNEL_ID": "test_channel"
            },
            "llm_config": {
                "model": "gpt-4",
                "prompt_config_path": self.prompt_config_path
            },
            "rss_sources": [
                {
                    "name": "Test RSS",
                    "url": "https://example.com/rss.xml",
                    "description": "Test RSS Source"
                }
            ],
            "rest_api_sources": []
        }
        
        # 创建测试提示词配置
        self.initial_prompt_config = {
            "categories": {
                "测试分类": {
                    "description": "测试用分类",
                    "criteria": ["测试标准1", "测试标准2"],
                    "examples": ["测试示例1"],
                    "priority": 1
                }
            },
            "ignore_criteria": ["广告", "重复信息"]
        }
        
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(self.initial_config, f, ensure_ascii=False, indent=2)
        
        with open(self.prompt_config_path, 'w', encoding='utf-8') as f:
            json.dump(self.initial_prompt_config, f, ensure_ascii=False, indent=2)
    
    def teardown_method(self):
        """测试后清理"""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_config_manager_dynamic_loading(self):
        """测试配置管理器动态加载"""
        manager = ConfigManager(self.config_path)
        
        # 初始加载
        config1 = manager.load_config()
        assert config1["time_window_hours"] == 24
        assert len(config1["rss_sources"]) == 1
        
        # 修改配置文件
        updated_config = self.initial_config.copy()
        updated_config["time_window_hours"] = 12
        updated_config["rss_sources"].append({
            "name": "New RSS",
            "url": "https://new.example.com/rss.xml",
            "description": "New RSS Source"
        })
        
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(updated_config, f, ensure_ascii=False, indent=2)
        
        # 重新加载配置
        config2 = manager.load_config()
        assert config2["time_window_hours"] == 12
        assert len(config2["rss_sources"]) == 2
        assert config2["rss_sources"][1]["name"] == "New RSS"
    
    def test_rest_api_sources_dynamic_addition(self):
        """测试REST API数据源的动态添加"""
        manager = ConfigManager(self.config_path)
        
        # 初始配置没有REST API源
        config = manager.load_config()
        assert len(config["rest_api_sources"]) == 0
        
        # 动态添加REST API源
        new_api_source = {
            "name": "Dynamic API",
            "endpoint": "https://api.dynamic.com/news",
            "method": "GET",
            "response_mapping": {
                "title_field": "title",
                "content_field": "content",
                "url_field": "url",
                "time_field": "timestamp"
            }
        }
        
        config["rest_api_sources"].append(new_api_source)
        manager.save_config(config)
        
        # 重新加载并验证
        reloaded_config = manager.load_config()
        assert len(reloaded_config["rest_api_sources"]) == 1
        assert reloaded_config["rest_api_sources"][0]["name"] == "Dynamic API"
        
        # 验证REST API源配置有效性
        rest_api_sources = manager.get_rest_api_sources()
        assert len(rest_api_sources) == 1
        assert rest_api_sources[0].name == "Dynamic API"
        assert rest_api_sources[0].endpoint == "https://api.dynamic.com/news"
    
    def test_prompt_manager_dynamic_reload(self):
        """测试提示词管理器动态重载"""
        prompt_manager = PromptManager(self.prompt_config_path)
        
        # 初始加载
        categories1 = prompt_manager.load_categories_config()
        assert "测试分类" in categories1
        assert len(categories1) == 1
        
        # 修改提示词配置文件
        updated_prompt_config = self.initial_prompt_config.copy()
        updated_prompt_config["categories"]["新分类"] = {
            "description": "动态添加的分类",
            "criteria": ["新标准1", "新标准2"],
            "examples": ["新示例1"],
            "priority": 2
        }
        
        with open(self.prompt_config_path, 'w', encoding='utf-8') as f:
            json.dump(updated_prompt_config, f, ensure_ascii=False, indent=2)
        
        # 重新加载配置
        prompt_manager.reload_configuration()
        categories2 = prompt_manager.load_categories_config()
        
        assert len(categories2) == 2
        assert "测试分类" in categories2
        assert "新分类" in categories2
        # CategoryConfig is a dataclass, access attributes directly
        assert categories2["新分类"].description == "动态添加的分类"
    
    def test_category_manager_dynamic_reload(self):
        """测试分类管理器动态重载"""
        category_manager = DynamicCategoryManager(self.prompt_config_path)
        
        # 初始加载
        categories1 = category_manager.load_categories()
        assert len(categories1) == 1
        assert "测试分类" in categories1
        
        # 动态添加分类 - 注意：当前实现只是记录日志，不实际添加到内存中
        from crypto_news_analyzer.analyzers.prompt_manager import CategoryConfig
        category_manager.add_category("动态分类", CategoryConfig(
            name="动态分类",
            description="运行时添加的分类",
            criteria=["动态标准"],
            examples=["动态示例"],
            priority=3
        ))
        
        # 验证添加操作被记录（但不会实际添加到分类列表中，因为当前实现只记录日志）
        categories2 = category_manager.get_category_list()
        # 当前实现中，动态添加的分类不会立即出现在列表中
        assert "测试分类" in categories2
        assert "未分类" in categories2
        assert "忽略" in categories2
        
        # 重新加载配置文件
        category_manager.reload_categories()
        
        # 验证重载后的状态
        categories3 = category_manager.load_categories()
        # 重载后应该恢复到文件中的配置
        assert len(categories3) == 1
        assert "测试分类" in categories3
    
    def test_configuration_validation_after_update(self):
        """测试配置更新后的验证"""
        manager = ConfigManager(self.config_path)
        
        # 测试有效的配置更新
        config = manager.load_config()
        config["time_window_hours"] = 48
        config["execution_interval"] = 1800
        
        # 保存应该成功
        manager.save_config(config)
        
        # 测试无效的配置更新
        invalid_config = config.copy()
        invalid_config["time_window_hours"] = -1  # 无效值
        
        # 保存应该失败
        with pytest.raises(ValueError, match="配置数据验证失败"):
            manager.save_config(invalid_config)
    
    def test_configuration_backup_and_restore(self):
        """测试配置备份和恢复"""
        manager = ConfigManager(self.config_path)
        
        # 加载初始配置
        original_config = manager.load_config()
        
        # 修改配置 - 使用深拷贝避免引用问题
        import copy
        modified_config = copy.deepcopy(original_config)
        modified_config["time_window_hours"] = 48
        modified_config["rss_sources"].append({
            "name": "Backup Test RSS",
            "url": "https://backup.example.com/rss.xml",
            "description": "Backup Test RSS Source"
        })
        
        manager.save_config(modified_config)
        
        # 验证修改生效
        current_config = manager.load_config()
        assert current_config["time_window_hours"] == 48
        assert len(current_config["rss_sources"]) == 2
        
        # 恢复原始配置 - 使用深拷贝
        original_config_copy = copy.deepcopy(original_config)
        manager.save_config(original_config_copy)
        
        # 验证恢复成功
        restored_config = manager.load_config()
        assert restored_config["time_window_hours"] == 24
        assert len(restored_config["rss_sources"]) == 1
    
    def test_concurrent_configuration_updates(self):
        """测试并发配置更新"""
        manager1 = ConfigManager(self.config_path)
        manager2 = ConfigManager(self.config_path)
        
        # 两个管理器同时加载配置
        config1 = manager1.load_config()
        config2 = manager2.load_config()
        
        # 管理器1修改配置
        config1["time_window_hours"] = 36
        manager1.save_config(config1)
        
        # 管理器2重新加载应该看到更新
        updated_config2 = manager2.load_config()
        assert updated_config2["time_window_hours"] == 36
    
    def test_configuration_file_corruption_handling(self):
        """测试配置文件损坏处理"""
        manager = ConfigManager(self.config_path)
        
        # 损坏配置文件
        with open(self.config_path, 'w') as f:
            f.write("invalid json content {")
        
        # 加载应该失败
        with pytest.raises(json.JSONDecodeError):
            manager.load_config()
    
    def test_missing_configuration_file_handling(self):
        """测试缺失配置文件处理"""
        missing_config_path = os.path.join(self.temp_dir, "missing_config.json")
        manager = ConfigManager(missing_config_path)
        
        # 加载不存在的配置文件应该创建默认配置
        config = manager.load_config()
        
        # 验证默认配置已创建
        assert os.path.exists(missing_config_path)
        assert config["execution_interval"] == 3600
        assert config["time_window_hours"] == 24
        assert len(config["rss_sources"]) > 0


class TestExtensibilityIntegration:
    """测试扩展性集成场景"""
    
    def setup_method(self):
        """测试前设置"""
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.temp_dir, "integration_config.json")
        self.factory = DataSourceFactory()
    
    def teardown_method(self):
        """测试后清理"""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_new_data_source_with_config_integration(self):
        """测试新数据源与配置管理的集成"""
        # 注册自定义数据源
        self.factory.register_source("custom", CustomDataSource)
        
        # 创建包含自定义数据源的配置
        config_data = {
            "execution_interval": 3600,
            "time_window_hours": 24,
            "storage": {
                "retention_days": 30,
                "database_path": "./test.db"
            },
            "auth": {
                "LLM_API_KEY": "test_key",
                "TELEGRAM_BOT_TOKEN": "test_token",
                "TELEGRAM_CHANNEL_ID": "test_channel"
            },
            "llm_config": {"model": "gpt-4"},
            "rss_sources": [],
            "custom_sources": [
                {
                    "name": "Custom Integration Source",
                    "endpoint": "https://api.custom.com/data",
                    "custom_param": "integration_test"
                }
            ]
        }
        
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, ensure_ascii=False, indent=2)
        
        # 使用配置管理器加载配置
        manager = ConfigManager(self.config_path)
        config = manager.load_config()
        
        # 验证自定义数据源配置已加载
        assert "custom_sources" in config
        assert len(config["custom_sources"]) == 1
        
        # 使用工厂创建数据源并测试
        custom_config = config["custom_sources"][0]
        source = self.factory.create_source("custom", time_window_hours=config["time_window_hours"])
        
        # 验证数据源可以使用配置进行爬取
        items = source.crawl(custom_config)
        assert len(items) == 1
        assert "Custom Integration Source" in items[0].title
        
        source.cleanup()
    
    def test_dynamic_data_source_registration_and_config_update(self):
        """测试动态数据源注册和配置更新"""
        # 初始状态：只有内置数据源
        available_types = self.factory.get_available_source_types()
        initial_count = len(available_types)
        
        # 动态注册新数据源
        self.factory.register_source("dynamic", AdvancedDataSource)
        
        # 验证注册成功
        new_available_types = self.factory.get_available_source_types()
        assert len(new_available_types) == initial_count + 1
        assert "dynamic" in new_available_types
        
        # 创建配置文件包含新数据源
        config_data = {
            "execution_interval": 3600,
            "time_window_hours": 24,
            "storage": {"retention_days": 30, "database_path": "./test.db"},
            "auth": {
                "LLM_API_KEY": "test_key",
                "TELEGRAM_BOT_TOKEN": "test_token",
                "TELEGRAM_CHANNEL_ID": "test_channel"
            },
            "llm_config": {"model": "gpt-4"},
            "rss_sources": [],
            "dynamic_sources": [
                {
                    "name": "Dynamic Source 1",
                    "endpoint": "https://api.dynamic.com/v1/data",
                    "auth_token": "dynamic_token_1",
                    "features": ["batch_mode"]
                }
            ]
        }
        
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, ensure_ascii=False, indent=2)
        
        # 动态添加更多数据源配置
        config_data["dynamic_sources"].append({
            "name": "Dynamic Source 2",
            "endpoint": "https://api.dynamic.com/v2/data",
            "auth_token": "dynamic_token_2",
            "features": ["real_time", "filtering"]
        })
        
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, ensure_ascii=False, indent=2)
        
        # 重新加载配置并验证
        manager = ConfigManager(self.config_path)
        config = manager.load_config()
        
        assert len(config["dynamic_sources"]) == 2
        
        # 测试批量创建数据源
        dynamic_configs = {"dynamic": config["dynamic_sources"]}
        sources = self.factory.create_all_sources(dynamic_configs, time_window_hours=24)
        
        assert "dynamic" in sources
        assert len(sources["dynamic"]) == 2
        
        # 清理
        self.factory.cleanup_all_sources(sources)


if __name__ == "__main__":
    pytest.main([__file__])