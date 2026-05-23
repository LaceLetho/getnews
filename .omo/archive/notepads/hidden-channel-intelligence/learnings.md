## 2026-05-03 Task 12

- Intelligence HTTP route guardrails can be inspected through FastAPI `APIRoute.dependant.dependencies`; current intelligence routes all depend on `api_server.verify_api_key`.
- Datasource list responses intentionally return `config_summary` only, not full `config_payload`; REST summaries should expose counts and response mapping but never header/param values.

## 2026-05-03 Task 13 (Final Integration Hardening)

- `.env.template` updated with intelligence collection section (`TELEGRAM_API_ID`, `TELEGRAM_API_HASH`, `TELEGRAM_STRING_SESSION`, `V2EX_PAT`) — all commented out as placeholders.
- New security guardrail test `test_env_template_contains_no_real_secrets` validates: (a) no real Telethon string session patterns, (b) no real V2EX PAT patterns, (c) all `KEY`/`TOKEN`/`SECRET`/`SESSION`/`PAT`/`AUTH` lines use placeholder values or are commented out. Test correctly allows known config defaults (`DATABASE_URL`, `LOG_LEVEL`, `API_HOST`, etc.).
- Full regression: 857 passed, 67 failed, 7 skipped. All 67 failures pre-existing and unrelated to intelligence changes. All 92 intelligence tests pass. All 10 security guardrails pass.
- Import integrity verified: `api_server`, `execution_coordinator`, `main`, `data_source_factory`, `intelligence.pipeline`, `telegram_intelligence_crawler`, `v2ex_intelligence_crawler` all import cleanly. `DataSourceFactory` correctly registers `telegram_group` and `v2ex` alongside existing `rss`, `x`, `rest_api`.
