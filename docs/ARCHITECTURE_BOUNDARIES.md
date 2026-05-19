# Architecture Boundaries: News and Intelligence Domains

Canonical reference for human developers and AI coding agents working on this codebase. This document defines what the domain boundaries are, what infrastructure they share, what surfaces remain invariant, and what is in/out of scope for the current boundary-refactoring work.

## Dual-Domain Overview

The `crypto_news_analyzer` package is a **single-package, dual-domain monorepo**. Two bounded contexts coexist in one codebase, sharing infrastructure but maintaining strict separation at the model, pipeline, and command/API surface levels.

### News Domain

**Purpose:** Crawl crypto news from public sources, produce structured analysis reports, and serve them via HTTP API and Telegram.

**Data flow:**

```
RSS/X/REST → ContentItem → LLMAnalyzer → ReportGenerator (Markdown)
```

- **Source types:** `rss`, `x`, `rest_api` (all tagged with `DataSourcePurpose.NEWS`)
- **Primary data models:** `ContentItem`, `AnalysisResult`
- **Primary modules:** `analyzers/`, `reporters/`, `semantic_search/`, `crawlers/`
- **API surfaces:** `POST /analyze`, `POST /semantic-search`, `GET/POST/DELETE /datasources`
- **Telegram commands:** `/news_analyze`, `/news_market`, `/news_semantic_search`, `/news_tokens`, `/datasource_*`

### Intelligence Domain

**Purpose:** Collect group/forum messages from Telegram and V2EX, drive topic-driven AI research, and manage a prompt lifecycle that produces structured findings.

**Data flow:**

```
Telegram/V2EX → RawIntelligenceItem → TopicResearchScheduler → TopicFinding
```

- **Source types:** `telegram_group`, `v2ex` (all tagged with `DataSourcePurpose.INTELLIGENCE`)
- **Primary data models:** `RawIntelligenceItem`, `IntelligenceTopic`, `TopicPrompt`, `TopicFinding`, `TopicResearchRun`
- **Primary modules:** `intelligence/` (pipeline, topics, topic_prompts, topic_research, topic_findings, merge, search, topic_enricher)
- **API surfaces:** `/intelligence/*` (topics CRUD, revise, confirm, merge-preview, merge-accept)
- **Telegram commands:** `/topic_create`, `/topic_revise`, `/topic_set_prompt`, `/topic_confirm`, `/topic_list`, `/topic_detail`, `/topic_merge`, `/topic_pause`, `/topic_archive`, `/topic_logs`

### Critical Boundary Rule

**Never mix `ContentItem` with `RawIntelligenceItem`.** These models belong to different domains. Do not pass one where the other is expected. Do not couple their pipelines. Do not write code that cross-references them.

The `ingestion` runtime mode runs both domains' collection loops and the Intelligence daily topic research scheduler. They execute as parallel concerns, not as alternatives or sub-components of each other.

### Legacy Note

The old entry-based intelligence pipeline (`EntryType`, `ExtractionObservation`, `CanonicalIntelligenceEntry`, `/intel_*` commands) is deprecated and exists only for backward compatibility. These models are not wired into the active runtime. The active Intelligence path is topic-only.

## Shared Infrastructure

Both domains share the following infrastructure, which must remain domain-agnostic:

| Component | Role | Domain Awareness |
|---|---|---|
| PostgreSQL + pgvector | Shared database for all content, topics, findings, jobs, and config | None — table-level separation |
| `config/manager.py` | Env + `config.jsonc` loading and normalization | None — generic config |
| `models.py` | Shared data/config/result Pydantic models | Knows both domains but treats them as separate model trees |
| `domain/models.py` + `domain/repositories.py` | Domain model definitions and repository interfaces | Defines interfaces for both domains |
| `storage/repositories.py` | SQLite/Postgres repository implementations | Implements both domains' repository interfaces |
| `execution_coordinator.py` | MainController for analysis-service and ingestion flows | Orchestrates both domains' scheduled tasks |
| `api_server.py` | FastAPI app factory with shared middleware, auth, /health | Mounts routes for both domains |
| Reporter / Telegram bot | Shared Telegram `Application` and command router | Dispatches commands to domain-specific handlers |
| LLM + embedding providers | Shared provider abstractions (`utils/llm_provider.py`) | Generic — domain-agnostic API calls |
| DataSourceFactory | Creates crawler/collector instances by type | Routes to domain-specific implementations by `DataSourcePurpose` |
| `utils/` | Logging, errors, time, async helpers | None — generic utilities |

## Compatibility Contract

The following surfaces are **invariant** under the current boundary-refactoring work. They must continue to work identically:

### HTTP Endpoints
- `POST /analyze`, `GET /analyze/{job_id}`, `GET /analyze/{job_id}/result` — unchanged
- `POST /semantic-search`, `GET /semantic-search/{job_id}`, `GET /semantic-search/{job_id}/result` — unchanged
- `GET/POST/DELETE /datasources` — unchanged
- `POST /intelligence/topics`, `GET /intelligence/topics`, `GET /intelligence/topics/{id}`, etc. — unchanged
- `GET /health` — unchanged

### Telegram Commands
- News: `/news_analyze`, `/news_market`, `/news_semantic_search`, `/news_tokens`, `/datasource_list`, `/datasource_add`, `/datasource_delete`, `/status`, `/help` — unchanged
- Intelligence: `/topic_create`, `/topic_revise`, `/topic_set_prompt`, `/topic_confirm`, `/topic_list`, `/topic_detail`, `/topic_merge`, `/topic_pause`, `/topic_archive`, `/topic_logs` — unchanged

### CLI Runtime Modes
- `--mode analysis-service` — unchanged
- `--mode api-only` — unchanged
- `--mode ingestion` — unchanged
- `--mode embedding-backfill` — unchanged
- Legacy `api-server` — deprecated compatibility alias, unchanged

### Environment Variables
All shared and domain-specific env vars remain unchanged: `DATABASE_URL`, `API_KEY`, `KIMI_API_KEY`, `GROK_API_KEY`, `OPENCODE_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHANNEL_ID`, `TELEGRAM_AUTHORIZED_USERS`, `X_CT0`, `X_AUTH_TOKEN`, `EXECUTION_INTERVAL`, `TIME_WINDOW_HOURS`, `LOG_LEVEL`, `CONFIG_PATH`, `API_HOST`, `API_PORT`.

### Database
- Single shared PostgreSQL + pgvector database — no DB split
- All existing tables, schemas, and migrations remain unchanged
- `datasources` and `datasource_tags` tables remain the shared source of truth for both domains

### Config Format
- `config.jsonc` format unchanged
- Data source bootstrap from `config.jsonc` on first startup unchanged

## Scope (This Refactor)

### Phase 1: Documentation (current)

- `AGENTS.md`: Updated with `## Dual-Domain Architecture` table and `## Agent Boundary Rules`
- `README.md`: Updated with dual-domain monorepo description, peer Intelligence domain in features and repository structure
- `docs/ARCHITECTURE_BOUNDARIES.md` (this document): Canonical boundary reference for humans and AI agents

### Phase 2: Low-Risk Code Grouping (future)

Potential low-risk improvements that respect the compatibility contract:

- Group domain-specific modules under clear namespace prefixes (e.g., ensure `intelligence/` modules are self-contained with no News imports)
- Add domain-specific type stubs or `__init__.py` re-exports that make the boundary visible at the import level
- Consolidate domain-specific error types in sub-packages (e.g., `intelligence/errors.py`, `analyzers/errors.py`)
- Add boundary lint rules (e.g., custom flake8 plugin or import-linter config) to enforce domain separation

None of these changes would alter any endpoint, command, config, or env var surface.

## Out of Scope

The following refactors are explicitly **out of scope**. This means: no repo split, no DB split, no service split, no endpoint rename, no Telegram command rename, and no config format change. They are not part of this work, and no code or documentation should assume or recommend them:

- **Full repository split:** The codebase remains a single package. No separate repos for News and Intelligence.
- **Database split:** Both domains continue to share one PostgreSQL + pgvector database. No per-domain database.
- **Service split:** The two Railway services (`crypto-news-analysis`, `crypto-news-ingestion`) remain as-is. No per-domain service (e.g., no separate `crypto-news-intelligence` service).
- **Endpoint renames or removals:** No URL path changes, no command renames, no API surface restructuring.
- **Telegram command renames:** News commands use `/news_` prefix (`/news_analyze`, `/news_market`, `/news_semantic_search`, `/news_tokens`). Intelligence commands use `/topic_` prefix. No further renames.
- **Config format changes:** `config.jsonc` structure remains as-is. No new top-level keys or format migration.
- **MainController extraction:** `execution_coordinator.py` remains the shared orchestrator. No extraction into per-domain controllers.
- **Shared module splits:** `storage/`, `models.py`, `domain/`, `utils/` remain shared. No per-domain fork of these.
- **New runtime modes:** No new `--mode` values. The existing four modes are sufficient.
- **Auth model changes:** The Bearer token auth model and `API_KEY` env var remain the sole auth mechanism for HTTP APIs.
- **Deployment topology changes:** The Railway split-service deployment topology (two app services, one database) remains unchanged.
- **Migration of legacy intelligence:** The deprecated entry-based pipeline stays as-is. No effort to extract, modernize, or remove it.
