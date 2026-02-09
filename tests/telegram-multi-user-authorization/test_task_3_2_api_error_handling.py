"""
Unit tests for Task 3.2: Handle API errors during resolution

Tests that _resolve_username() properly handles various API errors:
- Network errors
- Rate limit errors
- Timeout errors
- Permission errors
- General API exceptions
- Logs error with username and error message
- Returns None from _resolve_username()
- Continues initialization with other entries

Requirements: 6.5
"""

import os
import pytest
import logging
from unittest.mock import Mock, patch, AsyncMock
from telegram.error import TelegramError, NetworkError, TimedOut, RetryAfter

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
async def test_network_error_handling(caplog):
    """
    Test that network errors are caught and handled gracefully
    
    Requirements: 6.5 - Catch general API exceptions, log error, return None
    """
    caplog.set_level(logging.INFO)
    
    handler = create_test_handler("@user_network_error")
    
    # Mock the application and bot
    handler.application = Mock()
    handler.application.bot = Mock()
    
    # Simulate network error from Telegram API
    handler.application.bot.get_chat = AsyncMock(
        side_effect=NetworkError("Connection failed")
    )
    
    # Call _resolve_username directly
    result = await handler._resolve_username("@user_network_error")
    
    # Should return None
    assert result is None
    
    # Should log error with username and error message
    assert "Error resolving username @user_network_error" in caplog.text
    assert "Connection failed" in caplog.text


@pytest.mark.asyncio
async def test_timeout_error_handling(caplog):
    """
    Test that timeout errors are caught and handled gracefully
    
    Requirements: 6.5 - Catch general API exceptions, log error, return None
    """
    caplog.set_level(logging.INFO)
    
    handler = create_test_handler("@user_timeout")
    
    # Mock the application and bot
    handler.application = Mock()
    handler.application.bot = Mock()
    
    # Simulate timeout error from Telegram API
    handler.application.bot.get_chat = AsyncMock(
        side_effect=TimedOut("Request timed out")
    )
    
    # Call _resolve_username directly
    result = await handler._resolve_username("@user_timeout")
    
    # Should return None
    assert result is None
    
    # Should log error with username and error message
    assert "Error resolving username @user_timeout" in caplog.text
    assert "Request timed out" in caplog.text


@pytest.mark.asyncio
async def test_rate_limit_error_handling(caplog):
    """
    Test that rate limit errors are caught and handled gracefully
    
    Requirements: 6.5 - Catch general API exceptions, log error, return None
    """
    caplog.set_level(logging.INFO)
    
    handler = create_test_handler("@user_rate_limited")
    
    # Mock the application and bot
    handler.application = Mock()
    handler.application.bot = Mock()
    
    # Simulate rate limit error from Telegram API
    handler.application.bot.get_chat = AsyncMock(
        side_effect=RetryAfter(30)  # Rate limited, retry after 30 seconds
    )
    
    # Call _resolve_username directly
    result = await handler._resolve_username("@user_rate_limited")
    
    # Should return None
    assert result is None
    
    # Should log error with username and error message
    assert "Error resolving username @user_rate_limited" in caplog.text


@pytest.mark.asyncio
async def test_generic_telegram_error_handling(caplog):
    """
    Test that generic Telegram API errors are caught and handled gracefully
    
    Requirements: 6.5 - Catch general API exceptions, log error, return None
    """
    caplog.set_level(logging.INFO)
    
    handler = create_test_handler("@user_api_error")
    
    # Mock the application and bot
    handler.application = Mock()
    handler.application.bot = Mock()
    
    # Simulate generic Telegram API error
    handler.application.bot.get_chat = AsyncMock(
        side_effect=TelegramError("Bad Request: chat not found")
    )
    
    # Call _resolve_username directly
    result = await handler._resolve_username("@user_api_error")
    
    # Should return None
    assert result is None
    
    # Should log error with username and error message
    assert "Error resolving username @user_api_error" in caplog.text
    assert "chat not found" in caplog.text.lower()


@pytest.mark.asyncio
async def test_generic_exception_handling(caplog):
    """
    Test that generic Python exceptions are caught and handled gracefully
    
    Requirements: 6.5 - Catch general API exceptions, log error, return None
    """
    caplog.set_level(logging.INFO)
    
    handler = create_test_handler("@user_exception")
    
    # Mock the application and bot
    handler.application = Mock()
    handler.application.bot = Mock()
    
    # Simulate generic Python exception
    handler.application.bot.get_chat = AsyncMock(
        side_effect=ValueError("Invalid username format")
    )
    
    # Call _resolve_username directly
    result = await handler._resolve_username("@user_exception")
    
    # Should return None
    assert result is None
    
    # Should log error with username and error message
    assert "Error resolving username @user_exception" in caplog.text
    assert "Invalid username format" in caplog.text


@pytest.mark.asyncio
async def test_continue_after_api_error(caplog):
    """
    Test that initialization continues with other entries after API error
    
    Requirements: 6.5 - Continue initialization with other entries
    """
    caplog.set_level(logging.INFO)
    
    handler = create_test_handler("@user1,@user2,@user3")
    
    # Mock the application and bot
    handler.application = Mock()
    handler.application.bot = Mock()
    
    # Mock responses: first succeeds, second has network error, third succeeds
    async def mock_get_chat(username):
        if username == "@user1":
            chat = Mock()
            chat.id = 111111111
            return chat
        elif username == "@user2":
            raise NetworkError("Connection failed")
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
    assert "@user2" not in handler._username_cache
    
    # Should have logged the failure
    assert "Error resolving username @user2" in caplog.text
    assert "Connection failed" in caplog.text
    
    # Should have completed resolution summary
    assert "Username resolution complete: 2 succeeded, 1 failed" in caplog.text


@pytest.mark.asyncio
async def test_multiple_different_api_errors(caplog):
    """
    Test handling multiple different types of API errors in a single initialization
    
    Requirements: 6.5 - Handle multiple API errors gracefully
    """
    caplog.set_level(logging.INFO)
    
    handler = create_test_handler("@user1,@user2,@user3,@user4")
    
    # Mock the application and bot
    handler.application = Mock()
    handler.application.bot = Mock()
    
    # Different error types for each username
    async def mock_get_chat(username):
        if username == "@user1":
            raise NetworkError("Connection failed")
        elif username == "@user2":
            raise TimedOut("Request timed out")
        elif username == "@user3":
            raise RetryAfter(30)
        elif username == "@user4":
            raise TelegramError("Bad Request")
    
    handler.application.bot.get_chat = AsyncMock(side_effect=mock_get_chat)
    
    # Resolve all usernames (should not crash)
    await handler._resolve_all_usernames()
    
    # Should have no authorized users
    assert len(handler._authorized_user_ids) == 0
    assert len(handler._username_cache) == 0
    
    # Should have logged all failures with different error messages
    assert "Error resolving username @user1" in caplog.text
    assert "Connection failed" in caplog.text
    assert "Error resolving username @user2" in caplog.text
    assert "Request timed out" in caplog.text
    assert "Error resolving username @user3" in caplog.text
    assert "Error resolving username @user4" in caplog.text
    assert "Bad Request" in caplog.text
    
    # Should have completion summary
    assert "Username resolution complete: 0 succeeded, 4 failed" in caplog.text


@pytest.mark.asyncio
async def test_mixed_success_and_api_errors(caplog):
    """
    Test mixed scenario with direct IDs, successful resolution, and various API errors
    
    Requirements: 6.5 - Handle API errors while processing mixed format
    """
    caplog.set_level(logging.INFO)
    
    handler = create_test_handler("123456789,@valid_user,@network_error,987654321,@timeout_error")
    
    # Mock the application and bot
    handler.application = Mock()
    handler.application.bot = Mock()
    
    async def mock_get_chat(username):
        if username == "@valid_user":
            chat = Mock()
            chat.id = 555555555
            return chat
        elif username == "@network_error":
            raise NetworkError("Connection failed")
        elif username == "@timeout_error":
            raise TimedOut("Request timed out")
    
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
    assert "@network_error" not in handler._username_cache
    assert "@timeout_error" not in handler._username_cache
    
    # Should have logged the failures
    assert "Error resolving username @network_error" in caplog.text
    assert "Connection failed" in caplog.text
    assert "Error resolving username @timeout_error" in caplog.text
    assert "Request timed out" in caplog.text
    
    # Should have completion summary showing mixed results
    assert "Username resolution complete: 1 succeeded, 2 failed" in caplog.text
    assert "Total authorized users: 3" in caplog.text


@pytest.mark.asyncio
async def test_api_error_does_not_crash_bot():
    """
    Test that API errors during username resolution don't crash the bot initialization
    
    Requirements: 6.5 - Continue initialization with other entries (bot remains operational)
    """
    handler = create_test_handler("@error_user,123456789")
    
    # Mock the application and bot
    handler.application = Mock()
    handler.application.bot = Mock()
    
    # Simulate API error
    handler.application.bot.get_chat = AsyncMock(
        side_effect=NetworkError("Connection failed")
    )
    
    # Resolve usernames (should not crash)
    await handler._resolve_all_usernames()
    
    # Bot should still be operational with the direct user ID
    assert len(handler._authorized_user_ids) == 1
    assert "123456789" in handler._authorized_user_ids
    
    # Handler should still be functional
    assert handler.config.enabled is True


@pytest.mark.asyncio
async def test_authorization_check_after_api_error():
    """
    Test that authorization correctly rejects users whose usernames failed to resolve due to API errors
    
    Requirements: 6.5 - API errors should result in user not being authorized
    """
    handler = create_test_handler("@valid_user,@api_error_user")
    
    # Mock the application and bot
    handler.application = Mock()
    handler.application.bot = Mock()
    
    async def mock_get_chat(username):
        if username == "@valid_user":
            chat = Mock()
            chat.id = 111111111
            return chat
        else:
            raise NetworkError("Connection failed")
    
    handler.application.bot.get_chat = AsyncMock(side_effect=mock_get_chat)
    
    # Resolve usernames
    await handler._resolve_all_usernames()
    
    # Verify that only the valid user ID is in the authorized set
    assert "111111111" in handler._authorized_user_ids
    assert len(handler._authorized_user_ids) == 1
    
    # Verify the failed username is not in the cache
    assert "@valid_user" in handler._username_cache
    assert "@api_error_user" not in handler._username_cache


@pytest.mark.asyncio
async def test_error_message_includes_username_and_details(caplog):
    """
    Test that error logs include both username and detailed error message
    
    Requirements: 6.5 - Log error with username and error message
    """
    caplog.set_level(logging.INFO)
    
    handler = create_test_handler("@test_user")
    
    # Mock the application and bot
    handler.application = Mock()
    handler.application.bot = Mock()
    
    # Simulate detailed error message
    detailed_error = "Bad Request: chat not found - The username does not exist or the bot has no access"
    handler.application.bot.get_chat = AsyncMock(
        side_effect=TelegramError(detailed_error)
    )
    
    # Call _resolve_username
    result = await handler._resolve_username("@test_user")
    
    # Should return None
    assert result is None
    
    # Should log error with both username and full error details
    assert "Error resolving username @test_user" in caplog.text
    # Check for the key parts of the error message (case-insensitive)
    assert "chat not found" in caplog.text.lower()
    assert "username does not exist" in caplog.text.lower() or "bot has no access" in caplog.text.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
