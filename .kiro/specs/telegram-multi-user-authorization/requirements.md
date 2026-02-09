# Requirements Document

## Introduction

This document specifies the requirements for enhancing the Telegram bot authorization system to support multiple authorized users interacting with the bot in both private chats and group chats. Currently, the system only validates commands against a single TELEGRAM_CHANNEL_ID. The enhancement will leverage the existing `authorized_users` list in config.json to enable flexible multi-user and multi-context authorization.

The system will support both numeric user IDs (e.g., "123456789") and usernames (e.g., "@username") in the TELEGRAM_AUTHORIZED_USERS environment variable, providing administrators with flexible and human-readable configuration options. When usernames are provided, the system will resolve them to user IDs using the Telegram Bot API and cache the mappings for efficient authorization checks.

## Glossary

- **Bot**: The Telegram bot application that receives and processes commands
- **Private_Chat**: A one-on-one conversation between a user and the Bot
- **Group_Chat**: A Telegram group conversation where multiple users and the Bot are participants
- **Authorized_User**: A user whose user_id or username is listed in the authorized_users configuration
- **Command_Handler**: The TelegramCommandHandler class that processes incoming commands
- **User_ID**: The unique numeric identifier assigned by Telegram to each user
- **Username**: The Telegram username (handle) starting with "@" that uniquely identifies a user
- **Chat_ID**: The unique identifier for a chat (positive for private chats, negative for group chats)
- **Command_Sender**: The user who sends a command to the Bot
- **Username_Resolution**: The process of converting a username to its corresponding user_id using the Telegram Bot API
- **Username_Cache**: An in-memory mapping of usernames to user_ids to avoid repeated API calls

## Requirements

### Requirement 1: Private Chat Authorization

**User Story:** As an authorized user, I want to interact with the bot in private chats, so that I can execute commands without needing to use a specific channel.

#### Acceptance Criteria

1. WHEN an Authorized_User sends a command in a Private_Chat, THE Bot SHALL validate the Command_Sender's User_ID against the authorized_users list
2. WHEN the Command_Sender's User_ID matches an entry in the authorized_users list, THE Bot SHALL process the command
3. WHEN the Command_Sender's User_ID does not match any entry in the authorized_users list, THE Bot SHALL reject the command with a permission denied message
4. WHEN validating a Private_Chat command, THE Bot SHALL use the effective_user.id from the Telegram update object

### Requirement 2: Group Chat Authorization

**User Story:** As an authorized user, I want to interact with the bot in group chats, so that I can execute commands in collaborative environments.

#### Acceptance Criteria

1. WHEN an Authorized_User sends a command in a Group_Chat, THE Bot SHALL validate the Command_Sender's User_ID against the authorized_users list
2. WHEN the Command_Sender's User_ID matches an entry in the authorized_users list, THE Bot SHALL process the command regardless of the Group_Chat's Chat_ID
3. WHEN the Command_Sender's User_ID does not match any entry in the authorized_users list, THE Bot SHALL reject the command with a permission denied message
4. WHEN validating a Group_Chat command, THE Bot SHALL use the effective_user.id from the Telegram update object, not the chat.id

### Requirement 3: Chat Context Detection

**User Story:** As a system, I want to distinguish between private chats and group chats, so that I can apply appropriate authorization logic.

#### Acceptance Criteria

1. WHEN the Bot receives a command, THE Bot SHALL determine whether the command originated from a Private_Chat or a Group_Chat
2. WHEN the chat.type is "private", THE Bot SHALL classify the context as a Private_Chat
3. WHEN the chat.type is "group" or "supergroup", THE Bot SHALL classify the context as a Group_Chat
4. THE Bot SHALL apply the same User_ID-based authorization logic for both Private_Chat and Group_Chat contexts

### Requirement 4: Backward Compatibility

**User Story:** As a system administrator, I want the existing channel-based reporting to continue working, so that the enhancement does not break current functionality.

#### Acceptance Criteria

1. WHEN the Bot sends reports to the configured TELEGRAM_CHANNEL_ID, THE Bot SHALL continue using the existing TelegramSender functionality
2. THE Command_Handler SHALL NOT modify or interfere with the report sending mechanism
3. THE Bot SHALL maintain separate authorization logic for command processing (user-based) and report sending (channel-based)

### Requirement 5: Authorization Configuration

**User Story:** As a system administrator, I want to manage authorized users through environment variables using either user IDs or usernames, so that I can control who can interact with the bot in a flexible and user-friendly way.

#### Acceptance Criteria

1. THE Bot SHALL read the authorized users from the TELEGRAM_AUTHORIZED_USERS environment variable
2. THE TELEGRAM_AUTHORIZED_USERS environment variable SHALL contain a comma-separated list of Telegram user IDs and/or usernames
3. WHEN the Bot initializes, THE Bot SHALL parse the TELEGRAM_AUTHORIZED_USERS variable and load all entries into memory
4. WHEN the TELEGRAM_AUTHORIZED_USERS variable is empty or not set, THE Bot SHALL log a warning and reject all command attempts
5. THE Bot SHALL support multiple users in the authorized list without limitation on count
6. THE Bot SHALL trim whitespace from each entry during parsing to handle formatting variations
7. WHEN an entry in the environment variable is numeric, THE Bot SHALL treat it as a user ID
8. WHEN an entry in the environment variable starts with "@", THE Bot SHALL treat it as a username
9. WHEN an entry in the environment variable is neither numeric nor starts with "@", THE Bot SHALL log a warning and skip that entry

### Requirement 6: Username Resolution

**User Story:** As a system administrator, I want to use usernames in addition to user IDs, so that I can configure authorized users in a more human-readable and maintainable way.

#### Acceptance Criteria

1. WHEN a username is provided in TELEGRAM_AUTHORIZED_USERS (starting with "@"), THE Bot SHALL resolve it to the corresponding user_id using the Telegram Bot API
2. WHEN the Bot receives a command from a user, THE Bot SHALL check if the sender's user_id matches any resolved user_id from username entries
3. WHEN username resolution succeeds, THE Bot SHALL cache the username-to-user_id mapping to avoid repeated API calls
4. WHEN username resolution fails due to user not found, THE Bot SHALL log a warning and skip that username entry
5. WHEN username resolution fails due to API error, THE Bot SHALL log an error and skip that username entry
6. THE Bot SHALL attempt username resolution during initialization before accepting commands
7. THE Bot SHALL support mixed format with both numeric user IDs and @username entries in the same TELEGRAM_AUTHORIZED_USERS variable
8. WHEN the cached username-to-user_id mapping is used, THE Bot SHALL periodically refresh the cache to handle username changes

### Requirement 7: Permission Management

**User Story:** As a system administrator, I want all authorized users to have the same set of permissions, so that I can maintain simple and consistent access control.

#### Acceptance Criteria

1. WHEN an Authorized_User sends any supported command (/run, /status, /help), THE Bot SHALL allow the command execution
2. THE Bot SHALL NOT implement per-user permission differentiation in the initial version
3. ALL users listed in TELEGRAM_AUTHORIZED_USERS SHALL have access to all available commands
4. THE Bot SHALL support future extension to per-user permissions if needed

### Requirement 8: Error Handling and Logging

**User Story:** As a system administrator, I want comprehensive logging of authorization decisions, so that I can audit and troubleshoot access issues.

#### Acceptance Criteria

1. WHEN the Bot validates a command, THE Bot SHALL log the User_ID, username, chat type, and authorization decision
2. WHEN authorization fails, THE Bot SHALL log the reason for failure (user not authorized or insufficient permissions)
3. WHEN authorization succeeds, THE Bot SHALL log the command being executed and the user who triggered it
4. THE Bot SHALL include chat context information (private vs group) in all authorization logs
