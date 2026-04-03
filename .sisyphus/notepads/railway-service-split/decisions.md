
- 2026-04-03: For the Telegram token leak, keep the fix scoped to sender-local string redaction helpers and tests; do not touch shared logging infrastructure or Telegram API request construction, since the bot token must remain in the live request path.
- 2026-04-03: Use a global `LogRecordFactory` redaction hook in `crypto_news_analyzer/utils/logging.py` so both app logs and third-party library logs are sanitized before formatting; this keeps the fix centralized and minimal.
