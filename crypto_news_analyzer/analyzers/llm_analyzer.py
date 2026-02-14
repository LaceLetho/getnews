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
from typing import List, Dict, Any, Optional, Union
from datetime import datetime
from pathlib import Path

from ..models import ContentItem, AnalysisResult, StorageConfig
from ..utils.timezone_utils import format_datetime_utc8
from .market_snapshot_service import MarketSnapshotService, MarketSnapshot
from .structured_output_manager import (
    StructuredOutputManager,
    StructuredAnalysisResult,
    BatchAnalysisResult
)
from ..storage.cache_manager import SentMessageCacheManager

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
        model: str = "gpt-4",
        summary_model: str = "grok-beta",
        market_prompt_path: str = "./prompts/market_summary_prompt.md",
        analysis_prompt_path: str = "./prompts/analysis_prompt.md",
        temperature: float = 0.1,
        max_tokens: int = 4000,
        batch_size: int = 10,
        cache_ttl_minutes: int = 30,
        mock_mode: bool = False,
        cache_manager: Optional[SentMessageCacheManager] = None,
        storage_config: Optional[StorageConfig] = None
    ):
        """
        初始化LLM分析器
        
        Args:
            api_key: LLM API密钥，如果为None则从环境变量读取
            GROK_API_KEY: Grok API密钥，用于市场快照
            model: 分析使用的模型名称
            summary_model: 市场快照使用的模型名称
            market_prompt_path: 市场快照提示词路径
            analysis_prompt_path: 分析提示词路径
            temperature: 温度参数
            max_tokens: 最大token数
            batch_size: 批量分析的批次大小
            cache_ttl_minutes: 缓存有效期（分钟）
            mock_mode: 是否使用模拟模式（用于测试）
            cache_manager: 已发送消息缓存管理器（可选）
            storage_config: 存储配置（用于创建缓存管理器，可选）
        """
        self.api_key = api_key or os.getenv('LLM_API_KEY', '')
        self.GROK_API_KEY = GROK_API_KEY or os.getenv('GROK_API_KEY', '')
        self.model = model
        self.summary_model = summary_model
        self.market_prompt_path = Path(market_prompt_path)
        self.analysis_prompt_path = Path(analysis_prompt_path)
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.batch_size = batch_size
        self.cache_ttl_minutes = cache_ttl_minutes
        self.mock_mode = mock_mode
        self.logger = logging.getLogger(__name__)
        
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
                        base_url="https://api.x.ai/v1"
                    )
                else:
                    # 标准 OpenAI API
                    self.client = OpenAI(api_key=self.api_key)
            except Exception as e:
                self.logger.error(f"初始化OpenAI客户端失败: {e}")
        
        # 初始化市场快照服务
        self.market_snapshot_service = MarketSnapshotService(
            GROK_API_KEY=self.GROK_API_KEY,
            summary_model=self.summary_model,
            cache_ttl_minutes=self.cache_ttl_minutes,
            mock_mode=mock_mode
        )
        
        # 初始化结构化输出管理器
        self.structured_output_manager = StructuredOutputManager(library="instructor")
        
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
    
    def analyze_content_batch(
        self,
        items: List[ContentItem],
        use_cached_snapshot: bool = True
    ) -> List[StructuredAnalysisResult]:
        """
        批量分析内容（四步流程）
        
        Args:
            items: 内容项列表
            use_cached_snapshot: 是否使用缓存的市场快照
            
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
            
            # 第二步：合并提示词（注意市场快照中的超链接部分不要合并）
            system_prompt = self.merge_prompts_with_snapshot(market_snapshot)
            self.logger.info(f"系统提示词长度: {len(system_prompt)} 字符")
            
            # 第三步和第四步：使用结构化输出进行批量分析
            results = self._analyze_batch_with_structured_output(
                items, system_prompt
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
        
        # 调用市场快照服务获取快照
        snapshot = self.market_snapshot_service.get_market_snapshot(prompt_template)
        
        # 缓存快照
        self._cached_market_snapshot = snapshot
        
        return snapshot
    
    def merge_prompts_with_snapshot(self, market_snapshot: MarketSnapshot) -> str:
        """
        第二步：合并提示词（注意市场快照中的超链接部分不要合并）
        
        Args:
            market_snapshot: 市场快照对象
            
        Returns:
            合并后的系统提示词
        """
        # 读取分析提示词模板
        analysis_template = self._load_analysis_prompt_template()
        
        # 将市场快照内容插入到分析提示词中
        # 查找 ${Grok_Summary_Here} 占位符并替换
        system_prompt = analysis_template.replace(
            "${Grok_Summary_Here}",
            market_snapshot.content
        )
        
        # 替换 ${outdated_news} 占位符（最近12小时）
        outdated_news = self._get_formatted_cached_messages(hours=12)
        system_prompt = system_prompt.replace(
            "${outdated_news}",
            outdated_news
        )
        
        # 缓存系统提示词
        self._cached_system_prompt = system_prompt
        
        return system_prompt
    
    def _get_formatted_cached_messages(self, hours: int = 12) -> str:
        """
        获取格式化的缓存消息
        
        Args:
            hours: 时间范围（小时），默认12小时
        
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
        system_prompt: str
    ) -> List[StructuredAnalysisResult]:
        """
        第三步和第四步：使用结构化输出进行批量分析
        
        Args:
            items: 内容项列表
            system_prompt: 系统提示词
            
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
                # 构建用户提示词
                user_prompt = self._build_user_prompt(batch)
                
                # 构建消息列表
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
                
                # 以用户友好的方式打印最终发送给LLM的完整提示词
                self._log_final_prompt(system_prompt, user_prompt, i // self.batch_size + 1)
                
                # 使用结构化输出管理器强制返回结构化数据（启用web_search工具）
                batch_result = self.structured_output_manager.force_structured_response(
                    llm_client=self.client,
                    messages=messages,
                    model=self.model,
                    max_retries=3,
                    temperature=self.temperature,
                    batch_mode=True,
                    enable_web_search=True  # 启用web_search工具
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
    
    def _build_user_prompt(self, items: List[ContentItem]) -> str:
        """
        构建用户提示词（批量内容）
        
        Args:
            items: 内容项列表
            
        Returns:
            用户提示词字符串
        """
        from email.utils import format_datetime
        from ..utils.timezone_utils import convert_to_utc8
        
        prompt_parts = ["请分析以下新闻和社交媒体内容：\n"]
        
        for i, item in enumerate(items, 1):
            prompt_parts.append(f"\n--- 内容 {i} ---")
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
        # 截断过长的系统提示词，只显示前500字符和后200字符
        if len(system_prompt) > 700:
            self.logger.info(f"{system_prompt[:500]}\n\n... [中间省略 {len(system_prompt) - 700} 字符] ...\n\n{system_prompt[-200:]}")
        else:
            self.logger.info(system_prompt)
        self.logger.info(f"{'-' * 80}\n")

        # 打印用户提示词
        self.logger.info("👤 用户提示词 (User Prompt):")
        self.logger.info(f"{'-' * 80}")
        # 截断过长的用户提示词，只显示前1000字符和后300字符
        if len(user_prompt) > 1300:
            self.logger.info(f"{user_prompt[:1000]}\n\n... [中间省略 {len(user_prompt) - 1300} 字符] ...\n\n{user_prompt[-300:]}")
        else:
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
                return f.read().strip()
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
        
        categories = ["Whale", "MacroLiquidity", "Regulation", "NewProject", "Arbitrage", "Truth", "MonetarySystem", "MarketTrend"]
        
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
                category="MarketTrend",
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
            batch_mode=False
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
    
    def build_system_prompt(self, market_snapshot: MarketSnapshot) -> str:
        """
        构建系统提示词（便捷方法）
        
        此方法会自动替换 ${Grok_Summary_Here} 和 ${outdated_news} 占位符
        
        Args:
            market_snapshot: 市场快照
            
        Returns:
            系统提示词
        """
        return self.merge_prompts_with_snapshot(market_snapshot)
    
    def build_user_prompt(self, items: List[ContentItem]) -> str:
        """
        构建用户提示词（便捷方法）
        
        Args:
            items: 内容项列表
            
        Returns:
            用户提示词
        """
        return self._build_user_prompt(items)
    
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
