"""
市场数据模块 - 数据模型

定义市场数据相关的数据模型，包括K线数据、波动事件、资金费率等。
"""

from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum
import hashlib
import json


class VolatilityType(str, Enum):
    """波动类型"""
    SURGE = "surge"      # 暴涨
    PLUNGE = "plunge"    # 暴跌


class VolatilitySeverity(str, Enum):
    """波动严重程度"""
    LOW = "low"          # 轻度 (2-5%)
    MEDIUM = "medium"    # 中度 (5-10%)
    HIGH = "high"        # 重度 (10-20%)
    EXTREME = "extreme"  # 极端 (>20%)


@dataclass
class KlineData:
    """K线数据模型"""
    symbol: str                  # 交易对，如 BTCUSDT
    timestamp: datetime          # K线开始时间
    open_price: float
    high_price: float
    low_price: float
    close_price: float
    volume: float                # 成交量
    close_time: datetime         # K线结束时间
    quote_volume: float          # 成交额
    trades_count: int            # 成交笔数
    
    def __post_init__(self):
        """数据验证"""
        self.validate()
    
    def validate(self) -> None:
        """验证数据完整性"""
        if not self.symbol or not self.symbol.strip():
            raise ValueError("交易对不能为空")
        
        if not isinstance(self.timestamp, datetime):
            raise ValueError("时间戳必须是datetime对象")
        
        if self.open_price < 0 or self.high_price < 0 or self.low_price < 0 or self.close_price < 0:
            raise ValueError("价格不能为负数")
        
        if self.low_price > self.high_price:
            raise ValueError("最低价不能高于最高价")
        
        if self.volume < 0 or self.quote_volume < 0:
            raise ValueError("成交量不能为负数")
        
        if self.trades_count < 0:
            raise ValueError("成交笔数不能为负数")
    
    def price_change(self) -> float:
        """计算价格变化"""
        return self.close_price - self.open_price
    
    def price_change_percent(self) -> float:
        """计算价格变化百分比"""
        if self.open_price == 0:
            return 0.0
        return (self.close_price - self.open_price) / self.open_price * 100
    
    def is_bullish(self) -> bool:
        """是否为上涨K线"""
        return self.close_price > self.open_price
    
    def is_bearish(self) -> bool:
        """是否为下跌K线"""
        return self.close_price < self.open_price
    
    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        data['close_time'] = self.close_time.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'KlineData':
        """从字典反序列化"""
        if isinstance(data['timestamp'], str):
            data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        if isinstance(data['close_time'], str):
            data['close_time'] = datetime.fromisoformat(data['close_time'])
        return cls(**data)


@dataclass
class FundingRate:
    """资金费率数据模型"""
    symbol: str                  # 交易对，如 BTCUSDT
    funding_time: datetime       # 资金费率结算时间
    funding_rate: float          # 资金费率
    mark_price: float            # 标记价格
    
    def __post_init__(self):
        """数据验证"""
        self.validate()
    
    def validate(self) -> None:
        """验证数据完整性"""
        if not self.symbol or not self.symbol.strip():
            raise ValueError("交易对不能为空")
        
        if not isinstance(self.funding_time, datetime):
            raise ValueError("资金费率时间必须是datetime对象")
        
        if abs(self.funding_rate) > 0.1:  # 资金费率通常不会超过10%
            raise ValueError(f"资金费率异常: {self.funding_rate}")
    
    def is_positive(self) -> bool:
        """是否为正资金费率（多头支付空头）"""
        return self.funding_rate > 0
    
    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        data = asdict(self)
        data['funding_time'] = self.funding_time.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FundingRate':
        """从字典反序列化"""
        if isinstance(data['funding_time'], str):
            data['funding_time'] = datetime.fromisoformat(data['funding_time'])
        return cls(**data)


@dataclass
class OrderBookSnapshot:
    """订单簿快照数据模型"""
    symbol: str                  # 交易对
    timestamp: datetime          # 快照时间
    bids: List[tuple]            # 买单列表 [(price, quantity), ...]
    asks: List[tuple]            # 卖单列表 [(price, quantity), ...]
    
    def __post_init__(self):
        """数据验证"""
        self.validate()
    
    def validate(self) -> None:
        """验证数据完整性"""
        if not self.symbol or not self.symbol.strip():
            raise ValueError("交易对不能为空")
        
        if not isinstance(self.timestamp, datetime):
            raise ValueError("时间戳必须是datetime对象")
        
        if not isinstance(self.bids, list) or not isinstance(self.asks, list):
            raise ValueError("订单簿数据必须是列表")
    
    def best_bid(self) -> Optional[tuple]:
        """最优买单价格"""
        if self.bids:
            return max(self.bids, key=lambda x: x[0])
        return None
    
    def best_ask(self) -> Optional[tuple]:
        """最优卖单价格"""
        if self.asks:
            return min(self.asks, key=lambda x: x[0])
        return None
    
    def spread(self) -> Optional[float]:
        """买卖价差"""
        best_bid = self.best_bid()
        best_ask = self.best_ask()
        if best_bid and best_ask:
            return best_ask[0] - best_bid[0]
        return None
    
    def spread_percent(self) -> Optional[float]:
        """买卖价差百分比"""
        best_bid = self.best_bid()
        spread = self.spread()
        if spread is not None and best_bid and best_bid[0] > 0:
            return spread / best_bid[0] * 100
        return None
    
    def bid_depth(self, depth: int = 5) -> float:
        """买单深度（指定档位内的累计数量）"""
        return sum(qty for _, qty in self.bids[:depth])
    
    def ask_depth(self, depth: int = 5) -> float:
        """卖单深度（指定档位内的累计数量）"""
        return sum(qty for _, qty in self.asks[:depth])
    
    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        return {
            'symbol': self.symbol,
            'timestamp': self.timestamp.isoformat(),
            'bids': self.bids,
            'asks': self.asks
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'OrderBookSnapshot':
        """从字典反序列化"""
        if isinstance(data['timestamp'], str):
            data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        return cls(**data)


@dataclass
class VolatilityEvent:
    """价格波动事件模型"""
    id: str
    symbol: str                      # 币种，如 BTC
    start_time: datetime             # 波动开始时间
    end_time: datetime               # 波动结束时间
    price_change_percent: float      # 价格变化百分比
    start_price: float               # 起始价格
    end_price: float                 # 结束价格
    volatility_type: str             # "surge" 或 "plunge"
    severity: str                    # 严重程度
    
    # 关联的市场数据（可选）
    funding_rate: Optional[float] = None
    funding_time: Optional[datetime] = None
    basis_spread_percent: Optional[float] = None
    spot_price: Optional[float] = None
    futures_price: Optional[float] = None
    order_book_bid_depth: Optional[float] = None
    order_book_ask_depth: Optional[float] = None
    order_book_spread_percent: Optional[float] = None
    volume_spike_ratio: Optional[float] = None  # 成交量放大倍数
    
    created_at: Optional[datetime] = None
    
    def __post_init__(self):
        """数据验证"""
        if self.created_at is None:
            self.created_at = datetime.now()
        self.validate()
    
    def validate(self) -> None:
        """验证数据完整性"""
        if not self.id or not self.id.strip():
            raise ValueError("事件ID不能为空")
        
        if not self.symbol or not self.symbol.strip():
            raise ValueError("币种不能为空")
        
        if self.symbol.upper() not in ["BTC", "ETH"]:
            raise ValueError(f"不支持的币种: {self.symbol}")
        
        if not isinstance(self.start_time, datetime) or not isinstance(self.end_time, datetime):
            raise ValueError("时间必须是datetime对象")
        
        if self.end_time <= self.start_time:
            raise ValueError("结束时间必须晚于开始时间")
        
        if self.start_price <= 0 or self.end_price <= 0:
            raise ValueError("价格必须为正数")
        
        if self.volatility_type not in [VolatilityType.SURGE, VolatilityType.PLUNGE]:
            raise ValueError(f"无效的波动类型: {self.volatility_type}")
        
        if self.severity not in [VolatilitySeverity.LOW, VolatilitySeverity.MEDIUM, 
                                  VolatilitySeverity.HIGH, VolatilitySeverity.EXTREME]:
            raise ValueError(f"无效的严重程度: {self.severity}")
    
    def duration_seconds(self) -> float:
        """计算波动持续时间（秒）"""
        return (self.end_time - self.start_time).total_seconds()
    
    def duration_minutes(self) -> float:
        """计算波动持续时间（分钟）"""
        return self.duration_seconds() / 60
    
    def price_change_absolute(self) -> float:
        """计算价格变化绝对值"""
        return abs(self.end_price - self.start_price)
    
    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        data = asdict(self)
        data['start_time'] = self.start_time.isoformat()
        data['end_time'] = self.end_time.isoformat()
        if self.funding_time:
            data['funding_time'] = self.funding_time.isoformat()
        if self.created_at:
            data['created_at'] = self.created_at.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'VolatilityEvent':
        """从字典反序列化"""
        if isinstance(data['start_time'], str):
            data['start_time'] = datetime.fromisoformat(data['start_time'])
        if isinstance(data['end_time'], str):
            data['end_time'] = datetime.fromisoformat(data['end_time'])
        if data.get('funding_time') and isinstance(data['funding_time'], str):
            data['funding_time'] = datetime.fromisoformat(data['funding_time'])
        if data.get('created_at') and isinstance(data['created_at'], str):
            data['created_at'] = datetime.fromisoformat(data['created_at'])
        return cls(**data)
    
    def to_json(self) -> str:
        """序列化为JSON字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)
    
    @classmethod
    def generate_id(cls, symbol: str, start_time: datetime) -> str:
        """生成事件ID"""
        id_str = f"{symbol}_{start_time.isoformat()}"
        return hashlib.sha256(id_str.encode('utf-8')).hexdigest()[:16]
    
    @classmethod
    def classify_severity(cls, price_change_percent: float, thresholds: Dict[str, float] = None) -> str:
        """根据价格变化分类严重程度"""
        if thresholds is None:
            thresholds = {
                "low": 2.0,
                "medium": 5.0,
                "high": 10.0,
                "extreme": 20.0
            }
        
        abs_change = abs(price_change_percent)
        
        if abs_change >= thresholds.get("extreme", 20):
            return VolatilitySeverity.EXTREME
        elif abs_change >= thresholds.get("high", 10):
            return VolatilitySeverity.HIGH
        elif abs_change >= thresholds.get("medium", 5):
            return VolatilitySeverity.MEDIUM
        elif abs_change >= thresholds.get("low", 2):
            return VolatilitySeverity.LOW
        else:
            return VolatilitySeverity.LOW


@dataclass
class MarketContext:
    """市场上下文数据 - 用于与大模型分析集成"""
    volatility_events: List[VolatilityEvent]
    time_window_hours: int
    generated_at: datetime
    
    def __post_init__(self):
        """数据验证"""
        if not isinstance(self.generated_at, datetime):
            self.generated_at = datetime.now()
        
        if self.time_window_hours <= 0:
            raise ValueError("时间窗口必须为正数")
    
    def get_summary(self) -> str:
        """生成市场上下文的摘要文本"""
        if not self.volatility_events:
            return f"在最近的{self.time_window_hours}小时内未检测到显著的价格波动。"
        
        lines = [f"在最近的{self.time_window_hours}小时内检测到{len(self.volatility_events)}个异常波动事件："]
        
        for event in self.volatility_events:
            direction = "上涨" if event.volatility_type == VolatilityType.SURGE else "下跌"
            severity_cn = {
                VolatilitySeverity.LOW: "轻度",
                VolatilitySeverity.MEDIUM: "中度",
                VolatilitySeverity.HIGH: "重度",
                VolatilitySeverity.EXTREME: "极端"
            }.get(event.severity, event.severity)
            
            duration_str = f"{event.duration_minutes():.1f}分钟"
            
            line = f"- {event.symbol}: {direction}{event.price_change_percent:+.2f}% ({severity_cn})，持续{duration_str}"
            
            if event.funding_rate is not None:
                line += f"，资金费率{event.funding_rate*100:+.4f}%"
            
            if event.basis_spread_percent is not None:
                line += f"，基差{event.basis_spread_percent:+.2f}%"
            
            lines.append(line)
        
        return "\n".join(lines)
    
    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        return {
            'volatility_events': [e.to_dict() for e in self.volatility_events],
            'time_window_hours': self.time_window_hours,
            'generated_at': self.generated_at.isoformat()
        }
