# F4. Scope Fidelity Check — VERDICT: APPROVE

## Out of Scope (MUST NOT exist) — ALL PASS

### 1. Dashboards/ranking/semantic search/embeddings/extra taxonomy
**Result: PASS**
- `embedding` references found only in pre-existing `topic_converger.py` and `topic_enricher.py` (plan explicitly references these as pre-existing patterns)
- New files `topic_prompts.py` and `topic_findings.py` contain zero embedding/ranking/dashboard/taxonomy concepts
- No dashboards, ranking systems, or extra taxonomy added

### 2. Compatibility aliases for deleted commands/routes
**Result: PASS**
- Zero matches for `alias.*intel`, `intel.*alias`, `intel.*route`, `intel.*command` in:
  - `crypto_news_analyzer/reporters/telegram_command_handler.py`
  - `crypto_news_analyzer/api_server.py`

### 3. Real LLM calls in tests
**Result: PASS**
- Zero matches for `openai.OpenAI(` in all `test_topic_*.py` files
- All tests use fake/mock LLM clients

### 4. Hard-delete of raw messages
**Result: PASS**
- `DELETE FROM raw_intelligence_items WHERE expires_at < ?` in `data_manager.py:2825` is TTL-based retention cleanup, NOT a hard-delete migration step
- This is the standard retention mechanism the plan authorizes (180-day retention)

### 5. Source `channel` as product concept (not just source metadata)
**Result: PASS**
- `api_server.py:482`: `"source_channels"` is source metadata in `_topic_to_dict()`, alongside other metadata fields (`methods`, `vulnerabilities`, `enriched_summary`)
- `test_topic_prompt_workflow.py` lines 47, 188: `channel_name` etc. are in `OLD_CATEGORY_PATTERNS` used to VERIFY that new prompts do NOT contain old channel extraction fields — this is enforcement, not violation
- Zero `EntryType`, `entry_type`, `intel_entry`, `canonical`, or `/entries` in `api_server.py`

## In Scope (MUST exist) — ALL PASS

### 6. Topic prompt draft/revise/manual-confirm workflow
**Result: PASS**
- `crypto_news_analyzer/intelligence/topic_prompts.py` (375 lines):
  - `TopicPromptDraft` (Pydantic model for LLM response)
  - `TopicPromptRevision` (Pydantic model for revision)
  - `TopicPromptGenerator` (LLM-powered generation from user theme)
  - `TopicPromptReviser` (LLM-powered revision from user feedback)
  - `TopicPromptService` (manual replacement and confirm workflow)
  - Schema version validation on all models

### 7. Scheduled topic research runs only from ingestion
**Result: PASS**
- `execution_coordinator.py`: 8 references — scheduler is created (line 592, 594, 630), invoked after raw crawl (line 2220, 2222, 2226), and explicitly set to None in analysis-service init (line 536)
- `api_server.py`: Only `list_topic_research_runs` endpoint (line 1673) — read-only query, does NOT schedule research
- Confirmed: no topic research scheduling in FastAPI app creation or API server

### 8. Topic findings merge preview with stale rejection
**Result: PASS**
- `crypto_news_analyzer/intelligence/topic_findings.py` (285 lines):
  - `TopicFindingsMergeOutput` (Pydantic model for structured merge output)
  - `TopicFindingMergeService.create_merge_preview()` — creates preview with source_finding_ids, content_hash, 24h expiry
  - `TopicFindingMergeService.accept_merge_preview()` — explicit expiry check (line 152), stale active finding set check (line 156-160), exact source finding archival (lines 175-176)
  - `MergePreviewError` for all failure modes

### 9. HTTP API topic endpoints
**Result: PASS**
- 12 `/intelligence/topics` routes in `api_server.py`:
  - `POST /intelligence/topics` — create draft (201)
  - `POST /intelligence/topics/{id}/revise` — LLM revision
  - `PUT /intelligence/topics/{id}/prompt` — manual prompt set
  - `POST /intelligence/topics/{id}/confirm` — confirm activation
  - `POST /intelligence/topics/{id}/merge-preview` — create merge preview
  - `POST /intelligence/topics/{id}/merge-accept` — accept merge
  - `POST /intelligence/topics/{id}/pause` — pause topic
  - `POST /intelligence/topics/{id}/archive` — archive topic
  - `GET /intelligence/topics/{id}/runs` — list research runs
  - `GET /intelligence/topics` — list all topics
  - `GET /intelligence/topics/{id}` — topic detail
  - `POST /intelligence/topics/converge` — convergence (pre-existing)

### 10. Telegram topic commands
**Result: PASS**
- All 10 `/topic_*` commands registered in `telegram_command_handler.py`:
  - `/topic_create`, `/topic_revise`, `/topic_set_prompt`, `/topic_confirm`
  - `/topic_list`, `/topic_detail`, `/topic_logs`
  - `/topic_merge`, `/topic_pause`, `/topic_archive`
- Commands properly listed in BotCommand setup (lines 747-756)
- Help text includes all topic commands (lines 3191-3200)
- Callback handlers for merge accept with authorization checks

### 11. Old entry/intel surfaces removed
**Result: PASS**
- Zero `/intel_` matches in `telegram_command_handler.py`
- Zero `EntryType`, `entry_type`, `intel_entry`, `intelligence_entry`, `canonical`, or `/entries` in `api_server.py`
- Old intel commands are completely unregistered and removed from active product surface

### 12. Config retention default 180 days
**Result: PASS**
- `config.jsonc:64`: `"raw_message_retention_days": 180` — matches requirement
- Comment line 62: `"Topic and raw message retention in days (both default to 180)."` — clear documentation

## Summary

| # | Check | Status |
|---|-------|--------|
| 1 | No dashboards/ranking/embeddings/extra taxonomy | ✅ PASS |
| 2 | No compatibility aliases for deleted commands | ✅ PASS |
| 3 | No real LLM calls in tests | ✅ PASS |
| 4 | No hard-delete of raw messages | ✅ PASS |
| 5 | No source channel as product concept | ✅ PASS |
| 6 | Topic prompt workflow exists | ✅ PASS |
| 7 | Topic research only in ingestion | ✅ PASS |
| 8 | Merge preview with stale rejection exists | ✅ PASS |
| 9 | HTTP API topic endpoints exist | ✅ PASS |
| 10 | Telegram topic commands exist | ✅ PASS |
| 11 | Old entry/intel surfaces removed | ✅ PASS |
| 12 | Config retention default 180 days | ✅ PASS |

## VERDICT: APPROVE
All 12 scope checks pass. Nothing out of scope was added. All required in-scope items exist and are correctly implemented.
