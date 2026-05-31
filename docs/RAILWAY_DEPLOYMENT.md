# Railway Deployment Guide

Operator checklist for deploying the Cryptocurrency News Analyzer on Railway, including split-service topology, Serverless configuration, and cost control.

## 1. Split-Service Architecture Overview

The system runs as two long-lived Railway app services sharing one PostgreSQL/pgvector database:

| Service | Runtime Mode | Exposure | Responsibility |
|---|---|---|---|
| `crypto-news-analysis` | `analysis-service` | Public (domain: `news.tradao.xyz`) | HTTP API (`/analyze`, `/health`, `/ready`, `/semantic-search`), Telegram command listener |
| `crypto-news-ingestion` | `ingestion` | Private (no public domain) | RSS/X/REST crawling, Telegram/V2EX message collection, daily topic research scheduler |

Both services run from the same monorepo and share a single PostgreSQL/pgvector database. The ingestion service is a long-running scheduler loop; it must never sleep. The analysis service handles on-demand API traffic and is a candidate for Serverless.

The deprecated `api-server` runtime mode is **not recommended** for production. It exists only as a compatibility alias for `analysis-service` and should not be used in new deployments.

### Environment Variables (Shared)

Both services need these variables set via Railway's variable management:

```
DATABASE_URL=postgresql://postgres:<password>@<postgres-service>.railway.internal:5432/railway
```

**Important**: Use `DATABASE_URL` (private network) for production services. Do not use `DATABASE_PUBLIC_URL`, which routes through the TCP proxy and incurs egress charges. The `DATABASE_URL` provided by Railway automatically uses the private Wireguard mesh between services.

### Per-Service Variables

**`crypto-news-analysis`**:
```
API_KEY=<your-bearer-token>
KIMI_API_KEY=<your-kimi-key>
GROK_API_KEY=<your-grok-key>
TELEGRAM_BOT_TOKEN=<your-bot-token>
TELEGRAM_CHANNEL_ID=<your-channel-id>
TELEGRAM_AUTHORIZED_USERS=<user-ids>
```

**`crypto-news-ingestion`**:
```
EXECUTION_INTERVAL=300
X_CT0=<twitter-ct0>
X_AUTH_TOKEN=<twitter-auth-token>
KIMI_API_KEY=<your-kimi-key>
GROK_API_KEY=<your-grok-key>
```

## 2. Serverless / Sleep Configuration Checklist

Railway Serverless automatically puts a service to sleep after 10 minutes of no outbound traffic, and wakes it when inbound traffic arrives. While slept, the service incurs no compute costs.

### 2.1 Enable Serverless for `crypto-news-analysis` Only

The analysis service is a good Serverless candidate: it handles on-demand API requests and Telegram webhook deliveries. When idle, it can sleep without data loss.

**Operator step**: In the Railway dashboard, navigate to the `crypto-news-analysis` service. Go to **Settings > Deploy > Serverless** and enable the toggle. The operator must verify this is turned on and redeploy the service for the change to take effect.

### 2.2 Do NOT Enable Serverless for `crypto-news-ingestion`

The ingestion service runs a continuous scheduler loop. It crawls sources on a timer, processes topic research, and writes to the database. If put to sleep, it would miss crawl windows and research cycles.

**Operator step**: In the Railway dashboard, navigate to the `crypto-news-ingestion` service. Go to **Settings > Deploy > Serverless**. The operator must verify the Serverless toggle is **disabled** (off). The ingestion service must remain always-on.

### 2.3 PostgreSQL Serverless (Optional)

Railway may allow enabling Serverless on the PostgreSQL database service as well. When the database sleeps, it resumes on the next connection attempt, typically adding 2-5 seconds to the first query.

**Operator step**: In the Railway dashboard, navigate to the PostgreSQL service. Check **Settings > Deploy > Serverless** for availability. The operator must evaluate whether this feature is supported in the current Railway UI. If enabled, the operator must verify that both app services can tolerate the cold-start delay on first connection.

**Caveat**: Since `crypto-news-ingestion` is always running, its periodic database traffic may keep the shared PostgreSQL awake regardless, limiting the benefit of database-level Serverless. (See Section 3.)

### 2.4 Use `DATABASE_URL` (Private Networking)

Railway's private Wireguard mesh routes service-to-service traffic through internal DNS names under `railway.internal`. The `DATABASE_URL` variable uses this private network by default.

**Verified by**: The operator must confirm that `DATABASE_URL` points to a `railway.internal` hostname, not a public proxy endpoint. Example:

```
# Correct (private network, no egress charges):
DATABASE_URL=postgresql://postgres:password@postgres.railway.internal:5432/railway

# Incorrect (TCP proxy, incurs egress charges):
DATABASE_URL=postgresql://postgres:password@public-proxy.example.com:5432/railway
```

Do not substitute `DATABASE_PUBLIC_URL`. That variable routes traffic through the public TCP proxy and is meant for local development or external tooling, not for services running inside Railway.

### 2.5 Cold Start and First-Request 502 Handling

When a slept `crypto-news-analysis` service receives its first request, Railway wakes the container. During wake-up, the proxy may return a **502 Bad Gateway** before the application is ready to accept connections. Railway's platform probes the container every 30ms for up to 10 seconds before handing off the HTTP request.

The application includes bounded retry logic for database connections, so a 502 on the first request after a cold start is expected and harmless: the next request will succeed once the container is fully booted.

**Operator awareness**: External monitors or health-check systems that hit `/ready` or `/health` endpoints every few seconds will prevent the service from ever reaching the 10-minute idle threshold. The operator must adjust external monitor intervals to be longer than 10 minutes, or disable them entirely, if Serverless sleep is desired.

### 2.6 External Monitor Interference Warning

Frequent pings to `/health` or `/ready` count as inbound traffic and **do not prevent sleep** on their own (sleep is based on outbound traffic). However, if the application makes any outbound connection as a side effect of handling those pings (database queries, logging, telemetry), the service will never reach the 10-minute idle window.

**Operator step**: The operator must review the `/ready` endpoint implementation. If `/ready` performs a database readiness check, that outbound database connection resets the sleep timer. The operator should consider whether external monitoring is worth the cost of keeping the service perpetually awake.

## 3. Ingestion Limitation

The `crypto-news-ingestion` service is a long-running scheduler loop. It wakes on a timer (`EXECUTION_INTERVAL`, default 300 seconds), crawls configured RSS/X/REST sources, writes to the database, and runs daily topic research. This design makes it fundamentally incompatible with Serverless sleep.

### 3.1 Why Ingestion Cannot Sleep

Serverless sleep triggers after 10 minutes of zero outbound traffic. The ingestion service:
- Makes outbound HTTP requests to external news sources every crawl cycle.
- Writes crawled content to PostgreSQL on every cycle.
- Executes daily topic research that queries the database and calls external LLM APIs.
- Maintains a persistent scheduler loop that prevents idle detection.

Enabling Serverless on ingestion would cause it to sleep after 10 minutes of apparent inactivity (if no crawl is scheduled), missing subsequent crawl windows until an external request wakes it -- and no external requests target the ingestion service.

### 3.2 Database Wake-Up Side Effect

Because `crypto-news-ingestion` is always running, its regular database traffic (writes from crawling, reads from topic research) may keep the shared PostgreSQL service awake. If the operator enables PostgreSQL Serverless, the database may still never sleep due to the ingestion service's periodic queries.

This limits the cost savings from database-level Serverless. The primary cost reduction comes from enabling Serverless on `crypto-news-analysis` alone.

## 4. `/ready` Endpoint

The `GET /ready` endpoint is an HTTP readiness probe for external orchestration.

### 4.1 Behavior

- **200 OK**: The application is running and the database connection pool is healthy. Response body includes a `database` field indicating `ready` or `unavailable`.
- **503 Service Unavailable**: The application is running but the database is unreachable (connection timeout or pool exhaustion).

### 4.2 Intended Use: External Readiness Probes Only

`/ready` is designed for external monitoring systems (Railway health checks, uptime monitors, load balancers) to determine whether the service can accept traffic. It is **not** intended as an internal pre-query ping.

**Do not** call `/ready` from within the application before executing a database query. The endpoint performs its own database connection check, and calling it internally adds latency without providing useful information the connection pool does not already have.

### 4.3 Comparison with `/health`

| Endpoint | Checks Database | Use Case |
|---|---|---|
| `GET /health` | No | Lightweight liveness probe. Returns 200 if the process is alive. |
| `GET /ready` | Yes | Readiness probe. Returns 200 only if the database is reachable. |

Use `/health` for Railway's built-in health checks if database probing is not needed. Use `/ready` for external load balancers or uptime monitors that need to distinguish between "process alive" and "fully ready to serve."

### 4.4 Sleep Interaction

Since `/ready` queries the database, every call to it generates outbound traffic. This resets the 10-minute Serverless sleep timer. If an external monitor hits `/ready` every 5 minutes, the analysis service will never sleep.

**Operator step**: The operator must configure external `/ready` probes with an interval longer than 10 minutes, or disable them, to allow the service to enter Serverless sleep.

## 5. Cost Control Tips

### 5.1 Primary Savings: Serverless on Analysis Service

The `crypto-news-analysis` service typically handles infrequent, on-demand requests (API calls, Telegram commands, periodic `/news_analyze` triggers). Enabling Serverless converts its cost model from always-on compute to pay-per-request.

**Operator step**: The operator must enable Serverless on `crypto-news-analysis` (Settings > Deploy > Serverless) and redeploy. The operator must verify in the Railway billing dashboard that usage drops during idle periods.

### 5.2 Keep Ingestion Always-On

The `crypto-news-ingestion` service cannot sleep (Section 3.1). Its compute cost is unavoidable, but the operator can reduce its footprint:
- Extend `EXECUTION_INTERVAL` to reduce crawl frequency.
- Reduce the number of active datasources to lower per-cycle work.
- Limit topic research to fewer active topics.

### 5.3 Database Cost Tradeoffs

PostgreSQL is the persistent cost center in this architecture. Options for reducing it:

- **Enable PostgreSQL Serverless** (if available in Railway UI): The database sleeps when idle. However, the always-on ingestion service may prevent it from ever reaching idle (Section 3.2).
- **Right-size the database plan**: The operator must review actual storage and connection usage in the Railway dashboard and scale the plan accordingly.
- **Remove unused datasources and archived topics**: Less data stored means a lower storage footprint.

### 5.4 Monitoring Cost vs Serverless Sleep

Every external monitor that pings the service generates traffic. If cost reduction is the goal, the operator must weigh:
- **With monitors**: Higher reliability visibility, but the service may never sleep, negating Serverless savings.
- **Without monitors**: Lower visibility, but the service can sleep and save costs.

A practical middle ground: use Railway's built-in deployment logs for error detection and rely on Telegram `/status` for on-demand health checks, rather than continuous external monitoring.

## 6. Deployment Topology Summary

```
                           ┌──────────────────────────┐
     Public Internet ─────>│ crypto-news-analysis      │
     (news.tradao.xyz)     │ (analysis-service)        │
                           │ Serverless: ENABLED       │
                           └──────────┬───────────────┘
                                      │ private network
                                      │ DATABASE_URL
                                      ▼
                           ┌──────────────────────────┐
                           │ PostgreSQL + pgvector     │
                           │ Serverless: OPTIONAL      │
                           └──────────▲───────────────┘
                                      │ private network
                                      │ DATABASE_URL
                           ┌──────────┴───────────────┐
                           │ crypto-news-ingestion     │
                           │ (ingestion)               │
                           │ Serverless: DISABLED      │
                           └──────────────────────────┘
```

## 7. Verification Checklist

After initial deployment, the operator must verify:

- [ ] `crypto-news-analysis` domain resolves and returns 200 on `GET /health`
- [ ] `crypto-news-ingestion` has **no public domain** (Settings > Networking > Public Networking disabled)
- [ ] Both services use `DATABASE_URL` with a `railway.internal` hostname (not `DATABASE_PUBLIC_URL`)
- [ ] Serverless is **enabled** on `crypto-news-analysis` (Settings > Deploy > Serverless)
- [ ] Serverless is **disabled** on `crypto-news-ingestion` (Settings > Deploy > Serverless)
- [ ] `GET /ready` returns 200 with `{"database": "ready"}` when the database is reachable
- [ ] External monitor intervals are greater than 10 minutes or monitors are disabled
- [ ] Legacy `api-server` runtime is not in use (both services run `analysis-service` or `ingestion` modes)
