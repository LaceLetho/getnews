# Semantic Search API Guide

This document is for AI agents and developers that need to call the semantic search HTTP API.

## Read This First

- Production domain: `https://news.tradao.xyz`
- Auth is required: `Authorization: Bearer <API_KEY>`
- Semantic search is **asynchronous** (same pattern as `/analyze`)
- You must poll status and then fetch the result
- `POST /semantic-search` requires `hours`, `query`, and `user_id`
- This feature requires **PostgreSQL** backend; SQLite is not supported

## What is Semantic Search?

Unlike the category-based `/analyze` endpoint, semantic search:
- Accepts a freeform natural language query (e.g., "Bitcoin ETF approvals and institutional adoption")
- Uses LLM to decompose the query into subqueries (max 4)
- Performs vector similarity search over `title + content` using pgvector
- Returns a compact, cited report with source URLs
- Caps results at 200 unique items globally

## Endpoint Contract

### 1. Create semantic search job

`POST /semantic-search`

Required JSON body:

```json
{"hours": 24, "query": "Bitcoin ETF approvals", "user_id": "my_agent_01"}
```

Rules:

- `hours` is required (positive integer)
- `query` is required (max 300 characters)
- `query` cannot be blank or whitespace-only
- `user_id` is required
- `user_id` must match `^[A-Za-z0-9_-]{1,128}$`
- Results are capped at 200 unique items after deduplication

Expected success response:

- HTTP `202 Accepted`
- Response headers include `Retry-After`
- Response body includes:
  - `job_id` (prefix: `semantic_search_job_`)
  - `status`
  - `time_window_hours`
  - `status_url`
  - `result_url`

Example:

```bash
curl -i -X POST "https://news.tradao.xyz/semantic-search" \
  -H "Authorization: Bearer ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"hours":24,"query":"Bitcoin ETF approvals and institutional adoption","user_id":"my_agent_01"}'
```

Example success response:

```json
{
  "success": true,
  "job_id": "semantic_search_job_abc123",
  "status": "queued",
  "time_window_hours": 24,
  "status_url": "/semantic-search/semantic_search_job_abc123",
  "result_url": "/semantic-search/semantic_search_job_abc123/result"
}
```

### 2. Poll job status

`GET /semantic-search/{job_id}`

Example:

```bash
curl -X GET "https://news.tradao.xyz/semantic-search/semantic_search_job_abc123" \
  -H "Authorization: Bearer ${API_KEY}"
```

Response while running:

```json
{
  "job_id": "semantic_search_job_abc123",
  "status": "running",
  "time_window_hours": 24,
  "created_at": "2025-01-15T10:30:00Z"
}
```

Terminal statuses: `completed`, `failed`

### 3. Fetch result

`GET /semantic-search/{job_id}/result`

Example:

```bash
curl -X GET "https://news.tradao.xyz/semantic-search/semantic_search_job_abc123/result" \
  -H "Authorization: Bearer ${API_KEY}"
```

Success response:

```json
{
  "success": true,
  "job_id": "semantic_search_job_abc123",
  "status": "completed",
  "time_window_hours": 24,
  "query": "Bitcoin ETF approvals and institutional adoption",
  "normalized_intent": "ETF approvals, institutional investment, regulatory decisions",
  "matched_count": 45,
  "retained_count": 38,
  "report": "# 主题检索报告\n\n**查询主题**: Bitcoin ETF approvals...\n\n## 核心结论\n..."
}
```

Failed response:

```json
{
  "success": false,
  "job_id": "semantic_search_job_abc123",
  "status": "failed",
  "time_window_hours": 24,
  "error": "Query planning failed: LLM service unavailable"
}
```

## Error Responses

### 422 Validation Error

```json
{"detail": "Query cannot be blank or whitespace-only"}
```

### 401 Unauthorized

```json
{"detail": "Invalid or missing API key"}
```

### 422 Validation Error

```json
{"detail": "user_id must match ^[A-Za-z0-9_-]{1,128}$"}
```

### 503 Service Unavailable (SQLite backend)

```json
{"detail": "Semantic search requires postgres backend"}
```

## Report Format

The returned report is a compact Markdown document with this structure:

```markdown
# 主题检索报告

**原始查询**: Bitcoin ETF approvals and institutional adoption
**理解意图**: ETF approvals, institutional investment, regulatory decisions
**时间窗口**: 24小时
**匹配数量**: 45
**保留数量**: 38

## 核心结论

- [conclusion with citations]

## 关键信号

- [signal with citations]

## 来源

- Source Name - https://example.com/article
```

## Telegram Command

Authorized Telegram users can also use:

```
/semantic_search <hours> <topic>
```

Example:

```
/semantic_search 24 Bitcoin ETF approvals
```

## Configuration

Semantic search configuration (in `config.jsonc`):

```json
{
  "semantic_search": {
    "enabled": true,
    "query_max_chars": 300,
    "max_subqueries": 4,
    "per_subquery_limit": 50,
    "max_retained_items": 200,
    "embedding_model": "text-embedding-3-small",
    "embedding_dimensions": 1536
  }
}
```

## Environment Variables

- `OPENAI_API_KEY` - Required for embedding generation (text-embedding-3-small)
- `KIMI_API_KEY` or `GROK_API_KEY` - Required for LLM query planning and report synthesis

## Historical Embedding Backfill

To backfill embeddings for existing content:

```bash
uv run python -m crypto_news_analyzer.main --mode embedding-backfill --config ./config.jsonc --batch-size 100
```

Optional: add `--limit 1000` to process only the first 1000 missing embeddings.

This command is idempotent - re-running it will skip already-embedded rows.

## Limitations

- Requires PostgreSQL with pgvector extension
- Not available on SQLite backend
- Query limited to 300 characters
- Max 4 subqueries generated
- Max 200 unique items in final report
- Embedding generation requires OpenAI API key
