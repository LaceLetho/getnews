# 加密货币新闻分析工具

一个自动化系统，用于从多个信息源收集加密货币相关新闻和社交媒体内容，并通过大模型进行智能分析和分类，生成结构化的新闻快讯报告。

## 功能特性

- 🔄 **多源数据收集**: 支持RSS订阅和X/Twitter内容爬取
- 🤖 **智能分析**: 使用 MiniMax M2.1 大语言模型进行内容分析和分类
- 📊 **结构化报告**: 生成Markdown格式的分析报告
- 📱 **自动发送**: 通过Telegram Bot自动发送报告
- ⏰ **定时调度**: 支持定时自动执行
- 🔧 **配置驱动**: 通过配置文件管理所有信息源
- 🛡️ **容错设计**: 完善的错误处理和恢复机制
- 🎯 **智能分类**: 支持大户动向、利率事件、监管政策、真相揭露等多种分类
- ☁️ **云端部署**: 支持部署到 Railway 平台

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

### 1. 安装依赖

```bash
# 使用 uv（推荐）
uv pip install -r requirements.txt

# 或使用 pip
pip install -r requirements.txt
```

### 2. 配置系统

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
- 所有授权用户都有相同的权限，可以执行所有命令（/run, /status, /help）

### 3. 运行系统

```bash
# 使用 uv（推荐）
uv run python -m crypto_news_analyzer.main

# 或直接运行
python -m crypto_news_analyzer.main
```

### 4. 运行测试

```bash
# 运行所有测试
uv run pytest tests/

# 运行 MiniMax 集成测试
uv run pytest tests/test_minimax_llm_analyzer.py -v
```

## MiniMax M2.1 集成

本系统集成了 MiniMax M2.1 大语言模型进行智能内容分析：

### 支持的分类类别

- **大户动向**: 巨鲸资金流动和态度变化
- **利率事件**: 美联储相关的利率政策事件  
- **美国政府监管政策**: 美国政府对加密货币的监管政策变化
- **真相**: 揭露行业内幕、利益关系和不为人知的真相
- **新产品**: KOL提及的真正创新产品
- **市场新现象**: 重要的市场新趋势和变化

### API 配置

1. 访问 [MiniMax 平台](https://platform.minimax.io)
2. 创建账户并生成 API Key
3. 将 API Key 添加到 `.env` 文件中

详细的集成文档请参考 `docs/integration/minimax_integration_summary.md`

## Telegram 命令功能

系统支持通过 Telegram Bot 命令进行交互式控制：

### 可用命令

- `/run` - 立即执行一次数据收集和分析任务
- `/status` - 查询系统运行状态
- `/help` - 显示帮助信息

### 授权机制

系统使用基于用户的授权机制：

1. **私聊授权**: 授权用户可以在与 bot 的私聊中执行命令
2. **群组授权**: 授权用户可以在群组中执行命令（基于用户 ID，而非群组 ID）
3. **统一权限**: 所有授权用户拥有相同的权限，可以执行所有命令

### 报告发送规则

- **定时任务报告**: 自动发送到 `TELEGRAM_CHANNEL_ID` 指定的频道
- **手动触发报告**: 发送到用户触发命令的聊天窗口（私聊或群组）

### 配置授权用户

在 `.env` 文件中配置 `TELEGRAM_AUTHORIZED_USERS`：

```bash
# 支持用户ID和用户名混合格式
TELEGRAM_AUTHORIZED_USERS=123456789,@user1,987654321,@user2
```

### 速率限制

为防止滥用，系统实施了速率限制：
- 每小时最多执行命令次数（默认：60次）
- 命令冷却时间（默认：5分钟）

可在 `config.json` 的 `telegram_commands.command_rate_limit` 中调整。

## 配置说明

系统通过 `config.json` 文件进行配置，主要包括：

- **execution_interval**: 执行间隔（秒）
- **time_window_hours**: 时间窗口（小时）
- **storage**: 存储配置
- **auth**: 认证信息
- **llm_config**: LLM模型配置
- **rss_sources**: RSS订阅源列表
- **x_sources**: X/Twitter信息源列表

## 部署

### 本地运行

参考上面的"快速开始"部分。

### Railway 部署

详细的 Railway 部署指南请参考 [RAILWAY_DEPLOYMENT.md](./RAILWAY_DEPLOYMENT.md)

快速部署步骤：

1. 访问 [Railway](https://railway.app) 并登录
2. 选择 "Deploy from GitHub repo"
3. 在 Variables 中配置环境变量（LLM_API_KEY、TELEGRAM_BOT_TOKEN、TELEGRAM_CHANNEL_ID）
4. Railway 会自动检测 Dockerfile 并部署

## 开发状态

当前项目处于开发阶段，已完成：

✅ 项目结构搭建  
✅ 配置管理系统  
✅ 日志系统  
✅ 错误处理框架  
✅ RSS 爬取器  
✅ X/Twitter 爬取器  
✅ MiniMax M2.1 LLM 分析器  
✅ 数据存储管理  
✅ 完整的测试套件  
✅ Railway 部署支持  

待开发功能请参考 `.kiro/specs/crypto-news-analyzer/tasks.md`

## 许可证

MIT License