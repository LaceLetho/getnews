from pathlib import Path
import subprocess


ENTRYPOINT_PATH = Path(__file__).resolve().parents[1] / "docker-entrypoint.sh"


def _run_entrypoint_snippet(snippet: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", "-lc", snippet],
        capture_output=True,
        text=True,
        check=False,
    )


def test_get_mode_from_railway_service_accepts_split_service_aliases():
    result = _run_entrypoint_snippet(
        f"""
set -euo pipefail
source \"{ENTRYPOINT_PATH}\"
RAILWAY_SERVICE_NAME=\"crypto-news-analysis\"
mode=\"$(get_mode_from_railway_service)\"
if [[ \"$mode\" != \"analysis-service\" ]]; then
  printf 'unexpected service mapping: %s\\n' \"$mode\"
  exit 11
fi
"""
    )

    assert result.returncode == 0, result.stdout + result.stderr


def test_get_mode_from_railway_service_maps_ingestion_service():
    result = _run_entrypoint_snippet(
        f"""
set -euo pipefail
source \"{ENTRYPOINT_PATH}\"
RAILWAY_SERVICE_NAME=\"crypto-news-ingestion\"
mode=\"$(get_mode_from_railway_service)\"
if [[ \"$mode\" != \"ingestion\" ]]; then
  printf 'unexpected service mapping: %s\\n' \"$mode\"
  exit 11
fi
"""
    )

    assert result.returncode == 0, result.stdout + result.stderr


def test_entrypoint_main_rejects_unknown_modes():
    for mode in ("invalid-mode", "bogus-mode"):
        result = _run_entrypoint_snippet(
            f"""
set -euo pipefail
source \"{ENTRYPOINT_PATH}\"
validate_environment() {{ :; }}
show_configuration() {{ :; }}
health_check() {{ return 0; }}
log_execution_state() {{ :; }}
python() {{ return 0; }}

set +e
output=\"$( (main \"{mode}\") 2>&1 )\"
status=$?
set -e

if [[ $status -eq 0 ]]; then
  printf 'unexpected mode accepted: {mode}\\n'
  exit 12
fi

if [[ ! \"$output\" =~ (unsupported|不支持|未知的运行模式) ]]; then
  printf 'missing unsupported semantics for {mode}: %s\\n' \"$output\"
  exit 13
fi
"""
        )

        assert result.returncode == 0, result.stdout + result.stderr


def test_entrypoint_main_rejects_unknown_railway_service_name():
    result = _run_entrypoint_snippet(
        f"""
set -euo pipefail
source \"{ENTRYPOINT_PATH}\"
validate_environment() {{ :; }}
show_configuration() {{ :; }}
health_check() {{ return 0; }}
log_execution_state() {{ :; }}
python() {{ return 0; }}
RAILWAY_SERVICE_NAME=\"crypto-news-unknown\"

set +e
output=\"$( (main) 2>&1 )\"
status=$?
set -e

if [[ $status -eq 0 ]]; then
  printf 'unexpected railway service accepted: %s\\n' \"$RAILWAY_SERVICE_NAME\"
  exit 14
fi

if [[ ! \"$output\" =~ crypto-news-unknown ]]; then
  printf 'output did not mention rejected railway service: %s\\n' \"$output\"
  exit 15
fi

if [[ ! \"$output\" =~ (unsupported|不支持|未知的运行模式) ]]; then
  printf 'missing unsupported semantics for railway service: %s\\n' \"$output\"
  exit 16
fi
"""
    )

    assert result.returncode == 0, result.stdout + result.stderr
