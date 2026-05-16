# F2 Code Quality Review - Learnings

## Tools Setup
- `.venv/bin/` contains flake8, mypy, black - use those directly when `uv run` is not available
- `rg` (ripgrep) not available; use `grep -rnE` as fallback for text searches
- `python3 -m pip` not available either; rely on `.venv/bin/` binaries

## Flake8 Observations
- 171 total E/F/W errors in codebase, vast majority (169) are E501 (line too long > 100 chars) - pre-existing style debt
- 2 E122 real indentation bugs in api_server.py:503-504 (dict entries misaligned)
- 4 E226 (missing whitespace around operators) in utils/logging.py - pre-existing
- 1 E123 (bracket indentation) in telegram_command_handler.py - pre-existing
- Topic modules only have 3 E501 issues (cosmetic), no logic errors

## Mypy Observations
- execution_coordinator.py has several genuine type errors (Optional access, incompatible types) - pre-existing
- Topic modules have 3 minor issues:
  - topic_prompts.py:108 - no-any-return (minor)
  - topic_findings.py:201 - no-any-return (minor)
  - topic_enricher.py:19 - OpenAI = None type assignment (pattern issue)
  - topic_enricher.py:69 - truthy-function check on None (derives from line 19)
- The OpenAI sentinel pattern is a common Python idiom but technically violates type safety

## Clean Checks
- No TODOs, FIXMEs, HACKs, or bare `pass` stubs in topic_*.py
- No EntryType imports in topic_*.py modules
- No hardcoded secrets in topic_*.py or api_server.py (only a sanitization regex in topic_research.py)
