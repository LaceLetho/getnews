"""
市场快照获取服务

集成Grok等联网AI服务，获取当前市场现状快照。
支持缓存、质量验证和备用快照机制。
"""

import json
import logging
import time
import os
import re
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, asdict
import hashlib

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

from crypto_news_analyzer.utils.conversation_cache import ConversationIdManager


@dataclass
class MarketSnapshot:
    """市场快照数据模型"""
    content: str  # 市场快照内容
    timestamp: datetime  # 获取时间
    source: str  # 来源（grok, fallback, cached）
    quality_score: float  # 质量评分 (0.0-1.0)
    is_valid: bool  # 是否有效
    
    def __post_init__(self):
        """数据验证"""
        if not isinstance(self.timestamp, datetime):
            raise ValueError("时间戳必须是datetime对象")
        if not 0.0 <= self.quality_score <= 1.0:
            raise ValueError("质量评分必须在0.0到1.0之间")
        if not isinstance(self.is_valid, bool):
            raise ValueError("is_valid必须是布尔值")
    
    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MarketSnapshot':
        """从字典反序列化"""
        if isinstance(data['timestamp'], str):
            data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        return cls(**data)
    
    def to_json(self) -> str:
        """序列化为JSON字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'MarketSnapshot':
        """从JSON字符串反序列化"""
        data = json.loads(json_str)
        return cls.from_dict(data)


class MarketSnapshotService:
    """市场快照获取服务"""
    
    def __init__(self, 
                 GROK_API_KEY: Optional[str] = None,
                 summary_model: str = "grok-4-1-fast-reasoning",
                 fallback_providers: Optional[List[str]] = None,
                 cache_ttl_minutes: int = 30,
                 cache_dir: str = "./data/cache",
                 mock_mode: bool = False,
                 conversation_id: Optional[str] = None,
                 temperature: float = 0.5,
                 config: Optional[Dict[str, Any]] = None):
        """
        初始化市场快照服务
        
        Args:
            GROK_API_KEY: Grok API密钥，如果为None则从环境变量读取
            summary_model: 使用的模型名称
            fallback_providers: 备用服务提供商列表
            cache_ttl_minutes: 缓存有效期（分钟）
            cache_dir: 缓存目录
            mock_mode: 是否使用模拟模式（用于测试）
            conversation_id: 会话ID（用于提高缓存命中率，如果为None则自动生成）
            temperature: 温度参数（控制输出随机性）
            config: 配置字典（用于读取enable_debug_logging等设置）
        """
        self.GROK_API_KEY = GROK_API_KEY or os.getenv('GROK_API_KEY', '')
        self.summary_model = summary_model
        self.fallback_providers = fallback_providers or []
        self.cache_ttl_minutes = cache_ttl_minutes
        self.cache_dir = cache_dir
        self.mock_mode = mock_mode
        self.temperature = temperature
        self.config = config or {}
        self.logger = logging.getLogger(__name__)
        
        # 使用会话ID管理器获取或创建持久化的conversation_id
        conversation_id_manager = ConversationIdManager(cache_dir=cache_dir)
        self.conversation_id = conversation_id or conversation_id_manager.get_or_create_conversation_id("market_snapshot")
        
        # API配置 - 使用OpenAI SDK调用xAI API
        self.grok_api_base = "https://api.x.ai/v1"
        self.client = None
        
        if not mock_mode and self.GROK_API_KEY and OpenAI:
            try:
                self.client = OpenAI(
                    api_key=self.GROK_API_KEY,
                    base_url=self.grok_api_base,
                    default_headers={"x-grok-conv-id": self.conversation_id}
                )
                self.logger.info(f"Grok客户端已设置default_headers: x-grok-conv-id={self.conversation_id}")
            except Exception as e:
                self.logger.error(f"初始化OpenAI客户端失败: {e}")
                self.client = None
        
        # 重试配置
        self.max_retries = 3
        self.retry_delay = 2.0
        
        # 质量验证配置
        self.min_content_length = 50
        self.quality_keywords = [
            # 中文关键词
            "市场", "价格", "趋势", "政策", "监管", "利率", "行情", "预期",
            "比特币", "以太坊", "加密货币", "区块链", "DeFi", "NFT", "Layer2",
            "美联储", "通胀", "经济", "投资", "交易", "波动", "上涨", "下跌",
            "牛市", "熊市", "震荡", "突破", "支撑", "阻力", "成交量", "资金",
            "机构", "散户", "FOMO", "恐慌", "贪婪", "情绪", "信心", "风险",
            "合规", "ETF", "期货", "现货", "杠杆", "做多", "做空", "套利",
            # 英文关键词
            "market", "price", "trend", "policy", "regulation", "rate", "trading", "expectation",
            "bitcoin", "btc", "ethereum", "eth", "crypto", "blockchain", "defi", "nft", "layer2",
            "fed", "inflation", "economy", "investment", "trade", "volatility", "rally", "decline",
            "bull", "bear", "consolidation", "breakout", "support", "resistance", "volume", "fund",
            "institutional", "retail", "fomo", "fear", "greed", "sentiment", "confidence", "risk",
            "compliance", "etf", "futures", "spot", "leverage", "long", "short", "arbitrage",
            "inflow", "outflow", "accumulation", "distribution", "liquidity", "treasury", "yield"
        ]
        
        # 创建缓存目录
        os.makedirs(self.cache_dir, exist_ok=True)
        
        if mock_mode:
            self.logger.info("市场快照服务运行在模拟模式")
        elif not self.GROK_API_KEY:
            self.logger.warning("未提供Grok API密钥，将使用备用快照")
        else:
            self.logger.info(f"使用会话ID提高缓存命中率: {self.conversation_id}")
    
    def get_market_snapshot(self, prompt_template: str) -> MarketSnapshot:
        """
        获取市场快照
        
        Args:
            prompt_template: 提示词模板
            
        Returns:
            市场快照对象
        """
        try:
            # 模拟模式直接返回模拟数据，不使用缓存
            if self.mock_mode:
                self.logger.info("模拟模式：直接生成模拟快照")
                return self._generate_mock_snapshot()
            
            # 首先尝试从缓存获取
            cached_snapshot = self.get_cached_snapshot()
            if cached_snapshot:
                self.logger.info("使用缓存的市场快照")
                return cached_snapshot
            
            # 尝试从Grok API获取
            if self.GROK_API_KEY and not self.mock_mode:
                try:
                    snapshot = self._get_snapshot_from_grok(prompt_template)
                    if snapshot and self.validate_snapshot_quality(snapshot.content):
                        self.cache_snapshot(snapshot)
                        self.logger.info(f"成功从Grok获取市场快照，质量评分: {snapshot.quality_score}")
                        return snapshot
                except Exception as e:
                    self.logger.error(f"从Grok获取市场快照失败: {e}")
            
            # 尝试备用服务提供商
            for provider in self.fallback_providers:
                try:
                    snapshot = self._get_snapshot_from_provider(provider, prompt_template)
                    if snapshot and self.validate_snapshot_quality(snapshot.content):
                        self.cache_snapshot(snapshot)
                        self.logger.info(f"成功从{provider}获取市场快照")
                        return snapshot
                except Exception as e:
                    self.logger.error(f"从{provider}获取市场快照失败: {e}")
            
            # 使用备用快照
            fallback_snapshot = self.get_fallback_snapshot()
            self.logger.warning("使用备用市场快照")
            return fallback_snapshot
            
        except Exception as e:
            self.logger.error(f"获取市场快照失败: {e}")
            return self.get_fallback_snapshot()
    
    def _get_snapshot_from_grok(self, prompt_template: str) -> Optional[MarketSnapshot]:
        """
        从Grok API获取市场快照
        注意AI在编写本代码时因为不知道grok API会乱写，所以这段必须参考其API文档编写
        https://docs.x.ai/developers/api-reference#create-new-response
        
        Args:
            prompt_template: 提示词模板
            
        Returns:
            市场快照对象或None
        """
        if self.mock_mode:
            return self._generate_mock_snapshot()
        
        if not self.client:
            self.logger.error("OpenAI客户端未初始化")
            return None
        
        # 使用OpenAI SDK调用xAI API，启用web_search工具
        try:      
            messages = [
                {
                    "role": "system",
                    "content": prompt_template  # 使用完整的market_summary_prompt.md作为系统提示词
                },
                {
                    "role": "user", 
                    "content": "Generate a 24-Hour Crypto Market Snapshot"
                }
            ]
            
            # 根据配置决定是否启用DEBUG日志
            enable_debug = self.config.get("llm_config", {}).get("enable_debug_logging", False)
            
            if enable_debug:
                import logging as stdlib_logging
                openai_logger = stdlib_logging.getLogger("openai")
                httpx_logger = stdlib_logging.getLogger("httpx")
                original_openai_level = openai_logger.level
                original_httpx_level = httpx_logger.level
                openai_logger.setLevel(stdlib_logging.DEBUG)
                httpx_logger.setLevel(stdlib_logging.DEBUG)
            
            # 打印发送给LLM的完整内容到日志
            self.logger.info("=" * 80)
            self.logger.info("发送给Grok的市场快照请求:")
            self.logger.info(f"模型: {self.summary_model}")
            self.logger.info(f"温度: {self.temperature}")
            self.logger.info("-" * 80)
            self.logger.info("系统提示词:")
            self.logger.info(messages[0]["content"])
            self.logger.info("-" * 80)
            self.logger.info("用户消息:")
            self.logger.info(messages[1]["content"])
            self.logger.info("=" * 80)
            
            # 获取24小时之前的时间
            twenty_four_hours_ago = (datetime.now() - timedelta(hours=24)).isoformat()

            # 定义工具
            tools = [
                 {
                    "type": "web_search",
                    "from_date": twenty_four_hours_ago, 
                },
                {
                    "type": "x_search",
                    "from_date": twenty_four_hours_ago, 
                },
            ]
            
            self.logger.info(f"启用工具: web_search, x_search (from_date: {twenty_four_hours_ago})")
            
            # 调用 responses API，添加 x-grok-conv-id 头以提高缓存命中率
            response = self.client.responses.create(
                model=self.summary_model,
                input=messages,
                temperature=self.temperature,
                tools=tools,
                tool_choice="required"
            )
            
            # 恢复日志级别
            if enable_debug:
                openai_logger.setLevel(original_openai_level)
                httpx_logger.setLevel(original_httpx_level)
            
            if not response or not hasattr(response, 'output'):
                self.logger.error("Grok API返回空响应或格式错误")
                return None
            
            # 从response.output中提取最终的文本内容
            content = ""
            if response.output:
                for output_item in response.output:
                    if hasattr(output_item, 'type') and output_item.type == 'message':
                        if hasattr(output_item, 'content') and output_item.content:
                            for content_item in output_item.content:
                                if hasattr(content_item, 'type') and content_item.type == 'output_text':
                                    # 获取文本并清理超链接
                                    raw_content = content_item.text
                                    content = self._remove_hyperlinks(raw_content)
                                    break
                        break
            
            if content:
                self.logger.info(f"Grok API返回内容长度: {len(content)} 字符")
                self.logger.info(f"Grok API返回内容: {content}")
                
                # 计算质量评分
                quality_score = self._calculate_quality_score(content)
                self.logger.info(f"内容质量评分: {quality_score}")
                
                # 验证质量
                is_valid = self.validate_snapshot_quality(content)
                self.logger.info(f"质量验证结果: {is_valid}")
                
                if is_valid:
                    return MarketSnapshot(
                        content=content,
                        timestamp=datetime.now(),
                        source="grok",
                        quality_score=quality_score,
                        is_valid=True
                    )
                else:
                    self.logger.warning(f"Grok返回内容质量不符合要求，内容: {content}")
            else:
                self.logger.warning("Grok API返回空内容")
                self.logger.debug(f"完整响应: {response}")
                    
        except Exception as e:
            self.logger.error(f"调用Grok API失败: {e}")
            
        return None
    
    def _get_snapshot_from_provider(self, provider: str, prompt_template: str) -> Optional[MarketSnapshot]:
        """
        从备用服务提供商获取市场快照
        
        Args:
            provider: 服务提供商名称
            prompt_template: 提示词模板
            
        Returns:
            市场快照对象或None
        """
        # 这里可以实现其他服务提供商的集成
        # 目前返回None，表示暂不支持
        self.logger.info(f"备用服务提供商 {provider} 暂未实现")
        return None
    
    def validate_snapshot_quality(self, content: str) -> bool:
        """
        验证市场快照质量
        
        Args:
            content: 快照内容
            
        Returns:
            是否通过质量验证
        """
        if not content or len(content.strip()) < self.min_content_length:
            self.logger.debug(f"内容长度不足: {len(content.strip())} < {self.min_content_length}")
            return False
        
        # 检查是否包含关键词
        content_lower = content.lower()
        found_keywords = [kw for kw in self.quality_keywords if kw in content_lower]
        keyword_count = len(found_keywords)
        
        self.logger.debug(f"找到关键词数量: {keyword_count}, 关键词: {found_keywords}")
        
        # 至少包含1个关键词（降低要求）
        return keyword_count >= 1
    
    def _calculate_quality_score(self, content: str) -> float:
        """
        计算内容质量评分
        
        Args:
            content: 内容文本
            
        Returns:
            质量评分 (0.0-1.0)
        """
        if not content:
            return 0.0
        
        score = 0.0
        
        # 长度评分 (最多0.3分)
        length_score = min(0.3, len(content) / 500)
        score += length_score
        
        # 关键词评分 (最多0.4分)
        content_lower = content.lower()
        keyword_count = sum(1 for keyword in self.quality_keywords if keyword in content_lower)
        keyword_score = min(0.4, keyword_count * 0.1)
        score += keyword_score
        
        # 结构评分 (最多0.3分)
        # 检查是否有数字、标点符号等
        has_numbers = any(char.isdigit() for char in content)
        has_punctuation = any(char in '，。！？；：' for char in content)
        structure_score = 0.1 * (has_numbers + has_punctuation) + 0.1
        score += structure_score
        
        return min(1.0, score)
    
    def get_cached_snapshot(self) -> Optional[MarketSnapshot]:
        """
        获取缓存的市场快照
        
        Returns:
            缓存的市场快照或None
        """
        cache_file = os.path.join(self.cache_dir, "market_snapshot.json")
        
        try:
            if os.path.exists(cache_file):
                with open(cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                snapshot = MarketSnapshot.from_dict(data)
                
                # 检查缓存是否过期
                if self._is_cache_valid(snapshot.timestamp):
                    snapshot.source = "cached"
                    return snapshot
                else:
                    # 删除过期缓存
                    os.remove(cache_file)
                    self.logger.info("删除过期的市场快照缓存")
                    
        except Exception as e:
            self.logger.error(f"读取缓存失败: {e}")
            # 删除损坏的缓存文件
            try:
                if os.path.exists(cache_file):
                    os.remove(cache_file)
            except:
                pass
        
        return None
    
    def cache_snapshot(self, snapshot: MarketSnapshot, ttl_minutes: Optional[int] = None) -> None:
        """
        缓存市场快照
        
        Args:
            snapshot: 市场快照对象
            ttl_minutes: 缓存有效期（分钟），如果为None则使用默认值
        """
        if ttl_minutes is None:
            ttl_minutes = self.cache_ttl_minutes
        
        cache_file = os.path.join(self.cache_dir, "market_snapshot.json")
        
        try:
            # 更新时间戳为当前时间
            snapshot.timestamp = datetime.now()
            
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(snapshot.to_dict(), f, ensure_ascii=False, indent=2)
            
            self.logger.info(f"市场快照已缓存，有效期: {ttl_minutes} 分钟")
            
        except Exception as e:
            self.logger.error(f"缓存市场快照失败: {e}")
    
    def _remove_hyperlinks(self, text: str) -> str:
        """
        移除文本中的超链接格式
        
        移除以下格式：
        - Markdown链接: [text](url)
        - 引用标记: [[1]](url), [[2]]() 等
        - Grok引用标签: <grok:render>...</grok:render>
        - 纯URL: http://... 或 https://...
        
        Args:
            text: 原始文本
            
        Returns:
            清理后的文本
        """
        if not text:
            return text
        
        # 移除Grok引用标签 <grok:render>...</grok:render>
        text = re.sub(r'<grok:render[^>]*>.*?</grok:render>', '', text, flags=re.DOTALL)
        
        # 移除引用标记 [[1]](url), [[2]]() 等（包括有URL和空括号的情况）
        text = re.sub(r'\[\[\d+\]\]\([^\)]*\)', '', text)
        
        # 移除Markdown格式的链接 [text](url)，保留text部分
        text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
        
        # 移除纯URL链接（匹配到空格、标点或字符串结尾）
        text = re.sub(r'https?://[^\s\u4e00-\u9fff\)\]]+', '', text)
        
        # 清理多余的空格
        text = re.sub(r'\s+', ' ', text)
        
        # 在数字列表项之间添加双换行（处理 "1. xxx 2. xxx" 格式）
        # 在每个 "数字. " 前添加换行（除了第一个）
        text = re.sub(r'\s+(\d+\.\s+)', r'\n\n\1', text)
        
        # 清理开头的换行
        text = text.lstrip('\n')
        
        # 清理结尾的空白
        text = text.rstrip()
        
        return text
    
    def _is_cache_valid(self, cache_timestamp: datetime) -> bool:
        """
        检查缓存是否有效
        
        Args:
            cache_timestamp: 缓存时间戳
            
        Returns:
            是否有效
        """
        now = datetime.now()
        cache_age = now - cache_timestamp
        return cache_age.total_seconds() < (self.cache_ttl_minutes * 60)
    
    def get_fallback_snapshot(self) -> MarketSnapshot:
        """
        获取备用市场快照
        
        Returns:
            备用市场快照
        """
        fallback_content = """
当前加密货币市场现状（备用快照）：

1. 当前行情与普遍预期：市场处于震荡调整阶段，投资者情绪谨慎，等待更多政策和经济数据指引。

2. 主流赛道与热门新赛道：比特币和以太坊仍是主流关注焦点，DeFi、NFT、Layer2等赛道持续发展，AI相关代币受到关注。

3. 利率环境与主流预期：美联储政策仍是关键影响因素，市场密切关注通胀数据和利率决议。

4. 政策环境与核心政策焦点：各国监管政策逐步明确，合规化趋势明显，机构采用加速。

5. 舆论焦点：市场关注宏观经济环境、监管动态、技术创新和机构动向。

注意：这是备用快照，可能不反映最新市场状况。
        """.strip()
        
        return MarketSnapshot(
            content=fallback_content,
            timestamp=datetime.now(),
            source="fallback",
            quality_score=0.7,
            is_valid=True
        )
    
    def _generate_mock_snapshot(self) -> MarketSnapshot:
        """
        生成模拟市场快照（用于测试）
        
        Returns:
            模拟的市场快照
        """
        mock_content = f"""
当前加密货币市场现状（模拟数据 - {datetime.now().strftime('%Y-%m-%d %H:%M')}）：

1. 当前行情与普遍预期：比特币价格在45,000-50,000美元区间震荡，市场情绪偏向谨慎乐观，等待更多利好消息。

2. 主流赛道与热门新赛道：DeFi总锁仓量保持稳定，Layer2解决方案获得更多采用，AI+区块链概念受到关注。

3. 利率环境与主流预期：美联储暂停加息，市场预期未来可能降息，有利于风险资产表现。

4. 政策环境与核心政策焦点：美国SEC对加密货币ETF态度积极，欧盟MiCA法规即将实施，监管环境逐步明确。

5. 舆论焦点：机构投资者持续入场，传统金融与加密货币融合加速，技术创新推动行业发展。
        """.strip()
        
        return MarketSnapshot(
            content=mock_content,
            timestamp=datetime.now(),
            source="mock",
            quality_score=0.85,
            is_valid=True
        )
    
    def clear_cache(self) -> bool:
        """
        清除缓存
        
        Returns:
            是否成功清除
        """
        cache_file = os.path.join(self.cache_dir, "market_snapshot.json")
        
        try:
            if os.path.exists(cache_file):
                os.remove(cache_file)
                self.logger.info("市场快照缓存已清除")
                return True
            return True
        except Exception as e:
            self.logger.error(f"清除缓存失败: {e}")
            return False
    
    def get_cache_info(self) -> Dict[str, Any]:
        """
        获取缓存信息
        
        Returns:
            缓存信息字典
        """
        cache_file = os.path.join(self.cache_dir, "market_snapshot.json")
        
        info = {
            "cache_exists": os.path.exists(cache_file),
            "cache_file": cache_file,
            "cache_ttl_minutes": self.cache_ttl_minutes
        }
        
        if info["cache_exists"]:
            try:
                stat = os.stat(cache_file)
                cache_time = datetime.fromtimestamp(stat.st_mtime)
                info.update({
                    "cache_time": cache_time.isoformat(),
                    "cache_age_minutes": (datetime.now() - cache_time).total_seconds() / 60,
                    "is_valid": self._is_cache_valid(cache_time),
                    "file_size": stat.st_size
                })
            except Exception as e:
                info["error"] = str(e)
        
        return info
    
    def test_connection(self) -> Dict[str, Any]:
        """
        测试API连接
        
        Returns:
            连接测试结果
        """
        result = {
            "grok_available": False,
            "grok_error": None,
            "fallback_providers": [],
            "mock_mode": self.mock_mode
        }
        
        if self.mock_mode:
            result["grok_available"] = True
            result["message"] = "运行在模拟模式"
            return result
        
        if not self.GROK_API_KEY:
            result["grok_error"] = "未提供Grok API密钥"
            return result
        
        if not self.client:
            result["grok_error"] = "OpenAI客户端未初始化"
            return result
        
        # 测试Grok API连接
        try:
            response = self.client.chat.completions.create(
                model=self.summary_model,
                messages=[
                    {
                        "role": "user", 
                        "content": "请简单介绍一下当前的加密货币市场状况"
                    }
                ],
                max_tokens=50,
                tools=[
                    {
                        "type": "function",
                        "function": {
                            "name": "web_search",
                            "description": "Search for current cryptocurrency market information",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "query": {
                                        "type": "string",
                                        "description": "Search query"
                                    }
                                },
                                "required": ["query"]
                            }
                        }
                    }
                ],
                tool_choice="auto"
            )
            
            if response.choices and len(response.choices) > 0:
                result["grok_available"] = True
            else:
                result["grok_error"] = "API返回空响应"
                
        except Exception as e:
            result["grok_error"] = str(e)
        
        return result
    
    def update_config(self, **kwargs) -> None:
        """
        更新配置
        
        Args:
            **kwargs: 配置参数
        """
        if "GROK_API_KEY" in kwargs:
            self.GROK_API_KEY = kwargs["GROK_API_KEY"]
            self.headers["Authorization"] = f"Bearer {self.GROK_API_KEY}"
        
        if "cache_ttl_minutes" in kwargs:
            self.cache_ttl_minutes = kwargs["cache_ttl_minutes"]
        
        if "summary_model" in kwargs:
            self.summary_model = kwargs["summary_model"]
        
        if "fallback_providers" in kwargs:
            self.fallback_providers = kwargs["fallback_providers"]
        
        self.logger.info("市场快照服务配置已更新")