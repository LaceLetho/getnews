# 加密货币新闻分析工具

一个自动化系统，用于从多个信息源收集加密货币相关新闻和社交媒体内容，并通过大模型进行智能分析和分类，生成结构化的新闻快讯报告。

## 功能特性

- 🔄 **多源数据收集**: 支持RSS订阅和X/Twitter内容爬取
- 🤖 **智能分析**: 使用 MiniMax M2.1 大语言模型进行内容分析和分类
- 📊 **结构化报告**: 生成Markdown格式的分析报告
- 📱 **自动发送**: 通过Telegram Bot自动发送报告
- ⏰ **定时调度（仅爬取）**: 定时任务默认只执行数据爬取，不自动触发分析
- 🔧 **配置驱动**: 通过配置文件管理所有信息源
- 🛡️ **容错设计**: 完善的错误处理和恢复机制
- 🎯 **智能分类**: 支持大户动向、利率事件、监管政策、真相揭露等多种分类
- ☁️ **云端部署**: 支持部署到 Railway 平台
- 🌐 **HTTP API**: 支持 Bearer Token 鉴权的异步分析接口（`POST /analyze` 创建任务，轮询获取结果）
- 🤖 **Telegram 手动分析**: 支持 `/analyze [hours]` 按时间窗口触发分析

如果你要通过 HTTP API 调用新闻分析接口，或你是一个需要自动调用接口的 AI，请先阅读 [AI Analyze API Guide](docs/AI_ANALYZE_API_GUIDE.md)。该文档包含最新的请求体要求、鉴权方式、异步轮询流程和生产环境验证结果。

## 项目结构

```
crypto_news_analyzer/
├── __init__.py                 # 包初始化
├── main.py                     # 主程序入口
├── models.py                   # 数据模型定义
├── config/                     # 配置管理
│   ├── __init__.py
│   └── manager.py              # 配置管理器
├── crawlers/                   # 爬取器模块
│   ├── __init__.py
│   ├── rss_crawler.py          # RSS爬取器
│   └── x_crawler.py            # X/Twitter爬取器
├── analyzers/                  # 分析器模块
│   ├── __init__.py
│   ├── llm_analyzer.py         # LLM分析器 (MiniMax M2.1)
│   └── prompt_manager.py       # 提示词管理器
├── storage/                    # 存储模块
│   ├── __init__.py
│   └── data_manager.py         # 数据管理器
├── reporters/                  # 报告生成模块
│   └── __init__.py
└── utils/                      # 工具模块
    ├── __init__.py
    ├── logging.py              # 日志管理
    └── errors.py               # 错误处理
```

## 快速开始

### 1. 环境准备

本项目使用 `uv` 作为包管理器，推荐使用 Python 3.9+。

#### 安装 uv

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# 或使用 pip
pip install uv

# 或使用 Homebrew (macOS)
brew install uv
```

更多安装方式请参考 [uv 官方文档](https://docs.astral.sh/uv/getting-started/installation/)

### 2. 安装依赖

```bash
# 使用 uv 安装项目依赖（推荐）
uv pip install -e .

# 安装开发依赖（包含测试工具）
uv pip install -e ".[dev]"
```

**注意**: 项目已迁移到 `pyproject.toml` 管理依赖，不再使用 `requirements.txt`

### 3. 配置系统

复制环境变量模板并配置必要的 API 密钥：

```bash
cp .env.template .env
```

编辑 `.env` 文件：

```bash
# MiniMax API Key (从 https://platform.minimax.io 获取)
LLM_API_KEY=sk-api-your_minimax_api_key

# Telegram Bot 配置
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHANNEL_ID=your_channel_id

# API Server 鉴权（启用 --mode api-server 时必需）
API_KEY=your_api_key

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
- 所有授权用户都有相同的权限，可以执行所有命令（/run, /analyze, /status, /help）

### 4. 运行系统

支持三种运行模式：

- `once`：执行一次完整流程（爬取 + 分析 + 报告）
- `schedule`：定时调度模式（仅爬取），分析通过 Telegram `/analyze` 或 HTTP API 手动触发
- `api-server`：启动 FastAPI 服务，提供 `/health`、`/analyze` 接口，同时保留定时爬取与 Telegram 命令监听

```bash
# 一次性执行
uv run python -m crypto_news_analyzer.main --mode once

# 定时模式（仅爬取）
uv run python -m crypto_news_analyzer.main --mode schedule

# API 服务模式（默认监听 0.0.0.0:8080）
uv run python -m crypto_news_analyzer.main --mode api-server
```

可选 API 服务环境变量：

```bash
API_HOST=0.0.0.0
API_PORT=8080
```

### 5. 运行测试

```bash
# 运行所有测试
uv run pytest tests/

# 运行 MiniMax 集成测试
uv run pytest tests/test_minimax_llm_analyzer.py -v
```


## Telegram 命令功能

系统支持通过 Telegram Bot 命令进行交互式控制：

### 可用命令

- `/run` - 立即执行一次数据收集和分析任务
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

- **定时任务报告**: 自动发送到 `TELEGRAM_CHANNEL_ID` 指定的频道
- **手动触发报告**: 发送到用户触发命令的聊天窗口（私聊或群组）

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

## HTTP API（`--mode api-server`）

调用 `POST /analyze` 前，建议先阅读 [AI Analyze API Guide](docs/AI_ANALYZE_API_GUIDE.md)。
对 AI 代理尤其重要：该文档说明了真实必填参数、错误响应样例，以及正确的 `POST /analyze -> 轮询状态 -> 获取结果` 工作流。

### 认证方式

- 使用 `Authorization: Bearer <API_KEY>`
- `API_KEY` 来自环境变量

### 接口列表

- `GET /health`：健康检查
- `POST /analyze`：按小时窗口创建分析任务（返回 `202 Accepted`）
- `GET /analyze/{job_id}`：查询分析任务状态
- `GET /analyze/{job_id}/result`：获取分析任务最终结果

### 调用示例

```bash
curl -X POST "http://localhost:8080/analyze" \
  -H "Authorization: Bearer ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"hours": 24}'
```

### `POST /analyze` 请求与返回

- 请求体：`{"hours": <int>}`，`hours > 0`
- 成功时返回 `202 Accepted`
- 响应头：
  - `Location`：状态查询地址
  - `Retry-After`：建议轮询间隔（秒）
- 返回字段：
  - `success`：是否成功创建任务
  - `job_id`：分析任务 ID
  - `status`：初始状态（通常为 `queued`）
  - `time_window_hours`：实际使用的时间窗口（上限由配置控制，默认 24）
  - `status_url`：状态查询接口
  - `result_url`：结果获取接口

示例响应：

```json
{
  "success": true,
  "job_id": "analyze_job_xxx",
  "status": "queued",
  "time_window_hours": 24,
  "status_url": "/analyze/analyze_job_xxx",
  "result_url": "/analyze/analyze_job_xxx/result"
}
```

### 轮询任务状态

```bash
curl -H "Authorization: Bearer ${API_KEY}" \
  "http://localhost:8080/analyze/<job_id>"
```

状态接口返回：

- `queued`：任务已入队，等待执行
- `running`：分析进行中
- `completed`：分析完成，可读取结果
- `failed`：分析失败，可查看 `error`

### 获取最终分析结果

```bash
curl -H "Authorization: Bearer ${API_KEY}" \
  "http://localhost:8080/analyze/<job_id>/result"
```

- 若任务尚未完成，返回 `202`，提示 `Analyze job still queued/running`
- 若任务完成，返回最终 Markdown 报告与处理条目数

## 部署

### 本地运行

参考上面的"快速开始"部分。

### Railway 部署

详细的 Railway 部署指南请参考 [docs/RAILWAY_DEPLOYMENT.md](./docs/RAILWAY_DEPLOYMENT.md)

快速部署步骤：

1. 访问 [Railway](https://railway.app) 并登录
2. 选择 "Deploy from GitHub repo"
3. 在 Variables 中配置环境变量（LLM_API_KEY、TELEGRAM_BOT_TOKEN、TELEGRAM_CHANNEL_ID、TELEGRAM_AUTHORIZED_USERS、API_KEY）
4. Railway 会自动检测 Dockerfile 并部署

## 许可证

MIT License
