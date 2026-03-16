"""
市场数据服务

整合数据获取和波动检测功能的主服务。
"""

import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

from .models import (
    KlineData, 
    FundingRate, 
    VolatilityEvent, 
    OrderBookSnapshot,
    MarketContext,
    VolatilitySeverity
)
from .binance_client import BinanceClient
from .volatility_detector import VolatilityDetector, VolatilityConfig


logger = logging.getLogger(__name__)


class MarketDataService:
    """市场数据服务"""
    
    # 默认检测的币种
    DEFAULT_SYMBOLS = ["BTC", "ETH"]
    
    def __init__(
        self, 
        data_manager=None,
        symbols: Optional[List[str]] = None,
        volatility_config: Optional[VolatilityConfig] = None
    ):
        """
        初始化市场数据服务
        
        Args:
            data_manager: 数据管理器实例（可选）
            symbols: 要检测的币种列表，默认["BTC", "ETH"]
            volatility_config: 波动率检测配置
        """
        self.data_manager = data_manager
        self.symbols = symbols or self.DEFAULT_SYMBOLS
        self.volatility_config = volatility_config or VolatilityConfig()
        
        # 初始化组件
        self.binance_client = BinanceClient()
        self.volatility_detector = VolatilityDetector(self.volatility_config)
        
        self.logger = logging.getLogger(__name__)
        self.logger.info(
            f"市场数据服务初始化完成，检测币种: {self.symbols}"
        )
    
    def detect_volatility_for_time_window(
        self, 
        time_window_hours: int,
        enrich_with_market_data: bool = True
    ) -> List[VolatilityEvent]:
        """
        检测指定时间窗口内的波动事件
        
        Args:
            time_window_hours: 时间窗口（小时）
            enrich_with_market_data: 是否添加市场数据（资金费率、订单簿等）
        
        Returns:
            波动事件列表
        """
        all_events = []
        
        for symbol in self.symbols:
            try:
                symbol_upper = symbol.upper()
                trading_pair = f"{symbol_upper}USDT"
                
                self.logger.info(f"开始检测 {symbol} 的波动...")
                
                # 获取K线数据
                klines = self.binance_client.get_klines_for_time_window(
                    symbol=trading_pair,
                    time_window_hours=time_window_hours,
                    interval="1m"
                )
                
                if not klines:
                    self.logger.warning(f"未获取到 {symbol} 的K线数据")
                    continue
                
                # 检测波动
                events = self.volatility_detector.detect(klines, symbol=symbol_upper)
                
                if not events:
                    self.logger.info(f"{symbol} 未检测到显著波动")
                    continue
                
                # 添加市场数据（可选）
                if enrich_with_market_data:
                    events = self._enrich_events_with_market_data(
                        events, symbol_upper, klines
                    )
                
                # 分析成交量放大
                for event in events:
                    volume_spike = self.volatility_detector.analyze_volume_spike(klines, event)
                    event.volume_spike_ratio = volume_spike
                
                all_events.extend(events)
                
                self.logger.info(
                    f"{symbol} 检测到 {len(events)} 个波动事件"
                )
                
            except Exception as e:
                self.logger.error(f"检测 {symbol} 波动时出错: {e}")
                continue
        
        # 按时间排序
        all_events.sort(key=lambda e: e.start_time)
        
        self.logger.info(
            f"波动检测完成，共发现 {len(all_events)} 个事件"
        )
        
        return all_events
    
    def _enrich_events_with_market_data(
        self, 
        events: List[VolatilityEvent], 
        symbol: str,
        klines: List[KlineData]
    ) -> List[VolatilityEvent]:
        """
        为事件添加市场数据
        
        Args:
            events: 波动事件列表
            symbol: 币种
            klines: K线数据
        
        Returns:
            添加市场数据后的事件列表
        """
        if not events:
            return events
        
        trading_pair = f"{symbol}USDT"
        
        try:
            # 获取资金费率（时间窗口覆盖所有事件）
            if events:
                start_time = min(e.start_time for e in events) - timedelta(hours=1)
                end_time = max(e.end_time for e in events) + timedelta(hours=1)
                funding_rates = self.binance_client.get_funding_rate(
                    trading_pair, start_time=start_time, end_time=end_time
                )
            else:
                funding_rates = []
            
            # 获取订单簿（当前快照）
            order_book = self.binance_client.get_order_book(trading_pair, limit=100)
            
            # 获取基差
            basis_spread = self.binance_client.get_basis_spread(trading_pair)
            
            # 获取溢价指数数据（包含现货和合约价格）
            premium_data = self.binance_client.get_premium_index(trading_pair)
            spot_price = premium_data.get("index_price")
            futures_price = premium_data.get("mark_price")
            
            # 使用VolatilityDetector的enrich方法
            events = self.volatility_detector.enrich_events_with_market_data(
                events=events,
                funding_rates=funding_rates,
                order_book=order_book,
                basis_spread=basis_spread,
                spot_price=spot_price,
                futures_price=futures_price
            )
            
        except Exception as e:
            self.logger.warning(f"添加市场数据时出错: {e}")
        
        return events
    
    def save_events_to_database(self, events: List[VolatilityEvent]) -> int:
        """
        将波动事件保存到数据库
        
        Args:
            events: 波动事件列表
        
        Returns:
            成功保存的事件数量
        """
        if not self.data_manager:
            self.logger.warning("未配置数据管理器，无法保存事件")
            return 0
        
        if not events:
            return 0
        
        saved_count = 0
        for event in events:
            try:
                if self.data_manager.add_volatility_event(event):
                    saved_count += 1
            except Exception as e:
                self.logger.error(f"保存波动事件失败: {e}")
        
        self.logger.info(f"成功保存 {saved_count}/{len(events)} 个波动事件到数据库")
        return saved_count
    
    def get_recent_volatility_events(
        self, 
        hours: int = 24,
        symbols: Optional[List[str]] = None,
        min_severity: Optional[str] = None
    ) -> List[VolatilityEvent]:
        """
        从数据库获取最近的波动事件
        
        Args:
            hours: 时间窗口（小时）
            symbols: 币种过滤（可选）
            min_severity: 最小严重程度过滤（可选）
        
        Returns:
            波动事件列表
        """
        if not self.data_manager:
            self.logger.warning("未配置数据管理器，无法获取历史事件")
            return []
        
        try:
            events = self.data_manager.get_volatility_events(
                hours=hours,
                symbols=symbols,
                min_severity=min_severity
            )
            return events
        except Exception as e:
            self.logger.error(f"获取波动事件失败: {e}")
            return []
    
    def get_market_context_for_analysis(self, time_window_hours: int) -> MarketContext:
        """
        获取市场上下文（用于与大模型分析集成）
        
        Args:
            time_window_hours: 时间窗口（小时）
        
        Returns:
            MarketContext对象
        """
        # 优先从数据库获取已保存的事件
        events = self.get_recent_volatility_events(hours=time_window_hours)
        
        # 如果没有历史事件，进行实时检测
        if not events:
            self.logger.info("数据库中无波动事件，执行实时检测...")
            events = self.detect_volatility_for_time_window(time_window_hours)
            # 保存到数据库供后续使用
            self.save_events_to_database(events)
        
        return MarketContext(
            volatility_events=events,
            time_window_hours=time_window_hours,
            generated_at=datetime.now()
        )
    
    def get_current_prices(self) -> Dict[str, Dict[str, float]]:
        """
        获取当前价格
        
        Returns:
            币种价格字典
        """
        prices = {}
        
        for symbol in self.symbols:
            try:
                trading_pair = f"{symbol.upper()}USDT"
                ticker = self.binance_client.get_24hr_ticker(trading_pair)
                
                if ticker:
                    prices[symbol.upper()] = {
                        "last_price": ticker.get("last_price", 0),
                        "price_change_24h": ticker.get("price_change_percent", 0),
                        "high_24h": ticker.get("high_price", 0),
                        "low_24h": ticker.get("low_price", 0),
                        "volume_24h": ticker.get("volume", 0)
                    }
            except Exception as e:
                self.logger.error(f"获取 {symbol} 价格失败: {e}")
        
        return prices
    
    def get_summary_report(self, time_window_hours: int = 24) -> str:
        """
        生成市场数据摘要报告
        
        Args:
            time_window_hours: 时间窗口（小时）
        
        Returns:
            报告文本
        """
        events = self.get_recent_volatility_events(hours=time_window_hours)
        
        if not events:
            return f"最近{time_window_hours}小时内未检测到显著价格波动。"
        
        lines = [f"## 市场波动摘要（最近{time_window_hours}小时）\n"]
        
        # 统计信息
        summary = self.volatility_detector.get_summary(events)
        lines.append(f"- 波动事件总数: {summary['total_events']}")
        lines.append(f"- 暴涨次数: {summary['surge_count']}")
        lines.append(f"- 暴跌次数: {summary['plunge_count']}")
        lines.append(f"- 平均波幅: {summary['avg_change_percent']:.2f}%")
        lines.append(f"- 最大波幅: {summary['max_change_percent']:.2f}%")
        lines.append("")
        
        # 按币种分组
        by_symbol = {}
        for event in events:
            symbol = event.symbol
            if symbol not in by_symbol:
                by_symbol[symbol] = []
            by_symbol[symbol].append(event)
        
        for symbol, symbol_events in by_symbol.items():
            lines.append(f"### {symbol}")
            
            for event in symbol_events:
                direction = "📈" if event.volatility_type == "surge" else "📉"
                severity_emoji = {
                    VolatilitySeverity.LOW: "🟢",
                    VolatilitySeverity.MEDIUM: "🟡",
                    VolatilitySeverity.HIGH: "🟠",
                    VolatilitySeverity.EXTREME: "🔴"
                }.get(event.severity, "⚪")
                
                lines.append(
                    f"{direction} {severity_emoji} {event.start_time.strftime('%m-%d %H:%M')} "
                    f"{event.price_change_percent:+.2f}% "
                    f"({event.duration_minutes():.0f}分钟)"
                )
            
            lines.append("")
        
        return "\n".join(lines)
    
    def close(self) -> None:
        """关闭服务"""
        if self.binance_client:
            self.binance_client.close()
            self.logger.info("市场数据服务已关闭")
    
    def __enter__(self):
        """上下文管理器入口"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.close()
