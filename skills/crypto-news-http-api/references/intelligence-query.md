# Intelligence Query Reference

Hidden-channel intelligence query API. All endpoints require Bearer authentication. Results are read from the canonical intelligence knowledge base built by the private ingestion pipeline.

## Authentication

Send `Authorization: Bearer <API_KEY>` with every request. Unauthenticated requests return `401 Unauthorized`.

## Common Parameters

### window

Time window filter in the format `<N>h` (hours) or `<N>d` (days). Applied to `last_seen_at` for canonical entries.

| Examples | Meaning |
|----------|---------|
| `24h` | Last 24 hours |
| `7d` | Last 7 days |
| `30d` | Last 30 days |

Omit `window` to return results across all time.

### entry_type

Filter by entry category:

| Value | Meaning |
|-------|---------|
| `channel` | Social channel or community info |
| `slang` | Industry slang or jargon term |

### primary_label

Filter by primary classification. Valid labels:

`AI`, `crypto`, `暗网`, `账号交易`, `支付`, `游戏`, `电商`, `社媒`, `开发者工具`, `其他`

### secondary_tag

Secondary tags are LLM-generated and not enum-restricted. Filter with exact match on any tag.

### page / page_size

Integer pagination for `/intelligence/entries`. Defaults: `page=1`, `page_size=20`. Maximum `page_size` is `100`.

---

## GET /intelligence/entries

List canonical intelligence entries sorted by `last_seen_at` descending.

### Query Parameters

| Parameter | Type | Required | Default |
|-----------|------|----------|---------|
| `window` | string | No | all time |
| `entry_type` | string | No | all types |
| `primary_label` | string | No | all labels |
| `page` | integer | No | 1 |
| `page_size` | integer | No | 20 |

### Response (200)

```json
{
  "entries": [
    {
      "id": "uuid",
      "entry_type": "slang",
      "normalized_key": "土区礼品卡",
      "display_name": "土区礼品卡",
      "explanation": "土耳其区礼品卡/充值方式，常见于AI订阅代购...",
      "primary_label": "账号交易",
      "secondary_tags": ["礼品卡", "低价区域"],
      "confidence": 0.92,
      "first_seen_at": "2026-05-01T10:00:00",
      "last_seen_at": "2026-05-04T12:30:00",
      "evidence_count": 8,
      "model_name": "kimi-k2.5",
      "prompt_version": "1.0",
      "schema_version": "1.0",
      "created_at": "2026-05-01T10:00:00",
      "updated_at": "2026-05-04T12:30:00"
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
  "https://news.tradao.xyz/intelligence/entries?window=7d&entry_type=slang&page=1&page_size=10"
```

---

## GET /intelligence/entries/{entry_id}

Get a single intelligence entry by ID with optional raw evidence text.

### Query Parameters

| Parameter | Type | Required | Default |
|-----------|------|----------|---------|
| `include_raw` | boolean | No | false |

### Response (200)

Same shape as list entry, plus:

```json
{
  "raw_available": true,
  "raw_evidence": {
    "raw_item_id": "uuid",
    "raw_text": "完整原始文本，保持不变...",
    "source_type": "telegram_group",
    "source_url": "https://t.me/c/xxx/123",
    "published_at": "2026-05-04T12:00:00",
    "collected_at": "2026-05-04T13:00:00",
    "expires_at": "2026-06-03T13:00:00"
  }
}
```

When raw evidence has passed its 30-day TTL:

```json
{
  "raw_available": false
}
```

Returns `404` if entry ID does not exist.

### Example

```bash
curl -H "Authorization: Bearer ${API_KEY}" \
  "https://news.tradao.xyz/intelligence/entries/abc123?include_raw=true"
```

---

## GET /intelligence/search

Semantic search across canonical intelligence entries. Embeds the query text and returns ranked results by vector similarity combined with recency and confidence.

### Query Parameters

| Parameter | Type | Required | Default |
|-----------|------|----------|---------|
| `q` | string | **Yes** | — |
| `entry_type` | string | No | all types |
| `primary_label` | string | No | all labels |
| `window` | string | No | all time |

### Response (200)

```json
{
  "results": [
    {
      "id": "uuid",
      "entry_type": "channel",
      "normalized_key": "@seller_channel",
      "display_name": "GPT Plus 代购频道",
      "explanation": "提供 GPT Plus 土耳其区代购服务的 Telegram 频道...",
      "primary_label": "AI",
      "secondary_tags": ["代购", "GPT"],
      "confidence": 0.88,
      "last_seen_at": "2026-05-04T11:00:00",
      "evidence_count": 5,
      "similarity_score": 0.9234
    }
  ],
  "total": 3
}
```

`similarity_score` ranges from 0.0 to 1.0 (higher = more relevant).

### Example

```bash
curl -H "Authorization: Bearer ${API_KEY}" \
  "https://news.tradao.xyz/intelligence/search?q=GPT%20plus%E8%B4%AD%E4%B9%B0%E6%B8%A0%E9%81%93&window=7d"
```

---

## GET /intelligence/raw/{raw_item_id}

Get a raw intelligence item by ID. Returns the original collected text if still within the 30-day TTL window.

### Path Parameters

| Parameter | Type | Required |
|-----------|------|----------|
| `raw_item_id` | string | **Yes** (in path) |

### Response (200)

```json
{
  "raw_text": "完整原始文本内容...",
  "source_type": "v2ex",
  "source_url": "https://www.v2ex.com/t/1210190",
  "published_at": "2026-05-04T10:30:00",
  "expires_at": "2026-06-03T13:45:00",
  "is_expired": false
}
```

After 30-day TTL:

```json
{
  "raw_text": null,
  "source_type": "v2ex",
  "source_url": "https://www.v2ex.com/t/1210190",
  "published_at": "2026-05-04T10:30:00",
  "expires_at": "2026-06-03T13:45:00",
  "is_expired": true
}
```

Returns `404` if raw item ID does not exist.

### Example

```bash
curl -H "Authorization: Bearer ${API_KEY}" \
  "https://news.tradao.xyz/intelligence/raw/raw_abc123"
```

---

## Notes

- All intelligence endpoints are **synchronous** (no async job/poll flow). The semantic search and list operations return results immediately.
- Raw text returned is **byte-for-byte original** — no redaction or summarization.
- Raw text is only available within the 30-day TTL window. After expiration, `raw_text` is `null` and `is_expired` is `true`. Structured canonical knowledge remains queryable indefinitely.
- Search ranking combines vector similarity with recency and confidence scores.
- These endpoints exist only on `analysis-service` / `api-only` deployments. They are not available from `ingestion`.
