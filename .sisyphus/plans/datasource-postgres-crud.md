# Datasource Database Migration and CRUD Interfaces

## TL;DR
> **Summary**: Move datasource definitions out of `config.json` and into database-backed persistence, add normalized multi-tag support, and expose synchronous datasource create/list/delete through both REST API and Telegram while preserving current ingestion behavior.
> **Deliverables**:
> - Database-backed datasource source of truth with bootstrap import from `config.json`
> - Multi-tag datasource model and validation rules
> - REST create/list/delete endpoints under existing Bearer auth
> - Telegram create/list/delete commands under existing authorized-user checks
> - TDD coverage for repository, bootstrap, runtime loading, REST, and Telegram flows
> **Effort**: Large
> **Parallel**: YES - 2 waves
> **Critical Path**: 1 → 2 → 3 → 5 → 6/7/8/9/10

## Context
### Original Request
- Move datasource definitions from `config.json` into PostgreSQL and manage them from the database going forward.
- Add multi-tag support per datasource, e.g. `crypto`, `AI`, or multiple tags on the same datasource.
- Add datasource create/list/delete interfaces through both Telegram commands and REST API.

### Interview Summary
- Delete semantics are **hard delete**.
- Telegram must support datasource creation for **all supported types**, including `rest_api`.
- Permission model reuses the **existing API Bearer key** and **existing authorized Telegram users**.
- Testing strategy is **TDD**.

### Metis Review (gaps addressed)
- Keep the migration strictly **datasource-only**; do not expand into a broader config-to-database rewrite.
- Preserve current runtime crawl behavior by replacing datasource loading at the `execution_coordinator` seam rather than redesigning the crawler stack.
- Bound Telegram `rest_api` creation to a **single accepted JSON payload format** to avoid parser sprawl.
- Define bootstrap semantics, uniqueness rules, tag normalization, and active-crawl delete behavior explicitly in the plan.

## Work Objectives
### Core Objective
Replace config-file datasource definitions with database-backed datasource records that can be created, listed, and deleted via REST API and Telegram without requiring future edits to `config.json`.

### Deliverables
- New datasource persistence model and migrations
- Shared datasource validation/serialization rules, including tags
- Runtime datasource loading from repository-backed storage
- REST datasource create/list/delete endpoints
- Telegram datasource create/list/delete commands
- Automated tests for all new behavior

### Definition of Done (verifiable conditions with commands)
- `uv run pytest tests/test_datasource_repository.py -v` exits `0`.
- `uv run pytest tests/test_datasource_bootstrap.py -v` exits `0`.
- `uv run pytest tests/test_api_server.py -k datasource -v` exits `0`.
- `uv run pytest tests/test_telegram_command_handler_datasource.py -v` exits `0`.
- `uv run pytest tests/ -k "datasource or api_server or telegram_command_handler" -v` exits `0`.

### Must Have
- Datasource storage becomes database-backed runtime truth; `config.json` is bootstrap input only, not ongoing authority.
- Datasources support multiple normalized tags.
- REST and Telegram both support create/list/delete.
- `rss`, `x`, and `rest_api` are all valid datasource types in v1.
- Telegram create for all types uses one explicit JSON payload format after the command.
- Historical tables keep existing `source_name` / `source_type` snapshot fields; no foreign-key backfill is introduced.

### Must NOT Have (guardrails, AI slop patterns, scope boundaries)
- No datasource update/edit endpoint or command.
- No soft delete or `is_active` substitute.
- No tag-management subsystem, tag catalog UI, or report-generation work.
- No broader migration of unrelated config values from `config.json`.
- No historical backfill of datasource IDs into `content_items`, `analysis_jobs`, or `ingestion_jobs`.
- No free-form Telegram parser variants; only one accepted add-command payload shape.
- No storage of tags as comma-delimited strings.

## Verification Strategy
> ZERO HUMAN INTERVENTION - all verification is agent-executed.
- Test decision: **TDD** using existing `pytest` infrastructure.
- QA policy: Every task includes agent-executed validation and explicit failure-path coverage.
- Evidence: `.sisyphus/evidence/task-{N}-{slug}.{ext}`

## Execution Strategy
### Parallel Execution Waves
> Target: 5-8 tasks per wave. <3 per wave (except final) = under-splitting.
> Extract shared dependencies as Wave-1 tasks for max parallelism.

Wave 1: datasource contract/schema/runtime foundation (Tasks 1-5)
Wave 2: REST + Telegram management surfaces (Tasks 6-10)

### Dependency Matrix (full, all tasks)
| Task | Depends On | Blocks |
|---|---|---|
| 1 | — | 2, 3, 4 |
| 2 | 1 | 3, 5 |
| 3 | 1, 2 | 5, 6, 7, 8, 9, 10 |
| 4 | 1 | 6, 8, 9 |
| 5 | 2, 3 | 6, 7, 8, 9, 10 |
| 6 | 3, 4, 5 | F1-F4 |
| 7 | 3, 5 | F1-F4 |
| 8 | 3, 4, 5, 7 | F1-F4 |
| 9 | 3, 4, 5, 7 | F1-F4 |
| 10 | 3, 5, 7, 8, 9 | F1-F4 |

### Agent Dispatch Summary (wave → task count → categories)
- Wave 1 → 5 tasks → `deep`, `unspecified-high`, `quick`
- Wave 2 → 5 tasks → `unspecified-high`, `deep`, `writing`

## TODOs
> Implementation + Test = ONE task. Never separate.
> EVERY task MUST have: Agent Profile + Parallelization + QA Scenarios.

- [x] 1. Define datasource domain contract and failing tests

  **What to do**: Introduce a datasource domain model and repository contract that separate persisted datasource records from the existing crawler-facing `RSSSource` / `XSource` / `RESTAPISource` dataclasses. Lock in the v1 rules in tests first: supported `source_type` values are `rss`, `x`, and `rest_api`; tags are trimmed, lowercased, deduplicated, and sorted; tag count is capped at 16 and each tag length at 32; datasource uniqueness is enforced on `(source_type, name)`; hard delete is blocked when an `ingestion_jobs` row exists in `pending` or `running` status for the same `source_type` + `source_name` snapshot.
  **Must NOT do**: Do not add update/edit semantics, soft delete, or foreign keys from historical content/job tables to datasource IDs.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: this task fixes the shared contract that all later storage, runtime, REST, and Telegram work will depend on.
  - Skills: `[]` - no special skill required.
  - Omitted: [`git-master`] - no git action is part of plan execution.

  **Parallelization**: Can Parallel: NO | Wave 1 | Blocks: 2, 3, 4 | Blocked By: —

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `crypto_news_analyzer/models.py:101-227` - current crawler-facing source dataclasses and validation behaviors to preserve for runtime compatibility.
  - Pattern: `crypto_news_analyzer/domain/models.py:45-146` - existing domain-model serialization pattern (`to_dict()` / `from_dict()`).
  - Pattern: `crypto_news_analyzer/domain/repositories.py:17-129` - repository interface style to mirror for datasource persistence.
  - Test: `tests/test_api_server.py` - assertion style and fixture conventions for new datasource API coverage.
  - Test: `tests/test_telegram_command_handler_analyze.py` - stub-driven command handler test style to mirror.

  **Acceptance Criteria** (agent-executable only):
  - [ ] `uv run pytest tests/test_datasource_repository.py -k "contract or normalization or uniqueness or delete_guard" -v` exits `0`.
  - [ ] datasource contract tests prove tags normalize to lowercase, trimmed, deduplicated order.
  - [ ] datasource contract tests prove duplicate `(source_type, name)` records are rejected.
  - [ ] datasource contract tests prove delete is rejected when matching ingestion job status is `pending` or `running`.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Tag normalization contract
    Tool: Bash
    Steps: Run `uv run pytest tests/test_datasource_repository.py -k normalization -v`
    Expected: Test output contains `PASSED` for normalization cases and process exits 0
    Evidence: .sisyphus/evidence/task-1-datasource-contract.txt

  Scenario: Active-job delete guard
    Tool: Bash
    Steps: Run `uv run pytest tests/test_datasource_repository.py -k delete_guard -v`
    Expected: Test output shows deletion is rejected while matching ingestion job is pending/running
    Evidence: .sisyphus/evidence/task-1-datasource-contract-error.txt
  ```

  **Commit**: YES | Message: `test(datasource): add repository and normalization contracts` | Files: `crypto_news_analyzer/domain/*`, `tests/test_datasource_repository.py`

- [x] 2. Add datasource schema for Postgres and SQLite-backed test/runtime parity

  **What to do**: Add a new PostgreSQL migration after `001_init.sql` that creates `datasources` and `datasource_tags` tables. Use `datasources.id` as immutable primary key, store `source_type`, `name`, normalized config payload, created timestamp, and unique `(source_type, name)` constraint. Store tags in a separate `datasource_tags` table with one row per normalized tag so the design remains portable across PostgreSQL and SQLite-backed local/test runs. Mirror the same schema in the SQLite initialization path used by the storage layer so local tests and non-Postgres runtime do not regress.
  **Must NOT do**: Do not alter historical tables to add datasource foreign keys; do not use PostgreSQL-only array storage for tags.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: this is cross-backend schema work with migration and init-path coupling.
  - Skills: `[]` - no special skill required.
  - Omitted: [`grok-api-reference`] - no external API research is needed.

  **Parallelization**: Can Parallel: NO | Wave 1 | Blocks: 3, 5 | Blocked By: 1

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `migrations/postgresql/001_init.sql` - SQL naming and index style to follow for new migration.
  - Pattern: `crypto_news_analyzer/storage/data_manager.py:74-301` - SQLite/Postgres initialization seam that must stay aligned with SQL migrations.
  - Pattern: `crypto_news_analyzer/storage/repositories.py:376-412` - repository factory/backend dispatch conventions.
  - Pattern: `migrations/postgresql/README.md` - migration/backfill documentation conventions.

  **Acceptance Criteria** (agent-executable only):
  - [ ] `uv run pytest tests/test_datasource_bootstrap.py -k schema -v` exits `0`.
  - [ ] Postgres migration creates `datasources` and `datasource_tags` with the planned constraints and indexes.
  - [ ] SQLite initialization path creates equivalent tables required by datasource tests.
  - [ ] deleting a datasource cascades tag-row cleanup only; no historical-table mutation occurs.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Schema parity tests
    Tool: Bash
    Steps: Run `uv run pytest tests/test_datasource_bootstrap.py -k schema -v`
    Expected: Postgres and SQLite schema assertions pass, including unique constraint and tag cleanup behavior
    Evidence: .sisyphus/evidence/task-2-datasource-schema.txt

  Scenario: Historical-table isolation
    Tool: Bash
    Steps: Run `uv run pytest tests/test_datasource_bootstrap.py -k no_historical_backfill -v`
    Expected: Tests confirm datasource migration does not alter `content_items`, `analysis_jobs`, or `ingestion_jobs` schemas
    Evidence: .sisyphus/evidence/task-2-datasource-schema-error.txt
  ```

  **Commit**: YES | Message: `feat(storage): add datasource schema and tag tables` | Files: `migrations/postgresql/*`, `crypto_news_analyzer/storage/*`, `tests/test_datasource_bootstrap.py`

- [x] 3. Implement datasource repositories and bootstrap import logic

  **What to do**: Add datasource CRUD methods behind a dedicated repository abstraction and wire concrete storage implementations. Implement create/list/delete plus lookup helpers and active-job delete guard checks. Add bootstrap import logic that runs transactionally only when datasource storage is empty; it must read datasource arrays from `config.json`, convert them into datasource records, import them once, and then leave the database as the only runtime datasource source of truth. If datasource rows already exist, bootstrap must skip import and log a no-op outcome; it must not overwrite operator-managed rows.
  **Must NOT do**: Do not implement dual-write between `config.json` and database. Do not overwrite non-empty datasource tables from config.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: repository behavior and bootstrap semantics are central to the migration’s correctness.
  - Skills: `[]` - no special skill required.
  - Omitted: [`review-work`] - post-implementation review happens only in the final verification wave.

  **Parallelization**: Can Parallel: NO | Wave 1 | Blocks: 5, 6, 7, 8, 9, 10 | Blocked By: 1, 2

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `crypto_news_analyzer/storage/repositories.py:23-118` - concrete repository implementation style to mirror.
  - Pattern: `crypto_news_analyzer/storage/data_manager.py` - existing CRUD helper conventions and backend branching to reuse.
  - Pattern: `crypto_news_analyzer/config/manager.py:174-210` - current datasource retrieval contract bootstrap must replace without changing caller expectations.
  - Pattern: `config.json` - current datasource payload shape to import from during first-run bootstrap.
  - Pattern: `migrations/postgresql/001_init.sql:83-102` - `ingestion_jobs` snapshot fields (`source_type`, `source_name`, `status`) used for hard-delete blocking logic.

  **Acceptance Criteria** (agent-executable only):
  - [ ] `uv run pytest tests/test_datasource_repository.py -k "create or list or delete" -v` exits `0`.
  - [ ] `uv run pytest tests/test_datasource_bootstrap.py -k "bootstrap or idempotent" -v` exits `0`.
  - [ ] first bootstrap import inserts datasource rows from `config.json`; second bootstrap import inserts zero additional rows.
  - [ ] delete returns a conflict/guard failure when matching active ingestion jobs exist.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Idempotent bootstrap
    Tool: Bash
    Steps: Run `uv run pytest tests/test_datasource_bootstrap.py -k idempotent -v`
    Expected: First run creates N datasource rows; second run reports zero new rows and no duplicates
    Evidence: .sisyphus/evidence/task-3-datasource-bootstrap.txt

  Scenario: Bootstrap conflict safety
    Tool: Bash
    Steps: Run `uv run pytest tests/test_datasource_bootstrap.py -k skip_non_empty_table -v`
    Expected: Tests confirm non-empty datasource tables are not overwritten by config bootstrap
    Evidence: .sisyphus/evidence/task-3-datasource-bootstrap-error.txt
  ```

  **Commit**: YES | Message: `feat(storage): implement datasource repository and bootstrap` | Files: `crypto_news_analyzer/domain/*`, `crypto_news_analyzer/storage/*`, `tests/test_datasource_*`

- [x] 4. Add shared datasource validation and payload translation layer

  **What to do**: Create one shared validation/translation module used by both REST and Telegram surfaces. It must accept create payloads for `rss`, `x`, and `rest_api`; validate required fields by type; normalize tags; reject unsupported types; and convert validated datasource records into the existing crawler-facing dataclasses used by the crawl stage. For Telegram, define exactly one accepted add-command payload format: JSON following the command text, e.g. `/datasource_add { ... }`. For security, reject Telegram `rest_api` payloads containing obvious secret-bearing auth fields (for example authorization headers, bearer tokens, cookies, or API keys in inline payloads); those belong in REST-only or server-managed config paths.
  **Must NOT do**: Do not create separate validation stacks for REST and Telegram. Do not accept multiple Telegram payload syntaxes.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: this task locks input semantics shared by both interfaces and runtime conversion.
  - Skills: `[]` - no special skill required.
  - Omitted: [`llm-instructor`] - not relevant to datasource validation.

  **Parallelization**: Can Parallel: NO | Wave 1 | Blocks: 6, 8, 9, 10 | Blocked By: 1

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `crypto_news_analyzer/models.py:101-227` - canonical crawler-facing source object shapes to emit after validation.
  - Pattern: `crypto_news_analyzer/config/manager.py:413-489` - current per-type validation rules to preserve or centralize.
  - Pattern: `crypto_news_analyzer/api_server.py` - request-model and response-validation style.
  - Pattern: `crypto_news_analyzer/reporters/telegram_command_handler.py:641-727` - command parsing and validation error response style to mirror.

  **Acceptance Criteria** (agent-executable only):
  - [ ] `uv run pytest tests/test_datasource_repository.py -k payload_validation -v` exits `0`.
  - [ ] validation rejects malformed `rss`, `x`, and `rest_api` configs with type-specific errors.
  - [ ] Telegram payload tests prove JSON-after-command is the only supported add syntax.
  - [ ] Telegram validation rejects inline secret-bearing `rest_api` auth payloads with a concrete error message.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Type-specific validation
    Tool: Bash
    Steps: Run `uv run pytest tests/test_datasource_repository.py -k payload_validation -v`
    Expected: `rss`, `x`, and `rest_api` validation cases pass and invalid payloads are rejected with explicit messages
    Evidence: .sisyphus/evidence/task-4-datasource-validation.txt

  Scenario: Telegram secret rejection
    Tool: Bash
    Steps: Run `uv run pytest tests/test_telegram_command_handler_datasource.py -k secret_rejection -v`
    Expected: Test output shows inline token/header-bearing `rest_api` payloads are rejected in Telegram flows
    Evidence: .sisyphus/evidence/task-4-datasource-validation-error.txt
  ```

  **Commit**: YES | Message: `feat(datasource): add shared validation and translation layer` | Files: `crypto_news_analyzer/domain/*`, `crypto_news_analyzer/reporters/*`, `crypto_news_analyzer/api_server.py`, `tests/test_datasource_*`, `tests/test_telegram_command_handler_datasource.py`

- [x] 5. Switch runtime datasource loading from config arrays to repository-backed provider

  **What to do**: Preserve current call sites by keeping `ConfigManager` responsible for non-datasource settings while moving datasource retrieval behind a repository-backed provider. `ConfigManager.get_rss_sources()`, `get_x_sources()`, and `get_rest_api_sources()` must continue returning the existing typed source objects, but they should now read through the datasource repository/provider after optional bootstrap. Update the ingestion path so `_execute_crawling_stage()` continues to use `DataSourceFactory` and existing crawler adapters without needing to know whether sources came from JSON or database. Add regression tests proving ingestion can run when datasource arrays are absent or empty in `config.json` after bootstrap/database seeding.
  **Must NOT do**: Do not redesign the crawler factory or coordinator flow beyond the datasource loading seam.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: runtime compatibility is the highest regression-risk area.
  - Skills: `[]` - no special skill required.
  - Omitted: [`refactor`] - this is a bounded seam change, not an open-ended refactor exercise.

  **Parallelization**: Can Parallel: NO | Wave 1 | Blocks: 6, 7, 8, 9, 10 | Blocked By: 2, 3

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `crypto_news_analyzer/config/manager.py:174-210` - current datasource getter contract that callers depend on.
  - Pattern: `crypto_news_analyzer/execution_coordinator.py:837-889` - crawl-stage seam where datasource retrieval is consumed today.
  - Pattern: `crypto_news_analyzer/crawlers/data_source_factory.py:15-389` - factory contract and registered type names that runtime output must satisfy.
  - Pattern: `crypto_news_analyzer/crawlers/data_source_interface.py:14-171` - crawler contract the translated datasource objects must continue to satisfy.

  **Acceptance Criteria** (agent-executable only):
  - [ ] `uv run pytest tests/test_datasource_bootstrap.py -k runtime_loading -v` exits `0`.
  - [ ] `uv run pytest tests/test_execution_coordinator.py -k datasource -v` exits `0` if such coordinator coverage is added; otherwise the datasource runtime test suite exits `0`.
  - [ ] ingestion runtime tests prove DB-seeded datasources are crawled without requiring populated datasource arrays in `config.json`.
  - [ ] existing factory type names (`rss`, `x`, `rest_api`) remain unchanged at the crawl boundary.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: DB-backed runtime crawl setup
    Tool: Bash
    Steps: Run `uv run pytest tests/test_datasource_bootstrap.py -k runtime_loading -v`
    Expected: Tests confirm seeded datasource rows are returned through `ConfigManager` getters and consumed by the crawl stage
    Evidence: .sisyphus/evidence/task-5-runtime-loading.txt

  Scenario: Config-array independence
    Tool: Bash
    Steps: Run `uv run pytest tests/test_datasource_bootstrap.py -k empty_config_arrays -v`
    Expected: Tests confirm runtime still loads datasource rows from storage when JSON datasource arrays are empty or omitted
    Evidence: .sisyphus/evidence/task-5-runtime-loading-error.txt
  ```

  **Commit**: YES | Message: `refactor(ingestion): load datasources from repository` | Files: `crypto_news_analyzer/config/*`, `crypto_news_analyzer/execution_coordinator.py`, `tests/test_datasource_bootstrap.py`, `tests/test_execution_coordinator.py`

- [x] 6. Add synchronous REST datasource create/list/delete endpoints

  **What to do**: Extend the FastAPI app with `POST /datasources`, `GET /datasources`, and `DELETE /datasources/{datasource_id}` under the existing Bearer-auth dependency. Use shared datasource validation from Task 4, repository-backed persistence from Task 3, and synchronous HTTP semantics: create returns `201`, list returns `200`, delete returns `204`. Return `409` for duplicate `(source_type, name)` creation or active-job delete conflicts, and `422` for invalid payloads. List responses must include datasource `id`, `name`, `source_type`, normalized `tags`, and a safe config summary that does not leak prohibited secret-bearing fields.
  **Must NOT do**: Do not implement async job-style CRUD for datasources. Do not add update/filter endpoints beyond create/list/delete.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: endpoint work touches routing, auth reuse, validation, serialization, and test coverage.
  - Skills: `[]` - no special skill required.
  - Omitted: [`playwright`] - REST verification is better covered by pytest and curl-level checks.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: F1-F4 | Blocked By: 3, 4, 5

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `crypto_news_analyzer/api_server.py:199-207` - existing Bearer auth verification dependency to reuse.
  - Pattern: `crypto_news_analyzer/api_server.py:434-484` - endpoint declaration and response-shaping style.
  - Pattern: `tests/test_api_server.py` - FastAPI TestClient, auth, and error-path testing conventions.
  - Pattern: `crypto_news_analyzer/domain/models.py:45-146` - request/response serialization conventions for API-facing models.

  **Acceptance Criteria** (agent-executable only):
  - [ ] `uv run pytest tests/test_api_server.py -k datasource -v` exits `0`.
  - [ ] authorized `POST /datasources` creates `rss`, `x`, and `rest_api` datasources and returns `201` with normalized tags.
  - [ ] authorized `GET /datasources` returns created datasource records sorted deterministically by `source_type` then `name`.
  - [ ] authorized `DELETE /datasources/{datasource_id}` returns `204` and removes the datasource plus tag rows.
  - [ ] duplicate create or active-job delete attempts return `409`; missing auth returns the project’s existing auth failure response.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: REST create/list/delete happy path
    Tool: Bash
    Steps: Run `uv run pytest tests/test_api_server.py -k datasource -v`
    Expected: API tests pass for create, list, and delete with 201/200/204 responses and normalized tags
    Evidence: .sisyphus/evidence/task-6-rest-datasource.txt

  Scenario: REST duplicate and auth failures
    Tool: Bash
    Steps: Run `uv run pytest tests/test_api_server.py -k "datasource and (duplicate or unauthorized or delete_conflict)" -v`
    Expected: Duplicate create and active-job delete return conflict behavior; unauthorized access returns existing auth failure behavior
    Evidence: .sisyphus/evidence/task-6-rest-datasource-error.txt
  ```

  **Commit**: YES | Message: `feat(api): add datasource CRUD endpoints` | Files: `crypto_news_analyzer/api_server.py`, `crypto_news_analyzer/domain/*`, `tests/test_api_server.py`

- [x] 7. Register Telegram datasource commands and implement datasource listing

  **What to do**: Register new Telegram commands `/datasource_list`, `/datasource_add`, and `/datasource_delete` in the existing command handler while preserving current auth and rate-limit patterns. Implement `/datasource_list` first so operators can inspect seeded/created datasource records. The list response must include datasource ID, name, type, and normalized tags on each row so subsequent delete operations can target IDs unambiguously. Reuse existing authorization flow and async command handler structure already used for `/analyze`.
  **Must NOT do**: Do not introduce a separate admin-role framework. Do not omit datasource IDs from list output.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: command registration and response formatting must match existing Telegram architecture.
  - Skills: `[]` - no special skill required.
  - Omitted: [`dev-browser`] - Telegram command behavior is covered by unit tests, not browser automation.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: 8, 9, 10, F1-F4 | Blocked By: 3, 5

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `crypto_news_analyzer/reporters/telegram_command_handler.py:111-176` - command registration via `CommandHandler` in `_build_application()`.
  - Pattern: `crypto_news_analyzer/reporters/telegram_command_handler.py:328-408` - authorization and rate-limit guard style.
  - Pattern: `crypto_news_analyzer/reporters/telegram_command_handler.py:641-727` - async command handler structure and response messaging pattern.
  - Test: `tests/test_telegram_command_handler_analyze.py` - stub-driven command tests and authorization assertions.

  **Acceptance Criteria** (agent-executable only):
  - [ ] `uv run pytest tests/test_telegram_command_handler_datasource.py -k "list or registration" -v` exits `0`.
  - [ ] authorized `/datasource_list` returns a stable formatted list containing datasource IDs, names, types, and tags.
  - [ ] unauthorized datasource commands return the same denial path/message style used by existing protected commands.
  - [ ] command registration tests prove all three datasource commands are wired into the application.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Telegram datasource list happy path
    Tool: Bash
    Steps: Run `uv run pytest tests/test_telegram_command_handler_datasource.py -k list -v`
    Expected: Authorized list command returns datasource rows with ID, type, name, and tags
    Evidence: .sisyphus/evidence/task-7-telegram-list.txt

  Scenario: Telegram auth denial
    Tool: Bash
    Steps: Run `uv run pytest tests/test_telegram_command_handler_datasource.py -k unauthorized -v`
    Expected: Unauthorized datasource commands are rejected with the existing protected-command behavior
    Evidence: .sisyphus/evidence/task-7-telegram-list-error.txt
  ```

  **Commit**: YES | Message: `feat(telegram): register datasource commands and list handler` | Files: `crypto_news_analyzer/reporters/telegram_command_handler.py`, `tests/test_telegram_command_handler_datasource.py`

- [x] 8. Implement Telegram hard-delete command with active-job conflict handling

  **What to do**: Implement `/datasource_delete <datasource_id>` using repository-backed hard delete. The command must delete by immutable datasource ID only, confirm success with a clear response, and surface a conflict message when delete is blocked by a matching active ingestion job. Reuse authorization and error-handling style from existing commands and keep the handler non-interactive; no multi-step confirmation flow is introduced in v1.
  **Must NOT do**: Do not allow delete-by-name. Do not silently succeed on blocked deletes.

  **Recommended Agent Profile**:
  - Category: `quick` - Reason: once repository and command scaffolding exist, this is a focused handler + test change.
  - Skills: `[]` - no special skill required.
  - Omitted: [`frontend-ui-ux`] - not relevant.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: F1-F4 | Blocked By: 3, 5, 7

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `crypto_news_analyzer/reporters/telegram_command_handler.py:641-727` - command-handler structure, error responses, and async workflow style.
  - Pattern: `migrations/postgresql/001_init.sql:83-102` - ingestion job snapshot fields used by delete guard logic.
  - Test: `tests/test_telegram_command_handler_analyze.py` - handler test scaffolding for command invocations.

  **Acceptance Criteria** (agent-executable only):
  - [ ] `uv run pytest tests/test_telegram_command_handler_datasource.py -k delete -v` exits `0`.
  - [ ] authorized delete by datasource ID removes the datasource and confirms success.
  - [ ] delete of a datasource with a matching active ingestion job returns a clear conflict message.
  - [ ] malformed delete command without an ID returns a concrete usage/validation error.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Telegram delete happy path
    Tool: Bash
    Steps: Run `uv run pytest tests/test_telegram_command_handler_datasource.py -k delete_success -v`
    Expected: Authorized delete command removes the datasource and returns success text containing the datasource ID or name
    Evidence: .sisyphus/evidence/task-8-telegram-delete.txt

  Scenario: Telegram delete conflict and usage errors
    Tool: Bash
    Steps: Run `uv run pytest tests/test_telegram_command_handler_datasource.py -k "delete_conflict or delete_usage" -v`
    Expected: Active-job delete attempts and malformed commands return explicit error messages
    Evidence: .sisyphus/evidence/task-8-telegram-delete-error.txt
  ```

  **Commit**: YES | Message: `feat(telegram): add datasource delete command` | Files: `crypto_news_analyzer/reporters/telegram_command_handler.py`, `tests/test_telegram_command_handler_datasource.py`

- [x] 9. Implement Telegram add command for `rss` and `x` datasource payloads

  **What to do**: Implement `/datasource_add {json}` for `rss` and `x` payloads using the shared validator from Task 4. The command must parse the full JSON body from the message text after the command token, create the datasource through the repository/service layer, and respond with created ID, type, name, and normalized tags. Support only the single JSON-after-command syntax. Reject malformed JSON, unsupported types, duplicate names within the same type, and invalid type-specific config.
  **Must NOT do**: Do not add positional-argument variants. Do not special-case `rss` and `x` outside the shared validator.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: command parsing, validation, and persistence must line up exactly.
  - Skills: `[]` - no special skill required.
  - Omitted: [`ai-slop-remover`] - not relevant during planned implementation sequencing.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: 10, F1-F4 | Blocked By: 3, 4, 5, 7

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `crypto_news_analyzer/reporters/telegram_command_handler.py` - command parsing and message extraction patterns.
  - Pattern: `crypto_news_analyzer/models.py:101-179` - required config fields for `rss` and `x` source objects.
  - Pattern: `crypto_news_analyzer/config/manager.py:413-463` - existing validation intent for `rss` and `x` inputs.
  - Test: `tests/test_telegram_command_handler_analyze.py` - async command stubs and assertion structure.

  **Acceptance Criteria** (agent-executable only):
  - [ ] `uv run pytest tests/test_telegram_command_handler_datasource.py -k "add and (rss or x)" -v` exits `0`.
  - [ ] valid `rss` and `x` JSON payloads create datasource rows and return normalized success messages.
  - [ ] malformed JSON, duplicate `(source_type, name)`, and invalid `x` subtype/config payloads return concrete validation failures.
  - [ ] command parser accepts only one JSON-after-command syntax.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Telegram RSS/X add happy path
    Tool: Bash
    Steps: Run `uv run pytest tests/test_telegram_command_handler_datasource.py -k "add_rss or add_x" -v`
    Expected: Valid RSS and X payloads create datasource rows and return success messages with normalized tags
    Evidence: .sisyphus/evidence/task-9-telegram-add-rss-x.txt

  Scenario: Telegram RSS/X add validation failures
    Tool: Bash
    Steps: Run `uv run pytest tests/test_telegram_command_handler_datasource.py -k "duplicate or malformed_json or invalid_x" -v`
    Expected: Duplicate and malformed payloads are rejected with explicit validation messages
    Evidence: .sisyphus/evidence/task-9-telegram-add-rss-x-error.txt
  ```

  **Commit**: YES | Message: `feat(telegram): add datasource create command for rss and x` | Files: `crypto_news_analyzer/reporters/telegram_command_handler.py`, `tests/test_telegram_command_handler_datasource.py`

- [x] 10. Implement Telegram `rest_api` add flow and finalize cross-surface datasource UX

  **What to do**: Extend `/datasource_add {json}` to support `rest_api` payloads with the same single JSON-after-command syntax. Validate required `rest_api` fields using the shared validator, reject inline secret-bearing auth material, and make success/error messaging consistent with REST responses. Finalize datasource command help text so operators can discover the exact JSON format for `rss`, `x`, and `rest_api`, including an explicit example payload for `rest_api`. Add end-to-end regression coverage proving Telegram-created datasource records show up in `/datasource_list` and in REST `GET /datasources`.
  **Must NOT do**: Do not introduce a conversational multi-step form for Telegram creation. Do not allow inline bearer tokens, cookies, or API keys in Telegram `rest_api` payloads.

  **Recommended Agent Profile**:
  - Category: `writing` - Reason: this task is mostly user-facing command UX, examples, and consistency, on top of a bounded handler extension.
  - Skills: `[]` - no special skill required.
  - Omitted: [`playwright`] - no browser/UI work is involved.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: F1-F4 | Blocked By: 3, 4, 5, 7, 9

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `crypto_news_analyzer/models.py:181-227` - current `RESTAPISource` required fields and validation expectations.
  - Pattern: `crypto_news_analyzer/config/manager.py:465-489` - existing REST API datasource validation semantics.
  - Pattern: `crypto_news_analyzer/reporters/telegram_command_handler.py:164-176` - command registration/help discovery patterns.
  - Pattern: `tests/test_api_server.py` - REST output shape to align user-facing success/error data with.

  **Acceptance Criteria** (agent-executable only):
  - [ ] `uv run pytest tests/test_telegram_command_handler_datasource.py -k rest_api -v` exits `0`.
  - [ ] valid `rest_api` JSON payloads without secret-bearing auth material create datasource rows successfully.
  - [ ] inline secret-bearing `rest_api` payloads are rejected with a concrete Telegram error message.
  - [ ] help/usage output documents the exact supported `/datasource_add {json}` format and example payloads.
  - [ ] regression tests prove a Telegram-created datasource is visible in both Telegram list output and REST list output.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Telegram REST API add happy path
    Tool: Bash
    Steps: Run `uv run pytest tests/test_telegram_command_handler_datasource.py -k rest_api_success -v`
    Expected: Valid non-secret `rest_api` payload creates a datasource and returns success text with normalized tags
    Evidence: .sisyphus/evidence/task-10-telegram-rest-api.txt

  Scenario: Telegram REST API secret rejection and cross-surface visibility
    Tool: Bash
    Steps: Run `uv run pytest tests/test_telegram_command_handler_datasource.py -k "rest_api_secret_rejection or cross_surface_visibility" -v`
    Expected: Secret-bearing payloads are rejected; successful Telegram-created datasources appear in list/read surfaces consistently
    Evidence: .sisyphus/evidence/task-10-telegram-rest-api-error.txt
  ```

  **Commit**: YES | Message: `feat(telegram): support rest api datasource creation` | Files: `crypto_news_analyzer/reporters/telegram_command_handler.py`, `tests/test_telegram_command_handler_datasource.py`, `tests/test_api_server.py`

## Final Verification Wave (MANDATORY — after ALL implementation tasks)
> 4 review agents run in PARALLEL. ALL must APPROVE. Present consolidated results to user and get explicit "okay" before completing.
> **Do NOT auto-proceed after verification. Wait for user's explicit approval before marking work complete.**
> **Never mark F1-F4 as checked before getting user's okay.** Rejection or user feedback -> fix -> re-run -> present again -> wait for okay.
- [x] F1. Plan Compliance Audit — oracle
- [x] F2. Code Quality Review — unspecified-high
- [x] F3. Real Manual QA — unspecified-high (+ playwright if UI)
- [x] F4. Scope Fidelity Check — deep

## Commit Strategy
- Commit 1: `test(datasource): add repository and bootstrap contracts`
- Commit 2: `feat(storage): add datasource tables and repositories`
- Commit 3: `refactor(ingestion): load datasources from database`
- Commit 4: `feat(api): add datasource CRUD endpoints`
- Commit 5: `feat(telegram): add datasource management commands`

## Success Criteria
- Datasource creation, listing, and deletion no longer require editing `config.json`.
- Ingestion runtime pulls datasource definitions from repository-backed database storage.
- Tags are stored, normalized, returned, and filter-ready for future report segmentation.
- REST and Telegram surfaces enforce current auth rules and reject invalid payloads consistently.
- Bootstrap import is idempotent and does not duplicate datasource rows.
