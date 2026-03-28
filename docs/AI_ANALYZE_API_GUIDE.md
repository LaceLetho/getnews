# AI Analyze API Guide

This document is for AI agents that need to call the production or local HTTP analyze API.

## Read This First

- Production domain: `https://news.tradao.xyz`
- Auth is required: `Authorization: Bearer <API_KEY>`
- `POST /analyze` is **asynchronous**
- `POST /analyze` does **not** return the final report
- You must poll status and then fetch the result
- `POST /analyze` requires both `hours` and `user_id`

## Endpoint Contract

### 1. Create analyze job

`POST /analyze`

Required JSON body:

```json
{"hours": 1, "user_id": "my_agent_01"}
```

Rules:

- `hours` is required
- `hours` must be a positive integer
- `user_id` is required
- `user_id` is trimmed by the server before use
- `user_id` must match `^[A-Za-z0-9_-]{1,128}$`
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
  -d '{"hours":1,"user_id":"my_agent_01"}'
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

Example response headers:

```http
HTTP/2 202
location: /analyze/analyze_job_2f205899562a4104868384e65f81c8c1
retry-after: 2
```

Validation failures you should expect:

- Missing `user_id` -> HTTP `422`
- Invalid `user_id` (spaces, punctuation like `!`, non-ASCII, too long) -> HTTP `422`
- `hours <= 0` -> HTTP `422`
- `hours` below runtime minimum config -> HTTP `400`

Real missing-parameter example:

```json
{
  "detail": [
    {
      "type": "missing",
      "loc": ["body", "user_id"],
      "msg": "Field required",
      "input": {"hours": 1}
    }
  ]
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

Status response fields:

- `success`
- `job_id`
- `status`
- `time_window_hours`
- `created_at`
- `started_at`
- `completed_at`
- `items_processed`
- `error`
- `result_available`

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

1. Send `POST /analyze` with `{"hours": N, "user_id": "YOUR_AGENT_ID"}`
2. Save `job_id`
3. Poll `GET /analyze/{job_id}` until status becomes `completed` or `failed`
4. If `completed`, call `GET /analyze/{job_id}/result`
5. Do **not** expect the final report from the initial POST

## Copy-Paste Workflow

Use this exact workflow for production:

```bash
API_KEY="YOUR_API_KEY"
BASE_URL="https://news.tradao.xyz"
USER_ID="my_agent_01"

CREATE_RESPONSE=$(curl -sS -X POST "${BASE_URL}/analyze" \
  -H "Authorization: Bearer ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d "{\"hours\":1,\"user_id\":\"${USER_ID}\"}")

JOB_ID=$(printf '%s' "${CREATE_RESPONSE}" | sed -n 's/.*"job_id":"\([^"]*\)".*/\1/p')

while true; do
  STATUS_RESPONSE=$(curl -sS \
    -H "Authorization: Bearer ${API_KEY}" \
    "${BASE_URL}/analyze/${JOB_ID}")

  STATUS=$(printf '%s' "${STATUS_RESPONSE}" | sed -n 's/.*"status":"\([^"]*\)".*/\1/p')
  echo "${STATUS_RESPONSE}"

  if [ "${STATUS}" = "completed" ]; then
    curl -sS \
      -H "Authorization: Bearer ${API_KEY}" \
      "${BASE_URL}/analyze/${JOB_ID}/result"
    break
  fi

  if [ "${STATUS}" = "failed" ]; then
    exit 1
  fi

  sleep 2
done
```

## Important Gotchas

- Do not call `POST /analyze` without `hours`
- Do not call `POST /analyze` without `user_id`
- Do not assume HTTP API behavior matches Telegram `/analyze`
- Telegram can auto-estimate a window when the parameter is omitted; HTTP API cannot
- Do not treat `202` as failure; here it means “accepted / still processing”
- The status endpoint can return `"success": false` while the job is still `queued` or `running`; use the `status` field as the source of truth
- Cloudflare or edge behavior can differ by client type; `curl` has been verified against production
- Header names may appear in lowercase on real responses, for example `location` and `retry-after`

## Verified Production Behavior

The following was verified on `https://news.tradao.xyz` on `2026-03-28`:

- `GET /health` returns `200`
- `POST /analyze` without `user_id` returns `422`
- `POST /analyze` with `{"hours":1,"user_id":"codex_api_test"}` returns `202`
- `GET /analyze/{job_id}` returns live job state
- `GET /analyze/{job_id}/result` returns `202` while running
- `GET /analyze/{job_id}/result` returns `200` with the final report after completion
- A real production job completed successfully with:
  - `job_id`: `analyze_job_8139f373cfe44b04aa956c30348e2e68`
  - status flow: `running -> completed`
  - `items_processed`: `25`
  - `time_window_hours`: `1`
