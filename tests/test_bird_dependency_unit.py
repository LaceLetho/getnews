"""
Bird工具依赖管理单元测试

测试bird工具依赖管理的核心功能。
"""

import unittest
from unittest.mock import patch, MagicMock
import os
import tempfile
import json
from pathlib import Path

from crypto_news_analyzer.models import BirdConfig, BirdResult
from crypto_news_analyzer.crawlers.bird_dependency_manager import (
    BirdDependencyManager, DependencyStatus, ValidationResult
)
from crypto_news_analyzer.crawlers.bird_wrapper import BirdWrapper


class TestBirdConfig(unittest.TestCase):
    """测试BirdConfig数据模型"""
    
    def test_default_config(self):
        """测试默认配置"""
        config = BirdConfig()
        
        self.assertEqual(config.executable_path, "bird")
        self.assertEqual(config.timeout_seconds, 300)
        self.assertEqual(config.max_retries, 3)
        self.assertEqual(config.output_format, "json")
        self.assertEqual(config.rate_limit_delay, 1.0)
        self.assertEqual(config.config_file_path, "~/.bird/config.json")
        self.assertTrue(config.enable_auto_retry)
        self.assertEqual(config.retry_delay_seconds, 60)
    
    def test_config_validation(self):
        """测试配置验证"""
        # 有效配置
        config = BirdConfig(
            executable_path="/usr/bin/bird",
            timeout_seconds=120,
            max_retries=5,
            output_format="text"
        )
        # 不应该抛出异常
        config.validate()
        
        # 无效配置 - 空路径
        with self.assertRaises(ValueError):
            BirdConfig(executable_path="")
        
        # 无效配置 - 负超时
        with self.assertRaises(ValueError):
            BirdConfig(timeout_seconds=-1)
        
        # 无效配置 - 不支持的格式
        with self.assertRaises(ValueError):
            BirdConfig(output_format="xml")
    
    def test_config_serialization(self):
        """测试配置序列化"""
        config = BirdConfig(
            executable_path="/usr/bin/bird",
            timeout_seconds=120
        )
        
        # 序列化
        data = config.to_dict()
        self.assertIsInstance(data, dict)
        self.assertEqual(data["executable_path"], "/usr/bin/bird")
        self.assertEqual(data["timeout_seconds"], 120)
        
        # 反序列化
        config2 = BirdConfig.from_dict(data)
        self.assertEqual(config.executable_path, config2.executable_path)
        self.assertEqual(config.timeout_seconds, config2.timeout_seconds)


class TestBirdResult(unittest.TestCase):
    """测试BirdResult数据模型"""
    
    def test_result_creation(self):
        """测试结果创建"""
        result = BirdResult(
            success=True,
            output="test output",
            error="",
            exit_code=0,
            execution_time=1.5,
            command=["bird", "--version"]
        )
        
        self.assertTrue(result.success)
        self.assertEqual(result.output, "test output")
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.execution_time, 1.5)
        self.assertEqual(result.command, ["bird", "--version"])
    
    def test_result_validation(self):
        """测试结果验证"""
        # 有效结果
        result = BirdResult(
            success=False,
            output="",
            error="command not found",
            exit_code=127,
            execution_time=0.1,
            command=["bird"]
        )
        # 不应该抛出异常
        
        # 无效结果 - 命令不是列表
        with self.assertRaises(ValueError):
            BirdResult(
                success=True,
                output="",
                error="",
                exit_code=0,
                execution_time=1.0,
                command="bird --version"  # 应该是列表
            )
        
        # 无效结果 - 负执行时间
        with self.assertRaises(ValueError):
            BirdResult(
                success=True,
                output="",
                error="",
                exit_code=0,
                execution_time=-1.0,
                command=["bird"]
            )


class TestBirdDependencyManager(unittest.TestCase):
    """测试Bird依赖管理器"""
    
    def setUp(self):
        """设置测试"""
        self.config = BirdConfig()
        self.manager = BirdDependencyManager(self.config)
    
    def test_manager_creation(self):
        """测试管理器创建"""
        self.assertIsInstance(self.manager, BirdDependencyManager)
        self.assertEqual(self.manager.config, self.config)
    
    @patch('shutil.which')
    @patch('os.path.isfile')
    @patch('os.access')
    def test_find_executable_success(self, mock_access, mock_isfile, mock_which):
        """测试找到可执行文件"""
        # 模拟配置路径不存在，但which找到可执行文件
        def mock_isfile_side_effect(path):
            return path == "/usr/bin/bird"
        
        def mock_access_side_effect(path, mode):
            return path == "/usr/bin/bird"
        
        mock_isfile.side_effect = mock_isfile_side_effect
        mock_access.side_effect = mock_access_side_effect
        mock_which.return_value = "/usr/bin/bird"
        
        executable = self.manager._find_executable()
        self.assertEqual(executable, "/usr/bin/bird")
    
    @patch('shutil.which')
    def test_find_executable_not_found(self, mock_which):
        """测试未找到可执行文件"""
        mock_which.return_value = None
        
        executable = self.manager._find_executable()
        self.assertIsNone(executable)
    
    @patch('subprocess.run')
    def test_get_version_success(self, mock_run):
        """测试获取版本成功"""
        # 模拟成功的版本命令
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "bird version 1.2.3"
        mock_run.return_value = mock_result
        
        version = self.manager._get_version("/usr/bin/bird")
        self.assertEqual(version, "1.2.3")
    
    @patch('subprocess.run')
    def test_get_version_failure(self, mock_run):
        """测试获取版本失败"""
        # 模拟失败的版本命令
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_run.return_value = mock_result
        
        version = self.manager._get_version("/usr/bin/bird")
        self.assertIsNone(version)
    
    def test_version_compatibility(self):
        """测试版本兼容性检查"""
        # 兼容版本
        self.assertTrue(self.manager._is_version_compatible("1.5.0"))
        self.assertTrue(self.manager._is_version_compatible("bird version 1.2.3"))
        
        # 不兼容版本（太旧）
        self.assertFalse(self.manager._is_version_compatible("0.9.0"))
        
        # 不兼容版本（太新）
        self.assertFalse(self.manager._is_version_compatible("2.1.0"))
        
        # 无法解析的版本（假设兼容）
        self.assertTrue(self.manager._is_version_compatible("unknown"))
    
    def test_get_installation_instructions(self):
        """测试获取安装指导"""
        instructions = self.manager.get_installation_instructions()
        
        self.assertIsInstance(instructions, str)
        self.assertIn("npm install -g @steipete/bird@latest", instructions)
        self.assertIn("pip install", instructions)
        self.assertIn("curl", instructions)
    
    def test_validate_bird_configuration(self):
        """测试配置验证"""
        # 由于bird工具不存在，应该返回无效配置
        result = self.manager.validate_bird_configuration()
        
        self.assertIsInstance(result, ValidationResult)
        self.assertFalse(result.valid)  # 因为bird工具不存在
        self.assertIsInstance(result.issues, list)
        self.assertIsInstance(result.warnings, list)
        self.assertIsInstance(result.suggestions, list)
    
    def test_get_diagnostic_info(self):
        """测试获取诊断信息"""
        diagnostic = self.manager.get_diagnostic_info()
        
        self.assertIsInstance(diagnostic, dict)
        self.assertIn("timestamp", diagnostic)
        self.assertIn("config", diagnostic)
        self.assertIn("dependency_status", diagnostic)
        self.assertIn("validation_result", diagnostic)
        self.assertIn("environment_variables", diagnostic)
        self.assertIn("system_info", diagnostic)


class TestBirdWrapperMocked(unittest.TestCase):
    """测试Bird封装器（模拟环境）"""
    
    def setUp(self):
        """设置测试"""
        self.config = BirdConfig()
    
    @patch('crypto_news_analyzer.crawlers.bird_wrapper.BirdDependencyManager')
    def test_wrapper_creation_success(self, mock_manager_class):
        """测试封装器创建成功"""
        # 模拟依赖管理器返回可用状态
        mock_manager = MagicMock()
        mock_status = MagicMock()
        mock_status.available = True
        mock_status.version = "1.2.3"
        mock_status.executable_path = "/usr/bin/bird"
        mock_manager.check_bird_availability.return_value = mock_status
        mock_manager_class.return_value = mock_manager
        
        # 模拟环境变量
        with patch.dict(os.environ, {'X_CT0': 'test_ct0', 'X_AUTH_TOKEN': 'test_token'}):
            wrapper = BirdWrapper(self.config)
            self.assertIsInstance(wrapper, BirdWrapper)
    
    @patch('crypto_news_analyzer.crawlers.bird_wrapper.BirdDependencyManager')
    def test_wrapper_creation_failure(self, mock_manager_class):
        """测试封装器创建失败"""
        # 模拟依赖管理器返回不可用状态
        mock_manager = MagicMock()
        mock_status = MagicMock()
        mock_status.available = False
        mock_status.error_message = "bird not found"
        mock_manager.check_bird_availability.return_value = mock_status
        mock_manager_class.return_value = mock_manager
        
        with self.assertRaises(RuntimeError):
            BirdWrapper(self.config)
    
    @patch('crypto_news_analyzer.crawlers.bird_wrapper.BirdDependencyManager')
    @patch('subprocess.run')
    def test_execute_command_success(self, mock_run, mock_manager_class):
        """测试命令执行成功"""
        # 模拟依赖管理器
        mock_manager = MagicMock()
        mock_status = MagicMock()
        mock_status.available = True
        mock_manager.check_bird_availability.return_value = mock_status
        mock_manager_class.return_value = mock_manager
        
        # 模拟成功的命令执行
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "success output"
        mock_result.stderr = ""
        mock_run.return_value = mock_result
        
        with patch.dict(os.environ, {'X_CT0': 'test_ct0', 'X_AUTH_TOKEN': 'test_token'}):
            wrapper = BirdWrapper(self.config)
            result = wrapper.execute_command(["--version"])
            
            self.assertIsInstance(result, BirdResult)
            self.assertTrue(result.success)
            self.assertEqual(result.output, "success output")
            self.assertEqual(result.exit_code, 0)
    
    @patch('crypto_news_analyzer.crawlers.bird_wrapper.BirdDependencyManager')
    @patch('subprocess.run')
    def test_execute_command_failure(self, mock_run, mock_manager_class):
        """测试命令执行失败"""
        # 模拟依赖管理器
        mock_manager = MagicMock()
        mock_status = MagicMock()
        mock_status.available = True
        mock_manager.check_bird_availability.return_value = mock_status
        mock_manager_class.return_value = mock_manager
        
        # 模拟失败的命令执行
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "command failed"
        mock_run.return_value = mock_result
        
        with patch.dict(os.environ, {'X_CT0': 'test_ct0', 'X_AUTH_TOKEN': 'test_token'}):
            wrapper = BirdWrapper(self.config)
            result = wrapper.execute_command(["invalid"])
            
            self.assertIsInstance(result, BirdResult)
            self.assertFalse(result.success)
            self.assertEqual(result.error, "command failed")
            self.assertEqual(result.exit_code, 1)
    
    @patch('crypto_news_analyzer.crawlers.bird_wrapper.BirdDependencyManager')
    @patch('subprocess.run')
    def test_execute_command_timeout(self, mock_run, mock_manager_class):
        """测试命令执行超时"""
        # 模拟依赖管理器
        mock_manager = MagicMock()
        mock_status = MagicMock()
        mock_status.available = True
        mock_manager.check_bird_availability.return_value = mock_status
        mock_manager_class.return_value = mock_manager
        
        # 模拟超时异常
        from subprocess import TimeoutExpired
        mock_run.side_effect = TimeoutExpired(["bird", "--version"], 30)
        
        with patch.dict(os.environ, {'X_CT0': 'test_ct0', 'X_AUTH_TOKEN': 'test_token'}):
            wrapper = BirdWrapper(self.config)
            result = wrapper.execute_command(["--version"], timeout=30)
            
            self.assertIsInstance(result, BirdResult)
            self.assertFalse(result.success)
            self.assertIn("超时", result.error)
            self.assertEqual(result.exit_code, -1)
    
    @patch('crypto_news_analyzer.crawlers.bird_wrapper.BirdDependencyManager')
    def test_setup_authentication(self, mock_manager_class):
        """测试设置认证信息"""
        # 模拟依赖管理器
        mock_manager = MagicMock()
        mock_status = MagicMock()
        mock_status.available = True
        mock_manager.check_bird_availability.return_value = mock_status
        mock_manager_class.return_value = mock_manager
        
        with patch.dict(os.environ, {'X_CT0': 'test_ct0', 'X_AUTH_TOKEN': 'test_token'}):
            with tempfile.TemporaryDirectory() as temp_dir:
                config_path = os.path.join(temp_dir, "config.json")
                test_config = BirdConfig(config_file_path=config_path)
                
                wrapper = BirdWrapper(test_config)
                wrapper.setup_authentication("new_ct0", "new_token")
                
                # 验证配置文件是否创建
                self.assertTrue(os.path.exists(config_path))
                
                # 验证配置内容
                with open(config_path, 'r') as f:
                    config_data = json.load(f)
                
                self.assertEqual(config_data["auth"]["ct0"], "new_ct0")
                self.assertEqual(config_data["auth"]["auth_token"], "new_token")
    
    @patch('crypto_news_analyzer.crawlers.bird_wrapper.BirdDependencyManager')
    @patch('subprocess.run')
    def test_fetch_list_tweets(self, mock_run, mock_manager_class):
        """测试获取列表推文"""
        # 模拟依赖管理器
        mock_manager = MagicMock()
        mock_status = MagicMock()
        mock_status.available = True
        mock_manager.check_bird_availability.return_value = mock_status
        mock_manager_class.return_value = mock_manager
        
        # 模拟成功的命令执行
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = '{"tweets": [{"id": "123", "text": "test tweet"}]}'
        mock_result.stderr = ""
        mock_run.return_value = mock_result
        
        with patch.dict(os.environ, {'X_CT0': 'test_ct0', 'X_AUTH_TOKEN': 'test_token'}):
            wrapper = BirdWrapper(self.config)
            result = wrapper.fetch_list_tweets("test_list_id", 50)
            
            self.assertIsInstance(result, BirdResult)
            self.assertTrue(result.success)
            self.assertIn("test tweet", result.output)
    
    @patch('crypto_news_analyzer.crawlers.bird_wrapper.BirdDependencyManager')
    @patch('subprocess.run')
    def test_fetch_user_timeline(self, mock_run, mock_manager_class):
        """测试获取用户时间线"""
        # 模拟依赖管理器
        mock_manager = MagicMock()
        mock_status = MagicMock()
        mock_status.available = True
        mock_manager.check_bird_availability.return_value = mock_status
        mock_manager_class.return_value = mock_manager
        
        # 模拟成功的命令执行
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = '{"tweets": [{"id": "456", "text": "user tweet"}]}'
        mock_result.stderr = ""
        mock_run.return_value = mock_result
        
        with patch.dict(os.environ, {'X_CT0': 'test_ct0', 'X_AUTH_TOKEN': 'test_token'}):
            wrapper = BirdWrapper(self.config)
            result = wrapper.fetch_user_timeline("testuser", 25)
            
            self.assertIsInstance(result, BirdResult)
            self.assertTrue(result.success)
            self.assertIn("user tweet", result.output)
    
    @patch('crypto_news_analyzer.crawlers.bird_wrapper.BirdDependencyManager')
    def test_parse_tweet_data_json(self, mock_manager_class):
        """测试解析JSON格式推文数据"""
        # 模拟依赖管理器
        mock_manager = MagicMock()
        mock_status = MagicMock()
        mock_status.available = True
        mock_manager.check_bird_availability.return_value = mock_status
        mock_manager_class.return_value = mock_manager
        
        with patch.dict(os.environ, {'X_CT0': 'test_ct0', 'X_AUTH_TOKEN': 'test_token'}):
            wrapper = BirdWrapper(self.config)
            
            # 测试JSON格式数据
            json_data = '''[
                {
                    "id": "123456789",
                    "text": "This is a test tweet",
                    "created_at": "2024-01-01T12:00:00Z",
                    "user": {"screen_name": "testuser", "name": "Test User"}
                }
            ]'''
            
            tweets = wrapper.parse_tweet_data(json_data)
            
            self.assertEqual(len(tweets), 1)
            self.assertEqual(tweets[0]["id"], "123456789")
            self.assertEqual(tweets[0]["text"], "This is a test tweet")
    
    @patch('crypto_news_analyzer.crawlers.bird_wrapper.BirdDependencyManager')
    def test_parse_tweet_data_empty(self, mock_manager_class):
        """测试解析空数据"""
        # 模拟依赖管理器
        mock_manager = MagicMock()
        mock_status = MagicMock()
        mock_status.available = True
        mock_manager.check_bird_availability.return_value = mock_status
        mock_manager_class.return_value = mock_manager
        
        with patch.dict(os.environ, {'X_CT0': 'test_ct0', 'X_AUTH_TOKEN': 'test_token'}):
            wrapper = BirdWrapper(self.config)
            
            # 测试空数据
            tweets = wrapper.parse_tweet_data("")
            self.assertEqual(len(tweets), 0)
            
            # 测试None数据
            tweets = wrapper.parse_tweet_data(None)
            self.assertEqual(len(tweets), 0)
    
    @patch('crypto_news_analyzer.crawlers.bird_wrapper.BirdDependencyManager')
    @patch('subprocess.run')
    def test_test_connection(self, mock_run, mock_manager_class):
        """测试连接测试功能"""
        # 模拟依赖管理器
        mock_manager = MagicMock()
        mock_status = MagicMock()
        mock_status.available = True
        mock_manager.check_bird_availability.return_value = mock_status
        mock_manager_class.return_value = mock_manager
        
        # 模拟成功的连接测试
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = '{"user": {"screen_name": "twitter"}}'
        mock_result.stderr = ""
        mock_run.return_value = mock_result
        
        with patch.dict(os.environ, {'X_CT0': 'test_ct0', 'X_AUTH_TOKEN': 'test_token'}):
            wrapper = BirdWrapper(self.config)
            result = wrapper.test_connection()
            
            self.assertTrue(result)
    
    @patch('crypto_news_analyzer.crawlers.bird_wrapper.BirdDependencyManager')
    def test_get_diagnostic_info(self, mock_manager_class):
        """测试获取诊断信息"""
        # 模拟依赖管理器
        mock_manager = MagicMock()
        mock_status = MagicMock()
        mock_status.available = True
        mock_status.version = "1.2.3"
        mock_status.executable_path = "/usr/bin/bird"
        mock_status.error_message = None
        mock_manager.check_bird_availability.return_value = mock_status
        mock_manager_class.return_value = mock_manager
        
        with patch.dict(os.environ, {'X_CT0': 'test_ct0', 'X_AUTH_TOKEN': 'test_token'}):
            wrapper = BirdWrapper(self.config)
            
            # 模拟get_version方法
            with patch.object(wrapper, 'get_version', return_value="1.2.3"):
                with patch.object(wrapper, 'test_connection', return_value=True):
                    diagnostic = wrapper.get_diagnostic_info()
            
            self.assertIsInstance(diagnostic, dict)
            self.assertIn("config", diagnostic)
            self.assertIn("dependency_status", diagnostic)
            self.assertIn("connection_test", diagnostic)
            self.assertTrue(diagnostic["connection_test"])


if __name__ == '__main__':
    unittest.main()