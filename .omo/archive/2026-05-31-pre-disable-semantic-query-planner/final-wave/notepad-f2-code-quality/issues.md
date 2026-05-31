# F2 Code Quality Review - Issues Found

## MUST FIX (blocking)

### 1. api_server.py:503-504 — E122 indentation broken
**Severity:** Medium
**Description:** Dictionary literal in `_log_to_dict()` has misaligned entries. Lines 503-504 use 4-space and 0-space indentation instead of 8-space and 4-space respectively.
```python
# Line 501-504 (broken at 503-504):
        "started_at": _datetime_to_iso(getattr(log, "started_at", None)),
        "finished_at": _datetime_to_iso(getattr(log, "finished_at", None)),
    "created_at": _datetime_to_iso(getattr(log, "created_at", None)),
}
```
**Impact:** While Python tolerates misindented dict entries (parenthesized context), this violates PEP 8 and suggests a merge/edit artifact.

### 2. topic_enricher.py:19 — OpenAI = None type violation
**Severity:** Medium
**Description:** Conditional import pattern `OpenAI = None` (when `openai` not installed) causes mypy type error: "Cannot assign to a type". mypy tracks `OpenAI` as a class type from the `from openai import OpenAI` import, and assigning `None` to it breaks type safety. Line 69 then does `if OpenAI:` which mypy flags as truthy-function.
**Impact:** Runtime behavior is correct (common Python idiom), but strict type checking fails. The guard at line 69 also breaks when OpenAI is never imported (AttributeError if `openai` not installed and `OpenAI` is None, not truthy-checkable).

## SHOULD FIX (non-blocking)

### 3. topic_enricher.py — Missing dependency handling
**Severity:** Low
**Description:** The `from openai import OpenAI` import doesn't have a clear dependency chain. If `openai` isn't installed, the fallback path may cause subtle runtime issues.

### 4. topic_prompts.py:108 and topic_findings.py:201 — no-any-return
**Severity:** Low
**Description:** Functions returning `dict[str, Any]` and `Optional[MergePreview]` respectively may return `Any` in some code paths.
