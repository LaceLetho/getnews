---
name: crypto-news-http-api
description: Use when calling the Crypto News Analyzer HTTP API for async analysis jobs, semantic search, datasource management, or health checks from OpenClaw.
---

# Crypto News HTTP API Skill

This skill helps OpenClaw interact with the Crypto News Analyzer HTTP API for asynchronous news analysis, semantic search, datasource management, and operational monitoring.

## When to Use

Use this skill when you need to call `https://news.tradao.xyz` or a local deployment of the same API.

Typical triggers:

- Run asynchronous crypto news analysis over a time window
- Run asynchronous semantic search for a freeform topic query
- Poll an API job until it finishes and then fetch the final result
- Create, list, or delete datasources through the HTTP API
- Check service health before or after an API workflow

## Quick Reference

Authentication is Bearer token style: send `Authorization: Bearer <API_KEY>` with every request.

The core analysis workflow is asynchronous. `POST /analyze` creates a job and returns immediately. It does **not** return the final report. You must poll for status, then fetch the result.

Workflow: `POST /analyze` -> `GET /analyze/{job_id}` -> `GET /analyze/{job_id}/result`

Jobs move through these states: `queued`, `running`, `completed`, `failed`.

Semantic search follows the same async pattern. `POST /semantic-search` creates a job, returns `202 Accepted`, and includes `status_url`, `result_url`, plus a `Retry-After` header.

Semantic workflow: `POST /semantic-search` -> `GET /semantic-search/{job_id}` -> `GET /semantic-search/{job_id}/result`

Semantic search requires PostgreSQL with pgvector. SQLite runtime is unsupported.

For detailed guides, see:

- [Analyze Workflow Reference](references/analyze-workflow.md)
- [Semantic Search Reference](references/semantic-search.md)
- [Datasource Management Reference](references/datasource-management.md)
- [Operations and Maintenance Reference](references/operations-and-maintenance.md)

## Analyze Workflow

Create an analysis job by posting to `/analyze` with `hours` (how far back to look) and `user_id` (your agent identifier). The server responds with `202 Accepted`, a `job_id`, `status_url`, and `result_url`.

Poll the status endpoint until the job reaches `completed` or `failed`. Do not expect the analysis report in the initial POST response. Once completed, fetch the report from the result URL.

This pattern keeps long-running analysis work from blocking your client and lets you track progress transparently.

## Semantic Search

Create a semantic search job by posting to `/semantic-search` with `hours`, `query`, and `user_id`. The server responds with `202 Accepted`, a `job_id`, `status_url`, and `result_url`. Semantic search job IDs start with `semantic_search_job_`.

Poll the status endpoint until the job reaches `completed` or `failed`, then fetch the report from the result URL. Use the `status` field as the source of truth for lifecycle state; `success` becomes `true` only when the job is completed successfully.

Request rules:

- `hours` must be a positive integer
- `query` is required, trimmed, and capped at 300 characters
- `query` cannot be blank or whitespace-only
- `user_id` must match `^[A-Za-z0-9_-]{1,128}$`

Operational constraints:

- Semantic search is PostgreSQL-only and returns `503` when the backend does not support pgvector
- The API uses vector similarity over stored content embeddings and may combine that with keyword retrieval
- Query decomposition is capped at 4 subqueries
- Final retained results are capped at 200 unique items
- Embedding generation requires `OPENAI_API_KEY`; query planning and report synthesis require `KIMI_API_KEY` or `GROK_API_KEY`

The result body returns a Markdown report with `query`, `normalized_intent`, `matched_count`, `retained_count`, `time_window_hours`, and `report`. The report is structured for direct agent consumption with a normalized intent summary and cited signal blocks.

## Datasource Management

Configure news sources through the datasource API. Create sources with `POST /datasources`, list them with `GET /datasources`, and remove them with `DELETE /datasources/{id}`. All datasource routes require Bearer auth.

Tags help organize sources. Each datasource accepts up to 16 unique tags. Each tag is capped at 32 characters. Tags are normalized to lowercase and deduplicated automatically.

List responses include only safe summaries. For `rest_api` type datasources, secrets are redacted and counts replace raw credential fields. This prevents accidental credential exposure when reviewing configurations.

## Telegram Webhook

The webhook endpoint exists for maintainer-level Telegram integration. It is not the primary path for day-to-day operators. Regular users should interact through the API routes or Telegram slash commands instead.

When processing webhook updates, validate the `X-Telegram-Bot-Api-Secret-Token` header to confirm the request originates from Telegram.

## Endpoint Index

Supported HTTP routes:

- `GET /health` - Service health check
- `POST /analyze` - Create an analysis job (async, returns 202)
- `GET /analyze/{job_id}` - Check job status
- `GET /analyze/{job_id}/result` - Retrieve completed job results
- `POST /semantic-search` - Create a semantic search job (async, returns 202)
- `GET /semantic-search/{job_id}` - Check semantic search job status
- `GET /semantic-search/{job_id}/result` - Retrieve completed semantic search results
- `POST /datasources` - Create a datasource
- `GET /datasources` - List all datasources
- `DELETE /datasources/{id}` - Delete a datasource
- `POST /telegram/webhook` - Telegram webhook receiver

## Non-Goals

This skill does not cover:

- Telegram slash commands (use the Telegram bot directly)
- Autogenerated documentation routes (`/docs`, `/redoc`, `/openapi.json`)
- Deprecated compatibility aliases (`api-server`, `crypto-news-api`)
- Direct embedding backfill operations beyond pointing you to the documented command

These surfaces exist but are intentionally excluded from this API-focused skill.

## Updating

Keep this skill aligned with the live HTTP routes in `api_server.py`, the AI Analyze API Guide at `docs/AI_ANALYZE_API_GUIDE.md`, and the semantic search guide at `docs/SEMANTIC_SEARCH_API_GUIDE.md`.

When documentation disagrees with implementation, trust the code and tests over prose docs. Source precedence: code and tests first, then reference files, then guides.
