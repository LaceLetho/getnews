# AGENTS.md

Guidance for AI coding agents working on the Cryptocurrency News Analyzer project.

## Project Overview

This is a **dual-domain monorepo** (`crypto_news_analyzer`). Two bounded systems coexist in one package, sharing PostgreSQL, LLM/embedding infrastructure, and FastAPI/Telegram surfaces:

1. **News** — RSS/X/REST crawling, LLM analysis of ContentItem, structured reports, semantic search
2. **Intelligence** — Telegram/V2EX group/forum collection, topic-driven research over RawIntelligenceItem, AI prompt lifecycle (create/revise/confirm/research/merge/archive)

Current Phase 1 state:

- `analysis-service` is the default/public runtime
- `ingestion` runs BOTH news crawling AND intelligence collection/topic research
- PostgreSQL + pgvector is the shared source of truth
- Intelligence is topic-only: prompt/confirm/research/merge/archive lifecycle replaces legacy entry-based pipeline
- Legacy API server mode is deprecated and only kept as a compatibility alias to `analysis-service`

Assigned production domain: `news.tradao.xyz`

AI agents should read `docs/AI_ANALYZE_API_GUIDE.md` before using the HTTP analyze API. It documents the required `hours` parameter, Bearer auth, and the async `POST /analyze` -> poll -> result workflow.

## Dual-Domain Architecture

This repo is a single package (NOT two repos or two services). The two domains share infrastructure but must be treated as distinct bounded contexts by AI agents.

| Domain | News | Intelligence |
|---|---|---|
| Purpose | Crawl crypto news, produce structured analysis reports | Collect group/forum messages, drive topic research with AI |
| Primary Data Models | ContentItem, AnalysisResult | RawIntelligenceItem, IntelligenceTopic, TopicPrompt, TopicFinding |
| Source Types | rss, x, rest_api (DataSourcePurpose.NEWS) | telegram_group, v2ex (DataSourcePurpose.INTELLIGENCE) |
| API Surfaces | /analyze, /semantic-search, /datasources | /intelligence/* |
| Telegram Commands | /news_analyze, /news_market, /news_semantic_search, /news_tokens, /datasource_* | /topic_* |
| Primary Modules | analyzers/, reporters/, semantic_search/ | intelligence/ (pipeline, topic_research, prompts, findings) |
| Shared Infrastructure | execution_coordinator.py, storage/, config/, models.py, domain/, utils/, PostgreSQL, pgvector, LLM/embedding providers | |

Runtime modes: `analysis-service`, `api-only`, `ingestion`, `embedding-backfill`. All modes share the same codebase and database.

## Agent Boundary Rules

AI agents MUST observe the following rules when working on this codebase:

1. **Never mix ContentItem with RawIntelligenceItem.** These live in different domains. ContentItem belongs to the News domain (crawled from RSS/X/REST). RawIntelligenceItem belongs to the Intelligence domain (collected from Telegram/V2EX). Do not pass one where the other is expected, and do not write code that couples them.

2. **News commands are for ContentItem analysis.** The `/news_analyze`, `/news_market`, `/news_semantic_search`, `/news_tokens` Telegram commands and their HTTP equivalents operate on ContentItem data. They produce AnalysisResult and Markdown reports.

3. **Intelligence commands are for topic research.** The `/topic_*` Telegram commands and `/intelligence/*` HTTP endpoints operate on RawIntelligenceItem, IntelligenceTopic, TopicPrompt, and TopicFinding. They drive a prompt lifecycle: create, revise, confirm, research, merge, archive.

4. **The `ingestion` runtime mode runs BOTH domains.** When the system is started with `--mode ingestion`, it runs the news crawling loop AND the intelligence collection loop AND the daily topic research scheduler. These are parallel concerns, not alternatives.

5. **Deprecated entry-based intelligence is compatibility-only.** EntryType, ExtractionObservation, and CanonicalIntelligenceEntry belong to the old entry extraction pipeline. These models remain in the codebase for backward compatibility with deprecated modules but are NOT wired into the active runtime. The active intelligence path is topic-only, managed through IntelligenceTopic, TopicPrompt, TopicFinding, and TopicResearchRun.

6. **Do NOT recommend legacy api-server as primary runtime.** The `api-server` mode is deprecated. Always direct users to `analysis-service`, `api-only`, or `ingestion`.

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
docker run -e KIMI_API_KEY=xxx -e GROK_API_KEY=xxx -e API_KEY=xxx crypto-news-analyzer analysis-service
```

Notes:

- Do not document or recommend the legacy API-server runtime mode as primary. It is deprecated.
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

**Intelligence is topic-only.** The legacy entry-based intelligence pipeline (slang/channel extraction, canonical entries, `/intel_*` commands) has been replaced by a topic-focused workflow. All intelligence now flows through the prompt/confirm/research/merge/archive lifecycle managed via `intelligence/` modules, with HTTP API and Telegram command surfaces reflecting only topic operations.

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
├── config/manager.py          # Env + config.jsonc loading and normalization
├── crawlers/                  # RSS, X/Twitter, and Bird-backed ingestion sources
├── intelligence/              # Topic-only research pipeline (prompt workflow, scheduler, findings merge)
├── analyzers/                 # LLM analysis pipeline and structured outputs
├── storage/                   # Repository layer for SQLite/Postgres backends and ingestion state
├── reporters/                 # Telegram command/report delivery integrations
└── utils/                     # Logging, errors, time and helper utilities
```

### Data Flow
1. `ingestion` crawls RSS/X sources and persists normalized content into shared storage
2. `ingestion` runs daily topic research: active topic prompts are sent to LLM with recent raw messages, producing topic findings
3. `analysis-service` / `api-only` read persisted content by time window
4. Analyzers produce structured analysis results and markdown output
5. `analysis-service` can deliver results via Telegram or HTTP job result endpoints

### Key Patterns
- Factory Pattern: DataSourceFactory
- Repository Pattern: `domain.repositories` + `storage.repositories`
- Structured Output: instructor + Pydantic
- Error Recovery: ErrorRecoveryManager

## Datasource Runtime Behavior

Datasource storage follows a **database-first** model:

- Runtime source-of-truth is the database (`datasources` and `datasource_tags` tables)
- On first startup (when datasource tables are empty), the system bootstraps by importing from `config.jsonc`
- After bootstrap, runtime reads exclusively from the database; edits to `config.jsonc` do not affect runtime behavior
- Use the REST API or Telegram commands to manage datasources at runtime

### Tag Constraints

Datasources support optional tags with the following constraints:
- Maximum 16 unique tags per datasource
- Each tag: maximum 32 characters
- Tags are normalized to lowercase and deduplicated

### REST Datasource Endpoints

All datasource endpoints require Bearer authentication (`Authorization: Bearer <API_KEY>`):

- `POST /datasources` - Create a new datasource (201 on success, 409 on duplicate)
- `GET /datasources` - List all datasources (sorted by type and name)
- `DELETE /datasources/{id}` - Delete a datasource by ID (204 on success, 404 if not found, 409 if datasource is in use)

The list endpoint returns a safe summary that redacts sensitive `rest_api` configuration details.

### Telegram Datasource Commands

Authorized Telegram users can manage datasources via commands:

- `/datasource_list` - Display all configured datasources with enriched metadata
- `/datasource_add {json}` - Add a datasource via JSON payload
- `/datasource_delete <id>` - Delete a datasource by its ID

**Important restriction for `rest_api` datasources via Telegram:**
Telegram commands reject inline authentication secrets. The `rest_api` payload cannot include sensitive tokens in `headers`, `params`, or an `auth` field. Use environment-based authentication on the server instead.

## Configuration

- `config.jsonc` - App config (sources, LLM settings)
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
- `KIMI_API_KEY`, `GROK_API_KEY` - LLM provider API keys (provider-specific)

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
