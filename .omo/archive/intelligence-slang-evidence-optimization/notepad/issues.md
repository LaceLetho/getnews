# Issues

## Task 1 - Tracking State
- `lsp_diagnostics` could not run because `basedpyright-langserver` is not installed in this environment. Required pytest verification passed.

## Task 1 QA Retry - Tracking Backfill Idempotency
- Atlas QA found runtime schema ensure was resetting explicit tracking state on every startup. The retry scopes SQLite backfill to first column addition and keeps PostgreSQL runtime ensure non-destructive.

## Task 1 QA Retry - Optional Checkpoint Access
- Resolved the basedpyright optional-member diagnostic by narrowing `repository.get_checkpoint(...)` with a non-None assertion before reading `checkpoint_data`.

## Task 1 QA Retry - Dict Row Monkeypatch Typing
- Resolved changed-file basedpyright errors by initializing `DictRowContext.inner` and using `setattr` for the test-only `_get_connection` monkeypatch while preserving dict-row lookup behavior.

## Task 2 - Evidence Links
- Resolved a changed-file basedpyright cursor-binding error in `DataManager.upsert_canonical_intelligence_entry`; final changed-file error diagnostics are clean.

## Task 3 - Slang Semantic Merge
- Initial verification caught over-broad exact alias matching for channels; narrowed alias matching to slang to preserve channel exact-key behavior.
- Initial ignored-candidate test expectation counted active entries only; adjusted the guardrail test to match repository listing semantics after confirming ignored entries are hidden from active lists.

## Task 4 - Query Semantics
- Initial verification exposed the SQLite semantic-search fallback still using the default following scope when `tracking_scope="all"`; fixed by passing the requested scope into the fallback list query.

## Task 7 - Ingestion Slang Prefilter
- Initial verification exposed the in-memory runtime harness did not accept the merge engine's `observation_id` keyword when upserting canonical entries; updated the harness to match the production repository contract.
- `rg` is not installed in this environment, so changed-file marker scanning used the project grep tool instead.

## Task 5 - HTTP Intelligence API
- Initial focused verification caught tests that still assumed untracked slang appeared in default list/search scopes; updated those tests to use explicit all scope where needed.
- Initial detail-warning setup attempted to construct an invalid empty raw_text item; fixed by simulating purged text after valid raw item creation.

## Task 5 QA Retry - Evidence Context Size
- Atlas QA found the detail endpoint requested only 2 raw context items before/after each evidence anchor; updated the API and regression assertion to request 10 before and 10 after while preserving 5 evidence groups per page.

## Task 7 QA Retry - Prefilter Basedpyright Cleanup
- Resolved changed-file basedpyright errors by normalizing optional raw text through an empty-string fallback, casting dynamic repository list results to iterables, and narrowing optional runtime test fixtures before field access.

## Task 6 - Telegram Verification Notes
- Changed-file `lsp_diagnostics` is clean for `tests/test_intelligence_telegram_commands.py`; `telegram_command_handler.py` still reports existing broad basedpyright errors unrelated to this task.
- Changed-file marker scan still matches the pre-existing datasource help example `ds-xxx`; no new TODO/FIXME/HACK/debug markers were added.

## Task 8 - Verification Notes
- Initial full-suite run exposed older slang merge tests still reading the default following scope; updated those tests to use explicit all scope for untracked slang assertions.
- Pgvector integration verification was skipped because `TEST_DATABASE_URL` is not configured; the skip note is recorded in `.sisyphus/evidence/task-8-regression-error.log`.

## Final Verification Wave - Slang Semantic Scope
- Fixed semantic slang auto-merge to search `tracking_scope="all"` while retaining explicit ignored-candidate rejection, and added regression coverage for untracked non-ignored slang candidates merging at 0.93 similarity with matching primary label.
- Fixed the Telegram pagination callback helper's bare `state: dict` annotation to `dict[str, Any]`; changed-line diagnostics no longer include the final-wave bare-dict issue.

## F4 Scope Fidelity Check
- Approved post-remediation state: implementation remains scoped to intelligence slang tracking/evidence/deduplication, includes semantic slang candidate search with `tracking_scope="all"`, preserves exact-only channel merge behavior, and does not reposition legacy API runtime behavior.
- Focused verification passed for models/repositories, merge/extraction, API/Telegram, and ingestion runtime suites via `/data/.local/bin/uv`; pgvector integration was skipped because `TEST_DATABASE_URL` is not configured.
- LSP diagnostics still report broad pre-existing basedpyright warnings/errors in large legacy files such as `api_server.py`, `data_manager.py`, and `telegram_command_handler.py`; no scope-fidelity blocker was found in the reviewed implementation.

## F1 Plan Compliance Audit - Approval
- Re-audited the plan after final-wave remediation. The prior F1 blocker is resolved: `_find_semantic_slang_match` now passes `tracking_scope="all"`, still requires slang type, similarity >= 0.92, matching primary label, and rejects ignored candidates.
- Plan-level focused verification passed for models/repositories, merge/extraction, API/Telegram, and ingestion runtime. Pgvector integration remains environment-gated because `TEST_DATABASE_URL` is not configured.
- `telegram_command_handler.py` retains pre-existing basedpyright errors outside this final-wave blocker; the remediated pagination callback line is now `dict[str, Any]`.

## F2 Code Quality Review - 2026-05-10
- Reviewed current branch changes for the intelligence slang tracking/evidence/deduplication plan after remediation. No blocking code-quality, typing, maintainability, correctness, test-quality, or regression-risk issues found in the plan scope.
- Prior Telegram remediation is present at `crypto_news_analyzer/reporters/telegram_command_handler.py:525` with `state: dict[str, Any]`; remaining bare `dict` callback-state annotations are legacy/pre-existing and not introduced by this remediation.
- Targeted intelligence suite passed: `/data/.local/bin/uv run pytest tests/test_intelligence_models.py tests/test_intelligence_repositories.py tests/test_intelligence_merge.py tests/test_intelligence_extraction.py tests/test_intelligence_api.py tests/test_intelligence_telegram_commands.py tests/test_intelligence_ingestion_runtime.py -q`.
- Changed-file LSP diagnostics still report broad legacy basedpyright warnings/errors across existing modules, including pre-existing Telegram `Application` type-argument diagnostics; these were not treated as blockers because the targeted suite passes and the reviewed diff did not introduce a scoped blocking diagnostic.
