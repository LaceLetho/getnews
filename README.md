# 加密货币新闻分析工具

一个面向 Railway 双服务部署的加密货币新闻分析系统：私有 ingestion 服务负责抓取与入库，公网 analysis 服务负责 HTTP API、Telegram 命令、LLM 分析与结果查询。Phase 1 已完成服务拆分，当前共享同一个 PostgreSQL/pgvector 数据库。

## 当前架构

- `crypto-news-analysis`：公网服务，运行 `analysis-service`，提供 `/health`、`/analyze`、Telegram 命令监听
- `crypto-news-ingestion`：私有服务，运行 `ingestion`，负责 scheduler 驱动的采集、去重、入库
- PostgreSQL + pgvector：共享数据库，承载内容数据、`analysis_jobs`、`ingestion_jobs`

`api-server` 不再是推荐的生产模式；它只作为兼容别名映射到 `analysis-service`。

如果你要通过 HTTP API 调用新闻分析接口，或你是一个需要自动调用接口的 AI，请先阅读 [AI Analyze API Guide](docs/AI_ANALYZE_API_GUIDE.md)。该文档记录了当前有效的 `POST /analyze -> 轮询 -> 取结果` 异步契约。

## 功能特性

- 🔄 **多源采集**：支持 RSS、X/Twitter、REST API 数据源
- 🧠 **异步分析工作流**：`POST /analyze` 创建持久化 job，状态与结果可轮询
- 🗃️ **共享数据库**：PostgreSQL/pgvector 作为唯一真实数据源
- 🤖 **Telegram 运维入口**：支持 `/analyze`、`/market`、`/status` 等命令
- ⏰ **采集与分析解耦**：scheduler 默认只负责 ingestion，不自动执行分析
- ☁️ **Railway 双服务部署**：公网 analysis + 私有 ingestion + 私有数据库

## 仓库结构

```text
crypto_news_analyzer/
├── main.py                    # CLI/runtime 入口，支持 analysis-service / ingestion / once 等模式
├── api_server.py              # FastAPI 应用与 /analyze 异步接口
├── execution_coordinator.py   # 主流程编排器
├── domain/                    # 共享领域模型与 repository 接口
├── storage/                   # SQLite/Postgres 适配与 repository 实现
├── crawlers/                  # RSS/X/REST API 采集实现
├── analyzers/                 # LLM 分析、分类、快照逻辑
├── reporters/                 # Telegram 命令与报告发送
├── config/                    # 配置加载与环境变量覆盖
└── utils/                     # 日志、错误、时间处理

docs/
├── AI_ANALYZE_API_GUIDE.md
└── RAILWAY_DEPLOYMENT.md

migrations/postgresql/
├── 001_init.sql
└── README.md
```

## 快速开始

### 1. 安装依赖

本项目使用 `uv`。推荐 Python 3.9+。

```bash
uv pip install -e ".[dev]"
```

### 2. 配置环境变量

```bash
cp .env.template .env
```

至少需要根据运行模式配置：

```bash
# 共享数据库（当前默认后端为 postgres）
DATABASE_URL=postgresql://postgres:password@host:5432/railway

# Analysis 服务核心变量
API_KEY=your_api_key
LLM_API_KEY=your_llm_key
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHANNEL_ID=-1001234567890

# Analysis 服务按功能启用
GROK_API_KEY=your_grok_key
KIMI_API_KEY=your_kimi_key
TELEGRAM_AUTHORIZED_USERS=123456789,@operator

# Ingestion 服务按需配置
X_CT0=your_x_ct0
X_AUTH_TOKEN=your_x_auth_token
```

说明：

- `DATABASE_URL` 会覆盖 `config.json` 中的 `storage.database_url`
- 当前 `config.json` 已默认 `storage.backend=postgres`
- `crypto-news-ingestion` 不需要 Telegram 或 LLM 相关密钥
- `GROK_API_KEY` 主要用于市场快照；`KIMI_API_KEY` 未配置时会回退到 `LLM_API_KEY` 路径
- `TELEGRAM_AUTHORIZED_USERS` 仅在启用 Telegram 命令入口时需要

### 3. 常用运行模式

```bash
# 公网分析服务（默认模式）
uv run python -m crypto_news_analyzer.main --mode analysis-service

# 私有 ingestion 服务
uv run python -m crypto_news_analyzer.main --mode ingestion

# 仅 API（不启动 Telegram）
uv run python -m crypto_news_analyzer.main --mode api-only

# 一次性执行（本地/维护场景）
uv run python -m crypto_news_analyzer.main --mode once

# 兼容调度模式
uv run python -m crypto_news_analyzer.main --mode schedule
```

兼容说明：

- `--mode api-server` 会自动映射到 `analysis-service`
- 生产默认路径应使用 `analysis-service` 与 `ingestion`，而不是旧单体模式

### 4. 数据库迁移

初始化 PostgreSQL schema：

```bash
psql "$DATABASE_URL" -f migrations/postgresql/001_init.sql
```

或在容器内执行显式迁移入口：

```bash
/app/docker-entrypoint.sh migrate-postgres
```

更多说明见 [migrations/postgresql/README.md](migrations/postgresql/README.md)。

### 5. 运行测试

```bash
uv run pytest tests/
uv run mypy crypto_news_analyzer/
uv run flake8 crypto_news_analyzer/
```

## Telegram 命令

系统支持通过 Telegram Bot 进行交互控制。

常用命令：

- `/run`：立即执行一次完整任务（仅适用于 legacy/local 路径，不是 split-service 生产主路径）
- `/analyze [hours]`：按时间窗口触发分析
- `/market`：获取市场快照
- `/status`：查看系统状态
- `/tokens`：查看 token 使用情况
- `/help`：显示帮助

说明：

- 授权用户可在私聊或群组中使用命令
- 手动分析结果会回发到触发命令的聊天窗口
- split-service 生产路径下，`ingestion` 只负责采集，不负责定时发送分析报告
- `TELEGRAM_CHANNEL_ID` 主要用于 legacy `once` / `schedule` 路径下的报告投递

## HTTP API

HTTP API 由 `analysis-service` 暴露，使用 Bearer Token 鉴权。

### 接口列表

- `GET /health`
- `POST /analyze`
- `GET /analyze/{job_id}`
- `GET /analyze/{job_id}/result`

### 创建分析任务

```bash
curl -X POST "http://localhost:8080/analyze" \
  -H "Authorization: Bearer ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"hours":24,"user_id":"operator_01"}'
```

请求约束：

- `hours > 0`
- `user_id` 仅允许字母、数字、`_`、`-`

成功时返回 `202 Accepted`，并提供：

- `job_id`
- `status`
- `status_url`
- `result_url`
- `time_window_hours`

状态流转：`queued` → `running` → `completed` / `failed`

## Railway 部署

完整部署文档见 [docs/RAILWAY_DEPLOYMENT.md](docs/RAILWAY_DEPLOYMENT.md)。

当前推荐拓扑：

1. 创建一个私有 PostgreSQL 服务
2. 从同一仓库部署两个应用服务：`crypto-news-analysis`、`crypto-news-ingestion`
3. 两个服务共用同一个 `DATABASE_URL`
4. 仅为 `crypto-news-analysis` 绑定公网域名
5. 不要为 `crypto-news-ingestion` 暴露公网入口

## 相关文档

- [AI Analyze API Guide](docs/AI_ANALYZE_API_GUIDE.md)
- [Railway Deployment Guide](docs/RAILWAY_DEPLOYMENT.md)
- [PostgreSQL Migration README](migrations/postgresql/README.md)

## 许可证

MIT License
