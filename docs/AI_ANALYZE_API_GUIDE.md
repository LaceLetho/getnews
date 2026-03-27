# AI Analyze API Guide

This document is for AI agents that need to call the production or local HTTP analyze API.

## Read This First

- Production domain: `https://news.tradao.xyz`
- Auth is required: `Authorization: Bearer <API_KEY>`
- `POST /analyze` is **asynchronous**
- `POST /analyze` does **not** return the final report
- You must poll status and then fetch the result

## Endpoint Contract

### 1. Create analyze job

`POST /analyze`

Required JSON body:

```json
{"hours": 1}
```

Rules:

- `hours` is required
- `hours` must be a positive integer
- there is **no** “omit hours and auto-calculate” behavior for the HTTP API
- if `hours` exceeds server config, the server caps it to the configured max
- current fallback limits in code are min `1`, max `24`

Expected success response:

- HTTP `202 Accepted`
- response headers may include:
  - `Location`
  - `Retry-After`
- response body includes:
  - `job_id`
  - `status`
  - `time_window_hours`
  - `status_url`
  - `result_url`

Example:

```bash
curl -i -X POST "https://news.tradao.xyz/analyze" \
  -H "Authorization: Bearer ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"hours":1}'
```

Example body:

```json
{
  "success": true,
  "job_id": "analyze_job_2f205899562a4104868384e65f81c8c1",
  "status": "running",
  "time_window_hours": 1,
  "status_url": "/analyze/analyze_job_2f205899562a4104868384e65f81c8c1",
  "result_url": "/analyze/analyze_job_2f205899562a4104868384e65f81c8c1/result"
}
```

## 2. Poll job status

`GET /analyze/{job_id}`

Possible status values:

- `queued`
- `running`
- `completed`
- `failed`

Example:

```bash
curl -H "Authorization: Bearer ${API_KEY}" \
  "https://news.tradao.xyz/analyze/<job_id>"
```

If the job is still in progress, keep polling.

## 3. Fetch final result

`GET /analyze/{job_id}/result`

Example:

```bash
curl -H "Authorization: Bearer ${API_KEY}" \
  "https://news.tradao.xyz/analyze/<job_id>/result"
```

Behavior:

- if the job is still running, the endpoint returns HTTP `202`
- if the job is completed, the endpoint returns HTTP `200`
- if the job failed, inspect `status` / `error`

Completed result body includes:

- `success`
- `job_id`
- `status`
- `report`
- `items_processed`
- `time_window_hours`
- `error`

## Minimal Agent Workflow

1. Send `POST /analyze` with `{"hours": N}`
2. Save `job_id`
3. Poll `GET /analyze/{job_id}` until status becomes `completed` or `failed`
4. If `completed`, call `GET /analyze/{job_id}/result`
5. Do **not** expect the final report from the initial POST

## Important Gotchas

- Do not call `POST /analyze` without `hours`
- Do not assume HTTP API behavior matches Telegram `/analyze`
- Telegram can auto-estimate a window when the parameter is omitted; HTTP API cannot
- Do not treat `202` as failure; here it means “accepted / still processing”
- Cloudflare or edge behavior can differ by client type; `curl` has been verified against production

## Verified Production Behavior

The following has been verified on `https://news.tradao.xyz`:

- `GET /health` returns `200`
- `POST /analyze` returns `202`
- `GET /analyze/{job_id}` returns live job state
- `GET /analyze/{job_id}/result` returns `202` while running, then `200` with the final report
