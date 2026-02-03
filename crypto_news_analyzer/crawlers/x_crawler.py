"""
X/Twitter爬取器

实现X/Twitter内容爬取功能，包含反封控策略、会话管理和速率限制。
基于需求4.1-4.7的实现。
"""

import requests
import time
import random
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from urllib.parse import urlparse, parse_qs
import re
from dataclasses import dataclass

from ..models import ContentItem, XSource, CrawlResult, create_content_item_from_raw
from ..utils.errors import CrawlerError, AuthenticationError, RateLimitError
from ..utils.logging import get_logger


@dataclass
class XAuthConfig:
    """X认证配置"""
    ct0: str
    auth_token: str
    
    def validate(self) -> None:
        """验证认证配置"""
        if not self.ct0 or not self.ct0.strip():
            raise ValueError("X ct0参数不能为空")
        if not self.auth_token or not self.auth_token.strip():
            raise ValueError("X auth_token参数不能为空")


class XCrawler:
    """
    X/Twitter爬取器
    
    实现X/Twitter内容爬取，包含以下反封控策略：
    1. 速率限制 - 严格控制请求频率
    2. 随机延迟 - 模拟人类行为
    3. User-Agent轮换 - 使用真实浏览器标识
    4. 会话管理 - 维护长期会话
    5. 错误处理 - 智能处理429等错误
    """
    
    # 真实浏览器User-Agent列表
    USER_AGENTS = [
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ]
    
    # 基础请求头
    BASE_HEADERS = {
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache"
    }
    
    # 速率限制配置
    MIN_DELAY = 2.0  # 最小延迟（秒）
    MAX_DELAY = 8.0  # 最大延迟（秒）
    RATE_LIMIT_DELAY = 900  # 遇到429错误时的延迟（15分钟）
    MAX_RETRIES = 3  # 最大重试次数
    
    def __init__(self, ct0: str, auth_token: str, time_window_hours: int):
        """
        初始化X爬取器
        
        Args:
            ct0: X认证参数ct0
            auth_token: X认证令牌
            time_window_hours: 时间窗口（小时）
        """
        self.auth_config = XAuthConfig(ct0=ct0, auth_token=auth_token)
        self.auth_config.validate()
        
        self.time_window_hours = time_window_hours
        self.logger = get_logger(__name__)
        
        # 初始化会话
        self.session = requests.Session()
        self._setup_session()
        
        # 速率限制状态
        self.last_request_time = 0.0
        self.request_count = 0
        self.rate_limited_until = 0.0
        
        # 认证状态
        self.authenticated = False
        
        self.logger.info(f"X爬取器初始化完成，时间窗口: {time_window_hours}小时")
    
    def _setup_session(self) -> None:
        """设置会话配置"""
        # 设置基础请求头
        self.session.headers.update(self.BASE_HEADERS)
        
        # 轮换User-Agent
        self.rotate_user_agents()
        
        # 设置认证信息
        self.session.cookies.set("ct0", self.auth_config.ct0, domain=".x.com")
        self.session.cookies.set("auth_token", self.auth_config.auth_token, domain=".x.com")
        
        # 设置X-Csrf-Token
        self.session.headers["X-Csrf-Token"] = self.auth_config.ct0
        
        # 设置其他必需的头部
        self.session.headers["Authorization"] = "Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"
        
        self.logger.debug("会话配置完成")
    
    def rotate_user_agents(self) -> None:
        """轮换User-Agent"""
        user_agent = random.choice(self.USER_AGENTS)
        self.session.headers["User-Agent"] = user_agent
        self.logger.debug(f"轮换User-Agent: {user_agent[:50]}...")
    
    def add_random_delays(self) -> None:
        """添加随机延迟，模拟人类行为"""
        # 检查是否被速率限制
        current_time = time.time()
        if current_time < self.rate_limited_until:
            wait_time = self.rate_limited_until - current_time
            self.logger.warning(f"速率限制中，等待 {wait_time:.1f} 秒")
            time.sleep(wait_time)
        
        # 计算自上次请求的时间间隔
        time_since_last = current_time - self.last_request_time
        min_interval = self.MIN_DELAY
        
        if time_since_last < min_interval:
            delay = min_interval - time_since_last
            # 添加随机因子
            delay += random.uniform(0, self.MAX_DELAY - self.MIN_DELAY)
            self.logger.debug(f"添加延迟: {delay:.2f} 秒")
            time.sleep(delay)
        
        self.last_request_time = time.time()
        self.request_count += 1
    
    def handle_rate_limit_response(self, response: requests.Response) -> None:
        """处理速率限制响应"""
        if response.status_code == 429:
            # 解析Retry-After头部
            retry_after = response.headers.get("Retry-After")
            if retry_after:
                delay = int(retry_after)
            else:
                delay = self.RATE_LIMIT_DELAY
            
            self.rate_limited_until = time.time() + delay
            self.logger.warning(f"遇到速率限制 (429)，将等待 {delay} 秒")
            raise RateLimitError(f"X API速率限制，需等待 {delay} 秒")
        
        elif response.status_code == 401:
            self.logger.error("认证失败 (401)")
            raise AuthenticationError("X认证失败，请检查ct0和auth_token")
        
        elif response.status_code == 403:
            self.logger.error("访问被禁止 (403)")
            raise AuthenticationError("X访问被禁止，可能账户被限制")
        
        elif response.status_code >= 500:
            self.logger.warning(f"服务器错误 ({response.status_code})")
            raise CrawlerError(f"X服务器错误: {response.status_code}")
    
    def authenticate(self) -> bool:
        """
        验证认证状态
        
        Returns:
            bool: 认证是否成功
        """
        try:
            # 尝试获取用户信息来验证认证
            self.add_random_delays()
            
            # 使用简单的API端点验证认证
            url = "https://x.com/i/api/1.1/account/verify_credentials.json"
            response = self.session.get(url, timeout=30)
            
            if response.status_code == 200:
                self.authenticated = True
                self.logger.info("X认证验证成功")
                return True
            else:
                self.handle_rate_limit_response(response)
                self.authenticated = False
                self.logger.error(f"X认证验证失败: {response.status_code}")
                return False
                
        except Exception as e:
            self.authenticated = False
            self.logger.error(f"X认证验证异常: {str(e)}")
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
                raise AuthenticationError("X认证失败")
            
            items = []
            cursor = None
            max_requests = 5  # 限制请求次数防止过度爬取
            
            for request_num in range(max_requests):
                self.add_random_delays()
                
                # 构建API URL
                url = f"https://x.com/i/api/graphql/ErWsz9cObLel1BF-HjuBlA/ListLatestTweetsTimeline"
                
                # 构建查询参数
                variables = {
                    "listId": list_id,
                    "count": 20
                }
                
                if cursor:
                    variables["cursor"] = cursor
                
                params = {
                    "variables": json.dumps(variables),
                    "features": json.dumps({
                        "rweb_lists_timeline_redesign_enabled": True,
                        "responsive_web_graphql_exclude_directive_enabled": True,
                        "verified_phone_label_enabled": False,
                        "creator_subscriptions_tweet_preview_api_enabled": True,
                        "responsive_web_graphql_timeline_navigation_enabled": True,
                        "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
                        "tweetypie_unmention_optimization_enabled": True,
                        "responsive_web_edit_tweet_api_enabled": True,
                        "graphql_is_translatable_rweb_tweet_is_translatable_enabled": True,
                        "view_counts_everywhere_api_enabled": True,
                        "longform_notetweets_consumption_enabled": True,
                        "responsive_web_twitter_article_tweet_consumption_enabled": False,
                        "tweet_awards_web_tipping_enabled": False,
                        "freedom_of_speech_not_reach_fetch_enabled": True,
                        "standardized_nudges_misinfo": True,
                        "tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled": True,
                        "longform_notetweets_rich_text_read_enabled": True,
                        "longform_notetweets_inline_media_enabled": True,
                        "responsive_web_media_download_video_enabled": False,
                        "responsive_web_enhance_cards_enabled": False
                    })
                }
                
                # 发送请求
                response = self.session.get(url, params=params, timeout=30)
                
                # 处理响应
                if response.status_code != 200:
                    self.handle_rate_limit_response(response)
                    continue
                
                try:
                    data = response.json()
                    tweets = self._parse_timeline_response(data)
                    
                    if not tweets:
                        self.logger.info("没有更多推文，停止爬取")
                        break
                    
                    # 过滤时间窗口内的推文
                    filtered_tweets = self._filter_by_time_window(tweets)
                    items.extend(filtered_tweets)
                    
                    # 获取下一页游标
                    cursor = self._extract_cursor(data)
                    if not cursor:
                        self.logger.info("没有更多页面，停止爬取")
                        break
                    
                    self.logger.debug(f"第 {request_num + 1} 页爬取完成，获得 {len(filtered_tweets)} 条有效推文")
                    
                except json.JSONDecodeError as e:
                    self.logger.error(f"解析JSON响应失败: {str(e)}")
                    break
                except Exception as e:
                    self.logger.error(f"处理响应时出错: {str(e)}")
                    break
            
            self.logger.info(f"X列表爬取完成，共获得 {len(items)} 条内容")
            return items
            
        except Exception as e:
            self.logger.error(f"爬取X列表失败: {str(e)}")
            raise CrawlerError(f"爬取X列表失败: {str(e)}")
    
    def crawl_timeline(self) -> List[ContentItem]:
        """
        爬取X时间线内容
        
        Returns:
            List[ContentItem]: 爬取到的内容项列表
        """
        try:
            self.logger.info("开始爬取X时间线")
            
            # 确保已认证
            if not self.authenticated and not self.authenticate():
                raise AuthenticationError("X认证失败")
            
            items = []
            cursor = None
            max_requests = 3  # 时间线请求次数更少
            
            for request_num in range(max_requests):
                self.add_random_delays()
                
                # 构建API URL
                url = "https://x.com/i/api/graphql/V7H0Ap3_Hh2FyS75OCDO3Q/HomeTimeline"
                
                # 构建查询参数
                variables = {
                    "count": 20,
                    "includePromotedContent": True,
                    "latestControlAvailable": True,
                    "requestContext": "launch"
                }
                
                if cursor:
                    variables["cursor"] = cursor
                
                params = {
                    "variables": json.dumps(variables),
                    "features": json.dumps({
                        "rweb_lists_timeline_redesign_enabled": True,
                        "responsive_web_graphql_exclude_directive_enabled": True,
                        "verified_phone_label_enabled": False,
                        "creator_subscriptions_tweet_preview_api_enabled": True,
                        "responsive_web_graphql_timeline_navigation_enabled": True,
                        "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
                        "tweetypie_unmention_optimization_enabled": True,
                        "responsive_web_edit_tweet_api_enabled": True,
                        "graphql_is_translatable_rweb_tweet_is_translatable_enabled": True,
                        "view_counts_everywhere_api_enabled": True,
                        "longform_notetweets_consumption_enabled": True,
                        "responsive_web_twitter_article_tweet_consumption_enabled": False,
                        "tweet_awards_web_tipping_enabled": False,
                        "freedom_of_speech_not_reach_fetch_enabled": True,
                        "standardized_nudges_misinfo": True,
                        "tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled": True,
                        "longform_notetweets_rich_text_read_enabled": True,
                        "longform_notetweets_inline_media_enabled": True,
                        "responsive_web_media_download_video_enabled": False,
                        "responsive_web_enhance_cards_enabled": False
                    })
                }
                
                # 发送请求
                response = self.session.get(url, params=params, timeout=30)
                
                # 处理响应
                if response.status_code != 200:
                    self.handle_rate_limit_response(response)
                    continue
                
                try:
                    data = response.json()
                    tweets = self._parse_timeline_response(data)
                    
                    if not tweets:
                        self.logger.info("没有更多推文，停止爬取")
                        break
                    
                    # 过滤时间窗口内的推文
                    filtered_tweets = self._filter_by_time_window(tweets)
                    items.extend(filtered_tweets)
                    
                    # 获取下一页游标
                    cursor = self._extract_cursor(data)
                    if not cursor:
                        self.logger.info("没有更多页面，停止爬取")
                        break
                    
                    self.logger.debug(f"第 {request_num + 1} 页爬取完成，获得 {len(filtered_tweets)} 条有效推文")
                    
                except json.JSONDecodeError as e:
                    self.logger.error(f"解析JSON响应失败: {str(e)}")
                    break
                except Exception as e:
                    self.logger.error(f"处理响应时出错: {str(e)}")
                    break
            
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
                    items = self.crawl_timeline()
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
            
            # 在源之间添加额外延迟
            if len(sources) > 1:
                delay = random.uniform(5.0, 15.0)
                self.logger.debug(f"源间延迟: {delay:.2f} 秒")
                time.sleep(delay)
        
        success_count = sum(1 for r in results if r.status == "success")
        self.logger.info(f"X爬取完成，成功: {success_count}/{len(sources)}")
        
        return results
    
    def _parse_timeline_response(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """解析时间线响应数据"""
        tweets = []
        
        try:
            # 导航到推文数据
            instructions = data.get("data", {}).get("home", {}).get("home_timeline_urt", {}).get("instructions", [])
            if not instructions:
                # 尝试列表时间线格式
                instructions = data.get("data", {}).get("list", {}).get("tweets_timeline", {}).get("timeline", {}).get("instructions", [])
            
            for instruction in instructions:
                if instruction.get("type") == "TimelineAddEntries":
                    entries = instruction.get("entries", [])
                    
                    for entry in entries:
                        if entry.get("entryId", "").startswith("tweet-"):
                            tweet_data = self._extract_tweet_from_entry(entry)
                            if tweet_data:
                                tweets.append(tweet_data)
            
            return tweets
            
        except Exception as e:
            self.logger.error(f"解析时间线响应失败: {str(e)}")
            return []
    
    def _extract_tweet_from_entry(self, entry: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """从条目中提取推文数据"""
        try:
            content = entry.get("content", {})
            item_content = content.get("itemContent", {})
            tweet_results = item_content.get("tweet_results", {})
            result = tweet_results.get("result", {})
            
            if not result:
                return None
            
            # 提取推文基本信息
            tweet_data = {
                "id": result.get("rest_id", ""),
                "text": result.get("legacy", {}).get("full_text", ""),
                "created_at": result.get("legacy", {}).get("created_at", ""),
                "user": result.get("core", {}).get("user_results", {}).get("result", {}).get("legacy", {}),
                "entities": result.get("legacy", {}).get("entities", {}),
                "public_metrics": result.get("legacy", {}).get("public_metrics", {})
            }
            
            return tweet_data
            
        except Exception as e:
            self.logger.debug(f"提取推文数据失败: {str(e)}")
            return None
    
    def _extract_cursor(self, data: Dict[str, Any]) -> Optional[str]:
        """提取下一页游标"""
        try:
            instructions = data.get("data", {}).get("home", {}).get("home_timeline_urt", {}).get("instructions", [])
            if not instructions:
                # 尝试列表时间线格式
                instructions = data.get("data", {}).get("list", {}).get("tweets_timeline", {}).get("timeline", {}).get("instructions", [])
            
            for instruction in instructions:
                if instruction.get("type") == "TimelineAddEntries":
                    entries = instruction.get("entries", [])
                    
                    for entry in entries:
                        if entry.get("entryId", "").startswith("cursor-bottom-"):
                            content = entry.get("content", {})
                            operation = content.get("operation", {})
                            cursor = operation.get("cursor", {})
                            return cursor.get("value")
            
            return None
            
        except Exception as e:
            self.logger.debug(f"提取游标失败: {str(e)}")
            return None
    
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
            # Twitter时间格式: "Wed Oct 10 20:19:24 +0000 2018"
            from datetime import datetime
            import locale
            
            # 设置英文locale以正确解析月份名称
            try:
                locale.setlocale(locale.LC_TIME, 'en_US.UTF-8')
            except locale.Error:
                try:
                    locale.setlocale(locale.LC_TIME, 'C')
                except locale.Error:
                    pass  # 使用默认locale
            
            # 解析时间
            dt = datetime.strptime(time_str, "%a %b %d %H:%M:%S %z %Y")
            return dt.replace(tzinfo=None)  # 移除时区信息，使用本地时间
            
        except Exception as e:
            self.logger.warning(f"解析Twitter时间失败: {time_str}, 错误: {str(e)}")
            # 返回当前时间作为fallback
            return datetime.now()
    
    def _filter_by_time_window(self, tweets: List[Dict[str, Any]]) -> List[ContentItem]:
        """根据时间窗口过滤推文"""
        filtered_items = []
        cutoff_time = datetime.now() - timedelta(hours=self.time_window_hours)
        
        for tweet_data in tweets:
            try:
                item = self.parse_tweet(tweet_data)
                
                if item.publish_time >= cutoff_time:
                    filtered_items.append(item)
                else:
                    self.logger.debug(f"推文超出时间窗口，跳过: {item.title[:30]}...")
                    
            except Exception as e:
                self.logger.warning(f"处理推文时出错，跳过: {str(e)}")
                continue
        
        return filtered_items
    
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
    
    def implement_rate_limiting(self) -> None:
        """实现速率限制（已集成到add_random_delays中）"""
        self.add_random_delays()
    
    def __del__(self):
        """析构函数，清理资源"""
        if hasattr(self, 'session'):
            self.session.close()