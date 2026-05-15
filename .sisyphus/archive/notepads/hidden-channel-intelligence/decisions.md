## 2026-05-03 Task 12

- REST datasource endpoint summaries now strip query strings, fragments, and userinfo before API exposure so API-key/PAT-like query parameters cannot leak through `/datasources`.
- Raw intelligence text guardrail tests compare decoded response text and UTF-8 bytes exactly, preserving the no-redaction raw text contract while still requiring Bearer auth.
