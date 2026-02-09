"""
Unit tests for Task 3.1: Handle user not found errors

Tests that _resolve_username() properly handles user not found scenarios:
- Catches user not found exceptions from Telegram API
- Logs warning with username
- Returns None from _resolve_username()
- Continues initialization with other entries

Requirements: 6.4
"""

import os
import pytest
import logging
from unittest.mock import Mock, patch, AsyncMock
from telegram.error import TelegramError

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
async def test_user_not_found_exception(caplog):
    """
    Test that user not found exceptions are caught and handled gracefully
    
    Requirements: 6.4 - Catch user not found exceptions, log warning, return None
    """
    caplog.set_level(logging.INFO)
    
    handler = create_test_handler("@nonexistent_user")
    
    # Mock the application and bot
    handler.application = Mock()
    handler.application.bot = Mock()
    
    # Simulate user not found error from Telegram API
    handler.application.bot.get_chat = AsyncMock(
        side_effect=TelegramError("User not found")
    )
    
    # Call _resolve_username directly
    result = await handler._resolve_username("@nonexistent_user")
    
    # Should return None
    assert result is None
    
    # Should log error with username
    assert "Error resolving username @nonexistent_user" in caplog.text
    assert "User not found" in caplog.text


@pytest.mark.asyncio
async def test_user_not_found_returns_none_chat(caplog):
    """
    Test that when getChat returns None, it's handled as user not found
    
    Requirements: 6.4 - Handle user not found, log warning, return None
    """
    caplog.set_level(logging.INFO)
    
    handler = create_test_handler("@user_with_no_chat")
    
    # Mock the application and bot
    handler.application = Mock()
    handler.application.bot = Mock()
    
    # Simulate getChat returning None (user not found)
    handler.application.bot.get_chat = AsyncMock(return_value=None)
    
    # Call _resolve_username directly
    result = await handler._resolve_username("@user_with_no_chat")
    
    # Should return None
    assert result is None
    
    # Should log warning
    assert "Could not resolve username @user_with_no_chat: user not found" in caplog.text


@pytest.mark.asyncio
async def test_user_not_found_chat_without_id(caplog):
    """
    Test that when chat object has no ID, it's handled as user not found
    
    Requirements: 6.4 - Handle user not found, log warning, return None
    """
    caplog.set_level(logging.INFO)
    
    handler = create_test_handler("@user_no_id")
    
    # Mock the application and bot
    handler.application = Mock()
    handler.application.bot = Mock()
    
    # Simulate chat object without ID
    mock_chat = Mock()
    mock_chat.id = None
    handler.application.bot.get_chat = AsyncMock(return_value=mock_chat)
    
    # Call _resolve_username directly
    result = await handler._resolve_username("@user_no_id")
    
    # Should return None
    assert result is None
    
    # Should log warning
    assert "Could not resolve username @user_no_id: user not found" in caplog.text


@pytest.mark.asyncio
async def test_continue_with_other_entries_after_user_not_found(caplog):
    """
    Test that initialization continues with other entries when one user is not found
    
    Requirements: 6.4 - Continue initialization with other entries
    """
    caplog.set_level(logging.INFO)
    
    handler = create_test_handler("@valid_user,@nonexistent_user,@another_valid_user")
    
    # Mock the application and bot
    handler.application = Mock()
    handler.application.bot = Mock()
    
    # Mock responses: first succeeds, second fails (user not found), third succeeds
    call_count = [0]
    
    async def mock_get_chat(username):
        call_count[0] += 1
        if username == "@valid_user":
            chat = Mock()
            chat.id = 111111111
            return chat
        elif username == "@nonexistent_user":
            raise TelegramError("User not found")
        elif username == "@another_valid_user":
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
    assert handler._username_cache["@valid_user"] == "111111111"
    assert handler._username_cache["@another_valid_user"] == "333333333"
    assert "@nonexistent_user" not in handler._username_cache
    
    # Should have logged the failure
    assert "Error resolving username @nonexistent_user" in caplog.text
    
    # Should have completed resolution summary
    assert "Username resolution complete: 2 succeeded, 1 failed" in caplog.text


@pytest.mark.asyncio
async def test_multiple_user_not_found_errors(caplog):
    """
    Test handling multiple user not found errors in a single initialization
    
    Requirements: 6.4 - Handle multiple user not found errors gracefully
    """
    caplog.set_level(logging.INFO)
    
    handler = create_test_handler("@user1,@user2,@user3")
    
    # Mock the application and bot
    handler.application = Mock()
    handler.application.bot = Mock()
    
    # All users not found
    handler.application.bot.get_chat = AsyncMock(
        side_effect=TelegramError("User not found")
    )
    
    # Resolve all usernames (should not crash)
    await handler._resolve_all_usernames()
    
    # Should have no authorized users
    assert len(handler._authorized_user_ids) == 0
    assert len(handler._username_cache) == 0
    
    # Should have logged all failures
    assert "Error resolving username @user1" in caplog.text
    assert "Error resolving username @user2" in caplog.text
    assert "Error resolving username @user3" in caplog.text
    
    # Should have completion summary
    assert "Username resolution complete: 0 succeeded, 3 failed" in caplog.text


@pytest.mark.asyncio
async def test_mixed_success_and_user_not_found(caplog):
    """
    Test mixed scenario with direct IDs, successful username resolution, and user not found
    
    Requirements: 6.4 - Handle user not found while processing mixed format
    """
    caplog.set_level(logging.INFO)
    
    handler = create_test_handler("123456789,@valid_user,@nonexistent,987654321")
    
    # Mock the application and bot
    handler.application = Mock()
    handler.application.bot = Mock()
    
    async def mock_get_chat(username):
        if username == "@valid_user":
            chat = Mock()
            chat.id = 555555555
            return chat
        elif username == "@nonexistent":
            raise TelegramError("User not found")
    
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
    assert "@nonexistent" not in handler._username_cache
    
    # Should have logged the failure
    assert "Error resolving username @nonexistent" in caplog.text
    
    # Should have completion summary showing mixed results
    assert "Username resolution complete: 1 succeeded, 1 failed" in caplog.text
    assert "Total authorized users: 3" in caplog.text


@pytest.mark.asyncio
async def test_username_with_at_prefix_stripped(caplog):
    """
    Test that @ prefix is properly stripped before logging in error cases
    
    Requirements: 6.4 - Log warning with username (properly formatted)
    """
    caplog.set_level(logging.INFO)
    
    handler = create_test_handler("@testuser")
    
    # Mock the application and bot
    handler.application = Mock()
    handler.application.bot = Mock()
    
    # Simulate user not found
    handler.application.bot.get_chat = AsyncMock(
        side_effect=TelegramError("User not found")
    )
    
    # Call _resolve_username with @ prefix
    result = await handler._resolve_username("@testuser")
    
    # Should return None
    assert result is None
    
    # Should log with @ prefix in the error message
    assert "Error resolving username @testuser" in caplog.text


@pytest.mark.asyncio
async def test_authorization_check_after_user_not_found():
    """
    Test that authorization correctly rejects users whose usernames failed to resolve
    
    Requirements: 6.4 - User not found should result in user not being authorized
    
    Note: This test verifies that _authorized_user_ids is correctly populated.
    Full authorization check will work once task 5.1 updates is_authorized_user().
    """
    handler = create_test_handler("@valid_user,@nonexistent_user")
    
    # Mock the application and bot
    handler.application = Mock()
    handler.application.bot = Mock()
    
    async def mock_get_chat(username):
        if username == "@valid_user":
            chat = Mock()
            chat.id = 111111111
            return chat
        else:
            raise TelegramError("User not found")
    
    handler.application.bot.get_chat = AsyncMock(side_effect=mock_get_chat)
    
    # Resolve usernames
    await handler._resolve_all_usernames()
    
    # Verify that only the valid user ID is in the authorized set
    assert "111111111" in handler._authorized_user_ids
    assert "999999999" not in handler._authorized_user_ids
    assert "123456789" not in handler._authorized_user_ids
    
    # Verify the failed username is not in the cache
    assert "@valid_user" in handler._username_cache
    assert "@nonexistent_user" not in handler._username_cache


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
