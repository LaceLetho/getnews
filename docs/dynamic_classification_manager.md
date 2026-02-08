# 动态分类管理器 (DynamicClassificationManager)

## 概述

`DynamicClassificationManager` 是一个运行时分类管理组件，负责根据大模型返回的分析结果自动发现和管理分类。它支持动态分类变更、一致性验证和统计功能，不在代码中硬编码具体类别。

## 核心功能

### 1. 自动分类发现
- 从大模型响应中自动提取分类
- 支持运行时动态添加新分类
- 自动去重和标准化分类名称

### 2. 分类注册表管理
- 维护当前会话的分类集合
- 追踪分类的添加和移除
- 记录分类变更历史

### 3. 一致性验证
- 使用Jaccard相似度验证分类一致性
- 可配置的一致性阈值
- 检测分类标准的重大变化

### 4. 统计功能
- 统计每个分类的出现次数
- 提供分类分布信息
- 支持统计数据的重置和导出

### 5. 状态持久化
- 导出管理器状态
- 导入已保存的状态
- 支持状态恢复和迁移

## 设计原则

### 动态性
系统不在代码中硬编码具体的分类类别，完全依赖大模型返回的分类结果。这使得系统能够：
- 适应不同的分析场景
- 支持提示词的灵活调整
- 无需修改代码即可改变分类标准

### 一致性
通过Jaccard相似度算法验证分类的一致性：
```
相似度 = |A ∩ B| / |A ∪ B|
```
其中A是旧分类集合，B是新分类集合。

### 可追溯性
记录所有分类变更历史，包括：
- 变更时间戳
- 新增的分类
- 移除的分类
- 分类数量变化

## 使用示例

### 基本使用

```python
from crypto_news_analyzer.analyzers import DynamicClassificationManager
from crypto_news_analyzer.analyzers.structured_output_manager import StructuredAnalysisResult

# 初始化管理器
manager = DynamicClassificationManager()

# 处理分析结果
results = [
    StructuredAnalysisResult(
        time="2024-01-01 10:00",
        category="Whale",
        weight_score=80,
        summary="大户转移资金",
        source="https://example.com/1"
    ),
    StructuredAnalysisResult(
        time="2024-01-01 11:00",
        category="Fed",
        weight_score=90,
        summary="美联储政策变化",
        source="https://example.com/2"
    )
]

# 一站式处理
result = manager.process_analysis_results(results)

print(f"发现分类: {result['categories']}")
print(f"分类数量: {result['category_count']}")
print(f"一致性: {result['is_consistent']}")
print(f"统计: {result['statistics']}")
```

### 手动步骤处理

```python
# 1. 提取分类
categories = manager.extract_categories_from_response(results)
print(f"提取到的分类: {categories}")

# 2. 验证一致性
is_consistent = manager.validate_category_consistency(categories)
print(f"一致性: {is_consistent}")

# 3. 更新注册表
manager.update_category_registry(categories)

# 4. 更新统计
manager.update_statistics(results)

# 5. 获取当前分类
current_categories = manager.get_current_categories()
print(f"当前分类: {current_categories}")

# 6. 获取统计信息
stats = manager.get_category_statistics()
print(f"统计: {stats}")
```

### 配置一致性阈值

```python
# 设置更宽松的一致性阈值（默认0.8）
manager.set_consistency_threshold(0.6)

# 现在相似度 >= 0.6 就认为一致
```

### 处理分类变更

```python
# 检测到分类变更时
old_categories = {"Whale", "Fed"}
new_categories = {"Whale", "Regulation", "Security"}

manager.handle_category_changes(old_categories, new_categories)

# 查看变更历史
history = manager.get_category_history()
for event in history:
    if event.get("type") == "category_change":
        print(f"时间: {event['timestamp']}")
        print(f"新增: {event['added']}")
        print(f"移除: {event['removed']}")
```

### 状态持久化

```python
# 导出状态
state = manager.export_state()

# 保存到文件
import json
with open("classification_state.json", "w") as f:
    json.dump(state, f, ensure_ascii=False, indent=2)

# 从文件恢复
with open("classification_state.json", "r") as f:
    state = json.load(f)

new_manager = DynamicClassificationManager()
new_manager.import_state(state)
```

### 获取状态摘要

```python
summary = manager.get_summary()

print(f"当前分类: {summary['current_categories']}")
print(f"分类数量: {summary['category_count']}")
print(f"已处理项目: {summary['total_items_processed']}")
print(f"统计: {summary['statistics']}")
print(f"历史记录数: {summary['history_count']}")
print(f"一致性阈值: {summary['consistency_threshold']}")
```

### 重置数据

```python
# 只重置统计信息
manager.reset_statistics()

# 完全重置（包括分类注册表和历史）
manager.reset_all()
```

## API 参考

### 核心方法

#### `extract_categories_from_response(response_data: List[StructuredAnalysisResult]) -> Set[str]`
从大模型响应中提取分类。

**参数:**
- `response_data`: 结构化分析结果列表

**返回:**
- 分类名称集合

**验证需求:** 5.8

#### `update_category_registry(new_categories: Set[str]) -> None`
更新分类注册表。

**参数:**
- `new_categories`: 新发现的分类集合

**验证需求:** 5.9

#### `get_current_categories() -> List[str]`
获取当前分类列表（排序后）。

**返回:**
- 当前分类名称列表

**验证需求:** 5.9

#### `validate_category_consistency(categories: Set[str], previous_categories: Optional[Set[str]] = None) -> bool`
验证分类一致性。

**参数:**
- `categories`: 当前分类集合
- `previous_categories`: 之前的分类集合（可选）

**返回:**
- 是否一致

**验证需求:** 5.10

#### `handle_category_changes(old_categories: Set[str], new_categories: Set[str]) -> None`
处理分类变更。

**参数:**
- `old_categories`: 旧分类集合
- `new_categories`: 新分类集合

**验证需求:** 5.10

#### `get_category_statistics() -> Dict[str, int]`
获取分类统计信息。

**返回:**
- 分类统计字典

**验证需求:** 5.9

#### `update_statistics(results: List[StructuredAnalysisResult]) -> None`
更新分类统计信息。

**参数:**
- `results`: 分析结果列表

#### `process_analysis_results(results: List[StructuredAnalysisResult], validate_consistency: bool = True) -> Dict[str, Any]`
处理分析结果（一站式方法）。

**参数:**
- `results`: 分析结果列表
- `validate_consistency`: 是否验证一致性

**返回:**
- 处理结果字典，包含：
  - `categories`: 分类列表
  - `category_count`: 分类数量
  - `is_consistent`: 一致性状态
  - `statistics`: 统计信息

### 辅助方法

#### `get_category_history() -> List[Dict[str, Any]]`
获取分类变更历史。

#### `reset_statistics() -> None`
重置统计信息。

#### `reset_all() -> None`
重置所有数据。

#### `set_consistency_threshold(threshold: float) -> None`
设置一致性阈值（0.0-1.0）。

#### `get_summary() -> Dict[str, Any]`
获取管理器状态摘要。

#### `export_state() -> Dict[str, Any]`
导出管理器状态。

#### `import_state(state: Dict[str, Any]) -> None`
导入管理器状态。

## 集成示例

### 与LLM分析器集成

```python
from crypto_news_analyzer.analyzers import LLMAnalyzer, DynamicClassificationManager

# 初始化组件
llm_analyzer = LLMAnalyzer(mock_mode=True)
classification_manager = DynamicClassificationManager()

# 分析内容
content_items = [...]  # ContentItem列表
results = llm_analyzer.analyze_content_batch(content_items)

# 处理分类
classification_result = classification_manager.process_analysis_results(results)

# 使用分类结果
for category in classification_result['categories']:
    items_in_category = [
        r for r in results if r.category == category
    ]
    print(f"{category}: {len(items_in_category)} 条")
```

### 多批次处理

```python
manager = DynamicClassificationManager()

# 处理多个批次
for batch in batches:
    results = llm_analyzer.analyze_content_batch(batch)
    
    # 处理并验证一致性
    result = manager.process_analysis_results(
        results,
        validate_consistency=True
    )
    
    if not result['is_consistent']:
        print(f"警告: 批次 {batch_id} 的分类不一致")
        print(f"当前分类: {result['categories']}")
    
    # 累积统计
    print(f"累计统计: {manager.get_category_statistics()}")
```

## 一致性验证详解

### Jaccard相似度

Jaccard相似度用于衡量两个集合的相似程度：

```
J(A, B) = |A ∩ B| / |A ∪ B|
```

**示例:**
- A = {Whale, Fed, Regulation}
- B = {Whale, Fed, Security}
- 交集 = {Whale, Fed} (2个元素)
- 并集 = {Whale, Fed, Regulation, Security} (4个元素)
- 相似度 = 2/4 = 0.5

### 阈值设置建议

- **0.9-1.0**: 非常严格，几乎要求完全相同
- **0.8**: 默认值，允许少量变化
- **0.6-0.7**: 宽松，允许较大变化
- **0.5以下**: 非常宽松，可能失去一致性保证

### 一致性检查时机

1. **首次运行**: 跳过检查（没有历史数据）
2. **后续批次**: 与上一批次比较
3. **跨会话**: 可以导入历史状态进行比较

## 最佳实践

### 1. 合理设置阈值
根据业务需求调整一致性阈值：
- 稳定的分析场景：使用较高阈值（0.8-0.9）
- 探索性分析：使用较低阈值（0.6-0.7）

### 2. 监控分类变更
定期检查分类变更历史，识别异常：
```python
history = manager.get_category_history()
recent_changes = [h for h in history if h.get("type") == "category_change"]

if len(recent_changes) > threshold:
    print("警告: 分类变更频繁，可能需要检查提示词")
```

### 3. 持久化状态
在长期运行的系统中，定期保存状态：
```python
# 每小时保存一次
state = manager.export_state()
save_to_database(state)
```

### 4. 分析统计趋势
使用统计信息了解内容分布：
```python
stats = manager.get_category_statistics()
total = sum(stats.values())

for category, count in sorted(stats.items(), key=lambda x: x[1], reverse=True):
    percentage = (count / total) * 100
    print(f"{category}: {count} ({percentage:.1f}%)")
```

### 5. 处理空分类
大模型可能过滤掉所有内容：
```python
result = manager.process_analysis_results(results)

if result['category_count'] == 0:
    print("警告: 所有内容被过滤，可能需要调整过滤规则")
```

## 性能考虑

### 内存使用
- 分类集合: O(n) 其中n是分类数量
- 统计信息: O(n)
- 历史记录: O(m) 其中m是变更次数

### 时间复杂度
- 提取分类: O(k) 其中k是结果数量
- 一致性验证: O(n) 其中n是分类数量
- 更新统计: O(k)

### 优化建议
1. 定期清理历史记录（保留最近N条）
2. 对于大量数据，考虑批量处理
3. 使用缓存避免重复计算

## 故障排除

### 问题: 一致性总是False
**原因:** 阈值设置过高或分类变化确实很大
**解决:** 降低阈值或检查提示词配置

### 问题: 统计数据不准确
**原因:** 忘记调用update_statistics
**解决:** 使用process_analysis_results一站式方法

### 问题: 内存占用过高
**原因:** 历史记录过多
**解决:** 定期调用reset_statistics或reset_all

## 相关组件

- **LLMAnalyzer**: 生成分析结果
- **StructuredOutputManager**: 确保结构化输出
- **PromptManager**: 管理提示词配置
- **DynamicCategoryManager**: 管理分类配置文件

## 需求验证

本组件验证以下需求：

- **需求 5.8**: 支持动态分类，不在代码中硬编码具体类别
- **需求 5.9**: 根据返回数据中的类别数量动态展示分类
- **需求 5.10**: 支持分类标准的灵活变动，通过修改提示词实现分类调整

## 测试覆盖

完整的测试套件位于 `tests/test_dynamic_classification_manager.py`，包括：

- 初始化测试
- 分类提取测试
- 注册表管理测试
- 一致性验证测试
- 统计功能测试
- 状态持久化测试
- 多批次处理测试
- 边界条件测试

测试覆盖率: 99%
