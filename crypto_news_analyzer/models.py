"""
数据模型定义

定义系统中使用的所有数据结构和类型。
"""

from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, List, Optional, Any, Union
from enum import Enum
import json
import hashlib
import uuid
from urllib.parse import urlparse


@dataclass
class ContentItem:
    """内容项数据模型"""
    id: str
    title: str
    content: str
    url: str
    publish_time: datetime
    source_name: str
    source_type: str  # "rss" or "x"
    
    def __post_init__(self):
        """数据验证"""
        self.validate()
    
    def validate(self) -> None:
        """验证数据完整性"""
        if not self.title or not self.title.strip():
            raise ValueError("标题不能为空")
        
        if not self.content or not self.content.strip():
            raise ValueError("内容不能为空")
        
        if not self.url or not self._is_valid_url(self.url):
            raise ValueError(f"无效的URL: {self.url}")
        
        if not self.source_name or not self.source_name.strip():
            raise ValueError("数据源名称不能为空")
        
        # 允许任何非空的数据源类型，不限制为固定列表
        if not self.source_type or not self.source_type.strip():
            raise ValueError("数据源类型不能为空")
        
        if not isinstance(self.publish_time, datetime):
            raise ValueError("发布时间必须是datetime对象")
    
    def _is_valid_url(self, url: str) -> bool:
        """验证URL格式"""
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except Exception:
            return False
    
    def generate_content_hash(self) -> str:
        """生成内容哈希用于去重"""
        content_str = f"{self.title}{self.content}{self.url}"
        return hashlib.md5(content_str.encode('utf-8')).hexdigest()
    
    @classmethod
    def generate_id(cls, title: str, url: str, publish_time: datetime) -> str:
        """生成唯一ID"""
        id_str = f"{title}{url}{publish_time.isoformat()}"
        return hashlib.sha256(id_str.encode('utf-8')).hexdigest()[:16]
    
    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        data = asdict(self)
        data['publish_time'] = self.publish_time.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ContentItem':
        """从字典反序列化"""
        if isinstance(data['publish_time'], str):
            data['publish_time'] = datetime.fromisoformat(data['publish_time'])
        return cls(**data)
    
    def to_json(self) -> str:
        """序列化为JSON字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'ContentItem':
        """从JSON字符串反序列化"""
        data = json.loads(json_str)
        return cls.from_dict(data)


@dataclass
class RSSSource:
    """RSS订阅源配置"""
    name: str
    url: str
    description: str
    
    def __post_init__(self):
        """数据验证"""
        self.validate()
    
    def validate(self) -> None:
        """验证配置有效性"""
        if not self.name or not self.name.strip():
            raise ValueError("RSS源名称不能为空")
        
        if not self.url or not self._is_valid_url(self.url):
            raise ValueError(f"无效的RSS URL: {self.url}")
        
        if not self.description:
            self.description = ""  # 允许空描述
    
    def _is_valid_url(self, url: str) -> bool:
        """验证URL格式"""
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except Exception:
            return False
    
    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RSSSource':
        """从字典反序列化"""
        return cls(**data)


@dataclass
class XSource:
    """X/Twitter信息源配置"""
    name: str
    url: str
    type: str  # "list" or "timeline"
    
    def __post_init__(self):
        """数据验证"""
        self.validate()
    
    def validate(self) -> None:
        """验证配置有效性"""
        if not self.name or not self.name.strip():
            raise ValueError("X源名称不能为空")
        
        if not self.url or not self._is_valid_url(self.url):
            raise ValueError(f"无效的X URL: {self.url}")
        
        if self.type not in ["list", "timeline"]:
            raise ValueError(f"无效的X源类型: {self.type}")
    
    def _is_valid_url(self, url: str) -> bool:
        """验证URL格式"""
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except Exception:
            return False
    
    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'XSource':
        """从字典反序列化"""
        return cls(**data)


@dataclass
class RESTAPISource:
    """REST API数据源配置"""
    name: str
    endpoint: str
    method: str
    headers: Dict[str, str]
    params: Dict[str, Any]
    response_mapping: Dict[str, str]  # 字段映射配置
    
    def __post_init__(self):
        """数据验证"""
        self.validate()
    
    def validate(self) -> None:
        """验证配置有效性"""
        if not self.name or not self.name.strip():
            raise ValueError("REST API源名称不能为空")
        
        if not self.endpoint or not self._is_valid_url(self.endpoint):
            raise ValueError(f"无效的API端点: {self.endpoint}")
        
        if self.method.upper() not in ["GET", "POST", "PUT", "DELETE"]:
            raise ValueError(f"无效的HTTP方法: {self.method}")
        
        required_mappings = ["title_field", "content_field", "url_field", "time_field"]
        for field in required_mappings:
            if field not in self.response_mapping:
                raise ValueError(f"缺少必需的响应映射字段: {field}")
    
    def _is_valid_url(self, url: str) -> bool:
        """验证URL格式"""
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except Exception:
            return False
    
    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RESTAPISource':
        """从字典反序列化"""
        return cls(**data)


@dataclass
class AuthConfig:
    """认证配置"""
    x_ct0: str
    x_auth_token: str
    llm_api_key: str
    telegram_bot_token: str
    telegram_channel_id: str
    
    def __post_init__(self):
        """数据验证"""
        self.validate()
    
    def validate(self) -> None:
        """验证认证配置"""
        if not self.llm_api_key or not self.llm_api_key.strip():
            raise ValueError("LLM API密钥不能为空")
        
        if not self.telegram_bot_token or not self.telegram_bot_token.strip():
            raise ValueError("Telegram Bot Token不能为空")
        
        if not self.telegram_channel_id or not self.telegram_channel_id.strip():
            raise ValueError("Telegram Channel ID不能为空")
        
        # X认证参数可以为空（如果不使用X源）
        if self.x_ct0 and not self.x_ct0.strip():
            self.x_ct0 = ""
        if self.x_auth_token and not self.x_auth_token.strip():
            self.x_auth_token = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AuthConfig':
        """从字典反序列化"""
        return cls(**data)


@dataclass
class StorageConfig:
    """存储配置"""
    retention_days: int = 30
    max_storage_mb: int = 1000
    cleanup_frequency: str = "daily"
    database_path: str = "./data/crypto_news.db"
    
    def __post_init__(self):
        """数据验证"""
        self.validate()
    
    def validate(self) -> None:
        """验证存储配置"""
        if self.retention_days <= 0:
            raise ValueError("数据保留天数必须大于0")
        
        if self.max_storage_mb <= 0:
            raise ValueError("最大存储空间必须大于0MB")
        
        if self.cleanup_frequency not in ["daily", "weekly", "monthly"]:
            raise ValueError(f"无效的清理频率: {self.cleanup_frequency}")
        
        if not self.database_path or not self.database_path.strip():
            raise ValueError("数据库路径不能为空")
    
    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'StorageConfig':
        """从字典反序列化"""
        return cls(**data)


@dataclass
class AnalysisResult:
    """分析结果"""
    content_id: str
    category: str
    confidence: float
    reasoning: str
    should_ignore: bool
    key_points: List[str]
    
    def __post_init__(self):
        """数据验证"""
        self.validate()
    
    def validate(self) -> None:
        """验证分析结果"""
        if not self.content_id or not self.content_id.strip():
            raise ValueError("内容ID不能为空")
        
        if not self.category or not self.category.strip():
            raise ValueError("分类不能为空")
        
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("置信度必须在0.0到1.0之间")
        
        if not isinstance(self.should_ignore, bool):
            raise ValueError("should_ignore必须是布尔值")
        
        if not isinstance(self.key_points, list):
            raise ValueError("key_points必须是列表")
    
    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AnalysisResult':
        """从字典反序列化"""
        return cls(**data)
    
    def to_json(self) -> str:
        """序列化为JSON字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'AnalysisResult':
        """从JSON字符串反序列化"""
        data = json.loads(json_str)
        return cls.from_dict(data)


@dataclass
class CrawlResult:
    """爬取结果"""
    source_name: str
    status: str  # "success" or "error"
    item_count: int
    error_message: Optional[str]
    
    def __post_init__(self):
        """数据验证"""
        self.validate()
    
    def validate(self) -> None:
        """验证爬取结果"""
        if not self.source_name or not self.source_name.strip():
            raise ValueError("数据源名称不能为空")
        
        if self.status not in ["success", "error"]:
            raise ValueError(f"无效的状态: {self.status}")
        
        if self.item_count < 0:
            raise ValueError("项目数量不能为负数")
        
        if self.status == "error" and not self.error_message:
            raise ValueError("错误状态必须包含错误信息")
    
    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CrawlResult':
        """从字典反序列化"""
        return cls(**data)


@dataclass
class CrawlStatus:
    """爬取状态"""
    rss_results: List[CrawlResult]
    x_results: List[CrawlResult]
    total_items: int
    execution_time: datetime
    
    def __post_init__(self):
        """数据验证"""
        self.validate()
    
    def validate(self) -> None:
        """验证爬取状态"""
        if not isinstance(self.rss_results, list):
            raise ValueError("RSS结果必须是列表")
        
        if not isinstance(self.x_results, list):
            raise ValueError("X结果必须是列表")
        
        if self.total_items < 0:
            raise ValueError("总项目数不能为负数")
        
        if not isinstance(self.execution_time, datetime):
            raise ValueError("执行时间必须是datetime对象")
    
    def get_success_count(self) -> int:
        """获取成功的数据源数量"""
        success_count = 0
        for result in self.rss_results + self.x_results:
            if result.status == "success":
                success_count += 1
        return success_count
    
    def get_error_count(self) -> int:
        """获取失败的数据源数量"""
        error_count = 0
        for result in self.rss_results + self.x_results:
            if result.status == "error":
                error_count += 1
        return error_count
    
    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        data = asdict(self)
        data['execution_time'] = self.execution_time.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CrawlStatus':
        """从字典反序列化"""
        if isinstance(data['execution_time'], str):
            data['execution_time'] = datetime.fromisoformat(data['execution_time'])
        
        # 转换嵌套的CrawlResult对象
        data['rss_results'] = [CrawlResult.from_dict(r) for r in data['rss_results']]
        data['x_results'] = [CrawlResult.from_dict(r) for r in data['x_results']]
        
        return cls(**data)


# 基础内容分类枚举（可通过配置文件动态扩展）
class ContentCategory(Enum):
    """内容分类类别"""
    WHALE_MOVEMENTS = "大户动向"
    INTEREST_RATE_EVENTS = "利率事件"
    US_REGULATORY_POLICY = "美国政府监管政策"
    SECURITY_EVENTS = "安全事件"
    NEW_PRODUCTS = "新产品"
    MARKET_PHENOMENA = "市场新现象"
    UNCATEGORIZED = "未分类"
    IGNORED = "忽略"


@dataclass
class TelegramCommandConfig:
    """Telegram命令配置"""
    enabled: bool = True
    authorized_users: List[Dict[str, Any]] = None
    execution_timeout_minutes: int = 30
    max_concurrent_executions: int = 1
    command_rate_limit: Dict[str, int] = None

    def __post_init__(self):
        if self.authorized_users is None:
            self.authorized_users = []
        if self.command_rate_limit is None:
            self.command_rate_limit = {
                "max_commands_per_hour": 10,
                "cooldown_minutes": 5
            }


@dataclass
class ExecutionInfo:
    """执行信息"""
    execution_id: str
    trigger_type: str  # "scheduled", "manual", "startup"
    trigger_user: Optional[str]
    start_time: datetime
    end_time: Optional[datetime]
    status: str  # "running", "completed", "failed", "timeout"
    progress: float  # 0.0 to 1.0
    current_stage: str  # "crawling", "analyzing", "reporting", "sending"
    error_message: Optional[str]
    items_processed: int = 0
    categories_found: Dict[str, int] = None

    def __post_init__(self):
        if self.categories_found is None:
            self.categories_found = {}

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        data = asdict(self)
        data['start_time'] = self.start_time.isoformat()
        if self.end_time:
            data['end_time'] = self.end_time.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ExecutionInfo':
        """从字典反序列化"""
        if isinstance(data['start_time'], str):
            data['start_time'] = datetime.fromisoformat(data['start_time'])
        if data.get('end_time') and isinstance(data['end_time'], str):
            data['end_time'] = datetime.fromisoformat(data['end_time'])
        return cls(**data)


@dataclass
class ExecutionResult:
    """执行结果"""
    execution_id: str
    success: bool
    start_time: datetime
    end_time: datetime
    duration_seconds: float
    items_processed: int
    categories_found: Dict[str, int]
    errors: List[str]
    trigger_user: Optional[str]
    report_sent: bool
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        data = asdict(self)
        data['start_time'] = self.start_time.isoformat()
        data['end_time'] = self.end_time.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ExecutionResult':
        """从字典反序列化"""
        if isinstance(data['start_time'], str):
            data['start_time'] = datetime.fromisoformat(data['start_time'])
        if isinstance(data['end_time'], str):
            data['end_time'] = datetime.fromisoformat(data['end_time'])
        return cls(**data)


@dataclass
class CommandExecutionHistory:
    """命令执行历史"""
    command: str
    user_id: str
    username: str
    timestamp: datetime
    execution_id: Optional[str]
    success: bool
    response_message: str

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CommandExecutionHistory':
        """从字典反序列化"""
        if isinstance(data['timestamp'], str):
            data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        return cls(**data)


# 数据验证工具函数
def validate_time_window(hours: int) -> None:
    """验证时间窗口参数"""
    if not isinstance(hours, int) or hours <= 0:
        raise ValueError("时间窗口必须是正整数")


def validate_config_dict(config: Dict[str, Any], required_keys: List[str]) -> None:
    """验证配置字典包含必需的键"""
    missing_keys = [key for key in required_keys if key not in config]
    if missing_keys:
        raise ValueError(f"配置缺少必需的键: {missing_keys}")


def create_content_item_from_raw(
    title: str,
    content: str,
    url: str,
    publish_time: Union[datetime, str],
    source_name: str,
    source_type: str
) -> ContentItem:
    """从原始数据创建ContentItem对象"""
    # 处理时间格式
    if isinstance(publish_time, str):
        try:
            publish_time = datetime.fromisoformat(publish_time)
        except ValueError:
            # 尝试其他常见格式
            from dateutil import parser
            publish_time = parser.parse(publish_time)
    
    # 生成ID
    item_id = ContentItem.generate_id(title, url, publish_time)
    
    return ContentItem(
        id=item_id,
        title=title.strip(),
        content=content.strip(),
        url=url.strip(),
        publish_time=publish_time,
        source_name=source_name.strip(),
        source_type=source_type.strip()
    )


# 批量操作工具类
class DataModelUtils:
    """数据模型工具类"""
    
    @staticmethod
    def serialize_content_items(items: List[ContentItem]) -> str:
        """批量序列化ContentItem列表为JSON"""
        data = [item.to_dict() for item in items]
        return json.dumps(data, ensure_ascii=False, indent=2)
    
    @staticmethod
    def deserialize_content_items(json_str: str) -> List[ContentItem]:
        """从JSON批量反序列化ContentItem列表"""
        data = json.loads(json_str)
        return [ContentItem.from_dict(item_data) for item_data in data]
    
    @staticmethod
    def validate_content_items(items: List[ContentItem]) -> List[str]:
        """批量验证ContentItem列表，返回错误信息列表"""
        errors = []
        for i, item in enumerate(items):
            try:
                item.validate()
            except ValueError as e:
                errors.append(f"项目 {i}: {str(e)}")
        return errors
    
    @staticmethod
    def deduplicate_content_items(items: List[ContentItem]) -> List[ContentItem]:
        """基于内容哈希去重ContentItem列表"""
        seen_hashes = set()
        unique_items = []
        
        for item in items:
            content_hash = item.generate_content_hash()
            if content_hash not in seen_hashes:
                seen_hashes.add(content_hash)
                unique_items.append(item)
        
        return unique_items
    
    @staticmethod
    def filter_by_time_window(
        items: List[ContentItem], 
        time_window_hours: int,
        reference_time: Optional[datetime] = None
    ) -> List[ContentItem]:
        """根据时间窗口过滤ContentItem列表"""
        if reference_time is None:
            reference_time = datetime.now()
        
        from datetime import timedelta
        cutoff_time = reference_time - timedelta(hours=time_window_hours)
        
        return [item for item in items if item.publish_time >= cutoff_time]