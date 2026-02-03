"""
LLM分析器

与大语言模型API集成，进行内容分析和分类。
"""

import json
import logging
import time
from typing import Dict, Any, List, Optional
import requests
from dataclasses import dataclass

from ..models import ContentItem, AnalysisResult
from .prompt_manager import PromptManager, DynamicCategoryManager


@dataclass
class LLMResponse:
    """LLM响应数据"""
    category: str
    confidence: float
    reasoning: str
    should_ignore: bool
    key_points: List[str]


class LLMAnalyzer:
    """LLM分析器"""
    
    def __init__(self, api_key: str, model: str = "MiniMax-M2.1", 
                 prompt_config_path: str = "./prompts/analysis_prompt.json",
                 api_base_url: str = "https://api.minimax.chat/v1",
                 mock_mode: bool = False):
        """
        初始化LLM分析器
        
        Args:
            api_key: LLM API密钥
            model: 模型名称 (支持 MiniMax-M2.1, MiniMax-M2.1-lightning, MiniMax-M2, gpt-4等)
            prompt_config_path: 提示词配置文件路径
            api_base_url: API基础URL
            mock_mode: 是否使用模拟模式（用于测试）
        """
        self.api_key = api_key
        self.model = model
        self.mock_mode = mock_mode
        self.prompt_manager = PromptManager(prompt_config_path)
        self.category_manager = DynamicCategoryManager(prompt_config_path)
        self.logger = logging.getLogger(__name__)
        
        # 根据模型自动选择API配置
        if model.startswith("MiniMax"):
            # 使用 MiniMax 平台 API 端点（新 API key 格式）
            self.api_base_url = "https://platform.minimax.io/v1"
            self.use_minimax_format = True
        elif model.startswith("gpt"):
            self.api_base_url = "https://api.openai.com/v1"
            self.use_minimax_format = False
        else:
            self.api_base_url = api_base_url
            self.use_minimax_format = False
            
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        # 重试配置
        self.max_retries = 3
        self.retry_delay = 1.0
        
        if mock_mode:
            self.logger.info("LLM分析器运行在模拟模式")
        
    def analyze_content(self, content: str, title: str = "", source: str = "", content_id: str = "") -> AnalysisResult:
        """
        分析单个内容
        
        Args:
            content: 内容文本
            title: 标题
            source: 来源
            content_id: 内容ID
            
        Returns:
            分析结果
        """
        try:
            # 构建提示词
            prompt = self.prompt_manager.build_analysis_prompt(content, title, source)
            
            # 调用LLM API
            llm_response = self._call_llm_api(prompt)
            
            # 解析响应
            parsed_response = self.parse_llm_response(llm_response)
            
            # 验证分类
            if not self._validate_category_response(parsed_response.category):
                self.logger.warning(f"无效分类: {parsed_response.category}，设为未分类")
                parsed_response.category = "未分类"
            
            # 创建分析结果
            result = AnalysisResult(
                content_id=content_id or "temp_id",  # 提供默认ID
                category=parsed_response.category,
                confidence=parsed_response.confidence,
                reasoning=parsed_response.reasoning,
                should_ignore=parsed_response.should_ignore,
                key_points=parsed_response.key_points
            )
            
            self.logger.info(f"内容分析完成: {parsed_response.category} (置信度: {parsed_response.confidence})")
            return result
            
        except Exception as e:
            self.logger.error(f"内容分析失败: {e}")
            # 返回默认结果
            return AnalysisResult(
                content_id=content_id or "temp_id",
                category="未分类",
                confidence=0.0,
                reasoning=f"分析失败: {str(e)}",
                should_ignore=False,
                key_points=[]
            )
    
    def batch_analyze(self, items: List[ContentItem]) -> List[AnalysisResult]:
        """
        批量分析内容
        
        Args:
            items: 内容项列表
            
        Returns:
            分析结果列表
        """
        results = []
        
        # 获取批量大小配置
        llm_settings = self.prompt_manager.get_llm_settings()
        batch_size = llm_settings.get("batch_size", 10)
        
        self.logger.info(f"开始批量分析 {len(items)} 个内容项，批量大小: {batch_size}")
        
        for i in range(0, len(items), batch_size):
            batch = items[i:i + batch_size]
            
            for item in batch:
                result = self.analyze_content(item.content, item.title, item.source_name)
                result.content_id = item.id
                results.append(result)
                
                # 添加延迟避免API限制
                time.sleep(0.1)
            
            # 批次间延迟
            if i + batch_size < len(items):
                time.sleep(1.0)
        
        self.logger.info(f"批量分析完成，共处理 {len(results)} 个项目")
        return results
    
    def classify_content(self, content: str) -> str:
        """
        简单分类内容（不返回详细分析）
        
        Args:
            content: 内容文本
            
        Returns:
            分类名称
        """
        result = self.analyze_content(content)
        return result.category
    
    def should_ignore_content(self, content: str) -> bool:
        """
        判断内容是否应该忽略
        
        Args:
            content: 内容文本
            
        Returns:
            是否应该忽略
        """
        result = self.analyze_content(content)
        return result.should_ignore
    
    def parse_llm_response(self, response: str) -> LLMResponse:
        """
        解析LLM响应
        
        Args:
            response: LLM响应文本
            
        Returns:
            解析后的响应对象
        """
        try:
            # 清理响应文本，移除 <think> 标签和其他非JSON内容
            cleaned_response = self._clean_response_text(response)
            
            # 尝试解析JSON响应
            response_data = json.loads(cleaned_response)
            
            return LLMResponse(
                category=response_data.get("category", "未分类"),
                confidence=float(response_data.get("confidence", 0.0)),
                reasoning=response_data.get("reasoning", ""),
                should_ignore=bool(response_data.get("should_ignore", False)),
                key_points=response_data.get("key_points", [])
            )
            
        except json.JSONDecodeError as e:
            self.logger.error(f"解析LLM响应JSON失败: {e}")
            # 尝试从文本中提取信息
            return self._parse_text_response(response)
        except Exception as e:
            self.logger.error(f"解析LLM响应失败: {e}")
            return LLMResponse(
                category="未分类",
                confidence=0.0,
                reasoning=f"解析失败: {str(e)}",
                should_ignore=False,
                key_points=[]
            )
    
    def _clean_response_text(self, response: str) -> str:
        """
        清理响应文本，提取JSON部分
        
        Args:
            response: 原始响应文本
            
        Returns:
            清理后的JSON字符串
        """
        import re
        
        # 移除 <think> 标签及其内容
        response = re.sub(r'<think>.*?</think>', '', response, flags=re.DOTALL)
        
        # 查找JSON对象
        json_match = re.search(r'\{.*\}', response, flags=re.DOTALL)
        if json_match:
            return json_match.group(0).strip()
        
        # 如果没有找到JSON，返回原始响应
        return response.strip()
    
    def reload_prompt_config(self) -> None:
        """重新加载提示词配置"""
        self.prompt_manager.reload_configuration()
        self.category_manager.reload_categories()
        self.logger.info("提示词配置已重新加载")
    
    def _call_llm_api(self, prompt: str) -> str:
        """
        调用LLM API
        
        Args:
            prompt: 提示词
            
        Returns:
            API响应文本
        """
        if self.mock_mode:
            return self._generate_mock_response(prompt)
            
        llm_settings = self.prompt_manager.get_llm_settings()
        
        if self.model.startswith("MiniMax"):
            # 使用 OpenAI 兼容格式（适用于 platform.minimax.io）
            payload = {
                "model": self.model,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "temperature": llm_settings.get("temperature", 0.1),
                "max_tokens": llm_settings.get("max_tokens", 1000)
            }
            endpoint = f"{self.api_base_url}/chat/completions"
        else:
            # 使用 OpenAI 格式
            payload = {
                "model": self.model,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "temperature": llm_settings.get("temperature", 0.1),
                "max_tokens": llm_settings.get("max_tokens", 1000)
            }
            endpoint = f"{self.api_base_url}/chat/completions"
        
        for attempt in range(self.max_retries):
            try:
                response = requests.post(
                    endpoint,
                    headers=self.headers,
                    json=payload,
                    timeout=30
                )
                
                if response.status_code == 200:
                    response_data = response.json()
                    
                    # 统一使用 OpenAI 格式解析
                    if "choices" in response_data and len(response_data["choices"]) > 0:
                        choice = response_data["choices"][0]
                        if "message" in choice and "content" in choice["message"]:
                            return choice["message"]["content"]
                        elif "text" in choice:
                            return choice["text"]
                    
                    # 如果没有找到标准格式，记录错误
                    self.logger.error(f"无法解析响应格式: {response_data}")
                    return ""
                        
                elif response.status_code == 429:
                    # 速率限制，等待更长时间
                    wait_time = self.retry_delay * (2 ** attempt)
                    self.logger.warning(f"API速率限制，等待 {wait_time} 秒后重试")
                    time.sleep(wait_time)
                else:
                    self.logger.error(f"API调用失败: {response.status_code} - {response.text}")
                    if attempt == self.max_retries - 1:
                        raise Exception(f"API调用失败: {response.status_code}")
                    
            except requests.exceptions.Timeout:
                self.logger.warning(f"API调用超时，第 {attempt + 1} 次重试")
                if attempt == self.max_retries - 1:
                    raise Exception("API调用超时")
                time.sleep(self.retry_delay)
            except Exception as e:
                self.logger.error(f"API调用异常: {e}")
                if attempt == self.max_retries - 1:
                    raise
                time.sleep(self.retry_delay)
        
        raise Exception("API调用失败，已达到最大重试次数")
    
    def _generate_mock_response(self, prompt: str) -> str:
        """
        生成模拟响应（用于测试）
        
        Args:
            prompt: 提示词
            
        Returns:
            模拟的JSON响应
        """
        # 从提示词中提取实际要分析的内容
        # 查找 "内容：" 后面的实际内容
        content_start = prompt.find("内容：")
        if content_start != -1:
            content_section = prompt[content_start + 3:]  # 跳过 "内容："
            # 查找内容结束位置（通常是 "来源：" 或 "---"）
            content_end = content_section.find("来源：")
            if content_end == -1:
                content_end = content_section.find("---")
            if content_end != -1:
                actual_content = content_section[:content_end].strip()
            else:
                actual_content = content_section.strip()
        else:
            # 如果找不到标准格式，使用整个提示词
            actual_content = prompt
        
        content_lower = actual_content.lower()
        
        # 获取可用的分类列表
        try:
            categories = self.category_manager.load_categories()
            available_categories = list(categories.keys())
        except Exception:
            # 如果无法加载配置，使用默认分类
            available_categories = ["大户动向", "利率事件", "美国政府监管政策", "安全事件", "新产品", "市场新现象"]
        
        # 基于内容关键词进行智能分类匹配
        category_keywords = {
            # 大户动向相关关键词
            "大户动向": ["15000", "eth", "binance", "巨鲸地址转移", "转移", "巨鲸", "大户", "资金流动"],
            # 利率事件相关关键词  
            "利率事件": ["美联储", "会议纪要", "降息", "鲍威尔", "通胀数据", "fomc", "利率", "委员"],
            # 监管政策相关关键词
            "美国政府监管政策": ["sec", "监管", "政策", "法案", "cftc", "财政部"],
            # 安全事件相关关键词
            "安全事件": ["黑客攻击", "defi协议", "500万美元", "重入漏洞", "被盗", "安全", "漏洞", "攻击"],
            # 新产品相关关键词
            "新产品": ["新项目", "协议", "创新", "发布", "上线"],
            # 市场新现象相关关键词
            "市场新现象": ["新趋势", "链上数据", "异常", "新模式", "现象"]
        }
        
        # 检查是否应该忽略（先检查忽略条件）
        ignore_keywords = ["🚀", "超高收益率", "立即参与", "千载难逢"]
        should_ignore = any(keyword in content_lower for keyword in ignore_keywords)
        
        if should_ignore:
            return json.dumps({
                "category": "忽略",
                "confidence": 0.95,
                "reasoning": "内容疑似广告或推广软文，应该忽略。",
                "should_ignore": True,
                "key_points": ["广告内容", "推广信息"]
            }, ensure_ascii=False)
        
        # 查找匹配的分类
        matched_category = None
        max_matches = 0
        
        for category_name in available_categories:
            if category_name in category_keywords:
                keywords = category_keywords[category_name]
                matches = sum(1 for keyword in keywords if keyword in content_lower)
                if matches > max_matches:
                    max_matches = matches
                    matched_category = category_name
        
        if matched_category and max_matches > 0:
            # 根据匹配的分类生成响应
            confidence = min(0.95, 0.7 + (max_matches * 0.05))
            return json.dumps({
                "category": matched_category,
                "confidence": confidence,
                "reasoning": f"内容符合{matched_category}的分类标准，检测到相关关键词。",
                "should_ignore": False,
                "key_points": [f"{matched_category}相关", "关键词匹配"]
            }, ensure_ascii=False)
        else:
            return json.dumps({
                "category": "未分类",
                "confidence": 0.60,
                "reasoning": "内容不符合预定义的分类标准，归为未分类。",
                "should_ignore": False,
                "key_points": ["一般信息"]
            }, ensure_ascii=False)
    
    def get_available_categories(self) -> List[str]:
        """获取可用的分类列表"""
        return self.category_manager.get_category_list()
    
    def update_classification_config(self, new_config: Dict[str, Any]) -> None:
        """更新分类配置"""
        # 这里可以实现配置更新逻辑
        # 目前通过重新加载配置文件实现
        self.reload_prompt_config()
        self.logger.info("分类配置已更新")
        """
        验证分类响应有效性
        
        Args:
            category: 分类名称
            
        Returns:
            是否有效
        """
        try:
            categories = self.category_manager.load_categories()
            valid_categories = list(categories.keys()) + ["未分类", "忽略"]
            return category in valid_categories
        except Exception:
            return False
    
    def _parse_text_response(self, response: str) -> LLMResponse:
        """
        从文本响应中提取信息（备用解析方法）
        
        Args:
            response: 响应文本
            
        Returns:
            解析后的响应对象
        """
        # 简单的文本解析逻辑
        category = "未分类"
        confidence = 0.5
        reasoning = response[:200] + "..." if len(response) > 200 else response
        should_ignore = "忽略" in response or "ignore" in response.lower()
        key_points = []
        
        # 尝试从文本中提取分类
        categories = self.category_manager.load_categories()
        for cat_name in categories.keys():
            if cat_name in response:
                category = cat_name
                break
        
        return LLMResponse(
            category=category,
            confidence=confidence,
            reasoning=reasoning,
            should_ignore=should_ignore,
            key_points=key_points
        )
    
    def get_available_categories(self) -> List[str]:
        """获取可用的分类列表"""
        return self.category_manager.get_category_list()
    
    def update_classification_config(self, new_config: Dict[str, Any]) -> None:
        """更新分类配置"""
        # 这里可以实现配置更新逻辑
        # 目前通过重新加载配置文件实现
        self.reload_prompt_config()
        self.logger.info("分类配置已更新")
    
    def _validate_category_response(self, category: str) -> bool:
        """
        验证分类响应有效性
        
        Args:
            category: 分类名称
            
        Returns:
            是否有效
        """
        try:
            categories = self.category_manager.load_categories()
            valid_categories = list(categories.keys()) + ["未分类", "忽略"]
            return category in valid_categories
        except Exception:
            return False


class ContentClassifier:
    """内容分类器"""
    
    def __init__(self, llm_analyzer: LLMAnalyzer):
        """
        初始化内容分类器
        
        Args:
            llm_analyzer: LLM分析器实例
        """
        self.llm_analyzer = llm_analyzer
        self.logger = logging.getLogger(__name__)
        self.classified_items: Dict[str, List[ContentItem]] = {}
    
    def classify_item(self, item: ContentItem, analysis: AnalysisResult) -> str:
        """
        分类单个内容项
        
        Args:
            item: 内容项
            analysis: 分析结果
            
        Returns:
            分类名称
        """
        category = analysis.category
        
        # 存储分类结果
        if category not in self.classified_items:
            self.classified_items[category] = []
        
        self.classified_items[category].append(item)
        
        self.logger.debug(f"内容项已分类: {item.title[:50]}... -> {category}")
        return category
    
    def get_category_items(self, category: str) -> List[ContentItem]:
        """
        获取指定分类的内容项
        
        Args:
            category: 分类名称
            
        Returns:
            内容项列表
        """
        return self.classified_items.get(category, [])
    
    def generate_category_summary(self, category: str) -> str:
        """
        生成分类摘要
        
        Args:
            category: 分类名称
            
        Returns:
            分类摘要文本
        """
        items = self.get_category_items(category)
        
        if not items:
            return f"{category}: 暂无相关内容"
        
        summary = f"{category} ({len(items)}条):\n"
        for i, item in enumerate(items[:5], 1):  # 最多显示5条
            summary += f"{i}. {item.title}\n"
        
        if len(items) > 5:
            summary += f"... 还有 {len(items) - 5} 条内容\n"
        
        return summary
    
    def clear_classifications(self) -> None:
        """清空分类结果"""
        self.classified_items.clear()
        self.logger.info("分类结果已清空")
    
    def get_all_categories(self) -> List[str]:
        """获取所有分类名称"""
        return list(self.classified_items.keys())
    
    def get_classification_stats(self) -> Dict[str, int]:
        """获取分类统计信息"""
        return {category: len(items) for category, items in self.classified_items.items()}
    
    def get_available_categories(self) -> List[str]:
        """获取可用的分类列表"""
        return self.llm_analyzer.get_available_categories()
    
    def validate_category(self, category: str) -> bool:
        """验证分类是否有效"""
        return self.llm_analyzer._validate_category_response(category)
    
    def update_category_config(self, new_config: Dict[str, Any]) -> None:
        """更新分类配置"""
        self.llm_analyzer.update_classification_config(new_config)