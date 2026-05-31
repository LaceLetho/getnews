"""
已发送消息缓存管理器测试

测试SentMessageCacheManager的核心功能，包括缓存存储、读取和清理。
"""

import pytest
import tempfile
import os
from contextlib import contextmanager

from crypto_news_analyzer.storage.cache_manager import SentMessageCacheManager
from crypto_news_analyzer.models import StorageConfig
from crypto_news_analyzer.utils.errors import StorageError


class TestSentMessageCacheManager:
    """已发送消息缓存管理器测试"""

    def setup_method(self):
        """测试前设置"""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_cache.db")
        self.storage_config = StorageConfig(
            retention_days=30,
            max_storage_mb=1000,
            cleanup_frequency="daily",
            database_path=self.db_path
        )
        self.cache_manager = SentMessageCacheManager(self.storage_config)

    def teardown_method(self):
        """测试后清理"""
        if hasattr(self, 'cache_manager'):
            self.cache_manager.close()

        if os.path.exists(self.db_path):
            os.remove(self.db_path)

        if os.path.exists(self.temp_dir):
            os.rmdir(self.temp_dir)

    def test_cache_manager_initialization(self):
        """测试缓存管理器初始化"""
        assert self.cache_manager is not None
        assert os.path.exists(self.db_path)

        # 验证数据库表已创建
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 检查表是否存在
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='sent_message_cache'
        """)
        result = cursor.fetchone()
        assert result is not None
        assert result[0] == 'sent_message_cache'

        conn.close()

    def test_cache_sent_messages_basic(self):
        """测试基本的消息缓存功能"""
        messages = [
            {
                'summary': '比特币价格突破50000美元',
                'category': '市场新现象',
                'time': '2024-01-15 10:30:00'
            },
            {
                'summary': 'SEC批准比特币ETF',
                'category': '美国政府监管政策',
                'time': '2024-01-15 11:00:00'
            },
            {
                'summary': '某交易所遭受黑客攻击',
                'category': '安全事件',
                'time': '2024-01-15 12:00:00'
            }
        ]

        cached_count = self.cache_manager.cache_sent_messages(messages)

        assert cached_count == 3

    def test_cache_sent_messages_empty_list(self):
        """测试缓存空消息列表"""
        cached_count = self.cache_manager.cache_sent_messages([])
        assert cached_count == 0

    def test_cache_sent_messages_missing_fields(self):
        """测试缓存缺少必需字段的消息"""
        messages = [
            {
                'summary': '完整消息',
                'category': '市场新现象',
                'time': '2024-01-15 10:30:00'
            },
            {
                'summary': '缺少category字段',
                'time': '2024-01-15 11:00:00'
            },
            {
                'category': '缺少summary字段',
                'time': '2024-01-15 12:00:00'
            }
        ]

        cached_count = self.cache_manager.cache_sent_messages(messages)

        # 只有第一条消息应该被成功缓存
        assert cached_count == 1

    def test_get_cached_messages_within_24_hours(self):
        """测试获取24小时内的缓存消息"""
        messages = [
            {
                'summary': '最近的消息1',
                'category': '市场新现象',
                'time': '2024-01-15 10:30:00'
            },
            {
                'summary': '最近的消息2',
                'category': '安全事件',
                'time': '2024-01-15 11:00:00'
            }
        ]

        self.cache_manager.cache_sent_messages(messages)

        cached_messages = self.cache_manager.get_cached_messages(hours=24)

        assert len(cached_messages) == 2
        assert cached_messages[0]['summary'] in ['最近的消息1', '最近的消息2']
        assert all('sent_at' in msg for msg in cached_messages)

    def test_get_cached_messages_custom_time_range(self):
        """测试获取自定义时间范围的缓存消息"""
        # 先缓存一些消息
        messages = [
            {
                'summary': '消息1',
                'category': '市场新现象',
                'time': '2024-01-15 10:30:00'
            }
        ]

        self.cache_manager.cache_sent_messages(messages)

        # 测试不同的时间范围
        cached_1h = self.cache_manager.get_cached_messages(hours=1)
        cached_24h = self.cache_manager.get_cached_messages(hours=24)
        cached_48h = self.cache_manager.get_cached_messages(hours=48)

        # 所有时间范围都应该包含刚缓存的消息
        assert len(cached_1h) == 1
        assert len(cached_24h) == 1
        assert len(cached_48h) == 1

    def test_get_cached_messages_empty_cache(self):
        """测试从空缓存获取消息"""
        cached_messages = self.cache_manager.get_cached_messages(hours=24)
        assert len(cached_messages) == 0

    def test_cleanup_expired_cache(self):
        """测试清理过期缓存"""
        # 缓存一些消息
        messages = [
            {
                'summary': '消息1',
                'category': '市场新现象',
                'time': '2024-01-15 10:30:00'
            },
            {
                'summary': '消息2',
                'category': '安全事件',
                'time': '2024-01-15 11:00:00'
            }
        ]

        self.cache_manager.cache_sent_messages(messages)

        # 验证消息已缓存
        cached_before = self.cache_manager.get_cached_messages(hours=24)
        assert len(cached_before) == 2

        # 清理24小时内的缓存（应该删除所有消息）
        deleted_count = self.cache_manager.cleanup_expired_cache(hours=24)

        # 由于消息是刚刚缓存的，不应该被删除
        assert deleted_count == 0

        # 清理0小时内的缓存（应该删除所有消息）
        deleted_count = self.cache_manager.cleanup_expired_cache(hours=0)
        assert deleted_count == 2

        # 验证缓存已清空
        cached_after = self.cache_manager.get_cached_messages(hours=24)
        assert len(cached_after) == 0

    def test_cleanup_expired_cache_empty(self):
        """测试清理空缓存"""
        deleted_count = self.cache_manager.cleanup_expired_cache(hours=24)
        assert deleted_count == 0

    def test_get_cache_statistics(self):
        """测试获取缓存统计信息"""
        # 缓存不同分类的消息
        messages = [
            {
                'summary': '消息1',
                'category': '市场新现象',
                'time': '2024-01-15 10:30:00'
            },
            {
                'summary': '消息2',
                'category': '市场新现象',
                'time': '2024-01-15 11:00:00'
            },
            {
                'summary': '消息3',
                'category': '安全事件',
                'time': '2024-01-15 12:00:00'
            }
        ]

        self.cache_manager.cache_sent_messages(messages)

        stats = self.cache_manager.get_cache_statistics()

        assert stats['total_cached_messages'] == 3
        assert stats['messages_last_24h'] == 3
        assert '市场新现象' in stats['category_distribution']
        assert stats['category_distribution']['市场新现象'] == 2
        assert stats['category_distribution']['安全事件'] == 1
        assert stats['earliest_cache'] is not None
        assert stats['latest_cache'] is not None

    def test_get_cache_statistics_empty(self):
        """测试空缓存的统计信息"""
        stats = self.cache_manager.get_cache_statistics()

        assert stats['total_cached_messages'] == 0
        assert stats['messages_last_24h'] == 0
        assert len(stats['category_distribution']) == 0
        assert stats['earliest_cache'] is None
        assert stats['latest_cache'] is None

    def test_clear_all_cache(self):
        """测试清空所有缓存"""
        messages = [
            {
                'summary': '消息1',
                'category': '市场新现象',
                'time': '2024-01-15 10:30:00'
            },
            {
                'summary': '消息2',
                'category': '安全事件',
                'time': '2024-01-15 11:00:00'
            }
        ]

        self.cache_manager.cache_sent_messages(messages)

        # 验证消息已缓存
        cached_before = self.cache_manager.get_cached_messages(hours=24)
        assert len(cached_before) == 2

        # 清空所有缓存
        deleted_count = self.cache_manager.clear_all_cache()
        assert deleted_count == 2

        # 验证缓存已清空
        cached_after = self.cache_manager.get_cached_messages(hours=24)
        assert len(cached_after) == 0

    def test_context_manager(self):
        """测试上下文管理器功能"""
        with SentMessageCacheManager(self.storage_config) as cache_mgr:
            messages = [
                {
                    'summary': '测试消息',
                    'category': '市场新现象',
                    'time': '2024-01-15 10:30:00'
                }
            ]
            cached_count = cache_mgr.cache_sent_messages(messages)
            assert cached_count == 1

        # 上下文管理器退出后，连接应该已关闭
        # 创建新的管理器验证数据已保存
        new_cache_mgr = SentMessageCacheManager(self.storage_config)
        cached_messages = new_cache_mgr.get_cached_messages(hours=24)
        assert len(cached_messages) == 1
        new_cache_mgr.close()

    def test_thread_safety(self):
        """测试线程安全性"""
        import threading

        def cache_messages(thread_id):
            messages = [
                {
                    'summary': f'线程{thread_id}的消息',
                    'category': '市场新现象',
                    'time': f'2024-01-15 10:{thread_id:02d}:00'
                }
            ]
            self.cache_manager.cache_sent_messages(messages)

        threads = []
        for i in range(10):
            thread = threading.Thread(target=cache_messages, args=(i,))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        # 验证所有消息都已缓存
        cached_messages = self.cache_manager.get_cached_messages(hours=24)
        assert len(cached_messages) == 10

    def test_cache_messages_with_special_characters(self):
        """测试缓存包含特殊字符的消息"""
        messages = [
            {
                'summary': '消息包含特殊字符: <>&"\'',
                'category': '市场新现象',
                'time': '2024-01-15 10:30:00'
            },
            {
                'summary': '消息包含中文标点：，。！？',
                'category': '安全事件',
                'time': '2024-01-15 11:00:00'
            },
            {
                'summary': '消息包含emoji: 🚀💰📈',
                'category': '新产品',
                'time': '2024-01-15 12:00:00'
            }
        ]

        cached_count = self.cache_manager.cache_sent_messages(messages)
        assert cached_count == 3

        cached_messages = self.cache_manager.get_cached_messages(hours=24)
        assert len(cached_messages) == 3

        # 验证特殊字符被正确保存和读取
        summaries = [msg['summary'] for msg in cached_messages]
        assert any('<>&"\'' in s for s in summaries)
        assert any('，。！？' in s for s in summaries)
        assert any('🚀💰📈' in s for s in summaries)

    def test_cache_messages_with_long_content(self):
        """测试缓存长内容消息"""
        long_summary = '这是一条很长的消息摘要。' * 100  # 创建一个很长的摘要

        messages = [
            {
                'summary': long_summary,
                'category': '市场新现象',
                'time': '2024-01-15 10:30:00'
            }
        ]

        cached_count = self.cache_manager.cache_sent_messages(messages)
        assert cached_count == 1

        cached_messages = self.cache_manager.get_cached_messages(hours=24)
        assert len(cached_messages) == 1
        assert cached_messages[0]['summary'] == long_summary

    def test_multiple_cache_operations(self):
        """测试多次缓存操作"""
        # 第一次缓存
        messages1 = [
            {
                'summary': '第一批消息1',
                'category': '市场新现象',
                'time': '2024-01-15 10:30:00'
            }
        ]
        self.cache_manager.cache_sent_messages(messages1)

        # 第二次缓存
        messages2 = [
            {
                'summary': '第二批消息1',
                'category': '安全事件',
                'time': '2024-01-15 11:00:00'
            },
            {
                'summary': '第二批消息2',
                'category': '新产品',
                'time': '2024-01-15 11:30:00'
            }
        ]
        self.cache_manager.cache_sent_messages(messages2)

        # 验证所有消息都已缓存
        cached_messages = self.cache_manager.get_cached_messages(hours=24)
        assert len(cached_messages) == 3

        # 验证消息内容
        summaries = [msg['summary'] for msg in cached_messages]
        assert '第一批消息1' in summaries
        assert '第二批消息1' in summaries
        assert '第二批消息2' in summaries

    def test_format_cached_messages_for_prompt(self):
        """测试格式化缓存消息为提示词文本"""
        messages = [
            {
                'summary': '比特币价格突破50000美元',
                'category': 'BlackSwan',
                'time': '2024-01-15 10:30'
            },
            {
                'summary': 'SEC批准比特币ETF',
                'category': 'Regulation',
                'time': '2024-01-15 11:00'
            },
            {
                'summary': '某交易所遭受黑客攻击',
                'category': 'Security',
                'time': '2024-01-15 12:00'
            }
        ]

        self.cache_manager.cache_sent_messages(messages)

        formatted = self.cache_manager.format_cached_messages_for_prompt(hours=24)

        # 验证格式
        assert formatted != "无"
        lines = formatted.split('\n')
        assert len(lines) == 3

        # 验证每行格式: - [时间] [分类] 摘要
        for line in lines:
            assert line.startswith('- [')
            assert '] [' in line
            assert line.count('[') == 2
            assert line.count(']') == 2

        # 验证内容存在
        assert '比特币价格突破50000美元' in formatted
        assert 'SEC批准比特币ETF' in formatted
        assert '某交易所遭受黑客攻击' in formatted
        assert 'BlackSwan' in formatted
        assert 'Regulation' in formatted
        assert 'Security' in formatted

    def test_format_cached_messages_empty_cache(self):
        """测试格式化空缓存"""
        formatted = self.cache_manager.format_cached_messages_for_prompt(hours=24)
        assert formatted == "无"

    def test_format_cached_messages_custom_time_range(self):
        """测试格式化自定义时间范围的缓存消息"""
        messages = [
            {
                'summary': '消息1',
                'category': 'BlackSwan',
                'time': '2024-01-15 10:30'
            },
            {
                'summary': '消息2',
                'category': 'Whale',
                'time': '2024-01-15 11:00'
            }
        ]

        self.cache_manager.cache_sent_messages(messages)

        # 测试不同时间范围
        formatted_1h = self.cache_manager.format_cached_messages_for_prompt(hours=1)
        formatted_24h = self.cache_manager.format_cached_messages_for_prompt(hours=24)

        # 所有时间范围都应该包含消息
        assert formatted_1h != "无"
        assert formatted_24h != "无"
        assert '消息1' in formatted_24h
        assert '消息2' in formatted_24h


class _CacheFakeConnection:
    def __init__(self, executed):
        self._executed = executed
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def cursor(self):
        c = _CacheFakeCursor(self._executed)
        return c

    def execute(self, query, params=None):
        self._executed.append((query, params))

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


class _CacheFakeCursor:
    def __init__(self, executed):
        self._executed = executed

    def execute(self, query, params=None):
        self._executed.append((query, params))

    def fetchone(self):
        return None

    def fetchall(self):
        return []


@contextmanager
def _cache_retrying_helper(executed, call_counter, fail_on_attempts=1):
    call_counter["helper_calls"] += 1
    for _ in range(fail_on_attempts):
        call_counter["connect_attempts"] += 1
    call_counter["connect_attempts"] += 1
    conn = _CacheFakeConnection(executed)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def test_cache_manager_postgres_delegates_to_retry_helper_on_failure(monkeypatch):
    executed = []
    call_counter = {"helper_calls": 0, "connect_attempts": 0}

    def mock_helper(database_url, *, row_factory=None, config=None, logger=None):
        return _cache_retrying_helper(executed, call_counter, fail_on_attempts=1)

    monkeypatch.setattr(
        "crypto_news_analyzer.storage.cache_manager.connect_postgres_with_retry",
        mock_helper,
    )

    manager = SentMessageCacheManager(
        StorageConfig(
            backend="postgres",
            database_url="postgresql://user:pass@localhost:5432/db",
        )
    )

    assert manager.backend == "postgres"
    assert call_counter == {"helper_calls": 1, "connect_attempts": 2}
    assert any("sent_message_cache" in str(q) for q, _ in executed)


def test_cache_manager_postgres_all_attempts_exhausted(monkeypatch):
    call_counter = {"calls": 0}

    def mock_helper_always_fail(
        database_url, *, row_factory=None, config=None, logger=None
    ):
        call_counter["calls"] += 1
        import psycopg

        raise psycopg.OperationalError("connection refused (persistent)")

    monkeypatch.setattr(
        "crypto_news_analyzer.storage.cache_manager.connect_postgres_with_retry",
        mock_helper_always_fail,
    )

    with pytest.raises(StorageError, match="connection refused"):
        SentMessageCacheManager(
            StorageConfig(
                backend="postgres",
                database_url="postgresql://user:pass@localhost:5432/db",
            )
        )

    assert call_counter["calls"] == 1


def test_cache_manager_postgres_uses_retry_helper(monkeypatch):
    executed = []
    fake_conn = _CacheFakeConnection(executed)

    def fake_connect(*_args, **_kwargs):
        @contextmanager
        def ctx():
            yield fake_conn
        return ctx()

    monkeypatch.setattr(
        "crypto_news_analyzer.storage.cache_manager.connect_postgres_with_retry",
        fake_connect,
    )

    config = StorageConfig(
        backend="postgres",
        database_url="postgresql://user:pass@localhost:5432/db",
    )
    manager = SentMessageCacheManager(config)

    with manager._get_connection() as conn:
        assert conn is fake_conn


def test_cache_manager_postgres_retry_error_wrapped_in_storage_error(monkeypatch):
    def failing_connect(*_args, **_kwargs):
        @contextmanager
        def ctx():
            raise RuntimeError("connection refused")
        return ctx()

    monkeypatch.setattr(
        "crypto_news_analyzer.storage.cache_manager.connect_postgres_with_retry",
        failing_connect,
    )

    config = StorageConfig(
        backend="postgres",
        database_url="postgresql://user:pass@localhost:5432/db",
    )

    with pytest.raises(StorageError) as exc_info:
        SentMessageCacheManager(config)

    assert "数据库操作失败" in str(exc_info.value)
    assert exc_info.value.details["operation"] == "database_operation"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
