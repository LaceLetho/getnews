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
from .storage.data_manager import DataManager
from .crawlers.data_source_factory import get_data_source_factory, register_builtin_sources
from .analyzers.llm_analyzer import LLMAnalyzer
from .reporters.report_generator import ReportGenerator, create_analyzed_data
from .reporters.telegram_sender import TelegramSenderSync, create_telegram_config
from .models import ContentItem, CrawlStatus, CrawlResult, AnalysisResult, BirdConfig, TelegramCommandConfig
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
    trigger_chat_id: Optional[str] = None  # 触发命令的聊天ID
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)


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
        
        # 执行状态管理
        self.current_execution: Optional[ExecutionInfo] = None
        self.execution_history: List[ExecutionResult] = []
        self._execution_lock = threading.RLock()
        self._stop_event = threading.Event()
        self._scheduler_thread: Optional[threading.Thread] = None
        self._last_scheduled_time: Optional[datetime] = None  # 上次调度任务开始的时间
        
        # 并发控制
        self._max_concurrent_executions = 1
        self._execution_timeout_minutes = 30
        
        # 信号处理
        self._setup_signal_handlers()
        
        # 初始化标志
        self._initialized = False
        
        self.logger.info("主控制器初始化完成")
    
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
            
            # 初始化配置管理器
            self.config_manager = ConfigManager(self.config_path)
            config_data = self.config_manager.load_config()
            self.logger.info("配置管理器初始化完成")
            
            # 初始化数据管理器
            storage_config = self.config_manager.get_storage_config()
            self.data_manager = DataManager(storage_config)
            self.logger.info("数据管理器初始化完成")
            
            # 初始化缓存管理器
            from .storage.cache_manager import SentMessageCacheManager
            self.cache_manager = SentMessageCacheManager(storage_config)
            self.logger.info("缓存管理器初始化完成")
            
            # 清理过期缓存（需求17.12: 系统启动时调用cleanup_expired_cache）
            try:
                expired_count = self.cache_manager.cleanup_expired_cache(hours=24)
                self.logger.info(f"清理了 {expired_count} 条过期缓存记录")
            except Exception as e:
                self.logger.warning(f"清理过期缓存失败: {str(e)}")
            
            # 初始化错误恢复管理器
            self.error_manager = ErrorRecoveryManager()
            self.logger.info("错误恢复管理器初始化完成")
            
            # 注册内置数据源
            register_builtin_sources()
            self.logger.info("内置数据源注册完成")
            
            # 初始化LLM分析器
            auth_config = self.config_manager.get_auth_config()
            llm_config = config_data.get("llm_config", {})
            
            self.llm_analyzer = LLMAnalyzer(
                api_key=auth_config.LLM_API_KEY,
                GROK_API_KEY=auth_config.GROK_API_KEY,
                model=llm_config.get("model", "gpt-4"),
                summary_model=llm_config.get("summary_model", "grok-beta"),
                market_prompt_path=llm_config.get("market_prompt_path", "./prompts/market_summary_prompt.md"),
                analysis_prompt_path=llm_config.get("analysis_prompt_path", "./prompts/analysis_prompt.md"),
                temperature=llm_config.get("temperature", 0.1),
                max_tokens=llm_config.get("max_tokens", 4000),
                batch_size=llm_config.get("batch_size", 10),
                cache_ttl_minutes=llm_config.get("cache_ttl_minutes", 30),
                mock_mode=not auth_config.LLM_API_KEY  # 如果没有API密钥则使用模拟模式
            )
            
            # 初始化内容分类器
            self.logger.info("LLM分析器初始化完成")
            
            # 初始化报告生成器
            self.report_generator = ReportGenerator(
                include_market_snapshot=True,
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
                    self.logger.warning(f"Telegram命令处理器初始化失败: {str(e)}")
            
            self._initialized = True
            self.logger.info("系统组件初始化完成")
            return True
            
        except Exception as e:
            self.logger.error(f"系统初始化失败: {str(e)}")
            self.logger.debug(traceback.format_exc())
            return False
    
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
    
    def validate_prerequisites(self) -> Dict[str, Any]:
        """
        验证系统运行前提条件
        
        需求9.12: 添加容器启动时的配置验证和快速失败机制
        需求9.15: 容器环境配置无效时快速失败并提供明确的错误信息
        
        Returns:
            验证结果字典
        """
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
            
            # 验证execution_interval和time_window_hours可以获取（从环境变量或配置文件）
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
            auth_config = self.config_manager.get_auth_config()
            if not auth_config.LLM_API_KEY:
                validation_result["warnings"].append("LLM API密钥未配置，将使用模拟模式")
            
            if not auth_config.TELEGRAM_BOT_TOKEN or not auth_config.TELEGRAM_CHANNEL_ID:
                validation_result["warnings"].append("Telegram配置不完整，将跳过报告发送")
            
            # 验证数据源配置
            rss_sources = self.config_manager.get_rss_sources()
            x_sources = self.config_manager.get_x_sources()
            
            if not rss_sources and not x_sources:
                validation_result["warnings"].append("未配置任何数据源")
            
            # 验证存储路径
            storage_config = self.config_manager.get_storage_config()
            if not self.config_manager.validate_storage_path(storage_config.database_path):
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
            validation_result = self.validate_prerequisites()
            if not validation_result["valid"]:
                raise Exception(f"前提条件验证失败: {validation_result['errors']}")
            
            # 初始化系统（如果尚未初始化）
            if not self._initialized:
                if not self.initialize_system():
                    raise Exception("系统初始化失败")
            
            # 执行完整工作流
            result = self.coordinate_workflow(trigger_chat_id=trigger_chat_id)
            
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
                trigger_chat_id=trigger_chat_id,
                report_sent=False
            )
            
            # 记录执行历史
            self.execution_history.append(execution_result)
            
            # 记录执行日志
            self.log_execution_cycle(start_time, end_time, "failed")
            
            return execution_result
        
        finally:
            # 清理当前执行状态
            with self._execution_lock:
                self.current_execution = None
    
    def coordinate_workflow(self, trigger_chat_id: Optional[str] = None) -> Dict[str, Any]:
        """
        协调完整的工作流程
        
        Args:
            trigger_chat_id: 触发命令的聊天ID（用于发送报告）
        
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
            
            analysis_result = self._execute_analysis_stage(content_items)
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
                categorized_items=categorized_items
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
        result = {"success": False, "content_items": [], "crawl_status": None, "errors": []}
        
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
            auth_config = self.config_manager.get_auth_config()
            
            if x_sources and auth_config.X_CT0 and auth_config.X_AUTH_TOKEN:
                # 创建 BirdConfig（X爬取器使用bird工具，需要通过配置文件设置认证）
                bird_config = BirdConfig()
                
                for x_source in x_sources:
                    try:
                        crawler = factory.create_source("x", time_window_hours, bird_config=bird_config)
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
            
            # 数据去重和存储
            if all_content_items:
                added_count = self.data_manager.add_content_items(all_content_items)
                self.data_manager.deduplicate_content()
                self.logger.info(f"成功存储 {added_count} 个内容项")
            
            # 创建爬取状态
            crawl_status = CrawlStatus(
                rss_results=rss_results,
                x_results=x_results,
                total_items=len(all_content_items),
                execution_time=datetime.now()
            )
            
            # 保存爬取状态
            self.data_manager.save_crawl_status(crawl_status)
            
            result.update({
                "success": True,
                "content_items": all_content_items,
                "crawl_status": crawl_status
            })
            
        except Exception as e:
            error_msg = f"数据爬取阶段失败: {str(e)}"
            self.logger.error(error_msg)
            result["errors"].append(error_msg)
        
        return result
    
    def _execute_analysis_stage(self, newly_crawled_items: List[ContentItem]) -> Dict[str, Any]:
        """
        执行内容分析阶段
        
        重要: 由于RSS数据源和bird爬取都有时间/页数限制，本方法从本地数据库中
        获取时间窗口内的所有消息进行分析，而不仅仅使用刚爬取的消息。
        
        Args:
            newly_crawled_items: 刚爬取的内容项（用于日志记录）
            
        Returns:
            分析结果字典
        """
        result = {"success": False, "categorized_items": {}, "analysis_results": {}, "errors": []}
        
        try:
            # 从数据库获取时间窗口内的所有消息（使用配置管理器的getter方法）
            time_window_hours = self.config_manager.get_time_window_hours()
            
            # 获取时间窗口内的所有内容项（包括之前爬取的和刚爬取的）
            all_content_items = self.data_manager.get_content_items(
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
            
            # 批量分析内容
            analysis_results = self.llm_analyzer.analyze_content_batch(all_content_items)
            
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
            # 创建分析数据对象
            analyzed_data = create_analyzed_data(
                categorized_items=categorized_items,
                analysis_results=analysis_results,
                time_window_hours=time_window_hours
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
                              categorized_items: Optional[Dict[str, List[Any]]] = None) -> Dict[str, Any]:
        """
        执行报告发送阶段
        
        需求17.9: 报告发送成功后调用cache_sent_messages
        
        Args:
            report_content: 报告内容
            target_chat_id: 目标聊天ID（如果提供，发送到该聊天；否则发送到TELEGRAM_CHANNEL_ID）
            categorized_items: 分类后的内容项（用于缓存）
        
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
                if self.cache_manager and categorized_items:
                    try:
                        messages_to_cache = []
                        for category, items in categorized_items.items():
                            for item in items:
                                # item 是 StructuredAnalysisResult 对象
                                messages_to_cache.append({
                                    "summary": item.summary,
                                    "category": item.category,
                                    "time": item.time,
                                    "sent_at": datetime.now().isoformat()
                                })
                        
                        if messages_to_cache:
                            cached_count = self.cache_manager.cache_sent_messages(messages_to_cache)
                            self.logger.info(f"成功缓存 {cached_count} 条已发送消息")
                            
                            # 需求17.14: 实现缓存统计和监控
                            cache_stats = self.cache_manager.get_cache_statistics()
                            self.logger.info(f"缓存统计: {cache_stats}")
                    except Exception as cache_error:
                        # 需求17.15: 缓存失败不影响主流程
                        self.logger.warning(f"缓存已发送消息失败: {str(cache_error)}")
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
        
        consecutive_failures = 0
        max_consecutive_failures = 3
        
        while not self._stop_event.is_set():
            try:
                # 记录本次调度开始时间
                scheduled_time = datetime.now()
                self._last_scheduled_time = scheduled_time
                
                # 记录下次执行时间
                next_execution = scheduled_time + timedelta(seconds=interval_seconds)
                self.logger.info(f"下次执行时间: {next_execution.strftime('%Y-%m-%d %H:%M:%S')}")
                
                # 等待调度间隔或停止信号
                if self._stop_event.wait(interval_seconds):
                    break  # 收到停止信号
                
                # 检查是否有其他执行正在进行
                with self._execution_lock:
                    if self.current_execution and self.current_execution.status == ExecutionStatus.RUNNING:
                        self.logger.warning("上次执行仍在进行中，跳过本次调度")
                        continue
                
                # 执行工作流
                self.logger.info("定时调度触发执行")
                result = self.run_once(trigger_type="scheduled", trigger_user=None)
                
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
    
    def setup_environment_config(self) -> None:
        """
        设置环境变量配置
        
        注意: execution_interval 和 time_window_hours 现在通过 ConfigManager 的
        get_execution_interval() 和 get_time_window_hours() 方法自动从环境变量读取，
        无需在此处理。
        """
        # 环境变量配置现在由 ConfigManager 的 getter 方法处理
        # 保留此方法以保持向后兼容性
        pass
    
    def _deep_update(self, base_dict: Dict, update_dict: Dict) -> None:
        """深度更新字典"""
        for key, value in update_dict.items():
            if key in base_dict and isinstance(base_dict[key], dict) and isinstance(value, dict):
                self._deep_update(base_dict[key], value)
            else:
                base_dict[key] = value
    
    def handle_container_signals(self) -> None:
        """处理容器信号"""
        # 信号处理已在 _setup_signal_handlers 中设置
        pass
    
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


def run_one_time_execution(config_path: str = "./config.json") -> int:
    """
    执行一次性运行模式
    
    需求9.13: 实现退出状态码管理（0=成功，非0=失败）
    
    Args:
        config_path: 配置文件路径
        
    Returns:
        退出状态码 (0=成功, 1=配置错误, 2=执行失败, 3=异常错误)
    """
    controller = create_main_controller(config_path)
    
    try:
        # 设置环境变量配置
        controller.setup_environment_config()
        
        # 验证前提条件
        print("[INFO] 验证系统配置...", flush=True)
        validation_result = controller.validate_prerequisites()
        
        if not validation_result["valid"]:
            print(f"[ERROR] 前提条件验证失败:", flush=True)
            for error in validation_result["errors"]:
                print(f"  - {error}", flush=True)
            return 1  # 配置错误
        
        if validation_result["warnings"]:
            print(f"[WARN] 配置警告:", flush=True)
            for warning in validation_result["warnings"]:
                print(f"  - {warning}", flush=True)
        
        # 执行一次工作流
        print("[INFO] 开始执行工作流...", flush=True)
        result = controller.run_once()
        
        if result.success:
            print(f"[SUCCESS] 执行成功，处理了 {result.items_processed} 个项目", flush=True)
            print(f"[INFO] 执行时长: {result.duration_seconds:.2f} 秒", flush=True)
            print(f"[INFO] 报告发送: {'成功' if result.report_sent else '失败'}", flush=True)
            return 0  # 成功
        else:
            print(f"[ERROR] 执行失败:", flush=True)
            for error in result.errors:
                print(f"  - {error}", flush=True)
            return 2  # 执行失败
            
    except KeyboardInterrupt:
        print("[INFO] 接收到中断信号，正在退出...", flush=True)
        return 0  # 用户中断视为正常退出
    
    except Exception as e:
        print(f"[ERROR] 执行异常: {str(e)}", flush=True)
        import traceback
        traceback.print_exc()
        return 3  # 异常错误
    
    finally:
        try:
            controller.cleanup_resources()
            print("[INFO] 资源清理完成", flush=True)
        except Exception as e:
            print(f"[WARN] 资源清理失败: {str(e)}", flush=True)


def run_scheduled_mode(config_path: str = "./config.json") -> int:
    """
    执行定时调度模式（同时支持Telegram命令触发）
    
    需求9.13: 实现退出状态码管理（0=成功，非0=失败）
    需求16.1: 支持通过Telegram Bot接收用户命令
    需求16.12: 支持在定时调度模式和命令触发模式之间切换
    
    注意：此模式同时启动定时调度器和Telegram命令监听器，
    两者共享并发控制机制，不会发生冲突。
    
    Args:
        config_path: 配置文件路径
        
    Returns:
        退出状态码 (0=正常退出, 1=配置错误, 3=异常错误)
    """
    controller = create_main_controller(config_path)
    
    try:
        # 设置环境变量配置
        controller.setup_environment_config()
        
        # 验证前提条件
        print("[INFO] 验证系统配置...", flush=True)
        validation_result = controller.validate_prerequisites()
        
        if not validation_result["valid"]:
            print(f"[ERROR] 前提条件验证失败:", flush=True)
            for error in validation_result["errors"]:
                print(f"  - {error}", flush=True)
            return 1  # 配置错误
        
        if validation_result["warnings"]:
            print(f"[WARN] 配置警告:", flush=True)
            for warning in validation_result["warnings"]:
                print(f"  - {warning}", flush=True)
        
        # 初始化系统
        print("[INFO] 初始化系统组件...", flush=True)
        if not controller.initialize_system():
            print("[ERROR] 系统初始化失败", flush=True)
            return 1  # 配置错误
        
        # 启动定时调度器
        print("[INFO] 启动定时调度器...", flush=True)
        controller.start_scheduler()
        
        # 获取调度间隔
        interval_seconds = controller.config_manager.get_execution_interval()
        print(f"[INFO] 定时调度器已启动，间隔: {interval_seconds} 秒", flush=True)
        
        # 如果配置了Telegram命令处理器，同时启动命令监听器
        if controller.command_handler:
            print("[INFO] 启动Telegram命令监听器...", flush=True)
            controller.start_command_listener()
            print("[INFO] Telegram命令监听器已启动", flush=True)
            print("[INFO] 系统运行在混合模式：定时调度 + 命令触发", flush=True)
        else:
            print("[INFO] Telegram命令处理器未配置，仅运行定时调度模式", flush=True)
        
        print("[INFO] 等待停止信号 (Ctrl+C 或 SIGTERM)...", flush=True)
        
        # 等待停止信号
        try:
            while not controller._stop_event.is_set():
                time.sleep(1)
        except KeyboardInterrupt:
            print("[INFO] 接收到中断信号", flush=True)
        
        print("[INFO] 正在停止系统...", flush=True)
        
        # 停止调度器
        controller.stop_scheduler()
        
        # 停止命令监听器（如果已启动）
        if controller.command_handler:
            controller.stop_command_listener()
        
        print("[SUCCESS] 系统已正常停止", flush=True)
        return 0  # 正常退出
        
    except KeyboardInterrupt:
        print("[INFO] 接收到中断信号，正在退出...", flush=True)
        return 0  # 用户中断视为正常退出
    
    except Exception as e:
        print(f"[ERROR] 调度模式异常: {str(e)}", flush=True)
        import traceback
        traceback.print_exc()
        return 3  # 异常错误
    
    finally:
        try:
            controller.cleanup_resources()
            print("[INFO] 资源清理完成", flush=True)
        except Exception as e:
            print(f"[WARN] 资源清理失败: {str(e)}", flush=True)


def run_command_listener_mode(config_path: str = "./config.json") -> int:
    """
    执行命令监听模式
    
    需求16.1: 支持通过Telegram Bot接收用户命令
    需求16.12: 支持在定时调度模式和命令触发模式之间切换
    
    Args:
        config_path: 配置文件路径
        
    Returns:
        退出状态码 (0=正常退出, 1=配置错误, 3=异常错误)
    """
    controller = create_main_controller(config_path)
    
    try:
        # 设置环境变量配置
        controller.setup_environment_config()
        
        # 验证前提条件
        print("[INFO] 验证系统配置...", flush=True)
        validation_result = controller.validate_prerequisites()
        
        if not validation_result["valid"]:
            print(f"[ERROR] 前提条件验证失败:", flush=True)
            for error in validation_result["errors"]:
                print(f"  - {error}", flush=True)
            return 1  # 配置错误
        
        if validation_result["warnings"]:
            print(f"[WARN] 配置警告:", flush=True)
            for warning in validation_result["warnings"]:
                print(f"  - {warning}", flush=True)
        
        # 初始化系统
        print("[INFO] 初始化系统组件...", flush=True)
        if not controller.initialize_system():
            print("[ERROR] 系统初始化失败", flush=True)
            return 1  # 配置错误
        
        # 检查命令处理器是否可用
        if not controller.command_handler:
            print("[ERROR] Telegram命令处理器未配置或初始化失败", flush=True)
            return 1  # 配置错误
        
        # 启动命令监听器
        print("[INFO] 启动Telegram命令监听器...", flush=True)
        controller.start_command_listener()
        
        print("[INFO] Telegram命令监听器已启动", flush=True)
        print("[INFO] 等待用户命令 (Ctrl+C 或 SIGTERM 停止)...", flush=True)
        
        # 等待停止信号
        try:
            while not controller._stop_event.is_set():
                time.sleep(1)
        except KeyboardInterrupt:
            print("[INFO] 接收到中断信号", flush=True)
        
        print("[INFO] 正在停止命令监听器...", flush=True)
        controller.stop_command_listener()
        
        print("[SUCCESS] 命令监听器已正常停止", flush=True)
        return 0  # 正常退出
        
    except KeyboardInterrupt:
        print("[INFO] 接收到中断信号，正在退出...", flush=True)
        return 0  # 用户中断视为正常退出
    
    except Exception as e:
        print(f"[ERROR] 命令监听模式异常: {str(e)}", flush=True)
        import traceback
        traceback.print_exc()
        return 3  # 异常错误
    
    finally:
        try:
            controller.cleanup_resources()
            print("[INFO] 资源清理完成", flush=True)
        except Exception as e:
            print(f"[WARN] 资源清理失败: {str(e)}", flush=True)
