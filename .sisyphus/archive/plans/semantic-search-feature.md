# Semantic Search for Crypto News

## TL;DR
> **Summary**: Add a Postgres-only semantic search capability that exposes new HTTP async endpoints and a Telegram command, decomposes a user topic with LLM, retrieves time-bounded news via pgvector, and returns a compact cited report.
> **Deliverables**:
> - New HTTP async contract: `POST /semantic-search`, `GET /semantic-search/{job_id}`, `GET /semantic-search/{job_id}/result`
> - New Telegram command: `/semantic_search <hours> <topic>`
> - Dedicated semantic-search job persistence, vector retrieval layer, prompt(s), report builder, and tests
> - Ongoing embedding generation for newly ingested content plus one-off historical backfill command
> **Effort**: Large
> **Parallel**: YES - 2 waves
> **Critical Path**: T1 → T2 → T3/T4 → T5 → T6/T7 → T8 → T9

## Context
### Original Request
- Add a semantic search feature.
- Expose it through both Telegram and HTTP API.
- Request inputs are time window + freeform topic sentence.
- analysis-service should use LLM to understand intent, split into executable semantic-search queries, search PostgreSQL within the time window, cap the number of matched news items, then merge results with LLM using a prepared prompt template and return a compact report with data sources.

### Interview Summary
- HTTP must reuse the existing async job/result interaction pattern.
- HTTP keeps `user_id` for audit; business inputs remain `hours` + `query`.
- Search scope covers `title + content` (there is no stored summary field).
- Result format is compact summary + cited sources, not a raw dump of article bodies.
- All matched items should influence the output; upper bound is ~200 unique retained items.
- Reuse the system’s existing batch-processing style where possible.
- Historical embedding fill must run as a separate maintenance task.
- Test strategy is `tests-after`.

### Metis Review (gaps addressed)
- Do **not** reuse `analysis_jobs` unchanged; semantic search needs query-aware persistence.
- Do **not** force semantic search through the existing category-analysis/report pipeline.
- Freeze public contract and backend boundary: Postgres-only feature, explicit SQLite rejection.
- Add idempotent backfill semantics, queue-isolation rules, dedupe/cap rules, invalid-input handling, and no-match behavior.
- Keep docs aligned with code for the new async search contract to avoid `/analyze`-style drift.

## Work Objectives
### Core Objective
Implement a new semantic-search path that works on top of PostgreSQL/pgvector and returns query-centric, source-cited answers without interfering with the existing `/analyze` flow.

### Deliverables
- Dedicated semantic search config and contracts
- Dedicated semantic search job table/model/repository methods
- pgvector similarity query path with time-window filtering and deterministic cap handling
- Embedding generation service using OpenAI `text-embedding-3-small` (1536 dims)
- Incremental embedding writes for newly ingested content
- One-off historical backfill mode: `uv run python -m crypto_news_analyzer.main --mode embedding-backfill --config ./config.jsonc --batch-size 100`
- Semantic search prompt(s) and compact report formatting
- HTTP async endpoints and Telegram command
- Automated coverage for repository, backfill, service, HTTP, Telegram, and unsupported-backend paths

### Definition of Done (verifiable conditions with commands)
- `uv run pytest tests/test_semantic_search_storage.py -v`
- `uv run pytest tests/test_semantic_search_service.py -v`
- `uv run pytest tests/test_api_server_semantic_search.py -v`
- `uv run pytest tests/test_telegram_command_handler_semantic_search.py -v`
- `uv run pytest tests/test_embedding_backfill_mode.py -v`
- `uv run pytest tests/ -k "semantic_search or embedding_backfill" -v`

### Must Have
- Separate semantic-search path from the existing category-analysis pipeline
- Separate semantic-search job persistence contract with stored `query`
- Postgres-only execution guard with explicit 4xx/5xx rejection path for unsupported backend
- Deterministic retrieval limits: max 4 subqueries, max 50 candidates per subquery before merge, max 200 unique retained items after global dedupe
- Query decomposition fallback to original user query if LLM planning fails
- Compact final report with source names and URLs
- Idempotent backfill over rows where embeddings are missing
- Separate HTTP executor for semantic-search jobs so `/analyze` and `/semantic-search` do not contend on one single-worker pool

### Must NOT Have (guardrails, AI slop patterns, scope boundaries)
- Must NOT turn this into chatbot/RAG conversation memory
- Must NOT add dashboard/UI work
- Must NOT reuse `analysis_prompt.md` category filtering for semantic search answers
- Must NOT depend on SQLite semantic-search support; reject it explicitly
- Must NOT lazily backfill embeddings on user search requests
- Must NOT silently change embedding model/dimension after rollout
- Must NOT include keyword/hybrid fallback in Phase 1
- Must NOT let semantic-search jobs pollute `/analyze` manual dedupe cache

## Verification Strategy
> ZERO HUMAN INTERVENTION - all verification is agent-executed.
- Test decision: tests-after + pytest
- QA policy: Every task includes automated or command-driven QA scenarios
- Evidence: `.sisyphus/evidence/task-{N}-{slug}.{ext}`

## Execution Strategy
### Parallel Execution Waves
> Target: 5-8 tasks per wave. <3 per wave (except final) = under-splitting.
> Extract shared dependencies as Wave-1 tasks for max parallelism.

Wave 1: T1 contracts/config, T2 schema/jobs, T3 vector repository layer, T4 embedding service + incremental writes, T5 backfill runtime

Wave 2: T6 semantic-search orchestration + prompts/report, T7 HTTP async API, T8 Telegram command flow, T9 tests/docs/regression

### Dependency Matrix (full, all tasks)
| Task | Depends On | Blocks |
|---|---|---|
| T1 | - | T2, T4, T5, T6, T7, T8, T9 |
| T2 | T1 | T3, T7, T9 |
| T3 | T1, T2 | T4, T5, T6, T7, T9 |
| T4 | T1, T3 | T5, T6, T9 |
| T5 | T1, T3, T4 | T9 |
| T6 | T1, T3, T4 | T7, T8, T9 |
| T7 | T1, T2, T3, T6 | T9 |
| T8 | T1, T6 | T9 |
| T9 | T1-T8 | Final Verification |

### Agent Dispatch Summary (wave → task count → categories)
- Wave 1 → 5 tasks → deep, unspecified-high, quick
- Wave 2 → 4 tasks → deep, unspecified-high, writing

## TODOs
> Implementation + Test = ONE task. Never separate.
> EVERY task MUST have: Agent Profile + Parallelization + QA Scenarios.

- [x] 1. Freeze semantic-search contracts, config, and runtime guardrails

  **What to do**: Define a dedicated semantic-search contract instead of piggybacking on `/analyze`. Add a new `semantic_search` config section with concrete defaults: `query_max_chars=300`, `max_subqueries=4`, `per_subquery_limit=50`, `max_retained_items=200`, `synthesis_batch_size` defaulting to existing `llm_config.batch_size`, `embedding_model=text-embedding-3-small`, `embedding_dimensions=1536`, and `enabled=true`. Define new job/domain/API models for semantic-search requests/results that explicitly store `query`, `normalized_intent`, `matched_count`, and `retained_count`; freeze the job ID prefix to `semantic_search_job_`. Freeze the public names to `POST /semantic-search`, `GET /semantic-search/{job_id}`, `GET /semantic-search/{job_id}/result`, and Telegram `/semantic_search <hours> <topic>`.
  **Must NOT do**: Must NOT reuse `AnalysisRequest` as-is; must NOT leave route/command names undecided; must NOT pretend there is a persisted summary field in `ContentItem`; must NOT enable the feature for SQLite.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: cross-cutting contract decisions across API, storage, runtime, and Telegram surfaces
  - Skills: `[]` - no special skill required
  - Omitted: `['playwright']` - no browser work involved

  **Parallelization**: Can Parallel: NO | Wave 1 | Blocks: 2, 4, 5, 6, 7, 8, 9 | Blocked By: none

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `crypto_news_analyzer/api_server.py:80-128` - existing async request/status/result response model shape to mirror, but semantic-search needs query-aware variants
  - Pattern: `crypto_news_analyzer/api_server.py:252-260` - Bearer auth validation to reuse unchanged
  - Pattern: `crypto_news_analyzer/domain/models.py:154-193` - existing analysis job contract that is missing `query`; use as a contrast, not a reuse target
  - Pattern: `crypto_news_analyzer/main.py:12-28` - current runtime mode normalization pattern to extend carefully
  - API/Type: `crypto_news_analyzer/models.py:17-27` - persisted content fields are only `title`, `content`, `url`, `publish_time`, `source_name`, `source_type`

  **Acceptance Criteria** (agent-executable only):
  - [ ] A dedicated semantic-search config model and request/result/job contract exists with the exact names and limits defined above.
  - [ ] Invalid blank/whitespace-only query input and invalid `user_id` are rejected by validation, not by ad-hoc downstream string checks.
  - [ ] SQLite runtime is explicitly marked unsupported for semantic-search surfaces and backfill mode.
  - [ ] `uv run pytest tests/test_semantic_search_contracts.py -v` passes.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Contract defaults are stable
    Tool: Bash
    Steps: uv run pytest tests/test_semantic_search_contracts.py::test_semantic_search_config_defaults -v
    Expected: test passes and asserts 300-char query cap, 4 subqueries, 50 per-subquery candidates, 200 retained cap, and frozen route/command names
    Evidence: .sisyphus/evidence/task-1-contracts.txt

  Scenario: Invalid query is rejected early
    Tool: Bash
    Steps: uv run pytest tests/test_semantic_search_contracts.py::test_semantic_search_query_validation_rejects_blank_and_whitespace -v
    Expected: test passes and invalid query payloads are rejected without calling orchestration code
    Evidence: .sisyphus/evidence/task-1-contracts-error.txt
  ```

  **Commit**: NO | Message: `feat(semantic-search): freeze contracts and config` | Files: `crypto_news_analyzer/api_server.py`, `crypto_news_analyzer/domain/models.py`, `crypto_news_analyzer/config/manager.py`, `crypto_news_analyzer/models.py`, `tests/test_semantic_search_contracts.py`

- [x] 2. Add Postgres schema changes and dedicated semantic-search job persistence

  **What to do**: Extend PostgreSQL schema and runtime init with semantic-search-specific structures. Add `semantic_search_jobs` table instead of reusing `analysis_jobs`; required columns: `id`, `recipient_key`, `query`, `normalized_intent`, `time_window_hours`, `status`, `matched_count`, `retained_count`, `decomposition_json`, `result`, `error_message`, `created_at`, `started_at`, `completed_at`, `source`. Extend `content_items` with `embedding_model TEXT` and `embedding_updated_at TIMESTAMPTZ`, while keeping `embedding vector(1536)`. Keep phase-1 retrieval exact (no ANN index dependency); rely on existing `publish_time` btree filter plus vector operator over the bounded time window.
  **Must NOT do**: Must NOT overwrite or repurpose `analysis_jobs`; must NOT add HNSW/IVFFlat as a hidden dependency in phase 1; must NOT break existing migrations/runtime init parity.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: schema evolution plus runtime-init parity work
  - Skills: `[]` - no special skill required
  - Omitted: `['git-master']` - no git work here

  **Parallelization**: Can Parallel: NO | Wave 1 | Blocks: 3, 7, 9 | Blocked By: 1

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `migrations/postgresql/001_init.sql:1-19` - current pgvector extension and `content_items.embedding vector(1536)` schema
  - Pattern: `crypto_news_analyzer/storage/data_manager.py:80-166` - runtime schema bootstrap must stay aligned with migration files
  - Pattern: `migrations/postgresql/001_init.sql:63-81` - current `analysis_jobs` table/index style to mirror for a dedicated semantic-search job table
  - API/Type: `crypto_news_analyzer/domain/models.py:154-193` - existing query-less job model justifies separate persistence
  - Test: `tests/test_postgres_storage_path.py:57-86` - current vector bootstrap assertions to extend for the new schema

  **Acceptance Criteria** (agent-executable only):
  - [ ] PostgreSQL migration and runtime bootstrap create the same semantic-search table/columns.
  - [ ] `content_items` schema stores `embedding_model` and `embedding_updated_at` alongside `embedding`.
  - [ ] Existing analysis-job behavior remains unchanged.
  - [ ] `uv run pytest tests/test_semantic_search_storage.py -k "schema or job" -v` passes.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Runtime bootstrap matches migration
    Tool: Bash
    Steps: uv run pytest tests/test_semantic_search_storage.py::test_postgres_semantic_search_schema_bootstrap_matches_migration -v
    Expected: test passes and asserts semantic_search_jobs plus embedding metadata columns exist in both migration and runtime SQL
    Evidence: .sisyphus/evidence/task-2-schema.txt

  Scenario: Existing analysis tables are not repurposed
    Tool: Bash
    Steps: uv run pytest tests/test_semantic_search_storage.py::test_semantic_search_uses_dedicated_job_table_not_analysis_jobs -v
    Expected: test passes and confirms semantic search writes to dedicated persistence instead of analysis_jobs
    Evidence: .sisyphus/evidence/task-2-schema-error.txt
  ```

  **Commit**: NO | Message: `feat(semantic-search): add postgres schema and job persistence` | Files: `migrations/postgresql/001_init.sql`, `crypto_news_analyzer/storage/data_manager.py`, `crypto_news_analyzer/domain/models.py`, `tests/test_semantic_search_storage.py`

- [x] 3. Implement vector repository APIs and bounded retrieval semantics

  **What to do**: Extend repository interfaces and storage adapters with semantic-search-specific methods. Add a dedicated semantic-search repository interface or extend content repository with explicit methods for: fetching rows missing embeddings, persisting embeddings by content ID, creating/updating semantic-search jobs, and executing time-bounded cosine-distance retrieval. Retrieval must: filter by `publish_time` within the requested window, search over `title + "\n\n" + content`, return similarity score + source metadata, cap each subquery at 50 rows, and leave global dedupe/rerank to the orchestration layer.
  **Must NOT do**: Must NOT overload `get_content_items_since()` with semantic-search-only behavior; must NOT mix search-job operations into analysis repository methods; must NOT silently run semantic search under SQLite.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: repository boundaries and data contracts must be explicit
  - Skills: `[]` - no special skill required
  - Omitted: `['review-work']` - final verification wave handles review separately

  **Parallelization**: Can Parallel: NO | Wave 1 | Blocks: 4, 5, 6, 7, 9 | Blocked By: 1, 2

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `crypto_news_analyzer/domain/repositories.py:17-128` - existing job repository abstraction style
  - Pattern: `crypto_news_analyzer/domain/repositories.py:226-240` - content repository boundary location to extend carefully
  - Pattern: `crypto_news_analyzer/storage/repositories.py:33-127` - adapter style for job persistence
  - Pattern: `crypto_news_analyzer/storage/repositories.py:218-258` - current content repository adapter style over `DataManager`
  - Pattern: `crypto_news_analyzer/storage/data_manager.py:913-983` - current time-window content query to mirror for bounded retrieval semantics
  - Pattern: `crypto_news_analyzer/execution_coordinator.py:1893-1940` - existing analysis flow already starts with time-windowed content fetch

  **Acceptance Criteria** (agent-executable only):
  - [ ] Repository layer exposes explicit semantic-search read/write methods instead of implicit ad-hoc SQL in controllers.
  - [ ] Search queries return rows with score, source name, URL, and publish time, ordered by best similarity then recency within one subquery.
  - [ ] SQLite-backed calls fail with the defined unsupported-backend error path.
  - [ ] `uv run pytest tests/test_semantic_search_storage.py -k "retrieval or unsupported_backend" -v` passes.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Time-bounded vector retrieval is capped correctly
    Tool: Bash
    Steps: uv run pytest tests/test_semantic_search_storage.py::test_semantic_search_retrieval_applies_time_window_and_per_subquery_cap -v
    Expected: test passes and retrieval honors the requested hours window and the fixed per-subquery limit of 50
    Evidence: .sisyphus/evidence/task-3-retrieval.txt

  Scenario: Unsupported backend fails explicitly
    Tool: Bash
    Steps: uv run pytest tests/test_semantic_search_storage.py::test_semantic_search_repository_rejects_sqlite_backend -v
    Expected: test passes and SQLite raises the explicit unsupported-backend path rather than a generic SQL/runtime exception
    Evidence: .sisyphus/evidence/task-3-retrieval-error.txt
  ```

  **Commit**: NO | Message: `feat(semantic-search): add vector repository layer` | Files: `crypto_news_analyzer/domain/repositories.py`, `crypto_news_analyzer/storage/repositories.py`, `crypto_news_analyzer/storage/data_manager.py`, `tests/test_semantic_search_storage.py`

- [x] 4. Add embedding service and incremental embedding writes for newly ingested content

  **What to do**: Introduce a dedicated embedding service independent from `LLMAnalyzer`, initialized in both analysis-service and ingestion runtimes when semantic search is enabled. Use OpenAI `text-embedding-3-small` with `OPENAI_API_KEY`; encode article text as `title + "\n\n" + content`; validate the returned vector length is exactly 1536 before persistence. Update the ingestion/new-content save path so newly inserted Postgres rows receive embeddings plus `embedding_model` and `embedding_updated_at`. If embedding generation fails, keep the content row, leave `embedding` null, log a warning, and continue ingestion.
  **Must NOT do**: Must NOT route embeddings through the existing category-analysis prompt stack; must NOT fail the whole ingestion batch because one embedding request fails; must NOT generate embeddings for duplicate rows that were not inserted.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: runtime ownership spans ingestion and analysis-service initialization paths
  - Skills: `[]` - no special skill required
  - Omitted: `['llm-instructor']` - embedding calls do not use instructor structured-output flows

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: 5, 6, 9 | Blocked By: 1, 3

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `crypto_news_analyzer/storage/data_manager.py:351-422` - new-content insertion path; embedding write should hook only after confirmed inserts
  - Pattern: `crypto_news_analyzer/execution_coordinator.py:315-357` - analysis-service initialization pattern where new shared services can be wired
  - Pattern: `crypto_news_analyzer/execution_coordinator.py:413-425` - ingestion runtime currently disables LLM/report components, so embedding service must be separate from `LLMAnalyzer`
  - API/Type: `crypto_news_analyzer/models.py:17-27` - source fields available to compose embedding input text
  - External: `https://platform.openai.com/docs/guides/embeddings` - official basis for `text-embedding-3-small` returning 1536-dim vectors

  **Acceptance Criteria** (agent-executable only):
  - [ ] A dedicated embedding service exists and is initialized without relying on `LLMAnalyzer`.
  - [ ] New Postgres content rows receive embeddings on successful insert when `OPENAI_API_KEY` is configured.
  - [ ] Embedding failures degrade to `NULL` embeddings plus warnings rather than aborting the entire ingestion batch.
  - [ ] `uv run pytest tests/test_semantic_search_storage.py -k "incremental_embedding" -v` passes.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Newly inserted content gets embeddings automatically
    Tool: Bash
    Steps: uv run pytest tests/test_semantic_search_storage.py::test_new_postgres_content_is_embedded_after_insert -v
    Expected: test passes and a newly inserted row gets a 1536-dim vector plus embedding metadata without manual backfill
    Evidence: .sisyphus/evidence/task-4-incremental-embedding.txt

  Scenario: Embedding API failure does not abort ingestion
    Tool: Bash
    Steps: uv run pytest tests/test_semantic_search_storage.py::test_embedding_failure_keeps_content_row_and_logs_warning -v
    Expected: test passes and the content row persists with NULL embedding while the batch continues
    Evidence: .sisyphus/evidence/task-4-incremental-embedding-error.txt
  ```

  **Commit**: NO | Message: `feat(semantic-search): add embedding service and incremental writes` | Files: `crypto_news_analyzer/execution_coordinator.py`, `crypto_news_analyzer/storage/data_manager.py`, `crypto_news_analyzer/storage/repositories.py`, `crypto_news_analyzer/semantic_search/embedding_service.py`, `tests/test_semantic_search_storage.py`

- [x] 5. Add the one-off historical embedding backfill runtime mode

  **What to do**: Extend `main.py` with a new one-off runtime mode: `embedding-backfill`. Add CLI args `--batch-size` (default 100) and optional `--limit`. Implement a runner that only works on Postgres, selects rows `WHERE embedding IS NULL ORDER BY publish_time DESC`, embeds them in batches, updates metadata atomically per batch, and exits cleanly with resumable/idempotent semantics. Re-running the command must skip already-embedded rows rather than rewriting them.
  **Must NOT do**: Must NOT start HTTP API or Telegram listeners in this mode; must NOT truncate content; must NOT block forever on a single failed row; must NOT perform lazy backfill from user request paths.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: isolated maintenance/runtime work with data-safety constraints
  - Skills: `[]` - no special skill required
  - Omitted: `['crypto-news-debug']` - this is local/runtime design work, not Railway debugging

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: 9 | Blocked By: 1, 3, 4

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `crypto_news_analyzer/main.py:12-28` - supported runtime mode validation to extend
  - Pattern: `crypto_news_analyzer/main.py:31-64` - top-level mode dispatch pattern
  - Pattern: `crypto_news_analyzer/main.py:145-205` - one-off dedicated runtime loop structure to mirror for a non-HTTP execution path
  - Pattern: `crypto_news_analyzer/storage/data_manager.py:351-422` - content write path and locking style
  - Pattern: `migrations/postgresql/README.md` - existing project precedent for explicit operational backfill commands

  **Acceptance Criteria** (agent-executable only):
  - [ ] `normalize_runtime_mode()` recognizes `embedding-backfill` and CLI parsing accepts `--batch-size` and `--limit`.
  - [ ] Running the backfill twice does not re-embed rows that already have embeddings.
  - [ ] SQLite backend fails fast with a clear unsupported-backend message.
  - [ ] `uv run pytest tests/test_embedding_backfill_mode.py -v` passes.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Backfill processes missing embeddings idempotently
    Tool: Bash
    Steps: uv run pytest tests/test_embedding_backfill_mode.py::test_embedding_backfill_only_updates_rows_missing_embeddings -v
    Expected: test passes and rerunning the mode updates zero already-embedded rows
    Evidence: .sisyphus/evidence/task-5-backfill.txt

  Scenario: Unsupported backend is rejected
    Tool: Bash
    Steps: uv run pytest tests/test_embedding_backfill_mode.py::test_embedding_backfill_rejects_sqlite_backend -v
    Expected: test passes and the mode exits with the defined unsupported-backend error path
    Evidence: .sisyphus/evidence/task-5-backfill-error.txt
  ```

  **Commit**: NO | Message: `feat(semantic-search): add embedding backfill mode` | Files: `crypto_news_analyzer/main.py`, `crypto_news_analyzer/semantic_search/backfill_runner.py`, `crypto_news_analyzer/semantic_search/embedding_service.py`, `tests/test_embedding_backfill_mode.py`

- [x] 6. Implement semantic-search orchestration, prompts, and compact cited report generation

  **What to do**: Create a dedicated semantic-search service (for example `crypto_news_analyzer/semantic_search/service.py`) instead of reusing `analyze_by_time_window()`. Flow must be: validate request → plan query with LLM → fallback to original query if planning output is invalid → embed each subquery → run repository retrieval per subquery → global union/dedupe by content ID → rank by best similarity then publish time → retain max 200 → summarize in batches using existing-style chunking → reduce into one compact cited report. Add two new prompt templates: one for structured query planning and one for compact synthesis. The synthesis prompt must contain these fixed sections in order: `Role`, `Task`, `Input`, `Hard Constraints`, `Output Format`, `Fallback`; its constraints must explicitly forbid unsupported claims, require duplicate-event merging, require contradiction disclosure, forbid investment advice, and require every core conclusion to be supported by cited sources. Final markdown output must use this fixed structure: `# 主题检索报告` header, then a metadata block with normalized intent / original query / time window / matched count / retained count, then `## 核心结论`, `## 关键信号`, and `## 来源`; the no-match case must still return the same header + metadata block followed by a single no-match conclusion section.
  **Must NOT do**: Must NOT call `LLMAnalyzer.analyze_content_batch()`; must NOT use `analysis_prompt.md`; must NOT apply historical-title dedupe or category-only filtering; must NOT drop the original user query from the subquery set.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: core feature orchestration with multiple failure modes and LLM steps
  - Skills: `[]` - no special skill required
  - Omitted: `['llm-instructor']` - planner/synthesis prompts can use plain JSON/structured parsing without instructor-specific workflow assumptions unless already idiomatic in code

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: 7, 8, 9 | Blocked By: 1, 3, 4

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `crypto_news_analyzer/execution_coordinator.py:1893-2056` - existing manual analysis entrypoint to avoid reusing directly
  - Pattern: `crypto_news_analyzer/analyzers/llm_analyzer.py:241-275` - existing batch-processing entrypoint to emulate only at a high level
  - Pattern: `crypto_news_analyzer/analyzers/llm_analyzer.py:471-492` - concrete chunked batch loop style worth reusing for synthesis batching
  - Pattern: `crypto_news_analyzer/reporters/report_generator.py:320-349` - citation formatting expectations (`source` / related links) to mirror, without category-section layout
  - Pattern: `prompts/analysis_prompt.md:132-159` - current prompt rigor for structured output; create new semantic-search prompt(s), do not reuse category definitions
  - API/Type: `crypto_news_analyzer/models.py:17-27` - available fields for search corpus and citations

  **Acceptance Criteria** (agent-executable only):
  - [ ] Query planner produces up to 4 unique subqueries and always retains the original user query as one fallback-safe subquery.
  - [ ] Global retained set never exceeds 200 unique items after merge/dedupe.
  - [ ] No-match results return a compact, non-error report shape instead of raw exceptions.
  - [ ] `uv run pytest tests/test_semantic_search_service.py -v` passes.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Valid query is decomposed, deduped, and summarized
    Tool: Bash
    Steps: uv run pytest tests/test_semantic_search_service.py::test_semantic_search_service_plans_retrieves_and_summarizes_corpus -v
    Expected: test passes and asserts capped subqueries, global dedupe, retained-count <= 200, and cited source output
    Evidence: .sisyphus/evidence/task-6-service.txt

  Scenario: Planner failure falls back safely
    Tool: Bash
    Steps: uv run pytest tests/test_semantic_search_service.py::test_semantic_search_service_falls_back_to_original_query_when_planner_output_is_invalid -v
    Expected: test passes and the original user query still drives retrieval when planner output is malformed or empty
    Evidence: .sisyphus/evidence/task-6-service-error.txt
  ```

  **Commit**: NO | Message: `feat(semantic-search): add orchestration and prompts` | Files: `crypto_news_analyzer/semantic_search/service.py`, `crypto_news_analyzer/semantic_search/report_builder.py`, `prompts/semantic_search_query_planner.md`, `prompts/semantic_search_report.md`, `tests/test_semantic_search_service.py`

- [x] 7. Add HTTP async semantic-search API with isolated executor and job lifecycle

  **What to do**: Extend `api_server.py` with a dedicated semantic-search executor (`ThreadPoolExecutor(max_workers=1, thread_name_prefix="api-search")`) so search jobs do not share the existing analyze executor. Add Pydantic request/result/status models for semantic-search, reusing `verify_api_key()` and the `USER_ID_PATTERN` validator. Implement `POST /semantic-search`, `GET /semantic-search/{job_id}`, and `GET /semantic-search/{job_id}/result` with the same accepted/status/result behavior as `/analyze`, but backed by semantic-search jobs and the new service. Request body must be `{ "hours": int, "query": str, "user_id": str }`; accepted responses use the `semantic_search_job_` prefix; blank queries reject with 422; unsupported backend returns `503` with a stable detail string `Semantic search requires postgres backend`.
  **Must NOT do**: Must NOT reuse `enqueue_analyze_job()` or `AnalyzeJobRecord`; must NOT store semantic-search results in `analysis_jobs`; must NOT hide search queue contention behind the existing `api-analyze` executor.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: isolated HTTP contract work using strong existing route patterns
  - Skills: `[]` - no special skill required
  - Omitted: `['playwright']` - API surface is fully testable with pytest/TestClient

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: 9 | Blocked By: 1, 2, 3, 6

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `crypto_news_analyzer/api_server.py:42-50` - app state + current single-worker analyze executor; add a separate executor for search
  - Pattern: `crypto_news_analyzer/api_server.py:80-128` - existing request/result/status model style
  - Pattern: `crypto_news_analyzer/api_server.py:444-462` - analyze-job enqueue shape to mirror with a search-specific implementation
  - Pattern: `crypto_news_analyzer/api_server.py:465-621` - exact FastAPI route registration and response-header pattern to mirror
  - Pattern: `tests/test_api_server.py:598-683` - existing invalid `user_id` rejection and per-user isolation expectations

  **Acceptance Criteria** (agent-executable only):
  - [ ] `POST /semantic-search` returns `202` with `job_id`, `status_url`, `result_url`, and `Retry-After` header.
  - [ ] `GET /semantic-search/{job_id}` returns queued/running/completed/failed status consistently.
  - [ ] `GET /semantic-search/{job_id}/result` returns 200 with success/failure payload once the job is materialized.
  - [ ] `uv run pytest tests/test_api_server_semantic_search.py -v` passes.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Async semantic-search job is accepted and result is pollable
    Tool: Bash
    Steps: uv run pytest tests/test_api_server_semantic_search.py::test_semantic_search_accepts_job_and_exposes_status_and_result_urls -v
    Expected: test passes and the endpoint returns 202 plus stable status/result URLs and Retry-After header
    Evidence: .sisyphus/evidence/task-7-http.txt

  Scenario: Invalid and unsupported requests fail predictably
    Tool: Bash
    Steps: uv run pytest tests/test_api_server_semantic_search.py::test_semantic_search_rejects_blank_query_invalid_user_id_and_sqlite_backend -v
    Expected: test passes and invalid query/user_id/backend cases fail with the defined response codes and messages
    Evidence: .sisyphus/evidence/task-7-http-error.txt
  ```

  **Commit**: NO | Message: `feat(semantic-search): add async HTTP search API` | Files: `crypto_news_analyzer/api_server.py`, `crypto_news_analyzer/semantic_search/service.py`, `tests/test_api_server_semantic_search.py`

- [x] 8. Add Telegram `/semantic_search` command, help text, and notification flow

  **What to do**: Register a new Telegram command `/semantic_search` and implement both the async handler and the synchronous business method/background worker pair, mirroring the `/analyze` command structure. Syntax is fixed to `/semantic_search <hours> <topic>`; `hours` is required here to preserve the explicit two-business-parameter contract. Reuse authorization checks, rate limiting, logging, and `telegram_sender.send_report_to_chat()` delivery. Update help text and bot command registration so the command is discoverable.
  **Must NOT do**: Must NOT overload `/analyze`; must NOT auto-infer hours when the command is missing them; must NOT bypass authorization/rate-limit logic; must NOT use the analysis historical-title cache for semantic-search requests.

  **Recommended Agent Profile**:
  - Category: `quick` - Reason: surface-level command integration following an existing strong pattern
  - Skills: `[]` - no special skill required
  - Omitted: `['playwright']` - behavior is covered by Telegram unit tests, not browser automation

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: 9 | Blocked By: 1, 6

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `crypto_news_analyzer/reporters/telegram_command_handler.py:171-186` - command registration in `_build_application()`
  - Pattern: `crypto_news_analyzer/reporters/telegram_command_handler.py:654-731` - `_handle_analyze_command()` auth/rate-limit/arg-parse pattern
  - Pattern: `crypto_news_analyzer/reporters/telegram_command_handler.py:1434-1677` - `handle_analyze_command()` and background notification flow to mirror with search-specific methods
  - Pattern: `crypto_news_analyzer/reporters/telegram_command_handler.py:1786-1816` - help-text update location
  - Pattern: `tests/test_telegram_command_handler_analyze.py:10-220` - command-level test style and coordinator stub pattern

  **Acceptance Criteria** (agent-executable only):
  - [ ] `/semantic_search <hours> <topic>` is registered in the Telegram application and help output.
  - [ ] Missing/invalid args return a usage error instead of silently guessing intent.
  - [ ] Successful runs send a compact search report or a no-match message to the triggering chat.
  - [ ] `uv run pytest tests/test_telegram_command_handler_semantic_search.py -v` passes.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Authorized user can trigger semantic search with explicit hours and topic
    Tool: Bash
    Steps: uv run pytest tests/test_telegram_command_handler_semantic_search.py::test_semantic_search_command_triggers_background_search_and_returns_initial_ack -v
    Expected: test passes and the command validates auth, starts background execution, and returns the correct initial acknowledgment text
    Evidence: .sisyphus/evidence/task-8-telegram.txt

  Scenario: Invalid command usage is rejected clearly
    Tool: Bash
    Steps: uv run pytest tests/test_telegram_command_handler_semantic_search.py::test_semantic_search_command_rejects_missing_hours_or_topic -v
    Expected: test passes and missing or malformed command args return a clear usage error without invoking the coordinator
    Evidence: .sisyphus/evidence/task-8-telegram-error.txt
  ```

  **Commit**: NO | Message: `feat(semantic-search): add telegram semantic search command` | Files: `crypto_news_analyzer/reporters/telegram_command_handler.py`, `tests/test_telegram_command_handler_semantic_search.py`

- [x] 9. Finish regression coverage and docs alignment for the new semantic-search feature

  **What to do**: Add/finish the remaining regression tests and update operator/API documentation. Coverage must include: no-match result shape, duplicate subquery collapse, retained-count cap at 200, query-planner fallback behavior, unsupported SQLite backend, HTTP result contract, Telegram usage/help text, and backfill idempotency. Update `README.md` and add a dedicated `docs/SEMANTIC_SEARCH_API_GUIDE.md` for the new async contract. Keep `/analyze` docs unchanged except for cross-links.
  **Must NOT do**: Must NOT rewrite broad unrelated docs; must NOT leave the semantic-search API contract undocumented; must NOT leave route names or CLI names inconsistent between code and docs.

  **Recommended Agent Profile**:
  - Category: `writing` - Reason: documentation plus test/document alignment
  - Skills: `[]` - no special skill required
  - Omitted: `['railway-docs']` - this is project-internal API documentation, not Railway docs research

  **Parallelization**: Can Parallel: NO | Wave 2 | Blocks: Final Verification | Blocked By: 1, 2, 3, 4, 5, 6, 7, 8

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `README.md` - existing operator-facing documentation for HTTP API and Telegram commands
  - Pattern: `docs/AI_ANALYZE_API_GUIDE.md` - existing async API guide style to mirror for semantic search, without editing analyze semantics unnecessarily
  - Test: `tests/test_api_server.py:560-719` - current async API contract testing style
  - Test: `tests/test_telegram_command_handler_analyze.py:211-220` - command behavior test style and fixture conventions
  - Test: `tests/test_report_generator.py:127-220` - report-output assertion style for compact rendered content

  **Acceptance Criteria** (agent-executable only):
  - [ ] Dedicated semantic-search docs exist and match the implemented route names, request body, and async polling flow.
  - [ ] Full semantic-search regression suite passes.
  - [ ] README lists the new Telegram command and HTTP endpoint without regressing `/analyze` documentation.
  - [ ] `uv run pytest tests/ -k "semantic_search or embedding_backfill" -v` passes.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Full semantic-search regression suite passes
    Tool: Bash
    Steps: uv run pytest tests/ -k "semantic_search or embedding_backfill" -v
    Expected: all semantic-search and backfill-related tests pass with no skipped critical-path scenarios
    Evidence: .sisyphus/evidence/task-9-regression.txt

  Scenario: Documentation reflects the implemented contract
    Tool: Bash
    Steps: uv run pytest tests/test_api_server_semantic_search.py::test_semantic_search_docs_contract_matches_code_examples -v
    Expected: test passes and doc examples stay aligned with the code contract for route names and request fields
    Evidence: .sisyphus/evidence/task-9-regression-error.txt
  ```

  **Commit**: NO | Message: `docs(semantic-search): align guides and regression coverage` | Files: `README.md`, `docs/SEMANTIC_SEARCH_API_GUIDE.md`, `tests/test_api_server_semantic_search.py`, `tests/test_telegram_command_handler_semantic_search.py`, `tests/test_semantic_search_service.py`, `tests/test_embedding_backfill_mode.py`

## Final Verification Wave (MANDATORY — after ALL implementation tasks)
> 4 review agents run in PARALLEL. ALL must APPROVE. Present consolidated results to user and get explicit "okay" before completing.
> **Do NOT auto-proceed after verification. Wait for user's explicit approval before marking work complete.**
> **Never mark F1-F4 as checked before getting user's okay.** Rejection or user feedback -> fix -> re-run -> present again -> wait for okay.
- [x] F1. Plan Compliance Audit — oracle
- [x] F2. Code Quality Review — unspecified-high
- [x] F3. Real Manual QA — unspecified-high (+ playwright if UI)
- [x] F4. Scope Fidelity Check — deep

## Commit Strategy
- Prefer 1 final user-facing commit after T9 + final verification.
- Commit message: `feat(semantic-search): add async semantic search for API and Telegram`
- If executor chooses milestone commits, keep them isolated to: contracts/schema, embeddings/backfill, search surfaces/tests.

## Success Criteria
- A caller can submit `hours + query + user_id` to the new HTTP endpoint and retrieve a completed compact cited report asynchronously.
- An authorized Telegram user can run `/semantic_search <hours> <topic>` and receive a compact cited report or a clear no-match/failure response.
- Newly ingested Postgres content receives embeddings automatically.
- Historical Postgres content can be backfilled idempotently with the explicit one-off mode.
- Semantic search never routes through the existing category-only `/analyze` prompt/report path.
- Unsupported SQLite runtime fails explicitly and predictably.
