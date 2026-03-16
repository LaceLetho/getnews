# 波动率检测模块设计文档

## 概述

本模块用于在新闻分析之前异步检测ETH和BTC价格的异常波动事件。

## 功能需求

### 第一阶段

1. **获取K线数据**
   - 获取ETH和BTC的1分钟级别K线
   - 时间窗口 = 新闻时间窗口的2倍
   - 例如：新闻时间窗口1小时 → K线获取最近2小时

2. **检测异常波动**
   - 使用波动率算法识别突然的价格变动（如10:23-10:30暴涨5%或下跌5%）
   - 记录异常波动的时间段和涨跌幅

3. **收集市场数据**
   - 合约资金费率（Funding Rate）
   - 各交易所的基差（Spot vs Futures）
   - 订单簿快照（Order Book Depth）

4. **存储波动事件**
   - 将异常波动事件存储到数据库
   - 包含：波动时间、幅度、资金费率、基差等

### 第二阶段（待实施）
- 将异常波动事件与原始新闻列表一起给大模型分析
- 让大模型分析可能哪些消息引发了市场波动

## 架构设计

```
crypto_news_analyzer/
├── market_data/               # 新模块：市场数据收集
│   ├── __init__.py
│   ├── models.py             # 数据模型（K线、波动事件等）
│   ├── binance_client.py     # Binance API客户端
│   ├── volatility_detector.py # 波动率检测算法
│   └── market_data_service.py # 主服务（整合数据收集和分析）
└── ...
```

## 数据源选择

### 推荐：Binance API（免费、功能全面）

**优势：**
- 完全免费
- 数据质量高
- 无需API Key即可获取市场数据
- 支持REST API和WebSocket

**API端点：**

1. **K线数据（OHLCV）**
   ```
   GET /api/v3/klines
   参数：
   - symbol: BTCUSDT, ETHUSDT
   - interval: 1m
   - startTime/endTime: 时间戳（毫秒）
   - limit: 最多1000条
   ```

2. **资金费率**
   ```
   GET /api/v3/fundingRate
   参数：
   - symbol: BTCUSDT, ETHUSDT
   - startTime/endTime: 时间戳（毫秒）
   - limit: 最多1000条
   ```

3. **24hr Ticker（获取现货和合约标记价格）**
   ```
   GET /api/v3/ticker/24hr
   参数：
   - symbol: BTCUSDT
   ```

4. **深度订单簿**
   ```
   GET /api/v3/depth
   参数：
   - symbol: BTCUSDT
   - limit: 5, 10, 20, 50, 100, 500, 1000, 5000
   ```

**频率限制：**
- 公共API：1200请求/分钟
- 2小时1分钟K线 = 120条数据，轻松在限制范围内

## 数据模型设计

### 1. KlineData（K线数据）
```python
@dataclass
class KlineData:
    symbol: str              # BTCUSDT 或 ETHUSDT
    timestamp: datetime      # K线开始时间
    open_price: float
    high_price: float
    low_price: float
    close_price: float
    volume: float
    close_time: datetime
    quote_volume: float
    trades_count: int
```

### 2. VolatilityEvent（波动事件）
```python
@dataclass
class VolatilityEvent:
    id: str
    symbol: str              # BTC 或 ETH
    start_time: datetime     # 波动开始时间
    end_time: datetime       # 波动结束时间
    price_change_percent: float  # 涨跌幅度（%）
    start_price: float
    end_price: float
    volatility_type: str     # "surge" (暴涨) 或 "plunge" (暴跌)
    
    # 关联的市场数据
    funding_rate: Optional[float]     # 资金费率
    basis_spread_percent: Optional[float]  # 基差（%）
    spot_price: Optional[float]
    futures_price: Optional[float]
    
    # 订单簿快照
    order_book_bid_depth: Optional[float]  # 买单深度
    order_book_ask_depth: Optional[float]  # 卖单深度
    order_book_spread_percent: Optional[float]  # 买卖价差（%）
    
    created_at: datetime
```

### 3. FundingRate（资金费率）
```python
@dataclass
class FundingRate:
    symbol: str
    funding_time: datetime
    funding_rate: float
    mark_price: float
```

## 波动率检测算法

### 算法思路

1. **滑动窗口检测**
   - 使用5分钟滑动窗口（5根1分钟K线）
   - 计算窗口内的价格变化率：`(window_end_close - window_start_open) / window_start_open * 100`

2. **异常波动判定**
   - 涨幅 ≥ 5% → 暴涨事件
   - 跌幅 ≤ -5% → 暴跌事件

3. **连续波动合并**
   - 如果多个连续窗口都满足条件，合并为一个持续事件
   - 记录事件的开始时间和结束时间

### 伪代码
```python
def detect_volatility(klines: List[KlineData], threshold: float = 5.0) -> List[VolatilityEvent]:
    window_size = 5  # 5分钟
    events = []
    current_event = None
    
    for i in range(len(klines) - window_size + 1):
        window = klines[i:i+window_size]
        start_price = window[0].open_price
        end_price = window[-1].close_price
        change_percent = (end_price - start_price) / start_price * 100
        
        if abs(change_percent) >= threshold:
            if current_event is None:
                # 开始新事件
                current_event = VolatilityEvent(
                    start_time=window[0].timestamp,
                    start_price=start_price,
                    volatility_type="surge" if change_percent > 0 else "plunge",
                    ...
                )
            else:
                # 延续现有事件
                current_event.end_time = window[-1].close_time
                current_event.end_price = end_price
                current_event.price_change_percent = (
                    (end_price - current_event.start_price) / current_event.start_price * 100
                )
        else:
            if current_event is not None:
                # 结束当前事件
                events.append(current_event)
                current_event = None
    
    # 处理最后一个事件
    if current_event is not None:
        events.append(current_event)
    
    return events
```

## 数据库设计

### 新表：volatility_events
```sql
CREATE TABLE volatility_events (
    id TEXT PRIMARY KEY,
    symbol TEXT NOT NULL,              -- BTC 或 ETH
    start_time DATETIME NOT NULL,
    end_time DATETIME NOT NULL,
    price_change_percent REAL NOT NULL,
    start_price REAL NOT NULL,
    end_price REAL NOT NULL,
    volatility_type TEXT NOT NULL,     -- 'surge' 或 'plunge'
    
    -- 资金费率
    funding_rate REAL,
    funding_time DATETIME,
    
    -- 基差
    basis_spread_percent REAL,
    spot_price REAL,
    futures_price REAL,
    
    -- 订单簿
    order_book_bid_depth REAL,
    order_book_ask_depth REAL,
    order_book_spread_percent REAL,
    
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 索引
CREATE INDEX idx_volatility_events_time ON volatility_events (start_time, end_time);
CREATE INDEX idx_volatility_events_symbol ON volatility_events (symbol);
```

### 新表：klines（可选，用于缓存）
```sql
CREATE TABLE klines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    timestamp DATETIME NOT NULL,
    open_price REAL NOT NULL,
    high_price REAL,
    low_price REAL,
    close_price REAL NOT NULL,
    volume REAL,
    UNIQUE(symbol, timestamp)
);

CREATE INDEX idx_klines_symbol_time ON klines (symbol, timestamp);
```

## 集成方案

### 在 execution_coordinator.py 中添加

```python
class MainController:
    def __init__(self, ...):
        # ... 现有组件 ...
        self.volatility_detector: Optional[VolatilityDetector] = None
    
    def initialize_system(self) -> bool:
        # ... 现有初始化 ...
        
        # 初始化波动率检测器
        from .market_data.volatility_detector import VolatilityDetector
        self.volatility_detector = VolatilityDetector(self.data_manager)
        
    async def coordinate_workflow(self, ...):
        # 在新闻分析之前运行波动率检测
        await self._execute_volatility_detection_stage()
        
        # 继续原有的新闻爬取和分析流程
        ...
    
    async def _execute_volatility_detection_stage(self):
        """执行波动率检测阶段"""
        time_window_hours = self.config_manager.get_time_window_hours()
        volatility_events = await self.volatility_detector.detect(
            time_window_hours=time_window_hours * 2  # 2倍时间窗口
        )
        
        if volatility_events:
            self.logger.info(f"检测到 {len(volatility_events)} 个异常波动事件")
            # 存入数据库
            for event in volatility_events:
                self.data_manager.save_volatility_event(event)
```

## 配置选项

在 `config.json` 中添加：
```json
{
  "volatility_detection": {
    "enabled": true,
    "threshold_percent": 5.0,
    "window_minutes": 5,
    "symbols": ["BTC", "ETH"],
    "fetch_funding_rate": true,
    "fetch_basis_spread": true,
    "fetch_order_book": true
  }
}
```

## 开发计划

1. **数据模型** → 定义KlineData、VolatilityEvent等模型
2. **API客户端** → 实现Binance API客户端
3. **检测算法** → 实现滑动窗口波动率检测
4. **数据存储** → 扩展DataManager支持波动事件存储
5. **服务集成** → 创建VolatilityDetector主服务
6. **执行流集成** → 在execution_coordinator中添加调用
7. **配置** → 添加配置选项
8. **测试** → 单元测试和集成测试

## 注意事项

1. **API限流**: Binance有请求频率限制，需要实现重试和限流逻辑
2. **时间同步**: 确保使用UTC时间处理所有数据
3. **错误处理**: API可能失败，需要有fallback机制
4. **数据完整性**: 检测到的波动事件需要关联准确的市场数据
5. **性能**: 考虑到数据量不大（120条K线/2小时），性能应该不是问题
