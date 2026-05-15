# Hidden Channel Intelligence Collection

## TL;DR
> **Summary**: Add a private intelligence collection pipeline that crawls allowlisted Telegram chats via Telethon and V2EX official API, extracts niche channel/slang knowledge with a low-cost `opencode-go` model, stores append-first observations plus current canonical knowledge in Postgres/pgvector, and exposes synchronous HTTP + Telegram query surfaces from `analysis-service`.
> **Deliverables**:
> - New Postgres/pgvector schema, repositories, migrations, and TDD coverage for raw items, observations, canonical knowledge, embeddings, related candidates, and 30-day raw TTL purge.
> - New datasource types for allowlisted Telegram chats and V2EX API sources, with env-only secrets and no generic HTML crawler.
> - New extraction pipeline using `StructuredOutputManager`/instructor patterns, independent `intelligence_collection.extraction` LLM config using existing `opencode-go` provider, conservative merge/update rules, and semantic indexing.
> - Bearer-protected synchronous HTTP APIs and authorized Telegram commands for time-desc and semantic querying, including exact raw text return only while raw TTL is valid.
> **Effort**: Large
> **Parallel**: YES - 5 waves
> **Critical Path**: Schema/contracts/tests → collectors → extraction/merge/embedding → APIs/Telegram → verification

## Context
### Original Request
User wants to accumulate niche/hidden channel information from forums and group discussions that search engines struggle to find. Sources include Telegram group accounts and forum sites such as `v2ex.com`. The system should hourly crawl discussions, send messages plus a preset prompt to a low-cost LLM, extract channel information and industry slang, store results in Postgres with explanation/source/topic tags, expose query APIs from `crypto-news-analysis` supporting recency and semantic search, and merge/update old records with new crawl results.

### Interview Summary
- Architecture: keep existing two app services + one shared Postgres/pgvector; do not add a third service.
- `crypto-news-ingestion`: crawl, raw persistence, LLM extraction, conservative merge/update, embeddings, TTL cleanup.
- `crypto-news-analysis`: synchronous Bearer HTTP query APIs and authorized Telegram query commands.
- Telegram: use Telethon/MTProto user client with dedicated Telegram account, 2FA, `StringSession` stored only in Railway env/secret. Crawl only explicitly configured/allowlisted chats; never crawl all joined chats by default.
- Forum: first version only V2EX official API v1/v2; no generic HTML crawler.
- Raw storage: raw source text is stored unchanged, retained for 30 days, then purged. Within TTL, query APIs may return raw text byte-for-byte/string-for-string with no redaction. After TTL, only structured knowledge/provenance metadata remains.
- Access: internal Bearer APIs plus authorized Telegram commands. No public product API. User chose no query audit.
- Labels: primary enum = `AI`, `crypto`, `暗网`, `账号交易`, `支付`, `游戏`, `电商`, `社媒`, `开发者工具`, `其他`; secondary tags may be LLM-generated.
- Model: extraction config is independent but uses existing `opencode-go` provider; embeddings reuse existing `EmbeddingService` / `text-embedding-3-small`.
- Merge: conservative exact normalized identifier matching only: URL/domain/TG username/invite link/slang term. Semantic similarity creates related candidates only and must not auto-merge canonical records.
- Initial backfill: last 24 hours, then hourly incremental.
- Testing: TDD with real Postgres/pgvector integration tests in addition to existing fake psycopg/SQLite patterns.

### Metis Review (gaps addressed)
- Added explicit Telegram source allowlisting to avoid crawling every joined chat.
- Added upstream edit/delete default: preserve observed raw text until TTL; record latest observed edit timestamp/status when source APIs expose it; do not retroactively delete derived knowledge unless local TTL cleanup removes raw text.
- Added canonical knowledge shape: type, normalized key, title/term, explanation, handles/URLs/domains, aliases, primary label, secondary tags, confidence, first/last seen, evidence counts, related candidates, prompt/model/schema versions.
- Added raw access contract: raw text is not a separate privileged endpoint because user selected authorized callers may receive original TTL-window raw text; enforce Bearer/Telegram authorization only, no audit.
- Added prompt/model versioning: new prompt/model applies prospectively; re-extraction is a manual/backfill concern outside v1 unless tests introduce deterministic fixture re-extraction.
- Added low-confidence behavior: store observations with confidence; expose canonical entries only when confidence threshold or repeated evidence passes configured thresholds; API may optionally include low-confidence observations with `include_low_confidence=true`.

## Work Objectives
### Core Objective
Create a production-ready v1 of hidden channel intelligence collection that fits the existing split-service architecture and produces queryable, updateable structured knowledge without broadening into generic scraping or public exposure.

### Deliverables
- Schema/migrations for raw intelligence items, extraction observations, canonical intelligence entries, aliases, related candidates, embeddings, crawl checkpoints, and TTL cleanup bookkeeping.
- Repository/domain/config models for intelligence collection and querying.
- Telethon Telegram collector for explicitly allowlisted chats only.
- V2EX official API collector.
- Structured LLM extraction pipeline with opencode-go model config, prompt/schema/model version storage, and confidence handling.
- Conservative merge/update engine and related-candidate creation.
- Embedding generation and semantic search over canonical entries and raw TTL-window evidence.
- Synchronous HTTP query endpoints and authorized Telegram query commands.
- TDD coverage: unit, FastAPI TestClient, Telegram command handler tests, and real Postgres/pgvector integration tests.

### Slang Collection Design
- Black/industry slang is a first-class canonical intelligence entry with `entry_type=slang`, not a secondary attribute of channel entries.
- Slang observation fields: `term`, `normalized_term`, `literal_meaning`, `contextual_meaning`, `usage_example_raw_item_id`, `usage_quote`, `primary_label`, `secondary_tags`, `confidence`, `aliases_or_variants`, `detected_language`, `model_name`, `prompt_version`, `schema_version`.
- Canonical slang fields: `normalized_key`, `display_name`, `explanation`, `usage_summary`, `primary_label`, `secondary_tags`, `confidence`, `first_seen_at`, `last_seen_at`, `evidence_count`, `aliases`, `related_channel_entry_ids`, `embedding_text`.
- Slang merge rule: exact normalized term match merges; aliases/variants can be attached when extracted from the same raw evidence or exact observation relation; semantic similarity only creates related candidates.
- Slang search behavior: time-desc queries use `last_seen_at`; semantic search embeds `term + explanation + usage_summary + aliases + primary/secondary tags`; detail views can show TTL-window raw usage examples when `include_raw=true`.
- Example expected extraction: “土区礼品卡” → `entry_type=slang`, primary label `账号交易` or `支付`, contextual meaning “土耳其区礼品卡/充值方式”, aliases including “土区卡” if observed, and related channel candidates only when exact evidence mentions a channel handle/link.

### Definition of Done (verifiable conditions with commands)
- `uv run pytest tests/test_intelligence_models.py tests/test_intelligence_merge.py tests/test_intelligence_ttl.py -v` passes.
- `uv run pytest tests/test_intelligence_telegram_collector.py tests/test_intelligence_v2ex_collector.py -v` passes with external APIs mocked.
- `uv run pytest tests/test_intelligence_extraction.py tests/test_intelligence_api.py tests/test_intelligence_telegram_commands.py -v` passes.
- `TEST_DATABASE_URL=postgresql://... uv run pytest tests/integration/test_intelligence_pgvector.py -v` passes against a real Postgres database with pgvector enabled.
- `uv run pytest tests/ -v` passes.
- `uv run mypy crypto_news_analyzer/` passes.
- `uv run flake8 crypto_news_analyzer/` passes.

### Must Have
- Must reuse existing `ingestion` and `analysis-service` roles.
- Must not add a third service.
- Must store Telegram `StringSession`, V2EX PAT, API keys, and all secrets only in environment/secrets, never datasource DB rows, `config.jsonc`, logs, or API responses.
- Must crawl only explicitly configured Telegram chat IDs/usernames; never enumerate all joined chats.
- Must store raw source text unchanged and purge it after 30 days.
- Must keep derived structured knowledge after raw TTL purge.
- Must expose raw text only for retained raw evidence and only to existing Bearer/authorized Telegram surfaces.
- Must not implement query audit, because user explicitly rejected it.
- Must preserve provenance, confidence, prompt version, model version, schema version, and evidence IDs.
- Must perform only conservative exact-match merges.
- Must treat semantic similarity as related candidates only.
- Must use V2EX official API only.

### Must NOT Have (guardrails, AI slop patterns, scope boundaries)
- Must not implement generic HTML/forum scraping in v1.
- Must not auto-join Telegram groups or discover chats from the user account.
- Must not redact, summarize, or mutate raw text when returning TTL-window raw evidence.
- Must not expose public unauthenticated APIs.
- Must not add query audit tables/events.
- Must not merge entities solely by LLM judgment or embedding similarity.
- Must not store illegal secrets/private credentials found in content as first-class “channel info”; raw text may contain them within TTL, but extracted canonical knowledge should not promote private keys/tokens/passwords.
- Must not recommend legacy `api-server` mode as primary runtime.

## Verification Strategy
> ZERO HUMAN INTERVENTION - all verification is agent-executed.
- Test decision: TDD + pytest/FastAPI TestClient/Telegram handler tests + real Postgres/pgvector integration tests.
- QA policy: Every task has agent-executed scenarios.
- Evidence: `.sisyphus/evidence/task-{N}-{slug}.{ext}`

## Execution Strategy
### Parallel Execution Waves
> Target: 5-8 tasks per wave. <3 per wave (except final) = under-splitting.
> Extract shared dependencies as Wave-1 tasks for max parallelism.

Wave 1: Task 1 schema/contracts/test foundation; Task 2 config/datasource validation; Task 3 test infrastructure.
Wave 2: Task 4 Telegram collector; Task 5 V2EX collector; Task 6 extraction prompt/schema/service.
Wave 3: Task 7 merge/update engine; Task 8 embeddings/semantic retrieval; Task 9 scheduler/TTL orchestration.
Wave 4: Task 10 HTTP APIs; Task 11 Telegram commands; Task 12 security/secret guardrails.
Wave 5: Task 13 integration hardening and docs/config examples.

### Dependency Matrix (full, all tasks)
- Task 1 blocks Tasks 4-13.
- Task 2 blocks Tasks 4, 5, 6, 9, 12, 13.
- Task 3 blocks real integration verification in Tasks 7, 8, 9, 10.
- Task 4 and Task 5 block Task 9 and contribute fixtures to Task 6/7.
- Task 6 blocks Task 7.
- Task 7 blocks Task 8, Task 10, Task 11.
- Task 8 blocks semantic portions of Task 10 and Task 11.
- Task 9 blocks final ingestion-runtime acceptance.
- Task 10 and Task 11 can run in parallel after Tasks 7-8.
- Task 12 can run after Tasks 2, 4, 5, 10, 11.
- Task 13 runs after Tasks 1-12.

### Agent Dispatch Summary (wave → task count → categories)
- Wave 1 → 3 tasks → `deep`, `quick`, `unspecified-high`
- Wave 2 → 3 tasks → `deep`, `quick`
- Wave 3 → 3 tasks → `deep`, `unspecified-high`
- Wave 4 → 3 tasks → `quick`, `unspecified-high`
- Wave 5 → 1 task → `unspecified-high`

## TODOs
> Implementation + Test = ONE task. Never separate.
> EVERY task MUST have: Agent Profile + Parallelization + QA Scenarios.

- [x] 1. Define Intelligence Domain Schema, Migrations, and Repository Contracts

  **What to do**: Add the intelligence domain foundation before any collector logic. Create Postgres migration(s) following `migrations/postgresql/001_init.sql` and `002_datasource_schema.sql` style with `IF NOT EXISTS` guards. Add domain/repository contracts and storage implementations for: raw source items, extraction observations, canonical knowledge entries, aliases, related candidates, crawl checkpoints, embeddings metadata, and TTL cleanup status. Canonical entry fields must include `entry_type` (`channel` or `slang`), `normalized_key`, `display_name`, `explanation`, `usage_summary` for slang, `primary_label`, `secondary_tags`, `confidence`, `first_seen_at`, `last_seen_at`, `evidence_count`, `latest_raw_item_id`, `prompt_version`, `model_name`, `schema_version`, and timestamps. Slang observations must include `term`, `normalized_term`, `literal_meaning`, `contextual_meaning`, `usage_quote`, `aliases_or_variants`, and `detected_language`. Raw item rows must include `source_type`, `source_id`, `external_id`, `source_url`, `chat_id/thread_id/topic_id` metadata where applicable, `raw_text` unchanged, `published_at`, `collected_at`, `expires_at`, `content_hash`, and source edit/delete metadata if available.
  **Must NOT do**: Do not store Telethon sessions, V2EX PATs, API keys, or private credentials in any DB table. Do not add query audit tables. Do not add a third service schema.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: cross-cutting schema/repository contracts and migration invariants.
  - Skills: [] - No special skill required.
  - Omitted: [`git-master`] - No commit requested.

  **Parallelization**: Can Parallel: NO | Wave 1 | Blocks: [4,5,6,7,8,9,10,11,12,13] | Blocked By: []

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `migrations/postgresql/001_init.sql` - pgvector extension, table/index style, backward-compatible guards.
  - Pattern: `migrations/postgresql/002_datasource_schema.sql` - datasource table/tag schema style.
  - Pattern: `crypto_news_analyzer/domain/repositories.py` - repository ABC contracts.
  - Pattern: `crypto_news_analyzer/storage/repositories.py` - SQLite/Postgres implementation split and `RepositoryFactory` routing.
  - Pattern: `crypto_news_analyzer/storage/data_manager.py` - low-level Postgres/SQLite bootstrap and pgvector usage.
  - API/Type: `crypto_news_analyzer/domain/models.py` - dataclass/domain model style.
  - Test: `tests/test_postgres_storage_path.py` - fake psycopg pattern.
  - Test: `tests/test_semantic_search_storage.py` - semantic storage and embedding metadata tests.

  **Acceptance Criteria** (agent-executable only):
  - [ ] `uv run pytest tests/test_intelligence_models.py tests/test_intelligence_repositories.py -v` passes.
  - [ ] `TEST_DATABASE_URL=$TEST_DATABASE_URL uv run pytest tests/integration/test_intelligence_schema.py -v` creates all intelligence tables/indexes on real Postgres with pgvector.
  - [ ] A test asserts DB/API-safe datasource/config payloads never contain `StringSession`, V2EX PAT, or API keys.
  - [ ] A test asserts no query audit table/model/repository was introduced.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Real Postgres schema bootstrap
    Tool: Bash
    Steps: TEST_DATABASE_URL=$TEST_DATABASE_URL uv run pytest tests/integration/test_intelligence_schema.py::test_intelligence_schema_bootstraps_pgvector -v
    Expected: Test passes and verifies table existence, vector columns, uniqueness constraints, and indexes.
    Evidence: .sisyphus/evidence/task-1-schema-pgvector.txt

  Scenario: Secret persistence guard
    Tool: Bash
    Steps: uv run pytest tests/test_intelligence_models.py::test_intelligence_config_rejects_secret_fields -v
    Expected: Test passes and rejects Telethon session/V2EX PAT/API key fields in datasource config payloads.
    Evidence: .sisyphus/evidence/task-1-secret-guard.txt
  ```

  **Commit**: YES | Message: `feat(schema): add intelligence domain storage foundation` | Files: [`migrations/postgresql/*.sql`, `crypto_news_analyzer/domain/models.py`, `crypto_news_analyzer/domain/repositories.py`, `crypto_news_analyzer/storage/repositories.py`, `crypto_news_analyzer/storage/data_manager.py`, `tests/test_intelligence_models.py`, `tests/test_intelligence_repositories.py`, `tests/integration/test_intelligence_schema.py`]

- [x] 2. Add Intelligence Config, Datasource Types, and Validation

  **What to do**: Add an `intelligence_collection` config block and typed config model. Add datasource types `telegram_group` and `v2ex` to the existing DB-first datasource pipeline. Validation must require Telegram source allowlist identifiers (`chat_id` or `username`) and reject any session/auth secrets in datasource payloads. V2EX config must support API version (`v1`/`v2`), node allowlist, optional PAT env var name only, and hourly/backfill settings. Add primary label enum and secondary tag validation. Extraction model config must be independent from existing news analysis but constrained to existing `opencode-go` provider/model registry.
  **Must NOT do**: Do not add DeepSeek provider. Do not add generic HTML crawler config. Do not allow “crawl all joined Telegram chats”.

  **Recommended Agent Profile**:
  - Category: `quick` - Reason: bounded model/config validation changes.
  - Skills: [] - No special skill required.
  - Omitted: [`railway-docs`] - No Railway docs lookup needed.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: [4,5,6,9,12,13] | Blocked By: []

  **References**:
  - Pattern: `crypto_news_analyzer/datasource_payloads.py` - datasource create validation and Telegram inline secret rejection pattern.
  - Pattern: `crypto_news_analyzer/config/manager.py` - JSONC parsing and typed getter conventions.
  - Pattern: `crypto_news_analyzer/models.py` - config dataclass style, especially `SemanticSearchConfig`.
  - Pattern: `crypto_news_analyzer/config/llm_registry.py` - provider/model validation for `opencode-go`.
  - Pattern: `config.jsonc` - top-level config block style.
  - Test: `tests/test_datasource_repository.py` - datasource validation/storage tests.
  - Test: `tests/test_config_file_management_properties.py` - config persistence/property patterns.

  **Acceptance Criteria**:
  - [ ] `uv run pytest tests/test_intelligence_config.py tests/test_intelligence_datasource_payloads.py -v` passes.
  - [ ] Telegram datasource with no explicit `chat_id`/`username` is rejected.
  - [ ] Telegram datasource containing `session`, `string_session`, `password`, `api_hash`, or token-like values is rejected.
  - [ ] V2EX datasource with `crawler_mode=html` or arbitrary CSS selectors is rejected.
  - [ ] Extraction config rejects non-`opencode-go` providers for v1.

  **QA Scenarios**:
  ```
  Scenario: Telegram source allowlist enforced
    Tool: Bash
    Steps: uv run pytest tests/test_intelligence_datasource_payloads.py::test_telegram_datasource_requires_explicit_allowlist -v
    Expected: Missing chat identifier returns validation error; explicit chat_id or username passes.
    Evidence: .sisyphus/evidence/task-2-telegram-allowlist.txt

  Scenario: V2EX official API only
    Tool: Bash
    Steps: uv run pytest tests/test_intelligence_datasource_payloads.py::test_v2ex_rejects_html_crawler_config -v
    Expected: HTML/generic scraping config is rejected; v1/v2 API config is accepted.
    Evidence: .sisyphus/evidence/task-2-v2ex-api-only.txt
  ```

  **Commit**: YES | Message: `feat(config): add intelligence datasource validation` | Files: [`crypto_news_analyzer/models.py`, `crypto_news_analyzer/domain/models.py`, `crypto_news_analyzer/datasource_payloads.py`, `crypto_news_analyzer/config/manager.py`, `config.jsonc`, `tests/test_intelligence_config.py`, `tests/test_intelligence_datasource_payloads.py`]

- [x] 3. Add Real Postgres/pgvector Integration Test Harness

  **What to do**: Add reusable test infrastructure for real Postgres/pgvector integration tests while keeping local test ergonomics. Use `TEST_DATABASE_URL` gating so default `uv run pytest tests/` remains usable without Postgres, and add clear skip behavior when the env var is absent. Add helpers to initialize migrations, truncate intelligence tables, and assert pgvector extension/vector columns. Keep existing fake psycopg tests intact.
  **Must NOT do**: Do not require Docker Compose or Testcontainers for every local unit test run. Do not mutate production DBs; tests must require explicit `TEST_DATABASE_URL` and defensive database-name checks.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: test infrastructure and real DB safety need careful handling.
  - Skills: [] - No special skill required.
  - Omitted: [`crypto-news-debug`] - No production Railway debugging.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: [7,8,9,10,13] | Blocked By: [1]

  **References**:
  - Pattern: `pyproject.toml` - pytest configuration.
  - Pattern: `tests/test_semantic_search_storage.py` - existing pgvector/fake storage expectations.
  - Pattern: `migrations/postgresql/README.md` - migration execution context.
  - Test: `tests/test_postgres_storage_path.py` - Postgres path test style.

  **Acceptance Criteria**:
  - [ ] `uv run pytest tests/integration/test_intelligence_pgvector.py -v` skips cleanly when `TEST_DATABASE_URL` is absent.
  - [ ] `TEST_DATABASE_URL=$TEST_DATABASE_URL uv run pytest tests/integration/test_intelligence_pgvector.py -v` passes against real pgvector Postgres.
  - [ ] `uv run pytest tests/ -v` still runs non-integration tests without requiring Postgres.
  - [ ] A safety test refuses to run integration truncation if database name does not contain `test` or `ci`.

  **QA Scenarios**:
  ```
  Scenario: Integration tests skip without DB
    Tool: Bash
    Steps: unset TEST_DATABASE_URL; uv run pytest tests/integration/test_intelligence_pgvector.py -v
    Expected: Tests are skipped with an explicit TEST_DATABASE_URL message, not failed.
    Evidence: .sisyphus/evidence/task-3-pg-skip.txt

  Scenario: Real pgvector path works
    Tool: Bash
    Steps: TEST_DATABASE_URL=$TEST_DATABASE_URL uv run pytest tests/integration/test_intelligence_pgvector.py -v
    Expected: Tests pass and verify vector insert/search/upsert behavior.
    Evidence: .sisyphus/evidence/task-3-pgvector-real.txt
  ```

  **Commit**: YES | Message: `test(pgvector): add intelligence integration harness` | Files: [`tests/conftest.py`, `tests/integration/test_intelligence_pgvector.py`, `pyproject.toml`]

- [x] 4. Implement Allowlisted Telethon Telegram Collector

  **What to do**: Add a Telegram collector implementing the existing `DataSourceInterface` pattern. It must read only the explicitly configured chat ID/username, use env-only Telethon credentials/session (`TELEGRAM_API_ID`, `TELEGRAM_API_HASH`, `TELEGRAM_STRING_SESSION` or names chosen consistently), support last-24-hour backfill on first run, store per-source checkpoints, and handle hourly incremental fetches. It must catch FloodWait/rate errors, log safe metadata only, and return normalized raw intelligence items without mutating raw text. Tests must mock Telethon client and verify no all-chat enumeration calls are made.
  **Must NOT do**: Do not call APIs that list all dialogs/chats for crawling. Do not persist session material. Do not auto-join chats. Do not scrape Telegram via browser.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: async client integration, checkpointing, secrets, and rate-limit edge cases.
  - Skills: [] - No special skill required.
  - Omitted: [`bird-commands-reference`] - Not using Bird/X CLI.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: [9,13] | Blocked By: [1,2]

  **References**:
  - Pattern: `crypto_news_analyzer/crawlers/data_source_interface.py` - crawler contract and exceptions.
  - Pattern: `crypto_news_analyzer/crawlers/data_source_factory.py` - source registration.
  - Pattern: `crypto_news_analyzer/crawlers/x_crawler_adapter.py` - adapter-style crawler integration.
  - Pattern: `crypto_news_analyzer/execution_coordinator.py` - ingestion crawl orchestration and `IngestionJob` lifecycle.
  - External: Telethon docs - MTProto user client, sessions, FloodWait handling.
  - Test: `tests/test_rss_crawler.py` and `tests/test_bird_integration_properties.py` - crawler mocking/property patterns.

  **Acceptance Criteria**:
  - [ ] `uv run pytest tests/test_intelligence_telegram_collector.py -v` passes.
  - [ ] Test verifies collector fetches messages only from configured chat identifier.
  - [ ] Test verifies first run uses 24-hour cutoff; second run uses checkpoint.
  - [ ] Test verifies FloodWait results in safe retry/backoff status, not leaked session/log content.
  - [ ] Test verifies returned raw text equals fixture text exactly.

  **QA Scenarios**:
  ```
  Scenario: Allowlisted chat only
    Tool: Bash
    Steps: uv run pytest tests/test_intelligence_telegram_collector.py::test_collector_never_enumerates_all_joined_chats -v
    Expected: Mock Telethon client records no dialog enumeration and fetches only configured chat.
    Evidence: .sisyphus/evidence/task-4-telegram-allowlist.txt

  Scenario: FloodWait handled safely
    Tool: Bash
    Steps: uv run pytest tests/test_intelligence_telegram_collector.py::test_floodwait_does_not_persist_or_log_session_secret -v
    Expected: Error path stores safe status/checkpoint only; no secret appears in captured logs or rows.
    Evidence: .sisyphus/evidence/task-4-telegram-floodwait.txt
  ```

  **Commit**: YES | Message: `feat(collector): add allowlisted telegram intelligence source` | Files: [`crypto_news_analyzer/crawlers/telegram_intelligence_crawler.py`, `crypto_news_analyzer/crawlers/data_source_factory.py`, `crypto_news_analyzer/models.py`, `tests/test_intelligence_telegram_collector.py`]

- [x] 5. Implement V2EX Official API Collector

  **What to do**: Add a V2EX collector implementing `DataSourceInterface`. Support v1 public endpoints and v2 authenticated API via PAT env var name only. Support configured node allowlist, latest/hot/topic replies where API permits, rate-limit header handling, 24-hour initial backfill, checkpoints, and official API pagination. Normalize topics/replies into raw intelligence items with exact original content fields preserved. Store source URLs and external IDs for dedupe.
  **Must NOT do**: Do not implement generic HTML scraping, CSS selector parsing, browser automation, proxy rotation, or content mirroring beyond raw 30-day TTL storage.

  **Recommended Agent Profile**:
  - Category: `quick` - Reason: bounded HTTP API collector with mocked responses.
  - Skills: [] - No special skill required.
  - Omitted: [`playwright`] - No browser/HTML scraping allowed.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: [9,13] | Blocked By: [1,2]

  **References**:
  - Pattern: `crypto_news_analyzer/crawlers/rest_api_crawler.py` - HTTP fetch/response mapping conventions.
  - Pattern: `crypto_news_analyzer/crawlers/rss_crawler_adapter.py` - adapter contract.
  - Pattern: `crypto_news_analyzer/crawlers/data_source_interface.py` - crawler exceptions.
  - External: V2EX official API v1/v2 docs - rate limits and endpoints.
  - Test: `tests/test_rss_crawler.py` - network mocking style.

  **Acceptance Criteria**:
  - [ ] `uv run pytest tests/test_intelligence_v2ex_collector.py -v` passes.
  - [ ] Test verifies v1/v2 endpoint URLs are official API endpoints only.
  - [ ] Test verifies `X-Rate-Limit-Remaining` and reset headers influence collector status/backoff.
  - [ ] Test verifies raw topic/reply content equals fixture strings exactly.
  - [ ] Test verifies V2EX PAT value is read from env at runtime and never returned in config summaries.

  **QA Scenarios**:
  ```
  Scenario: V2EX API-only collection
    Tool: Bash
    Steps: uv run pytest tests/test_intelligence_v2ex_collector.py::test_v2ex_collector_uses_official_api_only -v
    Expected: Mock HTTP client sees only `/api/` or `/api/v2/` URLs; no HTML page URL is requested.
    Evidence: .sisyphus/evidence/task-5-v2ex-api-only.txt

  Scenario: V2EX rate limit backoff
    Tool: Bash
    Steps: uv run pytest tests/test_intelligence_v2ex_collector.py::test_v2ex_rate_limit_headers_update_checkpoint_status -v
    Expected: Remaining quota exhaustion records safe retry-after/checkpoint status without failing whole ingestion.
    Evidence: .sisyphus/evidence/task-5-v2ex-rate-limit.txt
  ```

  **Commit**: YES | Message: `feat(collector): add v2ex intelligence source` | Files: [`crypto_news_analyzer/crawlers/v2ex_intelligence_crawler.py`, `crypto_news_analyzer/crawlers/data_source_factory.py`, `tests/test_intelligence_v2ex_collector.py`]

- [x] 6. Add Structured Intelligence Extraction Pipeline

  **What to do**: Add a focused extractor that uses existing structured-output patterns to convert raw items into extraction observations for channel info and slang. Add prompt file, Pydantic structured result schema, prompt/model/schema version constants, confidence fields, primary label enum validation, secondary tag normalization, and batching. Configure extraction model independently under `intelligence_collection.extraction` but use existing `opencode-go` provider validation. Store observations append-first even when below canonical exposure threshold.
  **Must NOT do**: Do not reuse market/news analysis prompt. Do not add DeepSeek provider. Do not call semantic merge logic here. Do not promote private keys/tokens/passwords to canonical channel entries.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: structured LLM schema, confidence, versioning, and sensitive extraction boundaries.
  - Skills: [`llm-instructor`] - Structured output/instructor usage matches existing analyzer stack.
  - Omitted: [`grok-api-reference`] - opencode-go config is already in project registry.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: [7,13] | Blocked By: [1,2]

  **References**:
  - Pattern: `crypto_news_analyzer/analyzers/structured_output_manager.py` - instructor wrapper and retry style.
  - Pattern: `crypto_news_analyzer/analyzers/llm_analyzer.py` - batch analyzer and model runtime patterns.
  - Pattern: `crypto_news_analyzer/config/llm_registry.py` - provider/model validation.
  - Pattern: `prompts/analysis_prompt.md` - prompt file conventions.
  - Test: `tests/test_llm_analyzer.py` - LLM mocking pattern.

  **Acceptance Criteria**:
  - [ ] `uv run pytest tests/test_intelligence_extraction.py -v` passes.
  - [ ] Test verifies fixture text containing “GPT Plus 土区礼品卡渠道 @seller” produces channel and slang observations with primary label `AI` or `账号交易` as configured by fixture expectation.
  - [ ] Test verifies “币圈担保”, “土区礼品卡”, “会员质保”, and “手搓cdk” fixtures produce `entry_type=slang` observations with contextual meanings and usage quotes.
  - [ ] Test verifies prompt/model/schema versions are persisted with every observation.
  - [ ] Test verifies low-confidence observations are stored but not automatically canonicalized.
  - [ ] Test verifies secrets/private keys/tokens are not promoted into canonical candidate fields.

  **QA Scenarios**:
  ```
  Scenario: Structured extraction happy path
    Tool: Bash
    Steps: uv run pytest tests/test_intelligence_extraction.py::test_extracts_channel_and_slang_observations_from_fixture -v
    Expected: Extractor returns typed observations with confidence, labels, source raw_item_id, prompt_version, model_name, schema_version.
    Evidence: .sisyphus/evidence/task-6-extraction-happy.txt

  Scenario: Sensitive token not canonicalized
    Tool: Bash
    Steps: uv run pytest tests/test_intelligence_extraction.py::test_private_token_is_not_promoted_to_channel_info -v
    Expected: Observation either omits secret-like value or marks it non-canonical; no canonical key is generated from token/private key text.
    Evidence: .sisyphus/evidence/task-6-sensitive-boundary.txt
  ```

  **Commit**: YES | Message: `feat(extractor): add structured intelligence extraction` | Files: [`crypto_news_analyzer/analyzers/intelligence_extractor.py`, `crypto_news_analyzer/analyzers/structured_output_manager.py`, `prompts/intelligence_extraction_prompt.md`, `crypto_news_analyzer/models.py`, `tests/test_intelligence_extraction.py`]

- [x] 7. Implement Conservative Merge/Update and Related Candidate Logic

  **What to do**: Implement canonicalization and merge rules. Normalize URLs/domains, Telegram usernames, invite links, and slang terms. Exact normalized key match updates existing canonical entry (`last_seen_at`, `evidence_count`, aliases, confidence aggregation, latest evidence). Non-exact semantic/textual similarity creates `related_candidate` links only and must never mutate canonical entry identity. Add low-confidence threshold behavior: observations below configured threshold remain observations unless repeated evidence crosses threshold.
  **Must NOT do**: Do not merge by embedding similarity alone. Do not let LLM decide identity merges. Do not delete canonical knowledge when raw TTL purges evidence.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: data correctness and irreversible merge corruption risk.
  - Skills: [] - No special skill required.
  - Omitted: [`ai-slop-remover`] - Not a cleanup-only task.

  **Parallelization**: Can Parallel: NO | Wave 3 | Blocks: [8,10,11,13] | Blocked By: [1,3,6]

  **References**:
  - Pattern: `crypto_news_analyzer/storage/cache_manager.py` - dedupe/cache expiration thinking.
  - Pattern: `crypto_news_analyzer/storage/repositories.py` - upsert and repository implementation style.
  - Pattern: `crypto_news_analyzer/domain/repositories.py` - interface contracts.
  - Test: `tests/test_data_storage_properties.py` - property-based storage correctness style.
  - Test: `tests/test_datasource_repository.py` - duplicate/race-condition tests.

  **Acceptance Criteria**:
  - [ ] `uv run pytest tests/test_intelligence_merge.py -v` passes.
  - [ ] `TEST_DATABASE_URL=$TEST_DATABASE_URL uv run pytest tests/integration/test_intelligence_pgvector.py::test_exact_identifier_merge_and_related_candidate_separation -v` passes.
  - [ ] Exact same normalized URL/domain/TG username/invite/slang term merges into one canonical entry.
  - [ ] Exact same normalized slang term updates canonical slang `usage_summary`, aliases, evidence_count, and last_seen_at without creating a duplicate.
  - [ ] Similar wording with different identifier creates related candidate and keeps canonical entries separate.
  - [ ] Raw TTL purge does not delete canonical entries.

  **QA Scenarios**:
  ```
  Scenario: Exact identifier merges
    Tool: Bash
    Steps: uv run pytest tests/test_intelligence_merge.py::test_exact_telegram_username_updates_existing_canonical_entry -v
    Expected: One canonical entry remains; evidence_count increments; last_seen_at updates.
    Evidence: .sisyphus/evidence/task-7-exact-merge.txt

  Scenario: Semantic similarity does not merge
    Tool: Bash
    Steps: uv run pytest tests/test_intelligence_merge.py::test_semantic_similarity_creates_related_candidate_not_merge -v
    Expected: Two canonical entries remain and one related_candidate row links them.
    Evidence: .sisyphus/evidence/task-7-related-only.txt
  ```

  **Commit**: YES | Message: `feat(intelligence): add conservative merge engine` | Files: [`crypto_news_analyzer/intelligence/merge.py`, `crypto_news_analyzer/storage/repositories.py`, `tests/test_intelligence_merge.py`, `tests/integration/test_intelligence_pgvector.py`]

- [x] 8. Add Embedding and Semantic Retrieval for Intelligence Entries

  **What to do**: Reuse existing `EmbeddingService` to generate embeddings for canonical entry searchable text and optionally raw TTL-window evidence text. For slang entries, embedding text must concatenate term, explanation, usage summary, aliases, primary label, and secondary tags. Add repository methods for semantic search filtered by time window, primary label, secondary tag, source type, entry type, and raw availability. Ranking must combine vector distance with recency and confidence in a deterministic way documented in code comments/tests. Keep embedding model metadata per row for future backfills.
  **Must NOT do**: Do not introduce a new embedding provider. Do not call existing `/semantic-search` async job flow for these synchronous APIs. Do not embed expired raw text after TTL purge.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: pgvector retrieval and ranking require careful SQL/testing.
  - Skills: [] - No special skill required.
  - Omitted: [`llm-instructor`] - No LLM structured output in this task.

  **Parallelization**: Can Parallel: NO | Wave 3 | Blocks: [10,11,13] | Blocked By: [1,3,7]

  **References**:
  - Pattern: `crypto_news_analyzer/semantic_search/embedding_service.py` - embedding generation and metadata.
  - Pattern: `crypto_news_analyzer/semantic_search/service.py` - semantic retrieval concepts.
  - Pattern: `crypto_news_analyzer/storage/data_manager.py` - pgvector `<->` search and keyword fallback.
  - Pattern: `crypto_news_analyzer/models.py` - `SemanticSearchConfig` embedding dimensions.
  - Test: `tests/test_embedding_service.py` - fake OpenAI client.
  - Test: `tests/test_semantic_search_storage.py` - semantic storage tests.

  **Acceptance Criteria**:
  - [ ] `uv run pytest tests/test_intelligence_semantic_search.py -v` passes.
  - [ ] `TEST_DATABASE_URL=$TEST_DATABASE_URL uv run pytest tests/integration/test_intelligence_pgvector.py::test_intelligence_semantic_search_returns_expected_entry -v` passes.
  - [ ] Semantic query “GPT plus购买渠道” returns fixture entry for GPT Plus/TG seller evidence.
  - [ ] Time filter `window=7d` excludes older canonical entries by `last_seen_at` while preserving raw TTL behavior separately.
  - [ ] Embedding metadata includes model name and update timestamp.

  **QA Scenarios**:
  ```
  Scenario: Semantic query finds GPT Plus channel
    Tool: Bash
    Steps: TEST_DATABASE_URL=$TEST_DATABASE_URL uv run pytest tests/integration/test_intelligence_pgvector.py::test_query_gpt_plus_purchase_channel_returns_fixture -v
    Expected: Top result normalized_key matches fixture canonical entry and includes vector distance/confidence fields.
    Evidence: .sisyphus/evidence/task-8-semantic-gpt-plus.txt

  Scenario: Expired raw text is not embedded as raw evidence
    Tool: Bash
    Steps: uv run pytest tests/test_intelligence_semantic_search.py::test_expired_raw_item_not_used_for_raw_evidence_embedding -v
    Expected: Search can return canonical entry but raw evidence text is absent after TTL purge.
    Evidence: .sisyphus/evidence/task-8-expired-raw-embedding.txt
  ```

  **Commit**: YES | Message: `feat(search): add intelligence semantic retrieval` | Files: [`crypto_news_analyzer/intelligence/search.py`, `crypto_news_analyzer/storage/repositories.py`, `crypto_news_analyzer/semantic_search/embedding_service.py`, `tests/test_intelligence_semantic_search.py`, `tests/integration/test_intelligence_pgvector.py`]

- [x] 9. Orchestrate Hourly Intelligence Ingestion and 30-Day Raw TTL Cleanup

  **What to do**: Integrate collectors, raw persistence, extraction, merge/update, embedding generation, checkpoint updates, and raw TTL purge into `ingestion` runtime without adding a new service. Add a deterministic `run_intelligence_collection_once()` style orchestration path that the existing scheduler can call hourly. First run per source backfills only last 24 hours; later runs use checkpoints. TTL cleanup must delete or null raw text older than 30 days while retaining canonical knowledge, observations, and provenance metadata that does not contain raw text.
  **Must NOT do**: Do not start intelligence ingestion from `analysis-service`. Do not delete canonical entries when raw expires. Do not add query audit during orchestration.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: runtime orchestration, idempotency, error isolation, TTL correctness.
  - Skills: [] - No special skill required.
  - Omitted: [`crypto-news-debug`] - No production debugging.

  **Parallelization**: Can Parallel: NO | Wave 3 | Blocks: [10,11,13] | Blocked By: [1,2,4,5,6,7,8]

  **References**:
  - Pattern: `crypto_news_analyzer/execution_coordinator.py` - `start_scheduler()`, `_scheduler_loop()`, `run_crawl_only()`, `IngestionJob` lifecycle.
  - Pattern: `crypto_news_analyzer/main.py` - runtime mode dispatch and mode isolation.
  - Pattern: `crypto_news_analyzer/storage/data_manager.py` - persistence and embedding worker integration.
  - Test: `tests/test_ingestion_runtime.py` - runtime mode tests.
  - Test: `tests/test_main_controller.py` - controller/integration patterns.

  **Acceptance Criteria**:
  - [ ] `uv run pytest tests/test_intelligence_ingestion_runtime.py tests/test_intelligence_ttl.py -v` passes.
  - [ ] First source run uses 24-hour cutoff; subsequent run uses stored checkpoint.
  - [ ] Collector failure for one source records failure and does not abort all sources.
  - [ ] Raw text older than 30 days is purged/nullified; canonical entry remains queryable.
  - [ ] `analysis-service` mode test verifies intelligence ingestion does not start there.

  **QA Scenarios**:
  ```
  Scenario: Hourly orchestration is idempotent
    Tool: Bash
    Steps: uv run pytest tests/test_intelligence_ingestion_runtime.py::test_repeated_hourly_run_dedupes_and_updates_checkpoint -v
    Expected: Second run inserts no duplicate raw items and advances checkpoint only once.
    Evidence: .sisyphus/evidence/task-9-hourly-idempotent.txt

  Scenario: 30-day raw TTL preserves canonical knowledge
    Tool: Bash
    Steps: uv run pytest tests/test_intelligence_ttl.py::test_raw_text_expires_after_30_days_but_canonical_entry_remains -v
    Expected: raw_text unavailable after cleanup; canonical entry and metadata remain.
    Evidence: .sisyphus/evidence/task-9-ttl-retention.txt
  ```

  **Commit**: YES | Message: `feat(ingestion): orchestrate intelligence collection` | Files: [`crypto_news_analyzer/execution_coordinator.py`, `crypto_news_analyzer/main.py`, `crypto_news_analyzer/intelligence/pipeline.py`, `tests/test_intelligence_ingestion_runtime.py`, `tests/test_intelligence_ttl.py`]

- [x] 10. Add Synchronous Bearer-Protected HTTP Query APIs

  **What to do**: Add synchronous FastAPI endpoints in `analysis-service`/`api-only` app for intelligence querying. Required endpoints: recent/list query, semantic search query, entry detail, and raw evidence retrieval through the same authenticated surface. Use query params for `window` (e.g. `7d`), `entry_type`, `primary_label`, `secondary_tag`, `source_type`, `q`, `semantic`, `include_raw`, `include_low_confidence`, `page`, `page_size`. Return raw text exactly when `include_raw=true` and raw evidence is still within TTL; return `raw_text: null` or omit raw field after TTL with `raw_available=false`. Unauthorized requests return 401.
  **Must NOT do**: Do not implement async job/poll/result for v1 intelligence query. Do not add public routes. Do not add query audit. Do not redact raw text.

  **Recommended Agent Profile**:
  - Category: `quick` - Reason: follows existing FastAPI route/auth patterns.
  - Skills: [] - No special skill required.
  - Omitted: [`playwright`] - API tests do not require browser.

  **Parallelization**: Can Parallel: YES | Wave 4 | Blocks: [12,13] | Blocked By: [1,7,8,9]

  **References**:
  - Pattern: `crypto_news_analyzer/api_server.py` - FastAPI app, `HTTPBearer`, Pydantic request/response models, status codes.
  - Pattern: `docs/AI_ANALYZE_API_GUIDE.md` - API contract documentation style.
  - Test: `tests/test_api_server.py` - FastAPI TestClient/auth/job response tests.
  - Test: `tests/test_api_server_semantic_search.py` - semantic API test patterns.

  **Acceptance Criteria**:
  - [ ] `uv run pytest tests/test_intelligence_api.py -v` passes.
  - [ ] `GET /intelligence/items?window=7d&page=1&page_size=20` with Bearer returns 200 and time-desc entries.
  - [ ] Same request without Bearer returns 401.
  - [ ] `GET /intelligence/search?q=GPT%20plus%E8%B4%AD%E4%B9%B0%E6%B8%A0%E9%81%93&semantic=true&window=7d` returns fixture semantic result.
  - [ ] `include_raw=true` returns fixture raw text exactly while TTL-valid; expired raw evidence returns `raw_available=false`.

  **QA Scenarios**:
  ```
  Scenario: Authenticated recency API
    Tool: Bash
    Steps: uv run pytest tests/test_intelligence_api.py::test_list_recent_intelligence_requires_bearer_and_returns_time_desc -v
    Expected: Authorized request returns 200 sorted by last_seen_at desc; unauthorized request returns 401.
    Evidence: .sisyphus/evidence/task-10-api-list.txt

  Scenario: Raw text exact return within TTL
    Tool: Bash
    Steps: uv run pytest tests/test_intelligence_api.py::test_include_raw_returns_original_text_exactly_within_ttl -v
    Expected: Response raw_text equals fixture string exactly, including punctuation/spacing/newlines.
    Evidence: .sisyphus/evidence/task-10-api-raw-exact.txt
  ```

  **Commit**: YES | Message: `feat(api): add intelligence query endpoints` | Files: [`crypto_news_analyzer/api_server.py`, `crypto_news_analyzer/intelligence/search.py`, `tests/test_intelligence_api.py`]

- [x] 11. Add Authorized Telegram Intelligence Query Commands

  **What to do**: Add Telegram command handlers for authorized users to query recent intelligence and semantic search from `analysis-service`. Required commands: `/intel_recent [window] [label]`, `/intel_search <query>`, `/intel_detail <entry_id>`, and an explicit raw option such as `/intel_detail <entry_id> raw` if matching current command style. Respect existing authorized-user checks and command rate limits. Format responses with entry type, title/term, explanation, labels, confidence, last seen, source count, and raw text only when requested and TTL-valid.
  **Must NOT do**: Do not allow unauthorized Telegram users to query. Do not add query audit. Do not redact raw text when raw output is requested and TTL-valid. Do not send overly long messages without existing Telegram splitting/formatting safeguards.

  **Recommended Agent Profile**:
  - Category: `quick` - Reason: follows existing Telegram command handler patterns.
  - Skills: [] - No special skill required.
  - Omitted: [`bird-commands-reference`] - Not reading X/Twitter.

  **Parallelization**: Can Parallel: YES | Wave 4 | Blocks: [12,13] | Blocked By: [1,7,8,9]

  **References**:
  - Pattern: `crypto_news_analyzer/reporters/telegram_command_handler.py` - authorized commands and formatting.
  - Pattern: `README.md` - Telegram command documentation style.
  - Test: `tests/test_telegram_command_handler_semantic_search.py` - semantic command tests.
  - Test: `tests/test_telegram_command_handler_datasource.py` - datasource command auth tests.
  - Test: `tests/test_telegram_command_pbt.py` - property-based command safety tests.

  **Acceptance Criteria**:
  - [ ] `uv run pytest tests/test_intelligence_telegram_commands.py -v` passes.
  - [ ] Authorized `/intel_search GPT plus购买渠道` returns ranked entries from repository fixture.
  - [ ] Unauthorized user receives denial response and no repository query executes.
  - [ ] Raw detail command returns raw fixture text exactly when TTL-valid.
  - [ ] Expired raw evidence returns a clear “raw evidence expired” message while still showing structured entry.

  **QA Scenarios**:
  ```
  Scenario: Authorized Telegram semantic query
    Tool: Bash
    Steps: uv run pytest tests/test_intelligence_telegram_commands.py::test_authorized_intel_search_returns_ranked_entries -v
    Expected: Response contains fixture display_name, explanation, label, confidence, and source count.
    Evidence: .sisyphus/evidence/task-11-telegram-search.txt

  Scenario: Unauthorized Telegram denial
    Tool: Bash
    Steps: uv run pytest tests/test_intelligence_telegram_commands.py::test_unauthorized_intel_command_does_not_query_repository -v
    Expected: Unauthorized response is sent and fake repository records zero search calls.
    Evidence: .sisyphus/evidence/task-11-telegram-unauthorized.txt
  ```

  **Commit**: YES | Message: `feat(telegram): add intelligence query commands` | Files: [`crypto_news_analyzer/reporters/telegram_command_handler.py`, `tests/test_intelligence_telegram_commands.py`, `README.md`]

- [x] 12. Enforce Secrets, Access, and No-Audit Guardrails End-to-End

  **What to do**: Add cross-cutting tests and code guards ensuring secrets are env-only, config summaries redact auth hints, logs do not include session/PAT/API key values, all HTTP endpoints use existing Bearer auth, Telegram commands use existing authorized-user checks, and no query audit implementation exists. Add static-ish tests that scan new intelligence config/API responses for prohibited secret fields and audit artifacts. Keep raw text original by design while preventing accidental persistence of session secrets.
  **Must NOT do**: Do not add audit logs/events/tables. Do not add redaction of returned raw source text. Do not expose raw text through unauthenticated paths.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: security regression guardrails across config/API/logging/tests.
  - Skills: [] - No special skill required.
  - Omitted: [`crypto-news-debug`] - No production access needed.

  **Parallelization**: Can Parallel: YES | Wave 4 | Blocks: [13] | Blocked By: [2,4,5,10,11]

  **References**:
  - Pattern: `crypto_news_analyzer/datasource_payloads.py` - Telegram inline secret rejection tokens.
  - Pattern: `crypto_news_analyzer/api_server.py` - `verify_api_key()` dependency.
  - Pattern: `crypto_news_analyzer/reporters/telegram_command_handler.py` - authorized Telegram users.
  - Test: `tests/helpers/` - existing helper scan style.
  - Test: `tests/test_api_server.py` - unauthorized API checks.

  **Acceptance Criteria**:
  - [ ] `uv run pytest tests/test_intelligence_security_guardrails.py -v` passes.
  - [ ] Test verifies all intelligence HTTP routes require Bearer auth.
  - [ ] Test verifies Telegram intelligence commands reject unauthorized users.
  - [ ] Test verifies datasource config/API summaries never include session/PAT/API secret values.
  - [ ] Test verifies no new audit repository/table/model/route is present for intelligence queries.

  **QA Scenarios**:
  ```
  Scenario: No secret persistence or exposure
    Tool: Bash
    Steps: uv run pytest tests/test_intelligence_security_guardrails.py::test_intelligence_configs_and_api_summaries_do_not_expose_secrets -v
    Expected: Sentinel secret strings are absent from DB-safe payloads, API summaries, and captured logs.
    Evidence: .sisyphus/evidence/task-12-no-secret-exposure.txt

  Scenario: No query audit implementation
    Tool: Bash
    Steps: uv run pytest tests/test_intelligence_security_guardrails.py::test_no_intelligence_query_audit_artifacts_exist -v
    Expected: Test finds no audit table/model/repository/route names for intelligence query logging.
    Evidence: .sisyphus/evidence/task-12-no-audit.txt
  ```

  **Commit**: YES | Message: `test(security): enforce intelligence guardrails` | Files: [`crypto_news_analyzer/datasource_payloads.py`, `crypto_news_analyzer/api_server.py`, `crypto_news_analyzer/reporters/telegram_command_handler.py`, `tests/test_intelligence_security_guardrails.py`]

- [x] 13. Final Integration Hardening, Config Examples, and Regression Sweep

  **What to do**: Add final wiring, docs/config examples, and regression coverage after all feature tasks. Update `.env.template` with Telethon env var names, V2EX PAT env var convention, and opencode-go extraction config notes without real secrets. Update README command/API lists only if needed. Run full regression commands. Ensure existing `analysis-service`, `api-only`, and `ingestion` modes still behave as documented. Add any missing fixture tests discovered by integration sweep.
  **Must NOT do**: Do not include real session strings, tokens, private group names, or sensitive source examples. Do not document legacy API-server as primary. Do not add public product language.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: broad regression, docs/config consistency, and final wiring.
  - Skills: [] - No special skill required.
  - Omitted: [`railway-docs`] - Not changing Railway behavior beyond env vars.

  **Parallelization**: Can Parallel: NO | Wave 5 | Blocks: [F1,F2,F3,F4] | Blocked By: [1,2,3,4,5,6,7,8,9,10,11,12]

  **References**:
  - Pattern: `.env.template` - environment variable documentation.
  - Pattern: `README.md` - feature/API/Telegram command documentation style.
  - Pattern: `AGENTS.md` - required commands and runtime notes.
  - Pattern: `docs/AI_ANALYZE_API_GUIDE.md` - API guide style if a short intelligence API section is added.
  - Test: `tests/test_ingestion_runtime.py` and `tests/test_api_server.py` - runtime regression checks.

  **Acceptance Criteria**:
  - [ ] `uv run pytest tests/ -v` passes.
  - [ ] `uv run mypy crypto_news_analyzer/` passes.
  - [ ] `uv run flake8 crypto_news_analyzer/` passes.
  - [ ] `TEST_DATABASE_URL=$TEST_DATABASE_URL uv run pytest tests/integration/test_intelligence_pgvector.py -v` passes.
  - [ ] `.env.template` documents placeholder-only Telethon/V2EX/opencode-go extraction env vars with no real secrets.

  **QA Scenarios**:
  ```
  Scenario: Full local regression
    Tool: Bash
    Steps: uv run pytest tests/ -v && uv run mypy crypto_news_analyzer/ && uv run flake8 crypto_news_analyzer/
    Expected: All commands complete successfully with zero failures.
    Evidence: .sisyphus/evidence/task-13-full-regression.txt

  Scenario: Config examples contain no real secrets
    Tool: Bash
    Steps: uv run pytest tests/test_intelligence_security_guardrails.py::test_env_template_contains_placeholders_only -v
    Expected: Template contains only placeholder values and documented env var names.
    Evidence: .sisyphus/evidence/task-13-env-template.txt
  ```

  **Commit**: YES | Message: `chore(intelligence): finalize config and regression coverage` | Files: [`.env.template`, `README.md`, `docs/AI_ANALYZE_API_GUIDE.md`, `tests/test_intelligence_security_guardrails.py`]

## Final Verification Wave (MANDATORY — after ALL implementation tasks)
> 4 review agents run in PARALLEL. ALL must APPROVE. Present consolidated results to user and get explicit "okay" before completing.
> **Do NOT auto-proceed after verification. Wait for user's explicit approval before marking work complete.**
> **Never mark F1-F4 as checked before getting user's okay.** Rejection or user feedback -> fix -> re-run -> present again -> wait for okay.
- [x] F1. Plan Compliance Audit — oracle
- [x] F2. Code Quality Review — unspecified-high
- [x] F3. Real Manual QA — unspecified-high (+ playwright if UI)
- [x] F4. Scope Fidelity Check — deep

## Commit Strategy
- Make atomic commits per completed task when requested by the user during execution.
- Suggested commit scopes: `schema`, `config`, `collector`, `extractor`, `merge`, `search`, `api`, `telegram`, `tests`.
- Do not commit secrets, session strings, `.env`, generated Telethon session files, or test database dumps.

## Success Criteria
- Hourly ingestion can collect from explicitly allowlisted Telegram chats and V2EX official API fixtures, dedupe raw items, extract intelligence observations, merge exact canonical matches, embed canonical entries, and purge raw text older than 30 days.
- Analysis-service can synchronously return recent entries, semantic search results, and raw TTL-window evidence through Bearer HTTP API and authorized Telegram commands.
- Real Postgres/pgvector integration tests verify schema, upsert, vector search, and TTL behavior.
- No new third service, generic HTML crawler, query audit, public API, secret persistence, or semantic auto-merge is introduced.
