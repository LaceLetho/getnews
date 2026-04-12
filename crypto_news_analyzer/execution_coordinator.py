"""
执行协调器 (MainController)

协调系统内部各组件的执行顺序和工作流管理。支持一次性执行模式、内部定时调度和命令触发执行，适合Docker容器化部署。

根据需求9实现Docker化部署和内部定时调度功能：
- 需求9.1: 提供主控制器支持一次性执行模式，执行完整工作流后自动退出
- 需求9.2: 提供内部定时调度器，支持程序内部的周期性任务执行
- 需求9.3: 支持通过配置文件或环境变量设置调度间隔
- 需求9.8: 在指定的时间间隔自动触发完整的数据收集和分析工作流
- 需求9.9: 运行在定时调度模式时持续运行直到接收到停止信号
- 需求9.15: 容器环境配置无效时快速失败并提供明确的错误信息
- 需求9.19: 记录每次执行的开始时间、结束时间和执行状态
- 需求9.20: 定时任务执行失败时记录错误信息并在下个调度周期继续尝试
"""

import os
import sys
import signal
import threading
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, asdict
from enum import Enum
import json
import traceback
import asyncio

from .config.manager import ConfigManager
from .config.llm_registry import (
    get_provider_record,
    resolve_model_runtime,
    validate_llm_config_payload,
)
from .domain.models import DataSource, IngestionJob, IngestionJobStatus
from .storage.data_manager import DataManager
from .crawlers.data_source_factory import get_data_source_factory
from .analyzers.llm_analyzer import LLMAnalyzer
from .reporters.report_generator import ReportGenerator, create_analyzed_data
from .reporters.telegram_sender import TelegramSenderSync, create_telegram_config
from .models import ContentItem, CrawlStatus, CrawlResult, AnalysisResult, TelegramCommandConfig
from .utils.logging import get_log_manager
from .utils.errors import ErrorRecoveryManager


class ExecutionMode(Enum):
    """执行模式"""
    ONE_TIME = "one_time"  # 一次性执行
    SCHEDULED = "scheduled"  # 定时调度
    COMMAND_TRIGGERED = "command_triggered"  # 命令触发


class ExecutionStatus(Enum):
    """执行状态"""
    NOT_STARTED = "not_started"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


@dataclass
class ExecutionInfo:
    """执行信息"""
    execution_id: str
    trigger_type: str  # "scheduled", "manual", "startup"
    trigger_user: Optional[str]
    start_time: datetime
    end_time: Optional[datetime]
    status: ExecutionStatus
    progress: float  # 0.0 to 1.0
    current_stage: str  # "crawling", "analyzing", "reporting", "sending"
    error_message: Optional[str]
    items_processed: int = 0
    categories_found: Dict[str, int] = None

    def __post_init__(self):
        if self.categories_found is None:
            self.categories_found = {}


@dataclass
class ExecutionResult:
    """执行结果"""
    execution_id: str
    success: bool
    start_time: datetime
    end_time: datetime
    duration_seconds: float
    items_processed: int
    categories_found: Dict[str, int]
    errors: List[str]
    trigger_user: Optional[str]
    report_sent: bool
    trigger_type: str = "manual"  # "scheduled", "manual", "startup"
    trigger_chat_id: Optional[str] = None  # 触发命令的聊天ID

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        data = asdict(self)
        data['start_time'] = self.start_time.isoformat()
        data['end_time'] = self.end_time.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ExecutionResult':
        """从字典反序列化"""
        if isinstance(data['start_time'], str):
            data['start_time'] = datetime.fromisoformat(data['start_time'])
        if isinstance(data['end_time'], str):
            data['end_time'] = datetime.fromisoformat(data['end_time'])
        return cls(**data)



class MainController:
    """
    主控制器 (ExecutionCoordinator)
    
    负责协调系统各组件的执行，支持多种运行模式。
    """
    
    def __init__(self, config_path: str = "./config.json"):
        """
        初始化主控制器
        
        Args:
            config_path: 配置文件路径
        """
        self.config_path = config_path
        self.logger = logging.getLogger(__name__)
        
        # 核心组件
        self.config_manager: Optional[ConfigManager] = None
        self.data_manager: Optional[DataManager] = None
        self.llm_analyzer: Optional[LLMAnalyzer] = None
        self.report_generator: Optional[ReportGenerator] = None
        self.telegram_sender: Optional[TelegramSenderSync] = None
        self.error_manager: Optional[ErrorRecoveryManager] = None
        self.command_handler: Optional[Any] = None  # TelegramCommandHandler实例
        self.cache_manager: Optional[Any] = None  # SentMessageCacheManager实例
        self.market_snapshot_service: Optional[Any] = None  # MarketSnapshotService实例（可选）
        self.analysis_repository: Optional[Any] = None
        self.ingestion_repository: Optional[Any] = None
        self.content_repository: Optional[Any] = None
        self.cache_repository: Optional[Any] = None
        self.datasource_repository: Optional[Any] = None
        
        # 执行状态管理
        self.current_execution: Optional[ExecutionInfo] = None
        self.execution_history: List[ExecutionResult] = []
        self._execution_lock = threading.RLock()
        self._stop_event = threading.Event()
        self._scheduler_thread: Optional[threading.Thread] = None
        self._last_scheduled_time: Optional[datetime] = None  # 上次调度任务开始的时间
        self._history_file = "./data/execution_history.json"  # 执行历史持久化文件
        
        # 并发控制
        self._max_concurrent_executions = 1
        self._execution_timeout_minutes = 30
        
        # 信号处理
        self._setup_signal_handlers()
        
        # 初始化标志
        self._initialized = False
        
        # 加载执行历史
        self._load_execution_history()
         
        self.logger.info("主控制器初始化完成")

    @staticmethod
    def _normalize_manual_recipient_key(manual_source: str, recipient_id: str) -> str:
        normalized_source = str(manual_source).strip().lower()
        normalized_recipient_id = str(recipient_id).strip()

        if normalized_source not in {"api", "telegram"}:
            raise ValueError(f"不支持的手动分析来源: {manual_source}")

        if not normalized_recipient_id:
            raise ValueError("手动分析接收者标识不能为空")

        return f"{normalized_source}:{normalized_recipient_id}"

    def _resolve_manual_recipient_key(self, chat_id: str, manual_source: str = "telegram") -> str:
        normalized_chat_id = str(chat_id).strip()

        if normalized_chat_id.startswith("api:") or normalized_chat_id.startswith("telegram:"):
            return normalized_chat_id

        return self._normalize_manual_recipient_key(manual_source, normalized_chat_id)

    def _record_manual_analysis_success(
        self,
        recipient_key: str,
        time_window_hours: int,
        items_count: int,
    ) -> None:
        if self.analysis_repository is None:
            raise ValueError("分析仓储未初始化")

        self.analysis_repository.log_execution(
            recipient_key=recipient_key,
            time_window_hours=time_window_hours,
            items_count=items_count,
            success=True,
        )

    def _build_manual_report_messages(
        self,
        categorized_items: Optional[Dict[str, List[Any]]],
    ) -> List[Dict[str, str]]:
        messages_to_cache: List[Dict[str, str]] = []
        if not categorized_items:
            return messages_to_cache

        for items in categorized_items.values():
            for item in items:
                messages_to_cache.append(
                    {
                        "title": item.title,
                        "body": item.body,
                        "category": item.category,
                        "time": item.time,
                    }
                )

        return messages_to_cache

    def _persist_manual_analysis_success(
        self,
        recipient_key: str,
        time_window_hours: int,
        items_count: int,
        final_report_messages: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        if final_report_messages:
            if self.cache_repository is None:
                raise ValueError("缓存仓储未初始化")

            cached_count = self.cache_repository.cache_sent_messages(
                final_report_messages,
                recipient_key=recipient_key,
            )
            self.logger.info(
                f"手动分析成功标题已缓存，recipient_key={recipient_key}，titles={cached_count}"
            )

        self._record_manual_analysis_success(
            recipient_key=recipient_key,
            time_window_hours=time_window_hours,
            items_count=items_count,
        )

    def _get_manual_historical_titles(self, recipient_key: str) -> List[str]:
        if self.analysis_repository is None:
            raise ValueError("分析仓储未初始化")

        if self.cache_repository is None:
            self.logger.info(
                f"缓存仓储未初始化，recipient_key={recipient_key}，使用空历史标题集"
            )
            return []

        prior_success_time = self.analysis_repository.get_last_successful_analysis(recipient_key)
        if prior_success_time is None:
            self.logger.info(
                f"手动分析无历史成功锚点，recipient_key={recipient_key}，使用空历史标题集"
            )
            return []

        historical_titles = self.cache_repository.get_titles_since(
            recipient_key,
            since=prior_success_time,
        )
        self.logger.info(
            f"手动分析历史标题查询完成，recipient_key={recipient_key}，anchor_time={prior_success_time.isoformat()}，titles={len(historical_titles)}"
        )
        return historical_titles
    
    def _setup_signal_handlers(self) -> None:
        """
        设置信号处理器
        
        需求9.11: 实现优雅停止机制，处理SIGTERM和SIGINT信号
        """
        def signal_handler(signum, frame):
            signal_name = "SIGTERM" if signum == signal.SIGTERM else "SIGINT" if signum == signal.SIGINT else f"Signal {signum}"
            self.logger.info(f"接收到信号 {signal_name}，开始优雅关闭")
            
            # 设置停止标志
            self._stop_event.set()
            
            # 如果有正在执行的任务，标记为取消状态
            with self._execution_lock:
                if self.current_execution and self.current_execution.status == ExecutionStatus.RUNNING:
                    self.logger.info(f"正在取消执行: {self.current_execution.execution_id}")
                    self.current_execution.status = ExecutionStatus.CANCELLED
            
            # 停止调度器
            self.stop_scheduler()
            
            # 清理资源
            self.cleanup_resources()
            
            self.logger.info("优雅关闭完成")
        
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)
    
    def initialize_system(self) -> bool:
        """
        初始化系统组件
        
        Returns:
            是否初始化成功
        """
        try:
            self.logger.info("开始初始化系统组件")
            config_data = self._initialize_core_system_components()
            runtime_mode = os.environ.get("CRYPTO_NEWS_RUNTIME_MODE", "analysis-service").strip().lower()
            
            # 初始化LLM分析器
            auth_config = self.config_manager.get_auth_config()
            llm_config = validate_llm_config_payload(config_data.get("llm_config", {}))
            analysis_model_runtime = resolve_model_runtime(llm_config.model)
            fallback_model_runtimes = [
                resolve_model_runtime(model_config) for model_config in llm_config.fallback_models
            ]
            market_model_runtime = resolve_model_runtime(llm_config.market_model)
            provider_credentials = self._resolve_provider_credentials(auth_config, llm_config)
            self._validate_runtime_auth(
                auth_config,
                llm_config,
                mode=runtime_mode,
            )
            
            self.llm_analyzer = LLMAnalyzer(
                provider_credentials=provider_credentials,
                model=analysis_model_runtime,
                fallback_models=fallback_model_runtimes,
                market_model=market_model_runtime,
                market_prompt_path=llm_config.market_prompt_path,
                analysis_prompt_path=llm_config.analysis_prompt_path,
                temperature=llm_config.temperature,
                max_tokens=llm_config.max_tokens,
                batch_size=llm_config.batch_size,
                cache_ttl_minutes=llm_config.cache_ttl_minutes,
                cached_messages_hours=llm_config.cached_messages_hours,
                mock_mode=False,
                storage_config=self.storage_config,  # 传入storage_config以创建缓存管理器
                config=config_data  # 传入完整配置
            )
            
            # 获取LLMAnalyzer内部的market_snapshot_service实例供命令处理器使用
            self.market_snapshot_service = self.llm_analyzer.market_snapshot_service
            
            # 初始化内容分类器
            self.logger.info("LLM分析器初始化完成")
            
            # 初始化报告生成器
            self.report_generator = ReportGenerator(
                omit_empty_categories=True
            )
            self.logger.info("报告生成器初始化完成")
            
            # 初始化Telegram发送器
            if auth_config.TELEGRAM_BOT_TOKEN and auth_config.TELEGRAM_CHANNEL_ID:
                telegram_config = create_telegram_config(
                    bot_token=auth_config.TELEGRAM_BOT_TOKEN,
                    channel_id=auth_config.TELEGRAM_CHANNEL_ID
                )
                self.telegram_sender = TelegramSenderSync(telegram_config)
                self.logger.info("Telegram发送器初始化完成")
            else:
                self.logger.warning("Telegram配置不完整，将跳过报告发送")
            
            # 初始化Telegram命令处理器（如果配置启用）
            telegram_command_config = self._get_telegram_command_config()
            if telegram_command_config.enabled and auth_config.TELEGRAM_BOT_TOKEN:
                try:
                    from .reporters.telegram_command_handler import TelegramCommandHandlerSync
                    self.command_handler = TelegramCommandHandlerSync(
                        bot_token=auth_config.TELEGRAM_BOT_TOKEN,
                        execution_coordinator=self,
                        config=telegram_command_config,
                        market_snapshot_service=self.market_snapshot_service
                    )
                    self.logger.info("Telegram命令处理器初始化完成")
                except Exception as e:
                    self.logger.error(f"Telegram命令处理器初始化失败: {str(e)}")
                    self.logger.debug(traceback.format_exc())
                    # 不设置command_handler，让它保持为None
            else:
                if not telegram_command_config.enabled:
                    self.logger.info("Telegram命令功能未启用（telegram_commands.enabled=false）")
                elif not auth_config.TELEGRAM_BOT_TOKEN:
                    self.logger.warning("Telegram Bot Token未配置，无法启用命令功能")
            
            self._initialized = True
            self.logger.info("系统组件初始化完成")
            return True
            
        except Exception as e:
            self.logger.error(f"系统初始化失败: {str(e)}")
            self.logger.debug(traceback.format_exc())
            return False

    def initialize_ingestion_system(self) -> bool:
        try:
            self.logger.info("开始初始化摄取服务组件（ingestion-only）")
            self._initialize_core_system_components()

            self.llm_analyzer = None
            self.report_generator = None
            self.telegram_sender = None
            self.command_handler = None
            self.market_snapshot_service = None

            self._initialized = True
            self.logger.info("摄取服务组件初始化完成（ingestion-only）")
            return True
        except Exception as e:
            self.logger.error(f"摄取服务初始化失败: {str(e)}")
            self.logger.debug(traceback.format_exc())
            return False

    def _initialize_core_system_components(self) -> Dict[str, Any]:
        # 初始化配置管理器
        self.config_manager = ConfigManager(self.config_path)
        config_data = self.config_manager.load_config()
        self.logger.info("配置管理器初始化完成")

        # 初始化数据管理器
        storage_config = self.config_manager.get_storage_config()
        self.storage_config = storage_config  # 保存为实例变量供后续使用
        self.data_manager = DataManager(storage_config)
        self.logger.info("数据管理器初始化完成")

        # 初始化缓存管理器
        from .storage.cache_manager import SentMessageCacheManager

        self.cache_manager = SentMessageCacheManager(storage_config)
        self.logger.info("缓存管理器初始化完成")

        # 初始化Repository（存储边界提取，Task 4）
        from .storage.repositories import RepositoryFactory

        self._repositories = RepositoryFactory.create_repositories(
            storage_config,
            data_manager=self.data_manager,
            cache_manager=self.cache_manager,
        )
        self.analysis_repository = self._repositories["analysis"]
        self.datasource_repository = self._repositories["datasource"]
        self.ingestion_repository = self._repositories["ingestion"]
        self.content_repository = self._repositories["content"]
        self.cache_repository = self._repositories["cache"]
        self.logger.info("Repository初始化完成（存储边界已提取）")

        self._bootstrap_datasources_from_config_if_empty()
        self.config_manager.set_datasource_repository(self.datasource_repository)
        self.logger.info("运行时数据源已切换为仓储读取")

        # 清理过期缓存（需求17.12: 系统启动时调用cleanup_expired_cache）
        try:
            if self.cache_repository is None:
                raise ValueError("缓存仓储未初始化")
            expired_count = self.cache_repository.cleanup_expired(
                datetime.utcnow() - timedelta(hours=24)
            )
            self.logger.info(f"清理了 {expired_count} 条过期缓存记录")
        except Exception as e:
            self.logger.warning(f"清理过期缓存失败: {str(e)}")

        # 初始化错误恢复管理器
        self.error_manager = ErrorRecoveryManager()
        self.logger.info("错误恢复管理器初始化完成")

        # 内置数据源已在模块导入时自动注册（见 crawlers/__init__.py）
        return config_data

    def _bootstrap_datasources_from_config_if_empty(self) -> None:
        if self.data_manager is None:
            raise ValueError("数据管理器未初始化")

        config_rows_by_type = {
            "rss": self.config_manager.config_data.get("rss_sources", []),
            "x": self.config_manager.config_data.get("x_sources", []),
            "rest_api": self.config_manager.config_data.get("rest_api_sources", []),
        }

        datasource_rows: List[DataSource] = []
        for source_type, rows in config_rows_by_type.items():
            for row in rows:
                datasource_rows.append(
                    DataSource.create(
                        name=row["name"],
                        source_type=source_type,
                        config_payload=dict(row),
                    )
                )

        inserted = self.data_manager.bootstrap_datasources_if_empty(datasource_rows)
        if inserted:
            self.logger.info(f"数据源启动导入完成，导入 {len(datasource_rows)} 条配置数据")
        else:
            self.logger.info("数据源存储非空，跳过启动导入")
    
    def _get_telegram_command_config(self) -> TelegramCommandConfig:
        """
        获取Telegram命令配置
        
        Returns:
            TelegramCommandConfig对象
        """
        config_data = self.config_manager.config_data
        telegram_commands = config_data.get("telegram_commands", {})
        
        return TelegramCommandConfig(
            enabled=telegram_commands.get("enabled", False),
            authorized_users=telegram_commands.get("authorized_users", []),
            execution_timeout_minutes=telegram_commands.get("execution_timeout_minutes", 30),
            max_concurrent_executions=telegram_commands.get("max_concurrent_executions", 1),
            command_rate_limit=telegram_commands.get("command_rate_limit", {
                "max_commands_per_hour": 10,
                "cooldown_minutes": 5
            })
        )
    
    def validate_prerequisites(self, validation_scope: Optional[str] = None) -> Dict[str, Any]:
        """
        验证系统运行前提条件
        
        需求9.12: 添加容器启动时的配置验证和快速失败机制
        需求9.15: 容器环境配置无效时快速失败并提供明确的错误信息
        
        Returns:
            验证结果字典
        """
        normalized_scope = (validation_scope or os.environ.get("CRYPTO_NEWS_RUNTIME_MODE", "")).strip().lower()
        skip_analysis_auth_validation = normalized_scope == "ingestion"

        validation_result = {
            "valid": True,
            "errors": [],
            "warnings": []
        }
        
        try:
            # 验证配置文件
            if not os.path.exists(self.config_path):
                validation_result["errors"].append(f"配置文件不存在: {self.config_path}")
                validation_result["valid"] = False
                return validation_result
            
            # 验证配置内容
            if not self.config_manager:
                self.config_manager = ConfigManager(self.config_path)
            
            config_data = self.config_manager.load_config()
            
            # 验证必需的配置项（execution_interval和time_window_hours现在从环境变量读取）
            required_configs = ["storage", "llm_config"]
            for config_key in required_configs:
                if config_key not in config_data:
                    validation_result["errors"].append(f"缺少必需配置项: {config_key}")
                    validation_result["valid"] = False
            
            try:
                execution_interval = self.config_manager.get_execution_interval()
                time_window_hours = self.config_manager.get_time_window_hours()
                if execution_interval <= 0 or time_window_hours <= 0:
                    validation_result["errors"].append("execution_interval和time_window_hours必须为正整数")
                    validation_result["valid"] = False
            except Exception as e:
                validation_result["errors"].append(f"无法获取execution_interval或time_window_hours: {e}")
                validation_result["valid"] = False
            
            # 验证认证配置
            if not skip_analysis_auth_validation:
                auth_config = self.config_manager.get_auth_config()
                try:
                    llm_config = validate_llm_config_payload(config_data.get("llm_config", {}))
                    self._validate_runtime_auth(auth_config, llm_config, mode=normalized_scope or "analysis-service")
                except Exception as e:
                    validation_result["errors"].append(str(e))
                    validation_result["valid"] = False

                if (
                    (normalized_scope or "analysis-service") == "analysis-service"
                    and (not auth_config.TELEGRAM_BOT_TOKEN or not auth_config.TELEGRAM_CHANNEL_ID)
                ):
                    validation_result["warnings"].append("Telegram配置不完整，将跳过报告发送")
            
            # 验证数据源配置
            rss_sources = self.config_manager.get_rss_sources()
            x_sources = self.config_manager.get_x_sources()
            
            if not rss_sources and not x_sources:
                validation_result["warnings"].append("未配置任何数据源")
            
            # 验证存储路径
            storage_config = self.config_manager.get_storage_config()
            if storage_config.backend == "sqlite" and not self.config_manager.validate_storage_path(storage_config.database_path):
                validation_result["errors"].append(f"存储路径无效: {storage_config.database_path}")
                validation_result["valid"] = False
            
            # 验证必要目录的写权限
            required_dirs = ["./data", "./logs"]
            for dir_path in required_dirs:
                if not os.path.exists(dir_path):
                    try:
                        os.makedirs(dir_path, exist_ok=True)
                        self.logger.info(f"创建目录: {dir_path}")
                    except Exception as e:
                        validation_result["errors"].append(f"无法创建目录 {dir_path}: {str(e)}")
                        validation_result["valid"] = False
                elif not os.access(dir_path, os.W_OK):
                    validation_result["errors"].append(f"目录不可写: {dir_path}")
                    validation_result["valid"] = False
            
            self.logger.info(f"前提条件验证完成: {'通过' if validation_result['valid'] else '失败'}")
            
            # 如果验证失败，记录详细错误信息
            if not validation_result["valid"]:
                self.logger.error("配置验证失败，详细错误:")
                for error in validation_result["errors"]:
                    self.logger.error(f"  - {error}")
            
            # 记录警告信息
            if validation_result["warnings"]:
                self.logger.warning("配置验证警告:")
                for warning in validation_result["warnings"]:
                    self.logger.warning(f"  - {warning}")
            
        except Exception as e:
            validation_result["errors"].append(f"验证过程中发生异常: {str(e)}")
            validation_result["valid"] = False
            self.logger.error(f"前提条件验证异常: {str(e)}")
            self.logger.debug(traceback.format_exc())
        
        return validation_result

    def _required_llm_provider_env_vars(self, llm_config: Any) -> List[str]:
        providers = {
            llm_config.model.provider,
            llm_config.market_model.provider,
            *(model.provider for model in llm_config.fallback_models),
        }
        return sorted({get_provider_record(provider).env_var for provider in providers})

    def _resolve_provider_credentials(self, auth_config: Any, llm_config: Any) -> Dict[str, str]:
        credentials: Dict[str, str] = {}
        for env_var in self._required_llm_provider_env_vars(llm_config):
            provider_record = get_provider_record(env_var.removesuffix("_API_KEY").lower())
            credentials[provider_record.name] = getattr(auth_config, env_var, "").strip()
        return credentials

    def _validate_runtime_auth(self, auth_config: Any, llm_config: Any, mode: str) -> None:
        auth_config.validate(
            mode=mode,
            required_provider_env_vars=self._required_llm_provider_env_vars(llm_config),
        )
    
    def run_once(self, trigger_type: str = "manual", trigger_user: Optional[str] = None, trigger_chat_id: Optional[str] = None) -> ExecutionResult:
        """
        执行一次完整的工作流
        
        需求16.6: 支持手动触发执行
        需求16.14: 为手动触发的执行设置超时限制
        
        Args:
            trigger_type: 触发类型 ("manual", "scheduled", "startup")
            trigger_user: 触发用户ID（手动触发时）
            trigger_chat_id: 触发命令的聊天ID（用于发送报告）
        
        Returns:
            执行结果
        """
        execution_id = f"exec_{int(time.time())}"
        start_time = datetime.now()
        
        # 创建执行信息
        execution_info = ExecutionInfo(
            execution_id=execution_id,
            trigger_type=trigger_type,
            trigger_user=trigger_user,
            start_time=start_time,
            end_time=None,
            status=ExecutionStatus.RUNNING,
            progress=0.0,
            current_stage="initializing",
            error_message=None
        )
        
        with self._execution_lock:
            self.current_execution = execution_info
        
        try:
            self.logger.info(f"开始执行工作流 {execution_id}")
            
            # 验证前提条件
            validation_result = self.validate_prerequisites(validation_scope="analysis-service")
            if not validation_result["valid"]:
                raise Exception(f"前提条件验证失败: {validation_result['errors']}")
            
            # 初始化系统（如果尚未初始化）
            if not self._initialized:
                if not self.initialize_system():
                    raise Exception("系统初始化失败")
            
            # 执行完整工作流
            result = self.coordinate_workflow(trigger_chat_id=trigger_chat_id, is_manual=(trigger_type == "manual"))
            
            # 更新执行状态
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            execution_result = ExecutionResult(
                execution_id=execution_id,
                success=result["success"],
                start_time=start_time,
                end_time=end_time,
                duration_seconds=duration,
                items_processed=result.get("items_processed", 0),
                categories_found=result.get("categories_found", {}),
                errors=result.get("errors", []),
                trigger_user=trigger_user,
                trigger_type=trigger_type,
                trigger_chat_id=trigger_chat_id,
                report_sent=result.get("report_sent", False)
            )
            
            # 更新执行信息
            with self._execution_lock:
                if self.current_execution:
                    self.current_execution.end_time = end_time
                    self.current_execution.status = ExecutionStatus.COMPLETED if result["success"] else ExecutionStatus.FAILED
                    self.current_execution.progress = 1.0
                    self.current_execution.current_stage = "completed"
                    if not result["success"]:
                        self.current_execution.error_message = "; ".join(result.get("errors", []))
            
            # 记录执行历史
            self.execution_history.append(execution_result)
            self._save_execution_history()
            
            # 记录执行日志
            self.log_execution_cycle(start_time, end_time, "success" if result["success"] else "failed")
            
            self.logger.info(f"工作流执行完成 {execution_id}: {'成功' if result['success'] else '失败'}")
            return execution_result
            
        except Exception as e:
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            error_msg = str(e)
            self.logger.error(f"工作流执行失败 {execution_id}: {error_msg}")
            self.logger.debug(traceback.format_exc())
            
            # 更新执行状态
            with self._execution_lock:
                if self.current_execution:
                    self.current_execution.end_time = end_time
                    self.current_execution.status = ExecutionStatus.FAILED
                    self.current_execution.error_message = error_msg
            
            execution_result = ExecutionResult(
                execution_id=execution_id,
                success=False,
                start_time=start_time,
                end_time=end_time,
                duration_seconds=duration,
                items_processed=0,
                categories_found={},
                errors=[error_msg],
                trigger_user=trigger_user,
                trigger_type=trigger_type,
                trigger_chat_id=trigger_chat_id,
                report_sent=False
            )
            
            # 记录执行历史
            self.execution_history.append(execution_result)
            self._save_execution_history()
            
            # 记录执行日志
            self.log_execution_cycle(start_time, end_time, "failed")
            
            return execution_result
        
        finally:
            # 清理当前执行状态
            with self._execution_lock:
                self.current_execution = None
    
    def coordinate_workflow(self, trigger_chat_id: Optional[str] = None, is_manual: bool = False) -> Dict[str, Any]:
        """
        协调完整的工作流程
        
        Args:
            trigger_chat_id: 触发命令的聊天ID（用于发送报告）
            is_manual: 是否为手动触发（手动触发时不缓存消息）
        
        Returns:
            工作流执行结果
        """
        result = {
            "success": False,
            "items_processed": 0,
            "categories_found": {},
            "errors": [],
            "report_sent": False
        }
        
        try:
            # 使用配置管理器的getter方法获取时间窗口
            time_window_hours = self.config_manager.get_time_window_hours()
            
            # 阶段1: 数据爬取
            self._update_execution_progress(0.1, "crawling")
            self.logger.info("开始数据爬取阶段")
            
            crawl_result = self._execute_crawling_stage(time_window_hours)
            if not crawl_result["success"]:
                result["errors"].extend(crawl_result["errors"])
                return result
            
            content_items = crawl_result["content_items"]
            crawl_status = crawl_result["crawl_status"]
            
            self.logger.info(f"数据爬取完成，获取到 {len(content_items)} 个内容项")
            
            # 阶段2: 内容分析
            self._update_execution_progress(0.4, "analyzing")
            self.logger.info("开始内容分析阶段")
            
            analysis_result = self._execute_analysis_stage(content_items, is_manual=is_manual)
            if not analysis_result["success"]:
                result["errors"].extend(analysis_result["errors"])
                return result
            
            categorized_items = analysis_result["categorized_items"]
            analysis_results = analysis_result["analysis_results"]
            
            self.logger.info(f"内容分析完成，分类结果: {len(categorized_items)} 个类别")
            
            # 阶段3: 报告生成
            self._update_execution_progress(0.7, "reporting")
            self.logger.info("开始报告生成阶段")
            
            report_result = self._execute_reporting_stage(categorized_items, analysis_results, crawl_status, time_window_hours)
            if not report_result["success"]:
                result["errors"].extend(report_result["errors"])
                return result
            
            report_content = report_result["report_content"]
            
            # 阶段4: 报告发送
            self._update_execution_progress(0.9, "sending")
            self.logger.info("开始报告发送阶段")
            
            send_result = self._execute_sending_stage(
                report_content, 
                target_chat_id=trigger_chat_id,
                categorized_items=categorized_items,
                should_cache=not is_manual  # 手动触发时不缓存
            )
            
            # 更新结果
            result.update({
                "success": True,
                "items_processed": len(content_items),
                "categories_found": {cat: len(items) for cat, items in categorized_items.items()},
                "report_sent": send_result["success"]
            })
            
            if not send_result["success"]:
                result["errors"].extend(send_result["errors"])
            
            self._update_execution_progress(1.0, "completed")
            self.logger.info("工作流程执行完成")
            
        except Exception as e:
            error_msg = f"工作流程执行异常: {str(e)}"
            self.logger.error(error_msg)
            result["errors"].append(error_msg)
        
        return result
    
    def _execute_crawling_stage(self, time_window_hours: int) -> Dict[str, Any]:
        """执行数据爬取阶段"""
        result = {
            "success": False,
            "content_items": [],
            "crawl_status": None,
            "items_new": 0,
            "errors": [],
        }
        
        try:
            factory = get_data_source_factory()
            all_content_items = []
            rss_results = []
            x_results = []
            
            # 爬取RSS源
            rss_sources = self.config_manager.get_rss_sources()
            for rss_source in rss_sources:
                try:
                    crawler = factory.create_source("rss", time_window_hours)
                    items = crawler.crawl(rss_source.to_dict())
                    all_content_items.extend(items)
                    
                    rss_results.append(CrawlResult(
                        source_name=rss_source.name,
                        status="success",
                        item_count=len(items),
                        error_message=None
                    ))
                    
                except Exception as e:
                    error_msg = f"RSS源 {rss_source.name} 爬取失败: {str(e)}"
                    self.logger.warning(error_msg)
                    rss_results.append(CrawlResult(
                        source_name=rss_source.name,
                        status="error",
                        item_count=0,
                        error_message=str(e)
                    ))
            
            # 爬取X源
            x_sources = self.config_manager.get_x_sources()
            x_auth = self.config_manager.get_x_auth_credentials()

            if x_sources and x_auth["X_CT0"] and x_auth["X_AUTH_TOKEN"]:
                bird_config = self.config_manager.get_bird_config()
                
                for x_source in x_sources:
                    try:
                        crawler = factory.create_source("x", time_window_hours, bird_config=bird_config, data_manager=self.data_manager)
                        items = crawler.crawl(x_source.to_dict())
                        all_content_items.extend(items)
                        
                        x_results.append(CrawlResult(
                            source_name=x_source.name,
                            status="success",
                            item_count=len(items),
                            error_message=None
                        ))
                        
                    except Exception as e:
                        error_msg = f"X源 {x_source.name} 爬取失败: {str(e)}"
                        self.logger.warning(error_msg)
                        x_results.append(CrawlResult(
                            source_name=x_source.name,
                            status="error",
                            item_count=0,
                            error_message=str(e)
                        ))

            rest_api_sources = self.config_manager.get_rest_api_sources()
            for rest_api_source in rest_api_sources:
                try:
                    crawler = factory.create_source("rest_api", time_window_hours)
                    items = crawler.crawl(rest_api_source.to_dict())
                    all_content_items.extend(items)
                except Exception as e:
                    error_msg = f"REST API源 {rest_api_source.name} 爬取失败: {str(e)}"
                    self.logger.warning(error_msg)

            # 数据去重和存储
            added_count = 0
            if all_content_items:
                if self.content_repository is None:
                    raise ValueError("内容仓储未初始化")
                added_count = self.content_repository.save_many(all_content_items)
                self.content_repository.deduplicate()
                self.logger.info(f"成功存储 {added_count} 个内容项")
            
            # 创建爬取状态
            crawl_status = CrawlStatus(
                rss_results=rss_results,
                x_results=x_results,
                total_items=len(all_content_items),
                execution_time=datetime.now()
            )
            
            # 保存爬取状态
            if self.content_repository is None:
                raise ValueError("内容仓储未初始化")
            self.content_repository.save_crawl_status(crawl_status)
            
            result.update({
                "success": True,
                "content_items": all_content_items,
                "crawl_status": crawl_status,
                "items_new": added_count,
            })
            
        except Exception as e:
            error_msg = f"数据爬取阶段失败: {str(e)}"
            self.logger.error(error_msg)
            result["errors"].append(error_msg)
        
        return result
    
    def _execute_analysis_stage(
        self,
        newly_crawled_items: List[ContentItem],
        is_manual: bool = False,
        analysis_time_window_hours: Optional[int] = None,
        preloaded_content_items: Optional[List[ContentItem]] = None,
        manual_historical_titles: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        执行内容分析阶段
        
        重要: 由于RSS数据源和bird爬取都有时间/页数限制，本方法从本地数据库中
        获取时间窗口内的所有消息进行分析，而不仅仅使用刚爬取的消息。
        
        Args:
            newly_crawled_items: 刚爬取的内容项（用于日志记录）
            is_manual: 是否为手动触发（手动触发时不包含 Outdated News）
            analysis_time_window_hours: 分析时间窗口（小时），传入时优先于配置
            preloaded_content_items: 预加载的待分析内容项（传入时不再重新查询数据库）
            
        Returns:
            分析结果字典
        """
        result = {"success": False, "categorized_items": {}, "analysis_results": {}, "errors": []}
        
        try:
            if preloaded_content_items is not None:
                all_content_items = preloaded_content_items
                self.logger.info(f"使用预加载内容项进行分析，共 {len(all_content_items)} 个")
            else:
                time_window_hours = (
                    analysis_time_window_hours
                    if analysis_time_window_hours is not None
                    else self.config_manager.get_time_window_hours()
                )

                # 获取时间窗口内的所有内容项（包括之前爬取的和刚爬取的）
                if self.content_repository is None:
                    raise ValueError("内容仓储未初始化")
                all_content_items = self.content_repository.get_recent_content_items(
                    time_window_hours=time_window_hours
                )
            
            self.logger.info(f"从数据库获取到时间窗口内的 {len(all_content_items)} 个内容项进行分析")
            self.logger.info(f"其中本次新爬取 {len(newly_crawled_items)} 个，历史数据 {len(all_content_items) - len(newly_crawled_items)} 个")
            
            if not all_content_items:
                self.logger.info("没有内容需要分析")
                result["success"] = True
                return result
            
            # 获取最小权重阈值配置
            llm_config = self.config_manager.config_data.get("llm_config", {})
            min_weight_score = llm_config.get("min_weight_score", 50)
            
            # 批量分析内容（仅在定时任务时包含 Outdated News）
            is_scheduled = not is_manual
            analyzer_kwargs: Dict[str, Any] = {"is_scheduled": is_scheduled}
            if is_manual:
                analyzer_kwargs["historical_titles"] = list(manual_historical_titles or [])

            analysis_results = self.llm_analyzer.analyze_content_batch(
                all_content_items,
                **analyzer_kwargs,
            )
            
            # 分类内容 - 注意这里存储的是 StructuredAnalysisResult 而不是 ContentItem
            categorized_items = {}
            analysis_dict = {}
            
            for item, analysis in zip(all_content_items, analysis_results):
                # 跳过低权重的内容
                if analysis.weight_score < min_weight_score:
                    continue
                
                category = analysis.category
                
                if category not in categorized_items:
                    categorized_items[category] = []
                
                # 存储 StructuredAnalysisResult 而不是 ContentItem
                categorized_items[category].append(analysis)
                analysis_dict[item.id] = analysis
            
            result.update({
                "success": True,
                "categorized_items": categorized_items,
                "analysis_results": analysis_dict
            })
            
        except Exception as e:
            error_msg = f"内容分析阶段失败: {str(e)}"
            self.logger.error(error_msg)
            result["errors"].append(error_msg)
        
        return result
    
    def _execute_reporting_stage(self, categorized_items: Dict[str, List[ContentItem]], 
                                analysis_results: Dict[str, AnalysisResult], 
                                crawl_status: CrawlStatus, 
                                time_window_hours: int) -> Dict[str, Any]:
        """执行报告生成阶段"""
        result = {"success": False, "report_content": "", "errors": []}
        
        try:
            # 获取模型信息
            model_info = self.llm_analyzer.get_model_info() if self.llm_analyzer else None
            
            # 创建分析数据对象
            analyzed_data = create_analyzed_data(
                categorized_items=categorized_items,
                analysis_results=analysis_results,
                time_window_hours=time_window_hours,
                model_info=model_info
            )
            
            # 生成报告
            report_content = self.report_generator.generate_telegram_report(
                analyzed_data, 
                crawl_status
            )
            
            result.update({
                "success": True,
                "report_content": report_content
            })
            
        except Exception as e:
            error_msg = f"报告生成阶段失败: {str(e)}"
            self.logger.error(error_msg)
            result["errors"].append(error_msg)
        
        return result
    
    def _execute_sending_stage(self, report_content: str, target_chat_id: Optional[str] = None, 
                              categorized_items: Optional[Dict[str, List[Any]]] = None,
                              should_cache: bool = True) -> Dict[str, Any]:
        """
        执行报告发送阶段
        
        需求17.9: 报告发送成功后调用cache_sent_messages
        
        Args:
            report_content: 报告内容
            target_chat_id: 目标聊天ID（如果提供，发送到该聊天；否则发送到TELEGRAM_CHANNEL_ID）
            categorized_items: 分类后的内容项（用于缓存）
            should_cache: 是否缓存已发送消息（手动触发时为False，定时任务为True）
        
        Returns:
            发送结果字典
        """
        result = {"success": False, "errors": []}
        
        try:
            if not self.telegram_sender:
                self.logger.warning("Telegram发送器未配置，跳过报告发送")
                # 保存本地备份
                backup_path = self._save_report_backup(report_content)
                self.logger.info(f"报告已保存到本地: {backup_path}")
                result["success"] = True
                return result
            
            # 确定发送目标
            if target_chat_id:
                # 用户触发的报告，发送到触发命令的聊天窗口
                self.logger.info(f"发送报告到用户触发的聊天窗口: {target_chat_id}")
                send_result = self.telegram_sender.send_report_to_chat(report_content, target_chat_id)
            else:
                # 定时任务报告，发送到配置的频道
                self.logger.info(f"发送报告到配置的频道: {self.telegram_sender.config.channel_id}")
                send_result = self.telegram_sender.send_report(report_content)
            
            if send_result.success:
                self.logger.info(f"报告发送成功，消息ID: {send_result.message_id}")
                result["success"] = True
                
                # 需求17.9: 报告发送成功后缓存已发送的消息
                # 手动触发时不缓存，避免影响定时任务的去重逻辑
                if should_cache and self.cache_repository and categorized_items:
                    try:
                        messages_to_cache = []
                        for category, items in categorized_items.items():
                            for item in items:
                                # item 是 StructuredAnalysisResult 对象
                                messages_to_cache.append({
                                    "title": item.title,
                                    "body": item.body,
                                    "category": item.category,
                                    "time": item.time,
                                    "sent_at": datetime.now().isoformat()
                                })
                        
                        if messages_to_cache:
                            cached_count = self.cache_repository.cache_sent_messages(messages_to_cache)
                            self.logger.info(f"成功缓存 {cached_count} 条已发送消息")
                            
                            # 需求17.14: 实现缓存统计和监控
                            cache_stats = self.cache_repository.get_cache_statistics()
                            self.logger.info(f"缓存统计: {cache_stats}")
                    except Exception as cache_error:
                        # 需求17.15: 缓存失败不影响主流程
                        self.logger.warning(f"缓存已发送消息失败: {str(cache_error)}")
                elif not should_cache:
                    self.logger.info("手动触发执行，跳过消息缓存以避免影响定时任务去重")
            else:
                error_msg = f"报告发送失败: {send_result.error_message}"
                self.logger.error(error_msg)
                result["errors"].append(error_msg)
                
                # 保存本地备份
                backup_path = self._save_report_backup(report_content)
                self.logger.info(f"报告已保存到本地备份: {backup_path}")
            
        except Exception as e:
            error_msg = f"报告发送阶段失败: {str(e)}"
            self.logger.error(error_msg)
            result["errors"].append(error_msg)
            
            # 保存本地备份
            try:
                backup_path = self._save_report_backup(report_content)
                self.logger.info(f"报告已保存到本地备份: {backup_path}")
            except Exception as backup_error:
                self.logger.error(f"保存本地备份失败: {str(backup_error)}")
        
        return result
    
    def _save_report_backup(self, report_content: str) -> str:
        """保存报告备份"""
        import os
        from datetime import datetime
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"crypto_news_report_{timestamp}.md"
        
        # 确保备份目录存在
        backup_dir = "logs"
        os.makedirs(backup_dir, exist_ok=True)
        
        backup_path = os.path.join(backup_dir, filename)
        
        with open(backup_path, 'w', encoding='utf-8') as f:
            f.write(report_content)
        
        return backup_path
    
    def _update_execution_progress(self, progress: float, stage: str) -> None:
        """更新执行进度"""
        with self._execution_lock:
            if self.current_execution:
                self.current_execution.progress = progress
                self.current_execution.current_stage = stage
    
    def start_scheduler(self, interval_seconds: Optional[int] = None) -> None:
        """
        启动定时调度器
        
        Args:
            interval_seconds: 调度间隔（秒），如果为None则从配置文件读取
        """
        if self._scheduler_thread and self._scheduler_thread.is_alive():
            self.logger.warning("调度器已在运行")
            return
        
        # 获取调度间隔
        if interval_seconds is None:
            # 使用配置管理器的getter方法（优先从环境变量读取）
            interval_seconds = self.config_manager.get_execution_interval()
        
        self.logger.info(f"启动定时调度器，间隔: {interval_seconds} 秒")
        
        # 重置停止事件
        self._stop_event.clear()
        
        # 启动调度器线程
        self._scheduler_thread = threading.Thread(
            target=self._scheduler_loop,
            args=(interval_seconds,),
            daemon=True
        )
        self._scheduler_thread.start()
    
    def _scheduler_loop(self, interval_seconds: int) -> None:
        """
        调度器循环
        
        需求9.18: 定时任务执行失败时的错误处理和重试机制
        需求9.20: 定时任务执行失败时记录错误信息并在下个调度周期继续尝试
        """
        self.logger.info("调度器循环开始")
        
        # 尝试从执行历史中恢复上次调度时间（避免重新部署后时间重置）
        if not self._last_scheduled_time and self.execution_history:
            # 查找最近一次scheduled类型的执行
            for result in reversed(self.execution_history):
                if result.trigger_type == "scheduled":
                    self._last_scheduled_time = result.start_time
                    self.logger.info(f"从执行历史恢复上次调度时间: {self._last_scheduled_time.strftime('%Y-%m-%d %H:%M:%S')}")
                    break
        
        # 如果仍然没有上次调度时间，初始化为当前时间
        if not self._last_scheduled_time:
            self._last_scheduled_time = datetime.now()
            self.logger.info(f"初始化上次调度时间为当前时间: {self._last_scheduled_time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        consecutive_failures = 0
        max_consecutive_failures = 3
        
        while not self._stop_event.is_set():
            try:
                # 计算下次执行时间（基于上次调度时间 + 间隔）
                next_execution = self._last_scheduled_time + timedelta(seconds=interval_seconds)
                
                # 计算需要等待的时间
                now = datetime.now()
                wait_seconds = (next_execution - now).total_seconds()
                
                # 如果下次执行时间已经过了，立即执行
                if wait_seconds <= 0:
                    self.logger.info(f"下次执行时间 {next_execution.strftime('%Y-%m-%d %H:%M:%S')} 已过，立即执行")
                    wait_seconds = 0
                else:
                    self.logger.info(f"下次执行时间: {next_execution.strftime('%Y-%m-%d %H:%M:%S')}，等待 {wait_seconds:.0f} 秒")
                
                # 等待到下次执行时间或停止信号
                if wait_seconds > 0 and self._stop_event.wait(wait_seconds):
                    break  # 收到停止信号
                
                # 检查是否有其他执行正在进行
                with self._execution_lock:
                    if self.current_execution and self.current_execution.status == ExecutionStatus.RUNNING:
                        self.logger.warning("上次执行仍在进行中，跳过本次调度")
                        continue
                
                # 执行工作流
                self.logger.info("定时调度触发执行")
                result = self.run_crawl_only()
                
                # 更新上次调度时间为本次调度的理论时间（而不是实际执行时间）
                # 这样可以避免执行耗时影响下次调度时间
                self._last_scheduled_time = next_execution
                
                if result.success:
                    self.logger.info(f"定时执行成功，处理了 {result.items_processed} 个项目")
                    consecutive_failures = 0  # 重置连续失败计数
                else:
                    consecutive_failures += 1
                    self.logger.error(f"定时执行失败 (连续失败: {consecutive_failures}/{max_consecutive_failures}): {'; '.join(result.errors)}")
                    
                    # 如果连续失败次数过多，增加等待时间
                    if consecutive_failures >= max_consecutive_failures:
                        backoff_time = min(300, 60 * consecutive_failures)  # 最多等待5分钟
                        self.logger.warning(f"连续失败{consecutive_failures}次，等待{backoff_time}秒后继续")
                        if self._stop_event.wait(backoff_time):
                            break
                
            except Exception as e:
                consecutive_failures += 1
                self.logger.error(f"调度器循环异常 (连续失败: {consecutive_failures}/{max_consecutive_failures}): {str(e)}")
                self.logger.debug(traceback.format_exc())
                
                # 如果连续失败次数过多，增加等待时间
                if consecutive_failures >= max_consecutive_failures:
                    backoff_time = min(300, 60 * consecutive_failures)
                    self.logger.warning(f"连续异常{consecutive_failures}次，等待{backoff_time}秒后继续")
                    if self._stop_event.wait(backoff_time):
                        break
                else:
                    # 等待一段时间后继续
                    if self._stop_event.wait(60):  # 等待1分钟
                        break
        
        self.logger.info("调度器循环结束")
    
    def stop_scheduler(self) -> None:
        """停止定时调度器"""
        self.logger.info("停止定时调度器")
        self._stop_event.set()
        
        if self._scheduler_thread and self._scheduler_thread.is_alive():
            self._scheduler_thread.join(timeout=10)
            if self._scheduler_thread.is_alive():
                self.logger.warning("调度器线程未能在超时时间内停止")
    
    def get_execution_status(self) -> Optional[ExecutionInfo]:
        """获取当前执行状态"""
        with self._execution_lock:
            return self.current_execution
    
    def get_execution_history(self, limit: int = 10) -> List[ExecutionResult]:
        """获取执行历史"""
        return self.execution_history[-limit:] if limit > 0 else self.execution_history
    def _load_execution_history(self) -> None:
        """从文件加载执行历史"""
        try:
            import os
            if os.path.exists(self._history_file):
                with open(self._history_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.execution_history = [ExecutionResult.from_dict(item) for item in data]
                    self.logger.info(f"已加载 {len(self.execution_history)} 条执行历史记录")
            else:
                self.logger.info("执行历史文件不存在，从空历史开始")
        except Exception as e:
            self.logger.error(f"加载执行历史失败: {e}")
            self.execution_history = []

    def _save_execution_history(self) -> None:
        """保存执行历史到文件（保留最近100条）"""
        try:
            import os
            os.makedirs(os.path.dirname(self._history_file), exist_ok=True)

            # 只保留最近100条记录
            history_to_save = self.execution_history[-100:]
            data = [item.to_dict() for item in history_to_save]

            with open(self._history_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            self.logger.debug(f"已保存 {len(history_to_save)} 条执行历史记录")
        except Exception as e:
            self.logger.error(f"保存执行历史失败: {e}")

    
    def is_execution_running(self) -> bool:
        """检查是否有执行正在进行"""
        with self._execution_lock:
            return (self.current_execution is not None and 
                   self.current_execution.status == ExecutionStatus.RUNNING)
    
    def get_next_execution_time(self) -> Optional[datetime]:
        """获取下次执行时间"""
        if not self._scheduler_thread or not self._scheduler_thread.is_alive():
            return None
        
        # 从配置获取间隔（使用配置管理器的getter方法）
        interval_seconds = self.config_manager.get_execution_interval()
        
        # 如果有上次调度时间，使用它来计算下次执行时间
        if self._last_scheduled_time:
            return self._last_scheduled_time + timedelta(seconds=interval_seconds)
        
        # 如果没有上次调度时间，使用当前时间估算
        return datetime.now() + timedelta(seconds=interval_seconds)
    
    def log_execution_cycle(self, start_time: datetime, end_time: datetime, status: str) -> None:
        """
        记录执行周期日志
        
        需求9.17: 记录每次执行的开始时间、结束时间和执行状态
        需求9.16: 配置容器日志标准输出
        """
        duration = (end_time - start_time).total_seconds()
        
        log_entry = {
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration_seconds": duration,
            "status": status,
            "timestamp": datetime.now().isoformat()
        }
        
        # 输出到标准输出（容器日志）
        self.logger.info(f"执行周期记录: {json.dumps(log_entry, ensure_ascii=False)}")
        
        # 同时输出到标准输出以确保容器日志可见
        print(f"[EXECUTION_CYCLE] {json.dumps(log_entry, ensure_ascii=False)}", flush=True)
    
    def cleanup_resources(self) -> None:
        """清理资源"""
        self.logger.info("开始清理资源")
        
        try:
            # 停止调度器
            self.stop_scheduler()
            
            # 清理数据管理器
            if self.data_manager:
                self.data_manager.close()
            
            # 清理缓存管理器
            if self.cache_manager:
                self.cache_manager.close()
            
            self.logger.info("资源清理完成")
            
        except Exception as e:
            self.logger.error(f"资源清理失败: {str(e)}")
    
    def _deep_update(self, base_dict: Dict, update_dict: Dict) -> None:
        """深度更新字典"""
        for key, value in update_dict.items():
            if key in base_dict and isinstance(base_dict[key], dict) and isinstance(value, dict):
                self._deep_update(base_dict[key], value)
            else:
                base_dict[key] = value
    
    def get_system_status(self) -> Dict[str, Any]:
        """获取系统状态"""
        from crypto_news_analyzer.utils.timezone_utils import format_datetime_utc8
        
        status = {
            "initialized": self._initialized,
            "scheduler_running": bool(self._scheduler_thread and self._scheduler_thread.is_alive()),
            "current_execution": None,
            "execution_history_count": len(self.execution_history),
            "next_execution_time": None
        }
        
        # 当前执行状态
        current_exec = self.get_execution_status()
        if current_exec:
            status["current_execution"] = {
                "execution_id": current_exec.execution_id,
                "status": current_exec.status.value if hasattr(current_exec.status, 'value') else str(current_exec.status),
                "progress": current_exec.progress,
                "current_stage": current_exec.current_stage,
                "start_time": current_exec.start_time.isoformat()
            }
        
        # 下次执行时间 - 转换为UTC+8格式
        next_time = self.get_next_execution_time()
        if next_time:
            status["next_execution_time"] = format_datetime_utc8(next_time, '%Y-%m-%d %H:%M:%S')
        
        return status
    
    def trigger_manual_execution(self, user_id: str = None, chat_id: str = None) -> ExecutionResult:
        """
        触发手动执行
        
        需求16.6: 实现并发控制，防止多个执行同时进行
        需求16.9: 添加执行超时管理和状态查询功能
        
        Args:
            user_id: 触发用户ID
            chat_id: 触发命令的聊天ID（用于发送报告）
            
        Returns:
            执行结果
        """
        runtime_mode = os.environ.get("CRYPTO_NEWS_RUNTIME_MODE", "").strip().lower()
        if runtime_mode in {"api-only", "analysis-service"}:
            raise RuntimeError(
                "Manual ingestion execution is disabled in analysis-service/api-only runtime; "
                "use /analyze or HTTP /analyze instead"
            )

        # 检查并发限制
        with self._execution_lock:
            if self.current_execution and self.current_execution.status == ExecutionStatus.RUNNING:
                # 返回一个表示拒绝的结果
                return ExecutionResult(
                    execution_id="rejected",
                    success=False,
                    start_time=datetime.now(),
                    end_time=datetime.now(),
                    duration_seconds=0.0,
                    items_processed=0,
                    categories_found={},
                    errors=["系统正在执行任务，请稍后再试"],
                    trigger_user=user_id,
                    trigger_chat_id=chat_id,
                    report_sent=False
                )
        
        # 执行工作流
        return self.run_once(trigger_type="manual", trigger_user=user_id, trigger_chat_id=chat_id)
    
    def get_current_execution_info(self) -> Optional[ExecutionInfo]:
        """
        获取当前执行信息
        
        需求16.9: 添加执行超时管理和状态查询功能
        
        Returns:
            当前执行信息，如果没有则返回None
        """
        with self._execution_lock:
            return self.current_execution
    
    def cancel_current_execution(self) -> bool:
        """
        取消当前执行
        
        Returns:
            是否成功取消
        """
        with self._execution_lock:
            if self.current_execution and self.current_execution.status == ExecutionStatus.RUNNING:
                self.current_execution.status = ExecutionStatus.CANCELLED
                self.logger.info(f"取消执行: {self.current_execution.execution_id}")
                return True
            return False
    
    def set_execution_timeout(self, timeout_minutes: int) -> None:
        """
        设置执行超时时间
        
        需求16.14: 为手动触发的执行设置超时限制
        
        Args:
            timeout_minutes: 超时时间（分钟）
        """
        self._execution_timeout_minutes = timeout_minutes
        self.logger.info(f"执行超时时间设置为: {timeout_minutes} 分钟")
    
    def start_command_listener(self) -> None:
        """
        启动Telegram命令监听器
        
        需求16.1: 支持通过Telegram Bot接收用户命令
        """
        if self.command_handler:
            try:
                self.logger.info("启动Telegram命令监听器")
                self.command_handler.start_command_listener()
            except Exception as e:
                self.logger.error(f"启动命令监听器失败: {str(e)}")
        else:
            self.logger.warning("命令处理器未初始化，无法启动监听器")
    
    def stop_command_listener(self) -> None:
        """停止Telegram命令监听器"""
        if self.command_handler:
            try:
                self.logger.info("停止Telegram命令监听器")
                self.command_handler.stop_command_listener()
            except Exception as e:
                self.logger.error(f"停止命令监听器失败: {str(e)}")


    def run_crawl_only(
        self,
        trigger_type: str = "scheduled",
        trigger_user: Optional[str] = None,
    ) -> ExecutionResult:
        """
        仅执行爬取阶段，不执行分析
        
        Returns:
            执行结果
        """
        execution_id = f"crawl_{int(time.time())}"
        start_time = datetime.now()
        source_type = "scheduler"
        source_name = "crawl_only"
        
        # 创建执行信息
        execution_info = ExecutionInfo(
            execution_id=execution_id,
            trigger_type=trigger_type,
            trigger_user=trigger_user,
            start_time=start_time,
            end_time=None,
            status=ExecutionStatus.RUNNING,
            progress=0.0,
            current_stage="crawling",
            error_message=None
        )
        
        ingestion_job: Optional[IngestionJob] = None
        
        try:
            self.logger.info(f"开始爬取阶段 {execution_id}")
            
            # 验证前提条件
            validation_result = self.validate_prerequisites(validation_scope="ingestion")
            if not validation_result["valid"]:
                raise Exception(f"前提条件验证失败: {validation_result['errors']}")
            
            # 初始化系统（如果尚未初始化）
            if not self._initialized:
                if not self.initialize_system():
                    raise Exception("系统初始化失败")

            if self.ingestion_repository is None:
                raise Exception("IngestionRepository未初始化")

            with self._execution_lock:
                if self.current_execution and self.current_execution.status == ExecutionStatus.RUNNING:
                    skipped_job = IngestionJob.create(source_type=source_type, source_name=source_name)
                    skipped_job.status = IngestionJobStatus.SKIPPED.value
                    skipped_job.error_message = "当前存在内存中的运行任务，跳过重复触发"
                    skipped_job.metadata = {
                        "trigger_type": trigger_type,
                        "skip_reason": "in_memory_running_execution",
                    }
                    self.ingestion_repository.save(skipped_job)

                    end_time = datetime.now()
                    duration = (end_time - start_time).total_seconds()
                    self.logger.info("检测到内存中运行任务，已持久化跳过 ingestion 作业")

                    execution_result = ExecutionResult(
                        execution_id=execution_id,
                        success=True,
                        start_time=start_time,
                        end_time=end_time,
                        duration_seconds=duration,
                        items_processed=0,
                        categories_found={},
                        errors=[],
                        trigger_user=trigger_user,
                        trigger_type=trigger_type,
                        trigger_chat_id=None,
                        report_sent=False,
                    )
                    self.execution_history.append(execution_result)
                    self._save_execution_history()
                    return execution_result

                running_jobs = self.ingestion_repository.get_by_source(
                    source_type=source_type,
                    source_name=source_name,
                    status=IngestionJobStatus.RUNNING.value,
                    limit=1,
                )
                if running_jobs:
                    skipped_job = IngestionJob.create(source_type=source_type, source_name=source_name)
                    skipped_job.status = IngestionJobStatus.SKIPPED.value
                    skipped_job.error_message = "已存在运行中的 ingestion 作业，跳过重复触发"
                    skipped_job.metadata = {
                        "trigger_type": trigger_type,
                        "skip_reason": "persistent_running_job",
                        "active_job_id": running_jobs[0].id,
                    }
                    self.ingestion_repository.save(skipped_job)

                    end_time = datetime.now()
                    duration = (end_time - start_time).total_seconds()
                    self.logger.info(
                        f"检测到运行中的持久化 ingestion 作业，跳过本次触发，active_job_id={running_jobs[0].id}"
                    )

                    execution_result = ExecutionResult(
                        execution_id=execution_id,
                        success=True,
                        start_time=start_time,
                        end_time=end_time,
                        duration_seconds=duration,
                        items_processed=0,
                        categories_found={},
                        errors=[],
                        trigger_user=trigger_user,
                        trigger_type=trigger_type,
                        trigger_chat_id=None,
                        report_sent=False,
                    )
                    self.execution_history.append(execution_result)
                    self._save_execution_history()
                    return execution_result

                ingestion_job = IngestionJob.create(source_type=source_type, source_name=source_name)
                ingestion_job.metadata = {"trigger_type": trigger_type}
                self.ingestion_repository.save(ingestion_job)

                if not self.ingestion_repository.update_status(
                    ingestion_job.id,
                    IngestionJobStatus.RUNNING.value,
                ):
                    raise Exception("无法将 ingestion 作业更新为 running")

                self.current_execution = execution_info

            self.logger.info(f"已创建并启动 ingestion 作业: {ingestion_job.id}")

            # 执行爬取阶段
            time_window_hours = self.config_manager.get_time_window_hours()
            crawl_result = self._execute_crawling_stage(time_window_hours)
            
            # 更新执行状态
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            if crawl_result["success"]:
                # 更新执行信息
                with self._execution_lock:
                    if self.current_execution:
                        self.current_execution.end_time = end_time
                        self.current_execution.status = ExecutionStatus.COMPLETED
                        self.current_execution.progress = 1.0
                        self.current_execution.current_stage = "completed"
                
                execution_result = ExecutionResult(
                    execution_id=execution_id,
                    success=True,
                    start_time=start_time,
                    end_time=end_time,
                    duration_seconds=duration,
                    items_processed=len(crawl_result.get("content_items", [])),
                    categories_found={},
                    errors=[],
                    trigger_user=trigger_user,
                    trigger_type=trigger_type,
                    trigger_chat_id=None,
                    report_sent=False
                )

                if ingestion_job is not None:
                    self.ingestion_repository.complete_job(
                        job_id=ingestion_job.id,
                        items_crawled=len(crawl_result.get("content_items", [])),
                        items_new=int(crawl_result.get("items_new", 0)),
                    )
                
                # 记录执行历史
                self.execution_history.append(execution_result)
                self._save_execution_history()
                
                # 记录执行日志
                self.log_execution_cycle(start_time, end_time, "success")
                
                self.logger.info(f"爬取阶段完成 {execution_id}: 成功")
            else:
                raise Exception("; ".join(crawl_result.get("errors", ["爬取失败"])))
            
            return execution_result
            
        except Exception as e:
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            error_msg = str(e)
            self.logger.error(f"爬取阶段失败 {execution_id}: {error_msg}")
            self.logger.debug(traceback.format_exc())
            
            # 更新执行状态
            with self._execution_lock:
                if self.current_execution:
                    self.current_execution.end_time = end_time
                    self.current_execution.status = ExecutionStatus.FAILED
                    self.current_execution.error_message = error_msg
            
            execution_result = ExecutionResult(
                execution_id=execution_id,
                success=False,
                start_time=start_time,
                end_time=end_time,
                duration_seconds=duration,
                items_processed=0,
                categories_found={},
                errors=[error_msg],
                trigger_user=trigger_user,
                trigger_type=trigger_type,
                trigger_chat_id=None,
                report_sent=False
            )

            if ingestion_job is not None:
                self.ingestion_repository.update_status(
                    job_id=ingestion_job.id,
                    status=IngestionJobStatus.FAILED.value,
                    error_message=error_msg,
                )
            
            # 记录执行历史
            self.execution_history.append(execution_result)
            self._save_execution_history()
            
            # 记录执行日志
            self.log_execution_cycle(start_time, end_time, "failed")
            
            return execution_result
        
        finally:
            # 清理当前执行状态
            with self._execution_lock:
                self.current_execution = None

    def analyze_by_time_window(
        self,
        chat_id: str,
        time_window_hours: int,
        manual_source: str = "telegram",
    ) -> Dict[str, Any]:
        """
        按时间窗口执行分析

        Args:
            chat_id: 聊天ID
            time_window_hours: 时间窗口（小时）

        Returns:
            包含report_content和execution_id的字典
        """
        from datetime import timezone

        execution_id = f"analyze_{chat_id}_{int(time.time())}"
        result = {
            "success": False,
            "report_content": "",
            "items_processed": 0,
            "execution_id": execution_id,
            "final_report_messages": [],
            "errors": []
        }
        recipient_key = self._resolve_manual_recipient_key(chat_id, manual_source)

        try:
            if self.content_repository is None:
                raise Exception("内容仓储未初始化")
            if self.analysis_repository is None:
                raise Exception("分析仓储未初始化")

            # 初始化系统（如果尚未初始化）
            if not self._initialized:
                if not self.initialize_system():
                    raise Exception("系统初始化失败")

            since_time = datetime.now(timezone.utc) - timedelta(hours=time_window_hours)

            # 从数据库获取时间窗口内的内容
            content_items = self.content_repository.get_content_items_since(
                since_time=since_time,
                max_hours=time_window_hours
            )
            self.logger.info(f"从数据库获取到 {len(content_items)} 个内容项进行时间窗口分析 (execution_id: {execution_id})")
            
            if not content_items:
                result["success"] = True
                return result

            manual_historical_titles = self._get_manual_historical_titles(recipient_key)
            
            # 执行分析阶段
            analysis_result = self._execute_analysis_stage(
                content_items,
                is_manual=True,
                analysis_time_window_hours=time_window_hours,
                preloaded_content_items=content_items,
                manual_historical_titles=manual_historical_titles,
            )
            if not analysis_result["success"]:
                result["errors"].extend(analysis_result["errors"])
                self.analysis_repository.log_execution(
                    recipient_key=recipient_key,
                    time_window_hours=time_window_hours,
                    items_count=len(content_items),
                    success=False,
                    error_message="; ".join(analysis_result["errors"])
                )
                return result
            
            categorized_items = analysis_result["categorized_items"]
            analysis_results = analysis_result["analysis_results"]
            
            # 执行报告生成阶段
            report_result = self._execute_reporting_stage(
                categorized_items, 
                analysis_results, 
                None,  # crawl_status
                time_window_hours
            )
            
            if not report_result["success"]:
                result["errors"].extend(report_result["errors"])
                self.analysis_repository.log_execution(
                    recipient_key=recipient_key,
                    time_window_hours=time_window_hours,
                    items_count=len(content_items),
                    success=False,
                    error_message="; ".join(report_result["errors"])
                )
                return result
            
            result["success"] = True
            result["report_content"] = report_result["report_content"]
            result["items_processed"] = len(content_items)
            result["final_report_messages"] = self._build_manual_report_messages(categorized_items)

            if not result["report_content"] and len(content_items) > 0:
                error_message = "分析未生成有效报告内容"
                result["success"] = False
                result["errors"].append(error_message)
                self.analysis_repository.log_execution(
                    recipient_key=recipient_key,
                    time_window_hours=time_window_hours,
                    items_count=len(content_items),
                    success=False,
                    error_message=error_message,
                )
                return result
            
        except Exception as e:
            error_msg = f"时间窗口分析失败: {str(e)}"
            self.logger.error(error_msg)
            self.logger.debug(traceback.format_exc())
            result["errors"].append(error_msg)
            if self.analysis_repository is not None:
                self.analysis_repository.log_execution(
                    recipient_key=recipient_key,
                    time_window_hours=time_window_hours,
                    items_count=0,
                    success=False,
                    error_message=error_msg
                )
        
        return result

    def get_markdown_report_for_api(self, time_window_hours: int, user_id: Optional[str] = None) -> str:
        """
        获取API用的Markdown报告
        
        Args:
            time_window_hours: 时间窗口（小时）
            user_id: API调用方标识，用于手动分析历史隔离
        
        Returns:
            Markdown格式的报告内容
        """
        api_user_id = str(user_id).strip() if user_id is not None else ""
        if not api_user_id:
            raise ValueError("API user_id不能为空")

        recipient_key = self._normalize_manual_recipient_key("api", api_user_id)

        analyze_result = self.analyze_by_time_window(
            chat_id=api_user_id,
            time_window_hours=time_window_hours,
            manual_source="api",
        )
        
        if analyze_result["success"]:
            self._persist_manual_analysis_success(
                recipient_key=recipient_key,
                time_window_hours=time_window_hours,
                items_count=analyze_result.get("items_processed", 0),
                final_report_messages=analyze_result.get("final_report_messages", []),
            )
            return analyze_result.get("report_content", "")
        else:
            errors = analyze_result.get("errors", ["未知错误"])
            return f"# 分析失败\n\n错误信息: {'; '.join(errors)}"

# 工具函数
def create_main_controller(config_path: str = "./config.json") -> MainController:
    """
    创建主控制器实例
    
    Args:
        config_path: 配置文件路径
        
    Returns:
        MainController实例
    """
    return MainController(config_path)
