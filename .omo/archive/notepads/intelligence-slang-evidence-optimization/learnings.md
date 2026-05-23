# Learnings

## Task 1 - Tracking State
- Added global canonical tracking fields with type-aware defaults: channels track by default, slang starts untracked, ignored rows stay untracked.
- SQLite initialization can add and backfill tracking columns on existing intelligence databases while preserving ignored state.

## Task 1 QA Retry - Tracking Backfill Idempotency
- Fixed recurring SQLite startup backfill by running channel/slang/ignored tracking initialization only when the tracking column is newly added. PostgreSQL runtime ensure now only adds missing columns; rollout backfill remains in migration SQL.
- Added restart regression coverage proving manually followed slang and manually unfollowed channels survive a subsequent DataManager initialization.

## Task 2 - Evidence Links
- Added dedicated evidence anchors so canonical entries can retain multiple raw provenance rows instead of relying on `latest_raw_item_id` history.
- Raw context windows are scoped by source/conversation tuple and ordered by `COALESCE(published_at, collected_at), id` to keep anchor neighborhoods deterministic.

## Task 3 - Slang Semantic Merge
- Reused the existing IntelligenceSearchService semantic_search surface inside the merge engine so slang candidates are resolved before creating a new canonical row.
- Exact alias lookup is intentionally scoped to slang so channel canonicalization remains exact-key only.

## Task 4 - Query Semantics
- Repository ordinary list/count/semantic search now default to `tracking_scope="following"`, which keeps channels visible while hiding untracked slang.
- Discovery is represented as `tracking_scope="discovery"` and is side-effect-free until callers explicitly invoke `mark_discovery_presented` after payload assembly.

## Task 7 - Ingestion Slang Prefilter
- Intelligence ingestion now filters newly saved raw items before extractor batching, so standard HTTP analysis and extractor schemas remain unchanged.
- The skip dictionary must include slang display names, aliases, and normalized keys, while channels are excluded entirely from prefilter decisions.

## Task 5 - HTTP Intelligence API
- Discovery uses the repository discovery scope and marks entries presented only after the response payload is assembled.
- List and search default to following scope; explicit all/discovery scopes expose the corresponding repository views.
- Detail responses page evidence anchors separately from legacy raw fallback and include anchor context windows for provenance review.

## Task 6 - Telegram Follow-First Discovery
- Telegram `/intel_recent` now uses discovery tracking scope and presents Follow actions while deferring `mark_discovery_presented` until after page payload/callback state assembly in the async surface.
- Telegram `/intel_search` explicitly searches the default followed scope, matching repository semantics that hide untracked slang unless discovery is requested elsewhere.
- Telegram detail rendering now pages evidence anchors in groups of 5 and requests 10-item before/after raw context around each anchor.

## Task 8 - Cross-Surface Regression
- Added final regression guardrails around exact-only channel merge behavior, raw TTL evidence association preservation, and following-scope visibility across HTTP list/search.
- The required SQLite-backed intelligence regression suite writes to `.sisyphus/evidence/task-8-regression.log` and currently passes 122 tests.

## Task F3 - Real Manual QA
- Focused HTTP QA passed for default following visibility, one-time discovery presentation, follow/unfollow state separation, evidence-context detail pagination, and semantic-search discovery scope.
- Focused Telegram QA passed for `/intel_recent` discovery payload/state assembly, deferred presentation marking, follow/unfollow buttons and callbacks, and evidence detail pagination callbacks.
- Remediation checks passed for untracked slang semantic merge using `tracking_scope="all"` and Telegram detail callback state typing/pagination behavior.

## Final Wave Completion - 2026-05-10
- F1-F4 were marked complete after all reviewers returned APPROVE and the targeted intelligence suite passed with 123 tests.
- Pgvector integration remains environment-gated because TEST_DATABASE_URL is not configured.
