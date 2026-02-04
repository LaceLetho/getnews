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
from .analyzers.llm_analyzer import LLMAnalyzer, ContentClassifier
from .reporters.report_generator import ReportGenerator, create_analyzed_data
from .reporters.telegram_sender import TelegramSenderSync, create_telegram_config
from .models import ContentItem, CrawlStatus, CrawlResult, AnalysisResult
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
        self.content_classifier: Optional[ContentClassifier] = None
        self.report_generator: Optional[ReportGenerator] = None
        self.telegram_sender: Optional[TelegramSenderSync] = None
        self.error_manager: Optional[ErrorRecoveryManager] = None
        
        # 执行状态管理
        self.current_execution: Optional[ExecutionInfo] = None
        self.execution_history: List[ExecutionResult] = []
        self._execution_lock = threading.RLock()
        self._stop_event = threading.Event()
        self._scheduler_thread: Optional[threading.Thread] = None
        
        # 信号处理
        self._setup_signal_handlers()
        
        # 初始化标志
        self._initialized = False
        
        self.logger.info("主控制器初始化完成")
    
    def _setup_signal_handlers(self) -> None:
        """设置信号处理器"""
        def signal_handler(signum, frame):
            self.logger.info(f"接收到信号 {signum}，开始优雅关闭")
            self.stop_scheduler()
            self._stop_event.set()
        
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
                api_key=auth_config.llm_api_key,
                model=llm_config.get("model", "MiniMax-M2.1"),
                prompt_config_path=llm_config.get("prompt_config_path", "./prompts/analysis_prompt.json"),
                mock_mode=not auth_config.llm_api_key  # 如果没有API密钥则使用模拟模式
            )
            
            # 初始化内容分类器
            self.content_classifier = ContentClassifier(self.llm_analyzer)
            self.logger.info("LLM分析器和内容分类器初始化完成")
            
            # 初始化报告生成器
            self.report_generator = ReportGenerator(
                include_summary=True,
                prompt_config_path=llm_config.get("prompt_config_path", "./prompts/analysis_prompt.json")
            )
            self.logger.info("报告生成器初始化完成")
            
            # 初始化Telegram发送器
            if auth_config.telegram_bot_token and auth_config.telegram_channel_id:
                telegram_config = create_telegram_config(
                    bot_token=auth_config.telegram_bot_token,
                    channel_id=auth_config.telegram_channel_id
                )
                self.telegram_sender = TelegramSenderSync(telegram_config)
                self.logger.info("Telegram发送器初始化完成")
            else:
                self.logger.warning("Telegram配置不完整，将跳过报告发送")
            
            self._initialized = True
            self.logger.info("系统组件初始化完成")
            return True
            
        except Exception as e:
            self.logger.error(f"系统初始化失败: {str(e)}")
            self.logger.debug(traceback.format_exc())
            return False
    
    def validate_prerequisites(self) -> Dict[str, Any]:
        """
        验证系统运行前提条件
        
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
            
            # 验证必需的配置项
            required_configs = ["time_window_hours", "execution_interval", "storage", "llm_config"]
            for config_key in required_configs:
                if config_key not in config_data:
                    validation_result["errors"].append(f"缺少必需配置项: {config_key}")
                    validation_result["valid"] = False
            
            # 验证认证配置
            auth_config = self.config_manager.get_auth_config()
            if not auth_config.llm_api_key:
                validation_result["warnings"].append("LLM API密钥未配置，将使用模拟模式")
            
            if not auth_config.telegram_bot_token or not auth_config.telegram_channel_id:
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
            
            self.logger.info(f"前提条件验证完成: {'通过' if validation_result['valid'] else '失败'}")
            
        except Exception as e:
            validation_result["errors"].append(f"验证过程中发生异常: {str(e)}")
            validation_result["valid"] = False
            self.logger.error(f"前提条件验证异常: {str(e)}")
        
        return validation_result
    
    def run_once(self) -> ExecutionResult:
        """
        执行一次完整的工作流
        
        Returns:
            执行结果
        """
        execution_id = f"exec_{int(time.time())}"
        start_time = datetime.now()
        
        # 创建执行信息
        execution_info = ExecutionInfo(
            execution_id=execution_id,
            trigger_type="manual",
            trigger_user=None,
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
            result = self.coordinate_workflow()
            
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
                trigger_user=None,
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
                trigger_user=None,
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
    
    def coordinate_workflow(self) -> Dict[str, Any]:
        """
        协调完整的工作流程
        
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
            config_data = self.config_manager.config_data
            time_window_hours = config_data["time_window_hours"]
            
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
            
            send_result = self._execute_sending_stage(report_content)
            
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
            
            if x_sources and auth_config.x_ct0 and auth_config.x_auth_token:
                for x_source in x_sources:
                    try:
                        crawler = factory.create_source("x", time_window_hours, 
                                                      ct0=auth_config.x_ct0, 
                                                      auth_token=auth_config.x_auth_token)
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
    
    def _execute_analysis_stage(self, content_items: List[ContentItem]) -> Dict[str, Any]:
        """执行内容分析阶段"""
        result = {"success": False, "categorized_items": {}, "analysis_results": {}, "errors": []}
        
        try:
            if not content_items:
                self.logger.info("没有内容需要分析")
                result["success"] = True
                return result
            
            # 批量分析内容
            analysis_results = self.llm_analyzer.batch_analyze(content_items)
            
            # 分类内容
            categorized_items = {}
            analysis_dict = {}
            
            for item, analysis in zip(content_items, analysis_results):
                # 跳过被忽略的内容
                if analysis.should_ignore:
                    continue
                
                category = self.content_classifier.classify_item(item, analysis)
                
                if category not in categorized_items:
                    categorized_items[category] = []
                
                categorized_items[category].append(item)
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
            report_content = self.report_generator.generate_report(analyzed_data, crawl_status)
            
            result.update({
                "success": True,
                "report_content": report_content
            })
            
        except Exception as e:
            error_msg = f"报告生成阶段失败: {str(e)}"
            self.logger.error(error_msg)
            result["errors"].append(error_msg)
        
        return result
    
    def _execute_sending_stage(self, report_content: str) -> Dict[str, Any]:
        """执行报告发送阶段"""
        result = {"success": False, "errors": []}
        
        try:
            if not self.telegram_sender:
                self.logger.warning("Telegram发送器未配置，跳过报告发送")
                # 保存本地备份
                backup_path = self._save_report_backup(report_content)
                self.logger.info(f"报告已保存到本地: {backup_path}")
                result["success"] = True
                return result
            
            # 发送报告
            send_result = self.telegram_sender.send_report(report_content)
            
            if send_result.success:
                self.logger.info(f"报告发送成功，消息ID: {send_result.message_id}")
                result["success"] = True
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
            # 从配置文件或环境变量获取
            interval_seconds = int(os.getenv("EXECUTION_INTERVAL", 
                                           self.config_manager.config_data.get("execution_interval", 3600)))
        
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
        """调度器循环"""
        self.logger.info("调度器循环开始")
        
        while not self._stop_event.is_set():
            try:
                # 记录下次执行时间
                next_execution = datetime.now() + timedelta(seconds=interval_seconds)
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
                result = self.run_once()
                
                if result.success:
                    self.logger.info(f"定时执行成功，处理了 {result.items_processed} 个项目")
                else:
                    self.logger.error(f"定时执行失败: {'; '.join(result.errors)}")
                
            except Exception as e:
                self.logger.error(f"调度器循环异常: {str(e)}")
                self.logger.debug(traceback.format_exc())
                
                # 等待一段时间后继续
                if not self._stop_event.wait(60):  # 等待1分钟
                    continue
                else:
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
        
        # 从配置获取间隔
        interval_seconds = int(os.getenv("EXECUTION_INTERVAL", 
                                       self.config_manager.config_data.get("execution_interval", 3600)))
        
        # 获取最后一次执行时间
        if self.execution_history:
            last_execution = self.execution_history[-1]
            return last_execution.end_time + timedelta(seconds=interval_seconds)
        
        return datetime.now() + timedelta(seconds=interval_seconds)
    
    def log_execution_cycle(self, start_time: datetime, end_time: datetime, status: str) -> None:
        """记录执行周期日志"""
        duration = (end_time - start_time).total_seconds()
        
        log_entry = {
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration_seconds": duration,
            "status": status,
            "timestamp": datetime.now().isoformat()
        }
        
        self.logger.info(f"执行周期记录: {json.dumps(log_entry, ensure_ascii=False)}")
    
    def cleanup_resources(self) -> None:
        """清理资源"""
        self.logger.info("开始清理资源")
        
        try:
            # 停止调度器
            self.stop_scheduler()
            
            # 清理数据管理器
            if self.data_manager:
                self.data_manager.close()
            
            # 清理其他资源
            if self.content_classifier:
                self.content_classifier.clear_classifications()
            
            self.logger.info("资源清理完成")
            
        except Exception as e:
            self.logger.error(f"资源清理失败: {str(e)}")
    
    def setup_environment_config(self) -> None:
        """设置环境变量配置"""
        # 从环境变量覆盖配置
        env_mappings = {
            "TIME_WINDOW_HOURS": "time_window_hours",
            "EXECUTION_INTERVAL": "execution_interval"
        }
        
        config_updates = {}
        for env_key, config_path in env_mappings.items():
            env_value = os.getenv(env_key)
            if env_value:
                # 解析嵌套配置路径
                keys = config_path.split('.')
                current = config_updates
                for key in keys[:-1]:
                    if key not in current:
                        current[key] = {}
                    current = current[key]
                
                # 转换数值类型
                if keys[-1] in ["time_window_hours", "execution_interval"]:
                    current[keys[-1]] = int(env_value)
                else:
                    current[keys[-1]] = env_value
        
        # 更新配置
        if config_updates and self.config_manager:
            current_config = self.config_manager.config_data.copy()
            self._deep_update(current_config, config_updates)
            self.config_manager.config_data = current_config
            self.logger.info("环境变量配置已应用")
    
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
        
        # 下次执行时间
        next_time = self.get_next_execution_time()
        if next_time:
            status["next_execution_time"] = next_time.isoformat()
        
        return status


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
    
    Args:
        config_path: 配置文件路径
        
    Returns:
        退出状态码 (0=成功, 非0=失败)
    """
    controller = create_main_controller(config_path)
    
    try:
        # 设置环境变量配置
        controller.setup_environment_config()
        
        # 验证前提条件
        validation_result = controller.validate_prerequisites()
        if not validation_result["valid"]:
            print(f"前提条件验证失败: {validation_result['errors']}")
            return 1
        
        # 执行一次工作流
        result = controller.run_once()
        
        if result.success:
            print(f"执行成功，处理了 {result.items_processed} 个项目")
            return 0
        else:
            print(f"执行失败: {'; '.join(result.errors)}")
            return 1
            
    except Exception as e:
        print(f"执行异常: {str(e)}")
        return 1
    
    finally:
        controller.cleanup_resources()


def run_scheduled_mode(config_path: str = "./config.json") -> int:
    """
    执行定时调度模式
    
    Args:
        config_path: 配置文件路径
        
    Returns:
        退出状态码 (0=成功, 非0=失败)
    """
    controller = create_main_controller(config_path)
    
    try:
        # 设置环境变量配置
        controller.setup_environment_config()
        
        # 验证前提条件
        validation_result = controller.validate_prerequisites()
        if not validation_result["valid"]:
            print(f"前提条件验证失败: {validation_result['errors']}")
            return 1
        
        # 初始化系统
        if not controller.initialize_system():
            print("系统初始化失败")
            return 1
        
        # 启动调度器
        controller.start_scheduler()
        
        print("定时调度器已启动，等待停止信号...")
        
        # 等待停止信号
        try:
            while not controller._stop_event.is_set():
                time.sleep(1)
        except KeyboardInterrupt:
            print("接收到中断信号")
        
        print("正在停止调度器...")
        controller.stop_scheduler()
        
        return 0
        
    except Exception as e:
        print(f"调度模式异常: {str(e)}")
        return 1
    
    finally:
        controller.cleanup_resources()