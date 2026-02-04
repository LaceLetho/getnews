"""
配置管理器测试

测试ConfigManager类的核心功能。
"""

import pytest
import json
import tempfile
import os
from pathlib import Path

from crypto_news_analyzer.config.manager import ConfigManager
from crypto_news_analyzer.utils.errors import ConfigError


class TestConfigManager:
    """配置管理器测试类"""
    
    def setup_method(self):
        """测试前设置"""
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.temp_dir, "test_config.json")
        self.manager = ConfigManager(self.config_path)
    
    def teardown_method(self):
        """测试后清理"""
        if os.path.exists(self.config_path):
            os.remove(self.config_path)
        os.rmdir(self.temp_dir)
    
    def test_create_default_config(self):
        """测试创建默认配置"""
        config = self.manager.load_config()
        
        # 验证必需字段存在
        assert "execution_interval" in config
        assert "time_window_hours" in config
        assert "storage" in config
        assert "rss_sources" in config
        
        # 验证默认值
        assert config["execution_interval"] == 3600
        assert config["time_window_hours"] == 24
        assert len(config["rss_sources"]) > 0
    
    def test_validate_config_success(self):
        """测试配置验证成功"""
        valid_config = {
            "execution_interval": 1800,
            "time_window_hours": 12,
            "storage": {
                "retention_days": 30,
                "database_path": "./test.db"
            },
            "llm_config": {
                "model": "gpt-4"
            }
        }
        
        assert self.manager.validate_config(valid_config) is True
    
    def test_validate_config_failure(self):
        """测试配置验证失败"""
        invalid_config = {
            "execution_interval": -1,  # 无效值
            "time_window_hours": "invalid"  # 错误类型
        }
        
        assert self.manager.validate_config(invalid_config) is False