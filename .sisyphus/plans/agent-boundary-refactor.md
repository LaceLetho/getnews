# Agent Boundary Refactor: Phase 1 + Phase 2 Only

## TL;DR
> **Summary**: Keep this project as a single repository while making the news and intelligence domains explicit to AI agents through documentation, local module boundaries, compatibility-preserving route/command grouping, crawler typing clarification, and test organization.
> **Deliverables**:
> - Updated agent/human documentation describing a dual-domain monorepo.
> - Clear compatibility contract for news vs intelligence boundaries.
> - Low-risk source changes that group FastAPI routes, Telegram commands, crawler item typing, and tests without changing runtime behavior.
> - Verification evidence proving endpoint paths, Telegram command names, CLI modes, env vars, DB schema, and behavior remain unchanged.
> **Effort**: Medium
> **Parallel**: YES - 3 waves
> **Critical Path**: Task 1 → Task 4 → Task 6 → Final Verification Wave

## Context
### Original Request
The project contains two relatively independent functions:
1. crypto news crawling and analysis
2. group/forum message crawling, topic management, and research

The user asked whether the project should be split at repository level to prevent AI agents from confusing the two. After analysis, the recommendation was: do **not** split repositories now; instead keep a single repository and clarify boundaries. The user then requested a concrete refactoring plan for only the first two recommended phases.

### Interview Summary
- Decision: keep a monorepo.
- Decision: implement only Phase 1 and Phase 2.
- Phase 1: documentation and agent guidance only.
- Phase 2: low-risk boundary clarification in code/tests only.
- Test strategy: tests-after using existing `uv run pytest`, `black --check`, `flake8`, and `mypy` commands.
- No full repo split, no package rename, no new services, no DB split, no deployment topology change.

### Metis Review (gaps addressed)
- Added strict compatibility contract for endpoints, commands, CLI modes, env vars, DB schema, and imports.
- Made route/Telegram/test grouping conditional on preserving behavior.
- Required `lsp_find_references` before moving symbols.
- Required no deletion of deprecated entry-based intelligence code; only label or document it.
- Required docs hierarchy so agents know which document is authoritative.
- Required executable acceptance criteria with no human manual verification.

## Work Objectives
### Core Objective
Reduce AI-agent confusion between the news domain and the intelligence/topic-research domain while preserving all existing runtime behavior and keeping a single repository.

### Deliverables
- `AGENTS.md` rewritten to state dual-domain architecture upfront.
- README and/or one canonical docs page updated to describe news vs intelligence as peer bounded contexts sharing infrastructure.
- Module docstrings and comments added where local code boundaries are misleading.
- Crawler interface typing clarified so intelligence crawlers are not typed as returning only `ContentItem`.
- FastAPI route registration grouped by domain without changing endpoint paths or behavior.
- Telegram command registration/help grouping clarified by domain without changing command names or authorization behavior.
- Tests organized or labeled by domain without breaking pytest discovery.
- Verification evidence under `.sisyphus/evidence/`.

### Definition of Done (verifiable conditions with commands)
- `uv run pytest tests/ -v` exits `0` or failures are confirmed as pre-existing and unrelated with evidence.
- `uv run black --check crypto_news_analyzer/ tests/` exits `0`.
- `uv run flake8 crypto_news_analyzer/` exits `0`.
- `uv run mypy crypto_news_analyzer/` has no new errors; if a baseline exists, evidence distinguishes baseline vs new errors.
- No new DB migration file is added.
- Public HTTP paths and methods are unchanged for `/analyze`, `/semantic-search`, `/datasources`, and `/intelligence/*`.
- Telegram command names remain unchanged for `/analyze`, `/market`, `/semantic_search`, `/datasource_*`, and `/topic_*`.
- CLI modes remain unchanged: `analysis-service`, `api-only`, `ingestion`, `embedding-backfill`.

### Must Have
- Explicit dual-domain docs: news domain, intelligence domain, shared infrastructure, and forbidden cross-domain assumptions.
- Compatibility-preserving implementation only.
- Concrete evidence for all changed areas.
- Existing imports preserved where practical; otherwise compatibility re-exports/shims must be added.

### Must NOT Have (guardrails, AI slop patterns, scope boundaries)
- MUST NOT split the repository.
- MUST NOT rename top-level package `crypto_news_analyzer`.
- MUST NOT add services, queues, databases, DB migrations, config formats, or deployment topology changes.
- MUST NOT change endpoint paths, HTTP methods, response schemas, status codes, auth behavior, Telegram command names, CLI modes, env var names, or DB table names.
- MUST NOT extract `MainController`, split `domain/models.py`, or split `storage/data_manager.py` in this plan.
- MUST NOT delete deprecated entry-based intelligence code; only document/label as deprecated compatibility code.
- MUST NOT present the domains as fully independent apps; docs must say “dual-domain monorepo with shared infrastructure.”
- MUST NOT run formatters that write changes until implementation edits are complete and scoped.

## Verification Strategy
> ZERO HUMAN INTERVENTION - all verification is agent-executed.
- Test decision: tests-after using existing pytest/black/flake8/mypy; no new test framework.
- QA policy: Every task has agent-executed scenarios.
- Evidence: `.sisyphus/evidence/task-{N}-{slug}.{ext}`

## Execution Strategy
### Parallel Execution Waves
> Target: 5-8 tasks per wave. <3 per wave (except final) = under-splitting.
> Extract shared dependencies as Wave-1 tasks for max parallelism.

Wave 1: Task 1 documentation source of truth first, then Task 2 README/canonical docs and Task 3 module boundary annotations in parallel after Task 1 vocabulary is established.
Wave 2: Task 4 crawler interface typing, Task 5 FastAPI route grouping, Task 6 Telegram command grouping, Task 7 test organization.
Wave 3: Task 8 compatibility audit and final local verification.

### Dependency Matrix (full, all tasks)
- Task 1: blocks Task 2 and Task 3 by defining canonical vocabulary.
- Task 2: blocked by Task 1; can run parallel with Task 3 after Task 1.
- Task 3: blocked by Task 1; independent from Tasks 4-7 after vocabulary is clear.
- Task 4: blocked by Task 1; independent from Tasks 5-7.
- Task 5: blocked by Task 1; independent from Tasks 4, 6, 7.
- Task 6: blocked by Task 1; independent from Tasks 4, 5, 7.
- Task 7: blocked by Task 1; should run after or alongside Tasks 4-6 but must account for changed imports.
- Task 8: blocked by Tasks 1-7.

### Agent Dispatch Summary (wave → task count → categories)
- Wave 1 → 3 tasks → writing, quick.
- Wave 2 → 4 tasks → quick, unspecified-low.
- Wave 3 → 1 task → unspecified-high.

## TODOs
> Implementation + Test = ONE task. Never separate.
> EVERY task MUST have: Agent Profile + Parallelization + QA Scenarios.

- [x] 1. Establish dual-domain agent guidance in `AGENTS.md`

  **What to do**: Update `AGENTS.md` so the first project overview paragraph states this is a dual-domain monorepo: (a) crypto news crawling/analysis and (b) group/forum intelligence topic research. Add a `## Dual-Domain Architecture` section with a table containing: domain name, purpose, primary data models, source types, API surfaces, Telegram commands, primary modules, and shared infrastructure. Add a `## Agent Boundary Rules` section that says agents must not mix `ContentItem` with `RawIntelligenceItem`, must not treat `/topic_*` as news-analysis commands, must not use deprecated entry-based intelligence as the active path, and must remember `ingestion` runs both news crawling and intelligence collection/research.
  **Must NOT do**: Do not remove existing build/test commands, Railway guidance, or project-specific notes. Do not imply two independent repositories or services. Do not recommend legacy `api-server` as primary runtime.

  **Recommended Agent Profile**:
  - Category: `writing` - Documentation rewrite with architectural precision.
  - Skills: [] - No specialized skill needed.
  - Omitted: [`railway-docs`] - Not changing Railway behavior.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: Tasks 2, 3, 4, 5, 6, 7 | Blocked By: none

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `AGENTS.md` - Current agent guidance and build/test commands to preserve.
  - Pattern: `README.md` - Current public architecture wording and command lists.
  - API/Type: `crypto_news_analyzer/models.py` - News-side models including `ContentItem` and config dataclasses.
  - API/Type: `crypto_news_analyzer/domain/models.py` - Domain models including `RawIntelligenceItem`, `IntelligenceTopic`, `TopicPrompt`, `TopicFinding`, `TopicResearchRun`, and datasource purpose/type enums.
  - Pattern: `crypto_news_analyzer/main.py` - Runtime modes to document without renaming.
  - Pattern: `crypto_news_analyzer/execution_coordinator.py` - `ingestion` runs both news and intelligence work.

  **Acceptance Criteria** (agent-executable only):
  - [ ] `AGENTS.md` contains literal headings `Dual-Domain Architecture` and `Agent Boundary Rules`.
  - [ ] `AGENTS.md` mentions `ContentItem`, `RawIntelligenceItem`, `DataSourcePurpose.NEWS`, and `DataSourcePurpose.INTELLIGENCE`.
  - [ ] `AGENTS.md` explicitly says `ingestion` runs both news crawling and intelligence collection/topic research.
  - [ ] `AGENTS.md` states deprecated entry-based intelligence models are compatibility-only and not the active topic workflow.
  - [ ] `uv run pytest tests/ -q` is run after the docs edit and produces evidence; docs-only edits should not affect tests.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Agent guidance names both domains
    Tool: Bash
    Steps: Run a Python script that reads AGENTS.md and asserts it contains: "Dual-Domain Architecture", "Agent Boundary Rules", "ContentItem", "RawIntelligenceItem", "DataSourcePurpose.NEWS", "DataSourcePurpose.INTELLIGENCE", and "ingestion".
    Expected: Script exits 0 and writes .sisyphus/evidence/task-1-agents-guidance.txt with PASS and matched terms.
    Evidence: .sisyphus/evidence/task-1-agents-guidance.txt

  Scenario: Docs edit did not break tests
    Tool: Bash
    Steps: Run `uv run pytest tests/ -q`.
    Expected: Exit code 0, or a captured pre-existing unrelated baseline failure with no files from this task implicated.
    Evidence: .sisyphus/evidence/task-1-pytest.txt
  ```

  **Commit**: NO | Optional message if user explicitly requests commits later: `docs(agents): clarify news and intelligence boundaries` | Files: [`AGENTS.md`]

- [x] 2. Update README and add canonical boundary documentation

  **What to do**: Update `README.md` so intelligence/topic research is presented as a peer domain, not only a Telegram feature. Add or update `docs/ARCHITECTURE_BOUNDARIES.md` as the canonical human/agent boundary reference. The docs page must include: two data-flow diagrams in text form, shared infrastructure list, public compatibility contract, in-scope Phase 1/2 boundary improvements, and out-of-scope future refactors. If an architecture-boundary document already exists under `docs/`, update it instead of creating a duplicate.
  **Must NOT do**: Do not change API examples, env var names, deployment topology, or runtime command recommendations except to clarify domain ownership. Do not create multiple competing boundary docs.

  **Recommended Agent Profile**:
  - Category: `writing` - Structured architecture documentation.
  - Skills: [] - No specialized skill needed.
  - Omitted: [`railway-docs`] - No Railway feature behavior is changing.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: none after Task 1 | Blocked By: Task 1

  **References**:
  - Pattern: `README.md` - Current user-facing overview, module tree, runtime commands, API docs, Telegram command docs.
  - Pattern: `docs/AI_ANALYZE_API_GUIDE.md` - Must remain authoritative for `/analyze`; link rather than duplicating the full API contract.
  - Pattern: `docs/RAILWAY_DEPLOYMENT.md` - Deployment topology remains unchanged.
  - API/Type: `crypto_news_analyzer/api_server.py` - Contains both `/analyze`/`/semantic-search` and `/intelligence/*` routes.
  - API/Type: `crypto_news_analyzer/reporters/telegram_command_handler.py` - Contains news and intelligence command surfaces.

  **Acceptance Criteria**:
  - [ ] `README.md` lists `intelligence/` as a peer module in the repository structure.
  - [ ] `README.md` contains text equivalent to “dual-domain monorepo with shared infrastructure.”
  - [ ] `docs/ARCHITECTURE_BOUNDARIES.md` exists or an existing equivalent docs page has that content.
  - [ ] Boundary docs include exact data flows: `RSS/X/REST -> ContentItem -> LLMAnalyzer -> ReportGenerator` and `Telegram/V2EX -> RawIntelligenceItem -> TopicResearchScheduler -> TopicFinding`.
  - [ ] Boundary docs state no repository split, DB split, service split, endpoint rename, Telegram command rename, or config format change is part of this refactor.

  **QA Scenarios**:
  ```
  Scenario: Boundary docs contain required contract
    Tool: Bash
    Steps: Run a Python script that reads README.md and docs/ARCHITECTURE_BOUNDARIES.md, asserting required domain names, data flows, and compatibility phrases are present.
    Expected: Script exits 0 and writes PASS plus matched headings.
    Evidence: .sisyphus/evidence/task-2-boundary-docs.txt

  Scenario: API guide remains linked and unchanged in meaning
    Tool: Bash
    Steps: Run a Python script asserting README.md still references docs/AI_ANALYZE_API_GUIDE.md and does not remove the documented `POST /analyze` async workflow text.
    Expected: Script exits 0.
    Evidence: .sisyphus/evidence/task-2-api-guide-link.txt
  ```

  **Commit**: NO | Optional message if user explicitly requests commits later: `docs(architecture): document dual-domain monorepo boundaries` | Files: [`README.md`, `docs/ARCHITECTURE_BOUNDARIES.md`]

- [x] 3. Add local module boundary annotations without behavior changes

  **What to do**: Add or improve concise module docstrings/comments in boundary-sensitive modules so agents see domain intent locally before editing. Target files: `crypto_news_analyzer/intelligence/__init__.py`, `crypto_news_analyzer/analyzers/__init__.py` if present, `crypto_news_analyzer/crawlers/data_source_factory.py`, `crypto_news_analyzer/crawlers/data_source_interface.py`, `crypto_news_analyzer/api_server.py`, and `crypto_news_analyzer/reporters/telegram_command_handler.py`. Comments must say which parts are news, which are intelligence, and which infrastructure is shared. Add visible deprecation comments near deprecated entry-based intelligence models in `crypto_news_analyzer/domain/models.py` only if existing comments are insufficient.
  **Must NOT do**: Do not move code in this task. Do not change imports, logic, function signatures, route registration, command behavior, or runtime output.

  **Recommended Agent Profile**:
  - Category: `quick` - Small source comments/docstrings only.
  - Skills: [] - No specialized skill needed.
  - Omitted: [`ai-slop-remover`] - This is targeted annotation, not broad style cleanup.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: none after Task 1 | Blocked By: Task 1

  **References**:
  - Pattern: `crypto_news_analyzer/intelligence/__init__.py` - Existing short intelligence docstring.
  - Pattern: `crypto_news_analyzer/crawlers/data_source_factory.py` - Flat registry for `rss`, `x`, `rest_api`, `v2ex`, `telegram_group`.
  - Pattern: `crypto_news_analyzer/crawlers/data_source_interface.py` - Current crawler interface typing ambiguity.
  - Pattern: `crypto_news_analyzer/api_server.py` - Shared FastAPI app.
  - Pattern: `crypto_news_analyzer/reporters/telegram_command_handler.py` - Shared Telegram handler.
  - API/Type: `crypto_news_analyzer/domain/models.py` - Deprecated compatibility-only intelligence entry models and active topic models.

  **Acceptance Criteria**:
  - [ ] Targeted modules contain boundary comments/docstrings with “news”, “intelligence”, and “shared infrastructure” where applicable.
  - [ ] No function body behavior changes are introduced by this task.
  - [ ] `uv run pytest tests/ -q` exits 0 or documents unrelated baseline failures.
  - [ ] `uv run black --check crypto_news_analyzer/` exits 0.

  **QA Scenarios**:
  ```
  Scenario: Local boundary annotations present
    Tool: Bash
    Steps: Run a Python script that reads each target file and asserts at least one boundary phrase appears in each changed file.
    Expected: Script exits 0 and records changed files plus matched phrases.
    Evidence: .sisyphus/evidence/task-3-boundary-annotations.txt

  Scenario: Annotation-only source remains valid
    Tool: Bash
    Steps: Run `uv run black --check crypto_news_analyzer/` and `uv run pytest tests/ -q`.
    Expected: Both exit 0, or pytest baseline is documented as pre-existing and unrelated.
    Evidence: .sisyphus/evidence/task-3-validation.txt
  ```

  **Commit**: NO | Optional message if user explicitly requests commits later: `docs(code): annotate news and intelligence boundaries` | Files: [`crypto_news_analyzer/intelligence/__init__.py`, `crypto_news_analyzer/analyzers/__init__.py`, `crypto_news_analyzer/crawlers/data_source_factory.py`, `crypto_news_analyzer/crawlers/data_source_interface.py`, `crypto_news_analyzer/api_server.py`, `crypto_news_analyzer/reporters/telegram_command_handler.py`, `crypto_news_analyzer/domain/models.py`]

- [x] 4. Clarify crawler interface typing for news vs intelligence items

  **What to do**: Fix the misleading crawler interface contract that currently suggests all crawlers return `List[ContentItem]`. Before editing, use LSP references for `DataSourceInterface`, `crawl`, `ContentItem`, and intelligence crawler `crawl` methods. Choose the lowest-risk compatible typing change: prefer a covariant return contract such as `Sequence[CrawlItem]` with `CrawlItem = Union[ContentItem, RawIntelligenceItem]` if imports are safe; do **not** use invariant `List[Union[...]]` if existing `list[ContentItem]` implementations would become mypy-incompatible. If importing `RawIntelligenceItem` would create circular imports, use `Protocol`/`Any` with explicit docstring explaining news crawlers return `ContentItem` and intelligence crawlers return `RawIntelligenceItem`. Update implementation annotations in `telegram_intelligence_crawler.py` and `v2ex_intelligence_crawler.py` only as needed to match the interface. Add or update tests that assert factory-created news crawlers and intelligence crawlers still return their expected item types.
  **Must NOT do**: Do not redesign crawler factory. Do not change crawler runtime behavior, source type strings, datasource payload validation, persistence logic, or ingestion scheduling. Do not introduce broad generics unless localized and test-backed.

  **Recommended Agent Profile**:
  - Category: `quick` - Small typing/interface refactor with targeted tests.
  - Skills: [] - No specialized skill needed.
  - Omitted: [`llm-instructor`] - No LLM structured-output work.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: Task 8 | Blocked By: Task 1

  **References**:
  - API/Type: `crypto_news_analyzer/crawlers/data_source_interface.py` - Current shared interface and return annotation.
  - Pattern: `crypto_news_analyzer/crawlers/rss_crawler_adapter.py` - News crawler adapter expected to return `ContentItem`.
  - Pattern: `crypto_news_analyzer/crawlers/x_crawler_adapter.py` - News crawler adapter expected to return `ContentItem`.
  - Pattern: `crypto_news_analyzer/crawlers/rest_api_crawler.py` - News crawler expected to return `ContentItem`.
  - Pattern: `crypto_news_analyzer/crawlers/telegram_intelligence_crawler.py` - Intelligence crawler expected to return `RawIntelligenceItem`.
  - Pattern: `crypto_news_analyzer/crawlers/v2ex_intelligence_crawler.py` - Intelligence crawler expected to return raw intelligence items.
  - Test: `tests/test_data_source_factory.py` - Existing factory/crawler tests to extend.
  - Test: `tests/test_intelligence_telegram_collector.py` and `tests/test_intelligence_v2ex_collector.py` - Existing intelligence crawler tests.

  **Acceptance Criteria**:
  - [ ] `data_source_interface.py` no longer states or implies all crawlers return only `List[ContentItem]`.
  - [ ] News crawler annotations remain compatible with `ContentItem`.
  - [ ] Intelligence crawler annotations explicitly allow or state `RawIntelligenceItem`.
  - [ ] `uv run pytest tests/test_data_source_factory.py tests/test_intelligence_telegram_collector.py tests/test_intelligence_v2ex_collector.py -v` exits 0.
  - [ ] `uv run mypy crypto_news_analyzer/` has no new errors attributable to this change.

  **QA Scenarios**:
  ```
  Scenario: Crawler type contract is explicit
    Tool: Bash
    Steps: Run a Python script that reads data_source_interface.py and intelligence crawler files, asserting the interface mentions both ContentItem/news and RawIntelligenceItem/intelligence or uses a documented generalized return type.
    Expected: Script exits 0 and writes the discovered annotation/docstring lines.
    Evidence: .sisyphus/evidence/task-4-crawler-contract.txt

  Scenario: Crawler factory and collectors still pass
    Tool: Bash
    Steps: Run `uv run pytest tests/test_data_source_factory.py tests/test_intelligence_telegram_collector.py tests/test_intelligence_v2ex_collector.py -v` and `uv run mypy crypto_news_analyzer/`.
    Expected: Targeted pytest exits 0; mypy has no new crawler-interface errors.
    Evidence: .sisyphus/evidence/task-4-validation.txt
  ```

  **Commit**: NO | Optional message if user explicitly requests commits later: `refactor(crawlers): clarify news and intelligence crawl item types` | Files: [`crypto_news_analyzer/crawlers/data_source_interface.py`, `crypto_news_analyzer/crawlers/telegram_intelligence_crawler.py`, `crypto_news_analyzer/crawlers/v2ex_intelligence_crawler.py`, `tests/test_data_source_factory.py`, `tests/test_intelligence_telegram_collector.py`, `tests/test_intelligence_v2ex_collector.py`]

- [x] 5. Group FastAPI routes by domain without changing public API behavior

  **What to do**: Before moving code, inventory current paths/methods from `crypto_news_analyzer/api_server.py` and save evidence. Use `lsp_find_references` for the app factory and any route/helper symbols before extraction. Then introduce domain grouping for route registration while preserving the same app factory, auth dependencies, endpoint paths, methods, status codes, response models, job behavior, and OpenAPI visibility. Preferred approach: extract route registration helpers or routers into `crypto_news_analyzer/api/news_routes.py` and `crypto_news_analyzer/api/intelligence_routes.py` only if this can be done without circular imports or import-path breakage; otherwise keep code in `api_server.py` but add explicit `register_news_routes()` and `register_intelligence_routes()` sections. Add compatibility imports if any existing tests or callers import route helpers directly from `api_server.py`.
  **Must NOT do**: Do not change `/analyze`, `/semantic-search`, `/datasources`, `/intelligence/*`, `/health`, auth behavior, background job behavior, app factory signature, dependency injection, or OpenAPI route paths. Do not split into multiple FastAPI apps.

  **Recommended Agent Profile**:
  - Category: `unspecified-low` - Compatibility-preserving internal route organization.
  - Skills: [] - No specialized skill needed.
  - Omitted: [`dev-browser`] - API tests are sufficient; no browser UI.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: Task 8 | Blocked By: Task 1

  **References**:
  - Pattern: `crypto_news_analyzer/api_server.py` - Current app factory and route definitions.
  - Test: `tests/test_api_server.py` - Existing news/analyze API tests.
  - Test: `tests/test_api_server_semantic_search.py` - Existing semantic search API tests.
  - Test: `tests/test_intelligence_api.py` - Existing intelligence route tests.
  - Test: `tests/test_topic_findings_api.py` - Existing topic findings route tests.
  - Test: `tests/*datasource*.py` - Existing datasource tests discovered in repo; include any datasource API coverage if present.
  - API/Type: `crypto_news_analyzer/domain/models.py` - Request/response domain models used by routes.

  **Acceptance Criteria**:
  - [ ] Pre-change and post-change route inventories match for path+method across `/health`, `/analyze`, `/semantic-search`, `/datasources`, and `/intelligence/*`.
  - [ ] `uv run pytest tests/test_api_server.py tests/test_api_server_semantic_search.py tests/test_intelligence_api.py tests/test_topic_findings_api.py tests/test_telegram_command_handler_datasource.py tests/test_datasource_bootstrap.py tests/test_datasource_repository.py tests/test_intelligence_datasource_payloads.py -v` exits 0, or any absent file is omitted with evidence from `glob tests/*datasource*.py`.
  - [ ] App factory import path from `crypto_news_analyzer.api_server` remains valid.
  - [ ] No new FastAPI app is introduced.

  **QA Scenarios**:
  ```
  Scenario: HTTP route inventory unchanged
    Tool: Bash
    Steps: Use FastAPI TestClient or app route introspection to write sorted `METHOD PATH` lines before and after the refactor, then compare them for exact equality.
    Expected: Route inventory matches exactly for public routes.
    Evidence: .sisyphus/evidence/task-5-route-inventory.txt

  Scenario: API behavior tests pass
    Tool: Bash
    Steps: Run `uv run pytest tests/test_api_server.py tests/test_api_server_semantic_search.py tests/test_intelligence_api.py tests/test_topic_findings_api.py tests/test_telegram_command_handler_datasource.py tests/test_datasource_bootstrap.py tests/test_datasource_repository.py tests/test_intelligence_datasource_payloads.py -v`, omitting only files proven absent by a file glob.
    Expected: Exit code 0.
    Evidence: .sisyphus/evidence/task-5-api-tests.txt
  ```

  **Commit**: NO | Optional message if user explicitly requests commits later: `refactor(api): group news and intelligence routes` | Files: [`crypto_news_analyzer/api_server.py`, `crypto_news_analyzer/api/news_routes.py`, `crypto_news_analyzer/api/intelligence_routes.py`, `tests/test_api_server.py`, `tests/test_api_server_semantic_search.py`, `tests/test_intelligence_api.py`, `tests/test_topic_findings_api.py`, `tests/*datasource*.py`]

- [x] 6. Group Telegram commands by domain without changing command behavior

  **What to do**: Before editing, inventory registered Telegram command names, aliases, authorization checks, and help output from `telegram_command_handler.py`. Use `lsp_find_references` for the command handler class and any command registration/handler methods before extraction. Group news commands and intelligence commands in source structure. Preferred approach: extract registration/helper functions into `crypto_news_analyzer/reporters/telegram_news_commands.py` and `crypto_news_analyzer/reporters/telegram_intelligence_commands.py` only if imports remain simple and tests pass; otherwise keep the class in one file and create explicit `register_news_commands()` and `register_intelligence_commands()` methods/sections. Preserve centralized authorization, rate limiting, command parser behavior, help behavior, and all command names.
  **Must NOT do**: Do not rename commands. Do not alter `/analyze`, `/market`, `/semantic_search`, `/datasource_*`, `/topic_create`, `/topic_revise`, `/topic_set_prompt`, `/topic_confirm`, `/topic_list`, `/topic_detail`, `/topic_logs`, `/topic_merge`, `/topic_pause`, or `/topic_archive`. Do not bypass existing auth/rate-limit logic.

  **Recommended Agent Profile**:
  - Category: `unspecified-low` - Internal command organization with compatibility tests.
  - Skills: [] - No specialized skill needed.
  - Omitted: [`bird-commands-reference`] - Telegram command registration, not Bird CLI crawling.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: Task 8 | Blocked By: Task 1

  **References**:
  - Pattern: `crypto_news_analyzer/reporters/telegram_command_handler.py` - Current mixed command handler.
  - Test: `tests/test_telegram_command_handler_analyze.py` - News analyze command tests.
  - Test: `tests/test_telegram_command_handler_semantic_search.py` - Semantic search command tests.
  - Test: `tests/test_intelligence_telegram_commands.py` - Topic command tests.
  - Test: `tests/test_topic_findings_telegram.py` - Topic merge Telegram tests.
  - API/Type: `crypto_news_analyzer/models.py` - Telegram command config and chat context models.

  **Acceptance Criteria**:
  - [ ] Command inventory before and after matches exactly for command names and aliases.
  - [ ] Authorization and rate-limit checks remain centralized and apply to both domains.
  - [ ] `uv run pytest tests/test_telegram_command_handler_analyze.py tests/test_telegram_command_handler_semantic_search.py tests/test_intelligence_telegram_commands.py tests/test_topic_findings_telegram.py -v` exits 0.
  - [ ] Help output still includes both news and topic commands with domain grouping.

  **QA Scenarios**:
  ```
  Scenario: Telegram command inventory unchanged
    Tool: Bash
    Steps: Run a unit-level inventory script or test helper before and after refactor to list registered command names/aliases; compare exact sorted output.
    Expected: Inventories match exactly.
    Evidence: .sisyphus/evidence/task-6-command-inventory.txt

  Scenario: Telegram behavior tests pass
    Tool: Bash
    Steps: Run `uv run pytest tests/test_telegram_command_handler_analyze.py tests/test_telegram_command_handler_semantic_search.py tests/test_intelligence_telegram_commands.py tests/test_topic_findings_telegram.py -v`.
    Expected: Exit code 0.
    Evidence: .sisyphus/evidence/task-6-telegram-tests.txt
  ```

  **Commit**: NO | Optional message if user explicitly requests commits later: `refactor(telegram): group news and topic commands` | Files: [`crypto_news_analyzer/reporters/telegram_command_handler.py`, `crypto_news_analyzer/reporters/telegram_news_commands.py`, `crypto_news_analyzer/reporters/telegram_intelligence_commands.py`, `tests/test_telegram_command_handler_analyze.py`, `tests/test_telegram_command_handler_semantic_search.py`, `tests/test_intelligence_telegram_commands.py`, `tests/test_topic_findings_telegram.py`]

- [x] 7. Organize tests by domain only when import-safe

  **What to do**: Assess test discovery and fixture structure before moving files. If `tests/conftest.py`, relative imports, coverage config, or CI assumptions make moves risky, do not move files; instead create `tests/README.md` with domain grouping and optionally add pytest markers if already configured or trivial. If safe, create `tests/news/`, `tests/intelligence/`, and `tests/shared/`, move test files by domain, and preserve fixture visibility by keeping shared fixtures in top-level `tests/conftest.py`. Update any CI/pytest config only if necessary to keep `uv run pytest tests/` working. Domain mapping: news tests include `test_llm_analyzer.py`, `test_rss_crawler.py`, `test_report_generator.py`, API analyze/semantic-search tests, Telegram analyze/semantic-search tests; intelligence tests include `test_intelligence_*`, `test_topic_*`, raw retention tests; shared tests include config, datasource, storage, repository factory, and runtime tests that touch both domains.
  **Must NOT do**: Do not rewrite test assertions just to fit directory moves. Do not hide failing tests. Do not change production behavior. Do not move tests if it requires broad import rewrites or fixture duplication.

  **Recommended Agent Profile**:
  - Category: `quick` - Test file organization with conservative fallback.
  - Skills: [] - No specialized skill needed.
  - Omitted: [`git-master`] - No commit requested by user during planning.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: Task 8 | Blocked By: Task 1

  **References**:
  - Pattern: `tests/` - Current flat test directory.
  - Test: `tests/test_intelligence_api.py`, `tests/test_topic_research_scheduler.py`, `tests/test_topic_prompt_workflow.py` - Intelligence tests.
  - Test: `tests/test_llm_analyzer.py`, `tests/test_report_generator.py`, `tests/test_api_server.py` - News tests.
  - Test: `tests/test_data_source_factory.py`, `tests/test_config_manager.py`, `tests/test_ingestion_runtime.py` - Likely shared tests.
  - Pattern: `pyproject.toml` - Pytest, black, mypy, flake8 config if present.

  **Acceptance Criteria**:
  - [ ] Either `tests/news/`, `tests/intelligence/`, and `tests/shared/` exist with moved files, OR `tests/README.md` documents why moves were unsafe and lists domain grouping.
  - [ ] `uv run pytest tests/ -v` still discovers and runs the test suite.
  - [ ] No production files are changed by this task.
  - [ ] Any pytest config change is minimal and only preserves existing discovery.

  **QA Scenarios**:
  ```
  Scenario: Test organization is explicit
    Tool: Bash
    Steps: Run a Python script that verifies either domain test directories exist or tests/README.md contains headings for News, Intelligence, and Shared.
    Expected: Script exits 0 and records chosen organization path.
    Evidence: .sisyphus/evidence/task-7-test-organization.txt

  Scenario: Pytest discovery preserved
    Tool: Bash
    Steps: Run `uv run pytest tests/ -v`.
    Expected: Exit code 0, or documented pre-existing unrelated baseline failure; pytest must not report import/discovery errors introduced by moves.
    Evidence: .sisyphus/evidence/task-7-pytest.txt
  ```

  **Commit**: NO | Optional message if user explicitly requests commits later: `test: organize news intelligence and shared tests` | Files: [`tests/news/`, `tests/intelligence/`, `tests/shared/`, `tests/README.md`, `pyproject.toml`]

- [x] 8. Run compatibility audit and full verification

  **What to do**: After Tasks 1-7, perform a compatibility audit. Verify no forbidden files or concepts changed: no DB migrations, no service/deployment split, no endpoint/command/CLI/env var rename, no deletion of deprecated intelligence compatibility code. Generate inventories for routes, Telegram commands, CLI modes, and migrations. Run formatting, linting, typing, targeted tests for changed areas, and full test suite. If any command has baseline failures, rerun the smallest command on the pre-change baseline if available or document why the failure is unrelated using failure paths and stack traces.
  **Must NOT do**: Do not fix unrelated failures by expanding scope into medium refactors. Do not add new migrations or deployment files to satisfy tests. Do not mark final verification as complete without evidence.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Cross-cutting audit and evidence collection.
  - Skills: [] - No specialized skill needed.
  - Omitted: [`crypto-news-debug`] - No production/Railway debugging is in scope.

  **Parallelization**: Can Parallel: NO | Wave 3 | Blocks: Final Verification Wave | Blocked By: Tasks 1-7

  **References**:
  - Pattern: `AGENTS.md`, `README.md`, `docs/ARCHITECTURE_BOUNDARIES.md` - Documentation deliverables.
  - Pattern: `crypto_news_analyzer/main.py` - CLI modes must remain unchanged.
  - Pattern: `crypto_news_analyzer/api_server.py` and any new route modules - HTTP route inventory.
  - Pattern: `crypto_news_analyzer/reporters/telegram_command_handler.py` and any new command modules - Telegram command inventory.
  - Pattern: `migrations/` - No new migrations should exist.
  - Pattern: `pyproject.toml` - Tool/test configuration.

  **Acceptance Criteria**:
  - [ ] Route inventory evidence shows no public path/method changes.
  - [ ] Telegram command inventory evidence shows no command-name changes.
  - [ ] CLI mode evidence shows `analysis-service`, `api-only`, `ingestion`, and `embedding-backfill` remain present.
  - [ ] Migration evidence shows no new DB migration files were added.
  - [ ] `uv run black --check crypto_news_analyzer/ tests/` exits 0.
  - [ ] `uv run flake8 crypto_news_analyzer/` exits 0.
  - [ ] `uv run mypy crypto_news_analyzer/` has no new errors.
  - [ ] `uv run pytest tests/ -v` exits 0 or unrelated pre-existing failures are documented with stack traces.

  **QA Scenarios**:
  ```
  Scenario: Compatibility contract preserved
    Tool: Bash
    Steps: Run scripts that collect route inventory, Telegram command inventory, CLI mode strings from main.py, and migration file list; compare against expected names from this plan.
    Expected: All expected routes/commands/modes exist; no forbidden migration addition is detected.
    Evidence: .sisyphus/evidence/task-8-compatibility-audit.txt

  Scenario: Full quality gate passes
    Tool: Bash
    Steps: Run `uv run black --check crypto_news_analyzer/ tests/`, `uv run flake8 crypto_news_analyzer/`, `uv run mypy crypto_news_analyzer/`, and `uv run pytest tests/ -v`.
    Expected: All exit 0, or any nonzero result is proven pre-existing and unrelated with concrete stack trace evidence.
    Evidence: .sisyphus/evidence/task-8-full-verification.txt
  ```

  **Commit**: NO | Optional message if user explicitly requests commits later: `refactor(boundaries): preserve compatibility after domain grouping` | Files: [all files changed by Tasks 1-7 plus evidence summary if repository tracks evidence]

## Final Verification Wave (MANDATORY — after ALL implementation tasks)
> 4 review agents run in PARALLEL. ALL must APPROVE. Present consolidated results to user and get explicit "okay" before completing.
> All QA and evidence collection is agent-executed; the explicit user "okay" is a workflow approval gate after evidence is presented, not a manual QA requirement.
> **Do NOT auto-proceed after verification. Wait for user's explicit approval before marking work complete.**
> **Never mark F1-F4 as checked before getting user's okay.** Rejection or user feedback -> fix -> re-run -> present again -> wait for okay.
- [x] F1. Plan Compliance Audit — oracle
- [x] F2. Code Quality Review — unspecified-high
- [x] F3. Real Manual QA — unspecified-high
- [x] F4. Scope Fidelity Check — deep

## Commit Strategy
- Do not commit unless the user explicitly requests commits.
- If the user later requests one commit after execution and tests pass, use: `refactor(architecture): clarify news and intelligence boundaries`.
- If the user later requests split commits, use:
  1. `docs(architecture): document news and intelligence boundaries`
  2. `refactor(boundaries): group routes commands and crawler typing`
- Do not commit generated evidence files unless repository convention explicitly tracks `.sisyphus/evidence/`.

## Success Criteria
- Agents reading `AGENTS.md` and README can identify news vs intelligence domains without tracing source code.
- Agents working in API, Telegram, crawler, and test areas see local domain boundaries before editing.
- Runtime behavior is unchanged.
- Verification commands pass or document pre-existing unrelated baseline failures.
