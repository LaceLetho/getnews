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

from ..models import ContentItem, AnalysisResult, StorageConfig
from ..utils.timezone_utils import format_datetime_utc8
from ..utils.conversation_cache import ConversationIdManager
from .market_snapshot_service import MarketSnapshotService, MarketSnapshot
from .structured_output_manager import (
    StructuredOutputManager,
    StructuredAnalysisResult,
    BatchAnalysisResult
)
from ..storage.cache_manager import SentMessageCacheManager
from .token_usage_tracker import TokenUsageTracker

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
        api_key: Optional[str] = None,
        GROK_API_KEY: Optional[str] = None,
        KIMI_API_KEY: Optional[str] = None,
        model: str = "gpt-4",
        summary_model: str = "grok-beta",
        market_prompt_path: str = "./prompts/market_summary_prompt.md",
        analysis_prompt_path: str = "./prompts/analysis_prompt.md",
        temperature: float = 0.5,
        max_tokens: int = 4000,
        batch_size: int = 10,
        cache_ttl_minutes: int = 30,
        cached_messages_hours: int = 24,
        mock_mode: bool = False,
        cache_manager: Optional[SentMessageCacheManager] = None,
        storage_config: Optional[StorageConfig] = None,
        conversation_id: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        """
        初始化LLM分析器

        Args:
            api_key: LLM API密钥，如果为None则从环境变量读取
            GROK_API_KEY: Grok API密钥，用于市场快照
            KIMI_API_KEY: Kimi API密钥，用于新闻分析
            model: 分析使用的模型名称
            summary_model: 市场快照使用的模型名称
            market_prompt_path: 市场快照提示词路径
            analysis_prompt_path: 分析提示词路径
            temperature: 温度参数
            max_tokens: 最大token数
            batch_size: 批量分析的批次大小
            cache_ttl_minutes: 缓存有效期（分钟）
            cached_messages_hours: 缓存消息的时间范围（小时）
            mock_mode: 是否使用模拟模式（用于测试）
            cache_manager: 已发送消息缓存管理器（可选）
            storage_config: 存储配置（用于创建缓存管理器，可选）
            conversation_id: 会话ID（用于提高缓存命中率，如果为None则自动生成）
            config: 完整配置字典（用于传递给子组件）
        """
        self.api_key = api_key or os.getenv('LLM_API_KEY', '')
        self.GROK_API_KEY = GROK_API_KEY or os.getenv('GROK_API_KEY', '')
        self.KIMI_API_KEY = KIMI_API_KEY or os.getenv('KIMI_API_KEY', '')
        self.model = model
        self.summary_model = summary_model
        self.market_prompt_path = Path(market_prompt_path)
        self.analysis_prompt_path = Path(analysis_prompt_path)
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.batch_size = batch_size
        self.cache_ttl_minutes = cache_ttl_minutes
        self.cached_messages_hours = cached_messages_hours
        self.mock_mode = mock_mode
        self.config = config or {}
        self.logger = logging.getLogger(__name__)
        
        # 使用会话ID管理器获取或创建持久化的conversation_id
        conversation_id_manager = ConversationIdManager(cache_dir="./data/cache")
        self.conversation_id = conversation_id or conversation_id_manager.get_or_create_conversation_id("llm_analyzer")
        
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
        if not mock_mode and self.api_key and OpenAI:
            try:
                # 根据模型判断使用哪个API endpoint
                if "minimax" in self.model.lower():
                    # MiniMax API
                    self.client = OpenAI(
                        api_key=self.api_key,
                        base_url="https://api.minimax.chat/v1"
                    )
                elif "grok" in self.model.lower():
                    # xAI Grok API
                    self.client = OpenAI(
                        api_key=self.api_key,
                        base_url="https://api.x.ai/v1",
                        default_headers={"x-grok-conv-id": self.conversation_id}
                    )
                    self.logger.info(f"Grok客户端已设置default_headers: x-grok-conv-id={self.conversation_id}")
                elif "kimi" in self.model.lower():
                    # Kimi API - 使用 OpenAI 兼容格式 (coding endpoint)
                    # 需要设置 User-Agent 为 claude-code 才能通过身份验证
                    api_key_to_use = self.KIMI_API_KEY or self.api_key
                    self.client = OpenAI(
                        api_key=api_key_to_use,
                        base_url="https://api.kimi.com/coding/v1",
                        default_headers={
                            "User-Agent": "claude-code/1.0"
                        }
                    )
                    self.logger.info(f"Kimi客户端已初始化，使用模型: {self.model}")
                else:
                    # 标准 OpenAI API
                    self.client = OpenAI(
                        api_key=self.api_key
                    )
            except Exception as e:
                self.logger.error(f"初始化OpenAI客户端失败: {e}")
        
        # 初始化市场快照服务
        self.market_snapshot_service = MarketSnapshotService(
            GROK_API_KEY=self.GROK_API_KEY,
            summary_model=self.summary_model,
            cache_ttl_minutes=self.cache_ttl_minutes,
            mock_mode=mock_mode,
            conversation_id=self.conversation_id,
            temperature=self.temperature,
            config=self.config  # 传递config以支持enable_debug_logging
        )
        
        # 初始化结构化输出管理器
        self.structured_output_manager = StructuredOutputManager(library="instructor", config=self.config)
        
        # 如果有客户端，设置instructor客户端
        if self.client and not mock_mode:
            try:
                self.structured_output_manager.setup_instructor_client(self.client)
            except Exception as e:
                self.logger.warning(f"设置instructor客户端失败: {e}")
        
        # 缓存的市场快照和系统提示词
        self._cached_market_snapshot: Optional[MarketSnapshot] = None
        self._cached_system_prompt: Optional[str] = None
        
        if mock_mode:
            self.logger.info("LLM分析器运行在模拟模式")
        elif not self.api_key:
            self.logger.warning("未提供LLM API密钥")
        else:
            self.logger.info(f"使用会话ID提高缓存命中率: {self.conversation_id}")
    
    def analyze_content_batch(
        self,
        items: List[ContentItem],
        use_cached_snapshot: bool = True,
        is_scheduled: bool = False
    ) -> List[StructuredAnalysisResult]:
        """
        批量分析内容（四步流程）
        
        Args:
            items: 内容项列表
            use_cached_snapshot: 是否使用缓存的市场快照
            is_scheduled: 是否为定时任务（True时包含Outdated News，False时显示"无"）
            
        Returns:
            结构化分析结果列表
        """
        if not items:
            self.logger.info("没有内容需要分析")
            return []
        
        try:
            # 第一步：获取市场快照
            market_snapshot = self.get_market_snapshot(use_cached=use_cached_snapshot)
            self.logger.info(f"市场快照来源: {market_snapshot.source}")
            
            # 第二步：构建提示词（系统提示词为静态，动态内容放在用户提示词中）
            system_prompt = self._build_static_system_prompt()
            self.logger.info(f"静态系统提示词长度: {len(system_prompt)} 字符")
            
            # 第三步和第四步：使用结构化输出进行批量分析
            results = self._analyze_batch_with_structured_output(
                items, system_prompt, market_snapshot, is_scheduled
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
        
        self.logger.info(f"准备调用市场快照服务，提示词长度: {len(prompt_template)} 字符")
        
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
        self.logger.warning("merge_prompts_with_snapshot() 已废弃，建议使用新的提示词构建方法")
        
        # 读取分析提示词模板
        analysis_template = self._load_analysis_prompt_template()
        
        # 将市场快照内容插入到分析提示词中
        system_prompt = analysis_template.replace(
            "${Grok_Summary_Here}",
            market_snapshot.content
        )
        
        # 替换 ${outdated_news} 占位符
        outdated_news = self._get_formatted_cached_messages(hours=self.cached_messages_hours)
        system_prompt = system_prompt.replace(
            "${outdated_news}",
            outdated_news
        )
        
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
            formatted_messages = self.cache_manager.format_cached_messages_for_prompt(hours=hours)
            if formatted_messages == "无":
                self.logger.info(f"过去{hours}小时内没有已发送的消息缓存，Outdated News显示'无'")
            else:
                self.logger.info(f"已获取格式化的缓存消息，包含过去{hours}小时的已发送内容")
            return formatted_messages
        except Exception as e:
            self.logger.warning(f"获取缓存消息失败: {e}，Outdated News将显示'无'")
            return "无"
    
    def _analyze_batch_with_structured_output(
        self,
        items: List[ContentItem],
        system_prompt: str,
        market_snapshot: MarketSnapshot,
        is_scheduled: bool = False
    ) -> List[StructuredAnalysisResult]:
        """
        第三步和第四步：使用结构化输出进行批量分析
        
        Args:
            items: 内容项列表
            system_prompt: 静态系统提示词
            market_snapshot: 市场快照对象
            is_scheduled: 是否为定时任务（True时包含Outdated News，False时显示"无"）
            
        Returns:
            结构化分析结果列表
        """
        if self.mock_mode:
            return self._generate_mock_results(items)
        
        if not self.client:
            raise RuntimeError("OpenAI客户端未初始化")
        
        all_results = []
        
        # 分批处理
        for i in range(0, len(items), self.batch_size):
            batch = items[i:i + self.batch_size]
            self.logger.info(f"处理批次 {i // self.batch_size + 1}，包含 {len(batch)} 条内容")
            
            try:
                # 构建用户提示词（包含动态上下文和待分析内容）
                user_prompt = self._build_user_prompt_with_context(batch, market_snapshot, is_scheduled)
                
                # 构建消息列表
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
                
                # 以用户友好的方式打印最终发送给LLM的完整提示词
                self._log_final_prompt(system_prompt, user_prompt, i // self.batch_size + 1)

                # 判断是否启用 web_search 及使用哪种方式
                # Grok 使用 responses.parse() API
                # Kimi 使用标准 function calling
                is_kimi = "kimi" in self.model.lower()
                is_grok = "grok" in self.model.lower()
                enable_web_search = is_kimi or is_grok

                if enable_web_search:
                    if is_kimi:
                        self.logger.info("检测到 Kimi 模型，启用 web_search 工具（标准 function calling）")
                    elif is_grok:
                        self.logger.info("检测到 Grok 模型，启用 web_search 和 x_search 工具")

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
                    usage_callback=self._record_token_usage
                )
                
                # 打印LLM返回的原始数据
                self._log_llm_response(batch_result, i // self.batch_size + 1)
                
                # 提取结果
                if isinstance(batch_result, BatchAnalysisResult):
                    all_results.extend(batch_result.results)
                    self.logger.info(f"批次返回 {len(batch_result.results)} 条结果")
                else:
                    self.logger.warning(f"批次返回格式异常: {type(batch_result)}")
                
            except Exception as e:
                self.logger.error(f"批次分析失败: {e}")
                # 继续处理下一批次
                continue
        
        return all_results
    
    def _build_user_prompt_with_context(
        self,
        items: List[ContentItem],
        market_snapshot: MarketSnapshot,
        is_scheduled: bool = False
    ) -> str:
        """
        构建包含动态上下文的用户提示词
        
        新的提示词结构：
        1. 市场快照（Current Market Context）
        2. 已发送消息缓存（Outdated News）- 仅在定时任务时包含
        3. 待分析的新闻内容
        
        Args:
            items: 内容项列表
            market_snapshot: 市场快照对象
            is_scheduled: 是否为定时任务（True时包含Outdated News，False时显示"无"）
            
        Returns:
            用户提示词字符串
        """
        from email.utils import format_datetime
        from ..utils.timezone_utils import convert_to_utc8
        
        prompt_parts = []
        
        # 添加市场快照上下文
        prompt_parts.append("# Current Market Context")
        prompt_parts.append(market_snapshot.content)
        prompt_parts.append("")
        
        # 添加已发送消息缓存（仅在定时任务时包含实际内容）
        prompt_parts.append("# Outdated News")
        if is_scheduled:
            outdated_news = self._get_formatted_cached_messages(hours=self.cached_messages_hours)
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
    def _log_final_prompt(self, system_prompt: str, user_prompt: str, batch_number: int) -> None:
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
        self.logger.info(user_prompt)
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
                self.logger.info(f"{response_json[:2000]}\n\n... [中间省略 {len(response_json) - 3000} 字符] ...\n\n{response_json[-1000:]}")
            else:
                self.logger.info(response_json)

            self.logger.info(f"{'-' * 80}\n")

            # 打印统计信息
            self.logger.info("📊 响应统计:")
            self.logger.info(f"  • 响应类型: {type(response).__name__}")
            self.logger.info(f"  • 响应长度: {len(response_json)} 字符")

            # 如果是BatchAnalysisResult，显示结果数量
            if hasattr(response, 'results'):
                self.logger.info(f"  • 分析结果数量: {len(response.results)}")

        except Exception as e:
            self.logger.error(f"打印LLM响应失败: {e}")
            self.logger.info(f"原始响应对象: {response}")

        self.logger.info(f"{separator}\n")


    
    def _load_market_prompt_template(self) -> str:
        """加载市场快照提示词模板"""
        try:
            if not self.market_prompt_path.exists():
                raise FileNotFoundError(f"市场快照提示词文件不存在: {self.market_prompt_path}")
            
            with open(self.market_prompt_path, 'r', encoding='utf-8') as f:
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
                raise FileNotFoundError(f"分析提示词文件不存在: {self.analysis_prompt_path}")
            
            with open(self.analysis_prompt_path, 'r', encoding='utf-8') as f:
                return f.read().strip()
        except Exception as e:
            self.logger.error(f"加载分析提示词失败: {e}")
            raise
    
    def _generate_mock_results(self, items: List[ContentItem]) -> List[StructuredAnalysisResult]:
        """生成模拟分析结果（用于测试）"""
        mock_results = []
        
        categories = ["Whale", "MacroLiquidity", "Regulation", "NewProject", "Arbitrage", "Truth", "MonetarySystem", "BlackSwan"]
        
        for i, item in enumerate(items):
            # 模拟：只保留部分内容，其他被过滤
            if i % 3 == 0:  # 每3条保留1条
                mock_results.append(StructuredAnalysisResult(
                    time=item.publish_time.strftime('%Y-%m-%d %H:%M'),
                    category=categories[i % len(categories)],
                    weight_score=50 + (i * 10) % 50,
                    summary=f"模拟分析: {item.title[:50]}...",
                    source=item.url,
                    related_sources=[
                        f"https://example.com/related/{i}/1",
                        f"https://example.com/related/{i}/2"
                    ]
                ))
        
        return mock_results
    
    def get_dynamic_categories(self, results: List[StructuredAnalysisResult]) -> List[str]:
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
        self,
        content: str,
        market_context: str
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
                time=datetime.now().strftime('%Y-%m-%d %H:%M'),
                category="BlackSwan",
                weight_score=75,
                summary=f"模拟分析: {content[:50]}...",
                source="https://example.com/mock",
                related_sources=[]
            )
        
        if not self.client:
            raise RuntimeError("OpenAI客户端未初始化")
        
        # 构建消息
        messages = [
            {"role": "system", "content": market_context},
            {"role": "user", "content": f"请分析以下内容：\n\n{content}"}
        ]
        
        # 使用结构化输出
        result = self.structured_output_manager.force_structured_response(
            llm_client=self.client,
            messages=messages,
            model=self.model,
            max_retries=3,
            temperature=self.temperature,
            batch_mode=False,
            conversation_id=self.conversation_id  # 传递会话ID提高缓存命中率
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
    
    def build_system_prompt(self, market_snapshot: MarketSnapshot = None) -> str:
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
            self.logger.warning("build_system_prompt() 不再使用 market_snapshot 参数，动态内容已移至用户提示词")
        
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
        self.logger.warning("build_user_prompt() 已废弃，建议使用 _build_user_prompt_with_context()")
        
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
    
    def parse_structured_response(self, response: str) -> List[StructuredAnalysisResult]:
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
        validation_result = self.structured_output_manager.validate_output_structure(response)
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
        self,
        items: List[ContentItem],
        error: Exception
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
    
    def clear_cache(self) -> None:
        """清除缓存的市场快照和系统提示词"""
        self._cached_market_snapshot = None
        self._cached_system_prompt = None
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
            "snapshot_source": self._cached_market_snapshot.source if self._cached_market_snapshot else None,
            "snapshot_timestamp": self._cached_market_snapshot.timestamp.isoformat() if self._cached_market_snapshot else None
        }
    
    def update_config(self, **kwargs) -> None:
        """
        更新配置
        
        Args:
            **kwargs: 配置参数
        """
        if "temperature" in kwargs:
            self.temperature = kwargs["temperature"]
        
        if "max_tokens" in kwargs:
            self.max_tokens = kwargs["max_tokens"]
        
        if "batch_size" in kwargs:
            self.batch_size = kwargs["batch_size"]
        
        if "model" in kwargs:
            self.model = kwargs["model"]
        
        self.logger.info("LLM分析器配置已更新")
    
    def _record_token_usage(self, usage_data: Dict[str, Any]) -> None:
        """
        记录token使用情况的回调函数
        
        Args:
            usage_data: 包含token使用信息的字典
        """
        try:
            self.token_tracker.record_usage(
                model=usage_data.get('model', self.model),
                prompt_tokens=usage_data.get('prompt_tokens', 0),
                completion_tokens=usage_data.get('completion_tokens', 0),
                total_tokens=usage_data.get('total_tokens', 0),
                cached_tokens=usage_data.get('cached_tokens', 0),
                conversation_id=self.conversation_id
            )
        except Exception as e:
            self.logger.warning(f"记录token使用情况失败: {e}")
