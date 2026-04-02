from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_PATH = REPO_ROOT / ".opencode" / "skills" / "crypto-news-debug" / "SKILL.md"


def _read_skill_text() -> str:
    assert SKILL_PATH.exists(), f"Skill file not found: {SKILL_PATH}"
    return SKILL_PATH.read_text(encoding="utf-8")


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


def test_skill_file_exists_and_has_minimal_frontmatter() -> None:
    text = _read_skill_text()
    frontmatter, _body = _split_frontmatter(text)

    assert SKILL_PATH == REPO_ROOT / ".opencode" / "skills" / "crypto-news-debug" / "SKILL.md"
    assert frontmatter.get("name") == "crypto-news-debug"
    assert frontmatter.get("description"), "Skill description must not be empty"


def test_skill_documents_required_env_and_endpoint() -> None:
    text = _read_skill_text()
    _frontmatter, body = _split_frontmatter(text)

    assert "RAILWAY_API_TOKEN" in body
    assert "Authorization: Bearer $RAILWAY_API_TOKEN" in body
    assert "https://backboard.railway.com/graphql/v2" in body
    assert "If `RAILWAY_API_TOKEN` is missing" in body


def test_v1_forbids_high_risk_actions() -> None:
    text = _read_skill_text()
    _frontmatter, body = _split_frontmatter(text)
    non_goals = _section(body, "Non-Goals").lower()
    lower_body = body.lower()

    for forbidden in [
        "rollback",
        "stop service",
        "cancel deployment",
        "delete service",
        "remove service",
        "update variables",
        "create domain",
        "create volume",
    ]:
        assert forbidden in non_goals, f"Missing forbidden-action guidance for: {forbidden}"

    for forbidden_guidance in [
        "rollback workflow",
        "stop a running deployment",
        "stop deployment",
        "cancel a deployment",
        "delete a service",
        "remove a service",
        "update environment variables",
        "create a domain",
        "create a volume",
    ]:
        assert forbidden_guidance not in lower_body, (
            f"Skill must not provide active guidance for forbidden action: {forbidden_guidance}"
        )


def test_mutations_require_explicit_scoping_and_error_handling() -> None:
    text = _read_skill_text()
    _frontmatter, body = _split_frontmatter(text)
    mutations = _section(body, "Operational Actions")

    assert "project → environment → service → deployment" in body
    assert "Only run restart or redeploy after resolving the exact project, environment, and service IDs" in mutations
    assert "Require explicit user intent before any mutation" in mutations
    assert "Confirm the target is an app service, not PostgreSQL or another managed database service" in mutations
    assert "Resolve the latest successful deployment before invoking a mutation" in mutations
    assert "After every mutation, re-check deployment state and logs" in mutations
    assert "If multiple candidates match, stop and present the candidates instead of guessing" in body
    assert "Treat HTTP 200 responses with a non-empty `errors` array as failures" in body


def test_database_services_are_read_only_in_v1() -> None:
    text = _read_skill_text()
    _frontmatter, body = _split_frontmatter(text)
    mutations = _section(body, "Operational Actions").lower()
    database_guidance = _section(body, "Database Safety").lower()

    assert "postgresql" in database_guidance
    assert "inspection-only" in database_guidance
    assert "do not restart or redeploy database services in v1" in database_guidance
    assert "postgresql restart" not in mutations
    assert "postgresql redeploy" not in mutations


def test_skill_documents_resolution_flow_aliases_and_backoff() -> None:
    text = _read_skill_text()
    _frontmatter, body = _split_frontmatter(text)
    resolution = _section(body, "Target Resolution")
    aliases = _section(body, "Service Aliases")
    failure_handling = _section(body, "Failure Handling")

    assert "project → environment → service → deployment" in resolution
    assert "crypto-news-analysis" in aliases
    assert "analysis-service" in aliases
    assert "crypto-news-ingestion" in aliases
    assert "ingestion" in aliases
    assert "crypto-news-api" in aliases
    assert "If no service matches, stop and report that no candidates were found" in failure_handling
    assert "If multiple services match, stop and list the candidates" in failure_handling
    assert "If logs are empty, report that the log query returned no entries" in failure_handling
    assert "X-RateLimit-Remaining" in failure_handling
    assert "X-RateLimit-Reset" in failure_handling
    assert "Retry-After" in failure_handling
    assert "back off before sending another request" in failure_handling
    assert "curl --include" in failure_handling
