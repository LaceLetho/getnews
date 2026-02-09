# Implementation Plan: Telegram Multi-User Authorization

## Overview

This implementation plan enhances the Telegram bot authorization system to support multiple authorized users interacting with the bot in both private chats and group chats. The system now supports both numeric user IDs and @username format in the TELEGRAM_AUTHORIZED_USERS environment variable, with automatic username resolution and caching.

The changes include:
1. Load authorized users from environment variable (supporting both IDs and usernames)
2. Resolve usernames to user IDs using Telegram Bot API
3. Cache username-to-user_id mappings for performance
4. Add chat context extraction helpers
5. Enhance logging to include chat context
6. Simplify authorization logic (remove per-user permissions)
7. Add comprehensive tests

## Tasks

- [ ] 1. Implement username resolution functionality
  - [x] 1.1 Create _resolve_username() method
    - Implement method to call Telegram Bot API's getChat endpoint
    - Accept username with or without @ prefix
    - Return user_id as string on success, None on failure
    - Handle API exceptions gracefully
    - Log resolution attempts and results
    - _Requirements: 6.1_

  - [x] 1.2 Add username cache data structure
    - Add `_username_cache` dictionary instance variable to TelegramCommandHandler
    - Initialize as empty dict in __init__
    - Store username -> user_id mappings
    - _Requirements: 6.3_

  - [ ]* 1.3 Write property test for username resolution
    - **Property 5: Username resolution and caching**
    - **Validates: Requirements 6.1, 6.3**

  - [ ]* 1.4 Write unit tests for username resolution
    - Test successful username resolution (specific example)
    - Test username not found error (error condition)
    - Test API error during resolution (error condition)
    - Test username with and without @ prefix (edge case)
    - _Requirements: 6.1, 6.4, 6.5_

- [ ] 2. Update authorization loading to support mixed format
  - [x] 2.1 Modify _load_authorized_users() method
    - Read TELEGRAM_AUTHORIZED_USERS environment variable
    - Parse comma-separated entries
    - Identify numeric entries as direct user IDs
    - Identify entries starting with "@" as usernames
    - Validate and skip invalid entries with warnings
    - Store direct user IDs in set
    - _Requirements: 5.1, 5.2, 5.3, 5.7, 5.8, 5.9_

  - [x] 2.2 Add username resolution loop to _load_authorized_users()
    - Iterate through username entries
    - Call _resolve_username() for each username
    - Add resolved user_ids to authorized set
    - Store mappings in _username_cache
    - Log resolution successes and failures
    - Continue on errors (don't crash)
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6_

  - [x] 2.3 Update initialization logging
    - Log total number of authorized users
    - Log count of users from direct IDs vs resolved usernames
    - _Requirements: 5.3, 6.6_

  - [ ]* 2.4 Write property test for mixed format parsing
    - **Property 4: Environment variable parsing completeness**
    - **Property 7: Mixed format authorization**
    - **Validates: Requirements 5.1, 5.2, 5.3, 5.6, 5.7, 5.8, 5.9, 6.2, 6.7**

  - [ ]* 2.5 Write unit tests for mixed format parsing
    - Test parsing with only user IDs (edge case)
    - Test parsing with only usernames (edge case)
    - Test parsing with mixed IDs and usernames (specific example)
    - Test parsing with spaces and formatting variations (edge case)
    - Test parsing with invalid entries (error condition)
    - Test parsing with empty environment variable (edge case)
    - _Requirements: 5.4, 5.5, 5.6, 5.9, 6.7_

- [ ] 3. Add error handling for username resolution
  - [x] 3.1 Handle user not found errors
    - Catch user not found exceptions from Telegram API
    - Log warning with username
    - Return None from _resolve_username()
    - Continue initialization with other entries
    - _Requirements: 6.4_

  - [x] 3.2 Handle API errors during resolution
    - Catch general API exceptions
    - Log error with username and error message
    - Return None from _resolve_username()
    - Continue initialization with other entries
    - _Requirements: 6.5_

  - [x] 3.3 Handle bot permission errors
    - Catch permission denied errors
    - Log error with explanation about permissions
    - Return None from _resolve_username()
    - Continue initialization with other entries
    - _Requirements: 6.5_

  - [ ]* 3.4 Write property test for error handling
    - **Property 6: Username resolution error handling**
    - **Validates: Requirements 6.4, 6.5**

  - [ ]* 3.5 Write unit tests for error scenarios
    - Test handling of user not found (error condition)
    - Test handling of API network error (error condition)
    - Test handling of permission denied (error condition)
    - Test that bot continues after resolution failures (integration)
    - _Requirements: 6.4, 6.5_

- [ ] 4. Checkpoint - Ensure username resolution tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 5. Update authorization logic
  - [x] 5.1 Simplify is_authorized_user() method
    - Remove username-based fallback logic
    - Check user_id against `_authorized_user_ids` set
    - Return boolean result
    - _Requirements: 1.1, 1.2, 1.3, 2.1, 2.2, 2.3, 6.2_

  - [x] 5.2 Remove validate_user_permissions() method
    - Delete the method entirely
    - All authorized users now have access to all commands
    - _Requirements: 7.1, 7.2, 7.3, 7.4_

  - [ ]* 5.3 Write property test for authorization with resolved usernames
    - Test that users authorized via username can execute commands
    - Test that authorization works identically for direct IDs and resolved usernames
    - _Requirements: 6.2, 6.7_

- [ ] 6. Add chat context extraction functionality
  - [x] 6.1 Create ChatContext dataclass
    - Add `ChatContext` dataclass in `crypto_news_analyzer/models.py`
    - Include fields: user_id, username, chat_id, chat_type, is_private, is_group
    - Add `context_description` property for human-readable output
    - _Requirements: 3.1, 3.2, 3.3_

  - [x] 6.2 Implement _extract_chat_context() helper method
    - Add method to `TelegramCommandHandler` class
    - Extract user_id from `update.effective_user.id`
    - Extract chat_id and chat_type from `update.effective_chat`
    - Return `ChatContext` instance with all fields populated
    - Handle missing fields gracefully with error logging
    - _Requirements: 1.4, 2.4, 3.1, 3.2, 3.3_

  - [ ]* 6.3 Write property test for chat context extraction
    - **Property 2: User ID extraction correctness**
    - **Property 3: Chat type classification**
    - **Validates: Requirements 1.4, 2.4, 3.1, 3.2, 3.3**

  - [ ]* 6.4 Write unit tests for chat context extraction edge cases
    - Test extraction from private chat (specific example)
    - Test extraction from group chat (specific example)
    - Test extraction from supergroup (specific example)
    - Test error handling when effective_user is missing
    - Test error handling when effective_chat is missing
    - _Requirements: 3.1, 3.2, 3.3_

- [ ] 7. Add enhanced authorization logging
  - [x] 7.1 Implement _log_authorization_attempt() method
    - Add method to `TelegramCommandHandler` class
    - Accept parameters: command, user_id, username, chat_type, chat_id, authorized, reason
    - Log at INFO level for successful authorization
    - Log at WARNING level for failed authorization
    - Include all context fields in log message
    - _Requirements: 8.1, 8.2, 8.3, 8.4_

  - [ ]* 7.2 Write property test for authorization logging completeness
    - **Property 8: Authorization logging completeness**
    - **Validates: Requirements 8.1, 8.2, 8.3, 8.4**

  - [ ]* 7.3 Write unit tests for logging edge cases
    - Test logging with missing username
    - Test logging with very long user_id
    - Test logging with special characters in fields
    - _Requirements: 8.1, 8.2, 8.3, 8.4_

- [ ] 8. Update command handlers to use chat context
  - [x] 8.1 Update _handle_run_command() method
    - Call `_extract_chat_context()` at the start of the method
    - Extract user_id, username, chat_type, chat_id from context
    - Update existing log statements to include chat_type and chat_id
    - Call `_log_authorization_attempt()` for all authorization checks
    - Remove `validate_user_permissions()` call
    - Update error messages to be consistent
    - _Requirements: 1.1, 1.2, 1.3, 2.1, 2.2, 2.3, 8.1, 8.2, 8.3, 8.4_

  - [x] 8.2 Update _handle_status_command() method
    - Call `_extract_chat_context()` at the start of the method
    - Extract user_id, username, chat_type, chat_id from context
    - Update existing log statements to include chat_type and chat_id
    - Call `_log_authorization_attempt()` for all authorization checks
    - Remove `validate_user_permissions()` call
    - _Requirements: 1.1, 1.2, 1.3, 2.1, 2.2, 2.3, 8.1, 8.2, 8.3, 8.4_

  - [x] 8.3 Update _handle_help_command() method
    - Call `_extract_chat_context()` at the start of the method
    - Extract user_id, username, chat_type, chat_id from context
    - Update existing log statements to include chat_type and chat_id
    - Call `_log_authorization_attempt()` for all authorization checks
    - Remove `validate_user_permissions()` call
    - Update help text to remove per-user permission logic
    - _Requirements: 1.1, 1.2, 1.3, 2.1, 2.2, 2.3, 8.1, 8.2, 8.3, 8.4_

  - [ ]* 8.4 Write property test for authorization consistency across chat types
    - **Property 1: User-based authorization consistency across chat contexts**
    - **Validates: Requirements 1.1, 1.2, 1.3, 2.1, 2.2, 2.3, 3.4**

  - [ ]* 8.5 Write property test for unauthorized user rejection
    - **Property 9: Unauthorized user rejection**
    - **Validates: Requirements 1.3, 2.3**

- [ ] 9. Update configuration files
  - [x] 9.1 Remove authorized_users from config.json
    - Remove the `authorized_users` field from telegram_commands section
    - Keep other telegram_commands configuration intact
    - _Requirements: 5.1_

  - [x] 9.2 Update .env.template
    - Add TELEGRAM_AUTHORIZED_USERS with example showing mixed format
    - Add comments explaining the format (IDs and usernames)
    - Provide example: "123456789,@user1,987654321,@user2"
    - Add note about username resolution requirements
    - _Requirements: 5.1, 5.2, 6.7_

  - [x] 9.3 Update documentation
    - Update README or deployment docs with new environment variable
    - Explain how to get Telegram user IDs
    - Explain username format and resolution process
    - Provide migration guide from config.json to environment variable
    - Document username resolution limitations (bot must have interacted with user)
    - _Requirements: 5.1, 6.1_

- [ ] 10. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 11. Verify backward compatibility
  - [ ]* 11.1 Write integration test for report sending
    - Verify TelegramSender still uses TELEGRAM_CHANNEL_ID for reports
    - Verify command handler doesn't interfere with report sending
    - Verify authorization logic is separate for commands vs reports
    - _Requirements: 4.1, 4.2, 4.3_

  - [ ]* 11.2 Write unit test for authorization independence
    - Test that command authorization uses user_id from env var
    - Test that report sending uses channel_id from env var
    - Verify they don't interfere with each other
    - _Requirements: 4.3_

  - [ ]* 11.3 Write integration test for username resolution with real API
    - When TELEGRAM_BOT_TOKEN is available, test real username resolution
    - Test with valid username that bot has interacted with
    - Verify resolved user_id is correct
    - Debug any authentication failures before using mocks
    - _Requirements: 6.1, 6.3_

- [ ] 12. Final checkpoint - Ensure all tests pass
  - Run all unit tests and property tests
  - Verify test coverage for critical paths
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- The existing `check_rate_limit()` method requires no changes
- Property tests should run minimum 100 iterations each
- Use `hypothesis` library for property-based testing in Python
- Use `uv` for all Python operations (uv run pytest, uv pip install, etc.)
- Prefer real integration tests when TELEGRAM_BOT_TOKEN is available via environment variables
- Focus on practical, meaningful tests rather than maximizing coverage metrics
- Username resolution requires the bot to have interacted with the user or user to have public profile

## Environment Variable Format

```bash
# Single user ID
TELEGRAM_AUTHORIZED_USERS=123456789

# Single username
TELEGRAM_AUTHORIZED_USERS=@username

# Multiple users (comma-separated, mixed format)
TELEGRAM_AUTHORIZED_USERS=123456789,@user1,987654321,@user2

# With spaces (will be trimmed automatically)
TELEGRAM_AUTHORIZED_USERS="123456789, @user1, 987654321, @user2"

# Real example from user request
TELEGRAM_AUTHORIZED_USERS=5844680524,@wingperp,@mcfangpy,@Huazero,@long0short
```

## Test Execution Commands

**Run all tests:**
```bash
uv run pytest tests/test_telegram_authorization_unit.py tests/test_telegram_authorization_properties.py -v
```

**Run only unit tests:**
```bash
uv run pytest tests/test_telegram_authorization_unit.py -v
```

**Run only property tests:**
```bash
uv run pytest tests/test_telegram_authorization_properties.py -v
```

**Run with coverage:**
```bash
uv run pytest tests/test_telegram_authorization_unit.py --cov=crypto_news_analyzer/reporters --cov-report=html
```

**Run integration tests with real Telegram API:**
```bash
# Requires TELEGRAM_BOT_TOKEN in environment
uv run pytest tests/test_telegram_authorization_integration.py -v
```

## Migration Guide

For users migrating from the old config.json format:

**Old format (config.json):**
```json
{
  "telegram_commands": {
    "authorized_users": [
      {"user_id": "123456789", "username": "@user1", "permissions": ["run", "status"]},
      {"user_id": "987654321", "username": "@user2", "permissions": ["status"]}
    ]
  }
}
```

**New format (environment variable with user IDs):**
```bash
TELEGRAM_AUTHORIZED_USERS=123456789,987654321
```

**New format (environment variable with usernames):**
```bash
TELEGRAM_AUTHORIZED_USERS=@user1,@user2
```

**New format (mixed):**
```bash
TELEGRAM_AUTHORIZED_USERS=123456789,@user2
```

**Note:** All authorized users now have access to all commands (/run, /status, /help). Per-user permissions are not supported in this version.

## Username Resolution Notes

**Requirements for username resolution:**
- The bot must have previously interacted with the user (user sent a message to the bot), OR
- The user must have a public profile

**If username resolution fails:**
- The bot will log a warning and skip that username
- Other entries will still be processed
- The bot will remain operational
- That user won't be authorized until bot restart with successful resolution

**Troubleshooting username resolution:**
- Ensure the username is correct (case-sensitive)
- Ensure the user has started a conversation with the bot
- Check bot logs for specific error messages
- Consider using numeric user IDs for critical users as fallback
