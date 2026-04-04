# AGENTS.md

Guidance for AI coding agents working on the Cryptocurrency News Analyzer project.

## Project Overview

Automated Python system collecting crypto news from RSS/X/REST sources, persisting to PostgreSQL, and exposing analysis through a public analysis service plus Telegram Bot.

Current Phase 1 state:

- `analysis-service` is the default/public runtime
- `ingestion` is the private crawler/scheduler runtime
- PostgreSQL + pgvector is the shared source of truth
- `api-server` is deprecated and only kept as a compatibility alias to `analysis-service`

Assigned production domain: `news.tradao.xyz`

AI agents should read `docs/AI_ANALYZE_API_GUIDE.md` before using the HTTP analyze API. It documents the required `hours` parameter, Bearer auth, and the async `POST /analyze` -> poll -> result workflow.

## Build/Lint/Test Commands

### 前置检查
在编写代码或运行测试前，先检查以下工具是否已安装。如果缺少任何工具，请立即安装：

- `uv` - Python 包管理和运行工具（必需，替代 pip/python）
- `pytest` - 测试框架
- `black` - 代码格式化
- `mypy` - 类型检查
- `flake8` - 代码风格检查

安装命令示例：
```bash
# 安装 uv (如果未安装)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 使用 uv 安装 Python 开发依赖
uv pip install -e ".[dev]"
```

### 常用命令

```bash
# Install dependencies
uv pip install -e ".[dev]"

# Run all tests
uv run pytest tests/

# Run single test file
uv run pytest tests/test_llm_analyzer.py -v

# Run single test function
uv run pytest tests/test_llm_analyzer.py::test_analyze_content -v

# Run specific test class
uv run pytest tests/test_llm_analyzer.py::TestLLMAnalyzer -v

# Run with coverage
uv run pytest tests/ -v --cov=crypto_news_analyzer

# Run property-based tests
uv run pytest tests/test_data_storage_properties.py -v

# Format code
uv run black crypto_news_analyzer/ tests/

# Type checking
uv run mypy crypto_news_analyzer/

# Linting
uv run flake8 crypto_news_analyzer/
```

## Code Style Guidelines

### Imports
- Standard library first (json, logging, os)
- Third-party next (requests, pydantic)
- Local imports last, use relative imports (from ..models import)
- Group with blank lines between sections

### Formatting
- **Black**: line-length 100, target Python 3.9+
- Use double quotes for strings
- Trailing commas in multi-line structures

### Types
- Use type hints for function parameters and returns
- from typing import List, Dict, Any, Optional, Union
- Use Optional[str] = None for optional params

### Naming
- snake_case for variables, functions
- CamelCase for classes
- UPPER_CASE for constants/env vars
- Private methods: _leading_underscore

### Docstrings
- Module docstrings explain purpose
- Class docstrings describe behavior
- Function docstrings include Args, Returns, Raises

### Error Handling
- Use custom exceptions from utils.errors
- Base exception: CryptoNewsAnalyzerError
- Specific types: NetworkError, AuthError, ConfigError, APIError
- Always log errors with logger = logging.getLogger(__name__)

## Application Commands

```bash
# Install Bird CLI (required for X/Twitter crawling)
npm install -g @laceletho/bird

# Run public analysis service (uses .env file for configuration)
uv run python -m crypto_news_analyzer.main --mode analysis-service

# Run isolated API service
uv run python -m crypto_news_analyzer.main --mode api-only

# Run private ingestion service
uv run python -m crypto_news_analyzer.main --mode ingestion

# Docker build and start
docker build -t crypto-news-analyzer .
docker run -e LLM_API_KEY=xxx -e API_KEY=xxx crypto-news-analyzer analysis-service
```

Notes:

- Do not document or recommend `--mode api-server` as the primary runtime. It is deprecated.
- Production Railway routing is service-name driven via `docker-entrypoint.sh`.

## Online Debugging & Logs

**Use the `crypto-news-debug` skill for production debugging:**

Load this skill to debug Railway deployments via GraphQL API:
- Check deployment status and logs
- Query environment variables
- Redeploy/restart services
- Filter error logs

```bash
# Load skill: skill crypto-news-debug
```

This skill provides curl commands for Railway GraphQL API debugging without CLI access.

## Architecture

The repository is split-service-first. Railway deploys two long-lived app services that share one PostgreSQL/pgvector database:

- `crypto-news-analysis` -> `analysis-service`
- `crypto-news-ingestion` -> `ingestion`

`api-only` remains available as an isolated API runtime for local or dedicated deployments.

### Module Organization
```
crypto_news_analyzer/
├── main.py                    # Retained runtime entrypoint and mode dispatch
├── execution_coordinator.py   # MainController for analysis-service and ingestion flows
├── api_server.py              # FastAPI app factory and analyze job endpoints
├── models.py                  # Shared data/config/result models
├── config/manager.py          # Env + config.json loading and normalization
├── crawlers/                  # RSS, X/Twitter, and Bird-backed ingestion sources
├── analyzers/                 # LLM analysis pipeline and structured outputs
├── storage/                   # Repository layer for SQLite/Postgres backends and ingestion state
├── reporters/                 # Telegram command/report delivery integrations
└── utils/                     # Logging, errors, time and helper utilities
```

### Data Flow
1. `ingestion` crawls RSS/X sources and persists normalized content into shared storage
2. `analysis-service` / `api-only` read persisted content by time window
3. Analyzers produce structured analysis results and markdown output
4. `analysis-service` can deliver results via Telegram or HTTP job result endpoints

### Key Patterns
- Factory Pattern: DataSourceFactory
- Repository Pattern: `domain.repositories` + `storage.repositories`
- Structured Output: instructor + Pydantic
- Error Recovery: ErrorRecoveryManager

## Configuration

- `config.json` - App config (sources, LLM settings)
- `.env` - Secrets (copy from `.env.template`)
- `docs/RAILWAY_DEPLOYMENT.md` - Current split-service deployment reference
- `migrations/postgresql/README.md` - Postgres cutover/backfill reference

### Shared env vars

- `DATABASE_URL` - shared PostgreSQL/pgvector connection string when `storage.backend=postgres`
- `CONFIG_PATH` - config file path override
- `LOG_LEVEL` - runtime logging verbosity

### `analysis-service` / `api-only`

- `API_KEY` - required Bearer auth secret for the HTTP analyze API
- `API_HOST`, `API_PORT` - API bind address/port
- `LLM_API_KEY` plus optional provider-specific keys such as `GROK_API_KEY` / `KIMI_API_KEY`

### `analysis-service` only

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHANNEL_ID`
- `TELEGRAM_AUTHORIZED_USERS`

### `ingestion`

- `EXECUTION_INTERVAL` - crawl loop interval
- `TIME_WINDOW_HOURS` - ingestion time window control
- `X_CT0`, `X_AUTH_TOKEN` - X/Twitter crawl credentials when that source is enabled

## Important Notes

- Always use `uv`, never raw `python` or `pip`
- All datetimes stored in UTC
- Production split-service deployments use a shared PostgreSQL/pgvector database as the source of truth
- Logs in `./logs/`
- Prompts in `./prompts/`
- Use `__post_init__` for dataclass validation
- X/Twitter requires Bird CLI: `npm install -g @laceletho/bird`
- For Railway production debugging, use the `crypto-news-debug` skill instead of guessing deployment state
