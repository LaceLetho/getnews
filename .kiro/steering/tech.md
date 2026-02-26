---
inclusion: auto
---

# Tech Stack

## Language & Runtime

- Python 3.9+
- Package manager: `uv` (required for all Python operations)

## Core Dependencies

- `requests`, `feedparser`, `beautifulsoup4` - Data collection
- `openai` SDK - Grok API integration (OpenAI-compatible)
- `instructor`, `pydantic` - Structured LLM outputs
- `python-telegram-bot` - Telegram Bot integration
- `httpx[socks]`, `aiohttp` - HTTP clients with proxy support
- `pytest`, `hypothesis` - Testing framework with property-based testing

## External Tools

- Bird CLI (`bird`) - X/Twitter content scraping
- Grok API - LLM analysis (grok-4-1-fast-reasoning model)
- Telegram Bot API - Report delivery and commands

## Build System

Project uses `pyproject.toml` for dependency management (no `requirements.txt`).

### Common Commands

```bash
# Install dependencies
uv pip install -e .

# Install with dev dependencies
uv pip install -e ".[dev]"

# Run application
uv run python -m crypto_news_analyzer.main --mode once
uv run python -m crypto_news_analyzer.main --mode schedule

# Run tests
uv run pytest tests/
uv run pytest tests/ -v --cov=crypto_news_analyzer

# Run specific test file
uv run pytest tests/test_minimax_llm_analyzer.py -v
```

## Configuration

- Environment variables: `.env` (copy from `.env.template`)
- Application config: `config.json`
- Required env vars: `LLM_API_KEY`, `GROK_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHANNEL_ID`
- Optional: `X_CT0`, `X_AUTH_TOKEN` (for X/Twitter)

## Deployment

- Local: Direct Python execution via `uv`
- Cloud: Railway platform with Dockerfile
- Storage: SQLite database at `./data/crypto_news.db`
