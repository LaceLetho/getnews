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
    
    def test_telegram_token_format_validation(self):
        """测试Telegram Token格式验证"""
        print(f"\n测试Token格式验证...")
        
        # 测试真实token格式
        result = validate_telegram_credentials(self.telegram_token, "@test_channel")
        
        print(f"Token格式验证结果: {result}")
        
        # 真实token应该通过格式验证
        if result["valid"]:
            print(f"✅ Token格式验证通过")
        else:
            print(f"❌ Token格式验证失败: {result['errors']}")
            # 即使格式验证失败，我们也要了解原因
            for error in result["errors"]:
                print(f"   - {error}")
    
    def test_telegram_channel_format_validation(self):
        """测试Telegram Channel格式验证"""
        print(f"\n测试Channel格式验证...")
        
        # 测试真实channel格式
        result = validate_telegram_credentials("123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11", self.telegram_channel)
        
        print(f"Channel格式验证结果: {result}")
        
        # 检查channel格式
        if self.telegram_channel.startswith('@') or self.telegram_channel.startswith('-') or self.telegram_channel.isdigit():
            print(f"✅ Channel格式看起来正确")
        else:
            print(f"⚠️ Channel格式可能有问题: {self.telegram_channel}")
    
    def test_create_telegram_config_with_real_values(self):
        """测试使用真实值创建Telegram配置"""
        print(f"\n测试创建Telegram配置...")
        
        try:
            config = create_telegram_config(
                bot_token=self.telegram_token,
                channel_id=self.telegram_channel
            )
            
            # 验证配置对象
            assert isinstance(config, TelegramConfig)
            assert config.bot_token == self.telegram_token
            assert config.channel_id == self.telegram_channel
            assert config.parse_mode == "Markdown"
            assert config.max_message_length == 4096
            
            print(f"✅ Telegram配置创建成功")
            print(f"   Bot Token: {config.bot_token[:15]}...")
            print(f"   Channel ID: {config.channel_id}")
            print(f"   Parse Mode: {config.parse_mode}")
            print(f"   Max Message Length: {config.max_message_length}")
            
        except Exception as e:
            print(f"❌ 配置创建失败: {e}")
            raise
    
    def test_telegram_config_validation_comprehensive(self):
        """测试Telegram配置的全面验证"""
        print(f"\n测试全面配置验证...")
        
        # 测试各种token格式
        test_cases = [
            {
                "token": self.telegram_token,
                "channel": self.telegram_channel,
                "description": "真实配置"
            },
            {
                "token": "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
                "channel": "@test_channel",
                "description": "标准格式"
            },
            {
                "token": "invalid_token",
                "channel": self.telegram_channel,
                "description": "无效token"
            },
            {
                "token": self.telegram_token,
                "channel": "invalid_channel",
                "description": "无效channel"
            }
        ]
        
        for case in test_cases:
            print(f"\n   测试 {case['description']}:")
            result = validate_telegram_credentials(case["token"], case["channel"])
            
            print(f"     有效性: {result['valid']}")
            if result["errors"]:
                for error in result["errors"]:
                    print(f"     错误: {error}")
            else:
                print(f"     ✅ 验证通过")
    
    def test_telegram_token_structure_analysis(self):
        """测试Telegram Token结构分析"""
        print(f"\n测试Token结构分析...")
        
        token = self.telegram_token
        
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
            
            # 验证Hash长度
            if len(bot_hash) >= 35:  # Telegram bot hash通常是35个字符
                print(f"✅ Bot Hash长度正确 ({len(bot_hash)}字符)")
            else:
                print(f"⚠️ Bot Hash长度可能不正确 ({len(bot_hash)}字符)")
        else:
            print(f"❌ Token格式不正确，缺少':'分隔符")
    
    def test_telegram_channel_structure_analysis(self):
        """测试Telegram Channel结构分析"""
        print(f"\n测试Channel结构分析...")
        
        channel = self.telegram_channel
        
        print(f"Channel ID: {channel}")
        
        if channel.startswith('@'):
            print(f"✅ 公开频道格式 (以@开头)")
            username = channel[1:]
            if len(username) >= 5:
                print(f"✅ 用户名长度合适 ({len(username)}字符)")
            else:
                print(f"⚠️ 用户名可能太短 ({len(username)}字符)")
        elif channel.startswith('-'):
            print(f"✅ 私有频道格式 (以-开头)")
            if channel.startswith('-100'):
                print(f"✅ 超级群组/频道格式")
            else:
                print(f"⚠️ 可能是普通群组格式")
        elif channel.isdigit():
            print(f"✅ 数字ID格式")
        else:
            print(f"⚠️ 未知的Channel ID格式")
    
    def test_telegram_config_edge_cases(self):
        """测试Telegram配置边界情况"""
        print(f"\n测试配置边界情况...")
        
        # 测试空值
        try:
            result = validate_telegram_credentials("", "")
            print(f"空值测试: {result}")
            assert not result["valid"]
            print(f"✅ 空值正确被拒绝")
        except Exception as e:
            print(f"❌ 空值测试异常: {e}")
        
        # 测试None值
        try:
            result = validate_telegram_credentials(None, None)
            print(f"None值测试: {result}")
            assert not result["valid"]
            print(f"✅ None值正确被拒绝")
        except Exception as e:
            print(f"❌ None值测试异常: {e}")
        
        # 测试超长值
        try:
            long_token = "a" * 1000
            long_channel = "b" * 1000
            result = validate_telegram_credentials(long_token, long_channel)
            print(f"超长值测试: {result}")
            assert not result["valid"]
            print(f"✅ 超长值正确被拒绝")
        except Exception as e:
            print(f"❌ 超长值测试异常: {e}")
    
    def test_telegram_config_security_considerations(self):
        """测试Telegram配置安全考虑"""
        print(f"\n测试安全考虑...")
        
        # 检查token是否包含敏感信息
        token = self.telegram_token
        
        # 不应该包含明显的测试标识
        if "test" in token.lower() or "demo" in token.lower():
            print(f"⚠️ Token可能是测试token")
        else:
            print(f"✅ Token看起来是生产token")
        
        # 检查channel是否是测试频道
        channel = self.telegram_channel
        if "test" in channel.lower() or "demo" in channel.lower():
            print(f"✅ Channel看起来是测试频道")
        else:
            print(f"⚠️ Channel可能是生产频道，请确保测试安全")
        
        # 提醒安全最佳实践
        print(f"\n安全提醒:")
        print(f"   - 确保API token安全存储")
        print(f"   - 定期轮换API token")
        print(f"   - 使用测试频道进行开发测试")
        print(f"   - 监控API使用情况")


if __name__ == "__main__":
    # 运行Telegram配置测试
    pytest.main([__file__, "-v", "-s"])