# Create OpenCode Railway Debug Skill

## TL;DR
> **Summary**: Add a project-local OpenCode skill named `crypto-news-debug` that lets coding agents inspect Railway split deployments with `RAILWAY_API_TOKEN`, and perform tightly-scoped restart/redeploy actions for app services only.
> **Deliverables**:
> - `.opencode/skills/crypto-news-debug/SKILL.md`
> - `tests/test_opencode_skill_crypto_news_debug.py`
> - Passing targeted pytest contract suite for the skill
> **Effort**: Short
> **Parallel**: YES - 3 waves
> **Critical Path**: 1 → 2/3/4 → 5/6/7/8/9 → 10

## Context
### Original Request
Create a reusable OpenCode skill so coding agents can use `RAILWAY_API_TOKEN` from the Railway Linux Docker environment to inspect multiple split-deployment Railway services, including PostgreSQL, `analysis-service`, `ingestion`, and future services, using official OpenCode skill docs and Railway API docs as references.

### Interview Summary
- Ignore `.kiro/*`; only target official OpenCode skill layout.
- Canonical skill name: `crypto-news-debug`.
- First version must support runtime selection of Railway `project` / `environment` / `service`.
- Primary UX is preset workflows, not freeform API usage.
- V1 allows limited operational actions: `restart` and `redeploy` for app services only.
- PostgreSQL / managed database services remain inspection-only in v1.
- Keep a small set of raw **read-only** GraphQL templates as fallback, but do not expose arbitrary write templates.

### Metis Review (gaps addressed)
- Narrowed scope to discovery, status, logs, restart, and redeploy only.
- Chose `crypto-news-debug` to match existing repo guidance in `AGENTS.md`.
- Locked database services to read-only to avoid unsafe parity assumptions with app services.
- Rejected MCP/custom dependency work for v1; plan uses Bash + `curl` examples only.
- Added contract tests to prevent scope creep into rollback, stop, cancel, remove, variable edits, domains, or volume operations.
- Added fail-closed rules for ambiguous target resolution, GraphQL `errors`, and rate-limit handling.

## Work Objectives
### Core Objective
Ship a project-local OpenCode skill that an agent can load and use immediately for Railway operational debugging, while keeping mutations narrowly scoped, explicit, and safe.

### Deliverables
- `.opencode/skills/crypto-news-debug/SKILL.md` with valid OpenCode frontmatter and complete usage instructions.
- `tests/test_opencode_skill_crypto_news_debug.py` enforcing the v1 contract.
- Explicit skill guidance for:
  - auth preflight with `RAILWAY_API_TOKEN`
  - project/environment/service/deployment discovery flow
  - read-only inspection workflows
  - app-service-only restart/redeploy workflows
  - raw read-only GraphQL fallback templates
  - GraphQL error and rate-limit handling

### Definition of Done (verifiable conditions with commands)
- `uv run pytest tests/test_opencode_skill_crypto_news_debug.py -q` exits 0.
- `uv run pytest tests/test_opencode_skill_crypto_news_debug.py -q` reports `6 passed`.
- `python - <<'PY'
from pathlib import Path
path = Path('.opencode/skills/crypto-news-debug/SKILL.md')
text = path.read_text(encoding='utf-8')
required = [
    'name: crypto-news-debug',
    'description:',
    'RAILWAY_API_TOKEN',
    'https://backboard.railway.com/graphql/v2',
    'project → environment → service → deployment',
    'restart',
    'redeploy',
]
missing = [item for item in required if item not in text]
assert not missing, missing
print('skill-contract-ok')
PY` prints `skill-contract-ok`.

### Must Have
- OpenCode skill file at `.opencode/skills/crypto-news-debug/SKILL.md`.
- Minimal valid frontmatter using only fields confirmed by official OpenCode docs (`name`, `description`, plus optional fields only if validated during execution).
- Explicit preflight step: if `RAILWAY_API_TOKEN` is missing, stop and instruct the agent to request/export it.
- Deterministic resolution flow: project → environment → service → deployment.
- Alias handling guidance matching repo deployment naming (`crypto-news-analysis` ↔ `analysis-service`, `crypto-news-ingestion` ↔ `ingestion`, legacy `crypto-news-api` alias).
- Read-only workflows for project/service/deployment/log inspection.
- Explicit restart/redeploy workflows for app services only, requiring resolved target scope before mutation.
- GraphQL response handling that treats HTTP 200 + `errors` as failure.
- Rate-limit guidance honoring `Retry-After` / backoff.
- Contract tests that fail if high-risk actions appear in the skill.

### Must NOT Have (guardrails, AI slop patterns, scope boundaries)
- No `.kiro/*` changes.
- No MCP server, custom helper script, CLI wrapper, or new dependency in v1.
- No arbitrary GraphQL mutation templates.
- No rollback, cancel, stop, delete/remove, variable edits, domain edits, volume operations, or database restart/redeploy guidance.
- No guessing when multiple projects/environments/services match; the skill must fail closed and present candidates.
- No unsupported assumptions about project-token headers; v1 should document Bearer-token workflow only unless execution-time validation proves otherwise.

## Verification Strategy
> ZERO HUMAN INTERVENTION — all verification is agent-executed.
- Test decision: **TDD** with `pytest` content-contract tests.
- QA policy: Every task includes agent-executed happy-path and edge-case scenarios.
- Evidence: `.sisyphus/evidence/task-{N}-{slug}.{ext}`

## Execution Strategy
### Parallel Execution Waves
> Target: 5-8 tasks per wave. <3 per wave (except final) = under-splitting.
> Extract shared dependencies as Wave-1 tasks for max parallelism.

Wave 1: contract-test foundation (`1-4`)
- test file scaffold and reusable readers
- positive contract tests
- negative/guardrail tests
- DB-safety and alias-resolution tests

Wave 2: skill authoring (`5-9`)
- skill scaffold/frontmatter
- auth preflight and target resolution
- read-only inspection workflows
- operational restart/redeploy workflows
- raw read-only GraphQL templates + failure handling

Wave 3: convergence (`10`)
- run targeted suite, tighten wording, and confirm green state

### Dependency Matrix (full, all tasks)
| Task | Depends On | Blocks |
|---|---|---|
| 1 | none | 2, 3, 4 |
| 2 | 1 | 5, 10 |
| 3 | 1 | 5, 10 |
| 4 | 1 | 5, 10 |
| 5 | 2, 3, 4 | 6, 7, 8, 9 |
| 6 | 5 | 10 |
| 7 | 5 | 10 |
| 8 | 5, 6 | 10 |
| 9 | 5, 6, 7, 8 | 10 |
| 10 | 2, 3, 4, 6, 7, 8, 9 | F1-F4 |

### Agent Dispatch Summary
| Wave | Task Count | Categories |
|---|---:|---|
| 1 | 4 | `quick`, `unspecified-low` |
| 2 | 5 | `writing`, `quick` |
| 3 | 1 | `quick` |
| Final Verification | 4 | `oracle`, `unspecified-high`, `deep` |

## TODOs
> Implementation + Test = ONE task. Never separate.
> EVERY task MUST have: Agent Profile + Parallelization + QA Scenarios.

- [x] 1. Add skill-contract test scaffold

  **What to do**: Create `tests/test_opencode_skill_crypto_news_debug.py` with shared helpers that load `.opencode/skills/crypto-news-debug/SKILL.md`, parse YAML frontmatter/body boundaries, and expose reusable assertions for exact-path existence and markdown content checks.
  **Must NOT do**: Do not add live Railway API calls, network access, snapshots, fixtures outside `tests/`, or a custom markdown parser dependency.

  **Recommended Agent Profile**:
  - Category: `quick` — Reason: single new pytest file with straightforward helpers.
  - Skills: `[]` — No extra skill required.
  - Omitted: `['writing']` — Test scaffold is code-first, not prose-first.

  **Parallelization**: Can Parallel: NO | Wave 1 | Blocks: 2, 3, 4 | Blocked By: none

  **References** (executor has NO interview context — be exhaustive):
  - Pattern: `tests/test_postgres_storage_path.py:54-112` — concise plain-pytest function style with inline assertions and monkeypatch usage.
  - Pattern: `tests/test_api_server.py:34-39` — helper-function pattern for shared test inputs.
  - API/Type: `AGENTS.md:13-45` — canonical `uv run pytest ...` command style for this repo.
  - External: `https://opencode.ai/docs/skills/` — official skill file path and frontmatter rules.

  **Acceptance Criteria** (agent-executable only):
  - [ ] `tests/test_opencode_skill_crypto_news_debug.py` exists and imports only stdlib + `pytest` if needed.
  - [ ] File contains reusable helpers for locating `SKILL.md`, splitting frontmatter, and reading the body text.
  - [ ] `uv run pytest tests/test_opencode_skill_crypto_news_debug.py -q` runs and reports collection without syntax/import errors once downstream tasks are complete.

  **QA Scenarios** (MANDATORY — task incomplete without these):
  ```
  Scenario: Happy path scaffold compiles
    Tool: Bash
    Steps: run `uv run pytest tests/test_opencode_skill_crypto_news_debug.py -q`
    Expected: pytest collects the file without SyntaxError/ImportError; failures, if any, are assertion failures from not-yet-authored content
    Evidence: .sisyphus/evidence/task-1-skill-contract-scaffold.txt

  Scenario: Edge case helper rejects missing skill file
    Tool: Bash
    Steps: add a dedicated test in the file that asserts the target path is `.opencode/skills/crypto-news-debug/SKILL.md` and fails if absent; run `uv run pytest tests/test_opencode_skill_crypto_news_debug.py::test_skill_file_exists_and_has_minimal_frontmatter -q`
    Expected: before task 5, the test fails specifically on missing file/path mismatch; after task 5, it passes
    Evidence: .sisyphus/evidence/task-1-skill-contract-scaffold-edge.txt
  ```

  **Commit**: NO | Message: `` | Files: `tests/test_opencode_skill_crypto_news_debug.py`

- [x] 2. Add positive contract tests for path, frontmatter, env, and endpoint

  **What to do**: Extend the test file with positive contract tests for exact skill location, minimal frontmatter (`name: crypto-news-debug`, non-empty `description`), presence of `RAILWAY_API_TOKEN`, and the Railway GraphQL endpoint string.
  **Must NOT do**: Do not assert speculative frontmatter fields (`allowed_tools`, `mcp_servers`, `compatibility`) unless validated during execution.

  **Recommended Agent Profile**:
  - Category: `quick` — Reason: targeted assertions in one test file.
  - Skills: `[]` — No extra skill required.
  - Omitted: `['deep']` — No architectural reasoning needed beyond locked requirements.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: 5, 10 | Blocked By: 1

  **References**:
  - Pattern: `AGENTS.md:99-113` — canonical skill name and required Railway debugging capabilities.
  - Pattern: `docs/RAILWAY_DEPLOYMENT.md:234-264` — authoritative endpoint and Bearer-token curl examples.
  - External: `https://opencode.ai/docs/skills/` — official minimal frontmatter requirements.
  - External: `https://docs.railway.com/integrations/api` — official Railway API endpoint/auth reference.

  **Acceptance Criteria**:
  - [ ] Tests named `test_skill_file_exists_and_has_minimal_frontmatter` and `test_skill_documents_required_env_and_endpoint` exist.
  - [ ] These tests assert exact path, `name`, non-empty `description`, `RAILWAY_API_TOKEN`, and `https://backboard.railway.com/graphql/v2`.
  - [ ] After tasks 5-9, both tests pass via targeted pytest commands.

  **QA Scenarios**:
  ```
  Scenario: Happy path contract passes
    Tool: Bash
    Steps: run `uv run pytest tests/test_opencode_skill_crypto_news_debug.py::test_skill_file_exists_and_has_minimal_frontmatter tests/test_opencode_skill_crypto_news_debug.py::test_skill_documents_required_env_and_endpoint -q`
    Expected: exit code 0 and output contains `2 passed`
    Evidence: .sisyphus/evidence/task-2-positive-contract.txt

  Scenario: Edge case missing env guidance is caught
    Tool: Bash
    Steps: rely on `test_skill_documents_required_env_and_endpoint` to assert `RAILWAY_API_TOKEN` guidance exists; run the same targeted pytest command
    Expected: if the skill omits env guidance or endpoint text, pytest fails with an assertion referencing the missing string
    Evidence: .sisyphus/evidence/task-2-positive-contract-edge.txt
  ```

  **Commit**: NO | Message: `` | Files: `tests/test_opencode_skill_crypto_news_debug.py`

- [x] 3. Add negative contract tests for non-goals and mutation scoping

  **What to do**: Add tests ensuring v1 forbids rollback, cancel, stop, remove/delete, variable edits, domain edits, and volume actions; also assert restart/redeploy instructions require resolved project/environment/service scope and mention GraphQL `errors` handling.
  **Must NOT do**: Do not allow substring-based loopholes such as documenting forbidden operations as “future ideas” in the active workflow sections.

  **Recommended Agent Profile**:
  - Category: `quick` — Reason: additional content assertions in the same file.
  - Skills: `[]` — No extra skill required.
  - Omitted: `['writing']` — Contract enforcement is still test-focused.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: 5, 10 | Blocked By: 1

  **References**:
  - Pattern: `AGENTS.md:101-113` — allowed user-visible capabilities already expected in-repo.
  - External: `https://docs.railway.com/integrations/api` — GraphQL response model; HTTP success does not guarantee operation success.
  - External: `https://opencode.ai/docs/skills/` — keep skill contract minimal and explicit.

  **Acceptance Criteria**:
  - [ ] Tests named `test_v1_forbids_high_risk_actions` and `test_mutations_require_explicit_scoping_and_error_handling` exist.
  - [ ] Tests fail if the skill text contains rollback/stop/cancel/remove/variable/domain/volume mutation guidance.
  - [ ] Tests require explicit scoping language and GraphQL `errors` handling language for restart/redeploy workflows.

  **QA Scenarios**:
  ```
  Scenario: Happy path guardrails pass
    Tool: Bash
    Steps: run `uv run pytest tests/test_opencode_skill_crypto_news_debug.py::test_v1_forbids_high_risk_actions tests/test_opencode_skill_crypto_news_debug.py::test_mutations_require_explicit_scoping_and_error_handling -q`
    Expected: exit code 0 and output contains `2 passed`
    Evidence: .sisyphus/evidence/task-3-guardrails.txt

  Scenario: Edge case arbitrary mutation wording is rejected
    Tool: Bash
    Steps: rely on `test_v1_forbids_high_risk_actions` to scan active workflow text for forbidden mutation terms; run the same targeted pytest command
    Expected: if forbidden mutation wording appears, pytest fails with a clear assertion naming the forbidden action
    Evidence: .sisyphus/evidence/task-3-guardrails-edge.txt
  ```

  **Commit**: NO | Message: `` | Files: `tests/test_opencode_skill_crypto_news_debug.py`

- [x] 4. Add database-safety, alias-resolution, and fallback-flow tests

  **What to do**: Add tests asserting PostgreSQL/managed DB services are inspection-only in v1; add assertions that the skill documents service alias mapping from repo deployment behavior and fail-closed handling for zero/multiple matches, empty logs, and rate-limit retry guidance.
  **Must NOT do**: Do not infer that database services support the same restart/redeploy semantics as app services.

  **Recommended Agent Profile**:
  - Category: `quick` — Reason: last contract expansion in one file.
  - Skills: `[]` — No extra skill required.
  - Omitted: `['deep']` — Safety rule is already decided.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: 5, 10 | Blocked By: 1

  **References**:
  - Pattern: `docker-entrypoint.sh:100-141` — source of service-name mapping and legacy alias behavior.
  - Pattern: `docs/RAILWAY_DEPLOYMENT.md:266-290` — analysis/ingestion mapping, public/private split, shared DB expectations.
  - External: `https://docs.railway.com/integrations/api` — rate-limit headers and query flow requirements.

  **Acceptance Criteria**:
  - [ ] Tests named `test_database_services_are_read_only_in_v1` and `test_skill_documents_resolution_flow_aliases_and_backoff` exist.
  - [ ] Tests assert DB services are inspection-only and that alias mapping includes `crypto-news-analysis`, `crypto-news-ingestion`, and legacy `crypto-news-api`.
  - [ ] Tests assert fail-closed wording for ambiguous matches, empty logs, and rate-limit/`Retry-After` handling.

  **QA Scenarios**:
  ```
  Scenario: Happy path DB safety contract passes
    Tool: Bash
    Steps: run `uv run pytest tests/test_opencode_skill_crypto_news_debug.py::test_database_services_are_read_only_in_v1 tests/test_opencode_skill_crypto_news_debug.py::test_skill_documents_resolution_flow_aliases_and_backoff -q`
    Expected: exit code 0 and output contains `2 passed`
    Evidence: .sisyphus/evidence/task-4-db-safety.txt

  Scenario: Edge case alias/backoff omission is caught
    Tool: Bash
    Steps: run the same targeted pytest command after authoring the skill
    Expected: pytest fails if alias text, ambiguity handling, empty-log handling, or `Retry-After` guidance is missing
    Evidence: .sisyphus/evidence/task-4-db-safety-edge.txt
  ```

  **Commit**: YES | Message: `test(skill): add crypto-news-debug contract tests` | Files: `tests/test_opencode_skill_crypto_news_debug.py`

- [x] 5. Scaffold the OpenCode skill file with minimal valid frontmatter

  **What to do**: Create `.opencode/skills/crypto-news-debug/SKILL.md` with only validated frontmatter fields (`name`, `description`) and stable section headings for auth preflight, target discovery, inspection workflows, app-service mutations, raw read-only GraphQL templates, and non-goals.
  **Must NOT do**: Do not add speculative frontmatter keys, reference `.kiro/*`, or create sidecar reference files unless tests require them.

  **Recommended Agent Profile**:
  - Category: `writing` — Reason: primary deliverable is structured markdown instructions.
  - Skills: `[]` — No extra skill required.
  - Omitted: `['quick']` — Needs careful contract alignment, not just file creation.

  **Parallelization**: Can Parallel: NO | Wave 2 | Blocks: 6, 7, 8, 9 | Blocked By: 2, 3, 4

  **References**:
  - Pattern: `AGENTS.md:99-113` — target skill name and expected capability set.
  - Pattern: `railway.toml:1-8` — confirms Railway deploy context for the repo.
  - External: `https://opencode.ai/docs/skills/` — official file path/frontmatter contract.

  **Acceptance Criteria**:
  - [ ] `.opencode/skills/crypto-news-debug/SKILL.md` exists.
  - [ ] Frontmatter contains exactly the validated minimum needed for OpenCode loading.
  - [ ] Body includes top-level sections required by tasks 6-9.

  **QA Scenarios**:
  ```
  Scenario: Happy path file contract passes
    Tool: Bash
    Steps: run `uv run pytest tests/test_opencode_skill_crypto_news_debug.py::test_skill_file_exists_and_has_minimal_frontmatter -q`
    Expected: exit code 0 and output contains `1 passed`
    Evidence: .sisyphus/evidence/task-5-skill-scaffold.txt

  Scenario: Edge case speculative frontmatter is avoided
    Tool: Bash
    Steps: run `python - <<'PY'
from pathlib import Path
text = Path('.opencode/skills/crypto-news-debug/SKILL.md').read_text(encoding='utf-8')
frontmatter = text.split('---', 2)[1]
forbidden = ['mcp_servers:', 'allowed_tools:', 'agent:', 'compatibility:']
extra = [x for x in forbidden if x in frontmatter]
assert not extra, extra
print('frontmatter-minimal')
PY`
    Expected: script prints `frontmatter-minimal`
    Evidence: .sisyphus/evidence/task-5-skill-scaffold-edge.txt
  ```

  **Commit**: NO | Message: `` | Files: `.opencode/skills/crypto-news-debug/SKILL.md`

- [x] 6. Author auth preflight and deterministic target-resolution workflow

  **What to do**: Document the exact preflight sequence: verify `RAILWAY_API_TOKEN` is set; use Bearer auth against `https://backboard.railway.com/graphql/v2`; discover project, then environment, then service, then deployment IDs; fail closed on zero/multiple matches; map service aliases using repo deployment names.
  **Must NOT do**: Do not document project-token headers, unsupported token variants, or guess IDs from names without a discovery step.

  **Recommended Agent Profile**:
  - Category: `writing` — Reason: precise operator instructions with repo-specific alias handling.
  - Skills: `[]` — No extra skill required.
  - Omitted: `['deep']` — Scope already fixed.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: 8, 9, 10 | Blocked By: 5

  **References**:
  - Pattern: `docs/RAILWAY_DEPLOYMENT.md:236-264` — canonical Bearer-token GraphQL curl structure.
  - Pattern: `docker-entrypoint.sh:100-141` — exact alias mapping between Railway service names and runtime modes.
  - External: `https://docs.railway.com/integrations/api` — official auth and resource-discovery guidance.

  **Acceptance Criteria**:
  - [ ] Skill text instructs the agent to stop if `RAILWAY_API_TOKEN` is unset.
  - [ ] Skill text documents the sequence `project → environment → service → deployment` verbatim.
  - [ ] Skill text documents ambiguity handling and alias mapping for `crypto-news-analysis`, `crypto-news-ingestion`, and `crypto-news-api`.

  **QA Scenarios**:
  ```
  Scenario: Happy path resolution contract passes
    Tool: Bash
    Steps: run `uv run pytest tests/test_opencode_skill_crypto_news_debug.py::test_skill_documents_resolution_flow_aliases_and_backoff -q`
    Expected: exit code 0 and output contains `1 passed`
    Evidence: .sisyphus/evidence/task-6-resolution-flow.txt

  Scenario: Edge case missing token guidance is rejected
    Tool: Bash
    Steps: run `uv run pytest tests/test_opencode_skill_crypto_news_debug.py::test_skill_documents_required_env_and_endpoint -q`
    Expected: pytest fails if `RAILWAY_API_TOKEN` preflight guidance is absent
    Evidence: .sisyphus/evidence/task-6-resolution-flow-edge.txt
  ```

  **Commit**: NO | Message: `` | Files: `.opencode/skills/crypto-news-debug/SKILL.md`

- [x] 7. Author read-only inspection workflows

  **What to do**: Write preset read-only workflows for listing projects, listing environments, resolving services, listing recent deployments, fetching build/runtime/http logs, and inspecting service state/log conditions for split deployments.
  **Must NOT do**: Do not include arbitrary query builders or workflow branches unrelated to this repo’s split deployment use case.

  **Recommended Agent Profile**:
  - Category: `writing` — Reason: workflow-heavy markdown with command examples.
  - Skills: `[]` — No extra skill required.
  - Omitted: `['quick']` — Needs careful instruction sequencing.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: 9, 10 | Blocked By: 5

  **References**:
  - Pattern: `AGENTS.md:101-113` — required capabilities: status, logs, environment-variable inspection, restart/redeploy.
  - Pattern: `docs/RAILWAY_DEPLOYMENT.md:238-264` — deployment list and deployment logs query examples.
  - Pattern: `docs/RAILWAY_DEPLOYMENT.md:266-290` — split-service expectations and shared database model.
  - External: `https://docs.railway.com/integrations/api` — official read-only query repertoire.

  **Acceptance Criteria**:
  - [ ] Skill includes named workflows for projects, environments, services, deployments, and logs.
  - [ ] Read-only commands use the official Railway GraphQL endpoint and Bearer auth format.
  - [ ] Workflow text clearly distinguishes app services from database services.

  **QA Scenarios**:
  ```
  Scenario: Happy path read-only workflows pass
    Tool: Bash
    Steps: run `uv run pytest tests/test_opencode_skill_crypto_news_debug.py::test_skill_documents_required_env_and_endpoint tests/test_opencode_skill_crypto_news_debug.py::test_skill_documents_resolution_flow_aliases_and_backoff -q`
    Expected: exit code 0 and output contains `2 passed`
    Evidence: .sisyphus/evidence/task-7-readonly-workflows.txt

  Scenario: Edge case empty-log handling is present
    Tool: Bash
    Steps: run `uv run pytest tests/test_opencode_skill_crypto_news_debug.py::test_skill_documents_resolution_flow_aliases_and_backoff -q`
    Expected: pytest fails if the skill does not tell the agent how to report empty logs without guessing root cause
    Evidence: .sisyphus/evidence/task-7-readonly-workflows-edge.txt
  ```

  **Commit**: NO | Message: `` | Files: `.opencode/skills/crypto-news-debug/SKILL.md`

- [x] 8. Author app-service-only restart and redeploy workflows

  **What to do**: Document restart and redeploy workflows that only apply after the agent has resolved the exact project/environment/service target and confirmed the target is an app service; require explicit user intent before mutation; require post-action verification via deployment status/log checks.
  **Must NOT do**: Do not document restart/redeploy for PostgreSQL or any managed DB service; do not allow mutation on ambiguous service matches.

  **Recommended Agent Profile**:
  - Category: `writing` — Reason: highest-risk prose in the skill, needs precision.
  - Skills: `[]` — No extra skill required.
  - Omitted: `['artistry']` — This is safety-critical, not creative.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: 9, 10 | Blocked By: 5, 6

  **References**:
  - Pattern: `AGENTS.md:101-113` — restart/redeploy are explicitly expected repo capabilities.
  - Pattern: `docker-entrypoint.sh:108-141` — authoritative distinction between app-service aliases and legacy mapping.
  - External: `https://docs.railway.com/integrations/api` — validate mutation names/examples before writing final commands.

  **Acceptance Criteria**:
  - [ ] Skill states restart/redeploy are available only for resolved app services.
  - [ ] Skill states DB services are inspection-only in v1.
  - [ ] Skill requires post-mutation verification via deployment/log inspection and GraphQL `errors` checking.

  **QA Scenarios**:
  ```
  Scenario: Happy path mutation guardrails pass
    Tool: Bash
    Steps: run `uv run pytest tests/test_opencode_skill_crypto_news_debug.py::test_mutations_require_explicit_scoping_and_error_handling tests/test_opencode_skill_crypto_news_debug.py::test_database_services_are_read_only_in_v1 -q`
    Expected: exit code 0 and output contains `2 passed`
    Evidence: .sisyphus/evidence/task-8-mutation-workflows.txt

  Scenario: Edge case DB mutation guidance is rejected
    Tool: Bash
    Steps: run the same targeted pytest command
    Expected: pytest fails if PostgreSQL/managed DB restart or redeploy guidance appears anywhere in the skill
    Evidence: .sisyphus/evidence/task-8-mutation-workflows-edge.txt
  ```

  **Commit**: NO | Message: `` | Files: `.opencode/skills/crypto-news-debug/SKILL.md`

- [x] 9. Add raw read-only GraphQL fallback templates and failure-handling guidance

  **What to do**: Add a small, fixed set of raw **read-only** GraphQL templates for project listing, service/deployment lookup, and log retrieval; document handling for GraphQL `errors`, null payloads, and Railway rate limits (`X-RateLimit-*`, `Retry-After`); keep write actions available only through the preset workflows from task 8.
  **Must NOT do**: Do not expose raw write templates, generic arbitrary query instructions, or freeform mutation examples.

  **Recommended Agent Profile**:
  - Category: `writing` — Reason: command-template curation with guardrails.
  - Skills: `[]` — No extra skill required.
  - Omitted: `['quick']` — Needs careful limit-setting and wording.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: 10 | Blocked By: 5, 6, 7, 8

  **References**:
  - Pattern: `docs/RAILWAY_DEPLOYMENT.md:238-264` — in-repo raw GraphQL query examples.
  - External: `https://docs.railway.com/integrations/api` — rate-limit headers, query shapes, and response caveats.
  - External: `https://opencode.ai/docs/skills/` — keep fallback content within the skill markdown itself.

  **Acceptance Criteria**:
  - [ ] Skill contains only read-only fallback GraphQL templates.
  - [ ] Skill documents HTTP 200 + `errors` as a failure condition.
  - [ ] Skill documents backoff/`Retry-After` handling and instructs the agent not to hammer the API.

  **QA Scenarios**:
  ```
  Scenario: Happy path fallback templates pass
    Tool: Bash
    Steps: run `uv run pytest tests/test_opencode_skill_crypto_news_debug.py::test_v1_forbids_high_risk_actions tests/test_opencode_skill_crypto_news_debug.py::test_skill_documents_resolution_flow_aliases_and_backoff -q`
    Expected: exit code 0 and output contains `2 passed`
    Evidence: .sisyphus/evidence/task-9-graphql-fallbacks.txt

  Scenario: Edge case raw write template is rejected
    Tool: Bash
    Steps: run `uv run pytest tests/test_opencode_skill_crypto_news_debug.py::test_v1_forbids_high_risk_actions -q`
    Expected: pytest fails if a raw mutation template or arbitrary write guidance appears in the skill
    Evidence: .sisyphus/evidence/task-9-graphql-fallbacks-edge.txt
  ```

  **Commit**: YES | Message: `feat(skill): add project-local crypto-news-debug OpenCode skill` | Files: `.opencode/skills/crypto-news-debug/SKILL.md`

- [x] 10. Run the targeted suite and tighten wording until fully green

  **What to do**: Run the full targeted contract suite, inspect any failures, and refine only the skill/test wording until all six tests pass. Confirm the final skill remains limited to v1 scope.
  **Must NOT do**: Do not widen scope just to make a test pass; fix wording/structure instead.

  **Recommended Agent Profile**:
  - Category: `quick` — Reason: short red/green polish loop.
  - Skills: `[]` — No extra skill required.
  - Omitted: `['deep']` — By this point, decisions are already fixed.

  **Parallelization**: Can Parallel: NO | Wave 3 | Blocks: F1, F2, F3, F4 | Blocked By: 2, 3, 4, 6, 7, 8, 9

  **References**:
  - Pattern: `AGENTS.md:19-44` — canonical targeted/full pytest command style.
  - Test: `tests/test_opencode_skill_crypto_news_debug.py` — newly added contract suite is the source of truth.

  **Acceptance Criteria**:
  - [ ] `uv run pytest tests/test_opencode_skill_crypto_news_debug.py -q` exits 0.
  - [ ] Output contains `6 passed`.
  - [ ] No forbidden mutation guidance appears in `.opencode/skills/crypto-news-debug/SKILL.md`.

  **QA Scenarios**:
  ```
  Scenario: Happy path full suite passes
    Tool: Bash
    Steps: run `uv run pytest tests/test_opencode_skill_crypto_news_debug.py -q`
    Expected: exit code 0 and output contains `6 passed`
    Evidence: .sisyphus/evidence/task-10-full-suite.txt

  Scenario: Edge case forbidden-scope regression is caught
    Tool: Bash
    Steps: run `python - <<'PY'
from pathlib import Path
text = Path('.opencode/skills/crypto-news-debug/SKILL.md').read_text(encoding='utf-8').lower()
forbidden = ['rollback', 'cancel deployment', 'delete service', 'remove service', 'variable update', 'domain create', 'volume create']
hits = [item for item in forbidden if item in text]
assert not hits, hits
print('scope-clean')
PY`
    Expected: script prints `scope-clean`
    Evidence: .sisyphus/evidence/task-10-full-suite-edge.txt
  ```

  **Commit**: NO | Message: `` | Files: `tests/test_opencode_skill_crypto_news_debug.py`, `.opencode/skills/crypto-news-debug/SKILL.md`

## Final Verification Wave (MANDATORY — after ALL implementation tasks)
> 4 review agents run in PARALLEL. ALL must APPROVE. Present consolidated results to user and get explicit "okay" before completing.
> **Do NOT auto-proceed after verification. Wait for user's explicit approval before marking work complete.**
> **Never mark F1-F4 as checked before getting user's okay.** Rejection or user feedback -> fix -> re-run -> present again -> wait for okay.
- [x] F1. Plan Compliance Audit — oracle
- [x] F2. Code Quality Review — unspecified-high
- [x] F3. Real Manual QA — unspecified-high (+ playwright if UI)
- [x] F4. Scope Fidelity Check — deep

## Commit Strategy
- Commit 1: `test(skill): add crypto-news-debug contract tests`
  - Files: `tests/test_opencode_skill_crypto_news_debug.py`
  - Rule: leave the repo in a deliberate red state only if the next task is immediately implementing the skill in the same working session.
- Commit 2: `feat(skill): add project-local crypto-news-debug OpenCode skill`
  - Files: `.opencode/skills/crypto-news-debug/SKILL.md`
  - Rule: only commit after the six-test targeted suite is green.

## Success Criteria
- Agents can load `crypto-news-debug` from `.opencode/skills/crypto-news-debug/SKILL.md`.
- The skill instructs agents to use `RAILWAY_API_TOKEN` with Bearer auth against Railway GraphQL.
- The skill supports deterministic discovery of project/environment/service/deployment targets.
- The skill supports read-only inspection for split deployments and keeps PostgreSQL inspection-only.
- The skill supports restart/redeploy only for explicitly resolved app services.
- The targeted pytest contract suite passes and prevents future scope drift.
