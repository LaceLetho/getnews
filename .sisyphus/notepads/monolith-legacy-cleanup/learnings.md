2026-04-03 (Task 1 characterization)
- Existing runtime tests already lock key retained behavior in `tests/test_ingestion_runtime.py` for `run_analysis_service`, `run_api_server_isolated`, and `run_ingestion_service`.
- `create_api_server(start_services=False)` uses `start_services` as the default for both scheduler and Telegram listener when explicit overrides are omitted; this is the core `api-only` runtime contract.
- `run.py` remains a thin wrapper around `crypto_news_analyzer.main.main`; runtime surface behavior should be characterized in `main.py`/service tests, not duplicated in wrapper logic.

2026-04-03 (Task 3 banned legacy reference scan)
- `PurePosixPath.match("README.md")` is basename-oriented and will accidentally match nested files like `.kiro/.../README.md`; exact root-file checks need anchored relative-path comparisons instead.
- The banned `/run` reference needs a command-aware regex so the scan does not flag unrelated filesystem paths such as `/app/run.py`.
- Treating `once`, `schedule`, and `scheduler` as punctuation-bounded tokens avoids false positives like prose uses of `once` while still catching CLI/help/runtime surfaces.

2026-04-03 (Task 2 negative removed runtime/alias tests)
- `normalize_runtime_mode` currently still accepts or maps multiple legacy names (`api-server`, `once`, `schedule`, `scheduler`), so negative tests must target `ValueError` unsupported semantics as the post-cleanup contract.
- `docker-entrypoint.sh` still translates removed compatibility surfaces at two levels: `api-server/api` argument fallback and `RAILWAY_SERVICE_NAME=crypto-news-api` service-name mapping.
- Shell-level testing of `docker-entrypoint.sh` is feasible via `source` + function overrides (`validate_environment`, `health_check`, `python`) to isolate alias-routing behavior without invoking full container dependencies.

2026-04-03 (Task 4 main runtime cleanup)
- `crypto_news_analyzer/main.py` runtime dispatch is now retained-only at CLI surface: `analysis-service`, `api-only`, and `ingestion`.
- Removing `DEPRECATED_RUNTIME_MODE_ALIASES` plus `api-server` mapping in `normalize_runtime_mode` aligns behavior with Task 2 negative tests (legacy names now raise directly instead of warning+fallback).
- `run.py` can remain a thin passthrough; only wrapper wording needed alignment so it no longer advertises legacy once/schedule semantics.

2026-04-03 (Task 4 follow-up fix)
- Keeping `scheduler` wording in internal helper names still causes runtime-surface ambiguity for agents even when CLI mode validation is strict.
- Renaming `run_scheduler_only` to `run_ingestion_loop` in `main.py` removes that ambiguity while preserving the same ingestion execution path.
- Setting `CRYPTO_NEWS_RUNTIME_MODE="ingestion"` inside the ingestion loop eliminates mixed internal mode signals.

2026-04-03 (Task 5 docker entrypoint legacy alias cleanup)
- Removing `crypto-news-api` from `get_mode_from_railway_service()` is not sufficient by itself, because an unknown `RAILWAY_SERVICE_NAME` would otherwise fall through to the default `analysis-service` path in `main()`.
- The entrypoint needs an explicit invalid-`RAILWAY_SERVICE_NAME` failure path in `main()` so removed Railway aliases are rejected before default-mode selection happens.
- Preserving the explicit `migrate-postgres` path requires skipping Railway service-name routing when the requested mode is already `migrate-postgres`.

2026-04-03 (Task 6 coordinator/Telegram/repository cleanup)
- `execution_coordinator.py` still contained legacy monolith compatibility surfaces (`setup_environment_config`, `handle_container_signals`, `run_one_time_execution`, `run_scheduled_mode`, `run_command_listener_mode`) even after retained split-service runtime cleanup in `main.py`; removing them keeps the module aligned with retained runtime entrypoints.
- Telegram `/run` removal is coupled across multiple user-visible surfaces (handler registration, bot command menu, command methods, help text, token hints), so deleting only one surface still leaves legacy guidance exposed.
- Moving rate-limit state from `last_run_command_time` to `last_analyze_command_time` preserves anti-abuse behavior on the retained manual trigger path (`/analyze`) while removing monolith command semantics.
- Repository factory compatibility aliases (`_data_manager`, `_cache_manager`) are removable when split-service callers consume concrete repository keys and controller-managed manager fields instead of factory backdoors.

2026-04-03 (Task 7 docs/templates/legacy test assets cleanup)
- Repo-facing cleanup needs to cover filenames as well as assertions: the Telegram authorization tests were already analyze-only in behavior, but their module names still exposed `/run` semantics to readers and tooling.
- Literal legacy-token scans can still be tripped by neutral phrases like `build/run`, so documentation wording should avoid stray `/run` substrings even when they are not command references.
- Railway deployment docs can stay accurate without naming removed aliases explicitly by referring to rejected legacy monolith modes generically.

2026-04-03 (Task 7 follow-up docs alignment)
- `AGENTS.md` must mirror the real deployment model, not just be legacy-string clean: SQLite-era shortcuts like `storage/ # SQLite persistence` and `SQLite at ./data/crypto_news.db` still mislead agents after runtime cleanup.
- `.env.template` is clearer for operators and agents when grouped by shared config, `analysis-service`/`api-only`, `analysis-service`-only Telegram+LLM needs, and `ingestion`, instead of one blended “required config” section.

2026-04-03 (Task 7 acceptance recheck)
- Final Task 7 follow-up verification confirmed that `AGENTS.md` and `.env.template` still contain the split-service sections and no longer contain the previously flagged SQLite-centric or monolith-centric statements.

2026-04-03 (Final-wave rejection fix-up)
- `README.md` stays operator-consistent when it presents only `analysis-service`, `api-only`, and `ingestion` as the long-lived runtime modes, and mentions `migrate-postgres` only as a separate maintenance note tied to `docker-entrypoint.sh`.
- `docker-entrypoint.sh` needs explicit mode validation before environment and health checks so an invalid manual mode fails with retained-surface guidance instead of misleading dependency or health-check noise.
