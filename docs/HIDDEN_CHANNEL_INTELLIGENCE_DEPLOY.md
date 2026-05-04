# Hidden Channel Intelligence — 部署指南

> 对应 plan：`.sisyphus/plans/hidden-channel-intelligence.md`
> 实现 review：`docs/HIDDEN_CHANNEL_INTELLIGENCE_REVIEW.md`
> 依赖基础部署：`docs/RAILWAY_DEPLOYMENT.md`

本指南覆盖从本地验证到 Railway 生产的完整上线流程。不新增第三个服务，仍沿用现有 split-service 拓扑。

---

## 0. 上线前 Preflight（部署前必须通过）

### 0.1 本地测试（无需 Postgres）

```bash
# intelligence 核心测试
uv run pytest tests/test_intelligence_models.py tests/test_intelligence_merge.py tests/test_intelligence_ttl.py -v
uv run pytest tests/test_intelligence_telegram_collector.py tests/test_intelligence_v2ex_collector.py -v
uv run pytest tests/test_intelligence_extraction.py tests/test_intelligence_api.py tests/test_intelligence_telegram_commands.py -v
uv run pytest tests/test_intelligence_config.py tests/test_intelligence_datasource_payloads.py -v
uv run pytest tests/test_intelligence_security_guardrails.py -v
uv run pytest tests/test_intelligence_repositories.py -v
uv run pytest tests/test_intelligence_semantic_search.py -v
uv run pytest tests/test_intelligence_ingestion_runtime.py tests/test_intelligence_ttl.py -v
```

### 0.2 完整回归

```bash
uv run pytest tests/ -v
uv run mypy crypto_news_analyzer/
uv run flake8 crypto_news_analyzer/
```

### 0.3 Real Postgres/pgvector 集成测试（需要测试库）

```bash
TEST_DATABASE_URL=postgresql://... uv run pytest tests/integration/test_intelligence_schema.py -v
TEST_DATABASE_URL=postgresql://... uv run pytest tests/integration/test_intelligence_pgvector.py -v
```

> 如果 0.1 / 0.2 / 0.3 有失败，不要推进到部署步骤。先修复，再重新跑 preflight。

---

## 1. Railway 环境变量配置

Railway 变量写入后在每个服务的 Variables 页面 **Review & Deploy** 才会生效。

### 1.1 两个服务都需要

| 变量 | 说明 |
|------|------|
| `DATABASE_URL` | 同一个共享 PostgreSQL/pgvector 连接串 |
| `CONFIG_PATH` | `./config.jsonc` |
| `LOG_LEVEL` | `INFO` |

### 1.2 `crypto-news-analysis` 需要

| 变量 | 说明 |
|------|------|
| `API_KEY` | Bearer 鉴权密钥 |
| `API_HOST` / `API_PORT` | `0.0.0.0` / `8080` |
| `KIMI_API_KEY` | Kimi LLM 凭证 |
| `GROK_API_KEY` | Grok LLM 凭证 |
| `OPENCODE_API_KEY` | opencode-go 提取凭证 |
| `OPENAI_API_KEY` | embedding / semantic search 凭证（text-embedding-3-small） |
| `TELEGRAM_BOT_TOKEN` | Telegram Bot token |
| `TELEGRAM_CHANNEL_ID` | 公告频道 ID |
| `TELEGRAM_AUTHORIZED_USERS` | 授权用户，逗号分隔（如 `123456,@user1`） |
| `TELEGRAM_TRANSPORT_MODE` | `webhook` |
| `TELEGRAM_WEBHOOK_BASE_URL` | `https://news.tradao.xyz` |
| `TELEGRAM_WEBHOOK_PATH` | `/telegram/webhook` |
| `TELEGRAM_WEBHOOK_SECRET_TOKEN` | 随机 secret |

### 1.3 `crypto-news-ingestion` 需要

| 变量 | 说明 |
|------|------|
| `EXECUTION_INTERVAL` | 调度间隔（秒），如 `3500` |
| `TIME_WINDOW_HOURS` | 时间窗口，如 `24` |
| `X_CT0` / `X_AUTH_TOKEN` | X/Twitter 抓取凭证（已有） |
| `OPENCODE_API_KEY` | intelligence extraction LLM 凭证 |
| `OPENAI_API_KEY` | embedding 生成凭证 |
| `TELEGRAM_API_ID` | Telethon MTProto 凭证 |
| `TELEGRAM_API_HASH` | Telethon MTProto 凭证 |
| `TELEGRAM_STRING_SESSION` | Telethon StringSession（Multiline 支持） |
| `V2EX_PAT` | V2EX v2 API 个人访问令牌（可选，按需配置） |

> **关键安全约束**：所有 session/secret/PAT 只通过 Railway Secret/Environment Variable 注入，不写入 `config.jsonc`、DB、日志或 API 响应。

---

## 2. 数据库迁移

### 2.1 迁移文件确认

仓库中新增 migration：

- `migrations/postgresql/003_intelligence_schema.sql`

`docker-entrypoint.sh migrate-postgres` 现在按文件名排序执行所有 `[0-9][0-9][0-9]_*.sql`，会包含 `003`。所有 SQL 均使用 `IF NOT EXISTS` 防护，**重复执行 001/002 不会影响已有表结构**，可放心全量重跑。

### 2.2 执行迁移（部署窗口中只执行一次）

1. 备份当前 Postgres 数据库。
2. 在 Railway 中通过 deploy 钩子或临时命令执行：

```bash
/app/docker-entrypoint.sh migrate-postgres
```

3. 确认以下表创建成功：

| 表名 | 用途 |
|------|------|
| `raw_intelligence_items` | 原始文本 + TTL |
| `intelligence_extraction_observations` | LLM 提取观察 |
| `intelligence_canonical_entries` | 规范化知识条目（含 pgvector embedding 列） |
| `intelligence_aliases` | 别名记录 |
| `intelligence_related_candidates` | 语义相似候选关联 |
| `intelligence_crawl_checkpoints` | 采集位点 |

4. 确认 pgvector 扩展已启用：

```sql
SELECT extname FROM pg_extension WHERE extname = 'vector';
```

### 2.3 迁移注意事项

- 迁移不回滚数据库。遇到问题优先向前修复，不要手动删表。
- `crypto-news-analysis` 和 `crypto-news-ingestion` 启动时均**不**自动执行迁移。
- 如果已有 SQLite 数据需要回填，参考 `migrations/postgresql/README.md`。

---

## 3. 部署顺序

```
变量配置 → 备份 DB → migrate-postgres → deploy analysis → 验证 API/Telegram → deploy ingestion → 验证日志 + 添加 datasources
```

### Step 1：变量检查

确认 1.2 和 1.3 中所有变量已在对应 Railway service 中设置。

### Step 2：备份数据库

在 Railway PostgreSQL 服务中执行备份。

### Step 3：执行迁移

执行 `/app/docker-entrypoint.sh migrate-postgres`（见 2.2）。

### Step 4：部署 `crypto-news-analysis`

- 触发部署或重启 `crypto-news-analysis`。
- 检查构建/部署日志，确认 `RAILWAY_SERVICE_NAME -> analysis-service`。
- 验证 `/health` 返回 `200`。

### Step 5：部署 `crypto-news-ingestion`

- 触发部署或重启 `crypto-news-ingestion`。
- 检查构建/部署日志，确认 `RAILWAY_SERVICE_NAME -> ingestion`。
- 确认日志中出现 intelligence pipeline 初始化信息。

> **说明**：analysis 和 ingestion 独立部署，Railway 不保证顺序。务必 migration 完成且 analysis 已验证后，再部署 ingestion（否则 ingestion 可能先于 schema 就绪运行）。

---

## 4. 添加 Intelligence Datasources

Datasource 采用 **数据库优先** 管理：首次启动时从 `config.jsonc` 导入（仅结构，不含 secret），运行时通过 DB 管理。推荐通过 REST API 或 Telegram 命令添加。

### 4.1 Telegram Group Datasource

```json
{
  "source_type": "telegram_group",
  "config_payload": {
    "name": "Crypto Alpha",
    "chat_username": "@cryptoalpha"
  }
}
```

或指定 `chat_id`：

```json
{
  "source_type": "telegram_group",
  "config_payload": {
    "name": "Private Group",
    "chat_id": "-1001234567890"
  }
}
```

**约束**：
- 必须显式提供 `chat_id` 或 `chat_username`。
- 不允许"扫描所有已加入群组"。
- 不允许在 payload 中内联 `session`、`api_hash`、`password` 等敏感字段。

### 4.2 V2EX Datasource

```json
{
  "source_type": "v2ex",
  "config_payload": {
    "name": "V2EX Crypto Node",
    "api_version": "v2",
    "node_allowlist": ["crypto"],
    "pat_env_var_name": "V2EX_PAT"
  }
}
```

**约束**：
- 仅支持 `v1` / `v2` API，不支持 HTML / CSS 爬取。
- PAT 只通过 env var 引用名称，不写入 payload。

### 4.3 添加方式

**REST API**（需 Bearer）：

```bash
curl -X POST "https://news.tradao.xyz/datasources" \
  -H "Authorization: Bearer ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"source_type":"telegram_group","config_payload":{...}}'
```

**Telegram 命令**（授权用户）：

```
/datasource_add {"source_type":"telegram_group","config_payload":{"name":"Crypto Alpha","chat_username":"@cryptoalpha"}}
```

---

## 5. 上线后验证

### 5.1 Analysis Service — HTTP API

```bash
# 健康检查
curl -sS https://news.tradao.xyz/health

# 无鉴权 → 期望 401
curl -i "https://news.tradao.xyz/intelligence/entries?window=7d"

# 鉴权查询
curl -i "https://news.tradao.xyz/intelligence/entries?window=7d&page=1&page_size=20" \
  -H "Authorization: Bearer ${API_KEY}"

# 语义搜索
curl -i "https://news.tradao.xyz/intelligence/search?q=GPT%20plus%E8%B4%AD%E4%B9%B0%E6%B8%A0%E9%81%93&semantic=true&window=7d" \
  -H "Authorization: Bearer ${API_KEY}"

# 条目详情
curl -i "https://news.tradao.xyz/intelligence/entries/{entry_id}" \
  -H "Authorization: Bearer ${API_KEY}"

# 原始文本（include_raw=true，TTL 内有效）
curl -i "https://news.tradao.xyz/intelligence/entries/{entry_id}?include_raw=true" \
  -H "Authorization: Bearer ${API_KEY}"
```

### 5.2 Analysis Service — Telegram 命令

| 命令 | 用途 |
|------|------|
| `/intel_recent 7d` | 最近 7 天条目 |
| `/intel_recent 7d crypto` | 按 primary label 过滤 |
| `/intel_search GPT plus购买渠道` | 语义搜索 |
| `/intel_detail <entry_id>` | 条目详情 |
| `/intel_detail <entry_id> raw` | 条目详情 + 原始文本 |

> 未授权用户应收到拒绝响应，且不会有实际 repository 查询。

### 5.3 Ingestion Service — 日志检查

在 Railway 日志中确认：

1. **启动映射**：`RAILWAY_SERVICE_NAME -> ingestion`
2. **Intelligence pipeline 初始化**：类似 `IntelligencePipeline started` 的日志
3. **Telegram collector 行为**：
   - 只抓取 allowlisted chat
   - 没有调用枚举所有 dialog/chat 的 API
4. **V2EX collector 行为**：
   - 只请求 `/api/` 或 `/api/v2/` 结尾的 URL
   - Rate-limit 触发时记录 retry-after，不崩溃
5. **Extraction**：
   - 使用 `opencode-go` provider
   - 每次 observation 附带 `model_name`、`prompt_version`、`schema_version`
6. **TTL cleanup**：
   - 超过 30 天的 `raw_text` 被置空
   - canonical entry 不受影响
7. **无 secret 泄露**：日志中不出现 `StringSession`、`api_hash`、`password`、`access_token` 等。

---

## 6. 回滚预案

如果部署后出现异常：

1. **冻结变更**：暂停新的 deploy/restart，尤其暂停 `crypto-news-ingestion`。
2. **回滚两个 app service**：通过 Railway Deployments 页面将 `crypto-news-analysis` 和 `crypto-news-ingestion` 分别回滚到上一个成功部署。
3. **不要回滚到旧单体模式** —— 旧模式已退役。
4. **数据库层面**：
   - Schema migration 不回滚。如果 migration 有问题，向前修复（新增 nullable column 或索引），不删除已有表。
   - 如果 migration 导致数据问题，从备份恢复数据库，再重启服务。
5. **回滚后验证**：
   - `/health` 正常
   - 日志中服务映射正确
   - 原有 `/analyze`、`/semantic_search` 等旧功能不受影响

---

## 7. 已知注意事项

1. **文档过期**：`docs/RAILWAY_DEPLOYMENT.md` 和 `migrations/postgresql/README.md` 中仍写 `migrate-postgres` 只执行 `001/002`。实际 `docker-entrypoint.sh` 已包含 `003`，生效的是代码不是文档。
2. **Review 问题**：部署前确认 `docs/HIDDEN_CHANNEL_INTELLIGENCE_REVIEW.md` 中记录的修复（Telegram 窗口、Postgres DDL、migration 路径、依赖、related candidates 生成等）已全部合并到当前分支。
3. **mypy**：仓库级 `mypy` 可能仍有告警，确认 intelligence 相关文件无新增类型错误后再上线。
4. **pgvector extension**：如果 Railway Postgres 实例未启用 pgvector，需手动启用后再跑 migration。
5. **首次冷启动**：新 datasource 首次运行时 backfill 最近 24 小时，之后走 checkpoint 增量。
