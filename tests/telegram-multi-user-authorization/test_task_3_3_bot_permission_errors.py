"""
Unit tests for Task 3.3: Handle bot permission errors

Tests that _resolve_username() properly handles bot permission errors:
- Catches permission denied errors from Telegram API
- Logs error with explanation about bot permissions
- Returns None from _resolve_username()
- Continues initialization with other entries

Requirements: 6.5
"""

import os
import pytest
import logging
from unittest.mock import Mock, patch, AsyncMock
from telegram.error import TelegramError, Forbidden

from crypto_news_analyzer.models import TelegramCommandConfig
from crypto_news_analyzer.reporters.telegram_command_handler import TelegramCommandHandler


class MockExecutionCoordinator:
    """Mock execution coordinator for testing"""
    
    def is_execution_running(self):
        return False
    
    def get_system_status(self):
        return {
            "initialized": True,
            "scheduler_running": False,
            "current_execution": None,
            "execution_history_count": 0,
            "next_execution_time": None
        }


def create_test_handler(env_value: str = "") -> TelegramCommandHandler:
    """Helper to create a test handler with mocked environment"""
    config = TelegramCommandConfig(
        enabled=True,
        authorized_users=[],  # Not used anymore
        execution_timeout_minutes=30,
        max_concurrent_executions=1,
        command_rate_limit={
            "max_commands_per_hour": 10,
            "cooldown_minutes": 5
        }
    )
    
    mock_coordinator = MockExecutionCoordinator()
    
    with patch.dict(os.environ, {'TELEGRAM_AUTHORIZED_USERS': env_value}):
        handler = TelegramCommandHandler(
            bot_token="test_token",
            execution_coordinator=mock_coordinator,
            config=config
        )
    
    return handler


@pytest.mark.asyncio
async def test_forbidden_error_handling(caplog):
    """
    Test that Forbidden (403) errors are caught and handled gracefully
    
    Requirements: 6.5 - Catch permission denied errors, log error, return None
    """
    caplog.set_level(logging.INFO)
    
    handler = create_test_handler("@restricted_user")
    
    # Mock the application and bot
    handler.application = Mock()
    handler.application.bot = Mock()
    
    # Simulate Forbidden error from Telegram API (bot lacks permissions)
    handler.application.bot.get_chat = AsyncMock(
        side_effect=Forbidden("Forbidden: bot was blocked by the user")
    )
    
    # Call _resolve_username directly
    result = await handler._resolve_username("@restricted_user")
    
    # Should return None
    assert result is None
    
    # Should log error with username and error message
    assert "Error resolving username @restricted_user" in caplog.text
    assert "Forbidden" in caplog.text or "bot was blocked" in caplog.text


@pytest.mark.asyncio
async def test_bot_blocked_by_user(caplog):
    """
    Test handling when bot is blocked by the user
    
    Requirements: 6.5 - Handle permission errors when bot is blocked
    """
    caplog.set_level(logging.INFO)
    
    handler = create_test_handler("@blocked_user")
    
    # Mock the application and bot
    handler.application = Mock()
    handler.application.bot = Mock()
    
    # Simulate bot blocked by user
    handler.application.bot.get_chat = AsyncMock(
        side_effect=Forbidden("Forbidden: bot was blocked by the user")
    )
    
    # Call _resolve_username directly
    result = await handler._resolve_username("@blocked_user")
    
    # Should return None
    assert result is None
    
    # Should log error
    assert "Error resolving username @blocked_user" in caplog.text


@pytest.mark.asyncio
async def test_bot_kicked_from_chat(caplog):
    """
    Test handling when bot was kicked from a chat
    
    Requirements: 6.5 - Handle permission errors when bot is kicked
    """
    caplog.set_level(logging.INFO)
    
    handler = create_test_handler("@kicked_user")
    
    # Mock the application and bot
    handler.application = Mock()
    handler.application.bot = Mock()
    
    # Simulate bot kicked from chat
    handler.application.bot.get_chat = AsyncMock(
        side_effect=Forbidden("Forbidden: bot was kicked from the group chat")
    )
    
    # Call _resolve_username directly
    result = await handler._resolve_username("@kicked_user")
    
    # Should return None
    assert result is None
    
    # Should log error
    assert "Error resolving username @kicked_user" in caplog.text


@pytest.mark.asyncio
async def test_insufficient_rights(caplog):
    """
    Test handling when bot has insufficient rights
    
    Requirements: 6.5 - Handle permission errors when bot lacks rights
    """
    caplog.set_level(logging.INFO)
    
    handler = create_test_handler("@no_rights_user")
    
    # Mock the application and bot
    handler.application = Mock()
    handler.application.bot = Mock()
    
    # Simulate insufficient rights
    handler.application.bot.get_chat = AsyncMock(
        side_effect=TelegramError("Bad Request: not enough rights to get chat")
    )
    
    # Call _resolve_username directly
    result = await handler._resolve_username("@no_rights_user")
    
    # Should return None
    assert result is None
    
    # Should log error
    assert "Error resolving username @no_rights_user" in caplog.text
    assert "not enough rights" in caplog.text.lower()


@pytest.mark.asyncio
async def test_continue_after_permission_error(caplog):
    """
    Test that initialization continues with other entries after permission error
    
    Requirements: 6.5 - Continue initialization with other entries
    """
    caplog.set_level(logging.INFO)
    
    handler = create_test_handler("@user1,@blocked_user,@user3")
    
    # Mock the application and bot
    handler.application = Mock()
    handler.application.bot = Mock()
    
    # Mock responses: first succeeds, second has permission error, third succeeds
    async def mock_get_chat(username):
        if username == "@user1":
            chat = Mock()
            chat.id = 111111111
            return chat
        elif username == "@blocked_user":
            raise Forbidden("Forbidden: bot was blocked by the user")
        elif username == "@user3":
            chat = Mock()
            chat.id = 333333333
            return chat
    
    handler.application.bot.get_chat = AsyncMock(side_effect=mock_get_chat)
    
    # Resolve all usernames
    await handler._resolve_all_usernames()
    
    # Should have resolved 2 out of 3 usernames
    assert len(handler._authorized_user_ids) == 2
    assert "111111111" in handler._authorized_user_ids
    assert "333333333" in handler._authorized_user_ids
    
    # Should have cached the successful resolutions
    assert handler._username_cache["@user1"] == "111111111"
    assert handler._username_cache["@user3"] == "333333333"
    assert "@blocked_user" not in handler._username_cache
    
    # Should have logged the failure
    assert "Error resolving username @blocked_user" in caplog.text
    
    # Should have completed resolution summary
    assert "Username resolution complete: 2 succeeded, 1 failed" in caplog.text


@pytest.mark.asyncio
async def test_mixed_permission_and_other_errors(caplog):
    """
    Test handling mixed permission errors and other error types
    
    Requirements: 6.5 - Handle permission errors alongside other error types
    """
    caplog.set_level(logging.INFO)
    
    handler = create_test_handler("@blocked,@not_found,@valid,@no_rights")
    
    # Mock the application and bot
    handler.application = Mock()
    handler.application.bot = Mock()
    
    # Different error types
    async def mock_get_chat(username):
        if username == "@blocked":
            raise Forbidden("Forbidden: bot was blocked by the user")
        elif username == "@not_found":
            raise TelegramError("User not found")
        elif username == "@valid":
            chat = Mock()
            chat.id = 555555555
            return chat
        elif username == "@no_rights":
            raise TelegramError("Bad Request: not enough rights")
    
    handler.application.bot.get_chat = AsyncMock(side_effect=mock_get_chat)
    
    # Resolve all usernames
    await handler._resolve_all_usernames()
    
    # Should have resolved 1 out of 4 usernames
    assert len(handler._authorized_user_ids) == 1
    assert "555555555" in handler._authorized_user_ids
    
    # Should have cached only the successful resolution
    assert handler._username_cache["@valid"] == "555555555"
    assert "@blocked" not in handler._username_cache
    assert "@not_found" not in handler._username_cache
    assert "@no_rights" not in handler._username_cache
    
    # Should have logged all failures
    assert "Error resolving username @blocked" in caplog.text
    assert "Error resolving username @not_found" in caplog.text
    assert "Error resolving username @no_rights" in caplog.text
    
    # Should have completion summary
    assert "Username resolution complete: 1 succeeded, 3 failed" in caplog.text


@pytest.mark.asyncio
async def test_mixed_direct_ids_and_permission_errors(caplog):
    """
    Test mixed scenario with direct IDs and permission errors
    
    Requirements: 6.5 - Handle permission errors while processing mixed format
    """
    caplog.set_level(logging.INFO)
    
    handler = create_test_handler("123456789,@blocked_user,987654321,@valid_user")
    
    # Mock the application and bot
    handler.application = Mock()
    handler.application.bot = Mock()
    
    async def mock_get_chat(username):
        if username == "@blocked_user":
            raise Forbidden("Forbidden: bot was blocked by the user")
        elif username == "@valid_user":
            chat = Mock()
            chat.id = 555555555
            return chat
    
    handler.application.bot.get_chat = AsyncMock(side_effect=mock_get_chat)
    
    # Initial state: 2 direct user IDs
    assert len(handler._authorized_user_ids) == 2
    assert "123456789" in handler._authorized_user_ids
    assert "987654321" in handler._authorized_user_ids
    
    # Resolve usernames
    await handler._resolve_all_usernames()
    
    # Should have 3 authorized users (2 direct + 1 resolved)
    assert len(handler._authorized_user_ids) == 3
    assert "123456789" in handler._authorized_user_ids
    assert "987654321" in handler._authorized_user_ids
    assert "555555555" in handler._authorized_user_ids
    
    # Should have cached the successful resolution
    assert handler._username_cache["@valid_user"] == "555555555"
    assert "@blocked_user" not in handler._username_cache
    
    # Should have logged the failure
    assert "Error resolving username @blocked_user" in caplog.text
    
    # Should have completion summary showing mixed results
    assert "Username resolution complete: 1 succeeded, 1 failed" in caplog.text
    assert "Total authorized users: 3" in caplog.text


@pytest.mark.asyncio
async def test_permission_error_does_not_crash_bot():
    """
    Test that permission errors during username resolution don't crash the bot
    
    Requirements: 6.5 - Bot remains operational after permission errors
    """
    handler = create_test_handler("@blocked_user,123456789")
    
    # Mock the application and bot
    handler.application = Mock()
    handler.application.bot = Mock()
    
    # Simulate permission error
    handler.application.bot.get_chat = AsyncMock(
        side_effect=Forbidden("Forbidden: bot was blocked by the user")
    )
    
    # Resolve usernames (should not crash)
    await handler._resolve_all_usernames()
    
    # Bot should still be operational with the direct user ID
    assert len(handler._authorized_user_ids) == 1
    assert "123456789" in handler._authorized_user_ids
    
    # Handler should still be functional
    assert handler.config.enabled is True


@pytest.mark.asyncio
async def test_authorization_check_after_permission_error():
    """
    Test that authorization correctly rejects users whose usernames failed due to permission errors
    
    Requirements: 6.5 - Permission errors should result in user not being authorized
    """
    handler = create_test_handler("@valid_user,@blocked_user")
    
    # Mock the application and bot
    handler.application = Mock()
    handler.application.bot = Mock()
    
    async def mock_get_chat(username):
        if username == "@valid_user":
            chat = Mock()
            chat.id = 111111111
            return chat
        else:
            raise Forbidden("Forbidden: bot was blocked by the user")
    
    handler.application.bot.get_chat = AsyncMock(side_effect=mock_get_chat)
    
    # Resolve usernames
    await handler._resolve_all_usernames()
    
    # Verify that only the valid user ID is in the authorized set
    assert "111111111" in handler._authorized_user_ids
    assert len(handler._authorized_user_ids) == 1
    
    # Verify the failed username is not in the cache
    assert "@valid_user" in handler._username_cache
    assert "@blocked_user" not in handler._username_cache


@pytest.mark.asyncio
async def test_all_permission_errors(caplog):
    """
    Test handling when all usernames fail due to permission errors
    
    Requirements: 6.5 - Handle all usernames failing with permission errors
    """
    caplog.set_level(logging.INFO)
    
    handler = create_test_handler("@blocked1,@blocked2,@blocked3")
    
    # Mock the application and bot
    handler.application = Mock()
    handler.application.bot = Mock()
    
    # All users have permission errors
    handler.application.bot.get_chat = AsyncMock(
        side_effect=Forbidden("Forbidden: bot was blocked by the user")
    )
    
    # Resolve all usernames (should not crash)
    await handler._resolve_all_usernames()
    
    # Should have no authorized users
    assert len(handler._authorized_user_ids) == 0
    assert len(handler._username_cache) == 0
    
    # Should have logged all failures
    assert "Error resolving username @blocked1" in caplog.text
    assert "Error resolving username @blocked2" in caplog.text
    assert "Error resolving username @blocked3" in caplog.text
    
    # Should have completion summary
    assert "Username resolution complete: 0 succeeded, 3 failed" in caplog.text


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
