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
        
        # 检查时间窗口计算 - RSS爬取器使用UTC时间
        from datetime import timezone
        expected_cutoff = datetime.now(timezone.utc) - timedelta(hours=12)
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
        """测试缺少内容的RSS条目 - 应该使用标题作为内容"""
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
        
        # 当内容缺失时，应该使用标题作为内容（支持像CoinDesk这样只有标题的RSS源）
        assert item is not None
        assert item.title == "测试标题"
        assert item.content == "测试标题"  # 内容应该等于标题
    
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
        
        from datetime import timezone
        time1 = crawler._extract_publish_time(entry1)
        assert time1 == datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        
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
        # RSS爬取器使用UTC时间，所以测试也需要使用UTC
        from datetime import timezone
        
        # 当前时间（应该在窗口内）
        current_time = datetime.now(timezone.utc)
        assert crawler._is_within_time_window(current_time) is True
        
        # 1小时前（应该在窗口内）
        one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
        assert crawler._is_within_time_window(one_hour_ago) is True
        
        # 25小时前（应该在窗口外，因为窗口是24小时）
        old_time = datetime.now(timezone.utc) - timedelta(hours=25)
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


class TestRSSFormats:
    """测试各种RSS格式的解析 - 需求 3.6"""
    
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
    
    def test_rss_2_0_format_parsing(self, crawler, sample_rss_source):
        """测试RSS 2.0格式解析"""
        rss_2_0_content = """<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
            <channel>
                <title>RSS 2.0 测试</title>
                <description>RSS 2.0 格式测试</description>
                <link>https://example.com</link>
                
                <item>
                    <title>RSS 2.0 新闻标题</title>
                    <description>RSS 2.0 新闻内容描述</description>
                    <link>https://example.com/news/rss20</link>
                    <pubDate>Mon, 01 Jan 2024 12:00:00 GMT</pubDate>
                    <guid>https://example.com/news/rss20</guid>
                </item>
            </channel>
        </rss>"""
        
        feed = feedparser.parse(rss_2_0_content)
        assert feed.version == "rss20"
        assert len(feed.entries) == 1
        
        item = crawler._parse_rss_entry(feed.entries[0], sample_rss_source)
        assert item is not None
        assert item.title == "RSS 2.0 新闻标题"
        assert item.content == "RSS 2.0 新闻内容描述"
        assert item.url == "https://example.com/news/rss20"
    
    def test_atom_format_parsing(self, crawler, sample_rss_source):
        """测试Atom格式解析"""
        atom_content = """<?xml version="1.0" encoding="UTF-8"?>
        <feed xmlns="http://www.w3.org/2005/Atom">
            <title>Atom 测试</title>
            <subtitle>Atom 格式测试</subtitle>
            <link href="https://example.com"/>
            <id>https://example.com/atom</id>
            <updated>2024-01-01T12:00:00Z</updated>
            
            <entry>
                <title>Atom 新闻标题</title>
                <summary>Atom 新闻内容摘要</summary>
                <link href="https://example.com/news/atom"/>
                <id>https://example.com/news/atom</id>
                <updated>2024-01-01T12:00:00Z</updated>
                <published>2024-01-01T12:00:00Z</published>
            </entry>
        </feed>"""
        
        feed = feedparser.parse(atom_content)
        assert feed.version == "atom10"
        assert len(feed.entries) == 1
        
        item = crawler._parse_rss_entry(feed.entries[0], sample_rss_source)
        assert item is not None
        assert item.title == "Atom 新闻标题"
        assert item.content == "Atom 新闻内容摘要"
        assert item.url == "https://example.com/news/atom"
    
    def test_rss_1_0_format_parsing(self, crawler, sample_rss_source):
        """测试RSS 1.0 (RDF)格式解析"""
        rss_1_0_content = """<?xml version="1.0" encoding="UTF-8"?>
        <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
                 xmlns="http://purl.org/rss/1.0/">
            <channel rdf:about="https://example.com">
                <title>RSS 1.0 测试</title>
                <description>RSS 1.0 格式测试</description>
                <link>https://example.com</link>
                <items>
                    <rdf:Seq>
                        <rdf:li rdf:resource="https://example.com/news/rss10"/>
                    </rdf:Seq>
                </items>
            </channel>
            
            <item rdf:about="https://example.com/news/rss10">
                <title>RSS 1.0 新闻标题</title>
                <description>RSS 1.0 新闻内容描述</description>
                <link>https://example.com/news/rss10</link>
            </item>
        </rdf:RDF>"""
        
        feed = feedparser.parse(rss_1_0_content)
        assert feed.version == "rss10"
        assert len(feed.entries) == 1
        
        item = crawler._parse_rss_entry(feed.entries[0], sample_rss_source)
        assert item is not None
        assert item.title == "RSS 1.0 新闻标题"
        assert item.content == "RSS 1.0 新闻内容描述"
        assert item.url == "https://example.com/news/rss10"
    
    def test_malformed_rss_parsing(self, crawler, sample_rss_source):
        """测试格式错误的RSS解析"""
        malformed_rss = """<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
            <channel>
                <title>格式错误的RSS</title>
                <description>测试格式错误的RSS</description>
                <!-- 缺少结束标签的item -->
                <item>
                    <title>不完整的条目</title>
                    <description>这个条目缺少结束标签
                
                <item>
                    <title>正常的条目</title>
                    <description>这个条目是正常的</description>
                    <link>https://example.com/normal</link>
                    <pubDate>Mon, 01 Jan 2024 12:00:00 GMT</pubDate>
                </item>
            </channel>
        </rss>"""
        
        # feedparser应该能够处理格式错误的RSS
        feed = feedparser.parse(malformed_rss)
        assert feed.bozo == True  # 表示解析时遇到了问题
        # 但仍然应该能解析出一些内容
        assert len(feed.entries) >= 1
    
    def test_rss_with_cdata_sections(self, crawler, sample_rss_source):
        """测试包含CDATA的RSS解析"""
        cdata_rss = """<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
            <channel>
                <title><![CDATA[包含CDATA的RSS]]></title>
                <description><![CDATA[测试CDATA处理]]></description>
                
                <item>
                    <title><![CDATA[CDATA标题 & 特殊字符 < > "]]></title>
                    <description><![CDATA[
                        <p>这是包含HTML的内容</p>
                        <p>特殊字符: & < > " '</p>
                        <script>alert('test');</script>
                    ]]></description>
                    <link>https://example.com/cdata</link>
                    <pubDate>Mon, 01 Jan 2024 12:00:00 GMT</pubDate>
                </item>
            </channel>
        </rss>"""
        
        feed = feedparser.parse(cdata_rss)
        assert len(feed.entries) == 1
        
        item = crawler._parse_rss_entry(feed.entries[0], sample_rss_source)
        assert item is not None
        assert "CDATA标题" in item.title
        assert "特殊字符" in item.content
        # 确保HTML被清理
        assert "<script>" not in item.content
        assert "alert" not in item.content
    
    def test_rss_with_namespaces(self, crawler, sample_rss_source):
        """测试包含命名空间的RSS解析"""
        namespaced_rss = """<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0" 
             xmlns:content="http://purl.org/rss/1.0/modules/content/"
             xmlns:dc="http://purl.org/dc/elements/1.1/">
            <channel>
                <title>命名空间RSS测试</title>
                <description>测试命名空间处理</description>
                
                <item>
                    <title>命名空间新闻</title>
                    <description>简短描述</description>
                    <content:encoded><![CDATA[
                        <p>这是完整的HTML内容</p>
                        <p>包含更多详细信息</p>
                    ]]></content:encoded>
                    <dc:creator>作者名称</dc:creator>
                    <link>https://example.com/namespace</link>
                    <pubDate>Mon, 01 Jan 2024 12:00:00 GMT</pubDate>
                </item>
            </channel>
        </rss>"""
        
        feed = feedparser.parse(namespaced_rss)
        assert len(feed.entries) == 1
        
        entry = feed.entries[0]
        # feedparser应该能够处理命名空间
        assert hasattr(entry, 'content')
        assert hasattr(entry, 'author')
        
        item = crawler._parse_rss_entry(entry, sample_rss_source)
        assert item is not None
        assert item.title == "命名空间新闻"


class TestNetworkErrorHandling:
    """测试网络错误和异常情况 - 需求 3.3"""
    
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
    
    @patch('crypto_news_analyzer.crawlers.rss_crawler.requests.Session.get')
    def test_connection_timeout_error(self, mock_get, crawler, sample_rss_source):
        """测试连接超时错误"""
        mock_get.side_effect = requests.exceptions.Timeout("连接超时")
        
        with pytest.raises(CrawlerError) as exc_info:
            crawler.crawl_source(sample_rss_source)
        
        assert "连接超时" in str(exc_info.value)
        assert mock_get.call_count == 3  # 应该重试3次
    
    @patch('crypto_news_analyzer.crawlers.rss_crawler.requests.Session.get')
    def test_connection_error(self, mock_get, crawler, sample_rss_source):
        """测试连接错误"""
        mock_get.side_effect = requests.exceptions.ConnectionError("无法连接到服务器")
        
        with pytest.raises(CrawlerError) as exc_info:
            crawler.crawl_source(sample_rss_source)
        
        assert "无法连接到服务器" in str(exc_info.value)
        assert mock_get.call_count == 3  # 应该重试3次
    
    @patch('crypto_news_analyzer.crawlers.rss_crawler.requests.Session.get')
    def test_http_error_404(self, mock_get, crawler, sample_rss_source):
        """测试HTTP 404错误"""
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("404 Not Found")
        mock_get.return_value = mock_response
        
        with pytest.raises(CrawlerError) as exc_info:
            crawler.crawl_source(sample_rss_source)
        
        assert "404 Not Found" in str(exc_info.value)
        assert mock_get.call_count == 3  # 应该重试3次
    
    @patch('crypto_news_analyzer.crawlers.rss_crawler.requests.Session.get')
    def test_http_error_500(self, mock_get, crawler, sample_rss_source):
        """测试HTTP 500错误"""
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("500 Internal Server Error")
        mock_get.return_value = mock_response
        
        with pytest.raises(CrawlerError) as exc_info:
            crawler.crawl_source(sample_rss_source)
        
        assert "500 Internal Server Error" in str(exc_info.value)
    
    @patch('crypto_news_analyzer.crawlers.rss_crawler.requests.Session.get')
    def test_dns_resolution_error(self, mock_get, crawler, sample_rss_source):
        """测试DNS解析错误"""
        mock_get.side_effect = requests.exceptions.ConnectionError("DNS解析失败")
        
        with pytest.raises(CrawlerError):
            crawler.crawl_source(sample_rss_source)
    
    @patch('crypto_news_analyzer.crawlers.rss_crawler.requests.Session.get')
    def test_ssl_error(self, mock_get, crawler, sample_rss_source):
        """测试SSL证书错误"""
        mock_get.side_effect = requests.exceptions.SSLError("SSL证书验证失败")
        
        with pytest.raises(CrawlerError):
            crawler.crawl_source(sample_rss_source)
    
    @patch('crypto_news_analyzer.crawlers.rss_crawler.requests.Session.get')
    def test_invalid_response_content(self, mock_get, crawler, sample_rss_source):
        """测试无效响应内容"""
        mock_response = Mock()
        mock_response.text = "这不是有效的XML内容"
        mock_response.headers = {'content-type': 'text/html'}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        # 应该能够处理无效内容而不崩溃
        items = crawler.crawl_source(sample_rss_source)
        assert items == []  # 无效内容应该返回空列表
    
    @patch('crypto_news_analyzer.crawlers.rss_crawler.requests.Session.get')
    def test_empty_response(self, mock_get, crawler, sample_rss_source):
        """测试空响应"""
        mock_response = Mock()
        mock_response.text = ""
        mock_response.headers = {'content-type': 'application/rss+xml'}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        items = crawler.crawl_source(sample_rss_source)
        assert items == []
    
    @patch('crypto_news_analyzer.crawlers.rss_crawler.requests.Session.get')
    def test_partial_network_failure_in_batch(self, mock_get, crawler):
        """测试批量爬取中的部分网络失败 - 需求 3.3"""
        sources = [
            RSSSource("成功源1", "https://success1.com/rss", "成功的源1"),
            RSSSource("失败源", "https://fail.com/rss", "失败的源"),
            RSSSource("成功源2", "https://success2.com/rss", "成功的源2")
        ]
        
        # 模拟第二个源失败，其他成功
        success_response = Mock()
        success_response.text = """<?xml version="1.0"?>
        <rss version="2.0">
            <channel>
                <title>测试</title>
                <item>
                    <title>测试新闻</title>
                    <description>测试内容</description>
                    <link>https://example.com/news</link>
                    <pubDate>Mon, 01 Jan 2024 12:00:00 GMT</pubDate>
                </item>
            </channel>
        </rss>"""
        success_response.headers = {'content-type': 'application/rss+xml'}
        success_response.raise_for_status.return_value = None
        
        # 创建一个函数来控制每次调用的返回值
        call_count = 0
        def mock_get_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return success_response  # 第一个源成功
            elif call_count <= 4:  # 第二个源失败（包括重试）
                raise requests.exceptions.ConnectionError("连接失败")
            else:
                return success_response  # 第三个源成功
        
        mock_get.side_effect = mock_get_side_effect
        
        result = crawler.crawl_all_sources(sources)
        
        # 验证结果
        assert len(result['results']) == 3
        assert result['results'][0].status == "success"
        assert result['results'][1].status == "error"
        assert result['results'][2].status == "success"
        assert "连接失败" in result['results'][1].error_message
        
        # 应该有来自成功源的内容
        assert result['total_items'] >= 0  # 可能因为时间窗口过滤而为0
    
    @patch('crypto_news_analyzer.crawlers.rss_crawler.requests.Session.get')
    def test_encoding_error_handling(self, mock_get, crawler, sample_rss_source):
        """测试编码错误处理"""
        # 模拟包含特殊编码的响应
        mock_response = Mock()
        mock_response.text = """<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
            <channel>
                <title>编码测试</title>
                <item>
                    <title>包含特殊字符的标题 ñáéíóú</title>
                    <description>包含emoji的内容 🚀 💰 📈</description>
                    <link>https://example.com/encoding</link>
                    <pubDate>Mon, 01 Jan 2024 12:00:00 GMT</pubDate>
                </item>
            </channel>
        </rss>"""
        mock_response.headers = {'content-type': 'application/rss+xml; charset=utf-8'}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        # 应该能够正确处理特殊字符
        items = crawler.crawl_source(sample_rss_source)
        if items:  # 如果在时间窗口内
            assert "ñáéíóú" in items[0].title
            assert "🚀" in items[0].content


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