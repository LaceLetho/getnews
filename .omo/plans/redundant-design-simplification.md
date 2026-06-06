# 高置信冗余设计精简计划

## TL;DR
> **Summary**: 以 `docs/plans/remove-is_active-redundancy.md` 为起点，激进删除/合并高置信冗余设计，但所有删除必须有代码证据、迁移策略、调用面验证和自动化回归。高风险候选项只记录为禁止混入核心执行范围。
> **Deliverables**:
> - 删除 Topic 状态双重真源：`is_active` 与 `paused`
> - 删除/合并派生布尔、过期状态、零调用别名、重复 helper、重复 runtime wrapper
> - 更新 schema 迁移、接口/命令/测试、legacy reference guard
> - 输出每个任务的证据文件到 `.omo/evidence/`
> **Effort**: Large
> **Parallel**: YES - 5 waves
> **Critical Path**: T1 baseline inventory → T2/T3/T4 topic state simplification → T15 final guard updates → F1-F4 final verification

## Context

### Original Request
用户要求：参考 `docs/plans/remove-is_active-redundancy.md`，继续寻找更多冗余设计，本次尽量多精简代码。

### Interview Summary
- 用户选择：**激进精简** — deprecated alias、compatibility endpoint、旧 runtime 名称可在证据充分时删除。
- 用户选择：**高置信优先** — 只纳入有明确代码证据和自动化验证的候选项。
- 默认选择：把已有 `is_active/paused` 精简并入同一个大计划。
- 默认测试策略：tests-after；每个任务实现后更新/补充测试并跑针对性回归。

### Metis Review (gaps addressed)
- 添加硬性高置信门槛：定义、调用方、替代规则、兼容影响、迁移/测试必须齐全。
- 核心计划不得删除 `crawl_status`、SQLite 支持、LLM legacy normalizer、crawler adapter 抽象。
- 不得跨越 News `ContentItem` 与 Intelligence `RawIntelligenceItem` 边界。
- 每个删除项必须验证 Python caller、FastAPI route、Telegram command、runtime/config/docs/deployment reference。
- DB 变更必须覆盖旧数据：`is_active=true/false`、`paused`、`archived`、expired/non-expired merge preview。

## Work Objectives

### Core Objective
在不引入功能变更的前提下，删除高置信冗余代码路径和状态真源，让系统状态、API/runtime 分派和 helper 代码更单一、更可验证。

### Deliverables
- 单一 Topic lifecycle 真源：`lifecycle_status ∈ {draft, active, archived}`。
- 无 `is_active` DB 列/索引/领域字段；API 如仍需要 `is_active` 输出，则动态计算或在本激进计划中按任务明确删除。
- 无 `TopicLifecycleStatus.PAUSED`；旧 `paused` 数据迁移到 `archived`。
- `MergePreviewState.EXPIRED` 删除，过期判断只来自 `expires_at`。
- `ChatContext.is_private/is_group` 与 `ValidationResult.is_valid` 改为派生或直接判定，避免保存重复真值。
- 删除零调用 alias/dead code：`run_due_topics()`、`load_auth_from_env()`、`run_ingestion_service()`、`ExecutionMode`、`plugin_system_example.py` 等。
- 合并重复 helper：topic service factory、datasource tag normalization、runtime API service bootstrap、webhook path default。
- 更新测试、文档、banned legacy reference scan。

### Definition of Done (verifiable conditions with commands)
- `uv run pytest tests/ -v`
- `uv run mypy crypto_news_analyzer/`
- `uv run flake8 crypto_news_analyzer/`
- `uv run python tests/helpers/banned_legacy_reference_scan.py`
- `uv run python scripts/dump_routes.py > .omo/evidence/routes-after-redundant-design-simplification.txt`
- No source reference remains for banned removed symbols except migrations/tests that intentionally assert absence.

### Must Have
- Every deletion has a replacement rule or explicit absence proof.
- Persisted field/enum removals include migration/backfill tests.
- Tests cover happy path and failure/edge cases per task.
- API/Telegram/runtime command surfaces are inventoried before and after relevant tasks.

### Must NOT Have
- MUST NOT collapse News and Intelligence bounded contexts.
- MUST NOT pass `RawIntelligenceItem` into News analyzers or `ContentItem` into Intelligence research.
- MUST NOT remove `crawl_status` in core waves.
- MUST NOT drop SQLite support or SQLite stub repositories in core waves.
- MUST NOT remove LLM legacy normalizers in core waves.
- MUST NOT collapse `RSSCrawlerAdapter` / `XCrawlerAdapter` in core waves.
- MUST NOT opportunistically refactor unrelated analyzer/reporting behavior.

## Verification Strategy
> ZERO HUMAN INTERVENTION - all verification is agent-executed.
- Test decision: tests-after using existing pytest suite; add/update focused tests per task.
- QA policy: Every task has agent-executed scenarios.
- Evidence: `.omo/evidence/task-{N}-{slug}.{ext}`.

## Execution Strategy

### Parallel Execution Waves
> Target: 5-8 tasks per wave. <3 per wave (except final) = under-splitting.
> Extract shared dependencies as Wave-1 tasks for max parallelism.

Wave 1: T1 baseline inventory; T2 topic domain model; T5 MergePreview expiry; T6 derived value cleanup; T7 datasource tag normalizer.
Wave 2: T3 topic storage/schema; T8 service factory consolidation; T10 runtime wrapper simplification; T12 dead alias/dead file deletion.
Wave 3: T4 topic API/Telegram/tests; T9 repository no-op/alias cleanup; T11 API factory parameter simplification; T13 deprecated semantic command removal.
Wave 4: T14 duplicate execution/result model cleanup; T15 legacy guard/docs/test inventory updates.
Wave 5: Final verification wave F1-F4.

### Dependency Matrix (full, all tasks)
- T1 blocks all deletion tasks.
- T2 blocks T3 and T4.
- T3 blocks T4.
- T5 independent after T1.
- T6 independent after T1.
- T7 independent after T1.
- T8 independent after T1.
- T9 independent after T1.
- T10 blocks T11.
- T12 independent after T1.
- T13 requires T1 route/command inventory.
- T14 requires T1 caller inventory.
- T15 depends on T2-T14.
- F1-F4 depend on T15.

### Agent Dispatch Summary (wave → task count → categories)
- Wave 1 → 5 tasks → unspecified-high, quick
- Wave 2 → 4 tasks → unspecified-high, quick
- Wave 3 → 4 tasks → unspecified-high
- Wave 4 → 2 tasks → unspecified-high, writing
- Wave 5 → 4 review tasks → oracle, unspecified-high, deep

## Candidate Confidence Matrix

| Candidate | Core? | Reason |
|---|---:|---|
| `is_active` + `lifecycle_status` | YES | Existing plan proves full derivation and inconsistency bug |
| `PAUSED` + `ARCHIVED` | YES | No behavior distinction; both exclude research |
| `MergePreviewState.EXPIRED` + `expires_at` | YES | Expired state is cached result of timestamp comparison |
| `ChatContext.is_private/is_group` | YES | Purely derived from `chat_type` |
| `ValidationResult.is_valid` | YES | Purely derived from `errors` |
| Duplicate tag normalizer | YES | Identical implementation in two files |
| Duplicate topic service factories | YES | Same construction logic in API and Telegram surfaces |
| Repository aliases / `_json_value` / redundant ALTERs | YES | Pass-through/no-op/no-op startup schema statements |
| Runtime wrappers/API factory args | YES | Same runtime behavior with duplicated wrappers |
| `/news_semantic_search` | YES | Deprecated alias and user approved aggressive cleanup |
| `crawl_status` removal | NO | High-risk replacement needed via `ingestion_jobs`; excluded |
| SQLite removal/stub deletion | NO | Backend support decision not confirmed; excluded |
| LLM legacy normalizer removal | NO | Requires prompt/output proof; excluded |
| RSS/X adapter collapse | NO | Production path uses adapters; excluded |

## TODOs
> Implementation + Test = ONE task. Never separate.
> EVERY task MUST have: Agent Profile + Parallelization + QA Scenarios.

- [x] 1. Baseline current call surfaces and deletion evidence gates

  **What to do**: Create `.omo/evidence/task-1-baseline-inventory.md` containing current route list, Telegram command registration list, symbol caller/reference inventory for all planned removals, and current banned legacy scan output. Use LSP/codegraph where possible, plus `scripts/dump_routes.py` and existing tests/helpers scan. Do not modify production source in this task except evidence files if the executor is allowed by their mode; if not allowed, keep evidence in task output.
  **Must NOT do**: Do not delete or edit application code in this task. Do not mark candidates safe without checking route/command/config/docs references.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: broad but read-heavy verification across API, Telegram, runtime, tests, and docs.
  - Skills: [] - no special external service needed.
  - Omitted: [`use-railway`] - no production infrastructure operation.

  **Parallelization**: Can Parallel: NO | Wave 1 | Blocks: T2-T15 | Blocked By: none

  **References**:
  - Pattern: `tests/helpers/banned_legacy_reference_scan.py` - existing guard pattern to extend later.
  - Pattern: `scripts/dump_routes.py` - route inventory generator.
  - Pattern: `crypto_news_analyzer/reporters/telegram_command_handler.py` - command registration and help text.
  - Pattern: `docs/plans/remove-is_active-redundancy.md` - prior evidence standard.

  **Acceptance Criteria**:
  - [ ] Evidence file lists every planned symbol/route/command and whether references exist in `crypto_news_analyzer/`, `tests/`, `docs/`, `Dockerfile`, `docker-entrypoint.sh`, and `README.md`.
  - [ ] `uv run python scripts/dump_routes.py` completes and output is stored or pasted into evidence.
  - [ ] `uv run python tests/helpers/banned_legacy_reference_scan.py` completes and baseline result is recorded.

  **QA Scenarios**:
  ```
  Scenario: Baseline route inventory
    Tool: Bash
    Steps: Run `uv run python scripts/dump_routes.py > .omo/evidence/task-1-routes-before.txt`
    Expected: Command exits 0 and file contains `/health`, `/analyze`, and `/semantic-search` routes.
    Evidence: .omo/evidence/task-1-routes-before.txt

  Scenario: Legacy scan baseline
    Tool: Bash
    Steps: Run `uv run python tests/helpers/banned_legacy_reference_scan.py > .omo/evidence/task-1-legacy-scan-before.txt`
    Expected: Command exits 0 or known baseline violations are explicitly listed for later removal.
    Evidence: .omo/evidence/task-1-legacy-scan-before.txt
  ```

  **Commit**: NO | Message: `refactor(audit): capture redundancy baseline` | Files: [.omo/evidence/*]

- [x] 2. Simplify Topic lifecycle domain model

  **What to do**: In `crypto_news_analyzer/domain/models.py`, remove `TopicLifecycleStatus.PAUSED`, remove `IntelligenceTopic.is_active`, and update `IntelligenceTopic.__post_init__` / `from_dict` so `lifecycle_status` is the sole state source. Preserve `draft`, `active`, `archived`. Update any model serialization tests to expect no persisted domain `is_active` field and no `paused` enum.
  **Must NOT do**: Do not change API response compatibility in this task; API/Telegram response/command behavior is T4. Do not remove `archived_at`/status timestamp pairs on prompts/findings.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: persisted domain model change with migration downstream.
  - Skills: [] - code/test only.
  - Omitted: [`security-research`] - not a vulnerability audit.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: T3, T4 | Blocked By: T1

  **References**:
  - Pattern: `docs/plans/remove-is_active-redundancy.md:41-67` - model-layer steps.
  - API/Type: `crypto_news_analyzer/domain/models.py:TopicLifecycleStatus` - enum to reduce.
  - API/Type: `crypto_news_analyzer/domain/models.py:IntelligenceTopic` - field and validation target.
  - Test: `tests/test_intelligence_models.py` or current equivalent from T1 inventory - update lifecycle assertions.

  **Acceptance Criteria**:
  - [ ] No `TopicLifecycleStatus.PAUSED` reference remains outside migration/backward-compat tests.
  - [ ] `IntelligenceTopic` instances serialize without `is_active` as a domain field.
  - [ ] Topic lifecycle model tests pass with `draft`, `active`, `archived` only.

  **QA Scenarios**:
  ```
  Scenario: Active topic remains active by lifecycle_status
    Tool: Bash
    Steps: Run focused intelligence model tests, e.g. `uv run pytest tests/ -k "IntelligenceTopic or TopicLifecycleStatus" -v`
    Expected: Active topic is represented only by lifecycle_status='active'; no is_active assertion required.
    Evidence: .omo/evidence/task-2-topic-model-tests.txt

  Scenario: Paused enum rejected or absent
    Tool: Bash
    Steps: Run `uv run python - <<'PY'
from crypto_news_analyzer.domain.models import TopicLifecycleStatus
print([s.value for s in TopicLifecycleStatus])
assert 'paused' not in [s.value for s in TopicLifecycleStatus]
PY`
    Expected: Script exits 0 and prints only draft/active/archived.
    Evidence: .omo/evidence/task-2-paused-absent.txt
  ```

  **Commit**: NO | Message: `refactor(intelligence): simplify topic lifecycle model` | Files: [crypto_news_analyzer/domain/models.py, tests/*]

- [x] 3. Migrate Topic storage/repository from `is_active` to lifecycle status

  **What to do**: Update repository interfaces and storage methods so topic listing/counting filter by `lifecycle_status` instead of `is_active`. In `storage/intelligence_schema.py`, migrate existing `paused` rows to `archived`, drop `is_active` column and `idx_intelligence_topics_active`, and remove writes/reads of `is_active` in `storage/data_manager.py` and `storage/repositories.py`.
  **Must NOT do**: Do not leave dual query parameters (`is_active` and `lifecycle_status`) except in a migration-only compatibility read if absolutely required and tested. Do not drop unrelated columns.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: DB/schema/repository migration.
  - Skills: [] - local tests only.
  - Omitted: [`use-railway`] - no deployment or production DB mutation.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: T4 | Blocked By: T2

  **References**:
  - Pattern: `docs/plans/remove-is_active-redundancy.md:68-126` - repository/data/schema migration steps.
  - Pattern: `crypto_news_analyzer/storage/intelligence_schema.py` - topic table/index definitions.
  - Pattern: `crypto_news_analyzer/storage/data_manager.py:upsert_intelligence_topic` - remove `is_active` persistence.
  - API/Type: `crypto_news_analyzer/domain/repositories.py:list_topics/count_topics` - signature change.

  **Acceptance Criteria**:
  - [ ] `list_topics(lifecycle_status='active')` and `count_topics(lifecycle_status='active')` replace `is_active=True` everywhere.
  - [ ] Schema initialization updates old `paused` data to `archived` before enum reduction can break reads.
  - [ ] No `idx_intelligence_topics_active` or `is_active` column creation remains.

  **QA Scenarios**:
  ```
  Scenario: Migration converts paused and removes is_active
    Tool: Bash
    Steps: Run storage/schema tests with fixture rows for active, draft, paused, archived topics.
    Expected: paused rows read back as archived; active filtering returns only lifecycle_status='active'.
    Evidence: .omo/evidence/task-3-topic-storage-migration.txt

  Scenario: No topic storage reference to is_active
    Tool: Bash
    Steps: Run `uv run python tests/helpers/banned_legacy_reference_scan.py` after extending banned terms in T15, or run structural reference check from T1.
    Expected: No production references to topic `is_active` remain outside API response compatibility if T4 keeps dynamic output.
    Evidence: .omo/evidence/task-3-is-active-absence.txt
  ```

  **Commit**: NO | Message: `refactor(storage): use lifecycle status for topics` | Files: [crypto_news_analyzer/domain/repositories.py, crypto_news_analyzer/storage/intelligence_schema.py, crypto_news_analyzer/storage/data_manager.py, crypto_news_analyzer/storage/repositories.py, tests/*]

- [x] 4. Remove Topic pause API/Telegram surfaces and use archive-only inactive state

  **What to do**: Update `api_server.py`, `reporters/telegram/intelligence_commands.py`, and Telegram help/docs so topic pause/archive behavior matches the simplified lifecycle. Because user approved aggressive simplification, the decision is fixed: **delete the REST `POST /intelligence/topics/{id}/pause` route and delete Telegram `/topic_pause` command registration/help text**. Keep `/topic_archive` and archive endpoints as the only inactive-state transition. Tests must assert the pause route/command is absent and archive still works.
  **Must NOT do**: Do not reintroduce `paused` in responses. Do not keep two inactive states in user-facing docs.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: API/Telegram contract changes with tests.
  - Skills: [] - no Railway/Telegram live bot required.
  - Omitted: [`steel-browser`] - no browser UI.

  **Parallelization**: Can Parallel: NO | Wave 3 | Blocks: T15 | Blocked By: T2, T3

  **References**:
  - Pattern: `docs/plans/remove-is_active-redundancy.md:82-113` - caller/API changes.
  - Pattern: `crypto_news_analyzer/api_server.py` - topic list/detail/pause endpoints and response serializers.
  - Pattern: `crypto_news_analyzer/reporters/telegram/intelligence_commands.py` - topic pause/list command logic.
  - Test: `tests/test_topic_findings_api.py`, `tests/test_topic_findings_telegram.py`, `tests/test_topic_research_scheduler.py` or current equivalents from T1.

  **Acceptance Criteria**:
  - [ ] API topic list/detail never returns `lifecycle_status='paused'`.
  - [ ] Telegram topic commands never display paused as a state.
  - [ ] REST pause route is absent from `scripts/dump_routes.py` output.
  - [ ] Telegram `/topic_pause` is absent from command registration and help text.

  **QA Scenarios**:
  ```
  Scenario: Archive replaces pause in API
    Tool: Bash
    Steps: Run focused API tests for `/intelligence/topics` lifecycle transitions.
    Expected: Archive transition yields lifecycle_status='archived'; pause route is absent; paused is absent from response body.
    Evidence: .omo/evidence/task-4-topic-api-lifecycle.txt

  Scenario: Telegram topic list excludes paused
    Tool: Bash
    Steps: Run focused Telegram intelligence command tests.
    Expected: `/topic_list` active filter uses lifecycle_status='active'; `/topic_pause` is not registered; no paused help/list output remains.
    Evidence: .omo/evidence/task-4-topic-telegram-lifecycle.txt
  ```

  **Commit**: NO | Message: `refactor(intelligence): remove paused topic surface` | Files: [crypto_news_analyzer/api_server.py, crypto_news_analyzer/reporters/telegram/intelligence_commands.py, tests/*, README.md, docs/*]

- [x] 5. Remove `MergePreviewState.EXPIRED` and derive expiry from `expires_at`

  **What to do**: In `domain/models.py`, remove `MergePreviewState.EXPIRED`. In `storage/repositories.py`, change `accept_merge_preview` so expired previews return failure without mutating `state='expired'`. Keep `state='applied'` and `applied_at` because `applied_at` has independent audit value. Ensure list/filter logic uses `expires_at <= now` / `expires_at > now` only.
  **Must NOT do**: Do not remove `applied_at`. Do not compare naive local time to UTC-aware timestamps without normalization.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: persisted state enum cleanup and time edge cases.
  - Skills: [] - code/test only.
  - Omitted: [] - none.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: T15 | Blocked By: T1

  **References**:
  - API/Type: `crypto_news_analyzer/domain/models.py:MergePreviewState` - remove `EXPIRED` value.
  - Pattern: `crypto_news_analyzer/storage/repositories.py:accept_merge_preview` - expiry mutation target.
  - Pattern: `crypto_news_analyzer/storage/repositories.py:list_merge_previews` - expiry filter source of truth.

  **Acceptance Criteria**:
  - [ ] `MergePreviewState` has no `EXPIRED` value.
  - [ ] Expired pending previews are excluded by `expires_at`, not by state mutation.
  - [ ] Accepting expired preview fails without changing state.

  **QA Scenarios**:
  ```
  Scenario: Non-expired preview can be applied
    Tool: Bash
    Steps: Run merge preview tests with expires_at in the future.
    Expected: State transitions to applied and applied_at is populated.
    Evidence: .omo/evidence/task-5-merge-preview-apply.txt

  Scenario: Expired preview is rejected without expired state
    Tool: Bash
    Steps: Run merge preview test fixture with expires_at in the past.
    Expected: accept returns false/error; state remains pending or unchanged; query exclusion comes from expires_at.
    Evidence: .omo/evidence/task-5-merge-preview-expired.txt
  ```

  **Commit**: NO | Message: `refactor(intelligence): derive merge preview expiry from timestamp` | Files: [crypto_news_analyzer/domain/models.py, crypto_news_analyzer/storage/repositories.py, tests/*]

- [x] 6. Replace derived boolean fields with source-field checks

  **What to do**: Convert `ChatContext.is_private` and `ChatContext.is_group` in `models.py` into properties derived from `chat_type`, and update `telegram_command_handler.py` construction sites to stop passing redundant booleans. Remove `ValidationResult.is_valid` from `structured_output_manager.py` and update consumers to check `not result.errors`.
  **Must NOT do**: Do not change Telegram authorization semantics for `private`, `group`, `supergroup`, or `channel`. Do not remove `errors`/`warnings` diagnostic details.

  **Recommended Agent Profile**:
  - Category: `quick` - Reason: local model/helper cleanup with targeted tests.
  - Skills: [] - none.
  - Omitted: [] - none.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: T15 | Blocked By: T1

  **References**:
  - API/Type: `crypto_news_analyzer/models.py:ChatContext` - derived boolean fields.
  - Pattern: `crypto_news_analyzer/reporters/telegram_command_handler.py` - construction of `ChatContext` from chat type.
  - API/Type: `crypto_news_analyzer/analyzers/structured_output_manager.py:ValidationResult` - `is_valid` removal.
  - Pattern: `crypto_news_analyzer/analyzers/llm_analyzer.py` - validation consumer.

  **Acceptance Criteria**:
  - [ ] `ChatContext(chat_type='private').is_private is True` and `.is_group is False`.
  - [ ] `ChatContext(chat_type='group'|'supergroup').is_group is True`.
  - [ ] `ChatContext(chat_type='channel')` has both properties false unless existing tests prove other expected behavior.
  - [ ] No `ValidationResult.is_valid` field or consumer remains.

  **QA Scenarios**:
  ```
  Scenario: Telegram chat type derivation
    Tool: Bash
    Steps: Run Telegram command handler authorization/context tests.
    Expected: private/group/supergroup/channel derivations match old behavior.
    Evidence: .omo/evidence/task-6-chat-context-tests.txt

  Scenario: Structured output validation derives validity
    Tool: Bash
    Steps: Run analyzer structured output tests with empty and non-empty error lists.
    Expected: Empty errors proceeds; non-empty errors triggers validation failure path without is_valid field.
    Evidence: .omo/evidence/task-6-validation-result-tests.txt
  ```

  **Commit**: NO | Message: `refactor(models): derive validation and chat booleans` | Files: [crypto_news_analyzer/models.py, crypto_news_analyzer/reporters/telegram_command_handler.py, crypto_news_analyzer/analyzers/structured_output_manager.py, crypto_news_analyzer/analyzers/llm_analyzer.py, tests/*]

- [x] 7. Consolidate datasource tag normalization

  **What to do**: Keep one canonical `normalize_datasource_tags()` implementation. Preferred location: `crypto_news_analyzer/datasource_payloads.py` if it has no import cycle with `domain/models.py`; otherwise extract to `crypto_news_analyzer/utils/tags.py`. Update `domain/models.py` `DataSource` and `SafeDataSourceSummary` to use the canonical helper.
  **Must NOT do**: Do not change tag semantics: trim, lowercase, deduplicate, sorted output, max 16 tags, max 32 chars.

  **Recommended Agent Profile**:
  - Category: `quick` - Reason: small duplicate helper consolidation.
  - Skills: [] - none.
  - Omitted: [] - none.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: T15 | Blocked By: T1

  **References**:
  - Pattern: `crypto_news_analyzer/datasource_payloads.py:normalize_datasource_tags` - canonical behavior.
  - Pattern: `crypto_news_analyzer/domain/models.py:_normalize_datasource_tags` - duplicate to remove.
  - Test: `tests/test_intelligence_datasource_payloads.py`, `tests/test_datasource_repository.py`, `tests/test_topic_datasource_models.py` or current equivalents.

  **Acceptance Criteria**:
  - [ ] Only one tag normalization implementation remains.
  - [ ] Existing tag validation constraints still pass.
  - [ ] No import cycle introduced.

  **QA Scenarios**:
  ```
  Scenario: Tags normalize identically after consolidation
    Tool: Bash
    Steps: Run datasource payload/model tests with mixed case, whitespace, duplicates, too many tags, and long tags.
    Expected: Valid tags sorted/lowercased/deduped; invalid constraints still rejected.
    Evidence: .omo/evidence/task-7-tag-normalization.txt

  Scenario: Domain model import remains acyclic
    Tool: Bash
    Steps: Run `uv run python - <<'PY'
from crypto_news_analyzer.domain.models import DataSource, SafeDataSourceSummary
from crypto_news_analyzer.datasource_payloads import normalize_datasource_tags
print('ok')
PY`
    Expected: Script exits 0 and prints ok.
    Evidence: .omo/evidence/task-7-import-cycle-check.txt
  ```

  **Commit**: NO | Message: `refactor(datasources): consolidate tag normalization` | Files: [crypto_news_analyzer/datasource_payloads.py, crypto_news_analyzer/domain/models.py, tests/*]

- [x] 8. Consolidate topic workflow and merge service factories

  **What to do**: Extract duplicated `_get_topic_prompt_workflow_service()` and `_get_topic_finding_merge_service()` construction logic from `api_server.py` and `reporters/telegram_command_handler.py` into a shared helper module, e.g. `crypto_news_analyzer/intelligence/service_factory.py`. Preserve Telegram-side caching if it exists; helper should create services from controller dependencies consistently.
  **Must NOT do**: Do not change prompt generation, merge behavior, LLM provider selection, or controller initialization order.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: shared helper used by API and Telegram surfaces.
  - Skills: [] - none.
  - Omitted: [`llm-instructor`] - no LLM API behavior change.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: T15 | Blocked By: T1

  **References**:
  - Pattern: `crypto_news_analyzer/api_server.py:_get_topic_prompt_workflow_service` - duplicate helper.
  - Pattern: `crypto_news_analyzer/api_server.py:_get_topic_finding_merge_service` - duplicate helper.
  - Pattern: `crypto_news_analyzer/reporters/telegram_command_handler.py:_get_topic_prompt_workflow_service` - duplicate helper.
  - Pattern: `crypto_news_analyzer/reporters/telegram_command_handler.py:_get_topic_finding_merge_service` - duplicate helper.

  **Acceptance Criteria**:
  - [ ] API and Telegram both use the same service factory helper.
  - [ ] No duplicate construction logic remains in both surfaces.
  - [ ] Prompt lifecycle and merge tests still pass.

  **QA Scenarios**:
  ```
  Scenario: API topic prompt service still works
    Tool: Bash
    Steps: Run focused API tests for topic create/revise/confirm/prompt endpoints.
    Expected: Same service behavior; no missing dependency errors.
    Evidence: .omo/evidence/task-8-api-topic-service-factory.txt

  Scenario: Telegram topic prompt and merge services still work
    Tool: Bash
    Steps: Run focused Telegram intelligence command tests for create/revise/merge.
    Expected: Same service behavior; caching does not return stale or missing service objects.
    Evidence: .omo/evidence/task-8-telegram-topic-service-factory.txt
  ```

  **Commit**: NO | Message: `refactor(intelligence): share topic service factories` | Files: [crypto_news_analyzer/intelligence/service_factory.py, crypto_news_analyzer/api_server.py, crypto_news_analyzer/reporters/telegram_command_handler.py, tests/*]

- [x] 9. Remove repository no-op branches, aliases, and redundant startup ALTERs

  **What to do**: Remove one-line repository alias methods (`create_*` -> `save_*`, `get_*_by_id` duplicates) after updating callers to canonical names. Replace `_json_value()` no-op branch with a single expression or inline it. Remove redundant `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` statements for `semantic_search_jobs` when those columns are already present in `CREATE TABLE`. Keep actual migration-required ALTERs if T1 proves they are still needed for old DBs.
  **Must NOT do**: Do not remove repository protocol methods still required by tests or public abstractions. Do not delete schema migration support for real old production DBs without explicit evidence.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: repository interface cleanup and schema init guard.
  - Skills: [] - none.
  - Omitted: [] - none.

  **Parallelization**: Can Parallel: YES | Wave 3 | Blocks: T15 | Blocked By: T1

  **References**:
  - Pattern: `crypto_news_analyzer/domain/repositories.py` - ABC alias methods.
  - Pattern: `crypto_news_analyzer/storage/repositories.py` - implementation aliases and `_json_value`.
  - Pattern: `crypto_news_analyzer/storage/data_manager.py` - `semantic_search_jobs` CREATE/ALTER statements.

  **Acceptance Criteria**:
  - [ ] Canonical repository methods are used consistently.
  - [ ] No `_json_value` backend branch returns identical expressions.
  - [ ] Schema initialization for fresh DB still creates complete `semantic_search_jobs` table.

  **QA Scenarios**:
  ```
  Scenario: Repository canonical methods still persist entities
    Tool: Bash
    Steps: Run intelligence repository tests for prompts, findings, research runs, and merge previews.
    Expected: save/get/list operations pass with canonical methods only.
    Evidence: .omo/evidence/task-9-repository-alias-tests.txt

  Scenario: Fresh schema creates semantic_search_jobs columns
    Tool: Bash
    Steps: Run storage initialization tests or a temp DB schema init check that introspects semantic_search_jobs columns.
    Expected: processing_step, normalized_intent, matched_count, retained_count, decomposition_json, result, error_message, started_at, completed_at, source exist.
    Evidence: .omo/evidence/task-9-semantic-schema-columns.txt
  ```

  **Commit**: NO | Message: `refactor(storage): remove repository aliases and no-op schema branches` | Files: [crypto_news_analyzer/domain/repositories.py, crypto_news_analyzer/storage/repositories.py, crypto_news_analyzer/storage/data_manager.py, tests/*]

- [x] 10. Merge API runtime service wrappers

  **What to do**: In `main.py`, replace near-duplicate `run_analysis_service()` and `run_api_only_service()` with one private `_run_api_service(config_path, enable_telegram: bool, mode: str)` helper. Replace thin `run_ingestion_service()` with direct use of `run_ingestion_loop()` or remove wrapper if no external caller remains. Preserve supported CLI modes: `analysis-service`, `api-only`, `ingestion`, `embedding-backfill`.
  **Must NOT do**: Do not resurrect deprecated `api-server`, `once`, `schedule`, or `scheduler` modes. Do not change production mode names.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: runtime entrypoint refactor.
  - Skills: [] - none.
  - Omitted: [`use-railway`] - no deployment.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: T11, T15 | Blocked By: T1

  **References**:
  - Pattern: `crypto_news_analyzer/main.py:run_analysis_service` - duplicate runtime function.
  - Pattern: `crypto_news_analyzer/main.py:run_api_only_service` - duplicate runtime function.
  - Pattern: `crypto_news_analyzer/main.py:run_ingestion_service` - thin wrapper.
  - Test: `tests/shared/test_ingestion_runtime.py`, `tests/shared/test_docker_entrypoint_legacy_alias_rejection.py`.

  **Acceptance Criteria**:
  - [ ] `analysis-service` still starts API with Telegram command listener enabled.
  - [ ] `api-only` still starts API without Telegram command listener.
  - [ ] `ingestion` still starts ingestion loop.
  - [ ] Legacy banned modes remain rejected.

  **QA Scenarios**:
  ```
  Scenario: Runtime modes dispatch unchanged
    Tool: Bash
    Steps: Run runtime dispatch tests for analysis-service, api-only, ingestion, embedding-backfill.
    Expected: Supported modes map to same behavior as before; no duplicated wrapper required.
    Evidence: .omo/evidence/task-10-runtime-dispatch.txt

  Scenario: Legacy modes remain rejected
    Tool: Bash
    Steps: Run `uv run pytest tests/shared/test_docker_entrypoint_legacy_alias_rejection.py -v`
    Expected: Deprecated modes like api-server/once/schedule stay rejected.
    Evidence: .omo/evidence/task-10-legacy-mode-rejection.txt
  ```

  **Commit**: NO | Message: `refactor(runtime): consolidate API service entrypoints` | Files: [crypto_news_analyzer/main.py, tests/*]

- [x] 11. Simplify `create_api_server` startup parameters

  **What to do**: Replace `create_api_server(start_services=True, start_scheduler=None, start_command_listener=None)` with explicit booleans such as `enable_scheduler=False` and `enable_telegram=False`. Update call sites in `main.py` and `scripts/dump_routes.py`. Preserve exact startup behavior from T10: analysis-service enables Telegram, api-only disables Telegram and scheduler, route dumping starts no background services.
  **Must NOT do**: Do not start scheduler/listener during route dump or tests. Do not change route registration.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: API factory signature refactor with runtime implications.
  - Skills: [] - none.
  - Omitted: [] - none.

  **Parallelization**: Can Parallel: YES | Wave 3 | Blocks: T15 | Blocked By: T10

  **References**:
  - API/Type: `crypto_news_analyzer/api_server.py:create_api_server` - signature target.
  - Pattern: `crypto_news_analyzer/main.py` - runtime call sites.
  - Pattern: `scripts/dump_routes.py` - no-services route inventory call site.

  **Acceptance Criteria**:
  - [ ] `create_api_server` no longer has `start_services` or nullable startup flags.
  - [ ] Route inventory before/after is unchanged except intentionally removed routes from T4/T13.
  - [ ] No tests unexpectedly start background services.

  **QA Scenarios**:
  ```
  Scenario: Route dump starts no background services
    Tool: Bash
    Steps: Run `uv run python scripts/dump_routes.py > .omo/evidence/task-11-routes-after-api-factory.txt`
    Expected: Command exits 0 without starting scheduler/Telegram listener; routes match expected inventory.
    Evidence: .omo/evidence/task-11-routes-after-api-factory.txt

  Scenario: API tests use explicit startup flags
    Tool: Bash
    Steps: Run `uv run pytest tests/news/test_api_server.py -v`
    Expected: API tests pass without implicit service startup side effects.
    Evidence: .omo/evidence/task-11-api-server-tests.txt
  ```

  **Commit**: NO | Message: `refactor(api): make server startup flags explicit` | Files: [crypto_news_analyzer/api_server.py, crypto_news_analyzer/main.py, scripts/dump_routes.py, tests/*]

- [x] 12. Delete zero-caller aliases and dead example code

  **What to do**: Delete `ConfigManager.load_auth_from_env()` if T1 confirms zero callers; delete `TopicResearchScheduler.run_due_topics()` alias if zero callers; delete unused `ExecutionMode` enum and dependent `ExecutionInfo/ExecutionResult` only if T14 covers model unification; delete `crawlers/plugin_system_example.py` or move it out of package if project wants to preserve example content. For this plan decision: **delete the example file from package; do not move to docs unless tests/docs require it**.
  **Must NOT do**: Do not delete production crawlers or adapter classes. Do not delete `AuthConfig.from_env()` here unless T14 or tests prove it is only a test convenience.

  **Recommended Agent Profile**:
  - Category: `quick` - Reason: zero-caller deletion with tests.
  - Skills: [] - none.
  - Omitted: [] - none.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: T15 | Blocked By: T1

  **References**:
  - Pattern: `crypto_news_analyzer/config/manager.py:load_auth_from_env` - dead alias.
  - Pattern: `crypto_news_analyzer/intelligence/topic_research.py:run_due_topics` - dead alias.
  - Pattern: `crypto_news_analyzer/crawlers/plugin_system_example.py` - dead demo code.
  - Pattern: `crypto_news_analyzer/execution_coordinator.py:ExecutionMode` - unused enum candidate.

  **Acceptance Criteria**:
  - [ ] No production/test import references deleted symbols/files.
  - [ ] Package import of `crypto_news_analyzer.crawlers` still succeeds.
  - [ ] Runtime/config tests pass.

  **QA Scenarios**:
  ```
  Scenario: Deleted aliases have no references
    Tool: Bash
    Steps: Run T1 reference inventory commands for `load_auth_from_env`, `run_due_topics`, and `plugin_system_example` after deletion.
    Expected: No references remain outside changelog/evidence files.
    Evidence: .omo/evidence/task-12-dead-alias-reference-check.txt

  Scenario: Package imports remain healthy
    Tool: Bash
    Steps: Run `uv run python - <<'PY'
import crypto_news_analyzer
import crypto_news_analyzer.crawlers
from crypto_news_analyzer.config.manager import ConfigManager
print('ok')
PY`
    Expected: Script exits 0 and prints ok.
    Evidence: .omo/evidence/task-12-import-check.txt
  ```

  **Commit**: NO | Message: `refactor(cleanup): delete dead aliases and examples` | Files: [crypto_news_analyzer/config/manager.py, crypto_news_analyzer/intelligence/topic_research.py, crypto_news_analyzer/crawlers/plugin_system_example.py, crypto_news_analyzer/execution_coordinator.py, tests/*]

- [x] 13. Remove deprecated `/news_semantic_search` Telegram alias

  **What to do**: Remove `/news_semantic_search` command registration, handler wrapper, help text mention, docs mention, and tests that expect alias availability. Keep canonical `/semantic_search` unchanged. Because user approved aggressive cleanup, final behavior should be: `/news_semantic_search` is not registered. If command table tests require a graceful message, implement a generic unknown-command path, not a dedicated alias.
  **Must NOT do**: Do not change `/semantic_search` semantics, output format, or unified News+Intelligence retrieval behavior.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: user-facing Telegram command removal.
  - Skills: [] - no live Telegram.
  - Omitted: [`steel-browser`] - no browser UI.

  **Parallelization**: Can Parallel: YES | Wave 3 | Blocks: T15 | Blocked By: T1

  **References**:
  - Pattern: `crypto_news_analyzer/reporters/telegram_command_handler.py` - `/news_semantic_search` registration/handler/help text.
  - Pattern: `README.md` - command list says `/news_semantic_search` is deprecated alias.
  - Test: `tests/news/test_telegram_command_handler_semantic_search.py` or current equivalent.

  **Acceptance Criteria**:
  - [ ] `/semantic_search` command still registered and tested.
  - [ ] `/news_semantic_search` command no longer registered or documented.
  - [ ] Unified semantic search still returns News and Intelligence source breakdown.

  **QA Scenarios**:
  ```
  Scenario: Canonical semantic search still works
    Tool: Bash
    Steps: Run `uv run pytest tests/ -k "semantic_search and telegram" -v`
    Expected: `/semantic_search` tests pass and use canonical command only.
    Evidence: .omo/evidence/task-13-semantic-search-canonical.txt

  Scenario: Deprecated alias absent
    Tool: Bash
    Steps: Run command registration inspection from T1 for `news_semantic_search`.
    Expected: No command registration/help/docs mention remains outside evidence.
    Evidence: .omo/evidence/task-13-news-semantic-search-absence.txt
  ```

  **Commit**: NO | Message: `refactor(telegram): remove deprecated semantic search alias` | Files: [crypto_news_analyzer/reporters/telegram_command_handler.py, README.md, docs/*, tests/*]

- [x] 14. Unify duplicate execution/result models and rename ambiguous analysis result

  **What to do**: Resolve duplicate `ExecutionInfo` and `ExecutionResult` definitions in `models.py` and `execution_coordinator.py`. Use T1 caller evidence to choose canonical location. Decision: if `models.py` versions have zero real consumers, delete them; otherwise move canonical definitions to `domain/models.py` and import from there. Rename `domain/models.py:AnalysisResult` to `JobAnalysisResult` or `AnalysisResultPayload` to avoid collision with per-item `models.py:AnalysisResult`.
  **Must NOT do**: Do not rename per-item News analysis result in `models.py` unless import inventory proves it is safer. Do not change serialized result JSON keys.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: model naming/import cleanup across tests.
  - Skills: [] - none.
  - Omitted: [] - none.

  **Parallelization**: Can Parallel: YES | Wave 4 | Blocks: T15 | Blocked By: T1

  **References**:
  - API/Type: `crypto_news_analyzer/models.py:ExecutionInfo` and `ExecutionResult` - duplicate candidates.
  - API/Type: `crypto_news_analyzer/execution_coordinator.py:ExecutionInfo` and `ExecutionResult` - active versions.
  - API/Type: `crypto_news_analyzer/models.py:AnalysisResult` - per-item News result; keep name unless evidence says otherwise.
  - API/Type: `crypto_news_analyzer/domain/models.py:AnalysisResult` - job-level result; rename preferred.

  **Acceptance Criteria**:
  - [ ] Only one canonical `ExecutionInfo` and `ExecutionResult` definition remains, or duplicate unused definitions are deleted with no import breakage.
  - [ ] Job-level analysis result has non-conflicting name.
  - [ ] Serialized job result payload remains backward-compatible unless tests/docs intentionally update it.

  **QA Scenarios**:
  ```
  Scenario: Execution result serialization stable
    Tool: Bash
    Steps: Run main controller/execution coordinator tests that serialize execution info/results.
    Expected: Same JSON keys and status values as before unless explicitly documented.
    Evidence: .omo/evidence/task-14-execution-result-serialization.txt

  Scenario: Analysis result imports unambiguous
    Tool: Bash
    Steps: Run analyzer tests and API job result tests.
    Expected: Per-item AnalysisResult and job-level JobAnalysisResult imports resolve without ambiguity.
    Evidence: .omo/evidence/task-14-analysis-result-imports.txt
  ```

  **Commit**: NO | Message: `refactor(models): remove duplicate execution models` | Files: [crypto_news_analyzer/models.py, crypto_news_analyzer/domain/models.py, crypto_news_analyzer/execution_coordinator.py, tests/*]

- [x] 15. Update docs, banned legacy guards, and full regression inventory

  **What to do**: Update README/docs/AGENTS guidance to remove deleted aliases/states and reflect simplified lifecycle/runtime behavior. Extend `tests/helpers/banned_legacy_reference_scan.py` to block reintroduction of `TopicLifecycleStatus.PAUSED`, topic `is_active`, `/news_semantic_search`, `MergePreviewState.EXPIRED`, and deleted aliases where safe. Run full route/command inventory after all changes and store evidence.
  **Must NOT do**: Do not ban strings that must remain in migration tests or historical plan docs unless allowlisted. Do not update docs to mention deprecated `api-server` alias as active.

  **Recommended Agent Profile**:
  - Category: `writing` - Reason: documentation and regression guard updates.
  - Skills: [] - none.
  - Omitted: [] - none.

  **Parallelization**: Can Parallel: NO | Wave 4 | Blocks: F1-F4 | Blocked By: T2-T14

  **References**:
  - Pattern: `tests/helpers/banned_legacy_reference_scan.py` - guard extension.
  - Pattern: `README.md` - runtime/Telegram/API docs.
  - Pattern: `docs/RAILWAY_DEPLOYMENT.md`, `docs/ARCHITECTURE_BOUNDARIES.md` - deprecated runtime claims.
  - Evidence: `.omo/evidence/task-1-*` - compare baseline to final.

  **Acceptance Criteria**:
  - [ ] Docs no longer instruct users to use removed commands/states/runtime aliases.
  - [ ] Banned legacy scan catches reintroduction of core removed symbols.
  - [ ] Route inventory after changes is recorded and expected diffs are explained.
  - [ ] Full test/lint/type commands pass or failures are captured with exact remediation.

  **QA Scenarios**:
  ```
  Scenario: Legacy guard catches removed symbols
    Tool: Bash
    Steps: Run `uv run python tests/helpers/banned_legacy_reference_scan.py > .omo/evidence/task-15-legacy-scan-after.txt`
    Expected: Exits 0; removed symbols absent outside explicit allowlist.
    Evidence: .omo/evidence/task-15-legacy-scan-after.txt

  Scenario: Full regression suite
    Tool: Bash
    Steps: Run `uv run pytest tests/ -v`, `uv run mypy crypto_news_analyzer/`, and `uv run flake8 crypto_news_analyzer/`.
    Expected: All commands exit 0, or exact failures are fixed before final verification.
    Evidence: .omo/evidence/task-15-full-regression.txt
  ```

  **Commit**: NO | Message: `test(docs): guard removed redundancy paths` | Files: [README.md, docs/*, tests/helpers/banned_legacy_reference_scan.py, tests/*]

## Optional / High-Risk Candidates — DO NOT execute in this plan without new user approval

- `crawl_status` table/model removal: likely legacy but needs replacement from `ingestion_jobs` and report-generation redesign.
- SQLite support/stub repository removal: backend support decision not confirmed.
- LLM legacy normalizer removal in `structured_output_manager.py`: requires prompt/output evidence that legacy shapes are impossible.
- `RSSCrawlerAdapter` / `XCrawlerAdapter` collapse: production factory currently uses adapters.
- Full SQLite/Postgres DDL unification: useful but broad schema-init refactor; do only after core cleanup passes.
- `MarketSnapshot.is_valid` removal: partial redundancy with `quality_score`, but threshold semantics need a separate product decision.

## Final Verification Wave (MANDATORY — after ALL implementation tasks)
> 4 review agents run in PARALLEL. ALL must APPROVE. Present consolidated results to user and get explicit "okay" before completing.
> **Do NOT auto-proceed after verification. Wait for user's explicit approval before marking work complete.**
> **Never mark F1-F4 as checked before getting user's okay.** Rejection or user feedback -> fix -> re-run -> present again -> wait for okay.
- [ ] F1. Plan Compliance Audit — oracle
  - Verify every completed change maps to T1-T15 only.
  - Verify high-risk exclusions were not implemented.
  - Verify evidence files exist for each task.
- [ ] F2. Code Quality Review — unspecified-high
  - Check for AI slop: unnecessary compatibility wrappers, dead imports, broad try/except, duplicated helper logic reintroduced.
  - Run `uv run mypy crypto_news_analyzer/` and `uv run flake8 crypto_news_analyzer/`.
- [ ] F3. Real Manual QA — unspecified-high
  - Run focused API and Telegram command unit tests; use route dump for API route presence/absence.
  - No browser/Playwright required because this project has HTTP/Telegram surfaces, not a web UI.
- [ ] F4. Scope Fidelity Check — deep
  - Confirm News/Intelligence boundaries remain intact.
  - Confirm optional high-risk removals were not mixed into core implementation.
  - Confirm docs match actual runtime/command/API surfaces.

## Commit Strategy
- User did not request commits. Implementation agents should not commit unless explicitly instructed.
- If commits are later requested, use small commits by wave:
  - `refactor(intelligence): simplify topic lifecycle state`
  - `refactor(models): remove derived redundant state`
  - `refactor(storage): remove repository aliases and no-op schema code`
  - `refactor(runtime): consolidate service startup paths`
  - `test(docs): guard removed legacy redundancy paths`

## Success Criteria
- All T1-T15 completed or intentionally marked skipped with reason.
- No core removed symbol remains in production code:
  - `TopicLifecycleStatus.PAUSED`
  - topic domain/storage `is_active`
  - `MergePreviewState.EXPIRED`
  - `/news_semantic_search`
  - `run_due_topics`
  - `load_auth_from_env`
  - `plugin_system_example.py`
- `uv run pytest tests/ -v` passes.
- `uv run mypy crypto_news_analyzer/` passes.
- `uv run flake8 crypto_news_analyzer/` passes.
- `uv run python tests/helpers/banned_legacy_reference_scan.py` passes.
- Final verification agents F1-F4 approve and user explicitly says okay.
