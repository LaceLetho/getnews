# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **Cryptocurrency News Analyzer** - an automated Python system that collects crypto-related news from RSS feeds and X/Twitter, analyzes content using LLM (Grok/MiniMax), and delivers structured reports via Telegram Bot.

## Common Commands

### Package Manager

This project uses `uv` as the package manager (not pip):

```bash
# Install dependencies
uv pip install -e .

# Install with dev dependencies
uv pip install -e ".[dev]"

# Run Python scripts
uv run python -m crypto_news_analyzer.main
```

### Running the Application

```bash
# One-time execution mode
uv run python -m crypto_news_analyzer.main --mode once

# Scheduled mode (runs continuously with internal scheduler)
uv run python -m crypto_news_analyzer.main --mode schedule

# Or via the wrapper script
python run.py --mode once
```

### Testing

```bash
# Run all tests
uv run pytest tests/

# Run with coverage
uv run pytest tests/ -v --cov=crypto_news_analyzer

# Run specific test file
uv run pytest tests/test_llm_analyzer.py -v

# Run property-based tests
uv run pytest tests/test_data_storage_properties.py -v
```

### Code Quality

```bash
# Format code
uv run black crypto_news_analyzer/ tests/

# Type checking
uv run mypy crypto_news_analyzer/

# Linting
uv run flake8 crypto_news_analyzer/
```

## Architecture

### Module Organization

```
crypto_news_analyzer/
├── main.py                    # CLI entry point
├── execution_coordinator.py   # MainController orchestrates the workflow
├── models.py                  # Data models (ContentItem, AnalysisResult, etc.)
├── config/
│   └── manager.py             # Configuration management
├── crawlers/                  # Data collection
│   ├── rss_crawler.py         # RSS feed crawling
│   ├── x_crawler.py           # X/Twitter via Bird CLI
│   ├── bird_wrapper.py        # Bird CLI integration
│   └── data_source_factory.py # Factory for data sources
├── analyzers/                 # LLM analysis
│   ├── llm_analyzer.py        # Grok/MiniMax integration
│   ├── prompt_manager.py      # Prompt templates
│   ├── category_parser.py     # Dynamic category parsing
│   └── market_snapshot_service.py  # Market context generation
├── storage/
│   └── data_manager.py        # SQLite persistence & deduplication
├── reporters/
│   ├── report_generator.py    # Markdown report generation
│   ├── telegram_sender.py     # Telegram Bot integration
│   └── telegram_command_handler.py # Bot commands (/run, /status, etc.)
└── utils/
    ├── logging.py             # Structured logging
    ├── errors.py              # Error recovery framework
    └── timezone_utils.py      # UTC timezone handling
```

### Data Flow

1. **Crawlers** collect from RSS/X sources → `List[ContentItem]`
2. **Storage** deduplicates and persists items to SQLite
3. **Analyzers** send content to LLM API (Grok) → `List[AnalysisResult]`
4. **Reporters** generate Markdown reports from analyzed results
5. **Telegram Bot** sends reports to configured channel/chat

### Key Design Patterns

- **Factory Pattern**: `DataSourceFactory` creates appropriate crawlers based on source type
- **Plugin System**: Data sources are dynamically loaded via the factory
- **Structured Output**: Uses `instructor` library with Pydantic for typed LLM responses
- **Error Recovery**: Centralized error handling with `ErrorRecoveryManager`

## Configuration

### Files

- `config.json` - Application configuration (sources, LLM settings, rate limits)
- `.env` - Secrets and API keys (copy from `.env.template`)

### Required Environment Variables

```bash
LLM_API_KEY=          # For content analysis (xAI/OpenAI/MiniMax compatible)
GROK_API_KEY=         # For market snapshot generation
TELEGRAM_BOT_TOKEN=   # Telegram Bot API token
TELEGRAM_CHANNEL_ID=  # Target channel for scheduled reports
TELEGRAM_AUTHORIZED_USERS=  # Comma-separated user IDs or @usernames
```

### Optional Environment Variables

```bash
X_CT0=                # X/Twitter auth (only if using X sources)
X_AUTH_TOKEN=         # X/Twitter auth (only if using X sources)
TIME_WINDOW_HOURS=24  # How far back to fetch content
EXECUTION_INTERVAL=3600  # Seconds between scheduled runs
LOG_LEVEL=INFO
```

## External Dependencies

### Bird CLI

X/Twitter crawling requires the Bird CLI tool (installed via npm):

```bash
npm install -g @laceletho/bird@latest
```

Bird CLI requires authentication via `~/.bird/config.json` or environment variables.

### LLM API

The system uses xAI Grok API (OpenAI-compatible) for content analysis:
- Model: `grok-4-1-fast-reasoning` (configurable in config.json)
- Uses structured output with Pydantic models via `instructor`

## Deployment

### Local Development

Use `uv run` commands as shown above.

### Docker

```bash
# Build image
docker build -t crypto-news-analyzer .

# Run once
docker run -e LLM_API_KEY=xxx -e TELEGRAM_BOT_TOKEN=xxx crypto-news-analyzer once

# Run scheduled
docker run -e LLM_API_KEY=xxx -e EXECUTION_INTERVAL=3600 crypto-news-analyzer schedule
```

### Railway (Production)

- Deployment is configured via `railway.toml` and `Dockerfile`
- Environment variables set in Railway Dashboard (not .env file)
- Runs in scheduled mode by default
- Uses volumes for persistent SQLite storage

## Testing Strategy

The project uses multiple testing approaches:

1. **Unit Tests** - Component-level testing (`test_*.py`)
2. **Property-Based Tests** - Using Hypothesis for robustness (`test_*_properties.py`)
3. **Integration Tests** - Testing component interactions

Test files follow naming convention:
- `test_<component>_unit.py` - Unit tests
- `test_<component>_properties.py` - Property-based tests
- `test_<component>_pbt.py` - Additional property-based tests

## Common Tasks

### Adding a New RSS Source

Edit `config.json` and add to `rss_sources` array:

```json
{
  "name": "Source Name",
  "url": "https://example.com/feed.xml",
  "description": "Description"
}
```

### Adding a New Category

Categories are dynamically configured in `config.json` under classification settings. The `CategoryParser` and `DynamicClassificationManager` handle dynamic category definitions.

### Debugging Telegram Bot

Check `logs/` directory for execution logs. The bot uses `python-telegram-bot` v20+ with async handlers.

## Important Notes

- Always use `uv` for Python operations, not raw `python` or `pip`
- Timezone handling: All datetimes are stored in UTC
- Database: SQLite at `./data/crypto_news.db` (gitignored)
- Logs: Written to `./logs/` directory
- Prompts: Stored in `./prompts/` directory as Markdown files

## How to debug
The ./DEBUG.md explained how to do debug online.