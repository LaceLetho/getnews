from __future__ import annotations

import argparse
import os
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Iterable, List, Sequence, Tuple


REPO_ROOT = Path(__file__).resolve().parents[2]

IGNORED_PATH_PREFIXES: Tuple[str, ...] = (
    ".git",
    ".venv",
    ".sisyphus/evidence",
    "docs/archive",
)

EXACT_ACTIONABLE_PATHS: Tuple[str, ...] = (
    "README.md",
    "AGENTS.md",
    ".env.template",
    "crypto_news_analyzer/main.py",
    "crypto_news_analyzer/reporters/telegram_command_handler.py",
    "docker-entrypoint.sh",
)

ACTIONABLE_DIRECTORY_SUFFIX_RULES: Tuple[Tuple[str, str], ...] = (
    ("docs", ".md"),
    ("tests/telegram-multi-user-authorization", ".py"),
)

BANNED_LEGACY_REFERENCES: Tuple[Tuple[str, re.Pattern[str]], ...] = (
    ("api-server", re.compile(r"api-server")),
    ("/run", re.compile(r"(?<![A-Za-z0-9_.-])/run\b")),
    ("run_api_server", re.compile(r"\brun_api_server\b")),
    ("run_api_server_isolated", re.compile(r"\brun_api_server_isolated\b")),
    ("run_command_listener_mode", re.compile(r"\brun_command_listener_mode\b")),
    ("once", re.compile(r"\bonce\b(?=\s*(?:[`\"':;,.()\[\]{}$：；，]|$))")),
    ("schedule", re.compile(r"\bschedule\b(?=\s*(?:[`\"':;,.()\[\]{}$：；，]|$))")),
    ("scheduler", re.compile(r"\bscheduler\b(?=\s*(?:[`\"':;,.()\[\]{}$：；，]|$))")),
    ("crypto-news-api", re.compile(r"crypto-news-api")),
)


@dataclass(frozen=True)
class LegacyReferenceMatch:
    path: str
    line_number: int
    reference: str
    line_text: str


def _as_posix_path(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def is_ignored_path(relative_path: str) -> bool:
    path_parts = PurePosixPath(relative_path).parts
    for ignored_prefix in IGNORED_PATH_PREFIXES:
        ignored_parts = PurePosixPath(ignored_prefix).parts
        if path_parts[: len(ignored_parts)] == ignored_parts:
            return True
    return False


def is_actionable_path(relative_path: str) -> bool:
    if is_ignored_path(relative_path):
        return False

    if relative_path in EXACT_ACTIONABLE_PATHS:
        return True

    return any(
        relative_path.startswith(f"{directory}/") and relative_path.endswith(suffix)
        for directory, suffix in ACTIONABLE_DIRECTORY_SUFFIX_RULES
    )


def iter_candidate_files(root: Path) -> Iterable[Path]:
    root = root.resolve()

    for current_root, dirnames, filenames in os.walk(root, topdown=True):
        current_root_path = Path(current_root)
        relative_root = "."
        if current_root_path != root:
            relative_root = _as_posix_path(current_root_path, root)

        filtered_dirnames = []
        for dirname in sorted(dirnames):
            relative_dir = dirname if relative_root == "." else f"{relative_root}/{dirname}"
            if not is_ignored_path(relative_dir):
                filtered_dirnames.append(dirname)
        dirnames[:] = filtered_dirnames

        for filename in sorted(filenames):
            file_path = current_root_path / filename
            relative_path = _as_posix_path(file_path, root)
            if is_actionable_path(relative_path):
                yield file_path


def scan_file(file_path: Path, root: Path) -> List[LegacyReferenceMatch]:
    matches: List[LegacyReferenceMatch] = []
    relative_path = _as_posix_path(file_path, root)
    lines = file_path.read_text(encoding="utf-8", errors="replace").splitlines()

    for line_number, line_text in enumerate(lines, start=1):
        for reference, pattern in BANNED_LEGACY_REFERENCES:
            if pattern.search(line_text):
                matches.append(
                    LegacyReferenceMatch(
                        path=relative_path,
                        line_number=line_number,
                        reference=reference,
                        line_text=line_text,
                    )
                )

    return matches


def scan_repo(root: Path = REPO_ROOT) -> List[LegacyReferenceMatch]:
    root = root.resolve()
    matches: List[LegacyReferenceMatch] = []

    for file_path in iter_candidate_files(root):
        matches.extend(scan_file(file_path, root))

    return sorted(matches, key=lambda match: (match.path, match.line_number, match.reference))


def format_report(matches: Sequence[LegacyReferenceMatch]) -> str:
    if not matches:
        return "No banned legacy references found in actionable repo files."

    report_lines = [
        f"Found {len(matches)} banned legacy reference(s) in actionable repo files:",
    ]
    for match in matches:
        report_lines.append(
            f"{match.path}:{match.line_number}: [{match.reference}] {match.line_text}"
        )

    return "\n".join(report_lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Scan actionable repo files for banned legacy monolith references.",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=REPO_ROOT,
        help="Repository root to scan.",
    )
    args = parser.parse_args(argv)

    matches = scan_repo(args.root)
    print(format_report(matches))
    return 1 if matches else 0


if __name__ == "__main__":
    raise SystemExit(main())
