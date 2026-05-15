
## Scope Review — 2026-05-06

### Guardrail Verification

All 8 guardrails verified PASS:

| # | Guardrail | Verdict | Evidence |
|---|-----------|---------|----------|
| 1 | No per-user ignore state | PASS | `ignored_by` records operator identity but filtering is global; `list_ignored_canonical_entries` has no user filter |
| 2 | No bulk ignore/unignore | PASS | Only single-entry `ignore_canonical_entry` / `unignore_canonical_entry` |
| 3 | No ignore reason prompt or moderation workflow | PASS | `IntelligenceIgnoreRequest` has only `ignored_by`, no `reason` field |
| 4 | No dashboard/admin UI | PASS | `glob **/*.{html,css,js,jsx,tsx}` → no matches |
| 5 | No deletion of canonical entries, aliases, observations, raw rows, or raw evidence text as part of ignore | PASS | `ignore_canonical_intelligence_entry` is UPDATE only; migration is ALTER TABLE ADD COLUMN |
| 6 | No hiding ignored entries from exact detail endpoints | PASS | `get_canonical_intelligence_entry_by_id` has no `is_ignored` filter; `GET /intelligence/entries/{entry_id}` returns ignore metadata |
| 7 | No unrelated Telegram command redesign | PASS | Changes scoped to inline buttons, pagination, `/intel_ignored`, `/intel_unignore` |
| 8 | No broad repository rewrites beyond intelligence canonical ignore semantics | PASS | Changes limited to: domain/models, domain/repositories, storage/data_manager, storage/repositories, api_server, telegram_command_handler, intelligence/merge, intelligence/pipeline, migrations |

### Test Results
- `tests/test_intelligence_repositories.py` — 6 passed
- `tests/test_intelligence_api.py` — 32 passed
- `tests/test_intelligence_telegram_commands.py` — 19 passed
- `tests/test_intelligence_ingestion_runtime.py` — 9 passed
- **Total: 66 passed**

### Diff Scope
- 13 files changed: 8 production, 1 migration, 4 test files
- 1948 insertions, 75 deletions
- New untracked file: `migrations/postgresql/004_intelligence_ignore_state.sql` (migration for existing DBs)

### LSP Diagnostics
- `merge.py`: warnings only (pre-existing deprecated types)
- `data_manager.py`: 1217 diagnostics (pre-existing — no new errors from this change)
- `api_server.py`: 255 diagnostics (pre-existing — no new errors from this change)  
- `telegram_command_handler.py`: 826 diagnostics (pre-existing — no new errors from this change)

### Verdict: APPROVE
