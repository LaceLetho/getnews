"""
配置管理器测试

测试ConfigManager类的核心功能。
"""

import tempfile
import os

from crypto_news_analyzer.config.manager import ConfigManager


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
        os.environ.pop("EXECUTION_INTERVAL", None)
        os.environ.pop("TIME_WINDOW_HOURS", None)

        config = self.manager.load_config()

        # 验证必需字段存在
        assert "storage" in config
        assert "rss_sources" in config

        # 验证默认值
        assert self.manager.get_execution_interval() == 3600
        assert self.manager.get_time_window_hours() == 24
        assert len(config["rss_sources"]) > 0

    def test_validate_config_success(self):
        """测试配置验证成功"""
        valid_config = {
            "storage": {
                "retention_days": 30,
                "max_storage_mb": 1000,
                "cleanup_frequency": "daily",
                "database_path": "./test.db",
            },
            "llm_config": {"model": "gpt-4"},
        }

        assert self.manager.validate_config(valid_config) is True

    def test_validate_config_failure(self):
        """测试配置验证失败"""
        invalid_config = {"storage": {"retention_days": 0, "database_path": "./test.db"}}

        assert self.manager.validate_config(invalid_config) is False

    def test_execution_interval_uses_env_or_default_only(self, monkeypatch):
        monkeypatch.delenv("EXECUTION_INTERVAL", raising=False)
        self.manager.config_data = {"execution_interval": 99}

        assert self.manager.get_execution_interval() == 3600

        monkeypatch.setenv("EXECUTION_INTERVAL", "7200")
        assert self.manager.get_execution_interval() == 7200

    def test_time_window_uses_env_or_default_only(self, monkeypatch):
        monkeypatch.delenv("TIME_WINDOW_HOURS", raising=False)
        self.manager.config_data = {"time_window_hours": 99}

        assert self.manager.get_time_window_hours() == 24

        monkeypatch.setenv("TIME_WINDOW_HOURS", "48")
        assert self.manager.get_time_window_hours() == 48

    def test_get_x_auth_credentials_does_not_depend_on_llm_auth_fields(self, monkeypatch):
        monkeypatch.setenv("X_CT0", "x-ct0-token")
        monkeypatch.setenv("X_AUTH_TOKEN", "x-auth-token")
        monkeypatch.delenv("LLM_API_KEY", raising=False)
        monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
        monkeypatch.delenv("TELEGRAM_CHANNEL_ID", raising=False)

        x_auth = self.manager.get_x_auth_credentials()

        assert x_auth["X_CT0"] == "x-ct0-token"
        assert x_auth["X_AUTH_TOKEN"] == "x-auth-token"
