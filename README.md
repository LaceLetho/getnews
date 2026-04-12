# 加密货币新闻分析工具

一个面向 Railway 双服务部署的加密货币新闻分析系统：私有 ingestion 服务负责抓取与入库，公网 analysis 服务负责 HTTP API、Telegram 命令、LLM 分析与结果查询。Phase 1 已完成服务拆分，当前共享同一个 PostgreSQL/pgvector 数据库。

## 当前架构

- `crypto-news-analysis`：公网服务，运行 `analysis-service`，提供 `/health`、`/analyze`、Telegram 命令监听
- `crypto-news-ingestion`：私有服务，运行 `ingestion`，负责 scheduler 驱动的采集、去重、入库
- PostgreSQL + pgvector：共享数据库，承载内容数据、`analysis_jobs`、`ingestion_jobs`、数据源配置

旧版 API server 模式不再是推荐的生产模式；它只作为兼容别名映射到 `analysis-service`。

如果你要通过 HTTP API 调用新闻分析接口，或你是一个需要自动调用接口的 AI，请先阅读 [AI Analyze API Guide](docs/AI_ANALYZE_API_GUIDE.md)。该文档记录了当前有效的 `POST /analyze -> 轮询 -> 取结果` 异步契约。

## 功能特性

- 🔄 **多源数据收集**: 支持RSS订阅和X/Twitter内容爬取
- 🤖 **智能分析**: 使用 MiniMax M2.1 大语言模型进行内容分析和分类
- 📊 **结构化报告**: 生成Markdown格式的分析报告
- 📱 **自动发送**: 通过Telegram Bot自动发送报告
- 🔁 **Split-service 运行面**: 仅保留 `analysis-service`、`api-only`、`ingestion` 三种运行模式
- 🔧 **数据库优先的数据源管理**: 首次启动从 `config.json` 导入，运行时通过数据库管理，支持 REST API 和 Telegram 命令操作
- 🛡️ **容错设计**: 完善的错误处理和恢复机制
- 🎯 **智能分类**: 支持大户动向、利率事件、监管政策、真相揭露等多种分类
- ☁️ **云端部署**: 支持部署到 Railway 平台
- 🌐 **HTTP API**: 支持 Bearer Token 鉴权的异步分析接口（`POST /analyze` 创建任务，轮询获取结果）
- 🤖 **Telegram 手动分析**: 支持 `/analyze [hours]` 按时间窗口触发分析

如果你要通过 HTTP API 调用新闻分析接口，或你是一个需要自动调用接口的 AI，请先阅读 [AI Analyze API Guide](docs/AI_ANALYZE_API_GUIDE.md)。该文档包含最新的请求体要求、鉴权方式、异步轮询流程和生产环境验证结果。

## 仓库结构

```text
crypto_news_analyzer/
├── __init__.py
├── main.py                     # 运行模式入口（analysis-service / api-only / ingestion）
├── api_server.py               # FastAPI 异步分析 API
├── execution_coordinator.py    # 分析、摄取与调度协调器
├── models.py                   # 共享数据模型
├── config/
│   └── manager.py              # 配置加载与归一化
├── domain/
│   ├── models.py               # 领域模型
│   └── repositories.py         # 仓储接口
├── crawlers/
│   ├── rss_crawler.py          # RSS 爬取器
│   └── x_crawler.py            # X/Twitter 爬取器
├── analyzers/
│   ├── llm_analyzer.py         # LLM 分析器
│   └── prompt_manager.py       # 提示词管理器
├── storage/
│   ├── repositories.py         # SQLite/Postgres 仓储实现
│   └── data_manager.py         # 数据管理器
├── reporters/
│   └── telegram_command_handler.py # Telegram 命令处理
└── utils/
    ├── logging.py              # 日志管理
    └── errors.py               # 错误处理
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

# LLM Provider 凭证（analysis-service / api-only 必需）
# 使用 provider-specific 环境变量而非通用 LLM_API_KEY
KIMI_API_KEY=your_kimi_api_key_here
GROK_API_KEY=your_grok_api_key_here

# API 鉴权（启用 analysis-service / api-only 时必需）
API_KEY=your_api_key

# Telegram 配置（analysis-service 可选）
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHANNEL_ID=-1001234567890

# Telegram 授权用户（支持用户ID和用户名）
# 多个用户用逗号分隔，可以混合使用用户ID和@username格式
# 示例: 123456789,@user1,987654321,@user2
TELEGRAM_AUTHORIZED_USERS=your_user_id_here

# X/Twitter 认证 (可选)
X_CT0=your_X_CT0
X_AUTH_TOKEN=your_X_AUTH_TOKEN
```

#### 如何获取 Telegram 用户 ID

1. 在 Telegram 中搜索 `@userinfobot`
2. 发送 `/start` 命令
3. Bot 会返回你的用户 ID

#### Telegram 授权用户配置说明

系统支持两种格式配置授权用户：

1. **用户 ID（数字）**: 直接使用 Telegram 用户 ID，例如 `123456789`
2. **用户名（@开头）**: 使用 Telegram 用户名，例如 `@username`

可以混合使用两种格式，用逗号分隔：

```bash
# 仅用户ID
TELEGRAM_AUTHORIZED_USERS=123456789,987654321

# 仅用户名
TELEGRAM_AUTHORIZED_USERS=@user1,@user2,@user3

# 混合格式（推荐）
TELEGRAM_AUTHORIZED_USERS=5844680524,@wingperp,@mcfangpy,@Huazero,@long0short
```

**注意事项：**
- 使用用户名时，bot 必须先与该用户互动过，或者用户有公开的 profile
- 如果用户名解析失败，系统会记录警告并跳过该用户名
- 建议对关键用户使用用户 ID 作为备份
- 所有授权用户都有相同的权限，可以执行所有可用命令（/analyze, /status, /help 等）

### LLM 配置

模型配置在 `config.json` 的 `llm_config` 字段中定义。环境变量仅用于提供 provider 的 API 密钥（`KIMI_API_KEY`、`GROK_API_KEY`）。

**`llm_config` 结构：**

```json
{
  "llm_config": {
    "model": {
      "provider": "kimi",
      "name": "kimi-k2.5",
      "options": {"thinking_level": "medium"}
    },
    "fallback_models": [
      {"provider": "grok", "name": "grok-4-1-fast-reasoning", "options": {}}
    ],
    "market_model": {
      "provider": "grok",
      "name": "grok-4-1-fast-reasoning",
      "options": {}
    },
    "temperature": 0.5,
    "max_tokens": 4000,
    "batch_size": 10
  }
}
```

**支持的 Provider 和模型：**

- **kimi** (环境变量: `KIMI_API_KEY`)
  - kimi-k2.5, kimi-k2-turbo-preview, kimi-k2-thinking-turbo
- **grok** (环境变量: `GROK_API_KEY`)
  - grok-4-1-fast-reasoning, grok-4-1-fast-non-reasoning, grok-4.20-reasoning, grok-4.20-non-reasoning

**配置字段说明：**

- `model`: 主分析模型配置（必需）
- `fallback_models`: 备用模型列表，主模型失败时按顺序尝试（必需）
- `market_model`: 市场快照专用模型（必需，建议使用 grok）
- `options.thinking_level`: 可选，取值：disabled, low, medium, high, xhigh

### 4. 运行系统

支持三种常驻运行模式：

- `analysis-service`：启动公网分析服务，提供 `/health`、`/analyze` 接口，并启用 Telegram `/analyze`
- `api-only`：仅启动 FastAPI 分析接口，不启用 Telegram 命令监听
- `ingestion`：启动私有摄取循环，按 `EXECUTION_INTERVAL` 周期抓取内容

```bash
# 公网分析服务（默认监听 0.0.0.0:8080）
uv run python -m crypto_news_analyzer.main --mode analysis-service

# 隔离 API 服务（默认监听 0.0.0.0:8080）
uv run python -m crypto_news_analyzer.main --mode api-only

# 私有摄取服务
uv run python -m crypto_news_analyzer.main --mode ingestion
```

维护说明：`migrate-postgres` 是 `docker-entrypoint.sh` 提供的一次性 PostgreSQL 迁移入口，仅用于部署/维护场景，不属于 `crypto_news_analyzer.main` 的常驻运行模式列表。

可选 API 服务环境变量：

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


## Telegram 命令功能

系统支持通过 Telegram Bot 命令进行交互式控制：

### 可用命令

- `/analyze [hours]` - 按时间窗口分析历史消息（不传参数时按“距上次成功分析时间”自动估算，最大24小时）
- `/market` - 获取当前市场快照
- `/status` - 查询系统运行状态
- `/tokens` - 查看token使用统计
- `/help` - 显示帮助信息

### 多用户授权机制

系统支持多个授权用户在私聊和群组中与bot交互：

1. **私聊授权**: 授权用户可以在与 bot 的私聊中执行命令
2. **群组授权**: 授权用户可以在群组中执行命令（基于用户 ID，而非群组 ID）
3. **统一权限**: 所有授权用户拥有相同的权限，可以执行所有命令

### 报告发送规则

- **默认频道报告**: 未显式指定目标聊天时，发送到 `TELEGRAM_CHANNEL_ID` 指定的频道
- **手动分析报告**: 由 Telegram `/analyze` 触发时，发送到用户触发命令的聊天窗口（私聊或群组）

### 配置授权用户

在 `.env` 文件中配置 `TELEGRAM_AUTHORIZED_USERS`，支持两种格式：

```bash
# 支持用户ID和用户名混合格式
# 格式1: 用户ID（数字）
# 格式2: 用户名（@开头）
# 多个用户用逗号分隔

# 示例1: 仅用户ID
TELEGRAM_AUTHORIZED_USERS=123456789,987654321

# 示例2: 仅用户名
TELEGRAM_AUTHORIZED_USERS=@user1,@user2,@user3

# 示例3: 混合格式（推荐）
TELEGRAM_AUTHORIZED_USERS=5844680524,@wingperp,@mcfangpy,@Huazero,@long0short
```




### 速率限制

为防止滥用，系统实施了速率限制：
- 每小时最多执行命令次数（默认：120次）
- 命令冷却时间（默认：5分钟）

可在 `config.json` 的 `telegram_commands.command_rate_limit` 中调整。

## HTTP API（`analysis-service` / `api-only`）

调用 `POST /analyze` 前，建议先阅读 [AI Analyze API Guide](docs/AI_ANALYZE_API_GUIDE.md)。
对 AI 代理尤其重要：该文档说明了真实必填参数、错误响应样例，以及正确的 `POST /analyze -> 轮询状态 -> 获取结果` 工作流。

### 认证方式

- 使用 `Authorization: Bearer <API_KEY>`
- `API_KEY` 来自环境变量

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

## 数据源管理

系统采用**数据库优先**的数据源管理模式。首次启动时，若数据源表为空，系统会从 `config.json` 自动导入配置。此后运行时，所有数据源读写均通过数据库进行，修改 `config.json` 不会影响运行时行为。

### 数据源标签约束

- 每个数据源最多 16 个唯一标签
- 单个标签最长 32 个字符
- 标签自动转为小写并去重

### REST API 数据源接口

所有数据源接口需 Bearer 认证 (`Authorization: Bearer <API_KEY>`)：

- `POST /datasources` - 创建数据源（成功返回 201，重复返回 409）
- `GET /datasources` - 列出所有数据源（按类型和名称排序）
- `DELETE /datasources/{id}` - 删除指定数据源（成功返回 204，不存在返回 404，正在使用返回 409）

列表接口返回安全的摘要信息，敏感字段（如 `rest_api` 的认证信息）会被脱敏。

### Telegram 数据源命令

授权用户可通过 Telegram Bot 管理数据源：

- `/datasource_list` - 查看已配置的数据源列表
- `/datasource_add {json}` - 添加数据源，参数为 JSON 对象
- `/datasource_delete <id>` - 删除指定 ID 的数据源

**`rest_api` 数据源通过 Telegram 添加的限制：**
Telegram 命令禁止内联提交认证信息。`rest_api` 的 `config_payload` 中不得包含 `headers`、`params` 或 `auth` 字段的敏感令牌。请改用服务端环境变量配置认证。

#### 数据源添加示例

```
/datasource_add {"source_type":"rss","tags":["markets","btc"],"config_payload":{"name":"CoinDesk","url":"https://www.coindesk.com/rss","description":"Industry news"}}
```

```
/datasource_add {"source_type":"x","tags":["whales"],"config_payload":{"name":"Whale Watch","url":"https://x.com/i/lists/1234567890","type":"list"}}
```

```
/datasource_add {"source_type":"rest_api","tags":["news"],"config_payload":{"name":"News API","endpoint":"https://api.example.com/news","method":"GET","headers":{},"params":{},"response_mapping":{"title_field":"title","content_field":"body","url_field":"url","time_field":"published_at"}}}
```

## 许可证

MIT License
