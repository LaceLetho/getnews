"""
Bird工具依赖管理器

管理bird工具的安装检查、版本验证和配置管理。
基于需求4.3和4.11的实现。
"""

import subprocess
import shutil
import os
import json
import logging
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass
from pathlib import Path
import re

from ..utils.logging import get_logger
from ..models import BirdConfig, BirdResult


@dataclass
class DependencyStatus:
    """依赖状态"""
    available: bool
    version: Optional[str]
    executable_path: Optional[str]
    error_message: Optional[str]
    installation_instructions: Optional[str]


@dataclass
class ValidationResult:
    """验证结果"""
    valid: bool
    issues: List[str]
    warnings: List[str]
    suggestions: List[str]


class BirdDependencyManager:
    """
    Bird工具依赖管理器
    
    负责检查bird工具的安装状态、版本兼容性验证、
    配置管理和错误诊断。
    """
    
    # 支持的bird工具版本范围
    MIN_SUPPORTED_VERSION = "0.8.0"
    MAX_SUPPORTED_VERSION = "2.0.0"
    
    # 常见的bird工具安装路径
    COMMON_PATHS = [
        "bird",
        "/usr/local/bin/bird",
        "/usr/bin/bird",
        "~/.local/bin/bird",
        "./bird",
        "/opt/bird/bin/bird"
    ]
    
    def __init__(self, config: Optional[BirdConfig] = None):
        """
        初始化依赖管理器
        
        Args:
            config: Bird工具配置，如果为None则使用默认配置
        """
        self.config = config or BirdConfig()
        self.logger = get_logger(__name__)
        self._cached_status: Optional[DependencyStatus] = None
        
        self.logger.debug(f"Bird依赖管理器初始化完成，可执行文件路径: {self.config.executable_path}")
    
    def check_bird_availability(self) -> DependencyStatus:
        """
        检查bird工具的可用性
        
        Returns:
            DependencyStatus: 依赖状态信息
        """
        try:
            self.logger.info("开始检查bird工具可用性")
            
            # 检查缓存
            if self._cached_status and self._cached_status.available:
                self.logger.debug("使用缓存的bird工具状态")
                return self._cached_status
            
            # 查找可执行文件
            executable_path = self._find_executable()
            if not executable_path:
                status = DependencyStatus(
                    available=False,
                    version=None,
                    executable_path=None,
                    error_message="未找到bird工具可执行文件",
                    installation_instructions=self.get_installation_instructions()
                )
                self._cached_status = status
                return status
            
            # 检查版本
            version = self._get_version(executable_path)
            if not version:
                status = DependencyStatus(
                    available=False,
                    version=None,
                    executable_path=executable_path,
                    error_message="无法获取bird工具版本信息",
                    installation_instructions=self.get_installation_instructions()
                )
                self._cached_status = status
                return status
            
            # 验证版本兼容性
            if not self._is_version_compatible(version):
                status = DependencyStatus(
                    available=False,
                    version=version,
                    executable_path=executable_path,
                    error_message=f"bird工具版本 {version} 不兼容，支持版本范围: {self.MIN_SUPPORTED_VERSION} - {self.MAX_SUPPORTED_VERSION}",
                    installation_instructions=self.get_installation_instructions()
                )
                self._cached_status = status
                return status
            
            # 测试基本功能
            if not self._test_basic_functionality(executable_path):
                status = DependencyStatus(
                    available=False,
                    version=version,
                    executable_path=executable_path,
                    error_message="bird工具基本功能测试失败",
                    installation_instructions=self.get_installation_instructions()
                )
                self._cached_status = status
                return status
            
            # 一切正常
            status = DependencyStatus(
                available=True,
                version=version,
                executable_path=executable_path,
                error_message=None,
                installation_instructions=None
            )
            
            self._cached_status = status
            self.logger.info(f"bird工具可用性检查完成: 版本 {version}, 路径 {executable_path}")
            return status
            
        except Exception as e:
            error_msg = f"检查bird工具可用性时出错: {str(e)}"
            self.logger.error(error_msg)
            
            status = DependencyStatus(
                available=False,
                version=None,
                executable_path=None,
                error_message=error_msg,
                installation_instructions=self.get_installation_instructions()
            )
            self._cached_status = status
            return status
    
    def _find_executable(self) -> Optional[str]:
        """查找bird工具可执行文件"""
        # 首先尝试配置中指定的路径
        if self._is_executable_valid(self.config.executable_path):
            return self.config.executable_path
        
        # 尝试常见路径
        for path in self.COMMON_PATHS:
            expanded_path = os.path.expanduser(path)
            if self._is_executable_valid(expanded_path):
                return expanded_path
        
        # 使用shutil.which查找
        which_result = shutil.which("bird")
        if which_result and self._is_executable_valid(which_result):
            return which_result
        
        return None
    
    def _is_executable_valid(self, path: str) -> bool:
        """检查可执行文件是否有效"""
        try:
            expanded_path = os.path.expanduser(path)
            return os.path.isfile(expanded_path) and os.access(expanded_path, os.X_OK)
        except Exception:
            return False
    
    def _get_version(self, executable_path: str) -> Optional[str]:
        """获取bird工具版本"""
        try:
            result = subprocess.run(
                [executable_path, "--version"],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                # 解析版本信息
                version_text = result.stdout.strip()
                # 尝试提取版本号 (例如: "bird 1.2.3" 或 "version 1.2.3")
                version_match = re.search(r'(\d+\.\d+\.\d+)', version_text)
                if version_match:
                    return version_match.group(1)
                
                # 如果没有找到标准版本格式，返回原始输出
                return version_text
            
            return None
            
        except subprocess.TimeoutExpired:
            self.logger.warning("获取bird工具版本超时")
            return None
        except Exception as e:
            self.logger.warning(f"获取bird工具版本失败: {str(e)}")
            return None
    
    def _is_version_compatible(self, version: str) -> bool:
        """检查版本兼容性"""
        try:
            # 提取版本号
            version_match = re.search(r'(\d+\.\d+\.\d+)', version)
            if not version_match:
                # 如果无法解析版本号，假设兼容
                self.logger.warning(f"无法解析版本号: {version}，假设兼容")
                return True
            
            version_str = version_match.group(1)
            version_parts = [int(x) for x in version_str.split('.')]
            min_parts = [int(x) for x in self.MIN_SUPPORTED_VERSION.split('.')]
            max_parts = [int(x) for x in self.MAX_SUPPORTED_VERSION.split('.')]
            
            # 比较版本号
            return min_parts <= version_parts < max_parts
            
        except Exception as e:
            self.logger.warning(f"版本兼容性检查失败: {str(e)}，假设兼容")
            return True
    
    def _test_basic_functionality(self, executable_path: str) -> bool:
        """测试bird工具基本功能"""
        try:
            # 尝试执行help命令
            result = subprocess.run(
                [executable_path, "--help"],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            # 如果help命令成功执行，认为基本功能正常
            return result.returncode == 0
            
        except subprocess.TimeoutExpired:
            self.logger.warning("bird工具基本功能测试超时")
            return False
        except Exception as e:
            self.logger.warning(f"bird工具基本功能测试失败: {str(e)}")
            return False
    
    def install_bird_if_missing(self) -> bool:
        """
        如果bird工具缺失，尝试自动安装
        
        Returns:
            bool: 安装是否成功
        """
        self.logger.info("尝试自动安装bird工具")
        
        # 检查当前状态
        status = self.check_bird_availability()
        if status.available:
            self.logger.info("bird工具已可用，无需安装")
            return True
        
        # 尝试不同的安装方法
        installation_methods = [
            self._install_via_npm,
            self._install_via_pip,
            self._install_via_curl,
        ]
        
        for method in installation_methods:
            try:
                if method():
                    # 清除缓存并重新检查
                    self._cached_status = None
                    status = self.check_bird_availability()
                    if status.available:
                        self.logger.info("bird工具安装成功")
                        return True
            except Exception as e:
                self.logger.warning(f"安装方法失败: {str(e)}")
                continue
        
        self.logger.error("所有自动安装方法都失败")
        return False
    
    def _install_via_npm(self) -> bool:
        """通过npm安装bird工具"""
        try:
            self.logger.debug("尝试通过npm安装bird工具")
            result = subprocess.run(
                ["npm", "install", "-g", "@laceletho/bird@latest"],
                capture_output=True,
                text=True,
                timeout=300
            )
            return result.returncode == 0
        except Exception:
            return False
    
    def _install_via_pip(self) -> bool:
        """通过pip安装bird工具"""
        try:
            self.logger.debug("尝试通过pip安装bird工具")
            result = subprocess.run(
                ["pip", "install", "bird-tool"],
                capture_output=True,
                text=True,
                timeout=300
            )
            return result.returncode == 0
        except Exception:
            return False
    
    def _install_via_curl(self) -> bool:
        """通过curl下载安装bird工具"""
        try:
            self.logger.debug("尝试通过curl下载安装bird工具")
            # 这里需要根据实际的bird工具分发方式调整
            # 示例：下载到用户本地bin目录
            local_bin = os.path.expanduser("~/.local/bin")
            os.makedirs(local_bin, exist_ok=True)
            
            # 下载命令（需要根据实际情况调整URL）
            download_url = "https://github.com/steipete/bird/releases/latest/download/bird"
            result = subprocess.run(
                ["curl", "-L", "-o", f"{local_bin}/bird", download_url],
                capture_output=True,
                text=True,
                timeout=300
            )
            
            if result.returncode == 0:
                # 设置执行权限
                os.chmod(f"{local_bin}/bird", 0o755)
                return True
            
            return False
        except Exception:
            return False
    
    def update_bird_to_latest(self) -> bool:
        """
        更新bird工具到最新版本
        
        Returns:
            bool: 更新是否成功
        """
        self.logger.info("尝试更新bird工具到最新版本")
        
        # 首先检查当前状态
        status = self.check_bird_availability()
        if not status.available:
            self.logger.warning("bird工具不可用，尝试安装而非更新")
            return self.install_bird_if_missing()
        
        # 尝试更新
        try:
            # 根据安装方式选择更新方法
            if self._is_npm_installation(status.executable_path):
                result = subprocess.run(
                    ["npm", "update", "-g", "@laceletho/bird@latest"],
                    capture_output=True,
                    text=True,
                    timeout=300
                )
                success = result.returncode == 0
            elif self._is_pip_installation(status.executable_path):
                result = subprocess.run(
                    ["pip", "install", "--upgrade", "bird-tool"],
                    capture_output=True,
                    text=True,
                    timeout=300
                )
                success = result.returncode == 0
            else:
                # 对于其他安装方式，重新下载
                success = self._install_via_curl()
            
            if success:
                # 清除缓存并重新检查
                self._cached_status = None
                new_status = self.check_bird_availability()
                if new_status.available:
                    self.logger.info(f"bird工具更新成功，新版本: {new_status.version}")
                    return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"更新bird工具失败: {str(e)}")
            return False
    
    def _is_npm_installation(self, executable_path: Optional[str]) -> bool:
        """检查是否通过npm安装"""
        if not executable_path:
            return False
        return "node_modules" in executable_path or "npm" in executable_path
    
    def _is_pip_installation(self, executable_path: Optional[str]) -> bool:
        """检查是否通过pip安装"""
        if not executable_path:
            return False
        return "site-packages" in executable_path or "pip" in executable_path
    
    def get_installation_instructions(self) -> str:
        """
        获取安装指导信息
        
        Returns:
            str: 详细的安装指导
        """
        instructions = """
Bird工具安装指南:

1. 通过npm安装 (推荐):
   npm install -g @laceletho/bird@latest

安装完成后，请确保bird工具在PATH环境变量中，或在配置文件中指定完整路径。
        """.strip()
        
        return instructions
    
    def validate_bird_configuration(self) -> ValidationResult:
        """
        验证bird工具配置
        
        Returns:
            ValidationResult: 验证结果
        """
        issues = []
        warnings = []
        suggestions = []
        
        try:
            # 检查基本可用性
            status = self.check_bird_availability()
            if not status.available:
                issues.append(f"bird工具不可用: {status.error_message}")
                suggestions.append("请安装bird工具或检查配置路径")
            
            # 检查配置文件
            config_path = os.path.expanduser(self.config.config_file_path)
            if not os.path.exists(config_path):
                warnings.append(f"bird配置文件不存在: {config_path}")
                suggestions.append("请创建bird配置文件或使用环境变量配置认证信息")
            
            # 检查配置参数
            if self.config.timeout_seconds < 60:
                warnings.append("超时时间可能过短，建议至少60秒")
            
            if self.config.rate_limit_delay < 1.0:
                warnings.append("速率限制延迟可能过短，建议至少1秒")
            
            # 检查环境变量
            required_env_vars = ["X_CT0", "X_AUTH_TOKEN"]
            missing_env_vars = []
            for var in required_env_vars:
                if not os.getenv(var):
                    missing_env_vars.append(var)
            
            if missing_env_vars:
                warnings.append(f"缺少环境变量: {', '.join(missing_env_vars)}")
                suggestions.append("请设置X/Twitter认证环境变量")
            
            # 判断整体有效性
            valid = len(issues) == 0
            
            return ValidationResult(
                valid=valid,
                issues=issues,
                warnings=warnings,
                suggestions=suggestions
            )
            
        except Exception as e:
            return ValidationResult(
                valid=False,
                issues=[f"配置验证失败: {str(e)}"],
                warnings=[],
                suggestions=["请检查配置文件格式和权限"]
            )
    
    def get_diagnostic_info(self) -> Dict[str, Any]:
        """
        获取诊断信息
        
        Returns:
            Dict[str, Any]: 详细的诊断信息
        """
        diagnostic_info = {
            "timestamp": str(datetime.now()),
            "config": self.config.to_dict(),
            "dependency_status": None,
            "validation_result": None,
            "environment_variables": {},
            "system_info": {}
        }
        
        try:
            # 依赖状态
            status = self.check_bird_availability()
            diagnostic_info["dependency_status"] = {
                "available": status.available,
                "version": status.version,
                "executable_path": status.executable_path,
                "error_message": status.error_message
            }
            
            # 验证结果
            validation = self.validate_bird_configuration()
            diagnostic_info["validation_result"] = {
                "valid": validation.valid,
                "issues": validation.issues,
                "warnings": validation.warnings,
                "suggestions": validation.suggestions
            }
            
            # 环境变量
            env_vars = ["X_CT0", "X_AUTH_TOKEN", "PATH", "HOME"]
            for var in env_vars:
                value = os.getenv(var)
                if var in ["X_CT0", "X_AUTH_TOKEN"] and value:
                    # 隐藏敏感信息
                    diagnostic_info["environment_variables"][var] = f"{value[:8]}***"
                else:
                    diagnostic_info["environment_variables"][var] = value
            
            # 系统信息
            import platform
            diagnostic_info["system_info"] = {
                "platform": platform.platform(),
                "python_version": platform.python_version(),
                "architecture": platform.architecture()[0]
            }
            
        except Exception as e:
            diagnostic_info["error"] = str(e)
        
        return diagnostic_info
    
    def clear_cache(self) -> None:
        """清除缓存的状态信息"""
        self._cached_status = None
        self.logger.debug("已清除bird工具状态缓存")


# 导入datetime用于诊断信息
from datetime import datetime