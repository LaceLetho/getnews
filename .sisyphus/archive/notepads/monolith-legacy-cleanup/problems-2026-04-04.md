2026-04-03 (Task 1 characterization)
- Verification commands required by plan could not be fully executed in current container due to missing test/runtime tooling; re-run in CI/dev environment with `uv` and `pytest` installed.
- Runtime import path for wrapper checks requires dependency installation (e.g., `python-dotenv`) before behavioral execution can be validated.

2026-04-03 (Task 3 banned legacy reference scan)
- The new helper intentionally reports 84 current in-scope legacy-reference matches, so the guardrail is red until later cleanup tasks remove those surfaces.
- Because `pytest` is unavailable locally, verification relied on `python3` execution of the helper, `py_compile`, and direct invocation of the new test assertions as a deterministic fallback.

2026-04-03 (Task 2 negative removed runtime/alias tests)
- Failing-first negative tests were added, but behavioral proof (expected red before runtime cleanup) is blocked locally by missing `uv`/`pytest`; rerun targeted pytest in CI/dev to capture red-state evidence.
- File-level diagnostics are blocked by missing `basedpyright` language server in this environment.

2026-04-03 (Task 4 main runtime cleanup)
- Runtime-surface cleanup in `main.py` is complete, but environment tooling prevents full behavioral proof in-container: missing `uv`, `pytest`, and `python-dotenv` block targeted runtime/test commands.
- Local verification therefore relies on successful `py_compile` plus static reference checks; full retained/negative runtime test evidence must be collected in CI/dev where dependencies are installed.

2026-04-03 (Task 4 follow-up fix)
- Additional cleanup removed scheduler-named ingestion helper semantics in `main.py`, but full behavior validation is still pending CI/dev execution because local pytest tooling is unavailable.

2026-04-03 (Task 5 docker entrypoint legacy alias cleanup)
- Behavioral verification in this container had to rely on direct bash snippets rather than pytest because the available `python3` lacks the `pytest` module.
- The bash-level checks did confirm the Task 5 shell contract locally: retained Railway service names still map correctly, removed aliases no longer translate, and `migrate-postgres` remains reachable under a valid `RAILWAY_SERVICE_NAME`.

2026-04-03 (Task 6 coordinator/Telegram/repository cleanup)
- Full regression evidence for `tests/test_telegram_command_handler_analyze.py` and `tests/telegram-multi-user-authorization/` is blocked in-container by missing `uv` and missing `pytest`.
- Verification therefore relied on static checks and syntax compilation (`python3 -m py_compile`) for all Task 6 touched Python files, plus direct legacy-surface grep confirmation on scoped files.

2026-04-03 (Task 7 docs/templates/legacy test assets cleanup)
- Task 7 scoped legacy-reference verification is green for the targeted docs/templates and legacy test filenames, and the touched Python test files pass `python3 -m py_compile`.
- Full pytest collection/execution evidence for the renamed test modules still needs a CI/dev environment with `pytest` installed.

2026-04-03 (Task 7 follow-up docs alignment)
- This follow-up resolved semantic stale guidance in `AGENTS.md` and `.env.template`, but full repository verification still depends on the later Task 8 zero-reference and regression pass in an environment with pytest/LSP tooling installed.

2026-04-03 (Task 7 acceptance recheck)
- No additional unresolved problems were introduced by the acceptance recheck; remaining broader verification still belongs to later repo-wide validation work.
