"""
配置管理器

负责配置文件的读取、验证和管理。
"""

import logging
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from dotenv import load_dotenv

from .llm_registry import LLMRegistryError, validate_llm_config_payload
from ..datasource_payloads import (
    DataSourcePayloadValidationError,
    RuntimeSource,
    runtime_source_from_record,
    validate_datasource_config_payload,
)
from ..domain.models import DataSource
from ..domain.repositories import DataSourceRepository
from ..models import (
    IntelligenceConfig,
    RSSSource,
    XSource,
    AuthConfig,
    StorageConfig,
    RESTAPISource,
    BirdConfig,
    SemanticSearchConfig,
)


class ConfigManager:
    """配置文件管理器"""

    def __init__(self, config_path: str = "./config.jsonc"):
        """
        初始化配置管理器

        Args:
            config_path: 配置文件路径
        """
        self.config_path = Path(config_path)
        self.config_data: Dict[str, Any] = {}
        self.logger = logging.getLogger(__name__)
        self._datasource_repository: Optional[DataSourceRepository] = None

        # 加载环境变量
        load_dotenv()
        self.logger.info("环境变量已加载")

    def set_datasource_repository(
        self, repository: Optional[DataSourceRepository]
    ) -> None:
        self._datasource_repository = repository

    def load_config(self) -> Dict[str, Any]:
        """
        加载配置文件

        Returns:
            配置数据字典

        Raises:
            FileNotFoundError: 配置文件不存在
            json.JSONDecodeError: 配置文件格式无效
        """
        try:
            if not self.config_path.exists():
                self.logger.info(f"配置文件不存在，创建默认配置: {self.config_path}")
                self._create_default_config()

            with open(self.config_path, "r", encoding="utf-8") as f:
                self.config_data = self.parse_jsonc(f.read())

            if not self.validate_config(self.config_data):
                raise ValueError("配置文件验证失败")

            self.logger.info("配置文件加载成功")
            return self.config_data

        except json.JSONDecodeError as e:
            self.logger.error(f"配置文件格式无效: {e}")
            raise
        except Exception as e:
            self.logger.error(f"加载配置文件失败: {e}")
            raise

    @staticmethod
    def parse_jsonc(raw_text: str) -> Dict[str, Any]:
        """Load JSON while tolerating // and /* */ comments outside strings."""
        sanitized_chars: List[str] = []
        in_string = False
        escape_next = False
        index = 0
        text_length = len(raw_text)

        while index < text_length:
            char = raw_text[index]
            next_char = raw_text[index + 1] if index + 1 < text_length else ""

            if in_string:
                sanitized_chars.append(char)
                if escape_next:
                    escape_next = False
                elif char == "\\":
                    escape_next = True
                elif char == '"':
                    in_string = False
                index += 1
                continue

            if char == '"':
                in_string = True
                sanitized_chars.append(char)
                index += 1
                continue

            if char == "/" and next_char == "/":
                index += 2
                while index < text_length and raw_text[index] not in ("\n", "\r"):
                    index += 1
                continue

            if char == "/" and next_char == "*":
                index += 2
                while index + 1 < text_length and not (
                    raw_text[index] == "*" and raw_text[index + 1] == "/"
                ):
                    index += 1
                index = min(index + 2, text_length)
                continue

            sanitized_chars.append(char)
            index += 1

        return json.loads("".join(sanitized_chars))

    def validate_config(self, config: Dict[str, Any]) -> bool:
        """
        验证配置文件有效性

        Args:
            config: 配置数据

        Returns:
            是否有效
        """
        try:
            # 验证必需的顶级字段（execution_interval和time_window_hours现在从环境变量读取，不再必需）
            required_fields = ["storage", "llm_config"]

            for field in required_fields:
                if field not in config:
                    self.logger.error(f"缺少必需配置字段: {field}")
                    return False

            # 验证存储配置
            storage_config = config["storage"]
            if (
                not isinstance(storage_config.get("retention_days"), int)
                or storage_config["retention_days"] <= 0
            ):
                self.logger.error("数据保留天数必须为正整数")
                return False

            if (
                not isinstance(storage_config.get("max_storage_mb"), int)
                or storage_config["max_storage_mb"] <= 0
            ):
                self.logger.error("最大存储空间必须为正整数")
                return False

            cleanup_frequency = storage_config.get("cleanup_frequency", "daily")
            if cleanup_frequency not in ["daily", "weekly", "monthly"]:
                self.logger.error(f"无效的清理频率: {cleanup_frequency}")
                return False

            backend = storage_config.get("backend", "sqlite")
            if backend not in ["sqlite", "postgres"]:
                self.logger.error(f"不支持的存储后端: {backend}")
                return False

            if backend == "postgres":
                database_url = os.getenv("DATABASE_URL", "")
                if not isinstance(database_url, str) or not database_url.strip():
                    self.logger.error("PostgreSQL模式下必须提供DATABASE_URL环境变量")
                    return False
            else:
                storage_path = storage_config.get(
                    "database_path", "./data/crypto_news.db"
                )
                if not self.validate_storage_path(storage_path):
                    return False

            try:
                validate_llm_config_payload(config["llm_config"])
            except LLMRegistryError as exc:
                self.logger.error(f"LLM配置无效: {exc}")
                return False

            llm_batch_size = config["llm_config"].get("batch_size", 10)
            semantic_search_data = dict(config.get("semantic_search", {}))
            if "synthesis_batch_size" not in semantic_search_data:
                semantic_search_data["synthesis_batch_size"] = llm_batch_size

            try:
                SemanticSearchConfig.from_dict(semantic_search_data)
            except ValueError as exc:
                self.logger.error(f"语义搜索配置无效: {exc}")
                return False

            intelligence_collection_data = dict(config.get("intelligence_collection", {}))
            if intelligence_collection_data:
                try:
                    IntelligenceConfig.from_dict(intelligence_collection_data)
                except ValueError as exc:
                    self.logger.error(f"智能采集配置无效: {exc}")
                    return False

            # 验证RSS源配置
            if "rss_sources" in config:
                for source in config["rss_sources"]:
                    if not self._validate_rss_source(source):
                        return False

            # 验证X源配置
            if "x_sources" in config:
                for source in config["x_sources"]:
                    if not self._validate_x_source(source):
                        return False

            # 验证REST API源配置
            if "rest_api_sources" in config:
                for source in config["rest_api_sources"]:
                    if not self._validate_rest_api_source(source):
                        return False

            self.logger.info("配置文件验证通过")
            return True

        except Exception as e:
            self.logger.error(f"配置验证过程中出错: {e}")
            return False

    def save_config(self, config: Dict[str, Any]) -> None:
        """
        保存配置到文件

        Args:
            config: 配置数据

        Raises:
            ValueError: 配置数据无效
        """
        if not self.validate_config(config):
            raise ValueError("配置数据验证失败，无法保存")

        try:
            # 确保配置目录存在
            self.config_path.parent.mkdir(parents=True, exist_ok=True)

            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=2)

            self.config_data = config
            self.logger.info(f"配置已保存到: {self.config_path}")

        except Exception as e:
            self.logger.error(f"保存配置文件失败: {e}")
            raise

    def get_rss_sources(self) -> List[RSSSource]:
        """获取RSS订阅源列表"""
        return [
            source
            for source in self._get_runtime_sources("rss")
            if isinstance(source, RSSSource)
        ]

    def get_x_sources(self) -> List[XSource]:
        """获取X/Twitter信息源列表"""
        return [
            source
            for source in self._get_runtime_sources("x")
            if isinstance(source, XSource)
        ]

    def get_rest_api_sources(self) -> List[RESTAPISource]:
        """获取REST API数据源列表"""
        return [
            source
            for source in self._get_runtime_sources("rest_api")
            if isinstance(source, RESTAPISource)
        ]

    def _get_runtime_sources(
        self,
        source_type: str,
    ) -> List[RuntimeSource]:
        if self._datasource_repository is not None:
            records = list(self._datasource_repository.list(source_type=source_type))
        else:
            config_key_by_type = {
                "rss": "rss_sources",
                "x": "x_sources",
                "rest_api": "rest_api_sources",
            }
            config_key = config_key_by_type[source_type]
            records = [
                {
                    "source_type": source_type,
                    "config_payload": source_data,
                }
                for source_data in self.config_data.get(config_key, [])
            ]

        return [runtime_source_from_record(record) for record in records]

    def get_auth_config(self) -> AuthConfig:
        """获取认证配置，从环境变量读取"""
        # 所有认证参数都从环境变量获取
        return AuthConfig(
            X_CT0=os.getenv("X_CT0", ""),
            X_AUTH_TOKEN=os.getenv("X_AUTH_TOKEN", ""),
            GROK_API_KEY=os.getenv("GROK_API_KEY", ""),
            KIMI_API_KEY=os.getenv("KIMI_API_KEY", ""),
            OPENAI_API_KEY=os.getenv("OPENAI_API_KEY", ""),
            OPENCODE_API_KEY=os.getenv("OPENCODE_API_KEY", ""),
            TELEGRAM_BOT_TOKEN=os.getenv("TELEGRAM_BOT_TOKEN", ""),
            TELEGRAM_CHANNEL_ID=os.getenv("TELEGRAM_CHANNEL_ID", ""),
        )

    def get_x_auth_credentials(self) -> Dict[str, str]:
        return {
            "X_CT0": os.getenv("X_CT0", "").strip(),
            "X_AUTH_TOKEN": os.getenv("X_AUTH_TOKEN", "").strip(),
        }

    def get_execution_interval(self) -> int:
        """
        获取执行间隔（秒）

        Returns:
            执行间隔（秒）
        """
        # 优先从环境变量读取
        env_value = os.getenv("EXECUTION_INTERVAL")
        if env_value:
            try:
                return int(env_value)
            except ValueError:
                self.logger.warning(
                    f"环境变量EXECUTION_INTERVAL值无效: {env_value}，使用默认值"
                )

        return 3600

    def get_time_window_hours(self) -> int:
        """
        获取时间窗口（小时）

        Returns:
            时间窗口（小时）
        """
        # 优先从环境变量读取
        env_value = os.getenv("TIME_WINDOW_HOURS")
        if env_value:
            try:
                return int(env_value)
            except ValueError:
                self.logger.warning(
                    f"环境变量TIME_WINDOW_HOURS值无效: {env_value}，使用默认值"
                )

        return 24

    def get_storage_config(self) -> StorageConfig:
        """获取存储配置"""
        storage_data = self.config_data["storage"]
        backend = storage_data.get("backend", "sqlite")
        database_url = os.getenv("DATABASE_URL")
        return StorageConfig(
            retention_days=storage_data.get("retention_days", 30),
            max_storage_mb=storage_data.get("max_storage_mb", 1000),
            cleanup_frequency=storage_data.get("cleanup_frequency", "daily"),
            backend=backend,
            database_path=storage_data.get("database_path", "./data/crypto_news.db"),
            database_url=database_url,
            pgvector_dimensions=storage_data.get("pgvector_dimensions", 1536),
        )

    def get_bird_config(self) -> BirdConfig:
        """获取Bird工具配置"""
        return BirdConfig(
            executable_path=os.getenv("BIRD_EXECUTABLE_PATH", "bird"),
            timeout_seconds=int(os.getenv("BIRD_TIMEOUT_SECONDS", 300)),
            max_retries=int(os.getenv("BIRD_MAX_RETRIES", 3)),
            output_format=os.getenv("BIRD_OUTPUT_FORMAT", "json"),
            rate_limit_delay=float(os.getenv("BIRD_RATE_LIMIT_DELAY", 1.0)),
            config_file_path=os.getenv("BIRD_CONFIG_PATH", "~/.bird/config.json"),
            enable_auto_retry=os.getenv("BIRD_ENABLE_AUTO_RETRY", "true").lower()
            == "true",
            retry_delay_seconds=int(os.getenv("BIRD_RETRY_DELAY_SECONDS", 60)),
            bird_max_page=int(os.getenv("BIRD_MAX_PAGE", 3)),
        )

    def get_semantic_search_config(self) -> SemanticSearchConfig:
        """获取语义搜索配置。"""
        semantic_search_data = dict(self.config_data.get("semantic_search", {}))
        llm_batch_size = self.config_data.get("llm_config", {}).get("batch_size", 10)
        if "synthesis_batch_size" not in semantic_search_data:
            semantic_search_data["synthesis_batch_size"] = llm_batch_size
        return SemanticSearchConfig.from_dict(semantic_search_data)

    def get_intelligence_config(self) -> IntelligenceConfig:
        """获取智能采集配置。"""
        intelligence_data = dict(self.config_data.get("intelligence_collection", {}))
        return IntelligenceConfig.from_dict(intelligence_data)

    def get_analysis_config(self) -> Dict[str, int]:
        """
        获取分析配置

        Returns:
            包含 max_analysis_window_hours 和 min_analysis_window_hours 的字典
        """
        analysis_data = self.config_data.get("analysis_config", {})
        return {
            "max_analysis_window_hours": analysis_data.get(
                "max_analysis_window_hours", 24
            ),
            "min_analysis_window_hours": analysis_data.get(
                "min_analysis_window_hours", 1
            ),
        }

    def validate_bird_installation(self) -> bool:
        """
        验证bird工具安装状态

        Returns:
            bool: 是否已正确安装
        """
        try:
            from ..crawlers.bird_dependency_manager import BirdDependencyManager

            bird_config = self.get_bird_config()
            dependency_manager = BirdDependencyManager(bird_config)
            status = dependency_manager.check_bird_availability()

            if not status.available:
                self.logger.warning(f"Bird工具不可用: {status.error_message}")
                return False

            self.logger.info(f"Bird工具验证成功: 版本 {status.version}")
            return True

        except Exception as e:
            self.logger.error(f"验证bird工具安装失败: {str(e)}")
            return False

    def load_auth_from_env(self) -> AuthConfig:
        """从环境变量加载认证配置（别名方法，保持向后兼容）"""
        return self.get_auth_config()

    def validate_storage_path(self, path: str) -> bool:
        """
        验证存储路径有效性

        Args:
            path: 存储路径

        Returns:
            是否有效
        """
        try:
            storage_path = Path(path)

            # 确保父目录可以创建
            storage_path.parent.mkdir(parents=True, exist_ok=True)

            # 检查是否有写权限
            if storage_path.exists():
                if not os.access(storage_path, os.W_OK):
                    self.logger.error(f"存储路径无写权限: {path}")
                    return False
            else:
                # 检查父目录写权限
                if not os.access(storage_path.parent, os.W_OK):
                    self.logger.error(f"存储目录无写权限: {storage_path.parent}")
                    return False

            return True

        except Exception as e:
            self.logger.error(f"验证存储路径失败: {e}")
            return False

    def _create_default_config(self) -> None:
        """创建默认配置文件"""
        default_config = {
            "storage": {
                "retention_days": 30,
                "max_storage_mb": 1000,
                "cleanup_frequency": "daily",
                "backend": "sqlite",
                "database_path": "./data/crypto_news.db",
                "pgvector_dimensions": 1536,
            },
            "llm_config": {
                "model": {
                    "provider": "kimi",
                    "name": "kimi-k2.5",
                    "options": {},
                },
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
                "temperature": 0.4,
                "market_prompt_path": "./prompts/market_summary_prompt.md",
                "analysis_prompt_path": "./prompts/analysis_prompt.md",
                "batch_size": 10,
                "min_weight_score": 50,
                "cache_ttl_minutes": 240,
                "cached_messages_hours": 24,
                "enable_debug_logging": False,
            },
            "semantic_search": {
                "query_max_chars": 300,
                "max_subqueries": 4,
                "per_subquery_limit": 50,
                "max_retained_items": 200,
                "synthesis_batch_size": 10,
                "embedding_model": "text-embedding-3-small",
                "embedding_dimensions": 1536,
                "keyword_search_enabled": True,
                "keyword_search_limit": 30,
                "max_keyword_queries": 12,
                "enabled": True,
            },
            "intelligence_collection": {
                "extraction": {
                    "provider": "opencode-go",
                    "model": "kimi-k2.5",
                    "temperature": 0.5,
                    "max_tokens": 4000,
                },
                "collection": {
                    "interval_minutes": 60,
                    "ttl_days": 30,
                    "backfill_hours": 24,
                    "confidence_threshold": 0.6,
                },
                "sources": {},
            },
            "rss_sources": [
                {
                    "name": "PANews",
                    "url": "https://www.panewslab.com/zh/rss/newsflash.xml",
                    "description": "PANews 快讯",
                },
                {
                    "name": "金色财经",
                    "url": "https://www.jinse.com/rss/flash.xml",
                    "description": "金色财经快讯",
                },
            ],
            "x_sources": [
                {
                    "name": "Crypto List 1",
                    "url": "https://x.com/i/lists/1826855418095980750",
                    "type": "list",
                }
            ],
            "rest_api_sources": [],
        }

        self.save_config(default_config)

    def _validate_rss_source(self, source: Dict[str, Any]) -> bool:
        """验证RSS源配置"""
        try:
            validate_datasource_config_payload("rss", source)
        except DataSourcePayloadValidationError as exc:
            self.logger.error(f"RSS源配置无效: {exc}")
            return False
        return True

    def _validate_x_source(self, source: Dict[str, Any]) -> bool:
        """验证X源配置"""
        try:
            validate_datasource_config_payload("x", source)
        except DataSourcePayloadValidationError as exc:
            self.logger.error(f"X源配置无效: {exc}")
            return False
        return True

    def _validate_rest_api_source(self, source: Dict[str, Any]) -> bool:
        """验证REST API源配置"""
        try:
            validate_datasource_config_payload("rest_api", source)
        except DataSourcePayloadValidationError as exc:
            self.logger.error(f"REST API源配置无效: {exc}")
            return False
        return True
