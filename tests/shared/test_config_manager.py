"""
配置管理器测试

测试ConfigManager类的核心功能。
"""

import pytest
import tempfile
import os
from typing import cast

from crypto_news_analyzer.config.manager import ConfigManager
from crypto_news_analyzer.models import SemanticSearchConfig, StorageConfig


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
        assert config["llm_config"]["model"]["provider"] == "opencode-go"
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

    def test_load_config_supports_json_comments_in_semantic_search_block(self, monkeypatch):
        monkeypatch.setenv("DATABASE_URL", "postgresql://postgres:password@host:5432/db")

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

    def test_storage_config_default_postgres_connect_fields(self):
        """测试StorageConfig新字段的默认值"""
        config = StorageConfig()
        assert config.postgres_connect_max_attempts == 3
        assert config.postgres_connect_initial_delay_seconds == 1.0
        assert config.postgres_connect_max_delay_seconds == 10.0
        assert config.postgres_connect_timeout_seconds == 10

    def test_storage_config_valid_explicit_postgres_connect_fields(self):
        """测试StorageConfig显式设置有效值"""
        config = StorageConfig(
            postgres_connect_max_attempts=5,
            postgres_connect_initial_delay_seconds=2.0,
            postgres_connect_max_delay_seconds=20.0,
            postgres_connect_timeout_seconds=30,
        )
        assert config.postgres_connect_max_attempts == 5
        assert config.postgres_connect_initial_delay_seconds == 2.0
        assert config.postgres_connect_max_delay_seconds == 20.0
        assert config.postgres_connect_timeout_seconds == 30

    def test_storage_config_zero_max_attempts_raises(self):
        """测试postgres_connect_max_attempts为0时抛出异常"""
        with pytest.raises(ValueError, match="postgres_connect_max_attempts必须大于0"):
            StorageConfig(postgres_connect_max_attempts=0)

    def test_storage_config_negative_initial_delay_raises(self):
        """测试postgres_connect_initial_delay_seconds为负数时抛出异常"""
        with pytest.raises(ValueError, match="postgres_connect_initial_delay_seconds必须大于0"):
            StorageConfig(postgres_connect_initial_delay_seconds=-1.0)

    def test_storage_config_negative_max_delay_raises(self):
        """测试postgres_connect_max_delay_seconds为负数时抛出异常"""
        with pytest.raises(ValueError, match="postgres_connect_max_delay_seconds必须大于0"):
            StorageConfig(postgres_connect_max_delay_seconds=-5.0)

    def test_storage_config_max_delay_less_than_initial_delay_raises(self):
        """测试postgres_connect_max_delay_seconds小于postgres_connect_initial_delay_seconds时抛出异常"""
        with pytest.raises(
            ValueError,
            match="postgres_connect_max_delay_seconds必须大于等于postgres_connect_initial_delay_seconds",
        ):
            StorageConfig(
                postgres_connect_initial_delay_seconds=5.0,
                postgres_connect_max_delay_seconds=2.0,
            )

    def test_storage_config_zero_timeout_raises(self):
        """测试postgres_connect_timeout_seconds为0时抛出异常"""
        with pytest.raises(ValueError, match="postgres_connect_timeout_seconds必须大于0"):
            StorageConfig(postgres_connect_timeout_seconds=0)

    def test_get_storage_config_loads_explicit_postgres_connect_max_attempts(self):
        """测试ConfigManager从配置文件加载显式postgres_connect_max_attempts值"""
        import json

        config_with_explicit = {
            "storage": {
                "retention_days": 30,
                "max_storage_mb": 1000,
                "cleanup_frequency": "daily",
                "database_path": "./test.db",
                "postgres_connect_max_attempts": 5,
            },
            "llm_config": {
                "model": {"provider": "opencode-go", "name": "kimi-k2.5", "options": {}},
                "fallback_models": [
                    {"provider": "grok", "name": "grok-4-1-fast-reasoning", "options": {}}
                ],
                "market_model": {
                    "provider": "grok",
                    "name": "grok-4-1-fast-reasoning",
                    "options": {},
                },
            },
        }

        with open(self.config_path, "w", encoding="utf-8") as handle:
            json.dump(config_with_explicit, handle)

        self.manager.load_config()
        storage_config = self.manager.get_storage_config()

        assert storage_config.postgres_connect_max_attempts == 5

    def test_query_planning_enabled_omitted_uses_default_false(self):
        """query_planning_enabled not in config → default False."""
        manager = ConfigManager(config_path="./nonexistent-config.jsonc")
        manager.config_data = {
            "storage": {
                "retention_days": 30,
                "max_storage_mb": 1000,
                "cleanup_frequency": "daily",
                "backend": "sqlite",
                "database_path": "./data/crypto_news.db",
                "pgvector_dimensions": 1536,
            },
            "llm_config": {
                "model": {"provider": "kimi", "name": "kimi-k2.5", "options": {}},
                "fallback_models": [
                    {"provider": "grok", "name": "grok-4-1-fast-reasoning", "options": {}}
                ],
                "market_model": {
                    "provider": "grok",
                    "name": "grok-4-1-fast-reasoning",
                    "options": {},
                },
                "temperature": 0.4,
                "max_tokens": 1000,
                "batch_size": 7,
            },
        }
        config = manager.get_semantic_search_config()
        assert config.query_planning_enabled is False

    def test_query_planning_enabled_explicit_true_from_config(self):
        """Config with explicit query_planning_enabled: true is loaded correctly."""
        manager = ConfigManager(config_path="./nonexistent-config.jsonc")
        manager.config_data = {
            "storage": {
                "retention_days": 30,
                "max_storage_mb": 1000,
                "cleanup_frequency": "daily",
                "backend": "sqlite",
                "database_path": "./data/crypto_news.db",
                "pgvector_dimensions": 1536,
            },
            "llm_config": {
                "model": {"provider": "kimi", "name": "kimi-k2.5", "options": {}},
                "fallback_models": [
                    {"provider": "grok", "name": "grok-4-1-fast-reasoning", "options": {}}
                ],
                "market_model": {
                    "provider": "grok",
                    "name": "grok-4-1-fast-reasoning",
                    "options": {},
                },
                "temperature": 0.4,
                "max_tokens": 1000,
                "batch_size": 7,
            },
            "semantic_search": {
                "query_planning_enabled": True,
            },
        }
        config = manager.get_semantic_search_config()
        assert config.query_planning_enabled is True

    def test_query_planning_enabled_is_validated_type(self):
        """query_planning_enabled: non-bool config values are rejected."""
        with pytest.raises(ValueError, match="query_planning_enabled"):
            SemanticSearchConfig(query_planning_enabled="false")
