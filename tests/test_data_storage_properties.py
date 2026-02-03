"""
数据存储属性测试

使用Hypothesis进行属性测试，验证数据存储系统的时间窗口过滤正确性。
**功能: crypto-news-analyzer, 属性 9: 时间窗口过滤正确性**
**验证: 需求 10.1**
"""

import pytest
import tempfile
import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from hypothesis import given, strategies as st, assume, settings
from typing import List, Dict, Any

from crypto_news_analyzer.storage.data_manager import DataManager
from crypto_news_analyzer.models import ContentItem, StorageConfig, create_content_item_from_raw


# 策略定义：生成测试数据
@st.composite
def valid_content_item(draw, base_time: datetime = None):
    """生成有效的ContentItem"""
    if base_time is None:
        base_time = datetime.now()
    
    # 生成相对于基准时间的随机时间偏移
    hours_offset = draw(st.integers(min_value=-168, max_value=168))  # ±1周
    publish_time = base_time + timedelta(hours=hours_offset)
    
    title = draw(st.text(min_size=1, max_size=100).filter(lambda x: x.strip()))
    content = draw(st.text(min_size=1, max_size=500).filter(lambda x: x.strip()))
    
    # 生成唯一的URL
    url_id = draw(st.integers(min_value=1, max_value=999999))
    url = f"https://example.com/news/{url_id}"
    
    source_name = draw(st.sampled_from(["RSS源1", "RSS源2", "X源1", "X源2"]))
    source_type = draw(st.sampled_from(["rss", "x", "rest_api"]))
    
    return create_content_item_from_raw(
        title=title,
        content=content,
        url=url,
        publish_time=publish_time,
        source_name=source_name,
        source_type=source_type
    )


@st.composite
def content_items_with_known_times(draw):
    """生成具有已知时间分布的ContentItem列表"""
    base_time = datetime.now()
    
    # 生成不同时间范围的内容项
    items = []
    
    # 在时间窗口内的项目（最近24小时）
    within_window_count = draw(st.integers(min_value=1, max_value=10))
    for _ in range(within_window_count):
        hours_ago = draw(st.integers(min_value=0, max_value=23))  # 0-23小时前
        publish_time = base_time - timedelta(hours=hours_ago)
        item = draw(valid_content_item(base_time=publish_time))
        item.publish_time = publish_time  # 确保时间正确
        items.append(item)
    
    # 在时间窗口外的项目（24小时以前）
    outside_window_count = draw(st.integers(min_value=1, max_value=10))
    for _ in range(outside_window_count):
        hours_ago = draw(st.integers(min_value=25, max_value=168))  # 25-168小时前
        publish_time = base_time - timedelta(hours=hours_ago)
        item = draw(valid_content_item(base_time=publish_time))
        item.publish_time = publish_time  # 确保时间正确
        items.append(item)
    
    return items, base_time


@st.composite
def valid_storage_config(draw):
    """生成有效的存储配置"""
    return StorageConfig(
        retention_days=draw(st.integers(min_value=1, max_value=365)),
        max_storage_mb=draw(st.integers(min_value=100, max_value=10000)),
        cleanup_frequency=draw(st.sampled_from(["daily", "weekly", "monthly"])),
        database_path=draw(st.just("./test_data.db"))  # 使用固定路径便于清理
    )


class TestDataStorageProperties:
    """数据存储属性测试"""
    
    def setup_method(self):
        """测试前设置"""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_crypto_news.db")
        self.storage_config = StorageConfig(
            retention_days=30,
            max_storage_mb=1000,
            cleanup_frequency="daily",
            database_path=self.db_path
        )
        self.data_manager = DataManager(self.storage_config)
    
    def teardown_method(self):
        """测试后清理"""
        if hasattr(self, 'data_manager'):
            self.data_manager.close()
        
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        
        if os.path.exists(self.temp_dir):
            os.rmdir(self.temp_dir)
    
    @given(
        items_and_time=content_items_with_known_times(),
        time_window_hours=st.integers(min_value=1, max_value=72)
    )
    @settings(max_examples=100, deadline=None)
    def test_time_window_filtering_correctness(self, items_and_time, time_window_hours: int):
        """
        属性测试：时间窗口过滤正确性
        
        **功能: crypto-news-analyzer, 属性 9: 时间窗口过滤正确性**
        **验证: 需求 10.1**
        
        对于任何内容项，只有发布时间在指定时间窗口内的内容应该被包含在最终分析中
        """
        items, reference_time = items_and_time
        
        # 假设：有内容项需要测试
        assume(len(items) > 0)
        
        # 添加所有内容项到数据库
        added_count = self.data_manager.add_content_items(items)
        assume(added_count > 0)  # 确保至少添加了一些项目
        
        # 计算时间窗口的截止时间
        cutoff_time = reference_time - timedelta(hours=time_window_hours)
        
        # 手动计算应该在时间窗口内的项目
        expected_items = [
            item for item in items 
            if item.publish_time >= cutoff_time
        ]
        
        # 使用DataManager获取时间窗口内的内容
        # 注意：我们需要模拟当前时间为reference_time
        # 由于DataManager使用datetime.now()，我们需要直接测试get_content_items方法
        retrieved_items = self.data_manager.get_content_items(
            time_window_hours=time_window_hours
        )
        
        # 由于DataManager使用datetime.now()而不是reference_time，
        # 我们需要调整测试策略，直接测试filter_by_time_window方法
        
        # 先获取所有项目
        all_items = self.data_manager.get_content_items()
        
        # 手动过滤以验证逻辑
        current_time = datetime.now()
        current_cutoff = current_time - timedelta(hours=time_window_hours)
        
        expected_current_items = [
            item for item in all_items
            if item.publish_time >= current_cutoff
        ]
        
        # 验证：get_content_items返回的项目数量应该匹配预期
        assert len(retrieved_items) == len(expected_current_items), (
            f"时间窗口过滤结果不正确：期望 {len(expected_current_items)} 项，"
            f"实际获得 {len(retrieved_items)} 项"
        )
        
        # 验证：所有返回的项目都在时间窗口内
        for item in retrieved_items:
            assert item.publish_time >= current_cutoff, (
                f"项目 {item.id} 的发布时间 {item.publish_time} "
                f"早于截止时间 {current_cutoff}"
            )
        
        # 验证：所有在时间窗口内的项目都被返回了
        retrieved_ids = {item.id for item in retrieved_items}
        for expected_item in expected_current_items:
            assert expected_item.id in retrieved_ids, (
                f"时间窗口内的项目 {expected_item.id} 未被返回"
            )
    
    @given(
        items=st.lists(
            valid_content_item(),
            min_size=5,
            max_size=20
        ),
        time_window_hours=st.integers(min_value=1, max_value=168)
    )
    @settings(max_examples=50, deadline=None)
    def test_filter_by_time_window_removes_old_items(self, items: List[ContentItem], time_window_hours: int):
        """
        属性测试：时间窗口过滤移除旧项目的正确性
        
        验证filter_by_time_window方法正确移除超出时间窗口的项目
        """
        # 添加所有内容项
        added_count = self.data_manager.add_content_items(items)
        assume(added_count > 0)
        
        # 获取过滤前的项目数量
        items_before = self.data_manager.get_content_items()
        count_before = len(items_before)
        
        # 执行时间窗口过滤
        removed_count = self.data_manager.filter_by_time_window(time_window_hours)
        
        # 获取过滤后的项目
        items_after = self.data_manager.get_content_items()
        count_after = len(items_after)
        
        # 验证：移除的数量 + 剩余的数量 = 原始数量
        assert removed_count + count_after == count_before, (
            f"项目数量不匹配：移除 {removed_count} + 剩余 {count_after} "
            f"!= 原始 {count_before}"
        )
        
        # 验证：剩余的所有项目都在时间窗口内
        cutoff_time = datetime.now() - timedelta(hours=time_window_hours)
        for item in items_after:
            assert item.publish_time >= cutoff_time, (
                f"过滤后仍有项目 {item.id} 超出时间窗口：{item.publish_time} < {cutoff_time}"
            )
    
    @given(
        time_window_hours=st.integers(min_value=1, max_value=72)
    )
    @settings(max_examples=30, deadline=None)
    def test_empty_database_time_window_filtering(self, time_window_hours: int):
        """
        属性测试：空数据库的时间窗口过滤
        
        验证在空数据库上执行时间窗口过滤不会出错
        """
        # 确保数据库为空
        items = self.data_manager.get_content_items()
        assert len(items) == 0, "数据库应该为空"
        
        # 执行时间窗口过滤
        removed_count = self.data_manager.filter_by_time_window(time_window_hours)
        
        # 验证：空数据库应该移除0个项目
        assert removed_count == 0, f"空数据库不应该移除任何项目，但移除了 {removed_count} 个"
        
        # 验证：过滤后数据库仍然为空
        items_after = self.data_manager.get_content_items()
        assert len(items_after) == 0, "过滤后数据库应该仍然为空"
    
    @given(
        items=st.lists(
            valid_content_item(),
            min_size=1,
            max_size=10
        ),
        time_window_hours1=st.integers(min_value=1, max_value=24),
        time_window_hours2=st.integers(min_value=25, max_value=72)
    )
    @settings(max_examples=30, deadline=None)
    def test_different_time_windows_consistency(
        self, 
        items: List[ContentItem], 
        time_window_hours1: int, 
        time_window_hours2: int
    ):
        """
        属性测试：不同时间窗口的一致性
        
        验证较大的时间窗口应该包含较小时间窗口的所有项目
        """
        assume(time_window_hours1 < time_window_hours2)
        
        # 添加内容项
        added_count = self.data_manager.add_content_items(items)
        assume(added_count > 0)
        
        # 获取较小时间窗口的项目
        items_small_window = self.data_manager.get_content_items(
            time_window_hours=time_window_hours1
        )
        
        # 获取较大时间窗口的项目
        items_large_window = self.data_manager.get_content_items(
            time_window_hours=time_window_hours2
        )
        
        # 验证：较大时间窗口应该包含较小时间窗口的所有项目
        small_window_ids = {item.id for item in items_small_window}
        large_window_ids = {item.id for item in items_large_window}
        
        assert small_window_ids.issubset(large_window_ids), (
            f"较大时间窗口 ({time_window_hours2}h) 应该包含较小时间窗口 ({time_window_hours1}h) 的所有项目。"
            f"缺失的项目: {small_window_ids - large_window_ids}"
        )
        
        # 验证：较大时间窗口的项目数量应该 >= 较小时间窗口
        assert len(items_large_window) >= len(items_small_window), (
            f"较大时间窗口的项目数量 ({len(items_large_window)}) "
            f"应该 >= 较小时间窗口的项目数量 ({len(items_small_window)})"
        )
    
    @given(
        items=st.lists(
            valid_content_item(),
            min_size=3,
            max_size=15
        ),
        time_window_hours=st.integers(min_value=1, max_value=48)
    )
    @settings(max_examples=30, deadline=None)
    def test_time_window_filtering_idempotency(self, items: List[ContentItem], time_window_hours: int):
        """
        属性测试：时间窗口过滤的幂等性
        
        验证多次执行相同的时间窗口过滤应该产生相同的结果
        """
        # 添加内容项
        added_count = self.data_manager.add_content_items(items)
        assume(added_count > 0)
        
        # 第一次过滤
        removed_count1 = self.data_manager.filter_by_time_window(time_window_hours)
        items_after_first = self.data_manager.get_content_items()
        
        # 第二次过滤（应该不移除任何项目）
        removed_count2 = self.data_manager.filter_by_time_window(time_window_hours)
        items_after_second = self.data_manager.get_content_items()
        
        # 验证：第二次过滤不应该移除任何项目
        assert removed_count2 == 0, (
            f"第二次时间窗口过滤不应该移除任何项目，但移除了 {removed_count2} 个"
        )
        
        # 验证：两次过滤后的项目应该完全相同
        assert len(items_after_first) == len(items_after_second), (
            f"两次过滤后的项目数量不同：{len(items_after_first)} vs {len(items_after_second)}"
        )
        
        # 验证：项目ID集合应该相同
        ids_first = {item.id for item in items_after_first}
        ids_second = {item.id for item in items_after_second}
        assert ids_first == ids_second, "两次过滤后的项目ID集合不同"


if __name__ == "__main__":
    # 运行属性测试
    pytest.main([__file__, "-v", "--tb=short"])