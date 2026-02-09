"""
Unit tests for Task 2.3: Update initialization logging

Tests that the logging in _load_authorized_users() and _resolve_all_usernames()
properly shows:
1. Total number of authorized users after all processing
2. Count of users from direct IDs
3. Count of users from resolved usernames
"""

import os
import pytest
import asyncio
import logging
from unittest.mock import Mock, AsyncMock, patch

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
        authorized_users=[],
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


def test_load_authorized_users_logging(caplog):
    """Test that _load_authorized_users logs direct IDs and usernames to resolve"""
    caplog.set_level(logging.INFO)
    
    handler = create_test_handler("123456789,@user1,987654321,@user2,@user3")
    
    # Verify the log message contains the counts
    log_text = caplog.text
    assert "Loaded 2 direct user IDs and 3 usernames to resolve" in log_text


@pytest.mark.asyncio
async def test_resolve_all_usernames_logging_with_breakdown(caplog):
    """Test that _resolve_all_usernames logs total users with breakdown"""
    caplog.set_level(logging.INFO)
    
    handler = create_test_handler("123456789,987654321,@user1,@user2,@user3")
    
    # Mock the application and bot
    handler.application = Mock()
    handler.application.bot = Mock()
    
    # Mock successful resolutions for 2 out of 3 usernames
    async def mock_get_chat(username):
        if username == "@user1":
            chat = Mock()
            chat.id = 111111111
            return chat
        elif username == "@user2":
            chat = Mock()
            chat.id = 222222222
            return chat
        else:
            raise Exception("User not found")
    
    handler.application.bot.get_chat = AsyncMock(side_effect=mock_get_chat)
    
    # Resolve usernames
    await handler._resolve_all_usernames()
    
    # Verify the log message contains:
    # - Resolution results (2 succeeded, 1 failed)
    # - Total authorized users (4 = 2 direct + 2 resolved)
    # - Breakdown (2 from direct IDs, 2 from resolved usernames)
    log_text = caplog.text
    assert "Username resolution complete: 2 succeeded, 1 failed" in log_text
    assert "Total authorized users: 4" in log_text
    assert "(2 from direct IDs, 2 from resolved usernames)" in log_text


@pytest.mark.asyncio
async def test_resolve_all_usernames_logging_only_direct_ids(caplog):
    """Test logging when there are only direct IDs (no usernames to resolve)"""
    caplog.set_level(logging.INFO)
    
    handler = create_test_handler("123456789,987654321,555555555")
    
    # Mock the application and bot
    handler.application = Mock()
    handler.application.bot = Mock()
    
    # No usernames to resolve
    await handler._resolve_all_usernames()
    
    # Should log that there are no usernames to resolve
    log_text = caplog.text
    assert "No usernames to resolve" in log_text


@pytest.mark.asyncio
async def test_resolve_all_usernames_logging_only_usernames(caplog):
    """Test logging when there are only usernames (no direct IDs)"""
    caplog.set_level(logging.INFO)
    
    handler = create_test_handler("@user1,@user2")
    
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
    
    # Resolve usernames
    await handler._resolve_all_usernames()
    
    # Verify the log shows 0 from direct IDs, 2 from resolved usernames
    log_text = caplog.text
    assert "Username resolution complete: 2 succeeded, 0 failed" in log_text
    assert "Total authorized users: 2" in log_text
    assert "(0 from direct IDs, 2 from resolved usernames)" in log_text


@pytest.mark.asyncio
async def test_resolve_all_usernames_logging_all_failed(caplog):
    """Test logging when all username resolutions fail"""
    caplog.set_level(logging.INFO)
    
    handler = create_test_handler("123456789,@user1,@user2")
    
    # Mock the application and bot
    handler.application = Mock()
    handler.application.bot = Mock()
    
    # Mock all failures
    handler.application.bot.get_chat = AsyncMock(side_effect=Exception("API error"))
    
    # Resolve usernames
    await handler._resolve_all_usernames()
    
    # Verify the log shows 0 succeeded, 2 failed
    # Total should be 1 (only the direct ID)
    log_text = caplog.text
    assert "Username resolution complete: 0 succeeded, 2 failed" in log_text
    assert "Total authorized users: 1" in log_text
    assert "(1 from direct IDs, 0 from resolved usernames)" in log_text


@pytest.mark.asyncio
async def test_real_world_example_logging(caplog):
    """Test logging with real-world example from user request"""
    caplog.set_level(logging.INFO)
    
    handler = create_test_handler("5844680524,@wingperp,@mcfangpy,@Huazero,@long0short")
    
    # Mock the application and bot
    handler.application = Mock()
    handler.application.bot = Mock()
    
    # Mock successful resolutions for all usernames
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
    
    # Verify initial logging
    log_text = caplog.text
    assert "Loaded 1 direct user IDs and 4 usernames to resolve" in log_text
    
    # Clear the log to focus on resolution logging
    caplog.clear()
    
    # Resolve usernames
    await handler._resolve_all_usernames()
    
    # Verify resolution logging
    log_text = caplog.text
    assert "Username resolution complete: 4 succeeded, 0 failed" in log_text
    assert "Total authorized users: 5" in log_text
    assert "(1 from direct IDs, 4 from resolved usernames)" in log_text


@pytest.mark.asyncio
async def test_logging_shows_correct_breakdown_after_partial_success(caplog):
    """Test that breakdown is correct when some resolutions succeed and some fail"""
    caplog.set_level(logging.INFO)
    
    handler = create_test_handler("111,222,333,@user1,@user2,@user3,@user4,@user5")
    
    # Mock the application and bot
    handler.application = Mock()
    handler.application.bot = Mock()
    
    # Mock 3 successful resolutions out of 5
    async def mock_get_chat(username):
        if username in ["@user1", "@user3", "@user5"]:
            chat = Mock()
            chat.id = hash(username) % 1000000000  # Generate a unique ID
            return chat
        else:
            raise Exception("User not found")
    
    handler.application.bot.get_chat = AsyncMock(side_effect=mock_get_chat)
    
    # Resolve usernames
    await handler._resolve_all_usernames()
    
    # Verify the breakdown: 3 direct IDs + 3 resolved = 6 total
    log_text = caplog.text
    assert "Username resolution complete: 3 succeeded, 2 failed" in log_text
    assert "Total authorized users: 6" in log_text
    assert "(3 from direct IDs, 3 from resolved usernames)" in log_text


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
