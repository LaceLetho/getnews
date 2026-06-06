# Task 1: Symbol Reference Inventory

> Generated: 2026-06-05 | Audit type: Read-only reference discovery
> Plan: `/.omo/plans/redundant-design-simplification.md`

---

## 1. DOMAIN MODEL SYMBOLS

### 1.1 `TopicLifecycleStatus.PAUSED`

**Definition:**
- `crypto_news_analyzer/domain/models.py:70` — `PAUSED = "paused"` (enum member of `TopicLifecycleStatus`)
- `crypto_news_analyzer/domain/models.py:96` — `_TOPIC_LIFECYCLE_STATUS_VALUES` derives from enum; includes `"paused"`
- `crypto_news_analyzer/domain/models.py:868-869` — validation: `if self.lifecycle_status not in _TOPIC_LIFECYCLE_STATUS_VALUES: raise ValueError("... paused, archived")`

**Internal references (same file `domain/models.py`):**
- `crypto_news_analyzer/domain/models.py:873` — `IntelligenceTopic.__post_init__`: `TopicLifecycleStatus.PAUSED.value` in inactive-status set; sets `is_active = False`
- `crypto_news_analyzer/domain/models.py:909` — `IntelligenceTopic.from_dict`: default fallback `TopicLifecycleStatus.PAUSED.value` when `is_active` is falsy

**Production callers:**
- `crypto_news_analyzer/api_server.py:1915` — `topic.lifecycle_status = TopicLifecycleStatus.PAUSED.value` (REST `/intelligence/topics/{id}/pause` endpoint)

**Test references:**
- `tests/intelligence/test_topic_research_scheduler.py:486` — `lifecycle_status=TopicLifecycleStatus.PAUSED.value`

**Docs references:**
- `docs/plans/remove-is_active-redundancy.md:50,86-90,134,135` — plan documentation (expected: plan itself discusses removal)

**VERDICT: HAS REMAINING REFERENCES — listed below**
- `api_server.py:1915` (pause endpoint logic — must be replaced with ARCHIVED per T4)
- `domain/models.py:873,909` (internal model logic — must be updated per T2)
- `domain/models.py:868` (validation error message — must be updated)
- `domain/models.py:96` (`_TOPIC_LIFECYCLE_STATUS_VALUES` — value set derives from enum)
- `tests/intelligence/test_topic_research_scheduler.py:486` (test — must be updated)
- `docs/plans/remove-is_active-redundancy.md` (plan doc — expected, safe)

---

### 1.2 `IntelligenceTopic.is_active` (field)

**Definition:**
- `crypto_news_analyzer/domain/models.py:856` — `is_active: bool = True` (field on `IntelligenceTopic` dataclass)
- `crypto_news_analyzer/domain/models.py:870` — `__post_init__`: `self.is_active = bool(self.is_active)`
- `crypto_news_analyzer/domain/models.py:871-878` — `__post_init__`: sync logic (sets `is_active` based on `lifecycle_status`)
- `crypto_news_analyzer/domain/models.py:903` — `from_dict`: `is_active` in `allowed` set
- `crypto_news_analyzer/domain/models.py:909` — `from_dict`: uses `is_active` to derive default `lifecycle_status`

**Storage schema:**
- `crypto_news_analyzer/storage/intelligence_schema.py:49` — `is_active BOOLEAN NOT NULL DEFAULT TRUE` (CREATE TABLE column)
- `crypto_news_analyzer/storage/intelligence_schema.py:127` — `ON intelligence_topics (is_active, updated_at DESC)` (INDEX)

**Storage persist:**
- `crypto_news_analyzer/storage/data_manager.py:2679` — `"is_active"` in upsert column list
- `crypto_news_analyzer/storage/data_manager.py:2707` — `data["is_active"] = bool(data.get("is_active", True))`

**Repository interface (domain):**
- `crypto_news_analyzer/domain/repositories.py:459` — `list_topics(is_active: Optional[bool] = None)` parameter
- `crypto_news_analyzer/domain/repositories.py:465` — `count_topics(is_active: Optional[bool] = None)` parameter

**Repository implementation (storage):**
- `crypto_news_analyzer/storage/data_manager.py:2721-2727` — `list_intelligence_topics(is_active=)` SQL filter
- `crypto_news_analyzer/storage/data_manager.py:2742-2747` — `count_intelligence_topics(is_active=)` SQL filter
- `crypto_news_analyzer/storage/repositories.py:671,675` — `list_topics(is_active=)` delegation
- `crypto_news_analyzer/storage/repositories.py:678-679` — `count_topics(is_active=)` delegation

**Production callers using `is_active=True`:**
- `crypto_news_analyzer/intelligence/topic_research.py:262` — `list_topics(is_active=True, limit=100)`
- `crypto_news_analyzer/api_server.py:2049` — `is_active=True if active_only else None`
- `crypto_news_analyzer/api_server.py:2053` — `is_active=True if active_only else None`
- `crypto_news_analyzer/reporters/telegram/intelligence_commands.py:1124` — `list_topics(is_active=True)`
- `crypto_news_analyzer/reporters/telegram/intelligence_commands.py:1125` — `count_topics(is_active=True)`

**API response dynamic read:**
- `crypto_news_analyzer/api_server.py:582` — `"is_active": bool(getattr(topic, "is_active", True))` (serialized in topic response)

**Test references:**
- `tests/intelligence/test_intelligence_models.py:92-93` — asserts `active.is_active is True`, `paused.is_active is False`
- `tests/intelligence/test_topic_research_scheduler.py:105-111` — in-memory repo with `is_active` filter
- `tests/intelligence/test_topic_datasource_api.py:45-57` — in-memory repo with `is_active` filter
- `tests/intelligence/test_topic_datasource_schema.py:31,36` — SQL INSERT with `is_active` column
- `tests/shared/test_datasource_repository.py:256` — test dict with `"is_active": True`
- `tests/news/test_api_server.py:989,999` — test assertions on `"is_active": True`

**Docs/skills references:**
- `docs/TOPIC_LIFECYCLE.md:176` — `- is_active 改为 false`
- `skills/smart-news/references/intelligence-query.md:204` — `"is_active": true` in JSON example
- `docs/plans/remove-is_active-redundancy.md` — comprehensive plan (expected, safe)

**Deployment files:**
- No references in `Dockerfile`, `docker-entrypoint.sh`, or `README.md` to `is_active` for topics.

**VERDICT: BLOCKED BY wide surface — listed below**
- 8 production files (domain model + schema + data manager + 2 repos + 4 callers) must be updated per T2/T3
- 6 test files must be updated
- 2 docs/skills files must be updated
- API response currently reads `is_active` dynamically; must switch to `lifecycle_status == 'active'` derivation

---

### 1.3 `MergePreviewState.EXPIRED`

**Definition:**
- `crypto_news_analyzer/domain/models.py:89` — `EXPIRED = "expired"` (enum member of `MergePreviewState`)

**Internal usage (production):**
- `crypto_news_analyzer/storage/repositories.py:1632` — `self._set_merge_preview_state(preview_id, "expired", None)` (raw string, NOT the enum constant)

**Callers of `MergePreviewState.EXPIRED` (enum constant):**
- **NONE** — zero callers use the enum constant `MergePreviewState.EXPIRED`
- The raw string `"expired"` is used at `storage/repositories.py:1632` in `accept_merge_preview`

**Test references:**
- `tests/intelligence/test_topic_findings_api.py:446-461` — `test_expired_merge_preview_rejected()` uses `MatchPreviewError, match="expired"` (matches error message text, not the enum)
- `tests/intelligence/test_topic_findings_api.py:141,149` — `include_expired=False` parameter on in-memory repo (parameter name, not enum value)

**Docs references:**
- None found outside plan documents.

**VERDICT: SAFE TO DELETE — zero callers use the enum constant**
- The raw string `"expired"` at `storage/repositories.py:1632` will be removed per T5 (no more state mutation to "expired")
- Tests check error messages containing "expired", not the enum value — these remain valid after T5 refactor

---

## 2. ALIASES AND DEAD CODE

### 2.1 `load_auth_from_env` in `config/manager.py`

**Definition:**
- `crypto_news_analyzer/config/manager.py:482` — `def load_auth_from_env(self) -> AuthConfig: ... return self.get_auth_config()`

**Callers (production):**
- **NONE** — zero callers in any file across the entire codebase

**Test references:**
- **NONE** — zero test references

**Docs references:**
- **NONE** — zero docs references

**Deployment files:**
- No references in `Dockerfile`, `docker-entrypoint.sh`, or `README.md`

**VERDICT: SAFE TO DELETE — zero callers, pure pass-through alias to `get_auth_config()`**

---

### 2.2 `run_due_topics` in `intelligence/topic_research.py`

**Definition:**
- `crypto_news_analyzer/intelligence/topic_research.py:316` — `def run_due_topics(self) -> int: return self.run_scheduled_topic_research()`

**Callers (production):**
- **NONE** — zero callers outside the definition

**Test references:**
- **NONE** — zero test references

**Docs references:**
- **NONE** — zero docs references

**Deployment files:**
- No references in `Dockerfile`, `docker-entrypoint.sh`, or `README.md`

**VERDICT: SAFE TO DELETE — zero callers, pure backward-compatible alias to `run_scheduled_topic_research()`**

---

### 2.3 `ExecutionMode` enum in `execution_coordinator.py`

**Definition:**
- `crypto_news_analyzer/execution_coordinator.py:53-58` — `class ExecutionMode(Enum)` with values `ONE_TIME`, `SCHEDULED`, `COMMAND_TRIGGERED`

**Callers (production):**
- **NONE** — zero production code uses `ExecutionMode` (the class itself has no references beyond test import)

**Test references:**
- `tests/shared/test_main_controller.py:18` — imports `ExecutionMode` from `execution_coordinator`

**Docs references:**
- **NONE** — zero docs references

**Deployment files:**
- No references in `Dockerfile`, `docker-entrypoint.sh`, or `README.md`

**VERDICT: SAFE TO DELETE — one test reference that must be verified**
- `tests/shared/test_main_controller.py:18` imports it; verify it is actually USED in test logic (not just imported but unused)

---

### 2.4 `plugin_system_example.py` file

**File existence:**
- `crypto_news_analyzer/crawlers/plugin_system_example.py` — 349 lines, demo/example code with `if __name__ == "__main__"` entry

**Import references:**
- **NONE** — no other file imports `plugin_system_example` (confirmed by grep for `plugin_system_example` returning zero matches)

**Test references:**
- **NONE** — zero test references

**Docs references:**
- **NONE** — zero docs references

**Deployment files:**
- No references in `Dockerfile`, `docker-entrypoint.sh`, or `README.md`

**VERDICT: SAFE TO DELETE — self-contained demo file, zero imports**

---

## 3. REPOSITORY ALIASES

### 3.1 `create_topic_prompt_version`

**Definitions:**
- `crypto_news_analyzer/domain/repositories.py:471` — ABC: `return self.save_topic_prompt(prompt)` (alias to `save_topic_prompt`)
- `crypto_news_analyzer/storage/repositories.py:681` — impl: delegates back to `save_*`

**Production callers of `create_topic_prompt_version`:**
- `crypto_news_analyzer/intelligence/topic_prompts.py:537` — `self.repository.create_topic_prompt_version(prompt)`
- `crypto_news_analyzer/intelligence/topic_prompts.py:593` — `self.repository.create_topic_prompt_version(revised)`
- `crypto_news_analyzer/intelligence/topic_prompts.py:640` — `self.repository.create_topic_prompt_version(prompt)`
- `crypto_news_analyzer/intelligence/topic_prompts.py:664` — `self.repository.create_topic_prompt_version(current_active)`
- `crypto_news_analyzer/intelligence/topic_prompts.py:671` — `self.repository.create_topic_prompt_version(prompt)`
- `crypto_news_analyzer/intelligence/topic_prompts.py:713` — `self.repository.create_topic_prompt_version(prompt)`

**Test references:**
- `tests/intelligence/test_topic_findings_api.py:74` — in-memory repo mock defines `create_topic_prompt_version`
- `tests/intelligence/test_topic_findings_api.py:256` — calls `repo.create_topic_prompt_version(prompt)`
- `tests/intelligence/test_topic_findings_api.py:869` — calls `repo.create_topic_prompt_version(draft_prompt)`
- `tests/intelligence/test_topic_datasource_api.py:179` — in-memory repo mock defines `create_topic_prompt_version`

**VERDICT: BLOCKED — has 6 production callers; must redirect to `save_topic_prompt` first (T9)**

---

### 3.2 `create_topic_finding`

**Definitions:**
- `crypto_news_analyzer/domain/repositories.py:512` — ABC: `create_topic_finding(self, finding)`
- `crypto_news_analyzer/storage/repositories.py:813` — impl: `def create_topic_finding(self, finding) -> str:` ... `return self.save_topic_finding(finding)` (line 814)

**Production callers of `create_topic_finding`:**
- `crypto_news_analyzer/intelligence/topic_findings.py:333` — `self.repository.create_topic_finding(merged_finding)`
- `crypto_news_analyzer/intelligence/topic_research.py:660` — `self.repository.create_topic_finding(finding)`

**Test references:**
- `tests/intelligence/test_topic_findings_api.py:78` — mock defines `create_topic_finding`
- `tests/intelligence/test_topic_findings_api.py:273,432,547,895` — calls `repo.create_topic_finding(...)`
- `tests/intelligence/test_topic_datasource_api.py:182` — mock defines `create_topic_finding`
- `tests/intelligence/test_topic_prompt_workflow.py:421` — calls `repository.create_topic_finding(finding)`
- `tests/intelligence/test_topic_research_scheduler.py:159` — mock defines `create_topic_finding`

**VERDICT: BLOCKED — 2 production callers + 5+ test references; redirect to `save_topic_finding` (T9)**

---

### 3.3 `create_topic_research_run`

**Definitions:**
- `crypto_news_analyzer/domain/repositories.py:698` — ABC: `return self.save_topic_research_run(run)` (alias)
- `crypto_news_analyzer/storage/repositories.py:1282` — impl: `return self.save_topic_research_run(run)` (pass-through)

**Production callers:**
- `crypto_news_analyzer/intelligence/topic_research.py:351` — `self.repository.create_topic_research_run(run)`

**Test references:**
- `tests/intelligence/test_topic_research_scheduler.py:148` — mock defines `create_topic_research_run`

**VERDICT: BLOCKED — 1 production caller; redirect to `save_topic_research_run` (T9)**

---

### 3.4 `create_merge_preview`

**Definitions:**
- `crypto_news_analyzer/domain/repositories.py:741` — ABC: `return self.save_merge_preview(preview)` (alias)
- `crypto_news_analyzer/storage/repositories.py:1513` — impl: `return self.save_merge_preview(preview)` (pass-through)

**Production callers:**
- `crypto_news_analyzer/intelligence/topic_findings.py:192` — `self.repository.create_merge_preview(preview)`

**Test references:**
- `tests/intelligence/test_topic_findings_api.py:109` — mock defines `create_merge_preview`
- `tests/intelligence/test_topic_findings_api.py:288,326,340,354,420,455,473,511,527,551` — multiple calls to `service.create_merge_preview(...)` or `repo.create_merge_preview(...)`

**VERDICT: BLOCKED — 1 production caller + many test references; redirect to `save_merge_preview` (T9)**

---

### 3.5 `get_topic_research_run_by_id`

**Definitions:**
- `crypto_news_analyzer/domain/repositories.py:714` — ABC: `return None` (no-op base)
- `crypto_news_analyzer/domain/repositories.py:717-718` — `get_topic_research_run` is canonical, delegates: `return self.get_topic_research_run_by_id(run_id)`
- `crypto_news_analyzer/storage/repositories.py:1383-1384` — impl: delegates to `get_topic_research_run`

**Production callers of `get_topic_research_run_by_id` (direct):**
- **NONE** — only called from `get_topic_research_run` alias in same class

**Production callers of canonical `get_topic_research_run`:**
- `crypto_news_analyzer/storage/repositories.py:1329` — `self.get_topic_research_run(run_id)` (within update)
- `crypto_news_analyzer/storage/repositories.py:1381,1384` — delegates

**VERDICT: SAFE TO DELETE `get_topic_research_run_by_id` — zero direct callers; `get_topic_research_run` is canonical**

---

### 3.6 `get_merge_preview_by_id`

**Definitions:**
- `crypto_news_analyzer/domain/repositories.py:744` — ABC: `return None` (no-op base)
- `crypto_news_analyzer/domain/repositories.py:747-748` — `get_merge_preview` is canonical, delegates: `return self.get_merge_preview_by_id(preview_id)`
- `crypto_news_analyzer/storage/repositories.py:1578-1579` — impl: delegates to `get_merge_preview`

**Production callers of `get_merge_preview_by_id` (direct):**
- **NONE** — only called from `get_merge_preview` alias in same class

**Test references:**
- `tests/intelligence/test_topic_findings_api.py:119` — mock defines `get_merge_preview_by_id`

**Production callers of canonical `get_merge_preview`:**
- `crypto_news_analyzer/intelligence/topic_findings.py:201,287,364` — `self.repository.get_merge_preview(...)`
- `crypto_news_analyzer/storage/repositories.py:1579,1625` — `self.get_merge_preview(...)`

**VERDICT: SAFE TO DELETE `get_merge_preview_by_id` — zero direct callers; `get_merge_preview` is canonical**

---

### 3.7 `_json_value` in `storage/repositories.py`

**Definition:**
- `crypto_news_analyzer/storage/repositories.py:1679-1682` — conditional on `self._data.backend == "postgres"` — but BOTH branches return the same expression: `json.dumps(value, ensure_ascii=False)`

**Callers (all in same file):**
- `crypto_news_analyzer/storage/repositories.py:954` — `self._json_value({})`
- `crypto_news_analyzer/storage/repositories.py:1367` — `self._json_value(...)` (used for research run payload)
- `crypto_news_analyzer/storage/repositories.py:1477` — `self._json_value(checkpoint_payload or {})`
- `crypto_news_analyzer/storage/repositories.py:1500` — `self._json_value(checkpoint_payload or {})`
- `crypto_news_analyzer/storage/repositories.py:1522` — `self._json_value(preview.preview_payload)`
- `crypto_news_analyzer/storage/repositories.py:1523` — `self._json_value(source_ids)`
- `crypto_news_analyzer/storage/repositories.py:1665` — return `self._json_value(...)`

**VERDICT: SAFE TO REPLACE — no-op branch (both return same expression); inline `json.dumps(value, ensure_ascii=False)` at all 7 call sites**

---

## 4. DUPLICATE MODEL DEFINITIONS

### 4.1 `ExecutionInfo` duplicate

**models.py definition:**
- `crypto_news_analyzer/models.py:979-1013` — dataclass with `status: str`, `to_dict()`, `from_dict()`

**execution_coordinator.py definition:**
- `crypto_news_analyzer/execution_coordinator.py:73-90` — dataclass with `status: ExecutionStatus` (typed enum), `__post_init__`

**Importers of `models.py` version:**
- **NONE** — zero production importers of `ExecutionInfo` from `models.py`

**Importers of `execution_coordinator.py` version:**
- **NONE** — zero external imports of `ExecutionInfo` from `execution_coordinator.py`
- Internal usage in `execution_coordinator.py` only: `self.current_execution: Optional[ExecutionInfo]` (line 167), instantiations at lines 956, 1927, 2006

**Test references:**
- **NONE** — zero test references beyond `test_main_controller.py` import of `ExecutionMode` (separate symbol)

**VERDICT: SAFE TO DELETE models.py version — zero importers of that duplicate**

---

### 4.2 `ExecutionResult` duplicate

**models.py definition:**
- `crypto_news_analyzer/models.py:1017-1046` — dataclass with `trigger_chat_id`, `report_sent`, `to_dict()`, `from_dict()`

**execution_coordinator.py definition:**
- `crypto_news_analyzer/execution_coordinator.py:94-109` — dataclass with `trigger_type`, `trigger_chat_id`, `report_sent`, `from_dict()`

**Importers of `models.py` version:**
- `tests/shared/test_telegram_command_pbt.py:97-99` — imports `ExecutionResult` from `crypto_news_analyzer.models` and instantiates it as a mock return

**Importers of `execution_coordinator.py` version:**
- **NONE** — zero external imports
- Internal usage in `execution_coordinator.py` only: `self.execution_history: List[ExecutionResult]` (line 168), instantiations at lines 993, 1049, 1750, 1885, 1910, 1993, 2056, 2128, 2196, 2246

**VERDICT: BLOCKED — single test file imports models.py version; redirect to execution_coordinator.py canonical (T14)**

---

### 4.3 `AnalysisResult` duplicate — TWO DISTINCT TYPES (not truly duplicate)

**models.py definition (per-item News analysis):**
- `crypto_news_analyzer/models.py:741-774` — fields: `content_id`, `category`, `confidence`, `reasoning`, `should_ignore`, `key_points`

**domain/models.py definition (job-level result):**
- `crypto_news_analyzer/domain/models.py:690-726` — fields: `success`, `items_processed`, `report_content`, `final_report_messages`, `errors`, `categories_found`

**Importers of `models.py` `AnalysisResult` (per-item):**
- `crypto_news_analyzer/execution_coordinator.py:42-49` — imports `AnalysisResult` from `.models`
- `tests/shared/test_main_controller.py:19` — imports `AnalysisResult` from `crypto_news_analyzer.models`

**Importers of `domain/models.py` `AnalysisResult` (job-level, via `domain/__init__.py`):**
- `crypto_news_analyzer/domain/__init__.py:12` — re-exports `AnalysisResult` from `.models`
- **ZERO production code** imports it from `domain/__init__.py`
- **ZERO test code** imports it from `domain/__init__.py`

**Analysis:**
These are TWO SEMANTICALLY DIFFERENT TYPES that happen to share a name:
- `models.py:AnalysisResult` = per-item news analysis (used by `execution_coordinator.py`)
- `domain/models.py:AnalysisResult` = job-level analysis result payload (unused, exported but never imported)

**VERDICT: SAFE TO RENAME domain/models.py `AnalysisResult` — zero consumers; rename to `JobAnalysisResult` or similar per T14**

---

## 5. DERIVED BOOLEAN FIELDS

### 5.1 `ChatContext.is_private` and `ChatContext.is_group`

**Definition:**
- `crypto_news_analyzer/models.py:949-950` — `is_private: bool`, `is_group: bool` (fields on `ChatContext` class, line 940)

**Construction site (passing values):**
- `crypto_news_analyzer/reporters/telegram_command_handler.py:712-722` — computes `is_private`/`is_group` from `chat_type` and passes as constructor args

**Test references:**
- `tests/telegram-multi-user-authorization/test_task_6_1_chat_context.py:24-185` — 15+ assertions on `is_private`/`is_group` fields
- `tests/telegram-multi-user-authorization/test_task_8_2_handle_status_command.py:98-99` — constructs with `is_private=True, is_group=False`
- `tests/telegram-multi-user-authorization/test_task_8_1_handle_analyze_command.py:74-75` — constructs with booleans
- `tests/telegram-multi-user-authorization/test_task_6_2_extract_chat_context.py:59-245` — 5+ assertions

**VERDICT: BLOCKED — 1 production construction site + 4 test files; convert to @property derived from `chat_type` (T6)**

---

### 5.2 `ValidationResult.is_valid` in `structured_output_manager.py`

**Definition:**
- `crypto_news_analyzer/analyzers/structured_output_manager.py:38` — `is_valid: bool` (field on `ValidationResult` dataclass, line 35)
- `crypto_news_analyzer/analyzers/structured_output_manager.py:1164` — instantiated with `is_valid=False` (validation error path)
- `crypto_news_analyzer/analyzers/structured_output_manager.py:1178-1185` — computed as `len(errors) == 0`, instantiated with `is_valid=is_valid`

**Consumer:**
- `crypto_news_analyzer/analyzers/llm_analyzer.py:1092` — `return validation_result.is_valid` (reads the field)

**Test references:**
- `tests/shared/test_structured_output_manager.py:514` — `ValidationResult(is_valid=True, errors=[], warnings=[])`
- `tests/shared/test_structured_output_manager.py:522` — `ValidationResult(is_valid=False, errors=["错误1", "错误2"], warnings=["警告1"])`

**Note:** `is_valid` also exists on `MarketSnapshot` in `models.py:904` and `market_snapshot_service.py:40` — these are DIFFERENT symbols, NOT covered by this plan (listed as optional/high-risk).

**VERDICT: BLOCKED — 1 production consumer + 2 test references; convert to `@property` derived from `not self.errors` (T6)**

---

## 6. TAG NORMALIZATION

### 6.1 `normalize_datasource_tags` (canonical)

**Definition:**
- `crypto_news_analyzer/datasource_payloads.py:53-55` — `def normalize_datasource_tags(tags: List[str] | None) -> List[str]: ... return sorted(normalized_tags)`

**Callers:**
- `crypto_news_analyzer/datasource_payloads.py:59` — `validate_datasource_tags` calls `normalize_datasource_tags(tags)`

**Test references:**
- **NONE** — zero direct test references to `normalize_datasource_tags` by name (tests call `validate_datasource_tags` which delegates)

### 6.2 `_normalize_datasource_tags` (duplicate in domain/models.py)

**Definition:**
- `crypto_news_analyzer/domain/models.py:196-198` — `def _normalize_datasource_tags(tags: Optional[List[str]]) -> List[str]: ... return sorted(normalized_tags)`

**Callers (all within same file):**
- `crypto_news_analyzer/domain/models.py:231` — `DataSource.__post_init__`: `self.tags = _normalize_datasource_tags(self.tags)`
- `crypto_news_analyzer/domain/models.py:318` — `SafeDataSourceSummary.__post_init__`: `self.tags = _normalize_datasource_tags(self.tags)`

**Test references:**
- **NONE** — zero direct test references

**Analysis:** The two implementations are IDENTICAL (both do `{str(tag).strip().lower() for tag in (tags or []) if str(tag).strip()}`, `return sorted(...)`). The canonical one is in `datasource_payloads.py`; the duplicate is private in `domain/models.py`.

**VERDICT: SAFE TO REPLACE — redirect 2 call sites in domain/models.py to use the canonical `datasource_payloads.normalize_datasource_tags` (T7)**

---

## 7. RUNTIME / CONFIG

### 7.1 `run_analysis_service`

**Definition:**
- `crypto_news_analyzer/main.py:156-182` — sets `CRYPTO_NEWS_RUNTIME_MODE = "analysis-service"`, creates API server with `start_services=False, start_scheduler=False, start_command_listener=True`

**Callers:**
- `crypto_news_analyzer/main.py:89` — `exit_code = run_analysis_service(args.config)` (in main dispatch for `analysis-service` mode)

**Test references:**
- `tests/shared/test_ingestion_runtime.py:185-220` — `test_run_analysis_service_starts_telegram_without_scheduler(monkeypatch)` calls `main.run_analysis_service("./custom-config.jsonc")`

**VERDICT: BLOCKED — 1 dispatch caller + 1 test; merge with `run_api_only_service` into unified `_run_api_service` (T10)**

---

### 7.2 `run_api_only_service`

**Definition:**
- `crypto_news_analyzer/main.py:120-153` — sets `CRYPTO_NEWS_RUNTIME_MODE = "api-only"`, creates API server with `start_services=False`

**Callers:**
- `crypto_news_analyzer/main.py:92` — `exit_code = run_api_only_service(args.config)` (in main dispatch for `api-only` mode)

**Test references:**
- `tests/shared/test_ingestion_runtime.py:135-172` — `test_run_api_only_service_sets_api_only_runtime_and_keeps_services_stopped(...)` calls `main.run_api_only_service("./custom-config.jsonc")`

**VERDICT: BLOCKED — 1 dispatch caller + 1 test; merge with `run_analysis_service` (T10)**

---

### 7.3 `run_ingestion_service`

**Definition:**
- `crypto_news_analyzer/main.py:231-245` — thin wrapper: `return run_ingestion_loop(config_path)`

**Callers:**
- `crypto_news_analyzer/main.py:95` — `exit_code = run_ingestion_service(args.config)` (in main dispatch for `ingestion` mode)

**Test references:**
- `tests/shared/test_ingestion_runtime.py:120-129` — `test_run_ingestion_service_delegates_to_ingestion_loop(monkeypatch)` calls `main.run_ingestion_service("custom-config.jsonc")`

**VERDICT: BLOCKED — 1 dispatch caller + 1 test; replace with direct `run_ingestion_loop` call (T10)**

---

### 7.4 `create_api_server`

**Definition:**
- `crypto_news_analyzer/api_server.py:2401` — `def create_api_server(config_path, start_services, start_scheduler, start_command_listener, ...)`

**Production callers:**
- `crypto_news_analyzer/main.py:134` — imports `create_api_server` from `.api_server`
- `crypto_news_analyzer/main.py:142` — `app = create_api_server(config_path, start_services=False)` (api-only)
- `crypto_news_analyzer/main.py:159` — imports `create_api_server` from `.api_server`
- `crypto_news_analyzer/main.py:166` — `app = create_api_server(config_path, start_services=False, start_scheduler=False, start_command_listener=True)` (analysis-service)
- `scripts/dump_routes.py:34,36` — imports and calls `create_api_server(..., start_services=False)` for route dump

**Test callers:**
- `tests/news/test_api_server.py:378` — `api_server.create_api_server(..., start_services=False)`
- `tests/news/test_api_server.py:1076,1098,1118` — 3 tests named `test_create_api_server_lifespan_*`
- `tests/news/test_api_server_semantic_search.py:165` — `api_server.create_api_server("./config.jsonc", start_services=False)`
- `tests/shared/test_ingestion_runtime.py:149,168,197,216` — mock patches for `create_api_server`
- `tests/intelligence/test_topic_findings_api.py:630` — `api_server.create_api_server(...)`
- `tests/intelligence/test_intelligence_security_guardrails.py:104` — `api_server.create_api_server(...)`
- `tests/intelligence/test_topic_datasource_api.py:283` — `api_server.create_api_server(...)`

**VERDICT: BLOCKED — signature simplification per T11 requires updating 3 production files + 6 test files**

---

### 7.5 `TELEGRAM_WEBHOOK_PATH` env var reads

**Read sites:**
- `crypto_news_analyzer/api_server.py:2355` — `@app.post(os.getenv("TELEGRAM_WEBHOOK_PATH", "/telegram/webhook"))` (FastAPI route decorator)
- `crypto_news_analyzer/reporters/telegram_command_handler.py:175` — `path = os.getenv("TELEGRAM_WEBHOOK_PATH", "/telegram/webhook").strip()` (webhook URL builder)

**Test references:**
- `tests/news/test_api_server.py:1146,1167` — `monkeypatch.setenv("TELEGRAM_WEBHOOK_PATH", "/telegram/webhook")`
- `tests/shared/test_openclaw_skill_smart_news.py:399` — mentions `TELEGRAM_WEBHOOK_PATH` in a string literal

**Docs references:**
- `skills/smart-news/references/operations-and-maintenance.md:21` — documents the env var usage

**Deployment files:**
- No references in `Dockerfile`, `docker-entrypoint.sh`, or `README.md`

**VERDICT: SAFE TO EXTRACT AS CONSTANT — 2 production reads of the same default; extract to single constant (T10/T11)**

---

## 8. SERVICE FACTORY DUPLICATION

### 8.1 `_get_topic_prompt_workflow_service`

**Definitions (2 locations):**
1. `crypto_news_analyzer/api_server.py:1076-1100` — module-level helper, takes `(controller, repository)`, extracts llm info from `controller.llm_analyzer.analysis_model_runtime.model_name`
2. `crypto_news_analyzer/reporters/telegram_command_handler.py:1679-1706` — instance method of `TelegramCommandHandler`, no params, reads from `self.execution_coordinator`, caches on controller

**Callers (api_server.py):**
- `crypto_news_analyzer/api_server.py:1769` — `service = _get_topic_prompt_workflow_service(controller, repository)`
- `crypto_news_analyzer/api_server.py:1815` — `service = _get_topic_prompt_workflow_service(controller, repository)`
- `crypto_news_analyzer/api_server.py:1846` — `service = _get_topic_prompt_workflow_service(controller, repository)`
- `crypto_news_analyzer/api_server.py:1883` — `service = _get_topic_prompt_workflow_service(controller, repository)`

**Callers (telegram_command_handler.py):**
- `crypto_news_analyzer/reporters/telegram/intelligence_commands.py:273` — `self._get_topic_prompt_workflow_service()` (via `self` = handler)
- `crypto_news_analyzer/reporters/telegram/intelligence_commands.py:326` — same
- `crypto_news_analyzer/reporters/telegram/intelligence_commands.py:404` — same
- `crypto_news_analyzer/reporters/telegram/intelligence_commands.py:446` — same

**Test references:**
- `tests/intelligence/test_intelligence_telegram_commands.py:107` — `handler._get_topic_prompt_workflow_service = Mock(return_value=service)`
- `tests/intelligence/test_topic_findings_telegram.py:103` — `patch.object(handler, "_get_topic_prompt_workflow_service", ...)`
- `tests/intelligence/test_topic_findings_telegram.py:401,435` — `handler._get_topic_prompt_workflow_service = Mock(...)`

**VERDICT: BLOCKED — consolidate 2 definitions into shared helper module (T8)**

---

### 8.2 `_get_topic_finding_merge_service`

**Definitions (2 locations):**
1. `crypto_news_analyzer/api_server.py:1103-1127` — module-level helper, takes `(controller, repository)`, returns `TopicFindingMergeService`
2. `crypto_news_analyzer/reporters/telegram_command_handler.py:1708-1734` — instance method, constructs with `intelligence_repository=repository`, `model_name` derived differently

**Callers (api_server.py):**
- `crypto_news_analyzer/api_server.py:852` — `merge_service = _get_topic_finding_merge_service(controller, repository)`

**Callers (telegram_command_handler.py):**
- `crypto_news_analyzer/reporters/telegram/intelligence_commands.py:517` — `merge_service = self._get_topic_finding_merge_service()`

**Test references:**
- `tests/intelligence/test_topic_findings_telegram.py:260` — `patch.object(handler, "_get_topic_finding_merge_service", ...)`
- `tests/intelligence/test_topic_findings_telegram.py:296` — `patch.object(handler, "_get_topic_finding_merge_service", ...)`

**VERDICT: BLOCKED — consolidate 2 definitions into shared helper module (T8)**

---

## 9. CROSS-CUTTING SUMMARY

### 9.1 `Dockerfile` references
- `Dockerfile:83` — references `execution_coordinator.MainController` (NOT a removal target — MainController is kept)

### 9.2 `docker-entrypoint.sh` references
- **NONE** — zero references to any planned removal symbols

### 9.3 `README.md` references
- `README.md:22` — mentions `/news_semantic_search` as deprecated alias (T13 removal target)
- `README.md:51` — mentions `execution_coordinator.py` in directory tree (NOT a removal target)
- `README.md:251` — `/news_semantic_search <hours> <topic> - 已弃用别名` (T13 removal target)

### 9.4 `docs/` references (beyond plan documents)
- `docs/ARCHITECTURE_BOUNDARIES.md:23,89,138` — mentions `/news_semantic_search` as deprecated alias (T13)
- `docs/ARCHITECTURE_BOUNDARIES.md:70` — mentions `execution_coordinator.py` (NOT a removal target)
- `docs/ARCHITECTURE_BOUNDARIES.md:20` — mentions `AnalysisResult` in data models list (ambiguous — T14)
- `docs/TOPIC_LIFECYCLE.md:176` — mentions `is_active` (T2)
- `docs/plans/remove-is_active-redundancy.md` — comprehensive removal plan (expected, safe)

### 9.5 `skills/` references
- `skills/smart-news/references/semantic-search.md:154` — mentions `/news_semantic_search` as deprecated alias (T13)
- `skills/smart-news/references/intelligence-query.md:204` — JSON example with `"is_active": true` (T2/T4)
- `skills/smart-news/references/operations-and-maintenance.md:21` — documents `TELEGRAM_WEBHOOK_PATH` (T10/T11)

### 9.6 `AGENTS.md` references
- `AGENTS.md:36,50` — mentions `/news_semantic_search` as deprecated alias (T13)

---

## 10. FINAL VERDICT SUMMARY

| Symbol | Verdict |
|--------|---------|
| `TopicLifecycleStatus.PAUSED` | BLOCKED — 3 production + 1 test + docs |
| `IntelligenceTopic.is_active` | BLOCKED — 8 production files + 6 tests + 2 docs |
| `MergePreviewState.EXPIRED` | **SAFE** — zero callers use enum constant |
| `load_auth_from_env` | **SAFE** — zero callers |
| `run_due_topics` | **SAFE** — zero callers |
| `ExecutionMode` | **SAFE** — 1 test import to update |
| `plugin_system_example.py` | **SAFE** — zero imports |
| `create_topic_prompt_version` | BLOCKED — 6 production callers |
| `create_topic_finding` | BLOCKED — 2 production + 5+ test callers |
| `create_topic_research_run` | BLOCKED — 1 production caller |
| `create_merge_preview` | BLOCKED — 1 production + many test callers |
| `get_topic_research_run_by_id` | **SAFE** — zero direct callers |
| `get_merge_preview_by_id` | **SAFE** — zero direct callers |
| `_json_value` no-op | **SAFE** — can inline at 7 call sites |
| `ExecutionInfo` (`models.py`) | **SAFE** — zero importers |
| `ExecutionResult` (`models.py`) | BLOCKED — 1 test file imports it |
| `AnalysisResult` (`domain/models.py`) | **SAFE** — zero consumers; rename only |
| `ChatContext.is_private/is_group` | BLOCKED — 1 production + 4 test files |
| `ValidationResult.is_valid` | BLOCKED — 1 production consumer + 2 tests |
| `_normalize_datasource_tags` | **SAFE** — duplicate; redirect 2 call sites |
| `run_analysis_service` | BLOCKED — merge into unified wrapper |
| `run_api_only_service` | BLOCKED — merge into unified wrapper |
| `run_ingestion_service` | BLOCKED — replace with direct call |
| `create_api_server` params | BLOCKED — 3 production + 6 test call sites |
| `TELEGRAM_WEBHOOK_PATH` default | **SAFE** — extract as constant |
| `_get_topic_prompt_workflow_service` (2 defs) | BLOCKED — consolidate 4 + 4 callers |
| `_get_topic_finding_merge_service` (2 defs) | BLOCKED — consolidate 1 + 1 callers |
