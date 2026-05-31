## 2026-05-03 Task 12

- `uv` was missing from the shell environment and was installed to `/data/.local/bin/uv`; commands in this session used that absolute path.

## 2026-05-03 Task 13

- Initial `test_env_template_contains_no_real_secrets` was too strict — flagged legitimate config defaults (DATABASE_URL, LOG_LEVEL, API_HOST, etc.) as non-placeholder violations. Refined to only flag lines with secret-indicator keys (KEY, TOKEN, SECRET, SESSION, PAT, AUTH, PASSWORD) plus pattern-based checks for Telethon sessions and V2EX PAT.
- 67 pre-existing test failures confirmed across unrelated test modules (category_parser, bird_dependency, config_manager/extensibility, report_generator, telegram_formatter, timezone_integration, semantic_search_service, etc.). None are caused by intelligence changes.
- No new tests or failures introduced by intelligence work.

## 2026-05-03 F2 code-quality review
- REJECT: IntelligencePipeline passes repository kwargs into DataSourceFactory.create_source, but V2EXIntelligenceCrawler.__init__ does not accept **kwargs, so real v2ex pipeline creation fails before crawl. Existing tests use FakeFactory and miss this integration.
- API raw TTL handling mixes timezone-aware datetime.now(timezone.utc) with crawler/model naive datetime.utcnow values, risking TypeError in /intelligence/raw and include_raw comparisons.
- LSP diagnostics showed no errors but many warnings around Any-heavy protocols, deprecated UTC helpers, unused imports, and unannotated attributes.
- Intelligence test suite passed: 94 passed, 7 skipped. Tests are assertion-heavy with no assert True placeholders, but they miss real factory-to-v2ex pipeline coverage and naive/aware API raw expiry coverage.

## 2026-05-03 F4 scope-fidelity check

- REJECT: V2EX remains wired into the intelligence pipeline through DataSourceFactory with repository kwargs, but V2EXIntelligenceCrawler.__init__ does not accept those kwargs; real v2ex collection can fail before crawl despite unit tests passing.
- REJECT: GET /intelligence/raw/{raw_item_id} returns raw_text even when expires_at is already expired, conflicting with the plan contract that exact raw text is returned only while raw TTL is valid.
- Positive fidelity checks: migration 003 has the requested 6 intelligence tables, intelligence HTTP surface has the 4 requested endpoints, Telegram registers the 3 requested /intel_* commands, slang is modeled as entry_type=slang, and merge logic only canonicalizes by exact normalized key while semantic similarity saves related candidates.

## 2026-05-03 F3 Manual QA
- Intelligence suite: `uv run pytest tests/test_intelligence_*.py -v` passed (92 passed).
- Broad suite command completed with 67 failures / 857 passed / 7 skipped; last lines show timezone integration report-header assertions failing. Baseline/new status was not provable from this run alone.
- Mypy first 10 lines show existing type errors starting in `crypto_news_analyzer/models.py` and utils modules.
- Import integrity check failed: `IntelligenceSearchService` is not exported from `crypto_news_analyzer.intelligence`.
- `.env.template` contains an Intelligence Collection section with commented empty placeholders for Telethon and V2EX credentials only.
- LSP diagnostics on package reported many warnings/diagnostics and basedpyright errors in coordinator output.

## 2026-05-03 Final verification wave fixes

- Expired raw intelligence evidence must never return `raw_text` from HTTP raw endpoints; API TTL checks now normalize aware DB/test timestamps to naive UTC before comparing against `datetime.utcnow()`.
- Raw-text purge should key off `expires_at`, not `collected_at`, and should null the text so purged rows remain readable by domain models.
- `V2EXIntelligenceCrawler` must tolerate factory kwargs (`repository` / `intelligence_repository`) like the Telegram crawler path.

## 2026-05-03 F3 re-review

- REJECT: `uv run pytest tests/test_intelligence_*.py -v` passed (92 passed), and the expired raw regression also passed, but `python3 -c "from crypto_news_analyzer.intelligence import IntelligenceMergeEngine, IntelligenceSearchService, IntelligencePipeline"` still fails because `IntelligencePipeline` is not exported from `crypto_news_analyzer.intelligence`.
