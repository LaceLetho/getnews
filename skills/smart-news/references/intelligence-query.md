# Intelligence Query Reference

Topic-first intelligence HTTP API. All endpoints require Bearer authentication and manage the topic research lifecycle (create → revise → confirm → research → merge → archive).

These endpoints are synchronous — results return immediately. Do not use an async job/poll workflow for intelligence routes.

## Authentication

Send `Authorization: Bearer <API_KEY>` with every request. Missing or invalid credentials return `401 Unauthorized`.

## Topic Lifecycle

Topics progress through states: `draft` → `active` → `paused` / `archived`. Only `active` topics are researched by the ingestion scheduler. Merge previews expire after 24 hours.

## Deprecated Routes

The old entry-based routes (`/intelligence/entries*`, `/intelligence/discovery`, `/intelligence/labels`, `/intelligence/search`, `/intelligence/raw/*`, `/intelligence/topics/converge`) have been removed. Use only the topic-first endpoints documented below.

---

## POST /intelligence/topics

Create a new intelligence topic with an LLM-generated draft prompt.

### Request Body

| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| `theme` | string | Yes | 1–500 characters |
| `source_context` | object | No | Optional context for prompt generation |
| `datasource_ids` | string[] | No | Optional list of datasource IDs to associate. Omitted = no associations. |

### Status Codes

| Code | Meaning |
|------|---------|
| `201` | Topic draft created |
| `400` | Invalid theme or topic parameters |
| `401` | Missing or invalid Bearer token |
| `503` | LLM service unavailable |

### Response (201)

Returns a `TopicPromptVersionResponse`:

```json
{
  "id": "prompt-uuid",
  "intelligence_topic_id": "topic-uuid",
  "prompt_version": "v1.0",
  "prompt_text": "LLM-generated research prompt...",
  "schema_version": "v1.0",
  "status": "draft",
  "created_by": "api",
  "activated_by": null,
  "activation_notes": null,
  "created_at": "2026-05-18T10:00:00+00:00",
  "activated_at": null,
  "archived_at": null,
  "updated_at": "2026-05-18T10:00:00+00:00",
  "audit_history": []
}
```

### Example

```bash
curl -X POST "https://news.tradao.xyz/intelligence/topics" \
  -H "Authorization: Bearer ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"theme": "crypto payment channels in Telegram groups"}'
```

---

## POST /intelligence/topics/{topic_id}/revise

Revise the most recent draft prompt using LLM and user feedback. Returns a new prompt version.

### Request Body

| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| `feedback` | string | Yes | 1–5000 characters |

### Response

Returns a `TopicPromptVersionResponse` with the revised prompt.

### Example

```bash
curl -X POST "https://news.tradao.xyz/intelligence/topics/topic-uuid/revise" \
  -H "Authorization: Bearer ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"feedback": "Focus on stablecoin settlement, exclude NFT marketplaces"}'
```

---

## PUT /intelligence/topics/{topic_id}/prompt

Manually set or replace the topic prompt text. Context-aware behavior:
- If an active prompt exists → edits it in place (new version with same activation)
- If no active prompt → creates a draft revision

### Request Body

| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| `prompt_text` | string | Yes | 1–50000 characters |

### Response

Returns a `TopicPromptVersionResponse`.

### Example

```bash
curl -X PUT "https://news.tradao.xyz/intelligence/topics/topic-uuid/prompt" \
  -H "Authorization: Bearer ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"prompt_text": "Custom manual research prompt text..."}'
```

---

## POST /intelligence/topics/{topic_id}/confirm

Confirm a draft prompt version, activating it for scheduled research.

### Request Body

| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| `prompt_version_id` | string | Yes | Must reference a draft prompt version |
| `activation_notes` | string | No | Max 2000 characters |

### Response

Returns a `TopicPromptVersionResponse` with status `active`.

### Example

```bash
curl -X POST "https://news.tradao.xyz/intelligence/topics/topic-uuid/confirm" \
  -H "Authorization: Bearer ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"prompt_version_id": "prompt-uuid", "activation_notes": "Ready for daily research"}'
```

---

## GET /intelligence/topics

List intelligence topics with pagination and filtering.

### Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `active_only` | boolean | No | `true` | Filter to active topics only |
| `page` | integer | No | 1 | Page number (1-based) |
| `page_size` | integer | No | 20 | Items per page |

### Response (200)

```json
{
  "items": [
    {
      "id": "topic-uuid",
      "name": "Stablecoin Settlement Channels",
      "description": "Research on stablecoin payment channels",
      "enriched_summary": "LLM-generated deep-dive summary of findings",
      "finding_count": 5,
      "enriched_at": "2026-05-18T06:00:00+00:00",
      "updated_at": "2026-05-18T06:30:00+00:00"
    }
  ],
  "total": 12,
  "page": 1,
  "page_size": 20
}
```

### Example

```bash
curl -H "Authorization: Bearer ${API_KEY}" \
  "https://news.tradao.xyz/intelligence/topics?active_only=true&page=1&page_size=20"
```

---

## GET /intelligence/topics/{topic_id}

Get full detail for a single topic including prompt versions, active findings, citations, merge availability, and recent run logs.

### Response (200)

```json
{
  "topic": {
    "id": "topic-uuid",
    "name": "Stablecoin Settlement Channels",
    "description": "Research on stablecoin payment channels",
    "enriched_summary": "LLM-generated summary",
    "source_channels": [],
    "methods": null,
    "vulnerabilities": null,
    "latest_findings": [],
    "is_active": true,
    "enriched_at": "2026-05-18T06:00:00+00:00",
    "updated_at": "2026-05-18T06:30:00+00:00"
  },
  "prompt_versions": [
    {
      "id": "prompt-uuid",
      "intelligence_topic_id": "topic-uuid",
      "prompt_version": "v1.0",
      "prompt_text": "Research prompt text...",
      "schema_version": "v1.0",
      "status": "active",
      "created_by": "api",
      "activated_by": "api",
      "activation_notes": "Ready for daily research",
      "created_at": "2026-05-18T10:00:00+00:00",
      "activated_at": "2026-05-18T10:05:00+00:00",
      "archived_at": null,
      "updated_at": "2026-05-18T10:05:00+00:00",
      "audit_history": []
    }
  ],
  "current_prompt": { /* same shape as above, the active prompt */ },
  "active_findings": [
    {
      "id": "finding-uuid",
      "intelligence_topic_id": "topic-uuid",
      "prompt_version_id": "prompt-uuid",
      "finding_payload": { /* LLM-generated structured finding */ },
      "confidence": 0.92,
      "citations": [
        {
          "raw_item_id": "raw-uuid",
          "source_type": "telegram_group",
          "source_url": "https://t.me/example/123",
          "published_at": "2026-05-18T05:00:00+00:00"
        }
      ],
      "source_finding_ids": [],
      "status": "active",
      "found_at": "2026-05-18T06:00:00+00:00",
      "created_at": "2026-05-18T06:00:00+00:00",
      "updated_at": "2026-05-18T06:00:00+00:00"
    }
  ],
  "citations": [ /* deduplicated list of all citations across active findings */ ],
  "merge_available": false,
  "recent_logs": [
    {
      "id": "log-uuid",
      "run_type": "topic_research",
      "status": "success",
      "topic_id": "topic-uuid",
      "entry_id": null,
      "message": null,
      "details": {},
      "started_at": "2026-05-18T06:00:00+00:00",
      "finished_at": "2026-05-18T06:00:01+00:00",
      "created_at": "2026-05-18T06:00:01+00:00"
    }
  ]
}
```

Returns `404` if the topic ID does not exist.

### Example

```bash
curl -H "Authorization: Bearer ${API_KEY}" \
  "https://news.tradao.xyz/intelligence/topics/topic-uuid"
```

---

## POST /intelligence/topics/{topic_id}/pause

Pause a topic, stopping further scheduled research runs.

### Response (200)

```json
{
  "success": true,
  "topic_id": "topic-uuid",
  "lifecycle_status": "paused",
  "updated_at": "2026-05-18T11:00:00+00:00"
}
```

Returns `404` if the topic ID does not exist.

### Example

```bash
curl -X POST "https://news.tradao.xyz/intelligence/topics/topic-uuid/pause" \
  -H "Authorization: Bearer ${API_KEY}"
```

---

## POST /intelligence/topics/{topic_id}/archive

Archive a topic, removing it from active research permanently.

### Response (200)

```json
{
  "success": true,
  "topic_id": "topic-uuid",
  "lifecycle_status": "archived",
  "updated_at": "2026-05-18T12:00:00+00:00"
}
```

Returns `404` if the topic ID does not exist.

### Example

```bash
curl -X POST "https://news.tradao.xyz/intelligence/topics/topic-uuid/archive" \
  -H "Authorization: Bearer ${API_KEY}"
```

---

## GET /intelligence/topics/{topic_id}/runs

List research run logs for a specific topic.

### Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `run_type` | string | No | all types | Filter by run type |
| `page` | integer | No | 1 | Page number |
| `page_size` | integer | No | 20 | Items per page |

### Response (200)

```json
{
  "items": [
    {
      "id": "log-uuid",
      "run_type": "topic_research",
      "status": "success",
      "topic_id": "topic-uuid",
      "entry_id": null,
      "message": null,
      "details": {},
      "started_at": "2026-05-18T06:00:00+00:00",
      "finished_at": "2026-05-18T06:00:01+00:00",
      "created_at": "2026-05-18T06:00:01+00:00"
    }
  ],
  "page": 1,
  "page_size": 20
}
```

### Example

```bash
curl -H "Authorization: Bearer ${API_KEY}" \
  "https://news.tradao.xyz/intelligence/topics/topic-uuid/runs?page=1&page_size=10"
```

---

## GET /intelligence/topic-runs

List topic research run logs across all topics with optional filters.

### Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `topic_id` | string | No | all topics | Filter by topic |
| `run_type` | string | No | all types | Filter by run type |
| `page` | integer | No | 1 | Page number |
| `page_size` | integer | No | 20 | Items per page |

### Response

Same shape as `GET /intelligence/topics/{topic_id}/runs`.

### Example

```bash
curl -H "Authorization: Bearer ${API_KEY}" \
  "https://news.tradao.xyz/intelligence/topic-runs?run_type=topic_research&page=1&page_size=10"
```

---

## Topic-Datasource Association API

Manage which Intelligence datasources feed each topic's scheduled research. Only datasources with `purpose = "intelligence"` can be associated. All association changes are atomic and validated in one transaction.

### GET /intelligence/topics/{topic_id}/datasources

List all datasource associations for a topic. Returns safe summaries with no `config_payload`.

**Status Codes:**

| Code | Meaning |
|------|---------|
| `200` | Association list returned |
| `401` | Missing or invalid Bearer token |
| `404` | Topic not found |

**Response (200)**

Returns `List[SafeDataSourceSummaryResponse]`:

```json
[
  {
    "id": "ds-uuid",
    "source_type": "telegram_group",
    "name": "Crypto Alpha",
    "tags": ["alpha", "signals"]
  }
]
```

Returns `[]` if the topic has no associations.

### PUT /intelligence/topics/{topic_id}/datasources

Atomically replace all datasource associations for a topic. `PUT []` clears all associations.

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `datasource_ids` | string[] | Yes | List of datasource IDs. Empty array clears all associations. |

**Status Codes:**

| Code | Meaning |
|------|---------|
| `200` | Associations replaced, returns updated list |
| `400` | Non-intelligence datasource ID supplied (no partial update) |
| `401` | Missing or invalid Bearer token |
| `404` | Unknown topic or unknown datasource ID |

**Example:**

```bash
curl -X PUT "https://news.tradao.xyz/intelligence/topics/topic-uuid/datasources" \
  -H "Authorization: Bearer ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"datasource_ids": ["ds-uuid-1", "ds-uuid-2"]}'
```

To clear all associations:

```bash
curl -X PUT "https://news.tradao.xyz/intelligence/topics/topic-uuid/datasources" \
  -H "Authorization: Bearer ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"datasource_ids": []}'
```

### POST /intelligence/topics/{topic_id}/datasources/{datasource_id}

Idempotently add a datasource association. No-op if already associated.

**Status Codes:**

| Code | Meaning |
|------|---------|
| `200` | Association added (or already present), returns updated list |
| `400` | Non-intelligence datasource ID supplied |
| `401` | Missing or invalid Bearer token |
| `404` | Unknown topic or unknown datasource ID |

**Example:**

```bash
curl -X POST "https://news.tradao.xyz/intelligence/topics/topic-uuid/datasources/ds-uuid" \
  -H "Authorization: Bearer ${API_KEY}"
```

### DELETE /intelligence/topics/{topic_id}/datasources/{datasource_id}

Idempotently remove a datasource association. No-op if already absent.

**Status Codes:**

| Code | Meaning |
|------|---------|
| `200` | Association removed (or already absent), returns updated list |
| `401` | Missing or invalid Bearer token |
| `404` | Unknown topic |

**Example:**

```bash
curl -X DELETE "https://news.tradao.xyz/intelligence/topics/topic-uuid/datasources/ds-uuid" \
  -H "Authorization: Bearer ${API_KEY}"
```

### Association Behavior Notes

- **New topics default empty**: created via `POST /intelligence/topics` (with or without optional `datasource_ids`) have no associations unless explicitly specified.
- **Empty association skips research**: active topics with no associations are skipped by the daily scheduler — no LLM call, no checkpoint advance.
- **No automatic backfill**: adding or removing associations does not retroactively affect completed research runs. Changes take effect on the next scheduled cycle.
- **Only Intelligence datasources**: linking a `news` datasource returns `400` with no partial update.
- **Datasource deletion guarded**: deleting a datasource associated with any topic returns `409 Conflict`.

---

## Status Codes

| Status | Meaning |
|--------|---------|
| `200` | Success |
| `201` | Topic draft or merge preview created |
| `400` | Invalid parameters or merge preview error |
| `401` | Missing or invalid Bearer token |
| `404` | Topic or resource not found |
| `422` | FastAPI validation error |
| `500` | Internal server error |
| `503` | LLM service or repository not initialized |

## Notes

- All intelligence routes are synchronous — results return immediately without polling.
- Only `active` topics receive scheduled research from the ingestion service.
- Merge previews expire after 24 hours; accepting a stale preview is rejected.
- Prompt lifecycle: create draft → revise (optional) → confirm → active. Manual edits via `PUT /prompt` can shortcut this.
- These endpoints exist only on `analysis-service` / `api-only` deployments. They are not available from `ingestion`.

## Updating

Canonical sources for this reference:

1. `crypto_news_analyzer/api_server.py` — route definitions and response models
2. `crypto_news_analyzer/intelligence/topic_prompts.py` — prompt workflow service
3. `crypto_news_analyzer/intelligence/topic_findings.py` — findings and merge service
4. `crypto_news_analyzer/domain/models.py` — `TopicLifecycleStatus` enum and `SafeDataSourceSummary`
5. `crypto_news_analyzer/domain/repositories.py` — `IntelligenceRepository` datasource association contract
6. `tests/intelligence/test_topic_datasource_api.py` — association API contract tests

When sources disagree, trust code over prose.
