# Optimize Intelligence Slang Tracking, Evidence, and Deduplication

## TL;DR
> **Summary**: Rework the intelligence slang workflow so new slang is untracked by default, shown exactly once in recent discovery, hidden from search until followed, semantically deduplicated at high confidence, and fully linked to all supporting raw evidence.
> **Deliverables**:
> - Global slang tracking state with one-time recent discovery semantics
> - Automatic slang-only semantic merge with strict guardrails
> - Full evidence association storage plus nearby raw-context retrieval
> - HTTP + Telegram follow/unfollow/detail flows aligned with the new model
> - Ingestion pre-filtering of untracked/ignored slang before LLM extraction
> - TDD coverage across models, repositories, merge, API, Telegram, and ingestion runtime
> **Effort**: Large
> **Parallel**: YES - 3 waves
> **Critical Path**: 1 → 3 → 4 → 5 → 6 → 8

## Context
### Original Request
Optimize the intelligence collection feature so slang collection is less redundant, most slang is not continuously tracked by default, raw evidence detail shows much more surrounding context, merged entries preserve all raw evidence associations, and ingestion saves LLM tokens by suppressing uninteresting slang.

### Interview Summary
- Tracking state is global operator state, not per-user.
- New slang is untracked by default, hidden from search, and shown once in recent discovery.
- Recent discovery replaces the old ignore-first interaction with a follow action.
- Equivalent slang should auto-merge semantically, but only with strict safety rules.
- Detail views show 5 evidence groups per page; each group includes the anchor evidence item plus 10 nearby raw items.
- LLM savings should come from pre-filtering raw items matching untracked/ignored slang before extraction.
- Test strategy is TDD.

### Metis Review (gaps addressed)
- Resolved state-model ambiguity by introducing explicit tracking state separate from legacy hard-ignore.
- Resolved “recent only once” ambiguity with a persisted presentation timestamp rather than ephemeral cache state.
- Resolved semantic merge ID-stability risk by merging observations into existing slang before creating a duplicate canonical entry whenever embeddings are available.
- Resolved evidence-loss risk by adding a canonical-entry↔raw-evidence association table instead of relying on `latest_raw_item_id` alone.

## Work Objectives
### Core Objective
Make slang intelligence cheaper and less noisy without weakening evidence traceability or accidentally broadening channel-merge behavior.

### Deliverables
- Schema + domain model support for global slang tracking and one-time discovery presentation.
- Repository + storage support for evidence associations and nearby raw-item context windows.
- Slang-only semantic auto-merge using embedding similarity `>= 0.92` and matching `primary_label`.
- API and Telegram follow/unfollow/detail flows reflecting the new tracking model.
- Ingestion raw-item pre-filtering based on untracked/ignored slang dictionary matches.
- Regression coverage proving the new behavior and preserving existing channel behavior.

### Definition of Done (verifiable conditions with commands)
- `uv run pytest tests/test_intelligence_models.py tests/test_intelligence_repositories.py -v`
- `uv run pytest tests/test_intelligence_merge.py tests/test_intelligence_extraction.py -v`
- `uv run pytest tests/test_intelligence_api.py tests/test_intelligence_telegram_commands.py -v`
- `uv run pytest tests/test_intelligence_ingestion_runtime.py -v`
- `uv run pytest tests/integration/test_intelligence_pgvector.py -v` (only when `TEST_DATABASE_URL` is configured)

### Must Have
- New slang defaults to untracked and does not appear in search until followed.
- `intel_recent`-style discovery surfaces each untracked slang exactly once unless followed.
- Semantic auto-merge applies to `slang` only, never to `channel`.
- Every canonical entry detail can show all associated evidence anchors and each anchor’s ±10 neighboring raw items.
- Ingestion pre-filtering uses canonical slang display names plus aliases/normalized terms from untracked or ignored slang.

### Must NOT Have (guardrails, AI slop patterns, scope boundaries)
- Do not change channel merge behavior beyond preserving existing exact-key logic.
- Do not add per-user preference tables or user-specific query semantics.
- Do not rely on LLM-only merge decisions for slang deduplication.
- Do not overwrite evidence history with only `latest_raw_item_id`.
- Do not implement a general moderation queue beyond one-time recent discovery and follow/unfollow.
- Do not mutate standard news `/analyze` behavior outside the intelligence ingestion path.

## Verification Strategy
> ZERO HUMAN INTERVENTION - all verification is agent-executed.
- Test decision: TDD with existing `pytest` suite.
- QA policy: Every task includes agent-executed happy-path and edge-path scenarios.
- Evidence: `.sisyphus/evidence/task-{N}-{slug}.{ext}`

## Execution Strategy
### Parallel Execution Waves
> Target: 5-8 tasks per wave. <3 per wave (except final) = under-splitting.
> Extract shared dependencies as Wave-1 tasks for max parallelism.

Wave 1: schema/state contract, evidence association storage, merge-engine contract
Wave 2: API/query semantics, Telegram surfaces, ingestion pre-filtering
Wave 3: cross-surface regression, migration validation, final verification

### Dependency Matrix (full, all tasks)
- 1 blocks 2, 3, 4, 5, 6, 7, 8
- 2 blocks 5, 6, 8
- 3 blocks 4, 5, 7, 8
- 4 blocks 5, 6, 8
- 5 and 6 can run in parallel after 1, 2, 3, 4
- 7 can run in parallel with 5 and 6 after 1 and 3
- 8 depends on 1-7

### Agent Dispatch Summary (wave → task count → categories)
- Wave 1 → 3 tasks → `unspecified-high`, `ultrabrain`
- Wave 2 → 4 tasks → `unspecified-high`
- Wave 3 → 1 task → `unspecified-high`

## TODOs
> Implementation + Test = ONE task. Never separate.
> EVERY task MUST have: Agent Profile + Parallelization + QA Scenarios.

- [x] 1. Add global slang tracking state and rollout migration

  **What to do**: Extend canonical intelligence entries with `tracking_enabled: bool` and `discovery_presented_at: Optional[datetime]`. Keep `is_ignored` as a separate hard-suppress flag. Default new `slang` entries to `tracking_enabled=False`; default `channel` entries to `tracking_enabled=True`. Add PostgreSQL migration plus SQLite bootstrap changes. Backfill existing rows as follows: non-ignored channels -> `tracking_enabled=TRUE`; non-ignored slang -> `tracking_enabled=FALSE`, `discovery_presented_at=NULL`; ignored entries -> preserve `is_ignored=TRUE`, force `tracking_enabled=FALSE`, set `discovery_presented_at` to current timestamp so they never enter discovery.
  **Must NOT do**: Do not replace `is_ignored` semantics globally. Do not add per-user tables. Do not hide channels by default.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: coordinated schema, model, and migration work across storage layers.
  - Skills: `[]` - No special skill required.
  - Omitted: `['playwright']` - No browser work in this task.

  **Parallelization**: Can Parallel: NO | Wave 1 | Blocks: 2, 3, 4, 5, 6, 7, 8 | Blocked By: none

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `crypto_news_analyzer/domain/models.py:827` - Canonical entry fields and validation hooks to extend.
  - API/Type: `crypto_news_analyzer/domain/repositories.py:393` - Repository contract that all storage implementations must continue satisfying.
  - Pattern: `crypto_news_analyzer/storage/data_manager.py:423` - SQLite intelligence schema bootstrap starts here.
  - Pattern: `crypto_news_analyzer/storage/data_manager.py:475` - Canonical entry table creation in SQLite bootstrap.
  - Pattern: `migrations/postgresql/003_intelligence_schema.sql:3` - Existing PostgreSQL intelligence schema baseline.
  - Test: `tests/test_intelligence_models.py:1` - Model round-trip and validation style.
  - Test: `tests/test_intelligence_repositories.py:22` - Repository round-trip contract pattern.
  - Test: `tests/test_intelligence_repositories.py:222` - Existing ignore lifecycle behavior that must remain valid.

  **Acceptance Criteria** (agent-executable only):
  - [ ] `CanonicalIntelligenceEntry` serializes/deserializes the new fields without breaking existing ignore behavior.
  - [ ] SQLite bootstrap creates the new columns for fresh databases and tolerates existing databases via additive migration logic.
  - [ ] PostgreSQL migration applies without touching unrelated intelligence tables.
  - [ ] `uv run pytest tests/test_intelligence_models.py tests/test_intelligence_repositories.py -v`

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: New slang defaults to untracked and channels remain tracked
    Tool: Bash
    Steps: Run `uv run pytest tests/test_intelligence_models.py -v`
    Expected: Added tests prove slang entries default `tracking_enabled=False`, channels remain `True`, and new fields round-trip cleanly.
    Evidence: .sisyphus/evidence/task-1-tracking-state.log

  Scenario: Ignore backfill does not re-surface ignored entries
    Tool: Bash
    Steps: Run `uv run pytest tests/test_intelligence_repositories.py -v`
    Expected: Repository tests prove ignored entries preserve `is_ignored=True` and do not qualify as discovery candidates after migration/backfill.
    Evidence: .sisyphus/evidence/task-1-tracking-state-error.log
  ```

  **Commit**: NO | Message: `feat(intelligence): add slang tracking state` | Files: `crypto_news_analyzer/domain/models.py`, `crypto_news_analyzer/storage/data_manager.py`, `migrations/postgresql/*.sql`, `tests/test_intelligence_models.py`, `tests/test_intelligence_repositories.py`

- [x] 2. Persist full entry-evidence links and nearby raw context

  **What to do**: Add a dedicated evidence association table linking canonical entry, observation, and raw item. Write repository/storage methods to upsert evidence links during canonicalization, list paginated evidence anchors for one entry, and fetch a deterministic raw-context window of `10 before + anchor + 10 after` within the same conversation scope. Scope the window by `(source_type, source_id, chat_id, thread_id, topic_id)` and order by `COALESCE(published_at, collected_at), id`.
  **Must NOT do**: Do not infer evidence from `latest_raw_item_id` only. Do not mix context from different chats/threads/topics. Do not page individual context rows separately from their anchor evidence group.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: repository/storage work with deterministic pagination and association integrity.
  - Skills: `[]` - No special skill required.
  - Omitted: `['playwright']` - Pure backend data task.

  **Parallelization**: Can Parallel: NO | Wave 1 | Blocks: 5, 6, 8 | Blocked By: 1

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `crypto_news_analyzer/domain/repositories.py:409` - Existing raw-item lookup entry point.
  - Pattern: `crypto_news_analyzer/domain/repositories.py:425` - Existing observation lookup by raw item.
  - Pattern: `crypto_news_analyzer/storage/repositories.py:561` - Raw-item lookup implementation style.
  - Pattern: `crypto_news_analyzer/storage/repositories.py:595` - Canonical-entry upsert/get flow that should also attach evidence.
  - Pattern: `crypto_news_analyzer/domain/models.py:827` - `latest_raw_item_id` remains summary metadata, not full provenance.
  - Pattern: `crypto_news_analyzer/storage/data_manager.py:445` - Observation table schema and foreign-key style.
  - Pattern: `crypto_news_analyzer/storage/data_manager.py:475` - Canonical entry table neighborhood.
  - Test: `tests/test_intelligence_repositories.py:22` - Repository round-trip harness.
  - Test: `tests/test_intelligence_api.py:33` - Raw-item fixture pattern used later by API detail tests.

  **Acceptance Criteria** (agent-executable only):
  - [ ] Canonicalization persists one evidence link per `(entry_id, raw_item_id)` and preserves the originating observation ID.
  - [ ] Repository can page evidence anchors in newest-first order and return each anchor’s ±10 raw neighbors within one conversation scope.
  - [ ] Detail consumers can request page 1..N without duplicate anchors across pages.
  - [ ] `uv run pytest tests/test_intelligence_repositories.py -v`

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: One entry returns multiple evidence anchors with nearby context
    Tool: Bash
    Steps: Run `uv run pytest tests/test_intelligence_repositories.py -v`
    Expected: Added repository tests prove multiple raw items remain linked to one entry and each evidence anchor returns 21 context rows max in deterministic order.
    Evidence: .sisyphus/evidence/task-2-evidence-links.log

  Scenario: Context query does not leak across conversations
    Tool: Bash
    Steps: Run `uv run pytest tests/test_intelligence_repositories.py -k context -v`
    Expected: Edge-case tests prove neighboring rows from another source/thread/topic are excluded even if timestamps interleave.
    Evidence: .sisyphus/evidence/task-2-evidence-links-error.log
  ```

  **Commit**: NO | Message: `feat(intelligence): persist evidence context` | Files: `crypto_news_analyzer/domain/repositories.py`, `crypto_news_analyzer/storage/data_manager.py`, `crypto_news_analyzer/storage/repositories.py`, `migrations/postgresql/*.sql`, `tests/test_intelligence_repositories.py`

- [x] 3. Add slang-only semantic auto-merge before duplicate entry creation

  **What to do**: Upgrade `IntelligenceMergeEngine` so the flow is: exact normalized-key match → exact alias match → slang-only semantic candidate lookup. For the semantic path, build embedding text from observation term, literal/contextual meaning, aliases, and `primary_label`; query existing canonical entries via repository semantic search; auto-merge only when `entry_type == slang`, best candidate similarity `>= 0.92`, `primary_label` matches, candidate is not ignored, and candidate is not a `channel`. If embeddings are unavailable or no candidate qualifies, fall back to creating a new slang entry. When merging, preserve the existing entry ID, retain `tracking_enabled=True` if already followed, and add the new term/aliases into the survivor’s `aliases` list.
  **Must NOT do**: Do not auto-merge channels. Do not call the LLM to decide merges. Do not create then delete duplicate canonical IDs when a qualified semantic match exists.

  **Recommended Agent Profile**:
  - Category: `ultrabrain` - Reason: core logic change with safety thresholds and fallback behavior.
  - Skills: `[]` - Existing embedding/search interfaces are already in-repo.
  - Omitted: `['llm-instructor']` - No new instructor workflow is needed.

  **Parallelization**: Can Parallel: NO | Wave 1 | Blocks: 4, 5, 6, 7, 8 | Blocked By: 1

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `crypto_news_analyzer/intelligence/merge.py:1` - Current conservative exact-only merge policy.
  - Pattern: `crypto_news_analyzer/intelligence/merge.py:25` - Canonicalization loop to extend.
  - Pattern: `crypto_news_analyzer/intelligence/pipeline.py:72` - Source-processing pipeline that invokes canonicalization.
  - API/Type: `crypto_news_analyzer/domain/repositories.py:513` - Embedding persistence/search contract for intelligence entries.
  - Pattern: `crypto_news_analyzer/storage/repositories.py:682` - Existing intelligence embedding + semantic search implementation.
  - Pattern: `crypto_news_analyzer/analyzers/intelligence_extractor.py:228` - Observation payload fields available before canonical creation.
  - Test: `tests/test_intelligence_merge.py:131` - Existing slang normalized-key merge baseline.
  - Test: `tests/test_intelligence_merge.py:169` - Existing semantic-related-candidate behavior that must remain for non-merge cases.
  - Test: `tests/test_intelligence_merge.py:220` - Evidence-count/confidence merge assertions to preserve.

  **Acceptance Criteria** (agent-executable only):
  - [ ] Equivalent slang observations merge into the existing canonical slang entry when similarity and label guardrails pass.
  - [ ] Non-qualifying candidates remain separate entries and still produce related-candidate links later in the pipeline.
  - [ ] Channel entries remain exact-only and existing tests keep passing.
  - [ ] `uv run pytest tests/test_intelligence_merge.py -v`

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Synonymous slang merges automatically under strict threshold
    Tool: Bash
    Steps: Run `uv run pytest tests/test_intelligence_merge.py -v`
    Expected: Added tests prove slang observations with similarity >= 0.92 and matching label merge into one canonical entry with merged aliases/evidence.
    Evidence: .sisyphus/evidence/task-3-semantic-merge.log

  Scenario: Embedding outage falls back to safe separate-entry behavior
    Tool: Bash
    Steps: Run `uv run pytest tests/test_intelligence_merge.py -k fallback -v`
    Expected: Edge-case tests prove merge engine creates a new slang entry and does not crash or cross-merge when embedding lookup is unavailable.
    Evidence: .sisyphus/evidence/task-3-semantic-merge-error.log
  ```

  **Commit**: NO | Message: `feat(intelligence): auto-merge equivalent slang` | Files: `crypto_news_analyzer/intelligence/merge.py`, `crypto_news_analyzer/intelligence/pipeline.py`, `tests/test_intelligence_merge.py`

- [x] 4. Implement repository query semantics for discovery, follow state, and hidden slang

  **What to do**: Extend repository/storage contracts so callers can (a) list one-time discovery slang entries, (b) mark discovery entries as presented, (c) follow/unfollow an entry by toggling `tracking_enabled`, and (d) filter ordinary list/search results so untracked slang is hidden by default while channels remain visible. Use `tracking_scope` values `following`, `discovery`, and `all`; make `following` the default for ordinary list/search. `discovery` must return only `slang` entries with `tracking_enabled=False`, `is_ignored=False`, and `discovery_presented_at IS NULL`, then mark those IDs with the current timestamp after the page payload is assembled successfully.
  **Must NOT do**: Do not make ordinary list/search side-effectful. Do not apply discovery semantics to channels. Do not make unfollow reset `discovery_presented_at` back to null.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: query contract changes propagate through both SQLite and API/Telegram callers.
  - Skills: `[]` - No special skill required.
  - Omitted: `['playwright']` - Backend-only contract work.

  **Parallelization**: Can Parallel: NO | Wave 2 | Blocks: 5, 6, 8 | Blocked By: 1, 3

  **References** (executor has NO interview context - be exhaustive):
  - API/Type: `crypto_news_analyzer/domain/repositories.py:461` - Existing list/count contracts to extend carefully.
  - API/Type: `crypto_news_analyzer/domain/repositories.py:481` - Existing ignore/unignore contract; keep separate from follow/unfollow.
  - Pattern: `crypto_news_analyzer/storage/repositories.py:542` - SQLite intelligence repository implementation hub.
  - Pattern: `crypto_news_analyzer/storage/repositories.py:702` - Existing semantic query pattern to mirror for filtered discovery/list behavior.
  - Pattern: `tests/test_intelligence_repositories.py:222` - Ignore lifecycle that must remain independent.
  - Test: `tests/test_intelligence_api.py:189` - Fake repository list/count filtering pattern used by API tests.
  - Test: `tests/test_intelligence_telegram_commands.py:237` - Recent-page payload/state expectations that discovery will replace.

  **Acceptance Criteria** (agent-executable only):
  - [ ] Repository exposes discovery listing, presentation marking, and follow/unfollow persistence.
  - [ ] Ordinary list/search queries default to followed entries plus channels and exclude untracked slang.
  - [ ] Discovery queries return only unseen untracked slang and do not re-return the same entry after presentation is marked.
  - [ ] `uv run pytest tests/test_intelligence_repositories.py -v`

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Discovery returns unseen slang once and follow state persists
    Tool: Bash
    Steps: Run `uv run pytest tests/test_intelligence_repositories.py -v`
    Expected: Added tests prove discovery returns only unpresented slang once, marks `discovery_presented_at`, and follow/unfollow toggles `tracking_enabled` without altering ignore state.
    Evidence: .sisyphus/evidence/task-4-query-semantics.log

  Scenario: Unfollowed slang stays hidden from ordinary search/list queries
    Tool: Bash
    Steps: Run `uv run pytest tests/test_intelligence_repositories.py -k tracking -v`
    Expected: Edge-case tests prove untracked slang is excluded from default list/search while channels continue to appear.
    Evidence: .sisyphus/evidence/task-4-query-semantics-error.log
  ```

  **Commit**: NO | Message: `feat(intelligence): add discovery and follow query semantics` | Files: `crypto_news_analyzer/domain/repositories.py`, `crypto_news_analyzer/storage/data_manager.py`, `crypto_news_analyzer/storage/repositories.py`, `tests/test_intelligence_repositories.py`

- [x] 5. Update HTTP intelligence endpoints for discovery, follow, and full evidence detail

  **What to do**: Add `GET /intelligence/discovery` for one-time slang discovery, `POST /intelligence/entries/{entry_id}/follow`, and `POST /intelligence/entries/{entry_id}/unfollow`. Extend `GET /intelligence/entries` and `GET /intelligence/search` to accept `tracking_scope` (default `following`). Extend `GET /intelligence/entries/{entry_id}` so detail responses return paginated evidence groups with fields for anchor raw item, neighboring raw items, `evidence_page`, `evidence_page_size`, and `evidence_total`. Keep `GET /intelligence/raw/{raw_item_id}` as the single-raw fallback and keep ignore endpoints intact for hard suppression.
  **Must NOT do**: Do not break existing bearer auth or ignored-entry endpoints. Do not expose untracked slang in default search/list responses. Do not omit expired-evidence warnings when the anchor raw text has already been purged.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: multiple response models and endpoint behaviors change together.
  - Skills: `[]` - Existing FastAPI patterns are sufficient.
  - Omitted: `['playwright']` - HTTP behavior can be fully verified by API tests.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: 8 | Blocked By: 1, 2, 3, 4

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `crypto_news_analyzer/api_server.py:1347` - Canonical list endpoint entry point.
  - Pattern: `crypto_news_analyzer/api_server.py:1384` - Existing ignored-list endpoint to preserve.
  - Pattern: `crypto_news_analyzer/api_server.py:1446` - Existing ignore mutation endpoint style.
  - Pattern: `crypto_news_analyzer/api_server.py:1499` - Existing detail endpoint with optional raw evidence.
  - Pattern: `crypto_news_analyzer/api_server.py:1544` - Search endpoint entry point.
  - Pattern: `crypto_news_analyzer/api_server.py:1600` - Raw-item endpoint to keep intact.
  - Test: `tests/test_intelligence_api.py:25` - Authorized request pattern.
  - Test: `tests/test_intelligence_api.py:105` - Fake repository used to encode new endpoint semantics.

  **Acceptance Criteria** (agent-executable only):
  - [ ] Discovery endpoint returns only unseen untracked slang and marks presentation after response assembly.
  - [ ] Follow/unfollow endpoints mutate `tracking_enabled` and leave `is_ignored` untouched.
  - [ ] Detail endpoint returns 5 evidence groups by default and includes neighbor context for each anchor.
  - [ ] Default list/search responses exclude untracked slang unless `tracking_scope=all` or `tracking_scope=discovery` is explicitly requested.
  - [ ] `uv run pytest tests/test_intelligence_api.py -v`

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: API discovery and follow flow works end-to-end
    Tool: Bash
    Steps: Run `uv run pytest tests/test_intelligence_api.py -v`
    Expected: Added API tests prove discovery returns untracked slang once, follow/unfollow endpoints update state, and default search/list hide untracked slang.
    Evidence: .sisyphus/evidence/task-5-http-api.log

  Scenario: Detail endpoint preserves expired-evidence warnings and paginates anchors
    Tool: Bash
    Steps: Run `uv run pytest tests/test_intelligence_api.py -k detail -v`
    Expected: Edge-case tests prove expired anchor evidence is still represented safely and page 2 returns the next evidence-anchor batch without duplication.
    Evidence: .sisyphus/evidence/task-5-http-api-error.log
  ```

  **Commit**: NO | Message: `feat(intelligence): refresh intelligence http endpoints` | Files: `crypto_news_analyzer/api_server.py`, `crypto_news_analyzer/domain/repositories.py`, `crypto_news_analyzer/storage/repositories.py`, `tests/test_intelligence_api.py`

- [x] 6. Rework Telegram intelligence commands around follow-first discovery

  **What to do**: Update Telegram command registration and callback handling to add `/intel_follow` and `/intel_unfollow`, keep `/intel_ignored` + `/intel_unignore` for legacy hard suppression, and convert `/intel_recent` into a one-time discovery inbox for untracked slang. `intel_recent` should page over discovery entries, show a Follow button instead of Ignore, and mark the page’s discovery entries as presented after the page payload is built. `intel_search` should default to followed entries only. `intel_detail` should render paginated evidence groups and their neighboring raw context, with callback pagination reusing stored state tokens.
  **Must NOT do**: Do not remove existing auth checks. Do not drop ignored/unignore admin flows. Do not send untracked slang back into `/intel_recent` after it has been shown once.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: stateful Telegram pagination/callback flow plus formatting changes.
  - Skills: `[]` - Existing callback-state cache already exists.
  - Omitted: `['playwright']` - Telegram is verified by unit tests and callback payload assertions.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: 8 | Blocked By: 1, 2, 4, 5

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `crypto_news_analyzer/reporters/telegram_command_handler.py:73` - Existing intelligence page size constant already matches the required 5-group default.
  - Pattern: `crypto_news_analyzer/reporters/telegram_command_handler.py:196` - Command registration block to extend.
  - Pattern: `crypto_news_analyzer/reporters/telegram_command_handler.py:218` - Callback query routing pattern to expand.
  - Pattern: `tests/test_intelligence_telegram_commands.py:88` - Command registration assertions.
  - Test: `tests/test_intelligence_telegram_commands.py:237` - Recent-page payload/state behavior to update.
  - Test: `tests/test_intelligence_telegram_commands.py:281` - Ignored-list behavior that must keep working.
  - Test: `tests/test_intelligence_telegram_commands.py:344` - Existing detail raw-evidence rendering baseline.
  - Test: `tests/test_intelligence_telegram_commands.py:377` - Callback dispatch pattern for detail/action flows.

  **Acceptance Criteria** (agent-executable only):
  - [ ] `/intel_recent` emits follow-first discovery cards and does not reuse already-presented untracked slang.
  - [ ] `/intel_search` hides untracked slang by default and can still show followed slang plus channels.
  - [ ] `/intel_detail` paginates evidence groups with nearby context and callback state remains valid across pages.
  - [ ] `uv run pytest tests/test_intelligence_telegram_commands.py -v`

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Telegram discovery inbox renders follow buttons and stable callback state
    Tool: Bash
    Steps: Run `uv run pytest tests/test_intelligence_telegram_commands.py -v`
    Expected: Added tests prove `/intel_recent` returns discovery payloads, callback tokens stay valid, and `/intel_follow` updates tracking state.
    Evidence: .sisyphus/evidence/task-6-telegram.log

  Scenario: Legacy ignore admin flow still works beside follow flow
    Tool: Bash
    Steps: Run `uv run pytest tests/test_intelligence_telegram_commands.py -k ignore -v`
    Expected: Edge-case tests prove ignored/unignore commands and callbacks still function and are not conflated with follow/unfollow.
    Evidence: .sisyphus/evidence/task-6-telegram-error.log
  ```

  **Commit**: NO | Message: `feat(intelligence): update telegram discovery workflow` | Files: `crypto_news_analyzer/reporters/telegram_command_handler.py`, `tests/test_intelligence_telegram_commands.py`

- [x] 7. Pre-filter ingestion batches with untracked/ignored slang dictionary

  **What to do**: Add a deterministic pre-filter step before LLM extraction for intelligence ingestion. Build two normalized dictionaries from canonical `slang` entries: `untracked_or_ignored_terms` from entries where `tracking_enabled=False OR is_ignored=True`, and `followed_terms` from `tracking_enabled=True AND is_ignored=False`. Normalize candidate terms using the same slang normalization logic used by merge. Skip a raw item only when its normalized text matches at least one `untracked_or_ignored_term` and zero `followed_terms`. Log skipped counts and matched terms, and surface the skip count in pipeline results. Leave mixed-signal raw items in the batch so followed slang still gets analyzed.
  **Must NOT do**: Do not pre-filter channels. Do not drop items that contain both tracked and untracked slang markers. Do not move this logic into the HTTP `/analyze` news-analysis path.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: ingestion runtime behavior and extraction batching must stay deterministic.
  - Skills: `[]` - Existing pipeline/extractor seams are sufficient.
  - Omitted: `['llm-instructor']` - No new instructor schema work.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: 8 | Blocked By: 1, 3

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `crypto_news_analyzer/intelligence/pipeline.py:35` - Collection result payload where skip counts can be surfaced.
  - Pattern: `crypto_news_analyzer/intelligence/pipeline.py:72` - Per-source ingestion flow to insert filtering before extraction.
  - Pattern: `crypto_news_analyzer/analyzers/intelligence_extractor.py:169` - Extractor input contract that should receive only retained raw items.
  - Pattern: `crypto_news_analyzer/analyzers/intelligence_extractor.py:228` - Current full-batch prompt payload construction.
  - Pattern: `crypto_news_analyzer/intelligence/merge.py:25` - Reuse the same normalization rules for slang matching.
  - Test: `tests/test_intelligence_extraction.py:39` - Fake repository/client pattern for extraction-batch assertions.
  - Test: `tests/test_intelligence_ingestion_runtime.py:1` - Runtime pipeline test harness.

  **Acceptance Criteria** (agent-executable only):
  - [ ] Ingestion skips raw items containing only untracked/ignored slang markers before LLM extraction.
  - [ ] Mixed items containing any followed slang marker still reach extraction.
  - [ ] Pipeline result includes a deterministic skipped-item count and tests cover the guardrails.
  - [ ] `uv run pytest tests/test_intelligence_extraction.py tests/test_intelligence_ingestion_runtime.py -v`

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Purely untracked slang raw items are removed before prompt batching
    Tool: Bash
    Steps: Run `uv run pytest tests/test_intelligence_extraction.py tests/test_intelligence_ingestion_runtime.py -v`
    Expected: Added tests prove skipped raw items never enter `_build_messages` payloads and pipeline metrics report the skip count.
    Evidence: .sisyphus/evidence/task-7-prefilter.log

  Scenario: Mixed tracked/untracked slang text is retained for safety
    Tool: Bash
    Steps: Run `uv run pytest tests/test_intelligence_ingestion_runtime.py -k mixed -v`
    Expected: Edge-case tests prove a raw item mentioning any followed slang still reaches extraction even if it also contains untracked slang variants.
    Evidence: .sisyphus/evidence/task-7-prefilter-error.log
  ```

  **Commit**: NO | Message: `feat(intelligence): prefilter untracked slang before extraction` | Files: `crypto_news_analyzer/intelligence/pipeline.py`, `crypto_news_analyzer/analyzers/intelligence_extractor.py`, `tests/test_intelligence_extraction.py`, `tests/test_intelligence_ingestion_runtime.py`

- [x] 8. Lock in cross-surface regression and migration safety

  **What to do**: Add final regression coverage tying together migration defaults, semantic slang merge, discovery consumption, follow/unfollow behavior, evidence pagination, and ingestion pre-filtering. Cover both SQLite unit paths and PostgreSQL/pgvector integration paths where available. Validate that channel behavior, legacy ignore flows, and raw TTL expiry behavior remain unchanged except where explicitly planned.
  **Must NOT do**: Do not add flaky network-dependent tests. Do not require manual Telegram/API verification to declare the task done. Do not weaken existing security/auth tests.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: broad regression task spanning several already-modified subsystems.
  - Skills: `[]` - Existing pytest infrastructure is enough.
  - Omitted: `['playwright']` - No browser UI exists for this feature.

  **Parallelization**: Can Parallel: NO | Wave 3 | Blocks: final verification only | Blocked By: 1, 2, 3, 4, 5, 6, 7

  **References** (executor has NO interview context - be exhaustive):
  - Test: `tests/test_intelligence_merge.py:93` - Existing exact-merge baseline for channels/usernames.
  - Test: `tests/test_intelligence_merge.py:169` - Existing semantic-related-candidate non-merge baseline.
  - Test: `tests/test_intelligence_api.py:105` - Fake repository API harness.
  - Test: `tests/test_intelligence_telegram_commands.py:88` - Telegram command registration and callback harness.
  - Test: `tests/test_intelligence_repositories.py:22` - Storage contract round-trip harness.
  - Test: `tests/test_intelligence_extraction.py:16` - Fake OpenAI client pattern for prompt/input assertions.
  - Test: `tests/test_intelligence_ingestion_runtime.py:1` - End-to-end intelligence ingestion runtime tests.
  - Test: `tests/integration/test_intelligence_pgvector.py:1` - Real PostgreSQL/pgvector validation path when configured.

  **Acceptance Criteria** (agent-executable only):
  - [ ] Full targeted suite passes on SQLite-backed tests.
  - [ ] pgvector integration tests pass when `TEST_DATABASE_URL` is available.
  - [ ] Added regressions explicitly prove channel behavior and ignore lifecycle remain unchanged.
  - [ ] `uv run pytest tests/test_intelligence_models.py tests/test_intelligence_repositories.py tests/test_intelligence_merge.py tests/test_intelligence_extraction.py tests/test_intelligence_api.py tests/test_intelligence_telegram_commands.py tests/test_intelligence_ingestion_runtime.py -v`
  - [ ] `uv run pytest tests/integration/test_intelligence_pgvector.py -v` (only when `TEST_DATABASE_URL` is configured)

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Targeted intelligence suite passes after all feature changes
    Tool: Bash
    Steps: Run `uv run pytest tests/test_intelligence_models.py tests/test_intelligence_repositories.py tests/test_intelligence_merge.py tests/test_intelligence_extraction.py tests/test_intelligence_api.py tests/test_intelligence_telegram_commands.py tests/test_intelligence_ingestion_runtime.py -v`
    Expected: All targeted tests pass with new discovery/follow/evidence/prefilter semantics and preserved channel/ignore behavior.
    Evidence: .sisyphus/evidence/task-8-regression.log

  Scenario: Pgvector-specific merge/search paths remain valid
    Tool: Bash
    Steps: Run `uv run pytest tests/integration/test_intelligence_pgvector.py -v`
    Expected: If `TEST_DATABASE_URL` is configured, integration tests pass; otherwise the task documents the environment-gated skip without treating it as a feature failure.
    Evidence: .sisyphus/evidence/task-8-regression-error.log
  ```

  **Commit**: NO | Message: `test(intelligence): cover discovery and evidence regressions` | Files: `tests/test_intelligence_models.py`, `tests/test_intelligence_repositories.py`, `tests/test_intelligence_merge.py`, `tests/test_intelligence_extraction.py`, `tests/test_intelligence_api.py`, `tests/test_intelligence_telegram_commands.py`, `tests/test_intelligence_ingestion_runtime.py`, `tests/integration/test_intelligence_pgvector.py`

## Final Verification Wave (MANDATORY — after ALL implementation tasks)
> 4 review agents run in PARALLEL. ALL must APPROVE. Present consolidated results to user and get explicit "okay" before completing.
> **Do NOT auto-proceed after verification. Wait for user's explicit approval before marking work complete.**
> **Never mark F1-F4 as checked before getting user's okay.** Rejection or user feedback -> fix -> re-run -> present again -> wait for okay.
- [x] F1. Plan Compliance Audit — oracle
- [x] F2. Code Quality Review — unspecified-high
- [x] F3. Real Manual QA — unspecified-high (+ playwright if UI)
- [x] F4. Scope Fidelity Check — deep

## Commit Strategy
- Create one final atomic commit after F1-F4 approval: `feat(intelligence): streamline slang tracking and evidence context`
- Do not commit partial schema/API/Telegram states that break recent/search semantics.

## Success Criteria
- New slang no longer floods search or repeated tracking by default.
- Equivalent slang variants converge into one canonical slang entry under the strict merge guardrails.
- Entry detail exposes complete evidence provenance with nearby raw context.
- Untracked/ignored slang meaningfully reduces ingestion LLM input volume without regressing tracked discoveries.
