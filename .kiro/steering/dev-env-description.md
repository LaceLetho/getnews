---
inclusion: always
---

# Development Environment

## Python Configuration

- **Python Version**: Python 3.9 (macOS default installation)
- **Python Command**: Always use `python3` instead of `python` when executing Python scripts or commands
- **Package Manager**: Use `pip3` for installing Python packages

## Command Examples

When working with Python in this environment:

```bash
# Run Python scripts
python3 script.py

# Install packages
pip3 install package-name

# Run tests
python3 -m pytest

# Create virtual environments
python3 -m venv venv
```

## Important Notes

- Do not assume `python` command is available or points to Python 3
- Always explicitly use `python3` to ensure compatibility with the environment
- When suggesting commands or writing scripts, use `python3` as the interpreter
