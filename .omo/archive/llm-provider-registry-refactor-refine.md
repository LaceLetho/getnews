# LLM Provider Registry Refactor — Runtime Completion Refine

## TL;DR
> **Summary**: Finish the original refactor by moving runtime execution onto resolved registry metadata, deleting substring-based provider routing, replacing the hardcoded Kimi→Grok fallback with an ordered `fallback_models` policy, removing lingering `summary_model` coupling, and closing the remaining docs/test acceptance gaps.
> **Deliverables**:
> - Resolved runtime metadata boundary for analyzer and market snapshot initialization
> - Registry capability corrections for `thinking_level` based on official Kimi/xAI docs
> - Ordered fallback execution driven only by `llm_config.fallback_models`
> - `market_model` runtime decoupling from analysis fallback and `summary_model`
> - Dedicated provider reference doc + cleanup of active residual legacy refs
> - Exact pytest node coverage for startup, fallback, option-mapping, and market-model failures
> **Effort**: Medium
> **Parallel**: YES - 2 waves
> **Critical Path**: 1 → 2 → 3 → 4 → 5

## Context
### Original Request
- 根据 review 结果，修正原 plan 的完成状态与表述，并补一份 refine plan，完成未达标的 runtime / docs / test 工作。

### Interview Summary
- 原 plan 已修正为“部分完成，未验收通过”。
- refine plan 只覆盖未达标项，不重复规划已实质完成的 registry/schema、auth scope、defaults/property tests 基础工作。
- `market_model` 继续按 registry 合同支持当前已注册 provider，不降级成 Grok-only 临时方案。
- 构造器兼容只允许保留在外层 wiring/adapter；内部 runtime 类必须切到 resolved metadata。

### Metis Review (gaps addressed)
- 必须重开 3/5/6/7/8/10，而不是继续把原 plan 当作完成状态。
- 必须把所有“run the new targeted test”之类模糊 QA 场景改成精确 pytest node 命令。
- 必须明确 `thinking_level` 的 provider 语义，不允许实现者自行猜测。
- 必须限制 scope，避免演变成新的 provider framework 或历史档案清理工程。

### Oracle Review (runtime strategy)
- 在组合边界先做一次“legacy input → resolved metadata”规范化；从该边界往里，运行时只接受 resolved metadata。
- 兼容层只允许存在于 public entrypoint/factory/wiring，内部 analyzer / executor / snapshot service 立即切换到规范化合同。
- fallback 只对少量明确允许的运行时失败生效；解析失败、配置失败、缺凭证、未知 provider/model 一律不得 fallback。
- fallback 必须单跳、禁止 self-fallback，并在目标模型能力不满足时 fail-fast。

### Provider Option Research (official docs)
- **Kimi**: 仅 `kimi-k2.5` 支持 binary `thinking` 控制；OpenAI SDK 调用时应通过 `extra_body={"thinking": {"type": "enabled|disabled"}}` 传递。`kimi-k2-thinking` / `kimi-k2-thinking-turbo` 为 always-on，不支持请求级 thinking_level 控制；`kimi-k2-turbo-preview` 不支持 thinking。Sources: `https://platform.moonshot.ai/docs/guide/use-kimi-k2-thinking-model`, `https://platform.moonshot.ai/docs/api/chat`.
- **Grok**: 当前 registry 中的 Grok 4 系列模型不支持 `reasoning_effort` / `reasoning.effort`；向这些模型发送 reasoning control 会报错。当前项目注册的 Grok 模型必须视为 **不支持** `thinking_level`。 Source: `https://docs.x.ai/developers/model-capabilities/text/reasoning`.

## Work Objectives
### Core Objective
让 runtime 真正遵守静态 registry 合同：provider 决策来自 resolved metadata，而不是 model-name substring；fallback 来自配置的 `fallback_models`；`market_model` 独立于分析 fallback；provider-specific options 只在官方支持的模型上发送。

### Deliverables
- 一个单一的 resolved runtime metadata handoff（coordinator/wiring → analyzer/snapshot runtime）
- 更新后的 registry capability metadata：
  - `kimi-k2.5` 支持 `thinking_level`
  - `kimi-k2-turbo-preview` 不支持 `thinking_level`
  - `kimi-k2-thinking-turbo` 不支持请求级 `thinking_level`（always-on）
  - 当前所有 Grok registry 模型都不支持 `thinking_level`
- 删除 analyzer / structured output / market snapshot 中的 substring-based provider routing 与 stale provider branches
- 按 `fallback_models` 顺序执行的单跳 fallback 链，只允许 content-filter / rate-limit / provider 5xx
- `market_model` 驱动的 snapshot runtime 与启动校验；移除 `summary_model` 运行时耦合
- `docs/LLM_PROVIDER_REFERENCE.md` 与 active docs/test cleanup
- 精确 pytest node 覆盖以上行为

### Definition of Done (verifiable conditions with commands)
- `uv run pytest tests/test_llm_registry.py -q` 通过
- `uv run pytest tests/test_main_controller.py::test_validate_prerequisites_ingestion_scope_skips_analysis_auth -q` 通过
- `uv run pytest tests/test_main_controller.py::test_validate_prerequisites_analysis_scope_requires_analysis_auth -q` 通过
- `uv run pytest tests/test_main_controller.py::test_initialize_system_rejects_invalid_market_model -q` 通过
- `uv run pytest tests/test_main_controller.py::test_initialize_system_rejects_missing_fallback_provider_credentials -q` 通过
- `uv run pytest tests/test_llm_analyzer.py::test_fallback_models_are_tried_in_configured_order -q` 通过
- `uv run pytest tests/test_llm_analyzer.py::test_rate_limit_error_uses_next_fallback_model -q` 通过
- `uv run pytest tests/test_llm_analyzer.py::test_auth_error_does_not_enter_fallback_chain -q` 通过
- `uv run pytest tests/test_llm_analyzer.py::test_parse_failure_does_not_enter_fallback_chain -q` 通过
- `uv run pytest tests/test_structured_output_manager.py::test_kimi_thinking_level_maps_into_request_payload -q` 通过
- `uv run pytest tests/test_structured_output_manager.py::test_unsupported_thinking_level_fails_before_request -q` 通过
- `uv run pytest tests/test_multi_step_analysis_unit.py::test_market_snapshot_local_fallback_only_after_valid_provider_init -q` 通过
- `uv run pytest tests/test_config_manager.py -q` 通过
- 运行时代码中不再存在 `summary_model` 作为活动配置接口；仅允许迁移错误消息中提及该名字
- 运行时代码中不再存在 `"kimi" in model.lower()` / `"grok" in model.lower()` / MiniMax/OpenAI legacy routing branches 作为 provider 决策入口
- `docs/LLM_PROVIDER_REFERENCE.md` 存在，并列出当前项目支持的 provider、model、env var、option 支持矩阵

### Must Have
- resolved metadata 在 startup/wiring 阶段一次性生成并向内传递
- fallback 顺序严格按 `llm_config.fallback_models`
- fallback 仅允许单跳，且不得 fallback 到自身
- fallback 仅允许 `ContentFilterError`、rate-limit、provider 5xx
- `market_model` 独立校验，且只有在 valid initialization 完成后才能使用本地 snapshot fallback
- `thinking_level` 只在官方支持的模型上发送
- refine plan 中所有 QA 步骤必须是可复制执行的精确命令

### Must NOT Have (guardrails, AI slop patterns, scope boundaries)
- 不得继续保留 `summary_model` 作为运行时参数/更新入口/隐式 fallback 来源
- 不得在 analyzer / snapshot / structured-output 内部继续用 substring 推断 provider
- 不得把 `thinking_level` 发送到当前 registry 中的 Grok 模型
- 不得把 `thinking_level` 发送到 `kimi-k2-turbo-preview` 或 `kimi-k2-thinking-turbo`
- 不得在 resolution/config/auth/unsupported-option/parse failure 上触发 fallback
- 不得引入新 provider、consumer auth、plugin framework、archive cleanup

## Verification Strategy
> ZERO HUMAN INTERVENTION - all verification is agent-executed.
- Test decision: tests-after with exact pytest nodes + focused suite reruns
- QA policy: Every task contains exact happy-path and failure-path commands
- Evidence: `.sisyphus/evidence/task-{N}-{slug}.{ext}`

## Execution Strategy
### Parallel Execution Waves
> Target: 4-6 tasks per wave. Shared contract work lands first; runtime rewrites depend on that contract.

Wave 1: runtime contract + docs foundation
- 1. Correct registry option-capability metadata and define resolved runtime metadata helpers
- 2. Rewire coordinator/analyzer composition boundary to pass resolved metadata
- 6. Complete provider reference doc and active legacy acceptance cleanup

Wave 2: runtime behavior completion
- 3. Remove substring routing and stale provider branches from analyzer/output manager
- 4. Replace hardcoded fallback with configured single-hop fallback execution
- 5. Decouple market snapshot runtime from `summary_model` and make startup validation exact

### Dependency Matrix (full, all tasks)
| Task | Blocks | Blocked By |
|---|---|---|
| 1 | 2, 3, 4, 5, 6 | - |
| 2 | 3, 4, 5 | 1 |
| 3 | 4, 5 | 1, 2 |
| 4 | Final verification | 1, 2, 3 |
| 5 | Final verification | 1, 2, 3 |
| 6 | Final verification | 1 |

### Agent Dispatch Summary
| Wave | Task Count | Categories |
|---|---:|---|
| Wave 1 | 3 | deep, writing |
| Wave 2 | 3 | deep, unspecified-high |
| Final Verification | 4 | oracle, unspecified-high, deep |

## TODOs
> Implementation + Test = ONE task. Never separate.
> EVERY task MUST have: Agent Profile + Parallelization + QA Scenarios.

- [x] 1. Correct registry capability metadata and define resolved runtime metadata helpers

  **What to do**:
  - Update static model capability metadata in `crypto_news_analyzer/config/llm_registry.py` to match official docs:
    - `kimi-k2.5` → supports request-level `thinking_level`
    - `kimi-k2-turbo-preview` → does not support request-level `thinking_level`
    - `kimi-k2-thinking-turbo` → does not support request-level `thinking_level` because thinking is always on
    - all currently registered Grok models → do not support request-level `thinking_level`
  - Introduce one resolved runtime metadata shape for downstream execution. It must contain, at minimum: role (`analysis` / `market` / `fallback[i]`), `ModelConfig`, `ModelRecord`, `ProviderRecord`, normalized option payload, and derived capability flags (`enable_web_search`, `enable_x_search`, request-level thinking mapping).
  - Keep the source of truth in registry helpers; do not duplicate provider/model metadata in analyzers.
  - Define exact option normalization rules:
    - `kimi-k2.5`: `thinking_level=disabled` → `thinking.type=disabled`; `low|medium|high|xhigh` → `thinking.type=enabled`
    - `kimi-k2-turbo-preview`, `kimi-k2-thinking-turbo`, all current Grok models: any `thinking_level` must fail validation before request
  - Expose helper(s) that allow runtime code to consume resolved metadata without falling back to string heuristics.

  **Must NOT do**:
  - Do not mark Grok 4 models as supporting `thinking_level`.
  - Do not keep analyzer-local provider metadata copies.
  - Do not encode request-shaping logic as ad-hoc booleans scattered across classes.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: This task defines the authoritative runtime contract used by all remaining work.
  - Skills: `[]` - No special skill required.
  - Omitted: [`grok-api-reference`] - Official docs decisions are already captured in this plan.

  **Parallelization**: Can Parallel: NO | Wave 1 | Blocks: 2, 3, 4, 5, 6 | Blocked By: []

  **References**:
  - Pattern: `crypto_news_analyzer/config/llm_registry.py:109-347` - Current provider/model metadata and validation entrypoints.
  - Pattern: `crypto_news_analyzer/analyzers/structured_output_manager.py:446-487` - Current Kimi request shaping using `extra_body` for `thinking`.
  - External: `https://platform.moonshot.ai/docs/guide/use-kimi-k2-thinking-model` - Official Kimi thinking behavior.
  - External: `https://platform.moonshot.ai/docs/api/chat` - Official Kimi chat schema including `thinking`.
  - External: `https://docs.x.ai/developers/model-capabilities/text/reasoning` - Official Grok reasoning support limitations.

  **Acceptance Criteria**:
  - [ ] Registry capability flags match official provider docs for all current Kimi/Grok models.
  - [ ] A single resolved metadata helper/API exists for runtime consumers.
  - [ ] Validation rejects `thinking_level` on unsupported models before any provider request is attempted.
  - [ ] No runtime task needs to inspect model-name substrings to know provider/capabilities.

  **QA Scenarios**:
  ```
  Scenario: Registry validation matches official thinking support matrix
    Tool: Bash
    Steps: Run `uv run pytest tests/test_llm_registry.py -q`
    Expected: Supported/unsupported `thinking_level` cases pass/fail exactly per registry rules.
    Evidence: .sisyphus/evidence/task-1-registry-runtime-contract.txt

  Scenario: Unsupported thinking option fails before runtime
    Tool: Bash
    Steps: Run `uv run pytest tests/test_structured_output_manager.py::test_unsupported_thinking_level_fails_before_request -q`
    Expected: Validation fails before any OpenAI client invocation for unsupported model/provider combinations.
    Evidence: .sisyphus/evidence/task-1-registry-runtime-contract-error.txt
  ```

  **Commit**: NO | Message: `refactor(registry): align runtime capability metadata` | Files: [`crypto_news_analyzer/config/llm_registry.py`, tests]

- [x] 2. Rewire coordinator and public entrypoints to pass resolved runtime metadata

  **What to do**:
  - At `MainController.initialize_system()`, resolve analysis model, fallback models, and market model once, then pass the resolved metadata objects into `LLMAnalyzer`.
  - Preserve backward compatibility only at the outer wiring boundary. `LLMAnalyzer` may accept a temporary adapter shape, but internal execution paths must consume resolved metadata only.
  - Remove the need for analyzer-local fallback to `validate_llm_config_payload()` swallowing errors and then guessing provider by substring.
  - Make missing/invalid model metadata fatal before any client or market snapshot service is constructed.
  - Ensure `_resolve_provider_credentials()` and `_validate_runtime_auth()` continue to use the exact provider set required by `model`, `fallback_models`, and `market_model`.

  **Must NOT do**:
  - Do not leave mixed contracts active inside analyzer internals.
  - Do not preserve `summary_model` as a public constructor path for new runtime wiring.
  - Do not defer resolution into `LLMAnalyzer.__init__` if coordinator already has validated config.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: This is the composition boundary that eliminates legacy runtime ambiguity.
  - Skills: `[]` - No special skill required.
  - Omitted: [`crypto-news-http-api`] - HTTP contract is unchanged.

  **Parallelization**: Can Parallel: NO | Wave 1 | Blocks: 3, 4, 5 | Blocked By: [1]

  **References**:
  - Pattern: `crypto_news_analyzer/execution_coordinator.py:311-347` - Current startup wiring still passes `model`/`summary_model` strings.
  - Pattern: `crypto_news_analyzer/execution_coordinator.py:525-658` - Current mode-aware auth and provider-credential resolution.
  - Pattern: `crypto_news_analyzer/analyzers/llm_analyzer.py:54-123` - Current constructor and config-validation fallback.
  - Pattern: `crypto_news_analyzer/analyzers/market_snapshot_service.py:73-145` - Current snapshot service constructor contract.

  **Acceptance Criteria**:
  - [ ] Coordinator passes resolved runtime metadata, not plain model strings, into analyzer wiring.
  - [ ] Invalid analysis/market/fallback config fails before any runtime client construction.
  - [ ] Compatibility shims, if any, exist only at the outer entrypoint/factory boundary.

  **QA Scenarios**:
  ```
  Scenario: Ingestion scope still skips analysis auth after rewiring
    Tool: Bash
    Steps: Run `uv run pytest tests/test_main_controller.py::test_validate_prerequisites_ingestion_scope_skips_analysis_auth -q`
    Expected: Ingestion validation succeeds without LLM credentials and without analyzer initialization.
    Evidence: .sisyphus/evidence/task-2-resolved-wiring.txt

  Scenario: Missing fallback provider credential fails before analyzer creation
    Tool: Bash
    Steps: Run `uv run pytest tests/test_main_controller.py::test_initialize_system_rejects_missing_fallback_provider_credentials -q`
    Expected: Startup aborts before constructing analyzer clients when any configured fallback provider credential is absent.
    Evidence: .sisyphus/evidence/task-2-resolved-wiring-error.txt
  ```

  **Commit**: NO | Message: `refactor(startup): hand off resolved llm metadata` | Files: [`crypto_news_analyzer/execution_coordinator.py`, `crypto_news_analyzer/analyzers/llm_analyzer.py`, tests]

- [x] 3. Remove substring routing and stale provider branches from analyzer and structured output runtime

  **What to do**:
  - Replace all provider routing in `LLMAnalyzer` that uses `"kimi" in self.model.lower()` / `"grok" in ...` with resolved metadata decisions from task 1.
  - Delete stale MiniMax / generic OpenAI fallback branches that are outside the current registry-supported provider set.
  - Replace `StructuredOutputManager.force_structured_response()` web-search branching so it uses resolved model capabilities rather than substring detection on the model name.
  - Ensure web-search / x-search behavior is derived from `ModelRecord.supports_web_search` and `supports_x_search`.
  - Preserve `_last_used_model` reporting, but make it use exact provider/model identifiers from resolved metadata.

  **Must NOT do**:
  - Do not leave any active provider decision based on model-name substring checks.
  - Do not keep dead provider branches for providers not present in `PROVIDERS`.
  - Do not leak provider-specific request options across providers.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: This is the highest-risk runtime behavior cleanup.
  - Skills: `[]` - No special skill required.
  - Omitted: [`llm-instructor`] - Instructor integration is not the decision source.

  **Parallelization**: Can Parallel: NO | Wave 2 | Blocks: 4, 5 | Blocked By: [1, 2]

  **References**:
  - Pattern: `crypto_news_analyzer/analyzers/llm_analyzer.py:152-191` - Current client construction via substring routing and stale MiniMax/OpenAI branches.
  - Pattern: `crypto_news_analyzer/analyzers/llm_analyzer.py:229-259` - Current provider resolution fallback to substring heuristics.
  - Pattern: `crypto_news_analyzer/analyzers/llm_analyzer.py:513-548` - Current web-search and last-used-model routing by substring.
  - Pattern: `crypto_news_analyzer/analyzers/structured_output_manager.py:290-301` - Current Kimi-vs-Grok web-search branch by model string.

  **Acceptance Criteria**:
  - [ ] Runtime provider/client/web-search routing is derived only from resolved metadata.
  - [ ] No active MiniMax or generic OpenAI provider branches remain for the analysis runtime path.
  - [ ] `_last_used_model` reflects exact configured model/provider transitions.

  **QA Scenarios**:
  ```
  Scenario: Analyzer initializes without substring provider inference
    Tool: Bash
    Steps: Run `uv run pytest tests/test_llm_analyzer.py -q -k "initialization"`
    Expected: Initialization passes using resolved metadata and no provider-name substring routing.
    Evidence: .sisyphus/evidence/task-3-runtime-routing.txt

  Scenario: Unsupported provider/model never reaches request path
    Tool: Bash
    Steps: Run `uv run pytest tests/test_llm_analyzer.py::test_invalid_resolved_metadata_fails_before_client_call -q`
    Expected: Invalid provider/model metadata fails before any OpenAI client request path is entered.
    Evidence: .sisyphus/evidence/task-3-runtime-routing-error.txt
  ```

  **Commit**: NO | Message: `refactor(analyzer): remove substring provider routing` | Files: [`crypto_news_analyzer/analyzers/llm_analyzer.py`, `crypto_news_analyzer/analyzers/structured_output_manager.py`, tests]

- [x] 4. Replace hardcoded fallback with configured single-hop fallback execution

  **What to do**:
  - Remove the current hardcoded Kimi content-filter → Grok fallback block from `_analyze_batch_with_structured_output()`.
  - Implement fallback as an ordered single-hop policy driven by `llm_config.fallback_models`, with each fallback target already resolved into runtime metadata.
  - Allowed fallback-trigger classes are exactly:
    - `ContentFilterError`
    - provider rate-limit failures
    - provider 5xx / transient upstream server failures
  - Disallowed fallback-trigger classes are exactly:
    - auth/credential failures
    - unsupported option / invalid config / invalid metadata
    - bad request / 4xx request-shape errors
    - parse/validation failures after a provider returned content
  - If no fallback model is configured, or the next fallback resolves to the same provider+model, surface the primary error directly.
  - Rebuild request capability flags and provider-specific request payload from the fallback model’s resolved metadata; never reuse the primary model’s provider-specific options blindly.

  **Must NOT do**:
  - Do not use `summary_model` or `market_model` as analysis fallback.
  - Do not enter fallback when primary resolution/config/auth already failed.
  - Do not implement multi-hop loops or self-fallback.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: Fallback classification and request rebuilding are failure-sensitive.
  - Skills: `[]` - No special skill required.
  - Omitted: [`grok-api-reference`] - Official fallback-eligibility decisions are already made here.

  **Parallelization**: Can Parallel: NO | Wave 2 | Blocks: Final verification | Blocked By: [1, 2, 3]

  **References**:
  - Pattern: `crypto_news_analyzer/analyzers/llm_analyzer.py:564-627` - Current hardcoded Kimi→Grok fallback to remove.
  - Pattern: `crypto_news_analyzer/analyzers/llm_analyzer.py:1092-1111` - Current fallback helper stub to replace or delete.
  - Pattern: `crypto_news_analyzer/utils/errors.py:98-125` - Existing provider/runtime error taxonomy.
  - Test: `tests/test_llm_analyzer.py:491-575` - Current hardcoded fallback tests to rewrite/generalize.

  **Acceptance Criteria**:
  - [ ] Fallback order follows `llm_config.fallback_models` exactly.
  - [ ] Fallback triggers only on the allowed error classes.
  - [ ] Disallowed failures surface directly without entering fallback.
  - [ ] Fallback is single-hop and cannot target the same provider+model as primary.

  **QA Scenarios**:
  ```
  Scenario: Fallback models are tried in configured order
    Tool: Bash
    Steps: Run `uv run pytest tests/test_llm_analyzer.py::test_fallback_models_are_tried_in_configured_order -q`
    Expected: The analyzer tries fallback targets strictly in config order and records the exact transition.
    Evidence: .sisyphus/evidence/task-4-configured-fallback.txt

  Scenario: Disallowed failures do not enter fallback chain
    Tool: Bash
    Steps: Run `uv run pytest tests/test_llm_analyzer.py::test_auth_error_does_not_enter_fallback_chain -q` && `uv run pytest tests/test_llm_analyzer.py::test_parse_failure_does_not_enter_fallback_chain -q`
    Expected: Auth and parse failures surface directly; no fallback model is attempted.
    Evidence: .sisyphus/evidence/task-4-configured-fallback-error.txt
  ```

  **Commit**: NO | Message: `refactor(analyzer): execute configured fallback policy` | Files: [`crypto_news_analyzer/analyzers/llm_analyzer.py`, tests]

- [x] 5. Decouple market snapshot runtime from `summary_model` and make startup validation exact

  **What to do**:
  - Remove `summary_model` as an active runtime constructor/update field from `LLMAnalyzer` and `MarketSnapshotService`.
  - Drive market snapshot runtime entirely from resolved `market_model` metadata.
  - Make `MarketSnapshotService` provider behavior use resolved metadata instead of the current Grok-centric + fallback-provider stub model.
  - Support current registry-backed providers for market snapshot execution according to their capability metadata:
    - Grok models may use `web_search` + `x_search` where supported.
    - Kimi market models may use Kimi web search only where supported.
  - Keep local fallback snapshot only as post-initialization execution resilience. Invalid or uncredentialed `market_model` must fail startup in modes that require the feature.
  - Make startup validation mode-aware: validate market snapshot eagerly only when the runtime mode uses it.

  **Must NOT do**:
  - Do not retain `summary_model` update paths such as `update_config(summary_model=...)`.
  - Do not use local snapshot fallback to hide startup misconfiguration.
  - Do not make `market_model` implicitly participate in analysis fallback.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: This removes the remaining hidden coupling while preserving a working market snapshot feature.
  - Skills: `[]` - No special skill required.
  - Omitted: [`crypto-news-http-api`] - HTTP behavior is unchanged.

  **Parallelization**: Can Parallel: NO | Wave 2 | Blocks: Final verification | Blocked By: [1, 2, 3]

  **References**:
  - Pattern: `crypto_news_analyzer/analyzers/llm_analyzer.py:193-203,244-259,571-573` - Current `summary_model` coupling to snapshot config and fallback behavior.
  - Pattern: `crypto_news_analyzer/analyzers/market_snapshot_service.py:73-145` - Current constructor and Grok-only client setup.
  - Pattern: `crypto_news_analyzer/analyzers/market_snapshot_service.py:181-191` - Current provider inference from `summary_model`.
  - Pattern: `crypto_news_analyzer/analyzers/market_snapshot_service.py:222-247` - Current Grok-first + fallback-provider execution.
  - Pattern: `crypto_news_analyzer/analyzers/market_snapshot_service.py:390-404,764-789` - Current stub fallback provider and `summary_model` update path.

  **Acceptance Criteria**:
  - [ ] `market_model` is the only active runtime configuration source for market snapshots.
  - [ ] Invalid or uncredentialed `market_model` fails startup in relevant modes before service initialization.
  - [ ] Local snapshot fallback remains available only after successful valid market provider initialization.
  - [ ] Analysis fallback no longer reads any market snapshot configuration fields.

  **QA Scenarios**:
  ```
  Scenario: Invalid market model fails startup explicitly
    Tool: Bash
    Steps: Run `uv run pytest tests/test_main_controller.py::test_initialize_system_rejects_invalid_market_model -q`
    Expected: Startup stops with a market-model-specific configuration error before snapshot service initialization.
    Evidence: .sisyphus/evidence/task-5-market-runtime.txt

  Scenario: Local snapshot fallback does not mask startup misconfiguration
    Tool: Bash
    Steps: Run `uv run pytest tests/test_multi_step_analysis_unit.py::test_market_snapshot_local_fallback_only_after_valid_provider_init -q`
    Expected: Local fallback is only used after valid provider initialization; invalid startup config still fails early.
    Evidence: .sisyphus/evidence/task-5-market-runtime-error.txt
  ```

  **Commit**: NO | Message: `refactor(snapshot): remove summary-model runtime coupling` | Files: [`crypto_news_analyzer/analyzers/market_snapshot_service.py`, `crypto_news_analyzer/analyzers/llm_analyzer.py`, `crypto_news_analyzer/execution_coordinator.py`, tests]

- [x] 6. Complete provider reference docs and active residual legacy cleanup

  **What to do**:
  - Add `docs/LLM_PROVIDER_REFERENCE.md` as the canonical provider/model/options matrix required by the original plan.
  - Document exact current support:
    - providers and env vars
    - exact model names from registry
    - which models support request-level `thinking_level`
    - which models support web search / x search
    - explicit statement that ChatGPT Plus / Go and other consumer subscriptions are not API providers
  - Update maintained docs (`README.md`, `AGENTS.md`, `docs/RAILWAY_DEPLOYMENT.md`, `.env.template`) so they reference the provider reference doc and avoid implying the refactor is fully complete if runtime tasks remain.
  - Clean active residual legacy refs that would undermine acceptance in maintained tests/docs (for example active `LLM_API_KEY` fixtures or legacy default model names in non-archive tests), but do not touch archive/history content.

  **Must NOT do**:
  - Do not rewrite archive docs.
  - Do not leave `LLM_API_KEY` described as a valid runtime input.
  - Do not document unsupported reasoning controls for current Grok models.

  **Recommended Agent Profile**:
  - Category: `writing` - Reason: This is synchronized doc and acceptance cleanup across maintained files.
  - Skills: `[]` - No special skill required.
  - Omitted: [`railway-docs`] - Project-specific doc alignment is the goal.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: Final verification | Blocked By: [1]

  **References**:
  - Pattern: `.env.template` - Maintained env template.
  - Pattern: `README.md` - Primary user-facing config docs.
  - Pattern: `AGENTS.md` - Agent-facing runtime guidance.
  - Pattern: `docs/RAILWAY_DEPLOYMENT.md` - Deployment/runtime docs.
  - Pattern: `tests/test_extensibility_unit.py` - Active test file still containing generic legacy key references.
  - Pattern: `tests/test_ingestion_jobs.py` - Active test file with stale model default references to remove if still present.
  - External: `https://platform.moonshot.ai/docs/api/chat`
  - External: `https://docs.x.ai/developers/models`

  **Acceptance Criteria**:
  - [ ] `docs/LLM_PROVIDER_REFERENCE.md` exists and matches the current registry.
  - [ ] Maintained docs/templates point to provider-specific env vars and structured config.
  - [ ] Active non-archive docs/tests no longer advertise legacy runtime defaults as valid current behavior.

  **QA Scenarios**:
  ```
  Scenario: Provider reference doc exists and is aligned with registry
    Tool: Bash
    Steps: Run `python - <<'PY'
from pathlib import Path
root = Path('/data/workspace/getnews')
doc = root / 'docs' / 'LLM_PROVIDER_REFERENCE.md'
text = doc.read_text(encoding='utf-8')
required = ['KIMI_API_KEY', 'GROK_API_KEY', 'kimi-k2.5', 'grok-4-1-fast-reasoning', 'thinking_level']
missing = [item for item in required if item not in text]
assert doc.exists(), 'missing docs/LLM_PROVIDER_REFERENCE.md'
assert not missing, f'missing doc entries: {missing}'
print('provider reference doc validated')
PY`
    Expected: The dedicated provider reference doc exists and contains the required provider/model/option entries.
    Evidence: .sisyphus/evidence/task-6-provider-docs.txt

  Scenario: Active maintained docs/tests no longer advertise legacy runtime config
    Tool: Bash
    Steps: Run `python - <<'PY'
from pathlib import Path
root = Path('/data/workspace/getnews')
targets = [
    root / '.env.template',
    root / 'README.md',
    root / 'AGENTS.md',
    root / 'docs' / 'RAILWAY_DEPLOYMENT.md',
]
bad = []
for path in targets:
    text = path.read_text(encoding='utf-8')
    if 'LLM_API_KEY=' in text or 'MiniMax-M2.1' in text or 'grok-beta' in text or 'kimi-for-coding' in text:
        bad.append(str(path))
assert not bad, f'legacy guidance remains: {bad}'
print('maintained docs/templates cleaned')
PY`
    Expected: Maintained docs/templates no longer advertise legacy runtime inputs or deprecated defaults.
    Evidence: .sisyphus/evidence/task-6-provider-docs-error.txt
  ```

  **Commit**: NO | Message: `docs(llm): finish provider reference and cleanup` | Files: [`docs/LLM_PROVIDER_REFERENCE.md`, `.env.template`, `README.md`, `AGENTS.md`, `docs/*`, active tests]

## Final Verification Wave (MANDATORY — after ALL implementation tasks)
> 4 review agents run in PARALLEL. ALL must APPROVE. Present consolidated results to user and get explicit "okay" before completing.
> **Do NOT auto-proceed after verification. Wait for user's explicit approval before marking work complete.**
> **Never mark F1-F4 as checked before getting user's okay.** Rejection or user feedback -> fix -> re-run -> present again -> wait for okay.
- [x] F1. Plan Compliance Audit — oracle
- [x] F2. Code Quality Review — unspecified-high
- [x] F3. Real Manual QA — unspecified-high
- [x] F4. Scope Fidelity Check — deep

## Commit Strategy
- Do not create intermediate commits unless the user explicitly requests checkpoints.
- After all implementation tasks and F1-F4 pass, and the user explicitly says “okay”, create one commit:
  - `refactor(runtime): complete provider-aware llm routing and fallback`
- Include runtime code, docs, and tests together to avoid mixed old/new behavior.

## Success Criteria
- Runtime provider decisions come only from resolved registry metadata.
- Current Grok models no longer claim/support request-level `thinking_level`.
- Kimi request-level `thinking_level` behavior matches official Moonshot docs.
- Analysis fallback is driven solely by `fallback_models` and allowed error classes.
- `market_model` is the only active runtime market snapshot config source.
- `summary_model` no longer exists as an active runtime parameter.
- Dedicated provider reference docs exist and match the registry.
- Exact startup/runtime/option tests prove the behavior end-to-end.
