"""
Unit tests for Task 2.2: Username resolution loop in _resolve_all_usernames()

Tests the resolution of @username entries to user IDs using Telegram Bot API,
caching of mappings, and error handling during resolution.
"""

import os
import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock

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
async def test_resolve_all_usernames_success():
    """Test successful resolution of all usernames"""
    handler = create_test_handler("123456789,@user1,@user2")
    
    # Mock the application and bot
    handler.application = Mock()
    handler.application.bot = Mock()
    
    # Mock successful resolutions
    async def mock_get_chat(username):
        chat = Mock()
        if username == "@user1":
            chat.id = 111111111
        elif username == "@user2":
            chat.id = 222222222
        return chat
    
    handler.application.bot.get_chat = AsyncMock(side_effect=mock_get_chat)
    
    # Initial state: only direct user ID
    assert len(handler._authorized_user_ids) == 1
    assert "123456789" in handler._authorized_user_ids
    assert len(handler._usernames_to_resolve) == 2
    
    # Resolve usernames
    await handler._resolve_all_usernames()
    
    # After resolution: should have all 3 user IDs
    assert len(handler._authorized_user_ids) == 3
    assert "123456789" in handler._authorized_user_ids
    assert "111111111" in handler._authorized_user_ids
    assert "222222222" in handler._authorized_user_ids
    
    # Check cache
    assert handler._username_cache["@user1"] == "111111111"
    assert handler._username_cache["@user2"] == "222222222"


@pytest.mark.asyncio
async def test_resolve_all_usernames_partial_failure():
    """Test resolution with some usernames failing"""
    handler = create_test_handler("@user1,@user2,@user3")
    
    # Mock the application and bot
    handler.application = Mock()
    handler.application.bot = Mock()
    
    # Mock mixed success/failure
    async def mock_get_chat(username):
        if username == "@user1":
            chat = Mock()
            chat.id = 111111111
            return chat
        elif username == "@user2":
            raise Exception("User not found")
        elif username == "@user3":
            chat = Mock()
            chat.id = 333333333
            return chat
    
    handler.application.bot.get_chat = AsyncMock(side_effect=mock_get_chat)
    
    # Initial state: no direct user IDs
    assert len(handler._authorized_user_ids) == 0
    assert len(handler._usernames_to_resolve) == 3
    
    # Resolve usernames (should not crash on error)
    await handler._resolve_all_usernames()
    
    # After resolution: should have 2 successful resolutions
    assert len(handler._authorized_user_ids) == 2
    assert "111111111" in handler._authorized_user_ids
    assert "333333333" in handler._authorized_user_ids
    
    # Check cache (only successful resolutions)
    assert handler._username_cache["@user1"] == "111111111"
    assert handler._username_cache["@user3"] == "333333333"
    assert "@user2" not in handler._username_cache


@pytest.mark.asyncio
async def test_resolve_all_usernames_all_fail(caplog):
    """Test resolution when all usernames fail"""
    handler = create_test_handler("@user1,@user2")
    
    # Mock the application and bot
    handler.application = Mock()
    handler.application.bot = Mock()
    
    # Mock all failures
    handler.application.bot.get_chat = AsyncMock(side_effect=Exception("API error"))
    
    # Initial state
    assert len(handler._authorized_user_ids) == 0
    assert len(handler._usernames_to_resolve) == 2
    
    # Resolve usernames (should not crash)
    await handler._resolve_all_usernames()
    
    # After resolution: no new user IDs added
    assert len(handler._authorized_user_ids) == 0
    assert len(handler._username_cache) == 0
    
    # Check that errors were logged
    assert "Error resolving username @user1" in caplog.text
    assert "Error resolving username @user2" in caplog.text


@pytest.mark.asyncio
async def test_resolve_all_usernames_empty_list():
    """Test resolution with no usernames to resolve"""
    handler = create_test_handler("123456789,987654321")
    
    # Mock the application and bot
    handler.application = Mock()
    handler.application.bot = Mock()
    
    # Initial state: only direct user IDs
    assert len(handler._authorized_user_ids) == 2
    assert len(handler._usernames_to_resolve) == 0
    
    # Resolve usernames (should do nothing)
    await handler._resolve_all_usernames()
    
    # After resolution: no changes
    assert len(handler._authorized_user_ids) == 2
    assert len(handler._username_cache) == 0
    
    # Bot API should not be called
    handler.application.bot.get_chat.assert_not_called()


@pytest.mark.asyncio
async def test_resolve_all_usernames_mixed_format():
    """Test resolution with mixed user IDs and usernames"""
    handler = create_test_handler("5844680524,@wingperp,@mcfangpy,@Huazero,@long0short")
    
    # Mock the application and bot
    handler.application = Mock()
    handler.application.bot = Mock()
    
    # Mock successful resolutions
    user_id_map = {
        "@wingperp": 111111111,
        "@mcfangpy": 222222222,
        "@Huazero": 333333333,
        "@long0short": 444444444
    }
    
    async def mock_get_chat(username):
        chat = Mock()
        chat.id = user_id_map.get(username)
        return chat
    
    handler.application.bot.get_chat = AsyncMock(side_effect=mock_get_chat)
    
    # Initial state
    assert len(handler._authorized_user_ids) == 1
    assert "5844680524" in handler._authorized_user_ids
    assert len(handler._usernames_to_resolve) == 4
    
    # Resolve usernames
    await handler._resolve_all_usernames()
    
    # After resolution: should have all 5 user IDs
    assert len(handler._authorized_user_ids) == 5
    assert "5844680524" in handler._authorized_user_ids
    assert "111111111" in handler._authorized_user_ids
    assert "222222222" in handler._authorized_user_ids
    assert "333333333" in handler._authorized_user_ids
    assert "444444444" in handler._authorized_user_ids
    
    # Check cache
    assert len(handler._username_cache) == 4
    assert handler._username_cache["@wingperp"] == "111111111"
    assert handler._username_cache["@mcfangpy"] == "222222222"
    assert handler._username_cache["@Huazero"] == "333333333"
    assert handler._username_cache["@long0short"] == "444444444"


@pytest.mark.asyncio
async def test_resolve_username_returns_none():
    """Test handling when _resolve_username returns None"""
    handler = create_test_handler("@user1,@user2")
    
    # Mock the application and bot
    handler.application = Mock()
    handler.application.bot = Mock()
    
    # Mock one success, one returns None (user not found)
    async def mock_get_chat(username):
        if username == "@user1":
            chat = Mock()
            chat.id = 111111111
            return chat
        elif username == "@user2":
            # Return None to simulate user not found
            return None
    
    handler.application.bot.get_chat = AsyncMock(side_effect=mock_get_chat)
    
    # Resolve usernames
    await handler._resolve_all_usernames()
    
    # After resolution: only successful resolution
    assert len(handler._authorized_user_ids) == 1
    assert "111111111" in handler._authorized_user_ids
    
    # Check cache (only successful resolution)
    assert handler._username_cache["@user1"] == "111111111"
    assert "@user2" not in handler._username_cache


@pytest.mark.asyncio
async def test_resolve_username_chat_without_id():
    """Test handling when chat object has no id"""
    handler = create_test_handler("@user1")
    
    # Mock the application and bot
    handler.application = Mock()
    handler.application.bot = Mock()
    
    # Mock chat without id
    async def mock_get_chat(username):
        chat = Mock()
        chat.id = None  # No ID
        return chat
    
    handler.application.bot.get_chat = AsyncMock(side_effect=mock_get_chat)
    
    # Resolve usernames
    await handler._resolve_all_usernames()
    
    # After resolution: no user IDs added
    assert len(handler._authorized_user_ids) == 0
    assert len(handler._username_cache) == 0


@pytest.mark.asyncio
async def test_authorization_with_resolved_username():
    """Test that resolved usernames are added to authorized set"""
    handler = create_test_handler("123456789,@testuser")
    
    # Mock the application and bot
    handler.application = Mock()
    handler.application.bot = Mock()
    
    # Mock successful resolution
    async def mock_get_chat(username):
        chat = Mock()
        chat.id = 999999999
        return chat
    
    handler.application.bot.get_chat = AsyncMock(side_effect=mock_get_chat)
    
    # Before resolution: only direct user ID is in the set
    assert "123456789" in handler._authorized_user_ids
    assert "999999999" not in handler._authorized_user_ids
    
    # Resolve usernames
    await handler._resolve_all_usernames()
    
    # After resolution: both direct ID and resolved ID are in the set
    assert "123456789" in handler._authorized_user_ids
    assert "999999999" in handler._authorized_user_ids
    assert "111111111" not in handler._authorized_user_ids  # Not authorized


@pytest.mark.asyncio
async def test_logging_during_resolution(caplog):
    """Test that resolution logs appropriate messages"""
    import logging
    caplog.set_level(logging.INFO)
    
    handler = create_test_handler("@user1,@user2")
    
    # Mock the application and bot
    handler.application = Mock()
    handler.application.bot = Mock()
    
    # Mock one success, one failure
    async def mock_get_chat(username):
        if username == "@user1":
            chat = Mock()
            chat.id = 111111111
            return chat
        else:
            raise Exception("User not found")
    
    handler.application.bot.get_chat = AsyncMock(side_effect=mock_get_chat)
    
    # Resolve usernames
    await handler._resolve_all_usernames()
    
    # Check logging - verify key messages are present
    log_text = caplog.text
    assert "Resolving 2 usernames" in log_text
    assert "Successfully resolved @user1 to user_id 111111111" in log_text
    assert "Error resolving username @user2" in log_text
    assert "Username resolution complete: 1 succeeded, 1 failed" in log_text


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
