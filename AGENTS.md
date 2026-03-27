# AGENTS.md

Guidance for AI coding agents working on the Cryptocurrency News Analyzer project.

## Project Overview

Automated Python system collecting crypto news from RSS/X, analyzing with LLM (Grok/MiniMax), delivering reports via Telegram Bot.

Assigned production domain: `news.tradao.xyz`

AI agents should read `docs/AI_ANALYZE_API_GUIDE.md` before using the HTTP analyze API. It documents the required `hours` parameter, Bearer auth, and the async `POST /analyze` -> poll -> result workflow.

## Build/Lint/Test Commands

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

# Run once (uses .env file for configuration)
uv run python -m crypto_news_analyzer.main --mode once

# Run scheduled
uv run python -m crypto_news_analyzer.main --mode schedule

# Docker build/run
docker build -t crypto-news-analyzer .
docker run -e LLM_API_KEY=xxx crypto-news-analyzer once
```

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

### Module Organization
```
crypto_news_analyzer/
├── main.py                    # CLI entry point
├── execution_coordinator.py   # MainController orchestrates workflow
├── models.py                  # Data models (ContentItem, AnalysisResult)
├── config/manager.py          # Configuration management
├── crawlers/                  # Data collection (RSS, X/Twitter)
├── analyzers/                 # LLM analysis (Grok/MiniMax)
├── storage/                   # SQLite persistence
├── reporters/                 # Telegram bot integration
└── utils/                     # Logging, errors, timezone
```

### Data Flow
1. Crawlers → ContentItem[]
2. Storage → deduplicate & persist
3. Analyzers → LLM → AnalysisResult[]
4. Reporters → Markdown report
5. Telegram Bot → send to channel

### Key Patterns
- Factory Pattern: DataSourceFactory
- Plugin System: Dynamic data sources
- Structured Output: instructor + Pydantic
- Error Recovery: ErrorRecoveryManager

## Configuration

- `config.json` - App config (sources, LLM settings)
- `.env` - Secrets (copy from `.env.template`)

Required env vars:
- LLM_API_KEY, GROK_API_KEY
- TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL_ID
- TELEGRAM_AUTHORIZED_USERS

## Important Notes

- Always use `uv`, never raw `python` or `pip`
- All datetimes stored in UTC
- SQLite at `./data/crypto_news.db`
- Logs in `./logs/`
- Prompts in `./prompts/`
- Use `__post_init__` for dataclass validation
- X/Twitter requires Bird CLI: `npm install -g @laceletho/bird`
