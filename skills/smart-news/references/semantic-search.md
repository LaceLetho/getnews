# Semantic Search Reference

This document describes the asynchronous semantic search HTTP API for AI agents and operators.

## Authentication

All semantic search endpoints require Bearer token authentication:

```
Authorization: Bearer <API_KEY>
```

Requests without a valid token receive HTTP 401.

## Overview

Semantic search is asynchronous and follows the same three-step pattern as `/analyze`:

1. **Create**: `POST /semantic-search` with `hours`, `query`, and `user_id`
2. **Poll**: `GET /semantic-search/{job_id}` until the job reaches a terminal state
3. **Fetch**: `GET /semantic-search/{job_id}/result` to retrieve the final Markdown report

The POST response returns immediately. It does not include the final report.

## Request Contract

### Endpoint

```
POST /semantic-search
```

### Required Parameters

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `hours` | integer | `> 0` | Search time window in hours. Values below server minimum return HTTP 400. Values above server maximum are capped. |
| `query` | string | non-blank, max 300 chars | Natural-language topic query for semantic retrieval. |
| `user_id` | string | `^[A-Za-z0-9_-]{1,128}$` | Requesting user identifier. Server trims whitespace before validation. |

### Success Response (HTTP 202 Accepted)

The response body includes:

- `success`
- `job_id`
- `status`
- `query`
- `normalized_intent`
- `matched_count`
- `retained_count`
- `time_window_hours`
- `status_url`
- `result_url`

Response headers include:

- `Location`
- `Retry-After`

Job IDs use the prefix `semantic_search_job_`.

## Job Status Contract

### Endpoint

```
GET /semantic-search/{job_id}
```

### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `success` | boolean | `true` only when `status` is `completed` |
| `job_id` | string | The semantic search job identifier |
| `status` | string | Current state: `queued`, `running`, `completed`, or `failed` |
| `query` | string | Original normalized query |
| `normalized_intent` | string | LLM-normalized search intent |
| `matched_count` | integer | Total matched items before final retention |
| `retained_count` | integer | Final retained items used for synthesis |
| `time_window_hours` | integer | Search time window after server caps |
| `created_at` | string (ISO 8601) | Job creation timestamp |
| `started_at` | string (ISO 8601) or null | When execution began |
| `completed_at` | string (ISO 8601) or null | When execution finished |
| `error` | string or null | Error message if failed |
| `result_available` | boolean | `true` when status is `completed` or `failed` |

Use the `status` field as the source of truth, not the `success` boolean.

## Result Contract

### Endpoint

```
GET /semantic-search/{job_id}/result
```

### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `success` | boolean | `true` only when `status` is `completed` |
| `job_id` | string | The semantic search job identifier |
| `status` | string | Terminal state: `completed` or `failed` |
| `query` | string | Original query |
| `normalized_intent` | string | LLM-normalized search intent |
| `matched_count` | integer | Total matched items |
| `retained_count` | integer | Final retained items |
| `report` | string | Markdown semantic search report |
| `time_window_hours` | integer | Search time window |
| `error` | string or null | Error text when failed |

## Report Structure

The Markdown report follows this structure:

```markdown
# Topic Search Report

- Normalized intent: ...
- Original query: ...
- Time window: N hours
- Matched items: N
- Retained items: N

## Key Signals

### Signal 1
Concise synthesized paragraph.
Sources: [Source Name](https://example.com/article)
```

The live service currently returns the headings in Chinese (`# 主题检索报告`, `## 关键信号`). Treat the exact report string as implementation-defined content and preserve it as returned.

## Limits and Dependencies

- Requires PostgreSQL with pgvector; SQLite is unsupported
- Query length is capped at 300 characters
- Query decomposition is capped at 4 subqueries
- Final retained results are capped at 200 unique items
- `OPENAI_API_KEY` is required for embedding generation
- `KIMI_API_KEY` or `GROK_API_KEY` is required for query planning and report synthesis

## Telegram and Backfill Notes

- Telegram command: `/semantic_search <hours> <topic>`
- Historical embedding backfill command:

```bash
uv run python -m crypto_news_analyzer.main --mode embedding-backfill --config ./config.jsonc --batch-size 100
```

Optional: add `--limit 1000` to process only part of the backlog.

## Updating

Canonical sources for this reference:

1. `crypto_news_analyzer/api_server.py`
2. `crypto_news_analyzer/models.py`
3. `crypto_news_analyzer/domain/models.py`
4. `docs/SEMANTIC_SEARCH_API_GUIDE.md`
5. `tests/test_api_server_semantic_search.py`
6. `tests/test_semantic_search_contracts.py`

When sources disagree, trust code and tests over prose.
