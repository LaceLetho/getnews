---
inclusion: always
---

# Development Environment

## Python Environment

- System Python: 3.9 (macOS default)
- Package Manager: Use `uv` for all Python operations
- Rationale: `uv` prevents global environment pollution and handles Python version management automatically

## Package Management Rules

- ALWAYS use `uv` commands instead of direct `pip` or `python` commands
- Install packages: `uv pip install <package>`
- Run scripts: `uv run <script.py>`
- Execute commands: `uvx <command>` for one-off tool execution
- Create virtual environments: `uv venv` (if needed)

## Best Practices

- Never modify the system Python installation
- Use `uv` to ensure consistent dependency resolution
- Let `uv` handle Python version compatibility automatically

