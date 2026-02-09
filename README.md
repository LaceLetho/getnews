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
- 🎯 **智能分类**: 支持大户动向、利率事件、监管政策、安全事件等多种分类

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
pip install -r requirements.txt
```

### 2. 配置系统

创建 `.env` 文件并配置必要的 API 密钥：

```bash
# MiniMax API Key (从 https://platform.minimax.io 获取)
LLM_API_KEY=sk-api-your_minimax_api_key

# Telegram Bot 配置
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHANNEL_ID=your_channel_id

# X/Twitter 认证 (可选)
X_CT0=your_X_CT0
X_AUTH_TOKEN=your_X_AUTH_TOKEN
```

### 3. 运行系统

```bash
python -m crypto_news_analyzer.main
```

### 4. 运行测试

```bash
# 运行所有测试
python -m pytest tests/

# 运行 MiniMax 集成测试
python -m pytest tests/test_minimax_llm_analyzer.py -v
```

## MiniMax M2.1 集成

本系统集成了 MiniMax M2.1 大语言模型进行智能内容分析：

### 支持的分类类别

- **大户动向**: 巨鲸资金流动和态度变化
- **利率事件**: 美联储相关的利率政策事件  
- **美国政府监管政策**: 美国政府对加密货币的监管政策变化
- **安全事件**: 影响较大的安全相关事件
- **新产品**: KOL提及的真正创新产品
- **市场新现象**: 重要的市场新趋势和变化

### API 配置

1. 访问 [MiniMax 平台](https://platform.minimax.io)
2. 创建账户并生成 API Key
3. 将 API Key 添加到 `.env` 文件中

详细的集成文档请参考 `docs/integration/minimax_integration_summary.md`

## 配置说明

系统通过 `config.json` 文件进行配置，主要包括：

- **execution_interval**: 执行间隔（秒）
- **time_window_hours**: 时间窗口（小时）
- **storage**: 存储配置
- **auth**: 认证信息
- **llm_config**: LLM模型配置
- **rss_sources**: RSS订阅源列表
- **x_sources**: X/Twitter信息源列表

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

待开发功能请参考 `.kiro/specs/crypto-news-analyzer/tasks.md`

## 许可证

MIT License