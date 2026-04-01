"""
已发送消息缓存管理器

负责管理已发送消息的缓存，用于避免重复发送相同内容。
"""

import sqlite3
import threading
from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Dict, Any, Tuple, cast
from contextlib import contextmanager
from pathlib import Path

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:
    psycopg = None
    dict_row = None

from ..models import StorageConfig
from ..utils.logging import get_log_manager
from ..utils.errors import StorageError

logger = get_log_manager().get_logger(__name__)
RECIPIENT_CACHE_LOOKBACK_HOURS = 48


class SentMessageCacheManager:
    """已发送消息缓存管理器类"""

    def __init__(self, storage_config: StorageConfig):
        """
        初始化缓存管理器

        Args:
            storage_config: 存储配置
        """
        self.config = storage_config
        self.backend = storage_config.backend
        self.db_path = storage_config.database_path
        self.database_url = storage_config.database_url
        self._lock = threading.RLock()  # 线程安全锁
        self._connection_pool: Dict[int, sqlite3.Connection] = {}  # 简单的连接池

        if self.backend == "sqlite":
            self._ensure_database_directory()
        elif self.backend == "postgres":
            if psycopg is None:
                raise StorageError(
                    "PostgreSQL backend requires psycopg package",
                    operation="cache_initialization",
                )
            if not self.database_url:
                raise StorageError(
                    "PostgreSQL backend requires database_url",
                    operation="cache_initialization",
                )

        # 初始化缓存表
        self._initialize_cache_table()

        logger.info(
            f"缓存管理器初始化完成，后端: {self.backend}, "
            f"数据库: {self.db_path if self.backend == 'sqlite' else 'postgres'}"
        )

    def _ensure_database_directory(self) -> None:
        """确保数据库目录存在"""
        db_dir = Path(self.db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)

    def _initialize_cache_table(self) -> None:
        """初始化缓存表结构"""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            if self.backend == "postgres":
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS sent_message_cache (
                        id BIGSERIAL PRIMARY KEY,
                        title TEXT NOT NULL,
                        body TEXT NOT NULL,
                        category TEXT NOT NULL,
                        time TEXT NOT NULL,
                        sent_at TIMESTAMPTZ NOT NULL,
                        recipient_key TEXT,
                        created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                    )
                """)
            else:
                cursor.execute("""
                    SELECT name FROM sqlite_master
                    WHERE type='table' AND name='sent_message_cache'
                """)
                table_exists = cursor.fetchone() is not None

                if table_exists:
                    cursor.execute("PRAGMA table_info(sent_message_cache)")
                    columns = {row[1] for row in cursor.fetchall()}

                    if "summary" in columns and "title" not in columns:
                        logger.info("检测到旧表结构，开始迁移...")
                        self._migrate_summary_to_title_body(conn)
                        logger.info("表结构迁移完成")
                        cursor.execute("PRAGMA table_info(sent_message_cache)")
                        columns = {row[1] for row in cursor.fetchall()}

                    if "recipient_key" not in columns:
                        cursor.execute(
                            "ALTER TABLE sent_message_cache ADD COLUMN recipient_key TEXT"
                        )
                else:
                    cursor.execute("""
                        CREATE TABLE sent_message_cache (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            title TEXT NOT NULL,
                            body TEXT NOT NULL,
                            category TEXT NOT NULL,
                            time TEXT NOT NULL,
                            sent_at DATETIME NOT NULL,
                            recipient_key TEXT,
                            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                        )
                    """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_sent_at 
                ON sent_message_cache (sent_at)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_category 
                ON sent_message_cache (category)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_recipient_key_sent_at
                ON sent_message_cache (recipient_key, sent_at)
            """)

            conn.commit()
            logger.info("缓存表结构初始化完成")

    def _migrate_summary_to_title_body(self, conn: sqlite3.Connection) -> None:
        """迁移旧表结构：将 summary 列拆分为 title 和 body"""
        cursor = conn.cursor()

        try:
            # 1. 创建新表
            cursor.execute("""
                CREATE TABLE sent_message_cache_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    body TEXT NOT NULL,
                    category TEXT NOT NULL,
                    time TEXT NOT NULL,
                    sent_at DATETIME NOT NULL,
                    recipient_key TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 2. 迁移数据：将 summary 同时作为 title 和 body
            cursor.execute("""
                INSERT INTO sent_message_cache_new 
                    (id, title, body, category, time, sent_at, recipient_key, created_at)
                SELECT 
                    id, 
                    summary as title, 
                    summary as body, 
                    category, 
                    time, 
                    sent_at,
                    NULL as recipient_key,
                    created_at
                FROM sent_message_cache
            """)

            # 3. 删除旧表
            cursor.execute("DROP TABLE sent_message_cache")

            # 4. 重命名新表
            cursor.execute("ALTER TABLE sent_message_cache_new RENAME TO sent_message_cache")

            conn.commit()
            logger.info("成功迁移 sent_message_cache 表结构")

        except Exception as e:
            conn.rollback()
            logger.error(f"迁移表结构失败: {e}")
            raise

    @contextmanager
    def _get_connection(self) -> Iterator[Any]:
        """获取数据库连接（上下文管理器）"""
        if self.backend == "postgres":
            conn = None
            try:
                conn = psycopg.connect(self.database_url, row_factory=dict_row)
                yield conn
                conn.commit()
            except Exception as e:
                if conn is not None:
                    conn.rollback()
                logger.error(f"数据库操作失败: {e}")
                raise StorageError(f"数据库操作失败: {e}", operation="database_operation")
            finally:
                if conn is not None:
                    conn.close()
            return

        thread_id = threading.get_ident()

        if thread_id not in self._connection_pool:
            conn = sqlite3.connect(self.db_path, check_same_thread=False, timeout=30.0)
            conn.row_factory = sqlite3.Row  # 启用字典式访问
            self._connection_pool[thread_id] = conn

        conn = self._connection_pool[thread_id]

        try:
            yield conn
        except Exception as e:
            conn.rollback()
            logger.error(f"数据库操作失败: {e}")
            raise StorageError(f"数据库操作失败: {e}", operation="database_operation")
        finally:
            # 不在这里关闭连接，保持连接池
            pass

    def _sql(self, query: str) -> str:
        if self.backend == "postgres":
            return query.replace("?", "%s")
        return query

    def _normalize_cache_message(
        self,
        message: Dict[str, Any],
    ) -> Optional[Tuple[str, str, str, str]]:
        if all(key in message for key in ["title", "body", "category", "time"]):
            return (
                cast(str, message["title"]),
                cast(str, message["body"]),
                cast(str, message["category"]),
                cast(str, message["time"]),
            )

        if all(key in message for key in ["summary", "category", "time"]):
            summary = cast(str, message["summary"])
            return (
                summary,
                summary,
                cast(str, message["category"]),
                cast(str, message["time"]),
            )

        return None

    def cache_sent_messages(
        self,
        messages: List[Dict[str, Any]],
        recipient_key: Optional[str] = None,
    ) -> int:
        """
        缓存已发送的消息

        Args:
            messages: 消息列表，每个消息包含 title, body, category, time 字段

        Returns:
            成功缓存的消息数量
        """
        if not messages:
            logger.info("没有消息需要缓存")
            return 0

        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cached_count = 0
                sent_at = datetime.now(timezone.utc)

                for message in messages:
                    try:
                        normalized_message = self._normalize_cache_message(message)
                        if normalized_message is None:
                            logger.warning(f"消息缺少必需字段，跳过: {message}")
                            continue
                        title, body, category, time_text = normalized_message

                        cursor.execute(
                            self._sql("""
                            INSERT INTO sent_message_cache 
                            (title, body, category, time, sent_at, recipient_key)
                            VALUES (?, ?, ?, ?, ?, ?)
                        """),
                            (
                                title,
                                body,
                                category,
                                time_text,
                                sent_at.isoformat(),
                                recipient_key,
                            ),
                        )

                        cached_count += 1

                    except Exception as e:
                        logger.warning(f"缓存消息失败: {e}, 消息: {message}")
                        continue

                conn.commit()
                logger.info(f"成功缓存 {cached_count}/{len(messages)} 条消息")
                return cached_count

    def get_cached_messages(self, hours: int = 24) -> List[Dict[str, Any]]:
        """
        获取指定时间范围内的缓存消息

        Args:
            hours: 时间范围（小时），默认24小时

        Returns:
            缓存消息列表，每条消息包含 title, body, category, time, sent_at 字段
        """
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)

        with self._get_connection() as conn:
            cursor = conn.cursor()

            if self.backend == "postgres":
                cursor.execute(
                    self._sql("""
                        SELECT title, body, category, time, sent_at
                        FROM sent_message_cache
                        WHERE recipient_key IS NULL
                          AND sent_at >= ?
                        ORDER BY sent_at DESC, id DESC
                        """),
                    (cutoff_time.isoformat(),),
                )
            else:
                cursor.execute(
                    self._sql("""
                        SELECT title, body, category, time, sent_at
                        FROM sent_message_cache
                        WHERE recipient_key IS NULL
                          AND julianday(sent_at) >= julianday(?)
                        ORDER BY julianday(sent_at) DESC, id DESC
                        """),
                    (cutoff_time.isoformat(),),
                )

            rows = cursor.fetchall()

            # 转换为字典列表
            messages = []
            for row in rows:
                try:
                    messages.append(
                        {
                            "title": row["title"],
                            "summary": row["title"],
                            "body": row["body"],
                            "category": row["category"],
                            "time": row["time"],
                            "sent_at": row["sent_at"],
                        }
                    )
                except Exception as e:
                    logger.warning(f"解析缓存消息失败: {e}")
                    continue

            logger.info(f"获取到 {len(messages)} 条缓存消息（{hours}小时内）")
            return messages

    def get_recipient_cached_titles(
        self,
        recipient_key: str,
        anchor_time: datetime,
    ) -> List[str]:
        if not recipient_key:
            logger.info("recipient_key 为空，返回空标题列表")
            return []

        if anchor_time.tzinfo is None:
            anchor_time_utc = anchor_time.replace(tzinfo=timezone.utc)
        else:
            anchor_time_utc = anchor_time.astimezone(timezone.utc)

        window_start = anchor_time_utc - timedelta(hours=RECIPIENT_CACHE_LOOKBACK_HOURS)

        with self._get_connection() as conn:
            cursor = conn.cursor()

            if self.backend == "postgres":
                cursor.execute(
                    self._sql("""
                        SELECT title
                        FROM sent_message_cache
                        WHERE recipient_key = ?
                          AND sent_at >= ?
                          AND sent_at <= ?
                        ORDER BY sent_at ASC, id ASC
                        """),
                    (recipient_key, window_start.isoformat(), anchor_time_utc.isoformat()),
                )
            else:
                cursor.execute(
                    self._sql("""
                        SELECT title
                        FROM sent_message_cache
                        WHERE recipient_key = ?
                          AND julianday(sent_at) >= julianday(?)
                          AND julianday(sent_at) <= julianday(?)
                        ORDER BY julianday(sent_at) ASC, id ASC
                        """),
                    (recipient_key, window_start.isoformat(), anchor_time_utc.isoformat()),
                )

            titles = [row["title"] for row in cursor.fetchall()]
            logger.info(f"获取到 {len(titles)} 条收件人缓存标题，recipient_key={recipient_key}")
            return titles

    def cleanup_expired_cache(self, hours: int = 24) -> int:
        """
        清理过期的缓存记录

        Args:
            hours: 保留时间（小时），默认24小时

        Returns:
            删除的记录数量
        """
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)

        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                if self.backend == "postgres":
                    cursor.execute(
                        self._sql("""
                            DELETE FROM sent_message_cache
                            WHERE sent_at < ?
                            """),
                        (cutoff_time.isoformat(),),
                    )
                else:
                    cursor.execute(
                        self._sql("""
                            DELETE FROM sent_message_cache
                            WHERE julianday(sent_at) < julianday(?)
                            """),
                        (cutoff_time.isoformat(),),
                    )

                deleted_count = cast(int, cursor.rowcount)
                conn.commit()

                logger.info(f"清理过期缓存完成，删除了 {deleted_count} 条记录")
                return deleted_count

    def format_cached_messages_for_prompt(self, hours: int = 24) -> str:
        """
        格式化缓存消息为提示词文本

        格式: - [时间] [分类] 摘要

        Args:
            hours: 时间范围（小时），默认24小时

        Returns:
            格式化后的文本，如果没有缓存则返回"无"
        """
        messages = self.get_cached_messages(hours=hours)

        if not messages:
            return "无"

        formatted_lines = []
        for message in messages:
            try:
                # 格式: - [时间] [分类] 标题
                line = f"- [{message['time']}] [{message['category']}] {message['title']}"
                formatted_lines.append(line)
            except Exception as e:
                logger.warning(f"格式化缓存消息失败: {e}, 消息: {message}")
                continue

        if not formatted_lines:
            return "无"

        result = "\n".join(formatted_lines)
        logger.info(f"格式化了 {len(formatted_lines)} 条缓存消息用于提示词")
        return result

    def get_cache_statistics(self) -> Dict[str, Any]:
        """
        获取缓存统计信息

        Returns:
            统计信息字典
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*) AS total_count FROM sent_message_cache")
            total_row = cursor.fetchone()
            total_count = total_row[0] if self.backend == "sqlite" else total_row["total_count"]

            cutoff_24h = datetime.now(timezone.utc) - timedelta(hours=24)
            if self.backend == "postgres":
                cursor.execute(
                    self._sql("""
                        SELECT COUNT(*) AS total_count FROM sent_message_cache
                        WHERE sent_at >= ?
                        """),
                    (cutoff_24h.isoformat(),),
                )
                count_row = cursor.fetchone()
                count_24h = count_row["total_count"]

                cursor.execute(
                    self._sql("""
                        SELECT category, COUNT(*) as count
                        FROM sent_message_cache
                        WHERE sent_at >= ?
                        GROUP BY category
                        ORDER BY count DESC
                        """),
                    (cutoff_24h.isoformat(),),
                )
            else:
                cursor.execute(
                    self._sql("""
                        SELECT COUNT(*) AS total_count FROM sent_message_cache
                        WHERE julianday(sent_at) >= julianday(?)
                        """),
                    (cutoff_24h.isoformat(),),
                )
                count_row = cursor.fetchone()
                count_24h = count_row[0]

                cursor.execute(
                    self._sql("""
                        SELECT category, COUNT(*) as count
                        FROM sent_message_cache
                        WHERE julianday(sent_at) >= julianday(?)
                        GROUP BY category
                        ORDER BY count DESC
                        """),
                    (cutoff_24h.isoformat(),),
                )

            category_stats = {}
            for row in cursor.fetchall():
                category_stats[row["category"]] = row["count"]

            cursor.execute("""
                SELECT MIN(sent_at), MAX(sent_at) 
                FROM sent_message_cache
            """)
            time_range = cursor.fetchone()

            if self.backend == "sqlite":
                earliest_cache = time_range[0] if time_range and time_range[0] else None
                latest_cache = time_range[1] if time_range and time_range[1] else None
            else:
                earliest_cache = time_range.get("min") if time_range else None
                latest_cache = time_range.get("max") if time_range else None

            return {
                "total_cached_messages": total_count,
                "messages_last_24h": count_24h,
                "category_distribution": category_stats,
                "earliest_cache": earliest_cache,
                "latest_cache": latest_cache,
            }

    def clear_all_cache(self) -> int:
        """
        清空所有缓存（谨慎使用）

        Returns:
            删除的记录数量
        """
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("DELETE FROM sent_message_cache")
                deleted_count = cast(int, cursor.rowcount)
                conn.commit()

                logger.warning(f"清空所有缓存，删除了 {deleted_count} 条记录")
                return deleted_count

    def close(self) -> None:
        """关闭缓存管理器，清理资源"""
        with self._lock:
            for conn in self._connection_pool.values():
                try:
                    conn.close()
                except Exception as e:
                    logger.warning(f"关闭数据库连接失败: {e}")

            self._connection_pool.clear()
            logger.info("缓存管理器已关闭")

    def __enter__(self):
        """上下文管理器入口"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.close()
