# Railway 部署指南（含 API Server 模式）

本文档用于部署 `getnews` 到 Railway，并覆盖 PR #1 后的新运行方式：

- `schedule`：定时仅爬取（不自动分析）
- `api-server`：提供 HTTP API（`/health`、`/analyze`）+ 定时爬取 + Telegram 命令监听

---

## 1. 运行模式说明

### `schedule` 模式

- 定时任务只执行爬取阶段
- 不自动执行分析
- 分析通过 Telegram `/analyze` 命令手动触发

### `api-server` 模式（推荐线上）

- 提供 HTTP 接口：
  - `GET /health`
  - `POST /analyze`
  - `GET /analyze/{job_id}`
  - `GET /analyze/{job_id}/result`
- 同时保留：
  - 定时爬取
  - Telegram 命令监听（含 `/analyze`）

当前仓库 `railway.toml` 默认：

```toml
[deploy]
startCommand = "/app/docker-entrypoint.sh api-server"
```

---

## 2. 必需环境变量

在 Railway Dashboard → Variables 中至少配置以下内容：

```bash
# LLM
LLM_API_KEY=...
# 可按你的模型配置补充 GROK_API_KEY / KIMI_API_KEY

# Telegram
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHANNEL_ID=...
TELEGRAM_AUTHORIZED_USERS=123456789,@your_username

# X / Twitter 抓取（可选，按实际数据源决定）
X_CT0=...
X_AUTH_TOKEN=...

# API Server 鉴权（api-server 模式必需）
API_KEY=your_strong_api_key
```

推荐可选项：

```bash
CONFIG_PATH=./config.json
TIME_WINDOW_HOURS=1
EXECUTION_INTERVAL=3500
LOG_LEVEL=INFO

# API 监听地址（api-server 模式）
API_HOST=0.0.0.0
API_PORT=8080
```

---

## 3. 部署与验证

### 部署

1. Railway 选择 GitHub 仓库部署
2. 确认 `railway.toml` 使用 `api-server` 启动命令
3. 配置变量后触发部署

### 验证 HTTP 接口

```bash
# 健康检查
curl -sS https://<your-domain>/health

# 创建分析任务（hours > 0）
curl -i -X POST "https://<your-domain>/analyze" \
  -H "Authorization: Bearer ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"hours":24}'

# 查询任务状态
curl -H "Authorization: Bearer ${API_KEY}" \
  "https://<your-domain>/analyze/<job_id>"

# 获取最终结果
curl -H "Authorization: Bearer ${API_KEY}" \
  "https://<your-domain>/analyze/<job_id>/result"
```

预期：

- `/health` 返回 200，且 `initialized=true`
- `/analyze`：
  - 无 token 或错误 token 返回 401
  - `hours<=0` 返回 422（Pydantic 校验）
  - 合法请求返回 202，包含 `job_id/status_url/result_url`
- `GET /analyze/{job_id}`：
  - 返回 200，包含任务状态（`queued/running/completed/failed`）
- `GET /analyze/{job_id}/result`：
  - 任务未完成时返回 202
  - 任务完成时返回 200，包含 `report/items_processed/time_window_hours`

说明：

- 这是为避免 Cloudflare 524 引入的异步接口契约
- `POST /analyze` 不再同步返回 Markdown 报告
- 客户端应保存 `job_id` 并轮询状态/结果接口

---

## 4. Telegram 手动分析命令

可用命令（与权限配置相关）：

- `/run`
- `/analyze [hours]`
- `/market`
- `/status`
- `/tokens`
- `/help`

`/analyze` 说明：

- `/analyze 24`：分析最近 24 小时
- `/analyze`：按“距离该 chat 上次成功分析时间”自动计算窗口（最大 24 小时）

---

## 5. 日志排查（Railway GraphQL）

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

---

## 6. 持久化存储（Volume）

Railway Volume 仍需在控制台手动创建，推荐挂载：

- `/app/data`（数据库与缓存）

注意：

- Volume 在运行时挂载，不在构建时挂载
- 重部署/重启不会丢失 volume 数据
- 删除服务可能导致 volume 一并删除（请提前备份）

---

## 7. 常见问题

### Q: 这是 worker 还是 web 服务？

A: `api-server` 模式下是 **web + worker 混合**：既有 HTTP API，也有后台爬取与 Telegram 命令监听。

### Q: 为什么 `/analyze` 的 `hours=0` 返回 422 而不是 400？

A: 因为请求体先经过 Pydantic 校验（`hours > 0`），不满足时由 FastAPI 直接返回 422。

### Q: 如何确认线上是否真的命中了接口？

A: 查 `deploymentLogs` 中的 Uvicorn 访问日志，例如：

- `"POST /analyze HTTP/1.1" 202 Accepted`
- `"GET /analyze/<job_id> HTTP/1.1" 200 OK`
- `"GET /analyze/<job_id>/result HTTP/1.1" 200 OK`
