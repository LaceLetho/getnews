from pathlib import Path

from tests.helpers.banned_legacy_reference_scan import format_report
from tests.helpers.banned_legacy_reference_scan import is_actionable_path
from tests.helpers.banned_legacy_reference_scan import iter_candidate_files
from tests.helpers.banned_legacy_reference_scan import scan_repo


REPO_ROOT = Path(__file__).resolve().parents[1]
KNOWN_HOTSPOTS = {
    "README.md",
    "AGENTS.md",
    ".env.template",
    "docs/RAILWAY_DEPLOYMENT.md",
    "crypto_news_analyzer/main.py",
    "crypto_news_analyzer/reporters/telegram_command_handler.py",
    "docker-entrypoint.sh",
    "tests/telegram-multi-user-authorization/test_task_8_1_handle_analyze_command.py",
}
IGNORED_PREFIXES = (".git/", ".venv/", ".sisyphus/evidence/")


def _write_file(root: Path, relative_path: str, content: str) -> None:
    file_path = root / relative_path
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content, encoding="utf-8")


def test_scan_repo_only_reports_actionable_files_and_skips_noise(tmp_path):
    _write_file(tmp_path, "README.md", "legacy api-server guidance\n")
    _write_file(tmp_path, "docs/reference.md", "use /run carefully\n")
    _write_file(
        tmp_path,
        "crypto_news_analyzer/main.py",
        "SUPPORTED = ('analysis-service', 'api-only', 'ingestion')\n",
    )
    _write_file(
        tmp_path,
        "crypto_news_analyzer/reporters/telegram_command_handler.py",
        'command = "/run"\n',
    )
    _write_file(tmp_path, "docker-entrypoint.sh", "RAILWAY_SERVICE_NAME=crypto-news-api\n")
    _write_file(
        tmp_path,
        "tests/telegram-multi-user-authorization/test_legacy_surface.py",
        'assert command == "/run"\n',
    )
    _write_file(tmp_path, ".git/HEAD", "api-server\n")
    _write_file(tmp_path, ".venv/bin/activate", "api-server\n")
    _write_file(tmp_path, ".sisyphus/evidence/task-3.txt", "api-server\n")
    _write_file(tmp_path, "crypto_news_analyzer/execution_coordinator.py", "analysis-service\n")

    matches = scan_repo(tmp_path)

    assert {match.path for match in matches} == {
        "README.md",
        "docs/reference.md",
        "crypto_news_analyzer/reporters/telegram_command_handler.py",
        "docker-entrypoint.sh",
        "tests/telegram-multi-user-authorization/test_legacy_surface.py",
    }
    assert all(is_actionable_path(match.path) for match in matches)
    assert not any(match.path.startswith(IGNORED_PREFIXES) for match in matches)


def test_iter_candidate_files_covers_known_legacy_hotspots():
    candidate_paths = {
        file_path.relative_to(REPO_ROOT).as_posix() for file_path in iter_candidate_files(REPO_ROOT)
    }

    assert KNOWN_HOTSPOTS.issubset(candidate_paths)


def test_repo_scan_output_is_sorted_and_scope_bound():
    matches = scan_repo(REPO_ROOT)
    report = format_report(matches)

    assert report
    assert all(is_actionable_path(match.path) for match in matches)
    assert not any(match.path.startswith(IGNORED_PREFIXES) for match in matches)
    assert matches == sorted(matches, key=lambda match: (match.path, match.line_number, match.reference))
