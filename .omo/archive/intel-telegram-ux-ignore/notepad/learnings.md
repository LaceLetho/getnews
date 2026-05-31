## Task 1: Canonical Intelligence Ignore State

### Pattern: SQLite boolean storage
SQLite stores booleans as integers (0/1). When deserializing via row dict, they come back as Python ints 0/1, not bools. Must explicitly coerce `bool(data["is_ignored"])` in `_serialize_canonical_intelligence_entry_row` to ensure `from_dict` receives proper True/False values.

### Pattern: Datetime serialization in canonical entries
New datetime field `ignored_at` must be added to both `to_dict()` and `from_dict()` datetime key lists in `CanonicalIntelligenceEntry`. The `_serialize_canonical_intelligence_entry_row` handles it automatically via `_dt_out()` which iterates all row keys.

### Pattern: Adding columns to existing upsert
When adding columns to `upsert_canonical_intelligence_entry`, order in the `columns` list must match the INSERT order. The ON CONFLICT DO UPDATE uses `columns[1:]` for SET assignments.

### Pattern: Filter clause placement
For `is_ignored = FALSE` filter in list/count methods, added as the first filter clause in the `filters` list with `params.append(False)` before any conditional filters. This ensures consistent SQL construction: `WHERE is_ignored = ? AND [optional filters]`.

### Pattern: Ignore/unignore with atomic SELECT-after-UPDATE
Both `ignore_canonical_intelligence_entry` and `unignore_canonical_intelligence_entry` use UPDATE → check rowcount → SELECT in the same transaction (same `with self._lock` / `with conn` block) to return the updated row atomically.

### Files modified
- `domain/models.py` - 3 new fields + datetime serialization
- `domain/repositories.py` - 4 new abstract methods
- `storage/repositories.py` - 4 new concrete delegations
- `storage/data_manager.py` - schema init, serialization, filters, 4 new methods
- `migrations/postgresql/003_intelligence_schema.sql` - 3 new columns + index
- `migrations/postgresql/004_intelligence_ignore_state.sql` - NEW migration
- `tests/test_intelligence_repositories.py` - 2 new tests (6 total, all passing)

## Task 2: Intelligence API Ignore Endpoints

### Pattern: FastAPI path conflict prevention
`/intelligence/entries/ignored` must be registered before `/intelligence/entries/{entry_id}` so FastAPI doesn't treat `ignored` as a detail ID.

### Pattern: Optional body for idempotent ignore
`POST /intelligence/entries/{entry_id}/ignore` accepts an optional JSON body and falls back to `ignored_by="api"` when omitted.

### Pattern: Shared ignore serialization helper
Added `_datetime_to_iso()` so `ignored_at` is serialized consistently in list, detail, ignore, unignore, and search responses.

### Pattern: Test repository must mirror ignored filtering
The in-memory intelligence repository used by API tests must exclude ignored entries from list/count/search paths while still allowing exact lookups and ignored-list queries.

### Task 2: Semantic search ignore coverage

### Pattern: Test double must mirror production ignore filters
The in-memory intelligence repository used by API tests needs to filter out `is_ignored` entries in both `count_semantic_search_candidates()` and `semantic_search()`; otherwise the API tests can pass against the service layer while still masking a repository regression.

### Pattern: Search semantics verified at API boundary
The `/intelligence/search` API test should assert both `total` and `results` when entries are ignored. This catches cases where ignored rows leak into pagination or counting even if the ranking order looks correct.

## Task 3: Ignore-aware intelligence ingestion

### Pattern: Ignored canonical entries still complete observation lifecycle
When canonicalization finds an ignored canonical entry by `(entry_type, normalized_key)`, mark the observation canonicalized and return the existing entry for pipeline accounting, but skip `_merge_observation_into_entry()` and `upsert_canonical_entry()`. This prevents ignored-period evidence from mutating the canonical row while still avoiding repeated extraction/canonicalization attempts.

### Pattern: Embedding work filters active entries in pipeline
`IntelligencePipeline._generate_embeddings()` filters `canonical_entries` to entries where `is_ignored` is false before calling `batch_generate_embeddings()`. This lets merge return ignored entries for dedupe/accounting without causing embedding refreshes.

### Pattern: Runtime tests need real merge engine for ignore behavior
The ingestion runtime tests normally mock the merge engine. Ignore/unignore regression coverage uses `IntelligenceMergeEngine` with an enriched `MemoryIntelligenceRepository` stub so tests can assert no duplicate normalized-key entry, canonicalized observations, immutable ignored fields, and future-only updates after unignore.

### Task 3: Telegram callback plumbing

### Pattern: Keep callback payloads compact
Telegram callback data should stay prefix-stable and short: `intel:d:<uuid>`, `intel:i:<uuid>`, `intel:u:<uuid>`, `intel:p:<token>:<page>`. Ten-ish char URL-safe tokens are enough for pagination state lookup while keeping payloads under the 64-byte ceiling.

### Pattern: TTL state for pagination
Store pagination metadata in-memory with `stored_at`, `kind`, `query/window/label/page_size`, `chat_id`, and `user_id`. On callback, lazily reject stale tokens after 900 seconds and respond with a retry message.

### Pattern: Callback auth must mirror command auth
Callback queries must reuse the same `is_authorized_user()` and `check_rate_limit()` gates as commands. Unauthorized callbacks should be answered immediately and must not reach repository mutations.

### Task 4: Inline keyboard intel lists

### Pattern: Recent/search/ignored lists can share one keyboard builder
Build one helper that emits per-entry rows plus a final pagination row. Reuse it for `/intel_recent`, `/intel_search`, and `/intel_ignored`; only the action button label/callback changes (`忽略` vs `恢复`).

### Pattern: Ignored listing uses zero-based repository paging
`list_ignored_canonical_entries()` expects `page=0` for the first page, unlike the visible Telegram commands which are 1-based. Translate `page -> page - 1` at the repository boundary and keep the callback state/user-facing page 1-based.

## Validation pass notes

### Verified callback payload sizes
- `intel:d:<uuid>` / `intel:i:<uuid>` / `intel:u:<uuid>` stay at 44 bytes for a 36-char UUID.
- `intel:p:<10-char-token>:<page>` stays well under the 64-byte Telegram ceiling.

### Lint cleanup
- Wrapped the new intelligence index SQL strings and pagination param list in `storage/data_manager.py` to avoid introducing fresh flake8 E501 violations in the modified section.

### Test signal
- `tests/test_intelligence_telegram_commands.py` passed end-to-end after the changes.

## QA Verification (2026-05-06)

### 1. Intelligence Test Suite: ✅ ALL 66 PASSED
`pytest tests/test_intelligence_repositories.py tests/test_intelligence_api.py tests/test_intelligence_telegram_commands.py tests/test_intelligence_ingestion_runtime.py -v`
- 66 collected, 66 passed in 8.16s. Zero failures, zero errors.

### 2. Broader Regression Suite: ✅ NO INTELLIGENCE REGRESSIONS
`pytest tests/ --ignore=tests/integration -q`
- 922 passed, 72 failed in 159.52s
- All 72 failures are pre-existing, in files unrelated to intelligence:
  test_telegram_command_handler_semantic_search, test_telegram_command_pbt,
  test_telegram_formatter, test_telegram_report_properties, test_timezone_integration,
  test_bird_dependency_unit, test_bird_integration_properties, test_category_parser,
  test_datasource_bootstrap, test_extensibility_unit
- None of these test files touch intelligence ignore code paths.

### 3. API Response Shapes: ✅ IGNORE FIELDS ON ALL MODELS
All four intelligence response models carry is_ignored, ignored_at, ignored_by:
- IntelligenceEntryResponse (L352-354) — used by /entries list
- IntelligenceEntryDetailResponse (L384-386) — used by /entries/{id} detail
- IntelligenceSearchResultItem (L403-405) — used by /search results
- IntelligenceIgnoreResponse (L411-413) — used by /ignore and /unignore

All response serializers include ignore fields:
- _canonical_entry_to_response() (L469-471)
- _canonical_entry_to_detail_response() (L496-498)
- ignore_intelligence_entry() (L1422-1424)
- unignore_intelligence_entry() (L1440-1442)

### 4. Callback Payload Size: ✅ ALL UNDER 64 BYTES
Entry IDs are uuid.uuid4() (36 chars, no prefix).
- intel:d:<uuid> = 44 bytes ✅
- intel:i:<uuid> = 44 bytes ✅
- intel:u:<uuid> = 44 bytes ✅
- intel:p:<10-char-token>:<page> = ~22 bytes ✅

### 5. Pagination State TTL: ✅ 900 SECONDS (15 MINUTES)
Verified in telegram_command_handler.py:
- _cleanup_expired_callback_state() L229: `now - stored_at > 900`
- _get_callback_state() L246: `time.time() - stored_at > 900`
Both use 900 seconds = exactly 15 minutes.

### 6. Migration Idempotency: ✅ IF NOT EXISTS
`migrations/postgresql/004_intelligence_ignore_state.sql`:
- `ADD COLUMN IF NOT EXISTS` on all three columns
- `CREATE INDEX IF NOT EXISTS` on the is_ignored index
Fully idempotent — safe to re-run.

### 7. Ignore Fields Coverage: ✅ MODEL → SCHEMA → SERIALIZERS
- domain/models.py L844-846: CanonicalIntelligenceEntry dataclass fields
- domain/models.py L902, L916: to_dict()/from_dict() serialize/deserialize ignored_at
- storage/data_manager.py L492-494: DDL column definitions (is_ignored, ignored_at, ignored_by)
- storage/data_manager.py L2574-2576: upsert_canonical_intelligence_entry() column list
- storage/data_manager.py L2677, L2723: WHERE is_ignored = ? filters in list/count
- storage/data_manager.py L2818, L2848: embedding search ignores filtered entries
- storage/repositories.py L642: ignore_canonical_entry abstract + concrete delegation
- api_server.py: All 4 response models + 4 serializers include the fields

### LSP Diagnostics: ✅ CLEAN
- api_server.py, domain/models.py, storage/data_manager.py,
  storage/repositories.py, intelligence/merge.py, intelligence/pipeline.py:
  Zero errors.
- telegram_command_handler.py: pre-existing type-checker warnings only (optional access, missing generics) — none related to ignore feature.

### VERDICT: APPROVE
All 7 QA checks pass. No intelligence-related regressions found.

## Task 5: Plan compliance audit fixes

### Pattern: Labels should be data-backed, not enum-backed
When exposing intelligence labels in HTTP/Telegram, filter `PrimaryLabel` by `count_canonical_entries(primary_label=...)` so ignored-only labels do not appear.

### Pattern: Callback detail should match command detail defaults
Telegram detail callbacks should reuse the same plain detail formatter as `/intel_detail` unless raw evidence is explicitly requested.

### Pattern: Callback acks need explicit failure text
For unknown callback payloads, answer with a short error message instead of an empty ack so users get immediate feedback.

### Pattern: Keep helper names unique
Duplicate helper definitions like `_datetime_to_iso` can trigger F811; remove the later copy and keep a single shared serializer.
