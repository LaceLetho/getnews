# Monolith Legacy Cleanup Plan

## TL;DR
> **Summary**: 删除 Phase 1 拆分后仍残留的单体兼容路径，只保留清晰的 split-service 执行面，避免 coding agent 被 `/run`、`api-server`、`once`、`schedule`、旧入口函数和兼容测试误导。
> **Deliverables**:
> - 仅保留 `analysis-service`、`api-only`、`ingestion` 三条运行路径
> - 删除 `/run` 及其帮助、菜单、提示、测试与文档残留
> - 删除 `api-server`、`api`、`once`、`schedule`、`scheduler`、`crypto-news-api` 等兼容模式/别名
> - 删除旧单体入口函数、无效兼容方法、兼容测试与遗留示例
> **Effort**: Large
> **Parallel**: YES - 3 waves
> **Critical Path**: 1 → 2 → 4 → 5 → 6 → 7 → 8

## Context
### Original Request
- 审查当前项目中仍遗留的单体应用模式和代码。
- 准备把它们都删掉，让代码更加简洁，不混淆 coding agent 的判断。

### Interview Summary
- 用户要求**彻底移除兼容模式**，而不是只隐藏误导性暴露。
- 用户确认测试策略采用**先补测试再删除**（characterization-first / split-service guardrails first）。
- 清理目标不仅包括运行模式，还包括 Telegram 命令暴露、测试、文档、模板、兼容入口与别名。

### Metis Review (gaps addressed)
- 明确把删除范围锁定在“兼容/遗留面清理”，不扩展为 coordinator 或 API 架构重做。
- 明确先补支持路径与禁用路径测试，再删除兼容代码，避免因为 import/path 变化造成错误归因。
- 明确需要 repo-wide zero-reference 验证，防止删除运行时代码后仍残留 `/run`、`api-server`、`once`、`schedule` 等字符串误导 agent。
- 明确保留 `run.py` 作为中性薄封装入口，但它不得继续暴露任何遗留模式；不把它当作本次删除目标。

## Work Objectives
### Core Objective
把仓库从“split-service + monolith compatibility”收敛为“split-service only”，使实现者、测试、文档和 AI agent 都只能看到当前有效的执行模型：
1. `analysis-service`：公网 API + Telegram `/analyze`
2. `api-only`：隔离 API
3. `ingestion`：私有摄取服务

### Deliverables
- `main.py`、`docker-entrypoint.sh`、`execution_coordinator.py` 中不再保留 monolith runtime 和兼容别名
- Telegram 不再注册、展示或提示 `/run`
- 旧 monolith helper / no-op compat 方法 / backward-compat alias 被删除
- legacy 文档、模板、测试和示例全部收敛到 split-service-only 语义
- repo 中不再残留 banned legacy references

### Definition of Done (verifiable conditions with commands)
- `uv run pytest tests/test_ingestion_runtime.py tests/test_api_server.py tests/test_telegram_command_handler_analyze.py tests/test_main_controller.py -q` 退出码为 `0`
- `uv run pytest tests/telegram-multi-user-authorization -q` 退出码为 `0`，且相关断言已改为 split-service-only 语义
- `python3 -m py_compile crypto_news_analyzer/main.py crypto_news_analyzer/execution_coordinator.py crypto_news_analyzer/reporters/telegram_command_handler.py crypto_news_analyzer/api_server.py` 退出码为 `0`
- `uv run python -m crypto_news_analyzer.main --mode analysis-service --help` 退出码为 `0`
- `uv run python -m crypto_news_analyzer.main --mode ingestion --help` 退出码为 `0`
- `uv run python -m crypto_news_analyzer.main --mode api-server`、`uv run python -m crypto_news_analyzer.main --mode once`、`uv run python -m crypto_news_analyzer.main --mode schedule`、`uv run python -m crypto_news_analyzer.main --mode scheduler` 均以非 `0` 退出并输出明确“unsupported/unknown mode”语义
- repo scan 不再命中 `api-server|/run|run_api_server|run_command_listener_mode|once|schedule|crypto-news-api`（允许第三方锁文件或 Git 历史除外）

### Must Have
- 只保留 split-service runtime surface：`analysis-service`、`api-only`、`ingestion`
- Telegram 手动入口只保留 `/analyze` 相关能力
- 删除 runtime、tests、docs、templates、scripts 中的 monolith assumptions
- 先建立 split-service guardrails，再删除兼容代码

### Must NOT Have (guardrails, AI slop patterns, scope boundaries)
- 不借本次清理重构 coordinator 主逻辑
- 不改 `/analyze` API 契约
- 不重新设计 Telegram 系统，只删除 `/run` 及其遗留提示
- 不保留“只是 warning 的旧别名”——本次目标是移除而不是继续兼容
- 不把 `run.py` 误删；它可以保留为薄封装，但不得继续承载遗留模式

## Verification Strategy
> ZERO HUMAN INTERVENTION — all verification is agent-executed.
- Test decision: **TDD / characterization-first**, framework = `pytest` + targeted CLI/runtime assertions + reference scans
- QA policy: Every task includes agent-executed happy-path + failure/edge-case scenarios
- Evidence: `.sisyphus/evidence/task-{N}-{slug}.{ext}`

## Execution Strategy
### Parallel Execution Waves
> Target: 5-8 tasks per wave. <3 per wave (except final) = under-splitting.
> Extract shared dependencies as Wave-1 tasks for max parallelism.

Wave 1: split-service guardrails and banned-surface tests (`1,2,3`)
Wave 2: runtime and Telegram legacy removal (`4,5,6`)
Wave 3: docs/templates/tests purge and zero-reference enforcement (`7,8`)

### Dependency Matrix (full, all tasks)
- `1` blocks `2,3,4,5,6,7,8`
- `2` blocks `4,5,6,7,8`
- `3` blocks `4,5,6,7,8`
- `4` blocks `5,6,7,8`
- `5` blocks `7,8`
- `6` blocks `7,8`
- `7` blocks `8`
- `8` precedes Final Verification Wave

### Agent Dispatch Summary (wave → task count → categories)
- Wave 1 → 3 tasks → `deep`, `unspecified-high`
- Wave 2 → 3 tasks → `deep`, `unspecified-high`
- Wave 3 → 2 tasks → `unspecified-high`, `quick`

## TODOs
> Implementation + Test = ONE task. Never separate.
> EVERY task MUST have: Agent Profile + Parallelization + QA Scenarios.

- [x] 1. 为 retained split-service surface 建立 characterization 测试

  **What to do**: 新增/调整测试，明确仓库唯一支持的运行面是 `analysis-service`、`api-only`、`ingestion`；为 `main.py`、`run.py`、`docker-entrypoint.sh` 的当前有效路径加护栏，确保后续删 legacy 代码时不会误伤 split-service 能力。
  **Must NOT do**: 不先删除 legacy 代码；不在本任务里改帮助文案或文档；不把 retained 行为和 forbidden 行为混在同一个模糊断言里。

  **Recommended Agent Profile**:
  - Category: `deep` — Reason: 需要先把支持路径的真实契约锁定，后续删除才安全
  - Skills: `[]` — 现有 pytest 栈足够
  - Omitted: `['playwright']` — 无浏览器 UI

  **Parallelization**: Can Parallel: NO | Wave 1 | Blocks: `2,3,4,5,6,7,8` | Blocked By: none

  **References** (executor has NO interview context — be exhaustive):
  - Pattern: `crypto_news_analyzer/main.py:20-31,64-99,183-276` — 当前 retained runtime modes 与 dispatch 逻辑
  - Pattern: `docker-entrypoint.sh:277-297` — 容器入口默认 mode 选择与 alias 处理
  - Pattern: `crypto_news_analyzer/api_server.py` — retained API server surface
  - Test: `tests/test_ingestion_runtime.py` — ingestion runtime 测试基础
  - Test: `tests/test_api_server.py` — analysis/API 测试基础
  - Test: `tests/test_telegram_command_handler_analyze.py` — Telegram `/analyze` 测试基础

  **Acceptance Criteria** (agent-executable only):
  - [ ] retained mode 测试明确只覆盖 `analysis-service`、`api-only`、`ingestion`
  - [ ] `run.py` 仍可作为薄封装入口，但其测试不再允许任何 legacy mode
  - [ ] `uv run pytest tests/test_ingestion_runtime.py tests/test_api_server.py tests/test_telegram_command_handler_analyze.py -q` exits `0`

  **QA Scenarios** (MANDATORY — task incomplete without these):
  ```
  Scenario: Retained split-service runtime matrix is locked
    Tool: Bash
    Steps: run `uv run pytest tests/test_ingestion_runtime.py tests/test_api_server.py tests/test_telegram_command_handler_analyze.py -q | tee .sisyphus/evidence/task-1-retained-runtime.txt`
    Expected: exit code 0; tests assert only supported split-service modes remain valid
    Evidence: .sisyphus/evidence/task-1-retained-runtime.txt

  Scenario: Thin wrapper entrypoint does not reintroduce legacy modes
    Tool: Bash
    Steps: run targeted runtime tests covering `run.py` and save output to `.sisyphus/evidence/task-1-run-wrapper.txt`
    Expected: wrapper delegates only to retained modes and rejects removed ones via shared validation
    Evidence: .sisyphus/evidence/task-1-run-wrapper.txt
  ```

  **Commit**: YES | Message: `test(runtime): lock retained split-service entrypoints` | Files: `tests/`, `run.py`

- [x] 2. 为 removed runtime names 和 alias 加负向测试

  **What to do**: 为 `api-server`、`api`、`once`、`schedule`、`scheduler`、`crypto-news-api` 等遗留模式/别名建立 failing-first 负向测试，锁定“删除后必须明确拒绝”的目标行为；覆盖 CLI、容器入口、service-name translation 三类入口。
  **Must NOT do**: 不继续保留 warning + 自动映射；不允许 removed mode 被静默转成 retained mode；不遗漏 `docker-entrypoint.sh` 中的兼容别名。

  **Recommended Agent Profile**:
  - Category: `deep` — Reason: 需要把遗留面从“兼容”改成“明确非法”，避免回归
  - Skills: `[]` — pytest/bash 足够
  - Omitted: `['playwright']` — 无 UI

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: `4,5,6,7,8` | Blocked By: `1`

  **References** (executor has NO interview context — be exhaustive):
  - Pattern: `crypto_news_analyzer/main.py:28-45` — `DEPRECATED_RUNTIME_MODE_ALIASES` 当前会把 `api-server` 映射为 `analysis-service`
  - Pattern: `docker-entrypoint.sh:125-141,290-297` — `api-server` / `api` / `crypto-news-api` 当前兼容路径
  - Pattern: `docs/RAILWAY_DEPLOYMENT.md` — 当前文档已说明 `api-server` 为 retired alias，可据此反向锁定删除目标
  - Test: `tests/test_ingestion_runtime.py`
  - Test: `tests/test_api_server.py`

  **Acceptance Criteria** (agent-executable only):
  - [ ] negative tests 覆盖 CLI `--mode` 和 `docker-entrypoint.sh` 参数/服务名兼容面
  - [ ] tests 明确要求 removed modes 返回非 `0` / unsupported 语义，而不是 warning + fallback
  - [ ] 负向测试在 legacy 代码删除前先失败、删除后转绿

  **QA Scenarios** (MANDATORY — task incomplete without these):
  ```
  Scenario: Removed runtime names are rejected everywhere
    Tool: Bash
    Steps: run targeted negative tests for `api-server`, `api`, `once`, `schedule`, `scheduler`; save output to `.sisyphus/evidence/task-2-negative-modes.txt`
    Expected: tests prove each removed mode is rejected with exact expected unsupported-mode semantics
    Evidence: .sisyphus/evidence/task-2-negative-modes.txt

  Scenario: Legacy Railway/service-name aliases are no longer translated
    Tool: Bash
    Steps: run targeted tests for `crypto-news-api` and docker entrypoint alias handling; save output to `.sisyphus/evidence/task-2-negative-aliases.txt`
    Expected: old service names or aliases no longer auto-map to retained runtime modes
    Evidence: .sisyphus/evidence/task-2-negative-aliases.txt
  ```

  **Commit**: YES | Message: `test(runtime): reject legacy modes and aliases` | Files: `tests/`, `docker-entrypoint.sh`

- [x] 3. 建立 banned legacy reference 扫描护栏

  **What to do**: 新增仓库级 reference-scan 测试/脚本，明确禁止 `api-server`、`/run`、`run_api_server`、`run_command_listener_mode`、`once`、`schedule`、`scheduler`、`crypto-news-api` 等遗留字符串继续出现在代码、文档、模板、测试帮助文案中；允许名单必须显式且最小化。
  **Must NOT do**: 不依赖人工 grep；不把第三方依赖文件、Git 历史或证据文件误纳入失败条件；不允许 scan 规则过宽导致 executor 无法稳定复现。

  **Recommended Agent Profile**:
  - Category: `unspecified-high` — Reason: 需要工程化地锁定 zero-reference 结果，防止遗漏
  - Skills: `[]`
  - Omitted: `['playwright']`

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: `7,8` | Blocked By: `1`

  **References** (executor has NO interview context — be exhaustive):
  - Pattern: `README.md`, `AGENTS.md`, `.env.template` — 文档和模板是最容易残留 legacy strings 的地方
  - Pattern: `crypto_news_analyzer/reporters/telegram_command_handler.py` — `/run` 和帮助文案残留点
  - Pattern: `crypto_news_analyzer/main.py`, `docker-entrypoint.sh` — mode/alias 残留点
  - Test: `tests/telegram-multi-user-authorization/` — `/run` 相关遗留测试集中区

  **Acceptance Criteria** (agent-executable only):
  - [ ] 新扫描规则能稳定跳过 `.git`、`.venv`、`.sisyphus/evidence` 等非源码区域
  - [ ] banned-string scan 在 legacy 删除完成后转绿
  - [ ] scan 结果可作为最终验收命令直接执行

  **QA Scenarios** (MANDATORY — task incomplete without these):
  ```
  Scenario: Repository-wide legacy reference scan is enforceable
    Tool: Bash
    Steps: run the new banned-string scan and save output to `.sisyphus/evidence/task-3-banned-scan.txt`
    Expected: scan deterministically reports only in-scope files and becomes green once legacy cleanup is complete
    Evidence: .sisyphus/evidence/task-3-banned-scan.txt

  Scenario: Allowed directories do not create false positives
    Tool: Bash
    Steps: run scan in CI-like environment and save output to `.sisyphus/evidence/task-3-scan-allowlist.txt`
    Expected: ignored directories/files are excluded by rule, and failures point only to actionable repo files
    Evidence: .sisyphus/evidence/task-3-scan-allowlist.txt
  ```

  **Commit**: YES | Message: `test(repo): enforce zero legacy runtime references` | Files: `tests/`, `scripts/` or `tests/helpers/`

- [x] 4. 删除 `main.py` 中的 legacy modes、alias 和单体入口函数

  **What to do**: 在 `crypto_news_analyzer/main.py` 中收缩运行面，只保留 `analysis-service`、`api-only`、`ingestion`；删除 `DEPRECATED_RUNTIME_MODE_ALIASES`、`api-server` fallback、`once`、`schedule`、`scheduler` dispatch，以及 `run_api_server()`、`initialize_system()` 等 backward-compat 函数；统一 unknown mode 报错语义。
  **Must NOT do**: 不保留 deprecated warning fallback；不保留多余 mode 只是改名；不修改 retained 三种模式的真实行为。

  **Recommended Agent Profile**:
  - Category: `deep` — Reason: 这是主入口收敛点，影响 CLI、tests、容器和 agent 推断
  - Skills: `[]`
  - Omitted: `['playwright']`

  **Parallelization**: Can Parallel: NO | Wave 2 | Blocks: `5,6,7,8` | Blocked By: `1,2`

  **References** (executor has NO interview context — be exhaustive):
  - Pattern: `crypto_news_analyzer/main.py:20-31` — 当前支持模式和 deprecated alias 定义
  - Pattern: `crypto_news_analyzer/main.py:34-51` — `normalize_runtime_mode()` 当前 alias 映射逻辑
  - Pattern: `crypto_news_analyzer/main.py:82-99` — 当前 `once/schedule/scheduler` dispatch
  - Pattern: `crypto_news_analyzer/main.py:114-144` — `run_api_server()` backward-compatible monolith path
  - Pattern: `crypto_news_analyzer/main.py:279-320` — `initialize_system()` backward-compat helper
  - Test: 新增的 runtime matrix / negative mode tests

  **Acceptance Criteria** (agent-executable only):
  - [ ] `main.py` 只接受三种 mode：`analysis-service`、`api-only`、`ingestion`
  - [ ] `api-server`、`once`、`schedule`、`scheduler` 不再出现在 main runtime surface
  - [ ] `uv run python -m crypto_news_analyzer.main --mode analysis-service --help` exits `0`
  - [ ] `uv run python -m crypto_news_analyzer.main --mode api-server` exits non-zero with explicit unsupported-mode semantics

  **QA Scenarios** (MANDATORY — task incomplete without these):
  ```
  Scenario: Main entrypoint exposes only retained modes
    Tool: Bash
    Steps: run targeted runtime tests and save output to `.sisyphus/evidence/task-4-main-runtime.txt`
    Expected: retained modes work; removed modes fail deterministically; no alias fallback remains
    Evidence: .sisyphus/evidence/task-4-main-runtime.txt

  Scenario: Legacy wrapper functions are gone from the main entrypoint surface
    Tool: Bash
    Steps: run banned-string scan plus py_compile checks; save output to `.sisyphus/evidence/task-4-main-cleanup.txt`
    Expected: `run_api_server` and `initialize_system` no longer appear in actionable source files, and main.py compiles cleanly
    Evidence: .sisyphus/evidence/task-4-main-cleanup.txt
  ```

  **Commit**: YES | Message: `refactor(runtime): remove monolith modes from main entrypoint` | Files: `crypto_news_analyzer/main.py`, `run.py`, `tests/`

- [x] 5. 删除 `docker-entrypoint.sh` 的 legacy alias translation 和旧 Railway service compat

  **What to do**: 从 `docker-entrypoint.sh` 中移除 `api-server`、`api`、`crypto-news-api` 的兼容映射，以及任何自动将 legacy surface 转换为 retained runtime 的逻辑；保留 Railway split-service 当前有效映射，仅允许 `crypto-news-analysis -> analysis-service` 与 `crypto-news-ingestion -> ingestion`。
  **Must NOT do**: 不保留“先 warning 再自动修正”的旧逻辑；不删除当前有效的 `RAILWAY_SERVICE_NAME` split-service 选择；不把 migrate-postgres 单次发布入口误删。

  **Recommended Agent Profile**:
  - Category: `unspecified-high` — Reason: 主要是部署/入口层语义收敛，影响生产启动边界
  - Skills: `[]`
  - Omitted: `['playwright']`

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: `7,8` | Blocked By: `2,4`

  **References** (executor has NO interview context — be exhaustive):
  - Pattern: `docker-entrypoint.sh:100-123` — 当前 Railway service 校验包含 `crypto-news-api` 兼容说明
  - Pattern: `docker-entrypoint.sh:125-141` — `get_mode_from_railway_service()` 当前 legacy service-name 映射
  - Pattern: `docker-entrypoint.sh:290-297` — `api-server` / `api` 当前 alias fallback
  - Pattern: `railway.toml` — 当前统一 startCommand 入口
  - Test: 新增的 docker-entrypoint negative alias tests

  **Acceptance Criteria** (agent-executable only):
  - [ ] entrypoint 不再自动接受 `api-server`、`api`、`crypto-news-api`
  - [ ] 仅保留 `crypto-news-analysis` 与 `crypto-news-ingestion` 的 service-name routing
  - [ ] `migrate-postgres` 入口仍保持可用

  **QA Scenarios** (MANDATORY — task incomplete without these):
  ```
  Scenario: Container entrypoint rejects removed aliases
    Tool: Bash
    Steps: run targeted bash/pytest tests for `docker-entrypoint.sh` alias handling; save output to `.sisyphus/evidence/task-5-entrypoint-aliases.txt`
    Expected: removed aliases fail with explicit unsupported semantics; no silent fallback remains
    Evidence: .sisyphus/evidence/task-5-entrypoint-aliases.txt

  Scenario: Railway split-service routing still works
    Tool: Bash
    Steps: run tests simulating `RAILWAY_SERVICE_NAME=crypto-news-analysis` and `crypto-news-ingestion`; save output to `.sisyphus/evidence/task-5-entrypoint-routing.txt`
    Expected: analysis maps to `analysis-service`; ingestion maps to `ingestion`; migration command remains reachable separately
    Evidence: .sisyphus/evidence/task-5-entrypoint-routing.txt
  ```

  **Commit**: YES | Message: `refactor(deploy): drop legacy runtime alias translation` | Files: `docker-entrypoint.sh`, `tests/`, `docs/RAILWAY_DEPLOYMENT.md`

- [x] 6. 删除 coordinator、Telegram、repository 层的 monolith compatibility surface

  **What to do**: 删除 `execution_coordinator.py` 中仅服务于 monolith 的 runner/no-op compat 方法（包括 `run_one_time_execution()`、`run_scheduled_mode()`、`run_command_listener_mode()`、`setup_environment_config()`、`handle_container_signals()` 等），删除 Telegram `/run` 的 handler、注册、速率限制专用逻辑、help/menu/token 提示，删除 `storage/repositories.py` 中 `_data_manager` / `_cache_manager` backward-compat aliases；保留 `/analyze` 与 retained split-service 行为。
  **Must NOT do**: 不改 `/analyze` 主流程；不重写 Telegram 系统整体架构；不删除 `analysis-service` 下 `/analyze`、`/status`、`/market` 等仍有效功能。

  **Recommended Agent Profile**:
  - Category: `deep` — Reason: 涉及运行时边界、Telegram 入口、compat attributes，多点联动
  - Skills: `[]`
  - Omitted: `['playwright']`

  **Parallelization**: Can Parallel: NO | Wave 2 | Blocks: `7,8` | Blocked By: `1,2,4`

  **References** (executor has NO interview context — be exhaustive):
  - Pattern: `crypto_news_analyzer/execution_coordinator.py:1419-1429,1439-1442` — no-op backward-compat methods
  - Pattern: `crypto_news_analyzer/execution_coordinator.py:1996-2059` — `run_one_time_execution()` monolith runner
  - Pattern: `crypto_news_analyzer/execution_coordinator.py:2062-2159` — `run_scheduled_mode()` mixed monolith path
  - Pattern: `crypto_news_analyzer/execution_coordinator.py:2162-2242` — `run_command_listener_mode()` legacy Telegram-only path
  - Pattern: `crypto_news_analyzer/reporters/telegram_command_handler.py:449-450,510-513` — `/run` 注册与菜单暴露
  - Pattern: `crypto_news_analyzer/reporters/telegram_command_handler.py:526-599,1217-1283` — `/run` handler 和业务逻辑
  - Pattern: `crypto_news_analyzer/reporters/telegram_command_handler.py:1400,1445,1453` — help / token 提示中的 `/run` 残留
  - Pattern: `crypto_news_analyzer/storage/repositories.py:411-414` — `_data_manager` / `_cache_manager` backward-compat aliases
  - Test: `tests/test_telegram_command_handler_analyze.py`
  - Test: `tests/telegram-multi-user-authorization/`

  **Acceptance Criteria** (agent-executable only):
  - [ ] `execution_coordinator.py` 不再提供 monolith runner functions
  - [ ] Telegram 不再注册、展示、执行或提示 `/run`
  - [ ] repository factory 不再暴露 `_data_manager` / `_cache_manager` compat aliases
  - [ ] `uv run pytest tests/test_telegram_command_handler_analyze.py tests/telegram-multi-user-authorization -q` exits `0`

  **QA Scenarios** (MANDATORY — task incomplete without these):
  ```
  Scenario: Telegram surface is split-service only
    Tool: Bash
    Steps: run Telegram-focused tests and save output to `.sisyphus/evidence/task-6-telegram-surface.txt`
    Expected: `/run` is absent from handlers/help/menu/prompts; `/analyze` remains functional
    Evidence: .sisyphus/evidence/task-6-telegram-surface.txt

  Scenario: Coordinator no longer exposes monolith runners
    Tool: Bash
    Steps: run targeted runtime/import tests plus banned-string scan; save output to `.sisyphus/evidence/task-6-coordinator-cleanup.txt`
    Expected: monolith runner functions and compat aliases are gone without breaking retained split-service tests
    Evidence: .sisyphus/evidence/task-6-coordinator-cleanup.txt
  ```

  **Commit**: YES | Message: `refactor(legacy): remove monolith coordinator and telegram surfaces` | Files: `crypto_news_analyzer/execution_coordinator.py`, `crypto_news_analyzer/reporters/telegram_command_handler.py`, `crypto_news_analyzer/storage/repositories.py`, `tests/`

- [x] 7. 清理 legacy 文档、模板、示例和测试资产

  **What to do**: 更新/删除所有仍向 agent 暗示 monolith 或 compat modes 的文档与测试资产：README、AGENTS、`.env.template`、部署文档、Telegram 多用户授权测试、`/run` 专用测试、legacy 注释/需求描述、示例命令；把保留的测试全部改写为 split-service-only 语义。
  **Must NOT do**: 不重写整个文档体系；不保留“已废弃但仍可用”的描述；不留下 legacy 测试文件名/断言继续暗示 `/run` 是有效入口。

  **Recommended Agent Profile**:
  - Category: `unspecified-high` — Reason: 涉及多类文件清理，但边界清晰
  - Skills: `[]`
  - Omitted: `['playwright']`

  **Parallelization**: Can Parallel: YES | Wave 3 | Blocks: `8` | Blocked By: `3,4,5,6`

  **References** (executor has NO interview context — be exhaustive):
  - Pattern: `README.md`, `AGENTS.md`, `.env.template` — 用户与 agent 的第一接触面
  - Pattern: `docs/RAILWAY_DEPLOYMENT.md` — 旧 alias 和旧 service name 说明需收敛
  - Pattern: `tests/telegram-multi-user-authorization/test_task_8_1_handle_run_command.py` — `/run` 专用 legacy 测试
  - Pattern: `tests/telegram-multi-user-authorization/test_rate_limit_run_only.py` — `/run` 专属速率限制测试
  - Pattern: `tests/test_execution_coordinator_cache_integration.py` — `/run` legacy 注释/需求引用
  - Pattern: `crypto_news_analyzer/reporters/telegram_command_handler.py` — 需求注释和帮助文案可能需同步清理

  **Acceptance Criteria** (agent-executable only):
  - [ ] README / AGENTS / `.env.template` 仅描述 retained split-service 行为
  - [ ] `/run` 专用 legacy 测试文件被删除或重组为 split-service-only 测试
  - [ ] 文档与测试命名/注释不再暗示 `api-server`、`once`、`schedule`、`/run` 为有效能力

  **QA Scenarios** (MANDATORY — task incomplete without these):
  ```
  Scenario: Docs and templates no longer advertise monolith paths
    Tool: Bash
    Steps: run banned-string scan against docs/templates and save output to `.sisyphus/evidence/task-7-docs-cleanup.txt`
    Expected: docs/templates contain only retained split-service terminology and no removed runtime examples
    Evidence: .sisyphus/evidence/task-7-docs-cleanup.txt

  Scenario: Legacy /run test assets are gone or rewritten
    Tool: Bash
    Steps: run targeted test discovery / pytest collection and save output to `.sisyphus/evidence/task-7-test-assets.txt`
    Expected: no collected test module remains centered on `/run` or removed monolith modes
    Evidence: .sisyphus/evidence/task-7-test-assets.txt
  ```

  **Commit**: YES | Message: `test(docs): purge monolith references from docs and legacy tests` | Files: `README.md`, `AGENTS.md`, `.env.template`, `docs/`, `tests/`

- [x] 8. 统一最终 split-service-only surface 并执行 zero-reference 收口

  **What to do**: 在前述删除完成后，做最后一轮仓库收口：修复剩余 import/调用碎片、更新 retained mode 帮助与错误信息、确认 `run.py` 仅透传 retained modes、运行 zero-reference 扫描并清除最后残留；本任务是全仓收尾，不新增功能。
  **Must NOT do**: 不在这里追加新兼容层；不把 banned strings 留在注释、错误信息、测试快照或样例命令里；不临时恢复 alias 以“让某些旧测试通过”。

  **Recommended Agent Profile**:
  - Category: `quick` — Reason: 前置任务完成后，本任务应主要是碎片收口和最终一致性修复
  - Skills: `[]`
  - Omitted: `['playwright']`

  **Parallelization**: Can Parallel: NO | Wave 3 | Blocks: Final Verification Wave | Blocked By: `3,4,5,6,7`

  **References** (executor has NO interview context — be exhaustive):
  - Pattern: `run.py` — 保留但必须与 `main.py` 的 retained-only mode policy 完全一致
  - Pattern: `crypto_news_analyzer/main.py`, `docker-entrypoint.sh`, `README.md`, `AGENTS.md`, `.env.template` — 最后统一入口/帮助/示例语义
  - Pattern: banned-string scan helper introduced in Task 3 — 本任务的核心验收工具
  - Test: 所有前置新增负向/正向 runtime tests

  **Acceptance Criteria** (agent-executable only):
  - [ ] repo scan 对 banned legacy references 全绿
  - [ ] retained split-service tests 全绿，且不依赖任何 deleted compatibility path
  - [ ] `python3 -m py_compile crypto_news_analyzer/main.py crypto_news_analyzer/execution_coordinator.py crypto_news_analyzer/reporters/telegram_command_handler.py crypto_news_analyzer/api_server.py` exits `0`

  **QA Scenarios** (MANDATORY — task incomplete without these):
  ```
  Scenario: Final zero-reference sweep passes
    Tool: Bash
    Steps: run the final banned-string scan plus targeted grep assertions; save output to `.sisyphus/evidence/task-8-zero-reference.txt`
    Expected: no actionable repo file contains removed runtime names, legacy command names, or monolith-only help text
    Evidence: .sisyphus/evidence/task-8-zero-reference.txt

  Scenario: Split-service-only regression suite stays green
    Tool: Bash
    Steps: run final targeted pytest suite and py_compile checks; save output to `.sisyphus/evidence/task-8-final-regression.txt`
    Expected: retained runtime behavior passes, removed surfaces stay absent, and source files compile cleanly
    Evidence: .sisyphus/evidence/task-8-final-regression.txt
  ```

  **Commit**: YES | Message: `chore(cleanup): finalize split-service-only runtime surface` | Files: repo-wide targeted cleanup files

## Final Verification Wave (MANDATORY — after ALL implementation tasks)
> 4 review agents run in PARALLEL. ALL must APPROVE. Present consolidated results to user and get explicit "okay" before completing.
> **Do NOT auto-proceed after verification. Wait for user's explicit approval before marking work complete.**
> **Never mark F1-F4 as checked before getting user's okay.** Rejection or user feedback -> fix -> re-run -> present again -> wait for okay.
- [x] F1. Plan Compliance Audit — oracle
- [x] F2. Code Quality Review — unspecified-high
- [x] F3. Real Manual QA — unspecified-high
- [x] F4. Scope Fidelity Check — deep

## Commit Strategy
- Branch first: 从新分支 `chore/remove-monolith-legacy` 开始执行，禁止直接在主分支上删除兼容路径
- Commit 1: split-service characterization + negative legacy-mode tests
- Commit 2: runtime/entrypoint alias removal
- Commit 3: execution coordinator and compat helper cleanup
- Commit 4: Telegram `/run` removal and UX cleanup
- Commit 5: legacy tests/docs/templates purge and zero-reference enforcement

## Success Criteria
- 仓库只剩 `analysis-service`、`api-only`、`ingestion` 三种有效运行语义
- Telegram 暴露面只剩 split-service 有效命令，不再出现 `/run`
- 代码、测试、文档、模板、脚本中不再残留 monolith compatibility 线索
- coding agent 从仓库表面无法再推断出旧单体运行模型
