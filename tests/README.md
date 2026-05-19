# Test Organization by Domain

This directory contains tests organized by the dual-domain architecture.

## Directory Structure

```
tests/
├── conftest.py          # Shared pytest fixtures (top-level for visibility)
├── __init__.py
├── helpers/             # Test helper utilities
├── integration/         # Integration tests
├── telegram-multi-user-authorization/
├── news/               # News domain tests
├── intelligence/       # Intelligence domain tests
└── shared/             # Shared infrastructure tests
```

## Domain Groupings

### News Domain (`tests/news/`)

Tests for RSS/X/REST crawling, LLM analysis, structured reports, and semantic search.

- `test_llm_analyzer.py` - LLM analyzer and four-step analysis
- `test_rss_crawler.py` - RSS feed crawler
- `test_report_generator.py` - Markdown report generation
- `test_api_server.py` - FastAPI analyze endpoints
- `test_api_server_semantic_search.py` - Semantic search endpoints
- `test_telegram_command_handler_analyze.py` - Telegram /news_analyze command
- `test_telegram_command_handler_semantic_search.py` - Telegram /news_semantic_search command
- `test_telegram_report_properties.py` - Report delivery properties
- `test_embedding_service.py` - Embedding service
- `test_semantic_search_service.py` - Semantic search service
- `test_category_parser.py` - Category parsing

### Intelligence Domain (`tests/intelligence/`)

Tests for Telegram/V2EX collection, topic research pipeline, and AI prompt lifecycle.

- `test_intelligence_telegram_commands.py` - Intelligence Telegram commands
- `test_intelligence_ttl.py` - TTL management
- `test_intelligence_models.py` - Intelligence domain models
- `test_intelligence_repositories.py` - Repository implementations
- `test_intelligence_extraction.py` - Entry extraction
- `test_intelligence_semantic_search.py` - Intelligence semantic search
- `test_intelligence_security_guardrails.py` - Security checks
- `test_intelligence_api.py` - Intelligence REST API
- `test_intelligence_ingestion_runtime.py` - Intelligence ingestion runtime
- `test_intelligence_datasource_payloads.py` - Datasource payloads
- `test_intelligence_config.py` - Intelligence configuration
- `test_intelligence_v2ex_collector.py` - V2EX collector
- `test_intelligence_telegram_collector.py` - Telegram collector
- `test_topic_prompt_workflow.py` - Topic prompt workflow
- `test_topic_research_scheduler.py` - Topic research scheduler
- `test_topic_findings_telegram.py` - Topic findings Telegram delivery
- `test_topic_findings_api.py` - Topic findings API
- `test_raw_message_retention.py` - Raw message retention
- `test_intelligence_merge.py` - Finding merge operations

### Shared Infrastructure (`tests/shared/`)

Tests for shared components used by both domains: config, storage, data sources, execution coordinator, cache, etc.

- `test_data_source_factory.py` - DataSource factory
- `test_config_manager.py` - ConfigManager
- `test_ingestion_runtime.py` - Ingestion runtime
- `test_datasource_bootstrap.py` - Datasource bootstrap
- `test_datasource_repository.py` - Datasource repository
- `test_data_storage_properties.py` - Storage properties
- `test_main_controller.py` - MainController
- `test_execution_coordinator_cache_integration.py` - Execution coordinator cache
- `test_ingestion_jobs.py` - Ingestion jobs
- `test_cache_manager.py` - Cache manager
- `test_cache_manager_properties.py` - Cache properties
- `test_llm_registry.py` - LLM registry
- `test_llm_analyzer_cache_integration.py` - LLM analyzer cache
- `test_structured_output_manager.py` - Structured output manager
- `test_semantic_search_storage.py` - Semantic search storage
- `test_semantic_search_contracts.py` - Semantic search contracts
- `test_telegram_command_handler_datasource.py` - Telegram datasource commands
- `test_telegram_formatter.py` - Telegram formatter
- `test_telegram_sender.py` - Telegram sender
- `test_telegram_sending_reliability_properties.py` - Telegram reliability
- `test_telegram_real_config.py` - Real Telegram config
- `test_telegram_command_pbt.py` - Property-based tests for Telegram commands
- `test_timezone_utils.py` - Timezone utilities
- `test_timezone_integration.py` - Timezone integration
- `test_config_file_management_properties.py` - Config file management
- `test_config_persistence_properties.py` - Config persistence
- `test_dynamic_classification_manager.py` - Dynamic classification
- `test_embedding_backfill_mode.py` - Embedding backfill mode
- `test_extensibility_unit.py` - Extensibility tests
- `test_multi_step_analysis_unit.py` - Multi-step analysis unit
- `test_multi_step_analysis_properties.py` - Multi-step analysis properties
- `test_bird_dependency_unit.py` - Bird dependency
- `test_bird_integration_properties.py` - Bird integration
- `test_rss_content_parsing_properties.py` - RSS content parsing
- `test_analyze_time_window_override_regression.py` - Time window override
- `test_banned_legacy_reference_scan.py` - Legacy reference scan
- `test_docker_entrypoint_legacy_alias_rejection.py` - Docker entrypoint
- `test_postgres_storage_path.py` - Postgres storage path
- `test_openclaw_skill_smart_news.py` - Openclaw smart-news skill
- `test_opencode_skill_crypto_news_debug.py` - Opencode skill
- `test_logging_redaction.py` - Logging redaction
- `test_run_wrapper.py` - Run wrapper
- `test_next_execution_time_fix.py` - Next execution time