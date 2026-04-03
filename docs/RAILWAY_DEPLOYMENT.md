# Railway 部署指南（双服务 + 共享 PostgreSQL）

本文档对应 Task 11 的 Railway 切流结果：同一仓库部署为两个应用服务，并共享一个私有 PostgreSQL/pgvector 数据库。

- `crypto-news-analysis`：公网服务，提供分析 API + Telegram 命令监听，运行 `analysis-service`
- `crypto-news-ingestion`：私有服务，只执行数据摄取，运行 `ingestion`
- PostgreSQL/pgvector：私有数据库，两个服务共用同一个 `DATABASE_URL`

任何历史单体模式或兼容别名现在都会被入口层直接拒绝；生产路径只保留当前双服务运行面。

---

## 1. Railway 拓扑

| Railway 服务 | 是否公网 | 启动模式 | 用途 |
| --- | --- | --- | --- |
| `crypto-news-analysis` | 是 | `analysis-service` | 暴露 `/health`、`/analyze`，并启用 Telegram 命令监听（禁用调度器） |
| `crypto-news-ingestion` | 否 | `ingestion` | 定时执行爬取/摄取任务 |
| PostgreSQL/pgvector | 否 | N/A | 两个应用服务共享的数据库 |

仓库内的 `railway.toml` 现在使用统一启动命令：

```toml
[deploy]
startCommand = "/app/docker-entrypoint.sh"
```

容器启动后由 `docker-entrypoint.sh` 根据 Railway 自动注入的 `RAILWAY_SERVICE_NAME` 路由到正确模式：

- `crypto-news-analysis` -> `analysis-service`
- `crypto-news-ingestion` -> `ingestion`

这意味着两个 Railway 应用服务可以继续共用**同一个代码库、同一个 Dockerfile、同一个 railway.toml**。

切流完成后的生产默认路径只有三种：

- `crypto-news-analysis` -> `analysis-service`
- `crypto-news-ingestion` -> `ingestion`
- 发布窗口中的单次 schema 变更 -> `migrate-postgres`

不要恢复任何旧单体运行模式；生产常驻路径只保留当前双服务拓扑。

---

## 2. 环境变量

### 两个应用服务都需要

```bash
# 共享 PostgreSQL/pgvector
DATABASE_URL=postgresql://...

# 通用运行配置
CONFIG_PATH=./config.json
LOG_LEVEL=INFO
TIME_WINDOW_HOURS=24
```

说明：

- `DATABASE_URL` 会覆盖 `config.json` 中的 `storage.database_url`
- Railway 中两个应用服务必须指向**同一个**私有 Postgres 实例
- 若使用 PostgreSQL 后端，请确保配置中的 `storage.backend=postgres`

### 仅 `crypto-news-analysis` 需要

```bash
# API 服务鉴权与监听
API_KEY=your_strong_api_key
API_HOST=0.0.0.0
API_PORT=8080

# LLM 相关密钥（用于新闻分析和市场快照）
# 主 LLM API 密钥（必需）
LLM_API_KEY=...

# 若使用 Kimi 为主模型，可额外配置（优先于 LLM_API_KEY 用于 Kimi 路径）
KIMI_API_KEY=...

# 市场快照：必须使用 Grok
GROK_API_KEY=...

# Telegram Bot（用于命令监听和报告推送）
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHANNEL_ID=...
TELEGRAM_AUTHORIZED_USERS=...
```

### 仅 `crypto-news-ingestion` 需要

```bash
# 调度间隔（秒）
EXECUTION_INTERVAL=3500

# X/Twitter 抓取凭证（按实际抓取源配置）
X_CT0=...
X_AUTH_TOKEN=...
```

`crypto-news-ingestion` 必须保持私有，不要为它绑定公网域名。

**重要说明：**

- `crypto-news-ingestion` **不**需要 `LLM_API_KEY`、`GROK_API_KEY`、`KIMI_API_KEY` 等 LLM 相关密钥，因为它不初始化 LLMAnalyzer、market snapshot service 或 Telegram 组件
- `crypto-news-analysis` 需要完整的 LLM 和 Telegram 配置，因为它执行实际的新闻分析并响应 API/Telegram 命令

### 模型密钥使用方式与 fallback 机制

**市场快照（Market Snapshot）**

- 仅使用 `GROK_API_KEY`
- 内部有缓存机制，失效时重新获取
- Grok 不可用时回退到本地 fallback 快照（非实时）

**新闻分析（News Analysis）**

- 主模型：Kimi（使用 `KIMI_API_KEY`，若未配置则使用 `LLM_API_KEY`）
- 备用模型：Grok（仅在 Kimi 返回**内容过滤错误**时触发）
- 注意：fallback 机制有限，仅在 `ContentFilterError` 时切换，其他错误不会自动切换

---

## 3. 创建双服务 + 共享数据库

1. 在 Railway 项目中创建一个 PostgreSQL 服务（私有）
2. 在同一个 Railway 项目里，从同一 GitHub 仓库创建两个应用服务：
   - `crypto-news-analysis`
   - `crypto-news-ingestion`
3. 将 PostgreSQL 生成的同一个 `DATABASE_URL` 同时注入到这两个应用服务
4. 仅为 `crypto-news-analysis` 绑定公网域名
5. 不要为 `crypto-news-ingestion` 绑定公网域名或暴露公开入口

推荐检查项：

- `crypto-news-analysis` 的部署日志里应出现 `RAILWAY_SERVICE_NAME -> analysis-service`
- `crypto-news-ingestion` 的部署日志里应出现 `RAILWAY_SERVICE_NAME -> ingestion`
- `crypto-news-analysis` 不应启动摄取循环；但应可接收 Telegram `/analyze` 命令

---

## 4. 单一迁移执行策略

不要让两个常驻服务在启动时自动执行数据库迁移。

当前仓库提供了一个**显式单次命令**用于 schema 初始化/升级：

```bash
/app/docker-entrypoint.sh migrate-postgres
```

该命令会读取：

- `DATABASE_URL`
- `/app/migrations/postgresql/001_init.sql`

推荐策略：

1. 在部署窗口中先执行一次 `migrate-postgres`
2. 确认迁移成功后，再部署或重启 `crypto-news-analysis` / `crypto-news-ingestion`
3. 不要把 `migrate-postgres` 配成两个常驻服务的默认启动命令

换句话说，迁移是**单独的发布步骤**，不是 analysis/ingestion 两个服务的常规启动流程。

若需要把旧 SQLite 数据回填到 PostgreSQL，不要从本地通过 Railway 公网 PostgreSQL 代理执行大批量导入。应在挂载了 SQLite volume 的 Railway 应用容器内执行：

```bash
railway ssh -s <service-with-sqlite-volume> \
  "/opt/venv/bin/python3 /app/migrations/postgresql/remote_internal_backfill.py \
    --sqlite-path /app/data/crypto_news.db \
    --postgres-url \"\$DATABASE_URL\""
```

说明：

- 该脚本使用 Railway 私网连接 PostgreSQL
- 该脚本会先清空 `content_items`、`crawl_status`、`analysis_execution_log`、`sent_message_cache`
- 执行前确认目标 PostgreSQL 已完成 `001_init.sql`

---

## 5. 验证 analysis 公网服务

```bash
# 健康检查
curl -sS https://<analysis-domain>/health

# 创建分析任务（hours > 0，user_id 必填）
curl -i -X POST "https://<analysis-domain>/analyze" \
  -H "Authorization: Bearer ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"hours":24,"user_id":"operator_01"}'

# 查询任务状态
curl -H "Authorization: Bearer ${API_KEY}" \
  "https://<analysis-domain>/analyze/<job_id>"

# 获取最终结果
curl -H "Authorization: Bearer ${API_KEY}" \
  "https://<analysis-domain>/analyze/<job_id>/result"
```

预期：

- `/health` 返回 `200`
- `POST /analyze`：
  - 无 token 或错误 token 返回 `401`
  - 缺少 `user_id` 或格式非法返回 `422`
  - `hours<=0` 返回 `422`
  - 合法请求返回 `202`，包含 `job_id/status_url/result_url`
- `GET /analyze/{job_id}` 返回 `200`
- `GET /analyze/{job_id}/result`：任务未完成时返回 `202`，完成后返回 `200`

说明：

- `POST /analyze` 是异步接口
- 客户端应保存 `job_id` 并轮询状态/结果接口

---

## 6. 验证 ingestion 私有服务

`crypto-news-ingestion` 没有公网入口，建议通过 Railway 日志验证：

- 服务名为 `crypto-news-ingestion`
- 启动模式为 `ingestion`
- 没有绑定公网域名
- 使用与 `crypto-news-analysis` 相同的 `DATABASE_URL`

如果部署日志显示入口仍接受 legacy 单体模式或旧 Railway 服务别名，说明仍残留兼容逻辑，需要改回当前仓库里的 split-service 入口语义。

---

## 7. 回滚预案（回到上一个稳定部署/配置）

如果本次切流后的部署异常，按下面步骤回滚；**不要**把任何旧单体模式重新设为常驻生产路径：

1. 先冻结变更：暂停新的 deploy/restart 操作，并避免在故障窗口继续触发 `crypto-news-ingestion`
2. 在 Railway 的 Deployments/Variables 页面记录两个服务当前版本，并找到各自“上一个稳定”的 deployment/configuration
3. 将 `crypto-news-analysis` 回滚到上一个稳定部署，并恢复它当时的公网域名/API 相关变量；回滚后它仍应运行 `analysis-service`
4. 将 `crypto-news-ingestion` 回滚到上一个稳定部署，并恢复它当时的私有变量配置；回滚后它仍应运行 `ingestion`
5. 保持两个服务继续共用同一个稳定的 `DATABASE_URL`；如果问题与 schema 变更直接相关，先按现有数据库备份/恢复流程处理数据层，再重启两个服务
6. 若本次发布包含 schema 变更，确认 `migrate-postgres` 不再重复执行，只在需要时按单次发布步骤重新运行
7. 回滚完成后检查日志，确认服务映射重新回到 `crypto-news-analysis -> analysis-service` 与 `crypto-news-ingestion -> ingestion`

这份回滚预案的目标是回到**上一个稳定的双服务部署**，而不是恢复旧单体入口。

---

## 8. 日志排查（Railway GraphQL）

如果你在本地有 `RAILWAY_API_TOKEN`，可直接查部署与日志：

```bash
# 最新部署
curl -s -X POST https://backboard.railway.com/graphql/v2 \
  -H "Authorization: Bearer $RAILWAY_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "query deployments($input: DeploymentListInput!, $first: Int) { deployments(input: $input, first: $first) { edges { node { id status createdAt staticUrl } } } }",
    "variables": {
      "input": {
        "projectId": "<PROJECT_ID>",
        "environmentId": "<ENV_ID>",
        "serviceId": "<SERVICE_ID>"
      },
      "first": 5
    }
  }'
```

```bash
# 部署日志
curl -s -X POST https://backboard.railway.com/graphql/v2 \
  -H "Authorization: Bearer $RAILWAY_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "query { deploymentLogs(deploymentId: \"<DEPLOYMENT_ID>\", limit: 200) { message severity timestamp } }"
  }'
```

重点关注：

- `crypto-news-analysis` 是否映射到 `analysis-service`
- `crypto-news-ingestion` 是否映射到 `ingestion`
- 是否只有单次 `migrate-postgres` 发布步骤执行了 schema 迁移

---

## 9. 常见问题

### Q: 为什么不再推荐旧单体模式作为 Railway 默认模式？

A: 因为切流后的目标是把公网 API 与私有 ingestion 拆成两个独立服务，避免继续使用单服务混合部署假设。旧单体兼容模式已完全退役，入口层不会再把它翻译成保留模式。

### Q: 哪个服务应该公开？

A: 只有 `crypto-news-analysis` 应该公开；`crypto-news-ingestion` 必须保持私有。

### Q: 数据库应该怎么接？

A: 两个应用服务都使用同一个 `DATABASE_URL`，连接同一个 Railway 私有 PostgreSQL/pgvector 实例。

### Q: 数据库迁移由谁执行？

A: 迁移不是两个常驻服务之一的默认职责，而是单独执行一次的发布步骤：`/app/docker-entrypoint.sh migrate-postgres`。
