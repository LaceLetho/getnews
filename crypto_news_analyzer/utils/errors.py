"""
错误处理框架

定义系统中使用的异常类型和错误处理策略。
"""

import time
import logging
from typing import Type, Dict, Any, Optional, Callable
from enum import Enum
from dataclasses import dataclass


class ErrorType(Enum):
    """错误类型枚举"""
    NETWORK_ERROR = "network_error"
    AUTH_ERROR = "auth_error"
    PARSE_ERROR = "parse_error"
    API_ERROR = "api_error"
    CONFIG_ERROR = "config_error"
    STORAGE_ERROR = "storage_error"
    RATE_LIMIT_ERROR = "rate_limit_error"
    X_PLATFORM_ERROR = "x_platform_error"


class CryptoNewsAnalyzerError(Exception):
    """系统基础异常类"""
    
    def __init__(self, message: str, error_type: ErrorType, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.error_type = error_type
        self.details = details or {}
        self.timestamp = time.time()


class NetworkError(CryptoNewsAnalyzerError):
    """网络相关错误"""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, ErrorType.NETWORK_ERROR, details)


class AuthError(CryptoNewsAnalyzerError):
    """认证相关错误"""
    
    def __init__(self, message: str, service: str, details: Optional[Dict[str, Any]] = None):
        details = details or {}
        details["service"] = service
        super().__init__(message, ErrorType.AUTH_ERROR, details)


class AuthenticationError(AuthError):
    """认证失败错误（AuthError的别名，用于向后兼容）"""
    
    def __init__(self, message: str, service: str = "unknown", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, service, details)


class ParseError(CryptoNewsAnalyzerError):
    """解析相关错误"""
    
    def __init__(self, message: str, source: str, details: Optional[Dict[str, Any]] = None):
        details = details or {}
        details["source"] = source
        super().__init__(message, ErrorType.PARSE_ERROR, details)


class APIError(CryptoNewsAnalyzerError):
    """API调用错误"""
    
    def __init__(self, message: str, api_name: str, status_code: Optional[int] = None, details: Optional[Dict[str, Any]] = None):
        details = details or {}
        details["api_name"] = api_name
        if status_code:
            details["status_code"] = status_code
        super().__init__(message, ErrorType.API_ERROR, details)


class ConfigError(CryptoNewsAnalyzerError):
    """配置相关错误"""
    
    def __init__(self, message: str, config_field: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        details = details or {}
        if config_field:
            details["config_field"] = config_field
        super().__init__(message, ErrorType.CONFIG_ERROR, details)


class StorageError(CryptoNewsAnalyzerError):
    """存储相关错误"""
    
    def __init__(self, message: str, operation: str, details: Optional[Dict[str, Any]] = None):
        details = details or {}
        details["operation"] = operation
        super().__init__(message, ErrorType.STORAGE_ERROR, details)


class RateLimitError(CryptoNewsAnalyzerError):
    """速率限制错误"""
    
    def __init__(self, message: str, service: str, retry_after: Optional[int] = None, details: Optional[Dict[str, Any]] = None):
        details = details or {}
        details["service"] = service
        if retry_after:
            details["retry_after"] = retry_after
        super().__init__(message, ErrorType.RATE_LIMIT_ERROR, details)


class XPlatformError(CryptoNewsAnalyzerError):
    """X平台特定错误"""
    
    def __init__(self, message: str, response_code: Optional[int] = None, details: Optional[Dict[str, Any]] = None):
        details = details or {}
        if response_code:
            details["response_code"] = response_code
        super().__init__(message, ErrorType.X_PLATFORM_ERROR, details)


class CrawlerError(CryptoNewsAnalyzerError):
    """爬取器通用错误"""
    
    def __init__(self, message: str, crawler_type: str = "unknown", details: Optional[Dict[str, Any]] = None):
        details = details or {}
        details["crawler_type"] = crawler_type
        super().__init__(message, ErrorType.NETWORK_ERROR, details)


@dataclass
class RecoveryAction:
    """错误恢复动作"""
    action_type: str  # "retry", "skip", "fail", "delay"
    delay_seconds: Optional[float] = None
    max_retries: Optional[int] = None
    should_continue: bool = True
    message: Optional[str] = None


class RetryStrategy:
    """重试策略基类"""
    
    def should_retry(self, error: Exception, attempt: int) -> bool:
        """判断是否应该重试"""
        raise NotImplementedError
    
    def calculate_delay(self, attempt: int) -> float:
        """计算重试延迟时间"""
        raise NotImplementedError


class ExponentialBackoffRetry(RetryStrategy):
    """指数退避重试策略"""
    
    def __init__(self, max_retries: int = 3, base_delay: float = 1.0, max_delay: float = 60.0):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
    
    def should_retry(self, error: Exception, attempt: int) -> bool:
        return attempt < self.max_retries
    
    def calculate_delay(self, attempt: int) -> float:
        delay = self.base_delay * (2 ** attempt)
        return min(delay, self.max_delay)


class NoRetryStrategy(RetryStrategy):
    """不重试策略"""
    
    def should_retry(self, error: Exception, attempt: int) -> bool:
        return False
    
    def calculate_delay(self, attempt: int) -> float:
        return 0.0


class SkipAndContinueStrategy(RetryStrategy):
    """跳过并继续策略"""
    
    def should_retry(self, error: Exception, attempt: int) -> bool:
        return False
    
    def calculate_delay(self, attempt: int) -> float:
        return 0.0


class DelayRetryStrategy(RetryStrategy):
    """延迟重试策略"""
    
    def __init__(self, max_retries: int = 3, delay: float = 5.0):
        self.max_retries = max_retries
        self.delay = delay
    
    def should_retry(self, error: Exception, attempt: int) -> bool:
        return attempt < self.max_retries
    
    def calculate_delay(self, attempt: int) -> float:
        return self.delay


class ExtendedDelayRetryStrategy(RetryStrategy):
    """扩展延迟重试策略（用于X平台速率限制）"""
    
    def __init__(self, max_retries: int = 2, base_delay: float = 900.0):  # 15分钟基础延迟
        self.max_retries = max_retries
        self.base_delay = base_delay
    
    def should_retry(self, error: Exception, attempt: int) -> bool:
        return attempt < self.max_retries
    
    def calculate_delay(self, attempt: int) -> float:
        return self.base_delay * (attempt + 1)


class ErrorRecoveryManager:
    """错误恢复管理器"""
    
    def __init__(self):
        self.retry_strategies: Dict[Type[Exception], RetryStrategy] = {
            NetworkError: ExponentialBackoffRetry(max_retries=3),
            AuthError: NoRetryStrategy(),
            ParseError: SkipAndContinueStrategy(),
            RateLimitError: DelayRetryStrategy(),
            XPlatformError: ExtendedDelayRetryStrategy(),
            APIError: ExponentialBackoffRetry(max_retries=2)
        }
        self.logger = logging.getLogger(__name__)
    
    def handle_error(self, error: Exception, context: str, attempt: int = 0) -> RecoveryAction:
        """
        处理错误并返回恢复动作
        
        Args:
            error: 异常对象
            context: 错误上下文
            attempt: 当前尝试次数
            
        Returns:
            恢复动作
        """
        error_type = type(error)
        strategy = self.retry_strategies.get(error_type, NoRetryStrategy())
        
        self.logger.error(f"在 {context} 中发生错误: {str(error)}")
        
        if strategy.should_retry(error, attempt):
            delay = strategy.calculate_delay(attempt)
            self.logger.info(f"将在 {delay} 秒后重试 (尝试 {attempt + 1})")
            
            return RecoveryAction(
                action_type="retry",
                delay_seconds=delay,
                max_retries=getattr(strategy, 'max_retries', None),
                should_continue=True,
                message=f"重试第 {attempt + 1} 次"
            )
        else:
            if isinstance(strategy, SkipAndContinueStrategy):
                self.logger.warning(f"跳过错误项目，继续处理: {str(error)}")
                return RecoveryAction(
                    action_type="skip",
                    should_continue=True,
                    message="跳过当前项目"
                )
            else:
                self.logger.error(f"错误无法恢复: {str(error)}")
                return RecoveryAction(
                    action_type="fail",
                    should_continue=False,
                    message="操作失败"
                )
    
    def should_retry(self, error: Exception, attempt: int) -> bool:
        """判断是否应该重试"""
        error_type = type(error)
        strategy = self.retry_strategies.get(error_type, NoRetryStrategy())
        return strategy.should_retry(error, attempt)
    
    def calculate_delay(self, error: Exception, attempt: int) -> float:
        """计算重试延迟时间"""
        error_type = type(error)
        strategy = self.retry_strategies.get(error_type, NoRetryStrategy())
        return strategy.calculate_delay(attempt)
    
    def handle_x_platform_errors(self, response_code: int) -> RecoveryAction:
        """
        处理X平台特定错误
        
        Args:
            response_code: HTTP响应码
            
        Returns:
            恢复动作
        """
        if response_code == 429:  # Rate limit
            self.logger.warning("X平台速率限制，将延长等待时间")
            return RecoveryAction(
                action_type="delay",
                delay_seconds=900,  # 15分钟
                should_continue=True,
                message="遇到速率限制，延长等待时间"
            )
        elif response_code in [401, 403]:  # Auth errors
            self.logger.error("X平台认证失败")
            return RecoveryAction(
                action_type="fail",
                should_continue=False,
                message="认证失败，请检查认证信息"
            )
        elif response_code >= 500:  # Server errors
            self.logger.warning("X平台服务器错误，稍后重试")
            return RecoveryAction(
                action_type="retry",
                delay_seconds=300,  # 5分钟
                should_continue=True,
                message="服务器错误，稍后重试"
            )
        else:
            return RecoveryAction(
                action_type="skip",
                should_continue=True,
                message=f"未知错误码 {response_code}，跳过"
            )
    
    def log_recovery_action(self, action: RecoveryAction) -> None:
        """记录恢复动作"""
        self.logger.info(f"错误恢复动作: {action.action_type} - {action.message}")
    
    def generate_error_report(self, errors: list) -> str:
        """
        生成错误报告
        
        Args:
            errors: 错误列表
            
        Returns:
            错误报告字符串
        """
        if not errors:
            return "无错误"
        
        report_lines = ["## 错误报告", ""]
        
        error_counts = {}
        for error in errors:
            error_type = type(error).__name__
            error_counts[error_type] = error_counts.get(error_type, 0) + 1
        
        report_lines.append("### 错误统计")
        for error_type, count in error_counts.items():
            report_lines.append(f"- {error_type}: {count} 次")
        
        report_lines.append("\n### 详细错误")
        for i, error in enumerate(errors[:10], 1):  # 只显示前10个错误
            report_lines.append(f"{i}. {type(error).__name__}: {str(error)}")
        
        if len(errors) > 10:
            report_lines.append(f"... 还有 {len(errors) - 10} 个错误")
        
        return "\n".join(report_lines)