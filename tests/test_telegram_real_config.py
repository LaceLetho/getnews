#!/usr/bin/env python3
"""
Telegram真实配置测试

测试Telegram配置的有效性和格式验证
"""

import os
import sys
import pytest
from dotenv import load_dotenv

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crypto_news_analyzer.reporters import (
    TelegramConfig,
    create_telegram_config,
    validate_telegram_credentials
)


class TestTelegramRealConfig:
    """Telegram真实配置测试类"""
    
    @classmethod
    def setup_class(cls):
        """测试类初始化"""
        # 加载环境变量
        load_dotenv()
        
        # 获取真实的Telegram配置
        cls.telegram_token = os.getenv('telegram_bot_token')
        cls.telegram_channel = os.getenv('telegram_channel_id')
        
        if not all([cls.telegram_token, cls.telegram_channel]):
            pytest.skip("缺少Telegram配置，跳过真实配置测试")
        
        print(f"使用Telegram Token: {cls.telegram_token[:15]}...")
        print(f"使用Telegram Channel: {cls.telegram_channel}")
    
    def test_real_config_validation(self):
        """测试真实配置验证 - 专注于真实环境测试"""
        print(f"\n测试真实配置验证...")
        
        # 测试真实配置
        result = validate_telegram_credentials(self.telegram_token, self.telegram_channel)
        
        print(f"真实配置验证结果: {result}")
        
        # 创建配置对象
        config = create_telegram_config(
            bot_token=self.telegram_token,
            channel_id=self.telegram_channel
        )
        
        # 验证配置对象
        assert isinstance(config, TelegramConfig)
        assert config.bot_token == self.telegram_token
        assert config.channel_id == self.telegram_channel
        
        print(f"✅ 真实配置验证完成")
    
    def test_real_environment_analysis(self):
        """测试真实环境分析 - 专注于生产环境特性"""
        print(f"\n测试真实环境分析...")
        
        token = self.telegram_token
        channel = self.telegram_channel
        
        # 分析token结构
        if ':' in token:
            bot_id, bot_hash = token.split(':', 1)
            print(f"Bot ID: {bot_id}")
            print(f"Bot Hash: {bot_hash[:10]}...")
            
            # 验证Bot ID是否为数字
            if bot_id.isdigit():
                print(f"✅ Bot ID格式正确 (数字)")
            else:
                print(f"❌ Bot ID格式错误 (非数字)")
        
        # 分析channel结构
        print(f"Channel ID: {channel}")
        
        if channel.startswith('@'):
            print(f"✅ 公开频道格式")
        elif channel.startswith('-'):
            print(f"✅ 私有频道格式")
            if channel.startswith('-100'):
                print(f"✅ 超级群组/频道格式")
        elif channel.isdigit():
            print(f"✅ 数字ID格式")
        else:
            print(f"⚠️ 未知的Channel ID格式")
        
        # 安全提醒
        print(f"\n安全提醒:")
        print(f"   - 确保API token安全存储")
        print(f"   - 使用测试频道进行开发测试")
        print(f"   - 监控API使用情况")


if __name__ == "__main__":
    # 运行Telegram配置测试
    pytest.main([__file__, "-v", "-s"])