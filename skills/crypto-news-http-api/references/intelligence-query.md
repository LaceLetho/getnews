# Intelligence Query Reference

Hidden-channel intelligence HTTP API. All endpoints require Bearer authentication and read from the canonical intelligence knowledge base built by the private ingestion pipeline.

These endpoints are synchronous. Do not use an async job/poll workflow for intelligence routes.

## Authentication

Send `Authorization: Bearer <API_KEY>` with every request. Missing or invalid credentials return `401 Unauthorized`.

## Common Parameters

### window

Time window filter in the format `<N>h` (hours) or `<N>d` (days). The filter is applied to canonical entry `last_seen_at`.

Examples:

| Value | Meaning |
|-------|---------|
| `24h` | Last 24 hours |
| `7d` | Last 7 days |
| `30d` | Last 30 days |

Omit `window` to query all time. The current implementation ignores invalid window strings instead of returning `400`.

### entry_type

Filter by canonical entry category:

| Value | Meaning |
|-------|---------|
| `channel` | Social channel or community information |
| `slang` | Industry slang or jargon term |

### primary_label

Filter by primary classification. Valid API values are:

`AI`, `crypto`, `暗网`, `账号交易`, `支付`, `游戏`, `电商`, `社媒`, `开发者工具`, `其他`

### tracking_scope

Supported by `GET /intelligence/entries` and `GET /intelligence/search`.

| Value | Meaning |
|-------|---------|
| `following` | Entries whose follow status is `follow`. This is the default. |
| `discovery` | Entries whose follow status is `unset`. |
| `unset` | Alias for unset follow status. |
| `unfollowed` | Entries whose follow status is `unfollow`. |
| `all` | All non-ignored entries. |

Invalid values return `400 Bad Request`.

### page / page_size

Integer pagination. Defaults are `page=1` and `page_size=20`. Values are clamped to `page>=1` and `1<=page_size<=100`.

## Entry State

Canonical intelligence entries use one follow state: `follow`, `unfollow`, or `unset`.

Newly collected slang and channel entries default to `unset`. Following/unfollowing updates this state.

Discovery returns entries with `follow_status=unset`; it does not mark returned entries as presented.

## GET /intelligence/entries

List non-ignored canonical intelligence entries sorted by repository ordering, normally newest `last_seen_at` first.

### Query Parameters

| Parameter | Type | Required | Default |
|-----------|------|----------|---------|
| `window` | string | No | all time |
| `entry_type` | string | No | all types |
| `primary_label` | string | No | all labels |
| `tracking_scope` | string | No | `following` |
| `page` | integer | No | 1 |
| `page_size` | integer | No | 20 |

### Response (200)

```json
{
  "entries": [
    {
      "id": "entry-uuid",
      "entry_id": "entry-uuid",
      "entry_type": "slang",
      "normalized_key": "term-key",
      "display_name": "Example Term",
      "explanation": "Meaning and context",
      "usage_summary": "How the term is used",
      "primary_label": "AI",
      "secondary_tags": ["subscription", "reseller"],
      "confidence": 0.92,
      "first_seen_at": "2026-05-01T10:00:00+00:00",
      "evidence_count": 8,
      "aliases": ["alternate term"],
      "model_name": "opencode-go/glm-5.1",
      "prompt_version": "v1.0",
      "schema_version": "v1.0",
      "created_at": "2026-05-01T10:00:00+00:00",
      "updated_at": "2026-05-04T12:30:00+00:00",
      "is_ignored": false,
      "ignored_at": null,
      "ignored_by": null,
      "tracking_enabled": true,
      "discovery_presented_at": null
    }
  ],
  "total": 42,
  "page": 1,
  "page_size": 20
}
```

### Example

```bash
curl -H "Authorization: Bearer ${API_KEY}" \
  "https://news.tradao.xyz/intelligence/entries?window=7d&entry_type=slang&tracking_scope=all&page=1&page_size=10"
```

## GET /intelligence/discovery

List entries whose follow status is unset.

### Query Parameters

| Parameter | Type | Required | Default |
|-----------|------|----------|---------|
| `window` | string | No | all time |
| `primary_label` | string | No | all labels |
| `page` | integer | No | 1 |
| `page_size` | integer | No | 20 |

### Response (200)

Same envelope and entry item shape as `GET /intelligence/entries`.

### Example

```bash
curl -H "Authorization: Bearer ${API_KEY}" \
  "https://news.tradao.xyz/intelligence/discovery?primary_label=AI&page=1&page_size=10"
```

## GET /intelligence/entries/ignored

List ignored canonical intelligence entries.

### Query Parameters

| Parameter | Type | Required | Default |
|-----------|------|----------|---------|
| `window` | string | No | all time |
| `entry_type` | string | No | all types |
| `primary_label` | string | No | all labels |
| `page` | integer | No | 1 |
| `page_size` | integer | No | 20 |

### Response (200)

Same envelope and entry item shape as `GET /intelligence/entries`, with `is_ignored=true` for returned entries.

### Example

```bash
curl -H "Authorization: Bearer ${API_KEY}" \
  "https://news.tradao.xyz/intelligence/entries/ignored?page=1&page_size=20"
```

## GET /intelligence/labels

List searchable primary labels. Use the returned `value` in `primary_label` filters.

If there are no canonical entries and no ignored canonical entries, the endpoint returns all enum labels. Otherwise it returns labels that currently exist among non-ignored canonical entries.

### Response (200)

```json
{
  "labels": [
    {"name": "AI", "value": "AI"},
    {"name": "CRYPTO", "value": "crypto"},
    {"name": "PAYMENT", "value": "支付"}
  ]
}
```

### Example

```bash
curl -H "Authorization: Bearer ${API_KEY}" \
  "https://news.tradao.xyz/intelligence/labels"
```

## POST /intelligence/entries/{entry_id}/ignore

Mark an entry ignored. The operation is idempotent and returns `404` if the entry does not exist.

### Request Body

The body is optional.

```json
{
  "ignored_by": "operator-id"
}
```

If omitted, `ignored_by` defaults to `api`.

### Response (200)

```json
{
  "success": true,
  "entry_id": "entry-uuid",
  "is_ignored": true,
  "ignored_at": "2026-05-04T13:00:00+00:00",
  "ignored_by": "operator-id"
}
```

## POST /intelligence/entries/{entry_id}/unignore

Restore an ignored entry. The operation is idempotent and returns `404` if the entry does not exist.

### Response (200)

```json
{
  "success": true,
  "entry_id": "entry-uuid",
  "is_ignored": false,
  "ignored_at": null,
  "ignored_by": null
}
```

## POST /intelligence/entries/{entry_id}/follow

Set an entry's follow status to `follow`. Returns `404` if the entry does not exist.

### Response (200)

```json
{
  "success": true,
  "entry_id": "entry-uuid",
  "tracking_enabled": true,
  "is_ignored": false,
  "follow_status": "follow"
}
```

## POST /intelligence/entries/{entry_id}/unfollow

Set an entry's follow status to `unfollow`. Returns `404` if the entry does not exist.

### Response (200)

```json
{
  "success": true,
  "entry_id": "entry-uuid",
  "tracking_enabled": false,
  "is_ignored": true,
  "follow_status": "unfollow"
}
```

## GET /intelligence/entries/{entry_id}

Get a single intelligence entry by ID. The detail response includes latest source display information when available and paginated evidence context groups.

### Query Parameters

| Parameter | Type | Required | Default |
|-----------|------|----------|---------|
| `include_raw` | boolean | No | false |
| `evidence_page` | integer | No | 1 |
| `evidence_page_size` | integer | No | 5 |

`evidence_page_size` is clamped to `1..100`.

### Response (200)

The base detail fields match entry list items and add:

```json
{
  "last_seen_at": "2026-05-04T12:30:00+00:00",
  "source": "telegram_group: https://t.me/example/123",
  "raw_available": true,
  "raw_evidence": {
    "raw_item_id": "raw-uuid",
    "raw_text": "Original raw text",
    "source_type": "telegram_group",
    "source_url": "https://t.me/example/123",
    "published_at": "2026-05-04T12:00:00+00:00",
    "collected_at": "2026-05-04T13:00:00+00:00",
    "expires_at": "2026-06-03T13:00:00+00:00"
  },
  "evidence_groups": [
    {
      "observation_id": "observation-uuid",
      "raw_item_id": "raw-uuid",
      "observed_at": "2026-05-04T13:00:00+00:00",
      "published_at": "2026-05-04T12:00:00+00:00",
      "collected_at": "2026-05-04T13:00:00+00:00",
      "anchor_raw_item": {
        "raw_item_id": "raw-uuid",
        "raw_text": "Original raw text",
        "source_type": "telegram_group",
        "source_url": "https://t.me/example/123",
        "source": "telegram_group: https://t.me/example/123",
        "published_at": "2026-05-04T12:00:00+00:00",
        "collected_at": "2026-05-04T13:00:00+00:00",
        "expires_at": "2026-06-03T13:00:00+00:00",
        "is_expired": false
      },
      "neighboring_raw_items": [],
      "warning": null
    }
  ],
  "evidence_page": 1,
  "evidence_page_size": 5,
  "evidence_total": 1
}
```

When `include_raw=true` but latest raw text is expired or unavailable, `raw_available` is `false` and `raw_evidence` remains `null`. Evidence group raw text is also null for expired or purged raw items, with a warning when applicable.

Returns `404` if the entry ID does not exist.

### Example

```bash
curl -H "Authorization: Bearer ${API_KEY}" \
  "https://news.tradao.xyz/intelligence/entries/entry-uuid?include_raw=true&evidence_page=1&evidence_page_size=5"
```

## GET /intelligence/search

Semantic search across non-ignored canonical intelligence entries. The route embeds the required query text and returns ranked results.

### Query Parameters

| Parameter | Type | Required | Default |
|-----------|------|----------|---------|
| `q` | string | Yes | - |
| `entry_type` | string | No | all types |
| `primary_label` | string | No | all labels |
| `window` | string | No | all time |
| `tracking_scope` | string | No | `following` |
| `page` | integer | No | 1 |
| `page_size` | integer | No | 20 |

Missing `q` returns `422 Unprocessable Entity`. If the embedding service or storage configuration is unavailable, the endpoint returns `503 Service Unavailable`.

### Response (200)

```json
{
  "results": [
    {
      "id": "entry-uuid",
      "entry_id": "entry-uuid",
      "entry_type": "channel",
      "normalized_key": "channel-key",
      "display_name": "Example Channel",
      "explanation": "Context for this channel",
      "primary_label": "AI",
      "secondary_tags": ["reseller", "subscription"],
      "confidence": 0.88,
      "evidence_count": 5,
      "similarity_score": 0.9234,
      "is_ignored": false,
      "ignored_at": null,
      "ignored_by": null,
      "tracking_enabled": true
    }
  ],
  "total": 25,
  "page": 1,
  "page_size": 20
}
```

### Example

```bash
curl -H "Authorization: Bearer ${API_KEY}" \
  "https://news.tradao.xyz/intelligence/search?q=payment%20channels&window=7d&tracking_scope=all&page=1&page_size=10"
```

## GET /intelligence/raw/{raw_item_id}

Get a raw intelligence item by ID. Returns original collected text if it is still within its retention window.

### Path Parameters

| Parameter | Type | Required |
|-----------|------|----------|
| `raw_item_id` | string | Yes |

### Response (200)

```json
{
  "raw_text": "Original raw text",
  "source_type": "v2ex",
  "source_url": "https://www.v2ex.com/t/1210190",
  "published_at": "2026-05-04T10:30:00+00:00",
  "expires_at": "2026-06-03T13:45:00+00:00",
  "is_expired": false
}
```

After expiration:

```json
{
  "raw_text": null,
  "source_type": "v2ex",
  "source_url": "https://www.v2ex.com/t/1210190",
  "published_at": "2026-05-04T10:30:00+00:00",
  "expires_at": "2026-06-03T13:45:00+00:00",
  "is_expired": true
}
```

Returns `404` if raw item ID does not exist.

### Example

```bash
curl -H "Authorization: Bearer ${API_KEY}" \
  "https://news.tradao.xyz/intelligence/raw/raw-uuid"
```

## Status Codes

| Status | Meaning |
|--------|---------|
| `200` | Success |
| `400` | Invalid `tracking_scope` |
| `401` | Missing or invalid Bearer token |
| `404` | Entry or raw item not found |
| `422` | FastAPI validation error, such as missing `q` on search |
| `503` | Intelligence repository, embedding service, or storage config is not initialized |

## Notes

- Raw text is returned byte-for-byte while available; it is not summarized or redacted by these routes.
- Expired raw text is represented as `raw_text: null` and `is_expired: true`.
- Canonical structured knowledge remains queryable after raw text expires.
- `GET /intelligence/search` is separate from async `POST /semantic-search`; intelligence search is synchronous and query-only.
- These endpoints exist only on `analysis-service` / `api-only` deployments. They are not available from `ingestion`.
