"""
LLM分析器

实现四步分析流程：
1. 获取市场快照
2. 合并提示词（注意市场快照中的超链接部分不要合并）
3. 结构化输出
4. 批量分析

支持动态分类，不硬编码具体类别。
"""

import json
import logging
import os
import uuid
from typing import List, Dict, Any, Optional, Union
from datetime import datetime
from pathlib import Path

from ..config.llm_registry import (
    ModelConfig,
    ResolvedModelRuntime,
    resolve_model_runtime,
)
from ..models import ContentItem, AnalysisResult, StorageConfig
from ..utils.timezone_utils import format_datetime_utc8
from ..utils.conversation_cache import ConversationIdManager
from .market_snapshot_service import MarketSnapshotService, MarketSnapshot
from .structured_output_manager import (
    StructuredOutputManager,
    StructuredAnalysisResult,
    BatchAnalysisResult,
)
from ..storage.cache_manager import SentMessageCacheManager
from .token_usage_tracker import TokenUsageTracker
from ..utils.errors import ContentFilterError

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None


class LLMAnalyzer:
    """
    LLM分析器

    实现四步分析流程：
    1. 第一步：获取市场快照
    2. 第二步：合并提示词（注意市场快照中的超链接部分不要合并）
    3. 第三步：结构化输出
    4. 第四步：批量分析

    支持动态分类，不硬编码具体类别。
    """

    def __init__(
        self,
        provider_credentials: Optional[Dict[str, str]] = None,
        model: Optional[ResolvedModelRuntime] = None,
        fallback_models: Optional[List[ResolvedModelRuntime]] = None,
        market_model: Optional[ResolvedModelRuntime] = None,
        market_prompt_path: str = "./prompts/market_summary_prompt.md",
        analysis_prompt_path: str = "./prompts/analysis_prompt.md",
        temperature: float = 0.5,
        batch_size: int = 10,
        cache_ttl_minutes: int = 30,
        cached_messages_hours: int = 24,
        mock_mode: bool = False,
        cache_manager: Optional[SentMessageCacheManager] = None,
        storage_config: Optional[StorageConfig] = None,
        conversation_id: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        """
        初始化LLM分析器

        Args:
            provider_credentials: 提供商凭证映射
            model: 分析模型解析后的运行时元数据
            fallback_models: 备用分析模型解析后的运行时元数据
            market_model: 市场快照模型解析后的运行时元数据
            market_prompt_path: 市场快照提示词路径
            analysis_prompt_path: 分析提示词路径
            temperature: 温度参数
            batch_size: 批量分析的批次大小
            cache_ttl_minutes: 缓存有效期（分钟）
            cached_messages_hours: 缓存消息的时间范围（小时）
            mock_mode: 是否使用模拟模式（用于测试）
            cache_manager: 已发送消息缓存管理器（可选）
            storage_config: 存储配置（用于创建缓存管理器，可选）
            conversation_id: 会话ID（用于提高缓存命中率，如果为None则自动生成）
            config: 完整配置字典（用于传递给子组件）
        """
        self.provider_credentials = {
            "grok": os.getenv("GROK_API_KEY", "").strip(),
            "kimi": os.getenv("KIMI_API_KEY", "").strip(),
        }
        for provider, value in (provider_credentials or {}).items():
            self.provider_credentials[provider] = (value or "").strip()

        self.analysis_model_runtime = model or resolve_model_runtime(
            ModelConfig(provider="kimi", name="kimi-k2.5", options={})
        )
        self.fallback_model_runtimes = list(fallback_models or [])
        self.market_model_runtime = market_model or resolve_model_runtime(
            ModelConfig(provider="grok", name="grok-4-1-fast-reasoning", options={})
        )

        self.GROK_API_KEY = self.provider_credentials.get("grok", "")
        self.KIMI_API_KEY = self.provider_credentials.get("kimi", "")
        self.model = self.analysis_model_runtime.name
        self.market_model = self.market_model_runtime.name
        self.market_prompt_path = Path(market_prompt_path)
        self.analysis_prompt_path = Path(analysis_prompt_path)
        self.temperature = temperature
        self.cache_ttl_minutes = cache_ttl_minutes
        self.cached_messages_hours = cached_messages_hours
        self.mock_mode = mock_mode
        self.config = config or {}
        self.logger = logging.getLogger(__name__)
        self.analysis_provider = self.analysis_model_runtime.provider_name
        self.market_provider = self.market_model_runtime.provider_name
        self.analysis_api_key = self.provider_credentials.get(
            self.analysis_provider, ""
        )

        self.batch_size = batch_size

        # 使用会话ID管理器获取或创建持久化的conversation_id
        conversation_id_manager = ConversationIdManager(cache_dir="./data/cache")
        self.conversation_id = (
            conversation_id
            or conversation_id_manager.get_or_create_conversation_id("llm_analyzer")
        )

        # 初始化token使用追踪器
        self.token_tracker = TokenUsageTracker(max_records=50)

        # 初始化缓存管理器
        self.cache_manager = cache_manager
        if not self.cache_manager and storage_config:
            try:
                self.cache_manager = SentMessageCacheManager(storage_config)
                self.logger.info("已创建缓存管理器实例")
            except Exception as e:
                self.logger.warning(f"创建缓存管理器失败: {e}")

        # 初始化OpenAI客户端
        self.client = None
        if not mock_mode and self.analysis_api_key and OpenAI:
            try:
                self.client = self._build_client(
                    self.analysis_model_runtime, self.analysis_api_key
                )
            except Exception as e:
                self.logger.error(f"初始化OpenAI客户端失败: {e}")

        # 初始化市场快照服务
        self.market_snapshot_service = MarketSnapshotService(
            provider_credentials=self.provider_credentials,
            market_model_config=self.market_model_runtime.to_dict(),
            cache_ttl_minutes=self.cache_ttl_minutes,
            mock_mode=mock_mode,
            conversation_id=self.conversation_id,
            temperature=self.temperature,
            config=self.config,  # 传递config以支持enable_debug_logging
        )

        # 初始化结构化输出管理器
        self.structured_output_manager = StructuredOutputManager(
            library="instructor", config=self.config
        )

        # 如果有客户端，设置instructor客户端
        if self.client and not mock_mode:
            try:
                self.structured_output_manager.setup_instructor_client(self.client)
            except Exception as e:
                self.logger.warning(f"设置instructor客户端失败: {e}")

        # 缓存的市场快照和系统提示词
        self._cached_market_snapshot: Optional[MarketSnapshot] = None
        self._cached_system_prompt: Optional[str] = None

        # 记录实际使用的模型（包括备用模型）
        self._last_used_model: Optional[str] = None

        if mock_mode:
            self.logger.info("LLM分析器运行在模拟模式")
        elif not self.analysis_api_key:
            self.logger.warning("未提供当前分析模型所需的LLM提供商密钥")
        else:
            self.logger.info(f"使用会话ID提高缓存命中率: {self.conversation_id}")

    def _build_client(self, runtime: ResolvedModelRuntime, api_key: str):
        if OpenAI is None:
            raise RuntimeError("openai package is not installed")

        default_headers = dict(runtime.provider.default_headers)
        conversation_header_name = runtime.provider.conversation_header_name
        if conversation_header_name:
            default_headers[conversation_header_name] = self.conversation_id

        client_kwargs: Dict[str, Any] = {
            "api_key": api_key,
            "base_url": runtime.provider.base_url,
        }
        if default_headers:
            client_kwargs["default_headers"] = default_headers

        client = OpenAI(**client_kwargs)
        setattr(client, "_provider", runtime.provider_name)
        if conversation_header_name:
            self.logger.info(
                f"{runtime.provider.name.capitalize()}客户端已设置default_headers: "
                f"{conversation_header_name}={self.conversation_id}"
            )
        else:
            self.logger.info(
                f"{runtime.provider.name.capitalize()}客户端已初始化，使用模型: {runtime.name}"
            )
        return client

    def _supports_web_search(self, runtime: ResolvedModelRuntime) -> bool:
        return runtime.model.supports_web_search

    def _display_provider_name(self, runtime: ResolvedModelRuntime) -> str:
        if runtime.provider_name == "kimi":
            return "Kimi"
        if runtime.provider_name == "grok":
            return "Grok"
        return runtime.provider_name

    def _select_content_filter_fallback_runtime(self) -> Optional[ResolvedModelRuntime]:
        for runtime in self.fallback_model_runtimes:
            if runtime.provider_name == "grok":
                return runtime
        if self.market_model_runtime.provider_name == "grok":
            return self.market_model_runtime
        return None

    def analyze_content_batch(
        self,
        items: List[ContentItem],
        use_cached_snapshot: bool = True,
        is_scheduled: bool = False,
        historical_titles: Optional[List[str]] = None,
    ) -> List[StructuredAnalysisResult]:
        """
        批量分析内容（四步流程）

        Args:
            items: 内容项列表
            use_cached_snapshot: 是否使用缓存的市场快照
            is_scheduled: 是否为定时任务（True时使用全局缓存，False时使用historical_titles）
            historical_titles: 手动调用时传入的历史标题列表

        Returns:
            结构化分析结果列表
        """
        if not items:
            self.logger.info("没有内容需要分析")
            return []

        try:
            market_snapshot = self.get_market_snapshot(use_cached=use_cached_snapshot)
            self.logger.info(f"市场快照来源: {market_snapshot.source}")

            system_prompt = self._build_static_system_prompt()
            self.logger.info(f"静态系统提示词长度: {len(system_prompt)} 字符")

            results = self._analyze_batch_with_structured_output(
                items, system_prompt, market_snapshot, is_scheduled, historical_titles
            )

            self.logger.info(f"批量分析完成，返回 {len(results)} 条结果")
            return results

        except Exception as e:
            self.logger.error(f"批量分析失败: {e}")
            raise

    def get_market_snapshot(self, use_cached: bool = True) -> MarketSnapshot:
        """
        第一步：获取市场快照

        Args:
            use_cached: 是否使用缓存的快照

        Returns:
            市场快照对象
        """
        # 如果允许使用缓存且有缓存，直接返回
        if use_cached and self._cached_market_snapshot:
            self.logger.info("使用内存缓存的市场快照")
            return self._cached_market_snapshot

        # 读取市场快照提示词模板
        prompt_template = self._load_market_prompt_template()

        self.logger.info(
            f"准备调用市场快照服务，提示词长度: {len(prompt_template)} 字符"
        )

        # 调用市场快照服务获取快照
        snapshot = self.market_snapshot_service.get_market_snapshot(prompt_template)

        # 缓存快照
        self._cached_market_snapshot = snapshot

        return snapshot

    def merge_prompts_with_snapshot(self, market_snapshot: MarketSnapshot) -> str:
        """
        第二步：合并提示词（已废弃，保留用于向后兼容）

        注意：此方法已废弃，新的实现将动态内容移到用户提示词中。
        建议使用 _build_static_system_prompt() 和 _build_user_prompt_with_context()

        Args:
            market_snapshot: 市场快照对象

        Returns:
            合并后的系统提示词（包含动态内容，不推荐用于生产环境）
        """
        self.logger.warning(
            "merge_prompts_with_snapshot() 已废弃，建议使用新的提示词构建方法"
        )

        # 读取分析提示词模板
        analysis_template = self._load_analysis_prompt_template()

        # 将市场快照内容插入到分析提示词中
        if "${Grok_Summary_Here}" in analysis_template:
            system_prompt = analysis_template.replace(
                "${Grok_Summary_Here}", market_snapshot.content
            )
        else:
            system_prompt = f"{analysis_template}\n\n# Current Market Context\n{market_snapshot.content}"

        # 替换 ${outdated_news} 占位符
        outdated_news = self._get_formatted_cached_messages(
            hours=self.cached_messages_hours
        )
        if "${outdated_news}" in system_prompt:
            system_prompt = system_prompt.replace("${outdated_news}", outdated_news)
        else:
            system_prompt = f"{system_prompt}\n\n# Outdated News\n{outdated_news}"

        return system_prompt

    def _build_static_system_prompt(self) -> str:
        """
        构建静态系统提示词（不包含动态内容）

        这是新的推荐方法，将动态内容（市场快照、缓存消息）移到用户提示词中，
        以提高LLM缓存命中率。

        Returns:
            静态系统提示词
        """
        # 如果有缓存，直接返回
        if self._cached_system_prompt:
            self.logger.debug("使用缓存的静态系统提示词")
            return self._cached_system_prompt

        # 读取分析提示词模板（不包含占位符）
        analysis_template = self._load_analysis_prompt_template()

        # 缓存静态系统提示词
        self._cached_system_prompt = analysis_template

        return analysis_template

    def _get_formatted_cached_messages(self, hours: int = 6) -> str:
        """
        获取格式化的缓存消息

        Args:
            hours: 时间范围（小时），默认6小时

        Returns:
            格式化后的缓存消息文本，如果没有缓存管理器或缓存为空则返回"无"
        """
        if not self.cache_manager:
            self.logger.debug("未配置缓存管理器，Outdated News将显示'无'")
            return "无"

        try:
            formatted_messages = self.cache_manager.format_cached_messages_for_prompt(
                hours=hours
            )
            if formatted_messages == "无":
                self.logger.info(
                    f"过去{hours}小时内没有已发送的消息缓存，Outdated News显示'无'"
                )
            else:
                self.logger.info(
                    f"已获取格式化的缓存消息，包含过去{hours}小时的已发送内容"
                )
            return formatted_messages
        except Exception as e:
            self.logger.warning(f"获取缓存消息失败: {e}，Outdated News将显示'无'")
            return "无"

    def _format_historical_titles(self, titles: List[str]) -> str:
        """
        格式化历史标题列表，用于手动分析时的Outdated News部分。

        Args:
            titles: 历史标题列表

        Returns:
            格式化后的标题文本，重复标题会被去重（保留首次出现的顺序）
        """
        if not titles:
            return "无"

        seen = set()
        unique_titles = []
        for title in titles:
            if title not in seen:
                seen.add(title)
                unique_titles.append(title)

        if not unique_titles:
            return "无"

        formatted_lines = [f"- {title}" for title in unique_titles]
        return "\n".join(formatted_lines)

    def _deduplicate_titles_preserving_order(
        self, titles: Optional[List[str]]
    ) -> List[str]:
        if not titles:
            return []

        seen = set()
        unique_titles = []
        for title in titles:
            if not title or title in seen:
                continue
            seen.add(title)
            unique_titles.append(title)

        return unique_titles

    def _extract_result_titles(
        self, results: List[StructuredAnalysisResult]
    ) -> List[str]:
        return self._deduplicate_titles_preserving_order(
            [result.title for result in results if getattr(result, "title", None)]
        )

    def _analyze_batch_with_structured_output(
        self,
        items: List[ContentItem],
        system_prompt: str,
        market_snapshot: MarketSnapshot,
        is_scheduled: bool = False,
        historical_titles: Optional[List[str]] = None,
    ) -> List[StructuredAnalysisResult]:
        """
        第三步和第四步：使用结构化输出进行批量分析

        Args:
            items: 内容项列表
            system_prompt: 静态系统提示词
            market_snapshot: 市场快照对象
            is_scheduled: 是否为定时任务（True时使用全局缓存，False时使用historical_titles）
            historical_titles: 手动调用时传入的历史标题列表

        Returns:
            结构化分析结果列表
        """
        if self.mock_mode:
            return self._generate_mock_results(items)

        if not self.client:
            raise RuntimeError("OpenAI客户端未初始化")

        all_results = []
        rolling_historical_titles = self._deduplicate_titles_preserving_order(
            historical_titles
        )

        for i in range(0, len(items), self.batch_size):
            batch = items[i : i + self.batch_size]
            messages: List[Dict[str, str]] = []
            self.logger.info(
                f"处理批次 {i // self.batch_size + 1}，包含 {len(batch)} 条内容"
            )

            try:
                batch_historical_titles = (
                    historical_titles if is_scheduled else rolling_historical_titles
                )
                user_prompt = self._build_user_prompt_with_context(
                    batch, market_snapshot, is_scheduled, batch_historical_titles
                )

                # 构建消息列表
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ]

                # 以用户友好的方式打印最终发送给LLM的完整提示词
                self._log_final_prompt(
                    system_prompt, user_prompt, i // self.batch_size + 1
                )

                # 判断是否启用 web_search 及使用哪种方式
                # Grok 使用 responses.parse() API
                # Kimi 使用内置 web_search（builtin_function + $web_search）
                enable_web_search = self._supports_web_search(
                    self.analysis_model_runtime
                )

                if enable_web_search:
                    if self.analysis_model_runtime.provider_name == "kimi":
                        self.logger.info("检测到 Kimi 模型，启用内置 web_search 工具")
                    elif self.analysis_model_runtime.provider_name == "grok":
                        self.logger.info(
                            "检测到 Grok 模型，启用 web_search 和 x_search 工具"
                        )

                # 使用结构化输出管理器强制返回结构化数据
                batch_result = self.structured_output_manager.force_structured_response(
                    llm_client=self.client,
                    messages=messages,
                    model=self.model,
                    max_retries=3,
                    temperature=self.temperature,
                    batch_mode=True,
                    enable_web_search=enable_web_search,
                    conversation_id=self.conversation_id,
                    usage_callback=self._record_token_usage,
                )

                # 记录主模型使用情况（如果没有使用过备用模型）
                if self._last_used_model is None:
                    self._last_used_model = self._display_provider_name(
                        self.analysis_model_runtime
                    )

                # 打印LLM返回的原始数据
                self._log_llm_response(batch_result, i // self.batch_size + 1)

                # 提取结果
                if isinstance(batch_result, BatchAnalysisResult):
                    all_results.extend(batch_result.results)
                    if not is_scheduled:
                        rolling_historical_titles = (
                            self._deduplicate_titles_preserving_order(
                                rolling_historical_titles
                                + self._extract_result_titles(batch_result.results)
                            )
                        )
                    self.logger.info(f"批次返回 {len(batch_result.results)} 条结果")
                else:
                    self.logger.warning(f"批次返回格式异常: {type(batch_result)}")

            except ContentFilterError as e:
                self.logger.error(f"Kimi 内容过滤错误: {e}")
                # 尝试使用 Grok 作为备用模型
                fallback_runtime = self._select_content_filter_fallback_runtime()
                fallback_api_key = ""
                if fallback_runtime is not None:
                    fallback_api_key = self.provider_credentials.get(
                        fallback_runtime.provider_name, ""
                    )

                if (
                    self.analysis_model_runtime.provider_name == "kimi"
                    and fallback_runtime is not None
                    and fallback_api_key
                ):
                    self.logger.info("尝试切换到 Grok 模型重试...")
                    try:
                        fallback_client = self._build_client(
                            fallback_runtime, fallback_api_key
                        )

                        # 记录使用了备用模型
                        self._last_used_model = (
                            f"{self._display_provider_name(self.analysis_model_runtime)} (主模型) -> "
                            f"{self._display_provider_name(fallback_runtime)} (备用模型)"
                        )

                        # Grok 备用模型保持开启 web_search/x_search
                        batch_result = (
                            self.structured_output_manager.force_structured_response(
                                llm_client=fallback_client,
                                messages=messages,
                                model=fallback_runtime.name,
                                max_retries=2,
                                temperature=self.temperature,
                                batch_mode=True,
                                enable_web_search=self._supports_web_search(
                                    fallback_runtime
                                ),
                                conversation_id=self.conversation_id,
                                usage_callback=self._record_token_usage,
                            )
                        )

                        # 打印LLM返回的原始数据
                        self._log_llm_response(batch_result, i // self.batch_size + 1)

                        # 提取结果
                        if isinstance(batch_result, BatchAnalysisResult):
                            all_results.extend(batch_result.results)
                            if not is_scheduled:
                                rolling_historical_titles = (
                                    self._deduplicate_titles_preserving_order(
                                        rolling_historical_titles
                                        + self._extract_result_titles(
                                            batch_result.results
                                        )
                                    )
                                )
                            self.logger.info(
                                f"Grok备用模型批次返回 {len(batch_result.results)} 条结果"
                            )
                        else:
                            self.logger.warning(
                                f"Grok批次返回格式异常: {type(batch_result)}"
                            )

                    except Exception as fallback_error:
                        self.logger.error(
                            f"Grok备用模型失败，停止当前分析: {fallback_error}"
                        )
                        raise
                else:
                    self.logger.warning("未配置可用的备用模型凭证，无法使用备用模型")
                    raise

            except Exception as e:
                self.logger.error(f"批次分析失败: {e}")
                # 继续处理下一批次
                continue

        return all_results

    def _build_user_prompt_with_context(
        self,
        items: List[ContentItem],
        market_snapshot: MarketSnapshot,
        is_scheduled: bool = False,
        historical_titles: Optional[List[str]] = None,
    ) -> str:
        """
        构建包含动态上下文的用户提示词

        新的提示词结构：
        1. 市场快照（Current Market Context）
        2. 已发送消息缓存（Outdated News）
        3. 待分析的新闻内容

        Args:
            items: 内容项列表
            market_snapshot: 市场快照对象
            is_scheduled: 是否为定时任务（True时使用全局缓存，False时使用historical_titles）
            historical_titles: 手动调用时传入的历史标题列表

        Returns:
            用户提示词字符串
        """
        from email.utils import format_datetime
        from ..utils.timezone_utils import convert_to_utc8

        prompt_parts = []

        prompt_parts.append("# Current Market Context")
        prompt_parts.append(market_snapshot.content)
        prompt_parts.append("")

        prompt_parts.append("# Outdated News")
        if is_scheduled:
            outdated_news = self._get_formatted_cached_messages(
                hours=self.cached_messages_hours
            )
        elif historical_titles:
            outdated_news = self._format_historical_titles(historical_titles)
        else:
            outdated_news = "无"
        prompt_parts.append(outdated_news)
        prompt_parts.append("")

        # 添加待分析的新闻内容
        prompt_parts.append("# News and Social Media Content to Analyze")
        prompt_parts.append("请分析以下新闻和社交媒体消息：\n")

        for i, item in enumerate(items, 1):
            prompt_parts.append(f"\n--- 消息 {i} ---")

            # X/Twitter内容的标题只是正文的截断，跳过以节省token
            if item.source_type != "x":
                prompt_parts.append(f"标题: {item.title}")

            prompt_parts.append(f"内容: {item.content}")
            prompt_parts.append(f"来源: {item.url}")

            # 将 datetime 转换为 RFC 2822 格式（带时区信息）
            dt_with_tz = convert_to_utc8(item.publish_time)
            rfc2822_time = format_datetime(dt_with_tz)
            prompt_parts.append(f"发布时间: {rfc2822_time}")

        prompt_parts.append("\n\n请按照要求输出JSON格式的分析结果。")

        return "\n".join(prompt_parts)

    def _format_user_prompt_for_logging(self, user_prompt: str) -> str:
        """
        格式化用户提示词日志输出。

        当 user_prompt 是包含 message 字段的 JSON 字符串时，只输出
        message 的内容，并保留换行等可读格式；否则返回原始内容。
        对超长提示词进行截断，避免生产日志因单条消息过大而难以阅读。
        """
        if not user_prompt:
            return user_prompt

        try:
            prompt_payload = json.loads(user_prompt)
        except (TypeError, json.JSONDecodeError):
            return self._truncate_text_for_logging(user_prompt)

        if not isinstance(prompt_payload, dict):
            return self._truncate_text_for_logging(user_prompt)

        message = prompt_payload.get("message")
        raw_text = message if isinstance(message, str) else user_prompt
        return self._truncate_text_for_logging(raw_text)

    def _truncate_text_for_logging(self, text: str, max_length: int = 8000) -> str:
        """
        截断过长日志文本，保留首尾上下文。

        Args:
            text: 待输出文本
            max_length: 允许输出的最大字符数

        Returns:
            适合日志输出的文本
        """
        enable_debug = self.config.get("llm_config", {}).get(
            "enable_debug_logging", False
        )
        if enable_debug:
            return text

        if not text or len(text) <= max_length:
            return text

        head_length = max_length // 2
        tail_length = max_length - head_length
        omitted_chars = len(text) - max_length

        return (
            f"{text[:head_length]}\n\n"
            f"... [日志截断，省略 {omitted_chars} 字符] ...\n\n"
            f"{text[-tail_length:]}"
        )

    def _log_final_prompt(
        self, system_prompt: str, user_prompt: str, batch_number: int
    ) -> None:
        """
        以用户友好的方式打印最终发送给LLM的完整提示词

        Args:
            system_prompt: 系统提示词
            user_prompt: 用户提示词
            batch_number: 批次编号
        """
        separator = "=" * 80

        self.logger.info(f"\n{separator}")
        self.logger.info(f"📤 发送给LLM的完整提示词 (批次 {batch_number})")
        self.logger.info(f"{separator}\n")

        # 打印系统提示词
        self.logger.info("🤖 系统提示词 (System Prompt):")
        self.logger.info(f"{'-' * 80}")
        self.logger.info(system_prompt)
        self.logger.info(f"{'-' * 80}\n")

        # 打印用户提示词
        self.logger.info("👤 用户提示词 (User Prompt):")
        self.logger.info(f"{'-' * 80}")
        self.logger.info(self._format_user_prompt_for_logging(user_prompt))
        self.logger.info(f"{'-' * 80}\n")

        # 打印统计信息
        self.logger.info("📊 提示词统计:")
        self.logger.info(f"  • 系统提示词长度: {len(system_prompt)} 字符")
        self.logger.info(f"  • 用户提示词长度: {len(user_prompt)} 字符")
        self.logger.info(f"  • 总长度: {len(system_prompt) + len(user_prompt)} 字符")
        self.logger.info(f"  • 模型: {self.model}")
        self.logger.info(f"  • 温度: {self.temperature}")
        self.logger.info(f"{separator}\n")

    def _log_llm_response(self, response: Any, batch_number: int) -> None:
        """
        以用户友好的方式打印LLM返回的原始数据

        Args:
            response: LLM返回的响应对象
            batch_number: 批次编号
        """
        import json
        from pydantic import BaseModel

        separator = "=" * 80

        self.logger.info(f"\n{separator}")
        self.logger.info(f"📥 LLM返回的原始数据 (批次 {batch_number})")
        self.logger.info(f"{separator}\n")

        try:
            # 如果是Pydantic模型，转换为字典
            if isinstance(response, BaseModel):
                response_dict = response.model_dump()
                response_json = json.dumps(response_dict, ensure_ascii=False, indent=2)
            # 如果已经是字典
            elif isinstance(response, dict):
                response_json = json.dumps(response, ensure_ascii=False, indent=2)
            # 其他类型，尝试转换为字符串
            else:
                response_json = str(response)

            # 打印响应数据
            self.logger.info("🔍 响应内容:")
            self.logger.info(f"{'-' * 80}")

            # 如果响应太长，进行智能截断
            if len(response_json) > 3000:
                self.logger.info(
                    f"{response_json[:2000]}\n\n... [中间省略 {len(response_json) - 3000} 字符] ...\n\n{response_json[-1000:]}"
                )
            else:
                self.logger.info(response_json)

            self.logger.info(f"{'-' * 80}\n")

            # 打印统计信息
            self.logger.info("📊 响应统计:")
            self.logger.info(f"  • 响应类型: {type(response).__name__}")
            self.logger.info(f"  • 响应长度: {len(response_json)} 字符")

            # 如果是BatchAnalysisResult，显示结果数量
            if isinstance(response, BatchAnalysisResult):
                self.logger.info(f"  • 分析结果数量: {len(response.results)}")

        except Exception as e:
            self.logger.error(f"打印LLM响应失败: {e}")
            self.logger.info(f"原始响应对象: {response}")

        self.logger.info(f"{separator}\n")

    def _load_market_prompt_template(self) -> str:
        """加载市场快照提示词模板"""
        try:
            if not self.market_prompt_path.exists():
                raise FileNotFoundError(
                    f"市场快照提示词文件不存在: {self.market_prompt_path}"
                )

            with open(self.market_prompt_path, "r", encoding="utf-8") as f:
                content = f.read().strip()

            # 打印加载的提示词长度用于调试
            self.logger.info(f"成功加载市场快照提示词，长度: {len(content)} 字符")

            if not content:
                self.logger.warning("市场快照提示词文件为空")
                return "请简要描述当前加密货币市场的现状。"

            return content
        except Exception as e:
            self.logger.error(f"加载市场快照提示词失败: {e}")
            # 返回默认提示词
            return "请简要描述当前加密货币市场的现状。"

    def _load_analysis_prompt_template(self) -> str:
        """加载分析提示词模板"""
        try:
            if not self.analysis_prompt_path.exists():
                raise FileNotFoundError(
                    f"分析提示词文件不存在: {self.analysis_prompt_path}"
                )

            with open(self.analysis_prompt_path, "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception as e:
            self.logger.error(f"加载分析提示词失败: {e}")
            raise

    def _generate_mock_results(
        self, items: List[ContentItem]
    ) -> List[StructuredAnalysisResult]:
        """生成模拟分析结果（用于测试）"""
        mock_results = []

        categories = [
            "Whale",
            "MacroLiquidity",
            "Regulation",
            "NewProject",
            "Arbitrage",
            "Truth",
            "MonetarySystem",
            "BlackSwan",
        ]

        for i, item in enumerate(items):
            # 模拟：只保留部分内容，其他被过滤
            if i % 3 == 0:  # 每3条保留1条
                mock_results.append(
                    StructuredAnalysisResult(
                        time=item.publish_time.strftime("%Y-%m-%d %H:%M"),
                        category=categories[i % len(categories)],
                        weight_score=50 + (i * 10) % 50,
                        title=item.title,
                        body=f"模拟分析: {item.title[:50]}...",
                        source=item.url,
                        related_sources=[
                            f"https://example.com/related/{i}/1",
                            f"https://example.com/related/{i}/2",
                        ],
                    )
                )

        return mock_results

    def get_dynamic_categories(
        self, results: List[StructuredAnalysisResult]
    ) -> List[str]:
        """
        从分析结果中提取动态分类

        Args:
            results: 分析结果列表

        Returns:
            分类名称列表（去重）
        """
        categories = set()
        for result in results:
            if result.category:
                categories.add(result.category)

        return sorted(list(categories))

    def classify_content_dynamic(
        self, content: str, market_context: str
    ) -> StructuredAnalysisResult:
        """
        动态分类单条内容（用于特殊场景）

        Args:
            content: 内容文本
            market_context: 市场上下文

        Returns:
            结构化分析结果
        """
        if self.mock_mode:
            return StructuredAnalysisResult(
                time=datetime.now().strftime("%Y-%m-%d %H:%M"),
                category="BlackSwan",
                weight_score=75,
                title=content[:50],
                body=f"模拟分析: {content[:50]}...",
                source="https://example.com/mock",
                related_sources=[],
            )

        if not self.client:
            raise RuntimeError("OpenAI客户端未初始化")

        # 构建消息
        messages = [
            {"role": "system", "content": market_context},
            {"role": "user", "content": f"请分析以下内容：\n\n{content}"},
        ]

        # 使用结构化输出
        result = self.structured_output_manager.force_structured_response(
            llm_client=self.client,
            messages=messages,
            model=self.model,
            max_retries=3,
            temperature=self.temperature,
            batch_mode=False,
            conversation_id=self.conversation_id,  # 传递会话ID提高缓存命中率
        )

        if isinstance(result, BatchAnalysisResult):
            raise TypeError(
                "Expected StructuredAnalysisResult for single-content analysis"
            )

        return result

    def should_ignore_content(self, content: str) -> bool:
        """
        判断内容是否应该被忽略

        注意：在四步流程中，过滤逻辑由大模型在批量分析时完成，
        此方法主要用于预处理阶段的快速过滤。

        Args:
            content: 内容文本

        Returns:
            是否应该忽略
        """
        # 基本的预过滤规则
        if not content or len(content.strip()) < 10:
            return True

        # 其他过滤逻辑由大模型在分析时完成
        return False

    def build_system_prompt(
        self, market_snapshot: Optional[MarketSnapshot] = None
    ) -> str:
        """
        构建系统提示词（便捷方法）

        注意：此方法的行为已更改。现在返回静态系统提示词（不包含动态内容）。
        如果需要包含动态内容的完整提示词，请使用 merge_prompts_with_snapshot()（已废弃）
        或使用新的 _build_user_prompt_with_context() 方法。

        Args:
            market_snapshot: 市场快照（为了向后兼容保留，但不再使用）

        Returns:
            静态系统提示词
        """
        if market_snapshot:
            self.logger.warning(
                "build_system_prompt() 不再使用 market_snapshot 参数，动态内容已移至用户提示词"
            )

        return self._build_static_system_prompt()

    def build_user_prompt(self, items: List[ContentItem]) -> str:
        """
        构建用户提示词（便捷方法，已废弃）

        注意：此方法已废弃，不包含动态上下文。
        建议使用 _build_user_prompt_with_context() 方法。

        Args:
            items: 内容项列表

        Returns:
            用户提示词（不包含动态上下文）
        """
        self.logger.warning(
            "build_user_prompt() 已废弃，建议使用 _build_user_prompt_with_context()"
        )

        from email.utils import format_datetime
        from ..utils.timezone_utils import convert_to_utc8

        prompt_parts = ["请分析以下新闻和社交媒体消息：\n"]

        for i, item in enumerate(items, 1):
            prompt_parts.append(f"\n--- 消息 {i} ---")

            if item.source_type != "x":
                prompt_parts.append(f"标题: {item.title}")

            prompt_parts.append(f"内容: {item.content}")
            prompt_parts.append(f"来源: {item.url}")

            dt_with_tz = convert_to_utc8(item.publish_time)
            rfc2822_time = format_datetime(dt_with_tz)
            prompt_parts.append(f"发布时间: {rfc2822_time}")

        prompt_parts.append("\n\n请按照要求输出JSON格式的分析结果。")

        return "\n".join(prompt_parts)

    def parse_structured_response(
        self, response: str
    ) -> List[StructuredAnalysisResult]:
        """
        解析结构化响应（用于错误恢复）

        Args:
            response: 响应字符串

        Returns:
            结构化分析结果列表
        """
        try:
            # 尝试使用结构化输出管理器恢复
            result = self.structured_output_manager.handle_malformed_response(
                response, batch_mode=True
            )

            if isinstance(result, BatchAnalysisResult):
                return result.results
            else:
                return []
        except Exception as e:
            self.logger.error(f"解析结构化响应失败: {e}")
            return []

    def validate_response_format(self, response: Dict[str, Any]) -> bool:
        """
        验证响应格式

        Args:
            response: 响应字典

        Returns:
            是否有效
        """
        validation_result = self.structured_output_manager.validate_output_structure(
            response
        )
        return validation_result.is_valid

    def handle_empty_batch_response(self) -> List[StructuredAnalysisResult]:
        """
        处理空批次响应（所有内容被过滤）

        Returns:
            空列表
        """
        self.logger.info("批次返回空结果，所有内容被过滤")
        return []

    def retry_with_fallback_model(
        self, items: List[ContentItem], error: Exception
    ) -> List[StructuredAnalysisResult]:
        """
        使用备用模型重试

        Args:
            items: 内容项列表
            error: 原始错误

        Returns:
            分析结果列表
        """
        self.logger.warning(f"主模型失败: {error}，尝试使用备用模型")

        # 这里可以实现备用模型逻辑
        # 目前返回空列表
        return []

    def get_model_info(self) -> str:
        """
        获取模型使用信息

        Returns:
            模型信息字符串，说明本次分析使用的模型
        """
        if self._last_used_model:
            return self._last_used_model
        return self._display_provider_name(self.analysis_model_runtime)

    def clear_cache(self) -> None:
        """清除缓存的市场快照和系统提示词"""
        self._cached_market_snapshot = None
        self._cached_system_prompt = None
        self._last_used_model = None  # 同时清除模型使用记录
        self.logger.info("已清除LLM分析器缓存")

    def get_cache_info(self) -> Dict[str, Any]:
        """
        获取缓存信息

        Returns:
            缓存信息字典
        """
        return {
            "has_cached_snapshot": self._cached_market_snapshot is not None,
            "has_cached_prompt": self._cached_system_prompt is not None,
            "snapshot_source": self._cached_market_snapshot.source
            if self._cached_market_snapshot
            else None,
            "snapshot_timestamp": self._cached_market_snapshot.timestamp.isoformat()
            if self._cached_market_snapshot
            else None,
        }

    def update_config(self, **kwargs) -> None:
        """
        更新配置

        Args:
            **kwargs: 配置参数
        """
        if "temperature" in kwargs:
            self.temperature = kwargs["temperature"]

        if "batch_size" in kwargs:
            self.batch_size = kwargs["batch_size"]

        if "model" in kwargs:
            runtime = kwargs["model"]
            if isinstance(runtime, ResolvedModelRuntime):
                self.analysis_model_runtime = runtime
                self.model = runtime.name
                self.analysis_provider = runtime.provider_name
                self.analysis_api_key = self.provider_credentials.get(
                    self.analysis_provider, ""
                )

        self.logger.info("LLM分析器配置已更新")

    def _record_token_usage(self, usage_data: Dict[str, Any]) -> None:
        """
        记录token使用情况的回调函数

        Args:
            usage_data: 包含token使用信息的字典
        """
        try:
            self.token_tracker.record_usage(
                model=usage_data.get("model", self.model),
                prompt_tokens=usage_data.get("prompt_tokens", 0),
                completion_tokens=usage_data.get("completion_tokens", 0),
                total_tokens=usage_data.get("total_tokens", 0),
                cached_tokens=usage_data.get("cached_tokens", 0),
                conversation_id=self.conversation_id,
            )
        except Exception as e:
            self.logger.warning(f"记录token使用情况失败: {e}")
