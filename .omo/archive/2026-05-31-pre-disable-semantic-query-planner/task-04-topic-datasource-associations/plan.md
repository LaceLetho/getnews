# Topic Datasource Associations

## TL;DR
> **Summary**: Add explicit many-to-many associations between Intelligence topics and intelligence datasources so topic research consumes only bound sources instead of the global intelligence source pool.
> **Deliverables**:
> - PostgreSQL + SQLite schema support for topic-datasource links and raw item datasource identity
> - Repository methods and scoped raw item queries
> - Scheduler behavior for empty/scoped associations
> - HTTP API and Telegram commands for viewing and updating associations
> - Tests-after coverage for repository, scheduler, API, Telegram, and schema smoke
> **Effort**: Large
> **Parallel**: YES - 5 waves
> **Critical Path**: Task 1 → Task 3 → Task 4 → Task 5 → Task 6/7/8 → Task 9/10/11

## Context
### Original Request
用户需要改造 intelligence 管线的 topic 与数据源对应关系逻辑：当前所有 topic 共用 intelligence 的所有数据源；目标是单独建立 topic 与 intelligence datasource 的多对多关联，并增加命令与接口用于查询和设定关联。

### Interview Summary
- Existing topics after migration: associate to all existing intelligence datasources to preserve current behavior.
- New topics default: empty datasource association when omitted.
- Empty association research: skip topic, do not call LLM, do not advance checkpoint.
- Checkpoint granularity: keep topic-level checkpoint/cursor.
- Association changes: no automatic historical backfill/reset.
- Management surfaces: both HTTP API and Telegram commands.
- Test strategy: tests-after plus mandatory agent-executed QA.

### Metis Review (gaps addressed)
- Added raw-item identity guardrail: topic links use datasource IDs, so `raw_intelligence_items` must carry stable `datasource_id`; source-type/source-id mapping is only for best-effort backfill.
- Added SQLite schema requirement, not only PostgreSQL migrations.
- Added safe datasource summary requirement; never expose `config_payload` secrets through association endpoints or Telegram output.
- Added datasource deletion guardrail: associated datasources are in-use and deletion returns `409` until unbound.
- Added idempotent PUT/POST/DELETE semantics and all-or-nothing validation.

## Work Objectives
### Core Objective
Make Intelligence topic research datasource-scoped: each topic reads only raw intelligence items from datasources explicitly associated with that topic.

### Deliverables
- `intelligence_topic_datasources` join table with unique `(topic_id, datasource_id)` relation.
- Nullable `raw_intelligence_items.datasource_id`, written during collection and best-effort backfilled.
- Repository interface and implementation for association get/set/add/remove.
- Repository SQL filtering raw items by associated `datasource_id` before `LIMIT`.
- Scheduler skip path for topics with zero associations.
- HTTP endpoints for topic datasource associations.
- Telegram commands for topic datasource associations.
- Automated tests and agent QA evidence.

### Definition of Done (verifiable conditions with commands)
- `uv run pytest tests/intelligence/ -v` passes.
- `uv run pytest tests/shared/test_datasource_repository.py tests/shared/test_telegram_command_handler_datasource.py tests/news/test_api_server.py -v` passes, updated if endpoint tests move.
- `uv run mypy crypto_news_analyzer/` passes or existing baseline deviations are documented in `.omo/evidence/final-mypy.txt`.
- `uv run flake8 crypto_news_analyzer/` passes or existing baseline deviations are documented in `.omo/evidence/final-flake8.txt`.
- Manual agent QA proves topic A bound to source X does not analyze source Y raw items.

### Must Have
- Only `DataSourcePurpose.INTELLIGENCE` datasources may be linked to topics.
- Existing topics are backfilled to all existing intelligence datasources.
- New topics created without datasource IDs have zero associations.
- `PUT []` is valid and disables scheduled research for that topic.
- Empty association does not call LLM and does not advance checkpoint.
- Association update is transactional and all-or-nothing.
- Raw item scoped query filters in SQL before `LIMIT`.
- API/Telegram responses show safe datasource summaries only.

### Must NOT Have (guardrails, AI slop patterns, scope boundaries)
- MUST NOT modify News-domain `ContentItem` behavior or `/analyze` behavior.
- MUST NOT allow news datasources to be linked to intelligence topics.
- MUST NOT introduce per-datasource checkpoints.
- MUST NOT automatically reset/backfill topic checkpoints after association changes.
- MUST NOT fetch global raw items and filter in Python.
- MUST NOT expose datasource `config_payload` secrets.
- MUST NOT refactor legacy entry-based intelligence pipeline.
- MUST NOT add admin UI, tag-based dynamic associations, or broad scheduler rewrites.

## Verification Strategy
> Verification is agent-executed, then gated by explicit user approval in the Final Verification Wave.
- Test decision: tests-after using existing pytest, FastAPI `TestClient`, SQLite repository, and Telegram `AsyncMock` patterns.
- QA policy: Every task has agent-executed scenarios.
- Evidence: `.omo/evidence/task-{N}-{slug}.{ext}`

## Execution Strategy
### Parallel Execution Waves
> Target: 5-8 tasks per wave. <3 per wave (except final) = under-splitting.
> Extract shared dependencies as Wave-1 tasks for max parallelism.

Wave 1: Task 1 schema foundation; Task 2 domain/repository contracts.
Wave 2: Task 3 collection/raw identity.
Wave 3: Task 4 repository implementation.
Wave 4: Task 5 scheduler integration; Task 6 HTTP API; Task 7 Telegram commands; Task 8 datasource deletion guard.
Wave 5: Task 9 repository/scheduler tests; Task 10 API/Telegram/schema tests; Task 11 docs/help text.

### Dependency Matrix (full, all tasks)
- Task 1 blocks Tasks 3, 4, 8, 9, 10.
- Task 2 blocks Tasks 4, 5, 6, 7, 9, 10.
- Task 3 blocks Tasks 4, 5, 9.
- Task 4 blocks Tasks 5, 6, 7, 8, 9, 10.
- Task 5 blocks Task 9.
- Task 6 blocks Task 10.
- Task 7 blocks Task 10 and Task 11.
- Task 8 blocks Task 10.
- Tasks 9-11 block Final Verification Wave.

### Agent Dispatch Summary (wave → task count → categories)
- Wave 1 → 2 tasks → `unspecified-high`, `deep`
- Wave 2 → 1 task → `unspecified-high`
- Wave 3 → 1 task → `unspecified-high`
- Wave 4 → 4 tasks → `unspecified-high`, `quick`
- Wave 5 → 3 tasks → `unspecified-high`, `writing`

## TODOs
> Implementation + Test = ONE task. Never separate.
> EVERY task MUST have: Agent Profile + Parallelization + QA Scenarios.

- [x] 1. Add datasource association schema and migration backfill

  **What to do**: Add PostgreSQL migration `migrations/postgresql/011_topic_datasource_association.sql` and equivalent SQLite schema/bootstrap changes in storage initialization. Create `intelligence_topic_datasources(topic_id, datasource_id, created_at)` with uniqueness on `(topic_id, datasource_id)`, indexes on both columns, `topic_id` FK `ON DELETE CASCADE`, and `datasource_id` FK `ON DELETE RESTRICT`/`NO ACTION` so datasource deletion is blocked while associated. Add nullable `raw_intelligence_items.datasource_id` with `ON DELETE SET NULL` or no hard FK if existing raw history constraints make FK unsafe, plus an index. PostgreSQL migration and SQLite/bootstrap behavior must both backfill every existing topic to every existing datasource where `purpose = 'intelligence'`. Add best-effort raw item datasource_id backfill using `source_type` + existing source identifier mapping. Include idempotent `IF NOT EXISTS` / safe alter behavior matching existing migrations. Add schema/backfill tests in this same task.
  **Must NOT do**: Do not delete raw items. Do not make `raw_intelligence_items.datasource_id` non-null. Do not create per-datasource checkpoints. Do not backfill new topics to all sources after migration.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: schema and migration changes affect production data safety.
  - Skills: [] - No external skill required.
  - Omitted: [`use-railway`] - Not deploying or operating production infra.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: Tasks 3, 4, 8, 9, 10 | Blocked By: none

  **References**:
  - Pattern: `migrations/postgresql/002_datasource_schema.sql` - datasource table schema and purpose/source_type/name uniqueness.
  - Pattern: `migrations/postgresql/009_topic_only_intelligence_schema.sql` - topic-only table/index/checkpoint migration style.
  - Pattern: `migrations/postgresql/README.md` - manual migration expectations.
  - Pattern: `crypto_news_analyzer/storage/repositories.py` - SQLite/Postgres repository schema initialization patterns.

  **Acceptance Criteria**:
  - [ ] New PostgreSQL migration contains `intelligence_topic_datasources` and `raw_intelligence_items.datasource_id` changes.
  - [ ] SQLite in-memory repository initialization creates the same logical structures.
  - [ ] PostgreSQL migration backfills existing topics to all existing intelligence datasources only.
  - [ ] SQLite/bootstrap path backfills existing topics to all existing intelligence datasources only when initializing/upgrading local storage.
  - [ ] News datasources are not backfilled into topic associations.
  - [ ] Raw item datasource_id backfill leaves unmappable rows `NULL` rather than guessing incorrectly.

  **QA Scenarios**:
  ```
  Scenario: Existing topic compatibility backfill
    Tool: Bash
    Steps: Run targeted schema/backfill test or migration smoke command created in this task; inspect generated evidence file.
    Expected: Existing topic has one association per existing intelligence datasource and zero news datasource associations.
    Evidence: .omo/evidence/task-1-schema-backfill.txt

  Scenario: Unmapped raw item remains safe
    Tool: Bash
    Steps: Run schema smoke with a raw item whose source_type/source_id does not match any datasource.
    Expected: raw item remains present with datasource_id NULL; migration does not fail.
    Evidence: .omo/evidence/task-1-unmapped-raw-item.txt
  ```

  **Commit**: NO | Message: `feat(intelligence): add topic datasource schema` | Files: [migrations/postgresql/011_topic_datasource_association.sql, crypto_news_analyzer/storage/repositories.py]

- [x] 2. Add domain and repository contracts for topic datasource associations

  **What to do**: Update `crypto_news_analyzer/domain/models.py` and `crypto_news_analyzer/domain/repositories.py` with explicit association contracts. Add a safe datasource summary type or reuse existing safe summary shape if present. Add repository ABC methods: `get_topic_datasource_ids(topic_id)`, `set_topic_datasources(topic_id, datasource_ids)`, `add_topic_datasources(topic_id, datasource_ids)`, `remove_topic_datasources(topic_id, datasource_ids)`, and a scoped raw item method or extended `get_raw_items_since(..., datasource_ids=...)`. Define validation semantics in docstrings: unknown topic = not found, unknown datasource = not found, non-intelligence datasource = validation error, duplicate IDs normalized/deduped, mixed invalid set fails atomically. Add import/serialization tests in this same task.
  **Must NOT do**: Do not add datasource associations to News models. Do not expose raw `config_payload` in any public response model.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: contract choices determine all downstream implementations.
  - Skills: [] - No special skill needed.
  - Omitted: [`llm-instructor`] - Not changing structured LLM output.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: Tasks 4, 5, 6, 7, 9, 10 | Blocked By: none

  **References**:
  - API/Type: `crypto_news_analyzer/domain/models.py:56` - `DataSourcePurpose` enum.
  - API/Type: `crypto_news_analyzer/domain/models.py:192` - `DataSource` model.
  - API/Type: `crypto_news_analyzer/domain/models.py:779` - `IntelligenceTopic` model.
  - API/Type: `crypto_news_analyzer/domain/repositories.py:375` - `DataSourceRepository` ABC.
  - API/Type: `crypto_news_analyzer/domain/repositories.py:403` - `IntelligenceRepository` ABC.

  **Acceptance Criteria**:
  - [ ] Repository contracts document all-or-nothing replacement and idempotent add/remove semantics.
  - [ ] Contracts preserve topic-level checkpoint semantics.
  - [ ] Public summary type excludes datasource secrets.
  - [ ] Existing type imports remain acyclic.

  **QA Scenarios**:
  ```
  Scenario: Contract imports load
    Tool: Bash
    Steps: Run `uv run python -c "from crypto_news_analyzer.domain.repositories import IntelligenceRepository; from crypto_news_analyzer.domain.models import DataSourcePurpose"`.
    Expected: Command exits 0 with no import cycle.
    Evidence: .omo/evidence/task-2-contract-imports.txt

  Scenario: Safe summary excludes config payload
    Tool: Bash
    Steps: Run a small unit test or type-level assertion added in this task for safe summary serialization.
    Expected: Serialized datasource association summary has id, source_type, name, tags; no raw config_payload.
    Evidence: .omo/evidence/task-2-safe-summary.txt
  ```

  **Commit**: NO | Message: `feat(intelligence): define topic datasource contracts` | Files: [crypto_news_analyzer/domain/models.py, crypto_news_analyzer/domain/repositories.py]

- [x] 3. Persist datasource_id on newly collected raw intelligence items

  **What to do**: Update intelligence collection flow so every `RawIntelligenceItem` produced from a database `DataSource` carries that datasource's stable `DataSource.id` into `raw_intelligence_items.datasource_id`. Modify `IntelligencePipeline._list_intelligence_datasources()`, source creation/saving flow, and raw item serialization only as needed. Keep `source_type` and `source_id` unchanged for compatibility and dedup behavior. Add collector/raw storage tests in this same task.
  **Must NOT do**: Do not couple `ContentItem` or News crawlers to intelligence datasource IDs. Do not remove legacy `source_id` fields from raw intelligence items.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: data identity must be correct to prevent silent research gaps.
  - Skills: [] - No special skill needed.
  - Omitted: [`bird-commands-reference`] - X/Twitter crawling is unrelated.

  **Parallelization**: Can Parallel: NO | Wave 2 | Blocks: Tasks 4, 5, 9 | Blocked By: Task 1

  **References**:
  - Pattern: `crypto_news_analyzer/intelligence/pipeline.py:20` - `IntelligencePipeline` collection flow.
  - Pattern: `crypto_news_analyzer/intelligence/pipeline.py:94` - `_list_intelligence_datasources()` lists all intelligence datasources.
  - Pattern: `crypto_news_analyzer/intelligence/pipeline.py:212` - `_source_identifier()` source identity mapping.
  - Pattern: `crypto_news_analyzer/storage/repositories.py:578` - `SQLiteIntelligenceRepository` raw item persistence.

  **Acceptance Criteria**:
  - [ ] New raw intelligence items saved from Telegram/V2EX datasources include datasource_id.
  - [ ] Existing `source_type`/`source_id` behavior is unchanged.
  - [ ] If a raw item is created without a DB datasource context, datasource_id remains NULL and is excluded from scoped topic research.

  **QA Scenarios**:
  ```
  Scenario: Collector writes datasource_id
    Tool: Bash
    Steps: Run a unit test with fake intelligence datasource and fake collected raw item.
    Expected: Stored raw item row has datasource_id equal to DataSource.id.
    Evidence: .omo/evidence/task-3-collector-datasource-id.txt

  Scenario: Legacy raw item compatibility
    Tool: Bash
    Steps: Save a RawIntelligenceItem without datasource_id through repository compatibility path.
    Expected: Save succeeds; datasource_id is NULL; source_type/source_id remain unchanged.
    Evidence: .omo/evidence/task-3-legacy-raw-item.txt
  ```

  **Commit**: NO | Message: `feat(intelligence): persist raw datasource identity` | Files: [crypto_news_analyzer/intelligence/pipeline.py, crypto_news_analyzer/domain/models.py, crypto_news_analyzer/storage/repositories.py]

- [x] 4. Implement association repository methods and scoped raw item SQL

  **What to do**: Implement association CRUD in `crypto_news_analyzer/storage/repositories.py` for SQLite/Postgres-compatible SQL. `set_topic_datasources` is full replacement, transactional, and accepts `[]`. `add` and `remove` are idempotent no-ops for already-present/missing associations. Validate topic exists, all datasource IDs exist, and every datasource has `purpose == DataSourcePurpose.INTELLIGENCE`; fail the entire request on any invalid ID. Update raw item query to filter by datasource IDs in SQL before ordering/limit. Keep topic-level cursor. Prefer composite cursor safety using existing checkpoint payload if already available; do not introduce per-datasource checkpoint. Add repository CRUD/query tests in this same task.
  **Must NOT do**: Do not Python-filter after LIMIT. Do not partially update when mixed valid/invalid datasource IDs are supplied.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: transactional repository semantics and SQL correctness are central.
  - Skills: [] - No special skill needed.
  - Omitted: [`use-railway`] - No live database operation required.

  **Parallelization**: Can Parallel: NO | Wave 3 | Blocks: Tasks 5, 6, 7, 8, 9, 10 | Blocked By: Tasks 1, 2, 3

  **References**:
  - Pattern: `crypto_news_analyzer/storage/repositories.py:1008` - current `get_raw_items_since` fetches all raw items and must be fixed.
  - Pattern: `tests/shared/test_datasource_repository.py` - datasource repository CRUD and duplicate/race test style.
  - Pattern: `tests/intelligence/test_raw_intelligence_storage.py` - SQLite raw intelligence storage test style.

  **Acceptance Criteria**:
  - [ ] `get_topic_datasource_ids(topic_id)` returns deterministic ID ordering.
  - [ ] `set_topic_datasources(topic_id, [])` removes all associations.
  - [ ] Non-intelligence datasource validation rejects the full update.
  - [ ] Scoped raw item query includes only rows whose `datasource_id` is in associated IDs.
  - [ ] Rows with `datasource_id IS NULL` are excluded from scoped topic research.

  **QA Scenarios**:
  ```
  Scenario: Atomic replacement rejects mixed invalid IDs
    Tool: Bash
    Steps: Run repository test setting [valid_intelligence_id, news_id, missing_id].
    Expected: Method raises validation/not-found error and existing associations remain unchanged.
    Evidence: .omo/evidence/task-4-atomic-validation.txt

  Scenario: SQL filters before limit
    Tool: Bash
    Steps: Seed 20 unbound/noisy rows and 2 bound rows, call scoped query with limit 2.
    Expected: Returned rows are the 2 bound rows; noisy rows do not consume the limit.
    Evidence: .omo/evidence/task-4-sql-before-limit.txt
  ```

  **Commit**: NO | Message: `feat(intelligence): implement topic datasource repository` | Files: [crypto_news_analyzer/storage/repositories.py]

- [x] 5. Enforce datasource associations in topic research scheduler

  **What to do**: Update `crypto_news_analyzer/intelligence/topic_research.py` so scheduled research loads datasource associations for each topic before fetching raw messages. If a topic has zero associations, skip the topic with explicit log/status evidence, do not call LLM, and do not update checkpoint. If a topic has associations, pass datasource IDs to repository scoped raw item query. Association changes do not reset checkpoint. Add scheduler skip/filter tests in this same task.
  **Must NOT do**: Do not create per-datasource checkpoints. Do not call LLM with empty raw item list caused solely by no datasource associations. Do not advance checkpoint on no-association skip.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: scheduler semantics control production research behavior.
  - Skills: [] - No special skill needed.
  - Omitted: [`llm-instructor`] - No LLM schema change required.

  **Parallelization**: Can Parallel: YES | Wave 4 | Blocks: Task 9 | Blocked By: Tasks 2, 4

  **References**:
  - Pattern: `crypto_news_analyzer/intelligence/topic_research.py:209` - `TopicResearchScheduler`.
  - Pattern: `crypto_news_analyzer/intelligence/topic_research.py:253` - `run_scheduled_topic_research()` active topic loop.
  - Pattern: `crypto_news_analyzer/intelligence/topic_research.py:397` - `_fetch_raw_messages_since()` currently calls unscoped fetch.
  - Pattern: `crypto_news_analyzer/intelligence/topic_research.py:717` - checkpoint cursor behavior; avoid advancing on skip.
  - Test: `tests/intelligence/test_topic_research_scheduler.py` - scheduler fake repository and fake LLM patterns.

  **Acceptance Criteria**:
  - [ ] Topic with zero associations is skipped without LLM call.
  - [ ] Topic with associations passes only associated datasource IDs into repository fetch.
  - [ ] Topic checkpoint remains unchanged on no-association skip.
  - [ ] Existing active topics keep researching after migration backfill.

  **QA Scenarios**:
  ```
  Scenario: Empty association skips research
    Tool: Bash
    Steps: Run scheduler test with active topic and no associated datasource IDs.
    Expected: LLM fake call count is 0; checkpoint unchanged; skip log/status asserted.
    Evidence: .omo/evidence/task-5-empty-skip.txt

  Scenario: Scoped association researches only bound source
    Tool: Bash
    Steps: Seed fake repository with topic linked to datasource X and raw rows from X/Y.
    Expected: LLM receives only datasource X raw rows.
    Evidence: .omo/evidence/task-5-scoped-research.txt
  ```

  **Commit**: NO | Message: `feat(intelligence): scope topic research by datasource` | Files: [crypto_news_analyzer/intelligence/topic_research.py]

- [x] 6. Add HTTP API for topic datasource associations

  **What to do**: Update `crypto_news_analyzer/api_server.py` request/response models and routes. Add required endpoints: `GET /intelligence/topics/{topic_id}/datasources` returns safe datasource summaries; `PUT /intelligence/topics/{topic_id}/datasources` with `{"datasource_ids": [...]}` replaces associations atomically; `POST /intelligence/topics/{topic_id}/datasources/{datasource_id}` adds one association idempotently; `DELETE /intelligence/topics/{topic_id}/datasources/{datasource_id}` removes one association idempotently. Allow `POST /intelligence/topics` optional `datasource_ids`; omitted and `[]` both mean empty for new topics. Ensure the underlying topic creation service/manager creates no associations unless explicit datasource IDs are supplied by the caller, so non-HTTP create paths inherit the same empty-by-default behavior. Include datasource_ids/summaries in topic detail/list only if existing response sizes remain manageable; otherwise keep dedicated endpoint authoritative. Add FastAPI tests in this same task.
  **Must NOT do**: Do not expose raw datasource config. Do not alter `/datasources` News behavior except shared safe summary reuse. Do not accept non-intelligence datasource IDs.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: authenticated API contract and validation semantics must be precise.
  - Skills: [] - No special skill needed.
  - Omitted: [`steel-browser`] - API testing does not require browser automation.

  **Parallelization**: Can Parallel: YES | Wave 4 | Blocks: Task 10 | Blocked By: Tasks 2, 4

  **References**:
  - Pattern: `crypto_news_analyzer/api_server.py:1378` - `register_intelligence_routes()`.
  - Pattern: `tests/intelligence/test_topic_findings_api.py` - intelligence API `TestClient` patterns.
  - Pattern: `tests/intelligence/test_intelligence_security_guardrails.py` - auth/secret leakage tests.
  - Pattern: `tests/news/test_api_server.py` - datasource API endpoint tests.

  **Acceptance Criteria**:
  - [ ] Unauthenticated requests follow existing Bearer auth behavior.
  - [ ] Unknown topic returns `404`.
  - [ ] Unknown datasource returns `404` and no partial update.
  - [ ] News datasource returns `400` or existing validation-error status and no partial update.
  - [ ] `PUT []` succeeds and returns empty association list.
  - [ ] `POST /intelligence/topics` with omitted `datasource_ids` creates a topic with zero associations.
  - [ ] Responses include safe summaries with no `config_payload`.

  **QA Scenarios**:
  ```
  Scenario: Replace associations over HTTP
    Tool: Bash
    Steps: Run FastAPI TestClient test for authenticated PUT then GET.
    Expected: GET returns exactly the replacement datasource IDs and safe summaries.
    Evidence: .omo/evidence/task-6-http-replace.txt

  Scenario: Reject news datasource over HTTP
    Tool: Bash
    Steps: Run FastAPI TestClient test PUT with one intelligence ID and one news ID.
    Expected: Error response; previous associations unchanged; response contains no secrets.
    Evidence: .omo/evidence/task-6-http-news-reject.txt
  ```

  **Commit**: NO | Message: `feat(api): manage topic datasource associations` | Files: [crypto_news_analyzer/api_server.py]

- [x] 7. Add Telegram commands for topic datasource associations

  **What to do**: Update `crypto_news_analyzer/reporters/telegram/intelligence_commands.py` and command registration/help surfaces. Add commands using datasource IDs only: `/topic_sources <topic_id>` to view associations; `/topic_sources_set <topic_id> <ds_id...|none>` to replace; `/topic_sources_add <topic_id> <ds_id...>` to add idempotently; `/topic_sources_remove <topic_id> <ds_id...>` to remove idempotently. Replies must show datasource ID, source_type, name, tags, and a warning when association list is empty. Enforce existing auth and rate-limit patterns. Ensure `/topic_create` continues to create topics with zero datasource associations unless a future explicit datasource argument is implemented; do not implicitly bind all datasources. Add Telegram command tests in this same task.
  **Must NOT do**: Do not accept datasource names as identifiers in write commands. Do not print raw config payload or secrets. Do not make `/topic_create` implicitly bind all datasources.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: command UX and auth behavior must match existing Telegram patterns.
  - Skills: [] - No special skill needed.
  - Omitted: [`steel-browser`] - Telegram command tests use stubs, not browser.

  **Parallelization**: Can Parallel: YES | Wave 4 | Blocks: Task 10, Task 11 | Blocked By: Tasks 2, 4

  **References**:
  - Pattern: `crypto_news_analyzer/reporters/telegram/intelligence_commands.py:20` - `IntelligenceCommandsMixin`.
  - Pattern: `crypto_news_analyzer/reporters/telegram/intelligence_commands.py:669` - `_handle_topic_list_command` style.
  - Pattern: `tests/intelligence/test_topic_findings_telegram.py` - `/topic_*` command test style.
  - Pattern: `tests/shared/test_telegram_command_handler_datasource.py` - datasource command validation/auth stub style.

  **Acceptance Criteria**:
  - [ ] Authorized users can view, set, add, and remove associations.
  - [ ] Unauthorized users are rejected using existing auth behavior.
  - [ ] `/topic_sources_set <topic_id> none` clears associations.
  - [ ] Add existing association and remove missing association are idempotent no-ops with clear replies.
  - [ ] Replies include copyable datasource IDs and no secrets.
  - [ ] `/topic_create <theme>` creates a topic with zero datasource associations.

  **QA Scenarios**:
  ```
  Scenario: Telegram set and view associations
    Tool: Bash
    Steps: Run Telegram command stub test for `/topic_sources_set topic1 ds1 ds2` then `/topic_sources topic1`.
    Expected: Reply lists ds1 and ds2 with names/types/tags; no config payload.
    Evidence: .omo/evidence/task-7-telegram-set-view.txt

  Scenario: Telegram clear associations
    Tool: Bash
    Steps: Run stub test for `/topic_sources_set topic1 none`.
    Expected: Reply warns topic has no datasources and scheduled research will skip it.
    Evidence: .omo/evidence/task-7-telegram-clear.txt
  ```

  **Commit**: NO | Message: `feat(telegram): add topic datasource commands` | Files: [crypto_news_analyzer/reporters/telegram/intelligence_commands.py]

- [x] 8. Block deletion of datasources associated with topics

  **What to do**: Update datasource deletion logic in repository/API/Telegram paths so datasource associations count as in-use. If a datasource is associated with any topic, deletion returns the existing in-use conflict behavior (`409` for HTTP; clear Telegram error). Keep DB-level `ON DELETE RESTRICT`/`NO ACTION` as a safety net, but application behavior should require explicit unbind before delete. Add repository/API/Telegram delete-guard tests in this same task.
  **Must NOT do**: Do not cascade-delete topic associations silently from the user-facing delete command. Do not delete raw historical items.

  **Recommended Agent Profile**:
  - Category: `quick` - Reason: targeted in-use guard once repository association count exists.
  - Skills: [] - No special skill needed.
  - Omitted: [`use-railway`] - No infrastructure operation.

  **Parallelization**: Can Parallel: YES | Wave 4 | Blocks: Task 10 | Blocked By: Tasks 1, 4

  **References**:
  - Pattern: `tests/shared/test_datasource_repository.py` - delete/in-use checks.
  - Pattern: `tests/shared/test_telegram_command_handler_datasource.py` - `/datasource_delete` behavior.
  - Pattern: `tests/news/test_api_server.py` - `DELETE /datasources/{id}` behavior.

  **Acceptance Criteria**:
  - [ ] Repository delete rejects datasource linked to any topic.
  - [ ] HTTP delete returns `409` for topic-associated datasource.
  - [ ] Telegram `/datasource_delete` reports the datasource is associated with topics and must be unbound first.
  - [ ] Deleting unassociated datasource behavior remains unchanged.

  **QA Scenarios**:
  ```
  Scenario: HTTP delete associated datasource
    Tool: Bash
    Steps: Run datasource API test deleting datasource linked to a topic.
    Expected: HTTP 409 and association remains intact.
    Evidence: .omo/evidence/task-8-http-delete-associated.txt

  Scenario: Telegram delete associated datasource
    Tool: Bash
    Steps: Run Telegram datasource delete stub for associated datasource.
    Expected: Reply explains it is in use by topics and must be unbound first.
    Evidence: .omo/evidence/task-8-telegram-delete-associated.txt
  ```

  **Commit**: NO | Message: `fix(datasource): block deleting topic-linked sources` | Files: [crypto_news_analyzer/storage/repositories.py, crypto_news_analyzer/api_server.py, crypto_news_analyzer/reporters/telegram_command_handler.py]

- [x] 9. Consolidate repository and scheduler regression coverage

  **What to do**: After Tasks 1-5 add their implementation-specific tests, run and harden the combined repository/scheduler regression coverage under `tests/intelligence/` and `tests/shared/`. Fill only cross-layer gaps that were not naturally covered inside Tasks 1-5: association CRUD, raw scoped query, schema smoke, and scheduler skip/filter behavior. Use SQLite `:memory:` repository patterns and fake scheduler dependencies. Tests should prove raw SQL filters before limit by seeding noisy unbound rows before bound rows.
  **Must NOT do**: Do not require real PostgreSQL for default test run. Do not use network or live Telegram/LLM services.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: tests must capture data isolation semantics precisely.
  - Skills: [] - No special skill needed.
  - Omitted: [`use-railway`] - No live deployment.

  **Parallelization**: Can Parallel: YES | Wave 5 | Blocks: Final Verification | Blocked By: Tasks 1, 2, 4, 5

  **References**:
  - Test: `tests/intelligence/test_topic_research_scheduler.py` - fake repository/LLM scheduler pattern.
  - Test: `tests/shared/test_datasource_repository.py` - SQLite datasource repository test pattern.
  - Test: `tests/intelligence/test_raw_intelligence_storage.py` - raw item save idempotency pattern.
  - Test: `tests/intelligence/test_intelligence_schema_cleanup.py` - schema assertion pattern.

  **Acceptance Criteria**:
  - [ ] Tests cover get/set/add/remove associations.
  - [ ] Tests cover unknown topic, unknown datasource, news datasource, duplicate IDs, and atomic failure.
  - [ ] Tests cover SQL before LIMIT scoping.
  - [ ] Tests cover empty association scheduler skip without LLM/checkpoint.
  - [ ] Tests cover associated datasource scheduler filtering.

  **QA Scenarios**:
  ```
  Scenario: Repository test suite
    Tool: Bash
    Steps: Run `uv run pytest tests/intelligence/test_topic_datasource_associations.py tests/shared/test_datasource_repository.py -v`.
    Expected: All repository/schema association tests pass.
    Evidence: .omo/evidence/task-9-repository-tests.txt

  Scenario: Scheduler test suite
    Tool: Bash
    Steps: Run `uv run pytest tests/intelligence/test_topic_research_scheduler.py -v`.
    Expected: Empty association and scoped association scheduler tests pass.
    Evidence: .omo/evidence/task-9-scheduler-tests.txt
  ```

  **Commit**: NO | Message: `test(intelligence): cover topic datasource scoping` | Files: [tests/intelligence/test_topic_datasource_associations.py, tests/intelligence/test_topic_research_scheduler.py, tests/shared/test_datasource_repository.py]

- [x] 10. Consolidate API and Telegram regression coverage

  **What to do**: After Tasks 6-8 add their implementation-specific tests, run and harden combined FastAPI and Telegram command regression coverage. Fill only cross-layer gaps that were not naturally covered inside Tasks 6-8. API tests cover authenticated GET/PUT/POST/DELETE, safe summaries, empty list, unknown topic/datasource, news datasource rejection, and no partial update. Telegram tests cover view/set/add/remove/clear, unauthorized rejection, usage errors, idempotent add/remove, and no secret leakage.
  **Must NOT do**: Do not require a real Telegram bot or running server. Do not snapshot secrets.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: route and command contracts are user-facing.
  - Skills: [] - No special skill needed.
  - Omitted: [`steel-browser`] - No browser UI.

  **Parallelization**: Can Parallel: YES | Wave 5 | Blocks: Final Verification | Blocked By: Tasks 6, 7, 8

  **References**:
  - Test: `tests/intelligence/test_topic_findings_api.py` - intelligence API TestClient pattern.
  - Test: `tests/intelligence/test_intelligence_security_guardrails.py` - secret leakage/auth pattern.
  - Test: `tests/intelligence/test_topic_findings_telegram.py` - topic command stubs.
  - Test: `tests/shared/test_telegram_command_handler_datasource.py` - datasource Telegram command patterns.

  **Acceptance Criteria**:
  - [ ] API tests verify auth and status codes.
  - [ ] API tests verify safe response shape and no config payload.
  - [ ] Telegram tests verify all new commands and usage errors.
  - [ ] Existing topic lifecycle API/Telegram tests continue passing.

  **QA Scenarios**:
  ```
  Scenario: API association contract
    Tool: Bash
    Steps: Run `uv run pytest tests/intelligence/test_topic_datasource_api.py -v`.
    Expected: GET/PUT/POST/DELETE association API tests pass with safe summaries.
    Evidence: .omo/evidence/task-10-api-tests.txt

  Scenario: Telegram association commands
    Tool: Bash
    Steps: Run `uv run pytest tests/intelligence/test_topic_datasource_telegram.py -v`.
    Expected: view/set/add/remove/clear/unauthorized tests pass.
    Evidence: .omo/evidence/task-10-telegram-tests.txt
  ```

  **Commit**: NO | Message: `test(intelligence): cover datasource association interfaces` | Files: [tests/intelligence/test_topic_datasource_api.py, tests/intelligence/test_topic_datasource_telegram.py]

- [x] 11. Update user-facing command/API help text and internal guidance

  **What to do**: Update relevant help output and docs strings so users can discover the new association workflow. Include the exact Telegram commands and HTTP endpoints. Clarify that new topics default to no datasource associations, empty topics skip scheduled research, and association changes do not backfill historical messages. If README/API docs are updated, keep runtime guidance aligned with AGENTS.md dual-domain boundaries.
  **Must NOT do**: Do not recommend legacy `api-server` runtime. Do not document News datasource associations because they are out of scope.

  **Recommended Agent Profile**:
  - Category: `writing` - Reason: user-facing command guidance and docs clarity.
  - Skills: [] - No special skill needed.
  - Omitted: [`use-railway`] - No deployment docs needed.

  **Parallelization**: Can Parallel: YES | Wave 5 | Blocks: Final Verification | Blocked By: Task 7

  **References**:
  - Pattern: `README.md` - existing Telegram and Intelligence API command documentation.
  - Pattern: `crypto_news_analyzer/reporters/telegram/intelligence_commands.py` - help/usage responses near command handlers.
  - Pattern: `AGENTS.md` - dual-domain boundaries and runtime mode constraints.

  **Acceptance Criteria**:
  - [ ] Help text lists `/topic_sources`, `/topic_sources_set`, `/topic_sources_add`, `/topic_sources_remove`.
  - [ ] API docs/help list GET/PUT/POST/DELETE association endpoints.
  - [ ] Docs state new topics default empty and empty topics skip research.
  - [ ] Docs state association changes do not auto-backfill historical raw items.

  **QA Scenarios**:
  ```
  Scenario: Telegram help includes new commands
    Tool: Bash
    Steps: Run command/help test or inspect generated help response via existing Telegram stub.
    Expected: New topic datasource commands appear with ID-based usage examples.
    Evidence: .omo/evidence/task-11-help-text.txt

  Scenario: Documentation scope check
    Tool: Bash
    Steps: Run text check or review evidence confirming docs mention Intelligence-only scope and omit legacy api-server recommendations.
    Expected: Docs are accurate and do not blur News/Intelligence boundaries.
    Evidence: .omo/evidence/task-11-doc-scope.txt
  ```

  **Commit**: NO | Message: `docs(intelligence): document topic datasource controls` | Files: [README.md, crypto_news_analyzer/reporters/telegram/intelligence_commands.py]

## Final Verification Wave (MANDATORY — after ALL implementation tasks)
> 4 review agents run in PARALLEL. ALL must APPROVE. Present consolidated results to user and get explicit "okay" before completing.
> **Do NOT auto-proceed after verification. Wait for user's explicit approval before marking work complete.**
> **Never mark F1-F4 as checked before getting user's okay.** Rejection or user feedback -> fix -> re-run -> present again -> wait for okay.
- [x] F1. Plan Compliance Audit — oracle
- [x] F2. Code Quality Review — unspecified-high
- [x] F3. Real Manual QA — unspecified-high
- [x] F4. Scope Fidelity Check — deep

## Commit Strategy
- User did not request commits. Do not commit by default.
- If user later requests commits, use one atomic commit after all tests and final verification pass.
- Suggested message: `feat(intelligence): scope topics to datasources`.
- Stage only intended files; never commit secrets or `.omo/evidence/*` unless user explicitly asks.

## Success Criteria
- Existing topics continue current behavior after migration because they are linked to all existing intelligence datasources.
- New topics without datasource IDs have zero links and are skipped by scheduler without LLM call/checkpoint advancement.
- Topic A linked to datasource X and topic B linked to datasource Y each receive only their bound raw intelligence items.
- API and Telegram allow operators to view, replace, add, remove, and clear associations.
- News datasource and News analysis behavior is unchanged.
- All automated tests and final verification agents pass.
