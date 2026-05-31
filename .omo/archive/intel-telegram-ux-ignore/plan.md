# Optimize Telegram Intel UX with Global Ignore

## TL;DR
> **Summary**: Add inline `详情` / `忽略` actions to Telegram intelligence result lists, backed by a global database ignore state that hides ignored entries from discovery surfaces while preserving exact detail lookup. Include recovery via Telegram and HTTP, plus ingestion safeguards so ignored canonical entries are not mutated or duplicated.
> **Deliverables**:
> - Inline Telegram buttons for `/intel_recent` and `/intel_search`
> - Previous/next pagination buttons for paginated Telegram intel commands
> - Global canonical-entry ignore/unignore persistence
> - Authenticated HTTP ignore/unignore and ignored-list endpoints
> - Default filtering of ignored entries from Telegram/API list, labels, and search
> - Ingestion/merge guard for ignored canonical entries
> - TDD coverage for repository, API, Telegram callbacks, and ingestion behavior
> **Effort**: Large
> **Parallel**: YES - 3 waves
> **Critical Path**: Task 1 → Tasks 2/3/4/6 → Task 5 → Final Verification

## Context
### Original Request
User requested Telegram `/intel` UX improvements. Current row format shows a raw ID:
`1. 土区直充 | ID: a98d3e93-da25-44eb-9479-fc41d216f22f | 类型: slang | 标签: 支付 | 置信度: 0.85`.

Desired row format:
`1. 土区直充 | [详情 button] | [忽略 button] | slang | 支付 | 0.85`, with summary text still shown underneath. `详情` should behave like `/intel_detail`; `忽略` should persist a database mark so future query/search commands and interfaces hide the entry, and ingestion stops updating it.

### Interview Summary
- Add inline buttons to both `/intel_recent` and `/intel_search`.
- Add pagination buttons to paginated Telegram intel commands: `/intel_recent`, `/intel_search`, and planned `/intel_ignored`.
- Ignore is global, not per Telegram user.
- Add recovery capability: Telegram ignored list + unignore, and HTTP ignored list + unignore.
- Add Bearer-protected HTTP write endpoints.
- Exact detail lookup remains available for ignored entries via `/intel_detail <id>` and `GET /intelligence/entries/{entry_id}`.
- Use TDD.
- Defaults applied from Metis: unignored entries resume only from future ingestion; no backfill/re-merge of raw items collected while ignored.

### Metis Review (gaps addressed)
- Callback authorization must reuse command authorization because global ignore is destructive.
- Telegram callback data has a 64-byte limit; UUID payloads fit using compact forms `intel:d:<uuid>`, `intel:i:<uuid>`, and `intel:u:<uuid>`. Pagination callbacks must use compact state tokens, not full query/label text.
- Ignored entries must not be duplicated by ingestion when matching raw evidence appears later.
- `/intel_labels` and `GET /intelligence/labels` must exclude ignored entries by default because they are discovery/query surfaces.
- Scope excludes per-user ignore, bulk operations, ignore reasons, dashboards, raw-row deletion, and broad Telegram redesign.

## Work Objectives
### Core Objective
Make intelligence entries actionable from Telegram result lists while enforcing a consistent global ignore state across storage, API, Telegram, search, and ingestion.

### Deliverables
- Database/model fields: `is_ignored: bool`, `ignored_at: Optional[datetime]`, `ignored_by: Optional[str]` on canonical intelligence entries.
- PostgreSQL migration: `migrations/postgresql/004_intelligence_ignore_state.sql` for existing DBs; fresh schema updated in `003_intelligence_schema.sql`.
- Repository contract and storage implementation methods:
  - `ignore_canonical_entry(entry_id: str, ignored_by: Optional[str] = None) -> Optional[CanonicalIntelligenceEntry]`
  - `unignore_canonical_entry(entry_id: str) -> Optional[CanonicalIntelligenceEntry]`
  - `list_ignored_canonical_entries(...)`
  - `count_ignored_canonical_entries(...)`
  - Existing list/count/search methods exclude ignored entries by default.
- HTTP API:
  - `GET /intelligence/entries/ignored`
  - `POST /intelligence/entries/{entry_id}/ignore`
  - `POST /intelligence/entries/{entry_id}/unignore`
  - Existing list/search/labels hide ignored entries by default; detail still returns ignored entries.
- Telegram:
  - Callback query handler with same auth/rate-limit policy as commands.
  - `详情` and `忽略` inline buttons for `/intel_recent` and `/intel_search`.
  - `上一页` / `下一页` inline buttons for `/intel_recent`, `/intel_search`, and `/intel_ignored`.
  - `/intel_ignored [page]` and `/intel_unignore <id>`.
  - Help/bot command registration updated.
- Ingestion/merge:
  - Matching ignored canonical entries are detected but not mutated.
  - No duplicate canonical entry is created for an ignored normalized key.
  - After unignore, only future ingestion can update the entry.

### Definition of Done (verifiable conditions with commands)
- `uv run pytest tests/test_intelligence_repositories.py -v`
- `uv run pytest tests/test_intelligence_api.py -v`
- `uv run pytest tests/test_intelligence_telegram_commands.py -v`
- `uv run pytest tests/test_intelligence_ingestion_runtime.py -v`
- `uv run pytest tests/ -v`
- `uv run mypy crypto_news_analyzer/`
- `uv run flake8 crypto_news_analyzer/`

### Must Have
- `详情` callback returns same formatted detail body as `/intel_detail <id>`.
- `忽略` callback globally marks the canonical entry ignored and acknowledges the action.
- Pagination callbacks render the previous/next page for `/intel_recent`, `/intel_search`, and `/intel_ignored` without requiring the user to retype the command.
- Ignored entries are absent from `/intel_recent`, `/intel_search`, `/intel_labels`, `GET /intelligence/entries`, `GET /intelligence/search`, and `GET /intelligence/labels` by default.
- Ignored entries are present in `/intel_ignored` and `GET /intelligence/entries/ignored`.
- Exact detail lookup remains available and includes ignore metadata.
- All callback operations reject unauthorized Telegram users before repository mutation.
- Ingestion does not update ignored canonical entry fields and does not create a duplicate.

### Must NOT Have (guardrails, AI slop patterns, scope boundaries)
- No per-user ignore state.
- No bulk ignore/unignore.
- No ignore reason prompt or moderation workflow.
- No dashboard/admin UI.
- No deletion of canonical entries, aliases, observations, raw rows, or raw evidence text as part of ignore.
- No hiding ignored entries from exact detail endpoints.
- No unrelated Telegram command redesign.
- No broad repository rewrites beyond intelligence canonical ignore semantics.

## Verification Strategy
> ZERO HUMAN INTERVENTION - all verification is agent-executed.
- Test decision: TDD + existing `pytest` framework from `pyproject.toml:81`.
- QA policy: Every task has agent-executed scenarios.
- Evidence: `.sisyphus/evidence/task-{N}-{slug}.{ext}`

## Execution Strategy
### Parallel Execution Waves
> Target: 5-8 tasks per wave. <3 per wave (except final) is allowed here because Task 1 is a genuine shared storage dependency.
> Extract shared dependencies as Wave-1 tasks for max parallelism.

Wave 1: Task 1 foundation storage/domain/repository ignore state.
Wave 2: Tasks 2, 3, 4, 6 in parallel after Task 1.
Wave 3: Task 5 after Tasks 2 and 4; Task 7 after Task 5.

### Dependency Matrix (full, all tasks)
- Task 1 blocks Tasks 2, 3, 4, 5, 6, 7.
- Task 2 blocks Task 5 only for shared response/endpoint semantics.
- Task 3 has no downstream blocker after completion but must finish before final verification.
- Task 4 blocks Task 5.
- Task 5 blocks Task 7.
- Task 6 has no downstream blocker after completion but must finish before final verification.
- Task 7 has no downstream blocker after completion but must finish before final verification.

### Agent Dispatch Summary (wave → task count → categories)
- Wave 1 → 1 task → `deep`
- Wave 2 → 4 tasks → `quick`, `quick`, `quick`, `deep`
- Wave 3 → 2 tasks → `quick`, `quick`

## TODOs
> Implementation + Test = ONE task. Never separate.
> EVERY task MUST have: Agent Profile + Parallelization + QA Scenarios.

- [x] 1. Add canonical intelligence ignore state to domain, schema, and repository

  **What to do**: Add global ignore fields to `CanonicalIntelligenceEntry`, fresh SQLite/Postgres schemas, existing Postgres migration, repository interface, SQLite/Postgres-backed implementation, and serialization. Use fields exactly: `is_ignored: bool = False`, `ignored_at: Optional[datetime] = None`, `ignored_by: Optional[str] = None`. Add `migrations/postgresql/004_intelligence_ignore_state.sql` with idempotent `ALTER TABLE intelligence_canonical_entries ADD COLUMN IF NOT EXISTS ...` statements and index `idx_intelligence_canonical_entries_is_ignored`. Update `migrations/postgresql/003_intelligence_schema.sql` so fresh Postgres DBs include these columns. Update `DataManager._initialize_intelligence_tables` and row serialization. Add repository methods exactly named `ignore_canonical_entry`, `unignore_canonical_entry`, `list_ignored_canonical_entries`, and `count_ignored_canonical_entries`. Existing `get_canonical_entry_by_id` and `get_canonical_entry_by_normalized_key` must return ignored entries; discovery list/count/search methods must exclude ignored by default.
  **Must NOT do**: Do not add per-user tables, ignore reasons, audit history tables, hard delete, or raw-row deletion. Do not hide ignored entries from exact ID/normalized-key lookups.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: Cross-layer storage/domain/repository contract change with migration compatibility risk.
  - Skills: [] - No specialized skill required.
  - Omitted: [`playwright`] - No browser/UI work.

  **Parallelization**: Can Parallel: NO | Wave 1 | Blocks: [2, 3, 4, 5, 6, 7] | Blocked By: []

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `crypto_news_analyzer/domain/models.py:826` - `CanonicalIntelligenceEntry` fields, validation, `to_dict`, `from_dict`.
  - Pattern: `crypto_news_analyzer/domain/repositories.py:393` - `IntelligenceRepository` canonical method contract.
  - Pattern: `crypto_news_analyzer/storage/repositories.py:542` - `SQLiteIntelligenceRepository` delegates intelligence repository operations to `DataManager`.
  - Pattern: `crypto_news_analyzer/storage/data_manager.py:414` - SQLite/Postgres-compatible intelligence table initialization.
  - Pattern: `crypto_news_analyzer/storage/data_manager.py:2478` - canonical upsert method and alias persistence.
  - Pattern: `crypto_news_analyzer/storage/data_manager.py:2553` - canonical entry row serialization.
  - Pattern: `crypto_news_analyzer/storage/data_manager.py:2589` - list filters for canonical entries.
  - Pattern: `crypto_news_analyzer/storage/data_manager.py:2636` - count filters for canonical entries.
  - Pattern: `crypto_news_analyzer/storage/data_manager.py:2730` - semantic search count filters.
  - Pattern: `crypto_news_analyzer/storage/data_manager.py:2757` - semantic search result filters.
  - Pattern: `migrations/postgresql/003_intelligence_schema.sql:87` - fresh Postgres canonical table definition.
  - Test: `tests/test_intelligence_repositories.py:22` - round-trip repository tests.
  - Test: `tests/test_intelligence_repositories.py:131` - schema assertions.

  **Acceptance Criteria** (agent-executable only):
  - [ ] `CanonicalIntelligenceEntry.create(...)` defaults to `is_ignored is False`, `ignored_at is None`, `ignored_by is None`.
  - [ ] Existing rows created before the new fields serialize/load as not ignored.
  - [ ] `repository.ignore_canonical_entry(existing_id, ignored_by="telegram:123")` returns the updated entry with `is_ignored=True`, non-null `ignored_at`, and `ignored_by="telegram:123"`.
  - [ ] Repeating ignore on an already ignored entry is idempotent and keeps/refreshes only audit fields consistently per implementation; test asserts no exception and still ignored.
  - [ ] `repository.unignore_canonical_entry(existing_id)` returns the updated entry with `is_ignored=False`, `ignored_at=None`, `ignored_by=None`.
  - [ ] Ignore/unignore for missing IDs returns `None` and does not create rows.
  - [ ] `list_canonical_entries`, `count_canonical_entries`, `semantic_search`, and `count_semantic_search_candidates` exclude ignored entries by default.
  - [ ] `get_canonical_entry_by_id` and `get_canonical_entry_by_normalized_key` still return ignored entries.
  - [ ] `list_ignored_canonical_entries` and `count_ignored_canonical_entries` return only ignored entries with pagination and existing filters.
  - [ ] `uv run pytest tests/test_intelligence_repositories.py -v` passes.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Repository ignore lifecycle
    Tool: Bash
    Steps: Run `uv run pytest tests/test_intelligence_repositories.py::test_intelligence_repository_ignore_lifecycle -v` after adding the test.
    Expected: Test passes and proves default visible → ignored hidden from list/search → exact detail visible → unignored visible again.
    Evidence: .sisyphus/evidence/task-1-repository-ignore-lifecycle.txt

  Scenario: Missing and idempotent ignore operations
    Tool: Bash
    Steps: Run `uv run pytest tests/test_intelligence_repositories.py::test_intelligence_repository_ignore_missing_and_idempotent -v` after adding the test.
    Expected: Missing ID returns None; duplicate ignore and duplicate unignore do not raise and preserve correct final state.
    Evidence: .sisyphus/evidence/task-1-repository-ignore-edge.txt
  ```

  **Commit**: NO | Message: `feat(intelligence): add canonical ignore state` | Files: [`crypto_news_analyzer/domain/models.py`, `crypto_news_analyzer/domain/repositories.py`, `crypto_news_analyzer/storage/repositories.py`, `crypto_news_analyzer/storage/data_manager.py`, `migrations/postgresql/003_intelligence_schema.sql`, `migrations/postgresql/004_intelligence_ignore_state.sql`, `tests/test_intelligence_repositories.py`]

- [x] 2. Add HTTP ignore/unignore/ignored-list endpoints and default filtering

  **What to do**: Add API response/request models and routes in `create_api_server`. Endpoint names are fixed: `GET /intelligence/entries/ignored`, `POST /intelligence/entries/{entry_id}/ignore`, `POST /intelligence/entries/{entry_id}/unignore`. Register the literal `GET /intelligence/entries/ignored` route before `GET /intelligence/entries/{entry_id}` so FastAPI does not treat `ignored` as an entry ID. Add optional JSON request body for ignore: `{"ignored_by": "operator-id"}`; if omitted use `ignored_by="api"`. Response model fields exactly: `success: bool`, `entry_id: str`, `is_ignored: bool`, `ignored_at: Optional[str]`, `ignored_by: Optional[str]`. Add ignore metadata fields to `IntelligenceEntryResponse`, `IntelligenceEntryDetailResponse`, and `IntelligenceSearchResultItem`. Ensure `GET /intelligence/entries`, `GET /intelligence/labels`, and default API list surfaces exclude ignored entries. Ensure `GET /intelligence/entries/{entry_id}` returns ignored entries with metadata.
  **Must NOT do**: Do not add `DELETE` endpoints. Do not require a body for ignore. Do not hide exact detail endpoint. Do not expose unauthenticated mutations.

  **Recommended Agent Profile**:
  - Category: `quick` - Reason: Focused FastAPI route/model updates after repository foundation exists.
  - Skills: [] - No specialized skill required.
  - Omitted: [`playwright`] - API-only verification.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: [5] | Blocked By: [1]

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `crypto_news_analyzer/api_server.py:333` - `IntelligenceEntryResponse` fields.
  - Pattern: `crypto_news_analyzer/api_server.py:361` - `IntelligenceEntryDetailResponse` fields.
  - Pattern: `crypto_news_analyzer/api_server.py:385` - `IntelligenceSearchResultItem` fields.
  - Pattern: `crypto_news_analyzer/api_server.py:424` - `_canonical_entry_to_response` serializer.
  - Pattern: `crypto_news_analyzer/api_server.py:581` - Bearer auth dependency.
  - Pattern: `crypto_news_analyzer/api_server.py:1262` - `GET /intelligence/entries` route.
  - Pattern: `crypto_news_analyzer/api_server.py:1299` - `GET /intelligence/labels` route.
  - Pattern: `crypto_news_analyzer/api_server.py:1311` - exact detail route that must keep returning ignored entries.
  - Pattern: `crypto_news_analyzer/api_server.py:1366` - search route.
  - Test: `tests/test_intelligence_api.py:405` - auth tests for intelligence endpoints.
  - Test: `tests/test_intelligence_api.py:450` - list/pagination tests.
  - Test: `tests/test_intelligence_api.py:586` - labels tests.
  - Test: `tests/test_intelligence_api.py:606` - detail tests.

  **Acceptance Criteria** (agent-executable only):
  - [ ] Unauthenticated `POST /intelligence/entries/{id}/ignore` and `/unignore` return 401.
  - [ ] Authenticated ignore existing entry returns 200 and response `is_ignored=true`.
  - [ ] Authenticated ignore missing entry returns 404.
  - [ ] Authenticated duplicate ignore returns 200 and remains ignored.
  - [ ] Authenticated unignore existing entry returns 200 and response `is_ignored=false`.
  - [ ] Authenticated duplicate unignore returns 200 and remains unignored.
  - [ ] `GET /intelligence/entries` excludes ignored entries by default.
  - [ ] `GET /intelligence/labels` excludes labels/counts contributed only by ignored entries.
  - [ ] `GET /intelligence/entries/ignored` returns ignored entries only with pagination metadata.
  - [ ] `GET /intelligence/entries/{entry_id}` returns ignored entry details and includes ignore metadata.
  - [ ] `uv run pytest tests/test_intelligence_api.py -v` passes.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: HTTP ignore and hidden list behavior
    Tool: Bash
    Steps: Run `uv run pytest tests/test_intelligence_api.py::test_ignore_entry_hides_from_entries_and_labels -v` after adding the test.
    Expected: Ignore endpoint returns 200; list and labels exclude ignored entry; detail still returns it with `is_ignored=true`.
    Evidence: .sisyphus/evidence/task-2-api-ignore-list.txt

  Scenario: HTTP auth and idempotency failure path
    Tool: Bash
    Steps: Run `uv run pytest tests/test_intelligence_api.py::test_ignore_unignore_auth_missing_and_idempotent -v` after adding the test.
    Expected: 401 without Bearer, 404 missing entry, duplicate ignore/unignore are 200 with stable final state.
    Evidence: .sisyphus/evidence/task-2-api-ignore-edge.txt
  ```

  **Commit**: NO | Message: `feat(api): add intelligence ignore endpoints` | Files: [`crypto_news_analyzer/api_server.py`, `tests/test_intelligence_api.py`]

- [x] 3. Ensure semantic intelligence search excludes ignored entries consistently

  **What to do**: Verify and adjust `IntelligenceSearchService.semantic_search` and repository semantic search/count paths so ignored entries are excluded from API `/intelligence/search` and Telegram `/intel_search` by default. Filtering must happen at repository/storage query level, not only after pagination, so `total`, pagination, and all-ignored result sets are correct. Add tests for all-ignored results and mixed ignored/visible results. Include ignore metadata on result models even though default search hides ignored entries.
  **Must NOT do**: Do not post-filter after fetching a page if that makes totals/page sizes wrong. Do not remove exact detail access. Do not alter unrelated semantic search for news content (`/semantic-search`).

  **Recommended Agent Profile**:
  - Category: `quick` - Reason: Focused search/count filter verification after Task 1.
  - Skills: [] - No specialized skill required.
  - Omitted: [`playwright`] - No browser/UI work.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: [] | Blocked By: [1]

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `crypto_news_analyzer/intelligence/search.py:61` - service builds count and result queries.
  - Pattern: `crypto_news_analyzer/storage/data_manager.py:2730` - semantic candidate count filters.
  - Pattern: `crypto_news_analyzer/storage/data_manager.py:2757` - semantic candidate result filters.
  - Pattern: `crypto_news_analyzer/storage/repositories.py:648` - repository count delegate.
  - Pattern: `crypto_news_analyzer/storage/repositories.py:661` - repository semantic search delegate.
  - Pattern: `crypto_news_analyzer/api_server.py:1366` - HTTP intelligence search route.
  - Pattern: `crypto_news_analyzer/reporters/telegram_command_handler.py:2402` - Telegram `/intel_search` business method uses intelligence search service.
  - Test: `tests/test_intelligence_api.py:766` - ranked search result test.
  - Test: `tests/test_intelligence_api.py:807` - search filter test.
  - Test: `tests/test_intelligence_api.py:980` - empty search behavior.

  **Acceptance Criteria** (agent-executable only):
  - [ ] Repository semantic count excludes ignored entries before returning `total`.
  - [ ] Repository semantic results exclude ignored entries before `limit/offset` pagination.
  - [ ] API `/intelligence/search?q=...` returns `total=0` and `results=[]` when all matches are ignored.
  - [ ] API `/intelligence/search?q=...` returns only visible entries when mixed ignored/visible matches exist.
  - [ ] Telegram `/intel_search` business method receives only visible entries from service.
  - [ ] `uv run pytest tests/test_intelligence_api.py::test_semantic_search_excludes_ignored_entries -v` passes after adding it.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Mixed visible and ignored semantic matches
    Tool: Bash
    Steps: Run `uv run pytest tests/test_intelligence_api.py::test_semantic_search_excludes_ignored_entries -v` after adding the test.
    Expected: Response contains visible entry only; `total` equals visible count, not raw match count.
    Evidence: .sisyphus/evidence/task-3-search-hidden.txt

  Scenario: All search matches ignored
    Tool: Bash
    Steps: Run `uv run pytest tests/test_intelligence_api.py::test_semantic_search_all_ignored_returns_empty -v` after adding the test.
    Expected: HTTP 200 with `results=[]`, `total=0`, page metadata unchanged.
    Evidence: .sisyphus/evidence/task-3-search-all-ignored.txt
  ```

  **Commit**: NO | Message: `fix(search): exclude ignored intelligence entries` | Files: [`crypto_news_analyzer/intelligence/search.py`, `crypto_news_analyzer/storage/data_manager.py`, `crypto_news_analyzer/storage/repositories.py`, `tests/test_intelligence_api.py`]

- [x] 4. Add Telegram callback query plumbing with command-equivalent authorization

  **What to do**: Add `CallbackQueryHandler` registration in `_build_application` and implement a single private callback router, e.g. `_handle_intel_callback_query`. Supported callback payloads must be compact and under Telegram's 64-byte limit: `intel:d:<uuid>` for details, `intel:i:<uuid>` for ignore, `intel:u:<uuid>` for unignore/restore, and `intel:p:<token>:<page>` for pagination. Add an in-memory TTL callback state map on `TelegramCommandHandler` for pagination tokens; state stores command kind (`recent`, `search`, `ignored`), query/window/label/page_size, chat_id, and creating user_id. Use token length 8-12 URL-safe chars so callback data stays well under 64 bytes. Expire state after 15 minutes and acknowledge expired/missing state with `翻页已过期，请重新执行命令`. The callback handler must extract user/chat context from `update.callback_query`, apply `is_authorized_user` and rate-limit checks consistently with command handlers, call `callback_query.answer(...)` with concise status text, and never mutate repository state for unauthorized users. Add mocked callback tests because no callback coverage exists today.
  **Must NOT do**: Do not allow callbacks without authorization. Do not introduce per-user ignore state. Do not require real Telegram network calls in tests. Do not use callback payloads containing full JSON or long text.

  **Recommended Agent Profile**:
  - Category: `quick` - Reason: Localized Telegram framework plumbing and tests.
  - Skills: [] - No specialized skill required.
  - Omitted: [`playwright`] - Telegram is tested with mocks, not browser automation.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: [5] | Blocked By: [1]

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `crypto_news_analyzer/reporters/telegram_command_handler.py:179` - `_build_application` command handler registration.
  - Pattern: `crypto_news_analyzer/reporters/telegram_command_handler.py:371` - `is_authorized_user` policy.
  - Pattern: `crypto_news_analyzer/reporters/telegram_command_handler.py:417` - rate limit helper.
  - Pattern: `crypto_news_analyzer/reporters/telegram_command_handler.py:462` - message-based chat context extraction; callback handler needs analogous extraction from `callback_query.from_user` and `callback_query.message.chat`.
  - Pattern: `crypto_news_analyzer/reporters/telegram_command_handler.py:510` - authorization logging pattern.
  - Test: `tests/test_intelligence_telegram_commands.py:72` - application registration test.
  - Test: `tests/test_intelligence_telegram_commands.py:94` - authorized command dispatch pattern.
  - Test: `tests/test_intelligence_telegram_commands.py:114` - unauthorized command blocks repository calls.

  **Acceptance Criteria** (agent-executable only):
  - [ ] `_build_application` registers `CallbackQueryHandler` for pattern `^intel:(d|i|u|p):`.
  - [ ] Callback payload constants/helpers produce strings no longer than 64 bytes for UUID IDs.
  - [ ] Unauthorized callback users receive callback acknowledgement and no repository mutation.
  - [ ] Authorized detail callback dispatches detail logic for the entry ID.
  - [ ] Authorized ignore callback dispatches ignore logic for the entry ID.
  - [ ] Authorized unignore callback dispatches restore logic for the entry ID.
  - [ ] Authorized pagination callback dispatches the stored command state with requested page number.
  - [ ] Expired/missing pagination state is acknowledged with `翻页已过期，请重新执行命令` and no exception.
  - [ ] Unknown/malformed callback payloads are acknowledged with an error and do not raise.
  - [ ] `uv run pytest tests/test_intelligence_telegram_commands.py -v` passes.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Authorized callback routing
    Tool: Bash
    Steps: Run `uv run pytest tests/test_intelligence_telegram_commands.py::test_authorized_intel_callback_dispatches_detail_and_ignore -v` after adding the test.
    Expected: Detail callback calls detail handler; ignore callback calls ignore handler; both answer callback query.
    Evidence: .sisyphus/evidence/task-4-callback-authorized.txt

  Scenario: Unauthorized callback cannot mutate global ignore
    Tool: Bash
    Steps: Run `uv run pytest tests/test_intelligence_telegram_commands.py::test_unauthorized_intel_callback_does_not_ignore_entry -v` after adding the test.
    Expected: Repository ignore method is not called; callback is answered with unauthorized message.
    Evidence: .sisyphus/evidence/task-4-callback-unauthorized.txt

  Scenario: Pagination callback state expiry
    Tool: Bash
    Steps: Run `uv run pytest tests/test_intelligence_telegram_commands.py::test_intel_pagination_callback_expired_state_is_safe -v` after adding the test.
    Expected: Missing/expired token is acknowledged with the rerun-command message; no repository mutation or unhandled exception occurs.
    Evidence: .sisyphus/evidence/task-4-pagination-expired.txt
  ```

  **Commit**: NO | Message: `feat(telegram): add intel callback routing` | Files: [`crypto_news_analyzer/reporters/telegram_command_handler.py`, `tests/test_intelligence_telegram_commands.py`]

- [x] 5. Implement interactive Telegram intel list/detail/ignore/unignore UX

  **What to do**: Update Telegram `/intel_recent` and `/intel_search` command paths so result rows use the requested visible metadata shape: `N. {display_name} | slang | 支付 | 0.85`, with inline buttons `详情` and `忽略` attached for each listed entry. Because Telegram inline keyboards are message-level, build rows with one button row per entry: `[详情, 忽略]` where callback data maps to that entry. Preserve summary text under each entry. Add pagination button rows to `/intel_recent`, `/intel_search`, and `/intel_ignored`: include `上一页` when current page > 1 and `下一页` when current page < total_pages. Pagination buttons must use Task 4's `intel:p:<token>:<page>` callback and edit the existing message text/markup when possible; if edit fails, send a replacement message. Implement detail callback so it returns the same formatted body as `/intel_detail <id>`. Implement ignore callback so it calls repository ignore with `ignored_by="telegram:{user_id}"`, acknowledges success, and edits or replies with clear status `已忽略：{display_name}`. Add `/intel_ignored [page]` to list ignored entries with `详情` and `恢复` buttons, and `/intel_unignore <id>` to restore by exact ID. Update bot command registration and help text.
  **Must NOT do**: Do not remove `/intel_detail`. Do not require users to copy IDs for normal details. Do not make ignored entries inaccessible by exact detail. Do not redesign non-intelligence commands.

  **Recommended Agent Profile**:
  - Category: `quick` - Reason: Telegram command formatting/callback behavior once plumbing and repository methods exist.
  - Skills: [] - No specialized skill required.
  - Omitted: [`playwright`] - Telegram interaction is tested with mocked python-telegram-bot objects.

  **Parallelization**: Can Parallel: NO | Wave 3 | Blocks: [7] | Blocked By: [1, 2, 4]

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `crypto_news_analyzer/reporters/telegram_command_handler.py:611` - bot command registration.
  - Pattern: `crypto_news_analyzer/reporters/telegram_command_handler.py:914` - `/intel_recent` wrapper parsing and response send path.
  - Pattern: `crypto_news_analyzer/reporters/telegram_command_handler.py:1055` - `/intel_search` wrapper parsing and response send path.
  - Pattern: `crypto_news_analyzer/reporters/telegram_command_handler.py:1146` - `/intel_detail` wrapper behavior.
  - Pattern: `crypto_news_analyzer/reporters/telegram_command_handler.py:2199` - current summary row formatting.
  - Pattern: `crypto_news_analyzer/reporters/telegram_command_handler.py:2214` - detail formatting to reuse for callback.
  - Pattern: `crypto_news_analyzer/reporters/telegram_command_handler.py:2238` - current search result formatting.
  - Pattern: `crypto_news_analyzer/reporters/telegram_command_handler.py:2269` - current recent result formatting.
  - Pattern: `crypto_news_analyzer/reporters/telegram_command_handler.py:2322` - `/intel_recent` business method.
  - Pattern: `crypto_news_analyzer/reporters/telegram_command_handler.py:2385` - `/intel_labels` business method; must now use filtered repository counts.
  - Pattern: `crypto_news_analyzer/reporters/telegram_command_handler.py:2402` - `/intel_search` business method.
  - Pattern: `crypto_news_analyzer/reporters/telegram_command_handler.py:2431` - `/intel_detail` business method.
  - Test: `tests/test_intelligence_telegram_commands.py:148` - current search formatting test.
  - Test: `tests/test_intelligence_telegram_commands.py:172` - current recent formatting test.
  - Test: `tests/test_intelligence_telegram_commands.py:223` - detail raw text test.

  **Acceptance Criteria** (agent-executable only):
  - [ ] `/intel_recent` sends inline keyboard rows with `详情` and `忽略` buttons for each entry.
  - [ ] `/intel_search` sends inline keyboard rows with `详情` and `忽略` buttons for each result.
  - [ ] `/intel_recent` includes `上一页`/`下一页` buttons according to current/total page.
  - [ ] `/intel_search` includes `上一页`/`下一页` buttons according to current/total page while preserving the original query.
  - [ ] `/intel_ignored` includes `上一页`/`下一页` buttons according to current/total page.
  - [ ] Visible row text no longer includes `ID: <uuid>` in list/search rows.
  - [ ] Detail callback returns same body as `handle_intel_detail_command(..., entry_id)`.
  - [ ] Ignore callback marks entry ignored globally and acknowledges success.
  - [ ] Already ignored callback returns a successful/idempotent acknowledgement.
  - [ ] Missing entry callback returns a friendly not-found acknowledgement.
  - [ ] `/intel_ignored [page]` lists ignored entries only and includes `详情` and `恢复` buttons.
  - [ ] `/intel_unignore <id>` restores the entry and it reappears in `/intel_recent`/`/intel_search` if it matches filters.
  - [ ] Help text and bot command registration include `/intel_ignored` and `/intel_unignore`.
  - [ ] `uv run pytest tests/test_intelligence_telegram_commands.py -v` passes.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Recent and search results include action buttons
    Tool: Bash
    Steps: Run `uv run pytest tests/test_intelligence_telegram_commands.py::test_intel_recent_and_search_include_inline_action_buttons -v` after adding the test.
    Expected: Mock send calls include reply markup with `详情` and `忽略`; visible text excludes `ID:` and preserves summary.
    Evidence: .sisyphus/evidence/task-5-telegram-buttons.txt

  Scenario: Ignore and restore lifecycle from Telegram
    Tool: Bash
    Steps: Run `uv run pytest tests/test_intelligence_telegram_commands.py::test_intel_ignore_and_unignore_telegram_lifecycle -v` after adding the test.
    Expected: Ignore callback hides entry from list/search; `/intel_ignored` shows it; `/intel_unignore <id>` restores it.
    Evidence: .sisyphus/evidence/task-5-telegram-ignore-unignore.txt

  Scenario: Telegram pagination buttons preserve command state
    Tool: Bash
    Steps: Run `uv run pytest tests/test_intelligence_telegram_commands.py::test_intel_pagination_buttons_preserve_recent_search_and_ignored_state -v` after adding the test.
    Expected: Recent/search/ignored list responses include correct previous/next buttons; clicking next rerenders page 2 with original filters/query.
    Evidence: .sisyphus/evidence/task-5-telegram-pagination.txt
  ```

  **Commit**: NO | Message: `feat(telegram): add interactive intel actions` | Files: [`crypto_news_analyzer/reporters/telegram_command_handler.py`, `tests/test_intelligence_telegram_commands.py`]

- [x] 6. Prevent ingestion from mutating ignored canonical entries without creating duplicates

  **What to do**: Update merge/upsert behavior so when observations normalize to an existing ignored canonical entry, the system marks observations canonicalized as appropriate but does not mutate the ignored canonical entry's display fields, explanation, usage summary, labels, confidence, aliases, evidence count, last_seen, latest_raw_item_id, embeddings, or updated_at. It also must not create a duplicate entry for the same `(entry_type, normalized_key)`. Future-only unignore rule: after unignore, subsequent new observations can update the entry; no backfill/re-merge of observations collected while ignored is required.
  **Must NOT do**: Do not skip raw item persistence globally. Do not delete observations. Do not create duplicate canonical entries for ignored normalized keys. Do not update embeddings for ignored canonical entries.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: Requires careful merge semantics across ingestion, observations, canonicalization, and embedding generation.
  - Skills: [] - No specialized skill required.
  - Omitted: [`playwright`] - No browser/UI work.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: [] | Blocked By: [1]

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `crypto_news_analyzer/intelligence/pipeline.py:72` - per-source ingestion sequence saves raw, extracts observations, canonicalizes, generates embeddings.
  - Pattern: `crypto_news_analyzer/intelligence/pipeline.py:137` - raw dedupe save logic; should not be disabled by ignore.
  - Pattern: `crypto_news_analyzer/intelligence/pipeline.py:181` - embedding generation for canonical entries returned by merge.
  - Pattern: `crypto_news_analyzer/intelligence/merge.py:25` - canonicalization loop and existing-entry detection.
  - Pattern: `crypto_news_analyzer/intelligence/merge.py:45` - existing canonical entry lookup by normalized key.
  - Pattern: `crypto_news_analyzer/intelligence/merge.py:144` - merge mutation logic to bypass for ignored entries.
  - Pattern: `crypto_news_analyzer/domain/repositories.py:446` - normalized-key lookup must return ignored entries to avoid duplicates.
  - Test: `tests/test_intelligence_ingestion_runtime.py:163` - repeated run dedupe behavior.
  - Test: `tests/test_intelligence_ingestion_runtime.py:182` - same text/new external ID counts as evidence today; ignored entries should be exception.
  - Test: `tests/test_intelligence_ingestion_runtime.py:202` - related candidate/embedding behavior.

  **Acceptance Criteria** (agent-executable only):
  - [ ] New raw items matching ignored canonical entries may still be saved, but canonical entry fields remain unchanged.
  - [ ] Matching ignored canonical entries do not get evidence count incremented.
  - [ ] Matching ignored canonical entries do not get `last_seen_at`, `latest_raw_item_id`, aliases, or `updated_at` changed.
  - [ ] Matching ignored canonical entries are not returned for embedding generation.
  - [ ] No duplicate canonical entry is created for the ignored normalized key.
  - [ ] Observations from ignored matches do not remain in an infinite uncanonicalized retry loop.
  - [ ] After unignore, a future new observation can update the canonical entry normally.
  - [ ] `uv run pytest tests/test_intelligence_ingestion_runtime.py -v` passes.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Ignored canonical entry is not mutated by new evidence
    Tool: Bash
    Steps: Run `uv run pytest tests/test_intelligence_ingestion_runtime.py::test_ignored_canonical_entry_is_not_updated_by_new_evidence -v` after adding the test.
    Expected: Entry snapshot before/after ingestion is unchanged for mutable fields; no duplicate normalized key exists.
    Evidence: .sisyphus/evidence/task-6-ingestion-skip-update.txt

  Scenario: Unignored entry resumes future-only updates
    Tool: Bash
    Steps: Run `uv run pytest tests/test_intelligence_ingestion_runtime.py::test_unignored_entry_resumes_future_ingestion_updates -v` after adding the test.
    Expected: Ignored-period observations do not backfill; a new post-unignore observation updates evidence/last_seen normally.
    Evidence: .sisyphus/evidence/task-6-ingestion-unignore-future.txt
  ```

  **Commit**: NO | Message: `fix(ingestion): preserve ignored intelligence entries` | Files: [`crypto_news_analyzer/intelligence/merge.py`, `crypto_news_analyzer/intelligence/pipeline.py`, `tests/test_intelligence_ingestion_runtime.py`]

- [x] 7. Run full validation and remove UX/schema inconsistencies

  **What to do**: Run the full targeted and global validation suite, then fix only issues directly caused by Tasks 1-6. Verify docs/help strings and bot command list are consistent. Verify API schemas serialize new ignore metadata with ISO datetimes or nulls. Verify callback payload helpers never exceed 64 bytes, including pagination payloads. Verify no ignored state leaks into unrelated news semantic search or datasource functionality.
  **Must NOT do**: Do not expand scope into docs rewrites, unrelated command redesign, or new moderation features. Do not commit without explicit user request.

  **Recommended Agent Profile**:
  - Category: `quick` - Reason: Final cleanup and validation after implementation tasks.
  - Skills: [] - No specialized skill required.
  - Omitted: [`playwright`] - No browser UI; verification is pytest/API/Telegram mocks.

  **Parallelization**: Can Parallel: NO | Wave 3 | Blocks: [] | Blocked By: [5]

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `pyproject.toml:81` - pytest configuration.
  - Pattern: `pyproject.toml:67` - Black formatting config.
  - Pattern: `pyproject.toml:71` - Flake8 line length/ignore config.
  - Pattern: `pyproject.toml:75` - mypy config.
  - Pattern: `crypto_news_analyzer/reporters/telegram_command_handler.py:2826` - help text generation.
  - Pattern: `crypto_news_analyzer/api_server.py:424` - response serialization.
  - Test: `tests/test_intelligence_telegram_commands.py:72` - command registration.
  - Test: `tests/test_intelligence_api.py:405` - API auth baseline.
  - Test: `tests/test_intelligence_repositories.py:131` - schema baseline.

  **Acceptance Criteria** (agent-executable only):
  - [ ] `uv run pytest tests/test_intelligence_repositories.py -v` passes.
  - [ ] `uv run pytest tests/test_intelligence_api.py -v` passes.
  - [ ] `uv run pytest tests/test_intelligence_telegram_commands.py -v` passes.
  - [ ] `uv run pytest tests/test_intelligence_ingestion_runtime.py -v` passes.
  - [ ] `uv run pytest tests/ -v` passes.
  - [ ] `uv run mypy crypto_news_analyzer/` passes.
  - [ ] `uv run flake8 crypto_news_analyzer/` passes.
  - [ ] No source files outside the planned file set were changed except directly necessary imports/types.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Full regression suite
    Tool: Bash
    Steps: Run `uv run pytest tests/ -v`.
    Expected: All tests pass with no regressions in datasource, analysis, semantic search, Telegram auth, or intelligence suites.
    Evidence: .sisyphus/evidence/task-7-full-pytest.txt

  Scenario: Static checks
    Tool: Bash
    Steps: Run `uv run mypy crypto_news_analyzer/ && uv run flake8 crypto_news_analyzer/`.
    Expected: Both commands exit 0.
    Evidence: .sisyphus/evidence/task-7-static-checks.txt
  ```

  **Commit**: NO | Message: `test(intelligence): validate intel ignore UX` | Files: [`crypto_news_analyzer/reporters/telegram_command_handler.py`, `crypto_news_analyzer/api_server.py`, `crypto_news_analyzer/domain/models.py`, `crypto_news_analyzer/domain/repositories.py`, `crypto_news_analyzer/storage/repositories.py`, `crypto_news_analyzer/storage/data_manager.py`, `crypto_news_analyzer/intelligence/merge.py`, `crypto_news_analyzer/intelligence/pipeline.py`, `migrations/postgresql/003_intelligence_schema.sql`, `migrations/postgresql/004_intelligence_ignore_state.sql`, `tests/test_intelligence_repositories.py`, `tests/test_intelligence_api.py`, `tests/test_intelligence_telegram_commands.py`, `tests/test_intelligence_ingestion_runtime.py`]

## Final Verification Wave (MANDATORY — after ALL implementation tasks)
> 4 review agents run in PARALLEL. ALL must APPROVE. Present consolidated results to user and get explicit "okay" before completing.
> **Do NOT auto-proceed after verification. Wait for user's explicit approval before marking work complete.**
> **Never mark F1-F4 as checked before getting user's okay.** Rejection or user feedback -> fix -> re-run -> present again -> wait for okay.
- [x] F1. Plan Compliance Audit — oracle
- [x] F2. Code Quality Review — unspecified-high
- [x] F3. Real Manual QA — unspecified-high (+ mocked Telegram callback/API pytest; Playwright not required because no browser UI)
- [x] F4. Scope Fidelity Check — deep

## Commit Strategy
- Do not create git commits unless the user explicitly asks for commits.
- If the user later requests commits, use small atomic commits by layer after tests pass; never use `--no-verify`.

## Success Criteria
- Telegram result lists are actionable without exposing raw IDs in the visible row metadata.
- Paginated Telegram intel lists can move between pages with inline `上一页` / `下一页` buttons.
- Ignored entries are globally hidden from discovery surfaces but still accessible by exact detail lookup and recoverable.
- HTTP API and Telegram semantics match exactly.
- Ingestion respects ignored canonical entries without data loss or duplicate canonical entries.
- All listed test, type, and lint commands pass.
