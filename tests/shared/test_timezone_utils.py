"""
测试时区工具模块

验证所有时间格式化功能使用东八区(UTC+8)时区。
"""

import unittest
from datetime import datetime, timezone, timedelta

from crypto_news_analyzer.utils.timezone_utils import (
    now_utc8,
    format_datetime_utc8,
    format_datetime_short_utc8,
    format_datetime_full_utc8,
    convert_to_utc8,
    UTC_PLUS_8
)


class TestTimezoneUtils(unittest.TestCase):
    """测试时区工具函数"""
    
    def test_utc_plus_8_timezone(self):
        """测试UTC+8时区对象"""
        expected_offset = timedelta(hours=8)
        self.assertEqual(UTC_PLUS_8.utcoffset(None), expected_offset)
    
    def test_now_utc8_returns_timezone_aware(self):
        """测试now_utc8返回带时区信息的datetime"""
        result = now_utc8()
        
        self.assertIsNotNone(result.tzinfo)
        self.assertEqual(result.tzinfo, UTC_PLUS_8)
    
    def test_format_datetime_utc8_with_none(self):
        """测试format_datetime_utc8使用None参数（当前时间）"""
        result = format_datetime_utc8(None)
        
        # 验证格式正确（默认格式：YYYY-MM-DD HH:MM:SS）
        self.assertRegex(result, r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}')
    
    def test_format_datetime_utc8_with_datetime(self):
        """测试format_datetime_utc8使用指定datetime"""
        # 创建一个UTC时间
        utc_time = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        
        # 格式化为UTC+8（应该是18:30）
        result = format_datetime_utc8(utc_time)
        
        # 验证时间已转换为UTC+8
        self.assertIn("18:30:00", result)
        self.assertIn("2024-01-15", result)
    
    def test_format_datetime_utc8_with_naive_datetime(self):
        """测试format_datetime_utc8使用无时区信息的datetime"""
        # 创建一个无时区信息的datetime
        naive_time = datetime(2024, 1, 15, 10, 30, 0)
        
        # 应该假设为UTC并转换为UTC+8
        result = format_datetime_utc8(naive_time)
        
        # 验证格式正确
        self.assertRegex(result, r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}')
    
    def test_format_datetime_short_utc8(self):
        """测试短格式时间（不含年份）"""
        utc_time = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        
        result = format_datetime_short_utc8(utc_time)
        
        # 验证格式：MM-DD HH:MM
        self.assertRegex(result, r'\d{2}-\d{2} \d{2}:\d{2}')
        self.assertIn("01-15", result)
        self.assertIn("18:30", result)  # UTC 10:30 -> UTC+8 18:30
    
    def test_format_datetime_full_utc8(self):
        """测试完整格式时间"""
        utc_time = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        
        result = format_datetime_full_utc8(utc_time)
        
        # 验证格式：YYYY-MM-DD HH:MM:SS
        self.assertEqual(result, "2024-01-15 18:30:00")
    
    def test_convert_to_utc8_from_utc(self):
        """测试从UTC转换到UTC+8"""
        utc_time = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        
        result = convert_to_utc8(utc_time)
        
        self.assertEqual(result.tzinfo, UTC_PLUS_8)
        self.assertEqual(result.hour, 18)  # UTC 10:30 -> UTC+8 18:30
        self.assertEqual(result.minute, 30)
    
    def test_convert_to_utc8_from_naive(self):
        """测试从无时区信息的datetime转换到UTC+8"""
        naive_time = datetime(2024, 1, 15, 10, 30, 0)
        
        result = convert_to_utc8(naive_time)
        
        self.assertEqual(result.tzinfo, UTC_PLUS_8)
        # 无时区信息的datetime被假设为UTC，然后转换为UTC+8
        self.assertEqual(result.hour, 18)
    
    def test_custom_format_string(self):
        """测试自定义格式字符串"""
        utc_time = datetime(2024, 1, 15, 10, 30, 45, tzinfo=timezone.utc)
        
        result = format_datetime_utc8(utc_time, "%Y年%m月%d日 %H时%M分")
        
        self.assertEqual(result, "2024年01月15日 18时30分")
    
    def test_timezone_consistency(self):
        """测试时区一致性：多次调用应该使用相同的时区"""
        time1 = now_utc8()
        time2 = now_utc8()
        
        self.assertEqual(time1.tzinfo, time2.tzinfo)
        self.assertEqual(time1.tzinfo, UTC_PLUS_8)


if __name__ == '__main__':
    unittest.main()
