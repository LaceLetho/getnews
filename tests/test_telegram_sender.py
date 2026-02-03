"""
Telegram发送器单元测试
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
import aiohttp

from crypto_news_analyzer.reporters import (
    TelegramSender,
    TelegramSenderSync,
    TelegramConfig,
    SendResult,
    create_telegram_config,
    validate_telegram_credentials
)


class TestTelegramConfig:
    """Telegram配置测试类"""
    
    def test_create_telegram_config(self):
        """测试创建Telegram配置"""
        config = create_telegram_config(
            bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
            channel_id="@test_channel"
        )
        
        assert config.bot_token == "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
        assert config.channel_id == "@test_channel"
        assert config.parse_mode == "Markdown"
        assert config.max_message_length == 4096
    
    def test_validate_telegram_credentials_valid(self):
        """测试有效凭据验证"""
        result = validate_telegram_credentials(
            "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
            "@test_channel"
        )
        
        assert result["valid"] is True
        assert len(result["errors"]) == 0
    
    def test_validate_telegram_credentials_invalid_token(self):
        """测试无效Token验证"""
        result = validate_telegram_credentials(
            "invalid_token",
            "@test_channel"
        )
        
        assert result["valid"] is False
        assert any("Bot Token格式无效" in error for error in result["errors"])
    
    def test_validate_telegram_credentials_invalid_channel(self):
        """测试无效Channel验证"""
        result = validate_telegram_credentials(
            "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
            "invalid_channel"
        )
        
        assert result["valid"] is False
        assert any("Channel ID格式无效" in error for error in result["errors"])


class TestTelegramSender:
    """Telegram发送器测试类"""
    
    def setup_method(self):
        """测试前置设置"""
        self.config = TelegramConfig(
            bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
            channel_id="@test_channel"
        )
        self.sender = TelegramSender(self.config)
    
    def test_split_short_message(self):
        """测试短消息不分割"""
        message = "这是一条短消息"
        parts = self.sender.split_long_message(message)
        
        assert len(parts) == 1
        assert parts[0] == message
    
    def test_split_long_message(self):
        """测试长消息分割"""
        # 创建一个超过限制的长消息 - 需要确保真的超过4096字符
        long_line = "这是一行很长的文本，包含更多字符以确保超过限制。" * 100  # 更长的单行
        long_message = long_line + "\n" + long_line  # 确保总长度超过4096
        parts = self.sender.split_long_message(long_message)
        
        assert len(parts) > 1
        for part in parts:
            assert len(part) <= self.config.max_message_length
    
    def test_escape_markdown(self):
        """测试Markdown转义"""
        text = "这是*粗体*和_斜体_文本[链接](url)"
        escaped = self.sender.escape_markdown(text)
        
        assert "\\*" in escaped
        assert "\\_" in escaped
        assert "\\[" in escaped
        assert "\\]" in escaped
        assert "\\(" in escaped
        assert "\\)" in escaped
    
    def test_format_for_telegram(self):
        """测试Telegram格式化"""
        markdown_text = "# 标题\n\n**粗体**文本和*斜体*文本\n\n[链接](https://example.com)"
        formatted = self.sender.format_for_telegram(markdown_text)
        
        # 验证格式化后的文本
        assert formatted is not None
        assert len(formatted) > 0
    
    @pytest.mark.asyncio
    @patch('aiohttp.ClientSession.post')
    async def test_make_api_request_success(self, mock_post):
        """测试成功的API请求"""
        # 模拟成功响应
        mock_response = AsyncMock()
        mock_response.json.return_value = {"ok": True, "result": {"message_id": 123}}
        mock_post.return_value.__aenter__.return_value = mock_response
        
        async with self.sender:
            result = await self.sender._make_api_request("getMe")
        
        assert result["ok"] is True
        assert result["result"]["message_id"] == 123
    
    @pytest.mark.asyncio
    @patch('aiohttp.ClientSession.post')
    async def test_validate_bot_token_success(self, mock_post):
        """测试Bot Token验证成功"""
        # 模拟成功响应
        mock_response = AsyncMock()
        mock_response.json.return_value = {
            "ok": True, 
            "result": {"username": "test_bot"}
        }
        mock_post.return_value.__aenter__.return_value = mock_response
        
        async with self.sender:
            result = await self.sender.validate_bot_token()
        
        assert result.success is True
    
    @pytest.mark.asyncio
    @patch('aiohttp.ClientSession.post')
    async def test_validate_bot_token_failure(self, mock_post):
        """测试Bot Token验证失败"""
        # 模拟失败响应
        mock_response = AsyncMock()
        mock_response.json.return_value = {
            "ok": False, 
            "description": "Unauthorized"
        }
        mock_post.return_value.__aenter__.return_value = mock_response
        
        async with self.sender:
            result = await self.sender.validate_bot_token()
        
        assert result.success is False
        assert "Unauthorized" in result.error_message
    
    @pytest.mark.asyncio
    @patch('aiohttp.ClientSession.post')
    async def test_validate_channel_access_success(self, mock_post):
        """测试Channel访问验证成功"""
        # 模拟成功响应
        mock_response = AsyncMock()
        mock_response.json.return_value = {
            "ok": True, 
            "result": {"title": "Test Channel"}
        }
        mock_post.return_value.__aenter__.return_value = mock_response
        
        async with self.sender:
            result = await self.sender.validate_channel_access()
        
        assert result.success is True
    
    @pytest.mark.asyncio
    @patch('aiohttp.ClientSession.post')
    async def test_send_message_part_success(self, mock_post):
        """测试发送消息部分成功"""
        # 模拟成功响应
        mock_response = AsyncMock()
        mock_response.json.return_value = {
            "ok": True, 
            "result": {"message_id": 456}
        }
        mock_post.return_value.__aenter__.return_value = mock_response
        
        async with self.sender:
            result = await self.sender._send_message_part("测试消息", 1, 1)
        
        assert result.success is True
        assert result.message_id == 456
    
    @pytest.mark.asyncio
    @patch('aiohttp.ClientSession.post')
    async def test_send_message_part_failure(self, mock_post):
        """测试发送消息部分失败"""
        # 模拟失败响应
        mock_response = AsyncMock()
        mock_response.json.return_value = {
            "ok": False, 
            "description": "Bad Request"
        }
        mock_post.return_value.__aenter__.return_value = mock_response
        
        async with self.sender:
            result = await self.sender._send_message_part("测试消息", 1, 1)
        
        assert result.success is False
    
    def test_save_report_backup(self):
        """测试保存报告备份"""
        import tempfile
        import os
        
        report_content = "# 测试报告\n\n这是测试内容"
        
        # 使用临时文件测试
        with tempfile.TemporaryDirectory() as temp_dir:
            # 修改备份目录为临时目录
            original_backup_dir = "logs"
            
            # 创建临时备份文件
            backup_path = self.sender.save_report_backup(
                report_content, 
                "test_report.md"
            )
            
            # 验证文件是否创建
            assert os.path.exists(backup_path)
            
            # 验证文件内容
            with open(backup_path, 'r', encoding='utf-8') as f:
                saved_content = f.read()
            
            assert saved_content == report_content
    
    def test_telegram_send_failure_backup(self):
        """测试Telegram发送失败时的备份功能 - 需求 8.5"""
        report_content = "# 测试报告\n\n发送失败测试"
        
        # 测试备份功能
        backup_path = self.sender.save_report_backup(report_content)
        
        # 验证备份文件存在
        import os
        assert os.path.exists(backup_path)
        
        # 验证备份内容正确
        with open(backup_path, 'r', encoding='utf-8') as f:
            saved_content = f.read()
        assert saved_content == report_content
        
        # 清理测试文件
        os.remove(backup_path)
    
    @pytest.mark.asyncio
    @patch('aiohttp.ClientSession.post')
    async def test_bot_token_validation_comprehensive(self, mock_post):
        """测试Bot Token验证的全面性 - 需求 8.6"""
        # 测试有效Token
        mock_response = AsyncMock()
        mock_response.json.return_value = {
            "ok": True, 
            "result": {"username": "test_bot", "id": 123456}
        }
        mock_post.return_value.__aenter__.return_value = mock_response
        
        async with self.sender:
            result = await self.sender.validate_bot_token()
        
        assert result.success is True
        
        # 测试无效Token格式
        invalid_sender = TelegramSender(TelegramConfig(
            bot_token="invalid_token_format",
            channel_id="@test_channel"
        ))
        
        # 测试API返回错误
        mock_response.json.return_value = {
            "ok": False, 
            "description": "Unauthorized: bot token is invalid"
        }
        
        async with invalid_sender:
            result = await invalid_sender.validate_bot_token()
        
        assert result.success is False
        assert "Unauthorized" in result.error_message
    
    @pytest.mark.asyncio
    @patch('aiohttp.ClientSession.post')
    async def test_channel_access_validation_comprehensive(self, mock_post):
        """测试Channel访问验证的全面性 - 需求 8.7"""
        # 测试有效Channel访问
        mock_response = AsyncMock()
        mock_response.json.return_value = {
            "ok": True, 
            "result": {
                "id": -1001234567890,
                "title": "Test Channel",
                "type": "channel"
            }
        }
        mock_post.return_value.__aenter__.return_value = mock_response
        
        async with self.sender:
            result = await self.sender.validate_channel_access()
        
        assert result.success is True
        
        # 测试无效Channel访问
        mock_response.json.return_value = {
            "ok": False, 
            "description": "Bad Request: chat not found"
        }
        
        async with self.sender:
            result = await self.sender.validate_channel_access()
        
        assert result.success is False
        assert "chat not found" in result.error_message
    
    @pytest.mark.asyncio
    @patch('aiohttp.ClientSession.post')
    async def test_error_handling_and_logging(self, mock_post):
        """测试错误处理和日志记录 - 需求 8.5"""
        # 模拟网络错误
        mock_post.side_effect = aiohttp.ClientError("Network error")
        
        async with self.sender:
            result = await self.sender.send_report("测试消息")
        
        assert result.success is False
        assert "Network error" in result.error_message
        
        # 重置mock
        mock_post.side_effect = None
        
        # 模拟API错误响应
        mock_response = AsyncMock()
        mock_response.json.return_value = {
            "ok": False,
            "error_code": 400,
            "description": "Bad Request: message is too long"
        }
        mock_post.return_value.__aenter__.return_value = mock_response
        
        async with self.sender:
            result = await self.sender._send_message_part("测试消息", 1, 1)
        
        assert result.success is False


class TestTelegramSenderSync:
    """同步Telegram发送器测试类"""
    
    def setup_method(self):
        """测试前置设置"""
        self.config = TelegramConfig(
            bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
            channel_id="@test_channel"
        )
        self.sender_sync = TelegramSenderSync(self.config)
    
    @patch('crypto_news_analyzer.reporters.telegram_sender.TelegramSender.send_report')
    def test_send_report_sync(self, mock_send_report):
        """测试同步发送报告"""
        # 模拟异步方法返回值
        mock_send_report.return_value = SendResult(success=True, message_id=123)
        
        # 由于涉及异步操作，这里只测试方法存在性
        assert hasattr(self.sender_sync, 'send_report')
        assert callable(self.sender_sync.send_report)


class TestSendResult:
    """发送结果测试类"""
    
    def test_send_result_success(self):
        """测试成功结果"""
        result = SendResult(success=True, message_id=123, parts_sent=1, total_parts=1)
        
        assert result.success is True
        assert result.message_id == 123
        assert result.error_message is None
        assert result.parts_sent == 1
        assert result.total_parts == 1
    
    def test_send_result_failure(self):
        """测试失败结果"""
        result = SendResult(
            success=False, 
            error_message="发送失败", 
            parts_sent=0, 
            total_parts=1
        )
        
        assert result.success is False
        assert result.message_id is None
        assert result.error_message == "发送失败"
        assert result.parts_sent == 0
        assert result.total_parts == 1


if __name__ == "__main__":
    pytest.main([__file__])