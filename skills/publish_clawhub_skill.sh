#!/usr/bin/env bash

set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  skills/publish_clawhub_skill.sh <version> [changelog]
  skills/publish_clawhub_skill.sh --latest-version

Examples:
  skills/publish_clawhub_skill.sh 0.3.0
  skills/publish_clawhub_skill.sh 0.3.0 "Update to match current API state."
  skills/publish_clawhub_skill.sh --latest-version

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

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

SKILL_NAME="smart-news"
VERSION=""
CHANGELOG=""
LATEST_VERSION_ONLY=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --latest-version)
      LATEST_VERSION_ONLY=true
      shift
      ;;
    -*)
      echo "Unknown option: $1" >&2
      usage
      exit 1
      ;;
    *)
      if [[ -z "${VERSION}" ]]; then
        VERSION="$1"
      elif [[ -z "${CHANGELOG}" ]]; then
        CHANGELOG="$1"
      else
        echo "Unexpected argument: $1" >&2
        usage
        exit 1
      fi
      shift
      ;;
  esac
done

if [[ "${LATEST_VERSION_ONLY}" == "true" ]]; then
  SLUG="${CLAWHUB_SKILL_SLUG:-${SKILL_NAME}}"
  if ! command -v clawhub >/dev/null 2>&1; then
    echo "clawhub CLI is required. Install it with: npm install -g clawhub" >&2
    exit 1
  fi
  if ! clawhub whoami >/dev/null 2>&1; then
    echo "Not logged in to ClawHub. Run: clawhub login" >&2
    exit 1
  fi
  INSPECT_JSON="$(clawhub inspect "${SLUG}" --json 2>/dev/null || true)"
  if [[ -z "${INSPECT_JSON}" ]]; then
    echo "Skill '${SLUG}' not found on ClawHub or fetch failed." >&2
    exit 1
  fi
  LATEST_VER="$(printf '%s' "${INSPECT_JSON}" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('latestVersion',{}).get('version','') or d.get('skill',{}).get('tags',{}).get('latest',''))" 2>/dev/null || true)"
  if [[ -z "${LATEST_VER}" ]]; then
    echo "Skill '${SLUG}' found but could not determine latest version." >&2
    exit 1
  fi
  printf '%s\n' "${LATEST_VER}"
  exit 0
fi

if [[ -z "${VERSION}" ]]; then
  echo "Missing version argument." >&2
  usage
  exit 1
fi

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
