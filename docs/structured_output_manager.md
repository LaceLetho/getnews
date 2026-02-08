# 结构化输出管理器 (StructuredOutputManager)

## 概述

StructuredOutputManager 是一个用于强制大模型返回标准JSON格式的工具类，确保输出格式的一致性和可解析性。它集成了 instructor 等结构化输出库，提供了输出格式验证和错误恢复机制。

## 核心功能

### 1. 强制结构化输出

使用 Pydantic 模型定义标准输出格式，强制大模型返回符合规范的 JSON 数据：

```python
from crypto_news_analyzer.analyzers.structured_output_manager import (
    StructuredOutputManager,
    StructuredAnalysisResult
)

manager = StructuredOutputManager(library="instructor")
```

### 2. 标准输出格式

所有分析结果必须包含以下字段：

- **time**: 发布时间（字符串）
- **category**: 动态分类类别（字符串）
- **weight_score**: 重要性评分（0-100整数）
- **summary**: 内容摘要（非空字符串）
- **source**: 原文链接URL（有效的HTTP/HTTPS URL）

### 3. 输出格式验证

自动验证输出结构的完整性和正确性：

```python
response = {
    "time": "2024-01-01 12:00",
    "category": "大户动向",
    "weight_score": 85,
    "summary": "某巨鲸地址转移10000 ETH到交易所",
    "source": "https://example.com/news/123"
}

result = manager.validate_output_structure(response)
if result.is_valid:
    print("验证通过")
else:
    print(f"验证失败: {result.errors}")
```

### 4. 错误恢复机制

当大模型返回格式错误的响应时，自动尝试恢复：

- 从 markdown 代码块中提取 JSON
- 处理格式错误的 JSON 字符串
- 提供友好的错误信息

```python
malformed_response = """
```json
{
    "time": "2024-01-01 12:00",
    "category": "大户动向",
    "weight_score": 85,
    "summary": "测试",
    "source": "https://example.com"
}
```
"""

result = manager.handle_malformed_response(malformed_response)
```

### 5. 批量处理支持

支持单个结果和批量结果两种模式：

```python
# 单个结果
result = manager.force_structured_response(
    llm_client=client,
    messages=messages,
    batch_mode=False
)

# 批量结果
batch_result = manager.force_structured_response(
    llm_client=client,
    messages=messages,
    batch_mode=True
)
```

## 支持的库

### 1. Instructor（推荐）

使用 instructor 库强制结构化输出，支持自动重试和验证：

```python
manager = StructuredOutputManager(library="instructor")
instructor_client = manager.setup_instructor_client(openai_client)

result = manager.force_structured_response(
    llm_client=instructor_client,
    messages=messages,
    model="gpt-4",
    max_retries=3,
    temperature=0.1
)
```

### 2. Native JSON

使用原生 JSON 模式（OpenAI JSON mode）：

```python
manager = StructuredOutputManager(library="native_json")

result = manager.force_structured_response(
    llm_client=openai_client,
    messages=messages,
    model="gpt-4"
)
```

## 数据模型

### StructuredAnalysisResult

单个分析结果的数据模型：

```python
from pydantic import BaseModel, Field

class StructuredAnalysisResult(BaseModel):
    time: str = Field(..., description="发布时间")
    category: str = Field(..., description="分类类别")
    weight_score: int = Field(..., ge=0, le=100, description="重要性评分")
    summary: str = Field(..., min_length=1, description="内容摘要")
    source: str = Field(..., description="原文链接URL")
```

### BatchAnalysisResult

批量分析结果的容器：

```python
class BatchAnalysisResult(BaseModel):
    results: List[StructuredAnalysisResult] = Field(
        default_factory=list,
        description="分析结果列表，可以为空列表"
    )
```

### ValidationResult

验证结果数据类：

```python
@dataclass
class ValidationResult:
    is_valid: bool
    errors: List[str]
    warnings: List[str]
```

## 使用示例

### 完整工作流程

```python
import os
from openai import OpenAI
from crypto_news_analyzer.analyzers.structured_output_manager import (
    StructuredOutputManager
)

# 1. 初始化管理器
manager = StructuredOutputManager(library="instructor")

# 2. 创建并配置 LLM 客户端
client = OpenAI(api_key=os.getenv("LLM_API_KEY"))
instructor_client = manager.setup_instructor_client(client)

# 3. 准备消息
messages = [
    {
        "role": "system",
        "content": "你是一个加密货币新闻分析专家。"
    },
    {
        "role": "user",
        "content": "分析这条新闻并返回结构化结果..."
    }
]

# 4. 强制结构化输出
result = manager.force_structured_response(
    llm_client=instructor_client,
    messages=messages,
    model="gpt-4",
    max_retries=3,
    temperature=0.1,
    batch_mode=False
)

# 5. 使用结果
print(f"分类: {result.category}")
print(f"评分: {result.weight_score}")
print(f"摘要: {result.summary}")
```

## 验证规则

### 字段验证

1. **time**: 不能为空字符串
2. **category**: 不能为空字符串
3. **weight_score**: 必须是 0-100 之间的整数
4. **summary**: 不能为空字符串，最小长度为 1
5. **source**: 必须是有效的 URL（以 http:// 或 https:// 开头）

### 批量结果验证

- 空列表 `[]` 是有效的（表示所有内容被过滤）
- 每个结果项必须符合单个结果的验证规则
- 验证失败时会提供详细的错误信息

## 错误处理

### 常见错误

1. **ValidationError**: Pydantic 验证失败
   - 检查字段类型和值范围
   - 确保所有必需字段都存在

2. **JSONDecodeError**: JSON 解析失败
   - 自动尝试从 markdown 代码块提取
   - 提供格式错误的详细信息

3. **ImportError**: instructor 库未安装
   - 运行 `pip3 install instructor`

### 错误恢复策略

1. 尝试从 markdown 代码块提取 JSON
2. 尝试直接解析 JSON
3. 如果无法恢复，返回 None 或抛出异常

## 最佳实践

### 1. 使用 Instructor 库

推荐使用 instructor 库，它提供：
- 自动重试机制
- 更好的错误处理
- 类型安全的输出

### 2. 设置合理的重试次数

```python
result = manager.force_structured_response(
    llm_client=client,
    messages=messages,
    max_retries=3,  # 推荐 2-3 次
    temperature=0.1  # 低温度提高一致性
)
```

### 3. 验证输出

始终验证输出结构：

```python
validation_result = manager.validate_output_structure(response_dict)
if not validation_result.is_valid:
    logger.error(f"验证失败: {validation_result.errors}")
```

### 4. 处理空批量结果

空列表是有效的返回值：

```python
if len(batch_result.results) == 0:
    logger.warning("所有内容被过滤")
else:
    process_results(batch_result.results)
```

## 性能考虑

### 1. 批量处理

批量处理比多次单个调用更高效：

```python
# 推荐：批量处理
batch_result = manager.force_structured_response(
    llm_client=client,
    messages=messages,
    batch_mode=True
)

# 不推荐：多次单个调用
for item in items:
    result = manager.force_structured_response(...)
```

### 2. 温度参数

使用较低的温度值（0.0-0.2）提高输出一致性：

```python
result = manager.force_structured_response(
    llm_client=client,
    messages=messages,
    temperature=0.1  # 低温度
)
```

### 3. 重试策略

合理设置重试次数，避免过多的 API 调用：

```python
result = manager.force_structured_response(
    llm_client=client,
    messages=messages,
    max_retries=2  # 平衡可靠性和成本
)
```

## 测试

运行单元测试：

```bash
python3 -m pytest tests/test_structured_output_manager.py -v
```

运行示例：

```bash
PYTHONPATH=. python3 examples/structured_output_example.py
```

## 相关文档

- [Instructor 库文档](https://python.useinstructor.com/)
- [Pydantic 文档](https://docs.pydantic.dev/)
- [OpenAI JSON Mode](https://platform.openai.com/docs/guides/structured-outputs)

## 需求映射

该实现满足以下需求：

- **需求 5.5**: 使用结构化输出工具强制大模型返回结构化数据
- **需求 5.13**: 返回包含 time、category、weight_score、summary、source 字段的结构化结果
- **需求 5.15**: 验证分析结果的 JSON 格式正确性，确保所有必需字段都存在
