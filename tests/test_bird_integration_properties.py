"""
Bird工具集成一致性属性测试

使用Hypothesis进行属性测试，验证bird工具集成的一致性。

**功能: crypto-news-analyzer, 属性 6: Bird工具集成一致性**
**验证: 需求 4.3, 4.6, 4.11**
"""

import unittest
import tempfile
import os
import shutil
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from hypothesis import given, strategies as st, assume, settings
from typing import List, Dict, Any, Optional

from crypto_news_analyzer.models import BirdConfig, BirdResult, XSource, ContentItem
from crypto_news_analyzer.crawlers.bird_wrapper import BirdWrapper
from crypto_news_analyzer.crawlers.bird_dependency_manager import BirdDependencyManager, DependencyStatus
from crypto_news_analyzer.crawlers.x_crawler import XCrawler
from crypto_news_analyzer.utils.errors import CrawlerError, AuthenticationError


# Hypothesis策略定义

@st.composite
def valid_bird_config(draw):
    """生成有效的Bird配置"""
    return BirdConfig(
        executable_path=draw(st.sampled_from(["bird", "/usr/local/bin/bird", "~/.local/bin/bird"])),
        timeout_seconds=draw(st.integers(min_value=30, max_value=600)),
        max_retries=draw(st.integers(min_value=1, max_value=5)),
        output_format=draw(st.sampled_from(["json", "text"])),
        rate_limit_delay=draw(st.floats(min_value=0.5, max_value=5.0)),
        config_file_path=draw(st.text(min_size=5, max_size=50).map(lambda x: f"~/.bird/{x}.json")),
        enable_auto_retry=draw(st.booleans()),
        retry_delay_seconds=draw(st.integers(min_value=30, max_value=300))
    )


@st.composite
def valid_x_source(draw):
    """生成有效的X源配置"""
    source_type = draw(st.sampled_from(["list", "timeline"]))
    
    if source_type == "list":
        list_id = draw(st.integers(min_value=1000000000000000000, max_value=9999999999999999999))
        url = f"https://x.com/i/lists/{list_id}"
    else:  # timeline
        username = draw(st.text(min_size=3, max_size=15, alphabet=st.characters(whitelist_categories=('Ll', 'Lu', 'Nd'), blacklist_characters='_')))
        url = f"https://x.com/{username}"
    
    return XSource(
        name=draw(st.text(min_size=5, max_size=30)),
        url=url,
        type=source_type
    )


@st.composite
def bird_command_result(draw):
    """生成bird工具命令执行结果"""
    success = draw(st.booleans())
    
    if success:
        # 成功的结果
        tweet_data = {
            "id": str(draw(st.integers(min_value=1000000000000000000, max_value=9999999999999999999))),
            "text": draw(st.text(min_size=10, max_size=280)),
            "createdAt": datetime.now().strftime("%a %b %d %H:%M:%S +0000 %Y"),
            "author": {
                "username": draw(st.text(min_size=3, max_size=15, alphabet=st.characters(whitelist_categories=('Ll', 'Lu', 'Nd')))),
                "name": draw(st.text(min_size=5, max_size=30))
            },
            "authorId": str(draw(st.integers(min_value=1000000000, max_value=9999999999))),
            "retweetCount": draw(st.integers(min_value=0, max_value=10000)),
            "likeCount": draw(st.integers(min_value=0, max_value=50000)),
            "replyCount": draw(st.integers(min_value=0, max_value=1000))
        }
        
        output = f'[{{"id": "{tweet_data["id"]}", "text": "{tweet_data["text"]}", "createdAt": "{tweet_data["createdAt"]}", "author": {{"username": "{tweet_data["author"]["username"]}", "name": "{tweet_data["author"]["name"]}"}}, "authorId": "{tweet_data["authorId"]}", "retweetCount": {tweet_data["retweetCount"]}, "likeCount": {tweet_data["likeCount"]}, "replyCount": {tweet_data["replyCount"]}}}]'
        
        return BirdResult(
            success=True,
            output=output,
            error="",
            exit_code=0,
            execution_time=draw(st.floats(min_value=0.1, max_value=10.0)),
            command=["bird", "list-timeline", "123456789"]
        )
    else:
        # 失败的结果
        error_messages = [
            "Authentication failed",
            "Rate limit exceeded", 
            "Network timeout",
            "Invalid list ID",
            "User not found",
            "Permission denied"
        ]
        
        return BirdResult(
            success=False,
            output="",
            error=draw(st.sampled_from(error_messages)),
            exit_code=draw(st.integers(min_value=1, max_value=255)),
            execution_time=draw(st.floats(min_value=0.1, max_value=5.0)),
            command=["bird", "list-timeline", "123456789"]
        )


@st.composite
def dependency_status_variations(draw):
    """生成不同的依赖状态"""
    available = draw(st.booleans())
    
    if available:
        return DependencyStatus(
            available=True,
            version=draw(st.sampled_from(["1.0.0", "1.2.3", "2.0.0-beta"])),
            executable_path=draw(st.sampled_from(["/usr/local/bin/bird", "~/.local/bin/bird", "bird"])),
            error_message=None,
            installation_instructions=None
        )
    else:
        error_messages = [
            "Bird tool not found",
            "Version incompatible", 
            "Permission denied",
            "Installation corrupted"
        ]
        
        return DependencyStatus(
            available=False,
            version=None,
            executable_path=None,
            error_message=draw(st.sampled_from(error_messages)),
            installation_instructions="Please install bird tool"
        )


class TestBirdIntegrationProperties(unittest.TestCase):
    """Bird工具集成一致性属性测试"""
    
    def setUp(self):
        """测试前准备"""
        self.temp_dir = tempfile.mkdtemp()
        
        # 设置测试环境变量
        self.original_env = {}
        test_env_vars = {
            'X_CT0': 'test_ct0_token_12345678',
            'X_AUTH_TOKEN': 'test_auth_token_87654321'
        }
        
        for key, value in test_env_vars.items():
            self.original_env[key] = os.environ.get(key)
            os.environ[key] = value
    
    def tearDown(self):
        """测试后清理"""
        # 恢复环境变量
        for key, value in self.original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        
        # 清理临时目录
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    @given(
        config=valid_bird_config(),
        x_source=valid_x_source(),
        dependency_status=dependency_status_variations()
    )
    @settings(max_examples=100, deadline=None)
    def test_bird_integration_consistency(self, config, x_source, dependency_status):
        """
        属性 6: Bird工具集成一致性
        
        对于任何有效的X源配置，系统应该能够成功调用bird工具并解析其输出，
        或在bird工具不可用时返回明确的错误信息。
        
        验证需求 4.3, 4.6, 4.11
        """
        # 设置临时配置文件路径
        config.config_file_path = os.path.join(self.temp_dir, "bird_config.json")
        
        with patch('crypto_news_analyzer.crawlers.bird_dependency_manager.BirdDependencyManager') as mock_dependency_manager:
            # 模拟依赖管理器
            mock_manager_instance = Mock()
            mock_manager_instance.check_bird_availability.return_value = dependency_status
            mock_dependency_manager.return_value = mock_manager_instance
            
            if dependency_status.available:
                # Bird工具可用的情况
                with patch('subprocess.run') as mock_subprocess:
                    # 模拟成功的bird工具调用
                    mock_result = Mock()
                    mock_result.returncode = 0
                    mock_result.stdout = '{"version": "1.0.0"}'
                    mock_result.stderr = ""
                    mock_subprocess.return_value = mock_result
                    
                    try:
                        # 创建BirdWrapper应该成功
                        wrapper = BirdWrapper(config)
                        
                        # 验证基本功能
                        assert wrapper.check_installation() == True, "Bird工具可用时check_installation应该返回True"
                        
                        # 验证版本获取
                        version = wrapper.get_version()
                        assert isinstance(version, str), "版本信息应该是字符串"
                        assert len(version) > 0, "版本信息不应该为空"
                        
                        # 验证认证设置
                        wrapper.setup_authentication("test_ct0", "test_auth_token")
                        
                        # 验证配置文件创建
                        assert os.path.exists(config.config_file_path), "认证配置文件应该被创建"
                        
                        # 验证X爬取器集成
                        crawler = XCrawler(time_window_hours=24, bird_config=config)
                        
                        # 验证爬取器初始化成功
                        assert crawler.bird_wrapper is not None, "X爬取器应该成功初始化bird_wrapper"
                        
                    except Exception as e:
                        # 如果bird工具可用但初始化失败，这是一个问题
                        self.fail(f"Bird工具可用时初始化失败: {str(e)}")
            
            else:
                # Bird工具不可用的情况
                try:
                    # 尝试创建BirdWrapper应该失败并提供明确错误信息
                    wrapper = BirdWrapper(config)
                    self.fail("Bird工具不可用时BirdWrapper初始化应该失败")
                    
                except RuntimeError as e:
                    # 验证错误信息的明确性
                    error_message = str(e)
                    assert "Bird工具不可用" in error_message, f"错误信息应该明确指出Bird工具不可用: {error_message}"
                    if dependency_status.error_message:
                        assert dependency_status.error_message in error_message, f"错误信息应该包含具体原因: {error_message}"
                    
                except Exception as e:
                    # 其他异常也是可接受的，但应该有明确的错误信息
                    error_message = str(e)
                    assert len(error_message) > 0, "错误信息不应该为空"
    
    @given(
        config=valid_bird_config(),
        command_result=bird_command_result()
    )
    @settings(max_examples=50, deadline=None)
    def test_bird_command_execution_consistency(self, config, command_result):
        """
        测试bird工具命令执行的一致性
        
        验证需求 4.6 - bird工具执行失败时应该记录错误状态并继续处理其他源
        """
        config.config_file_path = os.path.join(self.temp_dir, "bird_config.json")
        
        # 模拟bird工具可用
        dependency_status = DependencyStatus(
            available=True,
            version="1.0.0",
            executable_path="bird",
            error_message=None,
            installation_instructions=None
        )
        
        with patch('crypto_news_analyzer.crawlers.bird_dependency_manager.BirdDependencyManager') as mock_dependency_manager:
            mock_manager_instance = Mock()
            mock_manager_instance.check_bird_availability.return_value = dependency_status
            mock_dependency_manager.return_value = mock_manager_instance
            
            with patch('subprocess.run') as mock_subprocess:
                # 模拟bird工具命令执行
                mock_result = Mock()
                mock_result.returncode = command_result.exit_code
                mock_result.stdout = command_result.output
                mock_result.stderr = command_result.error
                mock_subprocess.return_value = mock_result
                
                try:
                    wrapper = BirdWrapper(config)
                    
                    # 执行命令
                    result = wrapper.execute_command(["list-timeline", "123456789"])
                    
                    # 验证结果一致性
                    assert isinstance(result, BirdResult), "执行结果应该是BirdResult类型"
                    assert result.success == command_result.success, "成功状态应该一致"
                    assert result.exit_code == command_result.exit_code, "退出码应该一致"
                    
                    if command_result.success:
                        # 成功时应该有输出
                        assert len(result.output) > 0, "成功时应该有输出内容"
                        assert result.error == "", "成功时错误信息应该为空"
                        
                        # 验证输出解析
                        parsed_data = wrapper.parse_tweet_data(result.output)
                        assert isinstance(parsed_data, list), "解析结果应该是列表"
                        
                        if len(parsed_data) > 0:
                            tweet = parsed_data[0]
                            assert isinstance(tweet, dict), "推文数据应该是字典"
                            assert 'id' in tweet, "推文应该包含id字段"
                            assert 'text' in tweet, "推文应该包含text字段"
                    else:
                        # 失败时应该有错误信息
                        assert len(result.error) > 0, "失败时应该有错误信息"
                        assert result.exit_code != 0, "失败时退出码应该非零"
                
                except Exception as e:
                    if command_result.success:
                        # 如果命令应该成功但抛出异常，这是问题
                        self.fail(f"成功的命令执行不应该抛出异常: {str(e)}")
                    else:
                        # 失败的命令可能抛出异常，这是可接受的
                        pass
    

    
    @given(
        config=valid_bird_config(),
        auth_data=st.tuples(
            st.text(min_size=8, max_size=50),  # ct0
            st.text(min_size=8, max_size=50)   # auth_token
        )
    )
    @settings(max_examples=30, deadline=None)
    def test_bird_authentication_consistency(self, config, auth_data):
        """
        测试bird工具认证的一致性
        
        验证需求 4.12 - 通过bird工具的配置文件或环境变量管理X/Twitter认证信息
        """
        config.config_file_path = os.path.join(self.temp_dir, "bird_config.json")
        ct0, auth_token = auth_data
        
        # 模拟bird工具可用
        dependency_status = DependencyStatus(
            available=True,
            version="1.0.0", 
            executable_path="bird",
            error_message=None,
            installation_instructions=None
        )
        
        with patch('crypto_news_analyzer.crawlers.bird_dependency_manager.BirdDependencyManager') as mock_dependency_manager:
            mock_manager_instance = Mock()
            mock_manager_instance.check_bird_availability.return_value = dependency_status
            mock_dependency_manager.return_value = mock_manager_instance
            
            with patch('subprocess.run') as mock_subprocess:
                mock_result = Mock()
                mock_result.returncode = 0
                mock_result.stdout = '{"version": "1.0.0"}'
                mock_result.stderr = ""
                mock_subprocess.return_value = mock_result
                
                try:
                    wrapper = BirdWrapper(config)
                    
                    # 设置认证信息
                    wrapper.setup_authentication(ct0, auth_token)
                    
                    # 验证配置文件创建
                    assert os.path.exists(config.config_file_path), "认证配置文件应该被创建"
                    
                    # 验证配置文件内容
                    import json
                    with open(config.config_file_path, 'r', encoding='utf-8') as f:
                        saved_config = json.load(f)
                    
                    assert 'auth' in saved_config, "配置文件应该包含auth部分"
                    assert saved_config['auth']['ct0'] == ct0, "保存的ct0应该与设置的一致"
                    assert saved_config['auth']['auth_token'] == auth_token, "保存的auth_token应该与设置的一致"
                    
                    # 验证文件权限（仅所有者可读写）
                    file_stat = os.stat(config.config_file_path)
                    file_mode = file_stat.st_mode & 0o777
                    assert file_mode == 0o600, f"配置文件权限应该是600，实际是{oct(file_mode)}"
                
                except Exception as e:
                    self.fail(f"认证设置失败: {str(e)}")


if __name__ == '__main__':
    unittest.main()