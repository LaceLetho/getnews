# Disable Semantic Query Planner

## TL;DR
> **Summary**: Temporarily disable the LLM semantic-search query planner so the original user query is embedded directly, while preserving local keyword LIKE fallback and existing response shape. Do not add online rerank now; add explicit guardrails and evidence so rerank can be evaluated later from real usage.
> **Deliverables**:
> - `SemanticSearchConfig.query_planning_enabled` defaulting to `false`
> - Direct-query semantic planning path: `normalized_intent=query`, `subqueries=[query]`, no planner LLM call when disabled
> - Local-only keyword fallback behavior when planner is disabled
> - Updated unit tests and config comments
> - Rerank non-implementation guardrail and offline-evaluation notes
> **Effort**: Short
> **Parallel**: YES - 5 dependency-true waves
> **Critical Path**: Task 1 → Task 2 → Task 3 → Task 5 → Task 8 → Final Verification

## Context
### Original Request
User reported that semantic search currently asks an LLM to split the user's query into vector subqueries plus keyword LIKE fallback terms. This may confuse clear-intent requests such as “GMX项目消息” because the LLM may add unrelated concepts. User wants the LLM decomposition temporarily disabled and the raw user input used directly for vector search. User also asked whether rerank should be added after semantic search, considering current data content and scale.

### Interview Summary
- Decision: disable semantic query planning in the online path.
- Decision: keep keyword LIKE fallback, but make it local-only and based on the original query plus deterministic heuristics.
- Decision: do not add online rerank in this change.
- Default applied: implement disablement as a config-gated default (`query_planning_enabled=false`) rather than a hard delete, because the user said “暂时禁用”.
- Database finding: News has 160,476 rows with 100% embedding coverage; Intelligence has 17,154 rows with 0% embedding coverage. Recent semantic windows are moderate: last 24h News 804 rows, last 7d News 7,472 rows.
- Rerank rationale: current risk is pre-retrieval query pollution, not candidate ordering. `semantic_search_jobs` has only 2 rows, so there is not enough real-query evidence to justify online rerank cost/latency/failure points.

### Metis Review (gaps addressed)
- Hard-disable vs config-gated: resolved as config-gated default false.
- Keyword output after planner disablement: preserve field and populate from local keyword builder only when keyword fallback is enabled.
- Guardrails: no `_llm_complete()` or planner prompt load during normal disabled flow; preserve response fields; no online rerank; no storage SQL/schema/ranking changes.
- Edge cases: ticker in Chinese (`GMX项目消息`), `$GMX`, `#GMX`, keyword fallback disabled, duplicate local keyword candidates, blank query validation, schema compatibility.

## Work Objectives
### Core Objective
Make semantic search embed the exact validated user query by default, without LLM query decomposition, while preserving deterministic keyword fallback and public result shape.

### Deliverables
- Config model supports `query_planning_enabled: bool = False`.
- `config.jsonc` semantic-search comments reflect that LLM planning is disabled by default and `max_subqueries` only applies when planning is explicitly re-enabled.
- `SemanticSearchService._plan_subqueries()` bypasses LLM planning when disabled.
- Keyword fallback uses deterministic local candidates when planning is disabled.
- Tests prove no planner LLM call happens for `GMX项目消息` and the service remains schema-compatible.
- Plan/execution notes explicitly exclude online rerank.

### Definition of Done (verifiable conditions with commands)
- `uv run pytest tests/news/test_semantic_search_service.py -v` passes.
- `uv run pytest tests/news/test_api_server_semantic_search.py tests/news/test_telegram_command_handler_semantic_search.py -v` passes.
- `uv run pytest tests/shared/test_config_manager.py tests/shared/test_semantic_search_contracts.py -v` passes.
- `uv run mypy crypto_news_analyzer/` passes or reports no new errors attributable to this change.
- `uv run flake8 crypto_news_analyzer/ tests/news/test_semantic_search_service.py` passes.

### Must Have
- `SemanticSearchConfig.query_planning_enabled` exists and defaults to `False`.
- When disabled, `_plan_subqueries("GMX项目消息")` returns `("GMX项目消息", ["GMX项目消息"], [])` or an equivalent empty planned-keyword list before `_build_keyword_queries()` local expansion.
- During disabled semantic search, `_llm_complete()` is not called for query planning.
- During disabled semantic search, `prompts/semantic_search_query_planner.md` is not loaded for query planning.
- Existing API result keys remain: `success`, `report_content`, `normalized_intent`, `matched_count`, `retained_count`, `subqueries`, `keyword_queries`, `source_breakdown`.
- Keyword fallback still works when `keyword_search_enabled=True` and vector search returns no matches.

### Must NOT Have (guardrails, AI slop patterns, scope boundaries)
- Do not add online rerank or call any rerank model in the search path.
- Do not change `DataManager.unified_semantic_search_similar()` SQL ordering, limits, or schema.
- Do not change `DataManager.unified_semantic_search_keywords()` SQL except if tests expose a narrowly scoped LIKE escaping bug; otherwise leave SQL untouched.
- Do not backfill `raw_intelligence_items.embedding`.
- Do not change Telegram command syntax or HTTP DTO contracts.
- Do not delete `prompts/semantic_search_query_planner.md`; keep it available for possible re-enable.
- Do not mix `ContentItem` and `RawIntelligenceItem`; continue using `UnifiedSemanticSearchHit` DTO only for unified search results.

## Verification Strategy
> Evidence collection is ZERO HUMAN INTERVENTION - all verification commands and QA scenarios are agent-executed. Final completion still requires the explicit user approval gate defined in the Final Verification Wave.
- Test decision: tests-after using existing pytest suite.
- QA policy: Every task has agent-executed scenarios.
- Evidence: `.omo/evidence/task-{N}-{slug}.{ext}`

## Execution Strategy
### Parallel Execution Waves
> Target: 5-8 tasks per wave. <3 per wave (except final) = under-splitting.
> Extract shared dependencies as Wave-1 tasks for max parallelism.

Wave 1: Task 1 (config), Task 6 (rerank note/guardrail)
Wave 2: Task 2 (planner bypass), Task 4 (config comments/docs)
Wave 3: Task 3 (keyword tests/behavior), Task 7 (API/Telegram compatibility tests)
Wave 4: Task 5 (focused test sweep)
Wave 5: Task 8 (quality gates)

### Dependency Matrix (full, all tasks)
| Task | Depends On | Blocks |
|---|---|---|
| 1 | None | 2, 4, 5 |
| 2 | 1 | 3, 5, 7 |
| 3 | 2 | 5 |
| 4 | 1 | 8 |
| 5 | 1, 2, 3 | 8 |
| 6 | None | 8 |
| 7 | 2 | 8 |
| 8 | 4, 5, 6, 7 | Final Verification |

### Agent Dispatch Summary (wave → task count → categories)
| Wave | Task Count | Categories |
|---|---:|---|
| 1 | 2 | quick |
| 2 | 2 | quick, writing |
| 3 | 2 | unspecified-low |
| 4 | 1 | unspecified-low |
| 5 | 1 | unspecified-low |

## TODOs
> Implementation + Test = ONE task. Never separate.
> EVERY task MUST have: Agent Profile + Parallelization + QA Scenarios.

- [ ] 1. Add `query_planning_enabled` config default-off

  **What to do**: In `crypto_news_analyzer/models.py`, add `query_planning_enabled: bool = False` to `SemanticSearchConfig`. Extend `validate()` to require it is a bool, matching the existing `keyword_search_enabled` and `enabled` validation style. Ensure `to_dict()` and `from_dict()` continue to work through dataclass defaults without custom serialization changes. Add or update config tests so omitted config uses default `False`, explicit `true` is accepted, and non-bool values raise validation errors.
  **Must NOT do**: Do not remove `max_subqueries`; it remains meaningful only when query planning is explicitly enabled. Do not change `StorageConfig` or unrelated model defaults.

  **Recommended Agent Profile**:
  - Category: `quick` - Reason: Small model/config validation change with localized tests.
  - Skills: [] - No external skill needed.
  - Omitted: [`grok-api-reference`, `llm-instructor`] - No provider API behavior changes.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: 2, 4, 5 | Blocked By: None

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `crypto_news_analyzer/models.py:386-453` - `SemanticSearchConfig` dataclass fields, validation, `to_dict()`, `from_dict()`.
  - Pattern: `crypto_news_analyzer/models.py:423-430` - Bool validation style for `keyword_search_enabled` and `enabled`.
  - Test: `tests/shared/test_config_manager.py` - Config loading patterns.
  - Test: `tests/shared/test_semantic_search_contracts.py` - Semantic-search contract expectations.

  **Acceptance Criteria** (agent-executable only):
  - [ ] `uv run pytest tests/shared/test_config_manager.py tests/shared/test_semantic_search_contracts.py -v` exits 0.
  - [ ] A test instantiating `SemanticSearchConfig()` asserts `query_planning_enabled is False`.
  - [ ] A test instantiating `SemanticSearchConfig(query_planning_enabled=True)` asserts it is accepted.
  - [ ] A test instantiating `SemanticSearchConfig(query_planning_enabled="false")` raises `ValueError`.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Default config disables query planning
    Tool: Bash
    Steps: uv run python - <<'PY'
from crypto_news_analyzer.models import SemanticSearchConfig
cfg = SemanticSearchConfig()
assert cfg.query_planning_enabled is False
assert cfg.to_dict()["query_planning_enabled"] is False
print("ok")
PY
    Expected: Command prints `ok` and exits 0.
    Evidence: .omo/evidence/task-1-config-default.txt

  Scenario: Invalid config value is rejected
    Tool: Bash
    Steps: uv run python - <<'PY'
from crypto_news_analyzer.models import SemanticSearchConfig
try:
    SemanticSearchConfig(query_planning_enabled="false")
except ValueError as exc:
    assert "query_planning_enabled" in str(exc)
    print("ok")
else:
    raise AssertionError("expected ValueError")
PY
    Expected: Command prints `ok` and exits 0.
    Evidence: .omo/evidence/task-1-config-invalid.txt
  ```

  **Commit**: YES | Message: `fix(semantic-search): add query planning flag` | Files: [`crypto_news_analyzer/models.py`, `tests/shared/test_config_manager.py`, `tests/shared/test_semantic_search_contracts.py`]

- [ ] 2. Bypass query planner when config is disabled

  **What to do**: Update `SemanticSearchService._plan_subqueries()` so the first branch checks `if not self.semantic_search_config.query_planning_enabled:` and immediately returns `(query, [query], [])` after preserving validated/stripped input. This branch must not call `_load_prompt()`, `_llm_complete()`, or JSON parsing. Keep the existing LLM planning implementation intact under the enabled branch for future explicit re-enable. Add focused tests for `GMX项目消息` proving the planner LLM is not called and only the raw query is embedded.
  **Must NOT do**: Do not delete existing planner code. Do not change `_retrieve_matches()` vector SQL/data-manager calls. Do not change report synthesis LLM behavior; only query planning LLM is disabled.

  **Recommended Agent Profile**:
  - Category: `quick` - Reason: One service method plus targeted unit tests.
  - Skills: [] - No browser or external docs required.
  - Omitted: [`llm-instructor`] - Structured output is not being changed.

  **Parallelization**: Can Parallel: NO | Wave 2 | Blocks: 3, 5, 7 | Blocked By: 1

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `crypto_news_analyzer/semantic_search/service.py:141-157` - `search()` calls `_plan_subqueries()` and passes returned values into retrieval.
  - Pattern: `crypto_news_analyzer/semantic_search/service.py:256-307` - Current `_plan_subqueries()` loads planner prompt and calls `_llm_complete()`.
  - Pattern: `crypto_news_analyzer/semantic_search/service.py:339-343` - Each subquery is embedded; this must become exactly one embedding call for default config.
  - Test: `tests/news/test_semantic_search_service.py:52-70` - Existing planner test to replace/update for disabled default.

  **Acceptance Criteria** (agent-executable only):
  - [ ] `uv run pytest tests/news/test_semantic_search_service.py::test_query_planner_disabled_uses_original_query_without_llm -v` exits 0.
  - [ ] `service._plan_subqueries("GMX项目消息")` returns normalized intent `GMX项目消息`, subqueries `['GMX项目消息']`, and no planned keywords by default.
  - [ ] If `_llm_complete` is monkeypatched to raise `AssertionError`, default `_plan_subqueries()` still succeeds.
  - [ ] If `_load_prompt` is monkeypatched to raise `AssertionError`, default `_plan_subqueries()` still succeeds.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: GMX query bypasses planner
    Tool: Bash
    Steps: uv run pytest tests/news/test_semantic_search_service.py::test_query_planner_disabled_uses_original_query_without_llm -v | tee .omo/evidence/task-2-gmx-bypass.txt
    Expected: Test passes; evidence contains `PASSED` for the named test.
    Evidence: .omo/evidence/task-2-gmx-bypass.txt

  Scenario: Search embeds original query once
    Tool: Bash
    Steps: uv run pytest tests/news/test_semantic_search_service.py::test_search_embeds_original_query_once_when_planner_disabled -v | tee .omo/evidence/task-2-single-embedding.txt
    Expected: Test passes and asserts embedding service calls equal `["GMX项目消息"]`.
    Evidence: .omo/evidence/task-2-single-embedding.txt
  ```

  **Commit**: YES | Message: `fix(semantic-search): bypass planner by default` | Files: [`crypto_news_analyzer/semantic_search/service.py`, `tests/news/test_semantic_search_service.py`]

- [ ] 3. Make keyword fallback local-only under disabled planner

  **What to do**: Update keyword-query behavior so when `query_planning_enabled=False`, `planned_keyword_queries` from `_plan_subqueries()` is empty and `_build_keyword_queries()` constructs deterministic candidates from the original query, normalized intent, subqueries, `_expand_recall_aliases()`, and `_extract_query_fragments()`. Add tests covering `GMX项目消息`, `$GMX 项目消息`, and `keyword_search_enabled=False`. The expected keyword list must include a usable ticker term such as `gmx` and must not include any LLM-invented terms.
  **Must NOT do**: Do not introduce jieba, external NLP packages, or LLM calls for keyword extraction. Do not expand broad crypto synonyms unless existing local alias code already does so.

  **Recommended Agent Profile**:
  - Category: `unspecified-low` - Reason: Existing keyword builder may need careful test adjustment for CJK/ticker fragments.
  - Skills: [] - No external research needed.
  - Omitted: [`grok-api-reference`] - No model API changes.

  **Parallelization**: Can Parallel: NO | Wave 3 | Blocks: 5 | Blocked By: 2

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `crypto_news_analyzer/semantic_search/service.py:394-400` - `_retrieve_matches()` builds keyword queries after vector retrieval.
  - Pattern: `crypto_news_analyzer/semantic_search/service.py:462-484` - `_build_keyword_queries()` currently combines original query and planned keywords.
  - Pattern: `crypto_news_analyzer/semantic_search/service.py:486-498` - Local fallback candidate generation from aliases and fragments.
  - Pattern: `crypto_news_analyzer/storage/data_manager.py:1636-1792` - LIKE fallback expects normalized keyword strings.
  - Test: `tests/news/test_semantic_search_service.py:107-141` - Existing keyword fallback test using LLM-planned keywords; update to local-only behavior.
  - Test: `tests/news/test_semantic_search_service.py:144-185` - Existing `_build_keyword_queries()` tests; adjust expectations away from LLM dynamic keywords.

  **Acceptance Criteria** (agent-executable only):
  - [ ] `uv run pytest tests/news/test_semantic_search_service.py::test_keyword_recall_fills_gap_when_vector_search_is_empty -v` exits 0 with local-only expected keywords.
  - [ ] A test for `GMX项目消息` asserts repository keyword call contains `gmx` or an equivalent lowercased ticker fragment.
  - [ ] A test for `$GMX 项目消息` or `#GMX 项目消息` asserts punctuation does not prevent ticker fallback.
  - [ ] A test with `SemanticSearchConfig(keyword_search_enabled=False)` asserts repository keyword method is not called.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Local keyword fallback recovers GMX ticker
    Tool: Bash
    Steps: uv run pytest tests/news/test_semantic_search_service.py::test_keyword_fallback_extracts_ticker_from_chinese_query -v | tee .omo/evidence/task-3-gmx-keyword.txt
    Expected: Test passes and asserts keyword queries include `gmx`.
    Evidence: .omo/evidence/task-3-gmx-keyword.txt

  Scenario: Keyword fallback can be disabled
    Tool: Bash
    Steps: uv run pytest tests/news/test_semantic_search_service.py::test_keyword_fallback_not_called_when_disabled -v | tee .omo/evidence/task-3-keyword-disabled.txt
    Expected: Test passes and asserts `repository.keyword_calls == []`.
    Evidence: .omo/evidence/task-3-keyword-disabled.txt
  ```

  **Commit**: YES | Message: `fix(semantic-search): keep keyword fallback local` | Files: [`crypto_news_analyzer/semantic_search/service.py`, `tests/news/test_semantic_search_service.py`]

- [ ] 4. Update config comments and operator-facing wording

  **What to do**: Update `config.jsonc` semantic-search comments so they no longer say LLM decomposition is active by default. Add `query_planning_enabled: false` to the semantic-search block with a comment explaining that enabling it restores legacy LLM query planning and makes `max_subqueries` active. Update comments for `max_subqueries` and `max_keyword_queries` to distinguish LLM-planned terms from local deterministic keyword fallback.
  **Must NOT do**: Do not change runtime secrets, LLM model config, analysis config, or unrelated comments. Do not recommend deprecated `api-server` runtime.

  **Recommended Agent Profile**:
  - Category: `writing` - Reason: Config comments/documentation update only.
  - Skills: [] - No external docs needed.
  - Omitted: [`use-railway`] - No deployment operation needed.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: 8 | Blocked By: 1

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `config.jsonc:101-125` - Semantic-search config comments currently mention LLM subquery splitting and keyword expansion.
  - Pattern: `crypto_news_analyzer/models.py:386-401` - Config field order; mirror it in `config.jsonc` for readability.

  **Acceptance Criteria** (agent-executable only):
  - [ ] A `uv run python - <<'PY'` script loads `config.jsonc` through the repository's config parser path and confirms semantic-search config accepts `query_planning_enabled: false`.
  - [ ] `uv run pytest tests/shared/test_config_manager.py -v` exits 0.
  - [ ] `config.jsonc` comment for `max_subqueries` says it applies only when LLM query planning is enabled.
  - [ ] No comment claims LLM decomposition is active by default.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Config file remains parseable
    Tool: Bash
    Steps: uv run pytest tests/shared/test_config_manager.py -v | tee .omo/evidence/task-4-config-manager.txt
    Expected: Config manager tests pass.
    Evidence: .omo/evidence/task-4-config-manager.txt

  Scenario: Comments match disabled default
    Tool: Bash
    Steps: uv run python - <<'PY'
from pathlib import Path
text = Path('config.jsonc').read_text()
assert 'query_planning_enabled' in text
assert 'false' in text[text.index('query_planning_enabled'):text.index('query_planning_enabled') + 80]
assert '仅在启用' in text or 'disabled' in text.lower() or '关闭' in text
print('ok')
PY
    Expected: Command prints `ok` and exits 0.
    Evidence: .omo/evidence/task-4-comment-check.txt
  ```

  **Commit**: YES | Message: `docs(config): clarify semantic query planning default` | Files: [`config.jsonc`]

- [ ] 5. Rewrite semantic-search unit tests around direct-query contract

  **What to do**: Update `tests/news/test_semantic_search_service.py` so tests no longer assume LLM planning is the default. Replace or split existing planner tests: one default-disabled test, one explicit-enabled legacy planner test if keeping enabled branch coverage. Update no-match/report tests to expect `normalized_intent` equals original query and `subqueries` contains exactly the original query under default config. Preserve tests for dedupe, retained cap, source breakdown, mixed domains, and report shape.
  **Must NOT do**: Do not weaken assertions to only check `success=True`. Do not delete coverage for explicit `query_planning_enabled=True` branch if the legacy branch remains.

  **Recommended Agent Profile**:
  - Category: `unspecified-low` - Reason: Test suite update across multiple existing assertions.
  - Skills: [] - No external dependencies.
  - Omitted: [`playwright`] - Backend unit tests only.

  **Parallelization**: Can Parallel: NO | Wave 4 | Blocks: 8 | Blocked By: 1, 2, 3

  **References** (executor has NO interview context - be exhaustive):
  - Test: `tests/news/test_semantic_search_service.py:52-70` - Current planner caps/dedupe test.
  - Test: `tests/news/test_semantic_search_service.py:73-105` - Retained set cap currently expects two vector calls from LLM subqueries; update to direct-query default or explicit-enable branch.
  - Test: `tests/news/test_semantic_search_service.py:187-207` - Yield-channel LLM keyword test; convert to explicit-enabled branch or remove if redundant.
  - Test: `tests/news/test_semantic_search_service.py:209-232` - No-match result shape currently uses normalized LLM intent; update default expectations.
  - Test: `tests/news/test_semantic_search_service.py:475-585` - Unified source breakdown tests currently provide planner JSON responses; remove unnecessary planner response setup under default disabled behavior.

  **Acceptance Criteria** (agent-executable only):
  - [ ] `uv run pytest tests/news/test_semantic_search_service.py -v` exits 0.
  - [ ] At least one test covers default-disabled planner behavior.
  - [ ] At least one test covers explicit `query_planning_enabled=True` branch if branch remains in production code.
  - [ ] Existing mixed News/Intelligence source breakdown tests still pass without relying on query planner LLM responses.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Full semantic search service suite passes
    Tool: Bash
    Steps: uv run pytest tests/news/test_semantic_search_service.py -v | tee .omo/evidence/task-5-semantic-service-tests.txt
    Expected: All tests in file pass.
    Evidence: .omo/evidence/task-5-semantic-service-tests.txt

  Scenario: Explicit legacy planner branch remains covered
    Tool: Bash
    Steps: uv run pytest tests/news/test_semantic_search_service.py -k 'planning_enabled or planner_enabled or query_planning_enabled' -v | tee .omo/evidence/task-5-enabled-branch.txt
    Expected: At least one selected test passes; no selected test fails.
    Evidence: .omo/evidence/task-5-enabled-branch.txt
  ```

  **Commit**: YES | Message: `test(semantic-search): assert direct query planning contract` | Files: [`tests/news/test_semantic_search_service.py`]

- [ ] 6. Add rerank guardrail and evaluation note without online integration

  **What to do**: Add a concise code comment or test assertion documenting that online rerank is intentionally not part of this change. Preferred implementation: add tests asserting `SemanticSearchService.search()` uses `_rank_matches()` only and does not expose/call any rerank service; optionally add a short note in `tests/news/test_semantic_search_service.py` test name/docstring. If adding documentation, use an existing relevant doc/config comment, not a new product doc. Include the DB-based rationale in test comments only if concise: current News scale is moderate, Intelligence embeddings are absent, and job history is too small for rerank ROI.
  **Must NOT do**: Do not add rerank dependencies, config keys, model clients, network calls, or production code paths. Do not create a new docs file outside `.omo`.

  **Recommended Agent Profile**:
  - Category: `quick` - Reason: Guardrail test/comment only.
  - Skills: [] - No rerank library docs needed because no integration.
  - Omitted: [`librarian`] - External rerank docs are out of scope.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: 8 | Blocked By: None

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `crypto_news_analyzer/semantic_search/service.py:158-163` - Search currently ranks with `_rank_matches()` and then truncates.
  - Pattern: `crypto_news_analyzer/semantic_search/service.py:581-605` - Existing ranking is deterministic similarity/time sort.
  - Research: DB showed `semantic_search_jobs` only 2 rows; not enough real-query evidence for online rerank.
  - Research: `raw_intelligence_items` embedding coverage is 0%, so online rerank would not address unified-search recall gap.

  **Acceptance Criteria** (agent-executable only):
  - [ ] No production file contains an import module, class name, function name, method name, dataclass field, or config key containing `rerank`.
  - [ ] A Python AST/config-key check over `crypto_news_analyzer/` and `config.jsonc` exits 0 when scanning for executable rerank integration points.
  - [ ] Semantic-search tests still assert `_rank_matches()` ordering behavior.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: No online rerank production code added
    Tool: Bash
    Steps: uv run python - <<'PY'
import ast
import json
from pathlib import Path

bad = []
for path in Path('crypto_news_analyzer').rglob('*.py'):
    tree = ast.parse(path.read_text(), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [alias.name for alias in getattr(node, 'names', [])]
            if isinstance(node, ast.ImportFrom) and node.module:
                names.append(node.module)
            for name in names:
                if 'rerank' in name.lower():
                    bad.append(f'{path}: import {name}')
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if 'rerank' in node.name.lower():
                bad.append(f'{path}: symbol {node.name}')
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if 'rerank' in node.target.id.lower():
                bad.append(f'{path}: field {node.target.id}')
config_text = Path('config.jsonc').read_text()
for forbidden in ['rerank_model', 'rerank_enabled', 'reranker']:
    if forbidden in config_text.lower():
        bad.append(f'config.jsonc: {forbidden}')
assert not bad, bad
print('ok')
PY
    Expected: Command prints `ok` and exits 0.
    Evidence: .omo/evidence/task-6-no-rerank-code.txt

  Scenario: Existing rank behavior remains deterministic
    Tool: Bash
    Steps: uv run pytest tests/news/test_semantic_search_service.py -k 'rank or retained or source_breakdown' -v | tee .omo/evidence/task-6-ranking-tests.txt
    Expected: Selected tests pass.
    Evidence: .omo/evidence/task-6-ranking-tests.txt
  ```

  **Commit**: YES | Message: `test(semantic-search): guard against online rerank` | Files: [`tests/news/test_semantic_search_service.py`]

- [ ] 7. Verify API and Telegram compatibility for unchanged response contract

  **What to do**: Run and, if needed, minimally update API/Telegram tests to reflect default direct-query fields while preserving endpoint/command behavior. Ensure `/semantic-search` jobs and Telegram `/semantic_search` still pass user query unchanged into `SemanticSearchService.search()`, and that response/result formatting tolerates `subqueries=[original query]` and local keyword lists.
  **Must NOT do**: Do not change Telegram command syntax (`/semantic_search <hours> <topic>`). Do not rename `/news_semantic_search` alias. Do not alter HTTP status codes or response models.

  **Recommended Agent Profile**:
  - Category: `unspecified-low` - Reason: Compatibility verification across existing tests, likely no production changes.
  - Skills: [] - No browser needed; API tests use pytest/TestClient.
  - Omitted: [`playwright`] - No UI surface.

  **Parallelization**: Can Parallel: YES | Wave 3 | Blocks: 8 | Blocked By: 2

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `crypto_news_analyzer/api_server.py:1225` - News routes include `/semantic-search` endpoints in same registration area.
  - Test: `tests/news/test_api_server_semantic_search.py:137-152` - Fake semantic service captures query/time window passed by API.
  - Test: `tests/news/test_telegram_command_handler_semantic_search.py` - Telegram semantic command behavior.
  - Project rule: `AGENTS.md` says `/semantic_search` is canonical and `/news_semantic_search` is deprecated alias but still supported.

  **Acceptance Criteria** (agent-executable only):
  - [ ] `uv run pytest tests/news/test_api_server_semantic_search.py -v` exits 0.
  - [ ] `uv run pytest tests/news/test_telegram_command_handler_semantic_search.py -v` exits 0.
  - [ ] API tests prove raw query text is passed unchanged to service.
  - [ ] Telegram tests prove command parsing still passes topic text unchanged to service.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: HTTP semantic-search contract remains stable
    Tool: Bash
    Steps: uv run pytest tests/news/test_api_server_semantic_search.py -v | tee .omo/evidence/task-7-api-tests.txt
    Expected: All API semantic-search tests pass.
    Evidence: .omo/evidence/task-7-api-tests.txt

  Scenario: Telegram semantic-search command remains stable
    Tool: Bash
    Steps: uv run pytest tests/news/test_telegram_command_handler_semantic_search.py -v | tee .omo/evidence/task-7-telegram-tests.txt
    Expected: All Telegram semantic-search command tests pass.
    Evidence: .omo/evidence/task-7-telegram-tests.txt
  ```

  **Commit**: YES | Message: `test(semantic-search): preserve api telegram contracts` | Files: [`tests/news/test_api_server_semantic_search.py`, `tests/news/test_telegram_command_handler_semantic_search.py`]

- [ ] 8. Run full quality gates for semantic-search change set

  **What to do**: Run the focused tests and static checks after Tasks 1-7. Fix only issues caused by this change. Capture command outputs in `.omo/evidence/`. If `mypy` reports pre-existing unrelated errors, document the exact unrelated files in the evidence and still ensure no new type error is introduced in touched files.
  **Must NOT do**: Do not run formatters that rewrite unrelated files. Do not broaden fixes into unrelated modules. Do not skip failing semantic-search tests.

  **Recommended Agent Profile**:
  - Category: `unspecified-low` - Reason: Command execution and small follow-up fixes.
  - Skills: [] - Standard project toolchain only.
  - Omitted: [`git-master`] - Commit is not required unless the user explicitly asks execution agent to commit.

  **Parallelization**: Can Parallel: NO | Wave 5 | Blocks: Final Verification | Blocked By: 4, 5, 6, 7

  **References** (executor has NO interview context - be exhaustive):
  - Project command guide: `AGENTS.md` says use `uv run pytest`, `uv run mypy`, `uv run flake8`.
  - Tests: `tests/news/test_semantic_search_service.py`, `tests/news/test_api_server_semantic_search.py`, `tests/news/test_telegram_command_handler_semantic_search.py`, `tests/shared/test_config_manager.py`, `tests/shared/test_semantic_search_contracts.py`.
  - Style: `AGENTS.md` requires Black line length 100, type hints, and grouped imports.

  **Acceptance Criteria** (agent-executable only):
  - [ ] `uv run pytest tests/news/test_semantic_search_service.py tests/news/test_api_server_semantic_search.py tests/news/test_telegram_command_handler_semantic_search.py tests/shared/test_config_manager.py tests/shared/test_semantic_search_contracts.py -v` exits 0.
  - [ ] `uv run mypy crypto_news_analyzer/` exits 0 or evidence clearly identifies pre-existing unrelated failures and no touched-file failures.
  - [ ] `uv run flake8 crypto_news_analyzer/ tests/news/test_semantic_search_service.py tests/news/test_api_server_semantic_search.py tests/news/test_telegram_command_handler_semantic_search.py tests/shared/test_config_manager.py tests/shared/test_semantic_search_contracts.py` exits 0.
  - [ ] No source file outside the listed task files is modified unless required by a failing test directly caused by this change.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Focused regression suite passes
    Tool: Bash
    Steps: uv run pytest tests/news/test_semantic_search_service.py tests/news/test_api_server_semantic_search.py tests/news/test_telegram_command_handler_semantic_search.py tests/shared/test_config_manager.py tests/shared/test_semantic_search_contracts.py -v | tee .omo/evidence/task-8-focused-pytest.txt
    Expected: All selected tests pass.
    Evidence: .omo/evidence/task-8-focused-pytest.txt

  Scenario: Static quality gates pass
    Tool: Bash
    Steps: uv run mypy crypto_news_analyzer/ | tee .omo/evidence/task-8-mypy.txt && uv run flake8 crypto_news_analyzer/ tests/news/test_semantic_search_service.py tests/news/test_api_server_semantic_search.py tests/news/test_telegram_command_handler_semantic_search.py tests/shared/test_config_manager.py tests/shared/test_semantic_search_contracts.py | tee .omo/evidence/task-8-flake8.txt
    Expected: Both commands exit 0; if mypy has pre-existing unrelated failures, evidence names them and touched files are clean.
    Evidence: .omo/evidence/task-8-mypy.txt and .omo/evidence/task-8-flake8.txt
  ```

  **Commit**: YES | Message: `fix(semantic-search): use raw query by default` | Files: [`crypto_news_analyzer/models.py`, `crypto_news_analyzer/semantic_search/service.py`, `config.jsonc`, `tests/news/test_semantic_search_service.py`, `tests/news/test_api_server_semantic_search.py`, `tests/news/test_telegram_command_handler_semantic_search.py`, `tests/shared/test_config_manager.py`, `tests/shared/test_semantic_search_contracts.py`]

## Final Verification Wave (MANDATORY — after ALL implementation tasks)
> 4 review agents run in PARALLEL. ALL must APPROVE. Present consolidated results to user and get explicit "okay" before completing.
> **Do NOT auto-proceed after verification. Wait for user's explicit approval before marking work complete.**
> **Never mark F1-F4 as checked before getting user's okay.** Rejection or user feedback -> fix -> re-run -> present again -> wait for okay.
- [ ] F1. Plan Compliance Audit — oracle
- [ ] F2. Code Quality Review — unspecified-high
- [ ] F3. Real Manual QA — unspecified-high
- [ ] F4. Scope Fidelity Check — deep

## Commit Strategy
- One commit after all tasks and verification pass.
- Suggested message: `fix(semantic-search): disable llm query planning by default`
- Per-task `Commit` fields identify the file scope and fallback message if an execution agent is explicitly asked to commit per task; default execution should use this single final commit strategy.
- Commit files should include only semantic search config/service/tests/config comments and any `.omo/evidence/*` generated by the executor if the project convention permits evidence files in commits.

## Success Criteria
- Clear query `GMX项目消息` is embedded exactly once as the only vector subquery by default.
- Query planner LLM is not invoked unless `query_planning_enabled=True` is explicitly configured.
- Local keyword fallback continues to recover ticker/project-name matches.
- API/Telegram semantic search response shape remains backward-compatible.
- No online rerank model is added.
