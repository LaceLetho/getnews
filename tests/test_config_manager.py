"""
配置管理器测试

测试ConfigManager类的核心功能。
"""

import tempfile
import os
from typing import cast

from crypto_news_analyzer.config.manager import ConfigManager


class TestConfigManager:
    """配置管理器测试类"""

    temp_dir: str = ""
    config_path: str = ""
    manager: ConfigManager = cast(ConfigManager, object())

    def setup_method(self):
        """测试前设置"""
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.temp_dir, "test_config.jsonc")
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
        assert config["llm_config"]["model"]["provider"] == "kimi"
        assert config["llm_config"]["market_model"]["provider"] == "grok"

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
            "llm_config": {
                "model": {"provider": "kimi", "name": "kimi-k2.5", "options": {}},
                "fallback_models": [
                    {
                        "provider": "grok",
                        "name": "grok-4-1-fast-reasoning",
                        "options": {},
                    }
                ],
                "market_model": {
                    "provider": "grok",
                    "name": "grok-4-1-fast-reasoning",
                    "options": {},
                },
            },
        }

        assert self.manager.validate_config(valid_config) is True

    def test_validate_config_failure(self):
        """测试配置验证失败"""
        invalid_config = {
            "storage": {"retention_days": 0, "database_path": "./test.db"}
        }

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

    def test_get_x_auth_credentials_does_not_depend_on_llm_auth_fields(
        self, monkeypatch
    ):
        monkeypatch.setenv("X_CT0", "x-ct0-token")
        monkeypatch.setenv("X_AUTH_TOKEN", "x-auth-token")
        monkeypatch.delenv("LLM_API_KEY", raising=False)
        monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
        monkeypatch.delenv("TELEGRAM_CHANNEL_ID", raising=False)

        x_auth = self.manager.get_x_auth_credentials()

        assert x_auth["X_CT0"] == "x-ct0-token"
        assert x_auth["X_AUTH_TOKEN"] == "x-auth-token"

    def test_load_config_supports_json_comments_in_semantic_search_block(
        self, monkeypatch
    ):
        monkeypatch.setenv(
            "DATABASE_URL", "postgresql://postgres:password@host:5432/db"
        )

        config_with_comments = """
        {
          "storage": {
            "retention_days": 30,
            "max_storage_mb": 1000,
            "cleanup_frequency": "daily",
            "backend": "postgres",
            "pgvector_dimensions": 1536
          },
          "llm_config": {
            "model": {"provider": "opencode-go", "name": "kimi-k2.5", "options": {}},
            "fallback_models": [
              {"provider": "grok", "name": "grok-4-1-fast-reasoning", "options": {}}
            ],
            "market_model": {"provider": "grok", "name": "grok-4-1-fast-reasoning", "options": {}},
            "batch_size": 10
          },
          "semantic_search": {
            // 用户输入 query 的最大字符数
            "query_max_chars": 300,
            /* LLM 最多拆成多少个子查询 */
            "max_subqueries": 4,
            "per_subquery_limit": 50,
            "max_retained_items": 200,
            "synthesis_batch_size": 10,
            "embedding_model": "text-embedding-3-small",
            "embedding_dimensions": 1536,
            "enabled": true
          }
        }
        """.strip()

        with open(self.config_path, "w", encoding="utf-8") as handle:
            handle.write(config_with_comments)

        loaded = self.manager.load_config()
        semantic_search = self.manager.get_semantic_search_config()

        assert loaded["semantic_search"]["query_max_chars"] == 300
        assert semantic_search.max_subqueries == 4
        assert semantic_search.embedding_dimensions == 1536
        assert semantic_search.enabled is True
