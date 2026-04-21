# Datasource Management Reference

This document describes the HTTP API surface for managing datasources. All datasource routes require Bearer authentication.

## CRUD Routes

### POST /datasources

Creates a new datasource. Returns `201 Created` on success, `409 Conflict` if a datasource with the same type and name already exists, and `422 Unprocessable Entity` for invalid payloads.

**Request body structure:**
```json
{
  "source_type": "rss|x|rest_api",
  "tags": ["tag1", "tag2"],
  "config_payload": {
    "name": "My Source",
    ...
  }
}
```

**Response structure (201):**
```json
{
  "success": true,
  "datasource": {
    "id": "uuid",
    "name": "My Source",
    "source_type": "rss",
    "tags": ["tag1"],
    "config_summary": {
      ...
    }
  }
}
```

The `name` field in the top-level request must match `config_payload.name` when both are provided. The response returns a safe summary of the config, not the full payload.

### GET /datasources

Lists all datasources sorted by source type and name. Returns `200 OK` with a list of datasource summaries.

**Response structure:**
```json
{
  "success": true,
  "datasources": [
    {
      "id": "uuid",
      "name": "My Source",
      "source_type": "rss",
      "tags": ["tag1"],
      "config_summary": {
        ...
      }
    }
  ]
}
```

List responses always return safe summaries. For `rest_api` datasources, sensitive fields are redacted and replaced with counts.

### DELETE /datasources/{id}

Deletes a datasource by its UUID. Returns `204 No Content` on success, `404 Not Found` if the datasource does not exist, and `409 Conflict` if the datasource has active ingestion jobs.

The delete operation will fail with `409 Conflict` if there are pending or running ingestion jobs associated with this datasource (matched by `source_type:source_name`).

## Supported Datasource Types

The API supports three datasource types: `rss`, `x`, and `rest_api`.

### rss

RSS feed datasources crawl RSS/XML feeds.

**Required config_payload fields:**
- `name` (string, non-empty)
- `url` (string, valid HTTP/HTTPS URL)

**Optional config_payload fields:**
- `description` (string, defaults to empty string)

**Config summary in responses:**
- `url`: The RSS feed URL
- `description`: The description value

### x

X (formerly Twitter) datasources crawl X lists or timelines.

**Required config_payload fields:**
- `name` (string, non-empty)
- `url` (string, valid HTTPS URL on x.com or www.x.com)
- `type` (string, must be `"list"` or `"timeline"`)

**Config summary in responses:**
- `url`: The X URL
- `type`: Either `"list"` or `"timeline"`

### rest_api

REST API datasources fetch content from arbitrary HTTP endpoints.

**Required config_payload fields:**
- `name` (string, non-empty)
- `endpoint` (string, valid HTTP/HTTPS URL)
- `method` (string, one of: `GET`, `POST`, `PUT`, `DELETE`)
- `response_mapping` (object) with required fields:
  - `title_field` (string, non-empty)
  - `content_field` (string, non-empty)
  - `url_field` (string, non-empty)
  - `time_field` (string, non-empty)

**Optional config_payload fields:**
- `headers` (object, defaults to empty object)
- `params` (object, defaults to empty object)

**Config summary in responses:**
- `endpoint`: The API endpoint URL
- `method`: The HTTP method
- `response_mapping`: The full response mapping object
- `header_count`: Number of headers (count only, values redacted)
- `param_count`: Number of query params (count only, values redacted)

## Tag Constraints

Tags on datasources follow strict normalization and validation rules:

**Normalization:**
- Tags are converted to lowercase
- Leading and trailing whitespace is stripped
- Empty tags after trimming are discarded
- Tags are sorted alphabetically
- Duplicate tags are removed

**Limits:**
- Maximum 16 unique tags per datasource
- Each tag must be at most 32 characters after normalization

**Validation errors:**
- Exceeding 16 unique tags returns `422 Unprocessable Entity` with message: "tags cannot contain more than 16 unique values"
- Any tag exceeding 32 characters returns `422 Unprocessable Entity` with message: "each tag must be at most 32 characters"

Example: The tags `[" Markets ", "markets", "Layer2"]` normalize to `["layer2", "markets"]`.

## Safe Summaries and Secret Redaction

All datasource responses (create and list) return safe summaries instead of the full config payload. This prevents accidental exposure of sensitive credentials.

### rss and x Summaries

For RSS and X datasources, the config summary includes the URL and type-specific fields without modification.

### rest_api Redaction

For `rest_api` datasources, the following redaction rules apply:

- The `headers` object is replaced with `header_count` (integer)
- The `params` object is replaced with `param_count` (integer)
- The actual header names, parameter names, and their values are never returned
- The `endpoint`, `method`, and `response_mapping` are returned as-is (these are not secrets)

This ensures that API keys, bearer tokens, and other credentials stored in headers or params remain secret while still allowing clients to understand the datasource configuration.

Example redacted response for a rest_api datasource:
```json
{
  "id": "uuid",
  "name": "News API",
  "source_type": "rest_api",
  "tags": [],
  "config_summary": {
    "endpoint": "https://api.example.com/news",
    "method": "GET",
    "response_mapping": {
      "title_field": "title",
      "content_field": "body",
      "url_field": "url",
      "time_field": "published_at"
    },
    "header_count": 1,
    "param_count": 2
  }
}
```

## Delete Conflict Behavior

Deleting a datasource can fail with `409 Conflict` in the following scenarios:

**Active Ingestion Jobs:**
If there are ingestion jobs for this datasource (matched by `source_type:source_name`) with status `"pending"` or `"running"`, the delete operation is rejected.

**Error response:**
```json
{
  "detail": "Cannot delete datasource 'rss:CoinDesk' while matching ingestion jobs are active"
}
```

To delete a datasource with active jobs, either wait for the jobs to complete or cancel them first.

## Error Reference

| Status Code | Scenario | Detail Message Pattern |
|-------------|----------|------------------------|
| 201 | Create success | N/A (returns datasource) |
| 204 | Delete success | N/A (empty body) |
| 200 | List success | N/A (returns list) |
| 401 | Missing or invalid API key | "Invalid or missing API key" |
| 404 | Datasource not found | "Datasource not found" |
| 409 | Duplicate datasource | "Datasource 'type:name' already exists" |
| 409 | Datasource in use | "Cannot delete datasource 'type:name' while matching ingestion jobs are active" |
| 422 | Invalid payload structure | Pydantic validation error details |
| 422 | Invalid semantic payload | e.g., "x.type must be one of: list, timeline" |
| 422 | Tag limit exceeded | "tags cannot contain more than 16 unique values" |
| 422 | Tag too long | "each tag must be at most 32 characters" |
| 500 | Internal server error | Exception message |

## Updating

Keep this reference aligned with `crypto_news_analyzer/api_server.py` and `crypto_news_analyzer/datasource_payloads.py`. When the implementation changes, update this document to reflect the current validation rules, redaction behavior, and error responses.
