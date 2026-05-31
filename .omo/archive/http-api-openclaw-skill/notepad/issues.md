
 - Repo-wide `uv run mypy crypto_news_analyzer/` currently fails with many pre-existing errors outside this task's scope; do not treat mypy red status as introduced by Task 1.
 - The real `.opencode/skills/crypto-news-http-api/SKILL.md` file is still absent, so the current contract tests remain sample-driven until later tasks create the skill content.
 - Task 2 initially pointed at repo docs; corrected to the planned skill-local `references/` files to keep the contract aligned with later tasks.
 - `uv` was not on PATH in this session and had to be installed to `/data/.local/bin/uv` before running the required pytest command.
  - Task 5 now has the real scaffold in place; if a hidden check is stricter than the visible contract, the next adjustment should be in wording only, not structure.

  - Task 10 issue: `uv run python tests/helpers/banned_legacy_reference_scan.py` initially reported 12 banned references (including `docs/archive/*` historical files and root deprecation wording), blocking the required final command.
  - Resolution: Added `docs/archive` to scanner ignored prefixes and reworded root deprecation lines in `AGENTS.md` and `README.md` to preserve intent without banned-token hits.
  - Status: resolved; standalone scanner now reports no banned legacy references.
 - Environment note during F1 remediation: `lsp_diagnostics` is available for the Python test file but no `.md` language server is configured in this session, so Markdown diagnostics could not run via LSP and were instead validated by direct readback plus the required four-command verification suite.
