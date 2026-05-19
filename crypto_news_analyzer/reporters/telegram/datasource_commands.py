"""Datasource management Telegram command handlers (mixin for TelegramCommandHandler).

Contains /datasource_* command handlers for datasource CRUD operations.
"""

import logging
from typing import Any, Dict, List, Optional
from urllib.parse import urlsplit, urlunsplit

from telegram import Update
from telegram.ext import ContextTypes

from ...datasource_payloads import (
    DataSourcePayloadValidationError,
    TelegramDataSourceInputError,
    parse_telegram_datasource_command_json,
    validate_telegram_datasource_create_payload,
)
from ...domain.models import (
    DataSourceAlreadyExistsError,
    DataSourceInUseError,
)

logger = logging.getLogger(__name__)


class DatasourceCommandsMixin:
    """Mixin providing datasource management /datasource_* command handlers.

    Requires the host class to provide:
    - self.logger
    - self.execution_coordinator
    - self.is_authorized_user(user_id, username) -> bool
    - self.check_rate_limit(user_id) -> tuple[bool, Optional[str]]
    - self._extract_chat_context(update) -> ChatContext
    - self._escape_markdown_v1(text) -> str
    - self._log_authorization_attempt(...)
    - self._log_command_execution(...)
    - self._log_expected_command_outcome(...)
    - self._is_http_url(url) -> bool
    """

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
    @staticmethod
    def _datasource_list_title(purpose: Optional[str]) -> str:
        if purpose == "news":
            return "📚 新闻数据源列表"
        if purpose == "intelligence":
            return "📚 渠道情报数据源列表"
        return "📚 数据源列表"

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
