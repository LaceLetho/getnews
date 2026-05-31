# Unified Semantic Search Across News and Intelligence

## TL;DR
> **Summary**: Extend semantic search from News-only `content_items` to a unified search over `content_items` and `raw_intelligence_items`, keeping tables separate and merging ranked hits with `UNION ALL`.
> **Deliverables**:
> - `raw_intelligence_items` embedding columns and 7-day backfill path
> - HNSW indexes `idx_content_embedding_hnsw` and `idx_intelligence_embedding_hnsw`
> - Unified storage/repository retrieval with mixed result DTO
> - Existing HTTP `/semantic-search` behavior changed to unified search
> - Telegram canonical `/semantic_search` command plus temporary `/news_semantic_search` alias
> - Updated README/AGENTS/architecture/skills docs and tests
> **Effort**: Large
> **Parallel**: YES - 6 waves
> **Critical Path**: Task 1 → Task 2 → Task 3 → Task 4 → Tasks 5/6 → Task 7 → Task 8

## Context
### Original Request
1. `raw_intelligence_items` 添加 `embedding vector` 列，为过去7天的行补生成 embedding。
2. 两表都建 HNSW 索引：`idx_content_embedding_hnsw`, `idx_intelligence_embedding_hnsw`，要求查询速度不能太慢。
3. 在检索层做 `UNION ALL` 两表结果合并排序，无需改 Schema 做单表统一。
4. 从用户角度把语义搜索统一成一个接口，一次搜索可以搜到库里所有类别的原始消息。把 `/news_semantic_search` 改成 `/semantic_search`，HTTP API接口和 `@skills` 相关文档一并修改。

### Interview Summary
- Current semantic search is News-only: `SemanticSearchService` depends on `ContentRepository`, and `SemanticSearchMatch.item` is a `ContentItem`.
- HTTP already exposes `/semantic-search`; plan keeps that path and changes semantics/docs to unified search.
- Telegram currently exposes `/news_semantic_search`; plan adds `/semantic_search` as canonical and keeps `/news_semantic_search` as a one-release compatibility alias.
- Backfill scope is exactly recent Intelligence rows where `collected_at >= now() - interval '7 days'`.
- Unified search must preserve bounded contexts: do not pass `RawIntelligenceItem` into News analyzers, and do not create a single unified persistence table.

### Metis Review (gaps addressed)
- Added mixed result DTO with `source_domain` discriminator.
- Added privacy/auth guardrail: keep Bearer auth; do not introduce unauthenticated raw intelligence search; redact internal chat/source IDs from human-facing report text.
- Fixed timestamp semantics: 7-day Intelligence backfill uses `collected_at`.
- Added executable performance validation with `EXPLAIN ANALYZE` and timing assertions.
- Added compatibility decision for `/news_semantic_search` alias.

## Work Objectives
### Core Objective
Make semantic search a single unified user-facing capability over News content and Intelligence raw messages, while keeping database tables/domain models separate.

### Deliverables
- PostgreSQL migration adding Intelligence embedding columns and HNSW indexes.
- Runtime schema/bootstrap compatibility for new columns/indexes.
- Intelligence embedding backfill for recent 7-day `raw_intelligence_items`.
- Unified result DTO and repository/storage retrieval using `UNION ALL`.
- Semantic search service/report updates for mixed News/Intelligence hits.
- HTTP API docs/contract updates for `/semantic-search` unified behavior.
- Telegram command rename and help text updates.
- Updated skills/docs and regression tests.

### Definition of Done (verifiable conditions with commands)
- `uv run pytest tests/news/test_semantic_search_service.py tests/news/test_api_server_semantic_search.py tests/news/test_telegram_command_handler_semantic_search.py tests/shared/test_semantic_search_storage.py tests/shared/test_semantic_search_contracts.py tests/intelligence/test_raw_intelligence_storage.py -v` passes.
- A DB check confirms `raw_intelligence_items.embedding`, `embedding_model`, `embedding_updated_at` exist.
- A DB check confirms exact HNSW index names `idx_content_embedding_hnsw` and `idx_intelligence_embedding_hnsw` exist.
- A seeded unified search returns at least one `source_domain="news"` hit and one `source_domain="intelligence"` hit in one ranked result set.
- Telegram tests confirm `/semantic_search` works and `/news_semantic_search` remains an alias.
- `EXPLAIN ANALYZE` evidence is saved showing DB retrieval meets target: p95 <500ms for 7-day window and <2s all-time on current scale, excluding LLM/embedding API latency.

### Must Have
- `raw_intelligence_items.embedding vector(1536)` plus `embedding_model TEXT` and `embedding_updated_at TIMESTAMPTZ`.
- HNSW indexes use cosine opclass because current query uses pgvector cosine distance `<=>`.
- Retrieval uses `UNION ALL` over per-table top-K subqueries, then global sort by similarity and recency.
- Mixed result DTO has at minimum: `source_domain`, `source_type`, `id`, `title`, `content_excerpt`, `url`, `source_name`, `source_id`, `published_at`, `collected_at`, `similarity`.
- Human-facing report labels each hit as News or Intelligence.
- Existing `/semantic-search` route path remains.
- `/semantic_search` is canonical Telegram command; `/news_semantic_search` remains as alias with deprecation note.

### Must NOT Have (guardrails, AI slop patterns, scope boundaries)
- Do not create a single unified search table.
- Do not wire deprecated entry-based Intelligence models (`EntryType`, `CanonicalIntelligenceEntry`, etc.) into active search.
- Do not pass `RawIntelligenceItem` into News-only analyzers/reporters as if it were `ContentItem`.
- Do not backfill all historical Intelligence rows; only 7 days unless explicitly requested later.
- Do not expose raw Intelligence search without the existing HTTP Bearer auth.
- Do not remove `/news_semantic_search` immediately.
- Do not add UI/admin screens, faceted search, LLM reranking, analytics, or new auth systems.

## Verification Strategy
> ZERO HUMAN INTERVENTION - all verification is agent-executed.
- Test decision: tests-after with targeted regression tests using existing pytest infrastructure.
- QA policy: Every task has agent-executed happy + failure/edge scenarios.
- Evidence: `.omo/evidence/task-{N}-{slug}.{ext}`

## Execution Strategy
### Parallel Execution Waves
> Target: 5-8 tasks per wave. <3 per wave (except final) = under-splitting.
> Extract shared dependencies as Wave-1 tasks for max parallelism.

Wave 1: Task 1 (schema/indexes foundation)
Wave 2: Task 2 (Intelligence embedding backfill)
Wave 3: Task 3 (unified DTO/storage retrieval)
Wave 4: Task 4 (service/report mixed results)
Wave 5: Tasks 5-6 (HTTP API and Telegram command updates in parallel)
Wave 6: Tasks 7-8 sequentially (docs/skills, then performance/regression evidence)

### Dependency Matrix (full, all tasks)
| Task | Depends On | Blocks |
|---|---|---|
| 1. Schema + HNSW migration | none | 2, 3, 8 |
| 2. Intelligence embedding backfill | 1 | 3, 8 |
| 3. Unified storage retrieval | 1, 2 | 4, 5 |
| 4. Service/report mixed results | 3 | 5, 6, 8 |
| 5. HTTP unified API contract | 3, 4 | 8 |
| 6. Telegram command rename | 4 | 8 |
| 7. Docs and skills | 5, 6 | 8 |
| 8. Performance verification | 1-7 | Final Verification Wave |

### Agent Dispatch Summary (wave → task count → categories)
| Wave | Task Count | Categories |
|---|---:|---|
| 1 | 1 | unspecified-high |
| 2 | 1 | unspecified-high |
| 3 | 1 | deep |
| 4 | 1 | unspecified-high |
| 5 | 2 | unspecified-high, quick |
| 6 | 2 | writing, deep |

## TODOs
> Implementation + Test = ONE task. Never separate.
> EVERY task MUST have: Agent Profile + Parallelization + QA Scenarios.

- [x] 1. Add Intelligence embedding schema and HNSW indexes

  **What to do**:
  - Add a new PostgreSQL migration under `migrations/postgresql/` after the latest numbered migration.
  - Migration MUST include:
    - `CREATE EXTENSION IF NOT EXISTS vector;`
    - `ALTER TABLE raw_intelligence_items ADD COLUMN IF NOT EXISTS embedding vector(1536);`
    - `ALTER TABLE raw_intelligence_items ADD COLUMN IF NOT EXISTS embedding_model TEXT;`
    - `ALTER TABLE raw_intelligence_items ADD COLUMN IF NOT EXISTS embedding_updated_at TIMESTAMPTZ;`
    - `CREATE INDEX IF NOT EXISTS idx_content_embedding_hnsw ON content_items USING hnsw (embedding vector_cosine_ops) WHERE embedding IS NOT NULL;`
    - `CREATE INDEX IF NOT EXISTS idx_intelligence_embedding_hnsw ON raw_intelligence_items USING hnsw (embedding vector_cosine_ops) WHERE embedding IS NOT NULL;`
  - Use non-concurrent index creation in the standard migration file for compatibility with transaction-wrapped migration runners. If production lock risk is unacceptable during execution, create an additional operator note in the migration comments with the exact `CREATE INDEX CONCURRENTLY` equivalent; do not replace the standard migration SQL with concurrent SQL unless the migration runner is proven autocommit-safe.
  - Update runtime schema/bootstrap code so fresh PostgreSQL databases create the new Intelligence embedding columns and both exact HNSW indexes. Runtime bootstrap must create `idx_content_embedding_hnsw` on `content_items.embedding` and `idx_intelligence_embedding_hnsw` on `raw_intelligence_items.embedding` when the backend is PostgreSQL.
  - Update storage schema tests so migration/runtime bootstrap parity catches the new columns and indexes.

  **Must NOT do**:
  - Do not add embedding columns to deprecated `intelligence_canonical_entries` or other legacy entry tables.
  - Do not change `content_items.embedding` dimensionality.
  - Do not rename existing `content_items` indexes other than adding `idx_content_embedding_hnsw`.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: schema migration plus runtime bootstrap and tests require careful cross-file consistency.
  - Skills: [] - No external skill required.
  - Omitted: [`use-railway`] - Deployment is not part of plan execution.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: 2, 3, 8 | Blocked By: none

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `migrations/postgresql/001_init.sql` - `CREATE EXTENSION IF NOT EXISTS vector`, `content_items.embedding vector(1536)`, `embedding_model`, `embedding_updated_at`, `semantic_search_jobs` schema.
  - Pattern: `migrations/postgresql/003_intelligence_schema.sql` - existing `raw_intelligence_items` table definition; add new columns against this table.
  - Pattern: `crypto_news_analyzer/storage/intelligence_schema.py` - runtime Intelligence table bootstrap; keep fresh DB creation aligned with migrations.
  - Test: `tests/shared/test_semantic_search_storage.py` - schema/migration parity patterns and Postgres semantic storage tests.

  **Acceptance Criteria** (agent-executable only):
  - [ ] `uv run pytest tests/shared/test_semantic_search_storage.py -v` passes.
  - [ ] DB query returns all three new columns: `SELECT column_name FROM information_schema.columns WHERE table_name='raw_intelligence_items' AND column_name IN ('embedding','embedding_model','embedding_updated_at') ORDER BY column_name;`
  - [ ] DB query returns exact index names: `SELECT indexname FROM pg_indexes WHERE indexname IN ('idx_content_embedding_hnsw','idx_intelligence_embedding_hnsw') ORDER BY indexname;`

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Fresh schema has Intelligence embedding support
    Tool: Bash
    Steps: Run `uv run pytest tests/shared/test_semantic_search_storage.py -v` after adding a test that initializes schema and inspects raw_intelligence_items columns.
    Expected: Test passes and confirms embedding, embedding_model, embedding_updated_at exist.
    Evidence: .omo/evidence/task-1-schema-columns.txt

  Scenario: HNSW index creation is idempotent
    Tool: Bash
    Steps: Apply migration twice in a disposable PostgreSQL test database or execute index creation SQL twice in test setup.
    Expected: Second run succeeds without duplicate-index failure; pg_indexes contains both exact names.
    Evidence: .omo/evidence/task-1-hnsw-idempotent.txt
  ```

  **Commit**: NO | Message: `feat(search): add intelligence embedding schema` | Files: [`migrations/postgresql/*`, `crypto_news_analyzer/storage/intelligence_schema.py`, `tests/shared/test_semantic_search_storage.py`]

- [x] 2. Add 7-day Intelligence embedding backfill path

  **What to do**:
  - Extend embedding runtime so `raw_intelligence_items` can be embedded using the existing `EmbeddingService` with model `text-embedding-3-small` and dimensions 1536.
  - Add repository/data-manager methods for Intelligence raw item embedding:
    - fetch missing raw Intelligence embeddings constrained by `collected_at >= now() - interval '7 days'`, `raw_text IS NOT NULL`, non-empty trimmed raw text.
    - persist embedding with `embedding = CAST(? AS vector)`, `embedding_model`, `embedding_updated_at`.
  - Extend the existing `EmbeddingBackfillRunner`; do not create a separate runner class unless only used internally by `EmbeddingBackfillRunner`.
  - Add exact CLI flags to `main.py`:
    - `--include-intelligence` boolean flag, default `False`.
    - `--intelligence-days` integer flag, default `7`, validated as positive.
  - Default behavior MUST NOT unexpectedly backfill Intelligence unless the new flag is provided. The plan requirement is to provide and verify the 7-day path, not to alter existing News-only backfill defaults silently.
  - Use text input for Intelligence embeddings as `raw_text` only. Do not prepend source IDs/chat IDs to embedding text.
  - Skip rows where `raw_text` is NULL or whitespace.
  - On per-row embedding failure, log and continue; final report must count examined/embedded/skipped/failed.

  **Must NOT do**:
  - Do not embed rows older than 7 days unless `--intelligence-days` is explicitly changed.
  - Do not call LLM analysis models; use only the embedding service.
  - Do not store API keys or raw embedding payloads in logs.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: repository, CLI, and test changes with external API abstraction.
  - Skills: [] - Existing test stubs are enough.
  - Omitted: [`grok-api-reference`] - Embeddings use existing OpenAI-compatible `EmbeddingService`, not Grok API design.

  **Parallelization**: Can Parallel: NO | Wave 2 | Blocks: 3, 8 | Blocked By: 1

  **References**:
  - Pattern: `crypto_news_analyzer/semantic_search/embedding_service.py` - existing `EmbeddingService.generate_embedding()` and ContentItem batch embedding patterns.
  - Pattern: `crypto_news_analyzer/semantic_search/backfill_runner.py` - batch report counters and failure handling.
  - Pattern: `crypto_news_analyzer/main.py` - `--mode embedding-backfill`, `--batch-size`, `--limit` CLI wiring.
  - Pattern: `crypto_news_analyzer/storage/data_manager.py` - `get_content_items_missing_embeddings()` and `update_content_embedding()` SQL patterns.
  - API/Type: `crypto_news_analyzer/domain/models.py:729` - `RawIntelligenceItem.raw_text`, `collected_at`, `published_at`, `source_url`.
  - Test: `tests/shared/test_embedding_backfill_mode.py` - CLI/backfill mode pattern.
  - Test: `tests/news/test_embedding_service.py` - embedding service failure/retry pattern.

  **Acceptance Criteria**:
  - [ ] `uv run pytest tests/shared/test_embedding_backfill_mode.py tests/news/test_embedding_service.py -v` passes.
  - [ ] New test seeds one recent `raw_intelligence_items` row and one older-than-7-days row; backfill embeds only the recent row.
  - [ ] Backfill report includes counts for Intelligence examined/embedded/skipped/failed.
  - [ ] New test runs default `embedding-backfill` without `--include-intelligence` and verifies missing Intelligence embeddings remain NULL.

  **QA Scenarios**:
  ```
  Scenario: Backfill embeds only recent Intelligence raw text
    Tool: Bash
    Steps: Run targeted pytest that seeds two raw_intelligence_items rows: collected_at now-1d and now-8d, both missing embedding, then runs intelligence backfill with days=7.
    Expected: Recent row has embedding/model/updated_at; older row remains NULL.
    Evidence: .omo/evidence/task-2-backfill-recent.txt

  Scenario: Blank raw_text is skipped without aborting batch
    Tool: Bash
    Steps: Run targeted pytest with one whitespace raw_text row and one valid row.
    Expected: Valid row embedded; blank row counted as skipped; process exits success.
    Evidence: .omo/evidence/task-2-backfill-skip-blank.txt

  Scenario: Default backfill remains News-only
    Tool: Bash
    Steps: Run targeted pytest that seeds one raw_intelligence_items row missing embedding, then invokes embedding-backfill without `--include-intelligence`.
    Expected: Intelligence row embedding remains NULL and report has no Intelligence embedded count.
    Evidence: .omo/evidence/task-2-default-news-only.txt
  ```

  **Commit**: NO | Message: `feat(search): backfill intelligence embeddings` | Files: [`crypto_news_analyzer/semantic_search/backfill_runner.py`, `crypto_news_analyzer/main.py`, `crypto_news_analyzer/storage/data_manager.py`, `crypto_news_analyzer/storage/repositories.py`, `tests/shared/test_embedding_backfill_mode.py`]

- [x] 3. Create unified search DTO and `UNION ALL` storage retrieval

  **What to do**:
  - Add exact DTO `UnifiedSemanticSearchHit` to new file `crypto_news_analyzer/semantic_search/models.py` and import it from `crypto_news_analyzer/semantic_search/service.py`. Use this exact class name.
  - Required fields: `hit_key`, `source_domain`, `id`, `source_type`, `source_name`, `source_id`, `title`, `content_excerpt`, `url`, `published_at`, `collected_at`, `similarity`, `matched_subqueries`.
  - `hit_key` MUST be `f"{source_domain}:{id}"` and all merge/dedupe maps MUST key by `hit_key`, never bare `id`.
  - Mapping rules:
    - News: `source_domain='news'`, `title=content_items.title`, `content_excerpt=content_items.content`, `url=content_items.url`, `published_at=content_items.publish_time`, `collected_at=NULL`, `source_name=content_items.source_name`.
    - Intelligence: `source_domain='intelligence'`, `title` = first 80 non-control characters of `raw_text`, `content_excerpt=raw_text`, `url=source_url`, `published_at=raw_intelligence_items.published_at`, `collected_at=raw_intelligence_items.collected_at`, `source_name=source_type`, `source_id=datasource_id` only.
  - Add a PostgreSQL storage method that performs vector search with `UNION ALL`:
    - Each table subquery computes `1 - (embedding <=> CAST(? AS vector)) AS similarity`.
    - Each table filters `embedding IS NOT NULL`, `embedding_model = semantic_search_config.embedding_model`, and time window.
    - News time column: `publish_time`.
    - Intelligence time column: `COALESCE(published_at, collected_at)` for search windows; backfill still uses `collected_at`.
    - Each table subquery applies `ORDER BY embedding <=> CAST(? AS vector) ASC LIMIT semantic_search_config.per_subquery_limit` to allow HNSW use. This is the exact `per_domain_limit`; do not invent a separate config.
    - Outer query orders by `similarity DESC`, then `COALESCE(published_at, collected_at) DESC`, then `source_domain ASC`, then `id ASC`, and applies final `LIMIT`.
  - Add keyword fallback across both tables using `UNION ALL` with News title/content and Intelligence raw_text.
  - Keep SQLite semantic search unsupported as today.

  **Must NOT do**:
  - Do not build mixed DTO by mutating `ContentItem` or `RawIntelligenceItem` classes into each other.
  - Do not remove existing `ContentRepository.semantic_search_by_similarity()` until callers are migrated.
  - Do not use `SELECT *` in union SQL; explicitly project aligned columns.
  - Do not expose `chat_id`, `thread_id`, or raw internal `source_id` as display fields; Intelligence `source_id` in the DTO is `datasource_id` only.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: central retrieval contract and SQL performance/ranking correctness.
  - Skills: [] - No external skill required.
  - Omitted: [`frontend-ui-ux`] - No UI work.

  **Parallelization**: Can Parallel: NO | Wave 3 | Blocks: 4, 5 | Blocked By: 1, 2

  **References**:
  - Pattern: `crypto_news_analyzer/storage/data_manager.py:1238` - existing `semantic_search_similar()` cosine search SQL.
  - Pattern: `crypto_news_analyzer/storage/data_manager.py:1310` - existing keyword search pattern.
  - Pattern: `crypto_news_analyzer/storage/repositories.py:380` - `PostgresContentRepository` delegates to DataManager.
  - API/Type: `crypto_news_analyzer/domain/repositories.py:333` - current abstract semantic search method signature.
  - API/Type: `crypto_news_analyzer/domain/models.py:729` - `RawIntelligenceItem` fields.
  - Test: `tests/shared/test_semantic_search_storage.py` - Postgres retrieval and SQLite unsupported behavior.

  **Acceptance Criteria**:
  - [ ] New storage test seeds one News row and one Intelligence row with deterministic embeddings and verifies one unified ordered result list contains both.
  - [ ] New storage test verifies time window uses News `publish_time` and Intelligence `COALESCE(published_at, collected_at)`.
  - [ ] SQLite unified semantic search raises the same unsupported-backend error pattern as current semantic search.
  - [ ] New storage test seeds News and Intelligence rows with the same `id` and verifies both are preserved because `hit_key` differs.
  - [ ] New storage test seeds a row with mismatched `embedding_model` and verifies it is excluded.

  **QA Scenarios**:
  ```
  Scenario: Unified vector search returns News and Intelligence hits
    Tool: Bash
    Steps: Run targeted storage pytest seeding deterministic pgvector values in both tables, then call unified vector retrieval with a matching query vector.
    Expected: Result list has both `source_domain="news"` and `source_domain="intelligence"`, sorted by similarity descending.
    Evidence: .omo/evidence/task-3-union-vector.txt

  Scenario: One empty domain does not fail unified search
    Tool: Bash
    Steps: Run targeted storage pytest with only Intelligence rows and no matching News rows.
    Expected: Unified retrieval returns Intelligence hits without exception and matched_count equals Intelligence hit count.
    Evidence: .omo/evidence/task-3-empty-domain.txt

  Scenario: Same bare ID in both domains is preserved
    Tool: Bash
    Steps: Run targeted storage pytest with content_items.id='same-id' and raw_intelligence_items.id='same-id'.
    Expected: Unified retrieval returns two hits with hit_key values `news:same-id` and `intelligence:same-id`.
    Evidence: .omo/evidence/task-3-hit-key-dedupe.txt

  Scenario: Mismatched embedding_model is excluded
    Tool: Bash
    Steps: Run targeted storage pytest with one row embedding_model matching SemanticSearchConfig.embedding_model and one row using `other-model`.
    Expected: Only the matching-model row appears in unified vector results.
    Evidence: .omo/evidence/task-3-model-filter.txt
  ```

  **Commit**: NO | Message: `feat(search): add unified storage retrieval` | Files: [`crypto_news_analyzer/domain/*`, `crypto_news_analyzer/storage/*`, `crypto_news_analyzer/semantic_search/*`, `tests/shared/test_semantic_search_storage.py`]

- [x] 4. Update SemanticSearchService and reports for mixed hits

  **What to do**:
  - Replace internal `SemanticSearchMatch.item: ContentItem` dependence with unified hit/match structure.
  - Preserve existing query planning, subquery capping, keyword fallback, retained cap, and LLM synthesis batching behavior.
  - Batch prompt must show each item with domain label and safe fields:
    - News display: `[News] {source_name} | {title} | {url}`.
    - Intelligence display: `[Intelligence] {source_type} | {title} | {source_url or "no url"}`.
  - Human-facing report must not expose raw `chat_id`, internal raw `source_id`, or `datasource_id`. Use `source_type`/`source_name` labels instead.
  - Merge existing matches by `UnifiedSemanticSearchHit.hit_key`; never dedupe News and Intelligence together by bare `id`.
  - `SemanticSearchService.search()` MUST return `source_breakdown` with exact shape `{ "news": {"matched_count": int, "retained_count": int}, "intelligence": {"matched_count": int, "retained_count": int} }`.
  - Compute `source_breakdown.*.matched_count` from the full merged match set before retained-item cap.
  - Compute `source_breakdown.*.retained_count` from the ranked retained set after applying `max_retained_items`.
  - For domains with zero hits, include the domain key with both counts set to `0`.
  - No-match report must say unified search found no News or Intelligence matches.
  - Existing output title `# 主题检索报告` can remain.
  - Update tests to cover mixed retained set, report prompt truncation for Intelligence raw_text, and no-match unified wording.

  **Must NOT do**:
  - Do not change LLM providers or prompt model selection.
  - Do not introduce LLM reranking.
  - Do not remove keyword fallback.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: service behavior and prompt/report compatibility.
  - Skills: [] - Existing test stubs are sufficient.
  - Omitted: [`llm-instructor`] - No instructor model contract changes.

  **Parallelization**: Can Parallel: NO | Wave 4 | Blocks: 5, 6, 8 | Blocked By: 3

  **References**:
  - Pattern: `crypto_news_analyzer/semantic_search/service.py:36` - current `SemanticSearchMatch` ContentItem coupling to remove.
  - Pattern: `crypto_news_analyzer/semantic_search/service.py:286` - current `_retrieve_matches()` vector + keyword merge behavior.
  - Pattern: `crypto_news_analyzer/semantic_search/report_builder.py` - current Markdown report builder.
  - Prompt: `prompts/semantic_search_query_planner.md` - query decomposition prompt path.
  - Prompt: `prompts/semantic_search_report.md` - final report prompt path.
  - Test: `tests/news/test_semantic_search_service.py` - query planner, retained cap, keyword fallback, prompt truncation tests.

  **Acceptance Criteria**:
  - [ ] `uv run pytest tests/news/test_semantic_search_service.py -v` passes with updated mixed-hit tests.
  - [ ] A mixed test with 1 News and 1 Intelligence hit produces a prompt containing `[News]` and `[Intelligence]` labels.
  - [ ] No internal `chat_id`/`datasource_id` appears in generated human-facing prompt/report test output.
  - [ ] A service test with same bare `id` in News and Intelligence preserves both hits because keys are `news:{id}` and `intelligence:{id}`.
  - [ ] Service tests verify exact `source_breakdown` counts for mixed, News-only, Intelligence-only, and no-match result sets.

  **QA Scenarios**:
  ```
  Scenario: Mixed matches are retained and summarized
    Tool: Bash
    Steps: Run semantic service pytest with stub repository returning one News hit and one Intelligence hit.
    Expected: matched_count=2, retained_count=2, prompt/report includes both domain labels.
    Evidence: .omo/evidence/task-4-mixed-report.txt

  Scenario: Intelligence raw_text truncates in batch prompt
    Tool: Bash
    Steps: Run pytest using an Intelligence hit with raw_text longer than synthesis_item_content_max_chars.
    Expected: Prompt contains truncated marker and not full long raw_text.
    Evidence: .omo/evidence/task-4-raw-text-truncation.txt

  Scenario: Same bare IDs across domains are not collapsed
    Tool: Bash
    Steps: Run service pytest with stub repository returning a News hit and Intelligence hit sharing id `same-id`.
    Expected: matched_count=2 and retained set contains both `news:same-id` and `intelligence:same-id`.
    Evidence: .omo/evidence/task-4-same-id-preserved.txt

  Scenario: Source breakdown is computed by service
    Tool: Bash
    Steps: Run service pytest cases for mixed hits, News-only hits, Intelligence-only hits, and no matches.
    Expected: `source_breakdown` is always present with exact `news` and `intelligence` keys and correct matched_count/retained_count integers.
    Evidence: .omo/evidence/task-4-source-breakdown.txt
  ```

  **Commit**: NO | Message: `feat(search): support mixed semantic reports` | Files: [`crypto_news_analyzer/semantic_search/service.py`, `crypto_news_analyzer/semantic_search/report_builder.py`, `prompts/*`, `tests/news/test_semantic_search_service.py`]

- [x] 5. Keep HTTP `/semantic-search` path and update contract to unified behavior

  **What to do**:
  - Keep route constants in `crypto_news_analyzer/api_server.py` as `/semantic-search`, `/semantic-search/{job_id}`, `/semantic-search/{job_id}/result`.
  - Update Pydantic response/job models only as needed for mixed metadata. Preserve backward-compatible fields: `query`, `time_window_hours`, `matched_count`, `retained_count`, `report_content`, `status`, `error_message`.
  - Add exact optional response/job-result field `source_breakdown: Dict[str, Dict[str, int]]` to semantic search result payloads.
  - `source_breakdown` shape MUST be exactly: `{ "news": {"matched_count": int, "retained_count": int}, "intelligence": {"matched_count": int, "retained_count": int} }`.
  - Do not add per-hit raw content arrays to the HTTP response in this task; the Markdown report remains the primary human-readable result.
  - Update `ensure_semantic_search_supported()` only if it needs to validate unified repository availability; keep Postgres-only guard.
  - API request shape remains `{ "hours": number, "query": string, "user_id": string }`.
  - Add/modify API tests for mixed result metadata and ensure old News-only successful flow still passes.

  **Must NOT do**:
  - Do not rename HTTP path to `/semantic_search`; HTTP convention remains hyphenated `/semantic-search`.
  - Do not remove async job pattern.
  - Do not expose endpoint without Bearer auth.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: public API compatibility and async job behavior.
  - Skills: [] - Existing API tests cover patterns.
  - Omitted: [`playwright`] - No browser/UI verification needed.

  **Parallelization**: Can Parallel: YES | Wave 5 | Blocks: 7, 8 | Blocked By: 3, 4

  **References**:
  - Pattern: `crypto_news_analyzer/api_server.py:65` - semantic route constants.
  - Pattern: `crypto_news_analyzer/api_server.py:1318` - `POST /semantic-search` async job creation.
  - Pattern: `crypto_news_analyzer/api_server.py:1364` - job status endpoint.
  - Pattern: `crypto_news_analyzer/api_server.py:1376` - result endpoint.
  - Pattern: `crypto_news_analyzer/api_server.py:1040` - `_run_semantic_search_job()` service execution and persistence.
  - Test: `tests/news/test_api_server_semantic_search.py` - async job lifecycle, blank query, SQLite 503 guard.

  **Acceptance Criteria**:
  - [ ] `uv run pytest tests/news/test_api_server_semantic_search.py -v` passes.
  - [ ] POST `/semantic-search` still returns `202 Accepted` and same status/result URL structure.
  - [ ] Result endpoint can return unified report content containing both News and Intelligence labels in a stubbed mixed service test.
  - [ ] Result endpoint includes `source_breakdown` exactly shaped as `{ "news": {"matched_count": int, "retained_count": int}, "intelligence": {"matched_count": int, "retained_count": int} }`.

  **QA Scenarios**:
  ```
  Scenario: HTTP unified search job completes with mixed report
    Tool: Bash
    Steps: Run API pytest with stub SemanticSearchService returning mixed News/Intelligence report content.
    Expected: POST returns 202; polling returns completed; result contains mixed report and matched_count=2.
    Evidence: .omo/evidence/task-5-http-mixed-job.txt

  Scenario: HTTP backward-compatible request still works
    Tool: Bash
    Steps: Run existing API semantic search tests without changing request body shape.
    Expected: Existing tests pass; clients using hours/query/user_id are not broken.
    Evidence: .omo/evidence/task-5-http-compat.txt

  Scenario: HTTP result exposes exact source_breakdown shape
    Tool: Bash
    Steps: Run API pytest with stub SemanticSearchService returning source_breakdown for news and intelligence counts.
    Expected: Result JSON includes `source_breakdown.news.matched_count`, `source_breakdown.news.retained_count`, `source_breakdown.intelligence.matched_count`, and `source_breakdown.intelligence.retained_count` as integers.
    Evidence: .omo/evidence/task-5-source-breakdown.txt
  ```

  **Commit**: NO | Message: `feat(api): unify semantic search endpoint behavior` | Files: [`crypto_news_analyzer/api_server.py`, `tests/news/test_api_server_semantic_search.py`]

- [x] 6. Rename Telegram command to `/semantic_search` with `/news_semantic_search` alias

  **What to do**:
  - Register `CommandHandler("semantic_search", self._handle_semantic_search_command)` as canonical.
  - Keep `CommandHandler("news_semantic_search", self._handle_semantic_search_command)` as compatibility alias.
  - Update bot command list and help text to show `/semantic_search <hours> <topic>` as canonical.
  - Help text may mention `/news_semantic_search` as deprecated alias for one release.
  - Update user-facing validation errors to reference `/semantic_search`.
  - Ensure both commands call the same `handle_semantic_search_command()` path and unified `SemanticSearchService`.

  **Must NOT do**:
  - Do not remove alias in this task.
  - Do not rename unrelated `/news_analyze`, `/news_market`, or `/topic_*` commands.
  - Do not create a separate Intelligence semantic command.

  **Recommended Agent Profile**:
  - Category: `quick` - Reason: command registration/help/test updates once service is unified.
  - Skills: [] - Existing Telegram tests are sufficient.
  - Omitted: [`bird-commands-reference`] - X/Twitter CLI unrelated.

  **Parallelization**: Can Parallel: YES | Wave 5 | Blocks: 7, 8 | Blocked By: 4

  **References**:
  - Pattern: `crypto_news_analyzer/reporters/telegram_command_handler.py:242` - current `news_semantic_search` registration.
  - Pattern: `crypto_news_analyzer/reporters/telegram_command_handler.py:1057` - `_handle_semantic_search_command()` argument parsing.
  - Pattern: `crypto_news_analyzer/reporters/telegram_command_handler.py:1593` - `handle_semantic_search_command()` business dispatch.
  - Pattern: `crypto_news_analyzer/reporters/telegram_command_handler.py:1733` - background execution and notification.
  - Test: `tests/news/test_telegram_command_handler_semantic_search.py` - command registration, help, validation, background report delivery.

  **Acceptance Criteria**:
  - [ ] `uv run pytest tests/news/test_telegram_command_handler_semantic_search.py -v` passes.
  - [ ] Tests confirm `/semantic_search` is registered and appears in help.
  - [ ] Tests confirm `/news_semantic_search` is still registered and dispatches to same handler.

  **QA Scenarios**:
  ```
  Scenario: Canonical Telegram command dispatches unified search
    Tool: Bash
    Steps: Run Telegram command handler pytest invoking `/semantic_search 24 BTC ETF`.
    Expected: Handler validates args, starts background search, and uses unified SemanticSearchService.
    Evidence: .omo/evidence/task-6-telegram-canonical.txt

  Scenario: Deprecated alias still works
    Tool: Bash
    Steps: Run Telegram command handler pytest invoking `/news_semantic_search 24 BTC ETF`.
    Expected: Same handler path executes; response does not fail; help marks alias deprecated.
    Evidence: .omo/evidence/task-6-telegram-alias.txt
  ```

  **Commit**: NO | Message: `feat(telegram): add unified semantic_search command` | Files: [`crypto_news_analyzer/reporters/telegram_command_handler.py`, `tests/news/test_telegram_command_handler_semantic_search.py`]

- [x] 7. Update README, AGENTS, architecture docs, and smart-news skills

  **What to do**:
  - Update `README.md`:
    - Feature list should describe semantic search as unified News + Intelligence raw message search.
    - Telegram command list should use `/semantic_search <hours> <topic>` and mention `/news_semantic_search` alias/deprecation.
    - HTTP API section should state `/semantic-search` searches both `ContentItem` and `RawIntelligenceItem` under Bearer auth.
  - Update `AGENTS.md`:
    - Replace statement that semantic search only operates on ContentItem with new unified behavior.
    - Preserve boundary rule: do not mix ContentItem and RawIntelligenceItem in analyzers; semantic search uses DTO/adapters only.
  - Update `docs/ARCHITECTURE_BOUNDARIES.md`:
    - Update invariant surfaces and command names.
    - Document unified search as the explicit exception where both domains are retrieved together through a DTO, not mixed model objects.
  - Update `skills/smart-news/SKILL.md` and `skills/smart-news/references/semantic-search.md`:
    - Request/response contract.
    - Unified scope.
    - Telegram command rename.
    - Backfill command for Intelligence recent 7 days.
    - HNSW index/performance notes.
  - Update validation tests for skills/docs where present.

  **Must NOT do**:
  - Do not document legacy `api-server` as primary runtime.
  - Do not tell agents to pass raw Intelligence items into News analysis endpoints.
  - Do not remove existing `/semantic-search` HTTP docs.

  **Recommended Agent Profile**:
  - Category: `writing` - Reason: documentation and skill contract updates.
  - Skills: [] - No specialized skill required.
  - Omitted: [`customize-opencode`] - Updating project skills/docs, not OpenCode configuration.

  **Parallelization**: Can Parallel: NO | Wave 6 | Blocks: 8 | Blocked By: 5, 6

  **References**:
  - Docs: `README.md` - current feature/API/Telegram lists.
  - Docs: `AGENTS.md` - current dual-domain and semantic search guidance.
  - Docs: `docs/ARCHITECTURE_BOUNDARIES.md` - domain invariant surfaces.
  - Skill: `skills/smart-news/SKILL.md` - smart-news workflow docs.
  - Skill: `skills/smart-news/references/semantic-search.md` - canonical semantic search API reference.
  - Test: `tests/shared/test_openclaw_skill_smart_news.py` - skill validation.

  **Acceptance Criteria**:
  - [ ] `uv run pytest tests/shared/test_openclaw_skill_smart_news.py -v` passes.
  - [ ] Content search confirms no docs still claim semantic search is News-only except historical/deprecation context.
  - [ ] Content search confirms `/semantic_search` appears in Telegram docs and `/news_semantic_search` is marked alias/deprecated.

  **QA Scenarios**:
  ```
  Scenario: Smart-news skill documents unified semantic search
    Tool: Bash
    Steps: Run `uv run pytest tests/shared/test_openclaw_skill_smart_news.py -v` after updating skill docs.
    Expected: Skill validation passes and semantic search reference includes News + Intelligence scope.
    Evidence: .omo/evidence/task-7-skill-docs.txt

  Scenario: Docs no longer describe semantic search as News-only
    Tool: Bash
    Steps: Run a project content search for `news_semantic_search`, `ContentItem only`, and `RawIntelligenceItem` in docs/skills files.
    Expected: Only intentional alias/deprecation references remain; unified behavior is documented.
    Evidence: .omo/evidence/task-7-doc-grep.txt
  ```

  **Commit**: NO | Message: `docs(search): document unified semantic search` | Files: [`README.md`, `AGENTS.md`, `docs/ARCHITECTURE_BOUNDARIES.md`, `skills/smart-news/SKILL.md`, `skills/smart-news/references/semantic-search.md`, `tests/shared/test_openclaw_skill_smart_news.py`]

- [x] 8. Validate performance, edge cases, and full regression suite

  **What to do**:
  - Add a performance evidence script or pytest helper that runs `EXPLAIN ANALYZE` for the unified vector query.
  - The evidence must show:
    - HNSW indexes exist.
    - Query plan uses vector index scans where PostgreSQL planner can use them with the selected query shape.
    - DB retrieval timing meets p95 target on available seeded/current data: <500ms for 7-day window and <2s all-time, excluding LLM/embedding latency.
  - Validate edge cases:
    - no News matches, Intelligence matches exist;
    - News matches exist, no Intelligence matches;
    - neither domain matches;
    - null embeddings;
    - mismatched embedding_model excluded;
    - very long raw_text truncates in prompt;
    - exact 7-day backfill boundary.
  - Run the final targeted regression command and save output.

  **Must NOT do**:
  - Do not tune by disabling correctness tests.
  - Do not hardcode production row counts.
  - Do not claim performance success without captured command output.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: final cross-cutting performance and regression verification.
  - Skills: [] - No external skill required.
  - Omitted: [`use-railway`] - Production deployment/metrics are out of scope unless user asks.

  **Parallelization**: Can Parallel: NO | Wave 6 | Blocks: Final Verification Wave | Blocked By: 1, 2, 3, 4, 5, 6, 7

  **References**:
  - Pattern: `tests/shared/test_semantic_search_storage.py` - storage/performance-adjacent tests.
  - Pattern: `tests/news/test_api_server_semantic_search.py` - API regression tests.
  - Pattern: `tests/news/test_telegram_command_handler_semantic_search.py` - Telegram regression tests.
  - Pattern: `tests/news/test_semantic_search_service.py` - service regression tests.
  - SQL: use exact HNSW index names from Task 1.

  **Acceptance Criteria**:
  - [ ] `uv run pytest tests/news/test_semantic_search_service.py tests/news/test_api_server_semantic_search.py tests/news/test_telegram_command_handler_semantic_search.py tests/shared/test_semantic_search_storage.py tests/shared/test_semantic_search_contracts.py tests/intelligence/test_raw_intelligence_storage.py tests/shared/test_openclaw_skill_smart_news.py -v` passes.
  - [ ] `.omo/evidence/task-8-explain-analyze.txt` contains query plans and timings.
  - [ ] `.omo/evidence/task-8-regression.txt` contains final pytest output.

  **QA Scenarios**:
  ```
  Scenario: Unified query meets performance target
    Tool: Bash
    Steps: Run EXPLAIN ANALYZE for 7-day and all-time unified vector query against available PostgreSQL database after indexes exist.
    Expected: 7-day retrieval <500ms and all-time retrieval <2s, excluding external API calls; evidence file includes query plan.
    Evidence: .omo/evidence/task-8-explain-analyze.txt

  Scenario: Full targeted regression passes
    Tool: Bash
    Steps: Run the full targeted pytest command listed in Acceptance Criteria.
    Expected: All targeted tests pass with no unexpected skips/failures.
    Evidence: .omo/evidence/task-8-regression.txt
  ```

  **Commit**: NO | Message: `test(search): verify unified semantic search performance` | Files: [`tests/*`, `.omo/evidence/*`]

## Final Verification Wave (MANDATORY — after ALL implementation tasks)
> 4 review agents run in PARALLEL. ALL must APPROVE. Present consolidated results to user and get explicit "okay" before completing.
> **Do NOT auto-proceed after verification. Wait for user's explicit approval before marking work complete.**
> **Never mark F1-F4 as checked before getting user's okay.** Rejection or user feedback -> fix -> re-run -> present again -> wait for okay.
- [x] F1. Plan Compliance Audit — oracle
- [x] F2. Code Quality Review — unspecified-high
- [x] F3. Real Manual QA — unspecified-high
- [x] F4. Scope Fidelity Check — deep

## Commit Strategy
- Default: one final commit after all tasks and verification pass.
- Suggested final message: `feat(search): unify semantic search across news and intelligence`
- Include migration, code, tests, and docs in the same final commit because API/schema/service/docs are one atomic behavior change.
- Do not commit `.omo/evidence/*` unless repository convention explicitly tracks evidence; keep evidence for review session.

## Success Criteria
- Unified semantic search returns News and Intelligence hits in one ranked result set.
- `raw_intelligence_items` recent 7-day rows can be embedded and searched.
- HNSW indexes exist with exact requested names.
- HTTP `/semantic-search` remains compatible and now documents unified behavior.
- Telegram `/semantic_search` is canonical; `/news_semantic_search` remains as alias.
- Docs and smart-news skill reflect the new unified contract.
- Tests and performance evidence pass without manual verification.

## Gap Classification
### Critical
- None blocking after defaults and Oracle phase 1.

### Auto-Resolved
- Privacy/auth risk: keep existing Bearer auth and redact internal chat/source IDs from human-facing report text.
- HTTP naming ambiguity: keep `/semantic-search` route path; update semantics/docs only.
- Telegram backward compatibility: add `/semantic_search` and keep `/news_semantic_search` alias.

### Defaults Applied
- Backfill timestamp: `raw_intelligence_items.collected_at >= now() - interval '7 days'`.
- Performance target: DB retrieval p95 <500ms for 7-day window and <2s all-time on current scale, excluding LLM/embedding API latency.
- Mixed DTO shape: use explicit `source_domain` discriminator and safe display fields.
