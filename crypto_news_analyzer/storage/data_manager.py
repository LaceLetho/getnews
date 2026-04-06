"""
数据管理器

负责SQLite数据库的管理，包括数据存储、去重、时间过滤和清理机制。
"""

import sqlite3
import os
import json
import threading
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple
from contextlib import contextmanager
from pathlib import Path

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:
    psycopg = None
    dict_row = None

from ..models import ContentItem, CrawlStatus, StorageConfig
from ..domain.models import ACTIVE_INGESTION_JOB_STATUSES, DataSource
from ..utils.logging import get_log_manager
from ..utils.errors import StorageError

logger = get_log_manager().get_logger(__name__)


class DataManager:
    """数据管理器类"""

    def __init__(self, storage_config: StorageConfig):
        """
        初始化数据管理器

        Args:
            storage_config: 存储配置
        """
        self.config = storage_config
        self.backend = storage_config.backend
        self.db_path = storage_config.database_path
        self.database_url = storage_config.database_url
        self._lock = threading.RLock()  # 线程安全锁
        self._connection_pool = {}  # 简单的连接池

        if self.backend == "sqlite":
            self._ensure_database_directory()
        elif self.backend == "postgres":
            if psycopg is None:
                raise StorageError(
                    "PostgreSQL backend requires psycopg package",
                    operation="database_initialization",
                )
            if not self.database_url:
                raise StorageError(
                    "PostgreSQL backend requires database_url",
                    operation="database_initialization",
                )

        # 初始化数据库
        self._initialize_database()

        logger.info(
            f"数据管理器初始化完成，后端: {self.backend}, "
            f"数据库: {self.db_path if self.backend == 'sqlite' else 'postgres'}"
        )

    def _ensure_database_directory(self) -> None:
        """确保数据库目录存在"""
        db_dir = Path(self.db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)

    def _initialize_database(self) -> None:
        """初始化数据库表结构"""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            if self.backend == "postgres":
                cursor.execute("CREATE EXTENSION IF NOT EXISTS vector")
                cursor.execute(f"""
                    CREATE TABLE IF NOT EXISTS content_items (
                        id TEXT PRIMARY KEY,
                        title TEXT NOT NULL,
                        content TEXT NOT NULL,
                        url TEXT UNIQUE NOT NULL,
                        publish_time TIMESTAMPTZ NOT NULL,
                        source_name TEXT NOT NULL,
                        source_type TEXT NOT NULL,
                        content_hash TEXT NOT NULL,
                        embedding vector({self.config.pgvector_dimensions}),
                        created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                    )
                    """)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS crawl_status (
                        id BIGSERIAL PRIMARY KEY,
                        execution_time TIMESTAMPTZ NOT NULL,
                        total_items INTEGER NOT NULL,
                        rss_results JSONB NOT NULL,
                        x_results JSONB NOT NULL,
                        created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                    )
                    """)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS analysis_execution_log (
                        id BIGSERIAL PRIMARY KEY,
                        chat_id TEXT NOT NULL,
                        execution_time TIMESTAMPTZ NOT NULL,
                        time_window_hours INTEGER NOT NULL,
                        items_count INTEGER NOT NULL,
                        success BOOLEAN NOT NULL,
                        error_message TEXT,
                        created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                    )
                    """)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS analysis_jobs (
                        id TEXT PRIMARY KEY,
                        recipient_key TEXT NOT NULL,
                        time_window_hours INTEGER NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL,
                        status TEXT NOT NULL,
                        priority INTEGER NOT NULL DEFAULT 5,
                        started_at TIMESTAMPTZ,
                        completed_at TIMESTAMPTZ,
                        result TEXT,
                        error_message TEXT,
                        source TEXT NOT NULL DEFAULT 'api'
                    )
                    """)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS ingestion_jobs (
                        id TEXT PRIMARY KEY,
                        source_type TEXT NOT NULL,
                        source_name TEXT NOT NULL,
                        scheduled_at TIMESTAMPTZ NOT NULL,
                        status TEXT NOT NULL,
                        started_at TIMESTAMPTZ,
                        completed_at TIMESTAMPTZ,
                        items_crawled INTEGER NOT NULL DEFAULT 0,
                        items_new INTEGER NOT NULL DEFAULT 0,
                        error_message TEXT,
                        metadata JSONB,
                        created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                    )
                    """)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS datasources (
                        id TEXT PRIMARY KEY,
                        source_type TEXT NOT NULL,
                        name TEXT NOT NULL,
                        config_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
                        created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                    )
                    """)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS datasource_tags (
                        datasource_id TEXT NOT NULL,
                        tag TEXT NOT NULL,
                        PRIMARY KEY (datasource_id, tag),
                        FOREIGN KEY (datasource_id) REFERENCES datasources (id) ON DELETE CASCADE
                    )
                    """)
            else:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS content_items (
                        id TEXT PRIMARY KEY,
                        title TEXT NOT NULL,
                        content TEXT NOT NULL,
                        url TEXT UNIQUE NOT NULL,
                        publish_time DATETIME NOT NULL,
                        source_name TEXT NOT NULL,
                        source_type TEXT NOT NULL,
                        content_hash TEXT NOT NULL,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS crawl_status (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        execution_time DATETIME NOT NULL,
                        total_items INTEGER NOT NULL,
                        rss_results TEXT NOT NULL,
                        x_results TEXT NOT NULL,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS analysis_execution_log (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        chat_id TEXT NOT NULL,
                        execution_time DATETIME NOT NULL,
                        time_window_hours INTEGER NOT NULL,
                        items_count INTEGER NOT NULL,
                        success BOOLEAN NOT NULL,
                        error_message TEXT,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS analysis_jobs (
                        id TEXT PRIMARY KEY,
                        recipient_key TEXT NOT NULL,
                        time_window_hours INTEGER NOT NULL,
                        created_at DATETIME NOT NULL,
                        status TEXT NOT NULL,
                        priority INTEGER NOT NULL DEFAULT 5,
                        started_at DATETIME,
                        completed_at DATETIME,
                        result TEXT,
                        error_message TEXT,
                        source TEXT NOT NULL DEFAULT 'api'
                    )
                """)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS ingestion_jobs (
                        id TEXT PRIMARY KEY,
                        source_type TEXT NOT NULL,
                        source_name TEXT NOT NULL,
                        scheduled_at DATETIME NOT NULL,
                        status TEXT NOT NULL,
                        started_at DATETIME,
                        completed_at DATETIME,
                        items_crawled INTEGER NOT NULL DEFAULT 0,
                        items_new INTEGER NOT NULL DEFAULT 0,
                        error_message TEXT,
                        metadata TEXT,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS datasources (
                        id TEXT PRIMARY KEY,
                        source_type TEXT NOT NULL,
                        name TEXT NOT NULL,
                        config_payload TEXT NOT NULL DEFAULT '{}',
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS datasource_tags (
                        datasource_id TEXT NOT NULL,
                        tag TEXT NOT NULL,
                        PRIMARY KEY (datasource_id, tag),
                        FOREIGN KEY (datasource_id) REFERENCES datasources (id) ON DELETE CASCADE
                    )
                """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_publish_time
                ON content_items (publish_time)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_source
                ON content_items (source_name, source_type)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_content_hash
                ON content_items (content_hash)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_created_at
                ON content_items (created_at)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_analysis_chat_time
                ON analysis_execution_log (chat_id, execution_time)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_analysis_success
                ON analysis_execution_log (chat_id, success, execution_time)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_analysis_jobs_recipient
                ON analysis_jobs (recipient_key, created_at)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_analysis_jobs_status
                ON analysis_jobs (status, created_at)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_ingestion_jobs_source
                ON ingestion_jobs (source_type, source_name, scheduled_at)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_ingestion_jobs_status
                ON ingestion_jobs (status, scheduled_at)
            """)
            cursor.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_datasources_source_name
                ON datasources (source_type, name)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_datasources_created_at
                ON datasources (created_at)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_datasource_tags_tag
                ON datasource_tags (tag)
            """)

            conn.commit()
            logger.info("数据库表结构初始化完成")

    @contextmanager
    def _get_connection(self):
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
            conn.execute("PRAGMA foreign_keys = ON")
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

    def add_content_items(self, items: List[ContentItem]) -> int:
        """
        添加内容项到数据库

        Args:
            items: 内容项列表

        Returns:
            成功添加的项目数量
        """
        if not items:
            return 0

        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                added_count = 0

                for item in items:
                    try:
                        item.validate()
                        content_hash = item.generate_content_hash()

                        if self.backend == "postgres":
                            cursor.execute(
                                """
                                INSERT INTO content_items
                                (id, title, content, url, publish_time, source_name, source_type, content_hash)
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                                ON CONFLICT (url) DO NOTHING
                                """,
                                (
                                    item.id,
                                    item.title,
                                    item.content,
                                    item.url,
                                    item.publish_time.isoformat(),
                                    item.source_name,
                                    item.source_type,
                                    content_hash,
                                ),
                            )
                        else:
                            cursor.execute(
                                self._sql("""
                                INSERT OR IGNORE INTO content_items
                                (id, title, content, url, publish_time, source_name,
                                 source_type, content_hash)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            """),
                                (
                                    item.id,
                                    item.title,
                                    item.content,
                                    item.url,
                                    item.publish_time.isoformat(),
                                    item.source_name,
                                    item.source_type,
                                    content_hash,
                                ),
                            )

                        if cursor.rowcount > 0:
                            added_count += 1

                    except Exception as e:
                        logger.warning(f"添加内容项失败 {item.id}: {e}")
                        continue

                conn.commit()
                logger.info(f"成功添加 {added_count}/{len(items)} 个内容项")
                return added_count

    def _normalize_loaded_publish_time(self, publish_time: datetime) -> datetime:
        if publish_time.tzinfo is None:
            return publish_time

        from datetime import timezone

        return publish_time.astimezone(timezone.utc).replace(tzinfo=None)

    def _coerce_loaded_datetime(self, value: Any) -> datetime:
        if isinstance(value, datetime):
            return value

        if isinstance(value, str):
            return datetime.fromisoformat(value)

        raise TypeError(f"Unsupported datetime value type: {type(value).__name__}")

    def get_content_items(
        self,
        time_window_hours: Optional[int] = None,
        source_types: Optional[List[str]] = None,
        limit: Optional[int] = None,
    ) -> List[ContentItem]:
        """
        获取内容项

        Args:
            time_window_hours: 时间窗口（小时）
            source_types: 数据源类型过滤
            limit: 限制返回数量

        Returns:
            内容项列表
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # 构建查询条件
            conditions = []
            params = []

            if time_window_hours is not None:
                from datetime import timezone

                cutoff_time = datetime.now(timezone.utc) - timedelta(hours=time_window_hours)
                conditions.append("publish_time >= ?")
                params.append(cutoff_time.isoformat())

            if source_types:
                placeholders = ",".join(["?" for _ in source_types])
                conditions.append(f"source_type IN ({placeholders})")
                params.extend(source_types)

            # 构建SQL查询
            query = "SELECT * FROM content_items"
            if conditions:
                query += " WHERE " + " AND ".join(conditions)

            query += " ORDER BY publish_time DESC"

            if limit:
                query += " LIMIT ?"
                params.append(limit)

            cursor.execute(self._sql(query), params)
            rows = cursor.fetchall()

            # 转换为ContentItem对象
            items = []
            for row in rows:
                try:
                    publish_time = self._coerce_loaded_datetime(row["publish_time"])
                    publish_time = self._normalize_loaded_publish_time(publish_time)

                    item = ContentItem(
                        id=row["id"],
                        title=row["title"],
                        content=row["content"],
                        url=row["url"],
                        publish_time=publish_time,
                        source_name=row["source_name"],
                        source_type=row["source_type"],
                    )
                    items.append(item)
                except Exception as e:
                    logger.warning(f"解析内容项失败 {row['id']}: {e}")
                    continue

            logger.info(f"获取到 {len(items)} 个内容项")
            return items

    def deduplicate_content(self) -> int:
        """
        去重内容（基于内容哈希）

        Returns:
            删除的重复项数量
        """
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                # 查找重复的内容哈希
                cursor.execute("""
                    SELECT content_hash, COUNT(*) as count
                    FROM content_items
                    GROUP BY content_hash
                    HAVING COUNT(*) > 1
                """)

                duplicate_hashes = cursor.fetchall()
                deleted_count = 0

                for row in duplicate_hashes:
                    content_hash = row["content_hash"]

                    # 保留最新的一条记录，删除其他重复项
                    cursor.execute(
                        self._sql("""
                        DELETE FROM content_items
                        WHERE content_hash = ? AND id NOT IN (
                            SELECT id FROM content_items
                            WHERE content_hash = ?
                            ORDER BY created_at DESC
                            LIMIT 1
                        )
                    """),
                        (content_hash, content_hash),
                    )

                    deleted_count += cursor.rowcount

                conn.commit()
                logger.info(f"去重完成，删除了 {deleted_count} 个重复项")
                return deleted_count

    def filter_by_time_window(self, time_window_hours: int) -> int:
        """
        根据时间窗口过滤内容

        Args:
            time_window_hours: 时间窗口（小时）

        Returns:
            删除的过期项数量
        """
        cutoff_time = datetime.now() - timedelta(hours=time_window_hours)

        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute(
                    self._sql("""
                    DELETE FROM content_items
                    WHERE publish_time < ?
                """),
                    (cutoff_time.isoformat(),),
                )

                deleted_count = cursor.rowcount
                conn.commit()

                logger.info(f"时间窗口过滤完成，删除了 {deleted_count} 个过期项")
                return deleted_count

    def cleanup_old_data(self, retention_days: Optional[int] = None) -> int:
        """
        清理旧数据

        Args:
            retention_days: 保留天数，如果为None则使用配置中的值

        Returns:
            删除的项目数量
        """
        if retention_days is None:
            retention_days = self.config.retention_days

        cutoff_time = datetime.now() - timedelta(days=retention_days)

        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                # 删除旧的内容项
                cursor.execute(
                    self._sql("""
                    DELETE FROM content_items
                    WHERE created_at < ?
                """),
                    (cutoff_time.isoformat(),),
                )

                content_deleted = cursor.rowcount

                # 删除旧的爬取状态
                cursor.execute(
                    self._sql("""
                    DELETE FROM crawl_status
                    WHERE created_at < ?
                """),
                    (cutoff_time.isoformat(),),
                )

                status_deleted = cursor.rowcount

                conn.commit()

                total_deleted = content_deleted + status_deleted
                logger.info(
                    f"数据清理完成，删除了 {content_deleted} 个内容项和 {status_deleted} 个状态记录"
                )
                return total_deleted

    def get_storage_size(self) -> Dict[str, Any]:
        """
        获取存储使用情况

        Returns:
            存储信息字典
        """
        try:
            db_size_bytes = (
                os.path.getsize(self.db_path)
                if self.backend == "sqlite" and os.path.exists(self.db_path)
                else 0
            )
            db_size_mb = db_size_bytes / (1024 * 1024)

            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) AS total_count FROM content_items")
                content_row = cursor.fetchone()
                content_count = (
                    content_row[0]
                    if self.backend == "sqlite"
                    else content_row.get("total_count", 0)
                )

                cursor.execute("SELECT COUNT(*) AS total_count FROM crawl_status")
                status_row = cursor.fetchone()
                status_count = (
                    status_row[0] if self.backend == "sqlite" else status_row.get("total_count", 0)
                )

                cursor.execute("""
                    SELECT MIN(created_at), MAX(created_at) 
                    FROM content_items
                """)
                time_range = cursor.fetchone()

                if self.backend == "sqlite":
                    earliest_record = time_range[0] if time_range and time_range[0] else None
                    latest_record = time_range[1] if time_range and time_range[1] else None
                else:
                    earliest_record = time_range.get("min") if time_range else None
                    latest_record = time_range.get("max") if time_range else None

                return {
                    "database_size_mb": round(db_size_mb, 2),
                    "database_size_bytes": db_size_bytes,
                    "content_items_count": content_count,
                    "crawl_status_count": status_count,
                    "earliest_record": earliest_record,
                    "latest_record": latest_record,
                    "max_storage_mb": self.config.max_storage_mb,
                    "storage_usage_percent": round(
                        (db_size_mb / self.config.max_storage_mb) * 100, 2
                    ),
                }

        except Exception as e:
            logger.error(f"获取存储信息失败: {e}")
            raise StorageError(f"获取存储信息失败: {e}", operation="get_storage_size")

    def save_crawl_status(self, status: CrawlStatus) -> None:
        """
        保存爬取状态

        Args:
            status: 爬取状态对象
        """
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute(
                    self._sql("""
                    INSERT INTO crawl_status 
                    (execution_time, total_items, rss_results, x_results)
                    VALUES (?, ?, ?, ?)
                """),
                    (
                        status.execution_time.isoformat(),
                        status.total_items,
                        json.dumps([result.to_dict() for result in status.rss_results]),
                        json.dumps([result.to_dict() for result in status.x_results]),
                    ),
                )

                conn.commit()
                logger.info("爬取状态保存成功")

    def get_latest_crawl_status(self) -> Optional[CrawlStatus]:
        """
        获取最新的爬取状态

        Returns:
            最新的爬取状态，如果没有则返回None
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT * FROM crawl_status
                ORDER BY execution_time DESC
                LIMIT 1
            """)

            row = cursor.fetchone()
            if not row:
                return None

            try:
                from ..models import CrawlResult

                rss_payload = row["rss_results"]
                if isinstance(rss_payload, str):
                    rss_payload = json.loads(rss_payload)

                x_payload = row["x_results"]
                if isinstance(x_payload, str):
                    x_payload = json.loads(x_payload)

                rss_results = [CrawlResult.from_dict(r) for r in rss_payload]
                x_results = [CrawlResult.from_dict(r) for r in x_payload]

                return CrawlStatus(
                    rss_results=rss_results,
                    x_results=x_results,
                    total_items=row["total_items"],
                    execution_time=self._coerce_loaded_datetime(row["execution_time"]),
                )

            except Exception as e:
                logger.error(f"解析爬取状态失败: {e}")
                return None

    def export_data(self, format: str = "json", time_window_hours: Optional[int] = None) -> str:
        """
        导出数据

        Args:
            format: 导出格式 ("json" 或 "csv")
            time_window_hours: 时间窗口过滤

        Returns:
            导出的数据字符串
        """
        items = self.get_content_items(time_window_hours=time_window_hours)

        if format.lower() == "json":
            data = [item.to_dict() for item in items]
            return json.dumps(data, ensure_ascii=False, indent=2)

        elif format.lower() == "csv":
            import csv
            import io

            output = io.StringIO()
            writer = csv.writer(output)

            # 写入标题行
            writer.writerow(
                ["id", "title", "content", "url", "publish_time", "source_name", "source_type"]
            )

            # 写入数据行
            for item in items:
                writer.writerow(
                    [
                        item.id,
                        item.title,
                        item.content,
                        item.url,
                        item.publish_time.isoformat(),
                        item.source_name,
                        item.source_type,
                    ]
                )

            return output.getvalue()

        else:
            raise ValueError(f"不支持的导出格式: {format}")

    def close(self) -> None:
        """关闭数据管理器，清理资源"""
        with self._lock:
            for conn in self._connection_pool.values():
                try:
                    conn.close()
                except Exception as e:
                    logger.warning(f"关闭数据库连接失败: {e}")

            self._connection_pool.clear()
            logger.info("数据管理器已关闭")

    def __enter__(self):
        """上下文管理器入口"""
        return self

    def get_latest_message_time(
        self, source_name: str, source_type: str = "x"
    ) -> Optional[datetime]:
        """
        获取指定源的最近消息时间

        Args:
            source_name: 数据源名称
            source_type: 数据源类型（默认为"x"）

        Returns:
            最近消息的发布时间，如果没有历史数据则返回None
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                self._sql("""
                SELECT MAX(publish_time) as latest_time
                FROM content_items
                WHERE source_name = ? AND source_type = ?
            """),
                (source_name, source_type),
            )

            row = cursor.fetchone()

            if row and row["latest_time"]:
                try:
                    latest_time = self._coerce_loaded_datetime(row["latest_time"])
                    logger.info(f"数据源 {source_name} 的最近消息时间: {latest_time}")
                    return latest_time
                except Exception as e:
                    logger.warning(f"解析最近消息时间失败: {e}")
                    return None
            else:
                logger.info(f"数据源 {source_name} 没有历史数据")
                return None

    def get_source_message_counts(self, time_window_hours: int = 24) -> Dict[str, int]:
        """
        获取各个数据源在指定时间窗口内的消息数量

        Args:
            time_window_hours: 时间窗口（小时），默认24小时

        Returns:
            字典，key为数据源名称，value为消息数量
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            cutoff_time = datetime.now() - timedelta(hours=time_window_hours)

            cursor.execute(
                self._sql("""
                SELECT source_name, COUNT(*) as count
                FROM content_items
                WHERE publish_time >= ?
                GROUP BY source_name
                ORDER BY count DESC
            """),
                (cutoff_time.isoformat(),),
            )

            rows = cursor.fetchall()

            result = {}
            for row in rows:
                result[row["source_name"]] = row["count"]

            logger.info(
                f"获取到 {len(result)} 个数据源的消息统计（时间窗口: {time_window_hours}小时）"
            )
            return result

    def get_content_items_since(
        self,
        since_time: datetime,
        max_hours: int = 24,
        source_types: Optional[List[str]] = None,
        limit: Optional[int] = None,
    ) -> List[ContentItem]:
        """
        获取指定时间之后的内容项（带最大时间限制）

        Args:
            since_time: 起始时间
            max_hours: 最大时间窗口（小时），默认24小时
            source_types: 数据源类型过滤
            limit: 限制返回数量

        Returns:
            内容项列表
        """
        from datetime import timezone

        now = datetime.now(timezone.utc)
        max_end_time = since_time + timedelta(hours=max_hours)
        end_time = min(now, max_end_time)

        with self._get_connection() as conn:
            cursor = conn.cursor()

            conditions = ["publish_time >= ?", "publish_time <= ?"]
            params: List[Any] = [since_time.isoformat(), end_time.isoformat()]

            if source_types:
                placeholders = ",".join(["?" for _ in source_types])
                conditions.append(f"source_type IN ({placeholders})")
                params.extend(source_types)

            query = "SELECT * FROM content_items"
            if conditions:
                query += " WHERE " + " AND ".join(conditions)

            query += " ORDER BY publish_time DESC"

            if limit:
                query += " LIMIT ?"
                params.append(limit)

            cursor.execute(self._sql(query), params)
            rows = cursor.fetchall()

            items = []
            for row in rows:
                try:
                    publish_time = self._coerce_loaded_datetime(row["publish_time"])
                    publish_time = self._normalize_loaded_publish_time(publish_time)

                    item = ContentItem(
                        id=row["id"],
                        title=row["title"],
                        content=row["content"],
                        url=row["url"],
                        publish_time=publish_time,
                        source_name=row["source_name"],
                        source_type=row["source_type"],
                    )
                    items.append(item)
                except Exception as e:
                    logger.warning(f"解析内容项失败 {row['id']}: {e}")
                    continue

            logger.info(f"从 {since_time} 到 {end_time} 获取到 {len(items)} 个内容项")
            return items

    def check_content_hash_exists(self, content_hash: str) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                self._sql("""
                    SELECT 1 FROM content_items
                    WHERE content_hash = ?
                    LIMIT 1
                    """),
                (content_hash,),
            )
            return cursor.fetchone() is not None

    def log_analysis_execution(
        self,
        chat_id: str,
        time_window_hours: int,
        items_count: int,
        success: bool,
        error_message: Optional[str] = None,
    ) -> None:
        """
        记录分析执行日志

        Args:
            chat_id: 聊天ID（"api"表示API调用，或TG chat_id）
            time_window_hours: 分析的时间窗口（小时）
            items_count: 分析的项目数量
            success: 是否成功
            error_message: 错误信息（如果失败）
        """
        recipient_key = str(chat_id).strip()
        if not recipient_key:
            raise ValueError("analysis execution 标识不能为空")

        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute(
                    self._sql("""
                    INSERT INTO analysis_execution_log
                    (chat_id, execution_time, time_window_hours, items_count, success, error_message)
                    VALUES (?, ?, ?, ?, ?, ?)
                """),
                    (
                        recipient_key,
                        datetime.now().isoformat(),
                        time_window_hours,
                        items_count,
                        success,
                        error_message,
                    ),
                )

                conn.commit()
                logger.info(f"分析执行日志已记录: chat_id={recipient_key}, success={success}")

    def upsert_analysis_job(
        self,
        request_id: str,
        recipient_key: str,
        time_window_hours: int,
        created_at: datetime,
        status: str,
        priority: int,
        source: str,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
        result: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
    ) -> None:
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                if self.backend == "postgres":
                    cursor.execute(
                        self._sql("""
                        INSERT INTO analysis_jobs
                        (id, recipient_key, time_window_hours, created_at, status, priority,
                         started_at, completed_at, result, error_message, source)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT (id) DO UPDATE SET
                            recipient_key = EXCLUDED.recipient_key,
                            time_window_hours = EXCLUDED.time_window_hours,
                            created_at = EXCLUDED.created_at,
                            status = EXCLUDED.status,
                            priority = EXCLUDED.priority,
                            started_at = EXCLUDED.started_at,
                            completed_at = EXCLUDED.completed_at,
                            result = EXCLUDED.result,
                            error_message = EXCLUDED.error_message,
                            source = EXCLUDED.source
                        """),
                        (
                            request_id,
                            recipient_key,
                            time_window_hours,
                            created_at.isoformat(),
                            status,
                            priority,
                            started_at.isoformat() if started_at else None,
                            completed_at.isoformat() if completed_at else None,
                            json.dumps(result, ensure_ascii=False) if result is not None else None,
                            error_message,
                            source,
                        ),
                    )
                else:
                    cursor.execute(
                        self._sql("""
                        INSERT OR REPLACE INTO analysis_jobs
                        (id, recipient_key, time_window_hours, created_at, status, priority,
                         started_at, completed_at, result, error_message, source)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """),
                        (
                            request_id,
                            recipient_key,
                            time_window_hours,
                            created_at.isoformat(),
                            status,
                            priority,
                            started_at.isoformat() if started_at else None,
                            completed_at.isoformat() if completed_at else None,
                            json.dumps(result, ensure_ascii=False) if result is not None else None,
                            error_message,
                            source,
                        ),
                    )

                conn.commit()

    def get_analysis_job_by_id(self, request_id: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                self._sql("""
                SELECT * FROM analysis_jobs
                WHERE id = ?
                LIMIT 1
                """),
                (request_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return self._serialize_analysis_job_row(row)

    def get_analysis_jobs_by_recipient(
        self,
        recipient_key: str,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            params: List[Any] = [recipient_key]
            query = "SELECT * FROM analysis_jobs WHERE recipient_key = ?"
            if status:
                query += " AND status = ?"
                params.append(status)
            query += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)

            cursor.execute(self._sql(query), params)
            rows = cursor.fetchall()
            return [self._serialize_analysis_job_row(row) for row in rows]

    def get_pending_analysis_jobs(
        self,
        limit: int = 10,
        min_priority: int = 1,
    ) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                self._sql("""
                SELECT * FROM analysis_jobs
                WHERE status IN ('pending', 'queued')
                  AND priority >= ?
                ORDER BY priority DESC, created_at ASC
                LIMIT ?
                """),
                (min_priority, limit),
            )
            rows = cursor.fetchall()
            return [self._serialize_analysis_job_row(row) for row in rows]

    def update_analysis_job_status(
        self,
        request_id: str,
        status: str,
        error_message: Optional[str] = None,
    ) -> bool:
        started_at = datetime.now().isoformat() if status == "running" else None
        completed_at = datetime.now().isoformat() if status in {"completed", "failed", "cancelled"} else None

        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                if status == "running":
                    cursor.execute(
                        self._sql("""
                        UPDATE analysis_jobs
                        SET status = ?,
                            started_at = COALESCE(started_at, ?),
                            error_message = ?
                        WHERE id = ?
                        """),
                        (status, started_at, error_message, request_id),
                    )
                elif completed_at is not None:
                    cursor.execute(
                        self._sql("""
                        UPDATE analysis_jobs
                        SET status = ?,
                            completed_at = ?,
                            error_message = ?
                        WHERE id = ?
                        """),
                        (status, completed_at, error_message, request_id),
                    )
                else:
                    cursor.execute(
                        self._sql("""
                        UPDATE analysis_jobs
                        SET status = ?,
                            error_message = ?
                        WHERE id = ?
                        """),
                        (status, error_message, request_id),
                    )

                updated = cursor.rowcount > 0
                conn.commit()
                return updated

    def complete_analysis_job(
        self,
        request_id: str,
        result: Dict[str, Any],
    ) -> bool:
        status = "completed" if result.get("success") else "failed"
        error_message = None
        if not result.get("success"):
            errors = result.get("errors") or []
            error_message = "; ".join(str(error) for error in errors) or "Analysis failed"

        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    self._sql("""
                    UPDATE analysis_jobs
                    SET status = ?,
                        completed_at = ?,
                        result = ?,
                        error_message = ?
                    WHERE id = ?
                    """),
                    (
                        status,
                        datetime.now().isoformat(),
                        json.dumps(result, ensure_ascii=False),
                        error_message,
                        request_id,
                    ),
                )
                updated = cursor.rowcount > 0
                conn.commit()
                return updated

    def upsert_datasource(
        self,
        datasource_id: str,
        source_type: str,
        name: str,
        config_payload: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
        created_at: Optional[datetime] = None,
    ) -> None:
        with self._lock:
            with self._get_connection() as conn:
                self._upsert_datasource_with_connection(
                    conn=conn,
                    datasource_id=datasource_id,
                    source_type=source_type,
                    name=name,
                    config_payload=config_payload,
                    tags=tags,
                    created_at=created_at,
                )
                conn.commit()

    def _upsert_datasource_with_connection(
        self,
        conn: Any,
        datasource_id: str,
        source_type: str,
        name: str,
        config_payload: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
        created_at: Optional[datetime] = None,
    ) -> None:
        cursor = conn.cursor()
        payload = dict(config_payload or {})
        normalized_tags = sorted({str(tag).strip().lower() for tag in (tags or []) if str(tag).strip()})
        created_at_value = (created_at or datetime.utcnow()).isoformat()

        if self.backend == "postgres":
            cursor.execute(
                self._sql("""
                INSERT INTO datasources (id, source_type, name, config_payload, created_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT (id) DO UPDATE SET
                    source_type = EXCLUDED.source_type,
                    name = EXCLUDED.name,
                    config_payload = EXCLUDED.config_payload,
                    created_at = EXCLUDED.created_at
                """),
                (
                    datasource_id,
                    source_type,
                    name,
                    json.dumps(payload, ensure_ascii=False),
                    created_at_value,
                ),
            )
        else:
            cursor.execute(
                self._sql("""
                INSERT INTO datasources (id, source_type, name, config_payload, created_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    source_type = excluded.source_type,
                    name = excluded.name,
                    config_payload = excluded.config_payload,
                    created_at = excluded.created_at
                """),
                (
                    datasource_id,
                    source_type,
                    name,
                    json.dumps(payload, ensure_ascii=False),
                    created_at_value,
                ),
            )

        cursor.execute(
            self._sql("DELETE FROM datasource_tags WHERE datasource_id = ?"),
            (datasource_id,),
        )
        for tag in normalized_tags:
            cursor.execute(
                self._sql(
                    "INSERT INTO datasource_tags (datasource_id, tag) VALUES (?, ?)"
                ),
                (datasource_id, tag),
            )

    def get_datasource_count(self) -> int:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) AS count FROM datasources")
            row = cursor.fetchone()
            if row is None:
                return 0
            return int(row["count"] if self.backend == "postgres" else row[0])

    def get_datasource_by_id(self, datasource_id: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                self._sql("""
                SELECT * FROM datasources
                WHERE id = ?
                LIMIT 1
                """),
                (datasource_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return self._serialize_datasource_row(conn, row)

    def get_datasource_by_type_and_name(
        self,
        source_type: str,
        name: str,
    ) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                self._sql("""
                SELECT * FROM datasources
                WHERE source_type = ? AND name = ?
                LIMIT 1
                """),
                (source_type, name),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return self._serialize_datasource_row(conn, row)

    def list_datasources(self, source_type: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            params: List[Any] = []
            query = "SELECT * FROM datasources"
            if source_type is not None:
                query += " WHERE source_type = ?"
                params.append(source_type)
            query += " ORDER BY source_type ASC, name ASC"
            cursor.execute(self._sql(query), params)
            rows = cursor.fetchall()
            return [self._serialize_datasource_row(conn, row) for row in rows]

    def delete_datasource(self, datasource_id: str) -> bool:
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    self._sql("DELETE FROM datasources WHERE id = ?"),
                    (datasource_id,),
                )
                deleted = cursor.rowcount > 0
                conn.commit()
                return deleted

    def get_active_ingestion_job_ids_for_source(
        self,
        source_type: str,
        source_name: str,
    ) -> List[str]:
        statuses = sorted(ACTIVE_INGESTION_JOB_STATUSES)
        placeholders = ",".join(["?" for _ in statuses])

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                self._sql(
                    f"""
                    SELECT id FROM ingestion_jobs
                    WHERE source_type = ?
                      AND source_name = ?
                      AND status IN ({placeholders})
                    ORDER BY scheduled_at DESC
                    """
                ),
                [source_type, source_name, *statuses],
            )
            rows = cursor.fetchall()
            return [row["id"] if self.backend == "postgres" else row[0] for row in rows]

    def bootstrap_datasources_if_empty(self, datasources: List[DataSource]) -> bool:
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) AS count FROM datasources")
                row = cursor.fetchone()
                if row is None:
                    existing_count = 0
                else:
                    existing_count = int(row["count"] if self.backend == "postgres" else row[0])
                if existing_count > 0:
                    return False

                for datasource in datasources:
                    self._upsert_datasource_with_connection(
                        conn=conn,
                        datasource_id=datasource.id,
                        source_type=datasource.source_type,
                        name=datasource.name,
                        config_payload=datasource.config_payload,
                        tags=datasource.tags,
                        created_at=datasource.created_at,
                    )

                conn.commit()
                return True

    def _serialize_datasource_row(self, conn: Any, row: Any) -> Dict[str, Any]:
        config_payload = row["config_payload"]
        parsed_config_payload: Dict[str, Any] = {}
        if isinstance(config_payload, str) and config_payload:
            try:
                parsed_config_payload = json.loads(config_payload)
            except json.JSONDecodeError:
                logger.warning("datasources.config_payload JSON解析失败")
                parsed_config_payload = {}
        elif isinstance(config_payload, dict):
            parsed_config_payload = config_payload

        cursor = conn.cursor()
        cursor.execute(
            self._sql(
                "SELECT tag FROM datasource_tags WHERE datasource_id = ? ORDER BY tag ASC"
            ),
            (row["id"],),
        )
        tag_rows = cursor.fetchall()
        tags = [tag_row["tag"] if self.backend == "postgres" else tag_row[0] for tag_row in tag_rows]

        created_at = row["created_at"]
        if isinstance(created_at, datetime):
            created_at = created_at.isoformat()

        return {
            "id": row["id"],
            "source_type": row["source_type"],
            "name": row["name"],
            "config_payload": parsed_config_payload,
            "tags": tags,
            "created_at": created_at,
            "updated_at": None,
        }

    def _serialize_analysis_job_row(self, row: Any) -> Dict[str, Any]:
        def _serialize_datetime(value: Any) -> Any:
            if isinstance(value, datetime):
                return value.isoformat()
            return value

        result_payload = row["result"]
        parsed_result: Optional[Dict[str, Any]] = None
        if isinstance(result_payload, str) and result_payload:
            try:
                parsed_result = json.loads(result_payload)
            except json.JSONDecodeError:
                logger.warning("analysis_jobs.result JSON解析失败")
                parsed_result = None
        elif isinstance(result_payload, dict):
            parsed_result = result_payload

        return {
            "id": row["id"],
            "recipient_key": row["recipient_key"],
            "time_window_hours": row["time_window_hours"],
            "created_at": _serialize_datetime(row["created_at"]),
            "status": row["status"],
            "priority": row["priority"],
            "started_at": _serialize_datetime(row["started_at"]),
            "completed_at": _serialize_datetime(row["completed_at"]),
            "result": parsed_result,
            "error_message": row["error_message"],
            "source": row["source"],
        }

    def upsert_ingestion_job(
        self,
        job_id: str,
        source_type: str,
        source_name: str,
        scheduled_at: datetime,
        status: str,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
        items_crawled: int = 0,
        items_new: int = 0,
        error_message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                metadata_payload = metadata if metadata is not None else {}

                if self.backend == "postgres":
                    cursor.execute(
                        self._sql("""
                        INSERT INTO ingestion_jobs
                        (id, source_type, source_name, scheduled_at, status, started_at,
                         completed_at, items_crawled, items_new, error_message, metadata)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT (id) DO UPDATE SET
                            source_type = EXCLUDED.source_type,
                            source_name = EXCLUDED.source_name,
                            scheduled_at = EXCLUDED.scheduled_at,
                            status = EXCLUDED.status,
                            started_at = EXCLUDED.started_at,
                            completed_at = EXCLUDED.completed_at,
                            items_crawled = EXCLUDED.items_crawled,
                            items_new = EXCLUDED.items_new,
                            error_message = EXCLUDED.error_message,
                            metadata = EXCLUDED.metadata
                        """),
                        (
                            job_id,
                            source_type,
                            source_name,
                            scheduled_at.isoformat(),
                            status,
                            started_at.isoformat() if started_at else None,
                            completed_at.isoformat() if completed_at else None,
                            items_crawled,
                            items_new,
                            error_message,
                            json.dumps(metadata_payload, ensure_ascii=False),
                        ),
                    )
                else:
                    cursor.execute(
                        self._sql("""
                        INSERT OR REPLACE INTO ingestion_jobs
                        (id, source_type, source_name, scheduled_at, status, started_at,
                         completed_at, items_crawled, items_new, error_message, metadata)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """),
                        (
                            job_id,
                            source_type,
                            source_name,
                            scheduled_at.isoformat(),
                            status,
                            started_at.isoformat() if started_at else None,
                            completed_at.isoformat() if completed_at else None,
                            items_crawled,
                            items_new,
                            error_message,
                            json.dumps(metadata_payload, ensure_ascii=False),
                        ),
                    )

                conn.commit()

    def get_ingestion_job_by_id(self, job_id: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                self._sql("""
                SELECT * FROM ingestion_jobs
                WHERE id = ?
                LIMIT 1
                """),
                (job_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return self._serialize_ingestion_job_row(row)

    def get_ingestion_jobs_by_source(
        self,
        source_type: str,
        source_name: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()

            conditions = ["source_type = ?"]
            params: List[Any] = [source_type]

            if source_name:
                conditions.append("source_name = ?")
                params.append(source_name)
            if status:
                conditions.append("status = ?")
                params.append(status)

            query = f"SELECT * FROM ingestion_jobs WHERE {' AND '.join(conditions)}"
            query += " ORDER BY scheduled_at DESC LIMIT ?"
            params.append(limit)

            cursor.execute(self._sql(query), params)
            rows = cursor.fetchall()
            return [self._serialize_ingestion_job_row(row) for row in rows]

    def get_pending_ingestion_jobs(self, limit: int = 10) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                self._sql("""
                SELECT * FROM ingestion_jobs
                WHERE status IN ('pending', 'running')
                ORDER BY scheduled_at ASC
                LIMIT ?
                """),
                (limit,),
            )
            rows = cursor.fetchall()
            return [self._serialize_ingestion_job_row(row) for row in rows]

    def update_ingestion_job_status(
        self,
        job_id: str,
        status: str,
        error_message: Optional[str] = None,
    ) -> bool:
        started_at = datetime.now().isoformat() if status == "running" else None
        completed_at = (
            datetime.now().isoformat() if status in {"completed", "failed", "skipped"} else None
        )

        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                if status == "running":
                    cursor.execute(
                        self._sql("""
                        UPDATE ingestion_jobs
                        SET status = ?,
                            started_at = COALESCE(started_at, ?),
                            error_message = ?
                        WHERE id = ?
                        """),
                        (status, started_at, error_message, job_id),
                    )
                elif completed_at is not None:
                    cursor.execute(
                        self._sql("""
                        UPDATE ingestion_jobs
                        SET status = ?,
                            completed_at = ?,
                            error_message = ?
                        WHERE id = ?
                        """),
                        (status, completed_at, error_message, job_id),
                    )
                else:
                    cursor.execute(
                        self._sql("""
                        UPDATE ingestion_jobs
                        SET status = ?,
                            error_message = ?
                        WHERE id = ?
                        """),
                        (status, error_message, job_id),
                    )

                updated = cursor.rowcount > 0
                conn.commit()
                return updated

    def complete_ingestion_job(
        self,
        job_id: str,
        items_crawled: int,
        items_new: int,
    ) -> bool:
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    self._sql("""
                    UPDATE ingestion_jobs
                    SET status = 'completed',
                        completed_at = ?,
                        items_crawled = ?,
                        items_new = ?,
                        error_message = NULL
                    WHERE id = ?
                    """),
                    (
                        datetime.now().isoformat(),
                        items_crawled,
                        items_new,
                        job_id,
                    ),
                )
                updated = cursor.rowcount > 0
                conn.commit()
                return updated

    def get_ingestion_job_statistics(
        self,
        since: datetime,
        source_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        with self._get_connection() as conn:
            cursor = conn.cursor()

            conditions = ["scheduled_at >= ?"]
            params: List[Any] = [since.isoformat()]
            if source_type:
                conditions.append("source_type = ?")
                params.append(source_type)

            where_clause = " AND ".join(conditions)
            cursor.execute(
                self._sql(
                    f"""
                    SELECT
                        COUNT(*) AS total_jobs,
                        SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) AS completed_jobs,
                        SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS failed_jobs,
                        SUM(items_crawled) AS total_items_crawled,
                        SUM(items_new) AS total_items_new
                    FROM ingestion_jobs
                    WHERE {where_clause}
                    """
                ),
                params,
            )
            row = cursor.fetchone()

            return {
                "total_jobs": int(row["total_jobs"] or 0),
                "completed_jobs": int(row["completed_jobs"] or 0),
                "failed_jobs": int(row["failed_jobs"] or 0),
                "total_items_crawled": int(row["total_items_crawled"] or 0),
                "total_items_new": int(row["total_items_new"] or 0),
            }

    def _serialize_ingestion_job_row(self, row: Any) -> Dict[str, Any]:
        def _serialize_datetime(value: Any) -> Any:
            if isinstance(value, datetime):
                return value.isoformat()
            return value

        metadata_payload = row["metadata"]
        parsed_metadata: Dict[str, Any] = {}
        if isinstance(metadata_payload, str) and metadata_payload:
            try:
                parsed_metadata = json.loads(metadata_payload)
            except json.JSONDecodeError:
                logger.warning("ingestion_jobs.metadata JSON解析失败")
                parsed_metadata = {}
        elif isinstance(metadata_payload, dict):
            parsed_metadata = metadata_payload

        return {
            "id": row["id"],
            "source_type": row["source_type"],
            "source_name": row["source_name"],
            "scheduled_at": _serialize_datetime(row["scheduled_at"]),
            "status": row["status"],
            "started_at": _serialize_datetime(row["started_at"]),
            "completed_at": _serialize_datetime(row["completed_at"]),
            "items_crawled": row["items_crawled"],
            "items_new": row["items_new"],
            "error_message": row["error_message"],
            "metadata": parsed_metadata,
        }

    def get_last_successful_analysis_time(self, chat_id: str) -> Optional[datetime]:
        """
        获取指定chat_id的上次成功分析时间

        Args:
            chat_id: 聊天ID

        Returns:
            上次成功分析的执行时间，如果没有则返回None
        """
        recipient_key = str(chat_id).strip()
        if not recipient_key:
            raise ValueError("analysis execution 标识不能为空")

        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                self._sql("""
                SELECT execution_time FROM analysis_execution_log
                WHERE chat_id = ? AND success = TRUE
                ORDER BY execution_time DESC
                LIMIT 1
            """),
                (recipient_key,),
            )

            row = cursor.fetchone()
            if row and row["execution_time"]:
                try:
                    execution_time = self._coerce_loaded_datetime(row["execution_time"])
                    logger.info(f"chat_id={recipient_key} 的上次成功分析时间: {execution_time}")
                    return execution_time
                except Exception as e:
                    logger.warning(f"解析分析执行时间失败: {e}")
                    return None
            else:
                logger.info(f"chat_id={recipient_key} 没有成功分析记录")
                return None

    def cleanup_analysis_logs(self, retention_days: int = 30) -> int:
        """
        清理旧的分析执行日志

        Args:
            retention_days: 保留天数

        Returns:
            删除的记录数量
        """
        cutoff_time = datetime.now() - timedelta(days=retention_days)

        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute(
                    self._sql("""
                    DELETE FROM analysis_execution_log
                    WHERE created_at < ?
                """),
                    (cutoff_time.isoformat(),),
                )

                deleted_count = cursor.rowcount
                conn.commit()

                logger.info(f"清理了 {deleted_count} 条旧分析执行日志")
                return deleted_count

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.close()
