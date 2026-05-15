# Decisions

## Task 1 - Tracking State
- Kept `is_ignored` as hard suppression and modeled `tracking_enabled` as a separate discovery/follow state so later tasks can build follow/unfollow semantics without changing ignore behavior.
- Used an additive PostgreSQL rollout migration plus fresh-schema updates to keep new and existing deployments aligned.

## Task 2 - Evidence Links
- Evidence links use a unique `(entry_id, raw_item_id)` key and preserve the earliest observation provenance for repeated links to the same raw item.
- `save_canonical_entry` and `upsert_canonical_entry` accept optional `observation_id` for current canonicalization storage while exposing explicit evidence-link and context-window repository methods for later API/Telegram tasks.

## Task 3 - Slang Semantic Merge
- Semantic auto-merge is allowed only for slang entries at similarity >= 0.92 with matching primary_label, active candidate state, and non-channel candidate type.
- Canonical upserts now pass observation_id during merge canonicalization so evidence links are preserved for exact and semantic survivor updates.
- Embedding/search exceptions are treated as no-match outcomes so canonicalization safely creates a separate slang entry.

## Task 4 - Query Semantics
- Added repository-level `follow_canonical_entry`, `unfollow_canonical_entry`, and `mark_discovery_presented` methods rather than API or Telegram behavior, so Task 5 and Task 6 can consume the storage contract directly.
- Kept follow/unfollow independent from ignore/unignore: tracking toggles do not clear `is_ignored`, and unfollow does not reset `discovery_presented_at`.

## Task 7 - Ingestion Slang Prefilter
- Reused `IntelligenceMergeEngine.normalize_slang_key` directly for both candidate terms and raw text matching to keep merge and prefilter normalization identical.
- Kept mixed tracked/untracked raw items whenever any followed slang term matches, prioritizing recall over suppression when a followed marker is present.

## Task 5 - HTTP Intelligence API
- Follow/unfollow are independent tracking mutations and intentionally leave ignore state untouched.
- Evidence detail exposes paginated groups on the entry endpoint while keeping /intelligence/raw/{raw_item_id} as the single-item fallback.

## Task 6 - Telegram Follow-First Discovery
- Kept `/intel_follow` and `/intel_unfollow` as tracking-only operations; ignore/unignore remains the separate hard-suppression admin path.
- Reused existing Telegram callback state tokens for both discovery list pagination and detail evidence pagination instead of introducing a second pagination cache.

## Task 8 - Cross-Surface Regression
- Kept Task 8 changes test-only; no production behavior changes were needed after regression coverage passed.
- Used `tracking_scope="all"` in slang merge tests that need to inspect untracked canonical slang rows, preserving the production default that hides untracked slang.
