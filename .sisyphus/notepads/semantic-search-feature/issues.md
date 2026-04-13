## 2026-04-12 Code quality review

- REJECT: `api_server.py` validates blank semantic-search queries but does not enforce `SemanticSearchConfig.query_max_chars`, so oversized API requests are accepted and only fail asynchronously in the background job.
- REJECT: `telegram_command_handler.py` semantic-search flow does not clamp `hours` to configured limits and starts an unbounded raw thread per request instead of reusing a bounded executor.
- Maintainability: `telegram_command_handler.py` has significant static typing debt (for example `datetime` fields initialized with `None` in `CommandRateLimitState`), which makes diagnostics noisy and weakens type-safety.
- Coverage gap: semantic-search tests are strong overall, but `semantic_search/embedding_service.py` still lacks direct unit coverage for disabled-client and embedding-failure paths.

## 2026-04-12 Scope fidelity review

- REJECT: `semantic_search/service.py` persists and reuses a `conversation_id` via `ConversationIdManager(cache_dir="./data/cache")` and injects it into provider headers, which crosses the plan guardrail forbidding chatbot/conversation-memory behavior.
- Verification note: targeted semantic-search tests pass, but LSP diagnostics are not clean in feature-adjacent files such as `execution_coordinator.py` and `telegram_command_handler.py`.

## 2026-04-12 Guardrail cleanup

- No new blocking issues from this cleanup pass; semantic-search query validation now fails fast at ingress and the service no longer carries conversation state.

## 2026-04-12 Code quality re-verification

- REJECT: the specific `Optional[datetime]` handling concern in `telegram_command_handler.py` is addressed, but the file still has blocking basedpyright errors unrelated to hours clamping/raw threads (for example `is_authorized_user(self, user_id: str, username: str = None)` at line 362 and `_log_authorization_check(..., reason: str = None)` at line 509), so Telegram typing quality is not fully resolved.
