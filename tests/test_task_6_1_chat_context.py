"""
Unit tests for Task 6.1: ChatContext dataclass

Tests the ChatContext dataclass implementation including:
- Field initialization
- context_description property
- Different chat types (private, group, supergroup)
"""

import pytest
from crypto_news_analyzer.models import ChatContext


class TestChatContextDataclass:
    """Test ChatContext dataclass functionality"""
    
    def test_private_chat_context(self):
        """Test ChatContext for private chat - specific example"""
        context = ChatContext(
            user_id="123456",
            username="testuser",
            chat_id="123456",
            chat_type="private",
            is_private=True,
            is_group=False
        )
        
        assert context.user_id == "123456"
        assert context.username == "testuser"
        assert context.chat_id == "123456"
        assert context.chat_type == "private"
        assert context.is_private is True
        assert context.is_group is False
        assert context.context_description == "private chat (123456)"
    
    def test_group_chat_context(self):
        """Test ChatContext for group chat - specific example"""
        context = ChatContext(
            user_id="789012",
            username="groupuser",
            chat_id="-987654",
            chat_type="group",
            is_private=False,
            is_group=True
        )
        
        assert context.user_id == "789012"
        assert context.username == "groupuser"
        assert context.chat_id == "-987654"
        assert context.chat_type == "group"
        assert context.is_private is False
        assert context.is_group is True
        assert context.context_description == "group chat (-987654)"
    
    def test_supergroup_chat_context(self):
        """Test ChatContext for supergroup chat - specific example"""
        context = ChatContext(
            user_id="345678",
            username="supergroupuser",
            chat_id="-100123456789",
            chat_type="supergroup",
            is_private=False,
            is_group=True
        )
        
        assert context.user_id == "345678"
        assert context.username == "supergroupuser"
        assert context.chat_id == "-100123456789"
        assert context.chat_type == "supergroup"
        assert context.is_private is False
        assert context.is_group is True
        assert context.context_description == "supergroup chat (-100123456789)"
    
    def test_context_description_format(self):
        """Test context_description property format - edge case"""
        # Test with various chat_id formats
        test_cases = [
            ("private", "12345", "private chat (12345)"),
            ("group", "-67890", "group chat (-67890)"),
            ("supergroup", "-100111222333", "supergroup chat (-100111222333)"),
        ]
        
        for chat_type, chat_id, expected_desc in test_cases:
            context = ChatContext(
                user_id="123",
                username="user",
                chat_id=chat_id,
                chat_type=chat_type,
                is_private=(chat_type == "private"),
                is_group=(chat_type in ["group", "supergroup"])
            )
            assert context.context_description == expected_desc
    
    def test_all_fields_required(self):
        """Test that all fields are required - error condition"""
        # ChatContext should require all fields
        with pytest.raises(TypeError):
            ChatContext()  # Missing all required fields
        
        with pytest.raises(TypeError):
            ChatContext(user_id="123")  # Missing other fields
    
    def test_field_types(self):
        """Test field types are preserved - specific example"""
        context = ChatContext(
            user_id="123",
            username="user",
            chat_id="456",
            chat_type="private",
            is_private=True,
            is_group=False
        )
        
        assert isinstance(context.user_id, str)
        assert isinstance(context.username, str)
        assert isinstance(context.chat_id, str)
        assert isinstance(context.chat_type, str)
        assert isinstance(context.is_private, bool)
        assert isinstance(context.is_group, bool)
    
    def test_username_with_special_characters(self):
        """Test username with special characters - edge case"""
        context = ChatContext(
            user_id="123",
            username="user_name-123",
            chat_id="456",
            chat_type="private",
            is_private=True,
            is_group=False
        )
        
        assert context.username == "user_name-123"
        assert context.context_description == "private chat (456)"
    
    def test_empty_username(self):
        """Test with empty username - edge case"""
        context = ChatContext(
            user_id="123",
            username="",
            chat_id="456",
            chat_type="private",
            is_private=True,
            is_group=False
        )
        
        assert context.username == ""
        assert context.context_description == "private chat (456)"
    
    def test_boolean_flags_consistency(self):
        """Test boolean flags are consistent with chat_type - specific examples"""
        # Private chat
        private_context = ChatContext(
            user_id="123",
            username="user",
            chat_id="123",
            chat_type="private",
            is_private=True,
            is_group=False
        )
        assert private_context.is_private is True
        assert private_context.is_group is False
        
        # Group chat
        group_context = ChatContext(
            user_id="123",
            username="user",
            chat_id="-456",
            chat_type="group",
            is_private=False,
            is_group=True
        )
        assert group_context.is_private is False
        assert group_context.is_group is True
        
        # Supergroup chat
        supergroup_context = ChatContext(
            user_id="123",
            username="user",
            chat_id="-100789",
            chat_type="supergroup",
            is_private=False,
            is_group=True
        )
        assert supergroup_context.is_private is False
        assert supergroup_context.is_group is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
