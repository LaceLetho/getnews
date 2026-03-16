"""
Binance API 客户端

用于获取加密货币市场数据，包括K线、资金费率、订单簿等。
使用Binance官方API，无需认证即可获取市场数据。
"""

import logging
import time
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple
import requests
from requests.adapters import HTTPAdapter
from urllib.parse import urljoin

from .models import KlineData, FundingRate, OrderBookSnapshot


logger = logging.getLogger(__name__)


class BinanceClient:
    """Binance API客户端"""
    
    # API端点
    SPOT_BASE_URL = "https://api.binance.com"
    FUTURES_BASE_URL = "https://fapi.binance.com"
    
    # 请求权重限制 (每分钟1200)
    MAX_REQUESTS_PER_MINUTE = 1200
    
    def __init__(self, api_key: Optional[str] = None):
        """
        初始化Binance客户端
        
        Args:
            api_key: 可选的API Key，用于提高限流额度（市场数据不需要）
        """
        self.api_key = api_key
        self.session = requests.Session()
        
        # 配置重试策略
        adapter = HTTPAdapter(max_retries=3)
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)
        
        # 限流控制
        self._last_request_time = 0
        self._min_request_interval = 0.05  # 最小请求间隔50ms
        
        logger.info("Binance客户端初始化完成")
    
    def _make_request(self, endpoint: str, params: Optional[Dict] = None, 
                     base_url: str = None) -> Dict[str, Any]:
        """
        发送HTTP请求
        
        Args:
            endpoint: API端点路径
            params: 查询参数
            base_url: 基础URL（默认为现货API）
        
        Returns:
            JSON响应数据
        """
        if base_url is None:
            base_url = self.SPOT_BASE_URL
        
        url = urljoin(base_url, endpoint)
        
        # 限流控制
        self._rate_limit()
        
        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"请求失败: {url}, 错误: {e}")
            raise
    
    def _rate_limit(self) -> None:
        """简单的限流控制"""
        current_time = time.time()
        time_since_last = current_time - self._last_request_time
        
        if time_since_last < self._min_request_interval:
            sleep_time = self._min_request_interval - time_since_last
            time.sleep(sleep_time)
        
        self._last_request_time = time.time()
    
    def get_klines(self, symbol: str, interval: str = "1m", 
                   start_time: Optional[datetime] = None,
                   end_time: Optional[datetime] = None,
                   limit: int = 1000) -> List[KlineData]:
        """
        获取K线数据
        
        Args:
            symbol: 交易对，如 "BTCUSDT"
            interval: 时间间隔，如 "1m", "5m", "1h", "1d"
            start_time: 开始时间（可选）
            end_time: 结束时间（可选）
            limit: 返回数量限制（最大1000）
        
        Returns:
            KlineData列表
        """
        endpoint = "/api/v3/klines"
        
        params = {
            "symbol": symbol.upper(),
            "interval": interval,
            "limit": min(limit, 1000)
        }
        
        if start_time:
            params["startTime"] = int(start_time.timestamp() * 1000)
        if end_time:
            params["endTime"] = int(end_time.timestamp() * 1000)
        
        try:
            data = self._make_request(endpoint, params)
            klines = []
            
            for item in data:
                # Binance K线数据格式：
                # [open_time, open, high, low, close, volume, close_time, quote_volume, 
                #  trades_count, taker_buy_base, taker_buy_quote, ignore]
                kline = KlineData(
                    symbol=symbol.upper(),
                    timestamp=datetime.fromtimestamp(item[0] / 1000),
                    open_price=float(item[1]),
                    high_price=float(item[2]),
                    low_price=float(item[3]),
                    close_price=float(item[4]),
                    volume=float(item[5]),
                    close_time=datetime.fromtimestamp(item[6] / 1000),
                    quote_volume=float(item[7]),
                    trades_count=int(item[8])
                )
                klines.append(kline)
            
            logger.info(f"获取到 {len(klines)} 条 {symbol} 的 {interval} K线数据")
            return klines
            
        except Exception as e:
            logger.error(f"获取K线数据失败 {symbol}: {e}")
            return []
    
    def get_klines_for_time_window(self, symbol: str, 
                                    time_window_hours: int,
                                    interval: str = "1m") -> List[KlineData]:
        """
        获取指定时间窗口的K线数据
        
        Args:
            symbol: 交易对
            time_window_hours: 时间窗口（小时）
            interval: 时间间隔
        
        Returns:
            KlineData列表
        """
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=time_window_hours)
        
        return self.get_klines(
            symbol=symbol,
            interval=interval,
            start_time=start_time,
            end_time=end_time
        )
    
    def get_funding_rate(self, symbol: str, 
                        start_time: Optional[datetime] = None,
                        end_time: Optional[datetime] = None,
                        limit: int = 1000) -> List[FundingRate]:
        """
        获取资金费率历史
        
        Args:
            symbol: 交易对，如 "BTCUSDT"
            start_time: 开始时间（可选）
            end_time: 结束时间（可选）
            limit: 返回数量限制（最大1000）
        
        Returns:
            FundingRate列表
        """
        endpoint = "/fapi/v1/fundingRate"
        
        params = {
            "symbol": symbol.upper(),
            "limit": min(limit, 1000)
        }
        
        if start_time:
            params["startTime"] = int(start_time.timestamp() * 1000)
        if end_time:
            params["endTime"] = int(end_time.timestamp() * 1000)
        
        try:
            data = self._make_request(endpoint, params, base_url=self.FUTURES_BASE_URL)
            rates = []
            
            for item in data:
                rate = FundingRate(
                    symbol=symbol.upper(),
                    funding_time=datetime.fromtimestamp(item["fundingTime"] / 1000),
                    funding_rate=float(item["fundingRate"]),
                    mark_price=float(item.get("markPrice", 0))
                )
                rates.append(rate)
            
            logger.info(f"获取到 {len(rates)} 条 {symbol} 的资金费率数据")
            return rates
            
        except Exception as e:
            logger.error(f"获取资金费率失败 {symbol}: {e}")
            return []
    
    def get_latest_funding_rate(self, symbol: str) -> Optional[FundingRate]:
        """
        获取最新资金费率
        
        Args:
            symbol: 交易对
        
        Returns:
            最新的FundingRate，如果没有则返回None
        """
        rates = self.get_funding_rate(symbol, limit=1)
        return rates[0] if rates else None
    
    def get_funding_rate_for_time(self, symbol: str, target_time: datetime) -> Optional[FundingRate]:
        """
        获取指定时间点的资金费率（最接近的）
        
        Args:
            symbol: 交易对
            target_time: 目标时间
        
        Returns:
            最接近的FundingRate
        """
        # 获取目标时间前后1小时的费率数据
        start_time = target_time - timedelta(hours=1)
        end_time = target_time + timedelta(hours=1)
        
        rates = self.get_funding_rate(symbol, start_time=start_time, end_time=end_time)
        
        if not rates:
            return None
        
        # 找到最接近目标时间的费率
        closest_rate = min(rates, 
                          key=lambda r: abs((r.funding_time - target_time).total_seconds()))
        
        return closest_rate
    
    def get_order_book(self, symbol: str, limit: int = 100) -> Optional[OrderBookSnapshot]:
        """
        获取订单簿深度
        
        Args:
            symbol: 交易对
            limit: 深度档位（5, 10, 20, 50, 100, 500, 1000, 5000）
        
        Returns:
            OrderBookSnapshot对象
        """
        endpoint = "/api/v3/depth"
        
        params = {
            "symbol": symbol.upper(),
            "limit": limit
        }
        
        try:
            data = self._make_request(endpoint, params)
            
            # 解析买单和卖单
            bids = [(float(price), float(qty)) for price, qty in data.get("bids", [])]
            asks = [(float(price), float(qty)) for price, qty in data.get("asks", [])]
            
            snapshot = OrderBookSnapshot(
                symbol=symbol.upper(),
                timestamp=datetime.now(),
                bids=bids,
                asks=asks
            )
            
            logger.info(f"获取到 {symbol} 的订单簿，买盘{bids[:1]}，卖盘{asks[:1]}")
            return snapshot
            
        except Exception as e:
            logger.error(f"获取订单簿失败 {symbol}: {e}")
            return None
    
    def get_24hr_ticker(self, symbol: str) -> Dict[str, Any]:
        """
        获取24小时价格变动统计
        
        Args:
            symbol: 交易对
        
        Returns:
            24小时统计数据字典
        """
        endpoint = "/api/v3/ticker/24hr"
        
        params = {"symbol": symbol.upper()}
        
        try:
            data = self._make_request(endpoint, params)
            return {
                "symbol": data.get("symbol"),
                "price_change": float(data.get("priceChange", 0)),
                "price_change_percent": float(data.get("priceChangePercent", 0)),
                "weighted_avg_price": float(data.get("weightedAvgPrice", 0)),
                "open_price": float(data.get("openPrice", 0)),
                "high_price": float(data.get("highPrice", 0)),
                "low_price": float(data.get("lowPrice", 0)),
                "last_price": float(data.get("lastPrice", 0)),
                "volume": float(data.get("volume", 0)),
                "quote_volume": float(data.get("quoteVolume", 0)),
                "open_time": datetime.fromtimestamp(data.get("openTime", 0) / 1000),
                "close_time": datetime.fromtimestamp(data.get("closeTime", 0) / 1000),
                "first_id": data.get("firstId"),
                "last_id": data.get("lastId"),
                "count": data.get("count")
            }
        except Exception as e:
            logger.error(f"获取24小时统计失败 {symbol}: {e}")
            return {}
    
    def get_premium_index(self, symbol: str) -> Dict[str, Any]:
        """
        获取永续合约溢价指数（用于计算基差）
        
        Args:
            symbol: 交易对
        
        Returns:
            溢价指数数据
        """
        endpoint = "/fapi/v1/premiumIndex"
        
        params = {"symbol": symbol.upper()}
        
        try:
            data = self._make_request(endpoint, params, base_url=self.FUTURES_BASE_URL)
            return {
                "symbol": data.get("symbol"),
                "mark_price": float(data.get("markPrice", 0)),
                "index_price": float(data.get("indexPrice", 0)),
                "estimated_settle_price": float(data.get("estimatedSettlePrice", 0)),
                "last_funding_rate": float(data.get("lastFundingRate", 0)),
                "next_funding_time": datetime.fromtimestamp(
                    data.get("nextFundingTime", 0) / 1000
                ),
                "interest_rate": float(data.get("interestRate", 0)),
                "time": datetime.fromtimestamp(data.get("time", 0) / 1000)
            }
        except Exception as e:
            logger.error(f"获取溢价指数失败 {symbol}: {e}")
            return {}
    
    def get_basis_spread(self, symbol: str) -> Optional[float]:
        """
        计算基差（永续合约标记价格 - 现货指数价格）
        
        Args:
            symbol: 交易对
        
        Returns:
            基差百分比，如果失败则返回None
        """
        try:
            # 获取永续合约数据
            premium_data = self.get_premium_index(symbol)
            if not premium_data:
                return None
            
            mark_price = premium_data.get("mark_price", 0)
            index_price = premium_data.get("index_price", 0)
            
            if index_price > 0:
                basis_spread = (mark_price - index_price) / index_price * 100
                return basis_spread
            
            return None
            
        except Exception as e:
            logger.error(f"计算基差失败 {symbol}: {e}")
            return None
    
    def get_market_data_for_symbol(self, symbol: str, time_window_hours: int = 2) -> Dict[str, Any]:
        """
        获取指定币种的全套市场数据
        
        Args:
            symbol: 交易对，如 "BTCUSDT"
            time_window_hours: 时间窗口（小时）
        
        Returns:
            包含所有市场数据的字典
        """
        symbol = symbol.upper()
        
        # 获取K线数据
        klines = self.get_klines_for_time_window(
            symbol, time_window_hours, interval="1m"
        )
        
        # 获取资金费率
        start_time = datetime.now() - timedelta(hours=time_window_hours)
        end_time = datetime.now()
        funding_rates = self.get_funding_rate(symbol, start_time=start_time, end_time=end_time)
        
        # 获取订单簿
        order_book = self.get_order_book(symbol, limit=100)
        
        # 获取基差
        basis_spread = self.get_basis_spread(symbol)
        
        # 获取24小时统计
        ticker_24hr = self.get_24hr_ticker(symbol)
        
        return {
            "symbol": symbol,
            "klines": klines,
            "funding_rates": funding_rates,
            "order_book": order_book,
            "basis_spread_percent": basis_spread,
            "ticker_24hr": ticker_24hr,
            "timestamp": datetime.now()
        }
    
    def close(self) -> None:
        """关闭会话"""
        if self.session:
            self.session.close()
            logger.info("Binance客户端已关闭")
    
    def __enter__(self):
        """上下文管理器入口"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.close()
