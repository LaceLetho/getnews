"""
Unit tests for task 8.1: Update _handle_run_command() method

Tests verify that _handle_run_command():
- Calls _extract_chat_context() at the start
- Extracts user_id, username, chat_type, chat_id from context
- Updates log statements to include chat_type and chat_id
- Calls _log_authorization_attempt() for authorization checks
- Does not call validate_user_permissions() (removed)
- Has consistent error messages

Requirements: 1.1, 1.2, 1.3, 2.1, 2.2, 2.3, 8.1, 8.2, 8.3, 8.4
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, call
from telegram import Update, User, Chat, Message
from telegram.ext import ContextTypes
from crypto_news_analyzer.reporters.telegram_command_handler import TelegramCommandHandler
from crypto_news_analyzer.models import ChatContext


@pytest.fixture
def mock_config():
    """Create a mock configuration"""
    config = Mock()
    config.enabled = True
    config.execution_timeout_minutes = 30
    config.max_concurrent_executions = 1
    config.command_rate_limit = {}
    return config


@pytest.fixture
def mock_coordinator():
    """Create a mock execution coordinator"""
    coordinator = Mock()
    coordinator.trigger_execution = Mock(return_value="execution_id_123")
    coordinator.get_execution_status = Mock(return_value={
        "status": "running",
        "start_time": "2024-01-01T00:00:00"
    })
    return coordinator


@pytest.fixture
def handler(mock_config, mock_coordinator):
    """Create a TelegramCommandHandler instance for testing"""
    with patch.dict('os.environ', {'TELEGRAM_AUTHORIZED_USERS': '123456789'}):
        handler = TelegramCommandHandler(
            bot_token="test_token",
            execution_coordinator=mock_coordinator,
            config=mock_config
        )
        handler.application = Mock()
        handler.application.bot = Mock()
        return handler


def create_mock_update(user_id: str, username: str, chat_type: str, chat_id: str) -> Update:
    """Helper to create a mock Telegram Update object"""
    update = Mock(spec=Update)
    
    # Mock user
    user = Mock(spec=User)
    user.id = int(user_id)
    user.username = username
    user.first_name = username
    update.effective_user = user
    
    # Mock chat
    chat = Mock(spec=Chat)
    chat.id = int(chat_id)
    chat.type = chat_type
    update.effective_chat = chat
    
    # Mock message
    message = Mock(spec=Message)
    message.reply_text = AsyncMock()
    update.message = message
    
    return update


@pytest.mark.asyncio
async def test_handle_run_command_extracts_chat_context(handler):
    """Test that _handle_run_command calls _extract_chat_context at the start"""
    update = create_mock_update("123456789", "testuser", "private", "123456789")
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    
    # Mock the methods
    with patch.object(handler, '_extract_chat_context') as mock_extract:
        mock_extract.return_value = ChatContext(
            user_id="123456789",
            username="testuser",
            chat_id="123456789",
            chat_type="private",
            is_private=True,
            is_group=False
        )
        with patch.object(handler, 'is_authorized_user', return_value=True):
            with patch.object(handler, 'check_rate_limit', return_value=(True, None)):
                with patch.object(handler, 'handle_run_command', return_value="✅ 执行成功"):
                    with patch.object(handler, '_log_authorization_attempt'):
                        await handler._handle_run_command(update, context)
        
        # Verify _extract_chat_context was called
        mock_extract.assert_called_once_with(update)


@pytest.mark.asyncio
async def test_handle_run_command_uses_context_fields(handler):
    """Test that _handle_run_command extracts and uses fields from ChatContext"""
    update = create_mock_update("123456789", "testuser", "group", "-100123456789")
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    
    with patch.object(handler, 'is_authorized_user', return_value=True) as mock_auth:
        with patch.object(handler, 'check_rate_limit', return_value=(True, None)):
            with patch.object(handler, 'handle_run_command', return_value="✅ 执行成功"):
                with patch.object(handler, '_log_authorization_attempt') as mock_log_auth:
                    await handler._handle_run_command(update, context)
        
        # Verify is_authorized_user was called with user_id from context
        mock_auth.assert_called_once_with("123456789", "testuser")
        
        # Verify _log_authorization_attempt was called with context fields
        mock_log_auth.assert_called_once_with(
            command="/run",
            user_id="123456789",
            username="testuser",
            chat_type="group",
            chat_id="-100123456789",
            authorized=True
        )


@pytest.mark.asyncio
async def test_handle_run_command_logs_with_chat_context(handler):
    """Test that log statements include chat_type and chat_id"""
    update = create_mock_update("123456789", "testuser", "supergroup", "-100987654321")
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    
    with patch.object(handler, 'is_authorized_user', return_value=True):
        with patch.object(handler, 'check_rate_limit', return_value=(True, None)):
            with patch.object(handler, 'handle_run_command', return_value="✅ 执行成功"):
                with patch.object(handler, '_log_authorization_attempt'):
                    with patch.object(handler.logger, 'info') as mock_log_info:
                        await handler._handle_run_command(update, context)
        
        # Verify log includes chat context
        log_calls = [str(call) for call in mock_log_info.call_args_list]
        assert any("聊天类型: supergroup" in str(call) for call in log_calls)
        assert any("聊天ID: -100987654321" in str(call) for call in log_calls)


@pytest.mark.asyncio
async def test_handle_run_command_calls_log_authorization_attempt_on_failure(handler):
    """Test that _log_authorization_attempt is called when authorization fails"""
    update = create_mock_update("999999999", "unauthorized", "private", "999999999")
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    
    with patch.object(handler, 'is_authorized_user', return_value=False):
        with patch.object(handler, '_log_authorization_attempt') as mock_log_auth:
            with patch.object(handler, '_log_command_execution'):
                await handler._handle_run_command(update, context)
        
        # Verify _log_authorization_attempt was called with authorized=False
        mock_log_auth.assert_called_once_with(
            command="/run",
            user_id="999999999",
            username="unauthorized",
            chat_type="private",
            chat_id="999999999",
            authorized=False,
            reason="user not in authorized list"
        )


@pytest.mark.asyncio
async def test_handle_run_command_calls_log_authorization_attempt_on_success(handler):
    """Test that _log_authorization_attempt is called when authorization succeeds"""
    update = create_mock_update("123456789", "testuser", "private", "123456789")
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    
    with patch.object(handler, 'is_authorized_user', return_value=True):
        with patch.object(handler, 'check_rate_limit', return_value=(True, None)):
            with patch.object(handler, 'handle_run_command', return_value="✅ 执行成功"):
                with patch.object(handler, '_log_authorization_attempt') as mock_log_auth:
                    await handler._handle_run_command(update, context)
        
        # Verify _log_authorization_attempt was called with authorized=True
        mock_log_auth.assert_called_once_with(
            command="/run",
            user_id="123456789",
            username="testuser",
            chat_type="private",
            chat_id="123456789",
            authorized=True
        )


@pytest.mark.asyncio
async def test_handle_run_command_no_validate_user_permissions_call(handler):
    """Test that validate_user_permissions is NOT called (method removed)"""
    update = create_mock_update("123456789", "testuser", "private", "123456789")
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    
    # Verify the method doesn't exist
    assert not hasattr(handler, 'validate_user_permissions'), \
        "validate_user_permissions should be removed"
    
    with patch.object(handler, 'is_authorized_user', return_value=True):
        with patch.object(handler, 'check_rate_limit', return_value=(True, None)):
            with patch.object(handler, 'handle_run_command', return_value="✅ 执行成功"):
                with patch.object(handler, '_log_authorization_attempt'):
                    # Should execute without calling validate_user_permissions
                    await handler._handle_run_command(update, context)


@pytest.mark.asyncio
async def test_handle_run_command_consistent_error_message(handler):
    """Test that error messages are consistent"""
    update = create_mock_update("999999999", "unauthorized", "private", "999999999")
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    
    with patch.object(handler, 'is_authorized_user', return_value=False):
        with patch.object(handler, '_log_authorization_attempt'):
            with patch.object(handler, '_log_command_execution'):
                await handler._handle_run_command(update, context)
    
    # Verify consistent error message was sent
    update.message.reply_text.assert_called_once_with(
        "❌ 权限拒绝\n\n您没有权限执行此命令。"
    )


@pytest.mark.asyncio
async def test_handle_run_command_handles_context_extraction_error(handler):
    """Test that errors in _extract_chat_context are handled gracefully"""
    update = create_mock_update("123456789", "testuser", "private", "123456789")
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    
    with patch.object(handler, '_extract_chat_context') as mock_extract:
        mock_extract.side_effect = ValueError("Missing effective_user")
        
        await handler._handle_run_command(update, context)
        
        # Verify error message was sent
        update.message.reply_text.assert_called_once_with("❌ 处理命令时发生错误")


@pytest.mark.asyncio
async def test_handle_run_command_logs_error_with_context(handler):
    """Test that errors are logged with chat context information"""
    update = create_mock_update("123456789", "testuser", "group", "-100123456789")
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    
    with patch.object(handler, 'is_authorized_user', return_value=True):
        with patch.object(handler, 'check_rate_limit', return_value=(True, None)):
            with patch.object(handler, 'handle_run_command') as mock_handle:
                mock_handle.side_effect = Exception("Test error")
                with patch.object(handler, '_log_authorization_attempt'):
                    with patch.object(handler.logger, 'error') as mock_log_error:
                        await handler._handle_run_command(update, context)
        
        # Verify error log includes chat context
        error_call = str(mock_log_error.call_args)
        assert "testuser" in error_call
        assert "123456789" in error_call
        assert "group" in error_call
        assert "-100123456789" in error_call


@pytest.mark.asyncio
async def test_handle_run_command_private_chat_flow(handler):
    """Test complete flow for private chat"""
    update = create_mock_update("123456789", "testuser", "private", "123456789")
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    
    with patch.object(handler, 'is_authorized_user', return_value=True):
        with patch.object(handler, 'check_rate_limit', return_value=(True, None)):
            with patch.object(handler, 'handle_run_command', return_value="✅ 执行成功"):
                with patch.object(handler, '_log_authorization_attempt') as mock_log_auth:
                    await handler._handle_run_command(update, context)
        
        # Verify authorization was logged with private chat context
        mock_log_auth.assert_called_once()
        call_kwargs = mock_log_auth.call_args[1]
        assert call_kwargs['chat_type'] == 'private'
        assert call_kwargs['authorized'] == True


@pytest.mark.asyncio
async def test_handle_run_command_group_chat_flow(handler):
    """Test complete flow for group chat"""
    update = create_mock_update("123456789", "testuser", "group", "-100123456789")
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    
    with patch.object(handler, 'is_authorized_user', return_value=True):
        with patch.object(handler, 'check_rate_limit', return_value=(True, None)):
            with patch.object(handler, 'handle_run_command', return_value="✅ 执行成功"):
                with patch.object(handler, '_log_authorization_attempt') as mock_log_auth:
                    await handler._handle_run_command(update, context)
        
        # Verify authorization was logged with group chat context
        mock_log_auth.assert_called_once()
        call_kwargs = mock_log_auth.call_args[1]
        assert call_kwargs['chat_type'] == 'group'
        assert call_kwargs['chat_id'] == '-100123456789'
        assert call_kwargs['authorized'] == True
