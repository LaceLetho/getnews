#!/usr/bin/env bash

set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  skills/publish_clawhub_skill.sh <skill-name> <version> [changelog]

Examples:
  skills/publish_clawhub_skill.sh crypto-news-http-api 0.2.1
  skills/publish_clawhub_skill.sh crypto-news-http-api 0.2.1 "Tighten OpenClaw runtime guidance."

Environment overrides:
  CLAWHUB_SKILL_SLUG   Publish slug override (defaults to <skill-name>)
  CLAWHUB_SKILL_NAME   Display name override (defaults to title-cased skill name)
  CLAWHUB_TAGS         Comma-separated tags (defaults to latest)
  CLAWHUB_SKIP_TESTS   Set to 1 to skip pre-publish tests
EOF
}

if [[ "${1:-}" == "" || "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 1
fi

if [[ "${2:-}" == "" ]]; then
  usage
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

SKILL_NAME="$1"
VERSION="$2"
CHANGELOG="${3:-}"
SKILL_DIR="${SCRIPT_DIR}/${SKILL_NAME}"
SLUG="${CLAWHUB_SKILL_SLUG:-${SKILL_NAME}}"
DISPLAY_NAME="${CLAWHUB_SKILL_NAME:-$(printf '%s' "${SKILL_NAME}" | tr '-' ' ' | awk '{for (i = 1; i <= NF; i++) $i = toupper(substr($i, 1, 1)) substr($i, 2); print}')}"
TAGS="${CLAWHUB_TAGS:-latest}"
TEST_PATH="${REPO_ROOT}/tests/test_openclaw_skill_${SKILL_NAME//-/_}.py"

if [[ ! -d "${SKILL_DIR}" || ! -f "${SKILL_DIR}/SKILL.md" ]]; then
  echo "Skill directory not found or missing SKILL.md: ${SKILL_DIR}" >&2
  exit 1
fi

if ! command -v clawhub >/dev/null 2>&1; then
  echo "clawhub CLI is required. Install it with: npm install -g clawhub" >&2
  exit 1
fi

if ! clawhub whoami >/dev/null 2>&1; then
  echo "Not logged in to ClawHub. Run: clawhub login" >&2
  exit 1
fi

if [[ "${CLAWHUB_SKIP_TESTS:-0}" != "1" && -f "${TEST_PATH}" ]]; then
  echo "Running ${TEST_PATH##${REPO_ROOT}/}" >&2
  (
    cd "${REPO_ROOT}"
    uv run pytest "${TEST_PATH}" -v
  )
fi

PUBLISH_CMD=(
  clawhub
  publish
  "${SKILL_DIR}"
  --slug "${SLUG}"
  --name "${DISPLAY_NAME}"
  --version "${VERSION}"
  --tags "${TAGS}"
)

if [[ -n "${CHANGELOG}" ]]; then
  PUBLISH_CMD+=(--changelog "${CHANGELOG}")
fi

echo "Publishing ${SKILL_NAME}@${VERSION} to ClawHub" >&2
"${PUBLISH_CMD[@]}"
