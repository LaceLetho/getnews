"""
Unit tests for Task 7.1: _log_authorization_attempt() method

Tests the _log_authorization_attempt() method implementation including:
- Logging successful authorization at INFO level
- Logging failed authorization at WARNING level
- Including all context fields in log message
- Including optional reason parameter
- Handling various parameter combinations
"""

import pytest
from unittest.mock import Mock, patch
import logging

from crypto_news_analyzer.reporters.telegram_command_handler import TelegramCommandHandler
from crypto_news_analyzer.models import TelegramCommandConfig


class TestLogAuthorizationAttempt:
    """Test _log_authorization_attempt() method functionality"""
    
    @pytest.fixture
    def handler(self):
        """Create a TelegramCommandHandler instance for testing"""
        config = TelegramCommandConfig(enabled=True)
        
        # Create handler with minimal setup
        handler = TelegramCommandHandler(
            bot_token="test_token",
            execution_coordinator=None,
            config=config
        )
        
        return handler
    
    def test_log_successful_authorization_info_level(self, handler, caplog):
        """Test logging successful authorization at INFO level - specific example"""
        with caplog.at_level(logging.INFO):
            handler._log_authorization_attempt(
                command="/run",
                user_id="123456789",
                username="testuser",
                chat_type="private",
                chat_id="123456789",
                authorized=True
            )
        
        # Verify INFO level log was created
        assert len(caplog.records) == 1
        assert caplog.records[0].levelname == "INFO"
        
        # Verify log message contains all required fields
        log_message = caplog.records[0].message
        assert "Authorization attempt:" in log_message
        assert "command=/run" in log_message
        assert "user=testuser (123456789)" in log_message
        assert "chat_type=private" in log_message
        assert "chat_id=123456789" in log_message
        assert "authorized=True" in log_message
    
    def test_log_failed_authorization_warning_level(self, handler, caplog):
        """Test logging failed authorization at WARNING level - specific example"""
        with caplog.at_level(logging.WARNING):
            handler._log_authorization_attempt(
                command="/status",
                user_id="987654321",
                username="unauthorized_user",
                chat_type="group",
                chat_id="-100123456789",
                authorized=False
            )
        
        # Verify WARNING level log was created
        assert len(caplog.records) == 1
        assert caplog.records[0].levelname == "WARNING"
        
        # Verify log message contains all required fields
        log_message = caplog.records[0].message
        assert "Authorization attempt:" in log_message
        assert "command=/status" in log_message
        assert "user=unauthorized_user (987654321)" in log_message
        assert "chat_type=group" in log_message
        assert "chat_id=-100123456789" in log_message
        assert "authorized=False" in log_message
    
    def test_log_with_reason_parameter(self, handler, caplog):
        """Test logging with reason parameter included - specific example"""
        with caplog.at_level(logging.WARNING):
            handler._log_authorization_attempt(
                command="/run",
                user_id="111222333",
                username="blocked_user",
                chat_type="private",
                chat_id="111222333",
                authorized=False,
                reason="user not in authorized list"
            )
        
        # Verify log message includes reason
        log_message = caplog.records[0].message
        assert "reason=user not in authorized list" in log_message
    
    def test_log_without_reason_parameter(self, handler, caplog):
        """Test logging without reason parameter - edge case"""
        with caplog.at_level(logging.INFO):
            handler._log_authorization_attempt(
                command="/help",
                user_id="444555666",
                username="testuser",
                chat_type="private",
                chat_id="444555666",
                authorized=True,
                reason=None
            )
        
        # Verify log message does not include reason
        log_message = caplog.records[0].message
        assert "reason=" not in log_message
    
    def test_log_with_empty_reason(self, handler, caplog):
        """Test logging with empty reason string - edge case"""
        with caplog.at_level(logging.WARNING):
            handler._log_authorization_attempt(
                command="/status",
                user_id="777888999",
                username="testuser",
                chat_type="group",
                chat_id="-987654321",
                authorized=False,
                reason=""
            )
        
        # Verify log message does not include empty reason
        log_message = caplog.records[0].message
        # Empty string is falsy, so reason should not be appended
        assert "reason=" not in log_message
    
    def test_log_supergroup_chat_type(self, handler, caplog):
        """Test logging with supergroup chat type - specific example"""
        with caplog.at_level(logging.INFO):
            handler._log_authorization_attempt(
                command="/run",
                user_id="123456",
                username="supergroupuser",
                chat_type="supergroup",
                chat_id="-100987654321",
                authorized=True
            )
        
        # Verify supergroup chat type is logged correctly
        log_message = caplog.records[0].message
        assert "chat_type=supergroup" in log_message
        assert "chat_id=-100987654321" in log_message
    
    def test_log_with_special_characters_in_username(self, handler, caplog):
        """Test logging with special characters in username - edge case"""
        with caplog.at_level(logging.INFO):
            handler._log_authorization_attempt(
                command="/help",
                user_id="123456",
                username="user_name-123",
                chat_type="private",
                chat_id="123456",
                authorized=True
            )
        
        # Verify special characters are preserved in log
        log_message = caplog.records[0].message
        assert "user=user_name-123 (123456)" in log_message
    
    def test_log_with_very_long_user_id(self, handler, caplog):
        """Test logging with very long user ID - edge case"""
        with caplog.at_level(logging.INFO):
            handler._log_authorization_attempt(
                command="/status",
                user_id="9999999999999999",
                username="testuser",
                chat_type="private",
                chat_id="9999999999999999",
                authorized=True
            )
        
        # Verify long user ID is logged correctly
        log_message = caplog.records[0].message
        assert "user=testuser (9999999999999999)" in log_message
        assert "chat_id=9999999999999999" in log_message
    
    def test_log_all_command_types(self, handler, caplog):
        """Test logging for all command types - specific examples"""
        commands = ["/run", "/status", "/help"]
        
        for command in commands:
            caplog.clear()
            with caplog.at_level(logging.INFO):
                handler._log_authorization_attempt(
                    command=command,
                    user_id="123456",
                    username="testuser",
                    chat_type="private",
                    chat_id="123456",
                    authorized=True
                )
            
            # Verify command is logged correctly
            log_message = caplog.records[0].message
            assert f"command={command}" in log_message
    
    def test_log_negative_chat_id_for_groups(self, handler, caplog):
        """Test logging with negative chat_id for groups - specific example"""
        with caplog.at_level(logging.INFO):
            handler._log_authorization_attempt(
                command="/run",
                user_id="123456",
                username="groupuser",
                chat_type="group",
                chat_id="-987654321",
                authorized=True
            )
        
        # Verify negative chat_id is logged correctly
        log_message = caplog.records[0].message
        assert "chat_id=-987654321" in log_message
    
    def test_log_message_format_consistency(self, handler, caplog):
        """Test that log message format is consistent - specific example"""
        with caplog.at_level(logging.INFO):
            handler._log_authorization_attempt(
                command="/run",
                user_id="123456",
                username="testuser",
                chat_type="private",
                chat_id="123456",
                authorized=True,
                reason="test reason"
            )
        
        # Verify log message follows expected format
        log_message = caplog.records[0].message
        
        # Check that fields appear in expected order
        assert log_message.startswith("Authorization attempt:")
        assert log_message.index("command=") < log_message.index("user=")
        assert log_message.index("user=") < log_message.index("chat_type=")
        assert log_message.index("chat_type=") < log_message.index("chat_id=")
        assert log_message.index("chat_id=") < log_message.index("authorized=")
        assert log_message.index("authorized=") < log_message.index("reason=")
    
    def test_log_with_long_reason_message(self, handler, caplog):
        """Test logging with long reason message - edge case"""
        long_reason = "user not authorized because they are not in the TELEGRAM_AUTHORIZED_USERS environment variable list"
        
        with caplog.at_level(logging.WARNING):
            handler._log_authorization_attempt(
                command="/run",
                user_id="123456",
                username="testuser",
                chat_type="private",
                chat_id="123456",
                authorized=False,
                reason=long_reason
            )
        
        # Verify long reason is included in log
        log_message = caplog.records[0].message
        assert f"reason={long_reason}" in log_message
    
    def test_log_authorized_true_uses_info_level(self, handler):
        """Test that authorized=True uses INFO level - specific example"""
        with patch.object(handler.logger, 'info') as mock_info, \
             patch.object(handler.logger, 'warning') as mock_warning:
            
            handler._log_authorization_attempt(
                command="/run",
                user_id="123456",
                username="testuser",
                chat_type="private",
                chat_id="123456",
                authorized=True
            )
            
            # Verify info was called, warning was not
            assert mock_info.call_count == 1
            assert mock_warning.call_count == 0
    
    def test_log_authorized_false_uses_warning_level(self, handler):
        """Test that authorized=False uses WARNING level - specific example"""
        with patch.object(handler.logger, 'info') as mock_info, \
             patch.object(handler.logger, 'warning') as mock_warning:
            
            handler._log_authorization_attempt(
                command="/run",
                user_id="123456",
                username="testuser",
                chat_type="private",
                chat_id="123456",
                authorized=False
            )
            
            # Verify warning was called, info was not
            assert mock_info.call_count == 0
            assert mock_warning.call_count == 1
    
    def test_log_with_empty_username(self, handler, caplog):
        """Test logging with empty username - edge case"""
        with caplog.at_level(logging.INFO):
            handler._log_authorization_attempt(
                command="/help",
                user_id="123456",
                username="",
                chat_type="private",
                chat_id="123456",
                authorized=True
            )
        
        # Verify empty username is handled
        log_message = caplog.records[0].message
        assert "user= (123456)" in log_message
    
    def test_log_multiple_authorization_attempts(self, handler, caplog):
        """Test logging multiple authorization attempts - integration"""
        with caplog.at_level(logging.INFO):
            # Log multiple attempts
            handler._log_authorization_attempt(
                command="/run",
                user_id="111",
                username="user1",
                chat_type="private",
                chat_id="111",
                authorized=True
            )
            
            handler._log_authorization_attempt(
                command="/status",
                user_id="222",
                username="user2",
                chat_type="group",
                chat_id="-222",
                authorized=False,
                reason="not authorized"
            )
            
            handler._log_authorization_attempt(
                command="/help",
                user_id="333",
                username="user3",
                chat_type="supergroup",
                chat_id="-333",
                authorized=True
            )
        
        # Verify all three logs were created
        assert len(caplog.records) == 3
        
        # Verify first log (INFO)
        assert caplog.records[0].levelname == "INFO"
        assert "user=user1 (111)" in caplog.records[0].message
        
        # Verify second log (WARNING)
        assert caplog.records[1].levelname == "WARNING"
        assert "user=user2 (222)" in caplog.records[1].message
        assert "reason=not authorized" in caplog.records[1].message
        
        # Verify third log (INFO)
        assert caplog.records[2].levelname == "INFO"
        assert "user=user3 (333)" in caplog.records[2].message


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
