"""
Unit tests for Task 2.1: _load_authorized_users() method

Tests the parsing of TELEGRAM_AUTHORIZED_USERS environment variable
to identify numeric user IDs and @username entries.
"""

import os
import pytest
from unittest.mock import Mock, patch

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


def test_load_only_user_ids():
    """Test parsing with only numeric user IDs"""
    handler = create_test_handler("123456789,987654321")
    
    assert len(handler._authorized_user_ids) == 2
    assert "123456789" in handler._authorized_user_ids
    assert "987654321" in handler._authorized_user_ids
    assert len(handler._usernames_to_resolve) == 0


def test_load_only_usernames():
    """Test parsing with only @username entries"""
    handler = create_test_handler("@user1,@user2,@user3")
    
    assert len(handler._authorized_user_ids) == 0
    assert len(handler._usernames_to_resolve) == 3
    assert "@user1" in handler._usernames_to_resolve
    assert "@user2" in handler._usernames_to_resolve
    assert "@user3" in handler._usernames_to_resolve


def test_load_mixed_format():
    """Test parsing with mixed user IDs and usernames"""
    handler = create_test_handler("123456789,@user1,987654321,@user2")
    
    assert len(handler._authorized_user_ids) == 2
    assert "123456789" in handler._authorized_user_ids
    assert "987654321" in handler._authorized_user_ids
    
    assert len(handler._usernames_to_resolve) == 2
    assert "@user1" in handler._usernames_to_resolve
    assert "@user2" in handler._usernames_to_resolve


def test_load_with_spaces():
    """Test parsing with spaces around entries"""
    handler = create_test_handler(" 123456789 , @user1 , 987654321 ")
    
    assert len(handler._authorized_user_ids) == 2
    assert "123456789" in handler._authorized_user_ids
    assert "987654321" in handler._authorized_user_ids
    
    assert len(handler._usernames_to_resolve) == 1
    assert "@user1" in handler._usernames_to_resolve


def test_load_with_invalid_entries(caplog):
    """Test parsing with invalid entries - should log warnings and skip"""
    handler = create_test_handler("123456789,invalid_entry,@user1,another-bad")
    
    assert len(handler._authorized_user_ids) == 1
    assert "123456789" in handler._authorized_user_ids
    
    assert len(handler._usernames_to_resolve) == 1
    assert "@user1" in handler._usernames_to_resolve
    
    # Check that warnings were logged for invalid entries
    assert "Invalid entry in TELEGRAM_AUTHORIZED_USERS: invalid_entry" in caplog.text
    assert "Invalid entry in TELEGRAM_AUTHORIZED_USERS: another-bad" in caplog.text


def test_load_empty_env_var(caplog):
    """Test with empty TELEGRAM_AUTHORIZED_USERS environment variable"""
    handler = create_test_handler("")
    
    assert len(handler._authorized_user_ids) == 0
    assert len(handler._usernames_to_resolve) == 0
    
    # Check that warning was logged
    assert "No authorized users configured in TELEGRAM_AUTHORIZED_USERS" in caplog.text


def test_load_with_empty_entries():
    """Test parsing with empty entries (e.g., double commas)"""
    handler = create_test_handler("123456789,,@user1,,,987654321")
    
    assert len(handler._authorized_user_ids) == 2
    assert "123456789" in handler._authorized_user_ids
    assert "987654321" in handler._authorized_user_ids
    
    assert len(handler._usernames_to_resolve) == 1
    assert "@user1" in handler._usernames_to_resolve


def test_real_world_example():
    """Test with real-world example from user request"""
    handler = create_test_handler("5844680524,@wingperp,@mcfangpy,@Huazero,@long0short")
    
    assert len(handler._authorized_user_ids) == 1
    assert "5844680524" in handler._authorized_user_ids
    
    assert len(handler._usernames_to_resolve) == 4
    assert "@wingperp" in handler._usernames_to_resolve
    assert "@mcfangpy" in handler._usernames_to_resolve
    assert "@Huazero" in handler._usernames_to_resolve
    assert "@long0short" in handler._usernames_to_resolve


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
