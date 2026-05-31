# Railway Serverless DB Wakeup

## TL;DR
> **Summary**: Support Railway Serverless for the analysis service and a potentially sleeping Postgres by adding bounded DB connection retry/readiness in the storage layer. Do not make business code ping `/health`; keep ingestion常驻 and document that ingestion traffic may prevent shared Postgres from sleeping.
> **Deliverables**:
> - Configurable Postgres wake/retry settings in `StorageConfig`
> - Shared runtime Postgres connection helper used by `DataManager` and `SentMessageCacheManager`
> - New `/ready` endpoint with DB readiness check; existing `/health` contract preserved
> - Railway operator checklist for enabling Serverless on analysis + Postgres only
> - Tests for transient DB wake, failed DB readiness, health compatibility, and no ingestion sleep changes
> **Effort**: Medium
> **Parallel**: YES - 4 dependency-true waves
> **Critical Path**: Task 1 → Task 2 → Task 3 → Task 5 → Task 7 → Final Verification

## Context
### Original Request
User wants to reduce Railway cost after PostgreSQL HNSW indexes increased memory usage. They proposed enabling Railway Serverless/sleeping and having analysis/ingestion call an endpoint like `/health` before each Postgres operation to wake sleeping services.

### Interview Summary
- User selected target: **analysis + Postgres**.
- Decision: keep ingestion app out of serverless/sleep scope; ingestion remains a常驻 scheduler.
- Decision: do **not** call HTTP `/health` before DB operations.
- Decision: wake/verify Postgres through bounded DB connection retry and optional `SELECT 1` readiness.
- Decision: preserve `/health` as lightweight and add `/ready` for DB-aware readiness.
- Default applied: Railway service setting changes are documented operator steps only because the workspace is not linked and no Railway IDs were provided.

### Metis Review (gaps addressed)
- Always-on ingestion may keep the shared Postgres awake; the plan must state this limitation and not promise Postgres sleep savings while ingestion is actively connecting.
- Per-query `SELECT 1` is forbidden; readiness probes are only for `/ready` and connection validation/retry.
- Retry must be bounded and should not hide bad credentials/schema/query errors indefinitely.
- Railway health checks or external monitors hitting `/ready` can keep services awake; operator checklist must warn about this.

## Work Objectives
### Core Objective
Make analysis-service resilient to Railway cold starts and sleeping Postgres by handling transient Postgres connection failures in the storage layer, while preserving existing health behavior and avoiding ingestion serverless redesign.

### Deliverables
- `StorageConfig` fields for Postgres retry/wakeup behavior.
- A shared helper/module for Postgres runtime connection attempts and readiness checks.
- `DataManager._get_connection()` and `SentMessageCacheManager._get_connection()` use the helper.
- `/ready` endpoint returns DB-aware readiness status; `/health` remains unchanged.
- Tests prove transient connect failures retry and succeed, permanent failures are bounded, and ingestion runtime is untouched.
- Railway operator checklist documents enabling Serverless for analysis + Postgres and not ingestion.

### Definition of Done (verifiable conditions with commands)
- `uv run pytest tests/shared/test_config_manager.py tests/shared/test_postgres_storage_path.py tests/shared/test_cache_manager.py -v` passes.
- `uv run pytest tests/news/test_api_server.py tests/shared/test_ingestion_runtime.py -v` passes.
- `uv run mypy crypto_news_analyzer/` passes or shows no touched-file errors.
- `uv run flake8 crypto_news_analyzer/ tests/` passes or shows no touched-file errors if the repository has pre-existing unrelated failures.

### Must Have
- No code path pings `/health` before DB work.
- `/health` still returns only lightweight app status/initialized data.
- `/ready` performs bounded DB readiness check and returns deterministic healthy/unready status.
- Runtime Postgres retries cover both `crypto_news_analyzer/storage/data_manager.py` and `crypto_news_analyzer/storage/cache_manager.py`.
- Retry defaults are finite: max attempts 3, initial delay 1s, max delay 10s, connect timeout 10s.
- Ingestion app is not configured for sleep and no HTTP server is added to ingestion.

### Must NOT Have (guardrails, AI slop patterns, scope boundaries)
- Do not mutate Railway service settings without explicit project/service/environment IDs.
- Do not enable Serverless for ingestion in code or docs.
- Do not change `migrations/postgresql/remote_internal_backfill.py`.
- Do not add persistent connection pools that keep Postgres awake.
- Do not add a periodic background pinger; it would defeat Serverless sleep.
- Do not change HNSW indexes, pgvector schema, or database tuning.
- Do not document legacy `api-server` as primary runtime.

## Verification Strategy
> Evidence collection is ZERO HUMAN INTERVENTION - all verification commands and QA scenarios are agent-executed. Railway dashboard toggles remain operator steps unless explicit IDs are later supplied.
- Test decision: tests-after using existing pytest patterns plus focused new unit tests.
- QA policy: Every task has agent-executed scenarios.
- Evidence: `.omo/evidence/task-{N}-{slug}.{ext}`

## Execution Strategy
### Parallel Execution Waves
> Dependency-true waves only. Smaller waves are intentional because connection helper changes must land before storage/API tests.

Wave 1: Task 1 (config)
Wave 2: Task 2 (shared helper), Task 4 (health contract baseline), Task 6 (Railway checklist)
Wave 3: Task 3 (storage integration), Task 5 (ready endpoint)
Wave 4: Task 7 (quality gates)

### Dependency Matrix (full, all tasks)
| Task | Depends On | Blocks |
|---|---|---|
| 1 | None | 2, 6, 7 |
| 2 | 1 | 3, 5, 7 |
| 3 | 2 | 7 |
| 4 | None | 5, 7 |
| 5 | 2, 4 | 7 |
| 6 | 1 | 7 |
| 7 | 3, 5, 6 | Final Verification |

### Agent Dispatch Summary (wave → task count → categories)
| Wave | Task Count | Categories |
|---|---:|---|
| 1 | 1 | quick |
| 2 | 3 | quick, writing, unspecified-low |
| 3 | 2 | unspecified-low |
| 4 | 1 | unspecified-low |

## TODOs
> Implementation + Test = ONE task. Never separate.
> EVERY task MUST have: Agent Profile + Parallelization + QA Scenarios.

- [x] 1. Add bounded Postgres wake/retry config

  **What to do**: Add fields to `StorageConfig` in `crypto_news_analyzer/models.py`: `postgres_connect_max_attempts: int = 3`, `postgres_connect_initial_delay_seconds: float = 1.0`, `postgres_connect_max_delay_seconds: float = 10.0`, `postgres_connect_timeout_seconds: int = 10`. Validate positive values and `max_delay >= initial_delay`. Add config tests for defaults, explicit valid values, and invalid values.
  **Must NOT do**: Do not change SQLite behavior. Do not add Railway-specific fields to auth/LLM config.

  **Recommended Agent Profile**:
  - Category: `quick` - Reason: localized config/model validation.
  - Skills: [] - No external skill needed.
  - Omitted: [`use-railway`] - No Railway operation in this task.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: 2, 6, 7 | Blocked By: None

  **References**:
  - Pattern: `crypto_news_analyzer/models.py:337-383` - `StorageConfig` fields and validation.
  - Test: `tests/shared/test_config_manager.py` - config loading/validation tests.

  **Acceptance Criteria**:
  - [ ] `StorageConfig()` defaults match 3/1.0/10.0/10.
  - [ ] Invalid zero/negative attempts, delays, timeout raise `ValueError`.
  - [ ] `uv run pytest tests/shared/test_config_manager.py -v` exits 0.

  **QA Scenarios**:
  ```
  Scenario: Defaults are safe and finite
    Tool: Bash
    Steps: uv run python - <<'PY'
from crypto_news_analyzer.models import StorageConfig
c = StorageConfig()
assert c.postgres_connect_max_attempts == 3
assert c.postgres_connect_initial_delay_seconds == 1.0
assert c.postgres_connect_max_delay_seconds == 10.0
assert c.postgres_connect_timeout_seconds == 10
print('ok')
PY
    Expected: Prints `ok` and exits 0.
    Evidence: .omo/evidence/task-1-storage-defaults.txt

  Scenario: Invalid retry config is rejected
    Tool: Bash
    Steps: uv run pytest tests/shared/test_config_manager.py -k 'postgres_connect or storage' -v | tee .omo/evidence/task-1-storage-config-tests.txt
    Expected: Selected config tests pass.
    Evidence: .omo/evidence/task-1-storage-config-tests.txt
  ```

  **Commit**: YES | Message: `feat(storage): add postgres wake retry config` | Files: [`crypto_news_analyzer/models.py`, `tests/shared/test_config_manager.py`]

- [x] 2. Create shared Postgres connection/readiness helper

  **What to do**: Add a small runtime helper module under `crypto_news_analyzer/storage/` (recommended name: `postgres_connection.py`) that exposes a function such as `connect_postgres_with_retry(database_url, *, row_factory, config, logger)` and `check_postgres_ready(database_url, config)`. It should call `psycopg.connect(..., connect_timeout=config.postgres_connect_timeout_seconds, row_factory=dict_row)` with bounded exponential backoff. On successful readiness check, run `SELECT 1`; on normal connections, do not run extra `SELECT 1` before every query unless the helper is explicitly called for readiness. Preserve original exceptions for wrapping by callers.
  **Must NOT do**: Do not introduce a persistent pool. Do not sleep/retry around SQL query execution after a connection is already yielded. Do not catch exceptions forever.

  **Recommended Agent Profile**:
  - Category: `unspecified-low` - Reason: subtle error/retry behavior and test fakes.
  - Skills: [] - No external docs needed.
  - Omitted: [`use-railway`] - Local runtime helper only.

  **Parallelization**: Can Parallel: NO | Wave 2 | Blocks: 3, 5, 7 | Blocked By: 1

  **References**:
  - Pattern: `crypto_news_analyzer/storage/data_manager.py:428-446` - existing Postgres connection lifecycle.
  - Pattern: `crypto_news_analyzer/storage/cache_manager.py:196-212` - duplicate Postgres connection lifecycle.
  - Pattern: `crypto_news_analyzer/utils/errors.py:160-185` - existing exponential retry style if reuse is helpful.
  - Test: `tests/shared/test_datasource_bootstrap.py:28-49` - fake psycopg connection pattern.

  **Acceptance Criteria**:
  - [ ] Unit test: connect fails twice with transient exception then succeeds; helper attempts exactly 3 times.
  - [ ] Unit test: permanent failures stop after configured max attempts.
  - [ ] Unit test: readiness helper executes `SELECT 1` after connection succeeds.
  - [ ] Helper passes `connect_timeout` to `psycopg.connect`.

  **QA Scenarios**:
  ```
  Scenario: Sleeping Postgres wakes after transient failures
    Tool: Bash
    Steps: uv run pytest tests/shared/test_postgres_connection.py::test_connect_postgres_with_retry_succeeds_after_transient_failures -v | tee .omo/evidence/task-2-transient-retry.txt
    Expected: Test passes and asserts three attempts.
    Evidence: .omo/evidence/task-2-transient-retry.txt

  Scenario: Readiness probe is explicit only
    Tool: Bash
    Steps: uv run pytest tests/shared/test_postgres_connection.py::test_check_postgres_ready_executes_select_one -v | tee .omo/evidence/task-2-ready-select-one.txt
    Expected: Test passes and verifies `SELECT 1` only in readiness helper.
    Evidence: .omo/evidence/task-2-ready-select-one.txt
  ```

  **Commit**: YES | Message: `feat(storage): add postgres connection retry helper` | Files: [`crypto_news_analyzer/storage/postgres_connection.py`, `tests/shared/test_postgres_connection.py`]

- [x] 3. Integrate helper into runtime storage connection paths

  **What to do**: Replace direct `psycopg.connect` calls in `DataManager._get_connection()` and `SentMessageCacheManager._get_connection()` with the shared helper. Keep commit/rollback/close behavior and `StorageError` wrapping unchanged. Add tests for both storage paths using fake psycopg/helper behavior. Ensure SQLite path is unchanged.
  **Must NOT do**: Do not edit `migrations/postgresql/remote_internal_backfill.py`. Do not alter repository SQL or transaction semantics.

  **Recommended Agent Profile**:
  - Category: `unspecified-low` - Reason: touches core storage paths and must preserve behavior.
  - Skills: [] - No Railway mutation.
  - Omitted: [`use-railway`] - Local code only.

  **Parallelization**: Can Parallel: NO | Wave 3 | Blocks: 7 | Blocked By: 2

  **References**:
  - Pattern: `crypto_news_analyzer/storage/data_manager.py:428-446` - preserve context manager semantics.
  - Pattern: `crypto_news_analyzer/storage/cache_manager.py:196-212` - preserve cache connection semantics.
  - Test: `tests/shared/test_postgres_storage_path.py` - Postgres storage path tests.
  - Test: `tests/shared/test_cache_manager.py` - cache manager tests.

  **Acceptance Criteria**:
  - [ ] DataManager Postgres path retries transient connect failure and then completes operation.
  - [ ] SentMessageCacheManager Postgres path retries transient connect failure and then completes operation.
  - [ ] SQLite tests continue to pass.
  - [ ] StorageError message/operation remains compatible on permanent failure.

  **QA Scenarios**:
  ```
  Scenario: DataManager uses retry helper
    Tool: Bash
    Steps: uv run pytest tests/shared/test_postgres_storage_path.py -k 'retry or postgres' -v | tee .omo/evidence/task-3-data-manager-retry.txt
    Expected: Selected tests pass.
    Evidence: .omo/evidence/task-3-data-manager-retry.txt

  Scenario: Cache manager uses retry helper
    Tool: Bash
    Steps: uv run pytest tests/shared/test_cache_manager.py -k 'postgres or retry or connection' -v | tee .omo/evidence/task-3-cache-manager-retry.txt
    Expected: Selected tests pass.
    Evidence: .omo/evidence/task-3-cache-manager-retry.txt
  ```

  **Commit**: YES | Message: `fix(storage): retry postgres connects during wake` | Files: [`crypto_news_analyzer/storage/data_manager.py`, `crypto_news_analyzer/storage/cache_manager.py`, `tests/shared/test_postgres_storage_path.py`, `tests/shared/test_cache_manager.py`]

- [x] 4. Preserve `/health` contract with regression coverage

  **What to do**: Add/confirm tests that `/health` remains lightweight and returns `{"status":"healthy","initialized": <bool>}` without touching Postgres. If needed, monkeypatch DB readiness helper to raise and prove `/health` still returns its existing response.
  **Must NOT do**: Do not add DB checks to `/health`. Do not change status code or response shape for `/health`.

  **Recommended Agent Profile**:
  - Category: `quick` - Reason: API regression test only.
  - Skills: [] - No browser needed.
  - Omitted: [`playwright`] - HTTP tests use pytest/TestClient.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: 5, 7 | Blocked By: None

  **References**:
  - Pattern: `crypto_news_analyzer/api_server.py:1913-1920` - current `/health` implementation.
  - Test: `tests/news/test_api_server.py:405` - existing health initialized-state test.

  **Acceptance Criteria**:
  - [ ] `/health` tests pass with existing response shape.
  - [ ] Test proves `/health` does not call readiness helper.

  **QA Scenarios**:
  ```
  Scenario: Health remains lightweight
    Tool: Bash
    Steps: uv run pytest tests/news/test_api_server.py -k 'health' -v | tee .omo/evidence/task-4-health-tests.txt
    Expected: Health tests pass and no DB readiness helper is invoked.
    Evidence: .omo/evidence/task-4-health-tests.txt

  Scenario: DB readiness failure does not break health
    Tool: Bash
    Steps: uv run pytest tests/news/test_api_server.py::test_health_check_does_not_probe_database -v | tee .omo/evidence/task-4-health-no-db.txt
    Expected: Test passes.
    Evidence: .omo/evidence/task-4-health-no-db.txt
  ```

  **Commit**: YES | Message: `test(api): preserve lightweight health check` | Files: [`tests/news/test_api_server.py`]

- [x] 5. Add `/ready` DB readiness endpoint

  **What to do**: Add `GET /ready` in `register_infrastructure_routes()`. It should retrieve controller/storage config and call the readiness helper. Return `200` with JSON like `{"status":"ready","database":"ready","initialized":true}` when DB is reachable. Return `503` with JSON like `{"status":"not_ready","database":"unavailable","initialized":<bool>,"error":"..."}` when DB readiness fails. Keep errors sanitized; do not leak `DATABASE_URL`, credentials, hostnames with passwords, or stack traces.
  **Must NOT do**: Do not require Bearer auth for `/ready` unless `/health` currently does; keep infrastructure endpoint style consistent. Do not call `/ready` internally before every DB operation.

  **Recommended Agent Profile**:
  - Category: `unspecified-low` - Reason: API endpoint plus failure sanitization tests.
  - Skills: [] - No external docs needed.
  - Omitted: [`use-railway`] - Local endpoint only.

  **Parallelization**: Can Parallel: NO | Wave 3 | Blocks: 7 | Blocked By: 2, 4

  **References**:
  - Pattern: `crypto_news_analyzer/api_server.py:1913-1920` - infrastructure route registration pattern.
  - Pattern: `crypto_news_analyzer/api_server.py:1968-2052` - app state/controller setup.
  - Test: `tests/news/test_api_server.py` - FastAPI route tests.

  **Acceptance Criteria**:
  - [ ] `/ready` returns 200 and database ready JSON when helper succeeds.
  - [ ] `/ready` returns 503 and sanitized unavailable JSON when helper fails.
  - [ ] `/ready` response includes initialized state.
  - [ ] No response body includes `DATABASE_URL` or credential substrings.

  **QA Scenarios**:
  ```
  Scenario: Ready endpoint reports database ready
    Tool: Bash
    Steps: uv run pytest tests/news/test_api_server.py::test_ready_check_reports_database_ready -v | tee .omo/evidence/task-5-ready-ok.txt
    Expected: Test passes and response status is 200.
    Evidence: .omo/evidence/task-5-ready-ok.txt

  Scenario: Ready endpoint reports sanitized database failure
    Tool: Bash
    Steps: uv run pytest tests/news/test_api_server.py::test_ready_check_sanitizes_database_failure -v | tee .omo/evidence/task-5-ready-fail.txt
    Expected: Test passes; response status is 503 and contains no credentials.
    Evidence: .omo/evidence/task-5-ready-fail.txt
  ```

  **Commit**: YES | Message: `feat(api): add database readiness endpoint` | Files: [`crypto_news_analyzer/api_server.py`, `tests/news/test_api_server.py`]

- [x] 6. Document Railway operator checklist and ingestion limitation

  **What to do**: Update `docs/RAILWAY_DEPLOYMENT.md` or an existing Railway deployment section with a concise checklist: enable Serverless only for `crypto-news-analysis` and Postgres if Railway UI supports it; do not enable Serverless for `crypto-news-ingestion`; avoid external monitors that ping `/ready` frequently; use `DATABASE_URL` private networking, not `DATABASE_PUBLIC_URL`; expect first request cold-start/possible 502; shared ingestion traffic may keep Postgres awake and limit memory savings. Because Prometheus planning discovered current workspace is not linked, include “operator must verify in Railway dashboard” rather than claiming settings are applied.
  **Must NOT do**: Do not add new docs outside existing docs paths during execution unless no suitable Railway doc exists. Do not recommend legacy `api-server` runtime.

  **Recommended Agent Profile**:
  - Category: `writing` - Reason: deployment documentation only.
  - Skills: [`use-railway`] - Railway docs terminology should remain accurate.
  - Omitted: []

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: 7 | Blocked By: 1

  **References**:
  - External: Railway docs `/deployments/serverless` - Serverless/App-Sleeping behavior, cold boot, first request may 502, outbound traffic prevents sleep.
  - External: Railway docs `/pricing/cost-control` - UI path: service settings > Deploy > Serverless; use `DATABASE_URL` for private networking.
  - Project: `docs/RAILWAY_DEPLOYMENT.md` - current split-service deployment reference.
  - Project: `AGENTS.md` - production services are `crypto-news-analysis` and `crypto-news-ingestion`.

  **Acceptance Criteria**:
  - [ ] Deployment doc states ingestion should remain non-serverless unless redesigned.
  - [ ] Deployment doc warns ingestion DB traffic may keep Postgres awake.
  - [ ] Deployment doc says `/ready` is for external readiness only, not an internal pre-query ping.
  - [ ] Deployment doc does not mention legacy `api-server` as recommended runtime.

  **QA Scenarios**:
  ```
  Scenario: Railway checklist includes sleep boundaries
    Tool: Bash
    Steps: uv run python - <<'PY'
from pathlib import Path
text = Path('docs/RAILWAY_DEPLOYMENT.md').read_text()
assert 'Serverless' in text or 'sleep' in text.lower()
assert 'crypto-news-ingestion' in text
assert '/ready' in text
assert 'DATABASE_URL' in text
print('ok')
PY
    Expected: Prints `ok` and exits 0.
    Evidence: .omo/evidence/task-6-doc-check.txt

  Scenario: Legacy api-server is not recommended
    Tool: Bash
    Steps: uv run python - <<'PY'
from pathlib import Path
text = Path('docs/RAILWAY_DEPLOYMENT.md').read_text().lower()
assert 'api-server mode' not in text or 'deprecated' in text
print('ok')
PY
    Expected: Prints `ok` and exits 0.
    Evidence: .omo/evidence/task-6-no-legacy-runtime.txt
  ```

  **Commit**: YES | Message: `docs(railway): document serverless database wakeup` | Files: [`docs/RAILWAY_DEPLOYMENT.md`]

- [x] 7. Run focused quality gates and no-scope-creep checks

  **What to do**: Run all focused tests and static checks. Add a no-scope-creep check that `migrations/postgresql/remote_internal_backfill.py` is unchanged, no `/health` pre-DB call helper exists, and ingestion runtime tests still pass. Fix only issues caused by this plan.
  **Must NOT do**: Do not apply Railway settings. Do not edit unrelated modules. Do not skip `/ready` failure tests.

  **Recommended Agent Profile**:
  - Category: `unspecified-low` - Reason: command execution and small follow-up fixes.
  - Skills: [] - No mutation of Railway.
  - Omitted: [`git-master`] - Commit only if user explicitly asks.

  **Parallelization**: Can Parallel: NO | Wave 4 | Blocks: Final Verification | Blocked By: 3, 5, 6

  **References**:
  - Project commands: `AGENTS.md` says use `uv run pytest`, `uv run mypy`, `uv run flake8`.
  - Test files: `tests/shared/test_config_manager.py`, `tests/shared/test_postgres_storage_path.py`, `tests/shared/test_cache_manager.py`, `tests/news/test_api_server.py`, `tests/shared/test_ingestion_runtime.py`.

  **Acceptance Criteria**:
  - [ ] `uv run pytest tests/shared/test_config_manager.py tests/shared/test_postgres_connection.py tests/shared/test_postgres_storage_path.py tests/shared/test_cache_manager.py tests/news/test_api_server.py tests/shared/test_ingestion_runtime.py -v` exits 0.
  - [ ] `uv run mypy crypto_news_analyzer/` exits 0 or no touched-file errors.
  - [ ] `uv run flake8 crypto_news_analyzer/ tests/shared/test_config_manager.py tests/shared/test_postgres_connection.py tests/shared/test_postgres_storage_path.py tests/shared/test_cache_manager.py tests/news/test_api_server.py tests/shared/test_ingestion_runtime.py` exits 0.
  - [ ] `git diff --exit-code -- migrations/postgresql/remote_internal_backfill.py` exits 0.
  - [ ] No production code contains a function that pings `/health` before DB access.

  **QA Scenarios**:
  ```
  Scenario: Focused regression suite passes
    Tool: Bash
    Steps: uv run pytest tests/shared/test_config_manager.py tests/shared/test_postgres_connection.py tests/shared/test_postgres_storage_path.py tests/shared/test_cache_manager.py tests/news/test_api_server.py tests/shared/test_ingestion_runtime.py -v | tee .omo/evidence/task-7-focused-pytest.txt
    Expected: All selected tests pass.
    Evidence: .omo/evidence/task-7-focused-pytest.txt

  Scenario: No forbidden scope creep
    Tool: Bash
    Steps: git diff --exit-code -- migrations/postgresql/remote_internal_backfill.py && uv run python - <<'PY'
from pathlib import Path
bad = []
for path in Path('crypto_news_analyzer').rglob('*.py'):
    text = path.read_text().lower()
    if '/health' in text and 'postgres' in text and 'request' in text:
        bad.append(str(path))
assert not bad, bad
print('ok')
PY
    Expected: No migration diff and Python check prints `ok`.
    Evidence: .omo/evidence/task-7-no-scope-creep.txt
  ```

  **Commit**: YES | Message: `feat(railway): tolerate postgres wake on analysis cold start` | Files: [`crypto_news_analyzer/models.py`, `crypto_news_analyzer/storage/postgres_connection.py`, `crypto_news_analyzer/storage/data_manager.py`, `crypto_news_analyzer/storage/cache_manager.py`, `crypto_news_analyzer/api_server.py`, `docs/RAILWAY_DEPLOYMENT.md`, `tests/shared/test_postgres_connection.py`, `tests/shared/test_postgres_storage_path.py`, `tests/shared/test_cache_manager.py`, `tests/news/test_api_server.py`, `tests/shared/test_config_manager.py`, `tests/shared/test_ingestion_runtime.py`]

## Final Verification Wave (MANDATORY — after ALL implementation tasks)
> 4 review agents run in PARALLEL. ALL must APPROVE. Present consolidated results to user and get explicit "okay" before completing.
> **Do NOT auto-proceed after verification. Wait for user's explicit approval before marking work complete.**
> **Never mark F1-F4 as checked before getting user's okay.** Rejection or user feedback -> fix -> re-run -> present again -> wait for okay.
- [x] F1. Plan Compliance Audit — oracle  [APPROVED]
- [x] F2. Code Quality Review — unspecified-high  [APPROVED]
- [x] F3. Real Manual QA — unspecified-high  [APPROVED]
- [x] F4. Scope Fidelity Check — deep  [APPROVED]

## Commit Strategy
- One commit after all tasks and verification pass.
- Suggested message: `feat(railway): tolerate postgres wake on analysis cold start`
- Per-task `Commit` fields identify file scope and fallback messages; default execution should use this single final commit unless user explicitly requests atomic task commits.

## Success Criteria
- Analysis can cold-start and tolerate transient sleeping-Postgres connection failures with bounded retry.
- `/health` remains lightweight; `/ready` reports DB readiness.
- Ingestion remains常驻 and is not placed into serverless scope.
- Railway operator checklist accurately warns that ingestion traffic may keep Postgres awake.
- No HTTP `/health` ping is added before DB operations.
