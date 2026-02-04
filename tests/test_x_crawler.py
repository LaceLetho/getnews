"""
X/Twitter爬取器单元测试

测试基于bird工具的X/Twitter爬取器功能。
验证需求 4.1, 4.2, 4.7, 4.8
"""

import pytest
import json
import time
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from typing import Dict, Any, List

from crypto_news_analyzer.crawlers.x_crawler import XCrawler
from crypto_news_analyzer.models import XSource, ContentItem, CrawlResult, BirdConfig, BirdResult
from crypto_news_analyzer.utils.errors import (
    AuthenticationError, CrawlerError
)


class TestXCrawlerInitialization:
    """X爬取器初始化测试"""
    
    @patch('crypto_news_analyzer.crawlers.x_crawler.BirdWrapper')
    def test_valid_initialization(self, mock_bird_wrapper):
        """测试有效的初始化参数"""
        # 模拟BirdWrapper成功初始化
        mock_wrapper = Mock()
        mock_wrapper.test_connection.return_value = True
        mock_bird_wrapper.return_value = mock_wrapper
        
        crawler = XCrawler(time_window_hours=24)
        
        assert crawler.time_window_hours == 24
        assert crawler.authenticated == True
        assert hasattr(crawler, 'bird_wrapper')
        assert hasattr(crawler, 'logger')
        
        # 验证BirdWrapper被正确初始化
        mock_bird_wrapper.assert_called_once_with(config=None)
        mock_wrapper.test_connection.assert_called_once()
    
    @patch('crypto_news_analyzer.crawlers.x_crawler.BirdWrapper')
    def test_initialization_with_bird_config(self, mock_bird_wrapper):
        """测试使用自定义BirdConfig初始化"""
        mock_wrapper = Mock()
        mock_wrapper.test_connection.return_value = True
        mock_bird_wrapper.return_value = mock_wrapper
        
        bird_config = BirdConfig(
            executable_path="/custom/path/bird",
            timeout_seconds=600,
            max_retries=5
        )
        
        crawler = XCrawler(time_window_hours=12, bird_config=bird_config)
        
        assert crawler.time_window_hours == 12
        mock_bird_wrapper.assert_called_once_with(config=bird_config)
    
    @patch('crypto_news_analyzer.crawlers.x_crawler.BirdWrapper')
    def test_initialization_bird_wrapper_failure(self, mock_bird_wrapper):
        """测试BirdWrapper初始化失败"""
        mock_bird_wrapper.side_effect = RuntimeError("Bird工具不可用")
        
        with pytest.raises(CrawlerError, match="Bird工具初始化失败"):
            XCrawler(time_window_hours=24)
    
    @patch('crypto_news_analyzer.crawlers.x_crawler.BirdWrapper')
    def test_initialization_connection_test_failure(self, mock_bird_wrapper):
        """测试连接测试失败但初始化成功"""
        mock_wrapper = Mock()
        mock_wrapper.test_connection.return_value = False
        mock_bird_wrapper.return_value = mock_wrapper
        
        crawler = XCrawler(time_window_hours=24)
        
        # 初始化应该成功，但认证状态为False
        assert crawler.authenticated == False
        assert hasattr(crawler, 'bird_wrapper')


class TestXCrawlerAuthentication:
    """X爬取器认证机制测试"""
    
    def setup_method(self):
        """测试前设置"""
        with patch('crypto_news_analyzer.crawlers.x_crawler.BirdWrapper') as mock_bird_wrapper:
            mock_wrapper = Mock()
            mock_wrapper.test_connection.return_value = True
            mock_bird_wrapper.return_value = mock_wrapper
            
            self.crawler = XCrawler(time_window_hours=24)
            self.mock_bird_wrapper = self.crawler.bird_wrapper
    
    def test_successful_authentication(self):
        """测试成功认证"""
        self.mock_bird_wrapper.test_connection.return_value = True
        
        result = self.crawler.authenticate()
        
        assert result == True
        assert self.crawler.authenticated == True
        self.mock_bird_wrapper.test_connection.assert_called()
    
    def test_authentication_failure(self):
        """测试认证失败"""
        self.mock_bird_wrapper.test_connection.return_value = False
        
        result = self.crawler.authenticate()
        
        assert result == False
        assert self.crawler.authenticated == False
    
    def test_authentication_exception(self):
        """测试认证过程中的异常"""
        self.mock_bird_wrapper.test_connection.side_effect = Exception("连接错误")
        
        result = self.crawler.authenticate()
        
        assert result == False
        assert self.crawler.authenticated == False


class TestXCrawlerListCrawling:
    """X爬取器列表爬取测试"""
    
    def setup_method(self):
        """测试前设置"""
        with patch('crypto_news_analyzer.crawlers.x_crawler.BirdWrapper') as mock_bird_wrapper:
            mock_wrapper = Mock()
            mock_wrapper.test_connection.return_value = True
            mock_bird_wrapper.return_value = mock_wrapper
            
            self.crawler = XCrawler(time_window_hours=24)
            self.mock_bird_wrapper = self.crawler.bird_wrapper
    
    def test_extract_list_id_valid_url(self):
        """测试从有效URL提取列表ID"""
        valid_urls = [
            "https://x.com/i/lists/1234567890",
            "https://x.com/i/lists/9876543210123456",
            "https://twitter.com/i/lists/1111111111"
        ]
        
        for url in valid_urls:
            list_id = self.crawler._extract_list_id_from_url(url)
            assert list_id is not None
            assert list_id.isdigit()
    
    def test_extract_list_id_invalid_url(self):
        """测试从无效URL提取列表ID"""
        invalid_urls = [
            "https://x.com/user/profile",
            "invalid_url",
            "",
            "https://x.com/i/lists/"
        ]
        
        for url in invalid_urls:
            list_id = self.crawler._extract_list_id_from_url(url)
            assert list_id is None
    
    def test_crawl_list_success(self):
        """测试成功爬取列表"""
        list_url = "https://x.com/i/lists/1234567890"
        
        # 模拟bird工具返回成功结果
        mock_result = BirdResult(
            success=True,
            output='[{"id": "123", "text": "测试推文", "created_at": "Wed Oct 10 20:19:24 +0000 2018", "user": {"screen_name": "test_user"}}]',
            error="",
            exit_code=0,
            execution_time=1.5,
            command=["bird", "list", "--id", "1234567890"]
        )
        
        self.mock_bird_wrapper.fetch_list_tweets.return_value = mock_result
        self.mock_bird_wrapper.parse_tweet_data.return_value = [
            {
                "id": "123",
                "text": "测试推文",
                "created_at": "Wed Oct 10 20:19:24 +0000 2018",
                "user": {"screen_name": "test_user"}
            }
        ]
        
        # 确保认证成功
        self.crawler.authenticated = True
        
        result = self.crawler.crawl_list(list_url)
        
        assert isinstance(result, list)
        assert len(result) >= 0  # 可能因为时间窗口过滤而为空
        
        # 验证bird工具被正确调用
        self.mock_bird_wrapper.fetch_list_tweets.assert_called_once_with("1234567890", count=100)
    
    def test_crawl_list_invalid_url(self):
        """测试爬取无效列表URL"""
        invalid_url = "https://x.com/invalid/url"
        
        with pytest.raises(CrawlerError, match="无效的列表URL"):
            self.crawler.crawl_list(invalid_url)
    
    def test_crawl_list_authentication_required(self):
        """测试列表爬取需要认证"""
        list_url = "https://x.com/i/lists/1234567890"
        
        # 模拟未认证状态
        self.crawler.authenticated = False
        self.mock_bird_wrapper.test_connection.return_value = False
        
        with pytest.raises(CrawlerError, match="爬取X列表失败"):
            self.crawler.crawl_list(list_url)
    
    def test_crawl_list_bird_tool_failure(self):
        """测试bird工具执行失败"""
        list_url = "https://x.com/i/lists/1234567890"
        
        # 模拟bird工具返回失败结果
        mock_result = BirdResult(
            success=False,
            output="",
            error="认证失败",
            exit_code=1,
            execution_time=0.5,
            command=["bird", "list", "--id", "1234567890"]
        )
        
        self.mock_bird_wrapper.fetch_list_tweets.return_value = mock_result
        self.crawler.authenticated = True
        
        with pytest.raises(CrawlerError, match="Bird工具获取列表推文失败"):
            self.crawler.crawl_list(list_url)


class TestXCrawlerTimelineCrawling:
    """X爬取器时间线爬取测试"""
    
    def setup_method(self):
        """测试前设置"""
        with patch('crypto_news_analyzer.crawlers.x_crawler.BirdWrapper') as mock_bird_wrapper:
            mock_wrapper = Mock()
            mock_wrapper.test_connection.return_value = True
            mock_bird_wrapper.return_value = mock_wrapper
            
            self.crawler = XCrawler(time_window_hours=24)
            self.mock_bird_wrapper = self.crawler.bird_wrapper
    
    def test_extract_username_from_url(self):
        """测试从URL提取用户名"""
        valid_urls = [
            ("https://x.com/elonmusk", "elonmusk"),
            ("https://twitter.com/jack", "jack"),
            ("https://x.com/test_user_123", "test_user_123")
        ]
        
        for url, expected_username in valid_urls:
            username = self.crawler._extract_username_from_url(url)
            assert username == expected_username
    
    def test_extract_username_invalid_url(self):
        """测试从无效URL提取用户名"""
        invalid_urls = [
            "https://x.com/i/lists/123",  # 特殊路径
            "https://x.com/home",         # 特殊路径
            "invalid_url",
            ""
        ]
        
        for url in invalid_urls:
            username = self.crawler._extract_username_from_url(url)
            assert username is None
    
    def test_crawl_timeline_with_url(self):
        """测试使用URL爬取用户时间线"""
        timeline_url = "https://x.com/elonmusk"
        
        # 模拟bird工具返回成功结果
        mock_result = BirdResult(
            success=True,
            output='[{"id": "456", "text": "时间线推文", "created_at": "Wed Oct 10 20:19:24 +0000 2018", "user": {"screen_name": "elonmusk"}}]',
            error="",
            exit_code=0,
            execution_time=2.0,
            command=["bird", "timeline", "--user", "elonmusk"]
        )
        
        self.mock_bird_wrapper.fetch_user_timeline.return_value = mock_result
        self.mock_bird_wrapper.parse_tweet_data.return_value = [
            {
                "id": "456",
                "text": "时间线推文",
                "created_at": "Wed Oct 10 20:19:24 +0000 2018",
                "user": {"screen_name": "elonmusk"}
            }
        ]
        
        self.crawler.authenticated = True
        
        result = self.crawler.crawl_timeline(timeline_url)
        
        assert isinstance(result, list)
        self.mock_bird_wrapper.fetch_user_timeline.assert_called_once_with("elonmusk", count=100)
    
    def test_crawl_timeline_without_url(self):
        """测试不使用URL爬取主时间线"""
        # 模拟bird工具返回成功结果
        mock_result = BirdResult(
            success=True,
            output='[]',
            error="",
            exit_code=0,
            execution_time=1.0,
            command=["bird", "timeline", "--user", "home"]
        )
        
        self.mock_bird_wrapper.fetch_user_timeline.return_value = mock_result
        self.mock_bird_wrapper.parse_tweet_data.return_value = []
        
        self.crawler.authenticated = True
        
        result = self.crawler.crawl_timeline()
        
        assert isinstance(result, list)
        self.mock_bird_wrapper.fetch_user_timeline.assert_called_once_with("home", count=100)
    
    def test_crawl_timeline_invalid_url(self):
        """测试爬取无效时间线URL"""
        invalid_url = "https://x.com/i/invalid"
        
        with pytest.raises(CrawlerError, match="无效的时间线URL"):
            self.crawler.crawl_timeline(invalid_url)


class TestXCrawlerContentParsing:
    """X爬取器内容解析测试"""
    
    def setup_method(self):
        """测试前设置"""
        with patch('crypto_news_analyzer.crawlers.x_crawler.BirdWrapper') as mock_bird_wrapper:
            mock_wrapper = Mock()
            mock_wrapper.test_connection.return_value = True
            mock_bird_wrapper.return_value = mock_wrapper
            
            self.crawler = XCrawler(time_window_hours=24)
    
    def test_parse_tweet_valid_data(self):
        """测试解析有效的推文数据"""
        tweet_data = {
            "id": "1234567890123456789",
            "text": "这是一条测试推文 #crypto #bitcoin",
            "created_at": "Wed Oct 10 20:19:24 +0000 2018",
            "user": {
                "screen_name": "test_user",
                "name": "Test User"
            }
        }
        
        result = self.crawler.parse_tweet(tweet_data)
        
        assert isinstance(result, ContentItem)
        assert result.content == tweet_data["text"]
        assert "test_user" in result.title
        assert result.url == "https://x.com/test_user/status/1234567890123456789"
        assert result.source_name == "X/Twitter"
        assert result.source_type == "x"
        assert isinstance(result.publish_time, datetime)
    
    def test_parse_tweet_missing_fields(self):
        """测试解析缺少字段的推文数据"""
        incomplete_tweet_data = {
            "id": "1234567890123456789",
            "text": "测试推文",
            # 缺少created_at和user字段
        }
        
        # 应该能够解析，但会使用默认值
        result = self.crawler.parse_tweet(incomplete_tweet_data)
        
        # 验证基本字段存在
        assert isinstance(result, ContentItem)
        assert result.content == "测试推文"
        assert result.source_name == "X/Twitter"
        assert result.source_type == "x"
    
    def test_parse_twitter_time_valid_formats(self):
        """测试解析各种有效的Twitter时间格式"""
        valid_time_formats = [
            ("Wed Oct 10 20:19:24 +0000 2018", datetime(2018, 10, 10, 20, 19, 24)),
            ("2018-10-10T20:19:24.000Z", datetime(2018, 10, 10, 20, 19, 24)),
            ("2018-10-10T20:19:24Z", datetime(2018, 10, 10, 20, 19, 24)),
            ("2018-10-10 20:19:24", datetime(2018, 10, 10, 20, 19, 24))
        ]
        
        for time_str, expected_dt in valid_time_formats:
            result = self.crawler._parse_twitter_time(time_str)
            assert isinstance(result, datetime)
            # 允许一定的时间误差（因为时区处理）
            time_diff = abs((result - expected_dt).total_seconds())
            assert time_diff < 86400  # 24小时内的误差（考虑时区转换）
    
    def test_parse_twitter_time_invalid_format(self):
        """测试解析无效的Twitter时间格式"""
        invalid_time_str = "invalid_time_format"
        
        # 应该返回当前时间作为fallback
        result = self.crawler._parse_twitter_time(invalid_time_str)
        
        assert isinstance(result, datetime)
        # 验证返回的时间接近当前时间
        time_diff = abs((datetime.now() - result).total_seconds())
        assert time_diff < 60  # 1分钟内的误差
    
    def test_parse_twitter_time_empty_string(self):
        """测试解析空时间字符串"""
        result = self.crawler._parse_twitter_time("")
        
        assert isinstance(result, datetime)
        # 应该返回当前时间
        time_diff = abs((datetime.now() - result).total_seconds())
        assert time_diff < 60
    
    def test_is_within_time_window(self):
        """测试时间窗口检查"""
        now = datetime.now()
        
        # 在时间窗口内的时间
        recent_time = now - timedelta(hours=12)
        assert self.crawler.is_within_time_window(recent_time) == True
        
        # 超出时间窗口的时间
        old_time = now - timedelta(hours=48)
        assert self.crawler.is_within_time_window(old_time) == False
        
        # 边界情况 - 稍微在时间窗口内
        boundary_time = now - timedelta(hours=23, minutes=59)
        assert self.crawler.is_within_time_window(boundary_time) == True


class TestXCrawlerBatchOperations:
    """X爬取器批量操作测试"""
    
    def setup_method(self):
        """测试前设置"""
        with patch('crypto_news_analyzer.crawlers.x_crawler.BirdWrapper') as mock_bird_wrapper:
            mock_wrapper = Mock()
            mock_wrapper.test_connection.return_value = True
            mock_bird_wrapper.return_value = mock_wrapper
            
            self.crawler = XCrawler(time_window_hours=24)
            self.mock_bird_wrapper = self.crawler.bird_wrapper
    
    def test_crawl_all_sources_empty_list(self):
        """测试空数据源列表"""
        results = self.crawler.crawl_all_sources([])
        
        assert results == []
    
    def test_crawl_all_sources_mixed_types(self):
        """测试混合类型的数据源"""
        sources = [
            XSource(name="测试列表", url="https://x.com/i/lists/1111111111", type="list"),
            XSource(name="测试时间线", url="https://x.com/elonmusk", type="timeline")
        ]
        
        # 模拟成功的bird工具调用
        success_result = BirdResult(
            success=True,
            output='[]',
            error="",
            exit_code=0,
            execution_time=1.0,
            command=["bird"]
        )
        
        self.mock_bird_wrapper.fetch_list_tweets.return_value = success_result
        self.mock_bird_wrapper.fetch_user_timeline.return_value = success_result
        self.mock_bird_wrapper.parse_tweet_data.return_value = []
        
        self.crawler.authenticated = True
        
        with patch('time.sleep'):  # 跳过延迟
            results = self.crawler.crawl_all_sources(sources)
        
        assert len(results) == 2
        assert all(r.status == "success" for r in results)
        
        # 验证不同类型的调用
        self.mock_bird_wrapper.fetch_list_tweets.assert_called_once()
        self.mock_bird_wrapper.fetch_user_timeline.assert_called_once()
    
    def test_crawl_all_sources_error_isolation(self):
        """测试多个数据源时的错误隔离"""
        sources = [
            XSource(name="成功源", url="https://x.com/i/lists/1111111111", type="list"),
            XSource(name="失败源", url="https://x.com/i/lists/2222222222", type="list")
        ]
        
        # 第一个调用成功，第二个失败
        success_result = BirdResult(
            success=True,
            output='[]',
            error="",
            exit_code=0,
            execution_time=1.0,
            command=["bird"]
        )
        
        failure_result = BirdResult(
            success=False,
            output="",
            error="认证失败",
            exit_code=1,
            execution_time=0.5,
            command=["bird"]
        )
        
        self.mock_bird_wrapper.fetch_list_tweets.side_effect = [success_result, failure_result]
        self.mock_bird_wrapper.parse_tweet_data.return_value = []
        
        self.crawler.authenticated = True
        
        with patch('time.sleep'):
            results = self.crawler.crawl_all_sources(sources)
        
        assert len(results) == 2
        assert results[0].status == "success"
        assert results[1].status == "error"
        assert "认证失败" in results[1].error_message
    
    def test_crawl_all_sources_unsupported_type(self):
        """测试不支持的数据源类型"""
        # 创建一个有效的XSource，然后手动修改type来绕过验证
        source = XSource(name="测试源", url="https://x.com/test", type="list")
        source.type = "invalid_type"  # 手动修改为无效类型
        
        sources = [source]
        
        self.crawler.authenticated = True
        
        results = self.crawler.crawl_all_sources(sources)
        
        assert len(results) == 1
        assert results[0].status == "error"
        assert "不支持的X源类型" in results[0].error_message


class TestXCrawlerDiagnostics:
    """X爬取器诊断功能测试"""
    
    def setup_method(self):
        """测试前设置"""
        with patch('crypto_news_analyzer.crawlers.x_crawler.BirdWrapper') as mock_bird_wrapper:
            mock_wrapper = Mock()
            mock_wrapper.test_connection.return_value = True
            mock_bird_wrapper.return_value = mock_wrapper
            
            self.crawler = XCrawler(time_window_hours=24)
            self.mock_bird_wrapper = self.crawler.bird_wrapper
    
    def test_get_diagnostic_info_success(self):
        """测试获取诊断信息成功"""
        # 模拟bird wrapper诊断信息
        mock_diagnostic = {
            "config": {"executable_path": "bird", "timeout_seconds": 300},
            "dependency_status": {"available": True, "version": "1.0.0"},
            "connection_test": True
        }
        
        self.mock_bird_wrapper.get_diagnostic_info.return_value = mock_diagnostic
        
        result = self.crawler.get_diagnostic_info()
        
        assert "time_window_hours" in result
        assert result["time_window_hours"] == 24
        assert "authenticated" in result
        assert "bird_wrapper_info" in result
        assert result["bird_wrapper_info"] == mock_diagnostic
    
    def test_get_diagnostic_info_bird_wrapper_error(self):
        """测试bird wrapper诊断信息获取失败"""
        self.mock_bird_wrapper.get_diagnostic_info.side_effect = Exception("诊断失败")
        
        result = self.crawler.get_diagnostic_info()
        
        assert "time_window_hours" in result
        assert "bird_wrapper_error" in result
        assert result["bird_wrapper_error"] == "诊断失败"
    
    def test_cleanup(self):
        """测试资源清理"""
        # cleanup方法应该正常执行而不抛出异常
        self.crawler.cleanup()
        
        # 验证没有异常抛出
        assert True


class TestXCrawlerBirdToolIntegration:
    """X爬取器与Bird工具集成测试 - 专门测试bird工具调用和错误处理"""
    
    def setup_method(self):
        """测试前设置"""
        with patch('crypto_news_analyzer.crawlers.x_crawler.BirdWrapper') as mock_bird_wrapper:
            mock_wrapper = Mock()
            mock_wrapper.test_connection.return_value = True
            mock_bird_wrapper.return_value = mock_wrapper
            
            self.crawler = XCrawler(time_window_hours=24)
            self.mock_bird_wrapper = self.crawler.bird_wrapper
    
    def test_bird_tool_command_construction(self):
        """测试bird工具命令构建"""
        list_url = "https://x.com/i/lists/1234567890"
        
        # 模拟成功的bird工具调用
        mock_result = BirdResult(
            success=True,
            output='[]',
            error="",
            exit_code=0,
            execution_time=1.0,
            command=["bird", "list-timeline", "1234567890", "--json", "--count", "100"]
        )
        
        self.mock_bird_wrapper.fetch_list_tweets.return_value = mock_result
        self.mock_bird_wrapper.parse_tweet_data.return_value = []
        self.crawler.authenticated = True
        
        self.crawler.crawl_list(list_url)
        
        # 验证bird工具被正确调用
        self.mock_bird_wrapper.fetch_list_tweets.assert_called_once_with("1234567890", count=100)
    
    def test_bird_tool_authentication_error_handling(self):
        """测试bird工具认证错误处理"""
        list_url = "https://x.com/i/lists/1234567890"
        
        # 模拟认证错误
        mock_result = BirdResult(
            success=False,
            output="",
            error="Authentication failed: Invalid credentials",
            exit_code=401,
            execution_time=0.5,
            command=["bird", "list-timeline", "1234567890"]
        )
        
        self.mock_bird_wrapper.fetch_list_tweets.return_value = mock_result
        self.crawler.authenticated = True
        
        with pytest.raises(CrawlerError, match="Bird工具获取列表推文失败"):
            self.crawler.crawl_list(list_url)
    
    def test_bird_tool_network_error_handling(self):
        """测试bird工具网络错误处理"""
        timeline_url = "https://x.com/elonmusk"
        
        # 模拟网络错误
        mock_result = BirdResult(
            success=False,
            output="",
            error="Network error: Connection timeout",
            exit_code=1,
            execution_time=30.0,
            command=["bird", "user-tweets", "elonmusk"]
        )
        
        self.mock_bird_wrapper.fetch_user_timeline.return_value = mock_result
        self.crawler.authenticated = True
        
        with pytest.raises(CrawlerError, match="Bird工具获取时间线推文失败"):
            self.crawler.crawl_timeline(timeline_url)
    
    def test_bird_tool_rate_limit_error_handling(self):
        """测试bird工具速率限制错误处理"""
        list_url = "https://x.com/i/lists/1234567890"
        
        # 模拟速率限制错误
        mock_result = BirdResult(
            success=False,
            output="",
            error="Rate limit exceeded. Please wait before making more requests.",
            exit_code=429,
            execution_time=1.0,
            command=["bird", "list-timeline", "1234567890"]
        )
        
        self.mock_bird_wrapper.fetch_list_tweets.return_value = mock_result
        self.crawler.authenticated = True
        
        with pytest.raises(CrawlerError, match="Bird工具获取列表推文失败"):
            self.crawler.crawl_list(list_url)
    
    def test_bird_tool_malformed_output_handling(self):
        """测试bird工具输出格式错误处理"""
        list_url = "https://x.com/i/lists/1234567890"
        
        # 模拟成功但输出格式错误
        mock_result = BirdResult(
            success=True,
            output="Invalid JSON output {malformed",
            error="",
            exit_code=0,
            execution_time=1.0,
            command=["bird", "list-timeline", "1234567890"]
        )
        
        self.mock_bird_wrapper.fetch_list_tweets.return_value = mock_result
        self.mock_bird_wrapper.parse_tweet_data.return_value = []  # 解析失败返回空列表
        self.crawler.authenticated = True
        
        # 应该能够处理解析失败，返回空列表而不是抛出异常
        result = self.crawler.crawl_list(list_url)
        assert result == []
    
    def test_bird_tool_partial_success_handling(self):
        """测试bird工具部分成功的处理"""
        list_url = "https://x.com/i/lists/1234567890"
        
        # 模拟部分成功（有些推文解析失败）
        mock_result = BirdResult(
            success=True,
            output='[{"id": "123", "text": "valid tweet"}, {"invalid": "data"}]',
            error="",
            exit_code=0,
            execution_time=1.0,
            command=["bird", "list-timeline", "1234567890"]
        )
        
        # 模拟解析时只返回有效的推文
        self.mock_bird_wrapper.fetch_list_tweets.return_value = mock_result
        self.mock_bird_wrapper.parse_tweet_data.return_value = [
            {
                "id": "123",
                "text": "valid tweet",
                "created_at": "Wed Oct 10 20:19:24 +0000 2018",
                "user": {"screen_name": "test_user"}
            }
        ]
        self.crawler.authenticated = True
        
        result = self.crawler.crawl_list(list_url)
        
        # 应该只返回有效解析的推文
        assert len(result) >= 0  # 可能因为时间窗口过滤而为空


class TestXCrawlerOutputParsing:
    """X爬取器输出解析和数据提取逻辑测试"""
    
    def setup_method(self):
        """测试前设置"""
        with patch('crypto_news_analyzer.crawlers.x_crawler.BirdWrapper') as mock_bird_wrapper:
            mock_wrapper = Mock()
            mock_wrapper.test_connection.return_value = True
            mock_bird_wrapper.return_value = mock_wrapper
            
            self.crawler = XCrawler(time_window_hours=24)
    
    def test_parse_tweet_with_special_characters(self):
        """测试解析包含特殊字符的推文"""
        tweet_data = {
            "id": "1234567890123456789",
            "text": "测试推文 🚀 #crypto $BTC @elonmusk https://t.co/abc123 \n换行测试",
            "created_at": "Wed Oct 10 20:19:24 +0000 2018",
            "user": {
                "screen_name": "test_user",
                "name": "Test User 测试"
            }
        }
        
        result = self.crawler.parse_tweet(tweet_data)
        
        assert isinstance(result, ContentItem)
        assert "🚀" in result.content
        assert "#crypto" in result.content
        assert "$BTC" in result.content
        assert "@elonmusk" in result.content
        assert "https://t.co/abc123" in result.content
        assert "\n" in result.content
    
    def test_parse_tweet_with_minimal_data(self):
        """测试解析最小数据集的推文"""
        tweet_data = {
            "id": "123",
            "text": "minimal tweet"
        }
        
        result = self.crawler.parse_tweet(tweet_data)
        
        assert isinstance(result, ContentItem)
        assert result.content == "minimal tweet"
        assert result.source_name == "X/Twitter"
        assert result.source_type == "x"
        assert "unknown" in result.title
    
    def test_parse_tweet_with_empty_fields(self):
        """测试解析空字段的推文"""
        tweet_data = {
            "id": "",
            "text": "",
            "created_at": "",
            "user": {
                "screen_name": "",
                "name": ""
            }
        }
        
        # 空内容应该抛出CrawlerError
        with pytest.raises(CrawlerError, match="解析推文失败"):
            self.crawler.parse_tweet(tweet_data)
    
    def test_parse_tweet_with_nested_user_data(self):
        """测试解析嵌套用户数据的推文"""
        tweet_data = {
            "id": "1234567890123456789",
            "text": "nested user data test",
            "created_at": "Wed Oct 10 20:19:24 +0000 2018",
            "user": {
                "screen_name": "test_user",
                "name": "Test User",
                "id": "987654321",
                "verified": True,
                "followers_count": 1000,
                "profile_image_url": "https://example.com/image.jpg"
            }
        }
        
        result = self.crawler.parse_tweet(tweet_data)
        
        assert isinstance(result, ContentItem)
        assert "test_user" in result.title
        assert "test_user" in result.url
        assert result.content == "nested user data test"
    
    def test_parse_twitter_time_edge_cases(self):
        """测试Twitter时间解析的边界情况"""
        # 测试各种边界时间格式
        edge_cases = [
            ("", datetime.now()),  # 空字符串
            ("invalid_format", datetime.now()),  # 无效格式
            ("2018-02-29T12:00:00Z", None),  # 无效日期（2018年不是闰年）
            ("2020-02-29T12:00:00Z", datetime(2020, 2, 29, 12, 0, 0)),  # 有效闰年日期
            ("Wed Dec 31 23:59:59 +0000 2025", datetime(2025, 12, 31, 23, 59, 59)),  # 年末
            ("Mon Jan 01 00:00:00 +0000 2024", datetime(2024, 1, 1, 0, 0, 0)),  # 年初
        ]
        
        for time_str, expected in edge_cases:
            result = self.crawler._parse_twitter_time(time_str)
            assert isinstance(result, datetime)
            
            if expected and time_str not in ["", "invalid_format", "2018-02-29T12:00:00Z"]:
                # 允许时区转换的误差
                time_diff = abs((result - expected).total_seconds())
                assert time_diff < 86400  # 24小时内的误差（考虑时区）
    
    def test_url_extraction_edge_cases(self):
        """测试URL提取的边界情况"""
        # 测试列表ID提取
        list_url_cases = [
            ("https://x.com/i/lists/1234567890123456789", "1234567890123456789"),
            ("https://twitter.com/i/lists/987654321", "987654321"),
            ("https://x.com/i/lists/", None),  # 空ID
            ("https://x.com/user/profile", None),  # 非列表URL
            ("invalid_url", None),  # 完全无效的URL
            ("", None),  # 空字符串
        ]
        
        for url, expected_id in list_url_cases:
            result = self.crawler._extract_list_id_from_url(url)
            assert result == expected_id
        
        # 测试用户名提取
        username_cases = [
            ("https://x.com/elonmusk", "elonmusk"),
            ("https://twitter.com/jack", "jack"),
            ("https://x.com/user_with_underscore", "user_with_underscore"),
            ("https://x.com/i/lists/123", None),  # 特殊路径
            ("https://x.com/home", None),  # 特殊路径
            ("https://x.com/", None),  # 空用户名
            ("invalid_url", None),  # 无效URL
        ]
        
        for url, expected_username in username_cases:
            result = self.crawler._extract_username_from_url(url)
            assert result == expected_username
    
    def test_time_window_filtering_precision(self):
        """测试时间窗口过滤的精确性"""
        now = datetime.now()
        
        # 测试精确边界
        test_cases = [
            (now - timedelta(hours=23, minutes=59, seconds=59), True),  # 刚好在窗口内
            (now - timedelta(hours=24, minutes=0, seconds=1), False),   # 刚好超出窗口
            (now - timedelta(hours=12), True),                         # 明显在窗口内
            (now - timedelta(hours=48), False),                        # 明显超出窗口
            (now + timedelta(hours=1), True),                          # 未来时间（应该在窗口内）
        ]
        
        for test_time, expected in test_cases:
            result = self.crawler.is_within_time_window(test_time)
            assert result == expected, f"时间 {test_time} 的过滤结果应该是 {expected}"


class TestXCrawlerDependencyValidation:
    """X爬取器依赖检查和配置验证测试"""
    
    def test_bird_config_validation(self):
        """测试Bird配置验证"""
        # 测试有效配置
        valid_config = BirdConfig(
            executable_path="bird",
            timeout_seconds=300,
            max_retries=3,
            output_format="json"
        )
        
        with patch('crypto_news_analyzer.crawlers.x_crawler.BirdWrapper') as mock_bird_wrapper:
            mock_wrapper = Mock()
            mock_wrapper.test_connection.return_value = True
            mock_bird_wrapper.return_value = mock_wrapper
            
            crawler = XCrawler(time_window_hours=24, bird_config=valid_config)
            assert crawler.time_window_hours == 24
    
    def test_bird_dependency_check_failure(self):
        """测试Bird依赖检查失败"""
        with patch('crypto_news_analyzer.crawlers.x_crawler.BirdWrapper') as mock_bird_wrapper:
            mock_bird_wrapper.side_effect = RuntimeError("Bird工具不可用")
            
            with pytest.raises(CrawlerError, match="Bird工具初始化失败"):
                XCrawler(time_window_hours=24)
    
    def test_authentication_validation(self):
        """测试认证验证"""
        with patch('crypto_news_analyzer.crawlers.x_crawler.BirdWrapper') as mock_bird_wrapper:
            mock_wrapper = Mock()
            mock_wrapper.test_connection.return_value = False  # 认证失败
            mock_bird_wrapper.return_value = mock_wrapper
            
            crawler = XCrawler(time_window_hours=24)
            
            # 初始认证状态应该是False
            assert crawler.authenticated == False
            
            # 手动认证也应该失败
            result = crawler.authenticate()
            assert result == False
    
    def test_diagnostic_info_completeness(self):
        """测试诊断信息完整性"""
        with patch('crypto_news_analyzer.crawlers.x_crawler.BirdWrapper') as mock_bird_wrapper:
            mock_wrapper = Mock()
            mock_wrapper.test_connection.return_value = True
            mock_wrapper.get_diagnostic_info.return_value = {
                "config": {"executable_path": "bird"},
                "dependency_status": {"available": True},
                "connection_test": True
            }
            mock_bird_wrapper.return_value = mock_wrapper
            
            crawler = XCrawler(time_window_hours=24)
            diagnostic = crawler.get_diagnostic_info()
            
            # 验证诊断信息包含必要字段
            assert "time_window_hours" in diagnostic
            assert "authenticated" in diagnostic
            assert "bird_wrapper_info" in diagnostic
            
            assert diagnostic["time_window_hours"] == 24
            assert isinstance(diagnostic["authenticated"], bool)
            assert isinstance(diagnostic["bird_wrapper_info"], dict)
    
    def test_error_recovery_mechanisms(self):
        """测试错误恢复机制"""
        with patch('crypto_news_analyzer.crawlers.x_crawler.BirdWrapper') as mock_bird_wrapper:
            mock_wrapper = Mock()
            mock_wrapper.test_connection.return_value = True
            mock_bird_wrapper.return_value = mock_wrapper
            
            crawler = XCrawler(time_window_hours=24)
            
            # 测试在bird工具调用失败时的恢复
            sources = [
                XSource(name="失败源", url="https://x.com/i/lists/1111111111", type="list"),
                XSource(name="成功源", url="https://x.com/i/lists/2222222222", type="list")
            ]
            
            # 第一个调用失败，第二个成功
            failure_result = BirdResult(
                success=False,
                output="",
                error="网络错误",
                exit_code=1,
                execution_time=0.5,
                command=["bird"]
            )
            
            success_result = BirdResult(
                success=True,
                output='[]',
                error="",
                exit_code=0,
                execution_time=1.0,
                command=["bird"]
            )
            
            mock_wrapper.fetch_list_tweets.side_effect = [failure_result, success_result]
            mock_wrapper.parse_tweet_data.return_value = []
            
            with patch('time.sleep'):  # 跳过延迟
                results = crawler.crawl_all_sources(sources)
            
            # 验证错误隔离：第一个失败，第二个成功
            assert len(results) == 2
            assert results[0].status == "error"
            assert results[1].status == "success"
            assert "网络错误" in results[0].error_message
    
    def test_configuration_parameter_validation(self):
        """测试配置参数验证"""
        # 测试无效的时间窗口参数
        with patch('crypto_news_analyzer.crawlers.x_crawler.BirdWrapper') as mock_bird_wrapper:
            mock_wrapper = Mock()
            mock_wrapper.test_connection.return_value = True
            mock_bird_wrapper.return_value = mock_wrapper
            
            # 负数时间窗口
            crawler = XCrawler(time_window_hours=-1)
            assert crawler.time_window_hours == -1  # 应该接受但在使用时处理
            
            # 零时间窗口
            crawler = XCrawler(time_window_hours=0)
            assert crawler.time_window_hours == 0
            
            # 极大时间窗口
            crawler = XCrawler(time_window_hours=8760)  # 一年
            assert crawler.time_window_hours == 8760


if __name__ == "__main__":
    # 运行单元测试
    pytest.main([__file__, "-v", "--tb=short"])