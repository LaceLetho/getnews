"""
Telegram发送器

通过Telegram Bot API发送报告到指定频道。
"""

import asyncio
import logging
import re
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
import aiohttp
import time
from urllib.parse import quote


@dataclass
class TelegramConfig:
    """Telegram配置"""
    bot_token: str
    channel_id: str
    parse_mode: str = "Markdown"
    disable_web_page_preview: bool = True
    max_message_length: int = 4096
    retry_attempts: int = 3
    retry_delay: float = 1.0


@dataclass
class SendResult:
    """发送结果"""
    success: bool
    message_id: Optional[int] = None
    error_message: Optional[str] = None
    parts_sent: int = 0
    total_parts: int = 0


class TelegramSender:
    """Telegram发送器
    
    根据需求8实现Telegram报告发送功能：
    - 需求8.1: 通过Telegram Bot发送报告到指定频道
    - 需求8.2: 使用保存的bot_token进行认证
    - 需求8.3: 发送到指定的channel_id
    - 需求8.4: 保持报告的Markdown格式在Telegram中的可读性
    - 需求8.5: 发送失败时记录错误信息并提供本地报告备份
    - 需求8.6: 验证Telegram Bot Token的有效性
    - 需求8.7: 验证Telegram Channel ID的可访问性
    """
    
    def __init__(self, config: TelegramConfig):
        """初始化Telegram发送器
        
        Args:
            config: Telegram配置
        """
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.base_url = f"https://api.telegram.org/bot{config.bot_token}"
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        self._session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        if self._session:
            await self._session.close()
    
    async def send_report(self, report: str) -> SendResult:
        """发送报告
        
        Args:
            report: Markdown格式的报告内容
            
        Returns:
            发送结果
        """
        try:
            # 验证配置
            validation_result = await self.validate_configuration()
            if not validation_result.success:
                return SendResult(
                    success=False,
                    error_message=f"配置验证失败: {validation_result.error_message}"
                )
            
            # 分割长消息
            message_parts = self.split_long_message(report)
            
            # 发送所有部分
            sent_parts = 0
            last_message_id = None
            total_retry_budget = self.config.retry_attempts
            
            for i, part in enumerate(message_parts):
                # 为每个部分分配重试预算
                remaining_parts = len(message_parts) - i
                part_retry_budget = max(1, total_retry_budget // remaining_parts)
                
                part_result = await self._send_message_part(part, i + 1, len(message_parts), part_retry_budget)
                
                if part_result.success:
                    sent_parts += 1
                    last_message_id = part_result.message_id
                    self.logger.info(f"成功发送消息部分 {i + 1}/{len(message_parts)}")
                else:
                    self.logger.error(f"发送消息部分 {i + 1}/{len(message_parts)} 失败: {part_result.error_message}")
                    
                    # 减少剩余的重试预算
                    total_retry_budget -= part_retry_budget
                    
                    # 如果不是最后一部分，继续尝试发送剩余部分
                    if i < len(message_parts) - 1:
                        await asyncio.sleep(self.config.retry_delay)
                        continue
            
            success = sent_parts > 0
            return SendResult(
                success=success,
                message_id=last_message_id,
                error_message=None if success else "所有消息部分发送失败",
                parts_sent=sent_parts,
                total_parts=len(message_parts)
            )
            
        except Exception as e:
            error_msg = f"发送报告时发生异常: {str(e)}"
            self.logger.error(error_msg)
            return SendResult(success=False, error_message=error_msg)
    
    async def _send_message_part(self, message: str, part_num: int, total_parts: int, max_retries: int = None) -> SendResult:
        """发送单个消息部分
        
        Args:
            message: 消息内容
            part_num: 当前部分编号
            total_parts: 总部分数
            max_retries: 最大重试次数，如果为None则使用配置值
            
        Returns:
            发送结果
        """
        # 如果是多部分消息，添加部分标识
        if total_parts > 1:
            header = f"📊 *加密货币新闻分析报告 ({part_num}/{total_parts})*\n\n"
            message = header + message
        
        retry_attempts = max_retries if max_retries is not None else self.config.retry_attempts
        
        for attempt in range(retry_attempts):
            try:
                result = await self._make_api_request("sendMessage", {
                    "chat_id": self.config.channel_id,
                    "text": message,
                    "parse_mode": self.config.parse_mode,
                    "disable_web_page_preview": self.config.disable_web_page_preview
                })
                
                if result.get("ok"):
                    message_id = result.get("result", {}).get("message_id")
                    return SendResult(success=True, message_id=message_id)
                else:
                    error_desc = result.get("description", "未知错误")
                    self.logger.warning(f"API返回错误 (尝试 {attempt + 1}/{retry_attempts}): {error_desc}")
                    
                    if attempt < retry_attempts - 1:
                        await asyncio.sleep(self.config.retry_delay * (2 ** attempt))  # 指数退避
                    
            except Exception as e:
                self.logger.warning(f"发送消息失败 (尝试 {attempt + 1}/{retry_attempts}): {str(e)}")
                
                if attempt < retry_attempts - 1:
                    await asyncio.sleep(self.config.retry_delay * (2 ** attempt))
        
        return SendResult(success=False, error_message="达到最大重试次数")
    
    async def validate_configuration(self) -> SendResult:
        """验证配置有效性
        
        Returns:
            验证结果
        """
        try:
            # 验证Bot Token
            bot_valid = await self.validate_bot_token()
            if not bot_valid.success:
                return bot_valid
            
            # 验证Channel访问权限
            channel_valid = await self.validate_channel_access()
            if not channel_valid.success:
                return channel_valid
            
            return SendResult(success=True)
            
        except Exception as e:
            return SendResult(success=False, error_message=f"配置验证异常: {str(e)}")
    
    async def validate_bot_token(self) -> SendResult:
        """验证Bot Token有效性
        
        Returns:
            验证结果
        """
        try:
            result = await self._make_api_request("getMe")
            
            if result.get("ok"):
                bot_info = result.get("result", {})
                bot_username = bot_info.get("username", "未知")
                self.logger.info(f"Bot Token验证成功: @{bot_username}")
                return SendResult(success=True)
            else:
                error_desc = result.get("description", "Token无效")
                return SendResult(success=False, error_message=f"Bot Token验证失败: {error_desc}")
                
        except Exception as e:
            return SendResult(success=False, error_message=f"Bot Token验证异常: {str(e)}")
    
    async def validate_channel_access(self) -> SendResult:
        """验证Channel访问权限
        
        Returns:
            验证结果
        """
        try:
            result = await self._make_api_request("getChat", {
                "chat_id": self.config.channel_id
            })
            
            if result.get("ok"):
                chat_info = result.get("result", {})
                chat_title = chat_info.get("title", chat_info.get("username", "未知"))
                self.logger.info(f"Channel访问验证成功: {chat_title}")
                return SendResult(success=True)
            else:
                error_desc = result.get("description", "无法访问频道")
                return SendResult(success=False, error_message=f"Channel访问验证失败: {error_desc}")
                
        except Exception as e:
            return SendResult(success=False, error_message=f"Channel访问验证异常: {str(e)}")
    
    async def _make_api_request(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """发起API请求
        
        Args:
            method: API方法名
            params: 请求参数
            
        Returns:
            API响应
        """
        if not self._session:
            self._session = aiohttp.ClientSession()
        
        url = f"{self.base_url}/{method}"
        
        async with self._session.post(url, json=params or {}) as response:
            return await response.json()
    
    def split_long_message(self, message: str) -> List[str]:
        """分割长消息
        
        Args:
            message: 原始消息
            
        Returns:
            分割后的消息列表
        """
        if len(message) <= self.config.max_message_length:
            return [message]
        
        parts = []
        current_part = ""
        lines = message.split('\n')
        
        for line in lines:
            # 检查添加这一行是否会超出长度限制
            test_part = current_part + '\n' + line if current_part else line
            
            if len(test_part) <= self.config.max_message_length:
                current_part = test_part
            else:
                # 如果当前部分不为空，保存它
                if current_part:
                    parts.append(current_part)
                    current_part = line
                else:
                    # 单行就超出限制，需要进一步分割
                    line_parts = self._split_long_line(line)
                    parts.extend(line_parts[:-1])
                    current_part = line_parts[-1] if line_parts else ""
        
        # 添加最后一部分
        if current_part:
            parts.append(current_part)
        
        return parts
    
    def _split_long_line(self, line: str) -> List[str]:
        """分割超长行
        
        Args:
            line: 超长行
            
        Returns:
            分割后的行列表
        """
        parts = []
        max_length = self.config.max_message_length - 100  # 留一些缓冲
        
        while len(line) > max_length:
            # 尝试在合适的位置分割
            split_pos = max_length
            
            # 寻找最近的空格或标点符号
            for i in range(max_length - 1, max_length // 2, -1):
                if line[i] in ' .,;!?，。；！？':
                    split_pos = i + 1
                    break
            
            parts.append(line[:split_pos])
            line = line[split_pos:]
        
        if line:
            parts.append(line)
        
        return parts
    
    def escape_markdown(self, text: str) -> str:
        """转义Markdown特殊字符
        
        Args:
            text: 原始文本
            
        Returns:
            转义后的文本
        """
        # Telegram Markdown特殊字符
        special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
        
        for char in special_chars:
            text = text.replace(char, f'\\{char}')
        
        return text
    
    def format_for_telegram(self, markdown_text: str) -> str:
        """格式化Markdown文本以适配Telegram
        
        Args:
            markdown_text: 原始Markdown文本
            
        Returns:
            适配Telegram的文本
        """
        # 替换不支持的Markdown语法
        formatted_text = markdown_text
        
        # 将HTML标签转换为Markdown
        formatted_text = re.sub(r'<b>(.*?)</b>', r'*\1*', formatted_text)
        formatted_text = re.sub(r'<i>(.*?)</i>', r'_\1_', formatted_text)
        formatted_text = re.sub(r'<code>(.*?)</code>', r'`\1`', formatted_text)
        
        # 处理链接格式
        formatted_text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'[\1](\2)', formatted_text)
        
        # 限制连续换行
        formatted_text = re.sub(r'\n{3,}', '\n\n', formatted_text)
        
        return formatted_text
    
    def save_report_backup(self, report: str, filename: Optional[str] = None) -> str:
        """保存报告备份
        
        Args:
            report: 报告内容
            filename: 备份文件名，默认使用时间戳
            
        Returns:
            备份文件路径
        """
        import os
        from datetime import datetime
        
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"crypto_news_report_{timestamp}.md"
        
        # 确保备份目录存在
        backup_dir = "logs"
        os.makedirs(backup_dir, exist_ok=True)
        
        backup_path = os.path.join(backup_dir, filename)
        
        try:
            with open(backup_path, 'w', encoding='utf-8') as f:
                f.write(report)
            
            self.logger.info(f"报告备份已保存到: {backup_path}")
            return backup_path
            
        except Exception as e:
            self.logger.error(f"保存报告备份失败: {str(e)}")
            return ""


# 同步包装器
class TelegramSenderSync:
    """Telegram发送器同步包装器"""
    
    def __init__(self, config: TelegramConfig):
        self.config = config
        self.sender = TelegramSender(config)
    
    def send_report(self, report: str) -> SendResult:
        """同步发送报告"""
        return asyncio.run(self._send_report_async(report))
    
    async def _send_report_async(self, report: str) -> SendResult:
        """异步发送报告的内部方法"""
        async with self.sender:
            return await self.sender.send_report(report)
    
    def validate_configuration(self) -> SendResult:
        """同步验证配置"""
        return asyncio.run(self._validate_configuration_async())
    
    async def _validate_configuration_async(self) -> SendResult:
        """异步验证配置的内部方法"""
        async with self.sender:
            return await self.sender.validate_configuration()


# 工具函数
def create_telegram_config(
    bot_token: str,
    channel_id: str,
    parse_mode: str = "Markdown",
    max_message_length: int = 4096
) -> TelegramConfig:
    """创建Telegram配置
    
    Args:
        bot_token: Bot Token
        channel_id: 频道ID
        parse_mode: 解析模式
        max_message_length: 最大消息长度
        
    Returns:
        TelegramConfig对象
    """
    return TelegramConfig(
        bot_token=bot_token,
        channel_id=channel_id,
        parse_mode=parse_mode,
        max_message_length=max_message_length
    )


def validate_telegram_credentials(bot_token: str, channel_id: str) -> Dict[str, Any]:
    """验证Telegram凭据
    
    Args:
        bot_token: Bot Token
        channel_id: 频道ID
        
    Returns:
        验证结果字典
    """
    errors = []
    
    # 验证Bot Token格式
    if not bot_token or not isinstance(bot_token, str):
        errors.append("Bot Token不能为空")
    elif not re.match(r'^\d+:[A-Za-z0-9_-]+$', bot_token):
        errors.append("Bot Token格式无效")
    
    # 验证Channel ID格式
    if not channel_id or not isinstance(channel_id, str):
        errors.append("Channel ID不能为空")
    elif not (channel_id.startswith('@') or channel_id.startswith('-') or channel_id.isdigit()):
        errors.append("Channel ID格式无效")
    
    return {
        "valid": len(errors) == 0,
        "errors": errors
    }


async def test_telegram_connection(config: TelegramConfig) -> Dict[str, Any]:
    """测试Telegram连接
    
    Args:
        config: Telegram配置
        
    Returns:
        测试结果字典
    """
    async with TelegramSender(config) as sender:
        # 验证配置
        validation_result = await sender.validate_configuration()
        
        if not validation_result.success:
            return {
                "success": False,
                "error": validation_result.error_message,
                "bot_valid": False,
                "channel_valid": False
            }
        
        # 发送测试消息
        test_message = "🤖 *Telegram连接测试*\n\n这是一条测试消息，用于验证Bot配置是否正确。"
        send_result = await sender.send_report(test_message)
        
        return {
            "success": send_result.success,
            "error": send_result.error_message,
            "bot_valid": True,
            "channel_valid": True,
            "message_id": send_result.message_id
        }