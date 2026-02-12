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
import os
import threading
import time
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from collections import defaultdict

from telegram import Update, BotCommand
from telegram.ext import Application, CommandHandler, ContextTypes, filters
from telegram.error import TelegramError

from ..models import TelegramCommandConfig, CommandExecutionHistory, ExecutionResult, ChatContext
from ..utils.timezone_utils import now_utc8, format_datetime_utc8


@dataclass
class CommandRateLimitState:
    """命令速率限制状态"""
    command_count: int = 0
    last_reset_time: datetime = None
    last_run_command_time: datetime = None
    
    def __post_init__(self):
        if self.last_reset_time is None:
            self.last_reset_time = now_utc8()
        if self.last_run_command_time is None:
            self.last_run_command_time = now_utc8() - timedelta(minutes=10)


class TelegramCommandHandler:
    """
    Telegram命令处理器
    
    处理用户通过Telegram发送的命令，支持手动触发系统执行。
    """
    
    def __init__(
        self,
        bot_token: str,
        execution_coordinator: Any,  # MainController实例
        config: TelegramCommandConfig,
        market_snapshot_service: Optional[Any] = None  # MarketSnapshotService实例
    ):
        """
        初始化Telegram命令处理器
        
        Args:
            bot_token: Telegram Bot Token
            execution_coordinator: 执行协调器实例
            config: Telegram命令配置
            market_snapshot_service: 市场快照服务实例（可选）
        """
        self.bot_token = bot_token
        self.execution_coordinator = execution_coordinator
        self.config = config
        self.market_snapshot_service = market_snapshot_service
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
        
        # 授权用户ID集合 (用于快速查找)
        # 需求5.1, 5.7: 存储直接的用户ID
        self._authorized_user_ids: set = set()
        
        # 待解析的用户名列表
        # 需求5.8: 存储需要解析的@username条目
        self._usernames_to_resolve: List[str] = []
        
        # 用户名缓存 (username -> user_id mapping)
        # 需求6.3: 缓存用户名到user_id的映射以避免重复API调用
        self._username_cache: Dict[str, str] = {}
        
        self._load_authorized_users()
        
        self.logger.info("Telegram命令处理器初始化完成")
    
    def _load_authorized_users(self) -> None:
        """
        加载授权用户列表
        
        需求5.1: 从TELEGRAM_AUTHORIZED_USERS环境变量读取授权用户
        需求5.2: 解析逗号分隔的条目列表
        需求5.3: 在Bot初始化时解析并加载所有条目到内存
        需求5.6: 解析期间修剪每个条目的空白字符
        需求5.7: 数字条目视为用户ID
        需求5.8: 以"@"开头的条目视为用户名
        需求5.9: 既不是数字也不以"@"开头的条目记录警告并跳过
        """
        # 读取环境变量
        authorized_users_str = os.getenv('TELEGRAM_AUTHORIZED_USERS', '')
        
        if not authorized_users_str:
            # 需求5.4: 环境变量为空或未设置时记录警告
            self.logger.warning("No authorized users configured in TELEGRAM_AUTHORIZED_USERS")
            self._authorized_user_ids = set()
            self._usernames_to_resolve = []
            return
        
        # 解析逗号分隔的条目
        user_ids = set()
        usernames_to_resolve = []
        
        for entry in authorized_users_str.split(','):
            # 需求5.6: 修剪空白字符
            entry = entry.strip()
            
            if not entry:
                continue
            
            # 需求5.7: 数字条目视为直接用户ID
            if entry.isdigit():
                user_ids.add(entry)
                self.logger.debug(f"Added user ID: {entry}")
            # 需求5.8: 以"@"开头的条目视为用户名
            elif entry.startswith('@'):
                usernames_to_resolve.append(entry)
                self.logger.debug(f"Added username for resolution: {entry}")
            else:
                # 需求5.9: 无效条目记录警告并跳过
                self.logger.warning(f"Invalid entry in TELEGRAM_AUTHORIZED_USERS: {entry}")
        
        # 存储直接用户ID
        self._authorized_user_ids = user_ids
        
        # 存储待解析的用户名列表（供任务2.2使用）
        self._usernames_to_resolve = usernames_to_resolve
        
        self.logger.info(
            f"Loaded {len(self._authorized_user_ids)} direct user IDs and "
            f"{len(self._usernames_to_resolve)} usernames to resolve from TELEGRAM_AUTHORIZED_USERS"
        )
    async def _resolve_username(self, username: str) -> Optional[str]:
        """
        Resolve a Telegram username to user_id using Bot API

        需求6.1: 使用Telegram Bot API将用户名解析为user_id

        Args:
            username: Telegram username (with or without @ prefix)

        Returns:
            User ID as string, or None if resolution fails
        """
        # Remove @ prefix if present
        username_clean = username.lstrip('@')

        self.logger.info(f"Attempting to resolve username: @{username_clean}")

        try:
            # Use getChat API to resolve username
            # This requires the bot to have interacted with the user before
            # or the user to have a public profile
            chat = await self.application.bot.get_chat(f"@{username_clean}")

            if chat and chat.id:
                user_id = str(chat.id)
                self.logger.info(f"Successfully resolved username @{username_clean} to user_id {user_id}")
                return user_id
            else:
                self.logger.warning(f"Could not resolve username @{username_clean}: user not found")
                return None

        except Exception as e:
            self.logger.error(f"Error resolving username @{username_clean}: {e}")
            return None

    async def _resolve_all_usernames(self) -> None:
        """
        Resolve all usernames to user IDs during initialization
        
        需求2.2: 遍历用户名条目并解析为user_id
        需求6.1: 使用Telegram Bot API将用户名解析为user_id
        需求6.2: 将解析的user_id添加到授权集合
        需求6.3: 在_username_cache中存储映射
        需求6.4: 记录解析成功
        需求6.5: 记录解析失败
        需求6.6: 出错时继续(不崩溃)
        """
        if not self._usernames_to_resolve:
            self.logger.info("No usernames to resolve")
            return
        
        self.logger.info(f"Resolving {len(self._usernames_to_resolve)} usernames...")
        
        resolved_count = 0
        failed_count = 0
        
        # 需求2.2: 遍历用户名条目
        for username in self._usernames_to_resolve:
            try:
                # 需求2.2: 为每个用户名调用_resolve_username()
                user_id = await self._resolve_username(username)
                
                if user_id:
                    # 需求6.2: 将解析的user_id添加到授权集合
                    self._authorized_user_ids.add(user_id)
                    
                    # 需求6.3: 在_username_cache中存储映射
                    self._username_cache[username] = user_id
                    
                    # 需求6.4: 记录解析成功
                    self.logger.info(f"Successfully resolved {username} to user_id {user_id}")
                    resolved_count += 1
                else:
                    # 需求6.5: 记录解析失败
                    self.logger.warning(f"Failed to resolve username {username}: user not found")
                    failed_count += 1
                    
            except Exception as e:
                # 需求6.5: 记录解析失败
                # 需求6.6: 出错时继续(不崩溃)
                self.logger.error(f"Error resolving username {username}: {e}")
                failed_count += 1
                continue
        
        # 需求2.3: 更新初始化日志
        # 计算直接ID和解析用户名的数量
        direct_ids_count = len(self._authorized_user_ids) - resolved_count
        
        self.logger.info(
            f"Username resolution complete: {resolved_count} succeeded, {failed_count} failed. "
            f"Total authorized users: {len(self._authorized_user_ids)} "
            f"({direct_ids_count} from direct IDs, {resolved_count} from resolved usernames)"
        )

    
    def is_authorized_user(self, user_id: str, username: str = None) -> bool:
            """
            验证用户是否有权限执行命令

            需求1.1, 1.2, 1.3, 2.1, 2.2, 2.3, 6.2: 验证命令发送者的权限

            Args:
                user_id: Telegram用户ID
                username: Telegram用户名（可选，仅用于日志记录）

            Returns:
                是否授权
            """
            if not self.config.enabled:
                return False

            user_id_str = str(user_id)

            # 检查用户ID是否在授权用户ID集合中
            return user_id_str in self._authorized_user_ids
    
    
    def check_rate_limit(self, user_id: str) -> tuple[bool, Optional[str]]:
        """
        检查用户是否超过速率限制（仅针对/run命令）
        
        Args:
            user_id: 用户ID
            
        Returns:
            (是否允许, 错误消息)
        """
        user_id_str = str(user_id)
        state = self._rate_limit_states[user_id_str]
        now = now_utc8()
        
        # 检查是否需要重置计数器（每小时重置）
        hours_since_reset = (now - state.last_reset_time).total_seconds() / 3600
        if hours_since_reset >= 1.0:
            state.command_count = 0
            state.last_reset_time = now
        
        # 检查是否超过每小时限制
        max_per_hour = self.config.command_rate_limit.get("max_commands_per_hour", 10)
        if state.command_count >= max_per_hour:
            return False, f"已达到每小时命令限制 ({max_per_hour} 次)，请稍后再试"
        
        # 检查冷却时间（仅针对/run命令）
        cooldown_minutes = self.config.command_rate_limit.get("cooldown_minutes", 5)
        minutes_since_last = (now - state.last_run_command_time).total_seconds() / 60
        if minutes_since_last < cooldown_minutes:
            remaining = cooldown_minutes - minutes_since_last
            return False, f"命令冷却中，请等待 {remaining:.1f} 分钟"
        
        # 更新状态（仅更新/run命令的时间戳）
        state.command_count += 1
        state.last_run_command_time = now
        
        return True, None
        return True, None
    def _extract_chat_context(self, update: Update) -> ChatContext:
        """
        Extract chat context information from Telegram update

        需求1.4, 2.4, 3.1, 3.2, 3.3: 从Telegram Update对象中提取聊天上下文信息

        Args:
            update: Telegram Update object

        Returns:
            ChatContext instance with all fields populated

        Raises:
            ValueError: If effective_user or effective_chat is missing
        """
        # Handle missing fields gracefully with error logging
        if not update.effective_user:
            self.logger.error("Cannot extract chat context: effective_user is None")
            raise ValueError("Update object missing effective_user")

        if not update.effective_chat:
            self.logger.error("Cannot extract chat context: effective_chat is None")
            raise ValueError("Update object missing effective_chat")

        user = update.effective_user
        chat = update.effective_chat

        # Extract user info
        user_id = str(user.id)
        username = user.username or user.first_name or ""

        # Extract chat info
        chat_id = str(chat.id)
        chat_type = chat.type

        # Determine is_private and is_group based on chat_type
        is_private = chat_type == "private"
        is_group = chat_type in ["group", "supergroup"]

        return ChatContext(
            user_id=user_id,
            username=username,
            chat_id=chat_id,
            chat_type=chat_type,
            is_private=is_private,
            is_group=is_group
        )

    def _log_authorization_attempt(
        self,
        command: str,
        user_id: str,
        username: str,
        chat_type: str,
        chat_id: str,
        authorized: bool,
        reason: str = None
    ) -> None:
        """
        Log authorization attempt with full context

        需求8.1, 8.2, 8.3, 8.4: 记录授权尝试的完整上下文信息

        Args:
            command: Command name (e.g., "/run", "/status", "/help")
            user_id: User ID
            username: Username
            chat_type: Type of chat (private/group/supergroup)
            chat_id: Chat ID
            authorized: Whether authorization succeeded
            reason: Reason for authorization failure (if applicable)
        """
        log_message = (
            f"Authorization attempt: command={command}, "
            f"user={username} ({user_id}), "
            f"chat_type={chat_type}, chat_id={chat_id}, "
            f"authorized={authorized}"
        )

        if reason:
            log_message += f", reason={reason}"

        if authorized:
            self.logger.info(log_message)
        else:
            self.logger.warning(log_message)


    
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
            self.application.add_handler(CommandHandler("market", self._handle_market_command))
            self.application.add_handler(CommandHandler("status", self._handle_status_command))
            self.application.add_handler(CommandHandler("help", self._handle_help_command))
            self.application.add_handler(CommandHandler("start", self._handle_help_command))
            
            # 启动应用
            await self.application.initialize()
            await self.application.start()
            
            # 需求6.6: 在接受命令之前尝试解析用户名
            # 在应用初始化后解析用户名(需要bot实例来调用API)
            await self._resolve_all_usernames()
            
            # 设置Bot命令菜单
            await self._setup_bot_commands()
            
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
    
    async def _setup_bot_commands(self) -> None:
        """
        设置Bot命令菜单
        
        在Telegram对话框中显示可用命令列表
        """
        try:
            commands = [
                BotCommand("run", "立即执行数据收集和分析"),
                BotCommand("market", "获取当前市场现状快照"),
                BotCommand("status", "查询系统运行状态"),
                BotCommand("help", "显示帮助信息")
            ]
            
            await self.application.bot.set_my_commands(commands)
            self.logger.info("Bot命令菜单设置成功")
            
        except Exception as e:
            self.logger.error(f"设置Bot命令菜单失败: {str(e)}")
    
    async def _handle_run_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
            """
            处理/run命令

            需求16.2: 实现/run命令立即触发完整工作流
            需求1.1, 1.2, 1.3, 2.1, 2.2, 2.3, 8.1, 8.2, 8.3, 8.4: 使用聊天上下文和授权日志
            """
            # Extract chat context at the start
            try:
                chat_context = self._extract_chat_context(update)
            except ValueError as e:
                self.logger.error(f"Failed to extract chat context: {e}")
                await update.message.reply_text("❌ 处理命令时发生错误")
                return

            # Extract fields from context
            user_id = chat_context.user_id
            username = chat_context.username
            chat_type = chat_context.chat_type
            chat_id = chat_context.chat_id

            self.logger.info(
                f"收到/run命令，用户: {username} ({user_id}), "
                f"聊天类型: {chat_type}, 聊天ID: {chat_id}"
            )

            try:
                # 验证权限
                if not self.is_authorized_user(user_id, username):
                    response = "❌ 权限拒绝\n\n您没有权限执行此命令。"
                    await update.message.reply_text(response)
                    # Log authorization attempt
                    self._log_authorization_attempt(
                        command="/run",
                        user_id=user_id,
                        username=username,
                        chat_type=chat_type,
                        chat_id=chat_id,
                        authorized=False,
                        reason="user not in authorized list"
                    )
                    self._log_command_execution("/run", user_id, username, None, False, response)
                    return

                # Log successful authorization
                self._log_authorization_attempt(
                    command="/run",
                    user_id=user_id,
                    username=username,
                    chat_type=chat_type,
                    chat_id=chat_id,
                    authorized=True
                )

                # 检查速率限制
                allowed, error_msg = self.check_rate_limit(user_id)
                if not allowed:
                    response = f"⏱️ 速率限制\n\n{error_msg}"
                    await update.message.reply_text(response)
                    self._log_command_execution("/run", user_id, username, None, False, response)
                    return

                # 触发执行，传递chat_id用于报告发送
                response = self.handle_run_command(user_id, username, chat_id)
                await update.message.reply_text(response, parse_mode="Markdown")

            except Exception as e:
                error_msg = f"处理/run命令时发生错误: {str(e)}"
                self.logger.error(
                    f"{error_msg}, 用户: {username} ({user_id}), "
                    f"聊天类型: {chat_type}, 聊天ID: {chat_id}"
                )
                await update.message.reply_text(f"❌ 命令执行失败\n\n{str(e)}")
    
    async def _handle_status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        处理/status命令
        
        需求16.3: 实现/status命令返回系统运行状态
        需求1.1, 1.2, 1.3, 2.1, 2.2, 2.3, 8.1, 8.2, 8.3, 8.4: 使用聊天上下文和授权日志
        """
        # Extract chat context at the start
        try:
            chat_context = self._extract_chat_context(update)
        except ValueError as e:
            self.logger.error(f"Failed to extract chat context: {e}")
            await update.message.reply_text("❌ 处理命令时发生错误")
            return

        # Extract fields from context
        user_id = chat_context.user_id
        username = chat_context.username
        chat_type = chat_context.chat_type
        chat_id = chat_context.chat_id

        self.logger.info(
            f"收到/status命令，用户: {username} ({user_id}), "
            f"聊天类型: {chat_type}, 聊天ID: {chat_id}"
        )
        
        try:
            # 验证权限
            if not self.is_authorized_user(user_id, username):
                response = "❌ 权限拒绝\n\n您没有权限执行此命令。"
                await update.message.reply_text(response)
                # Log authorization attempt
                self._log_authorization_attempt(
                    command="/status",
                    user_id=user_id,
                    username=username,
                    chat_type=chat_type,
                    chat_id=chat_id,
                    authorized=False,
                    reason="user not in authorized list"
                )
                self._log_command_execution("/status", user_id, username, None, False, response)
                return

            # Log successful authorization
            self._log_authorization_attempt(
                command="/status",
                user_id=user_id,
                username=username,
                chat_type=chat_type,
                chat_id=chat_id,
                authorized=True
            )
            
            # 获取状态
            response = self.handle_status_command(user_id)
            await update.message.reply_text(response, parse_mode="Markdown")
            self._log_command_execution("/status", user_id, username, None, True, "状态查询成功")
            
        except Exception as e:
            error_msg = f"处理/status命令时发生错误: {str(e)}"
            self.logger.error(
                f"{error_msg}, 用户: {username} ({user_id}), "
                f"聊天类型: {chat_type}, 聊天ID: {chat_id}"
            )
            await update.message.reply_text(f"❌ 命令执行失败\n\n{str(e)}")
    
    async def _handle_market_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        处理/market命令
        
        需求16.3: 实现/market命令获取并返回市场快照
        需求16.17: 使用联网AI服务获取实时市场快照
        需求16.18: 将市场快照以Telegram格式发送给用户
        需求16.19: 在失败时返回错误信息并说明失败原因
        """
        try:
            # 提取聊天上下文
            chat_context = self._extract_chat_context(update)
            user_id = chat_context.user_id
            username = chat_context.username
            chat_type = chat_context.chat_type
            chat_id = chat_context.chat_id
            
            # 权限验证
            if not self.is_authorized_user(user_id, username):
                self._log_authorization_attempt(
                    user_id=user_id,
                    username=username,
                    command="/market",
                    chat_type=chat_type,
                    chat_id=chat_id,
                    authorized=False
                )
                await update.message.reply_text("❌ 您没有权限执行此命令")
                self._log_command_execution("/market", user_id, username, None, False, "权限拒绝")
                return
            
            # 速率限制检查
            allowed, wait_message = self.check_rate_limit(user_id)
            if not allowed:
                await update.message.reply_text(f"⏱️ {wait_message}")
                self._log_command_execution("/market", user_id, username, None, False, "速率限制")
                return
            
            # 记录授权日志
            self._log_authorization_attempt(
                user_id=user_id,
                username=username,
                command="/market",
                chat_type=chat_type,
                chat_id=chat_id,
                authorized=True
            )
            
            # 发送处理中消息
            await update.message.reply_text("🔄 正在获取市场快照...")
            
            # 获取市场快照
            response = self.handle_market_command(user_id, username)
            await update.message.reply_text(response, parse_mode="Markdown")
            self._log_command_execution("/market", user_id, username, None, True, "市场快照获取成功")
            
        except Exception as e:
            error_msg = f"处理/market命令时发生错误: {str(e)}"
            self.logger.error(
                f"{error_msg}, 用户: {username} ({user_id}), "
                f"聊天类型: {chat_type}, 聊天ID: {chat_id}"
            )
            await update.message.reply_text(f"❌ 命令执行失败\n\n{str(e)}")
            self._log_command_execution("/market", user_id, username, None, False, f"错误: {str(e)}")
    
    async def _handle_help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        处理/help命令

        需求16.4: 实现/help命令返回可用命令列表
        需求1.1, 1.2, 1.3, 2.1, 2.2, 2.3, 8.1, 8.2, 8.3, 8.4: 使用聊天上下文和授权日志
        """
        # Extract chat context at the start
        try:
            chat_context = self._extract_chat_context(update)
        except ValueError as e:
            self.logger.error(f"Failed to extract chat context: {e}")
            await update.message.reply_text("❌ 处理命令时发生错误")
            return

        # Extract fields from context
        user_id = chat_context.user_id
        username = chat_context.username
        chat_type = chat_context.chat_type
        chat_id = chat_context.chat_id

        self.logger.info(
            f"收到/help命令，用户: {username} ({user_id}), "
            f"聊天类型: {chat_type}, 聊天ID: {chat_id}"
        )

        try:
            # 验证权限
            if not self.is_authorized_user(user_id, username):
                response = "❌ 权限拒绝\n\n您没有权限使用此机器人。"
                await update.message.reply_text(response)
                # Log authorization attempt
                self._log_authorization_attempt(
                    command="/help",
                    user_id=user_id,
                    username=username,
                    chat_type=chat_type,
                    chat_id=chat_id,
                    authorized=False,
                    reason="user not in authorized list"
                )
                self._log_command_execution("/help", user_id, username, None, False, response)
                return

            # Log successful authorization
            self._log_authorization_attempt(
                command="/help",
                user_id=user_id,
                username=username,
                chat_type=chat_type,
                chat_id=chat_id,
                authorized=True
            )

            # 获取帮助信息
            response = self.handle_help_command(user_id)
            await update.message.reply_text(response, parse_mode="Markdown")
            self._log_command_execution("/help", user_id, username, None, True, "帮助信息已发送")

        except Exception as e:
            error_msg = f"处理/help命令时发生错误: {str(e)}"
            self.logger.error(
                f"{error_msg}, 用户: {username} ({user_id}), "
                f"聊天类型: {chat_type}, 聊天ID: {chat_id}"
            )
            await update.message.reply_text(f"❌ 命令执行失败\n\n{str(e)}")
    
    def handle_run_command(self, user_id: str, username: str, chat_id: str) -> str:
        """
        处理/run命令的业务逻辑
        
        Args:
            user_id: 用户ID
            username: 用户名
            chat_id: 聊天ID（用于发送报告）
            
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
                "执行完成后将自动发送报告到此聊天窗口。"
            )
            
            # 在后台线程中执行
            def execute_in_background():
                try:
                    result = self.trigger_manual_execution(user_id, chat_id)
                    self._send_execution_notification(chat_id, result)
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
                    f"时间: {format_datetime_utc8(last_exec.end_time, '%Y-%m-%d %H:%M:%S')}\n"
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
        
        if "market" in user_permissions:
            help_text.append(
                "/market - 获取当前市场现状快照\n"
                "使用联网AI服务获取实时市场信息和分析。\n"
            )
        
        help_text.append(
            "\n*注意事项:*\n"
            "• 命令有速率限制，请勿频繁调用\n"
            "• 执行过程可能需要几分钟时间\n"
            "• 执行完成后会自动发送报告"
        )
        
        return "\n".join(help_text)
    
    def handle_market_command(self, user_id: str, username: str) -> str:
        """
        处理/market命令的业务逻辑
        
        需求16.3: 获取并返回当前市场现状快照
        需求16.17: 使用联网AI服务获取实时市场快照
        需求16.18: 将市场快照以Telegram格式发送给用户
        需求16.19: 在失败时返回错误信息并说明失败原因
        
        Args:
            user_id: 用户ID
            username: 用户名
            
        Returns:
            响应消息（市场快照或错误信息）
        """
        try:
            self.logger.info(f"用户 {username} ({user_id}) 请求市场快照")
            
            # 检查市场快照服务是否可用
            if self.market_snapshot_service is None:
                error_msg = "市场快照服务未配置"
                self.logger.error(error_msg)
                return f"❌ {error_msg}\n\n请确保已正确配置GROK_API_KEY环境变量。"
            
            # 获取市场快照
            snapshot_result = self.market_snapshot_service.get_market_snapshot()
            
            if not snapshot_result.success or not snapshot_result.snapshot:
                error_msg = snapshot_result.error_message or "未知错误"
                self.logger.error(f"获取市场快照失败: {error_msg}")
                return f"❌ 获取市场快照失败\n\n原因: {error_msg}"
            
            # 格式化市场快照为Telegram消息
            snapshot = snapshot_result.snapshot
            response_parts = [
                "🌐 *市场现状快照*\n",
                f"📅 获取时间: {format_datetime_utc8(snapshot.timestamp, '%Y-%m-%d %H:%M:%S')}\n",
                f"📊 数据来源: {snapshot.source}\n",
                f"⭐ 质量评分: {snapshot.quality_score:.2f}\n",
                "\n---\n",
                snapshot.content
            ]
            
            response = "\n".join(response_parts)
            
            self.logger.info(f"市场快照获取成功，长度: {len(response)} 字符")
            return response
            
        except Exception as e:
            error_msg = f"处理/market命令时发生错误: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            return f"❌ 命令执行失败\n\n{str(e)}"
    
    def trigger_manual_execution(self, user_id: str, chat_id: str = None) -> ExecutionResult:
        """
        触发手动执行
        
        Args:
            user_id: 触发用户ID
            chat_id: 触发命令的聊天ID（用于发送报告）
            
        Returns:
            执行结果
        """
        self.logger.info(f"用户 {user_id} 在聊天 {chat_id} 触发手动执行")
        
        # 调用执行协调器的trigger_manual_execution方法，传递chat_id
        result = self.execution_coordinator.trigger_manual_execution(user_id=user_id, chat_id=chat_id)
        
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
            timestamp=now_utc8(),
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
        config: TelegramCommandConfig,
        market_snapshot_service: Optional[Any] = None
    ):
        self.handler = TelegramCommandHandler(bot_token, execution_coordinator, config, market_snapshot_service)
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
    config: TelegramCommandConfig,
    market_snapshot_service: Optional[Any] = None
) -> TelegramCommandHandler:
    """
    创建Telegram命令处理器
    
    Args:
        bot_token: Bot Token
        execution_coordinator: 执行协调器
        config: 命令配置
        market_snapshot_service: 市场快照服务（可选）
        
    Returns:
        TelegramCommandHandler实例
    """
    return TelegramCommandHandler(bot_token, execution_coordinator, config, market_snapshot_service)


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
