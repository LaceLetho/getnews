"""
REST API爬取器

实现REST API数据源的爬取功能，作为扩展数据源的示例。
支持GET/POST请求，自定义头部和参数，以及响应字段映射。
"""

import requests
import json
import time
import random
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union
from urllib.parse import urljoin, urlparse
import logging

from .data_source_interface import DataSourceInterface, CrawlError, ConfigValidationError
from ..models import ContentItem, CrawlResult, RESTAPISource, create_content_item_from_raw
from ..utils.errors import NetworkError, ParseError
from ..utils.logging import get_logger


class RESTAPICrawler(DataSourceInterface):
    """
    REST API数据源爬取器
    
    支持通过REST API获取新闻数据，具有以下特性：
    - 支持GET/POST/PUT/DELETE方法
    - 自定义请求头和参数
    - 灵活的响应字段映射
    - 时间窗口过滤
    - 错误处理和重试机制
    - 分页支持
    """
    
    # 支持的HTTP方法
    SUPPORTED_METHODS = ["GET", "POST", "PUT", "DELETE"]
    
    # 默认请求头
    DEFAULT_HEADERS = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9,zh-CN,zh;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Cache-Control": "no-cache"
    }
    
    def __init__(self, time_window_hours: int, timeout: int = 30, max_retries: int = 3):
        """
        初始化REST API爬取器
        
        Args:
            time_window_hours: 时间窗口（小时）
            timeout: 请求超时时间（秒）
            max_retries: 最大重试次数
        """
        self.time_window_hours = time_window_hours
        self.timeout = timeout
        self.max_retries = max_retries
        self.logger = get_logger(__name__)
        
        # 初始化会话
        self.session = requests.Session()
        self.session.headers.update(self.DEFAULT_HEADERS)
        
        # 计算时间窗口
        self.cutoff_time = datetime.now() - timedelta(hours=time_window_hours)
        
        self.logger.info(f"REST API爬取器初始化完成，时间窗口: {time_window_hours}小时")
    
    def get_source_type(self) -> str:
        """获取数据源类型标识"""
        return "rest_api"
    
    def get_supported_config_fields(self) -> List[str]:
        """获取支持的配置字段列表"""
        return [
            "name", "endpoint", "method", "headers", "params", "response_mapping",
            "pagination", "auth", "timeout", "max_items", "description"
        ]
    
    def get_required_config_fields(self) -> List[str]:
        """获取必需的配置字段列表"""
        return ["name", "endpoint", "method", "response_mapping"]
    
    def validate_config(self, config: Dict[str, Any]) -> bool:
        """
        验证REST API配置的有效性
        
        Args:
            config: REST API配置
            
        Returns:
            bool: 配置是否有效
            
        Raises:
            ConfigValidationError: 配置验证失败
        """
        try:
            # 检查必需字段
            required_fields = self.get_required_config_fields()
            missing_fields = [field for field in required_fields if field not in config]
            if missing_fields:
                raise ConfigValidationError(
                    f"缺少必需的配置字段: {missing_fields}",
                    source_type=self.get_source_type(),
                    source_name=config.get("name", "Unknown")
                )
            
            # 验证端点URL
            endpoint = config.get("endpoint", "")
            if not self._is_valid_url(endpoint):
                raise ConfigValidationError(
                    f"无效的API端点URL: {endpoint}",
                    source_type=self.get_source_type(),
                    source_name=config.get("name", "Unknown")
                )
            
            # 验证HTTP方法
            method = config.get("method", "").upper()
            if method not in self.SUPPORTED_METHODS:
                raise ConfigValidationError(
                    f"不支持的HTTP方法: {method}. 支持的方法: {self.SUPPORTED_METHODS}",
                    source_type=self.get_source_type(),
                    source_name=config.get("name", "Unknown")
                )
            
            # 验证响应映射
            response_mapping = config.get("response_mapping", {})
            required_mappings = ["title_field", "content_field", "url_field", "time_field"]
            missing_mappings = [field for field in required_mappings if field not in response_mapping]
            if missing_mappings:
                raise ConfigValidationError(
                    f"缺少必需的响应映射字段: {missing_mappings}",
                    source_type=self.get_source_type(),
                    source_name=config.get("name", "Unknown")
                )
            
            # 验证可选字段类型
            if "headers" in config and not isinstance(config["headers"], dict):
                raise ConfigValidationError(
                    "headers字段必须是字典类型",
                    source_type=self.get_source_type(),
                    source_name=config.get("name", "Unknown")
                )
            
            if "params" in config and not isinstance(config["params"], dict):
                raise ConfigValidationError(
                    "params字段必须是字典类型",
                    source_type=self.get_source_type(),
                    source_name=config.get("name", "Unknown")
                )
            
            return True
            
        except ConfigValidationError:
            raise
        except Exception as e:
            raise ConfigValidationError(
                f"配置验证时出现未知错误: {str(e)}",
                source_type=self.get_source_type(),
                source_name=config.get("name", "Unknown")
            ) from e
    
    def validate_source_availability(self, config: Dict[str, Any]) -> bool:
        """
        验证REST API是否可访问
        
        Args:
            config: REST API配置
            
        Returns:
            bool: API是否可访问
        """
        try:
            endpoint = config.get("endpoint", "")
            
            # 发送HEAD请求检查可访问性
            response = self.session.head(endpoint, timeout=10)
            return response.status_code < 500
            
        except Exception as e:
            self.logger.warning(f"REST API可访问性检查失败: {str(e)}")
            return False
    
    def crawl(self, config: Dict[str, Any]) -> List[ContentItem]:
        """
        爬取单个REST API数据源
        
        Args:
            config: REST API配置
            
        Returns:
            List[ContentItem]: 爬取到的内容项列表
            
        Raises:
            CrawlError: 爬取失败时抛出
        """
        # 验证配置
        self.validate_config(config)
        
        source_name = config.get("name", "Unknown API")
        self.logger.info(f"开始爬取REST API: {source_name}")
        
        try:
            # 构建请求参数
            request_params = self._build_request_params(config)
            
            # 发送API请求
            response_data = self._make_api_request(**request_params)
            
            # 解析响应数据
            items = self._parse_api_response(response_data, config)
            
            # 过滤时间窗口
            filtered_items = self._filter_by_time_window(items)
            
            self.logger.info(f"REST API {source_name} 爬取完成，获得 {len(filtered_items)} 条内容")
            return filtered_items
            
        except Exception as e:
            error_msg = f"爬取REST API失败 {source_name}: {str(e)}"
            self.logger.error(error_msg)
            raise CrawlError(error_msg, source_type=self.get_source_type(), source_name=source_name) from e
    
    def crawl_all_sources(self, sources: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        爬取所有REST API数据源
        
        Args:
            sources: REST API配置列表
            
        Returns:
            Dict[str, Any]: 包含爬取结果和状态的字典
        """
        self.logger.info(f"开始爬取 {len(sources)} 个REST API数据源")
        
        all_items = []
        crawl_results = []
        
        for source_config in sources:
            try:
                # 添加随机延迟避免过于频繁的请求
                if len(crawl_results) > 0:
                    delay = random.uniform(1, 3)
                    time.sleep(delay)
                
                items = self.crawl(source_config)
                all_items.extend(items)
                
                crawl_results.append(CrawlResult(
                    source_name=source_config.get("name", "Unknown API"),
                    status="success",
                    item_count=len(items),
                    error_message=None
                ))
                
            except Exception as e:
                source_name = source_config.get("name", "Unknown API")
                self.logger.error(f"REST API {source_name} 爬取失败: {e}")
                crawl_results.append(CrawlResult(
                    source_name=source_name,
                    status="error",
                    item_count=0,
                    error_message=str(e)
                ))
        
        self.logger.info(f"REST API爬取完成，总共获得 {len(all_items)} 条内容")
        
        return {
            'items': all_items,
            'results': crawl_results,
            'total_items': len(all_items)
        }
    
    def _build_request_params(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """构建API请求参数"""
        params = {
            "url": config["endpoint"],
            "method": config.get("method", "GET").upper(),
            "timeout": config.get("timeout", self.timeout)
        }
        
        # 设置请求头
        headers = self.DEFAULT_HEADERS.copy()
        if "headers" in config:
            headers.update(config["headers"])
        params["headers"] = headers
        
        # 设置请求参数
        if "params" in config:
            if params["method"] == "GET":
                params["params"] = config["params"]
            else:
                params["json"] = config["params"]
        
        # 设置认证
        if "auth" in config:
            auth_config = config["auth"]
            if auth_config.get("type") == "bearer":
                headers["Authorization"] = f"Bearer {auth_config.get('token', '')}"
            elif auth_config.get("type") == "basic":
                params["auth"] = (auth_config.get("username", ""), auth_config.get("password", ""))
        
        return params
    
    def _make_api_request(self, **kwargs) -> Dict[str, Any]:
        """发送API请求"""
        method = kwargs.pop("method", "GET")
        
        for attempt in range(self.max_retries):
            try:
                self.logger.debug(f"发送API请求: {method} {kwargs.get('url')} (尝试 {attempt + 1}/{self.max_retries})")
                
                response = self.session.request(method, **kwargs)
                response.raise_for_status()
                
                # 尝试解析JSON响应
                try:
                    return response.json()
                except json.JSONDecodeError:
                    # 如果不是JSON，尝试解析为文本
                    return {"text": response.text}
                
            except requests.exceptions.RequestException as e:
                self.logger.warning(f"API请求失败 (尝试 {attempt + 1}/{self.max_retries}): {e}")
                if attempt == self.max_retries - 1:
                    raise NetworkError(f"API请求失败，已重试 {self.max_retries} 次: {str(e)}") from e
                
                # 指数退避
                wait_time = (2 ** attempt) + random.uniform(0, 1)
                time.sleep(wait_time)
    
    def _parse_api_response(self, response_data: Dict[str, Any], config: Dict[str, Any]) -> List[ContentItem]:
        """解析API响应数据"""
        items = []
        response_mapping = config["response_mapping"]
        source_name = config.get("name", "Unknown API")
        
        try:
            # 获取数据数组
            data_array = self._extract_data_array(response_data, config)
            
            for item_data in data_array:
                try:
                    item = self._parse_single_item(item_data, response_mapping, source_name)
                    if item:
                        items.append(item)
                except Exception as e:
                    self.logger.warning(f"解析单个数据项失败: {e}")
                    continue
            
            return items
            
        except Exception as e:
            raise ParseError(f"解析API响应失败: {str(e)}") from e
    
    def _extract_data_array(self, response_data: Dict[str, Any], config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """从响应中提取数据数组"""
        # 如果配置了数据路径，按路径提取
        data_path = config.get("data_path", "")
        if data_path:
            current_data = response_data
            for key in data_path.split("."):
                if key and key in current_data:
                    current_data = current_data[key]
                else:
                    raise ParseError(f"数据路径 '{data_path}' 不存在")
            
            if isinstance(current_data, list):
                return current_data
            else:
                return [current_data]
        
        # 自动检测数据数组
        if isinstance(response_data, list):
            return response_data
        elif isinstance(response_data, dict):
            # 查找可能的数据数组字段
            for key in ["data", "items", "results", "articles", "news", "posts"]:
                if key in response_data and isinstance(response_data[key], list):
                    return response_data[key]
            
            # 如果没找到数组，将整个对象作为单个项目
            return [response_data]
        else:
            raise ParseError("无法从响应中提取数据数组")
    
    def _parse_single_item(self, item_data: Dict[str, Any], response_mapping: Dict[str, str], source_name: str) -> Optional[ContentItem]:
        """解析单个数据项"""
        try:
            # 提取字段
            title = self._extract_field(item_data, response_mapping["title_field"])
            content = self._extract_field(item_data, response_mapping["content_field"])
            url = self._extract_field(item_data, response_mapping["url_field"])
            time_str = self._extract_field(item_data, response_mapping["time_field"])
            
            # 验证必需字段
            if not title or not content or not url:
                self.logger.debug("数据项缺少必需字段，跳过")
                return None
            
            # 解析时间
            publish_time = self._parse_time_string(time_str)
            if not publish_time:
                self.logger.debug("无法解析时间，使用当前时间")
                publish_time = datetime.now()
            
            # 创建ContentItem
            return create_content_item_from_raw(
                title=title,
                content=content,
                url=url,
                publish_time=publish_time,
                source_name=source_name,
                source_type=self.get_source_type()
            )
            
        except Exception as e:
            self.logger.warning(f"解析数据项失败: {e}")
            return None
    
    def _extract_field(self, data: Dict[str, Any], field_path: str) -> str:
        """从数据中提取字段值"""
        if not field_path:
            return ""
        
        current_data = data
        for key in field_path.split("."):
            if key and isinstance(current_data, dict) and key in current_data:
                current_data = current_data[key]
            else:
                return ""
        
        return str(current_data) if current_data is not None else ""
    
    def _parse_time_string(self, time_str: str) -> Optional[datetime]:
        """解析时间字符串"""
        if not time_str:
            return None
        
        try:
            # 尝试ISO格式
            return datetime.fromisoformat(time_str.replace('Z', '+00:00'))
        except ValueError:
            pass
        
        try:
            # 尝试使用dateutil解析
            from dateutil import parser
            return parser.parse(time_str)
        except (ValueError, ImportError):
            pass
        
        try:
            # 尝试Unix时间戳
            timestamp = float(time_str)
            return datetime.fromtimestamp(timestamp)
        except (ValueError, OSError):
            pass
        
        return None
    
    def _filter_by_time_window(self, items: List[ContentItem]) -> List[ContentItem]:
        """根据时间窗口过滤内容项"""
        filtered_items = []
        
        for item in items:
            if item.publish_time >= self.cutoff_time:
                filtered_items.append(item)
            else:
                self.logger.debug(f"内容超出时间窗口，跳过: {item.title[:30]}...")
        
        return filtered_items
    
    def _is_valid_url(self, url: str) -> bool:
        """验证URL格式"""
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except Exception:
            return False
    
    def get_source_info(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """获取数据源信息"""
        base_info = super().get_source_info(config)
        
        # 添加REST API特定信息
        base_info.update({
            "supported_methods": self.SUPPORTED_METHODS,
            "default_timeout": self.timeout,
            "max_retries": self.max_retries,
            "features": [
                "自定义HTTP方法",
                "请求头和参数配置",
                "响应字段映射",
                "分页支持",
                "认证支持",
                "时间窗口过滤",
                "错误重试机制"
            ]
        })
        
        return base_info
    
    def cleanup(self) -> None:
        """清理资源"""
        if hasattr(self, 'session'):
            self.session.close()
            self.logger.debug("REST API爬取器资源清理完成")