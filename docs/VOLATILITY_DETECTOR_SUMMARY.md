# 波动率检测模块 - 开发完成总结

## 已完成的工作

### 1. 设计文档
- ✅ 创建了详细的设计文档 (`docs/volatility_detector_design.md`)
- ✅ 定义了数据源选择（使用Binance API）
- ✅ 设计了数据模型和数据库schema

### 2. 新模块创建 (`crypto_news_analyzer/market_data/`)

#### 数据模型 (`models.py`)
- `KlineData` - K线数据模型（OHLCV）
- `VolatilityEvent` - 波动事件模型（包含价格变化、严重程度、市场数据等）
- `FundingRate` - 资金费率模型
- `OrderBookSnapshot` - 订单簿快照模型
- `MarketContext` - 市场上下文（用于大模型分析）
- `VolatilityConfig` - 检测配置
- `VolatilityType` - 波动类型枚举（暴涨/暴跌）
- `VolatilitySeverity` - 严重程度枚举（轻度/中度/重度/极端）

#### Binance API客户端 (`binance_client.py`)
- 获取1分钟K线数据
- 获取资金费率历史
- 获取订单簿深度
- 计算基差（现货 vs 永续合约）
- 限流控制（1200请求/分钟）

#### 波动率检测算法 (`volatility_detector.py`)
- 5分钟滑动窗口检测
- 合并连续波动事件
- 支持自定义阈值和严重程度分级
- 成交量放大倍数分析

#### 市场数据服务 (`market_data_service.py`)
- 整合数据获取和波动检测
- 自动保存检测到的事件到数据库
- 生成市场上下文用于大模型分析
- 生成摘要报告

### 3. 数据库扩展 (`storage/data_manager.py`)
- 新增 `volatility_events` 表
- 新增索引（时间、币种、严重程度）
- CRUD方法：`add_volatility_event`, `get_volatility_events`, `get_volatility_events_count`

### 4. 配置集成 (`config.json`)
```json
"volatility_detection": {
  "enabled": true,
  "symbols": ["BTC", "ETH"],
  "threshold_percent": 5.0,
  "window_minutes": 5,
  "severity_thresholds": {
    "low": 2.0,
    "medium": 5.0,
    "high": 10.0,
    "extreme": 20.0
  },
  "fetch_funding_rate": true,
  "fetch_basis_spread": true,
  "fetch_order_book": true
}
```

### 5. 执行流程集成 (`execution_coordinator.py`)
- 在数据爬取之前执行波动率检测（阶段0）
- 自动初始化 `MarketDataService`
- 检测结果自动保存到数据库
- 波动率检测失败不会阻塞主流程

## 使用方法

### 启用波动率检测
在 `config.json` 中设置：
```json
"volatility_detection": {
  "enabled": true
}
```

### 运行系统
```bash
# 一次性执行
uv run python -m crypto_news_analyzer.main --mode once

# 定时调度
uv run python -m crypto_news_analyzer.main --mode schedule
```

### 检测逻辑
1. 系统启动时，会在新闻爬取之前执行波动率检测
2. 使用2倍新闻时间窗口获取K线数据（如新闻1小时 → K线2小时）
3. 检测>5%的价格波动（可配置）
4. 自动获取资金费率、基差、订单簿等市场数据
5. 将波动事件保存到数据库
6. 继续执行原有的新闻爬取和分析流程

## 数据结构示例

### 波动事件 (VolatilityEvent)
```python
{
    "id": "abc123...",
    "symbol": "BTC",
    "start_time": "2024-03-16T10:23:00",
    "end_time": "2024-03-16T10:30:00",
    "price_change_percent": 7.5,
    "start_price": 65000.0,
    "end_price": 69875.0,
    "volatility_type": "surge",
    "severity": "high",
    "funding_rate": 0.0001,
    "basis_spread_percent": 0.05,
    "volume_spike_ratio": 3.2,
    ...
}
```

## 第二阶段待开发（提示）

当前模块已完成第一阶段功能。第二阶段可以将波动事件传递给大模型分析：

```python
# 在_llm_analyzer.py中使用
from crypto_news_analyzer.market_data import MarketContext

market_context = market_data_service.get_market_context_for_analysis(time_window_hours)
context_text = market_context.get_summary()

# 将context_text添加到LLM提示词中
```

## 文件清单

新增/修改的文件：
```
docs/volatility_detector_design.md
crypto_news_analyzer/market_data/
├── __init__.py
├── models.py
├── binance_client.py
├── volatility_detector.py
└── market_data_service.py
crypto_news_analyzer/storage/data_manager.py  (扩展)
crypto_news_analyzer/execution_coordinator.py  (扩展)
config.json  (扩展)
```
