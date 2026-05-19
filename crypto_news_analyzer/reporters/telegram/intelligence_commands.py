"""Intelligence domain Telegram command handlers (mixin for TelegramCommandHandler).

Contains /topic_* command handlers for the intelligence topic research lifecycle:
create, revise, set_prompt, confirm, merge, pause, archive, list, detail.
"""

import asyncio
import hashlib
import logging
import time
from typing import Any, Dict, List, Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, CopyTextButton
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


class IntelligenceCommandsMixin:
    """Mixin providing intelligence /topic_* command handlers.

    Requires the host class to provide:
    - self.logger
    - self.execution_coordinator
    - self.is_authorized_user(user_id, username) -> bool
    - self.check_rate_limit(user_id) -> tuple[bool, Optional[str]]
    - self._escape_markdown_v1(text) -> str
    - self._split_text_for_telegram(text) -> List[str]
    - self._generate_callback_token() -> str
    - self._store_callback_state(token, state) -> None
    - self._get_callback_state(token) -> Optional[dict]
    - self._log_command_execution(...)
    - self._get_intelligence_repository()
    - self._get_topic_prompt_workflow_service()
    - self._get_topic_finding_merge_service()
    - self._active_topic_revision_keys: Set[str]
    - self._recent_topic_revision_results: Dict[str, Dict[str, Any]]
    - self._topic_revision_result_ttl_seconds: int
    - self.application: Optional[Application]
    """

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
            self.logger.exception(
                "后台处理/topic_revise失败: topic_id=%s error_type=%s error=%s",
                topic_id,
                type(e).__name__,
                e,
            )
            self._log_command_execution("/topic_revise", user_id, username, topic_id, False, str(e))
            try:
                error_detail = f"{type(e).__name__}: {e}" if str(e) else type(e).__name__
                await self._reply_text_with_timeout(
                    msg,
                    f"❌ 修订失败: {error_detail}\n\n请查看服务器日志获取详细信息。",
                )
            except Exception as send_error:
                self.logger.error("发送/topic_revise失败响应失败: %s", send_error)
        finally:
            self._active_topic_revision_keys.discard(request_key)

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
            self.logger.error(
                f"处理/topic_confirm命令时发生错误: {type(e).__name__}: {e}", exc_info=True
            )
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

            from ...intelligence.topic_findings import MergePreviewError

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
            topic_ids: List[str] = list(payload.get("topic_ids", []))
            keyboard: List[List[InlineKeyboardButton]] = []
            for i, tid in enumerate(topic_ids, 1):
                keyboard.append(
                    [
                        InlineKeyboardButton(
                            f"📋 复制 #{i} ID",
                            copy_text=CopyTextButton(text=tid),
                        ),
                    ]
                )
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
                    "topic_ids": topic_ids,
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
                    f"   发现: {finding_count} | 最近更新: {updated}"
                )
            total_pages = max(1, (total + page_size - 1) // page_size)
            if return_markup:
                footer = f"\n📄 共 {total} 个主题 | 第 {page}/{total_pages} 页\n💡 点击下方按钮复制主题 ID"
                lines.append(footer)
                return {
                    "text": "\n".join(lines),
                    "page": page,
                    "total_pages": total_pages,
                    "total": total,
                    "state_data": {},
                    "topic_ids": [t.id for t in topics],
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

            payload = self.handle_topic_detail_command(
                user_id, username, topic_id, return_markup=True
            )
            if isinstance(payload, dict):
                # Build inline keyboard with expand buttons for each finding.
                # Use short prefix + index (not full UUID) to stay within
                # Telegram's 64-byte callback_data limit.
                findings: List[Dict[str, Any]] = list(payload.get("findings", []))
                keyboard: List[List[InlineKeyboardButton]] = []
                token = None
                if findings and self.application is not None:
                    token = self._generate_callback_token()
                    for i, finding_info in enumerate(findings):
                        source_count = int(finding_info.get("source_count", 0))
                        idx = int(finding_info.get("index", 0))
                        label = f"📎 #{idx} 查看原文" if source_count == 0 else f"📎 #{idx} 查看原文 ({source_count})"
                        keyboard.append([
                            InlineKeyboardButton(
                                label,
                                callback_data=f"td:e:{token}:{i}",
                            )
                        ])

                markup = InlineKeyboardMarkup(keyboard) if keyboard else None
                await msg.reply_text(
                    str(payload.get("text", "")),
                    reply_markup=markup,
                    parse_mode="Markdown",
                )

                if token:
                    state_payload = dict(payload.get("state_data", {}))
                    state_payload.update({
                        "kind": "topic_detail",
                        "topic_id": topic_id,
                        "user_id": user_id,
                        "findings": findings,
                    })
                    self._store_callback_state(token, state_payload)
            else:
                # Fallback: plain text response (e.g., error message)
                chunks = self._split_text_for_telegram(str(payload))
                total = len(chunks)
                for i, chunk in enumerate(chunks):
                    if total > 1:
                        chunk = f"🔬 主题详情 ({i + 1}/{total})\n\n" + chunk
                    await msg.reply_text(chunk, parse_mode="Markdown")
        except Exception as e:
            self.logger.error(f"处理/topic_detail命令时发生错误: {e}")

    def handle_topic_detail_command(
        self, user_id: str, username: str, topic_id: str, return_markup: bool = False
    ) -> Any:
        try:
            repository = self._get_intelligence_repository()
            if repository is None:
                return "❌ 情报仓储未初始化"
            topic = repository.get_topic_by_id(topic_id)
            if topic is None:
                return "❌ 主题未找到"
            esc = self._escape_markdown_v1
            lines: List[str] = [f"🔬 {esc(topic.name)}\n"]

            active_prompt = repository.get_active_topic_prompt(topic_id)
            if active_prompt:
                safe_prompt = active_prompt.prompt_text.replace("```", "'''")
                lines.append(
                    f"*✏️ 当前提示词 (v{esc(active_prompt.prompt_version)})*\n"
                    f"```\n{safe_prompt}\n```\n"
                )

            active_findings = repository.list_active_findings(topic_id)
            findings_info: List[Dict[str, Any]] = []
            if active_findings:
                lines.append(f"*🔍 活跃研究发现 ({len(active_findings)} 条)*")
                for i, finding in enumerate(active_findings, 1):
                    payload = finding.finding_payload or {}
                    title = str(
                        payload.get("finding", "")
                        or payload.get("title", "")
                        or payload.get("summary", "")
                        or ""
                    )
                    if not title:
                        title = esc(str(payload)[:150])
                    else:
                        title = esc(title[:200])
                    conf_str = ""
                    conf = getattr(finding, "confidence", 0.0) or 0.0
                    if conf > 0:
                        conf_str = f" [置信度: {conf:.0%}]"
                    source_count = len(finding.source_raw_item_ids or [])
                    source_note = f" (📎{source_count}来源)" if source_count > 0 else ""
                    lines.append(f"  • #{i} {title}{conf_str}{source_note}")

                    if return_markup:
                        findings_info.append({
                            "id": finding.id,
                            "index": i,
                            "title": title,
                            "confidence": conf,
                            "source_count": source_count,
                        })
                lines.append("")

            if return_markup:
                lines.append("💡 点击下方按钮查看每条发现的原数据来源")
                return {
                    "text": "\n".join(lines),
                    "state_data": {},
                    "findings": findings_info,
                }

            self._log_command_execution("/topic_detail", user_id, username, topic_id, True, "")
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
                from ...intelligence.topic_findings import MergePreviewError

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
                        topic_ids: List[str] = list(payload.get("topic_ids", []))
                        keyboard: List[List[InlineKeyboardButton]] = []
                        for i, tid in enumerate(topic_ids, 1):
                            keyboard.append(
                                [
                                    InlineKeyboardButton(
                                        f"📋 复制 #{i} ID",
                                        copy_text=CopyTextButton(text=tid),
                                    ),
                                ]
                            )
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
                                "topic_ids": topic_ids,
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

            # td:e:{token}:{index}  — expand finding sources (short prefix to fit 64-byte callback_data)
            if data.startswith("td:e:"):
                parts = data.split(":", 3)
                if len(parts) != 4:
                    await callback_query.answer("操作已过期")
                    return
                token = parts[2]
                try:
                    finding_index = int(parts[3])
                except (ValueError, IndexError):
                    await callback_query.answer("操作已过期")
                    return

                state = self._get_callback_state(token)
                if not state:
                    await callback_query.answer("操作已过期，请重新执行 /topic_detail")
                    return

                stored_findings: List[Dict[str, Any]] = list(state.get("findings", []))
                if finding_index < 0 or finding_index >= len(stored_findings):
                    await callback_query.answer("发现已过期")
                    return
                finding_id = str(stored_findings[finding_index].get("id", ""))
                if not finding_id:
                    await callback_query.answer("发现数据异常")
                    return

                repository = self._get_intelligence_repository()
                if repository is None:
                    await callback_query.answer("仓储未初始化")
                    return

                finding = repository.get_topic_finding_by_id(finding_id)
                if finding is None:
                    await callback_query.answer("发现未找到")
                    return

                raw_item_ids = finding.source_raw_item_ids or []
                if not raw_item_ids:
                    await callback_query.answer("该发现无关联原数据")
                    return

                # Fetch all raw items
                raw_items = repository.get_raw_items_by_ids(raw_item_ids)
                if not raw_items:
                    await callback_query.answer("原数据已过期或被清理")
                    return

                await callback_query.answer(f"展开 {len(raw_items)} 条原数据")

                # Build the response with source links
                esc = self._escape_markdown_v1
                payload = finding.finding_payload or {}
                finding_title = str(
                    payload.get("finding", "")
                    or payload.get("title", "")
                    or payload.get("summary", "")
                    or "发现"
                )[:100]

                lines: List[str] = [
                    f"📎 *{esc(finding_title)}*\n",
                    f"📊 共 {len(raw_items)} 条原数据:\n",
                ]

                # Build inline keyboard for each raw item with URL
                raw_keyboard: List[List[InlineKeyboardButton]] = []
                for j, item in enumerate(raw_items, 1):
                    source_label = item.source_type or "unknown"
                    published = ""
                    if item.published_at:
                        published = item.published_at.strftime("%Y-%m-%d %H:%M")
                    snippet = (item.raw_text or "")[:150].replace("\n", " ")
                    if len(item.raw_text or "") > 150:
                        snippet += "..."

                    # Source URL for button
                    source_url = item.source_url
                    if not source_url and item.source_type == "telegram_group":
                        # Try to build a Telegram message link
                        chat_id = item.chat_id or ""
                        ext_id = item.external_id or ""
                        if chat_id and ext_id:
                            # Remove -100 prefix for public links if present
                            clean_chat = chat_id.replace("-100", "") if chat_id.startswith("-100") else chat_id
                            source_url = f"https://t.me/c/{clean_chat}/{ext_id}"

                    lines.append(
                        f"*#{j}* [{esc(source_label)}] {esc(snippet)}\n"
                        f"  `{published}`"
                    )

                    if source_url:
                        raw_keyboard.append([
                            InlineKeyboardButton(
                                f"🔗 打开 #{j}",
                                url=source_url,
                            )
                        ])

                # Send as a new message with URL buttons
                raw_markup = InlineKeyboardMarkup(raw_keyboard) if raw_keyboard else None
                chunks = self._split_text_for_telegram("\n".join(lines))
                for k, chunk in enumerate(chunks):
                    header = f"📎 原数据来源 ({k + 1}/{len(chunks)})\n\n" if len(chunks) > 1 else ""
                    await callback_query.message.reply_text(
                        header + chunk,
                        reply_markup=raw_markup if k == len(chunks) - 1 else None,
                        parse_mode="Markdown",
                        disable_web_page_preview=True,
                    )
                return

            await callback_query.answer("\u672a\u77e5\u64cd\u4f5c")
        except Exception as e:
            self.logger.error(f"\u5904\u7406topic callback\u5931\u8d25: {e}")
            try:
                await callback_query.answer("\u5904\u7406\u56de\u8c03\u5931\u8d25")
            except Exception:
                pass
