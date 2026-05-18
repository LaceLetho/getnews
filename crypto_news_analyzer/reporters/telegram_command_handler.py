"""
Telegram命令处理器

处理用户通过Telegram发送的命令，支持手动触发系统执行。

根据需求16实现Telegram命令触发功能：
- 需求16.1: 支持通过Telegram Bot接收用户命令
- 需求16.2: 支持/analyze命令手动触发分析
- 需求16.3: 实现/status命令返回系统运行状态
- 需求16.4: 实现/help命令返回可用命令列表
- 需求16.5: 验证命令发送者的权限，只允许授权用户触发执行
- 需求16.8: 记录所有手动触发的执行历史和触发用户信息
- 需求16.10: 支持配置授权用户列表，限制命令执行权限
- 需求16.11: 未授权用户发送命令时返回权限拒绝消息

SHARED INFRASTRUCTURE — Single bot handler registering BOTH news commands
(/analyze, /market, /semantic_search, /datasource_*) AND intelligence commands
(/topic_*). Domain grouping: news → /analyze, /market, /semantic_search,
/datasource_*; intelligence → /topic_*.
"""

import asyncio
import logging
import math
import os
import hashlib
import secrets
import time
import threading
from urllib.parse import quote, urlsplit, urlunsplit
from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from collections import defaultdict

from telegram import Update, BotCommand, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler

from ..datasource_payloads import (
    DataSourcePayloadValidationError,
    TelegramDataSourceInputError,
    parse_telegram_datasource_command_json,
    validate_telegram_datasource_create_payload,
)
from ..domain.models import (
    DataSourceAlreadyExistsError,
    DataSourceInUseError,
    PrimaryLabel,
)
from ..models import (
    ChatContext,
    CommandExecutionHistory,
    SemanticSearchConfig,
    TelegramCommandConfig,
)
from ..intelligence.search import IntelligenceSearchService
from ..utils.timezone_utils import now_utc8, format_datetime_utc8


@dataclass
class CommandRateLimitState:
    """命令速率限制状态"""

    command_count: int = 0
    last_reset_time: Optional[datetime] = None
    last_analyze_command_time: Optional[datetime] = None

    def __post_init__(self):
        if self.last_reset_time is None:
            self.last_reset_time = now_utc8()
        if self.last_analyze_command_time is None:
            self.last_analyze_command_time = now_utc8() - timedelta(minutes=10)


class TelegramCommandHandler:
    """
    Telegram命令处理器

    处理用户通过Telegram发送的命令，支持手动触发系统执行。
    """

    INTEL_PAGE_SIZE = 5
    INTEL_EVIDENCE_PAGE_SIZE = 5
    INTEL_EVIDENCE_CONTEXT_WINDOW = 5
    TELEGRAM_SAFE_MESSAGE_LIMIT = 4000

    def __init__(
        self,
        bot_token: str,
        execution_coordinator: Any,  # MainController实例
        config: TelegramCommandConfig,
        market_snapshot_service: Optional[Any] = None,  # MarketSnapshotService实例
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
        self._rate_limit_states: Dict[str, CommandRateLimitState] = defaultdict(
            CommandRateLimitState
        )

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

        # Intel callback pagination state cache
        self._callback_state: Dict[str, dict] = {}

        # Telegram may retry webhook deliveries if a handler blocks too long. Track
        # in-flight and recently completed prompt revisions so one logical request
        # cannot trigger many LLM calls.
        self._active_topic_revision_keys: Set[str] = set()
        self._recent_topic_revision_results: Dict[str, Dict[str, Any]] = {}
        self._topic_revision_result_ttl_seconds = 15 * 60

        self._load_authorized_users()

        self.logger.info("Telegram命令处理器初始化完成")

    @staticmethod
    def _normalize_webhook_base_url(base_url: str) -> str:
        normalized = base_url.strip().rstrip("/")
        if not normalized:
            raise ValueError("Telegram webhook base URL不能为空")
        if not normalized.startswith(("http://", "https://")):
            normalized = f"https://{normalized}"
        return normalized

    def uses_webhook(self) -> bool:
        transport_mode = os.getenv("TELEGRAM_TRANSPORT_MODE", "").strip().lower()
        if transport_mode:
            return transport_mode == "webhook"

        return any(
            os.getenv(env_name, "").strip()
            for env_name in (
                "TELEGRAM_WEBHOOK_BASE_URL",
                "RAILWAY_PUBLIC_DOMAIN",
                "RAILWAY_STATIC_URL",
                "RAILWAY_SERVICE_CRYPTO_NEWS_ANALYSIS_URL",
            )
        )

    def get_webhook_path(self) -> str:
        path = os.getenv("TELEGRAM_WEBHOOK_PATH", "/telegram/webhook").strip()
        if not path:
            return "/telegram/webhook"
        return path if path.startswith("/") else f"/{path}"

    def get_webhook_secret_token(self) -> str:
        configured_secret = os.getenv("TELEGRAM_WEBHOOK_SECRET_TOKEN", "").strip()
        if configured_secret:
            return configured_secret

        return hashlib.sha256(f"telegram-webhook:{self.bot_token}".encode("utf-8")).hexdigest()

    def get_webhook_url(self) -> str:
        base_url = (
            os.getenv("TELEGRAM_WEBHOOK_BASE_URL", "").strip()
            or os.getenv("RAILWAY_PUBLIC_DOMAIN", "").strip()
            or os.getenv("RAILWAY_STATIC_URL", "").strip()
            or os.getenv("RAILWAY_SERVICE_CRYPTO_NEWS_ANALYSIS_URL", "").strip()
        )
        if not base_url:
            raise ValueError(
                "未配置Telegram webhook公网地址，请设置TELEGRAM_WEBHOOK_BASE_URL或Railway公网域名变量"
            )

        return f"{self._normalize_webhook_base_url(base_url)}{self.get_webhook_path()}"

    def _build_application(self, use_updater: bool = True) -> Application:
        builder = Application.builder().token(self.bot_token)
        if not use_updater:
            builder = builder.updater(None)

        application = builder.build()

        # NEWS domain commands
        self._register_news_commands(application)

        # INTELLIGENCE domain commands
        self._register_intelligence_commands(application)

        # SHARED infrastructure commands
        application.add_handler(CommandHandler("start", self._handle_start_command))
        application.add_handler(
            CallbackQueryHandler(self._handle_topic_callback_query, pattern=r"^topic:")
        )
        return application

    def _register_news_commands(self, application: Application) -> None:
        """Register NEWS domain Telegram commands.

        News commands operate on ContentItem data: analysis, semantic search,
        market snapshots, system status, token stats, and datasource management.
        """
        application.add_handler(CommandHandler("analyze", self._handle_analyze_command))
        application.add_handler(
            CommandHandler("semantic_search", self._handle_semantic_search_command)
        )
        application.add_handler(CommandHandler("market", self._handle_market_command))
        application.add_handler(CommandHandler("status", self._handle_status_command))
        application.add_handler(CommandHandler("tokens", self._handle_tokens_command))
        application.add_handler(
            CommandHandler("datasource_list", self._handle_datasource_list_command)
        )
        application.add_handler(
            CommandHandler("datasource_add", self._handle_datasource_add_command)
        )
        application.add_handler(
            CommandHandler("datasource_delete", self._handle_datasource_delete_command)
        )
        application.add_handler(CommandHandler("help", self._handle_help_command))

    def _register_intelligence_commands(self, application: Application) -> None:
        """Register INTELLIGENCE domain Telegram commands.

        Intelligence commands operate on RawIntelligenceItem and IntelligenceTopic data:
        topic creation, revision, confirmation, listing, detail, logs, merge, pause, archive.
        """
        application.add_handler(CommandHandler("topic_create", self._handle_topic_create_command))
        application.add_handler(CommandHandler("topic_revise", self._handle_topic_revise_command))
        application.add_handler(
            CommandHandler("topic_set_prompt", self._handle_topic_set_prompt_command)
        )
        application.add_handler(CommandHandler("topic_confirm", self._handle_topic_confirm_command))
        application.add_handler(CommandHandler("topic_list", self._handle_topic_list_command))
        application.add_handler(CommandHandler("topic_detail", self._handle_topic_detail_command))
        application.add_handler(CommandHandler("topic_logs", self._handle_topic_logs_command))
        application.add_handler(CommandHandler("topic_merge", self._handle_topic_merge_command))
        application.add_handler(CommandHandler("topic_pause", self._handle_topic_pause_command))
        application.add_handler(CommandHandler("topic_archive", self._handle_topic_archive_command))

    def _generate_callback_token(self) -> str:
        return secrets.token_urlsafe(8)[:10]

    def _cleanup_expired_callback_state(self) -> None:
        now = time.time()
        expired_tokens = [
            token
            for token, payload in self._callback_state.items()
            if now - float(payload.get("stored_at", 0.0)) > 900
        ]
        for token in expired_tokens:
            self._callback_state.pop(token, None)

    def _store_callback_state(self, token: str, state: dict) -> None:
        self._cleanup_expired_callback_state()
        payload = dict(state)
        payload["stored_at"] = time.time()
        self._callback_state[token] = payload

    def _get_callback_state(self, token: str) -> Optional[dict]:
        state = self._callback_state.get(token)
        if state is None:
            return None

        stored_at = float(state.get("stored_at", 0.0))
        if time.time() - stored_at > 900:
            self._callback_state.pop(token, None)
            return None

        return dict(state)

    def _is_http_url(url: str) -> bool:
        try:
            parsed = urlsplit(str(url).strip())
        except Exception:
            return False
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)

    @staticmethod
    def _normalize_telegram_username(value: str) -> Optional[str]:
        candidate = str(value or "").strip()
        if not candidate:
            return None
        if candidate.startswith("https://t.me/") or candidate.startswith("http://t.me/"):
            path = urlsplit(candidate).path.strip("/")
            candidate = path.split("/", 1)[0] if path else ""
        candidate = candidate.lstrip("@").strip("/")
        if not candidate or candidate.lstrip("-").isdigit() or candidate.startswith("+"):
            return None
        return candidate

    @staticmethod
    def _telegram_private_chat_path_id(value: str) -> Optional[str]:
        candidate = str(value or "").strip()
        if not candidate:
            return None
        if candidate.startswith("-100") and candidate[4:].isdigit():
            return candidate[4:]
        if candidate.lstrip("-").isdigit():
            stripped = candidate.lstrip("-")
            return stripped if stripped else None
        return None

    def _build_telegram_source_url(self, raw_item: Any) -> Optional[str]:
        source_url = str(getattr(raw_item, "source_url", "") or "").strip()
        if self._is_http_url(source_url):
            return source_url

        chat_ref = (
            str(getattr(raw_item, "chat_id", "") or "").strip()
            or str(getattr(raw_item, "source_id", "") or "").strip()
        )
        message_id = str(getattr(raw_item, "external_id", "") or "").strip()

        username = self._normalize_telegram_username(chat_ref)
        if username:
            if message_id:
                return f"https://t.me/{quote(username)}/{quote(message_id)}"
            return f"https://t.me/{quote(username)}"

        private_chat_id = self._telegram_private_chat_path_id(chat_ref)
        if private_chat_id and message_id:
            return f"https://t.me/c/{quote(private_chat_id)}/{quote(message_id)}"

        return None

    def _telegram_chat_id(chat_id: str) -> Any:
        chat_id_value = str(chat_id).strip()
        if chat_id_value.lstrip("-").isdigit():
            return int(chat_id_value)
        return chat_id_value

    @staticmethod
    def _escape_markdown_v1(text: str) -> str:
        """Escape user-generated content for Telegram MarkdownV1 parse mode.

        Escapes special characters that would be interpreted as formatting:
        * (bold), _ (italic), ` (code), [ ] (links).
        """
        if not isinstance(text, str):
            text = str(text)
        for char in ("\\", "`", "*", "_", "[", "]"):
            text = text.replace(char, "\\" + char)
        return text

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
        authorized_users_str = os.getenv("TELEGRAM_AUTHORIZED_USERS", "")

        user_ids: set = set()
        usernames_to_resolve: list = []

        if authorized_users_str:
            # 解析逗号分隔的条目
            for entry in authorized_users_str.split(","):
                entry = entry.strip()
                if not entry:
                    continue
                if entry.isdigit():
                    user_ids.add(entry)
                    self.logger.debug(f"Added user ID: {entry}")
                elif entry.startswith("@"):
                    usernames_to_resolve.append(entry)
                    self.logger.debug(f"Added username for resolution: {entry}")
                else:
                    self.logger.warning(f"Invalid entry in TELEGRAM_AUTHORIZED_USERS: {entry}")
        else:
            self.logger.warning("No authorized users configured in TELEGRAM_AUTHORIZED_USERS")

        # Always also populate from config.authorized_users (for programmatic/test config support)
        if self.config.authorized_users:
            try:
                for user_entry in self.config.authorized_users:
                    uid = str(user_entry.get("user_id", ""))
                    uname = str(user_entry.get("username", ""))
                    if uid.isdigit():
                        user_ids.add(uid)
                        self._authorized_users[uid] = dict(user_entry)
                    if uname and not uname.startswith("@"):
                        uname = f"@{uname}"
                    if uname:
                        usernames_to_resolve.append(uname)
                if user_ids and not authorized_users_str:
                    self.logger.info(
                        "Populated authorized users from config (env var not set): "
                        f"{len(user_ids)} IDs, {len(usernames_to_resolve)} usernames"
                    )
            except (TypeError, AttributeError):
                self.logger.debug("Skipping config.authorized_users — not iterable")

        self._authorized_user_ids = user_ids
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
        username_clean = username.lstrip("@")

        self.logger.info(f"Attempting to resolve username: @{username_clean}")

        try:
            # Use getChat API to resolve username
            # This requires the bot to have interacted with the user before
            # or the user to have a public profile
            chat = await self.application.bot.get_chat(f"@{username_clean}")

            if chat and chat.id:
                user_id = str(chat.id)
                self.logger.info(
                    f"Successfully resolved username @{username_clean} to user_id {user_id}"
                )
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

    def is_authorized_user(self, user_id: str, username: Optional[str] = None) -> bool:
        """
        验证用户是否有权限执行命令

        需求1.1, 1.2, 1.3, 2.1, 2.2, 2.3, 6.2: 验证命令发送者的权限

        增强功能：如果用户名在待解析列表中，自动学习 username → user_id 映射

        Args:
            user_id: Telegram用户ID
            username: Telegram用户名（可选，用于自动学习映射）

        Returns:
            是否授权
        """
        if not self.config.enabled:
            return False

        user_id_str = str(user_id)

        # 检查用户ID是否在授权用户ID集合中
        if user_id_str in self._authorized_user_ids:
            return True

        # 如果提供了 username，检查是否在待解析列表中
        if username:
            username_with_at = f"@{username}" if not username.startswith("@") else username

            # 如果这个 username 在待解析列表中，自动学习映射
            if username_with_at in self._usernames_to_resolve:
                self.logger.info(
                    f"Auto-learning username mapping: {username_with_at} → {user_id_str}"
                )
                # 添加到授权用户集合
                self._authorized_user_ids.add(user_id_str)
                # 缓存映射关系
                self._username_cache[username_with_at] = user_id_str
                # 从待解析列表中移除
                self._usernames_to_resolve.remove(username_with_at)

                return True

        return False

    def check_rate_limit(self, user_id: str) -> tuple[bool, Optional[str]]:
        """
        检查用户是否超过速率限制（仅针对/analyze命令）

        Args:
            user_id: 用户ID

        Returns:
            (是否允许, 错误消息)
        """
        user_id_str = str(user_id)
        state = self._rate_limit_states[user_id_str]
        now = now_utc8()

        if state.last_reset_time is None:
            state.last_reset_time = now
        if state.last_analyze_command_time is None:
            state.last_analyze_command_time = now - timedelta(minutes=10)

        # 检查是否需要重置计数器（每小时重置）
        hours_since_reset = (now - state.last_reset_time).total_seconds() / 3600
        if hours_since_reset >= 1.0:
            state.command_count = 0
            state.last_reset_time = now

        # 检查是否超过每小时限制
        max_per_hour = self.config.command_rate_limit.get("max_commands_per_hour", 10)
        if state.command_count >= max_per_hour:
            return False, f"已达到每小时命令限制 ({max_per_hour} 次)，请稍后再试"

        # 检查冷却时间（仅针对/analyze命令）
        cooldown_seconds = self.config.command_rate_limit.get("cooldown_seconds", 1)
        seconds_since_last = (now - state.last_analyze_command_time).total_seconds()
        if seconds_since_last < cooldown_seconds:
            remaining = cooldown_seconds - seconds_since_last
            return False, f"命令冷却中，请等待 {remaining:.1f} 秒"

        # 更新状态（仅更新/analyze命令的时间戳）
        state.command_count += 1
        state.last_analyze_command_time = now

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
            is_group=is_group,
        )

    def _log_authorization_attempt(
        self,
        command: str,
        user_id: str,
        username: str,
        chat_type: str,
        chat_id: str,
        authorized: bool,
        reason: Optional[str] = None,
    ) -> None:
        """
        Log authorization attempt with full context

        需求8.1, 8.2, 8.3, 8.4: 记录授权尝试的完整上下文信息

        Args:
            command: Command name (e.g., "/analyze", "/status", "/help")
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
            self.application = self._build_application(use_updater=True)

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
            commands = []
            # Shared
            commands.append(BotCommand("start", "获取您的用户ID和授权状态"))
            commands.append(BotCommand("help", "显示帮助信息"))
            # News domain
            commands.append(BotCommand("analyze", "分析消息，可指定小时数如/analyze 24"))
            commands.append(
                BotCommand("semantic_search", "语义搜索，如/semantic_search 24 BTC adoption")
            )
            commands.append(BotCommand("market", "获取当前市场现状快照"))
            commands.append(BotCommand("status", "查询系统运行状态"))
            commands.append(BotCommand("tokens", "查看LLM token使用统计"))
            commands.append(BotCommand("datasource_list", "查看数据源列表"))
            commands.append(BotCommand("datasource_add", "添加数据源"))
            commands.append(BotCommand("datasource_delete", "删除数据源"))
            # Intelligence domain
            commands.append(BotCommand("topic_create", "从主题创建研究草稿"))
            commands.append(BotCommand("topic_revise", "修订主题提示词"))
            commands.append(BotCommand("topic_set_prompt", "手动设置主题提示词"))
            commands.append(BotCommand("topic_confirm", "确认并激活主题"))
            commands.append(BotCommand("topic_list", "查看主题列表"))
            commands.append(BotCommand("topic_detail", "查看主题详情和发现"))
            commands.append(BotCommand("topic_logs", "查看主题运行日志"))
            commands.append(BotCommand("topic_merge", "合并主题发现"))
            commands.append(BotCommand("topic_pause", "暂停主题"))
            commands.append(BotCommand("topic_archive", "归档主题"))

            await self.application.bot.set_my_commands(commands)
            self.logger.info("Bot命令菜单设置成功")

        except Exception as e:
            self.logger.error(f"设置Bot命令菜单失败: {str(e)}")

    async def initialize_webhook(self) -> str:
        """初始化Telegram webhook模式。"""
        if self.application:
            self.logger.warning("Telegram webhook已初始化")
            return self.get_webhook_url()

        self.logger.info("初始化Telegram webhook模式")
        self.application = self._build_application(use_updater=False)
        self._event_loop = asyncio.get_running_loop()

        await self.application.initialize()
        await self.application.start()
        await self._resolve_all_usernames()
        await self._setup_bot_commands()

        webhook_url = self.get_webhook_url()
        secret_token = self.get_webhook_secret_token()

        await self.application.bot.set_webhook(
            url=webhook_url,
            allowed_updates=Update.ALL_TYPES,
            secret_token=secret_token,
        )

        self.logger.info(f"Telegram webhook已注册到: {self.get_webhook_path()}")
        return webhook_url

    async def shutdown_webhook(self) -> None:
        """关闭Telegram webhook模式。"""
        if not self.application:
            return

        try:
            self.logger.info("停止Telegram webhook模式")
            await self.application.bot.delete_webhook(drop_pending_updates=False)
            await self.application.stop()
            await self.application.shutdown()
            self.application = None
            self.logger.info("Telegram webhook模式已停止")
        except Exception as e:
            self.logger.error(f"停止Telegram webhook模式失败: {str(e)}")

    async def handle_webhook_update(
        self,
        update_data: Dict[str, Any],
        secret_token: Optional[str] = None,
    ) -> None:
        """处理来自Webhook的Telegram更新。"""
        if not self.application:
            raise RuntimeError("Telegram webhook尚未初始化")

        expected_secret = self.get_webhook_secret_token()
        if secret_token != expected_secret:
            raise PermissionError("Invalid Telegram webhook secret token")

        update = Update.de_json(data=update_data, bot=self.application.bot)
        await self.application.process_update(update)

    async def _handle_analyze_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """
        处理/analyze命令

        分析指定时间窗口内的消息并发送报告。

        Args:
            update: Telegram Update对象
            context: Telegram Bot context对象
        """
        # Extract chat context at the start
        try:
            chat_context = self._extract_chat_context(update)
        except ValueError as e:
            self.logger.error(f"Failed to extract chat context: {e}")
            message = getattr(update, "effective_message", None) or update.message
            if message is not None:
                await message.reply_text("❌ 处理命令时发生错误")
            return

        # Extract fields from context
        user_id = chat_context.user_id
        username = chat_context.username
        chat_type = chat_context.chat_type
        chat_id = chat_context.chat_id

        self.logger.info(
            f"收到/analyze命令，用户: {username} ({user_id}), "
            f"聊天类型: {chat_type}, 聊天ID: {chat_id}, "
            f"参数: {context.args}"
        )

        try:
            # 验证权限
            if not self.is_authorized_user(user_id, username):
                response = "❌ 权限拒绝\n\n您没有权限执行此命令。"
                await update.message.reply_text(response)
                self._log_authorization_attempt(
                    command="/analyze",
                    user_id=user_id,
                    username=username,
                    chat_type=chat_type,
                    chat_id=chat_id,
                    authorized=False,
                    reason="user not in authorized list",
                )
                self._log_command_execution("/analyze", user_id, username, None, False, response)
                return

            # Log successful authorization
            self._log_authorization_attempt(
                command="/analyze",
                user_id=user_id,
                username=username,
                chat_type=chat_type,
                chat_id=chat_id,
                authorized=True,
            )

            allowed, error_msg = self.check_rate_limit(user_id)
            if not allowed:
                response = f"⏱️ 速率限制\n\n{error_msg}"
                await update.message.reply_text(response)
                self._log_command_execution("/analyze", user_id, username, None, False, response)
                return

            # 解析参数 - 从 context.args 获取小时数
            hours = None
            if context.args:
                try:
                    hours = int(context.args[0])
                except ValueError:
                    await update.message.reply_text(
                        "❌ 参数错误\n\n请输入有效的小时数，例如：/analyze 24"
                    )
                    return

            # 调用业务逻辑
            response = self.handle_analyze_command(user_id, username, chat_id, hours)
            await update.message.reply_text(response, parse_mode="Markdown")

        except Exception as e:
            error_msg = f"处理/analyze命令时发生错误: {str(e)}"
            self.logger.error(
                f"{error_msg}, 用户: {username} ({user_id}), "
                f"聊天类型: {chat_type}, 聊天ID: {chat_id}"
            )
            await update.message.reply_text(f"❌ 命令执行失败\n\n{str(e)}")

    async def _handle_semantic_search_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """
        处理/semantic_search命令

        语法: /semantic_search <hours> <topic>
        """
        try:
            chat_context = self._extract_chat_context(update)
        except ValueError as e:
            self.logger.error(f"Failed to extract chat context: {e}")
            await update.message.reply_text("❌ 处理命令时发生错误")
            return

        user_id = chat_context.user_id
        username = chat_context.username
        chat_type = chat_context.chat_type
        chat_id = chat_context.chat_id
        message = getattr(update, "effective_message", None) or update.message

        if message is None:
            self.logger.error("/semantic_search update has no effective message")
            return

        args = [str(arg).strip() for arg in (context.args or [])]

        self.logger.info(
            f"收到/semantic_search命令，用户: {username} ({user_id}), "
            f"聊天类型: {chat_type}, 聊天ID: {chat_id}, 参数: {context.args}"
        )

        try:
            if not self.is_authorized_user(user_id, username):
                response = "❌ 权限拒绝\n\n您没有权限执行此命令。"
                await update.message.reply_text(response)
                self._log_authorization_attempt(
                    command="/semantic_search",
                    user_id=user_id,
                    username=username,
                    chat_type=chat_type,
                    chat_id=chat_id,
                    authorized=False,
                    reason="user not in authorized list",
                )
                self._log_command_execution(
                    "/semantic_search", user_id, username, None, False, response
                )
                return

            self._log_authorization_attempt(
                command="/semantic_search",
                user_id=user_id,
                username=username,
                chat_type=chat_type,
                chat_id=chat_id,
                authorized=True,
            )

            allowed, error_msg = self.check_rate_limit(user_id)
            if not allowed:
                response = f"⏱️ 速率限制\n\n{error_msg}"
                await update.message.reply_text(response)
                self._log_command_execution(
                    "/semantic_search", user_id, username, None, False, response
                )
                return

            if len(args) < 2:
                await message.reply_text(
                    "❌ 参数错误\n\n用法: /semantic_search <hours> <topic>\n"
                    "示例: /semantic_search 24 BTC adoption"
                )
                return

            try:
                hours = int(args[0])
            except (TypeError, ValueError):
                await message.reply_text(
                    "❌ 参数错误\n\n请输入有效的小时数，例如：/semantic_search 24 BTC adoption"
                )
                return

            topic = " ".join(args[1:]).strip()
            if hours <= 0 or not topic:
                await message.reply_text(
                    "❌ 参数错误\n\n用法: /semantic_search <hours> <topic>\n"
                    "示例: /semantic_search 24 BTC adoption"
                )
                return

            try:
                config_manager = getattr(self.execution_coordinator, "config_manager", None)
                get_semantic_search_config = getattr(
                    config_manager, "get_semantic_search_config", None
                )
                semantic_search_config = (
                    get_semantic_search_config()
                    if callable(get_semantic_search_config)
                    else SemanticSearchConfig()
                )
                topic = semantic_search_config.validate_query(topic)
            except ValueError as e:
                await message.reply_text(f"❌ 参数错误\n\n{str(e)}")
                return

            response = self.handle_semantic_search_command(user_id, username, chat_id, hours, topic)
            await message.reply_text(response, parse_mode="Markdown")

        except Exception as e:
            error_msg = f"处理/semantic_search命令时发生错误: {str(e)}"
            self.logger.error(
                f"{error_msg}, 用户: {username} ({user_id}), 聊天类型: {chat_type}, 聊天ID: {chat_id}"
            )
            await update.message.reply_text(f"❌ 命令执行失败\n\n{str(e)}")

    async def _handle_status_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
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
                    reason="user not in authorized list",
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
                authorized=True,
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

    async def _handle_market_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
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
                    authorized=False,
                )
                await update.message.reply_text("❌ 您没有权限执行此命令")
                self._log_command_execution("/market", user_id, username, None, False, "权限拒绝")
                return

            # /market命令不需要速率限制检查，因为它只是读取缓存的市场快照

            # 记录授权日志
            self._log_authorization_attempt(
                user_id=user_id,
                username=username,
                command="/market",
                chat_type=chat_type,
                chat_id=chat_id,
                authorized=True,
            )

            # 发送处理中消息
            await update.message.reply_text("🔄 正在获取市场快照...")

            # 获取市场快照
            response = self.handle_market_command(user_id, username)
            # 不使用 Markdown 解析，避免特殊字符导致的解析错误
            await update.message.reply_text(response)
            self._log_command_execution(
                "/market", user_id, username, None, True, "市场快照获取成功"
            )

        except Exception as e:
            error_msg = f"处理/market命令时发生错误: {str(e)}"
            self.logger.error(
                f"{error_msg}, 用户: {username} ({user_id}), "
                f"聊天类型: {chat_type}, 聊天ID: {chat_id}"
            )
            await update.message.reply_text(f"❌ 命令执行失败\n\n{str(e)}")
            self._log_command_execution(
                "/market", user_id, username, None, False, f"错误: {str(e)}"
            )

    async def _handle_help_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
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
                    reason="user not in authorized list",
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
                authorized=True,
            )

            # 获取帮助信息
            response = self.handle_help_command(user_id)
            await update.message.reply_text(response)
            self._log_command_execution("/help", user_id, username, None, True, "帮助信息已发送")

        except Exception as e:
            error_msg = f"处理/help命令时发生错误: {str(e)}"
            self.logger.error(
                f"{error_msg}, 用户: {username} ({user_id}), "
                f"聊天类型: {chat_type}, 聊天ID: {chat_id}"
            )
            await update.message.reply_text(f"❌ 命令执行失败\n\n{str(e)}")

    async def _handle_tokens_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """
        处理/tokens命令 - 显示LLM token使用统计
        """
        try:
            chat_context = self._extract_chat_context(update)
        except ValueError as e:
            self.logger.error(f"Failed to extract chat context: {e}")
            await update.message.reply_text("❌ 处理命令时发生错误")
            return

        user_id = chat_context.user_id
        username = chat_context.username
        chat_type = chat_context.chat_type
        chat_id = chat_context.chat_id

        self.logger.info(
            f"收到/tokens命令，用户: {username} ({user_id}), "
            f"聊天类型: {chat_type}, 聊天ID: {chat_id}"
        )

        try:
            # 验证权限
            if not self.is_authorized_user(user_id, username):
                response = "❌ 权限拒绝\n\n您没有权限使用此机器人。"
                await update.message.reply_text(response)
                self._log_authorization_attempt(
                    command="/tokens",
                    user_id=user_id,
                    username=username,
                    chat_type=chat_type,
                    chat_id=chat_id,
                    authorized=False,
                    reason="user not in authorized list",
                )
                self._log_command_execution("/tokens", user_id, username, None, False, response)
                return

            # Log successful authorization
            self._log_authorization_attempt(
                command="/tokens",
                user_id=user_id,
                username=username,
                chat_type=chat_type,
                chat_id=chat_id,
                authorized=True,
            )

            # 获取token使用统计
            response = self.handle_tokens_command()
            await update.message.reply_text(response, parse_mode="Markdown")
            self._log_command_execution("/tokens", user_id, username, None, True, "Token统计已发送")

        except Exception as e:
            error_msg = f"处理/tokens命令时发生错误: {str(e)}"
            self.logger.error(
                f"{error_msg}, 用户: {username} ({user_id}), "
                f"聊天类型: {chat_type}, 聊天ID: {chat_id}"
            )
            await update.message.reply_text(f"❌ 命令执行失败\n\n{str(e)}")

    async def _handle_datasource_list_command(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        try:
            chat_context = self._extract_chat_context(update)
        except ValueError as e:
            self.logger.error(f"Failed to extract chat context: {e}")
            await update.message.reply_text("❌ 处理命令时发生错误")
            return

        user_id = chat_context.user_id
        username = chat_context.username
        chat_type = chat_context.chat_type
        chat_id = chat_context.chat_id

        self.logger.info(
            f"收到/datasource_list命令，用户: {username} ({user_id}), "
            f"聊天类型: {chat_type}, 聊天ID: {chat_id}"
        )

        try:
            if not self.is_authorized_user(user_id, username):
                response = "❌ 权限拒绝\n\n您没有权限执行此命令。"
                await update.message.reply_text(response)
                self._log_authorization_attempt(
                    command="/datasource_list",
                    user_id=user_id,
                    username=username,
                    chat_type=chat_type,
                    chat_id=chat_id,
                    authorized=False,
                    reason="user not in authorized list",
                )
                self._log_command_execution(
                    "/datasource_list",
                    user_id,
                    username,
                    None,
                    False,
                    response,
                )
                return

            self._log_authorization_attempt(
                command="/datasource_list",
                user_id=user_id,
                username=username,
                chat_type=chat_type,
                chat_id=chat_id,
                authorized=True,
            )

            purpose = None
            context_args = getattr(context, "args", None)
            if isinstance(context_args, (list, tuple)) and context_args:
                raw_purpose = str(context_args[0]).strip().lower()
                purpose = raw_purpose or None
            responses = self.handle_datasource_list_messages(purpose=purpose)
            for response in responses:
                await update.message.reply_text(response)
            self._log_command_execution(
                "/datasource_list",
                user_id,
                username,
                None,
                True,
                "数据源列表查询成功",
            )

        except Exception as e:
            error_msg = f"处理/datasource_list命令时发生错误: {str(e)}"
            self.logger.error(
                f"{error_msg}, 用户: {username} ({user_id}), "
                f"聊天类型: {chat_type}, 聊天ID: {chat_id}"
            )
            await update.message.reply_text(f"❌ 命令执行失败\n\n{str(e)}")

    async def _handle_datasource_add_command(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        payload: Optional[Dict[str, Any]] = None

        try:
            chat_context = self._extract_chat_context(update)
        except ValueError as e:
            self.logger.error(f"Failed to extract chat context: {e}")
            await update.message.reply_text("❌ 处理命令时发生错误")
            return

        user_id = chat_context.user_id
        username = chat_context.username
        chat_type = chat_context.chat_type
        chat_id = chat_context.chat_id

        command_text = str(getattr(update.message, "text", "") or "").strip()
        self.logger.info(
            f"收到/datasource_add命令，用户: {username} ({user_id}), "
            f"聊天类型: {chat_type}, 聊天ID: {chat_id}, 文本: {command_text}"
        )

        try:
            if not self.is_authorized_user(user_id, username):
                response = "❌ 权限拒绝\n\n您没有权限执行此命令。"
                await update.message.reply_text(response)
                self._log_authorization_attempt(
                    command="/datasource_add",
                    user_id=user_id,
                    username=username,
                    chat_type=chat_type,
                    chat_id=chat_id,
                    authorized=False,
                    reason="user not in authorized list",
                )
                self._log_command_execution(
                    "/datasource_add",
                    user_id,
                    username,
                    None,
                    False,
                    response,
                )
                return

            self._log_authorization_attempt(
                command="/datasource_add",
                user_id=user_id,
                username=username,
                chat_type=chat_type,
                chat_id=chat_id,
                authorized=True,
            )

            payload = parse_telegram_datasource_command_json(command_text, "/datasource_add")
            validated_payload = validate_telegram_datasource_create_payload(payload)

            repository = getattr(self.execution_coordinator, "datasource_repository", None)
            if repository is None:
                raise ValueError("数据源仓储未初始化")

            try:
                saved_datasource = repository.save(validated_payload.to_domain_datasource())
            except DataSourceAlreadyExistsError:
                datasource_key = (
                    f"{validated_payload.purpose}:"
                    f"{validated_payload.source_type}:"
                    f"{validated_payload.name}"
                )
                response = "⚠️ 数据源已存在\n\n" f"数据源 '{datasource_key}' 已存在，不能重复创建。"
                self._log_expected_command_outcome(
                    command="/datasource_add",
                    user_id=user_id,
                    username=username,
                    chat_type=chat_type,
                    chat_id=chat_id,
                    outcome="duplicate datasource",
                )
                await update.message.reply_text(response)
                self._log_command_execution(
                    "/datasource_add",
                    user_id,
                    username,
                    None,
                    False,
                    response,
                )
                return
            except ValueError as exc:
                if "uniqueness" in str(exc).lower():
                    datasource_key = (
                        f"{validated_payload.purpose}:"
                        f"{validated_payload.source_type}:"
                        f"{validated_payload.name}"
                    )
                    response = (
                        "⚠️ 数据源已存在\n\n" f"数据源 '{datasource_key}' 已存在，不能重复创建。"
                    )
                    self._log_expected_command_outcome(
                        command="/datasource_add",
                        user_id=user_id,
                        username=username,
                        chat_type=chat_type,
                        chat_id=chat_id,
                        outcome="duplicate datasource",
                    )
                    await update.message.reply_text(response)
                    self._log_command_execution(
                        "/datasource_add",
                        user_id,
                        username,
                        None,
                        False,
                        response,
                    )
                    return
                raise

            tags_text = ", ".join(saved_datasource.tags) if saved_datasource.tags else "（无标签）"
            response = (
                "✅ 数据源创建成功\n\n"
                f"ID: {saved_datasource.id}\n"
                f"用途: {saved_datasource.purpose}\n"
                f"类型: {saved_datasource.source_type}\n"
                f"名称: {saved_datasource.name}\n"
                f"标签: {tags_text}"
            )
            await update.message.reply_text(response)
            self._log_command_execution(
                "/datasource_add",
                user_id,
                username,
                None,
                True,
                response,
            )

        except TelegramDataSourceInputError as exc:
            response = self._format_datasource_add_error_response(str(exc), payload)
            self._log_expected_command_outcome(
                command="/datasource_add",
                user_id=user_id,
                username=username,
                chat_type=chat_type,
                chat_id=chat_id,
                outcome="malformed datasource command payload",
            )
            await update.message.reply_text(response)
            self._log_command_execution(
                "/datasource_add",
                user_id,
                username,
                None,
                False,
                response,
            )
        except DataSourcePayloadValidationError as exc:
            response = self._format_datasource_add_error_response(str(exc), payload)
            self._log_expected_command_outcome(
                command="/datasource_add",
                user_id=user_id,
                username=username,
                chat_type=chat_type,
                chat_id=chat_id,
                outcome="datasource payload validation failure",
            )
            await update.message.reply_text(response)
            self._log_command_execution(
                "/datasource_add",
                user_id,
                username,
                None,
                False,
                response,
            )
        except Exception as e:
            error_msg = f"处理/datasource_add命令时发生错误: {str(e)}"
            self.logger.error(
                f"{error_msg}, 用户: {username} ({user_id}), "
                f"聊天类型: {chat_type}, 聊天ID: {chat_id}"
            )
            await update.message.reply_text(f"❌ 命令执行失败\n\n{str(e)}")

    async def _handle_datasource_delete_command(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        try:
            chat_context = self._extract_chat_context(update)
        except ValueError as e:
            self.logger.error(f"Failed to extract chat context: {e}")
            await update.message.reply_text("❌ 处理命令时发生错误")
            return

        user_id = chat_context.user_id
        username = chat_context.username
        chat_type = chat_context.chat_type
        chat_id = chat_context.chat_id

        self.logger.info(
            f"收到/datasource_delete命令，用户: {username} ({user_id}), "
            f"聊天类型: {chat_type}, 聊天ID: {chat_id}, 参数: {context.args}"
        )

        try:
            if not self.is_authorized_user(user_id, username):
                response = "❌ 权限拒绝\n\n您没有权限执行此命令。"
                await update.message.reply_text(response)
                self._log_authorization_attempt(
                    command="/datasource_delete",
                    user_id=user_id,
                    username=username,
                    chat_type=chat_type,
                    chat_id=chat_id,
                    authorized=False,
                    reason="user not in authorized list",
                )
                self._log_command_execution(
                    "/datasource_delete",
                    user_id,
                    username,
                    None,
                    False,
                    response,
                )
                return

            self._log_authorization_attempt(
                command="/datasource_delete",
                user_id=user_id,
                username=username,
                chat_type=chat_type,
                chat_id=chat_id,
                authorized=True,
            )

            if not context.args or not str(context.args[0]).strip():
                response = "❌ 参数错误\n\n请输入数据源ID，例如：/datasource_delete ds-123"
                self._log_expected_command_outcome(
                    command="/datasource_delete",
                    user_id=user_id,
                    username=username,
                    chat_type=chat_type,
                    chat_id=chat_id,
                    outcome="missing datasource delete id",
                )
                await update.message.reply_text(response)
                self._log_command_execution(
                    "/datasource_delete",
                    user_id,
                    username,
                    None,
                    False,
                    response,
                )
                return

            datasource_id = str(context.args[0]).strip()
            repository = getattr(self.execution_coordinator, "datasource_repository", None)
            if repository is None:
                raise ValueError("数据源仓储未初始化")

            try:
                deleted = self.execution_coordinator.datasource_repository.delete(datasource_id)
            except DataSourceInUseError as exc:
                active_job_text = ", ".join(exc.active_job_ids) if exc.active_job_ids else "未知"
                response = (
                    "⚠️ 删除冲突\n\n"
                    f"数据源 ID {datasource_id} 当前不能删除，因为匹配的入库任务仍处于活跃状态。\n"
                    f"活跃任务: {active_job_text}"
                )
                self._log_expected_command_outcome(
                    command="/datasource_delete",
                    user_id=user_id,
                    username=username,
                    chat_type=chat_type,
                    chat_id=chat_id,
                    outcome="datasource delete blocked by active ingestion job",
                )
                await update.message.reply_text(response)
                self._log_command_execution(
                    "/datasource_delete",
                    user_id,
                    username,
                    None,
                    False,
                    response,
                )
                return

            if not deleted:
                response = f"❌ 未找到数据源\n\n未找到 ID 为 {datasource_id} 的数据源。"
                self._log_expected_command_outcome(
                    command="/datasource_delete",
                    user_id=user_id,
                    username=username,
                    chat_type=chat_type,
                    chat_id=chat_id,
                    outcome="datasource delete target not found",
                )
                await update.message.reply_text(response)
                self._log_command_execution(
                    "/datasource_delete",
                    user_id,
                    username,
                    None,
                    False,
                    response,
                )
                return

            response = f"✅ 数据源删除成功\n\n已删除数据源 ID: {datasource_id}"
            await update.message.reply_text(response)
            self._log_command_execution(
                "/datasource_delete",
                user_id,
                username,
                None,
                True,
                response,
            )

        except Exception as e:
            error_msg = f"处理/datasource_delete命令时发生错误: {str(e)}"
            self.logger.error(
                f"{error_msg}, 用户: {username} ({user_id}), "
                f"聊天类型: {chat_type}, 聊天ID: {chat_id}"
            )
            await update.message.reply_text(f"❌ 命令执行失败\n\n{str(e)}")

    async def _handle_start_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """
        处理/start命令 - 显示用户ID和基本信息
        """
        try:
            chat_context = self._extract_chat_context(update)
            user_id = chat_context.user_id
            username = chat_context.username

            is_authorized = self.is_authorized_user(user_id, username)

            response = [
                "👋 *欢迎使用加密货币新闻分析机器人*\n",
                "📋 *您的用户信息:*",
                f"• User ID: `{user_id}`",
                f"• Username: @{username}" if username else "• Username: (未设置)",
                f"• 授权状态: {'✅ 已授权' if is_authorized else '❌ 未授权'}\n",
            ]

            if not is_authorized:
                response.append(
                    "⚠️ 您当前没有使用权限。\n" "请将您的 User ID 发送给管理员以获取访问权限。"
                )
            else:
                response.append(
                    "✅ 您已获得授权，可以使用所有命令。\n输入 /help 查看可用命令列表。"
                )

            await update.message.reply_text("\n".join(response), parse_mode="Markdown")

        except Exception as e:
            self.logger.error(f"处理/start命令时发生错误: {str(e)}")
            await update.message.reply_text("❌ 命令执行失败")

    def handle_analyze_command(
        self, user_id: str, username: str, chat_id: str, hours: Optional[int] = None
    ) -> str:
        """
        处理/analyze命令的业务逻辑

        Args:
            user_id: 用户ID
            username: 用户名
            chat_id: 聊天ID（用于发送报告）
            hours: 分析时间窗口（小时数），可选

        Returns:
            响应消息
        """
        try:
            if self.execution_coordinator.is_execution_running():
                current_exec = self.execution_coordinator.get_execution_status()
                response = (
                    "⏳ 执行中\n\n"
                    f"系统正在执行任务，请稍后再试。\n\n"
                    f"执行ID: `{current_exec.execution_id}`\n"
                    f"当前阶段: {current_exec.current_stage}\n"
                    f"进度: {current_exec.progress * 100:.1f}%"
                )
                self._log_command_execution(
                    "/analyze", user_id, username, None, False, "执行中，拒绝新请求"
                )
                return response

            effective_hours = None
            window_description = None

            analysis_config = self.execution_coordinator.config_manager.get_analysis_config()
            max_hours = analysis_config.get("max_analysis_window_hours", 24)

            if hours is not None:
                effective_hours = min(max(hours, 1), max_hours)
                window_description = f"最近 {effective_hours} 小时"
            else:
                try:
                    recipient_key = self.execution_coordinator._resolve_manual_recipient_key(
                        chat_id,
                        manual_source="telegram",
                    )
                    last_analysis_time = (
                        self.execution_coordinator.data_manager.get_last_successful_analysis_time(
                            recipient_key
                        )
                    )
                    if last_analysis_time:
                        if last_analysis_time.tzinfo is None:
                            last_analysis_time = last_analysis_time.replace(tzinfo=timezone.utc)

                        now = datetime.now(last_analysis_time.tzinfo)
                        hours_since_last = (now - last_analysis_time).total_seconds() / 3600
                        bounded_hours = max(1, math.ceil(max(hours_since_last, 0)))
                        effective_hours = min(bounded_hours, max_hours)
                        if bounded_hours > max_hours:
                            window_description = f"最近 {effective_hours} 小时"
                        else:
                            window_description = f"自上次成功运行以来（约 {effective_hours} 小时）"
                        self.logger.info(
                            f"上次分析时间: {last_analysis_time}, 距今 {hours_since_last:.1f} 小时, "
                            f"使用时间窗口: {effective_hours} 小时"
                        )
                    else:
                        effective_hours = max_hours
                        window_description = f"最近 {effective_hours} 小时"
                        self.logger.info(f"没有找到上次分析记录，使用默认时间窗口: {max_hours}小时")
                except Exception as e:
                    self.logger.warning(f"获取上次分析时间失败: {str(e)}，使用默认{max_hours}小时")
                    effective_hours = max_hours
                    window_description = f"最近 {effective_hours} 小时"

            if effective_hours is None or effective_hours <= 0:
                effective_hours = 1

            if not window_description:
                window_description = f"最近 {effective_hours} 小时"

            response_initial = (
                f"🔍 开始分析\n\n"
                f"系统将分析{window_description}的消息。\n"
                "执行完成后将自动发送报告到此聊天窗口。"
            )

            def execute_in_background():
                try:
                    self._execute_analyze_and_notify(
                        user_id,
                        username,
                        chat_id,
                        effective_hours,
                        window_description,
                    )
                except Exception as e:
                    self.logger.error(f"后台分析执行失败: {str(e)}")

            thread = threading.Thread(target=execute_in_background, daemon=True)
            thread.start()

            return response_initial

        except Exception as e:
            error_msg = f"触发分析失败: {str(e)}"
            self.logger.error(error_msg)
            self._log_command_execution("/analyze", user_id, username, None, False, error_msg)
            return f"❌ 执行失败\n\n{str(e)}"

    def handle_semantic_search_command(
        self,
        user_id: str,
        username: str,
        chat_id: str,
        hours: int,
        topic: str,
    ) -> str:
        """
        处理/semantic_search命令的业务逻辑
        """
        try:
            semantic_search_service = self._get_semantic_search_service()
            if semantic_search_service is None:
                response = "❌ 语义搜索服务未初始化\n\n请先完成语义搜索模块配置。"
                self._log_command_execution(
                    "/semantic_search",
                    user_id,
                    username,
                    None,
                    False,
                    "语义搜索服务未初始化",
                )
                return response

            response_initial = (
                "🔎 开始语义搜索\n\n"
                f"系统将搜索最近 {hours} 小时内与「{topic}」相关的内容。\n"
                "执行完成后将自动发送报告到此聊天窗口。"
            )

            def execute_in_background():
                try:
                    self._execute_semantic_search_and_notify(
                        user_id,
                        username,
                        chat_id,
                        hours,
                        topic,
                        semantic_search_service,
                    )
                except Exception as e:
                    self.logger.error(f"后台语义搜索执行失败: {str(e)}")

            thread = threading.Thread(target=execute_in_background, daemon=True)
            thread.start()

            return response_initial

        except Exception as e:
            error_msg = f"触发语义搜索失败: {str(e)}"
            self.logger.error(error_msg)
            self._log_command_execution(
                "/semantic_search", user_id, username, None, False, error_msg
            )
            return f"❌ 执行失败\n\n{str(e)}"

    def _get_semantic_search_service(self) -> Optional[Any]:
        service = getattr(self.execution_coordinator, "semantic_search_service", None)
        if service is None:
            getter = getattr(self.execution_coordinator, "get_semantic_search_service", None)
            if callable(getter):
                service = getter()
        return service

    def _get_intelligence_repository(self) -> Optional[Any]:
        repository = getattr(self.execution_coordinator, "intelligence_repository", None)
        if repository is None:
            getter = getattr(self.execution_coordinator, "get_intelligence_repository", None)
            if callable(getter):
                repository = getter()
        return repository

    def _get_intelligence_search_service(self) -> Optional[Any]:
        service = getattr(self.execution_coordinator, "intelligence_search_service", None)
        if service is None:
            getter = getattr(self.execution_coordinator, "get_intelligence_search_service", None)
            if callable(getter):
                service = getter()

        if service is not None:
            return service

        repository = self._get_intelligence_repository()
        embedding_service = getattr(self.execution_coordinator, "embedding_service", None)
        storage_config = getattr(self.execution_coordinator, "storage_config", None)
        if repository is None or embedding_service is None or storage_config is None:
            return None

        return IntelligenceSearchService(
            embedding_service=embedding_service,
            intelligence_repository=repository,
            storage_config=storage_config,
        )

    def _get_topic_prompt_workflow_service(self) -> Optional[Any]:
        service = getattr(self.execution_coordinator, "topic_prompt_workflow_service", None)
        if service is not None:
            return service
        repository = self._get_intelligence_repository()
        if repository is None:
            return None
        llm_analyzer = getattr(self.execution_coordinator, "llm_analyzer", None)
        llm_client = getattr(llm_analyzer, "client", None) if llm_analyzer else None
        model_name = getattr(llm_analyzer, "model", "") if llm_analyzer else ""
        if llm_client is None:
            return None
        from ..intelligence.topic_prompts import TopicPromptWorkflowService

        service = TopicPromptWorkflowService(
            repository=repository,
            llm_client=llm_client,
            model_name=model_name,
        )
        setattr(self.execution_coordinator, "topic_prompt_workflow_service", service)
        return service

    def _get_topic_finding_merge_service(self) -> Optional[Any]:
        service = getattr(self.execution_coordinator, "topic_finding_merge_service", None)
        if service is not None:
            return service
        repository = self._get_intelligence_repository()
        if repository is None:
            return None
        llm_analyzer = getattr(self.execution_coordinator, "llm_analyzer", None)
        llm_client = getattr(llm_analyzer, "client", None) if llm_analyzer else None
        model_name = getattr(llm_analyzer, "model", "") if llm_analyzer else ""
        if llm_client is None:
            return None
        from ..intelligence.topic_findings import TopicFindingMergeService

        service = TopicFindingMergeService(
            intelligence_repository=repository,
            llm_client=llm_client,
            model_name=model_name,
        )
        setattr(self.execution_coordinator, "topic_finding_merge_service", service)
        return service

    def _build_topic_revision_key(self, user_id: str, topic_id: str, feedback: str) -> str:
        normalized_feedback = " ".join(str(feedback or "").split())
        digest = hashlib.sha256(normalized_feedback.encode("utf-8")).hexdigest()[:16]
        return f"{user_id}:{topic_id}:{digest}"

    def _get_recent_topic_revision_response(self, key: str) -> Optional[str]:
        now = time.monotonic()
        expired_keys = [
            item_key
            for item_key, item in self._recent_topic_revision_results.items()
            if float(item.get("expires_at", 0.0)) <= now
        ]
        for item_key in expired_keys:
            self._recent_topic_revision_results.pop(item_key, None)

        cached = self._recent_topic_revision_results.get(key)
        if cached is None:
            return None
        response = cached.get("response")
        return str(response) if response else None

    def _remember_topic_revision_response(self, key: str, response: str) -> None:
        self._recent_topic_revision_results[key] = {
            "response": response,
            "expires_at": time.monotonic() + self._topic_revision_result_ttl_seconds,
        }

    async def _reply_text_with_timeout(
        self,
        msg: Any,
        text: str,
        parse_mode: Optional[str] = None,
        timeout_seconds: float = 8.0,
    ) -> None:
        kwargs: Dict[str, Any] = {}
        if parse_mode:
            kwargs["parse_mode"] = parse_mode
        await asyncio.wait_for(msg.reply_text(text, **kwargs), timeout=timeout_seconds)

    async def _run_topic_revise_background(
        self,
        msg: Any,
        service: Any,
        topic_id: str,
        feedback: str,
        user_id: str,
        username: str,
        request_key: str,
    ) -> None:
        try:
            self.logger.info(
                "开始后台处理/topic_revise: topic_id=%s user_id=%s request_key=%s",
                topic_id,
                user_id,
                request_key,
            )
            prompt = await asyncio.to_thread(
                service.revise_prompt,
                topic_id=topic_id,
                feedback=feedback,
                activated_by=username,
            )
            esc = self._escape_markdown_v1
            trunc_prompt = esc(prompt.prompt_text[:500])
            suffix = "..." if len(prompt.prompt_text) > 500 else ""
            response = (
                f"✏️ *提示词已修订*\n\n"
                f"*Topic ID*: `{esc(topic_id)}`\n"
                f"*Version*: {esc(prompt.prompt_version)}\n\n"
                f"*修订后提示词*:\n{trunc_prompt}{suffix}\n\n"
                f"审查后使用 `/topic_confirm {esc(topic_id)}` 激活"
            )
            self._remember_topic_revision_response(request_key, response)
            self._log_command_execution("/topic_revise", user_id, username, topic_id, True, "")
            try:
                await self._reply_text_with_timeout(msg, response, parse_mode="Markdown")
            except Exception as send_error:
                self.logger.error(
                    "发送/topic_revise成功响应失败: topic_id=%s version=%s error=%s",
                    topic_id,
                    getattr(prompt, "prompt_version", "unknown"),
                    send_error,
                )
        except Exception as e:
            self.logger.exception("后台处理/topic_revise失败: topic_id=%s error=%s", topic_id, e)
            self._log_command_execution("/topic_revise", user_id, username, topic_id, False, str(e))
            try:
                await self._reply_text_with_timeout(msg, f"❌ 修订失败: {str(e)}")
            except Exception as send_error:
                self.logger.error("发送/topic_revise失败响应失败: %s", send_error)
        finally:
            self._active_topic_revision_keys.discard(request_key)

    def _normalize_intelligence_primary_label(self, label: Optional[str]) -> Optional[str]:
        normalized = str(label or "").strip()
        if not normalized:
            return None

        for item in PrimaryLabel:
            if normalized == item.value or normalized.lower() == item.name.lower():
                return item.value
        return normalized

    async def _handle_topic_create_command(self, update: Any, context: Any) -> None:
        try:
            msg = update.effective_message or update.message
            if msg is None:
                return
            user_id = str(update.effective_user.id if update.effective_user else "unknown")
            username = update.effective_user.username if update.effective_user else "unknown"

            if not self.is_authorized_user(user_id, username):
                await msg.reply_text("\u274c 权限拒绝")
                return

            allowed, error_msg = self.check_rate_limit(user_id)
            if not allowed:
                await msg.reply_text(f"\u23f1\ufe0f 速率限制\n\n{error_msg}")
                return

            args = [str(arg).strip() for arg in (context.args or []) if str(arg).strip()]
            if not args:
                await msg.reply_text(
                    "用法: /topic_create <主题描述>\n示例: /topic_create Bitcoin ETF flow analysis"
                )
                return

            theme = " ".join(args).strip()
            service = self._get_topic_prompt_workflow_service()
            if service is None:
                await msg.reply_text("\u274c 主题服务未初始化")
                return

            prompt = service.create_draft_topic(theme=theme, created_by=username)
            topic_id = prompt.intelligence_topic_id
            esc = self._escape_markdown_v1
            esc_theme = esc(theme)
            trunc_prompt = esc(prompt.prompt_text[:500])
            suffix = "..." if len(prompt.prompt_text) > 500 else ""
            response = (
                f"\U0001f4dd *主题草稿已创建*\n\n"
                f"*主题*: {esc_theme}\n"
                f"*Topic ID*: `{esc(topic_id)}`\n\n"
                f"*生成的提示词*:\n{trunc_prompt}{suffix}\n\n"
                f"*下一步*:\n"
                f"\u2022 `/topic_revise {esc(topic_id)} <反馈>` 让AI修订\n"
                f"\u2022 `/topic_set_prompt {esc(topic_id)} <完整提示词>` 手动替换\n"
                f"\u2022 `/topic_confirm {esc(topic_id)}` 确认激活"
            )
            await msg.reply_text(response, parse_mode="Markdown")
            self._log_command_execution("/topic_create", user_id, username, topic_id, True, "")
        except Exception as e:
            self.logger.error(f"处理/topic_create命令时发生错误: {e}")
            try:
                await msg.reply_text(f"\u274c 创建失败: {str(e)}")
            except Exception:
                pass

    async def _handle_topic_revise_command(self, update: Any, context: Any) -> None:
        try:
            msg = update.effective_message or update.message
            if msg is None:
                return
            user_id = str(update.effective_user.id if update.effective_user else "unknown")
            username = update.effective_user.username if update.effective_user else "unknown"

            if not self.is_authorized_user(user_id, username):
                await msg.reply_text("\u274c 权限拒绝")
                return

            args = [str(arg).strip() for arg in (context.args or []) if str(arg).strip()]
            if len(args) < 2:
                await msg.reply_text(
                    "用法: /topic_revise <topic_id> <反馈>\n"
                    "示例: /topic_revise abc123 增加对DeFi的关注"
                )
                return

            topic_id = args[0]
            feedback = " ".join(args[1:])

            service = self._get_topic_prompt_workflow_service()
            if service is None:
                await msg.reply_text("\u274c 主题服务未初始化")
                return

            request_key = self._build_topic_revision_key(user_id, topic_id, feedback)
            cached_response = self._get_recent_topic_revision_response(request_key)
            if cached_response:
                await msg.reply_text(cached_response, parse_mode="Markdown")
                self.logger.info(
                    "忽略重复/topic_revise请求并返回缓存结果: topic_id=%s user_id=%s request_key=%s",
                    topic_id,
                    user_id,
                    request_key,
                )
                return

            if request_key in self._active_topic_revision_keys:
                await msg.reply_text("⏳ 相同修订请求正在处理中，请稍后查看结果。")
                self.logger.info(
                    "忽略重复进行中的/topic_revise请求: topic_id=%s user_id=%s request_key=%s",
                    topic_id,
                    user_id,
                    request_key,
                )
                return

            self._active_topic_revision_keys.add(request_key)
            try:
                await self._reply_text_with_timeout(
                    msg,
                    "⏳ 已收到修订请求，正在后台处理。完成后会发送结果。",
                )
            except Exception as ack_error:
                self.logger.warning(
                    "发送/topic_revise接收确认失败，仍继续后台处理: topic_id=%s error=%s",
                    topic_id,
                    ack_error,
                )

            asyncio.create_task(
                self._run_topic_revise_background(
                    msg=msg,
                    service=service,
                    topic_id=topic_id,
                    feedback=feedback,
                    user_id=user_id,
                    username=username,
                    request_key=request_key,
                )
            )
        except Exception as e:
            self.logger.error(f"处理/topic_revise命令时发生错误: {e}")
            try:
                await msg.reply_text(f"\u274c 修订失败: {str(e)}")
            except Exception:
                pass

    async def _handle_topic_set_prompt_command(self, update: Any, context: Any) -> None:
        try:
            msg = update.effective_message or update.message
            if msg is None:
                return
            user_id = str(update.effective_user.id if update.effective_user else "unknown")
            username = update.effective_user.username if update.effective_user else "unknown"

            if not self.is_authorized_user(user_id, username):
                await msg.reply_text("\u274c 权限拒绝")
                return

            args = [str(arg).strip() for arg in (context.args or []) if str(arg).strip()]
            if len(args) < 2:
                await msg.reply_text("用法: /topic_set_prompt <topic_id> <完整提示词>")
                return

            topic_id = args[0]
            prompt_text = " ".join(args[1:])

            service = self._get_topic_prompt_workflow_service()
            if service is None:
                await msg.reply_text("\u274c 主题服务未初始化")
                return

            prompt = service.replace_prompt_manual(
                topic_id=topic_id, prompt_text=prompt_text, created_by=username
            )
            esc = self._escape_markdown_v1
            response = (
                f"\U0001f4dd *提示词已手动设置*\n\n"
                f"*Topic ID*: `{esc(topic_id)}`\n"
                f"*Version*: {esc(prompt.prompt_version)}\n\n"
                f"审查后使用 `/topic_confirm {esc(topic_id)}` 激活"
            )
            await msg.reply_text(response, parse_mode="Markdown")
            self._log_command_execution("/topic_set_prompt", user_id, username, topic_id, True, "")
        except Exception as e:
            self.logger.error(f"处理/topic_set_prompt命令时发生错误: {e}")
            try:
                await msg.reply_text(f"\u274c 设置失败: {str(e)}")
            except Exception:
                pass

    async def _handle_topic_confirm_command(self, update: Any, context: Any) -> None:
        try:
            msg = update.effective_message or update.message
            if msg is None:
                return
            user_id = str(update.effective_user.id if update.effective_user else "unknown")
            username = update.effective_user.username if update.effective_user else "unknown"

            if not self.is_authorized_user(user_id, username):
                await msg.reply_text("\u274c 权限拒绝")
                return

            args = [str(arg).strip() for arg in (context.args or []) if str(arg).strip()]
            if not args:
                await msg.reply_text("用法: /topic_confirm <topic_id>")
                return

            topic_id = args[0]
            service = self._get_topic_prompt_workflow_service()
            if service is None:
                await msg.reply_text("\u274c 主题服务未初始化")
                return

            repository = self._get_intelligence_repository()
            if repository is None:
                await msg.reply_text("\u274c 仓储未初始化")
                return

            drafts = repository.list_topic_prompts(topic_id, status="draft", limit=1)
            if not drafts:
                await msg.reply_text(
                    "\u274c 未找到待确认的草稿提示词。请先使用 /topic_create 或 /topic_revise"
                )
                return

            draft = drafts[0]
            prompt = service.confirm_prompt(
                topic_id=topic_id,
                prompt_version_id=draft.id,
                activated_by=username,
            )
            esc = self._escape_markdown_v1
            response = (
                f"\u2705 *主题已激活*\n\n"
                f"*Topic ID*: `{esc(topic_id)}`\n"
                f"*提示词版本*: {esc(prompt.prompt_version)}\n\n"
                f"研究将在下次采集周期自动运行。"
            )
            await msg.reply_text(response, parse_mode="Markdown")
            self._log_command_execution("/topic_confirm", user_id, username, topic_id, True, "")
        except Exception as e:
            self.logger.error(f"处理/topic_confirm命令时发生错误: {e}")
            try:
                await msg.reply_text(f"\u274c 确认失败: {str(e)}")
            except Exception:
                pass

    async def _handle_topic_merge_command(self, update: Any, context: Any) -> None:
        try:
            msg = update.effective_message or update.message
            if msg is None:
                return
            user_id = str(update.effective_user.id if update.effective_user else "unknown")
            username = update.effective_user.username if update.effective_user else "unknown"
            chat_id = str(msg.chat_id) if hasattr(msg, "chat_id") else ""

            if not self.is_authorized_user(user_id, username):
                await msg.reply_text("\u274c 权限拒绝")
                return

            args = [str(arg).strip() for arg in (context.args or []) if str(arg).strip()]
            if not args:
                await msg.reply_text("用法: /topic_merge <topic_id>")
                return

            topic_id = args[0]
            merge_service = self._get_topic_finding_merge_service()
            if merge_service is None:
                await msg.reply_text("\u274c 合并服务未初始化")
                return

            repository = self._get_intelligence_repository()
            if repository is None:
                await msg.reply_text("\u274c 仓储未初始化")
                return

            active_prompt = repository.get_active_topic_prompt(topic_id)
            if active_prompt is None:
                await msg.reply_text("\u274c 未找到活跃提示词。请先激活主题。")
                return

            from ..intelligence.topic_findings import MergePreviewError

            preview = merge_service.create_merge_preview(
                topic_id=topic_id,
                prompt_version_id=active_prompt.id,
                created_by=username,
            )

            esc = self._escape_markdown_v1
            preview_data = preview.preview_payload
            topic_name = esc(preview_data.get("topic_name", topic_id))
            merge_summary = esc(str(preview_data.get("merge_summary", ""))[:300])
            findings_count = len(preview_data.get("merged_findings", []))
            expires_at_text = (
                preview.expires_at.strftime("%Y-%m-%d %H:%M UTC") if preview.expires_at else "N/A"
            )

            text = (
                f"\U0001f500 *合并预览*\n\n"
                f"*主题*: {topic_name}\n"
                f"*合并发现数*: {findings_count}\n"
                f"*摘要*: {merge_summary}\n\n"
                f"*Preview ID*: `{esc(preview.id)}`\n"
                f"*过期时间*: {expires_at_text}"
            )

            if self.application is None:
                await msg.reply_text(text, parse_mode="Markdown")
                return

            token = self._generate_callback_token()
            self._store_callback_state(
                token,
                {
                    "chat_id": chat_id,
                    "user_id": user_id,
                    "kind": "topic_merge",
                    "preview_id": preview.id,
                    "topic_id": topic_id,
                },
            )

            from telegram import InlineKeyboardButton, InlineKeyboardMarkup

            keyboard = [
                [
                    InlineKeyboardButton(
                        "\u2705 接受合并", callback_data=f"topic:merge:accept:{token}"
                    )
                ]
            ]
            markup = InlineKeyboardMarkup(keyboard)
            await msg.reply_text(text, reply_markup=markup, parse_mode="Markdown")
            self._log_command_execution("/topic_merge", user_id, username, topic_id, True, "")
        except MergePreviewError as e:
            await msg.reply_text(f"\u274c 合并失败: {str(e)}")
        except Exception as e:
            self.logger.error(f"处理/topic_merge命令时发生错误: {e}")
            try:
                await msg.reply_text(f"\u274c 合并失败: {str(e)}")
            except Exception:
                pass

    async def _handle_topic_pause_command(self, update: Any, context: Any) -> None:
        try:
            msg = update.effective_message or update.message
            if msg is None:
                return
            user_id = str(update.effective_user.id if update.effective_user else "unknown")
            username = update.effective_user.username if update.effective_user else "unknown"

            if not self.is_authorized_user(user_id, username):
                await msg.reply_text("\u274c 权限拒绝")
                return

            args = [str(arg).strip() for arg in (context.args or []) if str(arg).strip()]
            if not args:
                await msg.reply_text("用法: /topic_pause <topic_id>")
                return

            topic_id = args[0]
            repository = self._get_intelligence_repository()
            if repository is None:
                await msg.reply_text("\u274c 仓储未初始化")
                return

            topic = repository.get_topic_by_id(topic_id)
            if topic is None:
                await msg.reply_text("\u274c 主题未找到")
                return

            topic.lifecycle_status = "paused"
            repository.save_topic(topic)
            esc = self._escape_markdown_v1
            await msg.reply_text(
                f"\u23f8\ufe0f 主题已暂停: `{esc(topic_id)}`", parse_mode="Markdown"
            )
            self._log_command_execution("/topic_pause", user_id, username, topic_id, True, "")
        except Exception as e:
            self.logger.error(f"处理/topic_pause命令时发生错误: {e}")
            try:
                await msg.reply_text(f"\u274c 暂停失败: {str(e)}")
            except Exception:
                pass

    async def _handle_topic_archive_command(self, update: Any, context: Any) -> None:
        try:
            msg = update.effective_message or update.message
            if msg is None:
                return
            user_id = str(update.effective_user.id if update.effective_user else "unknown")
            username = update.effective_user.username if update.effective_user else "unknown"

            if not self.is_authorized_user(user_id, username):
                await msg.reply_text("\u274c 权限拒绝")
                return

            args = [str(arg).strip() for arg in (context.args or []) if str(arg).strip()]
            if not args:
                await msg.reply_text("用法: /topic_archive <topic_id>")
                return

            topic_id = args[0]
            repository = self._get_intelligence_repository()
            if repository is None:
                await msg.reply_text("\u274c 仓储未初始化")
                return

            topic = repository.get_topic_by_id(topic_id)
            if topic is None:
                await msg.reply_text("\u274c 主题未找到")
                return

            topic.lifecycle_status = "archived"
            repository.save_topic(topic)
            esc = self._escape_markdown_v1
            await msg.reply_text(f"\U0001f4e6 主题已归档: `{esc(topic_id)}`", parse_mode="Markdown")
            self._log_command_execution("/topic_archive", user_id, username, topic_id, True, "")
        except Exception as e:
            self.logger.error(f"处理/topic_archive命令时发生错误: {e}")
            try:
                await msg.reply_text(f"\u274c 归档失败: {str(e)}")
            except Exception:
                pass

    async def _handle_topic_list_command(self, update: Any, context: Any) -> None:
        try:
            msg = update.effective_message or update.message
            if msg is None:
                self.logger.error("/topic_list update has no effective message")
                return
            user_id = str(update.effective_user.id if update.effective_user else "unknown")
            username = update.effective_user.username if update.effective_user else "unknown"

            if not self.is_authorized_user(user_id, username):
                await msg.reply_text("\u274c 权限拒绝")
                return

            chat_id = str(msg.chat_id) if hasattr(msg, "chat_id") else ""
            args = [str(arg).strip() for arg in (context.args or []) if str(arg).strip()]
            page = 1
            if args and args[0].isdigit():
                page = max(1, int(args[0]))
            payload = self.handle_topic_list_command(user_id, username, page, return_markup=True)
            if self.application is None:
                await msg.reply_text(str(payload.get("text", payload)))
                return
            token = self._generate_callback_token()
            page_num = int(payload.get("page", 1))
            total_pages = int(payload.get("total_pages", 1))
            keyboard: List[List[InlineKeyboardButton]] = []
            if page_num < total_pages:
                keyboard.append(
                    [
                        InlineKeyboardButton(
                            "更多",
                            callback_data=f"topic:list:p:{token}:{page_num + 1}",
                        ),
                    ]
                )
            markup = InlineKeyboardMarkup(keyboard) if keyboard else None
            sent_msg = await msg.reply_text(
                str(payload.get("text", "")),
                reply_markup=markup,
                parse_mode="Markdown",
            )
            state_payload = dict(payload.get("state_data", {}))
            state_payload.update(
                {
                    "kind": "topic_list",
                    "page": page_num,
                    "total_pages": total_pages,
                    "total": int(payload.get("total", 0)),
                    "chat_id": chat_id,
                    "user_id": user_id,
                    "sent_message_ids": [int(sent_msg.message_id)],
                }
            )
            self._store_callback_state(token, state_payload)
        except Exception as e:
            self.logger.error(f"处理/topic_list命令时发生错误: {e}")

    def handle_topic_list_command(
        self, user_id: str, username: str, page: int = 1, return_markup: bool = False
    ) -> Any:
        try:
            repository = self._get_intelligence_repository()
            if repository is None:
                return "❌ 情报仓储未初始化"
            page_size = 20
            offset = (page - 1) * page_size
            topics = repository.list_topics(is_active=True, limit=page_size + 1, offset=offset)
            total = repository.count_topics(is_active=True)
            has_more = len(topics) > page_size
            topics = topics[:page_size]
            if not topics and page == 1:
                return "📚 暂无活跃主题\n\n使用 /topic_create <主题描述> 创建新主题。"
            if not topics:
                return {
                    "text": f"📚 第 {page} 页无主题。",
                    "page": page,
                    "total_pages": 1,
                    "total": 0,
                    "state_data": {},
                }
            esc = self._escape_markdown_v1
            lines = ["📚 情报主题\n"]
            for i, topic in enumerate(topics, 1):
                findings = repository.list_topic_findings(topic.id) or []
                finding_count = len(findings)
                updated = topic.updated_at.strftime("%Y-%m-%d") if topic.updated_at else "-"
                lines.append(
                    f"{i}. {esc(topic.name)}\n"
                    f"   发现: {finding_count} | 最近更新: {updated}\n"
                    f"   /topic\\_detail {esc(topic.id)}"
                )
            total_pages = max(1, (total + page_size - 1) // page_size)
            if return_markup:
                footer = f"\n📄 共 {total} 个主题 | 第 {page}/{total_pages} 页"
                lines.append(footer)
                return {
                    "text": "\n".join(lines),
                    "page": page,
                    "total_pages": total_pages,
                    "total": total,
                    "state_data": {},
                }
            if has_more:
                lines.append(
                    f"\n📄 共 {total} 个主题 | 第 {page}/{total_pages} 页\n"
                    f"👉 更多: /topic\\_list {page + 1}"
                )
            else:
                lines.append(f"\n📄 共 {total} 个主题 | 第 {page}/{total_pages} 页")
            self._log_command_execution("/topic_list", user_id, username, None, True, "")
            return "\n".join(lines)
        except Exception as e:
            return f"❌ 查询失败: {str(e)}"

    async def _handle_topic_detail_command(self, update: Any, context: Any) -> None:
        try:
            msg = update.effective_message or update.message
            if msg is None:
                return
            user_id = str(update.effective_user.id if update.effective_user else "unknown")
            username = update.effective_user.username if update.effective_user else "unknown"

            if not self.is_authorized_user(user_id, username):
                await msg.reply_text("\u274c 权限拒绝")
                return

            parts = (msg.text or "").split(maxsplit=1)
            topic_id = parts[1].strip() if len(parts) > 1 else ""
            if not topic_id:
                await msg.reply_text("用法: /topic_detail <topic_id>")
                return
            response = self.handle_topic_detail_command(user_id, username, topic_id)
            await msg.reply_text(response, parse_mode="Markdown")
        except Exception as e:
            self.logger.error(f"处理/topic_detail命令时发生错误: {e}")

    def handle_topic_detail_command(self, user_id: str, username: str, topic_id: str) -> str:
        try:
            repository = self._get_intelligence_repository()
            if repository is None:
                return "❌ 情报仓储未初始化"
            topic = repository.get_topic_by_id(topic_id)
            if topic is None:
                return "❌ 主题未找到"
            esc = self._escape_markdown_v1
            lines = [f"🔬 {esc(topic.name)}\n"]
            if topic.description:
                lines.append(f"*描述*\n{esc(topic.description)}\n")
            if topic.enriched_summary:
                lines.append(f"*📋 深度摘要*\n{esc(topic.enriched_summary)}\n")
            if topic.methods:
                lines.append(f"*🛠 方法*\n{esc(topic.methods)}\n")
            if topic.vulnerabilities:
                lines.append(f"*🧨 漏洞/内幕*\n{esc(topic.vulnerabilities)}\n")
            if topic.latest_findings:
                lines.append("*🆕 最新发现*")
                for finding in topic.latest_findings:
                    lines.append(f"  • {esc(str(finding))}")
                lines.append("")
            self._log_command_execution("/topic_detail", user_id, username, topic_id, True, "")
            return "\n".join(lines)
        except Exception as e:
            return f"❌ 查询失败: {str(e)}"

    async def _handle_topic_logs_command(self, update: Any, context: Any) -> None:
        try:
            msg = update.effective_message or update.message
            if msg is None:
                return
            user_id = str(update.effective_user.id if update.effective_user else "unknown")
            username = update.effective_user.username if update.effective_user else "unknown"

            if not self.is_authorized_user(user_id, username):
                await msg.reply_text("\u274c 权限拒绝")
                return

            parts = (msg.text or "").split(maxsplit=1)
            topic_id = parts[1].strip() if len(parts) > 1 else ""
            response = self.handle_topic_logs_command(user_id, username, topic_id or None)
            await msg.reply_text(response, parse_mode="Markdown")
        except Exception as e:
            self.logger.error(f"处理/topic_logs命令时发生错误: {e}")

    def handle_topic_logs_command(
        self, user_id: str, username: str, topic_id: Optional[str] = None
    ) -> str:
        try:
            repository = self._get_intelligence_repository()
            if repository is None:
                return "❌ 情报仓储未初始化"
            logs = repository.list_topic_run_logs(topic_id=topic_id, limit=20, offset=0)
            if not logs:
                return "🧾 暂无运行日志"
            esc = self._escape_markdown_v1
            lines = ["🧾 Topic Run Logs\n"]
            for log in logs:
                created = log.created_at.strftime("%m-%d %H:%M") if log.created_at else ""
                status_icon = {"success": "✅", "skipped": "⏭️", "failed": "❌"}.get(
                    log.status, "?"
                )
                run_type_label = {
                    "auto_link": "自动链接",
                    "enrich": "主题累积",
                    "converge": "主题收敛",
                }.get(log.run_type, log.run_type)
                lines.append(f"{created} {status_icon} [{run_type_label}] {log.status}")
                if log.message:
                    lines.append(f"  {esc(log.message[:200])}")
            self._log_command_execution("/topic_logs", user_id, username, None, True, "")
            return "\n".join(lines)
        except Exception as e:
            return f"❌ 查询失败: {str(e)}"

    async def _handle_topic_callback_query(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        callback_query = getattr(update, "callback_query", None)
        if callback_query is None:
            return

        try:
            user = callback_query.from_user
            message = callback_query.message
            chat = message.chat if message is not None else None
            user_id = str(getattr(user, "id", ""))
            username = getattr(user, "username", None) or getattr(user, "first_name", "") or ""
            chat_id = str(getattr(chat, "id", "")) if chat is not None else ""

            if not self.is_authorized_user(user_id, username):
                await callback_query.answer("\u672a\u6388\u6743")
                return

            data = str(getattr(callback_query, "data", ""))

            # topic:merge:accept:{token}
            if data.startswith("topic:merge:accept:"):
                token = data.split(":", 3)[3]
                state = self._get_callback_state(token)
                if not state:
                    await callback_query.answer("操作已过期，请重新执行命令")
                    return
                preview_id = state.get("preview_id", "")
                topic_id = state.get("topic_id", "")
                merge_service = self._get_topic_finding_merge_service()
                if merge_service is None:
                    await callback_query.answer("\u5408\u5e76\u670d\u52a1\u672a\u521d\u59cb\u5316")
                    return
                from ..intelligence.topic_findings import MergePreviewError

                try:
                    merged = merge_service.accept_merge_preview(
                        preview_id, expected_topic_id=topic_id, operator=username
                    )
                    await callback_query.answer("\u5408\u5e76\u5df2\u63a5\u53d7")
                    esc = self._escape_markdown_v1
                    await callback_query.message.reply_text(
                        "\u2705 *\u5408\u5e76\u5b8c\u6210*\n\n"
                        f"*\u4e3b\u9898*: `{esc(topic_id)}`\n"
                        f"*\u5408\u5e76\u540e\u53d1\u73b0ID*: `{esc(merged.id)}`",
                        parse_mode="Markdown",
                    )
                except MergePreviewError as e:
                    await callback_query.answer(f"\u5408\u5e76\u5931\u8d25: {str(e)}")
                return

            # topic:list:p:{token}:{page}
            if data.startswith("topic:list:p:"):
                parts = data.split(":", 4)
                if len(parts) != 5:
                    await callback_query.answer("\u7ffb\u9875\u5df2\u8fc7\u671f")
                    return
                token = parts[3]
                try:
                    page = max(1, int(parts[4]))
                except ValueError:
                    page = 1

                state = self._get_callback_state(token)
                if not state:
                    await callback_query.answer("\u7ffb\u9875\u5df2\u8fc7\u671f")
                    return

                kind = str(state.get("kind", ""))
                if kind == "topic_list":
                    payload = self.handle_topic_list_command(
                        str(state.get("user_id", "")),
                        "",
                        page=page,
                        return_markup=True,
                    )
                    if isinstance(payload, dict):
                        new_token = self._generate_callback_token()
                        page_num = int(payload.get("page", 1))
                        total_pages = int(payload.get("total_pages", 1))
                        keyboard: List[List[InlineKeyboardButton]] = []
                        if page_num < total_pages:
                            keyboard.append(
                                [
                                    InlineKeyboardButton(
                                        "\u66f4\u591a",
                                        callback_data=f"topic:list:p:{new_token}:{page_num + 1}",
                                    )
                                ]
                            )
                        markup = InlineKeyboardMarkup(keyboard) if keyboard else None

                        new_state = dict(payload.get("state_data", {}))
                        new_state.update(
                            {
                                "kind": "topic_list",
                                "page": page_num,
                                "total_pages": total_pages,
                                "total": int(payload.get("total", 0)),
                                "chat_id": chat_id,
                                "user_id": user_id,
                            }
                        )
                        self._store_callback_state(new_token, new_state)

                        await callback_query.message.edit_text(
                            str(payload.get("text", "")),
                            reply_markup=markup,
                            parse_mode="Markdown",
                        )
                        await callback_query.answer()
                    else:
                        await callback_query.answer(str(payload))
                else:
                    await callback_query.answer("\u7ffb\u9875\u5df2\u8fc7\u671f")
                return

            await callback_query.answer("\u672a\u77e5\u64cd\u4f5c")
        except Exception as e:
            self.logger.error(f"\u5904\u7406topic callback\u5931\u8d25: {e}")
            try:
                await callback_query.answer("\u5904\u7406\u56de\u8c03\u5931\u8d25")
            except Exception:
                pass

    def _execute_semantic_search_and_notify(
        self,
        user_id: str,
        username: str,
        chat_id: str,
        hours: int,
        topic: str,
        semantic_search_service: Any,
    ) -> None:
        """
        在后台线程中执行语义搜索并发送结果
        """
        self.logger.info(
            f"开始后台语义搜索: 用户={username} ({user_id}), chat_id={chat_id}, 时间窗口={hours}小时, topic={topic}"
        )

        try:
            result = semantic_search_service.search(query=topic, time_window_hours=hours)
            success = result.get("success", False)
            errors = result.get("errors", [])
            report_content = result.get("report_content", "")
            execution_id = result.get("execution_id", "semantic-search")

            if success:
                if report_content:
                    send_result = self.execution_coordinator.telegram_sender.send_report_to_chat(
                        report_content,
                        chat_id,
                    )
                    self._log_command_execution(
                        "/semantic_search",
                        user_id,
                        username,
                        execution_id,
                        send_result.success,
                        (
                            "语义搜索完成"
                            if send_result.success
                            else f"报告发送失败: {send_result.error_message}"
                        ),
                    )

                    if not send_result.success:
                        self._send_message_sync(
                            chat_id,
                            (
                                "⚠️ *语义搜索完成但报告发送失败*\n\n"
                                f"主题: {topic}\n"
                                f"时间窗口: 最近 {hours} 小时\n"
                                f"错误: {send_result.error_message}"
                            ),
                        )
                else:
                    self._log_command_execution(
                        "/semantic_search",
                        user_id,
                        username,
                        execution_id,
                        True,
                        "语义搜索完成，无匹配内容",
                    )
                    self._send_message_sync(
                        chat_id,
                        (
                            "✅ *语义搜索完成*\n\n"
                            "暂无符合条件的新内容。\n"
                            f"搜索范围: 最近 {hours} 小时\n"
                            f"主题: {topic}"
                        ),
                    )
            else:
                error_msg = "; ".join(errors) if errors else "未知错误"
                self._log_command_execution(
                    "/semantic_search",
                    user_id,
                    username,
                    execution_id,
                    False,
                    f"语义搜索失败: {error_msg}",
                )
                self._send_message_sync(
                    chat_id,
                    (
                        "❌ *语义搜索失败*\n\n"
                        f"主题: {topic}\n"
                        f"时间窗口: 最近 {hours} 小时\n"
                        f"错误信息:\n{error_msg}"
                    ),
                )

        except Exception as e:
            error_msg = f"后台语义搜索执行异常: {str(e)}"
            self.logger.error(error_msg, exc_info=True)

            try:
                self._send_message_sync(
                    chat_id,
                    (
                        "❌ *语义搜索执行异常*\n\n"
                        f"主题: {topic}\n"
                        f"时间窗口: 最近 {hours} 小时\n"
                        f"{str(e)}"
                    ),
                )
            except Exception as notify_error:
                self.logger.error(f"发送语义搜索错误通知失败: {str(notify_error)}")

            self._log_command_execution(
                "/semantic_search",
                user_id,
                username,
                None,
                False,
                f"执行异常: {str(e)}",
            )

    def _execute_analyze_and_notify(
        self,
        user_id: str,
        username: str,
        chat_id: str,
        hours: int,
        window_description: Optional[str] = None,
    ) -> None:
        """
        在后台线程中执行分析并发送通知

        Args:
            user_id: 用户ID
            username: 用户名
            chat_id: 聊天ID（用于发送报告）
            hours: 分析时间窗口（小时数）
        """
        self.logger.info(
            f"开始后台分析: 用户={username} ({user_id}), "
            f"chat_id={chat_id}, 时间窗口={hours}小时"
        )

        try:
            result = self.execution_coordinator.analyze_by_time_window(chat_id, hours)

            execution_id = result.get("execution_id", "unknown")
            success = result.get("success", False)
            errors = result.get("errors", [])

            self._log_command_execution(
                "/analyze",
                user_id,
                username,
                execution_id,
                success,
                "分析完成" if success else f"分析失败: {'; '.join(errors)}",
            )

            window_text = window_description or f"最近 {hours} 小时"

            if success:
                items_processed = result.get("items_processed", 0)
                report_content = result.get("report_content", "")

                if not report_content and items_processed == 0:
                    self.logger.info(f"分析成功但无新内容: chat_id={chat_id}, 时间窗口={hours}小时")
                    notification = (
                        "✅ *分析完成*\n\n" "暂无符合条件的新内容。\n" f"分析范围: {window_text}"
                    )
                    self._send_message_sync(chat_id, notification)
                    return

                if not report_content and items_processed > 0:
                    self.logger.warning(
                        f"分析成功但报告为空: chat_id={chat_id}, 时间窗口={hours}小时, "
                        f"处理项目数={items_processed}"
                    )
                    notification = (
                        "⚠️ *分析完成但报告为空*\n\n"
                        f"处理项目: {items_processed}\n"
                        f"分析范围: {window_text}\n"
                        "请检查日志后重试。"
                    )
                    self._send_message_sync(chat_id, notification)
                    return

                self.logger.info(
                    f"分析成功，准备发送报告到 chat_id={chat_id}, " f"处理项目数: {items_processed}"
                )

                send_result = self.execution_coordinator.telegram_sender.send_report_to_chat(
                    report_content, chat_id
                )

                if send_result.success:
                    recipient_key = self.execution_coordinator._resolve_manual_recipient_key(
                        chat_id,
                        manual_source="telegram",
                    )
                    self.execution_coordinator._persist_manual_analysis_success(
                        recipient_key=recipient_key,
                        time_window_hours=hours,
                        items_count=items_processed,
                        final_report_messages=result.get("final_report_messages", []),
                    )
                    self.logger.info(f"报告已成功发送到 chat_id={chat_id}")
                    notification = (
                        "✅ *分析完成*\n\n"
                        f"处理项目: {items_processed}\n"
                        f"分析范围: {window_text}\n"
                        f"报告已发送。"
                    )
                else:
                    self.logger.warning(f"报告发送失败: {send_result.error_message}")
                    notification = (
                        "⚠️ *分析完成但报告发送失败*\n\n"
                        f"处理项目: {items_processed}\n"
                        f"分析范围: {window_text}\n"
                        f"错误: {send_result.error_message}"
                    )

                self._send_message_sync(chat_id, notification)

            else:
                error_msg = "; ".join(errors) if errors else "未知错误"
                self.logger.error(f"分析失败: {error_msg}")

                notification = f"❌ *分析失败*\n\n错误信息:\n{error_msg}"

                self._send_message_sync(chat_id, notification)

        except Exception as e:
            error_msg = f"后台分析执行异常: {str(e)}"
            self.logger.error(error_msg, exc_info=True)

            try:
                notification = f"❌ *分析执行异常*\n\n{str(e)}"
                self._send_message_sync(chat_id, notification)
            except Exception as notify_error:
                self.logger.error(f"发送错误通知失败: {str(notify_error)}")

            self._log_command_execution(
                "/analyze", user_id, username, None, False, f"执行异常: {str(e)}"
            )

    def handle_status_command(self, user_id: str) -> str:
        """
        处理/status命令的业务逻辑

        显示系统状态和最近24小时内各个信息源获取到的消息数量

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

            # 最近 scheduled 执行结果
            history = self.execution_coordinator.get_execution_history(limit=50)
            scheduled_history = [h for h in history if h.trigger_type == "scheduled"]
            if scheduled_history:
                last_exec = scheduled_history[-1]
                response_parts.append(
                    f"\n\n*最近scheduled执行:*\n"
                    f"时间: {format_datetime_utc8(last_exec.end_time, '%Y-%m-%d %H:%M:%S')}\n"
                    f"结果: {'✅ 成功' if last_exec.success else '❌ 失败'}\n"
                    f"处理项目: {last_exec.items_processed}\n"
                    f"耗时: {last_exec.duration_seconds:.1f} 秒"
                )

            # 最近24小时各数据源消息数量
            try:
                data_manager = self.execution_coordinator.data_manager
                if data_manager:
                    source_counts = data_manager.get_source_message_counts(time_window_hours=24)

                    if source_counts:
                        response_parts.append("\n\n*最近24小时数据源统计:*")

                        # 按消息数量降序排列
                        sorted_sources = sorted(
                            source_counts.items(), key=lambda x: x[1], reverse=True
                        )

                        for source_name, count in sorted_sources:
                            response_parts.append(f"• {source_name}: {count} 条")

                        total_messages = sum(source_counts.values())
                        response_parts.append(f"\n*总计*: {total_messages} 条消息")
                    else:
                        response_parts.append("\n\n*最近24小时数据源统计:* 暂无数据")
            except Exception as e:
                self.logger.warning(f"获取数据源统计失败: {str(e)}")
                response_parts.append("\n\n*最近24小时数据源统计:* 获取失败")

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
            user_permissions = [
                "analyze",
                "semantic_search",
                "topic_create",
                "topic_revise",
                "topic_set_prompt",
                "topic_confirm",
                "topic_list",
                "topic_detail",
                "topic_logs",
                "topic_merge",
                "topic_pause",
                "topic_archive",
                "market",
                "status",
                "help",
                "tokens",
                "datasource",
            ]

        help_text = ["🤖 加密货币新闻分析机器人\n", "可用命令:\n"]

        # News domain
        help_text.append("📰 新闻分析\n")
        if "analyze" in user_permissions:
            help_text.append(
                "/analyze [hours] - 按时间窗口执行分析\n"
                "不传参数时自动估算时间窗口，支持例如 /analyze 24。\n"
            )

        if "semantic_search" in user_permissions or not user_permissions:
            help_text.append(
                "/semantic_search <hours> <topic> - 按时间窗口执行语义搜索\n"
                "hours 为必填参数，例如 /semantic_search 24 BTC adoption。\n"
            )

        if "market" in user_permissions:
            help_text.append(
                "/market - 获取当前市场现状快照\n" "使用联网AI服务获取实时市场信息和分析。\n"
            )

        if "status" in user_permissions:
            help_text.append(
                "/status - 查询系统运行状态\n" "显示当前执行状态、系统信息和最近执行结果。\n"
            )

        if "tokens" in user_permissions or not user_permissions:
            help_text.append(
                "/tokens - 查看LLM token使用统计\n"
                "显示最近50次调用的token使用情况和缓存命中率。\n"
            )

        if "datasource" in user_permissions or not user_permissions:
            help_text.append(
                "/datasource_list - 查看已配置的数据源列表\n"
                "显示所有已注册的数据源及其基本信息。\n"
            )
            help_text.append(
                "/datasource_add {json} - 添加数据源\n"
                "格式: /datasource_add "
                '{"purpose":"news|intelligence","source_type":"...",'
                '"tags":["..."],"config_payload":{...}}\n'
                "\n"
                "示例 (RSS):\n"
                "/datasource_add "
                '{"purpose":"news","source_type":"rss","tags":["markets","btc"],'
                '"config_payload":{"name":"CoinDesk",'
                '"url":"https://www.coindesk.com/arc/outboundfeeds/rss/",'
                '"description":"Industry news"}}\n'
                "\n"
                "示例 (X):\n"
                "/datasource_add "
                '{"purpose":"news","source_type":"x","tags":["whales"],'
                '"config_payload":{"name":"Whale Watch",'
                '"url":"https://x.com/i/lists/1234567890","type":"list"}}\n'
                "\n"
                "示例 (REST API，注意：不可内联认证信息):\n"
                "/datasource_add "
                '{"purpose":"news","source_type":"rest_api","tags":["news"],'
                '"config_payload":{"name":"News API",'
                '"endpoint":"https://api.example.com/news","method":"GET",'
                '"headers":{},"params":{},'
                '"response_mapping":{"title_field":"title",'
                '"content_field":"body","url_field":"url",'
                '"time_field":"published_at"}}}\n'
            )
            help_text.append(
                "/datasource_delete <id> - 删除数据源\n"
                "格式: /datasource_delete ds-xxx\n"
                "注意: 如果数据源有活跃的入库任务，将无法删除。\n"
            )

        # Intelligence domain
        help_text.append("\n🧠 情报研究\n")
        help_text.append("/topic_create <主题> - 从主题创建研究草稿\n")
        help_text.append("/topic_revise <topic_id> <反馈> - 修订主题提示词\n")
        help_text.append("/topic_set_prompt <topic_id> <提示词> - 手动设置主题提示词\n")
        help_text.append("/topic_confirm <topic_id> - 确认并激活主题\n")
        help_text.append("/topic_list [page] - 查看主题列表\n")
        help_text.append("/topic_detail <topic_id> - 查看主题详情和发现\n")
        help_text.append("/topic_logs <topic_id> - 查看主题运行日志\n")
        help_text.append("/topic_merge <topic_id> - 合并主题发现\n")
        help_text.append("/topic_pause <topic_id> - 暂停主题\n")
        help_text.append("/topic_archive <topic_id> - 归档主题\n")

        # Shared
        help_text.append("\n⚙️ 通用\n")
        help_text.append("/help - 显示此帮助信息\n查看所有可用命令和使用说明。\n")

        help_text.append(
            "\n注意事项:\n"
            "• 命令有速率限制，请勿频繁调用\n"
            "• 执行过程可能需要几分钟时间\n"
            "• 执行完成后会自动发送报告"
        )

        return "\n".join(help_text)

    def handle_tokens_command(self) -> str:
        """
        处理/tokens命令的业务逻辑 - 显示LLM token使用统计

        Returns:
            响应消息
        """
        try:
            # 获取LLM分析器的token追踪器
            if (
                not hasattr(self.execution_coordinator, "llm_analyzer")
                or not self.execution_coordinator.llm_analyzer
            ):
                return "❌ LLM分析器未初始化\n\n请先运行 /analyze 命令执行一次分析。"

            tracker = self.execution_coordinator.llm_analyzer.token_tracker

            # 获取统计信息
            stats = tracker.get_statistics()

            if stats["total_calls"] == 0:
                return "📊 *Token使用统计*\n\n暂无记录\n\n请先运行 /analyze 命令执行一次分析。"

            # 格式化摘要
            summary = tracker.format_summary()

            # 格式化最近10次记录
            recent = tracker.format_recent_records(count=10)

            # 组合响应
            response = [
                summary,
                "\n" + "─" * 30 + "\n",
                recent,
                "\n\n💡 *提示:* 缓存命中率越高，token消耗越少",
            ]

            return "\n".join(response)

        except Exception as e:
            self.logger.error(f"获取token统计失败: {e}")
            return f"❌ 获取统计信息失败\n\n{str(e)}"

    def handle_datasource_list_command(self, purpose: Optional[str] = None) -> str:
        return "\n\n".join(self.handle_datasource_list_messages(purpose=purpose))

    def handle_datasource_list_messages(self, purpose: Optional[str] = None) -> List[str]:
        repository = getattr(self.execution_coordinator, "datasource_repository", None)
        if repository is None:
            raise ValueError("数据源仓储未初始化")

        if purpose is not None and purpose not in {"news", "intelligence"}:
            raise ValueError("purpose must be one of: news, intelligence")

        datasources = sorted(
            repository.list(purpose=purpose),
            key=lambda datasource: (datasource.purpose, datasource.source_type, datasource.name),
        )

        if not datasources:
            title = self._datasource_list_title(purpose)
            return [f"{title}\n\n暂无已配置数据源。"]

        response_lines = [
            self._datasource_list_title(purpose),
            "",
            f"共 {len(datasources)} 个数据源。",
            "",
        ]

        for index, datasource in enumerate(datasources, start=1):
            response_lines.extend(self._build_datasource_list_lines(index, datasource))
            if index < len(datasources):
                response_lines.append("")

        return self._split_telegram_message("\n".join(response_lines))

    def _split_telegram_message(
        self,
        text: str,
        max_length: int = TELEGRAM_SAFE_MESSAGE_LIMIT,
    ) -> List[str]:
        if len(text) <= max_length:
            return [text]

        messages: List[str] = []
        current_lines: List[str] = []
        current_length = 0

        for line in text.split("\n"):
            line_length = len(line)

            if line_length > max_length:
                if current_lines:
                    messages.append("\n".join(current_lines).rstrip())
                    current_lines = []
                    current_length = 0
                for start in range(0, line_length, max_length):
                    messages.append(line[start : start + max_length])
                continue

            projected_length = current_length + line_length + (1 if current_lines else 0)
            if current_lines and projected_length > max_length:
                messages.append("\n".join(current_lines).rstrip())
                current_lines = [line]
                current_length = line_length
            else:
                current_lines.append(line)
                current_length = projected_length

        if current_lines:
            messages.append("\n".join(current_lines).rstrip())

        return [message for message in messages if message]

    @staticmethod
    def _normalize_optional_display_text(value: Any) -> Optional[str]:
        if not isinstance(value, str):
            return None

        normalized_value = value.strip()
        return normalized_value or None

    def _build_datasource_list_lines(self, index: int, datasource: Any) -> List[str]:
        tags_text = ", ".join(datasource.tags) if datasource.tags else "（无标签）"
        lines = [
            f"{index}. ID: {datasource.id}",
            f"   用途: {datasource.purpose}",
            f"   类型: {datasource.source_type}",
            f"   名称: {datasource.name}",
            f"   标签: {tags_text}",
        ]

        config_payload = (
            datasource.config_payload if isinstance(datasource.config_payload, dict) else {}
        )
        source_type = str(datasource.source_type or "").strip().lower()

        if source_type in {"rss", "x"}:
            url = self._normalize_optional_display_text(config_payload.get("url"))
            if url:
                lines.append(f"   链接: {url}")

        if source_type == "rss":
            description = self._normalize_optional_display_text(config_payload.get("description"))
            if description:
                lines.append(f"   描述: {description}")

        if source_type == "rest_api":
            endpoint = self._normalize_optional_display_text(config_payload.get("endpoint"))
            description = self._normalize_optional_display_text(config_payload.get("description"))
            if endpoint:
                lines.append(f"   接口: {self._summarize_public_endpoint(endpoint)}")
            if description:
                lines.append(f"   描述: {description}")

        return lines

    def _format_datasource_lines(self, datasource: Any, index: int) -> List[str]:
        return self._build_datasource_list_lines(index, datasource)

    def _summarize_public_endpoint(self, endpoint: str) -> str:
        try:
            parsed = urlsplit(endpoint)
        except ValueError:
            return endpoint.split("?", 1)[0].split("#", 1)[0]
        netloc = parsed.hostname or ""
        if parsed.port is not None:
            netloc = f"{netloc}:{parsed.port}"
        return urlunsplit((parsed.scheme, netloc, parsed.path, "", ""))

    def _format_datasource_add_error_response(
        self,
        base_message: str,
        payload: Optional[Dict[str, Any]],
    ) -> str:
        source_type = None
        if isinstance(payload, dict):
            source_type = str(payload.get("source_type") or "").strip().lower() or None

        guidance = self._get_datasource_add_guidance(source_type)
        if not guidance:
            return base_message

        return f"{base_message}\n\n{guidance}"

    def _get_datasource_add_guidance(self, source_type: Optional[str]) -> str:
        guidance_lines = ["填写提示:"]

        if source_type == "rss":
            guidance_lines.append("- rss 的 config_payload 需要 name、url，可选 description。")
        elif source_type == "x":
            guidance_lines.append(
                "- x 的 config_payload 需要 name、url、type（list 或 timeline）。"
            )
        elif source_type == "rest_api":
            guidance_lines.append(
                "- rest_api 的 config_payload 需要 name、endpoint、method、response_mapping。"
            )
            guidance_lines.append("- rest_api 不支持在 auth、headers、params 中内联提交密钥。")
        else:
            guidance_lines.append(
                '- 顶层 JSON 结构: {"purpose":"news|intelligence",'
                '"source_type":"rss|x|rest_api|telegram_group|v2ex",'
                '"tags":[...],"config_payload":{...}}'
            )
            guidance_lines.append(
                "- rss 需要 name/url，x 需要 name/url/type，rest_api 需要 endpoint/method/response_mapping。"
            )

        guidance_lines.append("输入 /help 查看示例。")
        return "\n".join(guidance_lines)

    @staticmethod
    def _datasource_list_title(purpose: Optional[str]) -> str:
        if purpose == "news":
            return "📚 新闻数据源列表"
        if purpose == "intelligence":
            return "📚 渠道情报数据源列表"
        return "📚 数据源列表"

    def _log_expected_command_outcome(
        self,
        *,
        command: str,
        user_id: str,
        username: str,
        chat_type: str,
        chat_id: str,
        outcome: str,
    ) -> None:
        self.logger.info(
            f"预期命令结果: command={command}, user={username} ({user_id}), "
            f"chat_type={chat_type}, chat_id={chat_id}, outcome={outcome}"
        )

    def handle_market_command(self, user_id: str, username: str) -> str:
        """
        处理/market命令的业务逻辑

        需求16.3: 获取并返回当前市场现状快照（从缓存）
        需求16.17: 使用MarketSnapshotService获取市场快照（优先使用缓存）
        需求16.18: 将市场快照以Telegram格式发送给用户
        需求16.19: 在失败时返回错误信息并说明失败原因

        注意：此命令从缓存中读取市场快照，不会触发新的API调用。
        市场快照由系统定时任务更新。

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

            # 通过LLMAnalyzer获取市场快照（优先使用缓存，缓存不存在时自动生成）
            try:
                if (
                    hasattr(self.execution_coordinator, "llm_analyzer")
                    and self.execution_coordinator.llm_analyzer
                ):
                    snapshot = self.execution_coordinator.llm_analyzer.get_market_snapshot(
                        use_cached=True
                    )
                else:
                    self.logger.warning("LLMAnalyzer未初始化，使用备用快照")
                    snapshot = self.market_snapshot_service.get_fallback_snapshot()

            except Exception as e:
                self.logger.error(f"获取市场快照失败: {e}")
                snapshot = self.market_snapshot_service.get_fallback_snapshot()

            if not snapshot or not snapshot.is_valid:
                error_msg = "无法获取市场快照"
                self.logger.error(error_msg)
                return f"❌ {error_msg}\n\n请稍后再试或联系管理员。"

            # 格式化市场快照为Telegram消息（纯文本格式）
            response_parts = [
                "🌐 市场现状快照\n",
                f"📅 获取时间: {format_datetime_utc8(snapshot.timestamp, '%Y-%m-%d %H:%M:%S')}\n",
                f"📊 数据来源: {snapshot.source}\n",
                f"⭐ 质量评分: {snapshot.quality_score:.2f}\n",
                "\n" + "=" * 40 + "\n",
                snapshot.content,
            ]

            response = "\n".join(response_parts)

            self.logger.info(f"市场快照获取成功，长度: {len(response)} 字符")
            return response

        except Exception as e:
            error_msg = f"处理/market命令时发生错误: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            return f"❌ 命令执行失败\n\n{str(e)}"

    def get_execution_status(self) -> Dict[str, Any]:
        """
        获取执行状态

        Returns:
            执行状态字典
        """
        return self.execution_coordinator.get_system_status()

    async def _handle_unimplemented_datasource_command(
        self,
        update: Update,
        command_name: str,
        response_message: str,
    ) -> None:
        try:
            chat_context = self._extract_chat_context(update)
        except ValueError as e:
            self.logger.error(f"Failed to extract chat context: {e}")
            await update.message.reply_text("❌ 处理命令时发生错误")
            return

        user_id = chat_context.user_id
        username = chat_context.username
        chat_type = chat_context.chat_type
        chat_id = chat_context.chat_id

        self.logger.info(
            f"收到{command_name}命令，用户: {username} ({user_id}), "
            f"聊天类型: {chat_type}, 聊天ID: {chat_id}"
        )

        try:
            if not self.is_authorized_user(user_id, username):
                response = "❌ 权限拒绝\n\n您没有权限执行此命令。"
                await update.message.reply_text(response)
                self._log_authorization_attempt(
                    command=command_name,
                    user_id=user_id,
                    username=username,
                    chat_type=chat_type,
                    chat_id=chat_id,
                    authorized=False,
                    reason="user not in authorized list",
                )
                self._log_command_execution(command_name, user_id, username, None, False, response)
                return

            self._log_authorization_attempt(
                command=command_name,
                user_id=user_id,
                username=username,
                chat_type=chat_type,
                chat_id=chat_id,
                authorized=True,
            )
            await update.message.reply_text(response_message)
            self._log_command_execution(
                command_name, user_id, username, None, True, response_message
            )

        except Exception as e:
            error_msg = f"处理{command_name}命令时发生错误: {str(e)}"
            self.logger.error(
                f"{error_msg}, 用户: {username} ({user_id}), "
                f"聊天类型: {chat_type}, 聊天ID: {chat_id}"
            )
            await update.message.reply_text(f"❌ 命令执行失败\n\n{str(e)}")

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
                    chat_id=user_id, text=message, parse_mode="Markdown"
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
                    self._send_message_to_user(user_id, message), loop
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
        response_message: str,
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
            response_message=response_message,
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
        response_message: str,
    ) -> None:
        """
        公开的命令执行日志方法（向后兼容）
        """
        self._log_command_execution(
            command, user_id, username, execution_id, success, response_message
        )

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
        market_snapshot_service: Optional[Any] = None,
    ):
        self.handler = TelegramCommandHandler(
            bot_token, execution_coordinator, config, market_snapshot_service
        )
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

    def uses_webhook(self) -> bool:
        return self.handler.uses_webhook()

    def get_webhook_path(self) -> str:
        return self.handler.get_webhook_path()

    async def initialize_webhook(self) -> str:
        return await self.handler.initialize_webhook()

    async def shutdown_webhook(self) -> None:
        await self.handler.shutdown_webhook()

    async def handle_webhook_update(
        self,
        update_data: Dict[str, Any],
        secret_token: Optional[str] = None,
    ) -> None:
        await self.handler.handle_webhook_update(update_data, secret_token)


# 工具函数
def create_telegram_command_handler(
    bot_token: str,
    execution_coordinator: Any,
    config: TelegramCommandConfig,
    market_snapshot_service: Optional[Any] = None,
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
        command_rate_limit={"max_commands_per_hour": 10, "cooldown_seconds": 1},
    )
