# 精简 Topic 状态模型 — 实施方案

## 背景

当前 `IntelligenceTopic` 有两个问题：

**问题 1：`is_active` 冗余。** `is_active` (bool) 完全由 `lifecycle_status` (enum) 推导，是冗余字段：
- `lifecycle_status = active` → `is_active = True`
- `lifecycle_status ∈ {draft, paused, archived}` → `is_active = False`

另外，4 个代码路径在修改 `lifecycle_status` 时未同步 `is_active`，导致 DB 中出现不一致状态。

**问题 2：`paused` 和 `archived` 行为完全一样。** 两者都把 topic 从研究循环中排除，没有任何代码对它们做区分处理。语义上 `paused`（暂停）和 `archived`（归档）可以作为同一个终态。

## 方案：两步精简

| Step | 动作 | 结果 |
|---|---|---|
| A | 删除 `is_active` | 只保留 `lifecycle_status` 作为唯一状态源 |
| B | 合并 `paused` → `archived` | 三个非活跃状态缩减为两个：`draft` / `active` / `archived` |
| C | `/pause` API 保留兼容，内部设 `archived` | 不破坏外部接口 |

## 影响范围

| 文件 | 改动类型 | 说明 |
|---|---|---|
| `domain/models.py` | 模型 | 删除 `is_active` 字段 + 删除 `PAUSED` 枚举值 |
| `domain/repositories.py` | 接口 | `list_topics` / `count_topics` 参数改为 `lifecycle_status` |
| `storage/intelligence_schema.py` | 迁移 | DROP COLUMN `is_active` + DROP INDEX；UPDATE 所有 `paused` → `archived` |
| `storage/data_manager.py` | SQL | `upsert_intelligence_topic` 去掉 `is_active`；过滤改为 `lifecycle_status` |
| `storage/repositories.py` | 仓储实现 | 参数透传改动 |
| `intelligence/topic_research.py` | 研究调度 | `is_active=True` → `lifecycle_status='active'` |
| `api_server.py` | API | `pause` 端点改为设 `archived`；响应动态计算 `is_active` |
| `reporters/telegram/intelligence_commands.py` | Telegram | `/topic_pause` 改为设 `archived`；命令保留 |
| `reporters/telegram_command_handler.py` | 命令注册 | 无需改动（`/topic_pause` 命令名保留） |
| `intelligence/__init__.py` | 文档注释 | 更新状态描述 |
| 测试文件 | 测试更新 | 更新 `paused` 断言为 `archived`

## 实施步骤

### Step 1: 模型层 (`domain/models.py`)

**1a. 删除 `PAUSED` 枚举值：**

```python
class TopicLifecycleStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"
    # PAUSED = "paused"  ← 删除
```

**1b. 删除 `is_active` 字段：**

```python
# 删除
is_active: bool = True
```

**1c. 简化 `__post_init__`：**

删除 `is_active` 同步逻辑，只保留 `lifecycle_status` 校验。

**1d. 更新 `from_dict`：**

从 `allowed` 集合中移除 `"is_active"`。`paused` 的兜底逻辑不需要了（因为枚举值已删除）。

### Step 2: 仓储接口 (`domain/repositories.py`)

`list_topics` / `count_topics` 参数从 `is_active: Optional[bool]` 改为 `lifecycle_status: Optional[str]`。

### Step 3: 数据管理 (`storage/data_manager.py`)

**3a.** `upsert_intelligence_topic` — 从 columns 列表中移除 `"is_active"`。

**3b.** `list_intelligence_topics` 和 `count_intelligence_topics` — `is_active` 过滤改为 `lifecycle_status`，签名同步更新。

### Step 4: 仓储实现 (`storage/repositories.py`)

参数名同步更新，透传调用。

### Step 5: 调用方更新

| 位置 | 改前 | 改后 |
|---|---|---|
| `topic_research.py:262` | `repository.list_topics(is_active=True)` | `repository.list_topics(lifecycle_status='active')` |
| `api_server.py:2049` | `is_active=True if active_only else None` | `lifecycle_status='active' if active_only else None` |
| `api_server.py:2053` | `is_active=True if active_only else None` | 同上 |
| `intelligence_commands.py:1124` | `is_active=True` | `lifecycle_status='active'` |
| `intelligence_commands.py:1125` | `is_active=True` | `lifecycle_status='active'` |

### Step 6: pause → archive 内容统一

| 位置 | 改前 | 改后 |
|---|---|---|
| `api_server.py:1915` | `TopicLifecycleStatus.PAUSED.value` | `TopicLifecycleStatus.ARCHIVED.value` |
| `intelligence_commands.py:616` | `"paused"` | `"archived"` |
| `topic_research.py:257` | `Draft, paused, and archived` | `Draft and archived` |
| `intelligence/__init__.py:8` | 删除 `/topic_pause` 相关描述（改为 archive） |

`/topic_pause` 端点和 Telegram 命令保留不删，内部逻辑改为设 `archived`，对外兼容。

### Step 7: API 响应兼容 (`api_server.py`)

```python
# 改前
"is_active": bool(getattr(topic, "is_active", True)),

# 改后
"is_active": getattr(topic, "lifecycle_status", "active") == "active",
```

涉及 `api_server.py:491` 和 `:582`。

### Step 8: 数据库迁移 (`storage/intelligence_schema.py`)

```sql
-- 1. 将有 paused 状态的 topic 统一为 archived
UPDATE intelligence_topics SET lifecycle_status = 'archived' WHERE lifecycle_status = 'paused';

-- 2. 删除旧索引
DROP INDEX IF EXISTS idx_intelligence_topics_active;

-- 3. 删除冗余列
ALTER TABLE intelligence_topics DROP COLUMN IF EXISTS is_active;
```

### Step 9: 测试更新

| 文件 | 改动 |
|---|---|
| `test_topic_findings_api.py` | `"paused"` → `"archived"` |
| `test_topic_findings_telegram.py` | `"paused"` → `"archived"` |
| `test_intelligence_models.py` | 删除 `is_active` 断言；`PAUSED` → `ARCHIVED` |
| `test_topic_research_scheduler.py` | `PAUSED` → `ARCHIVED`；合并 `paused` 和 `archived` 测试用例 |

## 附带修复

- **`is_active` 不一致 bug**：不再需要维护两个字段的同步
- **`paused` 和 `archived` 的混淆**：合并后状态语义清晰，只有 `draft` → `active` → `archived` 一条线

## 向后兼容

- `POST /intelligence/topics/{id}/pause` 端点保留，内部行为等同于 archive
- `/topic_pause` Telegram 命令保留，行为等同于 `/topic_archive`
- API 响应中的 `is_active` 字段保留，改为动态计算

## 部署

Railway 单次部署：

1. 代码变更
2. `docker-entrypoint.sh migrate-postgres` 执行迁移（UPDATE `paused` → `archived` + DROP COLUMN + DROP INDEX）
3. 新代码运行时状态模型已精简

## 不回退项

以下模式经评估**不删除**：

- `archived_at` + `status='archived'`（TopicPrompt / TopicFinding）— 时间戳有独立查询价值
- `applied_at` + `state='applied'`（MergePreview）— 同上
- `found_at` + `status`（TopicFinding）— 不是冗余，是附加元数据
