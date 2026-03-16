"""
市场数据模块

用于获取加密货币市场数据并检测价格异常波动。
"""

from .models import KlineData, FundingRate, VolatilityEvent, OrderBookSnapshot
from .binance_client import BinanceClient
from .volatility_detector import VolatilityDetector
from .market_data_service import MarketDataService

__all__ = [
    'KlineData',
    'FundingRate', 
    'VolatilityEvent',
    'OrderBookSnapshot',
    'BinanceClient',
    'VolatilityDetector',
    'MarketDataService',
]
