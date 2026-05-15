# Topic-Only Intelligence Refactor

## TL;DR
> **Summary**: Replace the existing `slang/channel` + canonical-entry intelligence flow with a topic-only research system. Raw crawling remains in ingestion; confirmed topics drive scheduled LLM research; findings are stored, queried, merged, and archived by topic.
> **Deliverables**:
> - Topic prompt draft/revise/manual-edit/confirm workflow through HTTP API and Telegram.
> - Topic-only schema, repository, domain models, prompt templates, and structured LLM outputs.
> - Ingestion-only scheduled topic research using raw messages since per-topic checkpoint.
> - Topic detail and merge preview/accept workflows with stale-preview protection.
> - Removal of active `/intelligence/entries*` API routes and `/intel_*` Telegram commands.
> - TDD coverage for schema, services, API, Telegram, scheduler, retention, and old-surface removal.
> **Effort**: XL
> **Parallel**: YES - 8 waves
> **Critical Path**: Task 1 → Task 2 → Task 4 → Task 6 → Task 8 → Task 10 → Task 15 → Final Verification; plus user-surface cleanup path Task 7/9 → Task 11/12 → Task 13/14 → Task 15.

> **Single Plan Mandate**: This file is the single active plan for the topic-only intelligence refactor. Any other files under `.sisyphus/plans/` are unrelated historical/parallel plans and are not part of this work.

## Context

### Original Request
用户想大幅重构情报收集逻辑：取消 `slang/channel` 概念，只保留 `topic`。用户创建研究主题后，系统用预设提示词模板让 LLM 生成持续研究提示词，用户可修改或确认，确认后存入数据库。情报 pipeline 持续抓取原始聊天内容并入库，每天定期把主题提示词和上次运行以来的原始消息交给 LLM，按主题输出研究成果并存库。用户查看主题详情时返回主题提示词与全部成果，并可一键用 LLM 合并成果；满意后保存合并结果并隐藏旧成果。

### Interview Summary
- Entry points: HTTP API + Telegram.
- Old derived `slang/channel/canonical entry` data: discard/no migration; preserve raw messages.
- Old `/intelligence/entries*` API routes and `/intel_*` Telegram commands: delete from active product surface; no compatibility aliases.
- Topic research LLM output: structured JSON/Pydantic.
- Topic finding merge cleanup: soft archive/hide superseded findings with replacement metadata.
- Recurring topic research: private `ingestion` service only.
- Raw message retention: configurable, default 180 days.
- Topic prompt workflow: LLM-generated draft, LLM revision with feedback, direct manual replacement, confirm to activate.
- Test strategy: TDD.
- Defaults: global topics for all authorized users; lifecycle `draft` / `active` / `paused` / `archived`; only `active` topics are researched; prompt edits create versions; per-topic checkpoints use `collected_at` inclusion cursor and `published_at` ordering.

### Metis Review (gaps addressed)
- Added topic lifecycle and ownership defaults.
- Added per-topic checkpoint semantics and late-arriving message handling.
- Added persisted merge preview requirements: source finding IDs, expiry, stale-preview rejection.
- Added evidence lineage requirements: raw IDs, source refs, durable snippets.
- Added route/command naming decisions: keep `/intelligence/topics*`, keep/extend `/topic_*`, delete entries/intel surfaces.
- Added guardrails against concept leakage from raw source metadata into product domain.

## Work Objectives

### Core Objective
Make `topic` the only first-class intelligence object while preserving raw message ingestion and replacing channel/slang extraction with scheduled topic research and topic finding management.

### Deliverables
- New topic prompt and finding domain models.
- New database migrations and SQLite/Postgres repository support.
- New prompt templates under `prompts/` for prompt generation, topic research, and finding merge.
- Scheduled topic research service invoked only from ingestion mode.
- HTTP API topic workflow endpoints under `/intelligence/topics*`.
- Telegram topic workflow commands under `/topic_*`.
- Removal of old active entry/intel surfaces.
- TDD tests and full local verification commands.

### Definition of Done (verifiable conditions with commands)
- `uv run pytest tests/test_topic_prompt_workflow.py -v` passes.
- `uv run pytest tests/test_topic_research_scheduler.py -v` passes.
- `uv run pytest tests/test_topic_findings_api.py -v` passes.
- `uv run pytest tests/test_topic_findings_telegram.py -v` passes.
- `uv run pytest tests/test_raw_message_retention.py -v` passes.
- `uv run pytest tests/test_intelligence_models.py tests/test_intelligence_repositories.py -v` passes after replacing old entry expectations.
- `uv run pytest tests/ -v` passes.
- `uv run mypy crypto_news_analyzer/` passes.
- `uv run flake8 crypto_news_analyzer/` passes.

### Must Have
- `slang`, `channel`, `EntryType`, and canonical entries are not first-class intelligence concepts in new models, prompts, API responses, or Telegram output.
- Raw source/channel/thread metadata may remain only as raw message metadata for grouping/citation.
- `raw_intelligence_items.topic_id` is not reused as intelligence topic FK; use a new explicit name such as `intelligence_topic_id` where linkage is required.
- Scheduled topic research runs only from `ingestion` mode.
- Failed topic research does not advance checkpoints.
- Merge acceptance archives exactly the source findings bound to the accepted preview.

### Must NOT Have (guardrails, AI slop patterns, scope boundaries)
- Must not add dashboards, ranking systems, semantic search, embeddings, or extra taxonomy concepts.
- Must not add compatibility aliases for deleted `/intel_*` commands or `/intelligence/entries*` routes.
- Must not call real LLM, real Telegram, Railway, or production DB in automated tests.
- Must not hard-delete raw messages during this refactor.
- Must not expose source `channel` as a product/domain concept; only display it as source metadata/citation when necessary.

## Verification Strategy
> ZERO HUMAN INTERVENTION - all verification is agent-executed.
- Test decision: TDD with pytest, FastAPI `TestClient`, Telegram mocked updates/callbacks, SQLite repositories, mocked LLM structured outputs, and optional existing real Postgres marker tests.
- QA policy: Every task has agent-executed scenarios.
- Evidence: `.sisyphus/evidence/task-{N}-{slug}.{ext}`

## Execution Strategy

### Parallel Execution Waves
> This refactor has deliberate serial gates; waves are dependency-correct rather than artificially widened.
> Run tasks within the same wave in parallel only when all listed blockers are complete.

Wave 1: Task 1 — TDD contract and reference sweep foundation.
Wave 2: Tasks 2, 3, 5 — schema/domain, prompts, and retention config in parallel after contracts exist.
Wave 3: Task 4 — repository contracts after schema exists.
Wave 4: Task 6 — old extractor/merge unwiring after repository/domain contracts exist.
Wave 5: Tasks 7, 8, 9 — prompt workflow, scheduled research, and merge workflow in parallel after topic-only services exist.
Wave 6: Tasks 10, 11, 12 — runtime wiring, HTTP API, and Telegram UX in parallel after workflows exist.
Wave 7: Tasks 13, 14 — old surface cleanup and docs/config cleanup in parallel after user surfaces exist.
Wave 8: Task 15 — final validation after all implementation tasks.

### Dependency Matrix (full, all tasks)
- Task 1 blocks Tasks 2, 3, 5.
- Task 2 blocks Task 4.
- Tasks 2 and 4 block Task 6.
- Tasks 3, 4, and 6 block Tasks 7, 8, 9.
- Task 8 blocks Task 10.
- Tasks 7, 8, and 9 block Tasks 11, 12.
- Tasks 11 and 12 block Task 13.
- Tasks 5, 11, and 12 block Task 14.
- Tasks 10, 13, and 14 block Task 15.

### Agent Dispatch Summary (wave → task count → categories)
- Wave 1 → 1 task → deep.
- Wave 2 → 3 tasks → deep, writing, unspecified-high.
- Wave 3 → 1 task → deep.
- Wave 4 → 1 task → deep.
- Wave 5 → 3 tasks → unspecified-high, deep.
- Wave 6 → 3 tasks → unspecified-high.
- Wave 7 → 2 tasks → unspecified-high, writing.
- Wave 8 → 1 task → unspecified-high.

## TODOs
> Implementation + Test = ONE task. Never separate.
> EVERY task MUST have: Agent Profile + Parallelization + QA Scenarios.

- [ ] 1. Establish topic-only TDD contract and reference sweep

  **What to do**: Before implementation, add/adjust failing tests that define the new domain vocabulary and deleted old surface. Use LSP/AST search to list references to `EntryType`, `SlangObservation`, `ChannelObservation`, `CanonicalIntelligenceEntry`, `/intel_`, and `/intelligence/entries`. Create a short internal checklist in test comments or fixtures for required replacements: topic prompts, topic findings, merge previews, per-topic checkpoints, and raw retention.
  **Must NOT do**: Do not implement production behavior before the tests define expected behavior. Do not preserve compatibility aliases.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: broad cross-cutting dependency map and TDD sequencing.
  - Skills: [] - no specialized external skill required.
  - Omitted: [`git-master`] - no commit requested inside task.

  **Parallelization**: Can Parallel: NO | Wave 1 | Blocks: [2,3,5] | Blocked By: []

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `crypto_news_analyzer/domain/models.py:61-63` - `EntryType` enum to eliminate from active topic-only domain.
  - Pattern: `crypto_news_analyzer/analyzers/intelligence_extractor.py:51-102` - old separate channel/slang output contract to replace.
  - Pattern: `crypto_news_analyzer/api_server.py:1540-1986` - current `/intelligence/entries*` and topic routes.
  - Pattern: `crypto_news_analyzer/reporters/telegram_command_handler.py:197-238` - current `/intel_*` and `/topic_*` registration area.
  - Test: `tests/test_intelligence_extraction.py` - LLM fake-client pattern and old extraction tests.
  - Test: `tests/test_intelligence_api.py` - FastAPI in-memory repository and auth test pattern.
  - Test: `tests/test_intelligence_telegram_commands.py` - Telegram command/callback test pattern.

  **Acceptance Criteria** (agent-executable only):
  **Acceptance Verification Command**: `uv run pytest tests/test_topic_prompt_workflow.py tests/test_topic_research_scheduler.py tests/test_topic_findings_api.py tests/test_topic_findings_telegram.py --collect-only -q` | Evidence: `.sisyphus/evidence/task-1-topic-contract-collect.txt`
  - [ ] `uv run pytest tests/test_topic_prompt_workflow.py -v` exists and initially exercises draft/revise/manual-confirm behavior with mocked LLM.
  - [ ] `uv run pytest tests/test_topic_research_scheduler.py -v` exists and exercises active-only scheduling, checkpoint behavior, malformed LLM JSON, and no-message runs.
  - [ ] `uv run pytest tests/test_topic_findings_api.py -v` exists and exercises API auth, topic detail, merge preview, merge accept, and stale preview rejection.
  - [ ] `uv run pytest tests/test_topic_findings_telegram.py -v` exists and exercises `/topic_*` command flows and verifies `/intel_*` commands are not registered.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Contract tests are discoverable
    Tool: Bash
    Steps: Run `uv run pytest tests/test_topic_prompt_workflow.py tests/test_topic_research_scheduler.py tests/test_topic_findings_api.py tests/test_topic_findings_telegram.py --collect-only -q`
    Expected: Pytest collects the new topic-only tests without import errors.
    Evidence: .sisyphus/evidence/task-1-topic-contract-collect.txt

  Scenario: Old concept references are tracked
    Tool: Bash
    Steps: Run `uv run python - <<'PY'\nfrom pathlib import Path\nterms=['EntryType','SlangObservation','ChannelObservation','/intel_','/intelligence/entries']\nfor t in terms:\n print(t, sum(t in p.read_text(errors='ignore') for p in Path('.').rglob('*.py') if '.venv' not in p.parts))\nPY`
    Expected: Command prints counts for all tracked old concepts so later tasks can reduce/remove active references.
    Evidence: .sisyphus/evidence/task-1-old-reference-counts.txt
  ```

  **Commit**: NO | Message: `test(intelligence): define topic-only refactor contracts` | Files: [tests/test_topic_prompt_workflow.py, tests/test_topic_research_scheduler.py, tests/test_topic_findings_api.py, tests/test_topic_findings_telegram.py]

- [ ] 2. Add topic-only schema, migrations, and domain models

  **What to do**: Introduce topic prompt versions, topic findings, topic research run/checkpoint records, topic merge previews, and finding archive metadata. Preserve `raw_intelligence_items` and do not reuse its `topic_id`; use explicit names such as `intelligence_topic_id`, `prompt_version_id`, `source_finding_ids`, and `superseded_by_finding_id`. Add PostgreSQL migration and SQLite DDL parity. Update dataclasses/Pydantic/domain models to represent `draft/active/paused/archived` topic lifecycle, structured finding payloads, citations, and merge preview state.
  **Must NOT do**: Do not migrate old canonical entries into topics/findings. Do not make `channel` or `slang` model fields except as raw source metadata/citation text.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: schema and domain model replacement with migration parity.
  - Skills: [] - no specialized skill required.
  - Omitted: [`railway-docs`] - no Railway feature work.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: [4] | Blocked By: [1]

  **References**:
  - Pattern: `crypto_news_analyzer/domain/models.py:1004-1081` - existing `IntelligenceTopic` model to extend/rework.
  - Pattern: `crypto_news_analyzer/domain/models.py:1084-1154` - existing `IntelligenceTopicRunLog` to replace/extend for research runs.
  - Pattern: `migrations/postgresql/008_intelligence_topics.sql:1-18` - current topic table baseline.
  - Pattern: `migrations/postgresql/003_intelligence_schema.sql:3-20` - preserve `raw_intelligence_items` table.
  - Pattern: `crypto_news_analyzer/storage/data_manager.py:411-801` - SQLite DDL parity location.
  - Test: `tests/test_intelligence_models.py` - model validation pattern.
  - Test: `tests/test_intelligence_repositories.py` - SQLite repository contract pattern.

  **Acceptance Criteria**:
  **Acceptance Verification Command**: `uv run pytest tests/test_intelligence_models.py tests/test_intelligence_repositories.py -k 'topic or finding or merge_preview or prompt_version or raw_topic_id_not_intelligence_fk' -v` | Evidence: `.sisyphus/evidence/task-2-schema-sqlite.txt`
  - [ ] New migration creates topic prompt/finding/research-run/merge-preview storage with explicit intelligence topic FKs.
  - [ ] SQLite initialization creates equivalent tables/columns.
  - [ ] Model tests validate lifecycle states, prompt versions, finding citations, archive metadata, and merge preview stale/expiry fields.
  - [ ] Tests assert `raw_intelligence_items.topic_id` is not used as intelligence topic FK.

  **QA Scenarios**:
  ```
  Scenario: SQLite schema supports topic-only objects
    Tool: Bash
    Steps: Run `uv run pytest tests/test_intelligence_models.py tests/test_intelligence_repositories.py -k 'topic or finding or merge_preview or prompt_version' -v`
    Expected: Topic lifecycle, prompt version, finding, and preview tests pass.
    Evidence: .sisyphus/evidence/task-2-schema-sqlite.txt

  Scenario: Raw topic_id semantic ambiguity is prevented
    Tool: Bash
    Steps: Run `uv run pytest tests/test_intelligence_repositories.py -k 'raw_topic_id_not_intelligence_fk' -v`
    Expected: Test passes and fails if code attempts to use raw `topic_id` for intelligence linkage.
    Evidence: .sisyphus/evidence/task-2-topic-id-guard.txt
  ```

  **Commit**: NO | Message: `feat(intelligence): add topic-only persistence models` | Files: [crypto_news_analyzer/domain/models.py, crypto_news_analyzer/storage/data_manager.py, crypto_news_analyzer/storage/repositories.py, crypto_news_analyzer/domain/repositories.py, migrations/postgresql/*.sql, tests/test_intelligence_models.py, tests/test_intelligence_repositories.py]

- [ ] 3. Replace prompt templates for topic prompt generation, research, and merge

  **What to do**: Add prompt files under `prompts/` for: topic prompt generation from user theme, topic prompt revision from user feedback, scheduled topic research over raw messages, and finding merge. Each prompt must demand structured JSON matching Pydantic schemas and require citations/snippets for each finding. Remove or stop using the old `intelligence_extraction_prompt.md` channel/slang extraction prompt from active flow.
  **Must NOT do**: Do not mention `slang` or `channel` as intelligence categories. Source/channel metadata may only appear as raw source context.

  **Recommended Agent Profile**:
  - Category: `writing` - Reason: prompt artifacts and schema-aligned instructions.
  - Skills: [`llm-instructor`] - useful if structured-output integration uses instructor/Pydantic patterns.
  - Omitted: [`grok-api-reference`] - no provider-specific API change required.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: [7,8,9] | Blocked By: [1]

  **References**:
  - Pattern: `prompts/intelligence_extraction_prompt.md` - old prompt to remove from active topic research flow.
  - Pattern: `prompts/topic_enrichment_prompt.md` - current topic evidence enrichment style.
  - Pattern: `prompts/topic_convergence_prompt.md` - current merge/convergence prompt style.
  - Pattern: `crypto_news_analyzer/analyzers/prompt_manager.py` - prompt loading conventions.
  - Test: `tests/test_intelligence_extraction.py` - prompt payload isolation and fake LLM pattern.

  **Acceptance Criteria**:
  **Acceptance Verification Command**: `uv run pytest tests/test_topic_prompt_workflow.py -k 'prompt_template or schema or new_prompts_exclude_old_category_language' -v` | Evidence: `.sisyphus/evidence/task-3-prompts-schema.txt`
  - [ ] Prompt files exist for generate, revise, research, and merge workflows.
  - [ ] Unit tests assert prompts include schema/version instructions and exclude channel/slang category instructions.
  - [ ] Research prompt requires per-topic output and evidence citations.
  - [ ] Merge prompt requires source finding IDs and merged output suitable for persisted structured finding.

  **QA Scenarios**:
  ```
  Scenario: Prompt files are schema-aligned
    Tool: Bash
    Steps: Run `uv run pytest tests/test_topic_prompt_workflow.py -k 'prompt_template or schema' -v`
    Expected: Tests pass and verify required JSON keys/version markers.
    Evidence: .sisyphus/evidence/task-3-prompts-schema.txt

  Scenario: Old category language is absent from new prompts
    Tool: Bash
    Steps: Run `uv run pytest tests/test_topic_prompt_workflow.py -k 'new_prompts_exclude_old_category_language' -v`
    Expected: No forbidden category instructions appear in new active prompt templates.
    Evidence: .sisyphus/evidence/task-3-prompts-no-old-concepts.txt
  ```

  **Commit**: NO | Message: `feat(prompts): add topic research prompt templates` | Files: [prompts/topic_prompt_generation_prompt.md, prompts/topic_prompt_revision_prompt.md, prompts/topic_research_prompt.md, prompts/topic_findings_merge_prompt.md, tests/test_topic_prompt_workflow.py]

- [ ] 4. Implement repository contracts for prompt versions, findings, runs, and merge previews

  **What to do**: Extend `IntelligenceRepository` with methods for topic prompt drafts/versions, topic findings listing/creation/archive, per-topic run logs/checkpoints, merge preview create/get/accept/reject, and raw message retrieval since cursor. Implement in SQLite/Postgres repositories with uniqueness/idempotency constraints: processed raw `(raw_item_id, intelligence_topic_id, prompt_version, schema_version)` and merge preview source finding IDs.
  **Must NOT do**: Do not expose old canonical entry repository methods to new services. Do not advance checkpoint on failed run.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: repository contract changes affect API, scheduler, tests, and DB parity.
  - Skills: [] - no specialized skill required.
  - Omitted: [`playwright`] - no browser/UI task.

  **Parallelization**: Can Parallel: NO | Wave 3 | Blocks: [6] | Blocked By: [2]

  **References**:
  - Pattern: `crypto_news_analyzer/domain/repositories.py:418-704` - current `IntelligenceRepository` interface organization.
  - Pattern: `crypto_news_analyzer/storage/repositories.py` - SQLite/Postgres repository implementations.
  - Pattern: `tests/test_intelligence_repositories.py` - repository contract coverage style.
  - Pattern: `tests/integration/test_intelligence_pgvector.py` - optional real Postgres marker/safety style.

  **Acceptance Criteria**:
  **Acceptance Verification Command**: `uv run pytest tests/test_intelligence_repositories.py -k 'prompt_version or finding or checkpoint or topic_run or merge_preview' -v` | Evidence: `.sisyphus/evidence/task-4-checkpoint-repository.txt`
  - [ ] Repository tests pass for prompt version creation, active prompt lookup, finding create/list/archive, run success/failure checkpoint behavior, raw retrieval by `collected_at`, and merge preview stale rejection.
  - [ ] Duplicate processing attempts are idempotent and do not create duplicate findings/evidence links.
  - [ ] Failed research run records error details and leaves previous checkpoint unchanged.

  **QA Scenarios**:
  ```
  Scenario: Per-topic checkpoint is failure-safe
    Tool: Bash
    Steps: Run `uv run pytest tests/test_intelligence_repositories.py -k 'checkpoint or topic_run' -v`
    Expected: Successful run advances checkpoint; failed run does not.
    Evidence: .sisyphus/evidence/task-4-checkpoint-repository.txt

  Scenario: Merge preview rejects stale active finding set
    Tool: Bash
    Steps: Run `uv run pytest tests/test_intelligence_repositories.py -k 'merge_preview' -v`
    Expected: Accepting preview after active findings changed fails deterministically.
    Evidence: .sisyphus/evidence/task-4-merge-preview-repository.txt
  ```

  **Commit**: NO | Message: `feat(intelligence): add topic finding repository contracts` | Files: [crypto_news_analyzer/domain/repositories.py, crypto_news_analyzer/storage/repositories.py, tests/test_intelligence_repositories.py]

- [ ] 5. Add raw message retention configuration and tests

  **What to do**: Change raw text retention from the current intelligence TTL behavior to a configurable default of 180 days. Ensure referenced raw messages remain intelligible through persisted finding snippets/source refs even after retention cleanup. Update config parsing/defaults and tests for retention behavior.
  **Must NOT do**: Do not hard-delete raw messages as part of migration. Do not reduce retention below 180 days by default.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: config, lifecycle cleanup, and tests across storage/pipeline.
  - Skills: [] - no specialized skill required.
  - Omitted: [`railway-docs`] - no Railway runtime behavior change.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: [14] | Blocked By: [1]

  **References**:
  - Pattern: `crypto_news_analyzer/intelligence/pipeline.py:351-366` - current TTL cleanup path.
  - Pattern: `config.jsonc:38-72` - existing `intelligence_collection.collection.ttl_days` config.
  - Pattern: `tests/test_intelligence_ttl.py` - current TTL tests.
  - Pattern: `tests/test_intelligence_repositories.py:146-173` - raw item TTL cleanup test area.

  **Acceptance Criteria**:
  **Acceptance Verification Command**: `uv run pytest tests/test_raw_message_retention.py tests/test_intelligence_ttl.py -v` | Evidence: `.sisyphus/evidence/task-5-retention-default.txt`
  - [ ] Default raw retention is 180 days when not configured.
  - [ ] Retention cleanup uses the configured value and never removes active finding citation snippets/source refs.
  - [ ] Existing TTL tests are updated to topic-only terminology.
  - [ ] Config docs/comments do not recommend legacy entry extraction behavior.

  **QA Scenarios**:
  ```
  Scenario: Default retention is 180 days
    Tool: Bash
    Steps: Run `uv run pytest tests/test_raw_message_retention.py -k 'default_180_days' -v`
    Expected: Test passes and confirms default retention value.
    Evidence: .sisyphus/evidence/task-5-retention-default.txt

  Scenario: Finding evidence survives raw cleanup
    Tool: Bash
    Steps: Run `uv run pytest tests/test_raw_message_retention.py -k 'finding_snippet_survives_cleanup' -v`
    Expected: Cleanup may purge eligible raw text but persisted finding retains source refs/snippets.
    Evidence: .sisyphus/evidence/task-5-retention-evidence.txt
  ```

  **Commit**: NO | Message: `feat(intelligence): configure raw message retention` | Files: [crypto_news_analyzer/config/manager.py, crypto_news_analyzer/models.py, crypto_news_analyzer/intelligence/pipeline.py, config.jsonc, tests/test_raw_message_retention.py, tests/test_intelligence_ttl.py]

- [ ] 6. Replace old extractor/merge entry pipeline with topic-only service interfaces

  **What to do**: Remove active use of `ChannelObservation`, `SlangObservation`, `ExtractionObservation`, `CanonicalIntelligenceEntry`, `IntelligenceMergeEngine`, and old entry embedding/linking from topic research flow. Add service interfaces/classes for topic prompt generation/revision and structured topic research output parsing. Keep old modules only if needed temporarily for tests/import compatibility, but they must not be wired into runtime.
  **Must NOT do**: Do not add new channel/slang normalization logic. Do not keep old canonicalization in `run_intelligence_collection_once()`.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: replaces core pipeline abstraction and removes old concept wiring.
  - Skills: [`llm-instructor`] - helpful for structured LLM/Pydantic output contracts.
  - Omitted: [`bird-commands-reference`] - no X/Twitter CLI operation.

  **Parallelization**: Can Parallel: NO | Wave 4 | Blocks: [7,8,9] | Blocked By: [2,4]

  **References**:
  - Pattern: `crypto_news_analyzer/analyzers/intelligence_extractor.py:51-102` - old output models to remove/replace.
  - Pattern: `crypto_news_analyzer/intelligence/merge.py:133-205` - old entry-type branching merge logic to unwire/delete.
  - Pattern: `crypto_news_analyzer/intelligence/pipeline.py:49-104` - current crawl/extract/merge/embed/topic flow.
  - Pattern: `crypto_news_analyzer/intelligence/topics.py:39-105` - current entry-to-topic service dependency.
  - Test: `tests/test_intelligence_extraction.py` - replace old channel/slang extraction tests.
  - Test: `tests/test_intelligence_merge.py` - remove or replace old merge tests with topic finding tests.

  **Acceptance Criteria**:
  **Acceptance Verification Command**: `uv run pytest tests/test_topic_research_scheduler.py -k 'no_entry_extractor_dependency or malformed_llm_json or secret_filtering' -v` | Evidence: `.sisyphus/evidence/task-6-no-old-extractor.txt`
  - [ ] Runtime topic research flow has no dependency on `EntryType`, `ChannelObservation`, `SlangObservation`, or `IntelligenceMergeEngine`.
  - [ ] Old extraction/merge tests are replaced by topic prompt/research parsing tests.
  - [ ] Invalid LLM JSON returns validation error, records failed run context, and does not persist partial findings.
  - [ ] Secret filtering/guardrails from old extraction tests remain covered for topic research output/logging.

  **QA Scenarios**:
  ```
  Scenario: Old extractor is not wired into topic research
    Tool: Bash
    Steps: Run `uv run pytest tests/test_topic_research_scheduler.py -k 'no_entry_extractor_dependency' -v`
    Expected: Test passes and proves scheduled topic research uses topic-only service/parser.
    Evidence: .sisyphus/evidence/task-6-no-old-extractor.txt

  Scenario: Malformed structured LLM output is safe
    Tool: Bash
    Steps: Run `uv run pytest tests/test_topic_research_scheduler.py -k 'malformed_llm_json' -v`
    Expected: Failed run is logged, no findings are saved, checkpoint is unchanged.
    Evidence: .sisyphus/evidence/task-6-malformed-llm.txt
  ```

  **Commit**: NO | Message: `refactor(intelligence): replace entry extraction services` | Files: [crypto_news_analyzer/analyzers/intelligence_extractor.py, crypto_news_analyzer/intelligence/*.py, tests/test_intelligence_extraction.py, tests/test_intelligence_merge.py, tests/test_topic_research_scheduler.py]

- [ ] 7. Implement topic prompt draft/revise/manual-confirm workflow

  **What to do**: Add service methods and API/Telegram-ready repository calls for creating a draft topic from user theme, generating a professional research prompt via LLM, revising it with user feedback, replacing it manually, and confirming it into an active topic prompt version. Confirmed topic enters `active`; draft stays `draft`; prompt edit on active topic creates a new version and preserves old findings with original prompt version metadata.
  **Must NOT do**: Do not activate a topic without a confirmed prompt. Do not call real LLM in tests.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: workflow service with LLM mocking and versioned persistence.
  - Skills: [`llm-instructor`] - structured output validation guidance.
  - Omitted: [`dev-browser`] - no web UI.

  **Parallelization**: Can Parallel: YES | Wave 5 | Blocks: [11,12] | Blocked By: [3,4,6]

  **References**:
  - Pattern: `crypto_news_analyzer/analyzers/llm_analyzer.py` - existing LLM integration style.
  - Pattern: `crypto_news_analyzer/analyzers/prompt_manager.py` - prompt loading conventions.
  - Pattern: `tests/test_llm_analyzer.py` - mock mode pattern.
  - Pattern: `tests/test_intelligence_extraction.py` - fake OpenAI client payload queue pattern.

  **Acceptance Criteria**:
  **Acceptance Verification Command**: `uv run pytest tests/test_topic_prompt_workflow.py -k 'generate_confirm or manual_replace or revise_feedback or edit_active_prompt_version' -v` | Evidence: `.sisyphus/evidence/task-7-generate-confirm.txt`
  - [ ] Draft creation stores user theme and generated prompt candidate.
  - [ ] Revision with feedback creates a new draft candidate without overwriting prior history.
  - [ ] Manual replacement validates length/schema guardrails and can be confirmed.
  - [ ] Confirm creates/updates active prompt version and eligible topic state.

  **QA Scenarios**:
  ```
  Scenario: User theme becomes confirmed active topic prompt
    Tool: Bash
    Steps: Run `uv run pytest tests/test_topic_prompt_workflow.py -k 'generate_confirm' -v`
    Expected: Mocked LLM prompt is stored, confirmation sets state to active, active prompt version is retrievable.
    Evidence: .sisyphus/evidence/task-7-generate-confirm.txt

  Scenario: Manual replacement bypasses LLM but remains validated
    Tool: Bash
    Steps: Run `uv run pytest tests/test_topic_prompt_workflow.py -k 'manual_replace' -v`
    Expected: Manual prompt text is saved as current draft and rejects empty/oversized invalid content.
    Evidence: .sisyphus/evidence/task-7-manual-replace.txt
  ```

  **Commit**: NO | Message: `feat(intelligence): add topic prompt workflow` | Files: [crypto_news_analyzer/intelligence/topic_prompts.py, crypto_news_analyzer/analyzers/prompt_manager.py, tests/test_topic_prompt_workflow.py]

- [ ] 8. Implement ingestion-only scheduled topic research service

  **What to do**: Add a service invoked from ingestion after raw crawl storage that loads active topics, determines per-topic cursor, fetches raw messages collected since last successful run, compacts/group messages by source metadata and chronological order, chunks when input exceeds configured limits, calls LLM with topic research prompt, validates structured output, saves findings with citations/snippets/source refs, and records run logs/checkpoints. Partial topic success is allowed: successful topics advance their checkpoint; failed topics do not.
  **Must NOT do**: Do not run scheduled research in `analysis-service`, `api-only`, FastAPI startup, or Telegram bot startup. Do not skip late-arriving messages due to `published_at` cursor.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: core scheduled processing, idempotency, chunking, and failure semantics.
  - Skills: [`llm-instructor`] - structured outputs and validation.
  - Omitted: [`crypto-news-debug`] - no production debugging.

  **Parallelization**: Can Parallel: YES | Wave 5 | Blocks: [10,11,12] | Blocked By: [3,4,6]

  **References**:
  - Pattern: `crypto_news_analyzer/execution_coordinator.py:532-603` - ingestion pipeline initialization wiring.
  - Pattern: `crypto_news_analyzer/execution_coordinator.py:2171` - ingestion loop trigger.
  - Pattern: `crypto_news_analyzer/intelligence/pipeline.py:49-104` - current pipeline orchestration to replace.
  - Pattern: `crypto_news_analyzer/domain/models.py:656-768` - raw item fields including `published_at` and `collected_at`.
  - Pattern: `config.jsonc:38-72` - intelligence collection config defaults.
  - Test: `tests/test_intelligence_ingestion_runtime.py` - full pipeline runtime test style.

  **Acceptance Criteria**:
  **Acceptance Verification Command**: `uv run pytest tests/test_topic_research_scheduler.py -k 'active_topic_saves_findings or failure_does_not_advance_checkpoint or skips_inactive_topics or no_messages or idempotent_retry' -v` | Evidence: `.sisyphus/evidence/task-8-active-research.txt`
  - [ ] Only active topics are researched; draft/paused/archived topics are skipped with test coverage.
  - [ ] No raw messages since checkpoint creates a successful no-op run or explicit skipped run without findings.
  - [ ] Chunking/reduce behavior handles large raw input without dropping citations.
  - [ ] Duplicate/retry run does not duplicate findings for already processed raw/prompt/schema keys.
  - [ ] Topic run logs include status, counts, cursor start/end, prompt/schema versions, and error details.

  **QA Scenarios**:
  ```
  Scenario: Active topic research saves structured findings
    Tool: Bash
    Steps: Run `uv run pytest tests/test_topic_research_scheduler.py -k 'active_topic_saves_findings' -v`
    Expected: Mock raw messages produce validated findings linked to topic, prompt version, raw IDs, and snippets.
    Evidence: .sisyphus/evidence/task-8-active-research.txt

  Scenario: Failed topic does not advance checkpoint
    Tool: Bash
    Steps: Run `uv run pytest tests/test_topic_research_scheduler.py -k 'failure_does_not_advance_checkpoint' -v`
    Expected: Failed run log is saved and next run sees the same raw message window.
    Evidence: .sisyphus/evidence/task-8-failure-checkpoint.txt
  ```

  **Commit**: NO | Message: `feat(intelligence): run scheduled topic research in ingestion` | Files: [crypto_news_analyzer/intelligence/topic_research.py, crypto_news_analyzer/intelligence/pipeline.py, crypto_news_analyzer/execution_coordinator.py, tests/test_topic_research_scheduler.py, tests/test_intelligence_ingestion_runtime.py]

- [ ] 9. Implement finding merge preview and accept workflow

  **What to do**: Add service logic to create persisted merge previews for a topic from current active finding IDs plus topic prompt context. LLM returns structured merged finding content. Store preview with expiry, prompt version, source finding IDs, and content hash. Accepting a preview must verify it is unexpired, belongs to the topic, source finding IDs still match the active finding set intended for merge, then persist merged finding and archive/hide exactly those source findings with `superseded_by_finding_id` or equivalent.
  **Must NOT do**: Do not accept client-supplied merge result text as authoritative. Do not archive findings not bound to the preview.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: transactional workflow with LLM, persistence, stale rejection.
  - Skills: [`llm-instructor`] - structured merge output.
  - Omitted: [`playwright`] - no browser UI.

  **Parallelization**: Can Parallel: YES | Wave 5 | Blocks: [11,12] | Blocked By: [3,4,6]

  **References**:
  - Pattern: `crypto_news_analyzer/intelligence/topic_converger.py:105-148` - existing topic merge/convergence run style, but do not reuse pairwise convergence semantics as product merge.
  - Pattern: `prompts/topic_convergence_prompt.md` - existing merge prompt style reference.
  - Pattern: `tests/test_topic_converger_guided.py` - topic merge test style.
  - Pattern: `tests/test_intelligence_api.py` - API merge-like response test style.

  **Acceptance Criteria**:
  **Acceptance Verification Command**: `uv run pytest tests/test_topic_findings_api.py -k 'merge_preview or merge_accept_archives_exact_sources or stale_merge_preview_rejected' -v` | Evidence: `.sisyphus/evidence/task-9-merge-accept.txt`
  - [ ] Merge preview stores exact source finding IDs, topic ID, prompt version, expiry, and structured merged content.
  - [ ] Accept preview creates one merged active finding and archives source findings.
  - [ ] Accept preview rejects expired preview, topic mismatch, unauthorized request, and stale active finding set.
  - [ ] Archived findings are hidden from default topic detail but queryable in repository tests when explicitly requested.

  **QA Scenarios**:
  ```
  Scenario: Merge accept archives exact source findings
    Tool: Bash
    Steps: Run `uv run pytest tests/test_topic_findings_api.py -k 'merge_accept_archives_exact_sources' -v`
    Expected: One merged finding is active; all and only preview source findings are archived.
    Evidence: .sisyphus/evidence/task-9-merge-accept.txt

  Scenario: Stale preview is rejected
    Tool: Bash
    Steps: Run `uv run pytest tests/test_topic_findings_api.py -k 'stale_merge_preview_rejected' -v`
    Expected: Acceptance fails with deterministic error and no findings are archived.
    Evidence: .sisyphus/evidence/task-9-stale-preview.txt
  ```

  **Commit**: NO | Message: `feat(intelligence): add topic finding merge workflow` | Files: [crypto_news_analyzer/intelligence/topic_findings.py, prompts/topic_findings_merge_prompt.md, tests/test_topic_findings_api.py]

- [ ] 10. Wire topic research into ingestion runtime only

  **What to do**: Update `MainController`/pipeline initialization so ingestion mode creates and calls topic research services after raw crawl storage. Ensure analysis-service/api-only initialize only API/Telegram read/interactive dependencies and never start recurring topic research. Keep ingestion source crawling behavior intact for `purpose="intelligence"` sources.
  **Must NOT do**: Do not start background research loops from FastAPI app creation or Telegram command handler startup.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: runtime wiring and mode boundary correctness.
  - Skills: [] - no specialized skill required.
  - Omitted: [`crypto-news-debug`] - no live Railway inspection.

  **Parallelization**: Can Parallel: YES | Wave 6 | Blocks: [15] | Blocked By: [8]

  **References**:
  - Pattern: `crypto_news_analyzer/main.py` - runtime mode dispatch.
  - Pattern: `crypto_news_analyzer/execution_coordinator.py:532-603` - ingestion-only pipeline initialization.
  - Pattern: `crypto_news_analyzer/execution_coordinator.py:2171` - ingestion loop execution.
  - Pattern: `crypto_news_analyzer/api_server.py` - app factory must not schedule recurring research.
  - Test: `tests/test_intelligence_ingestion_runtime.py` - ingestion runtime pattern.
  - Test: `tests/test_api_server.py` - FastAPI factory/controller injection pattern.

  **Acceptance Criteria**:
  **Acceptance Verification Command**: `uv run pytest tests/test_intelligence_ingestion_runtime.py tests/test_api_server.py -k 'topic_research_invoked_after_raw_save or does_not_start_topic_research_scheduler' -v` | Evidence: `.sisyphus/evidence/task-10-ingestion-wiring.txt`
  - [ ] In ingestion mode, raw crawl → topic research is invoked in the intended order.
  - [ ] In analysis-service/api-only mode, topic research scheduler is not created or called.
  - [ ] Topic prompt/merge API calls can use services without starting recurring scheduler.
  - [ ] Existing non-intelligence analysis endpoints continue to initialize.

  **QA Scenarios**:
  ```
  Scenario: Ingestion invokes topic research after raw save
    Tool: Bash
    Steps: Run `uv run pytest tests/test_intelligence_ingestion_runtime.py -k 'topic_research_invoked_after_raw_save' -v`
    Expected: Spy services show raw save precedes topic research call.
    Evidence: .sisyphus/evidence/task-10-ingestion-wiring.txt

  Scenario: API server does not schedule research
    Tool: Bash
    Steps: Run `uv run pytest tests/test_api_server.py -k 'does_not_start_topic_research_scheduler' -v`
    Expected: App creation and test requests do not call recurring scheduler.
    Evidence: .sisyphus/evidence/task-10-api-no-scheduler.txt
  ```

  **Commit**: NO | Message: `refactor(runtime): limit topic research scheduling to ingestion` | Files: [crypto_news_analyzer/execution_coordinator.py, crypto_news_analyzer/main.py, crypto_news_analyzer/api_server.py, tests/test_intelligence_ingestion_runtime.py, tests/test_api_server.py]

- [ ] 11. Implement topic-only HTTP API workflow

  **What to do**: Under existing authenticated `/intelligence/topics*` namespace, expose endpoints for create draft from user theme, revise draft with feedback, manually replace prompt draft, confirm prompt, edit active prompt (new version), list topics, get topic detail with prompt versions and active findings, create merge preview, accept merge preview, pause/archive topic, and list topic research runs. Delete `/intelligence/entries*`, `/intelligence/discovery`, `/intelligence/search` entry routes if they expose old first-class entry concepts.
  **Must NOT do**: Do not expose `entry_type`, `slang`, `channel`, or canonical-entry fields in active topic responses. Do not add compatibility aliases.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: API contract replacement with auth, response models, tests.
  - Skills: [] - no specialized skill required.
  - Omitted: [`dev-browser`] - no browser UI.

  **Parallelization**: Can Parallel: YES | Wave 6 | Blocks: [13,14] | Blocked By: [7,8,9]

  **References**:
  - Pattern: `crypto_news_analyzer/api_server.py:338-544` - existing Pydantic response model area.
  - Pattern: `crypto_news_analyzer/api_server.py:1871-1947` - existing topic routes to keep/extend.
  - Pattern: `crypto_news_analyzer/api_server.py:1540-1847` - old entry/discovery/search/raw entry routes to remove or rewrite if old concept leaks.
  - Test: `tests/test_api_server.py` - auth and app factory pattern.
  - Test: `tests/test_intelligence_api.py` - in-memory repository pattern and intelligence route coverage.

  **Acceptance Criteria**:
  **Acceptance Verification Command**: `uv run pytest tests/test_topic_findings_api.py -k 'create_confirm_research_detail_merge or unauthorized or stale or old_entries_routes_404' -v` | Evidence: `.sisyphus/evidence/task-11-api-happy-path.txt`
  - [ ] All new topic endpoints require Bearer auth and reject unauthorized requests.
  - [ ] Topic detail returns topic state, prompt versions/current prompt, active findings, citations, and merge availability.
  - [ ] Merge preview/accept API handles success, unauthorized, expired, stale, and topic mismatch cases.
  - [ ] `/intelligence/entries*` routes are absent and tests expect 404, not compatibility content.

  **QA Scenarios**:
  ```
  Scenario: Topic API full happy path
    Tool: Bash
    Steps: Run `uv run pytest tests/test_topic_findings_api.py -k 'create_confirm_research_detail_merge' -v`
    Expected: Authenticated API creates/activates topic, shows findings, previews merge, accepts merge.
    Evidence: .sisyphus/evidence/task-11-api-happy-path.txt

  Scenario: Old entries API is deleted
    Tool: Bash
    Steps: Run `uv run pytest tests/test_topic_findings_api.py -k 'old_entries_routes_404' -v`
    Expected: `/intelligence/entries` and nested entry routes return 404 or are not registered.
    Evidence: .sisyphus/evidence/task-11-old-api-deleted.txt
  ```

  **Commit**: NO | Message: `feat(api): expose topic-only intelligence workflows` | Files: [crypto_news_analyzer/api_server.py, tests/test_topic_findings_api.py, tests/test_intelligence_api.py]

- [ ] 12. Implement Telegram topic workflow and remove `/intel_*`

  **What to do**: Add/extend `/topic_*` commands for topic draft creation from user theme, prompt revision, manual prompt set, confirm, list, detail, merge preview, merge accept, pause/archive, and logs. Use inline buttons/callbacks for confirm and merge accept where practical; callbacks must verify authorized user and preview/topic IDs. Remove `/intel_*` command registrations and handlers from active bot commands.
  **Must NOT do**: Do not expose old entry/channel/slang wording. Do not rely on manual Telegram verification; use mocked updates/callbacks.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: command UX, callbacks, authorization, message length handling.
  - Skills: [] - no specialized skill required.
  - Omitted: [`dev-browser`] - no browser automation.

  **Parallelization**: Can Parallel: YES | Wave 6 | Blocks: [13,14] | Blocked By: [7,8,9]

  **References**:
  - Pattern: `crypto_news_analyzer/reporters/telegram_command_handler.py:197-238` - command/callback registration area.
  - Pattern: `crypto_news_analyzer/reporters/telegram_command_handler.py:3803-4014` - current `/topic_*` handlers.
  - Pattern: `crypto_news_analyzer/reporters/telegram_command_handler.py:1490-3724` - old `/intel_*` handlers to remove/unregister.
  - Pattern: `crypto_news_analyzer/reporters/telegram_command_handler.py:1195-1217` - bot command setup.
  - Test: `tests/test_intelligence_telegram_commands.py` - mocked Telegram commands and callbacks.
  - Test: `tests/test_telegram_command_handler_analyze.py` - command handler stub pattern.

  **Acceptance Criteria**:
  **Acceptance Verification Command**: `uv run pytest tests/test_topic_findings_telegram.py -k 'topic_create_confirm_flow or topic_merge or intel_commands_not_registered or unauthorized_callback' -v` | Evidence: `.sisyphus/evidence/task-12-telegram-confirm.txt`
  - [ ] `/topic_create <theme>` produces prompt draft preview with confirm/revise guidance.
  - [ ] `/topic_revise <topic_id> <feedback>` and `/topic_set_prompt <topic_id> <prompt>` update drafts safely.
  - [ ] `/topic_confirm <topic_id>` activates topic.
  - [ ] `/topic_detail <topic_id>` shows current prompt and active findings with pagination/truncation.
  - [ ] `/topic_merge <topic_id>` creates preview; callback or command accepts preview only when authorized and not stale.
  - [ ] `/intel_*` commands are not registered.

  **QA Scenarios**:
  ```
  Scenario: Telegram topic prompt confirmation flow
    Tool: Bash
    Steps: Run `uv run pytest tests/test_topic_findings_telegram.py -k 'topic_create_confirm_flow' -v`
    Expected: Mocked authorized user creates draft and confirms active topic with expected messages/buttons.
    Evidence: .sisyphus/evidence/task-12-telegram-confirm.txt

  Scenario: Old Telegram intel commands are gone
    Tool: Bash
    Steps: Run `uv run pytest tests/test_topic_findings_telegram.py -k 'intel_commands_not_registered' -v`
    Expected: Bot command registration and dispatcher contain no `/intel_*` commands.
    Evidence: .sisyphus/evidence/task-12-intel-commands-gone.txt
  ```

  **Commit**: NO | Message: `feat(telegram): add topic-only intelligence commands` | Files: [crypto_news_analyzer/reporters/telegram_command_handler.py, tests/test_topic_findings_telegram.py, tests/test_intelligence_telegram_commands.py]

- [ ] 13. Remove old active entry/intel surfaces and old concept leakage

  **What to do**: Delete or fully unwire old entry/discovery/search APIs, `/intel_*` Telegram commands, old response fields, and active docs/help text that present channel/slang/canonical entries as product concepts. Run LSP/AST/text searches and update remaining references to be either raw source metadata, historical migration comments, or removed code. Update tests that formerly expected `entry_type` to expect topic-only models/responses.
  **Must NOT do**: Do not delete raw crawling/storage. Do not remove source metadata fields required for grouping/citations.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: broad cleanup with regression risk.
  - Skills: [] - no specialized skill required.
  - Omitted: [`ai-slop-remover`] - this is functional cleanup, not single-file style cleanup.

  **Parallelization**: Can Parallel: YES | Wave 7 | Blocks: [15] | Blocked By: [11,12]

  **References**:
  - Pattern: `crypto_news_analyzer/domain/models.py:61-63` - `EntryType` should not remain active.
  - Pattern: `crypto_news_analyzer/api_server.py:595-655` - current entry response converters carry `entry_type`.
  - Pattern: `crypto_news_analyzer/reporters/telegram_command_handler.py:379-399` - current entry formatting includes old type display.
  - Pattern: `prompts/intelligence_extraction_prompt.md:6-10` - old prompt separates channel/slang extraction.
  - Test: `tests/test_intelligence_models.py` - replace old enum validation expectations.
  - Test: `tests/test_intelligence_api.py` - replace old entry API expectations.

  **Acceptance Criteria**:
  **Acceptance Verification Command**: `uv run pytest tests/test_topic_findings_api.py tests/test_topic_findings_telegram.py -k 'no_old_concepts or help_excludes_intel_commands or old_entries_routes_404' -v` | Evidence: `.sisyphus/evidence/task-13-no-old-concepts.txt`
  - [ ] Active runtime code no longer imports or branches on `EntryType` for intelligence product behavior.
  - [ ] Active API responses do not include `entry_type`, channel-specific, or slang-specific product fields.
  - [ ] Bot help/commands do not advertise `/intel_*`.
  - [ ] New prompts do not instruct LLM to extract channel/slang categories.
  - [ ] Remaining old terms, if any, are restricted to historical migration files, removed/deprecated tests, or raw source metadata names.

  **QA Scenarios**:
  ```
  Scenario: Active old concept imports are absent
    Tool: Bash
    Steps: Run `uv run pytest tests/test_topic_findings_api.py tests/test_topic_findings_telegram.py -k 'no_old_concepts' -v`
    Expected: Tests pass and assert active responses/messages exclude old fields/labels.
    Evidence: .sisyphus/evidence/task-13-no-old-concepts.txt

  Scenario: Help/registration excludes old commands
    Tool: Bash
    Steps: Run `uv run pytest tests/test_topic_findings_telegram.py -k 'help_excludes_intel_commands' -v`
    Expected: Help text and bot command setup include topic commands and exclude `/intel_*`.
    Evidence: .sisyphus/evidence/task-13-help-cleanup.txt
  ```

  **Commit**: NO | Message: `refactor(intelligence): remove legacy entry surfaces` | Files: [crypto_news_analyzer/api_server.py, crypto_news_analyzer/reporters/telegram_command_handler.py, crypto_news_analyzer/domain/models.py, crypto_news_analyzer/intelligence/*.py, prompts/*.md, tests/*.py]

- [ ] 14. Update configuration, README/help text, and operational guardrails

  **What to do**: Update `config.jsonc` intelligence settings to topic-only names/defaults, including daily research interval, batch/chunk limits, retention default 180 days, and model config references. Update README/AGENTS-facing help only where needed to remove legacy entry concepts and document topic commands/API at a high level. Keep docs concise and do not add new deployment topology.
  **Must NOT do**: Do not document legacy API-server as primary. Do not add Railway-specific production changes.

  **Recommended Agent Profile**:
  - Category: `writing` - Reason: config/docs/help cleanup with precise wording.
  - Skills: [] - no specialized skill required.
  - Omitted: [`railway-docs`] - no Railway docs lookup needed.

  **Parallelization**: Can Parallel: YES | Wave 7 | Blocks: [15] | Blocked By: [5,11,12]

  **References**:
  - Pattern: `config.jsonc:38-72` - existing intelligence collection config.
  - Pattern: `README.md` - current feature/command/API documentation.
  - Pattern: `AGENTS.md` - project guidance; update only if necessary and accurate.
  - Pattern: `crypto_news_analyzer/reporters/telegram_command_handler.py:1195-1217` - command setup/help consistency.

  **Acceptance Criteria**:
  **Acceptance Verification Command**: `uv run pytest tests/test_raw_message_retention.py tests/test_topic_research_scheduler.py tests/test_topic_findings_telegram.py -k 'config_defaults or docs_exclude_deleted_commands' -v` | Evidence: `.sisyphus/evidence/task-14-config-defaults.txt`
  - [ ] Config defaults match implementation: retention 180 days, daily topic research, topic prompt/research/merge model config.
  - [ ] README/help text describes topic-only workflow and excludes `/intel_*` commands.
  - [ ] Docs do not reintroduce channel/slang as intelligence concepts.
  - [ ] Existing analysis-service/ingestion split guidance remains correct.

  **QA Scenarios**:
  ```
  Scenario: Config loads topic-only defaults
    Tool: Bash
    Steps: Run `uv run pytest tests/test_raw_message_retention.py tests/test_topic_research_scheduler.py -k 'config_defaults' -v`
    Expected: Tests pass and confirm configured/default values are read correctly.
    Evidence: .sisyphus/evidence/task-14-config-defaults.txt

  Scenario: Public docs exclude deleted commands
    Tool: Bash
    Steps: Run `uv run pytest tests/test_topic_findings_telegram.py -k 'docs_exclude_deleted_commands' -v`
    Expected: Deleted commands are not advertised; topic commands are documented.
    Evidence: .sisyphus/evidence/task-14-docs-cleanup.txt
  ```

  **Commit**: NO | Message: `docs(intelligence): document topic-only workflow` | Files: [config.jsonc, README.md, AGENTS.md, crypto_news_analyzer/reporters/telegram_command_handler.py, tests/test_raw_message_retention.py]

- [ ] 15. Full validation, cleanup, and migration safety review

  **What to do**: Run targeted and full verification. Fix failing tests, type errors, lint issues, stale imports, dead code, and migration parity issues. Confirm no production external services are required. If optional Postgres test environment is available through `TEST_DATABASE_URL`, run existing real Postgres-marked tests; otherwise record they were safely skipped by existing guard.
  **Must NOT do**: Do not skip failing tests. Do not use production database, real Telegram, or real LLM credentials.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: broad validation across refactor.
  - Skills: [] - no specialized skill required.
  - Omitted: [`crypto-news-debug`] - no production debugging.

  **Parallelization**: Can Parallel: NO | Wave 8 | Blocks: [Final Verification] | Blocked By: [10,13,14]

  **References**:
  - Test: `pyproject.toml:81-92` - pytest options/markers.
  - Test: `tests/conftest.py` - Postgres safety guard and fixtures.
  - Test: `tests/integration/test_intelligence_pgvector.py` - optional real Postgres marker.
  - Commands: AGENTS.md build/lint/test guidance requires `uv`.

  **Acceptance Criteria**:
  **Acceptance Verification Command**: `uv run pytest tests/ -v && uv run mypy crypto_news_analyzer/ && uv run flake8 crypto_news_analyzer/` | Evidence: `.sisyphus/evidence/task-15-full-verification.txt`
  - [ ] `uv run pytest tests/test_topic_prompt_workflow.py -v` passes.
  - [ ] `uv run pytest tests/test_topic_research_scheduler.py -v` passes.
  - [ ] `uv run pytest tests/test_topic_findings_api.py -v` passes.
  - [ ] `uv run pytest tests/test_topic_findings_telegram.py -v` passes.
  - [ ] `uv run pytest tests/test_raw_message_retention.py -v` passes.
  - [ ] `uv run pytest tests/ -v` passes.
  - [ ] `uv run mypy crypto_news_analyzer/` passes.
  - [ ] `uv run flake8 crypto_news_analyzer/` passes.

  **QA Scenarios**:
  ```
  Scenario: Full local verification passes
    Tool: Bash
    Steps: Run `uv run pytest tests/ -v && uv run mypy crypto_news_analyzer/ && uv run flake8 crypto_news_analyzer/`
    Expected: All commands exit 0 with no failures/errors.
    Evidence: .sisyphus/evidence/task-15-full-verification.txt

  Scenario: Optional Postgres integration is safe
    Tool: Bash
    Steps: Run `uv run pytest tests/integration/test_intelligence_pgvector.py -v`
    Expected: Tests pass when safe `TEST_DATABASE_URL` is configured, otherwise skip through existing safety guard; no production DB is used.
    Evidence: .sisyphus/evidence/task-15-postgres-optional.txt
  ```

  **Commit**: YES | Message: `refactor(intelligence): replace entry extraction with topic research` | Files: [crypto_news_analyzer/**, migrations/postgresql/*.sql, prompts/*.md, tests/*.py, config.jsonc, README.md]

## Final Verification Wave (MANDATORY — after ALL implementation tasks)
> 4 review agents run in PARALLEL. ALL must APPROVE before implementation is marked complete.
> Verification is fully agent-executed; consolidated results are presented to the user after completion and do not require user/manual QA to pass.
> Rejection from any verification agent -> fix -> re-run the full failed verification area -> require all approvals again.
- [ ] F1. Plan Compliance Audit — oracle
- [ ] F2. Code Quality Review — unspecified-high
- [ ] F3. Agent-Executed End-to-End QA — unspecified-high
- [ ] F4. Scope Fidelity Check — deep

## Commit Strategy
- Commit after all tests, mypy, and flake8 pass.
- Suggested message: `refactor(intelligence): replace entry extraction with topic research`
- Include migrations, prompts, source changes, tests, and minimal docs/config updates in one atomic commit unless hooks force follow-up fixes.
- Do not push unless explicitly requested.

## Success Criteria
- Topic is the only first-class intelligence concept in active product surfaces.
- Raw message ingestion remains stable and retains raw text for configurable 180-day default.
- Scheduled research produces structured per-topic findings from raw messages since the correct checkpoint.
- Topic detail returns prompt versions and active findings.
- Merge preview/accept archives old findings safely and rejects stale previews.
- Old entry/intel API/Telegram surfaces are absent.
- All verification commands pass without production services or real external APIs.
