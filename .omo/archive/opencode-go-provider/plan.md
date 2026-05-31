# OpenCode Go Provider Integration

## TL;DR
> **Summary**: Add `opencode-go` as a new provider in the LLM registry using `OPENCODE_API_KEY`, supporting exactly three OpenAI-compatible OpenCode Go models for `llm_config.model` and `fallback_models`, while explicitly rejecting `opencode-go` in `market_model` and defaulting all undocumented capabilities to unsupported.
> **Deliverables**:
> - New provider `opencode-go` with fixed 3-model registry snapshot
> - Auth/config/startup validation for `OPENCODE_API_KEY`
> - Analysis-model and fallback-model config support for OpenCode Go
> - Explicit validation-time rejection for `market_model.provider="opencode-go"`
> - Docs/examples/tests updated without changing current default provider setup
> **Effort**: Short
> **Parallel**: YES - 2 waves
> **Critical Path**: 1 → 2 → 3 → 5

## Context
### Original Request
- 用户希望继续扩展 LLM provider registry feature，使项目可以使用 OpenCode Go 提供的模型；示例为 Kimi K2.5。

### Interview Summary
- OpenCode Go 提供正式 API key，应视为服务端 API integration，而不是消费级订阅复用。
- 接入方式：作为新 provider `opencode-go`，不是现有 `kimi` provider 的 auth/base_url 变体。
- 第一阶段范围：仅支持 `llm_config.model` 与 `fallback_models`；**不支持** `market_model`。
- 第一阶段模型固定快照为 3 个：`glm-5.1`、`kimi-k2.5`、`mimo-v2-pro`。
- `fallback_models` 在本阶段只要求**配置与启动校验支持**，不新增“全量运行时 failover 语义”。
- 文档未明确声明的能力（`thinking_level` / `web_search` / `x_search` / `responses API` / tooling）一律按**不支持**处理。

### Metis Review (gaps addressed)
- 必须修复 `OPENCODE_API_KEY -> opencode-go` 的 auth 映射问题，不能继续依赖 env var 字符串反推 provider 名。
- 必须在 **配置校验阶段** 显式拒绝 `market_model.provider="opencode-go"`，不能只靠文档说明。
- 必须把 property tests 的“有效配置生成器”与 `market_model` 约束同步，否则新增 provider 后会自动生成非法 market config。
- 必须避免 scope creep：不引入 Anthropic transport、不接 MiniMax Go 模型、不做动态模型发现。

## Work Objectives
### Core Objective
以最小风险方式把 OpenCode Go 纳入现有 provider-aware LLM 配置体系：支持它作为分析模型与 fallback 配置项出现，使用独立凭证与独立 provider namespace，并通过静态 registry、启动校验、文档和测试把边界锁死。

### Deliverables
- `opencode-go` provider registry entry with env var `OPENCODE_API_KEY`
- Fixed model registry snapshot for exactly:
  - `glm-5.1`
  - `kimi-k2.5`
  - `mimo-v2-pro`
- Startup/auth/config validation that recognizes `opencode-go` in `model` and `fallback_models`
- Explicit validation-time rejection for `market_model.provider="opencode-go"`
- Conservative capability metadata for all 3 OpenCode Go models:
  - `supports_thinking_level = false`
  - `supports_web_search = false`
  - `supports_x_search = false`
  - `supports_responses_api = false`
- Docs/examples/env template updates for `OPENCODE_API_KEY`
- Focused tests for registry validation, startup auth, config generation, and docs

### Definition of Done (verifiable conditions with commands)
- `uv run pytest tests/test_llm_registry.py::test_opencode_go_analysis_models_validate tests/test_llm_registry.py::test_opencode_go_market_model_rejected tests/test_llm_registry.py::test_opencode_go_kimi_k2_5_rejects_thinking_level tests/test_llm_registry.py::test_opencode_go_unlisted_go_models_rejected -q` 通过
- `uv run pytest tests/test_main_controller.py::TestMainController::test_required_llm_provider_env_vars_include_opencode_go tests/test_main_controller.py::TestMainController::test_resolve_provider_credentials_maps_opencode_go_correctly tests/test_main_controller.py::TestMainController::test_runtime_auth_requires_opencode_api_key_when_opencode_go_configured tests/test_main_controller.py::TestMainController::test_runtime_auth_does_not_require_opencode_api_key_when_unused -q` 通过
- `uv run pytest tests/test_config_manager.py -q -k "opencode_go or llm_config"` 通过
- `uv run pytest tests/test_config_persistence_properties.py tests/test_config_file_management_properties.py -q` 通过
- `uv run pytest tests/test_llm_analyzer.py -q -k "opencode_go or initialization"` 通过
- `README.md`、`.env.template`、`docs/LLM_PROVIDER_REFERENCE.md` 中出现 `OPENCODE_API_KEY`
- `llm_config.market_model.provider="opencode-go"` 在配置校验阶段失败，错误消息包含 `llm_config.market_model`
- 默认配置与示例默认主路径仍保持现有 Kimi/Grok 组合，不把 `opencode-go` 变成默认 provider

### Must Have
- `opencode-go` 作为新 provider 出现在 registry 中
- 仅支持 3 个固定模型，其他 OpenCode Go 模型全部视为不支持
- `OPENCODE_API_KEY` 只在 `model` 或 `fallback_models` 使用 `opencode-go` 时才成为必需
- `market_model.provider="opencode-go"` 必须 fail-fast
- OpenCode Go 模型默认不支持 `thinking_level` / search / responses API
- property tests 不再生成 `market_model=opencode-go` 的“有效配置”

### Must NOT Have (guardrails, AI slop patterns, scope boundaries)
- 不得把 `opencode-go` 伪装成现有 `kimi` provider
- 不得加入 `glm-5`、`mimo-v2-omni`、`minimax-m2.5`、`minimax-m2.7`
- 不得引入 Anthropic transport 或 `/messages` 路径
- 不得让 `opencode-go` 进入 `market_model`
- 不得继承直连 Kimi/Grok 的 undocumented capabilities
- 不得改变当前默认 provider 选择为 `opencode-go`
- 不得做动态模型发现或 live catalog 拉取

## Verification Strategy
> ZERO HUMAN INTERVENTION - all verification is agent-executed.
- Test decision: tests-after with exact pytest node coverage
- QA policy: Every task contains agent-executable commands with explicit pass/fail outcomes
- Evidence: `.sisyphus/evidence/task-{N}-{slug}.{ext}`

## Execution Strategy
### Parallel Execution Waves
> Shared contract and auth wiring first, then docs/tests/defaults.

Wave 1: core contract and startup validation
- 1. Add `opencode-go` provider and fixed model registry snapshot
- 2. Wire `OPENCODE_API_KEY` through auth/config/startup validation
- 3. Add cross-field validation rejecting `market_model.provider="opencode-go"`

Wave 2: defaults/docs/tests cleanup
- 4. Keep runtime behavior conservative and analysis-only for OpenCode Go
- 5. Update docs, env template, and examples without changing current defaults
- 6. Update tests and property generators for the new provider boundary

### Dependency Matrix (full, all tasks)
| Task | Blocks | Blocked By |
|---|---|---|
| 1 | 2, 3, 4, 5, 6 | - |
| 2 | 4, 6 | 1 |
| 3 | 5, 6 | 1 |
| 4 | Final verification | 1, 2 |
| 5 | Final verification | 1, 3 |
| 6 | Final verification | 1, 2, 3, 4, 5 |

### Agent Dispatch Summary
| Wave | Task Count | Categories |
|---|---:|---|
| Wave 1 | 3 | deep |
| Wave 2 | 3 | deep, writing, unspecified-high |
| Final Verification | 4 | oracle, unspecified-high, deep |

## TODOs
> Implementation + Test = ONE task. Never separate.
> EVERY task MUST have: Agent Profile + Parallelization + QA Scenarios.

- [x] 1. Add `opencode-go` provider and fixed three-model registry snapshot

  **What to do**:
  - Update `crypto_news_analyzer/config/llm_registry.py` to add a new provider record:
    - provider key: `opencode-go`
    - env var: `OPENCODE_API_KEY`
    - base URL: derive the correct OpenAI SDK-compatible base URL from `https://opencode.ai/docs/go/`; do **not** blindly paste the full `/chat/completions` endpoint unless SDK semantics confirm it.
    - client class remains OpenAI-compatible in phase 1.
  - Add exactly these `MODELS["opencode-go"]` entries:
    - `glm-5.1`
    - `kimi-k2.5`
    - `mimo-v2-pro`
  - Assign conservative capabilities for all three:
    - `supports_web_search = false`
    - `supports_x_search = false`
    - `supports_thinking_level = false`
    - `supports_responses_api = false`
  - Reject all other OpenCode Go models by omission from registry; do not leave “future placeholders”.

  **Must NOT do**:
  - Do not add `glm-5`, `mimo-v2-omni`, `minimax-m2.5`, or `minimax-m2.7`.
  - Do not let `opencode-go/kimi-k2.5` inherit direct-Kimi `thinking_level` behavior.
  - Do not introduce dynamic model discovery.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: This defines the authoritative contract all other changes depend on.
  - Skills: `[]` - No special skill required.
  - Omitted: [`grok-api-reference`] - Not relevant to OpenCode Go provider addition.

  **Parallelization**: Can Parallel: NO | Wave 1 | Blocks: 2, 3, 4, 5, 6 | Blocked By: []

  **References**:
  - Pattern: `crypto_news_analyzer/config/llm_registry.py:109-245` - Existing provider/model registry shape.
  - Pattern: `crypto_news_analyzer/config/llm_registry.py:274-361` - Existing config validation entrypoints.
  - External: `https://opencode.ai/docs/go/` - Official OpenCode Go docs and model list.
  - Pattern: `docs/LLM_PROVIDER_REFERENCE.md` - Existing provider matrix format to mirror.

  **Acceptance Criteria**:
  - [x] `opencode-go` exists in provider registry with `OPENCODE_API_KEY`.
  - [x] Exactly 3 OpenCode Go models are accepted by the registry.
  - [x] `opencode-go/kimi-k2.5` rejects `thinking_level`.
  - [x] No undocumented OpenCode Go capabilities are enabled by default.

  **QA Scenarios**:
  ```
  Scenario: OpenCode Go analysis models validate
    Tool: Bash
    Steps: Run `uv run pytest tests/test_llm_registry.py::test_opencode_go_analysis_models_validate -q`
    Expected: The three allowed OpenCode Go models validate successfully for `model` and `fallback_models`.
    Evidence: .sisyphus/evidence/task-1-opencode-go-registry.txt

  Scenario: Unlisted OpenCode Go models are rejected
    Tool: Bash
    Steps: Run `uv run pytest tests/test_llm_registry.py::test_opencode_go_unlisted_go_models_rejected tests/test_llm_registry.py::test_opencode_go_kimi_k2_5_rejects_thinking_level -q`
    Expected: Unsupported Go models and `thinking_level` on `opencode-go/kimi-k2.5` both fail validation.
    Evidence: .sisyphus/evidence/task-1-opencode-go-registry-error.txt
  ```

  **Commit**: NO | Message: `feat(registry): add opencode-go provider snapshot` | Files: [`crypto_news_analyzer/config/llm_registry.py`, tests]

- [x] 2. Wire `OPENCODE_API_KEY` through auth/config/startup validation

  **What to do**:
  - Update `crypto_news_analyzer/models.py` so auth config can hold `OPENCODE_API_KEY`.
  - Update `crypto_news_analyzer/config/manager.py` to load `OPENCODE_API_KEY` from the environment.
  - Update `crypto_news_analyzer/execution_coordinator.py` so required provider env vars are derived from provider records directly, not by reverse-parsing env var names into provider names.
  - Ensure startup auth requirements include `OPENCODE_API_KEY` only when:
    - `llm_config.model.provider == "opencode-go"`, or
    - any `fallback_models[i].provider == "opencode-go"`
  - Ensure startup auth does **not** require `OPENCODE_API_KEY` when OpenCode Go is unused.

  **Must NOT do**:
  - Do not derive provider names from `env_var.removesuffix("_API_KEY")` for OpenCode Go.
  - Do not make `OPENCODE_API_KEY` globally required.
  - Do not add market_model auth support for `opencode-go` in phase 1.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: Auth and startup validation semantics are cross-cutting and failure-sensitive.
  - Skills: `[]` - No special skill required.
  - Omitted: [`crypto-news-http-api`] - HTTP API contract is unchanged.

  **Parallelization**: Can Parallel: NO | Wave 1 | Blocks: 4, 6 | Blocked By: [1]

  **References**:
  - Pattern: `crypto_news_analyzer/models.py:229-296` - Current AuthConfig shape.
  - Pattern: `crypto_news_analyzer/config/manager.py:234-245` - Current env loading for auth config.
  - Pattern: `crypto_news_analyzer/execution_coordinator.py:649-662` - Current provider env var resolution seam.
  - Pattern: `crypto_news_analyzer/execution_coordinator.py:664-682` - Current runtime auth validation.

  **Acceptance Criteria**:
  - [x] `OPENCODE_API_KEY` is loaded into auth config.
  - [x] Required provider env var resolution maps to `opencode-go`, not `opencode`.
  - [x] Startup requires `OPENCODE_API_KEY` only when OpenCode Go appears in `model` or `fallback_models`.

  **QA Scenarios**:
  ```
  Scenario: Startup requires OPENCODE_API_KEY when OpenCode Go is configured
    Tool: Bash
    Steps: Run `uv run pytest tests/test_main_controller.py::TestMainController::test_runtime_auth_requires_opencode_api_key_when_opencode_go_configured tests/test_main_controller.py::TestMainController::test_resolve_provider_credentials_maps_opencode_go_correctly -q`
    Expected: Startup/auth validation fails or maps credentials exactly as expected, and provider key is `opencode-go`.
    Evidence: .sisyphus/evidence/task-2-opencode-go-auth.txt

  Scenario: OPENCODE_API_KEY is not required when unused
    Tool: Bash
    Steps: Run `uv run pytest tests/test_main_controller.py::TestMainController::test_runtime_auth_does_not_require_opencode_api_key_when_unused tests/test_main_controller.py::TestMainController::test_required_llm_provider_env_vars_include_opencode_go -q`
    Expected: Unused OpenCode Go does not create a credential requirement, while used OpenCode Go does.
    Evidence: .sisyphus/evidence/task-2-opencode-go-auth-error.txt
  ```

  **Commit**: NO | Message: `refactor(auth): wire opencode-go credentials` | Files: [`crypto_news_analyzer/models.py`, `crypto_news_analyzer/config/manager.py`, `crypto_news_analyzer/execution_coordinator.py`, tests]

- [x] 3. Add explicit validation-time rejection for `market_model.provider="opencode-go"`

  **What to do**:
  - Update `validate_llm_config_payload()` / related registry validation so OpenCode Go is valid for:
    - `llm_config.model`
    - `llm_config.fallback_models[*]`
    but invalid for:
    - `llm_config.market_model`
  - Error message must point to `llm_config.market_model` and explain phase-1 restriction.
  - Keep `market_snapshot_service.py` behavior unchanged; this task is about early validation, not runtime adaptation.

  **Must NOT do**:
  - Do not silently allow OpenCode Go in market_model and hope runtime fails later.
  - Do not modify market snapshot provider behavior in phase 1.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: This is a deliberate scope boundary and must be enforced centrally.
  - Skills: `[]` - No special skill required.
  - Omitted: [`railway-docs`] - Not relevant to validation semantics.

  **Parallelization**: Can Parallel: NO | Wave 1 | Blocks: 5, 6 | Blocked By: [1]

  **References**:
  - Pattern: `crypto_news_analyzer/config/llm_registry.py:334-361` - Current llm_config payload validation.
  - Pattern: `crypto_news_analyzer/analyzers/market_snapshot_service.py:128-176` - Existing Grok-biased market path that phase 1 leaves unchanged.
  - Pattern: `docs/LLM_PROVIDER_REFERENCE.md` - Documentation target for explicit exclusion note.

  **Acceptance Criteria**:
  - [x] `market_model.provider="opencode-go"` fails at config validation time.
  - [x] The failure message includes `llm_config.market_model` and states phase-1 exclusion.
  - [x] Existing market snapshot runtime remains unchanged.

  **QA Scenarios**:
  ```
  Scenario: market_model rejects OpenCode Go explicitly
    Tool: Bash
    Steps: Run `uv run pytest tests/test_llm_registry.py::test_opencode_go_market_model_rejected -q`
    Expected: Validation fails before startup/runtime with a `llm_config.market_model`-scoped error.
    Evidence: .sisyphus/evidence/task-3-opencode-go-market-guard.txt

  Scenario: market snapshot path remains unaffected
    Tool: Bash
    Steps: Run `uv run pytest tests/test_main_controller.py -q -k "validate_prerequisites or initialize_system"`
    Expected: Existing market snapshot startup path still behaves as before for Grok/Kimi configs.
    Evidence: .sisyphus/evidence/task-3-opencode-go-market-guard-error.txt
  ```

  **Commit**: NO | Message: `feat(validation): forbid opencode-go market model` | Files: [`crypto_news_analyzer/config/llm_registry.py`, tests]

- [x] 4. Keep runtime behavior conservative and analysis-only for OpenCode Go

  **What to do**:
  - Ensure OpenCode Go models can be used by the existing analysis runtime path through the OpenAI-compatible client flow.
  - Ensure `structured_output_manager.py` and `llm_analyzer.py` do not accidentally treat `opencode-go/kimi-k2.5` as direct Kimi with Kimi-only features.
  - Keep OpenCode Go out of search-enabled paths and any provider-specific capability branches.
  - Keep `fallback_models` support conservative: config/startup support must work, but do not redesign runtime failover semantics in this phase.
  - If existing runtime fallback code assumes Grok/Kimi-specific behavior, make sure OpenCode Go does not accidentally enter unsupported capability branches.

  **Must NOT do**:
  - Do not add web_search/x_search/thinking/responses support for OpenCode Go.
  - Do not reinterpret phase 1 as “generic full failover engine”.
  - Do not add Anthropic or mixed-transport code.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: Runtime must remain stable while new provider support stays tightly scoped.
  - Skills: `[]` - No special skill required.
  - Omitted: [`llm-instructor`] - No new structured-output library work is needed.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: 6 | Blocked By: [1, 2]

  **References**:
  - Pattern: `crypto_news_analyzer/analyzers/llm_analyzer.py:54-220` - Current analysis client construction path.
  - Pattern: `crypto_news_analyzer/analyzers/llm_analyzer.py:222-238` - Existing provider-specific search/fallback helpers.
  - Pattern: `crypto_news_analyzer/analyzers/structured_output_manager.py:290-303` - Existing provider-specific web-search branch.
  - Pattern: `crypto_news_analyzer/config/llm_registry.py:122-139` - Model capability metadata that should drive conservative runtime behavior.

  **Acceptance Criteria**:
  - [x] OpenCode Go analysis models initialize through the existing OpenAI-compatible path.
  - [x] OpenCode Go models do not inherit Kimi/Grok-specific undocumented features.
  - [x] Runtime remains analysis-only for OpenCode Go in phase 1.

  **QA Scenarios**:
  ```
  Scenario: OpenCode Go analysis initialization succeeds conservatively
    Tool: Bash
    Steps: Run `uv run pytest tests/test_llm_analyzer.py -q -k "opencode_go or initialization"`
    Expected: OpenCode Go models initialize without entering search-specific or thinking-specific branches.
    Evidence: .sisyphus/evidence/task-4-opencode-go-runtime.txt

  Scenario: OpenCode Go Kimi model does not inherit thinking_level behavior
    Tool: Bash
    Steps: Run `uv run pytest tests/test_llm_registry.py::test_opencode_go_kimi_k2_5_rejects_thinking_level -q`
    Expected: `provider=opencode-go,name=kimi-k2.5` rejects `thinking_level` even though direct Kimi accepts it.
    Evidence: .sisyphus/evidence/task-4-opencode-go-runtime-error.txt
  ```

  **Commit**: NO | Message: `feat(runtime): support opencode-go analysis path` | Files: [`crypto_news_analyzer/analyzers/llm_analyzer.py`, `crypto_news_analyzer/analyzers/structured_output_manager.py`, tests]

- [x] 5. Update docs, env template, and examples without changing current defaults

  **What to do**:
  - Update `.env.template`, `README.md`, and `docs/LLM_PROVIDER_REFERENCE.md` to document `OPENCODE_API_KEY` and the new `opencode-go` provider.
  - Add OpenCode Go examples showing `provider: "opencode-go"` for `model` and `fallback_models`.
  - Explicitly document phase-1 exclusions:
    - unsupported `market_model`
    - unsupported OpenCode Go models outside the 3-model snapshot
    - unsupported capabilities (`thinking_level`, search, responses API, tooling)
  - Keep current default examples/config default path on Kimi/Grok unless a file already specifically enumerates all supported providers.

  **Must NOT do**:
- Do not make OpenCode Go the default in `config.jsonc` or generated defaults.
  - Do not describe unsupported Go models as supported.
  - Do not imply `market_model` works with OpenCode Go.

  **Recommended Agent Profile**:
  - Category: `writing` - Reason: This is synchronized docs/examples/env work with explicit product boundaries.
  - Skills: `[]` - No special skill required.
  - Omitted: [`railway-docs`] - Project-local docs are sufficient.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: 6 | Blocked By: [1, 3]

  **References**:
  - Pattern: `.env.template` - Existing provider env var section.
  - Pattern: `README.md` - User-facing provider and config docs.
  - Pattern: `docs/LLM_PROVIDER_REFERENCE.md` - Canonical provider/model matrix.
  - Pattern: `docs/RAILWAY_DEPLOYMENT.md` - Deployment/runtime docs that may mention env vars.

  **Acceptance Criteria**:
  - [x] `OPENCODE_API_KEY` is documented in maintained docs/templates.
  - [x] OpenCode Go docs mention exactly the 3 supported models.
  - [x] Docs explicitly state OpenCode Go is not supported for `market_model` in phase 1.
  - [x] Existing defaults remain Kimi/Grok unless explicitly intended otherwise.

  **QA Scenarios**:
  ```
  Scenario: Maintained docs mention OPENCODE_API_KEY and OpenCode Go support boundaries
    Tool: Bash
    Steps: Run `python - <<'PY'
from pathlib import Path
root = Path('/data/workspace/getnews')
targets = [root/'.env.template', root/'README.md', root/'docs'/'LLM_PROVIDER_REFERENCE.md']
required = ['OPENCODE_API_KEY', 'opencode-go', 'glm-5.1', 'kimi-k2.5', 'mimo-v2-pro']
for path in targets:
    text = path.read_text(encoding='utf-8')
    if path.name != '.env.template':
        for item in required[1:]:
            assert item in text, f'{item} missing in {path}'
    else:
        assert required[0] in text, f'OPENCODE_API_KEY missing in {path}'
print('docs validated')
PY`
    Expected: Maintained docs/templates contain OpenCode Go env/config references and supported models.
    Evidence: .sisyphus/evidence/task-5-opencode-go-docs.txt

  Scenario: Docs explicitly exclude market_model and unsupported models
    Tool: Bash
    Steps: Run `python - <<'PY'
from pathlib import Path
text = (Path('/data/workspace/getnews')/'docs'/'LLM_PROVIDER_REFERENCE.md').read_text(encoding='utf-8')
assert 'market_model' in text and 'not supported' in text.lower()
assert 'minimax-m2.7' not in text or 'not supported' in text.lower()
print('doc exclusions validated')
PY`
    Expected: Docs clearly state phase-1 exclusions for market_model and unsupported Go models.
    Evidence: .sisyphus/evidence/task-5-opencode-go-docs-error.txt
  ```

  **Commit**: NO | Message: `docs(llm): document opencode-go provider` | Files: [`.env.template`, `README.md`, `docs/LLM_PROVIDER_REFERENCE.md`, `docs/*`]

- [x] 6. Update tests and property generators for the new provider boundary

  **What to do**:
  - Add targeted registry tests for the 3 OpenCode Go models and rejected Go models.
  - Add startup/auth tests for `OPENCODE_API_KEY` presence/absence.
  - Update property-based config generators so “valid config” generation never emits `market_model=opencode-go`.
  - Add doc/config regression checks as needed so active maintained docs/examples stay aligned.
  - Ensure tests cover the same model name under two providers (`kimi/kimi-k2.5` vs `opencode-go/kimi-k2.5`) without capability leakage.

  **Must NOT do**:
  - Do not leave Hypothesis strategies generating OpenCode Go market_model as valid.
  - Do not rely on live API/network calls to OpenCode Go.
  - Do not add tests for unsupported MiniMax transport in this phase.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: This is a broad regression/test boundary update across unit and property tests.
  - Skills: `[]` - No special skill required.
  - Omitted: [`review-work`] - Final verification handles the review wave.

  **Parallelization**: Can Parallel: NO | Wave 2 | Blocks: Final verification | Blocked By: [1, 2, 3, 4, 5]

  **References**:
  - Test: `tests/test_llm_registry.py` - Registry validation and option rejection.
  - Test: `tests/test_main_controller.py` - Startup/auth validation seams.
  - Test: `tests/test_config_manager.py` - Default config and config parsing coverage.
  - Test: `tests/test_config_persistence_properties.py` - Config persistence generators.
  - Test: `tests/test_config_file_management_properties.py` - File-management generators.
  - Pattern: `README.md:175-177` - Current fallback wording that tests/docs should not overstate for phase 1.

  **Acceptance Criteria**:
  - [x] Tests cover all accepted and rejected OpenCode Go phase-1 cases.
  - [x] Property tests never emit invalid `market_model=opencode-go` as a valid config.
  - [x] Same-name model under different providers is tested for provider-specific capability separation.

  **QA Scenarios**:
  ```
  Scenario: OpenCode Go registry and auth test matrix passes
    Tool: Bash
    Steps: Run `uv run pytest tests/test_llm_registry.py::test_opencode_go_analysis_models_validate tests/test_llm_registry.py::test_opencode_go_market_model_rejected tests/test_llm_registry.py::test_opencode_go_kimi_k2_5_rejects_thinking_level tests/test_llm_registry.py::test_opencode_go_unlisted_go_models_rejected tests/test_main_controller.py::TestMainController::test_required_llm_provider_env_vars_include_opencode_go tests/test_main_controller.py::TestMainController::test_resolve_provider_credentials_maps_opencode_go_correctly tests/test_main_controller.py::TestMainController::test_runtime_auth_requires_opencode_api_key_when_opencode_go_configured tests/test_main_controller.py::TestMainController::test_runtime_auth_does_not_require_opencode_api_key_when_unused -q`
    Expected: Exact OpenCode Go validation/auth matrix passes with no live network dependency.
    Evidence: .sisyphus/evidence/task-6-opencode-go-tests.txt

  Scenario: Property generators respect market_model exclusion
    Tool: Bash
    Steps: Run `uv run pytest tests/test_config_persistence_properties.py tests/test_config_file_management_properties.py -q`
    Expected: Property-based tests pass with generators that never treat `market_model=opencode-go` as valid.
    Evidence: .sisyphus/evidence/task-6-opencode-go-tests-error.txt
  ```

  **Commit**: NO | Message: `test(config): cover opencode-go provider boundaries` | Files: [`tests/test_llm_registry.py`, `tests/test_main_controller.py`, `tests/test_config_manager.py`, property tests]

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
  - `feat(registry): add opencode-go provider support`
- Include registry, auth wiring, docs, and tests together to avoid partial provider exposure.

## Success Criteria
- `opencode-go` is available as a distinct provider with `OPENCODE_API_KEY`.
- Exactly 3 fixed OpenCode Go models are supported: `glm-5.1`, `kimi-k2.5`, `mimo-v2-pro`.
- OpenCode Go is valid for `model` and `fallback_models`, but invalid for `market_model`.
- OpenCode Go models default to no `thinking_level`, no search, and no undocumented capabilities.
- Startup/auth validation handles OpenCode Go correctly without breaking Kimi/Grok.
- Docs and tests reflect the exact supported scope and exclusions.
