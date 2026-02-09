"""
Unit tests for Task 6.2: _extract_chat_context() helper method

Tests the _extract_chat_context() method implementation including:
- Extraction from private chats
- Extraction from group chats
- Extraction from supergroups
- Error handling for missing fields
- Username extraction with various formats
"""

import pytest
from unittest.mock import Mock, MagicMock
from telegram import Update, User, Chat

from crypto_news_analyzer.reporters.telegram_command_handler import TelegramCommandHandler
from crypto_news_analyzer.models import ChatContext, TelegramCommandConfig


class TestExtractChatContext:
    """Test _extract_chat_context() method functionality"""
    
    @pytest.fixture
    def handler(self):
        """Create a TelegramCommandHandler instance for testing"""
        config = TelegramCommandConfig(enabled=True)
        
        # Create handler with minimal setup
        # We don't need a real bot_token or execution_coordinator for testing _extract_chat_context
        handler = TelegramCommandHandler(
            bot_token="test_token",
            execution_coordinator=None,
            config=config
        )
        
        return handler
    
    def test_extract_private_chat_context(self, handler):
        """Test extracting context from private chat - specific example"""
        # Create mock Update with private chat
        update = Mock(spec=Update)
        update.effective_user = Mock(spec=User)
        update.effective_user.id = 123456
        update.effective_user.username = "testuser"
        update.effective_user.first_name = "Test"
        
        update.effective_chat = Mock(spec=Chat)
        update.effective_chat.id = 123456
        update.effective_chat.type = "private"
        
        # Extract context
        context = handler._extract_chat_context(update)
        
        # Verify all fields
        assert context.user_id == "123456"
        assert context.username == "testuser"
        assert context.chat_id == "123456"
        assert context.chat_type == "private"
        assert context.is_private is True
        assert context.is_group is False
        assert context.context_description == "private chat (123456)"
    
    def test_extract_group_chat_context(self, handler):
        """Test extracting context from group chat - specific example"""
        # Create mock Update with group chat
        update = Mock(spec=Update)
        update.effective_user = Mock(spec=User)
        update.effective_user.id = 789012
        update.effective_user.username = "groupuser"
        update.effective_user.first_name = "Group"
        
        update.effective_chat = Mock(spec=Chat)
        update.effective_chat.id = -987654
        update.effective_chat.type = "group"
        
        # Extract context
        context = handler._extract_chat_context(update)
        
        # Verify all fields
        assert context.user_id == "789012"
        assert context.username == "groupuser"
        assert context.chat_id == "-987654"
        assert context.chat_type == "group"
        assert context.is_private is False
        assert context.is_group is True
        assert context.context_description == "group chat (-987654)"
    
    def test_extract_supergroup_chat_context(self, handler):
        """Test extracting context from supergroup - specific example"""
        # Create mock Update with supergroup chat
        update = Mock(spec=Update)
        update.effective_user = Mock(spec=User)
        update.effective_user.id = 345678
        update.effective_user.username = "supergroupuser"
        update.effective_user.first_name = "Super"
        
        update.effective_chat = Mock(spec=Chat)
        update.effective_chat.id = -100123456789
        update.effective_chat.type = "supergroup"
        
        # Extract context
        context = handler._extract_chat_context(update)
        
        # Verify all fields
        assert context.user_id == "345678"
        assert context.username == "supergroupuser"
        assert context.chat_id == "-100123456789"
        assert context.chat_type == "supergroup"
        assert context.is_private is False
        assert context.is_group is True
        assert context.context_description == "supergroup chat (-100123456789)"
    
    def test_extract_context_username_fallback_to_first_name(self, handler):
        """Test username extraction falls back to first_name when username is None - edge case"""
        # Create mock Update with no username
        update = Mock(spec=Update)
        update.effective_user = Mock(spec=User)
        update.effective_user.id = 111222
        update.effective_user.username = None
        update.effective_user.first_name = "FirstName"
        
        update.effective_chat = Mock(spec=Chat)
        update.effective_chat.id = 111222
        update.effective_chat.type = "private"
        
        # Extract context
        context = handler._extract_chat_context(update)
        
        # Verify username falls back to first_name
        assert context.user_id == "111222"
        assert context.username == "FirstName"
        assert context.chat_type == "private"
    
    def test_extract_context_no_username_or_first_name(self, handler):
        """Test username extraction when both username and first_name are None - edge case"""
        # Create mock Update with no username or first_name
        update = Mock(spec=Update)
        update.effective_user = Mock(spec=User)
        update.effective_user.id = 333444
        update.effective_user.username = None
        update.effective_user.first_name = None
        
        update.effective_chat = Mock(spec=Chat)
        update.effective_chat.id = 333444
        update.effective_chat.type = "private"
        
        # Extract context
        context = handler._extract_chat_context(update)
        
        # Verify username is empty string
        assert context.user_id == "333444"
        assert context.username == ""
        assert context.chat_type == "private"
    
    def test_extract_context_missing_effective_user(self, handler):
        """Test error handling when effective_user is missing - error condition"""
        # Create mock Update with no effective_user
        update = Mock(spec=Update)
        update.effective_user = None
        update.effective_chat = Mock(spec=Chat)
        update.effective_chat.id = 123456
        update.effective_chat.type = "private"
        
        # Should raise ValueError
        with pytest.raises(ValueError, match="Update object missing effective_user"):
            handler._extract_chat_context(update)
    
    def test_extract_context_missing_effective_chat(self, handler):
        """Test error handling when effective_chat is missing - error condition"""
        # Create mock Update with no effective_chat
        update = Mock(spec=Update)
        update.effective_user = Mock(spec=User)
        update.effective_user.id = 123456
        update.effective_user.username = "testuser"
        update.effective_user.first_name = "Test"
        update.effective_chat = None
        
        # Should raise ValueError
        with pytest.raises(ValueError, match="Update object missing effective_chat"):
            handler._extract_chat_context(update)
    
    def test_extract_context_user_id_conversion_to_string(self, handler):
        """Test that user_id is converted to string - specific example"""
        # Create mock Update with integer user_id
        update = Mock(spec=Update)
        update.effective_user = Mock(spec=User)
        update.effective_user.id = 999888777  # Integer
        update.effective_user.username = "testuser"
        update.effective_user.first_name = "Test"
        
        update.effective_chat = Mock(spec=Chat)
        update.effective_chat.id = 999888777
        update.effective_chat.type = "private"
        
        # Extract context
        context = handler._extract_chat_context(update)
        
        # Verify user_id is string
        assert context.user_id == "999888777"
        assert isinstance(context.user_id, str)
    
    def test_extract_context_chat_id_conversion_to_string(self, handler):
        """Test that chat_id is converted to string - specific example"""
        # Create mock Update with negative chat_id (group)
        update = Mock(spec=Update)
        update.effective_user = Mock(spec=User)
        update.effective_user.id = 123456
        update.effective_user.username = "testuser"
        update.effective_user.first_name = "Test"
        
        update.effective_chat = Mock(spec=Chat)
        update.effective_chat.id = -100123456789  # Negative integer
        update.effective_chat.type = "supergroup"
        
        # Extract context
        context = handler._extract_chat_context(update)
        
        # Verify chat_id is string
        assert context.chat_id == "-100123456789"
        assert isinstance(context.chat_id, str)
    
    def test_extract_context_is_private_flag_accuracy(self, handler):
        """Test is_private flag is set correctly for different chat types - edge case"""
        chat_types = [
            ("private", True, False),
            ("group", False, True),
            ("supergroup", False, True),
            ("channel", False, False),  # Edge case: channel is neither private nor group
        ]
        
        for chat_type, expected_is_private, expected_is_group in chat_types:
            update = Mock(spec=Update)
            update.effective_user = Mock(spec=User)
            update.effective_user.id = 123456
            update.effective_user.username = "testuser"
            update.effective_user.first_name = "Test"
            
            update.effective_chat = Mock(spec=Chat)
            update.effective_chat.id = 123456
            update.effective_chat.type = chat_type
            
            context = handler._extract_chat_context(update)
            
            assert context.is_private == expected_is_private, f"Failed for chat_type={chat_type}"
            assert context.is_group == expected_is_group, f"Failed for chat_type={chat_type}"
    
    def test_extract_context_returns_chat_context_instance(self, handler):
        """Test that method returns ChatContext instance - specific example"""
        # Create mock Update
        update = Mock(spec=Update)
        update.effective_user = Mock(spec=User)
        update.effective_user.id = 123456
        update.effective_user.username = "testuser"
        update.effective_user.first_name = "Test"
        
        update.effective_chat = Mock(spec=Chat)
        update.effective_chat.id = 123456
        update.effective_chat.type = "private"
        
        # Extract context
        context = handler._extract_chat_context(update)
        
        # Verify it's a ChatContext instance
        assert isinstance(context, ChatContext)
    
    def test_extract_context_with_special_characters_in_username(self, handler):
        """Test username with special characters - edge case"""
        # Create mock Update with special characters in username
        update = Mock(spec=Update)
        update.effective_user = Mock(spec=User)
        update.effective_user.id = 123456
        update.effective_user.username = "user_name-123"
        update.effective_user.first_name = "Test User"
        
        update.effective_chat = Mock(spec=Chat)
        update.effective_chat.id = 123456
        update.effective_chat.type = "private"
        
        # Extract context
        context = handler._extract_chat_context(update)
        
        # Verify username is preserved
        assert context.username == "user_name-123"
    
    def test_extract_context_large_user_id(self, handler):
        """Test with very large user ID - edge case"""
        # Create mock Update with large user_id
        update = Mock(spec=Update)
        update.effective_user = Mock(spec=User)
        update.effective_user.id = 9999999999999999
        update.effective_user.username = "testuser"
        update.effective_user.first_name = "Test"
        
        update.effective_chat = Mock(spec=Chat)
        update.effective_chat.id = 9999999999999999
        update.effective_chat.type = "private"
        
        # Extract context
        context = handler._extract_chat_context(update)
        
        # Verify large ID is handled correctly
        assert context.user_id == "9999999999999999"
        assert context.chat_id == "9999999999999999"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
