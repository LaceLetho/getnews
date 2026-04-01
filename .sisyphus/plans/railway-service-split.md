# Railway Service Split Plan

## TL;DR
> **Summary**: 将当前单体新闻分析应用，按“共享 PostgreSQL+pgvector 基础设施 + 私有 ingestion service + 公网 analysis/API service”重构，并以渐进式迁移替代一次性重写。
> **Deliverables**:
> - 明确的服务边界与共享数据契约
> - PostgreSQL/pgvector 迁移与作业持久化方案
> - Railway 双应用服务 + 单共享数据库部署形态
> - 保持现有 `/analyze` 异步工作流与 Telegram 分析能力的拆分路径
> **Effort**: XL
> **Parallel**: YES - 3 waves
> **Critical Path**: 1 → 2 → 4 → 5 → 6 → 8 → 9 → 10

## Context
### Original Request
- 将应用拆成三部分：数据库、消息爬取、拉取数据后筛选分析。
- 数据库未来迁移到 PostgreSQL + pgvector，支持语义搜索。
- 类别未来扩展到 crypto、AI、美股、个股等。
- 数据源未来扩展到 RSS、X、API、GitHub、V2EX、Reddit、Hacker News、YouTube、Podcast 等。
- 用户未来可以动态创建分析系统提示词，按类别和最近 24 小时消息发给 LLM 分析。
- 未来会增加基于语义搜索的历史/事件脉络分析服务。
- 三部分都计划部署在 Railway。

### Interview Summary
- Phase 1 数据库定位：共享数据库基础设施，不额外引入独立 data API service。
- 服务暴露方式：analysis/API 公网暴露；数据库与大多数内部任务服务走私网。
- Prompt 管理：Phase 1 不做 UI，仅规划底层能力与持久化契约。
- 爬取触发：定时为主，保留手动补充触发能力。
- 拆分节奏：分阶段渐进拆分。
- 验证策略：先补测试，再拆分。

### Metis Review (gaps addressed)
- 明确 Telegram 归属为 analysis/API 边界内能力，避免单独拆成第 3 个应用服务。
- 明确 Phase 1 不引入 queue/event bus/prompt UI/data API，防止平台化范围膨胀。
- 明确每一阶段都必须有回滚路径，且不能同时进行“存储迁移 + 运行时拆分 + 部署切换”。
- 明确 async job 状态必须脱离进程内内存，进入共享数据库持久化。

### Oracle Review (architecture decisions locked)
- 按 bounded context 而不是当前调用关系拆分：ingestion 只负责采集/标准化/持久化；analysis/API 负责 prompt 解析、检索、分析、对外入口、报告与 Telegram。
- 共享 PostgreSQL 在 Phase 1 同时承担“数据存储 + 轻量 job backbone”，暂不增加专用消息队列。
- 先把单体迁移到 Postgres 并稳定共享契约，再拆成 Railway 多服务；避免 dual-write。
- 所有外部手动触发统一经由 analysis/API 写入 job/request 表；ingestion 保持私有。

## Work Objectives
### Core Objective
把现有单体 Python 应用演进为同仓库、双应用服务、单共享数据库的 Railway 架构：
1. **Shared DB**: PostgreSQL + pgvector（私有）
2. **Ingestion Service**: 只负责抓取、规范化、去重、入库、采集作业状态（私有）
3. **Analysis/API Service**: 负责 HTTP API、Telegram、prompt 解析、时间窗检索、分析请求执行、报告与结果查询（公网）

### Deliverables
- 明确的服务职责矩阵（API、Telegram、scheduler、ingestion、analysis worker、migrations）
- 共享数据库 schema 与 ownership 规则
- **Phase 1 数据与作业契约**：`content_items`、`ingestion_jobs`、`analysis_jobs`（轻量作业状态表）
- **Phase 2 扩展契约**（已预留，未实现）：`analysis_requests`、`analysis_results`、`prompt_templates`、`content_embeddings`
- 单体到 Postgres 的迁移路径与回滚策略
- Railway 双服务部署与私网/公网边界
- 未来多类别、多数据源、语义搜索分析能力的兼容基础

### Definition of Done (verifiable conditions with commands)
- `uv run pytest tests/ -q` 退出码为 `0`
- `uv run mypy crypto_news_analyzer/` 退出码为 `0`
- `curl -sS -o /tmp/analyze-create.json -w "%{http_code}" -X POST "$ANALYSIS_BASE_URL/analyze" -H "Authorization: Bearer $API_KEY" -H "Content-Type: application/json" -d '{"hours":24,"user_id":"test"}'` 返回 `202`
- `curl -sS "$ANALYSIS_BASE_URL/analyze/$JOB_ID" -H "Authorization: Bearer $API_KEY"` 在服务重启后仍能查询同一 job
- `psql "$DATABASE_URL" -c "SELECT COUNT(*) FROM analysis_jobs;"`、`psql "$DATABASE_URL" -c "SELECT COUNT(*) FROM ingestion_jobs;"` 能返回非错误结果
- Railway 最终只有 analysis/API service 拥有公网域名；ingestion service 与数据库仅私网访问

### Must Have
- 同仓库拆分，不要求 Phase 1 拆成多仓库
- PostgreSQL + pgvector 作为共享基础设施
- Telegram 能力归属于 analysis/API service
- `/analyze` 保持异步创建/轮询/取结果的兼容语义
- 爬取服务支持 scheduler 主触发 + 手动补充触发
- 作业状态、重试、锁与结果持久化到共享数据库
- 类别采用稳定 slug（如 `crypto`、`ai`、`us-stocks`、`single-stock`）

### Must NOT Have (guardrails, AI slop patterns, scope boundaries)
- 不新增独立 data API service
- 不新增消息队列、事件总线、Redis、prompt UI、管理后台
- 不让 ingestion service 暴露公网只是为了手动触发
- 不采用 dual-write 作为默认迁移方案
- 不一次性同时改完数据库、服务边界、Railway 部署并直接切流
- 不把 embeddings 建在最终报告文本而不是原始内容分块上

## Verification Strategy
> ZERO HUMAN INTERVENTION — all verification is agent-executed.
- Test decision: **TDD / characterization-first**, framework = `pytest` + targeted API/DB assertions
- QA policy: Every task includes agent-executed happy-path + failure/edge-case scenarios
- Evidence: `.sisyphus/evidence/task-{N}-{slug}.{ext}`

## Execution Strategy
### Parallel Execution Waves
> Target: 5-8 tasks per wave. <3 per wave (except final) = under-splitting.
> Extract shared dependencies as Wave-1 tasks for max parallelism.

Wave 1: baseline contracts and isolation (`1,2,3,4`)
Wave 2: persistent data/job backbone (`5,6,7`)
Wave 3: service split and Railway deployment (`8,9,10,11`)

### Dependency Matrix (full, all tasks)
- `1` blocks `2,3,4,5,8,9,10,11`
- `2` blocks `8,9,10,11`
- `3` blocks `5,6,7,8,9,10,11`
- `4` blocks `5,8,9,10,11`
- `5` blocks `6,7,8,9,10,11`
- `6` blocks `9,10,11`
- `7` blocks `8,9,10,11`
- `8` blocks `9,10,11`
- `9` blocks `10,11`
- `10` blocks `11`
- `11` precedes Final Verification Wave

### Agent Dispatch Summary (wave → task count → categories)
- Wave 1 → 4 tasks → `deep`, `unspecified-high`
- Wave 2 → 3 tasks → `deep`, `unspecified-high`
- Wave 3 → 4 tasks → `deep`, `unspecified-high`, `quick`

## TODOs
> Implementation + Test = ONE task. Never separate.
> EVERY task MUST have: Agent Profile + Parallelization + QA Scenarios.

- [ ] 1. 建立拆分前行为基线（characterization tests）

  **What to do**: 为当前单体行为补齐回归护栏，覆盖 `POST /analyze -> poll -> result`、Telegram `/analyze`、scheduler crawl-only、去重/缓存/执行日志等关键路径；先锁定现状，再进行任何结构拆分。
  **Must NOT do**: 不修改现有对外 API 语义；不引入 Postgres；不开始服务拆分。

  **Recommended Agent Profile**:
  - Category: `deep` — Reason: 需要先理解当前行为并将隐式契约显式化
  - Skills: `[]` — 现有测试栈已足够
  - Omitted: `['playwright']` — 当前无浏览器 UI

  **Parallelization**: Can Parallel: NO | Wave 1 | Blocks: `2,3,4,5,8,9,10,11` | Blocked By: none

  **References** (executor has NO interview context — be exhaustive):
  - Pattern: `crypto_news_analyzer/api_server.py:289-382` — 当前异步分析 API 契约，必须先被测试锁定
  - Pattern: `crypto_news_analyzer/execution_coordinator.py` — 当前主流程编排中心，回归测试必须覆盖其关键行为
  - Pattern: `crypto_news_analyzer/reporters/telegram_command_handler.py` — Telegram `/analyze` 行为边界
  - Test: `tests/test_api_server.py` — API 测试模式
  - Test: `tests/test_main_controller.py` — 编排层测试模式
  - Test: `tests/test_telegram_command_handler_analyze.py` — Telegram 分析命令测试模式
  - Test: `tests/test_data_storage_properties.py` — 存储层性质测试模式
  - External: `docs/AI_ANALYZE_API_GUIDE.md` — `/analyze` 契约必须保持兼容

  **Acceptance Criteria** (agent-executable only):
  - [ ] `uv run pytest tests/test_api_server.py tests/test_main_controller.py tests/test_telegram_command_handler_analyze.py -q` exits `0`
  - [ ] `uv run pytest tests/test_data_storage_properties.py tests/test_config_persistence_properties.py -q` exits `0`
  - [ ] 新增/更新的测试明确断言：job 创建返回 `202`、轮询可见状态迁移、Telegram 分析入口可触发时间窗分析、scheduler 模式不自动执行分析

  **QA Scenarios** (MANDATORY — task incomplete without these):
  ```
  Scenario: Baseline API and command contracts are locked
    Tool: Bash
    Steps: run `uv run pytest tests/test_api_server.py tests/test_telegram_command_handler_analyze.py -q | tee .sisyphus/evidence/task-1-baseline-tests.txt`
    Expected: pytest exit code 0; output contains no FAILED or ERROR lines
    Evidence: .sisyphus/evidence/task-1-baseline-tests.txt

  Scenario: Scheduler-only behavior remains crawl-only
    Tool: Bash
    Steps: run `uv run pytest tests/test_main_controller.py -q | tee .sisyphus/evidence/task-1-scheduler-edge.txt`
    Expected: tests prove schedule/crawl-only path does not implicitly execute full analysis/report flow
    Evidence: .sisyphus/evidence/task-1-scheduler-edge.txt
  ```

  **Commit**: YES | Message: `test(split): lock monolith behavior before service extraction` | Files: `tests/test_api_server.py`, `tests/test_main_controller.py`, `tests/test_telegram_command_handler_analyze.py`, `tests/test_data_storage_properties.py`

- [ ] 2. 隔离启动副作用并拆出独立运行入口

  **What to do**: 把 API、scheduler、Telegram listener 的启动逻辑从共享入口中拆开，改为显式 app factory / runtime entrypoints；确保“启动 API”不会顺带启动 scheduler 或 Telegram，且 scheduler 可单独运行。
  **Must NOT do**: 不改变 API 路由契约；不在此任务中切到 Railway 多服务；不把业务逻辑复制成两份。

  **Recommended Agent Profile**:
  - Category: `deep` — Reason: 需要改造主入口与运行时装配，避免隐藏副作用
  - Skills: `[]` — 普通 Python 重构即可
  - Omitted: `['playwright']` — 无 UI 需求

  **Parallelization**: Can Parallel: NO | Wave 1 | Blocks: `8,9,10,11` | Blocked By: `1`

  **References** (executor has NO interview context — be exhaustive):
  - Pattern: `crypto_news_analyzer/api_server.py:404-413` — 当前 API 启动时附带启动 scheduler/listener，是必须消除的副作用
  - Pattern: `crypto_news_analyzer/main.py:27-45` — 当前运行模式入口
  - Pattern: `docker-entrypoint.sh:229-252` — 当前容器启动命令分发方式
  - Pattern: `crypto_news_analyzer/execution_coordinator.py:1882-1962` — scheduler-only 运行路径
  - Test: `tests/test_api_server.py` — 拆分后要继续保证 API 行为一致
  - Test: `tests/test_main_controller.py` — 拆分入口后要继续保证协调器行为一致

  **Acceptance Criteria** (agent-executable only):
  - [ ] 启动 API 进程时，不再触发 scheduler 和 Telegram listener 初始化
  - [ ] 启动 scheduler 进程时，不再加载 HTTP server
  - [ ] `uv run pytest tests/test_api_server.py tests/test_main_controller.py -q` exits `0`

  **QA Scenarios** (MANDATORY — task incomplete without these):
  ```
  Scenario: API runtime starts without background side effects
    Tool: Bash
    Steps: start API mode in test configuration; capture logs to `.sisyphus/evidence/task-2-api-runtime.txt`; grep for scheduler/listener startup markers
    Expected: HTTP app starts successfully and logs do not contain scheduler start or Telegram listener start markers
    Evidence: .sisyphus/evidence/task-2-api-runtime.txt

  Scenario: Scheduler runtime stays headless
    Tool: Bash
    Steps: start scheduler mode in test configuration; capture logs to `.sisyphus/evidence/task-2-scheduler-runtime.txt`; grep for web server bind markers
    Expected: scheduler initializes crawl loop only and logs do not contain FastAPI/HTTP bind messages
    Evidence: .sisyphus/evidence/task-2-scheduler-runtime.txt
  ```

  **Commit**: YES | Message: `refactor(runtime): isolate api and scheduler startup paths` | Files: `crypto_news_analyzer/main.py`, `crypto_news_analyzer/api_server.py`, `crypto_news_analyzer/execution_coordinator.py`, `docker-entrypoint.sh`

- [x] 3. 锁定共享领域契约与服务职责矩阵

  **What to do**: 在代码中引入可执行/可测试的共享契约层，明确时间窗语义、作业状态机、分析请求字段、服务 ownership；所有外部入口（HTTP、Telegram、scheduler/manual trigger）最终都要生成统一作业契约。
  **Phase 1 实现**: 使用轻量级 `analysis_jobs` 表承载作业状态，而非完整的 `analysis_requests/results` 分离结构；请求契约包含 `hours` + `user_id` 基础字段，类别扩展留待 Phase 2。
  **Must NOT do**: 不做 prompt UI；不做多租户前端；不让不同入口各自定义不同请求结构。

  **Recommended Agent Profile**:
  - Category: `deep` — Reason: 这是后续拆库、拆服务、加语义搜索的统一契约基础
  - Skills: `[]` — 以模型/类型/契约测试为主
  - Omitted: `['playwright']` — 无 UI

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: `5,6,7,8,9,10,11` | Blocked By: `1`

  **References** (executor has NO interview context — be exhaustive):
  - Pattern: `crypto_news_analyzer/models.py` — 现有数据模型定义，可扩展为共享契约基础
  - Pattern: `crypto_news_analyzer/config/manager.py:199-210,212-257,268-282` — 现有配置/env override 机制，需演进为按服务区分
  - Pattern: `crypto_news_analyzer/reporters/telegram_command_handler.py` — Telegram 命令必须复用统一分析请求结构
  - Pattern: `crypto_news_analyzer/api_server.py:289-382` — HTTP API 必须复用统一分析请求结构
  - Test: `tests/test_api_server.py` — 检查请求/响应契约
  - Test: `tests/test_config_persistence_properties.py` — 配置契约测试模式

  **Acceptance Criteria** (agent-executable only):
  - [x] Phase 1: 所有分析入口共享同一基础请求模型，包含 `time_window_hours`（通过 `hours` 字段）、`requested_by`（通过 `user_id` 字段）
  - [x] 时间窗语义被统一为单一规则，并由测试断言
  - [ ] Phase 2 扩展: 类别 slug (`crypto`, `ai`, `us-stocks`, `single-stock`)、`prompt_version`、`retrieval_mode` 字段预留

  **QA Scenarios** (MANDATORY — task incomplete without these):
  ```
  Scenario: HTTP and Telegram create the same analysis request contract
    Tool: Bash
    Steps: run targeted contract tests and save output to `.sisyphus/evidence/task-3-request-contract.txt`
    Expected: tests assert both entrypaths populate the same required fields and status defaults
    Evidence: .sisyphus/evidence/task-3-request-contract.txt

  Scenario: Basic request validation works consistently
    Tool: Bash
    Steps: execute targeted tests for invalid hours and missing user_id, save output to `.sisyphus/evidence/task-3-validation-edge.txt`
    Expected: both API and command-layer validators reject invalid requests with the same error semantics
    Evidence: .sisyphus/evidence/task-3-validation-edge.txt
  ```

  **Commit**: YES | Message: `feat(contract): define shared request and category contracts` | Files: `crypto_news_analyzer/models.py`, `crypto_news_analyzer/config/manager.py`, `crypto_news_analyzer/api_server.py`, `crypto_news_analyzer/reporters/telegram_command_handler.py`, `tests/`

- [ ] 4. 提取存储边界并引入 PostgreSQL-ready repository 层

  **What to do**: 将当前 SQLite 偏实现细节从业务流程中隔离出来，建立可替换的 repository/storage adapter 边界，使 `DataManager`/cache/job/result 访问不再直接绑死 SQLite；为后续 Postgres 迁移和双服务共享做准备。
  **Must NOT do**: 不做 dual-write；不在此任务里切流到 Postgres；不让业务层同时知道 SQLite 和 Postgres 两套细节。

  **Recommended Agent Profile**:
  - Category: `deep` — Reason: 关系到后续所有持久化与服务共享边界
  - Skills: `[]` — 常规抽象与测试即可
  - Omitted: `['playwright']` — 无 UI

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: `5,8,9,10,11` | Blocked By: `1`

  **References** (executor has NO interview context — be exhaustive):
  - Pattern: `crypto_news_analyzer/storage/data_manager.py` — 当前内容、执行日志、查询主要入口
  - Pattern: `crypto_news_analyzer/storage/cache_manager.py` — 当前发送缓存入口
  - Pattern: `config.json:6` — 当前 SQLite 路径配置
  - Pattern: `crypto_news_analyzer/models.py` — 现有存储配置模型
  - Test: `tests/test_data_storage_properties.py` — 存储行为性质测试

  **Acceptance Criteria** (agent-executable only):
  - [ ] 业务层通过统一 repository interface 读写内容、作业、缓存、分析结果
  - [ ] SQLite 仍可通过该 interface 跑通现有测试
  - [ ] `uv run pytest tests/test_data_storage_properties.py tests/test_main_controller.py -q` exits `0`

  **QA Scenarios** (MANDATORY — task incomplete without these):
  ```
  Scenario: SQLite-backed adapter preserves existing behavior
    Tool: Bash
    Steps: run `uv run pytest tests/test_data_storage_properties.py tests/test_main_controller.py -q | tee .sisyphus/evidence/task-4-storage-adapter.txt`
    Expected: exit code 0; storage tests still pass through the new abstraction
    Evidence: .sisyphus/evidence/task-4-storage-adapter.txt

  Scenario: Direct SQLite coupling is removed from orchestrator edge
    Tool: Bash
    Steps: run targeted tests that instantiate orchestrator/controller with repository abstraction and save output to `.sisyphus/evidence/task-4-abstraction-edge.txt`
    Expected: orchestrator tests pass without importing SQLite-specific classes directly
    Evidence: .sisyphus/evidence/task-4-abstraction-edge.txt
  ```

  **Commit**: YES | Message: `refactor(storage): introduce repository boundary before postgres cutover` | Files: `crypto_news_analyzer/storage/`, `crypto_news_analyzer/execution_coordinator.py`, `crypto_news_analyzer/models.py`, `tests/`

- [x] 5. 将主数据存储迁移到 PostgreSQL + pgvector

  **What to do**: 新建 PostgreSQL schema/migrations，承接 `content_items`、分析执行日志、发送缓存、轻量级作业表；完成一次性 backfill/cutover 方案，并让应用在单体模式下先稳定运行在 Postgres 上。
  **Phase 1 Schema**: `analysis_jobs`、`ingestion_jobs` 作为轻量级作业状态表；`prompt_templates`、`content_embeddings` 为 Phase 2 预留，当前仅创建占位结构或不创建。
  **Must NOT do**: 不保留长期 dual-write；不在 schema 未稳定前拆 Railway 多服务；不把 embeddings 建立在最终报告文本上。

  **Recommended Agent Profile**:
  - Category: `deep` — Reason: 数据迁移与 schema 设计将决定后续所有服务交互
  - Skills: `[]` — 以 DB migration 与 repository 适配为主
  - Omitted: `['playwright']` — 无 UI

  **Parallelization**: Can Parallel: NO | Wave 2 | Blocks: `6,7,8,9,10,11` | Blocked By: `1,3,4`

  **References** (executor has NO interview context — be exhaustive):
  - Pattern: `crypto_news_analyzer/storage/data_manager.py` — 当前内容/日志 schema 来源
  - Pattern: `crypto_news_analyzer/storage/cache_manager.py` — 当前发送缓存 schema 来源
  - Pattern: `crypto_news_analyzer/models.py` — 存储配置入口
  - Pattern: `config.json:6` — 当前 DB path，需要迁移为 `DATABASE_URL`
  - Test: `tests/test_data_storage_properties.py` — 迁移后必须继续通过

  **Acceptance Criteria** (agent-executable only):
  - [ ] 应用可在 PostgreSQL 模式下通过关键存储/编排/API 测试
  - [ ] `psql "$DATABASE_URL" -c "CREATE EXTENSION IF NOT EXISTS vector;"` 可成功执行（或 migration 已确保等效结果）
  - [ ] backfill 后关键表计数与 SQLite 源数据对齐，并有脚本化校验输出

  **QA Scenarios** (MANDATORY — task incomplete without these):
  ```
  Scenario: Postgres becomes the single working store
    Tool: Bash
    Steps: run migrations against `$DATABASE_URL`; run targeted storage/api tests; save combined output to `.sisyphus/evidence/task-5-postgres-cutover.txt`
    Expected: migrations succeed, pgvector available, targeted tests pass against Postgres-backed repository
    Evidence: .sisyphus/evidence/task-5-postgres-cutover.txt

  Scenario: Backfill validation catches count drift
    Tool: Bash
    Steps: run scripted SQLite→Postgres validation and save counts to `.sisyphus/evidence/task-5-backfill-validation.txt`
    Expected: content/log/cache table counts match expected cutover rules; mismatches fail the script
    Evidence: .sisyphus/evidence/task-5-backfill-validation.txt
  ```

  **Commit**: YES | Message: `feat(db): cut monolith storage over to postgres and pgvector` | Files: `crypto_news_analyzer/storage/`, `crypto_news_analyzer/models.py`, `config.json`, `tests/`, `migrations/`

- [x] 6. 将分析异步 job 状态持久化到共享数据库

  **What to do**: 用数据库中的 `analysis_jobs` 表替换 `api_server.py` 中的进程内 `analyze_jobs`；保留 `/analyze` 创建、轮询、取结果接口语义，并保证服务重启后状态不丢失。
  **Phase 1 实现说明**: 使用轻量级 `analysis_jobs` 表承载作业生命周期，而非完整的 `analysis_requests` + `analysis_results` 分离结构。后者的完整 request/result 分离、多版本 prompt 支持、语义检索等特性留待 Phase 2。
  **Must NOT do**: 不更改 `/analyze` 的异步工作流；不让 job 状态继续仅存在内存；不把结果覆盖成不可追溯的单条最新记录。

  **Recommended Agent Profile**:
  - Category: `deep` — Reason: 这是多实例/多服务安全性的核心
  - Skills: `[]` — 主要是持久化与 API 契约保持
  - Omitted: `['playwright']` — 无 UI

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: `9,10,11` | Blocked By: `3,5`

  **References** (executor has NO interview context — be exhaustive):
  - Pattern: `crypto_news_analyzer/api_server.py:6-55,167-172,198-217` — 当前进程内全局 job 状态实现，必须替换
  - Pattern: `crypto_news_analyzer/api_server.py:289-382` — 必须保留的 `/analyze` 异步接口语义
  - Pattern: `docs/AI_ANALYZE_API_GUIDE.md` — 对外 API 契约参考
  - Test: `tests/test_api_server.py` — 结果轮询与状态转移测试基础

  **Acceptance Criteria** (agent-executable only):
  - [ ] `POST /analyze` 仍返回 `202` 和可轮询 job 标识
  - [ ] 服务重启后，先前创建的 job 仍可查询状态和结果
  - [ ] `uv run pytest tests/test_api_server.py -q` exits `0`

  **QA Scenarios** (MANDATORY — task incomplete without these):
  ```
  Scenario: Persisted analysis jobs survive restart
    Tool: Bash
    Steps: create a job via API, restart the service, poll the same job ID, save transcript to `.sisyphus/evidence/task-6-job-persistence.txt`
    Expected: job remains queryable after restart and proceeds through queued/running/completed or failed states without loss
    Evidence: .sisyphus/evidence/task-6-job-persistence.txt

  Scenario: Invalid job lookup returns stable error contract
    Tool: Bash
    Steps: request a non-existent job ID and save response to `.sisyphus/evidence/task-6-missing-job.txt`
    Expected: API returns the documented not-found/status response without server error
    Evidence: .sisyphus/evidence/task-6-missing-job.txt
  ```

  **Commit**: YES | Message: `feat(api): persist analyze job lifecycle in postgres` | Files: `crypto_news_analyzer/api_server.py`, `crypto_news_analyzer/storage/`, `crypto_news_analyzer/models.py`, `tests/test_api_server.py`

- [x] 7. 为 ingestion 建立独立作业与幂等控制

  **What to do**: 引入 `ingestion_jobs` 与幂等控制；确保 scheduler 和手动触发都只是在数据库里登记作业，真正采集由 ingestion runtime 拉取并执行，避免重复抓取与重复发送。
  **Phase 1 实现**: 使用 `ingestion_jobs` 表承载采集作业状态；`ingestion_runs` 详细执行记录留待 Phase 2。
  **Must NOT do**: 不通过公网直接暴露 ingestion；不让多个 replica 同时执行同一 source run；不把 Telegram/HTTP 直接耦合到具体 crawler 实现。

  **Recommended Agent Profile**:
  - Category: `deep` — Reason: 多源抓取、多实例部署、后续扩展都依赖这里的幂等与状态机
  - Skills: `[]` — 以作业状态与锁机制为主
  - Omitted: `['playwright']` — 无 UI

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: `8,9,10,11` | Blocked By: `3,5`

  **References** (executor has NO interview context — be exhaustive):
  - Pattern: `crypto_news_analyzer/crawlers/data_source_interface.py` — 数据源执行抽象
  - Pattern: `crypto_news_analyzer/crawlers/data_source_factory.py` — 数据源注册与分发模式
  - Pattern: `crypto_news_analyzer/execution_coordinator.py:1120-1240` — 当前 scheduler/crawl 流程参考
  - Pattern: `crypto_news_analyzer/execution_coordinator.py:1882-1962` — scheduler-only 路径参考
  - Test: `tests/test_main_controller.py` — 编排与触发测试模式

  **Acceptance Criteria** (agent-executable only):
  - [ ] scheduler 触发与手动触发都写入统一 `ingestion_jobs` 表
  - [ ] 同一 source + time window 在锁持有期间不会被重复执行
  - [ ] 失败作业有状态、错误信息、重试计数，且测试覆盖

  **QA Scenarios** (MANDATORY — task incomplete without these):
  ```
  Scenario: Concurrent ingestion trigger deduplicates correctly
    Tool: Bash
    Steps: enqueue the same ingestion job twice under test concurrency; save output to `.sisyphus/evidence/task-7-ingestion-dedup.txt`
    Expected: only one run acquires the lock/execution slot; duplicate request is skipped or marked duplicate by design
    Evidence: .sisyphus/evidence/task-7-ingestion-dedup.txt

  Scenario: Source failure records retryable run state
    Tool: Bash
    Steps: inject a failing crawler in tests and save output to `.sisyphus/evidence/task-7-ingestion-failure.txt`
    Expected: run is marked failed with error details and retry metadata, without crashing the scheduler loop
    Evidence: .sisyphus/evidence/task-7-ingestion-failure.txt
  ```

  **Commit**: YES | Message: `feat(ingestion): add persisted ingestion jobs and idempotency` | Files: `crypto_news_analyzer/crawlers/`, `crypto_news_analyzer/execution_coordinator.py`, `crypto_news_analyzer/storage/`, `tests/`

- [x] 8. 落地私有 ingestion service runtime

  **What to do**: 基于已隔离的运行入口，将 crawler 执行、scheduler 驱动、manual backfill trigger 消费、source checkpoint/lock 管理统一收敛到独立 ingestion runtime；该服务只负责 fetch/normalize/persist，不负责分析、报告、Telegram 或公网 API。
  **Must NOT do**: 不暴露公网域名；不在 ingestion 中调用 LLM；不在 ingestion 中生成报告或处理 Telegram 命令。

  **Recommended Agent Profile**:
  - Category: `deep` — Reason: 需要真正把抓取职责从单体里剥离为独立 runtime
  - Skills: `[]` — 以 runtime orchestration 为主
  - Omitted: `['playwright']` — 无 UI

  **Parallelization**: Can Parallel: YES | Wave 3 | Blocks: `9,10,11` | Blocked By: `2,5,7`

  **References** (executor has NO interview context — be exhaustive):
  - Pattern: `crypto_news_analyzer/crawlers/data_source_interface.py` — crawler 统一接口
  - Pattern: `crypto_news_analyzer/crawlers/data_source_factory.py` — source 注册模式，新增来源时应沿用
  - Pattern: `crypto_news_analyzer/execution_coordinator.py` — 当前 crawl orchestration 来源
  - Pattern: `crypto_news_analyzer/main.py` — 新 runtime 入口接入点
  - Pattern: `docker-entrypoint.sh` — 容器模式分发点
  - Test: `tests/test_main_controller.py` — 当前抓取协调测试基础

  **Acceptance Criteria** (agent-executable only):
  - [ ] ingestion service 可在不启动 HTTP API 和 Telegram 的情况下独立运行
  - [ ] scheduler 产生的作业能被 ingestion service 消费并写入 `content_items`
  - [ ] 手动补充触发最终仍由 ingestion service 执行，而不是 analysis/API 直接运行 crawler

  **QA Scenarios** (MANDATORY — task incomplete without these):
  ```
  Scenario: Private ingestion runtime processes queued crawl jobs
    Tool: Bash
    Steps: enqueue a test ingestion job, start ingestion runtime only, save logs to `.sisyphus/evidence/task-8-ingestion-runtime.txt`
    Expected: job is claimed, source runs execute, normalized content is persisted, and no HTTP/Telegram startup markers appear
    Evidence: .sisyphus/evidence/task-8-ingestion-runtime.txt

  Scenario: Ingestion runtime rejects analysis-only actions
    Tool: Bash
    Steps: invoke an analysis/report-only codepath under ingestion runtime tests; save output to `.sisyphus/evidence/task-8-runtime-boundary.txt`
    Expected: tests prove ingestion runtime does not expose or execute analysis/report responsibilities
    Evidence: .sisyphus/evidence/task-8-runtime-boundary.txt
  ```

  **Commit**: YES | Message: `feat(ingestion): extract private ingestion service runtime` | Files: `crypto_news_analyzer/main.py`, `crypto_news_analyzer/execution_coordinator.py`, `crypto_news_analyzer/crawlers/`, `docker-entrypoint.sh`, `tests/`

- [x] 9. 落地公网 analysis/API service runtime

  **What to do**: 将 HTTP API、Telegram 命令、prompt 解析、时间窗检索、分析请求执行、报告生成、结果查询统一收敛到 analysis/API runtime；所有手动触发（HTTP/Telegram）必须只创建 `analysis_jobs` 或 `ingestion_jobs`，不直接运行 crawler。
  **Must NOT do**: 不在 analysis/API 中直接抓取数据源；不丢失现有 `/analyze` 鉴权与异步轮询语义；不让 Telegram 路径绕过统一请求契约。

  **Recommended Agent Profile**:
  - Category: `deep` — Reason: 需要统一所有公网入口和分析执行责任
  - Skills: `[]` — 以 API/Telegram/runtime orchestration 为主
  - Omitted: `['playwright']` — 无浏览器 UI

  **Parallelization**: Can Parallel: YES | Wave 3 | Blocks: `10,11` | Blocked By: `2,5,6,8`

  **References** (executor has NO interview context — be exhaustive):
  - Pattern: `crypto_news_analyzer/api_server.py` — 公网 API 入口
  - Pattern: `crypto_news_analyzer/reporters/telegram_command_handler.py` — Telegram 入口与命令模式
  - Pattern: `crypto_news_analyzer/analyzers/llm_analyzer.py` — 分析执行入口
  - Pattern: `crypto_news_analyzer/execution_coordinator.py` — 当前分析/报告/发送编排来源
  - Pattern: `docs/AI_ANALYZE_API_GUIDE.md` — `/analyze` 契约来源
  - Test: `tests/test_api_server.py` — API 回归测试
  - Test: `tests/test_telegram_command_handler_analyze.py` — Telegram 回归测试

  **Acceptance Criteria** (agent-executable only):
  - [ ] analysis/API service 成为唯一公网入口，并保留 Bearer 鉴权与 async analyze flow
  - [ ] Telegram `/analyze` 与 HTTP `/analyze` 都生成统一 `analysis_jobs` 作业
  - [ ] 手动补爬取需求通过受控入口写入 `ingestion_jobs`，不直接执行 crawler

  **QA Scenarios** (MANDATORY — task incomplete without these):
  ```
  Scenario: Public analysis API preserves async contract
    Tool: Bash
    Steps: POST to `/analyze`, poll status, fetch result; save responses to `.sisyphus/evidence/task-9-api-contract.txt`
    Expected: create returns 202; status transitions are queryable; result endpoint returns final analysis when complete
    Evidence: .sisyphus/evidence/task-9-api-contract.txt

  Scenario: Manual ingestion trigger does not run crawler inline
    Tool: Bash
    Steps: hit the chosen manual-ingestion endpoint/command in test mode; inspect DB state and logs; save to `.sisyphus/evidence/task-9-manual-trigger.txt`
    Expected: action creates an `ingestion_jobs` row and returns quickly; crawler execution is deferred to ingestion runtime
    Evidence: .sisyphus/evidence/task-9-manual-trigger.txt
  ```

  **Commit**: YES | Message: `feat(api): extract public analysis service responsibilities` | Files: `crypto_news_analyzer/api_server.py`, `crypto_news_analyzer/reporters/telegram_command_handler.py`, `crypto_news_analyzer/analyzers/`, `crypto_news_analyzer/execution_coordinator.py`, `tests/`

- [x] 10. 配置 Railway 双服务 + 单共享数据库部署

  **What to do**: 以同仓库方式配置 Railway：一个公网 analysis/API service、一个私有 ingestion service、一个私有 PostgreSQL+pgvector；分离各自 start command、环境变量、secret、私网访问和 healthcheck，保证公网只暴露 analysis/API。
  **Must NOT do**: 不把数据库暴露公网；不让 ingestion service 挂公网域名；不让多个服务同时自动执行 migrations。

  **Recommended Agent Profile**:
  - Category: `unspecified-high` — Reason: 主要是部署编排、运行命令和环境边界收敛
  - Skills: `[]` — repo 现有 Docker/Railway 配置即可支撑
  - Omitted: `['playwright']` — 无 UI

  **Parallelization**: Can Parallel: NO | Wave 3 | Blocks: `11` | Blocked By: `2,5,8,9`

  **References** (executor has NO interview context — be exhaustive):
  - Pattern: `railway.toml:6` — 当前只有单服务 startCommand
  - Pattern: `Dockerfile` — 当前容器镜像构建入口
  - Pattern: `docker-entrypoint.sh` — 运行模式分发点，需支持 service-specific mode
  - Pattern: `crypto_news_analyzer/config/manager.py:31-33,199-210,212-257,268-282` — 环境变量与配置注入模式
  - External: `docs/RAILWAY_DEPLOYMENT.md` — 当前 Railway 部署说明，需更新为双服务模式

  **Acceptance Criteria** (agent-executable only):
  - [ ] analysis/API service 具备公网域名，ingestion service 无公网域名
  - [ ] ingestion 与 analysis/API 均通过私网访问同一 `DATABASE_URL`
  - [ ] migrations 只在指定单一进程/部署步骤执行

  **QA Scenarios** (MANDATORY — task incomplete without these):
  ```
  Scenario: Railway analysis service is public and ingestion stays private
    Tool: Bash
    Steps: deploy both services in staging; hit public analysis URL; attempt direct public reachability check for ingestion; save outputs to `.sisyphus/evidence/task-10-railway-boundary.txt`
    Expected: analysis responds on public URL; ingestion has no public route or returns inaccessible from public internet by design
    Evidence: .sisyphus/evidence/task-10-railway-boundary.txt

  Scenario: Misconfigured ingestion public exposure is caught
    Tool: Bash
    Steps: run deployment/config validation scripts and save output to `.sisyphus/evidence/task-10-railway-misconfig.txt`
    Expected: validation fails if ingestion is assigned a public domain or if multiple services are configured to run migrations
    Evidence: .sisyphus/evidence/task-10-railway-misconfig.txt
  ```

  **Commit**: YES | Message: `chore(deploy): split railway into public api and private ingestion services` | Files: `railway.toml`, `Dockerfile`, `docker-entrypoint.sh`, `docs/RAILWAY_DEPLOYMENT.md`

- [x] 11. 完成切流、回滚预案与旧单体入口退役

  **What to do**: 在双服务稳定后，移除旧“单进程承载 API + scheduler + Telegram + crawl + analysis”的默认路径；保留明确回滚方案（可重新指向旧入口或上一个稳定部署），并补齐最终 cutover 验证脚本与运维说明。
  **Must NOT do**: 不在未通过所有回归与部署验证前删除旧入口；不留下两套长期并行主路径；不省略 rollback 验证。

  **Recommended Agent Profile**:
  - Category: `unspecified-high` — Reason: 这是收尾性切流与退役任务，影响面大但模式明确
  - Skills: `[]` — 以清理和最终验证为主
  - Omitted: `['playwright']` — 无 UI

  **Parallelization**: Can Parallel: NO | Wave 3 | Blocks: Final Verification Wave | Blocked By: `8,9,10`

  **References** (executor has NO interview context — be exhaustive):
  - Pattern: `crypto_news_analyzer/main.py` — 旧总入口退役点
  - Pattern: `docker-entrypoint.sh` — 默认启动行为退役点
  - Pattern: `railway.toml` — 生产启动路径配置
  - Test: `tests/test_api_server.py` — 最终 API 回归
  - Test: `tests/test_main_controller.py` — 最终编排与边界回归
  - Test: `tests/test_telegram_command_handler_analyze.py` — Telegram 最终回归

  **Acceptance Criteria** (agent-executable only):
  - [ ] 生产默认入口只剩 analysis/API service 与 ingestion service 两条明确路径
  - [ ] rollback 脚本/步骤可在 staging 验证通过
  - [ ] `uv run pytest tests/ -q` exits `0`

  **QA Scenarios** (MANDATORY — task incomplete without these):
  ```
  Scenario: Final cutover works end-to-end
    Tool: Bash
    Steps: run full regression suite; create ingestion job; wait for persisted content; trigger analysis; fetch result; save transcript to `.sisyphus/evidence/task-11-cutover.txt`
    Expected: end-to-end flow succeeds across separate services without using the retired monolith startup path
    Evidence: .sisyphus/evidence/task-11-cutover.txt

  Scenario: Rollback can restore previous stable path
    Tool: Bash
    Steps: execute staging rollback procedure and save output to `.sisyphus/evidence/task-11-rollback.txt`
    Expected: services return to prior known-good deployment/configuration and API contract remains reachable
    Evidence: .sisyphus/evidence/task-11-rollback.txt
  ```

  **Commit**: YES | Message: `chore(cutover): retire monolith runtime after split verification` | Files: `crypto_news_analyzer/main.py`, `docker-entrypoint.sh`, `railway.toml`, `docs/RAILWAY_DEPLOYMENT.md`, `tests/`

## Final Verification Wave (MANDATORY — after ALL implementation tasks)
> 4 review agents run in PARALLEL. ALL must APPROVE. Present consolidated results to user and get explicit "okay" before completing.
> **Do NOT auto-proceed after verification. Wait for user's explicit approval before marking work complete.**
> **Never mark F1-F4 as checked before getting user's okay.** Rejection or user feedback -> fix -> re-run -> present again -> wait for okay.
- [ ] F1. Plan Compliance Audit — oracle
- [ ] F2. Code Quality Review — unspecified-high
- [ ] F3. Real Manual QA — unspecified-high
- [ ] F4. Scope Fidelity Check — deep

## Commit Strategy
- Branch first: 从新分支 `feat/railway-service-split` 开始执行，禁止直接在当前主分支上做拆分开发
- Commit 1: characterization baseline + contract tests
- Commit 2: startup/entrypoint isolation
- Commit 3: PostgreSQL storage adapter + migrations
- Commit 4: persisted job state + ingestion/analysis tables
- Commit 5: runtime split + service-specific config
- Commit 6: Railway multi-service deployment + cutover
- Commit 7: legacy monolith decommission

## Phase 1 vs Phase 2 Scope Clarification

### Phase 1 (Current) - Core Service Split
**Goal**: 实现 Railway 双服务部署，保证现有功能可用

**Schema Implemented** (PostgreSQL migration includes legacy + new service-split tables):
- **Legacy tables** (migrated from SQLite): `content_items`, `crawl_status`, `analysis_execution_log`, `sent_message_cache`
- **NEW service-split tables**: `ingestion_jobs`, `analysis_jobs`

**API Contract**:
- `hours: int` - 时间窗口
- `user_id: str` - 请求来源标识

**Phase 1 明确不实现** (移至 Phase 2):
- `analysis_requests` / `analysis_results` 分离表结构
- `prompt_templates` 表与版本管理
- `content_embeddings` 与语义检索
- 类别 slug 字段 (`crypto`, `ai`, `us-stocks`)
- `retrieval_mode` 检索策略选择

### Phase 2 (Future) - Advanced Features
**Goal**: 多类别支持、语义搜索、Prompt 版本管理

**Schema To Add**:
- `analysis_requests` - 分析请求明细
- `analysis_results` - 分析结果存储
- `prompt_templates` - Prompt 模板版本
- `content_embeddings` - 内容向量嵌入
- `ingestion_runs` - 采集执行记录

**API Contract Extension**:
- `category: str` - 分析类别 slug
- `prompt_version: str` - Prompt 版本
- `retrieval_mode: str` - 检索模式

---

## Success Criteria
- 两个应用服务边界稳定：ingestion 不承接公网交互，analysis/API 不直接做采集调度
- PostgreSQL 成为唯一真实数据源，并承载 job/request/result 状态
- 现有 API/Telegram 分析能力在拆分后仍可用且状态不丢失
- 新增类别、数据源、语义搜索能力都可以在既有边界上增量扩展
