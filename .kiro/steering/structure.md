---
inclusion: auto
description: Project directory layout, module organization, and data flow architecture
---

# Project Structure

## Directory Layout

```
crypto_news_analyzer/          # Main package
├── __init__.py
├── main.py                    # Entry point
├── models.py                  # Data models (ContentItem, AnalysisResult, etc.)
├── execution_coordinator.py   # Orchestrates execution flow
├── config/                    # Configuration management
│   └── manager.py
├── crawlers/                  # Data collection
│   ├── rss_crawler.py
│   └── x_crawler.py           # Uses Bird CLI
├── analyzers/                 # LLM analysis
│   ├── llm_analyzer.py        # Grok integration
│   └── prompt_manager.py
├── storage/                   # Data persistence
│   └── data_manager.py
├── reporters/                 # Report generation
│   └── __init__.py
└── utils/                     # Utilities
    ├── logging.py
    └── errors.py

tests/                         # Test suite
├── test_*.py                  # Unit tests
└── property_tests/            # Property-based tests

prompts/                       # LLM prompt templates
├── analysis_prompt.md
└── market_summary_prompt.md

data/                          # Runtime data (gitignored)
└── crypto_news.db

.kiro/                         # Kiro IDE configuration
├── specs/                     # Feature specs
└── steering/                  # Project guidelines
```

## Module Organization

- `config/`: Centralized configuration loading from `config.json` and `.env`
- `crawlers/`: Source-specific data collection (RSS, X/Twitter)
- `analyzers/`: LLM-powered content analysis and categorization
- `storage/`: SQLite-based data persistence and deduplication
- `reporters/`: Markdown report generation
- `utils/`: Cross-cutting concerns (logging, error handling)

## Key Files

- `main.py`: CLI entry point with mode selection
- `execution_coordinator.py`: MainController orchestrates crawl → analyze → report → send
- `models.py`: All dataclasses (ContentItem, AnalysisResult, CrawlResult, etc.)
- `config.json`: Application configuration (sources, LLM settings, rate limits)
- `.env`: Secrets and API keys (never commit)

## Data Flow

1. Crawlers collect from RSS/X sources → ContentItem list
2. Storage deduplicates and persists items
3. Analyzers send to Grok for categorization → AnalysisResult list
4. Reporters generate Markdown from results
5. Telegram Bot sends report to channel/chat
