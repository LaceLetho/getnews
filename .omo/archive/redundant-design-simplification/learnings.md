# Learnings - Redundant Design Simplification

## 2026-06-05T08:10:00Z T2 Complete - Domain Model Simplification

### Changes Made

**`crypto_news_analyzer/domain/models.py`:**
- Removed `TopicLifecycleStatus.PAUSED = "paused"` (line 70). Enum now has only DRAFT, ACTIVE, ARCHIVED.
- Removed `IntelligenceTopic.is_active: bool = True` field (line 856). `lifecycle_status` is now the sole state source.
- Simplified `__post_init__`: removed all `is_active` derivation logic; now only validates `lifecycle_status` is in allowed values.
- Updated error message: "lifecycle_status must be one of: draft, active, archived" (removed "paused").
- Updated `from_dict`: removed `"is_active"` from `allowed` set, replaced backward-derivation fallback (`PAUSED` if `is_active` is falsy) with `ACTIVE` as default.
- `_TOPIC_LIFECYCLE_STATUS_VALUES` auto-updated to `{"draft", "active", "archived"}` via set comprehension.
- `to_dict()` naturally excludes `is_active` since it's no longer a dataclass field.

**Test files updated (4 files):**
- `tests/intelligence/test_intelligence_models.py:71-97` — replaced paused topic with archived, changed `is_active` assertions to `lifecycle_status` checks.
- `tests/intelligence/test_topic_research_scheduler.py:105-111,474-527` — updated `FakeTopicRepository.list_topics` to filter by `lifecycle_status == "active"`; removed paused_topic from `test_skips_inactive_topics`.
- `tests/intelligence/test_topic_datasource_api.py:45-58` — updated `InMemoryTopicDatasourceRepo.list_topics`/`count_topics` to filter by `lifecycle_status`.
- `tests/intelligence/test_topic_datasource_schema.py:36` — changed `int(topic.is_active)` to `1 if topic.lifecycle_status == "active" else 0`.

### Test Results
- All 62 affected tests pass (test_intelligence_models, test_topic_research_scheduler, test_topic_datasource_api, test_topic_datasource_schema).

### Blockers Cleared for T3/T4
- Domain model no longer references `PAUSED` or `is_active`.
- Remaining references (api_server.py pause endpoint, storage schema `is_active` column, Telegram commands) will be handled in T3 (storage) and T4 (API/Telegram).

### Subtlety
- `test_datasource_repository.py` and `test_api_server.py` still pass `"is_active": True` in dicts to `data_manager.upsert_intelligence_topic()`. These pass through the storage layer unchanged — `from_dict` now ignores `is_active`. The storage layer (T3) will need its own update to stop writing `is_active` to DB.
- `FakeTopicRepository` in-memory mocks retain `is_active` as a parameter name (for caller compatibility) but derive the filter from `lifecycle_status`.

## 2026-06-05 T2: Remove is_active and PAUSED from domain model

### Changes Made

**`crypto_news_analyzer/domain/models.py`:**
1. Removed `TopicLifecycleStatus.PAUSED = "paused"` — enum now: DRAFT, ACTIVE, ARCHIVED
2. Changed `_TOPIC_LIFECYCLE_STATUS_VALUES` from `{...}` to `frozenset({...})` — immutable
3. Removed `is_active: bool = True` field from `IntelligenceTopic` dataclass
4. Simplified `__post_init__`: removed entire is_active derivation block (lines 868-876 removed). Now only validates lifecycle_status membership.
5. Updated ValueError message: `"draft, active, paused, archived"` → `"draft, active, archived"`
6. Updated `from_dict`: removed `"is_active"` from `allowed` set; simplified `payload.setdefault` to just `TopicLifecycleStatus.ACTIVE.value` (no backward derivation from is_active)
7. `to_dict` uses `self.__dict__` — `is_active` no longer emitted (field removed)

**`tests/intelligence/test_intelligence_models.py`:**
- Line 74: Changed `"paused"` test case to `"archived"`
- Lines 92-93: Replaced `is_active` assertions with `lifecycle_status` assertions

### Verification
- `lsp_diagnostics`: clean (no new errors introduced)
- `uv run pytest tests/intelligence/test_intelligence_models.py -v`: 6/6 passed
- `uv run pytest tests/ -k "topic_lifecycle or is_active or TopicLifecycle" -v`: 1 selected, passed

### Remaining Out-of-File Callers (for T3/T4)
- `api_server.py:1915` — pause endpoint uses `TopicLifecycleStatus.PAUSED.value` (T4)
- `tests/intelligence/test_topic_research_scheduler.py:486` — uses `PAUSED.value` (T3)
- Storage layer (`is_active` column, index) — T3
- Repository layer (`is_active` parameter) — T3
- API response serialization (`is_active` dynamic read) — T4

## T5 Complete — Remove `MergePreviewState.EXPIRED`

**Changes Made:**
1. `domain/models.py:86-90` — Removed `EXPIRED = "expired"` from `MergePreviewState` enum. Enum now has: `PENDING`, `APPLIED`, `CANCELLED`.
2. `domain/models.py:1134` — Updated validation error message to reflect new state values.
3. `storage/repositories.py:1629-1633` — `accept_merge_preview` now simply returns `False` when expiry check fails, instead of mutating state to `"expired"`.

**Findings:**
- Zero callers of `MergePreviewState.EXPIRED` — the only reference was the raw string `"expired"` at `repositories.py:1632` (now removed).
- Expiry is already enforced at the service layer (`topic_findings.py:298-300`) via timestamp comparison, raising `MergePreviewError("merge preview has expired")` — this is a business error message, not an enum value.
- `list_merge_previews` filters by `expires_at > ?` timestamps (line 1605-1606), not by state — no change needed.
- `test_topic_findings_api.py:460` matches against the error message string "expired" (from service layer error), not the enum — test unaffected.
- No SQL migration needed — state column is plain varchar, no CHECK constraint.
- LSP diagnostics: clean on both changed files.
- `_MERGE_PREVIEW_STATE_VALUES` auto-updates from the enum, no manual intervention needed.
- All other "expired" references in codebase are in different contexts (cache cleanup, raw items, callback states, timestamp helpers `_is_expired`) — none reference merge preview state.
