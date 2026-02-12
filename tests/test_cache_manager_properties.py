"""
已发送消息缓存管理器属性测试

使用Hypothesis进行属性测试，验证缓存去重一致性。

**属性 20: 缓存去重一致性**
**验证: 需求 17.1, 17.5, 17.7, 17.8, 17.9**
"""

import pytest
import tempfile
import os
from datetime import datetime, timedelta
from hypothesis import given, strategies as st, settings, assume
from hypothesis.stateful import RuleBasedStateMachine, rule, invariant, initialize

from crypto_news_analyzer.storage.cache_manager import SentMessageCacheManager
from crypto_news_analyzer.models import StorageConfig


# 策略：生成有效的消息数据
@st.composite
def valid_message(draw):
    """生成有效的消息数据"""
    summary = draw(st.text(min_size=1, max_size=500))
    category = draw(st.text(min_size=1, max_size=50))
    time = draw(st.text(min_size=1, max_size=50))
    
    return {
        'summary': summary,
        'category': category,
        'time': time
    }


@st.composite
def message_list(draw, min_size=0, max_size=20):
    """生成消息列表"""
    return draw(st.lists(valid_message(), min_size=min_size, max_size=max_size))


class TestCacheManagerProperties:
    """缓存管理器属性测试"""
    
    def setup_method(self):
        """测试前设置"""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_cache_properties.db")
        self.storage_config = StorageConfig(
            retention_days=30,
            max_storage_mb=1000,
            cleanup_frequency="daily",
            database_path=self.db_path
        )
    
    def teardown_method(self):
        """测试后清理"""
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        
        if os.path.exists(self.temp_dir):
            os.rmdir(self.temp_dir)
    
    @given(messages=message_list(min_size=1, max_size=20))
    @settings(max_examples=100, deadline=None)
    def test_property_cache_and_retrieve_consistency(self, messages):
        """
        属性 20.1: 缓存和检索一致性
        
        验证需求 17.1: 报告发送成功后，系统应将已发送的新闻消息缓存到本地存储
        验证需求 17.5: 下次scheduled任务执行时，系统应从缓存中读取24小时内已发送的消息
        
        属性: 缓存的消息数量应该等于成功缓存的数量，且检索到的消息应该包含所有缓存的消息
        """
        with SentMessageCacheManager(self.storage_config) as cache_mgr:
            # 缓存消息
            cached_count = cache_mgr.cache_sent_messages(messages)
            
            # 属性1: 缓存数量应该等于输入消息数量（所有消息都有效）
            assert cached_count == len(messages), \
                f"缓存数量 {cached_count} 应该等于输入消息数量 {len(messages)}"
            
            # 检索消息
            retrieved = cache_mgr.get_cached_messages(hours=24)
            
            # 属性2: 检索到的消息数量应该等于缓存的数量
            assert len(retrieved) == cached_count, \
                f"检索到的消息数量 {len(retrieved)} 应该等于缓存数量 {cached_count}"
            
            # 属性3: 检索到的消息应该包含所有缓存的消息内容
            retrieved_summaries = {msg['summary'] for msg in retrieved}
            original_summaries = {msg['summary'] for msg in messages}
            assert retrieved_summaries == original_summaries, \
                "检索到的消息摘要应该与原始消息摘要一致"
    
    @given(
        messages1=message_list(min_size=1, max_size=10),
        messages2=message_list(min_size=1, max_size=10)
    )
    @settings(max_examples=100, deadline=None)
    def test_property_multiple_cache_operations_accumulate(self, messages1, messages2):
        """
        属性 20.2: 多次缓存操作累积性
        
        验证需求 17.1: 系统应将已发送的新闻消息缓存到本地存储
        
        属性: 多次缓存操作应该累积，总缓存数量应该等于所有缓存操作的总和
        """
        with SentMessageCacheManager(self.storage_config) as cache_mgr:
            # 第一次缓存
            count1 = cache_mgr.cache_sent_messages(messages1)
            
            # 第二次缓存
            count2 = cache_mgr.cache_sent_messages(messages2)
            
            # 检索所有消息
            all_messages = cache_mgr.get_cached_messages(hours=24)
            
            # 属性: 总缓存数量应该等于两次缓存的总和
            expected_total = count1 + count2
            assert len(all_messages) == expected_total, \
                f"总缓存数量 {len(all_messages)} 应该等于两次缓存的总和 {expected_total}"
    
    @given(
        messages=message_list(min_size=1, max_size=20),
        hours=st.integers(min_value=1, max_value=48)
    )
    @settings(max_examples=100, deadline=None)
    def test_property_time_window_filtering(self, messages, hours):
        """
        属性 20.3: 时间窗口过滤正确性
        
        验证需求 17.5: 系统应从缓存中读取24小时内已发送的消息
        
        属性: 使用不同时间窗口检索时，较大的时间窗口应该包含较小时间窗口的所有消息
        """
        with SentMessageCacheManager(self.storage_config) as cache_mgr:
            # 缓存消息
            cache_mgr.cache_sent_messages(messages)
            
            # 使用不同时间窗口检索
            messages_small = cache_mgr.get_cached_messages(hours=1)
            messages_large = cache_mgr.get_cached_messages(hours=hours)
            
            # 属性: 较大时间窗口应该包含较小时间窗口的所有消息
            small_summaries = {msg['summary'] for msg in messages_small}
            large_summaries = {msg['summary'] for msg in messages_large}
            
            assert small_summaries.issubset(large_summaries), \
                f"较大时间窗口({hours}h)应该包含较小时间窗口(1h)的所有消息"
    
    @given(messages=message_list(min_size=1, max_size=20))
    @settings(max_examples=100, deadline=None)
    def test_property_format_for_prompt_consistency(self, messages):
        """
        属性 20.4: 提示词格式化一致性
        
        验证需求 17.7: 系统应将缓存的消息格式化为简洁的文本摘要
        验证需求 17.8: 大模型分析新内容时应使用包含outdated_news的完整提示词
        
        属性: 格式化后的文本应该包含所有缓存消息的关键信息（时间、分类、摘要）
        """
        with SentMessageCacheManager(self.storage_config) as cache_mgr:
            # 缓存消息
            cache_mgr.cache_sent_messages(messages)
            
            # 格式化为提示词
            formatted = cache_mgr.format_cached_messages_for_prompt(hours=24)
            
            # 属性1: 格式化结果不应该为空
            assert formatted != "无", "有消息时格式化结果不应该为'无'"
            
            # 属性2: 格式化结果应该包含所有消息的摘要
            for msg in messages:
                assert msg['summary'] in formatted, \
                    f"格式化结果应该包含消息摘要: {msg['summary']}"
            
            # 属性3: 格式化结果应该包含所有消息的分类
            for msg in messages:
                assert msg['category'] in formatted, \
                    f"格式化结果应该包含消息分类: {msg['category']}"
            
            # 属性4: 格式化结果应该包含所有消息的时间
            for msg in messages:
                assert msg['time'] in formatted, \
                    f"格式化结果应该包含消息时间: {msg['time']}"
            
            # 属性5: 格式化结果应该使用正确的格式 "- [时间] [分类] 摘要"
            lines = formatted.split('\n')
            assert len(lines) == len(messages), \
                f"格式化行数 {len(lines)} 应该等于消息数量 {len(messages)}"
            
            for line in lines:
                assert line.startswith('- ['), "每行应该以'- ['开头"
                assert '] [' in line, "每行应该包含'] ['"
    
    @given(messages=message_list(min_size=1, max_size=20))
    @settings(max_examples=100, deadline=None)
    def test_property_empty_cache_returns_none_marker(self, messages):
        """
        属性 20.5: 空缓存标记一致性
        
        验证需求 17.9: 系统应确保大模型能够识别并过滤掉与缓存消息重复的内容
        
        属性: 当缓存为空时，格式化结果应该返回"无"
        """
        with SentMessageCacheManager(self.storage_config) as cache_mgr:
            # 验证空缓存返回"无"
            formatted_empty = cache_mgr.format_cached_messages_for_prompt(hours=24)
            assert formatted_empty == "无", "空缓存应该返回'无'"
            
            # 缓存消息
            cache_mgr.cache_sent_messages(messages)
            
            # 验证有消息时不返回"无"
            formatted_with_messages = cache_mgr.format_cached_messages_for_prompt(hours=24)
            assert formatted_with_messages != "无", "有消息时不应该返回'无'"
            
            # 清空缓存
            cache_mgr.clear_all_cache()
            
            # 验证清空后返回"无"
            formatted_after_clear = cache_mgr.format_cached_messages_for_prompt(hours=24)
            assert formatted_after_clear == "无", "清空缓存后应该返回'无'"
    
    @given(
        messages=message_list(min_size=1, max_size=20),
        cleanup_hours=st.integers(min_value=0, max_value=48)
    )
    @settings(max_examples=100, deadline=None)
    def test_property_cleanup_removes_expired_only(self, messages, cleanup_hours):
        """
        属性 20.6: 清理操作只删除过期消息
        
        验证需求 17.1: 系统应将已发送的新闻消息缓存到本地存储
        
        属性: 清理操作应该只删除超过指定时间的消息，不影响时间窗口内的消息
        """
        with SentMessageCacheManager(self.storage_config) as cache_mgr:
            # 缓存消息
            cached_count = cache_mgr.cache_sent_messages(messages)
            
            # 获取清理前的消息数量
            before_cleanup = cache_mgr.get_cached_messages(hours=48)
            
            # 执行清理（清理超过cleanup_hours的消息）
            deleted_count = cache_mgr.cleanup_expired_cache(hours=cleanup_hours)
            
            # 获取清理后的消息数量
            after_cleanup = cache_mgr.get_cached_messages(hours=48)
            
            # 属性1: 删除数量 + 剩余数量 = 原始数量
            assert deleted_count + len(after_cleanup) == len(before_cleanup), \
                f"删除数量({deleted_count}) + 剩余数量({len(after_cleanup)}) 应该等于原始数量({len(before_cleanup)})"
            
            # 属性2: 如果cleanup_hours很大，不应该删除任何消息
            if cleanup_hours >= 48:
                assert deleted_count == 0, \
                    f"cleanup_hours={cleanup_hours}时不应该删除任何消息"
                assert len(after_cleanup) == cached_count, \
                    "清理后的消息数量应该等于缓存数量"
    
    @given(messages=message_list(min_size=1, max_size=20))
    @settings(max_examples=100, deadline=None)
    def test_property_statistics_consistency(self, messages):
        """
        属性 20.7: 统计信息一致性
        
        验证需求 17.1: 系统应将已发送的新闻消息缓存到本地存储
        
        属性: 统计信息应该与实际缓存的消息数量和分类一致
        """
        with SentMessageCacheManager(self.storage_config) as cache_mgr:
            # 缓存消息
            cached_count = cache_mgr.cache_sent_messages(messages)
            
            # 获取统计信息
            stats = cache_mgr.get_cache_statistics()
            
            # 属性1: 总消息数应该等于缓存数量
            assert stats['total_cached_messages'] == cached_count, \
                f"统计的总消息数({stats['total_cached_messages']})应该等于缓存数量({cached_count})"
            
            # 属性2: 24小时内的消息数应该等于缓存数量（因为刚缓存）
            assert stats['messages_last_24h'] == cached_count, \
                f"24小时内的消息数({stats['messages_last_24h']})应该等于缓存数量({cached_count})"
            
            # 属性3: 分类统计的总和应该等于总消息数
            category_total = sum(stats['category_distribution'].values())
            assert category_total == cached_count, \
                f"分类统计总和({category_total})应该等于缓存数量({cached_count})"
            
            # 属性4: 每个分类的数量应该与实际消息匹配
            category_counts = {}
            for msg in messages:
                category = msg['category']
                category_counts[category] = category_counts.get(category, 0) + 1
            
            for category, count in category_counts.items():
                assert stats['category_distribution'].get(category, 0) == count, \
                    f"分类'{category}'的统计数量应该为{count}"
    
    @given(messages=message_list(min_size=0, max_size=20))
    @settings(max_examples=100, deadline=None)
    def test_property_empty_list_handling(self, messages):
        """
        属性 20.8: 空列表处理一致性
        
        验证需求 17.1: 系统应将已发送的新闻消息缓存到本地存储
        
        属性: 缓存空列表应该返回0，不影响现有缓存
        """
        with SentMessageCacheManager(self.storage_config) as cache_mgr:
            # 先缓存一些消息（如果有）
            if messages:
                initial_count = cache_mgr.cache_sent_messages(messages)
            else:
                initial_count = 0
            
            # 缓存空列表
            empty_count = cache_mgr.cache_sent_messages([])
            
            # 属性1: 缓存空列表应该返回0
            assert empty_count == 0, "缓存空列表应该返回0"
            
            # 属性2: 缓存空列表不应该影响现有缓存
            current_messages = cache_mgr.get_cached_messages(hours=24)
            assert len(current_messages) == initial_count, \
                f"缓存空列表后的消息数量({len(current_messages)})应该等于初始数量({initial_count})"


class CacheManagerStateMachine(RuleBasedStateMachine):
    """
    基于状态的缓存管理器测试
    
    验证缓存管理器在各种操作序列下的一致性
    """
    
    def __init__(self):
        super().__init__()
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_cache_state.db")
        self.storage_config = StorageConfig(
            retention_days=30,
            max_storage_mb=1000,
            cleanup_frequency="daily",
            database_path=self.db_path
        )
        self.cache_mgr = SentMessageCacheManager(self.storage_config)
        self.expected_count = 0  # 期望的消息数量
        self.all_messages = []  # 所有缓存的消息
    
    @rule(messages=message_list(min_size=1, max_size=10))
    def cache_messages(self, messages):
        """缓存消息"""
        cached_count = self.cache_mgr.cache_sent_messages(messages)
        self.expected_count += cached_count
        self.all_messages.extend(messages)
    
    @rule(hours=st.integers(min_value=1, max_value=48))
    def get_cached_messages(self, hours):
        """获取缓存消息"""
        retrieved = self.cache_mgr.get_cached_messages(hours=hours)
        # 验证检索到的消息数量不超过期望数量
        assert len(retrieved) <= self.expected_count
    
    @rule()
    def get_statistics(self):
        """获取统计信息"""
        stats = self.cache_mgr.get_cache_statistics()
        # 验证统计信息的一致性
        assert stats['total_cached_messages'] == self.expected_count
        assert stats['messages_last_24h'] <= self.expected_count
    
    @rule()
    def format_for_prompt(self):
        """格式化为提示词"""
        formatted = self.cache_mgr.format_cached_messages_for_prompt(hours=24)
        if self.expected_count == 0:
            assert formatted == "无"
        else:
            assert formatted != "无"
    
    @rule(hours=st.integers(min_value=0, max_value=48))
    def cleanup_expired(self, hours):
        """清理过期缓存"""
        before_count = len(self.cache_mgr.get_cached_messages(hours=48))
        deleted_count = self.cache_mgr.cleanup_expired_cache(hours=hours)
        after_count = len(self.cache_mgr.get_cached_messages(hours=48))
        
        # 验证删除数量的一致性
        assert deleted_count + after_count == before_count
        
        # 更新期望数量
        self.expected_count = after_count
    
    @invariant()
    def check_consistency(self):
        """不变量：统计信息应该与实际缓存一致"""
        stats = self.cache_mgr.get_cache_statistics()
        actual_count = len(self.cache_mgr.get_cached_messages(hours=48))
        assert stats['total_cached_messages'] == actual_count
    
    def teardown(self):
        """清理资源"""
        self.cache_mgr.close()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        if os.path.exists(self.temp_dir):
            os.rmdir(self.temp_dir)


# 状态机测试
TestCacheManagerStateMachine = CacheManagerStateMachine.TestCase


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
