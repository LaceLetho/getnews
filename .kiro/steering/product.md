---
inclusion: auto
description: Cryptocurrency news analysis tool product overview and core features
---

# Product Overview

Cryptocurrency news analysis tool that automates collection and intelligent analysis of crypto-related content from multiple sources (RSS feeds, X/Twitter). Uses LLM (Grok) to analyze and categorize content, generating structured Markdown reports delivered via Telegram Bot.

## Core Features

- Multi-source data collection (RSS, X/Twitter via Bird CLI)
- AI-powered content analysis and categorization using Grok models
- Automated Markdown report generation
- Telegram Bot integration for delivery and interactive commands
- Scheduled execution with Railway cloud deployment support
- Market snapshot generation for context

## Key Categories

- Whale movements (大户动向)
- Interest rate events (利率事件)
- US regulatory policy (美国政府监管政策)
- Industry revelations (真相)
- Innovative products (新产品)

## Execution Modes

- One-time execution: `--mode once`
- Scheduled mode: `--mode schedule`
- Telegram commands: `/run`, `/status`, `/help`
