# LLM Provider Registry and Fallback Refactor

## TL;DR
> **Summary**: Replace the ambiguous `LLM_API_KEY` model-selection flow with a provider-aware, static LLM registry; move `model` and `fallback_models` to structured config; validate configured models/credentials at startup; and document exact provider/model mappings.
> **Deliverables**:
> - Static provider/model registry + structured `llm_config`
> - Runtime-scoped startup validation with fail-fast behavior
> - Unified analysis fallback chain for content-filter / rate-limit / 5xx
> - Removal of `LLM_API_KEY` from code, docs, templates, and tests
> - Replacement of legacy unofficial model aliases with exact documented provider model names
> - Provider/model documentation with exact supported names
> **Effort**: Large
> **Parallel**: YES - 2 waves
> **Critical Path**: 1 → 2 → 3 → 4 → 8

## Audit Correction (2026-04-11)
- This plan was prematurely marked complete during interrupted execution recovery. It is **not accepted complete**.
- **Substantially complete** based on code review + targeted verification: 1, 2, 4, 9.
- **Partially implemented / reopened**: 3, 5, 6, 7, 8, 10.
- F1-F4 have **not** been executed or approved.
- Follow-up execution plan for the remaining work lives at `.sisyphus/plans/llm-provider-registry-refactor-refine.md`.
- The original QA scenarios include vague steps such as “run the new targeted test”; these are superseded by the refine plan’s exact commands.

## Context
### Original Request
- 按“方案 C”改造：移除 `LLM_API_KEY`；保留当前 provider 为 `KIMI_API_KEY` / `GROK_API_KEY`；在 `config.json` 中引入 `fallback_models`；程序启动后基于本地 provider/模型注册表校验 `model` 与 `fallback_models`；支持模型专属配置（例如 thinking level）；并提供每个 provider 的精确模型名文档。

### Interview Summary
- `LLM_API_KEY`：**直接硬删除**，不保留兼容 alias。
- 启动校验：`model` / `fallback_models` 无效或缺少对应 provider 凭证时，**启动失败**。
- fallback 触发条件：**仅** `ContentFilterError`、rate-limit、provider 5xx。
- 未来 OpenAI 类 provider 只做**扩展位**，不实现消费级账号认证；ChatGPT Plus / Go 不是 API provider。

### Metis Review (gaps addressed)
- 必须移除旧的 `mock_mode=not auth_config.LLM_API_KEY` 语义，否则新配置仍会被旧门禁干扰。
- 必须去掉 `summary_model` 兼任分析 fallback 的隐藏耦合，改为“新闻分析角色”和“市场快照角色”各自独立配置。
- 必须使用静态注册表做启动校验；不能依赖 live `/models` 探测。
- 必须把 Telegram/LLM 校验改成 **mode-aware**，避免继续用全局 dataclass 校验误伤 `api-only` / `ingestion`。

## Work Objectives
### Core Objective
建立一个确定性的 provider-aware LLM 配置与执行体系：模型与 provider 的绑定、凭证要求、可用 options、fallback 顺序、启动失败条件，都由本地静态注册表和结构化配置明确表达，不再依赖字符串猜测或模糊通用密钥。

### Deliverables
- 新的静态 provider/model registry 模块（当前覆盖 Kimi、Grok；预留未来 provider 扩展位）
- 新的结构化 `llm_config` schema：
  - `model`
  - `fallback_models`
  - `market_model`
  - 现有共享运行参数（`temperature` / `max_tokens` / `batch_size` / prompt paths / cache）
- 启动期 provider/model/options/credentials 校验逻辑
- 分析链路 fallback 执行器（content-filter / rate-limit / 5xx）
- 文档：provider 对应的精确模型名、环境变量、配置示例、非 API provider 说明；移除旧的非官方模型别名
- 测试：配置校验、启动校验、fallback 行为、model options 验证、默认值一致性

### Definition of Done (verifiable conditions with commands)
- `uv run pytest tests/test_config_manager.py -q` 通过
- `uv run pytest tests/test_main_controller.py -q -k "validate_prerequisites or initialize_system"` 通过
- `uv run pytest tests/test_llm_analyzer.py -q -k "fallback or content_filter or initialization"` 通过
- `uv run pytest tests/test_structured_output_manager.py -q -k "thinking or option or kimi or grok"` 通过
- `uv run pytest tests/test_config_persistence_properties.py -q` 通过
- `uv run pytest tests/test_config_file_management_properties.py -q` 通过
- `uv run pytest tests/test_execution_coordinator_cache_integration.py -q` 通过
- 代码库内不再存在 `LLM_API_KEY` 作为有效运行时配置入口（仅允许迁移说明中的历史文本，不允许运行时代码依赖）
- 默认 config / docs / env template 中的模型名与 registry 一致，不再出现旧的 `MiniMax-M2.1` / `grok-beta` 默认值漂移
- 默认 config / docs / env template 中不再使用 `kimi-for-coding` 这类非官方模型别名；统一采用 registry 中的精确官方模型名

### Must Have
- `llm_config.model` 从字符串升级为结构化对象
- `llm_config.fallback_models` 为有序列表，按配置顺序尝试
- `llm_config.market_model` 独立于分析 fallback 链
- provider 解析不再依赖 `"kimi" in model.lower()` 之类 substring heuristics
- 启动时对当前 service mode 需要的 LLM 角色做强校验
- `thinking_level` 等 model-specific options 有显式 schema 与校验
- 文档与默认配置中的模型名必须来自静态 registry 的精确官方列表

### Must NOT Have (guardrails, AI slop patterns, scope boundaries)
- 不得保留 `LLM_API_KEY` alias、静默兼容或“先用着再说”的灰度逻辑
- 不得在启动时调用远程 `/models` 进行动态发现
- 不得引入“ChatGPT Plus/Go 登录态就是 provider”的实现
- 不得把 `summary_model` 继续当分析 fallback 的隐式来源
- 不得在 auth failure / bad request / unsupported option / parse failure 时触发 fallback
- 不得保留旧的 mock-mode 自动降级逻辑；mock mode 仅限测试显式开启

## Verification Strategy
> ZERO HUMAN INTERVENTION - all verification is agent-executed.
- Test decision: tests-after + existing pytest/property-based suite
- QA policy: Every task has agent-executed scenarios
- Evidence: `.sisyphus/evidence/task-{N}-{slug}.{ext}`

## Execution Strategy
### Parallel Execution Waves
> Target: 5-8 tasks per wave. <3 per wave (except final) = under-splitting.
> Extract shared dependencies as Wave-1 tasks for max parallelism.

Wave 1: registry/schema foundation
- 1. Define static provider/model registry and structured LLM config contracts
- 2. Remove `LLM_API_KEY` and redesign auth/runtime-scoped validation
- 3. Replace startup prerequisite and mock-mode logic with resolved provider checks
- 4. Normalize defaults/examples and remove legacy model drift (`grok-beta`, `MiniMax-M2.1`, `kimi-for-coding`)

Wave 2: runtime integration + docs/tests
- 5. Refactor analyzer/provider routing to consume resolved model metadata
- 6. Implement structured fallback chain and provider-specific option mapping
- 7. Separate market snapshot model flow from analysis fallback flow
- 8. Update docs and env templates with exact provider/model tables
- 9. Add/update config and startup validation tests
- 10. Add/update runtime fallback and option validation tests

### Dependency Matrix (full, all tasks)
| Task | Blocks | Blocked By |
|---|---|---|
| 1 | 2, 3, 5, 6, 7, 8, 9, 10 | - |
| 2 | 3, 9 | 1 |
| 3 | 5, 7, 9 | 1, 2 |
| 4 | 8, 9 | 1 |
| 5 | 6, 10 | 1, 3 |
| 6 | 10 | 1, 5 |
| 7 | 10 | 1, 3 |
| 8 | Final verification | 1, 4 |
| 9 | Final verification | 1, 2, 3, 4 |
| 10 | Final verification | 1, 5, 6, 7 |

### Agent Dispatch Summary
| Wave | Task Count | Categories |
|---|---:|---|
| Wave 1 | 4 | deep, unspecified-high |
| Wave 2 | 6 | deep, unspecified-high, writing |
| Final Verification | 4 | oracle, unspecified-high, deep |

## TODOs
> Implementation + Test = ONE task. Never separate.
> EVERY task MUST have: Agent Profile + Parallelization + QA Scenarios.

- [x] 1. Define static provider/model registry and structured LLM config contracts

  **Status**: ✅ COMPLETED
  - Created `crypto_news_analyzer/config/llm_registry.py` with:
    - `PROVIDERS` registry for Kimi and Grok
    - `MODELS` registry with exact model names
    - `ModelConfig`, `LLMConfig` dataclasses
    - `validate_llm_config_payload()` function
    - Legacy alias rejection for `kimi-for-coding`
    - `thinking_level` option validation
  - All registry tests pass

  **What to do**:
  - Add a centralized static registry module for supported providers and models. Use new config-focused modules rather than embedding more heuristics into analyzers.
  - Define explicit provider records for:
    - `kimi` → env var `KIMI_API_KEY`, base URL `https://api.kimi.com/coding/v1`
    - `grok` → env var `GROK_API_KEY`, base URL `https://api.x.ai/v1`
    - future placeholder providers may exist in schema/registry shape, but only Kimi/Grok are enabled runtime providers in this change.
  - Define exact supported model registry entries for the current project docs baseline using official names only:
    - Kimi: `kimi-k2.5`, `kimi-k2-turbo-preview`, `kimi-k2-thinking-turbo`
    - Grok: `grok-4-1-fast-reasoning`, `grok-4-1-fast-non-reasoning`, `grok-4.20-reasoning`, `grok-4.20-non-reasoning`
  - Treat legacy alias `kimi-for-coding` as invalid configuration after this refactor. Validation must fail with a targeted migration message telling operators to switch to an exact registry model name.
  - Introduce structured config contracts for:
    - `llm_config.model`
    - `llm_config.fallback_models`
    - `llm_config.market_model`
  - Use a canonical object shape for all three:
    ```json
    {
      "provider": "kimi",
      "name": "kimi-k2.5",
      "options": {}
    }
    ```
  - Keep shared execution knobs (`temperature`, `max_tokens`, `batch_size`, prompt/cache fields) at `llm_config` top level.
  - Add a canonical generic option schema in `options`, with `thinking_level` as the first cross-provider field. Allowed enum: `disabled`, `low`, `medium`, `high`, `xhigh`.
  - Registry must define whether each provider/model supports `thinking_level`; unsupported use must fail validation before any request is sent.

  **Must NOT do**:
  - Do not rely on substring matching to infer provider from model name.
  - Do not call external `/models` APIs at startup.
  - Do not keep `summary_model` as a hidden alias for fallback.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: This task defines the authoritative contract all runtime/test/doc updates depend on.
  - Skills: `[]` - No special skill required.
  - Omitted: [`crypto-news-http-api`] - HTTP API contract is unchanged here.

  **Parallelization**: Can Parallel: NO | Wave 1 | Blocks: 2, 3, 5, 6, 7, 8, 9, 10 | Blocked By: []

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `config.json:9-20` - Current flat `llm_config` shape that must be replaced with structured role-aware config.
  - Pattern: `crypto_news_analyzer/config/manager.py:79-153` - Existing config validation is shallow and must gain deep schema checks.
  - Pattern: `crypto_news_analyzer/models.py:229-284` - Current auth dataclass; do not repeat this "flat keys + global validation" mistake in the new config contract.
  - Pattern: `crypto_news_analyzer/analyzers/structured_output_manager.py:290-486` - Existing seam for provider-specific payload shaping and future option mapping.
  - External: `https://docs.x.ai/docs/models` - Source for exact Grok model names to document.
  - External: `https://platform.moonshot.ai/docs/api/list-models` - Source for exact Kimi model names / registry documentation.

  **Acceptance Criteria** (agent-executable only):
  - [ ] A single authoritative registry module exists and is imported by config/runtime code rather than duplicating provider/model metadata.
  - [ ] `llm_config.model`, `llm_config.fallback_models`, and `llm_config.market_model` have one shared schema and one validator.
  - [ ] `thinking_level` is represented in schema with explicit allowed enum values and registry-level support metadata.
  - [ ] No runtime path requires remote model discovery to validate config.
  - [ ] Legacy alias `kimi-for-coding` is rejected with a migration-focused validation error.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Validate structured config shape succeeds
    Tool: Bash
    Steps: Run `uv run pytest tests/test_config_manager.py -q -k "llm_config or provider or registry"`
    Expected: New schema/validation tests pass with structured `model`, `fallback_models`, and `market_model` objects.
    Evidence: .sisyphus/evidence/task-1-llm-registry.txt

  Scenario: Unsupported option rejected before runtime
    Tool: Bash
    Steps: Run the new targeted test covering a config that sets `options.thinking_level` on a model/provider that registry marks unsupported.
    Expected: Validation fails before analyzer initialization; no provider request is attempted.
    Evidence: .sisyphus/evidence/task-1-llm-registry-error.txt
  ```

  **Commit**: NO | Message: `refactor(config): define provider-aware llm registry` | Files: [`crypto_news_analyzer/config/*`, `config.json`, tests]

- [x] 2. Remove `LLM_API_KEY` and redesign auth/runtime-scoped validation

  **What to do**:
  - Remove `LLM_API_KEY` from runtime code paths, env loading, and validation.
  - Refactor `AuthConfig` so it no longer requires a generic LLM key. Keep provider-specific credentials explicit.
  - Make credential validation runtime-scoped:
    - `analysis-service` / `api-only`: validate analysis model, analysis fallbacks, and market snapshot model credentials.
    - `ingestion`: skip LLM credential requirements entirely.
  - Separate Telegram validation from global auth dataclass enforcement; enforce Telegram only where the service mode actually needs it.
  - Ensure provider-specific env names remain explicit (`KIMI_API_KEY`, `GROK_API_KEY`), with future extension points for non-API-key auth represented by interfaces or optional token-provider hooks only.

  **Must NOT do**:
  - Do not preserve `LLM_API_KEY` as deprecated alias.
  - Do not keep Telegram required globally for all modes.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: This changes startup validity semantics across service modes.
  - Skills: `[]` - No special skill required.
  - Omitted: [`grok-api-reference`] - No external API syntax work is needed in this task.

  **Parallelization**: Can Parallel: NO | Wave 1 | Blocks: 3, 9 | Blocked By: [1]

  **References**:
  - Pattern: `crypto_news_analyzer/models.py:230-280` - `AuthConfig` currently hard-requires `LLM_API_KEY` and Telegram values.
  - Pattern: `crypto_news_analyzer/config/manager.py:227-238` - `get_auth_config()` currently returns `LLM_API_KEY`, `GROK_API_KEY`, `KIMI_API_KEY`.
  - Pattern: `README.md:78-99` - Current env var examples advertise `LLM_API_KEY`.
  - Pattern: `.env.template:34-38` - Runtime template currently documents `LLM_API_KEY` as primary key.

  **Acceptance Criteria**:
  - [ ] No runtime dataclass or config loader references `LLM_API_KEY`.
  - [ ] `analysis-service`/`api-only` fail startup when configured providers lack required credentials.
  - [ ] `ingestion` startup remains valid without any LLM credentials.
  - [ ] Telegram validation is mode-aware and no longer globally enforced by auth dataclass construction.

  **QA Scenarios**:
  ```
  Scenario: Ingestion mode no longer depends on LLM credentials
    Tool: Bash
    Steps: Run `uv run pytest tests/test_main_controller.py -q -k "ingestion and validate_prerequisites"`
    Expected: Ingestion-scoped prerequisite validation passes without Kimi/Grok credentials.
    Evidence: .sisyphus/evidence/task-2-auth-scope.txt

  Scenario: Analysis mode fails without required provider credential
    Tool: Bash
    Steps: Run the new targeted test where `llm_config.model.provider="kimi"` but `KIMI_API_KEY` is absent.
    Expected: Startup validation fails deterministically with a provider-specific error message.
    Evidence: .sisyphus/evidence/task-2-auth-scope-error.txt
  ```

  **Commit**: NO | Message: `refactor(auth): remove generic llm api key` | Files: [`crypto_news_analyzer/models.py`, `crypto_news_analyzer/config/manager.py`, tests]

- [ ] 3. Replace startup prerequisite and mock-mode logic with resolved provider checks

  **What to do**:
  - Refactor coordinator startup to resolve the configured model objects via the new registry before constructing analyzers/services.
  - Replace `mock_mode=not auth_config.LLM_API_KEY` with explicit test-only mock configuration. In production startup paths, invalid provider config must fail fast instead of silently entering mock mode.
  - Centralize startup validation in coordinator prerequisite logic so the same resolved model metadata drives initialization and error messages.
  - Make provider/model/options validation authoritative before `LLMAnalyzer` or `MarketSnapshotService` instances are created.

  **Must NOT do**:
  - Do not leave any path where missing generic keys implicitly enable mock mode.
  - Do not split startup validation between ad-hoc analyzer constructors and coordinator logic.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: This is the runtime gate that makes the new schema enforceable.
  - Skills: `[]` - No special skill required.
  - Omitted: [`crypto-news-debug`] - Deployment debugging is unrelated to config semantics.

  **Parallelization**: Can Parallel: NO | Wave 1 | Blocks: 5, 7, 9 | Blocked By: [1, 2]

  **References**:
  - Pattern: `crypto_news_analyzer/execution_coordinator.py:321-340` - Current analyzer initialization path, including `mock_mode=not auth_config.LLM_API_KEY`.
  - Pattern: `crypto_news_analyzer/execution_coordinator.py:519-624` - Existing centralized prerequisite validation seam to extend rather than duplicate.
  - Pattern: `crypto_news_analyzer/api_server.py` - API startup path must continue to work through coordinator initialization.

  **Acceptance Criteria**:
  - [ ] Coordinator resolves model configs before analyzer/service instantiation.
  - [ ] Production startup paths never auto-switch to mock mode because of missing credentials.
  - [ ] Unknown provider/model/options yield startup failure before any API client is created.

  **QA Scenarios**:
  ```
  Scenario: Startup validation rejects unknown fallback model
    Tool: Bash
    Steps: Run the new targeted controller/config test with an unknown `fallback_models[0].name`.
    Expected: Validation fails before `initialize_system()` creates analyzers.
    Evidence: .sisyphus/evidence/task-3-startup-validation.txt

  Scenario: Mock mode is no longer an implicit fallback
    Tool: Bash
    Steps: Run targeted initialization test with missing provider credentials and assert no mock-mode success path is used.
    Expected: Initialization fails with explicit configuration error, not mock execution.
    Evidence: .sisyphus/evidence/task-3-startup-validation-error.txt
  ```

  **Commit**: NO | Message: `refactor(startup): validate resolved llm providers` | Files: [`crypto_news_analyzer/execution_coordinator.py`, tests]

- [x] 4. Normalize defaults, templates, and examples to the new registry contract

  **What to do**:
  - Replace the default flat `llm_config` in `config.json` and `ConfigManager._create_default_config()` with the new structured objects.
  - Remove stale defaults and examples (`MiniMax-M2.1`, `grok-beta`, `LLM_API_KEY`, `kimi-for-coding`) everywhere they appear in shipped config/docs/templates.
  - Ensure the default config uses one canonical supported set of model names that exists in the registry.
  - Ensure the example config demonstrates `fallback_models` order explicitly and shows `market_model` separate from analysis fallback.

  **Must NOT do**:
  - Do not leave mixed legacy/new examples in committed docs/templates.
  - Do not keep incompatible defaults between `config.json` and `ConfigManager._create_default_config()`.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: This is a cross-file consistency sweep that still affects runtime defaults.
  - Skills: `[]` - No special skill required.
  - Omitted: [`frontend-ui-ux`] - No UI/design work.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: 8, 9 | Blocked By: [1]

  **References**:
  - Pattern: `config.json:9-20` - Current committed runtime config.
  - Pattern: `crypto_news_analyzer/config/manager.py:384-426` - Default config generator still seeds legacy model defaults.
  - Pattern: `README.md:18,85` - README drift still mentions MiniMax and `LLM_API_KEY`; update examples to exact registry model names.
  - Pattern: `docs/RAILWAY_DEPLOYMENT.md:116-129` - Current fallback narrative to align with new config semantics.

  **Acceptance Criteria**:
  - [ ] `config.json`, default config generator, `.env.template`, and docs all use the same provider/model names and field names.
  - [ ] No committed default/example uses `LLM_API_KEY`, `MiniMax-M2.1`, `grok-beta`, or `kimi-for-coding` as live current config.

  **QA Scenarios**:
  ```
  Scenario: Default config and generated config stay consistent
    Tool: Bash
    Steps: Run `uv run pytest tests/test_config_file_management_properties.py -q` and `uv run pytest tests/test_config_persistence_properties.py -q`
    Expected: Config round-trip/property tests pass with the new structured llm_config schema.
    Evidence: .sisyphus/evidence/task-4-defaults.txt

  Scenario: Legacy defaults are fully removed
    Tool: Bash
    Steps: Run targeted tests or content assertions that fail if committed defaults/examples still contain `LLM_API_KEY`, `MiniMax-M2.1`, `grok-beta`, or `kimi-for-coding` in active config paths.
    Expected: No legacy defaults remain in runtime-configured paths.
    Evidence: .sisyphus/evidence/task-4-defaults-error.txt
  ```

  **Commit**: NO | Message: `chore(config): normalize llm defaults and examples` | Files: [`config.json`, `crypto_news_analyzer/config/manager.py`, docs/tests]

- [ ] 5. Refactor analyzer/provider routing to consume resolved model metadata

  **What to do**:
  - Change analyzer initialization so it receives resolved provider/model metadata from the registry instead of free-form strings that it then inspects heuristically.
  - Remove provider routing via model-name substring checks from `LLMAnalyzer`.
  - Client construction must use resolved provider attributes (`base_url`, required headers, env-backed credential source, supported capabilities).
  - Keep a single place for provider client construction or client-factory logic; do not copy-paste provider setup across analyzer methods.
  - Preserve model usage reporting (`_last_used_model`) but update it to record exact configured model names/provider transitions.

  **Must NOT do**:
  - Do not leave fallback/client-routing code depending on `"kimi" in self.model.lower()` or `"grok" in ...`.
  - Do not create provider-specific runtime branching in multiple unrelated files if a shared resolved-model helper can own it.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: Runtime execution semantics change here.
  - Skills: `[]` - No special skill required.
  - Omitted: [`llm-instructor`] - The instructor library itself is not the source of this refactor.

  **Parallelization**: Can Parallel: NO | Wave 2 | Blocks: 6, 10 | Blocked By: [1, 3]

  **References**:
  - Pattern: `crypto_news_analyzer/analyzers/llm_analyzer.py:95-177` - Current provider/env resolution and client setup via substring matching.
  - Pattern: `crypto_news_analyzer/execution_coordinator.py:325-341` - Current constructor arguments into `LLMAnalyzer`.
  - Pattern: `crypto_news_analyzer/analyzers/token_usage_tracker.py` - Preserve model reporting compatibility if referenced downstream.

  **Acceptance Criteria**:
  - [ ] `LLMAnalyzer` no longer infers provider from model name substrings.
  - [ ] Client creation uses resolved provider metadata from the registry.
  - [ ] Model usage reporting identifies actual configured/fallback provider transitions with exact names.

  **QA Scenarios**:
  ```
  Scenario: Analyzer initializes with resolved provider metadata
    Tool: Bash
    Steps: Run `uv run pytest tests/test_llm_analyzer.py -q -k "initialization"`
    Expected: Initialization tests pass without relying on `LLM_API_KEY` or substring provider inference.
    Evidence: .sisyphus/evidence/task-5-analyzer-routing.txt

  Scenario: Unsupported provider/model never reaches request path
    Tool: Bash
    Steps: Run targeted tests that inject invalid resolved metadata / config and assert initialization or validation fails before any OpenAI client call.
    Expected: Runtime path refuses unsupported metadata deterministically.
    Evidence: .sisyphus/evidence/task-5-analyzer-routing-error.txt
  ```

  **Commit**: NO | Message: `refactor(analyzer): use resolved provider metadata` | Files: [`crypto_news_analyzer/analyzers/llm_analyzer.py`, coordinator/tests]

- [ ] 6. Implement structured fallback chain and provider-specific option mapping

  **What to do**:
  - Replace the hardcoded Kimi→Grok fallback block in `_analyze_batch_with_structured_output()` with an ordered fallback executor driven by `llm_config.fallback_models`.
  - Classify fallback-triggering exceptions explicitly:
    - include: `ContentFilterError`, provider rate-limit errors, provider 5xx/server errors
    - exclude: auth failures, unsupported option/config errors, bad request, parse/validation failures
  - Fallback granularity: **per batch**, preserving current batching architecture. If batch N falls back, record the exact path in model usage/report metadata.
  - Put provider-specific option mapping in `StructuredOutputManager` using resolved model/provider metadata.
  - Map generic `options.thinking_level` into provider payloads only when the registry says the target model supports it; otherwise fail before request.

  **Must NOT do**:
  - Do not use `summary_model` as implicit first fallback.
  - Do not trigger fallback for generic analysis exceptions.
  - Do not silently drop unsupported `thinking_level` values.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: This is the core behavior change with failure-mode sensitivity.
  - Skills: `[]` - No special skill required.
  - Omitted: [`grok-api-reference`] - Official docs were already researched; implementation should use the plan’s chosen config contract.

  **Parallelization**: Can Parallel: NO | Wave 2 | Blocks: 10 | Blocked By: [1, 5]

  **References**:
  - Pattern: `crypto_news_analyzer/analyzers/llm_analyzer.py:516-579` - Current hardcoded Kimi content-filter fallback to Grok.
  - Pattern: `crypto_news_analyzer/analyzers/llm_analyzer.py:1044-1063` - `retry_with_fallback_model()` stub to replace or remove.
  - Pattern: `crypto_news_analyzer/analyzers/structured_output_manager.py:290-486` - Existing provider-specific request shaping seam.
  - Pattern: `crypto_news_analyzer/utils/errors.py:98-125` - Existing error taxonomy (`RateLimitError`, `APIError`, `ContentFilterError`) to classify precisely.

  **Acceptance Criteria**:
  - [ ] Fallback order follows `llm_config.fallback_models` exactly.
  - [ ] Fallback triggers only on content-filter, rate-limit, and provider 5xx classifications.
  - [ ] Auth failure, bad request, unsupported option, and parse/validation failures do not trigger fallback.
  - [ ] `thinking_level` is mapped or rejected before the request based on registry support.

  **QA Scenarios**:
  ```
  Scenario: Allowed fallback errors advance the chain
    Tool: Bash
    Steps: Run `uv run pytest tests/test_llm_analyzer.py -q -k "fallback or content_filter"`
    Expected: Tests prove fallback occurs for content-filter, rate-limit, and 5xx classifications using configured fallback order.
    Evidence: .sisyphus/evidence/task-6-fallback-chain.txt

  Scenario: Disallowed errors do not advance the chain
    Tool: Bash
    Steps: Run new targeted tests for auth failure, bad request, parse failure, and unsupported option.
    Expected: Primary failure is surfaced directly; fallback chain is not entered.
    Evidence: .sisyphus/evidence/task-6-fallback-chain-error.txt
  ```

  **Commit**: NO | Message: `refactor(analyzer): add configured fallback chain` | Files: [`crypto_news_analyzer/analyzers/llm_analyzer.py`, `crypto_news_analyzer/analyzers/structured_output_manager.py`, tests]

- [ ] 7. Separate market snapshot model flow from analysis fallback flow

  **What to do**:
  - Replace `summary_model` usage with `market_model` resolved via the same registry/validation path as analysis models.
  - Keep market snapshot execution independent from analysis fallback chain.
  - If market snapshot provider/model is invalid or lacks credentials in a mode that needs it, fail startup rather than relying on runtime silent provider fallback.
  - Keep the existing static local fallback snapshot **only** as an execution-time resilience path after a valid market provider has been configured and initialized; do not use it to mask startup misconfiguration.

  **Must NOT do**:
  - Do not reuse `market_model` as analysis fallback.
  - Do not allow invalid `market_model` config to pass startup because a local fallback snapshot exists.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: Hidden coupling must be removed without breaking market snapshot behavior.
  - Skills: `[]` - No special skill required.
  - Omitted: [`crypto-news-http-api`] - HTTP contract does not change.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: 10 | Blocked By: [1, 3]

  **References**:
  - Pattern: `crypto_news_analyzer/analyzers/llm_analyzer.py:178-187` - Current snapshot service initialization from `summary_model`.
  - Pattern: `crypto_news_analyzer/analyzers/llm_analyzer.py:522-549` - Current misuse of `summary_model` as analysis fallback.
  - Pattern: `crypto_news_analyzer/analyzers/market_snapshot_service.py:72-125` - Current Grok-centric model config path.
  - Pattern: `crypto_news_analyzer/analyzers/market_snapshot_service.py:190-214,357-371` - Current fallback providers stub and local fallback behavior.

  **Acceptance Criteria**:
  - [ ] Market snapshot configuration is resolved from `llm_config.market_model`, not `summary_model`.
  - [ ] Analysis fallback no longer reads market snapshot model configuration.
  - [ ] Invalid `market_model` configuration fails startup.
  - [ ] Runtime local snapshot fallback remains available only after valid initialization.

  **QA Scenarios**:
  ```
  Scenario: Market model is validated independently of analysis chain
    Tool: Bash
    Steps: Run targeted controller/config tests with valid analysis config and invalid market model config.
    Expected: Startup fails specifically on `market_model` validation.
    Evidence: .sisyphus/evidence/task-7-market-model.txt

  Scenario: Local snapshot fallback does not mask startup misconfiguration
    Tool: Bash
    Steps: Run targeted tests proving a missing/invalid market provider credential fails startup instead of silently using fallback snapshot.
    Expected: Misconfiguration fails early; local fallback is only used after a valid provider path exists.
    Evidence: .sisyphus/evidence/task-7-market-model-error.txt
  ```

  **Commit**: NO | Message: `refactor(snapshot): decouple market model from analysis fallback` | Files: [`crypto_news_analyzer/analyzers/market_snapshot_service.py`, `crypto_news_analyzer/analyzers/llm_analyzer.py`, tests]

- [ ] 8. Update docs and env templates with exact provider/model tables

  **What to do**:
  - Update `.env.template`, `README.md`, `AGENTS.md`, and `docs/RAILWAY_DEPLOYMENT.md` in one pass.
  - Add a dedicated provider/model reference doc (for example `docs/LLM_PROVIDER_REFERENCE.md`) listing:
    - provider name
    - required environment variable / auth type
    - exact supported model names used by this project
    - supported options such as `thinking_level`
    - whether runtime fallback can target that provider
  - Explicitly document that ChatGPT Plus / Go / similar consumer subscriptions are not valid API providers.
  - Ensure every config example shows structured `model`, `fallback_models`, and `market_model`.

  **Must NOT do**:
  - Do not leave provider model names described vaguely (e.g. “latest Grok model”).
  - Do not document unsupported consumer auth modes as if they were available.

  **Recommended Agent Profile**:
  - Category: `writing` - Reason: Multiple docs need precise synchronized language.
  - Skills: `[]` - No special skill required.
  - Omitted: [`railway-docs`] - This is project-doc alignment, not generic Railway research.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: Final verification | Blocked By: [1, 4]

  **References**:
  - Pattern: `README.md` - Main setup/runtime docs.
  - Pattern: `AGENTS.md` - AI-agent-specific configuration guidance.
  - Pattern: `docs/RAILWAY_DEPLOYMENT.md:116-129` - Current provider/fallback deployment docs.
  - Pattern: `.env.template:34-38` - Existing env template section to replace.
  - External: `https://docs.x.ai/docs/models` - Exact Grok model names.
  - External: `https://platform.moonshot.ai/docs/api/list-models` - Exact Kimi model names and model-list reference.

  **Acceptance Criteria**:
  - [ ] All user-facing config docs describe the new structured schema and provider-specific env vars.
  - [ ] A dedicated provider/model reference doc exists with exact supported model names.
  - [ ] Docs explicitly state consumer subscriptions are not API providers.
  - [ ] Docs explicitly identify `kimi-for-coding` as removed legacy config and point to the exact replacement model names.

  **QA Scenarios**:
  ```
  Scenario: Provider reference doc is complete and aligned
    Tool: Bash
    Steps: Run a targeted content-check test or script that asserts the new provider reference doc includes Kimi and Grok sections, exact env vars, and structured config examples.
    Expected: Documentation completeness check passes.
    Evidence: .sisyphus/evidence/task-8-docs.txt

  Scenario: Legacy env var guidance is removed
    Tool: Bash
    Steps: Run a targeted content-check test or script asserting `.env.template`, `README.md`, and `AGENTS.md` no longer advertise `LLM_API_KEY` as a valid runtime key.
    Expected: No legacy guidance remains in maintained docs/templates.
    Evidence: .sisyphus/evidence/task-8-docs-error.txt
  ```

  **Commit**: NO | Message: `docs(llm): add provider registry reference` | Files: [`.env.template`, `README.md`, `AGENTS.md`, `docs/*`]

- [x] 9. Add/update config and startup validation tests

  **What to do**:
  - Update all tests/property strategies that currently assume `LLM_API_KEY` or flat model strings.
  - Add startup validation coverage for:
    - analysis mode + Kimi primary without `KIMI_API_KEY` → fail
    - analysis mode + unknown primary model → fail
    - analysis mode + Grok fallback without `GROK_API_KEY` → fail
    - ingestion mode without LLM credentials → pass
    - api-only mode without Telegram → pass if LLM provider requirements are satisfied
  - Update config property tests to generate structured model objects and ordered `fallback_models`.
  - Add consistency assertions that committed defaults and templates do not reintroduce legacy defaults.

  **Must NOT do**:
  - Do not leave tests only covering happy paths.
  - Do not keep fixtures that still require `LLM_API_KEY`.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: Broad test surface update across unit + property tests.
  - Skills: `[]` - No special skill required.
  - Omitted: [`review-work`] - This task is test authoring, not final review.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: Final verification | Blocked By: [1, 2, 3, 4]

  **References**:
  - Test: `tests/test_config_manager.py` - Existing config/env validation coverage.
  - Test: `tests/test_main_controller.py` - Existing prerequisite/init coverage.
  - Test: `tests/test_config_persistence_properties.py` - Property-based config persistence.
  - Test: `tests/test_config_file_management_properties.py` - Property-based config management.
  - Pattern: `crypto_news_analyzer/execution_coordinator.py:519-624` - Target runtime-scoped validation semantics.

  **Acceptance Criteria**:
  - [ ] All updated test suites pass with structured config objects and provider-specific credentials.
  - [ ] New negative tests cover invalid providers, invalid models, missing credentials, and ingestion/api-only scope behavior.
  - [ ] Property tests exercise `fallback_models` ordering and structured object round-trips.

  **QA Scenarios**:
  ```
  Scenario: Config and startup validation suite passes
    Tool: Bash
    Steps: Run `uv run pytest tests/test_config_manager.py -q` and `uv run pytest tests/test_main_controller.py -q -k "validate_prerequisites or initialize_system"`
    Expected: Validation/init tests pass with the new runtime-scoped provider rules.
    Evidence: .sisyphus/evidence/task-9-config-tests.txt

  Scenario: Invalid startup permutations fail deterministically
    Tool: Bash
    Steps: Run targeted negative tests for missing provider creds, unknown models, and invalid fallback entries.
    Expected: Each failure is explicit and mode-aware; ingestion remains unaffected.
    Evidence: .sisyphus/evidence/task-9-config-tests-error.txt
  ```

  **Commit**: NO | Message: `test(config): cover provider-aware startup validation` | Files: [`tests/test_config_manager.py`, `tests/test_main_controller.py`, property tests]

- [ ] 10. Add/update runtime fallback and option validation tests

  **What to do**:
  - Extend analyzer/structured-output tests so they verify configured fallback order and strict trigger taxonomy.
  - Add tests for provider option propagation/rejection:
    - supported `thinking_level` reaches provider payload
    - unsupported `thinking_level` fails before request
  - Add tests proving fallback does not occur on auth failure, unsupported option, bad request, or parse/validation failure.
  - Add/update model usage reporting assertions so mixed provider usage across batches is surfaced clearly.

  **Must NOT do**:
  - Do not rely only on old Kimi→Grok content-filter tests.
  - Do not leave provider-option behavior untested.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: Requires careful hands-on runtime-path test updates.
  - Skills: `[]` - No special skill required.
  - Omitted: [`grok-api-reference`] - No further external doc lookup is needed.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: Final verification | Blocked By: [1, 5, 6, 7]

  **References**:
  - Test: `tests/test_llm_analyzer.py:464-537` - Existing Kimi content-filter fallback tests to generalize.
  - Test: `tests/test_structured_output_manager.py` - Existing provider-specific request-shaping tests, including Kimi/Grok branches.
  - Pattern: `crypto_news_analyzer/analyzers/structured_output_manager.py:446-693` - Current Kimi web search implementation and option seam.
  - Pattern: `crypto_news_analyzer/analyzers/structured_output_manager.py:313-444` - Current Grok response path.

  **Acceptance Criteria**:
  - [ ] Runtime tests prove fallback advances only on allowed classifications.
  - [ ] Option mapping/rejection is covered before-request for all supported providers.
  - [ ] `_last_used_model` or equivalent reporting records exact fallback transitions.

  **QA Scenarios**:
  ```
  Scenario: Runtime fallback matrix passes
    Tool: Bash
    Steps: Run `uv run pytest tests/test_llm_analyzer.py -q -k "fallback or content_filter"`
    Expected: Runtime tests pass for allowed fallback classes and explicit no-fallback cases.
    Evidence: .sisyphus/evidence/task-10-runtime-tests.txt

  Scenario: Provider option behavior is enforced before request
    Tool: Bash
    Steps: Run `uv run pytest tests/test_structured_output_manager.py -q -k "thinking or option or kimi or grok"`
    Expected: Supported options map correctly; unsupported options fail without issuing provider requests.
    Evidence: .sisyphus/evidence/task-10-runtime-tests-error.txt
  ```

  **Commit**: NO | Message: `test(runtime): cover llm fallback and option mapping` | Files: [`tests/test_llm_analyzer.py`, `tests/test_structured_output_manager.py`]

## Final Verification Wave (MANDATORY — after ALL implementation tasks)
> 4 review agents run in PARALLEL. ALL must APPROVE. Present consolidated results to user and get explicit "okay" before completing.
> **Do NOT auto-proceed after verification. Wait for user's explicit approval before marking work complete.**
> **Never mark F1-F4 as checked before getting user's okay.** Rejection or user feedback -> fix -> re-run -> present again -> wait for okay.
- [ ] F1. Plan Compliance Audit — oracle
- [ ] F2. Code Quality Review — unspecified-high
- [ ] F3. Real Manual QA — unspecified-high
- [ ] F4. Scope Fidelity Check — deep

## Commit Strategy
- Do not create intermediate commits per task unless user explicitly requests task-by-task checkpoints.
- After F1-F4 all pass and the user explicitly says “okay”, create one commit:
  - `refactor(config): add provider-aware llm registry and fallback chain`
- Commit must include code, docs, templates, and tests together to avoid mixed legacy/new configuration states.

## Success Criteria
- The runtime no longer accepts or depends on `LLM_API_KEY`.
- `llm_config` is structured, role-aware, and validated statically at startup.
- Analysis fallback order is driven solely by `fallback_models` and only for approved error classes.
- Market snapshot configuration is independent from analysis fallback.
- Docs list exact supported providers and exact model names used by this project.
- Tests cover valid and invalid permutations across service modes.
- Legacy alias model names are no longer accepted silently.

## Current Status After Audit
- Registry/schema, provider-specific auth loading, defaults/templates, and most docs/test migration work are in place.
- Remaining blockers are runtime-facing: resolved metadata handoff into analyzers, removal of substring-based provider routing, replacement of hardcoded Kimi→Grok fallback with `fallback_models`, elimination of lingering `summary_model` coupling, and exact runtime-path tests that prove these behaviors.
