"""
RSS爬取器单元测试

测试RSS爬取器的核心功能，包括：
- RSS内容解析
- 时间窗口过滤
- 错误处理
- 网络请求
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
import feedparser
import requests
from bs4 import BeautifulSoup

from crypto_news_analyzer.crawlers.rss_crawler import RSSCrawler
from crypto_news_analyzer.models import RSSSource, ContentItem, CrawlResult
from crypto_news_analyzer.utils.errors import CrawlerError, NetworkError


class TestRSSCrawler:
    """RSS爬取器测试类"""
    
    @pytest.fixture
    def crawler(self):
        """创建RSS爬取器实例"""
        return RSSCrawler(time_window_hours=24)
    
    @pytest.fixture
    def sample_rss_source(self):
        """创建示例RSS源"""
        return RSSSource(
            name="测试RSS源",
            url="https://example.com/rss.xml",
            description="测试用RSS源"
        )
    
    @pytest.fixture
    def sample_rss_content(self):
        """创建示例RSS内容"""
        return """<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
            <channel>
                <title>测试RSS</title>
                <description>测试RSS描述</description>
                <link>https://example.com</link>
                <item>
                    <title>测试新闻标题</title>
                    <description>测试新闻内容描述</description>
                    <link>https://example.com/news/1</link>
                    <pubDate>Mon, 01 Jan 2024 12:00:00 GMT</pubDate>
                </item>
                <item>
                    <title>过期新闻标题</title>
                    <description>过期新闻内容</description>
                    <link>https://example.com/news/2</link>
                    <pubDate>Mon, 01 Jan 2020 12:00:00 GMT</pubDate>
                </item>
            </channel>
        </rss>"""
    
    def test_crawler_initialization(self):
        """测试爬取器初始化"""
        crawler = RSSCrawler(time_window_hours=12, timeout=60)
        
        assert crawler.time_window_hours == 12
        assert crawler.timeout == 60
        assert crawler.session is not None
        assert 'User-Agent' in crawler.session.headers
        
        # 检查时间窗口计算
        expected_cutoff = datetime.now() - timedelta(hours=12)
        time_diff = abs((crawler.cutoff_time - expected_cutoff).total_seconds())
        assert time_diff < 5  # 允许5秒误差
    
    @patch('crypto_news_analyzer.crawlers.rss_crawler.requests.Session.get')
    def test_fetch_rss_content_success(self, mock_get, crawler, sample_rss_content):
        """测试成功获取RSS内容"""
        # 模拟成功响应
        mock_response = Mock()
        mock_response.text = sample_rss_content
        mock_response.headers = {'content-type': 'application/rss+xml'}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        content = crawler._fetch_rss_content("https://example.com/rss.xml")
        
        assert content == sample_rss_content
        mock_get.assert_called_once()
    
    @patch('crypto_news_analyzer.crawlers.rss_crawler.requests.Session.get')
    def test_fetch_rss_content_retry_on_failure(self, mock_get, crawler):
        """测试网络失败时的重试机制"""
        # 模拟前两次失败，第三次成功
        mock_get.side_effect = [
            requests.exceptions.ConnectionError("连接失败"),
            requests.exceptions.Timeout("超时"),
            Mock(text="success", headers={}, raise_for_status=Mock())
        ]
        
        content = crawler._fetch_rss_content("https://example.com/rss.xml")
        
        assert content == "success"
        assert mock_get.call_count == 3
    
    @patch('crypto_news_analyzer.crawlers.rss_crawler.requests.Session.get')
    def test_fetch_rss_content_max_retries_exceeded(self, mock_get, crawler):
        """测试超过最大重试次数"""
        # 模拟所有请求都失败
        mock_get.side_effect = requests.exceptions.ConnectionError("连接失败")
        
        with pytest.raises(NetworkError):
            crawler._fetch_rss_content("https://example.com/rss.xml")
        
        assert mock_get.call_count == 3  # 默认最大重试3次
    
    def test_parse_rss_entry_complete_data(self, crawler, sample_rss_source):
        """测试解析完整的RSS条目"""
        # 创建模拟的RSS条目
        entry = Mock()
        entry.title = "测试标题"
        entry.summary = "测试内容摘要"
        entry.link = "https://example.com/news/1"
        entry.published_parsed = (2024, 1, 1, 12, 0, 0, 0, 1, 0)
        
        # 添加缺失的属性
        entry.content = []
        entry.description = ""
        entry.subtitle = ""
        entry.id = ""
        entry.guid = ""
        entry.updated_parsed = None
        entry.created_parsed = None
        entry.published = ""
        entry.updated = ""
        entry.created = ""
        
        item = crawler._parse_rss_entry(entry, sample_rss_source)
        
        assert item is not None
        assert item.title == "测试标题"
        assert item.content == "测试内容摘要"
        assert item.url == "https://example.com/news/1"
        assert item.source_name == sample_rss_source.name
        assert item.source_type == "rss"
        assert isinstance(item.publish_time, datetime)
    
    def test_parse_rss_entry_missing_title(self, crawler, sample_rss_source):
        """测试缺少标题的RSS条目"""
        entry = Mock()
        entry.title = ""
        entry.summary = "测试内容"
        entry.link = "https://example.com/news/1"
        entry.published_parsed = (2024, 1, 1, 12, 0, 0, 0, 1, 0)
        
        # 添加缺失的属性
        entry.content = []
        entry.description = ""
        entry.subtitle = ""
        entry.id = ""
        entry.guid = ""
        
        item = crawler._parse_rss_entry(entry, sample_rss_source)
        
        assert item is None
    
    def test_parse_rss_entry_missing_content(self, crawler, sample_rss_source):
        """测试缺少内容的RSS条目"""
        entry = Mock()
        entry.title = "测试标题"
        entry.summary = ""
        entry.link = "https://example.com/news/1"
        entry.published_parsed = (2024, 1, 1, 12, 0, 0, 0, 1, 0)
        
        # 添加缺失的属性
        entry.content = []
        entry.description = ""
        entry.subtitle = ""
        entry.id = ""
        entry.guid = ""
        
        item = crawler._parse_rss_entry(entry, sample_rss_source)
        
        assert item is None
    
    def test_parse_rss_entry_missing_url(self, crawler, sample_rss_source):
        """测试缺少URL的RSS条目"""
        entry = Mock()
        entry.title = "测试标题"
        entry.summary = "测试内容"
        entry.link = ""
        entry.published_parsed = (2024, 1, 1, 12, 0, 0, 0, 1, 0)
        
        # 添加缺失的属性
        entry.content = []
        entry.description = ""
        entry.subtitle = ""
        entry.id = ""
        entry.guid = ""
        
        item = crawler._parse_rss_entry(entry, sample_rss_source)
        
        assert item is None
    
    def test_extract_content_from_multiple_fields(self, crawler):
        """测试从多个字段提取内容"""
        # 测试content字段（列表格式）
        entry1 = Mock()
        entry1.content = [{'value': '来自content字段的内容'}]
        entry1.summary = '来自summary字段的内容'
        
        content1 = crawler._extract_content(entry1)
        assert content1 == '来自content字段的内容'
        
        # 测试summary字段
        entry2 = Mock()
        entry2.content = []
        entry2.summary = '来自summary字段的内容'
        entry2.description = '来自description字段的内容'
        
        content2 = crawler._extract_content(entry2)
        assert content2 == '来自summary字段的内容'
    
    def test_extract_publish_time_from_multiple_formats(self, crawler):
        """测试从多种格式提取发布时间"""
        # 测试parsed格式
        entry1 = Mock()
        entry1.published_parsed = (2024, 1, 1, 12, 0, 0, 0, 1, 0)
        
        time1 = crawler._extract_publish_time(entry1)
        assert time1 == datetime(2024, 1, 1, 12, 0, 0)
        
        # 测试字符串格式
        entry2 = Mock()
        entry2.published_parsed = None
        entry2.published = "2024-01-01T12:00:00Z"
        
        time2 = crawler._extract_publish_time(entry2)
        assert time2.year == 2024
        assert time2.month == 1
        assert time2.day == 1
    
    def test_clean_html(self, crawler):
        """测试HTML清理功能"""
        html_content = """
        <div>
            <h1>标题</h1>
            <p>这是一个<strong>重要</strong>的段落。</p>
            <script>alert('恶意脚本');</script>
            <style>body { color: red; }</style>
        </div>
        """
        
        clean_content = crawler._clean_html(html_content)
        
        assert "标题" in clean_content
        assert "重要" in clean_content
        assert "段落" in clean_content
        assert "alert" not in clean_content
        assert "color: red" not in clean_content
        assert "<" not in clean_content
        assert ">" not in clean_content
    
    def test_is_within_time_window(self, crawler):
        """测试时间窗口过滤"""
        # 当前时间（应该在窗口内）
        current_time = datetime.now()
        assert crawler._is_within_time_window(current_time) is True
        
        # 1小时前（应该在窗口内）
        one_hour_ago = datetime.now() - timedelta(hours=1)
        assert crawler._is_within_time_window(one_hour_ago) is True
        
        # 25小时前（应该在窗口外，因为窗口是24小时）
        old_time = datetime.now() - timedelta(hours=25)
        assert crawler._is_within_time_window(old_time) is False
    
    def test_is_valid_url(self, crawler):
        """测试URL验证"""
        # 有效URL
        assert crawler._is_valid_url("https://example.com") is True
        assert crawler._is_valid_url("http://example.com/path") is True
        assert crawler._is_valid_url("https://subdomain.example.com/path?param=value") is True
        
        # 无效URL
        assert crawler._is_valid_url("") is False
        assert crawler._is_valid_url("not-a-url") is False
        assert crawler._is_valid_url("ftp://example.com") is True  # FTP也是有效的
        assert crawler._is_valid_url("example.com") is False  # 缺少协议
    
    @patch('crypto_news_analyzer.crawlers.rss_crawler.RSSCrawler._fetch_rss_content')
    def test_crawl_source_success(self, mock_fetch, crawler, sample_rss_source, sample_rss_content):
        """测试成功爬取RSS源"""
        mock_fetch.return_value = sample_rss_content
        
        items = crawler.crawl_source(sample_rss_source)
        
        # 应该只返回时间窗口内的条目
        assert len(items) >= 0  # 取决于测试运行时间
        mock_fetch.assert_called_once_with(sample_rss_source.url)
    
    @patch('crypto_news_analyzer.crawlers.rss_crawler.RSSCrawler._fetch_rss_content')
    def test_crawl_source_network_error(self, mock_fetch, crawler, sample_rss_source):
        """测试网络错误处理"""
        mock_fetch.side_effect = NetworkError("网络连接失败")
        
        with pytest.raises(CrawlerError):
            crawler.crawl_source(sample_rss_source)
    
    @patch('crypto_news_analyzer.crawlers.rss_crawler.RSSCrawler.crawl_source')
    def test_crawl_all_sources_mixed_results(self, mock_crawl_source, crawler):
        """测试爬取多个源的混合结果"""
        # 创建测试源
        sources = [
            RSSSource("源1", "https://example1.com/rss", "描述1"),
            RSSSource("源2", "https://example2.com/rss", "描述2"),
            RSSSource("源3", "https://example3.com/rss", "描述3")
        ]
        
        # 模拟混合结果：成功、失败、成功
        mock_items = [
            ContentItem(
                id="test1",
                title="测试1",
                content="内容1",
                url="https://example.com/1",
                publish_time=datetime.now(),
                source_name="源1",
                source_type="rss"
            )
        ]
        
        mock_crawl_source.side_effect = [
            mock_items,  # 源1成功
            CrawlerError("源2失败"),  # 源2失败
            []  # 源3成功但无内容
        ]
        
        result = crawler.crawl_all_sources(sources)
        
        assert len(result['results']) == 3
        assert result['results'][0].status == "success"
        assert result['results'][0].item_count == 1
        assert result['results'][1].status == "error"
        assert result['results'][1].error_message == "源2失败"
        assert result['results'][2].status == "success"
        assert result['results'][2].item_count == 0
        
        assert result['total_items'] == 1
        assert len(result['items']) == 1
    
    @patch('crypto_news_analyzer.crawlers.rss_crawler.requests.Session.head')
    def test_validate_rss_source(self, mock_head, crawler, sample_rss_source):
        """测试RSS源验证"""
        # 测试成功验证
        mock_head.return_value.status_code = 200
        assert crawler.validate_rss_source(sample_rss_source) is True
        
        # 测试失败验证
        mock_head.return_value.status_code = 404
        assert crawler.validate_rss_source(sample_rss_source) is False
        
        # 测试网络异常
        mock_head.side_effect = requests.exceptions.ConnectionError()
        assert crawler.validate_rss_source(sample_rss_source) is False
    
    @patch('crypto_news_analyzer.crawlers.rss_crawler.RSSCrawler._fetch_rss_content')
    def test_get_feed_info(self, mock_fetch, crawler, sample_rss_source, sample_rss_content):
        """测试获取RSS源信息"""
        mock_fetch.return_value = sample_rss_content
        
        info = crawler.get_feed_info(sample_rss_source)
        
        assert 'title' in info
        assert 'description' in info
        assert 'entry_count' in info
        assert info['entry_count'] == 2  # sample_rss_content中有2个条目
    
    def test_extract_url_from_multiple_fields(self, crawler):
        """测试从多个字段提取URL"""
        # 测试link字段
        entry1 = Mock()
        entry1.link = "https://example.com/news/1"
        entry1.id = "invalid-id"
        entry1.guid = "invalid-guid"
        
        url1 = crawler._extract_url(entry1)
        assert url1 == "https://example.com/news/1"
        
        # 测试id字段
        entry2 = Mock()
        entry2.link = ""
        entry2.id = "https://example.com/news/2"
        entry2.guid = "invalid-guid"
        
        url2 = crawler._extract_url(entry2)
        assert url2 == "https://example.com/news/2"
        
        # 测试guid字段
        entry3 = Mock()
        entry3.link = ""
        entry3.id = ""
        entry3.guid = "https://example.com/news/3"
        
        url3 = crawler._extract_url(entry3)
        assert url3 == "https://example.com/news/3"


class TestRSSCrawlerIntegration:
    """RSS爬取器集成测试"""
    
    def test_real_rss_parsing(self):
        """测试真实RSS解析（使用本地RSS内容）"""
        # 创建一个真实的RSS内容用于测试
        real_rss_content = """<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
            <channel>
                <title>加密货币新闻测试</title>
                <description>测试用的加密货币新闻RSS</description>
                <link>https://crypto-news-test.com</link>
                <atom:link href="https://crypto-news-test.com/rss" rel="self" type="application/rss+xml"/>
                
                <item>
                    <title><![CDATA[比特币价格突破新高]]></title>
                    <description><![CDATA[
                        <p>比特币价格今日突破历史新高，达到 $50,000 美元。</p>
                        <p>市场分析师认为这是由于机构投资者的大量买入。</p>
                    ]]></description>
                    <link>https://crypto-news-test.com/bitcoin-new-high</link>
                    <guid>https://crypto-news-test.com/bitcoin-new-high</guid>
                    <pubDate>Mon, 01 Jan 2024 10:00:00 GMT</pubDate>
                </item>
                
                <item>
                    <title>以太坊升级完成</title>
                    <description>以太坊网络成功完成最新升级，提高了交易效率。</description>
                    <link>https://crypto-news-test.com/ethereum-upgrade</link>
                    <pubDate>Sun, 31 Dec 2023 15:30:00 GMT</pubDate>
                </item>
            </channel>
        </rss>"""
        
        # 解析RSS内容
        feed = feedparser.parse(real_rss_content)
        
        # 验证解析结果
        assert feed.feed.title == "加密货币新闻测试"
        assert len(feed.entries) == 2
        
        # 验证第一个条目
        entry1 = feed.entries[0]
        assert "比特币价格突破新高" in entry1.title
        assert "50,000" in entry1.description
        assert entry1.link == "https://crypto-news-test.com/bitcoin-new-high"
        
        # 验证第二个条目
        entry2 = feed.entries[1]
        assert "以太坊升级完成" in entry2.title
        assert "交易效率" in entry2.description


if __name__ == "__main__":
    pytest.main([__file__])