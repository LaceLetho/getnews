# 情报主题生命周期指南

## 概念

情报主题（Intelligence Topic）是一个 **AI 驱动的持续研究管线**。每个主题维护一条由 LLM 生成的提示词（prompt），系统定期用该提示词分析近期采集的原始消息，产出结构化的研究发现（findings），最终通过合并操作整合为综合报告。

### 核心数据模型

| 实体 | 说明 | 关键状态 |
|---|---|---|
| **Topic**（主题） | 研究主题本身，如"Bitcoin ETF 资金流" | `draft` → `active` → `paused` / `archived` |
| **Prompt**（提示词） | 指导 LLM 如何研究的指令，支持版本管理 | `draft` → `active` → `archived` |
| **Finding**（发现） | 每次研究产出的结构化结果 | `active` / `archived` / `superseded` |
| **Merge Preview**（合并预览） | 合并前的人工审核快照，24 小时有效 | `pending` → `applied` / `expired` / `cancelled` |

**Topic 与 Prompt 的状态是独立的**：Topic 有 `lifecycle_status`（draft/active/paused/archived），Prompt 有 `status`（draft/active/archived）。研究调度器只对 **Topic `lifecycle_status=active` 且 Prompt `status=active`** 的主题执行研究。

---

## 完整生命周期

```
  创建 ──────────── 修订 ────── 确认 ────── 研究（自动）── 合并
  │                  │            │              │            │
  ▼                  ▼            ▼              ▼            ▼
/topic_create   /topic_revise  /topic_confirm  [scheduler]  /topic_merge
  │              /topic_set_prompt
  │
  ├── 暂停 ── /topic_pause （停止研究，可恢复）
  │
  └── 归档 ── /topic_archive （永久停用，不可逆）
```

---

## 命令详解

### 1. `/topic_create <主题描述>`

创建新的研究主题，AI 自动生成第一条 draft 提示词。

```
用法: /topic_create <主题描述>
示例: /topic_create Bitcoin ETF flow analysis
      /topic_create 监控大户的链上转账行为
```

**发生了什么：**
- 在 `intelligence_topics` 表创建 topic，`lifecycle_status = draft`
- LLM 根据主题描述生成一条 research prompt，存入 `topic_prompts`（`status = draft`）
- 返回 topic ID 和生成的提示词文本

**返回示例：**
```
📝 主题草稿已创建
主题: Bitcoin ETF flow analysis
Topic ID: abc123-def456
生成的提示词: [前 500 字符的提示词]

下一步：
• /topic_revise abc123-def456 <反馈> 让AI修订
• /topic_set_prompt abc123-def456 <完整提示词> 手动替换
• /topic_confirm abc123-def456 确认激活
```

---

### 2. `/topic_revise <topic_id> <反馈>`

让 AI 根据你的反馈修订提示词。

```
用法: /topic_revise <topic_id> <反馈>
示例: /topic_revise abc123 增加对 DeFi 协议的关注
      /topic_revise abc123 请使用中文输出结果
```

**发生了什么：**
- LLM 读取最新一条 prompt，结合你的反馈生成修订版本
- 新 prompt 以 `status = draft` 存入，版本号自增（如 v1 → v2）
- 旧 prompt 保持不变（不会自动归档）

---

### 3. `/topic_set_prompt <topic_id> <完整提示词>`

手动替换提示词文本，绕过 AI 生成。

```
用法: /topic_set_prompt <topic_id> <完整提示词>
示例: /topic_set_prompt abc123 你是一个加密货币分析师。请分析以下消息...
```

**发生了什么：**
- 创建新的 draft prompt 版本，`prompt_text` 设为你提供的文本
- 版本号自增
- 审核历史记录 "Manual replacement" 标记

---

### 4. `/topic_confirm <topic_id>` ⭐ 关键步骤

确认并激活最新的 draft 提示词。

```
用法: /topic_confirm <topic_id>
示例: /topic_confirm abc123-def456
```

**发生了什么：**
- 找到该 topic 下最新 `status = draft` 的 prompt
- 将其 `status` 改为 `active`，记录 `activated_at` 和 `activated_by`
- 如果之前有 active prompt，将其 `status` 改为 `archived`
- **注意：此命令只改变 prompt 的 status，不会自动改变 topic 的 lifecycle_status**

> ⚠️ **常见错误**：`/topic_merge` 会报"未找到活跃提示词"，就是因为从未执行过 `/topic_confirm`，topic 下没有 `status=active` 的 prompt。

---

### 5. 自动研究（后台调度）

研究由 `ingestion` 服务的 scheduler 自动触发，无需手动操作。

**触发条件（两个条件必须同时满足）：**
- Topic 的 `lifecycle_status = active`
- 该 topic 存在 `status = active` 的 prompt

**研究过程：**
1. 获取自上次 checkpoint 以来采集的原始消息
2. 将消息分块，用 active prompt 调用 LLM 分析
3. LLM 返回结构化的 findings（JSON）
4. Findings 存入 `topic_findings` 表，`status = active`

---

### 6. `/topic_merge <topic_id>`

将分散的研究发现（findings）合并为综合报告。**必须先有 active prompt 和至少一条 finding。**

```
用法: /topic_merge <topic_id>
示例: /topic_merge abc123-def456
```

**发生了什么：**
1. 检查该 topic 是否有 `status=active` 的 prompt（没有则报错"未找到活跃提示词"）
2. 调用 merge service，收集所有 active findings，由 LLM 合并
3. 生成 **Merge Preview**（24 小时有效），显示合并摘要
4. 返回交互按钮：**「接受合并」** 或过期自动取消

**合并预览示例：**
```
🔄 合并预览
主题: Bitcoin ETF
合并发现数: 12
摘要: [合并后的综合摘要，最多 300 字符]

Preview ID: preview-xxx-yyy
过期时间: 2026-05-18 15:30 UTC

[ 接受合并 ]
```

点击「接受合并」后：
- 所有源 findings 的 status 改为 `archived`
- 生成一条新的合并后 finding（`status=active`）
- Merge preview 的 state 改为 `applied`

---

### 7. `/topic_pause <topic_id>`

暂停主题研究。已产出的 findings 保留，但不再自动研究。

```
用法: /topic_pause <topic_id>
```

**发生了什么：**
- Topic 的 `lifecycle_status` 改为 `paused`
- `is_active` 改为 `false`
- 研究调度器将跳过此 topic

> 暂停后可以通过重新 `/topic_confirm` 恢复（如果仍有 active prompt）。

---

### 8. `/topic_archive <topic_id>`

永久归档主题。所有数据保留，但不再可激活。

```
用法: /topic_archive <topic_id>
```

**发生了什么：**
- Topic 的 `lifecycle_status` 改为 `archived`
- 不可逆操作（除非直接修改数据库）

---

## 查询命令

### `/topic_list`

列出所有主题，支持分页。

```
用法: /topic_list
```

返回主题列表，包含 topic ID、名称、状态、最新 findings 摘要等。

### `/topic_detail <topic_id>`

查看单个主题的完整详情。

```
用法: /topic_detail <topic_id>
```

返回：主题信息、所有 prompt 版本历史、所有 active findings、研究运行日志摘要。

### `/topic_logs <topic_id>`

查看该主题的研究运行记录。

```
用法: /topic_logs <topic_id>
```

返回最近的研究运行时间、状态（成功/失败）、产出的 finding 数量等。

---

## 典型操作流程

### 场景：创建一个新的研究主题

```
1. /topic_create 监控稳定币 USDT 的增发与销毁
   → 获得 topic_id: xxxxx

2. 【审查 AI 生成的提示词】
   → /topic_detail xxxxx  查看完整提示词
   → 如果不满意: /topic_revise xxxxx 增加对 Tron 链的关注

3. /topic_confirm xxxxx
   → 激活！研究自动开始

4. 【等待 1-N 个采集周期后】
   → /topic_detail xxxxx  查看有多少 findings

5. /topic_merge xxxxx
   → 生成合并预览
   → 点击「接受合并」

6. 【研究饱和后】
   → /topic_pause xxxxx  暂停
   → 或 /topic_archive xxxxx  归档
```

---

## 常见问题

### Q: 为什么 `/topic_merge` 报错"未找到活跃提示词"？

**A:** 你创建了 topic 但从未执行 `/topic_confirm` 激活提示词。路线：`/topic_create` → `/topic_confirm` → 等待研究 → `/topic_merge`。

### Q: Topic 和 Prompt 的状态有什么区别？

**A:** `topic.lifecycle_status` 控制主题是否参与研究调度；`prompt.status` 控制用哪条提示词来研究。两者都是 `active` 时研究才会执行。

### Q: 合并预览过期了怎么办？

**A:** 重新执行 `/topic_merge <topic_id>` 即可生成新的预览。

### Q: 可以修改已激活的提示词吗？

**A:** 可以。使用 `/topic_set_prompt` 会创建新 draft，然后用 `/topic_confirm` 激活新版本。旧 active prompt 会自动归档。

### Q: `/topic_pause` 和 `/topic_archive` 的区别？

**A:** `pause` 是临时暂停（可恢复），`archive` 是永久归档（不可逆）。
