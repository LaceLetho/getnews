# LLM分析器文档

## 概述

LLM分析器实现了四步分析流程，用于智能分析加密货币新闻和社交媒体内容。它集成了市场快照服务和结构化输出管理器，支持动态分类，不硬编码具体类别。

## 四步分析流程

### 第一步：获取市场快照

使用联网AI服务（如Grok）获取当前加密货币市场的实时快照，包括：
- 当前行情与普遍预期
- 主流赛道与热门新赛道
- 利率环境与主流预期
- 政策环境与核心政策焦点
- 舆论焦点

### 第二步：合并提示词

将市场快照内容与分析提示词模板合并，生成包含完整市场上下文的系统提示词。

**注意**：市场快照中的超链接部分不会被合并，保持原样。

### 第三步：结构化输出

使用instructor等工具强制大模型返回标准JSON格式，确保输出包含以下字段：
- `time`: 发布时间
- `category`: 动态分类类别
- `weight_score`: 重要性评分（0-100）
- `summary`: 内容摘要
- `source`: 原文链接URL

### 第四步：批量分析

将所有新闻批量发送给大模型进行分析，大模型会：
- 完成语义去重
- 筛选过滤噪音内容
- 返回结构化的分析结果

## 核心特性

### 1. 动态分类

系统不硬编码具体的分类类别，而是根据大模型返回的结果动态识别和管理分类。这使得系统可以灵活适应不同的分类需求。

### 2. 批量处理

支持批量分析多条内容，自动分批处理以优化性能和成本。

### 3. 缓存机制

- 市场快照缓存：避免频繁调用联网AI服务
- 系统提示词缓存：提高处理效率

### 4. 模拟模式

支持模拟模式用于测试和开发，无需真实的API密钥。

## 使用方法

### 基本使用

```python
from crypto_news_analyzer.analyzers.llm_analyzer import LLMAnalyzer
from crypto_news_analyzer.models import ContentItem
from datetime import datetime

# 创建分析器
analyzer = LLMAnalyzer(
    api_key="your_api_key",
    grok_api_key="your_grok_key",
    model="gpt-4",
    mock_mode=False
)

# 创建内容项
items = [
    ContentItem(
        id="1",
        title="比特币突破50000美元",
        content="比特币价格今日突破50000美元大关...",
        url="https://example.com/news/1",
        publish_time=datetime.now(),
        source_name="测试源",
        source_type="rss"
    )
]

# 批量分析
results = analyzer.analyze_content_batch(items)

# 处理结果
for result in results:
    print(f"分类: {result.category}")
    print(f"重要性: {result.weight_score}")
    print(f"摘要: {result.summary}")
```

### 四步工作流

```python
# 第一步：获取市场快照
snapshot = analyzer.get_market_snapshot(use_cached=False)

# 第二步：合并提示词
system_prompt = analyzer.merge_prompts_with_snapshot(snapshot)

# 第三步和第四步：批量分析
results = analyzer.analyze_content_batch(items, use_cached_snapshot=True)
```

### 动态分类提取

```python
# 分析内容
results = analyzer.analyze_content_batch(items)

# 提取动态分类
categories = analyzer.get_dynamic_categories(results)

print(f"发现的分类: {categories}")
```

### 缓存管理

```python
# 查看缓存信息
cache_info = analyzer.get_cache_info()
print(f"有缓存的快照: {cache_info['has_cached_snapshot']}")

# 清除缓存
analyzer.clear_cache()
```

### 配置更新

```python
# 更新配置
analyzer.update_config(
    temperature=0.5,
    batch_size=20,
    max_tokens=2000
)
```

## 初始化参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `api_key` | str | None | LLM API密钥，如果为None则从环境变量读取 |
| `grok_api_key` | str | None | Grok API密钥，用于市场快照 |
| `model` | str | "gpt-4" | 分析使用的模型名称 |
| `summary_model` | str | "grok-beta" | 市场快照使用的模型名称 |
| `market_prompt_path` | str | "./prompts/market_summary_prompt.md" | 市场快照提示词路径 |
| `analysis_prompt_path` | str | "./prompts/analysis_prompt.md" | 分析提示词路径 |
| `temperature` | float | 0.1 | 温度参数 |
| `max_tokens` | int | 4000 | 最大token数 |
| `batch_size` | int | 10 | 批量分析的批次大小 |
| `mock_mode` | bool | False | 是否使用模拟模式 |

## 主要方法

### analyze_content_batch()

批量分析内容（四步流程）

**参数**:
- `items`: List[ContentItem] - 内容项列表
- `use_cached_snapshot`: bool - 是否使用缓存的市场快照

**返回**: List[StructuredAnalysisResult]

### get_market_snapshot()

获取市场快照（第一步）

**参数**:
- `use_cached`: bool - 是否使用缓存的快照

**返回**: MarketSnapshot

### merge_prompts_with_snapshot()

合并提示词（第二步）

**参数**:
- `market_snapshot`: MarketSnapshot - 市场快照对象

**返回**: str - 合并后的系统提示词

### get_dynamic_categories()

从分析结果中提取动态分类

**参数**:
- `results`: List[StructuredAnalysisResult] - 分析结果列表

**返回**: List[str] - 分类名称列表

### clear_cache()

清除缓存的市场快照和系统提示词

### get_cache_info()

获取缓存信息

**返回**: Dict[str, Any] - 缓存信息字典

### update_config()

更新配置

**参数**: 可变关键字参数，支持的配置项包括：
- `temperature`: float
- `max_tokens`: int
- `batch_size`: int
- `model`: str

## 环境变量

系统支持从环境变量读取配置：

- `LLM_API_KEY`: LLM API密钥
- `GROK_API_KEY`: Grok API密钥（用于市场快照）

## 提示词模板

### 市场快照提示词 (market_summary_prompt.md)

用于向联网AI请求市场快照的提示词模板。

### 分析提示词 (analysis_prompt.md)

用于内容分析的提示词模板，包含：
- 角色定义
- 分析目标
- 分类定义
- 输出格式要求
- 市场上下文占位符 `${Grok_Summary_Here}`

## 输出格式

### StructuredAnalysisResult

```python
{
    "time": "2024-01-01 12:00",
    "category": "Whale",
    "weight_score": 85,
    "summary": "某巨鲸地址转移10000 ETH到交易所",
    "source": "https://example.com/news/123"
}
```

### BatchAnalysisResult

```python
{
    "results": [
        {
            "time": "2024-01-01 12:00",
            "category": "Whale",
            "weight_score": 85,
            "summary": "...",
            "source": "..."
        },
        ...
    ]
}
```

**注意**: `results` 可以是空列表 `[]`，表示所有内容被过滤。

## 错误处理

### 常见错误

1. **API密钥未配置**
   - 错误: "未提供LLM API密钥"
   - 解决: 设置环境变量或在初始化时提供API密钥

2. **市场快照获取失败**
   - 系统会自动使用备用快照
   - 日志会记录错误信息

3. **结构化输出验证失败**
   - 系统会尝试恢复格式错误的响应
   - 如果无法恢复，会抛出ValidationError

4. **批量分析失败**
   - 系统会继续处理下一批次
   - 失败的批次会被记录在日志中

## 性能优化

### 批次大小

默认批次大小为10，可以根据实际情况调整：
- 较小的批次：更快的响应时间，但总体处理时间可能更长
- 较大的批次：更好的吞吐量，但单次请求时间更长

### 缓存策略

- 市场快照默认缓存30分钟
- 系统提示词在内存中缓存
- 可以通过 `use_cached=False` 强制刷新

### 并发处理

当前实现是串行处理批次，未来可以考虑并发处理多个批次以提高性能。

## 测试

### 单元测试

```bash
uv run pytest tests/test_llm_analyzer.py -v
```

### 模拟模式测试

```python
analyzer = LLMAnalyzer(mock_mode=True)
results = analyzer.analyze_content_batch(items)
```

### 真实API测试

需要配置环境变量：
```bash
export LLM_API_KEY="your_api_key"
export GROK_API_KEY="your_grok_key"
```

## 最佳实践

1. **使用缓存**: 在同一执行周期内，使用缓存的市场快照以减少API调用
2. **批量处理**: 尽可能批量处理内容以提高效率
3. **错误处理**: 捕获并处理可能的异常，避免单个失败影响整体流程
4. **日志记录**: 启用日志以便调试和监控
5. **模拟模式**: 在开发和测试阶段使用模拟模式

## 相关文档

- [市场快照服务文档](./market_snapshot_service.md)
- [结构化输出管理器文档](./structured_output_manager.md)
- [提示词管理器文档](./prompt_manager.md)

## 示例代码

完整的示例代码请参考：
- `examples/llm_analyzer_example.py`
- `tests/test_llm_analyzer.py`
