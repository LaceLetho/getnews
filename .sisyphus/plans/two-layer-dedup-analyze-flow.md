# Two-Layer Deduplication for Manual Analyze Flows

## TL;DR
> **Summary**: Add recipient-scoped historical deduplication for HTTP `/analyze` and Telegram `/analyze`, plus rolling intra-run batch deduplication so later LLM batches see titles already emitted earlier in the same run.
> **Deliverables**:
> - HTTP `user_id` plumbing and validation
> - Telegram `chat_id`-scoped manual dedup history
> - Recipient-scoped sent-title storage/query support
> - 48-hour historical `[Outdated News]` injection anchored to prior successful manual run
> - Per-batch prior-title propagation in LLM analysis
> - TDD coverage and scheduled-mode regression protection
> **Effort**: Large
> **Parallel**: YES - 2 waves
> **Critical Path**: 1 → 2 → 3 → 4 → 6/7 → 8

## Context
### Original Request
Add two dedup layers:
1. HTTP `/analyze` and Telegram `/analyze` should include titles from prior successful user-specific analyze reports in `[Outdated News]`, similar in intent to current scheduled dedup behavior.
2. When large news sets are split into multiple LLM batches, each later batch should receive titles returned by earlier batches in the same run inside `[Outdated News]`.

### Interview Summary
- HTTP must accept a caller-supplied identifier; Telegram uses `chat_id`.
- Dedup identity is normalized as a namespaced recipient key: `api:{user_id}` and `telegram:{chat_id}`.
- For each recipient, use the timestamp of that recipient’s last successful manual `/analyze` run as the anchor time.
- Historical dedup window is the 48-hour interval ending at that prior success timestamp, not ending at “now”.
- Historical dedup titles come from final delivered/returned report headline titles, not every raw analyzed item.
- HTTP success means a successful `/analyze` response was produced; Telegram success means the report was successfully sent to the target chat.
- Scheduled/global dedup behavior must remain unchanged.
- Test strategy is TDD.

### Metis Review (gaps addressed)
- Resolved recipient collision risk by adopting normalized `recipient_key` values instead of raw `user_id`/`chat_id`.
- Fixed anchor-time ambiguity by defining the query window as `[prior_success - 48h, prior_success]` in UTC.
- Fixed title-source ambiguity by using only final report titles actually delivered/returned.
- Added guardrail that failed or partially failed manual runs must not cache titles or advance success history.
- Added regression requirement that scheduled/global cache reads continue to work without recipient filtering.

## Work Objectives
### Core Objective
Implement deterministic two-layer deduplication for manual analyze flows so users do not receive repeated report headlines across runs or across batches within the same run.

### Deliverables
- Recipient-scoped manual dedup storage/query support.
- Manual analyze recipient-key normalization helper(s).
- Coordinator logic that loads historical outdated titles for manual analyze recipients.
- LLM analyzer support for merging historical outdated titles with rolling prior-batch titles.
- HTTP `/analyze` request/job changes requiring `user_id`.
- Telegram `/analyze` propagation and manual-success title caching.
- TDD coverage for storage, analyzer, HTTP, Telegram, and scheduled regression.

### Definition of Done (verifiable conditions with commands)
- Manual HTTP `/analyze` requires `user_id` and tests enforce rejection of missing/invalid values.
- Manual HTTP and Telegram analyze flows both populate `[Outdated News]` from the correct recipient-scoped 48-hour historical window anchored to the prior success timestamp.
- Later LLM batches include titles emitted by earlier batches in the same run.
- Failed manual runs do not write recipient-scoped sent-title history or advance manual success state.
- Scheduled/global dedup behavior still passes regression tests unchanged.
- `uv run pytest tests/test_llm_analyzer_cache_integration.py tests/test_llm_analyzer.py tests/test_multi_step_analysis_unit.py tests/test_api_server.py tests/test_main_controller.py -v` passes.

### Must Have
- Exact-recipient isolation between `api:{user_id}` and `telegram:{chat_id}`.
- UTC-safe bounded window queries.
- Ordered, de-duplicated merge of historical titles and prior-batch titles before prompt rendering.
- Minimal schema extension on `sent_message_cache` instead of broad architecture refactor.
- Reuse current `analysis_execution_log` for prior-success lookups, keyed by normalized recipient key for manual analyze flows.

### Must NOT Have (guardrails, AI slop patterns, scope boundaries)
- No refactor of scheduled workflow semantics.
- No fuzzy title normalization or semantic matching changes.
- No new linkage table unless existing schema update proves impossible during implementation.
- No writes to manual dedup history on failed sends, failed HTTP responses, or partial failures.
- No prompt-template redesign outside `[Outdated News]` population mechanics.

## Verification Strategy
> ZERO HUMAN INTERVENTION — all verification is agent-executed.
- Test decision: TDD with pytest.
- QA policy: Every task includes agent-executed scenarios.
- Evidence: `.sisyphus/evidence/task-{N}-{slug}.{ext}`

## Execution Strategy
### Parallel Execution Waves
> Target: 5-8 tasks per wave. <3 per wave (except final) = under-splitting.
> Extract shared dependencies as Wave-1 tasks for max parallelism.

Wave 1: storage contract, recipient-key semantics, historical-context assembly, prompt merge helper, rolling batch propagation.

Wave 2: HTTP recipient plumbing, Telegram manual caching/plumbing, cross-flow regression hardening.

### Dependency Matrix (full, all tasks)
| Task | Depends On | Blocks |
|---|---|---|
| 1 | none | 2, 3, 6, 7, 8 |
| 2 | 1 | 3, 6, 7 |
| 3 | 1, 2 | 4, 6, 7 |
| 4 | 3 | 5, 6, 7, 8 |
| 5 | 4 | 6, 7, 8 |
| 6 | 1, 2, 3, 4, 5 | 8 |
| 7 | 1, 2, 3, 4, 5 | 8 |
| 8 | 6, 7 | F1-F4 |

### Agent Dispatch Summary
| Wave | Task Count | Categories |
|---|---:|---|
| Wave 1 | 5 | unspecified-high, quick |
| Wave 2 | 3 | unspecified-high, quick |
| Final Verification | 4 | oracle, unspecified-high, deep |

## TODOs
> Implementation + Test = ONE task. Never separate.
> EVERY task MUST have: Agent Profile + Parallelization + QA Scenarios.

- [ ] 1. Add recipient-scoped sent-title storage and bounded lookup

  **What to do**: Extend `sent_message_cache` with nullable `recipient_key TEXT`, add an index on `(recipient_key, sent_at)`, keep existing scheduled/global queries working when `recipient_key` is `NULL` or ignored, and add a new query API that returns final report titles for one recipient inside the exact UTC window `[anchor_time - 48h, anchor_time]`. Write failing tests first for schema compatibility, boundary timestamps, duplicate-preserving storage, and recipient isolation, then implement the minimum storage changes to make them pass.
  **Must NOT do**: Do not replace the global scheduled cache query path; do not create a second linkage table unless the existing table cannot support the required query contract during implementation.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` — Reason: schema, query, and regression risk across storage reads.
  - Skills: `[]` — No extra skill required.
  - Omitted: `['git-master']` — Not needed for implementation planning.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: 2, 3, 6, 7, 8 | Blocked By: none

  **References**:
  - Pattern: `crypto_news_analyzer/storage/cache_manager.py:SentMessageCacheManager` — existing sent-title schema and cache/query methods.
  - Pattern: `crypto_news_analyzer/storage/cache_manager.py:cache_sent_messages` — current write path for successful report titles.
  - Pattern: `crypto_news_analyzer/storage/cache_manager.py:get_cached_messages` — preserve scheduled/global retrieval semantics.
  - Pattern: `crypto_news_analyzer/storage/cache_manager.py:format_cached_messages_for_prompt` — current formatting for legacy scheduled flow.
  - Test: `tests/test_llm_analyzer_cache_integration.py` — best existing home for cache-backed outdated-news coverage.

  **Acceptance Criteria**:
  - [ ] `sent_message_cache` supports manual rows with `recipient_key` and leaves legacy/global rows readable without backfill.
  - [ ] A recipient-scoped query returns titles for `recipient_key='api:user-a'` inside the exact inclusive anchor window and excludes `api:user-b` and `telegram:-1001` rows.
  - [ ] Query results preserve stored title order by `sent_at` ascending so prompt assembly is deterministic.
  - [ ] `uv run pytest tests/test_llm_analyzer_cache_integration.py -k "recipient or window or cached" -v` passes.

  **QA Scenarios** (MANDATORY — task incomplete without these):
  ```
  Scenario: Recipient-scoped historical lookup
    Tool: Bash
    Steps: Run `uv run pytest tests/test_llm_analyzer_cache_integration.py -k "recipient and anchor" -v | tee .sisyphus/evidence/task-1-storage-recipient.txt`
    Expected: Tests prove the query includes titles at `anchor_time` and `anchor_time-48h`, excludes later rows and other recipients, and exits 0.
    Evidence: .sisyphus/evidence/task-1-storage-recipient.txt

  Scenario: Legacy scheduled read remains valid
    Tool: Bash
    Steps: Run `uv run pytest tests/test_llm_analyzer_cache_integration.py -k "legacy or scheduled" -v | tee .sisyphus/evidence/task-1-storage-recipient-error.txt`
    Expected: Existing/global cache formatting tests still pass with `recipient_key` unset on legacy rows.
    Evidence: .sisyphus/evidence/task-1-storage-recipient-error.txt
  ```

  **Commit**: YES | Message: `add recipient-scoped sent title lookup for manual dedup` | Files: `crypto_news_analyzer/storage/cache_manager.py`, `tests/test_llm_analyzer_cache_integration.py`

- [ ] 2. Normalize manual recipient identity and defer success history writes until delivery success

  **What to do**: Introduce a shared helper that converts manual callers into `recipient_key` values (`api:{user_id}`, `telegram:{chat_id}`), store that normalized value in the existing `analysis_execution_log.chat_id` column for manual analyze rows only, keep scheduled/internal paths untouched, and update manual success-history recording so `analysis_execution_log` only records a successful manual `/analyze` after the actual success point: successful HTTP report generation for API and successful `send_report_to_chat()` completion for Telegram. Add failing tests first for recipient-key normalization, raw-key collision prevention, and “failed manual run does not advance last-success timestamp.”
  **Must NOT do**: Do not rename or migrate the `analysis_execution_log` table unnecessarily; do not let `analyze_by_time_window()` write a successful manual history row before the caller-specific completion step.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` — Reason: touches shared coordinator semantics and persistence timing.
  - Skills: `[]` — No extra skill required.
  - Omitted: `['git-master']` — Not needed for execution.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: 3, 6, 7 | Blocked By: 1

  **References**:
  - Pattern: `crypto_news_analyzer/storage/data_manager.py:analysis_execution_log` — existing last-success storage keyed by text identifier.
  - Pattern: `crypto_news_analyzer/storage/data_manager.py:log_analysis_execution` — current write API that must not mark manual success too early.
  - Pattern: `crypto_news_analyzer/storage/data_manager.py:get_last_successful_analysis_time` — reuse for normalized manual keys.
  - Pattern: `crypto_news_analyzer/execution_coordinator.py:analyze_by_time_window` — current manual analyze entrypoint.
  - Test: `tests/test_main_controller.py` — likely home for coordinator/history timing assertions.

  **Acceptance Criteria**:
  - [ ] `api:123` and `telegram:123` produce distinct manual history keys.
  - [ ] No successful manual history row is written when HTTP report generation fails or Telegram send fails.
  - [ ] Successful manual completion writes exactly one history row under the normalized `recipient_key`.
  - [ ] `uv run pytest tests/test_main_controller.py -k "recipient_key or last_success or manual" -v` passes.

  **QA Scenarios**:
  ```
  Scenario: Raw-key collision prevention
    Tool: Bash
    Steps: Run `uv run pytest tests/test_main_controller.py -k "collision or recipient_key" -v | tee .sisyphus/evidence/task-2-recipient-key.txt`
    Expected: Tests confirm `api:123` history never satisfies a Telegram lookup for `telegram:123`.
    Evidence: .sisyphus/evidence/task-2-recipient-key.txt

  Scenario: Failed manual run does not advance anchor
    Tool: Bash
    Steps: Run `uv run pytest tests/test_main_controller.py -k "failed and manual and last_success" -v | tee .sisyphus/evidence/task-2-recipient-key-error.txt`
    Expected: Tests show the previous success timestamp remains unchanged after a failed manual completion path.
    Evidence: .sisyphus/evidence/task-2-recipient-key-error.txt
  ```

  **Commit**: NO | Message: `n/a` | Files: `crypto_news_analyzer/execution_coordinator.py`, `crypto_news_analyzer/storage/data_manager.py`, `tests/test_main_controller.py`

- [ ] 3. Build manual historical outdated-title context from prior success anchor

  **What to do**: Add a coordinator-level helper for manual analyze flows that (a) resolves the normalized `recipient_key`, (b) reads the recipient’s prior successful manual analyze time, (c) queries recipient-scoped sent titles inside `[prior_success - 48h, prior_success]`, and (d) passes those titles into the analyzer only when a prior success exists; otherwise pass an explicit empty/`无` state. Write failing tests first for “no prior success”, “prior success with no cached titles”, “titles exactly at both window boundaries”, and “future rows after anchor excluded”.
  **Must NOT do**: Do not base the historical query on current wall-clock time; do not use global scheduled cache formatting for this manual path.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` — Reason: coordinator orchestration plus time-window semantics.
  - Skills: `[]` — No extra skill required.
  - Omitted: `['git-master']` — Not needed.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: 4, 6, 7 | Blocked By: 1, 2

  **References**:
  - Pattern: `crypto_news_analyzer/execution_coordinator.py:analyze_by_time_window` — inject manual historical context here.
  - Pattern: `crypto_news_analyzer/storage/data_manager.py:get_last_successful_analysis_time` — anchor lookup.
  - Pattern: `crypto_news_analyzer/storage/cache_manager.py:format_cached_messages_for_prompt` — legacy scheduled path to avoid altering.
  - API/Type: `crypto_news_analyzer/models.py:ExecutionResult` — preserve current result contract while extending context internally.
  - Test: `tests/test_main_controller.py` — coordinator-level time-window behavior.

  **Acceptance Criteria**:
  - [ ] First manual analyze for a recipient sends no historical titles and renders `[Outdated News]` as empty/`无`.
  - [ ] Second manual analyze for the same recipient uses only titles from the 48-hour window ending at the prior success timestamp.
  - [ ] Titles after the anchor time are excluded even if they are within the most recent 48 hours relative to “now”.
  - [ ] `uv run pytest tests/test_main_controller.py -k "outdated and anchor and 48" -v` passes.

  **QA Scenarios**:
  ```
  Scenario: Anchor-window historical context
    Tool: Bash
    Steps: Run `uv run pytest tests/test_main_controller.py -k "anchor and outdated" -v | tee .sisyphus/evidence/task-3-manual-history.txt`
    Expected: Tests assert the exact title set passed to the analyzer matches the prior-success anchored window only.
    Evidence: .sisyphus/evidence/task-3-manual-history.txt

  Scenario: No-prior-success fallback
    Tool: Bash
    Steps: Run `uv run pytest tests/test_main_controller.py -k "no prior success" -v | tee .sisyphus/evidence/task-3-manual-history-error.txt`
    Expected: Tests confirm manual analyze without prior success injects no historical titles and still completes.
    Evidence: .sisyphus/evidence/task-3-manual-history-error.txt
  ```

  **Commit**: NO | Message: `n/a` | Files: `crypto_news_analyzer/execution_coordinator.py`, `tests/test_main_controller.py`

- [ ] 4. Add explicit historical outdated-title injection to LLM prompt building

  **What to do**: Extend analyzer prompt-building APIs so manual callers can pass `historical_outdated_titles: List[str]` directly instead of relying on `is_scheduled=True`. Merge these titles into the existing `[Outdated News]` section using deterministic ordering, preserving the scheduled/global branch exactly as-is. Write failing tests first to verify manual prompt rendering with supplied titles, empty manual state rendering, and duplicate collapsing when the same title appears multiple times in historical input.
  **Must NOT do**: Do not force manual flows through the scheduled cache-reader branch; do not change prompt template sections outside the `[Outdated News]` contents.

  **Recommended Agent Profile**:
  - Category: `quick` — Reason: bounded analyzer API and prompt rendering change once contracts are defined.
  - Skills: `[]` — No extra skill required.
  - Omitted: `['git-master']` — Not needed.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: 5, 6, 7, 8 | Blocked By: 3

  **References**:
  - Pattern: `crypto_news_analyzer/analyzers/llm_analyzer.py:_build_user_prompt_with_context` — prompt assembly hot path.
  - Pattern: `crypto_news_analyzer/analyzers/llm_analyzer.py:_get_formatted_cached_messages` — preserve legacy scheduled behavior.
  - External: `prompts/analysis_prompt.md` — LLM instructions already mention outdated-news filtering.
  - Test: `tests/test_llm_analyzer_cache_integration.py` — prompt content assertions.

  **Acceptance Criteria**:
  - [ ] Manual callers can supply historical outdated titles without setting `is_scheduled=True`.
  - [ ] Prompt output contains those titles under `# Outdated News` in stable order.
  - [ ] Duplicate titles in the supplied historical list are rendered once.
  - [ ] `uv run pytest tests/test_llm_analyzer_cache_integration.py -k "manual and outdated and prompt" -v` passes.

  **QA Scenarios**:
  ```
  Scenario: Manual prompt renders historical titles
    Tool: Bash
    Steps: Run `uv run pytest tests/test_llm_analyzer_cache_integration.py -k "manual and prompt" -v | tee .sisyphus/evidence/task-4-prompt-history.txt`
    Expected: Tests assert `# Outdated News` contains the supplied historical titles and no scheduled cache lookup is required.
    Evidence: .sisyphus/evidence/task-4-prompt-history.txt

  Scenario: Duplicate historical titles collapse once
    Tool: Bash
    Steps: Run `uv run pytest tests/test_llm_analyzer_cache_integration.py -k "duplicate and outdated" -v | tee .sisyphus/evidence/task-4-prompt-history-error.txt`
    Expected: Prompt contains each historical title once in deterministic order.
    Evidence: .sisyphus/evidence/task-4-prompt-history-error.txt
  ```

  **Commit**: NO | Message: `n/a` | Files: `crypto_news_analyzer/analyzers/llm_analyzer.py`, `tests/test_llm_analyzer_cache_integration.py`

- [ ] 5. Propagate prior-batch result titles into later batch prompts

  **What to do**: In the structured batch-analysis loop, maintain a rolling ordered set of final result titles returned by completed earlier batches in the same run. For batch N>1, merge that rolling set with task 4’s `historical_outdated_titles` before rendering `[Outdated News]`. Only titles from actual emitted final results count; batches returning no new items must leave the rolling set unchanged. Write failing tests first for 2-batch and 3-batch cases, no-new-title middle batch behavior, and exact prompt content passed into later batches.
  **Must NOT do**: Do not use raw input source titles for rolling propagation; do not reset the rolling set between batches of the same run.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` — Reason: stateful multi-batch analyzer behavior with subtle duplication risk.
  - Skills: `[]` — No extra skill required.
  - Omitted: `['git-master']` — Not needed.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: 6, 7, 8 | Blocked By: 4

  **References**:
  - Pattern: `crypto_news_analyzer/analyzers/llm_analyzer.py:_analyze_batch_with_structured_output` — current batch loop and accumulation path.
  - Pattern: `crypto_news_analyzer/analyzers/llm_analyzer.py:analyze_content_batch` — caller entrypoint.
  - Test: `tests/test_llm_analyzer.py:test_batch_processing_with_multiple_batches` — current batching baseline.
  - Test: `tests/test_multi_step_analysis_unit.py` — existing multi-step analysis and semantic dedup coverage.

  **Acceptance Criteria**:
  - [ ] Batch 2 prompt includes titles returned by batch 1.
  - [ ] Batch 3 prompt includes titles returned by batches 1 and 2 even if batch 2 returned zero new titles.
  - [ ] Final merged report contains no duplicate title caused by cross-batch repetition in inputs when the LLM follows the prompt.
  - [ ] `uv run pytest tests/test_llm_analyzer.py tests/test_multi_step_analysis_unit.py -k "batch and outdated" -v` passes.

  **QA Scenarios**:
  ```
  Scenario: Three-batch rolling propagation
    Tool: Bash
    Steps: Run `uv run pytest tests/test_llm_analyzer.py tests/test_multi_step_analysis_unit.py -k "three_batch or prior_batch" -v | tee .sisyphus/evidence/task-5-batch-propagation.txt`
    Expected: Captured prompt assertions show later batches receive earlier emitted titles in `# Outdated News`.
    Evidence: .sisyphus/evidence/task-5-batch-propagation.txt

  Scenario: Empty middle batch preserves prior titles
    Tool: Bash
    Steps: Run `uv run pytest tests/test_llm_analyzer.py tests/test_multi_step_analysis_unit.py -k "empty middle batch or no new titles" -v | tee .sisyphus/evidence/task-5-batch-propagation-error.txt`
    Expected: Batch 3 still receives batch 1 titles when batch 2 contributes none.
    Evidence: .sisyphus/evidence/task-5-batch-propagation-error.txt
  ```

  **Commit**: YES | Message: `update batch analysis to carry forward prior titles` | Files: `crypto_news_analyzer/analyzers/llm_analyzer.py`, `tests/test_llm_analyzer.py`, `tests/test_multi_step_analysis_unit.py`

- [ ] 6. Require HTTP `user_id` and wire recipient-scoped manual dedup through the API job path

  **What to do**: Update `AnalyzeRequest` to require a non-empty trimmed `user_id` matching `^[A-Za-z0-9_-]{1,128}$`, persist it through `AnalyzeJobRecord`, and pass `recipient_key='api:{user_id}'` through the queued analyze job into the coordinator. After the job reaches `completed` with a generated report payload, cache the final filtered report titles derived from the structured analysis items used to render that report (do not parse Markdown) under that recipient and then write the manual success record so the next request can reuse them. Write failing tests first for request validation, missing/invalid `user_id`, recipient-key propagation, and same-user second-run historical injection.
  **Must NOT do**: Do not keep using the hardcoded `chat_id='api'` for manual dedup; do not write history/cache for failed jobs.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` — Reason: API model, async job, and completion semantics change together.
  - Skills: `[]` — No extra skill required.
  - Omitted: `['git-master']` — Not needed.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: 8 | Blocked By: 1, 2, 3, 4, 5

  **References**:
  - Pattern: `crypto_news_analyzer/api_server.py:AnalyzeRequest` — add required `user_id` field here.
  - Pattern: `crypto_news_analyzer/api_server.py:AnalyzeJobRecord` — persist caller identity through async execution.
  - Pattern: `crypto_news_analyzer/api_server.py:enqueue_analyze_job` and `_run_analyze_job` — thread `recipient_key` and defer success writes until completion.
  - Pattern: `crypto_news_analyzer/execution_coordinator.py:analyze_by_time_window` — shared coordinator entrypoint.
  - Test: `tests/test_api_server.py` — HTTP validation and job-path regression home.

  **Acceptance Criteria**:
  - [ ] `POST /analyze` without `user_id` fails with a 4xx validation response.
  - [ ] Invalid `user_id` values (blank, whitespace-only, >128 chars, unsupported chars) fail validation.
  - [ ] Two successful requests with the same `user_id` use the first response’s titles as historical outdated titles on the second run.
  - [ ] Two successful requests with different `user_id` values do not share dedup context.
  - [ ] `uv run pytest tests/test_api_server.py -k "analyze and user_id" -v` passes.

  **QA Scenarios**:
  ```
  Scenario: API validation and same-user reuse
    Tool: Bash
    Steps: Run `uv run pytest tests/test_api_server.py -k "user_id or same_user" -v | tee .sisyphus/evidence/task-6-http-user-id.txt`
    Expected: Validation tests reject bad IDs, and second-run tests assert the same recipient reuses prior titles.
    Evidence: .sisyphus/evidence/task-6-http-user-id.txt

  Scenario: API cross-user isolation
    Tool: Bash
    Steps: Run `uv run pytest tests/test_api_server.py -k "different_user or isolation" -v | tee .sisyphus/evidence/task-6-http-user-id-error.txt`
    Expected: Tests prove `api:user-a` history is never visible to `api:user-b`.
    Evidence: .sisyphus/evidence/task-6-http-user-id-error.txt
  ```

  **Commit**: YES | Message: `add user-scoped dedup context to analyze api` | Files: `crypto_news_analyzer/api_server.py`, `crypto_news_analyzer/execution_coordinator.py`, `tests/test_api_server.py`

- [ ] 7. Wire Telegram manual analyze into recipient-scoped dedup and success caching

  **What to do**: Use `recipient_key='telegram:{chat_id}'` for Telegram manual analyze, pass that key through the manual analyze path, and on `send_report_to_chat()` success cache the delivered report titles derived from the same filtered structured analysis items used to render the outgoing report, then write the successful manual history row. Add failing tests first for chat-scoped history reuse, group-chat semantics keyed by `chat_id`, send-failure no-write behavior, and parity with the HTTP recipient-key contract.
  **Must NOT do**: Do not use Telegram `user_id` as the dedup identity; do not write manual success/cache rows before `send_result.success` is true.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` — Reason: Telegram command flow has separate send-success semantics.
  - Skills: `[]` — No extra skill required.
  - Omitted: `['git-master']` — Not needed.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: 8 | Blocked By: 1, 2, 3, 4, 5

  **References**:
  - Pattern: `crypto_news_analyzer/reporters/telegram_command_handler.py:_handle_analyze_command` — extracts chat context.
  - Pattern: `crypto_news_analyzer/reporters/telegram_command_handler.py:handle_analyze_command` — manual analyze entry.
  - Pattern: `crypto_news_analyzer/reporters/telegram_command_handler.py:_execute_analyze_and_notify` — actual send success point.
  - Pattern: `crypto_news_analyzer/reporters/telegram_sender.py:send_report_to_chat` — gate for successful manual caching/history.
  - Test: `tests/test_main_controller.py` and Telegram command-handler tests in repo — use the existing Telegram-side test home.

  **Acceptance Criteria**:
  - [ ] Telegram `/analyze` uses `telegram:{chat_id}` as the dedup identity.
  - [ ] A second successful `/analyze` in the same chat uses titles from the previous successful chat report window.
  - [ ] A failed Telegram send leaves prior success time and cached titles unchanged.
  - [ ] Different chats do not share dedup context even if their returned titles match.
  - [ ] `uv run pytest tests/test_main_controller.py -k "telegram and analyze" -v` passes.

  **QA Scenarios**:
  ```
  Scenario: Telegram same-chat historical reuse
    Tool: Bash
    Steps: Run `uv run pytest tests/test_main_controller.py -k "telegram and same_chat" -v | tee .sisyphus/evidence/task-7-telegram-recipient.txt`
    Expected: Tests show the second run for one chat injects the prior delivered titles for that same chat only.
    Evidence: .sisyphus/evidence/task-7-telegram-recipient.txt

  Scenario: Telegram send failure preserves prior state
    Tool: Bash
    Steps: Run `uv run pytest tests/test_main_controller.py -k "telegram and send_failure" -v | tee .sisyphus/evidence/task-7-telegram-recipient-error.txt`
    Expected: Tests confirm failed send does not create cached titles or advance last-success history.
    Evidence: .sisyphus/evidence/task-7-telegram-recipient-error.txt
  ```

  **Commit**: YES | Message: `wire telegram manual analyze into recipient dedup flow` | Files: `crypto_news_analyzer/reporters/telegram_command_handler.py`, `crypto_news_analyzer/execution_coordinator.py`, `tests/test_main_controller.py`

- [ ] 8. Lock in regression coverage for scheduled behavior and full manual dedup path

  **What to do**: Add/adjust regression tests proving scheduled/global outdated-news behavior still follows the existing cache path unchanged, while manual HTTP/Telegram paths use the new recipient-scoped path. Run the focused feature suite first, then the broader analyzer/controller/API suite listed in Definition of Done. Fix any failures without broadening scope beyond this plan.
  **Must NOT do**: Do not silently change scheduled cache semantics to recipient-scoped behavior; do not skip regression coverage because targeted unit tests pass.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` — Reason: final integration guardrail across shared analyze/report flows.
  - Skills: `[]` — No extra skill required.
  - Omitted: `['git-master']` — Not needed.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: F1-F4 | Blocked By: 6, 7

  **References**:
  - Pattern: `crypto_news_analyzer/execution_coordinator.py:coordinate_workflow` — scheduled/manual branch behavior.
  - Pattern: `crypto_news_analyzer/analyzers/llm_analyzer.py:_get_formatted_cached_messages` — scheduled/global outdated-news path.
  - Test: `tests/test_llm_analyzer_cache_integration.py` — scheduled/manual prompt regression anchor.
  - Test: `tests/test_api_server.py`, `tests/test_main_controller.py`, `tests/test_llm_analyzer.py`, `tests/test_multi_step_analysis_unit.py` — full feature regression suite.

  **Acceptance Criteria**:
  - [ ] Scheduled/global outdated-news tests still pass without requiring `recipient_key`.
  - [ ] Manual feature tests for HTTP, Telegram, historical anchor windows, and per-batch propagation all pass together.
  - [ ] `uv run pytest tests/test_llm_analyzer_cache_integration.py tests/test_llm_analyzer.py tests/test_multi_step_analysis_unit.py tests/test_api_server.py tests/test_main_controller.py -v` passes.

  **QA Scenarios**:
  ```
  Scenario: Scheduled and manual regression suite
    Tool: Bash
    Steps: Run `uv run pytest tests/test_llm_analyzer_cache_integration.py tests/test_llm_analyzer.py tests/test_multi_step_analysis_unit.py tests/test_api_server.py tests/test_main_controller.py -v | tee .sisyphus/evidence/task-8-regression-suite.txt`
    Expected: Full targeted suite exits 0 with scheduled/global coverage unchanged and manual feature coverage green.
    Evidence: .sisyphus/evidence/task-8-regression-suite.txt

  Scenario: Scheduled path remains legacy/global
    Tool: Bash
    Steps: Run `uv run pytest tests/test_llm_analyzer_cache_integration.py -k "scheduled and legacy" -v | tee .sisyphus/evidence/task-8-regression-suite-error.txt`
    Expected: Tests confirm scheduled outdated-news retrieval still uses the existing global cache path without recipient scoping.
    Evidence: .sisyphus/evidence/task-8-regression-suite-error.txt
  ```

  **Commit**: NO | Message: `n/a` | Files: `tests/test_llm_analyzer_cache_integration.py`, `tests/test_llm_analyzer.py`, `tests/test_multi_step_analysis_unit.py`, `tests/test_api_server.py`, `tests/test_main_controller.py`

## Final Verification Wave (MANDATORY — after ALL implementation tasks)
> 4 review agents run in PARALLEL. ALL must APPROVE. Present consolidated results to user and get explicit "okay" before completing.
> **Do NOT auto-proceed after verification. Wait for user's explicit approval before marking work complete.**
> **Never mark F1-F4 as checked before getting user's okay.** Rejection or user feedback -> fix -> re-run -> present again -> wait for okay.
- [ ] F1. Plan Compliance Audit — oracle
- [ ] F2. Code Quality Review — unspecified-high
- [ ] F3. Real Manual QA — unspecified-high (+ playwright if UI)
- [ ] F4. Scope Fidelity Check — deep

## Commit Strategy
- Commit 1: `add recipient-scoped sent title lookup for manual dedup`
- Commit 2: `update batch analysis to carry forward prior titles`
- Commit 3: `add user-scoped dedup context to analyze api`
- Commit 4: `wire telegram manual analyze into recipient dedup flow`

## Success Criteria
- No manual analyze recipient sees titles from another recipient’s history.
- No later batch can re-emit a title already emitted by an earlier batch in the same run without the LLM first seeing it in `[Outdated News]`.
- Historical outdated-news lookup is based on the previous successful manual run’s timestamp, not current wall-clock time.
- Scheduled analyze/report behavior remains backward-compatible.
