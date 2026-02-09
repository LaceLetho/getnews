"""
X/Twitter爬取器

基于bird工具实现X/Twitter内容爬取功能。
通过bird工具避免复杂的反爬机制，提供稳定的数据获取能力。
基于需求4.1、4.2、4.7、4.8的实现。
"""

import time
import json
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from urllib.parse import urlparse

from ..models import ContentItem, XSource, CrawlResult, BirdConfig, create_content_item_from_raw
from ..utils.errors import CrawlerError, AuthenticationError
from ..utils.logging import get_logger
from .bird_wrapper import BirdWrapper


class XCrawler:
    """
    X/Twitter爬取器
    
    基于bird工具实现X/Twitter内容爬取，避免复杂的反爬机制。
    支持列表和时间线爬取，提供稳定的数据获取能力。
    """
    
    def __init__(self, time_window_hours: int, bird_config: Optional[BirdConfig] = None):
        """
        初始化X爬取器
        
        Args:
            time_window_hours: 时间窗口（小时）
            bird_config: Bird工具配置，如果为None则使用默认配置
        """
        self.time_window_hours = time_window_hours
        self.logger = get_logger(__name__)
        
        # 初始化bird工具封装器
        try:
            self.bird_wrapper = BirdWrapper(config=bird_config)
            self.logger.info("Bird工具初始化成功")
        except Exception as e:
            self.logger.error(f"Bird工具初始化失败: {str(e)}")
            raise CrawlerError(f"Bird工具初始化失败: {str(e)}")
        
        # 验证bird工具连接
        self.authenticated = False
        try:
            self.authenticated = self.bird_wrapper.test_connection()
            if self.authenticated:
                self.logger.info("X/Twitter连接验证成功")
            else:
                self.logger.warning("X/Twitter连接验证失败，某些功能可能不可用")
        except Exception as e:
            self.logger.warning(f"X/Twitter连接验证异常: {str(e)}")
        
        self.logger.info(f"X爬取器初始化完成，时间窗口: {time_window_hours}小时")
    
    def authenticate(self) -> bool:
        """
        验证认证状态
        
        Returns:
            bool: 认证是否成功
        """
        try:
            self.authenticated = self.bird_wrapper.test_connection()
            if self.authenticated:
                self.logger.info("X认证验证成功")
            else:
                self.logger.warning("X认证验证失败")
            return self.authenticated
        except Exception as e:
            self.logger.error(f"X认证验证异常: {str(e)}")
            self.authenticated = False
            return False
    
    def _extract_list_id_from_url(self, list_url: str) -> Optional[str]:
        """从列表URL提取列表ID"""
        try:
            # 匹配 https://x.com/i/lists/1234567890 格式
            match = re.search(r'/lists/(\d+)', list_url)
            if match:
                return match.group(1)
            
            self.logger.error(f"无法从URL提取列表ID: {list_url}")
            return None
            
        except Exception as e:
            self.logger.error(f"提取列表ID时出错: {str(e)}")
            return None
    
    def _extract_username_from_url(self, timeline_url: str) -> Optional[str]:
        """从时间线URL提取用户名"""
        try:
            # 匹配 https://x.com/username 或 https://twitter.com/username 格式
            match = re.search(r'(?:x\.com|twitter\.com)/([^/]+)', timeline_url)
            if match:
                username = match.group(1)
                # 过滤掉特殊路径
                if username not in ['i', 'home', 'explore', 'notifications', 'messages', 'settings']:
                    return username
            
            self.logger.error(f"无法从URL提取用户名: {timeline_url}")
            return None
            
        except Exception as e:
            self.logger.error(f"提取用户名时出错: {str(e)}")
            return None
    
    def crawl_list(self, list_url: str) -> List[ContentItem]:
        """
        爬取X列表内容
        
        Args:
            list_url: 列表URL
            
        Returns:
            List[ContentItem]: 爬取到的内容项列表
        """
        try:
            list_id = self._extract_list_id_from_url(list_url)
            if not list_id:
                raise CrawlerError(f"无效的列表URL: {list_url}")
            
            self.logger.info(f"开始爬取X列表: {list_id}")
            
            # 确保已认证
            if not self.authenticated and not self.authenticate():
                raise AuthenticationError("X认证失败，请检查认证配置")
            
            # 使用bird工具获取列表推文
            result = self.bird_wrapper.fetch_list_tweets(list_id)
            
            if not result.success:
                error_msg = f"Bird工具获取列表推文失败: {result.error}"
                self.logger.error(error_msg)
                raise CrawlerError(error_msg)
            
            # 解析bird工具输出
            tweets_data = self.bird_wrapper.parse_tweet_data(result.output)
            
            if not tweets_data:
                self.logger.warning("Bird工具返回空数据")
                return []
            
            # 转换为ContentItem并过滤时间窗口
            items = []
            for tweet_data in tweets_data:
                try:
                    item = self.parse_tweet(tweet_data)
                    if self.is_within_time_window(item.publish_time):
                        items.append(item)
                    else:
                        self.logger.debug(f"推文超出时间窗口，跳过: {item.title[:30]}...")
                except Exception as e:
                    self.logger.warning(f"解析推文失败，跳过: {str(e)}")
                    continue
            
            self.logger.info(f"X列表爬取完成，共获得 {len(items)} 条内容")
            return items
            
        except Exception as e:
            self.logger.error(f"爬取X列表失败: {str(e)}")
            raise CrawlerError(f"爬取X列表失败: {str(e)}")
    
    def crawl_timeline(self, timeline_url: Optional[str] = None) -> List[ContentItem]:
        """
        爬取X时间线内容
        
        Args:
            timeline_url: 时间线URL，如果为None则爬取主时间线
            
        Returns:
            List[ContentItem]: 爬取到的内容项列表
        """
        try:
            username = None
            if timeline_url:
                username = self._extract_username_from_url(timeline_url)
                if not username:
                    raise CrawlerError(f"无效的时间线URL: {timeline_url}")
                self.logger.info(f"开始爬取用户时间线: @{username}")
            else:
                self.logger.info("开始爬取主时间线")
            
            # 确保已认证
            if not self.authenticated and not self.authenticate():
                raise AuthenticationError("X认证失败，请检查认证配置")
            
            # 使用bird工具获取时间线推文
            if username:
                result = self.bird_wrapper.fetch_user_timeline(username)
            else:
                # 对于主时间线，使用默认用户或当前认证用户
                # 注意：bird工具可能需要特定的用户名参数
                self.logger.warning("主时间线爬取需要指定用户名，使用默认行为")
                result = self.bird_wrapper.fetch_user_timeline("home")
            
            if not result.success:
                error_msg = f"Bird工具获取时间线推文失败: {result.error}"
                self.logger.error(error_msg)
                raise CrawlerError(error_msg)
            
            # 解析bird工具输出
            tweets_data = self.bird_wrapper.parse_tweet_data(result.output)
            
            if not tweets_data:
                self.logger.warning("Bird工具返回空数据")
                return []
            
            # 转换为ContentItem并过滤时间窗口
            items = []
            for tweet_data in tweets_data:
                try:
                    item = self.parse_tweet(tweet_data)
                    if self.is_within_time_window(item.publish_time):
                        items.append(item)
                    else:
                        self.logger.debug(f"推文超出时间窗口，跳过: {item.title[:30]}...")
                except Exception as e:
                    self.logger.warning(f"解析推文失败，跳过: {str(e)}")
                    continue
            
            self.logger.info(f"X时间线爬取完成，共获得 {len(items)} 条内容")
            return items
            
        except Exception as e:
            self.logger.error(f"爬取X时间线失败: {str(e)}")
            raise CrawlerError(f"爬取X时间线失败: {str(e)}")
    
    def crawl_all_sources(self, sources: List[XSource]) -> List[CrawlResult]:
        """
        爬取所有X信息源
        
        Args:
            sources: X信息源列表
            
        Returns:
            List[CrawlResult]: 爬取结果列表
        """
        results = []
        
        if not sources:
            self.logger.info("没有配置X信息源，跳过X爬取")
            return results
        
        self.logger.info(f"开始爬取 {len(sources)} 个X信息源")
        
        for source in sources:
            try:
                self.logger.info(f"爬取X源: {source.name} ({source.type})")
                
                if source.type == "list":
                    items = self.crawl_list(source.url)
                elif source.type == "timeline":
                    items = self.crawl_timeline(source.url)
                else:
                    raise CrawlerError(f"不支持的X源类型: {source.type}")
                
                result = CrawlResult(
                    source_name=source.name,
                    status="success",
                    item_count=len(items),
                    error_message=None
                )
                
                self.logger.info(f"X源 {source.name} 爬取成功，获得 {len(items)} 条内容")
                
            except Exception as e:
                error_msg = str(e)
                self.logger.error(f"X源 {source.name} 爬取失败: {error_msg}")
                
                result = CrawlResult(
                    source_name=source.name,
                    status="error",
                    item_count=0,
                    error_message=error_msg
                )
            
            results.append(result)
            
            # 在源之间添加延迟，避免过于频繁的请求
            if len(sources) > 1:
                delay = 5.0  # 固定5秒延迟，bird工具内部已有速率限制
                self.logger.debug(f"源间延迟: {delay} 秒")
                time.sleep(delay)
        
        success_count = sum(1 for r in results if r.status == "success")
        self.logger.info(f"X爬取完成，成功: {success_count}/{len(sources)}")
        
        return results
    
    def parse_tweet(self, tweet_data: Dict[str, Any]) -> ContentItem:
        """
        解析推文数据为ContentItem
        
        Args:
            tweet_data: 推文原始数据
            
        Returns:
            ContentItem: 解析后的内容项
        """
        try:
            # 提取基本信息
            tweet_id = tweet_data.get("id", "")
            text = tweet_data.get("text", "").strip()
            created_at_str = tweet_data.get("created_at", "")
            user_data = tweet_data.get("user", {})
            
            # 解析时间
            publish_time = self._parse_twitter_time(created_at_str)
            
            # 构建标题（使用用户名和推文开头）
            username = user_data.get("screen_name", "unknown")
            title = f"@{username}: {text[:50]}..." if len(text) > 50 else f"@{username}: {text}"
            
            # 构建URL
            url = f"https://x.com/{username}/status/{tweet_id}"
            
            # 创建ContentItem
            return create_content_item_from_raw(
                title=title,
                content=text,
                url=url,
                publish_time=publish_time,
                source_name="X/Twitter",
                source_type="x"
            )
            
        except Exception as e:
            self.logger.error(f"解析推文失败: {str(e)}")
            raise CrawlerError(f"解析推文失败: {str(e)}")
    
    def _parse_twitter_time(self, time_str: str) -> datetime:
        """解析Twitter时间格式"""
        try:
            if not time_str:
                self.logger.warning("时间字符串为空，使用当前时间")
                return datetime.now()
            
            # 尝试多种时间格式
            time_formats = [
                "%a %b %d %H:%M:%S %z %Y",  # Bird工具格式: "Wed Feb 04 14:57:51 +0000 2026"
                "%a %b %d %H:%M:%S +0000 %Y",  # Twitter标准格式
                "%Y-%m-%dT%H:%M:%S.%fZ",    # ISO格式
                "%Y-%m-%dT%H:%M:%SZ",       # ISO格式（无毫秒）
                "%Y-%m-%d %H:%M:%S",        # 简单格式
            ]
            
            for fmt in time_formats:
                try:
                    dt = datetime.strptime(time_str, fmt)
                    
                    # 如果解析出的时间有时区信息，需要转换为本地时间
                    if dt.tzinfo is not None:
                        # 转换为UTC时间戳，然后转换为本地时间
                        import time
                        utc_timestamp = dt.timestamp()
                        local_dt = datetime.fromtimestamp(utc_timestamp)
                        self.logger.debug(f"时区转换: UTC {dt} -> 本地 {local_dt}")
                        return local_dt
                    else:
                        # 没有时区信息，直接返回
                        return dt
                        
                except ValueError:
                    continue
            
            # 如果所有格式都失败，尝试使用dateutil
            try:
                from dateutil import parser
                dt = parser.parse(time_str)
                
                # 如果有时区信息，转换为本地时间
                if dt.tzinfo is not None:
                    import time
                    utc_timestamp = dt.timestamp()
                    local_dt = datetime.fromtimestamp(utc_timestamp)
                    self.logger.debug(f"dateutil时区转换: UTC {dt} -> 本地 {local_dt}")
                    return local_dt
                else:
                    return dt
                    
            except Exception:
                pass
            
            self.logger.warning(f"无法解析时间格式: {time_str}，使用当前时间")
            return datetime.now()
            
        except Exception as e:
            self.logger.warning(f"解析Twitter时间失败: {time_str}, 错误: {str(e)}")
            return datetime.now()
    
    def is_within_time_window(self, publish_time: datetime) -> bool:
        """
        检查发布时间是否在时间窗口内
        
        Args:
            publish_time: 发布时间
            
        Returns:
            bool: 是否在时间窗口内
        """
        cutoff_time = datetime.now() - timedelta(hours=self.time_window_hours)
        return publish_time >= cutoff_time
    
    def get_diagnostic_info(self) -> Dict[str, Any]:
        """
        获取诊断信息
        
        Returns:
            Dict[str, Any]: 诊断信息
        """
        diagnostic_info = {
            "time_window_hours": self.time_window_hours,
            "authenticated": self.authenticated,
            "bird_wrapper_info": None
        }
        
        try:
            if self.bird_wrapper:
                diagnostic_info["bird_wrapper_info"] = self.bird_wrapper.get_diagnostic_info()
        except Exception as e:
            diagnostic_info["bird_wrapper_error"] = str(e)
        
        return diagnostic_info
    
    def cleanup(self) -> None:
        """清理资源"""
        try:
            if hasattr(self, 'bird_wrapper') and self.bird_wrapper:
                # BirdWrapper目前没有cleanup方法，但可以在这里添加清理逻辑
                pass
            self.logger.debug("X爬取器资源清理完成")
        except Exception as e:
            self.logger.warning(f"X爬取器清理时出错: {str(e)}")
    
    def __del__(self):
        """析构函数，清理资源"""
        self.cleanup()