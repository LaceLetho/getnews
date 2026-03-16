"""
波动率检测算法

实现基于滑动窗口的价格波动检测算法，识别异常波动事件。
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

from .models import KlineData, VolatilityEvent, VolatilityType, VolatilitySeverity


logger = logging.getLogger(__name__)


@dataclass
class VolatilityConfig:
    """波动率检测配置"""
    threshold_percent: float = 5.0          # 触发阈值（百分比）
    window_minutes: int = 5                 # 滑动窗口大小（分钟）
    merge_gap_minutes: int = 10             # 合并相邻事件的最大间隔（分钟）
    min_duration_minutes: float = 1.0       # 最小持续时间（分钟）
    severity_thresholds: Dict[str, float] = None  # 严重程度阈值
    
    def __post_init__(self):
        if self.severity_thresholds is None:
            self.severity_thresholds = {
                "low": 2.0,
                "medium": 5.0,
                "high": 10.0,
                "extreme": 20.0
            }


class VolatilityDetector:
    """波动率检测器"""
    
    def __init__(self, config: Optional[VolatilityConfig] = None):
        """
        初始化波动率检测器
        
        Args:
            config: 检测配置，如果为None则使用默认配置
        """
        self.config = config or VolatilityConfig()
        self.logger = logging.getLogger(__name__)
    
    def detect(self, klines: List[KlineData], symbol: str = None) -> List[VolatilityEvent]:
        """
        从K线数据中检测波动事件
        
        Args:
            klines: K线数据列表
            symbol: 币种符号（可选，如果K线数据中有则从K线获取）
        
        Returns:
            检测到的波动事件列表
        """
        if not klines:
            self.logger.warning("K线数据为空，无法检测波动")
            return []
        
        if len(klines) < self.config.window_minutes:
            self.logger.warning(f"K线数据不足（{len(klines)}条），需要至少{self.config.window_minutes}条")
            return []
        
        # 确保K线按时间排序
        klines = sorted(klines, key=lambda k: k.timestamp)
        
        # 从K线数据获取币种
        if symbol is None and klines:
            symbol = klines[0].symbol.replace("USDT", "").replace("USD", "")
        
        # 使用滑动窗口检测
        raw_events = self._detect_with_sliding_window(klines, symbol)
        
        # 合并连续事件
        merged_events = self._merge_continuous_events(raw_events)
        
        # 过滤掉持续时间过短的事件
        filtered_events = [
            e for e in merged_events 
            if e.duration_minutes() >= self.config.min_duration_minutes
        ]
        
        self.logger.info(
            f"检测到 {len(filtered_events)} 个波动事件 "
            f"（原始：{len(raw_events)}，合并后：{len(merged_events)}）"
        )
        
        return filtered_events
    
    def _detect_with_sliding_window(self, klines: List[KlineData], symbol: str) -> List[VolatilityEvent]:
        """
        使用滑动窗口检测波动
        
        算法说明：
        1. 使用N分钟滑动窗口（N = window_minutes）
        2. 计算窗口内的价格变化率
        3. 如果变化率超过阈值，记录为波动事件
        4. 窗口每次滑动1分钟
        
        Args:
            klines: K线数据列表
            symbol: 币种符号
        
        Returns:
            原始波动事件列表（未合并）
        """
        events = []
        window_size = self.config.window_minutes
        threshold = self.config.threshold_percent
        
        i = 0
        while i <= len(klines) - window_size:
            window = klines[i:i + window_size]
            
            # 计算窗口内的价格变化
            start_price = window[0].open_price
            end_price = window[-1].close_price
            
            if start_price <= 0:
                i += 1
                continue
            
            price_change_percent = (end_price - start_price) / start_price * 100
            abs_change = abs(price_change_percent)
            
            # 检查是否超过阈值
            if abs_change >= threshold:
                # 确定波动类型
                if price_change_percent > 0:
                    vol_type = VolatilityType.SURGE
                else:
                    vol_type = VolatilityType.PLUNGE
                
                # 分类严重程度
                severity = VolatilityEvent.classify_severity(
                    price_change_percent, 
                    self.config.severity_thresholds
                )
                
                # 创建事件
                event = VolatilityEvent(
                    id=VolatilityEvent.generate_id(symbol, window[0].timestamp),
                    symbol=symbol,
                    start_time=window[0].timestamp,
                    end_time=window[-1].close_time,
                    price_change_percent=round(price_change_percent, 4),
                    start_price=start_price,
                    end_price=end_price,
                    volatility_type=vol_type,
                    severity=severity
                )
                
                events.append(event)
                self.logger.debug(
                    f"检测到波动: {symbol} {vol_type.value} {price_change_percent:+.2f}% "
                    f"从 {start_price} 到 {end_price}"
                )
                
                # 跳过窗口的剩余部分，避免重复检测同一波动
                # 找到价格变化最大的点，从那里继续
                max_change_idx = self._find_max_change_in_window(window)
                i += max(1, max_change_idx)
            else:
                i += 1
        
        return events
    
    def _find_max_change_in_window(self, window: List[KlineData]) -> int:
        """
        在窗口内找到价格变化最大的K线索引
        
        Args:
            window: K线窗口
        
        Returns:
            索引位置
        """
        if len(window) < 2:
            return 0
        
        max_change = 0
        max_idx = 0
        
        for i in range(1, len(window)):
            change = abs(window[i].close_price - window[i-1].close_price)
            if change > max_change:
                max_change = change
                max_idx = i
        
        return max_idx
    
    def _merge_continuous_events(self, events: List[VolatilityEvent]) -> List[VolatilityEvent]:
        """
        合并连续的波动事件
        
        如果两个相同类型的波动事件之间的时间间隔小于阈值，则合并它们。
        
        Args:
            events: 原始事件列表
        
        Returns:
            合并后的事件列表
        """
        if not events:
            return []
        
        # 按时间排序
        events = sorted(events, key=lambda e: e.start_time)
        
        merged = []
        current_event = None
        
        for event in events:
            if current_event is None:
                current_event = event
                continue
            
            # 检查是否可以合并
            time_gap = (event.start_time - current_event.end_time).total_seconds() / 60
            same_type = event.volatility_type == current_event.volatility_type
            same_symbol = event.symbol == current_event.symbol
            
            if same_type and same_symbol and time_gap <= self.config.merge_gap_minutes:
                # 合并事件
                current_event.end_time = event.end_time
                current_event.end_price = event.end_price
                current_event.price_change_percent = (
                    (current_event.end_price - current_event.start_price) 
                    / current_event.start_price * 100
                )
                # 更新严重程度
                current_event.severity = VolatilityEvent.classify_severity(
                    current_event.price_change_percent,
                    self.config.severity_thresholds
                )
            else:
                # 保存当前事件并开始新事件
                merged.append(current_event)
                current_event = event
        
        # 添加最后一个事件
        if current_event:
            merged.append(current_event)
        
        return merged
    
    def enrich_events_with_market_data(
        self, 
        events: List[VolatilityEvent],
        funding_rates: List,
        order_book: Optional,
        basis_spread: Optional[float],
        spot_price: Optional[float],
        futures_price: Optional[float]
    ) -> List[VolatilityEvent]:
        """
        为波动事件添加市场数据
        
        Args:
            events: 波动事件列表
            funding_rates: 资金费率列表
            order_book: 订单簿快照
            basis_spread: 基差百分比
            spot_price: 现货价格
            futures_price: 合约价格
        
        Returns:
             enriched 事件列表
        """
        for event in events:
            # 查找最接近波动开始时间的资金费率
            if funding_rates:
                closest_funding = self._find_closest_funding_rate(
                    event.start_time, funding_rates
                )
                if closest_funding:
                    event.funding_rate = closest_funding.funding_rate
                    event.funding_time = closest_funding.funding_time
            
            # 添加订单簿数据
            if order_book:
                event.order_book_bid_depth = order_book.bid_depth()
                event.order_book_ask_depth = order_book.ask_depth()
                spread_percent = order_book.spread_percent()
                if spread_percent is not None:
                    event.order_book_spread_percent = spread_percent
            
            # 添加基差数据
            if basis_spread is not None:
                event.basis_spread_percent = basis_spread
            
            if spot_price is not None:
                event.spot_price = spot_price
            
            if futures_price is not None:
                event.futures_price = futures_price
        
        return events
    
    def _find_closest_funding_rate(self, target_time: datetime, funding_rates: List) -> Optional:
        """
        查找最接近目标时间的资金费率
        
        Args:
            target_time: 目标时间
            funding_rates: 资金费率列表
        
        Returns:
            最接近的FundingRate
        """
        if not funding_rates:
            return None
        
        return min(
            funding_rates,
            key=lambda r: abs((r.funding_time - target_time).total_seconds())
        )
    
    def analyze_volume_spike(self, klines: List[KlineData], event: VolatilityEvent) -> Optional[float]:
        """
        分析成交量放大倍数
        
        计算波动期间的平均成交量与之前一段时间的成交量的比值。
        
        Args:
            klines: K线数据列表
            event: 波动事件
        
        Returns:
            成交量放大倍数
        """
        if not klines:
            return None
        
        # 筛选出波动期间的K线
        event_klines = [
            k for k in klines
            if event.start_time <= k.timestamp <= event.end_time
        ]
        
        if not event_klines:
            return None
        
        # 计算波动期间的平均成交量
        event_avg_volume = sum(k.volume for k in event_klines) / len(event_klines)
        
        # 计算波动前30分钟的平均成交量
        baseline_start = event.start_time - timedelta(minutes=30)
        baseline_klines = [
            k for k in klines
            if baseline_start <= k.timestamp < event.start_time
        ]
        
        if baseline_klines:
            baseline_avg_volume = sum(k.volume for k in baseline_klines) / len(baseline_klines)
            if baseline_avg_volume > 0:
                return round(event_avg_volume / baseline_avg_volume, 2)
        
        return None
    
    def get_summary(self, events: List[VolatilityEvent]) -> Dict[str, any]:
        """
        获取波动检测的统计摘要
        
        Args:
            events: 波动事件列表
        
        Returns:
            统计摘要字典
        """
        if not events:
            return {
                "total_events": 0,
                "surge_count": 0,
                "plunge_count": 0,
                "avg_change_percent": 0,
                "max_change_percent": 0,
                "by_severity": {}
            }
        
        surge_count = sum(1 for e in events if e.volatility_type == VolatilityType.SURGE)
        plunge_count = len(events) - surge_count
        
        changes = [abs(e.price_change_percent) for e in events]
        
        by_severity = {}
        for severity in VolatilitySeverity:
            count = sum(1 for e in events if e.severity == severity.value)
            by_severity[severity.value] = count
        
        return {
            "total_events": len(events),
            "surge_count": surge_count,
            "plunge_count": plunge_count,
            "avg_change_percent": round(sum(changes) / len(changes), 2),
            "max_change_percent": round(max(changes), 2),
            "by_severity": by_severity
        }
