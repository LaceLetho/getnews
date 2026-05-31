# Decisions

- Extend `sent_message_cache` minimally with nullable `recipient_key` unless implementation proves impossible.
- Reuse `analysis_execution_log.chat_id` to store normalized recipient keys for manual analyze history.
- HTTP success means a completed analyze response was produced; Telegram success means report send completed successfully.
