"""
Bird工具Python封装层

提供Python接口调用bird工具的命令行功能。
基于需求4.4、4.5和4.12的实现。
"""

import subprocess
import json
import os
import time
import tempfile
from typing import Dict, List, Optional, Any
from pathlib import Path
import logging

from ..models import BirdConfig, BirdResult
from ..utils.logging import get_logger
from .bird_dependency_manager import BirdDependencyManager


class BirdWrapper:
    """
    Bird工具Python封装层
    
    提供调用bird工具命令行接口的Python封装，
    支持认证管理、命令执行和输出解析。
    """
    
    def __init__(self, config: Optional[BirdConfig] = None):
        """
        初始化Bird封装器
        
        Args:
            config: Bird工具配置，如果为None则使用默认配置
        """
        self.config = config or BirdConfig()
        self.logger = get_logger(__name__)
        self.dependency_manager = BirdDependencyManager(self.config)
        
        # 验证bird工具可用性
        self._validate_bird_availability()
        
        # 设置认证信息
        self._setup_authentication()
        
        self.logger.info("Bird工具封装器初始化完成")
    
    def _validate_bird_availability(self) -> None:
        """验证bird工具可用性"""
        status = self.dependency_manager.check_bird_availability()
        if not status.available:
            error_msg = f"Bird工具不可用: {status.error_message}"
            self.logger.error(error_msg)
            raise RuntimeError(error_msg)
        
        self.logger.info(f"Bird工具验证成功: 版本 {status.version}, 路径 {status.executable_path}")
    
    def _setup_authentication(self) -> None:
        """设置认证信息"""
        try:
            # 从环境变量读取认证信息
            ct0 = os.getenv('X_CT0')
            auth_token = os.getenv('X_AUTH_TOKEN')
            
            if not ct0 or not auth_token:
                self.logger.warning("未找到X/Twitter认证环境变量，某些功能可能不可用")
                return
            
            # 设置认证信息到bird配置
            self.setup_authentication(ct0, auth_token)
            
        except Exception as e:
            self.logger.error(f"设置认证信息失败: {str(e)}")
            raise
    
    def check_installation(self) -> bool:
        """
        检查bird工具安装状态
        
        Returns:
            bool: 是否已正确安装
        """
        status = self.dependency_manager.check_bird_availability()
        return status.available
    
    def get_version(self) -> str:
        """
        获取bird工具版本
        
        Returns:
            str: 版本信息
        """
        try:
            result = self.execute_command(["--version"], timeout=30)
            if result.success:
                return result.output.strip()
            else:
                raise RuntimeError(f"获取版本失败: {result.error}")
        except Exception as e:
            self.logger.error(f"获取bird工具版本失败: {str(e)}")
            raise
    
    def execute_command(self, args: List[str], timeout: Optional[int] = None) -> BirdResult:
        """
        执行bird工具命令
        
        Args:
            args: 命令参数列表
            timeout: 超时时间（秒），如果为None则使用配置中的默认值
            
        Returns:
            BirdResult: 执行结果
        """
        if timeout is None:
            timeout = self.config.timeout_seconds
        
        # 构建完整命令，添加认证参数
        command = [self.config.executable_path]
        
        # 添加认证参数
        ct0 = os.getenv('x_ct0')
        auth_token = os.getenv('x_auth_token')
        
        if ct0:
            command.extend(["--ct0", ct0])
        if auth_token:
            command.extend(["--auth-token", auth_token])
        
        # 添加用户命令参数
        command.extend(args)
        
        start_time = time.time()
        
        try:
            self.logger.debug(f"执行bird命令: {' '.join(command[:3])} ... (隐藏认证参数)")
            
            # 执行命令
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=self._get_environment()
            )
            
            execution_time = time.time() - start_time
            
            # 创建结果对象
            bird_result = BirdResult(
                success=result.returncode == 0,
                output=result.stdout,
                error=result.stderr,
                exit_code=result.returncode,
                execution_time=execution_time,
                command=command
            )
            
            if bird_result.success:
                self.logger.debug(f"Bird命令执行成功，耗时 {execution_time:.2f} 秒")
            else:
                self.logger.warning(f"Bird命令执行失败，退出码: {result.returncode}, 错误: {result.stderr}")
            
            return bird_result
            
        except subprocess.TimeoutExpired:
            execution_time = time.time() - start_time
            error_msg = f"Bird命令执行超时 ({timeout}秒)"
            self.logger.error(error_msg)
            
            return BirdResult(
                success=False,
                output="",
                error=error_msg,
                exit_code=-1,
                execution_time=execution_time,
                command=command
            )
            
        except Exception as e:
            execution_time = time.time() - start_time
            error_msg = f"Bird命令执行异常: {str(e)}"
            self.logger.error(error_msg)
            
            return BirdResult(
                success=False,
                output="",
                error=error_msg,
                exit_code=-1,
                execution_time=execution_time,
                command=command
            )
    
    def _get_environment(self) -> Dict[str, str]:
        """获取执行环境变量"""
        env = os.environ.copy()
        
        # 添加bird工具特定的环境变量
        ct0 = os.getenv('X_CT0')
        auth_token = os.getenv('X_AUTH_TOKEN')
        
        if ct0:
            env['X_CT0'] = ct0
        if auth_token:
            env['X_AUTH_TOKEN'] = auth_token
        
        return env
    
    def setup_authentication_from_env(self) -> None:
        """从环境变量设置认证信息"""
        ct0 = os.getenv('X_CT0')
        auth_token = os.getenv('X_AUTH_TOKEN')
        
        if not ct0 or not auth_token:
            raise ValueError("环境变量X_CT0和X_AUTH_TOKEN必须设置")
        
        self.setup_authentication(ct0, auth_token)
    
    def setup_authentication(self, ct0: str, auth_token: str) -> None:
        """
        设置X/Twitter认证信息
        
        Args:
            ct0: X认证参数ct0
            auth_token: X认证令牌
        """
        try:
            # 验证参数
            if not ct0 or not ct0.strip():
                raise ValueError("ct0参数不能为空")
            if not auth_token or not auth_token.strip():
                raise ValueError("auth_token参数不能为空")
            
            # 创建bird配置文件
            config_path = os.path.expanduser(self.config.config_file_path)
            config_dir = os.path.dirname(config_path)
            
            # 确保配置目录存在
            os.makedirs(config_dir, exist_ok=True)
            
            # 准备配置数据
            bird_config = {
                "auth": {
                    "ct0": ct0,
                    "auth_token": auth_token
                },
                "settings": {
                    "output_format": self.config.output_format,
                    "rate_limit_delay": self.config.rate_limit_delay,
                    "max_retries": self.config.max_retries,
                    "enable_auto_retry": self.config.enable_auto_retry,
                    "retry_delay_seconds": self.config.retry_delay_seconds
                }
            }
            
            # 写入配置文件
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(bird_config, f, indent=2)
            
            # 设置文件权限（仅所有者可读写）
            os.chmod(config_path, 0o600)
            
            self.logger.info(f"Bird认证配置已保存到: {config_path}")
            
        except Exception as e:
            self.logger.error(f"设置bird认证信息失败: {str(e)}")
            raise
    
    def fetch_list_tweets(self, list_id: str, count: int = 100) -> BirdResult:
        """
        获取X列表推文
        
        Args:
            list_id: 列表ID
            count: 获取数量
            
        Returns:
            BirdResult: 执行结果
        """
        try:
            # 构建命令参数
            args = [
                "list-timeline",
                list_id,
                "--json",
                "--count", str(count)
            ]
            
            # 添加速率限制延迟
            if hasattr(self, '_last_request_time'):
                elapsed = time.time() - self._last_request_time
                if elapsed < self.config.rate_limit_delay:
                    sleep_time = self.config.rate_limit_delay - elapsed
                    self.logger.debug(f"速率限制延迟: {sleep_time:.2f} 秒")
                    time.sleep(sleep_time)
            
            # 执行命令
            result = self.execute_command(args)
            self._last_request_time = time.time()
            
            return result
            
        except Exception as e:
            error_msg = f"获取列表推文失败: {str(e)}"
            self.logger.error(error_msg)
            
            return BirdResult(
                success=False,
                output="",
                error=error_msg,
                exit_code=-1,
                execution_time=0.0,
                command=["bird", "list-timeline", list_id]
            )
    
    def fetch_user_timeline(self, username: str, count: int = 100) -> BirdResult:
        """
        获取用户时间线
        
        Args:
            username: 用户名（不包含@符号）
            count: 获取数量
            
        Returns:
            BirdResult: 执行结果
        """
        try:
            # 清理用户名
            if username.startswith('@'):
                username = username[1:]
            
            # 构建命令参数
            if username == "home":
                # 主时间线
                args = [
                    "home",
                    "--json",
                    "--count", str(count)
                ]
            else:
                # 用户时间线
                args = [
                    "user-tweets",
                    username,
                    "--json",
                    "--count", str(count)
                ]
            
            # 添加速率限制延迟
            if hasattr(self, '_last_request_time'):
                elapsed = time.time() - self._last_request_time
                if elapsed < self.config.rate_limit_delay:
                    sleep_time = self.config.rate_limit_delay - elapsed
                    self.logger.debug(f"速率限制延迟: {sleep_time:.2f} 秒")
                    time.sleep(sleep_time)
            
            # 执行命令
            result = self.execute_command(args)
            self._last_request_time = time.time()
            
            return result
            
        except Exception as e:
            error_msg = f"获取用户时间线失败: {str(e)}"
            self.logger.error(error_msg)
            
            return BirdResult(
                success=False,
                output="",
                error=error_msg,
                exit_code=-1,
                execution_time=0.0,
                command=["bird", "user-tweets", username]
            )
    
    def parse_tweet_data(self, raw_data: str) -> List[Dict[str, Any]]:
        """
        解析推文数据
        
        Args:
            raw_data: bird工具的原始输出
            
        Returns:
            List[Dict[str, Any]]: 解析后的推文数据列表
        """
        try:
            if not raw_data or not raw_data.strip():
                return []
            
            # 根据输出格式解析数据
            if self.config.output_format == "json":
                return self._parse_json_output(raw_data)
            elif self.config.output_format == "text":
                return self._parse_text_output(raw_data)
            else:
                self.logger.warning(f"不支持的输出格式: {self.config.output_format}")
                return []
                
        except Exception as e:
            self.logger.error(f"解析推文数据失败: {str(e)}")
            return []
    
    def _parse_json_output(self, raw_data: str) -> List[Dict[str, Any]]:
        """解析JSON格式输出"""
        try:
            # 尝试解析为JSON
            data = json.loads(raw_data)
            
            # bird工具返回的数据可能是数组或单个对象
            if isinstance(data, list):
                tweets = data
            elif isinstance(data, dict):
                # 如果是单个对象，检查是否有tweets字段
                if 'tweets' in data:
                    tweets = data['tweets']
                elif 'data' in data:
                    tweets = data['data'] if isinstance(data['data'], list) else [data['data']]
                else:
                    tweets = [data]
            else:
                return []
            
            # 标准化推文数据格式
            normalized_tweets = []
            for item in tweets:
                if isinstance(item, dict):
                    tweet = self._normalize_tweet_data(item)
                    if tweet:
                        normalized_tweets.append(tweet)
            
            return normalized_tweets
            
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON解析失败: {str(e)}")
            return []
    
    def _parse_text_output(self, raw_data: str) -> List[Dict[str, Any]]:
        """解析文本格式输出"""
        try:
            tweets = []
            lines = raw_data.strip().split('\n')
            
            current_tweet = {}
            for line in lines:
                line = line.strip()
                if not line:
                    if current_tweet:
                        tweets.append(current_tweet)
                        current_tweet = {}
                    continue
                
                # 解析字段
                if line.startswith('ID: '):
                    current_tweet['id'] = line[4:]
                elif line.startswith('Text: '):
                    current_tweet['text'] = line[6:]
                elif line.startswith('User: '):
                    current_tweet['user'] = {'screen_name': line[6:]}
                elif line.startswith('Time: '):
                    current_tweet['created_at'] = line[6:]
                elif line.startswith('URL: '):
                    current_tweet['url'] = line[5:]
            
            # 添加最后一条推文
            if current_tweet:
                tweets.append(current_tweet)
            
            return tweets
            
        except Exception as e:
            self.logger.error(f"文本解析失败: {str(e)}")
            return []
    
    def _normalize_tweet_data(self, raw_tweet: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """标准化推文数据格式"""
        try:
            # bird工具的输出格式可能包含以下字段
            tweet = {
                'id': raw_tweet.get('id_str', raw_tweet.get('id', '')),
                'text': raw_tweet.get('full_text', raw_tweet.get('text', '')),
                'created_at': raw_tweet.get('created_at', ''),
                'user': {},
                'entities': raw_tweet.get('entities', {}),
                'public_metrics': raw_tweet.get('public_metrics', {})
            }
            
            # 处理用户信息
            user_data = raw_tweet.get('user', {})
            if user_data:
                tweet['user'] = {
                    'screen_name': user_data.get('screen_name', user_data.get('username', '')),
                    'name': user_data.get('name', ''),
                    'id': user_data.get('id_str', user_data.get('id', ''))
                }
            else:
                # 如果没有用户信息，尝试从其他字段获取
                tweet['user'] = {
                    'screen_name': raw_tweet.get('username', raw_tweet.get('screen_name', 'unknown')),
                    'name': raw_tweet.get('name', ''),
                    'id': raw_tweet.get('user_id', '')
                }
            
            # 确保必需字段存在
            if not tweet['id'] or not tweet['text']:
                return None
            
            return tweet
            
        except Exception as e:
            self.logger.warning(f"标准化推文数据失败: {str(e)}")
            return None
    
    def test_connection(self) -> bool:
        """
        测试与X/Twitter的连接
        
        Returns:
            bool: 连接是否成功
        """
        try:
            # 使用whoami命令测试连接
            result = self.execute_command(["whoami"], timeout=30)
            
            if result.success:
                self.logger.info("Bird工具连接测试成功")
                return True
            else:
                self.logger.warning(f"Bird工具连接测试失败: {result.error}")
                return False
                
        except Exception as e:
            self.logger.error(f"Bird工具连接测试异常: {str(e)}")
            return False
    
    def get_diagnostic_info(self) -> Dict[str, Any]:
        """
        获取诊断信息
        
        Returns:
            Dict[str, Any]: 诊断信息
        """
        diagnostic_info = {
            "config": self.config.to_dict(),
            "dependency_status": None,
            "connection_test": False,
            "version": None
        }
        
        try:
            # 依赖状态
            status = self.dependency_manager.check_bird_availability()
            diagnostic_info["dependency_status"] = {
                "available": status.available,
                "version": status.version,
                "executable_path": status.executable_path,
                "error_message": status.error_message
            }
            
            # 版本信息
            if status.available:
                try:
                    diagnostic_info["version"] = self.get_version()
                except Exception:
                    pass
            
            # 连接测试
            if status.available:
                diagnostic_info["connection_test"] = self.test_connection()
            
        except Exception as e:
            diagnostic_info["error"] = str(e)
        
        return diagnostic_info