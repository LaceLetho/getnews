import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = REPO_ROOT / "skills" / "crypto-news-http-api"
REFERENCE_DIR = SKILL_DIR / "references"
SKILL_PATH = SKILL_DIR / "SKILL.md"
ANALYZE_WORKFLOW_PATH = REFERENCE_DIR / "analyze-workflow.md"
DATASOURCE_MANAGEMENT_PATH = REFERENCE_DIR / "datasource-management.md"
OPERATIONS_AND_MAINTENANCE_PATH = REFERENCE_DIR / "operations-and-maintenance.md"
SEMANTIC_SEARCH_PATH = REFERENCE_DIR / "semantic-search.md"


def _read_text(path: Path) -> str:
    assert path.exists(), f"Required file not found: {path}"
    return path.read_text(encoding="utf-8")


def _split_frontmatter(text: str) -> tuple[dict[str, str], str]:
    assert text.startswith("---\n"), "Skill file must start with YAML frontmatter"

    parts = text.split("---\n", 2)
    assert len(parts) == 3, "Skill file must contain opening and closing frontmatter markers"

    frontmatter_text = parts[1].strip()
    body = parts[2].strip()
    frontmatter: dict[str, str] = {}

    for line in frontmatter_text.splitlines():
        if not line.strip():
            continue
        key, sep, value = line.partition(":")
        assert sep, f"Invalid frontmatter line: {line}"
        frontmatter[key.strip()] = value.strip()

    assert body, "Skill body must not be empty"
    return frontmatter, body


def _section(body: str, heading: str) -> str:
    marker = f"## {heading}\n"
    start = body.find(marker)
    assert start != -1, f"Missing section: {heading}"
    start += len(marker)

    next_start = body.find("\n## ", start)
    if next_start == -1:
        return body[start:].strip()
    return body[start:next_start].strip()


def test_skill_paths_target_crypto_news_http_api_files() -> None:
    assert SKILL_DIR == REPO_ROOT / "skills" / "crypto-news-http-api"
    assert REFERENCE_DIR == SKILL_DIR / "references"
    assert SKILL_PATH == SKILL_DIR / "SKILL.md"
    assert ANALYZE_WORKFLOW_PATH == REFERENCE_DIR / "analyze-workflow.md"
    assert DATASOURCE_MANAGEMENT_PATH == REFERENCE_DIR / "datasource-management.md"
    assert OPERATIONS_AND_MAINTENANCE_PATH == REFERENCE_DIR / "operations-and-maintenance.md"
    assert SEMANTIC_SEARCH_PATH == REFERENCE_DIR / "semantic-search.md"

    for path in [
        SKILL_PATH,
        ANALYZE_WORKFLOW_PATH,
        DATASOURCE_MANAGEMENT_PATH,
        OPERATIONS_AND_MAINTENANCE_PATH,
        SEMANTIC_SEARCH_PATH,
    ]:
        assert path.exists(), f"Missing shipped skill file: {path}"


def test_skill_requires_frontmatter_required_sections_and_reference_links() -> None:
    frontmatter, body = _split_frontmatter(_read_text(SKILL_PATH))

    assert frontmatter.get("name") == "crypto-news-http-api"
    assert (
        frontmatter.get("description")
        == "Use when calling the Crypto News Analyzer HTTP API for async analysis jobs, semantic search, datasource management, or health checks from OpenClaw."
    )
    assert "primaryEnv: API_KEY" in frontmatter.get("metadata", "")
    assert body.startswith("# Crypto News HTTP API Skill")

    for heading in [
        "When to Use",
        "Quick Reference",
        "OpenClaw Runtime",
        "Analyze Workflow",
        "Semantic Search",
        "Datasource Management",
        "Telegram Webhook",
        "Endpoint Index",
        "Non-Goals",
        "Updating",
    ]:
        assert _section(body, heading)

    for reference in [
        "references/analyze-workflow.md",
        "references/semantic-search.md",
        "references/datasource-management.md",
        "references/operations-and-maintenance.md",
    ]:
        assert reference in body, f"Missing reference-file pointer: {reference}"


def test_skill_endpoint_index_lists_only_supported_live_http_routes() -> None:
    _frontmatter, body = _split_frontmatter(_read_text(SKILL_PATH))
    endpoint_index = _section(body, "Endpoint Index")

    for endpoint in [
        "GET /health",
        "POST /analyze",
        "GET /analyze/{job_id}",
        "GET /analyze/{job_id}/result",
        "POST /semantic-search",
        "GET /semantic-search/{job_id}",
        "GET /semantic-search/{job_id}/result",
        "POST /datasources",
        "GET /datasources",
        "DELETE /datasources/{id}",
        "POST /telegram/webhook",
    ]:
        assert endpoint in endpoint_index, f"Missing supported endpoint: {endpoint}"

    for unsupported_surface in [
        "api-server",
        "crypto-news-api",
        "/run",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/swagger-ui",
        "/status",
        "/tokens",
        "/help",
        "/market",
        "/datasource_list",
        "/datasource_add",
        "/datasource_delete",
    ]:
        assert unsupported_surface not in endpoint_index, (
            "Unsupported surface must not be listed as a supported HTTP endpoint: "
            f"{unsupported_surface}"
        )


def test_skill_non_goals_explicitly_exclude_deprecated_and_telegram_flows() -> None:
    _frontmatter, body = _split_frontmatter(_read_text(SKILL_PATH))
    non_goals = _section(body, "Non-Goals")

    for exclusion in [
        "Telegram slash commands",
        "/docs",
        "/redoc",
        "/openapi.json",
        "api-server",
        "crypto-news-api",
    ]:
        assert exclusion in non_goals, f"Missing exclusion: {exclusion}"


def test_skill_body_is_practically_english_only() -> None:
    _frontmatter, body = _split_frontmatter(_read_text(SKILL_PATH))

    assert not re.search(r"[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]", body), (
        "Skill body must not contain CJK characters"
    )


def test_skill_quick_reference_covers_bearer_auth_and_async_workflow() -> None:
    _frontmatter, body = _split_frontmatter(_read_text(SKILL_PATH))
    quick_reference = _section(body, "Quick Reference")

    for expected in [
        "Authorization: Bearer <API_KEY>",
        "`POST /analyze` creates a job and returns immediately",
        "does **not** return the final report",
        "Workflow: `POST /analyze` -> `GET /analyze/{job_id}` -> `GET /analyze/{job_id}/result`",
        "`POST /semantic-search` creates a job",
        "Semantic workflow: `POST /semantic-search` -> `GET /semantic-search/{job_id}` -> `GET /semantic-search/{job_id}/result`",
        "`Retry-After`",
        "PostgreSQL with pgvector",
        "`queued`",
        "`running`",
        "`completed`",
        "`failed`",
    ]:
        assert expected in quick_reference, f"Missing workflow guidance: {expected}"


def test_skill_openclaw_runtime_section_covers_api_key_injection() -> None:
    _frontmatter, body = _split_frontmatter(_read_text(SKILL_PATH))
    openclaw_runtime = _section(body, "OpenClaw Runtime")

    for expected in [
        "metadata.openclaw.primaryEnv: API_KEY",
        "~/.openclaw/openclaw.json",
        '"crypto-news-http-api"',
        '"YOUR_API_KEY"',
        "do not send unauthenticated requests",
    ]:
        assert expected in openclaw_runtime, f"Missing OpenClaw runtime guidance: {expected}"


def test_skill_analyze_workflow_section_covers_202_polling_and_result_fetch() -> None:
    _frontmatter, body = _split_frontmatter(_read_text(SKILL_PATH))
    analyze_workflow = _section(body, "Analyze Workflow")

    for expected in [
        "`/analyze`",
        "`hours`",
        "`user_id`",
        "`202 Accepted`",
        "`job_id`",
        "`status_url`",
        "`result_url`",
        "`completed` or `failed`",
        "Do not expect the analysis report in the initial POST response",
    ]:
        assert expected in analyze_workflow, f"Missing analyze workflow contract: {expected}"


def test_skill_semantic_search_section_covers_async_contract_constraints_and_dependencies() -> None:
    _frontmatter, body = _split_frontmatter(_read_text(SKILL_PATH))
    semantic_search = _section(body, "Semantic Search")

    for expected in [
        "`/semantic-search`",
        "`hours`",
        "`query`",
        "`user_id`",
        "`202 Accepted`",
        "`semantic_search_job_`",
        "`completed` or `failed`",
        "`status` field as the source of truth",
        "300 characters",
        "`^[A-Za-z0-9_-]{1,128}$`",
        "PostgreSQL-only",
        "`503`",
        "4 subqueries",
        "200 unique items",
        "`OPENAI_API_KEY`",
        "`KIMI_API_KEY` or `GROK_API_KEY`",
    ]:
        assert expected in semantic_search, f"Missing semantic search contract: {expected}"


def test_skill_datasource_management_covers_crud_tags_and_redaction_rules() -> None:
    _frontmatter, body = _split_frontmatter(_read_text(SKILL_PATH))
    datasource_management = _section(body, "Datasource Management")

    for expected in [
        "`POST /datasources`",
        "`GET /datasources`",
        "`DELETE /datasources/{id}`",
        "All datasource routes require Bearer auth",
        "up to 16 unique tags",
        "32 characters",
        "lowercase",
        "deduplicated",
        "safe summaries",
        "redacted",
        "counts replace raw credential fields",
    ]:
        assert expected in datasource_management, f"Missing datasource contract: {expected}"


def test_skill_telegram_webhook_is_maintainer_oriented_integration_surface() -> None:
    _frontmatter, body = _split_frontmatter(_read_text(SKILL_PATH))
    webhook_section = _section(body, "Telegram Webhook")

    for expected in [
        "maintainer-level Telegram integration",
        "not the primary path for day-to-day operators",
        "API routes or Telegram slash commands",
        "`X-Telegram-Bot-Api-Secret-Token`",
    ]:
        assert expected in webhook_section, f"Missing webhook framing: {expected}"


def test_skill_updating_guidance_prefers_code_and_tests_when_prose_drifts() -> None:
    _frontmatter, body = _split_frontmatter(_read_text(SKILL_PATH))
    updating = _section(body, "Updating")

    assert "`api_server.py`" in updating
    assert "`docs/AI_ANALYZE_API_GUIDE.md`" in updating
    assert "`docs/SEMANTIC_SEARCH_API_GUIDE.md`" in updating
    assert "code and tests first, then reference files, then guides" in updating


def test_analyze_workflow_reference_covers_async_contract_and_current_status_result_behavior() -> None:
    analyze_reference = _read_text(ANALYZE_WORKFLOW_PATH)

    for expected in [
        "POST to `/analyze` with `hours` and `user_id` to enqueue a job",
        "GET `/analyze/{job_id}` to check status until completion",
        "GET `/analyze/{job_id}/result` to retrieve the final Markdown report",
        "202 Accepted",
        "`Location`",
        "`Retry-After`",
        "`success` | boolean | `true` only when `status` is `completed`",
        "`result_available` | boolean | `true` when status is `completed` or `failed`",
        "`queued` or `running` | 200 | Job metadata with empty `report`",
        "`completed` | 200 | Full result with Markdown `report`",
        "`failed` | 200 | Job metadata with `error` field set",
        "Job not found | 404 | Error detail",
        "Use the `status` field as the source of truth, not the `success` boolean",
        "State transitions: `queued` -> `running` -> (`completed` or `failed`)",
    ]:
        assert expected in analyze_reference, f"Missing analyze reference contract: {expected}"


def test_datasource_management_reference_covers_crud_tag_limits_and_redaction() -> None:
    datasource_reference = _read_text(DATASOURCE_MANAGEMENT_PATH)

    for expected in [
        "POST /datasources",
        "201 Created",
        "409 Conflict",
        "422 Unprocessable Entity",
        "GET /datasources",
        "DELETE /datasources/{id}",
        "sorted by source type and name",
        "Maximum 16 unique tags per datasource",
        "Each tag must be at most 32 characters after normalization",
        "Tags are converted to lowercase",
        "Duplicate tags are removed",
        "The `headers` object is replaced with `header_count`",
        "The `params` object is replaced with `param_count`",
        "The actual header names, parameter names, and their values are never returned",
    ]:
        assert expected in datasource_reference, f"Missing datasource reference contract: {expected}"


def test_operations_reference_covers_health_webhook_and_full_update_verification_workflow() -> None:
    operations_reference = _read_text(OPERATIONS_AND_MAINTENANCE_PATH)

    for expected in [
        "`GET /health`",
        '`{"status": "healthy", "initialized": true/false}`',
        "maintainer-only integration surface",
        "`TELEGRAM_WEBHOOK_PATH`",
        "`/telegram/webhook`",
        "`X-Telegram-Bot-Api-Secret-Token`",
        "`403 Forbidden`",
        "`503 Service Unavailable`",
        "not for manual invocation",
        "`crypto_news_analyzer/api_server.py`",
        "`tests/test_api_server.py`",
        "`docs/AI_ANALYZE_API_GUIDE.md`",
        "Before merge, run the full planned verification suite",
        "uv run pytest tests/test_openclaw_skill_crypto_news_http_api.py -v",
        'uv run pytest tests/test_api_server.py -k "health or analyze or datasource or webhook" -v',
        "uv run pytest tests/test_banned_legacy_reference_scan.py -v",
        "uv run python tests/helpers/banned_legacy_reference_scan.py",
        "code and tests over prose",
    ]:
        assert expected in operations_reference, f"Missing operations contract: {expected}"


def test_semantic_search_reference_covers_async_contract_limits_and_backfill() -> None:
    semantic_reference = _read_text(SEMANTIC_SEARCH_PATH)

    for expected in [
        "POST /semantic-search",
        "GET /semantic-search/{job_id}",
        "GET /semantic-search/{job_id}/result",
        "`hours`",
        "`query`",
        "`user_id`",
        "202 Accepted",
        "`Location`",
        "`Retry-After`",
        "`semantic_search_job_`",
        "`success` | boolean | `true` only when `status` is `completed`",
        "`result_available` | boolean | `true` when status is `completed` or `failed`",
        "Markdown semantic search report",
        "PostgreSQL with pgvector",
        "SQLite is unsupported",
        "300 characters",
        "4 subqueries",
        "200 unique items",
        "`OPENAI_API_KEY`",
        "`KIMI_API_KEY` or `GROK_API_KEY`",
        "`/semantic_search <hours> <topic>`",
        "embedding-backfill",
        "`docs/SEMANTIC_SEARCH_API_GUIDE.md`",
        "`tests/test_api_server_semantic_search.py`",
        "`tests/test_semantic_search_contracts.py`",
        "trust code and tests over prose",
    ]:
        assert expected in semantic_reference, f"Missing semantic reference contract: {expected}"
