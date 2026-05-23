# Issues

- Manual analyze paths now inject historical outdated titles (task 4 complete).
- Batch analysis currently does not propagate earlier batch titles into later batch prompts (task 5).
- Current sent-message cache is not recipient scoped.
- Unrelated prompt-builder tests in `tests/test_llm_analyzer_cache_integration.py` still expect cached outdated news when `_build_user_prompt_with_context(..., is_scheduled=False)` hardcodes `"无"`; left unchanged because analyzer behavior is out of scope for this storage task.
- Top-level task 1 verification now treats the two prompt-cache integration cases as scheduled/global coverage by passing `is_scheduled=True`, avoiding any accidental expansion into manual outdated-news injection.
- `crypto_news_analyzer/execution_coordinator.py` still has a large pre-existing basedpyright error backlog unrelated to this task, so file-level diagnostics are not yet zero even though the edited storage/test files are clean and the new manual-history paths are covered by passing tests.
- The tiny analyzer boundary extension for `historical_titles` is in place, and prompt rendering now renders those titles into `# Outdated News` when `is_scheduled=False` but `historical_titles` is provided (task 4 complete).
- `crypto_news_analyzer/execution_coordinator.py` and `crypto_news_analyzer/analyzers/llm_analyzer.py` both report pre-existing basedpyright errors unrelated to this change, so targeted tests are the reliable verification signal for this task.
- Task 5 batch propagation gap is now closed for manual analyzer runs: later batch prompts receive rolling prior final-result titles through the existing `historical_titles` / `# Outdated News` path without using raw input titles.
- `crypto_news_analyzer/execution_coordinator.py` still has a large pre-existing basedpyright error backlog unrelated to this API `user_id` task; targeted API and manual-history regressions are the reliable verification signal here.
- `crypto_news_analyzer/reporters/telegram_command_handler.py` still has a large pre-existing basedpyright backlog unrelated to this Telegram dedup/caching change, so targeted Telegram analyze behavior checks are the reliable verification signal for this task.
- This shell is missing `uv`, `pytest`, and the `telegram` package, so focused verification had to run through a direct-module Python harness with stubbed Telegram imports instead of the normal `uv run pytest ...` path.
- Task 8 is no longer blocked: `"/data/.local/bin/uv" run pytest tests/test_llm_analyzer_cache_integration.py tests/test_llm_analyzer.py tests/test_multi_step_analysis_unit.py tests/test_api_server.py tests/test_main_controller.py -v` now passes end-to-end.
- Non-blocking backlog remains in static analysis only: `execution_coordinator.py`, `llm_analyzer.py`, and `structured_output_manager.py` still report pre-existing basedpyright errors outside this regression slice, so runtime/test verification is still the trustworthy release signal here.
