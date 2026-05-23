2026-04-03 (Task 1 characterization)
- Added retained-surface characterization as positive coverage only (no legacy-removal negatives yet), aligned with Task 1 scope.
- Chose to assert retained runtime acceptance through `normalize_runtime_mode` for `analysis-service`, `api-only`, and `ingestion` without asserting legacy rejection (deferred to Task 2).
- Added a dedicated `run.py` wrapper test (`tests/test_run_wrapper.py`) to lock thin-wrapper delegation semantics without changing production runtime behavior.

2026-04-03 (Task 3 banned legacy reference scan)
- Implemented the guardrail as a standard-library helper at `tests/helpers/banned_legacy_reference_scan.py` plus `tests/test_banned_legacy_reference_scan.py`, so CI or local validation can run without `uv`.
- Scoped the scan explicitly to root docs/templates (`README.md`, `AGENTS.md`, `.env.template`), `docs/**/*.md`, `crypto_news_analyzer/main.py`, `crypto_news_analyzer/reporters/telegram_command_handler.py`, `docker-entrypoint.sh`, and `tests/telegram-multi-user-authorization/**/*.py`.
- Kept the ignore list minimal and explicit: `.git`, `.venv`, and `.sisyphus/evidence` are pruned before candidate-file evaluation.

2026-04-03 (Task 2 negative removed runtime/alias tests)
- Added failing-first negative runtime tests in `tests/test_ingestion_runtime.py` for removed CLI names only: `api-server`, `api`, `once`, `schedule`, `scheduler`.
- Added dedicated entrypoint negative tests in `tests/test_docker_entrypoint_legacy_alias_rejection.py` instead of changing existing positive characterization tests, to keep Task 1 retained-surface guardrails untouched.
- Enforced explicit rejection contract in tests (`non-zero` + unsupported/unknown semantics) rather than warning+fallback semantics, per cleanup target.

2026-04-03 (Task 4 main runtime cleanup)
- Removed monolith runtime names from `SUPPORTED_RUNTIME_MODES` in `main.py`; kept only `analysis-service`, `api-only`, and `ingestion`.
- Deleted legacy compatibility helpers `run_api_server()` and `initialize_system()` from `main.py` instead of retaining deprecated stubs.
- Kept `run_scheduler_only()` as an internal ingestion implementation detail for now (runtime CLI surface no longer exposes scheduler/schedule/once), avoiding scope creep into later tasks.

2026-04-03 (Task 4 follow-up fix)
- Reversed the prior internal-detail decision and removed scheduler-named helper semantics from `main.py` by renaming to `run_ingestion_loop()`.
- Updated the directly coupled ingestion runtime tests (`tests/test_ingestion_runtime.py`) to assert delegation to `run_ingestion_loop()`.
- Preserved existing controller call pattern (`initialize_ingestion_system()` + `start_scheduler()`) to keep ingestion behavior unchanged while removing scheduler runtime naming from main entrypoint surface.

2026-04-03 (Task 5 docker entrypoint legacy alias cleanup)
- Removed the shell-side legacy translations for `api-server`, `api`, and `crypto-news-api` from `docker-entrypoint.sh` instead of keeping warning-plus-fallback behavior.
- Kept Railway routing restricted to the retained split-service names only: `crypto-news-analysis -> analysis-service` and `crypto-news-ingestion -> ingestion`.
- Preserved explicit migration execution by allowing `main migrate-postgres` to bypass Railway service-name remapping.
- Updated `docs/RAILWAY_DEPLOYMENT.md` because it directly described the old `api-server -> analysis-service` compatibility behavior and would otherwise become misleading.

2026-04-03 (Task 6 coordinator/Telegram/repository cleanup)
- Deleted coordinator-level monolith compatibility helpers (`setup_environment_config`, `handle_container_signals`) and legacy runner entrypoints (`run_one_time_execution`, `run_scheduled_mode`, `run_command_listener_mode`) instead of keeping no-op or deprecated shims.
- Removed `/run` from Telegram command registration/menu and deleted `_handle_run_command` + `handle_run_command` + manual-execution notification helpers; retained manual trigger path is `/analyze` only.
- Applied command cooldown to `/analyze` and renamed internal rate-limit timestamp state to `last_analyze_command_time` so rate-limit semantics match the retained command surface.
- Removed repository factory transition aliases `_data_manager` and `_cache_manager`, keeping only explicit repository keys plus `_backend` metadata.

2026-04-03 (Task 7 docs/templates/legacy test assets cleanup)
- Rewrote the scoped docs/templates (`README.md`, `AGENTS.md`, `.env.template`, `docs/RAILWAY_DEPLOYMENT.md`) to describe only `analysis-service`, `api-only`, and `ingestion`, and avoided naming removed modes in user-facing examples.
- Renamed the surviving Telegram test modules to `test_task_8_1_handle_analyze_command.py` and `test_rate_limit_analyze_only.py` instead of deleting them, because their test bodies already asserted retained `/analyze` behavior.
- Kept the execution coordinator cache integration test intact and only updated its legacy `/run` requirements wording, since the test still validates retained manual-execution cache behavior.

2026-04-03 (Task 7 follow-up docs alignment)
- Expanded `AGENTS.md` from a generic app summary to a split-service operations guide with retained runtime modes, shared Postgres/pgvector source-of-truth wording, updated module organization, and service-scoped env vars.
- Reorganized `.env.template` into four top-level sections: shared config, `analysis-service`/`api-only`, `analysis-service` extras, and `ingestion`, so each service’s required variables are visually separated.

2026-04-03 (Task 7 acceptance recheck)
- No further edits were needed in the final follow-up pass because the two allowed files already satisfied the requested split-service semantics and stale-guidance removals.

2026-04-03 (Final-wave rejection fix-up)
- Kept `migrate-postgres` available only in `docker-entrypoint.sh` as a one-off maintenance path and removed it from the README runtime-mode list, so the documented `crypto_news_analyzer.main` surface now matches the retained three-mode CLI contract.
- Added an early `validate_mode()` gate in `docker-entrypoint.sh` after Railway/default mode resolution and before environment or health checks, preserving the existing invalid-`RAILWAY_SERVICE_NAME` failure path while making explicit invalid-mode feedback immediate.
