"""
X/Twitter内容解析完整性属性测试

使用Hypothesis进行属性测试，验证X/Twitter内容解析的完整性。
**功能: crypto-news-analyzer, 属性 4: 内容解析完整性**
**验证: 需求 4.5**
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock
from hypothesis import given, strategies as st, assume, settings
from typing import List, Dict, Any, Optional

from crypto_news_analyzer.crawlers.x_crawler import XCrawler
from crypto_news_analyzer.models import XSource, ContentItem


# 策略定义：生成有效的X/Twitter数据
@st.composite
def valid_x_tweet_data(draw):
    """生成有效的推文数据"""
    # 生成简单但有意义的推文内容
    tweet_texts = [
        "比特币突破新高！🚀 #Bitcoin #Crypto",
        "以太坊2.0升级完成，网络性能大幅提升 $ETH",
        "加密货币市场今日表现强劲，主流币种普涨",
        "DeFi协议锁仓量创历史新高 #DeFi",
        "NFT市场出现新趋势，艺术品交易活跃",
        "央行数字货币CBDC试点扩大范围"
    ]
    
    usernames = [
        "crypto_analyst", "blockchain_news", "defi_tracker",
        "nft_collector", "bitcoin_whale", "eth_developer"
    ]
    
    text = draw(st.sampled_from(tweet_texts))
    username = draw(st.sampled_from(usernames))
    
    # 生成推文ID
    tweet_id = draw(st.integers(min_value=1000000000000000000, max_value=9999999999999999999))
    
    # 生成时间（在合理范围内）
    now = datetime.now()
    hours_ago = draw(st.integers(min_value=0, max_value=48))
    publish_time = now - timedelta(hours=hours_ago)
    
    # 生成Twitter时间格式字符串
    created_at = publish_time.strftime("%a %b %d %H:%M:%S +0000 %Y")
    
    return {
        "id": str(tweet_id),
        "text": text,
        "created_at": created_at,
        "username": username,
        "publish_time": publish_time
    }


@st.composite
def x_tweet_with_variations(draw):
    """生成具有不同字段变体的推文数据"""
    base_data = draw(valid_x_tweet_data())
    
    # 创建模拟的推文数据结构
    tweet_data = {
        "id": base_data["id"],
        "text": base_data["text"],
        "created_at": base_data["created_at"],
        "user": {
            "screen_name": base_data["username"],
            "name": f"{base_data['username'].title()} User",
            "id": draw(st.integers(min_value=1000000, max_value=9999999999))
        },
        "entities": {
            "hashtags": [],
            "urls": [],
            "user_mentions": []
        },
        "public_metrics": {
            "retweet_count": draw(st.integers(min_value=0, max_value=1000)),
            "like_count": draw(st.integers(min_value=0, max_value=5000)),
            "reply_count": draw(st.integers(min_value=0, max_value=100))
        }
    }
    
    return tweet_data, base_data


@st.composite
def x_timeline_response_data(draw):
    """生成模拟的X时间线响应数据"""
    tweets_count = draw(st.integers(min_value=1, max_value=5))
    tweets = []
    expected_data = []
    
    for _ in range(tweets_count):
        tweet_data, base_data = draw(x_tweet_with_variations())
        tweets.append(tweet_data)
        expected_data.append(base_data)
    
    # 构建模拟的API响应结构
    response_data = {
        "data": {
            "home": {
                "home_timeline_urt": {
                    "instructions": [
                        {
                            "type": "TimelineAddEntries",
                            "entries": []
                        }
                    ]
                }
            }
        }
    }
    
    # 为每个推文创建条目
    for i, tweet_data in enumerate(tweets):
        entry = {
            "entryId": f"tweet-{tweet_data['id']}",
            "content": {
                "itemContent": {
                    "tweet_results": {
                        "result": {
                            "rest_id": tweet_data["id"],
                            "legacy": {
                                "full_text": tweet_data["text"],
                                "created_at": tweet_data["created_at"],
                                "entities": tweet_data["entities"],
                                "public_metrics": tweet_data["public_metrics"]
                            },
                            "core": {
                                "user_results": {
                                    "result": {
                                        "legacy": tweet_data["user"]
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
        response_data["data"]["home"]["home_timeline_urt"]["instructions"][0]["entries"].append(entry)
    
    return response_data, tweets, expected_data


class TestXContentParsingProperties:
    """X/Twitter内容解析完整性属性测试"""
    
    def setup_method(self):
        """测试前设置"""
        # 使用模拟的认证信息
        self.crawler = XCrawler(
            ct0="mock_ct0_token",
            auth_token="mock_auth_token",
            time_window_hours=72  # 使用更大的时间窗口
        )
        self.sample_source = XSource(
            name="测试X源",
            url="https://x.com/i/lists/1234567890",
            type="list"
        )
    
    @given(tweet_data=x_tweet_with_variations())
    @settings(max_examples=100, deadline=None)
    def test_x_content_parsing_completeness(self, tweet_data):
        """
        属性测试：X内容解析完整性
        
        **功能: crypto-news-analyzer, 属性 4: 内容解析完整性**
        **验证: 需求 4.5**
        
        对于任何有效的X内容，解析后的ContentItem应该包含标题、内容、发布时间和原文链接等所有必需字段
        """
        tweet_raw, expected_data = tweet_data
        
        # 解析推文数据
        result = self.crawler.parse_tweet(tweet_raw)
        
        # 验证：解析成功时应该是ContentItem对象
        assert isinstance(result, ContentItem), "解析结果应该是ContentItem对象"
        
        # 验证：所有必需字段都存在且非空
        assert result.title, "标题字段不能为空"
        assert result.content, "内容字段不能为空"
        assert result.url, "URL字段不能为空"
        assert result.publish_time, "发布时间字段不能为空"
        assert result.source_name, "数据源名称不能为空"
        assert result.source_type, "数据源类型不能为空"
        
        # 验证：字段类型正确
        assert isinstance(result.title, str), "标题应该是字符串"
        assert isinstance(result.content, str), "内容应该是字符串"
        assert isinstance(result.url, str), "URL应该是字符串"
        assert isinstance(result.publish_time, datetime), "发布时间应该是datetime对象"
        assert isinstance(result.source_name, str), "数据源名称应该是字符串"
        assert isinstance(result.source_type, str), "数据源类型应该是字符串"
        
        # 验证：字段内容正确
        assert expected_data["text"] in result.content, "内容应该包含原始推文文本"
        assert expected_data["username"] in result.title, "标题应该包含用户名"
        assert expected_data["id"] in result.url, "URL应该包含推文ID"
        assert result.source_name == "X/Twitter", "数据源名称应该是X/Twitter"
        assert result.source_type == "x", "数据源类型应该是x"
        
        # 验证：URL格式正确
        expected_url = f"https://x.com/{expected_data['username']}/status/{expected_data['id']}"
        assert result.url == expected_url, f"URL格式不正确，期望: {expected_url}, 实际: {result.url}"
        
        # 验证：发布时间在合理范围内
        time_diff = abs((result.publish_time - expected_data["publish_time"]).total_seconds())
        assert time_diff < 60, f"发布时间差异过大: {time_diff}秒"
        
        # 验证：内容完整性
        assert len(result.content.strip()) > 0, "内容不能为空"
        assert result.content == expected_data["text"], "内容应该与原始推文文本完全匹配"
    
    @given(
        tweets=st.lists(x_tweet_with_variations(), min_size=1, max_size=3),
        time_window=st.integers(min_value=48, max_value=72)
    )
    @settings(max_examples=20, deadline=None)
    def test_batch_parsing_completeness(self, tweets, time_window):
        """
        属性测试：批量解析的完整性
        
        验证批量解析多个推文时，每个有效推文都能正确解析
        """
        crawler = XCrawler(
            ct0="mock_ct0_token",
            auth_token="mock_auth_token", 
            time_window_hours=time_window
        )
        
        valid_results = []
        expected_count = 0
        
        for tweet_raw, expected_data in tweets:
            try:
                result = crawler.parse_tweet(tweet_raw)
                valid_results.append(result)
                
                # 只有在时间窗口内的推文才应该被计入期望数量
                if crawler.is_within_time_window(expected_data["publish_time"]):
                    expected_count += 1
                    
            except Exception as e:
                # 记录解析失败的情况，但不中断测试
                pytest.fail(f"推文解析失败: {str(e)}")
        
        # 验证：所有解析成功的推文都应该在时间窗口内
        filtered_results = [
            result for result in valid_results 
            if crawler.is_within_time_window(result.publish_time)
        ]
        
        assert len(filtered_results) == expected_count, \
            f"时间窗口内解析结果数量不匹配：期望 {expected_count}，实际 {len(filtered_results)}"
        
        # 验证：每个解析结果都包含完整字段
        for result in filtered_results:
            assert result.title, "批量解析中的标题字段不能为空"
            assert result.content, "批量解析中的内容字段不能为空"
            assert result.url, "批量解析中的URL字段不能为空"
            assert result.publish_time, "批量解析中的发布时间字段不能为空"
            assert result.source_name == "X/Twitter", "批量解析中的数据源名称不匹配"
            assert result.source_type == "x", "批量解析中的数据源类型不匹配"
    
    @given(response_data=x_timeline_response_data())
    @settings(max_examples=30, deadline=None)
    def test_timeline_response_parsing_completeness(self, response_data):
        """
        属性测试：时间线响应解析的完整性
        
        验证从X API响应中解析推文数据的完整性
        """
        api_response, tweet_list, expected_list = response_data
        
        # 解析时间线响应
        parsed_tweets = self.crawler._parse_timeline_response(api_response)
        
        # 验证：解析结果数量正确
        assert len(parsed_tweets) == len(tweet_list), \
            f"解析的推文数量不匹配：期望 {len(tweet_list)}，实际 {len(parsed_tweets)}"
        
        # 验证：每个解析的推文都包含必需字段
        for i, parsed_tweet in enumerate(parsed_tweets):
            expected_data = expected_list[i]
            
            assert "id" in parsed_tweet, "解析的推文应该包含ID字段"
            assert "text" in parsed_tweet, "解析的推文应该包含文本字段"
            assert "created_at" in parsed_tweet, "解析的推文应该包含创建时间字段"
            assert "user" in parsed_tweet, "解析的推文应该包含用户字段"
            
            # 验证字段内容正确
            assert parsed_tweet["id"] == expected_data["id"], "推文ID不匹配"
            assert parsed_tweet["text"] == expected_data["text"], "推文文本不匹配"
            assert parsed_tweet["created_at"] == expected_data["created_at"], "创建时间不匹配"
            assert parsed_tweet["user"]["screen_name"] == expected_data["username"], "用户名不匹配"
    
    @given(tweet_data=x_tweet_with_variations())
    @settings(max_examples=50, deadline=None)
    def test_twitter_time_parsing_robustness(self, tweet_data):
        """
        属性测试：Twitter时间解析的健壮性
        
        验证Twitter时间格式解析的正确性
        """
        tweet_raw, expected_data = tweet_data
        
        # 测试时间解析
        parsed_time = self.crawler._parse_twitter_time(expected_data["created_at"])
        
        # 验证：解析结果是datetime对象
        assert isinstance(parsed_time, datetime), "解析的时间应该是datetime对象"
        
        # 验证：时间在合理范围内（允许一定误差）
        time_diff = abs((parsed_time - expected_data["publish_time"]).total_seconds())
        assert time_diff < 60, f"时间解析误差过大: {time_diff}秒"
        
        # 验证：时间不是未来时间
        assert parsed_time <= datetime.now(), "解析的时间不应该是未来时间"
    
    @given(
        tweets=st.lists(x_tweet_with_variations(), min_size=2, max_size=5)
    )
    @settings(max_examples=15, deadline=None)
    def test_parsing_consistency_across_tweets(self, tweets):
        """
        属性测试：跨推文解析的一致性
        
        验证解析多个推文时的一致性行为
        """
        results = []
        
        for tweet_raw, expected_data in tweets:
            try:
                result = self.crawler.parse_tweet(tweet_raw)
                results.append((result, expected_data))
            except Exception as e:
                pytest.fail(f"推文解析失败: {str(e)}")
        
        # 验证：所有解析结果都具有一致的结构
        if results:
            first_result, _ = results[0]
            
            for result, expected_data in results:
                # 验证：所有结果都有相同的字段类型
                assert type(result.title) == type(first_result.title), "标题类型不一致"
                assert type(result.content) == type(first_result.content), "内容类型不一致"
                assert type(result.url) == type(first_result.url), "URL类型不一致"
                assert type(result.publish_time) == type(first_result.publish_time), "时间类型不一致"
                assert type(result.source_name) == type(first_result.source_name), "数据源名称类型不一致"
                assert type(result.source_type) == type(first_result.source_type), "数据源类型类型不一致"
                
                # 验证：所有结果都有相同的数据源信息
                assert result.source_name == first_result.source_name, "数据源名称不一致"
                assert result.source_type == first_result.source_type, "数据源类型不一致"
    
    @given(tweet_data=x_tweet_with_variations())
    @settings(max_examples=30, deadline=None)
    def test_content_item_validation_after_parsing(self, tweet_data):
        """
        属性测试：解析后ContentItem验证的完整性
        
        验证解析生成的ContentItem对象能够通过数据验证
        """
        tweet_raw, expected_data = tweet_data
        
        # 解析推文
        result = self.crawler.parse_tweet(tweet_raw)
        
        # 验证：ContentItem对象能够通过验证
        try:
            result.validate()
        except ValueError as e:
            pytest.fail(f"解析生成的ContentItem验证失败: {e}")
        
        # 验证：可以序列化和反序列化
        try:
            json_str = result.to_json()
            restored = ContentItem.from_json(json_str)
            assert restored.title == result.title, "序列化后标题不一致"
            assert restored.content == result.content, "序列化后内容不一致"
            assert restored.url == result.url, "序列化后URL不一致"
            assert restored.publish_time == result.publish_time, "序列化后时间不一致"
        except Exception as e:
            pytest.fail(f"ContentItem序列化/反序列化失败: {e}")
    
    @given(
        tweets=st.lists(x_tweet_with_variations(), min_size=1, max_size=3),
        time_window=st.integers(min_value=1, max_value=48)
    )
    @settings(max_examples=20, deadline=None)
    def test_time_window_filtering_completeness(self, tweets, time_window):
        """
        属性测试：时间窗口过滤的完整性
        
        验证时间窗口过滤功能的正确性
        """
        crawler = XCrawler(
            ct0="mock_ct0_token",
            auth_token="mock_auth_token",
            time_window_hours=time_window
        )
        
        # 解析所有推文
        all_results = []
        expected_in_window = []
        
        for tweet_raw, expected_data in tweets:
            try:
                result = crawler.parse_tweet(tweet_raw)
                all_results.append(result)
                
                # 检查是否应该在时间窗口内
                if crawler.is_within_time_window(expected_data["publish_time"]):
                    expected_in_window.append(result)
                    
            except Exception as e:
                pytest.fail(f"推文解析失败: {str(e)}")
        
        # 使用爬取器的过滤方法
        filtered_results = crawler._filter_by_time_window([
            {"id": result.id.split("_")[-1] if "_" in result.id else "123456789",
             "text": result.content,
             "created_at": result.publish_time.strftime("%a %b %d %H:%M:%S +0000 %Y"),
             "user": {"screen_name": result.title.split(":")[0].replace("@", "")}}
            for result in all_results
        ])
        
        # 验证：过滤结果数量正确
        assert len(filtered_results) == len(expected_in_window), \
            f"时间窗口过滤结果数量不匹配：期望 {len(expected_in_window)}，实际 {len(filtered_results)}"
        
        # 验证：所有过滤后的结果都在时间窗口内
        for result in filtered_results:
            assert crawler.is_within_time_window(result.publish_time), \
                "过滤后的结果应该都在时间窗口内"


if __name__ == "__main__":
    # 运行属性测试
    pytest.main([__file__, "-v", "--tb=short"])