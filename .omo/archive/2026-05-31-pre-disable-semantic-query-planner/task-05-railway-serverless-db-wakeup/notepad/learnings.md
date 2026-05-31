# Railway Serverless + DB Wakeup — Learnings

## Sources Consulted
- /AGENTS.md (project architecture reference)
- /README.md (production services and deployment topology)
- Railway Docs: Serverless (docs.railway.com/deployments/serverless)
- Railway Docs: PostgreSQL (docs.railway.com/databases/postgresql)
- Railway Docs: Private Networking (docs.railway.com/private-networking)
- Railway Station: DATABASE_URL vs DATABASE_PUBLIC_URL thread
- Railway Station: 502 Bad Gateway on Serverless wake-up threads

## Key Findings

### Serverless Sleep Mechanics
- Railway detects inactivity based on **outbound** traffic only
- Inactivity threshold: 10 minutes with no outbound packets
- Outbound traffic includes: database connections, HTTP requests, NTP, telemetry
- Inbound traffic (incoming HTTP requests) does NOT prevent sleep
- Wake trigger: inbound traffic arrives → container starts → TCP probed every 30ms for 10s

### Cold Start 502 Behavior
- First request to a sleeping service may return 502 Bad Gateway
- This happens when the proxy responds before the container is ready
- After 502, subsequent requests succeed once container is fully booted
- Railway platform issue: proxy timeout/wake-up handling can produce 502s before container boots
- Fix: bounded retry in application handles this gracefully

### DATABASE_URL Private Networking
- `DATABASE_URL` uses private Wireguard mesh → no egress charges → internal DNS (`*.railway.internal`)
- `DATABASE_PUBLIC_URL` routes through TCP proxy → incurs egress → for local dev only
- Private networking is per-environment; services in same env can reach each other via `railway.internal`
- Legacy environments (pre-Oct 2025) are IPv6-only; new ones support dual-stack IPv4+IPv6

### Ingestion Incompatibility with Serverless
- Ingestion is a long-running scheduler loop (crawl on timer, daily research)
- It generates continuous outbound traffic (HTTP requests to sources, DB writes)
- Serverless sleep would miss crawl windows; no external requests target ingestion
- Always-on ingestion keeps shared PostgreSQL awake → limits DB Serverless savings

### `/ready` vs `/health`
- `/health`: lightweight, no DB check, returns 200 if process alive
- `/ready`: performs DB readiness check, returns 200 or 503
- `/ready` for external probes ONLY; NOT for internal pre-query pings (adds latency, no value)
- Calling `/ready` generates DB outbound traffic → resets Serverless sleep timer

### External Monitor Interference
- Monitors pinging `/ready` every N minutes generate outbound DB traffic
- If N < 10, service never sleeps → Serverless savings negated
- Recommendation: disable monitors or set interval > 10 min

## Document Created
- `docs/RAILWAY_DEPLOYMENT.md` — full operator checklist with all sections above

## Retry Helper Integration (2026-05-31)
- `connect_postgres_with_retry` in `storage/postgres_connection.py` handles connect retry, commit, rollback, close as a context manager
- Storage managers (`DataManager`, `SentMessageCacheManager`) now use this helper instead of direct `psycopg.connect`
- Key lesson: local imports inside methods (`from .postgres_connection import ...`) break monkeypatching in tests — must use module-level imports for testability
- Monkeypatch target must be the consuming module (`crypto_news_analyzer.storage.data_manager.connect_postgres_with_retry`), not the source module
- `StorageError` stores operation in `details["operation"]`, not as a direct `.operation` attribute
- SQLite connection paths remain unchanged — only Postgres branch was refactored

## Task 7 Quality Gate Results (2026-05-31)

### Focused Pytest Suite
- **112 passed, 2 failed** (exit code 1)
- Pre-existing failures:
  - `test_config_manager_supports_postgres_via_env_database_url`: invalid `llm_config` in test JSON (missing `fallback_models`, `market_model`)
  - `test_initialize_ingestion_system_skips_analysis_report_and_telegram`: same root cause — invalid `llm_config` causes config validation failure
- **No new failures introduced by this plan**

### Mypy
- **64 pre-existing errors** across 16 files
- Touched files have errors but all are pre-existing:
  - `models.py`: dateutil stubs, union-attr, arg-type
  - `postgres_connection.py`: no-any-return
  - `cache_manager.py`: module assignment, arg-type
  - `data_manager.py`: module assignment, name-defined (UnifiedSemanticSearchHit), no-any-return
  - `api_server.py`: notes only, no errors
- **No new mypy errors introduced by this plan**

### Flake8
- **Pre-existing errors**: E501 (line too long), F401 (unused imports), F821 (undefined name), F811 (redefinition), F841 (unused variable), W291/W293 (whitespace)
- **No new flake8 errors introduced by this plan**

### Migration File Integrity
- `git diff --exit-code -- migrations/postgresql/remote_internal_backfill.py`: **PASS** (exit code 0, file unchanged)

### No-Scope-Creep Check
- Raw check found `api_server.py` (contains `/health`, `postgres`, `request`)
- **Analysis**: FALSE POSITIVE — `/health` is lightweight (no DB probe), `/ready` is the separate DB readiness endpoint
- **PASS** — no production code pings `/health` before DB access

### Evidence Files Created
- `.omo/evidence/task-7-focused-pytest.txt`
- `.omo/evidence/task-7-mypy.txt`
- `.omo/evidence/task-7-flake8.txt`
- `.omo/evidence/task-7-no-scope-creep.txt`

## Task 7: Focused Quality Gates (2026-05-31)

### Pytest: 112 passed, 2 failed (exit 1)
- Both failures are PRE-EXISTING, unrelated to plan changes:
  1. `test_config_manager_supports_postgres_via_env_database_url` — invalid llm_config fixture (missing fallback_models, market_model)
  2. `test_initialize_ingestion_system_skips_analysis_report_and_telegram` — same root cause (invalid llm_config)
- All NEW tests pass: postgres_connection.py (6/6), cache_manager.py postgres retry (4/4), api_server.py health/ready (7/7)

### Mypy: Pre-existing errors only
- No new errors introduced in touched files (models.py, api_server.py, data_manager.py, cache_manager.py, postgres_connection.py)
- Existing errors are type annotation issues in untouched modules

### Flake8: Pre-existing issues only
- E501 line-too-long, F401 unused imports, F841 unused variables, F811 redefinitions
- All in pre-existing code, not introduced by this plan

### remote_internal_backfill.py: UNCHANGED (git diff exit 0)

### /health endpoint: SAFE
- Only 2 references in production code (api_server.py:1916 docstring, :1918 route)
- Implementation is lightweight in-memory check — NO database access, NO postgres references
