"""
Telegram命令处理器

处理用户通过Telegram发送的命令，支持手动触发系统执行。

根据需求16实现Telegram命令触发功能：
- 需求16.1: 支持通过Telegram Bot接收用户命令
- 需求16.2: 实现/run命令立即触发完整工作流
- 需求16.3: 实现/status命令返回系统运行状态
- 需求16.4: 实现/help命令返回可用命令列表
- 需求16.5: 验证命令发送者的权限，只允许授权用户触发执行
- 需求16.8: 记录所有手动触发的执行历史和触发用户信息
- 需求16.10: 支持配置授权用户列表，限制命令执行权限
- 需求16.11: 未授权用户发送命令时返回权限拒绝消息
"""

import asyncio
import logging
import threading
import time
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass
from datetime import datetime
from collections import defaultdict

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, filters
from telegram.error import TelegramError

from ..models import TelegramCommandConfig, CommandExecutionHistory, ExecutionResult


@dataclass
class CommandRateLimitState:
    """命令速率限制状态"""
    command_count: int = 0
    last_reset_time: datetime = None
    last_command_time: datetime = None
    
    def __post_init__(self):
        if self.last_reset_time is None:
            self.last_reset_time = datetime.now()
        if self.last_command_time is None:
            self.last_command_time = datetime.now()


class TelegramCommandHandler:
    """
    Telegram命令处理器
    
    处理用户通过Telegram发送的命令，支持手动触发系统执行。
    """
    
    def __init__(
        self,
        bot_token: str,
        execution_coordinator: Any,  # MainController实例
        config: TelegramCommandConfig
    ):
        """
        初始化Telegram命令处理器
        
        Args:
            bot_token: Telegram Bot Token
            execution_coordinator: 执行协调器实例
            config: Telegram命令配置
        """
        self.bot_token = bot_token
        self.execution_coordinator = execution_coordinator
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Telegram应用
        self.application: Optional[Application] = None
        self._listener_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._event_loop: Optional[asyncio.AbstractEventLoop] = None
        
        # 命令执行历史
        self.command_history: List[CommandExecutionHistory] = []
        
        # 速率限制状态
        self._rate_limit_states: Dict[str, CommandRateLimitState] = defaultdict(CommandRateLimitState)
        
        # 授权用户缓存
        self._authorized_users: Dict[str, Dict[str, Any]] = {}
        self._load_authorized_users()
        
        self.logger.info("Telegram命令处理器初始化完成")
    
    def _load_authorized_users(self) -> None:
        """加载授权用户列表"""
        for user_config in self.config.authorized_users:
            user_id = str(user_config.get("user_id", ""))
            if user_id:
                self._authorized_users[user_id] = user_config
        
        self.logger.info(f"已加载 {len(self._authorized_users)} 个授权用户")
    
    def is_authorized_user(self, user_id: str, username: str = None) -> bool:
        """
        验证用户是否有权限执行命令
        
        需求16.5: 验证命令发送者的权限
        需求16.11: 未授权用户发送命令时返回权限拒绝消息
        
        Args:
            user_id: Telegram用户ID
            username: Telegram用户名（可选）
            
        Returns:
            是否授权
        """
        if not self.config.enabled:
            return False
        
        user_id_str = str(user_id)
        
        # 检查用户ID是否在授权列表中
        if user_id_str in self._authorized_users:
            return True
        
        # 如果提供了用户名，检查所有授权用户的用户名
        if username:
            for user_config in self.config.authorized_users:
                if user_config.get("username") == username:
                    return True
        
        return False
    
    def validate_user_permissions(self, user_id: str, command: str) -> bool:
        """
        验证用户对特定命令的权限
        
        Args:
            user_id: 用户ID
            command: 命令名称
            
        Returns:
            是否有权限
        """
        user_id_str = str(user_id)
        
        # 首先检查用户是否在授权列表中（通过ID）
        user_config = None
        if user_id_str in self._authorized_users:
            user_config = self._authorized_users[user_id_str]
        
        # 如果通过ID没找到，不再检查其他方式
        # 因为validate_user_permissions应该只用于已经通过is_authorized_user验证的用户
        if not user_config:
            return False
        
        permissions = user_config.get("permissions", [])
        
        # 如果没有指定权限，默认允许所有命令
        if not permissions:
            return True
        
        # 检查是否有该命令的权限
        return command in permissions
    
    def check_rate_limit(self, user_id: str) -> tuple[bool, Optional[str]]:
        """
        检查用户是否超过速率限制
        
        Args:
            user_id: 用户ID
            
        Returns:
            (是否允许, 错误消息)
        """
        user_id_str = str(user_id)
        state = self._rate_limit_states[user_id_str]
        now = datetime.now()
        
        # 检查是否需要重置计数器（每小时重置）
        hours_since_reset = (now - state.last_reset_time).total_seconds() / 3600
        if hours_since_reset >= 1.0:
            state.command_count = 0
            state.last_reset_time = now
        
        # 检查是否超过每小时限制
        max_per_hour = self.config.command_rate_limit.get("max_commands_per_hour", 10)
        if state.command_count >= max_per_hour:
            return False, f"已达到每小时命令限制 ({max_per_hour} 次)，请稍后再试"
        
        # 检查冷却时间
        cooldown_minutes = self.config.command_rate_limit.get("cooldown_minutes", 5)
        minutes_since_last = (now - state.last_command_time).total_seconds() / 60
        if minutes_since_last < cooldown_minutes:
            remaining = cooldown_minutes - minutes_since_last
            return False, f"命令冷却中，请等待 {remaining:.1f} 分钟"
        
        # 更新状态
        state.command_count += 1
        state.last_command_time = now
        
        return True, None
    
    async def start_command_listener(self) -> None:
        """
        启动命令监听器
        
        需求16.1: 支持通过Telegram Bot接收用户命令
        """
        if self.application:
            self.logger.warning("命令监听器已在运行")
            return
        
        try:
            self.logger.info("启动Telegram命令监听器")
            
            # 创建应用
            self.application = Application.builder().token(self.bot_token).build()
            
            # 注册命令处理器
            self.application.add_handler(CommandHandler("run", self._handle_run_command))
            self.application.add_handler(CommandHandler("status", self._handle_status_command))
            self.application.add_handler(CommandHandler("help", self._handle_help_command))
            self.application.add_handler(CommandHandler("start", self._handle_help_command))
            
            # 启动应用
            await self.application.initialize()
            await self.application.start()
            await self.application.updater.start_polling()
            
            # 保存事件循环引用以便从其他线程访问
            self._event_loop = asyncio.get_running_loop()
            
            self.logger.info("Telegram命令监听器已启动")
            
            # 保持运行直到收到停止信号
            while not self._stop_event.is_set():
                await asyncio.sleep(1)
            
        except Exception as e:
            self.logger.error(f"启动命令监听器失败: {str(e)}")
            raise
        finally:
            await self.stop_command_listener()
    
    async def stop_command_listener(self) -> None:
        """停止命令监听器"""
        if not self.application:
            return
        
        try:
            self.logger.info("停止Telegram命令监听器")
            
            await self.application.updater.stop()
            await self.application.stop()
            await self.application.shutdown()
            
            self.application = None
            self.logger.info("Telegram命令监听器已停止")
            
        except Exception as e:
            self.logger.error(f"停止命令监听器失败: {str(e)}")
    
    async def _handle_run_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        处理/run命令
        
        需求16.2: 实现/run命令立即触发完整工作流
        """
        user = update.effective_user
        user_id = str(user.id)
        username = user.username or user.first_name
        
        self.logger.info(f"收到/run命令，用户: {username} ({user_id})")
        
        try:
            # 验证权限
            if not self.is_authorized_user(user_id, username):
                response = "❌ 权限拒绝\n\n您没有权限执行此命令。"
                await update.message.reply_text(response)
                self._log_command_execution("/run", user_id, username, None, False, response)
                return
            
            # 验证命令权限
            if not self.validate_user_permissions(user_id, "run"):
                response = "❌ 权限不足\n\n您没有执行 /run 命令的权限。"
                await update.message.reply_text(response)
                self._log_command_execution("/run", user_id, username, None, False, response)
                return
            
            # 检查速率限制
            allowed, error_msg = self.check_rate_limit(user_id)
            if not allowed:
                response = f"⏱️ 速率限制\n\n{error_msg}"
                await update.message.reply_text(response)
                self._log_command_execution("/run", user_id, username, None, False, response)
                return
            
            # 触发执行
            response = self.handle_run_command(user_id, username)
            await update.message.reply_text(response, parse_mode="Markdown")
            
        except Exception as e:
            error_msg = f"处理/run命令时发生错误: {str(e)}"
            self.logger.error(error_msg)
            await update.message.reply_text(f"❌ 命令执行失败\n\n{str(e)}")
    
    async def _handle_status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        处理/status命令
        
        需求16.3: 实现/status命令返回系统运行状态
        """
        user = update.effective_user
        user_id = str(user.id)
        username = user.username or user.first_name
        
        self.logger.info(f"收到/status命令，用户: {username} ({user_id})")
        
        try:
            # 验证权限
            if not self.is_authorized_user(user_id, username):
                response = "❌ 权限拒绝\n\n您没有权限执行此命令。"
                await update.message.reply_text(response)
                self._log_command_execution("/status", user_id, username, None, False, response)
                return
            
            # 获取状态
            response = self.handle_status_command(user_id)
            await update.message.reply_text(response, parse_mode="Markdown")
            self._log_command_execution("/status", user_id, username, None, True, "状态查询成功")
            
        except Exception as e:
            error_msg = f"处理/status命令时发生错误: {str(e)}"
            self.logger.error(error_msg)
            await update.message.reply_text(f"❌ 命令执行失败\n\n{str(e)}")
    
    async def _handle_help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        处理/help命令
        
        需求16.4: 实现/help命令返回可用命令列表
        """
        user = update.effective_user
        user_id = str(user.id)
        username = user.username or user.first_name
        
        self.logger.info(f"收到/help命令，用户: {username} ({user_id})")
        
        try:
            # 验证权限
            if not self.is_authorized_user(user_id, username):
                response = "❌ 权限拒绝\n\n您没有权限使用此机器人。"
                await update.message.reply_text(response)
                self._log_command_execution("/help", user_id, username, None, False, response)
                return
            
            # 获取帮助信息
            response = self.handle_help_command(user_id)
            await update.message.reply_text(response, parse_mode="Markdown")
            self._log_command_execution("/help", user_id, username, None, True, "帮助信息已发送")
            
        except Exception as e:
            error_msg = f"处理/help命令时发生错误: {str(e)}"
            self.logger.error(error_msg)
            await update.message.reply_text(f"❌ 命令执行失败\n\n{str(e)}")
    
    def handle_run_command(self, user_id: str, username: str) -> str:
        """
        处理/run命令的业务逻辑
        
        Args:
            user_id: 用户ID
            username: 用户名
            
        Returns:
            响应消息
        """
        try:
            # 检查是否有执行正在进行
            if self.execution_coordinator.is_execution_running():
                current_exec = self.execution_coordinator.get_execution_status()
                response = (
                    "⏳ 执行中\n\n"
                    f"系统正在执行任务，请稍后再试。\n\n"
                    f"执行ID: `{current_exec.execution_id}`\n"
                    f"当前阶段: {current_exec.current_stage}\n"
                    f"进度: {current_exec.progress * 100:.1f}%"
                )
                self._log_command_execution("/run", user_id, username, None, False, "执行中，拒绝新请求")
                return response
            
            # 触发手动执行
            response_initial = (
                "🚀 开始执行\n\n"
                "系统已开始执行数据收集和分析任务。\n"
                "执行完成后将自动发送报告。"
            )
            
            # 在后台线程中执行
            def execute_in_background():
                try:
                    result = self.trigger_manual_execution(user_id)
                    self._send_execution_notification(user_id, result)
                except Exception as e:
                    self.logger.error(f"后台执行失败: {str(e)}")
            
            thread = threading.Thread(target=execute_in_background, daemon=True)
            thread.start()
            
            return response_initial
            
        except Exception as e:
            error_msg = f"触发执行失败: {str(e)}"
            self.logger.error(error_msg)
            self._log_command_execution("/run", user_id, username, None, False, error_msg)
            return f"❌ 执行失败\n\n{str(e)}"
    
    def handle_status_command(self, user_id: str) -> str:
        """
        处理/status命令的业务逻辑
        
        Args:
            user_id: 用户ID
            
        Returns:
            响应消息
        """
        try:
            status = self.get_execution_status()
            
            # 构建状态消息
            response_parts = ["📊 *系统状态*\n"]
            
            # 当前执行状态
            if status.get("current_execution"):
                exec_info = status["current_execution"]
                response_parts.append(
                    f"\n*当前执行:*\n"
                    f"执行ID: `{exec_info['execution_id']}`\n"
                    f"状态: {exec_info['status']}\n"
                    f"阶段: {exec_info['current_stage']}\n"
                    f"进度: {exec_info['progress'] * 100:.1f}%\n"
                    f"开始时间: {exec_info['start_time']}"
                )
            else:
                response_parts.append("\n*当前执行:* 无")
            
            # 系统状态
            response_parts.append(
                f"\n\n*系统信息:*\n"
                f"初始化: {'是' if status['initialized'] else '否'}\n"
                f"调度器: {'运行中' if status['scheduler_running'] else '已停止'}\n"
                f"历史执行: {status['execution_history_count']} 次"
            )
            
            # 下次执行时间
            if status.get("next_execution_time"):
                response_parts.append(f"\n下次执行: {status['next_execution_time']}")
            
            # 最近执行结果
            history = self.execution_coordinator.get_execution_history(limit=1)
            if history:
                last_exec = history[-1]
                response_parts.append(
                    f"\n\n*最近执行:*\n"
                    f"时间: {last_exec.end_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
                    f"结果: {'✅ 成功' if last_exec.success else '❌ 失败'}\n"
                    f"处理项目: {last_exec.items_processed}\n"
                    f"耗时: {last_exec.duration_seconds:.1f} 秒"
                )
            
            return "\n".join(response_parts)
            
        except Exception as e:
            error_msg = f"获取状态失败: {str(e)}"
            self.logger.error(error_msg)
            return f"❌ 状态查询失败\n\n{str(e)}"
    
    def handle_help_command(self, user_id: str) -> str:
        """
        处理/help命令的业务逻辑
        
        Args:
            user_id: 用户ID
            
        Returns:
            响应消息
        """
        user_id_str = str(user_id)
        user_permissions = []
        
        if user_id_str in self._authorized_users:
            user_config = self._authorized_users[user_id_str]
            user_permissions = user_config.get("permissions", [])
        
        # 如果没有指定权限，默认所有命令都可用
        if not user_permissions:
            user_permissions = ["run", "status", "help"]
        
        help_text = [
            "🤖 *加密货币新闻分析机器人*\n",
            "*可用命令:*\n"
        ]
        
        if "run" in user_permissions:
            help_text.append(
                "/run - 立即执行一次数据收集和分析\n"
                "触发完整的工作流程，包括数据爬取、内容分析和报告生成。\n"
            )
        
        if "status" in user_permissions:
            help_text.append(
                "/status - 查询系统运行状态\n"
                "显示当前执行状态、系统信息和最近执行结果。\n"
            )
        
        help_text.append(
            "/help - 显示此帮助信息\n"
            "查看所有可用命令和使用说明。\n"
        )
        
        help_text.append(
            "\n*注意事项:*\n"
            "• 命令有速率限制，请勿频繁调用\n"
            "• 执行过程可能需要几分钟时间\n"
            "• 执行完成后会自动发送报告"
        )
        
        return "\n".join(help_text)
    
    def trigger_manual_execution(self, user_id: str) -> ExecutionResult:
        """
        触发手动执行
        
        Args:
            user_id: 触发用户ID
            
        Returns:
            执行结果
        """
        self.logger.info(f"用户 {user_id} 触发手动执行")
        
        # 调用执行协调器的run_once方法
        result = self.execution_coordinator.run_once()
        
        # 更新触发用户信息
        result.trigger_user = user_id
        
        # 记录命令执行历史
        self._log_command_execution(
            "/run",
            user_id,
            user_id,  # 使用user_id作为username
            result.execution_id,
            result.success,
            "执行完成" if result.success else f"执行失败: {'; '.join(result.errors)}"
        )
        
        return result
    
    def get_execution_status(self) -> Dict[str, Any]:
        """
        获取执行状态
        
        Returns:
            执行状态字典
        """
        return self.execution_coordinator.get_system_status()
    
    def _send_execution_notification(self, user_id: str, result: ExecutionResult) -> None:
        """
        发送执行完成通知
        
        需求16.7: 执行完成后自动通知触发用户
        
        Args:
            user_id: 用户ID
            result: 执行结果
        """
        try:
            if result.success:
                message = (
                    "✅ *执行完成*\n\n"
                    f"执行ID: `{result.execution_id}`\n"
                    f"处理项目: {result.items_processed}\n"
                    f"耗时: {result.duration_seconds:.1f} 秒\n"
                    f"报告发送: {'成功' if result.report_sent else '失败'}\n\n"
                    "报告已发送到频道。"
                )
            else:
                message = (
                    "❌ *执行失败*\n\n"
                    f"执行ID: `{result.execution_id}`\n"
                    f"耗时: {result.duration_seconds:.1f} 秒\n\n"
                    f"错误信息:\n{chr(10).join(result.errors)}"
                )
            
            # 从后台线程安全地发送通知
            self._send_message_sync(user_id, message)
            
        except Exception as e:
            self.logger.error(f"发送执行通知失败: {str(e)}")
    
    async def _send_message_to_user(self, user_id: str, message: str) -> None:
        """
        发送消息给用户
        
        Args:
            user_id: 用户ID
            message: 消息内容
        """
        try:
            if self.application:
                await self.application.bot.send_message(
                    chat_id=user_id,
                    text=message,
                    parse_mode="Markdown"
                )
        except Exception as e:
            self.logger.error(f"发送消息失败: {str(e)}")
    
    def _send_message_sync(self, user_id: str, message: str) -> None:
        """
        从同步上下文发送消息给用户（用于后台线程）
        
        Args:
            user_id: 用户ID
            message: 消息内容
        """
        try:
            if not self.application:
                self.logger.warning("应用未初始化，无法发送消息")
                return
            
            # 使用保存的事件循环引用
            loop = self._event_loop
            
            if loop and loop.is_running():
                future = asyncio.run_coroutine_threadsafe(
                    self._send_message_to_user(user_id, message),
                    loop
                )
                # 等待最多10秒
                future.result(timeout=10)
            else:
                self.logger.warning("事件循环未运行，无法发送消息")
                
        except Exception as e:
            self.logger.error(f"同步发送消息失败: {str(e)}")
    
    def _log_command_execution(
        self,
        command: str,
        user_id: str,
        username: str,
        execution_id: Optional[str],
        success: bool,
        response_message: str
    ) -> None:
        """
        记录命令执行历史
        
        需求16.8: 记录所有手动触发的执行历史和触发用户信息
        
        Args:
            command: 命令名称
            user_id: 用户ID
            username: 用户名
            execution_id: 执行ID（如果有）
            success: 是否成功
            response_message: 响应消息
        """
        history_entry = CommandExecutionHistory(
            command=command,
            user_id=user_id,
            username=username,
            timestamp=datetime.now(),
            execution_id=execution_id,
            success=success,
            response_message=response_message
        )
        
        self.command_history.append(history_entry)
        
        # 限制历史记录数量
        if len(self.command_history) > 1000:
            self.command_history = self.command_history[-1000:]
        
        self.logger.info(
            f"命令执行记录: {command} by {username} ({user_id}), "
            f"success={success}, execution_id={execution_id}"
        )
    
    def log_command_execution(
        self,
        command: str,
        user_id: str,
        username: str,
        execution_id: Optional[str],
        success: bool,
        response_message: str
    ) -> None:
        """
        公开的命令执行日志方法（向后兼容）
        """
        self._log_command_execution(command, user_id, username, execution_id, success, response_message)
    
    def get_command_history(self, limit: int = 10) -> List[CommandExecutionHistory]:
        """
        获取命令执行历史
        
        Args:
            limit: 返回的历史记录数量
            
        Returns:
            命令执行历史列表
        """
        return self.command_history[-limit:] if limit > 0 else self.command_history


# 同步包装器
class TelegramCommandHandlerSync:
    """Telegram命令处理器同步包装器"""
    
    def __init__(
        self,
        bot_token: str,
        execution_coordinator: Any,
        config: TelegramCommandConfig
    ):
        self.handler = TelegramCommandHandler(bot_token, execution_coordinator, config)
        self._listener_thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
    
    def start_command_listener(self) -> None:
        """同步启动命令监听器"""
        if self._listener_thread and self._listener_thread.is_alive():
            return
        
        def run_listener():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self._loop.run_until_complete(self.handler.start_command_listener())
        
        self._listener_thread = threading.Thread(target=run_listener, daemon=True)
        self._listener_thread.start()
    
    def stop_command_listener(self) -> None:
        """同步停止命令监听器"""
        if self._loop:
            self.handler._stop_event.set()
            if self._listener_thread:
                self._listener_thread.join(timeout=10)


# 工具函数
def create_telegram_command_handler(
    bot_token: str,
    execution_coordinator: Any,
    config: TelegramCommandConfig
) -> TelegramCommandHandler:
    """
    创建Telegram命令处理器
    
    Args:
        bot_token: Bot Token
        execution_coordinator: 执行协调器
        config: 命令配置
        
    Returns:
        TelegramCommandHandler实例
    """
    return TelegramCommandHandler(bot_token, execution_coordinator, config)


def create_default_command_config() -> TelegramCommandConfig:
    """
    创建默认命令配置
    
    Returns:
        默认配置
    """
    return TelegramCommandConfig(
        enabled=True,
        authorized_users=[],
        execution_timeout_minutes=30,
        max_concurrent_executions=1,
        command_rate_limit={
            "max_commands_per_hour": 10,
            "cooldown_minutes": 5
        }
    )
