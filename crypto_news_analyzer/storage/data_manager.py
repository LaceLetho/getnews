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

from ..models import ContentItem, CrawlStatus, StorageConfig
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
        self.db_path = storage_config.database_path
        self._lock = threading.RLock()  # 线程安全锁
        self._connection_pool = {}  # 简单的连接池
        
        # 确保数据库目录存在
        self._ensure_database_directory()
        
        # 初始化数据库
        self._initialize_database()
        
        logger.info(f"数据管理器初始化完成，数据库路径: {self.db_path}")
    
    def _ensure_database_directory(self) -> None:
        """确保数据库目录存在"""
        db_dir = Path(self.db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)
    
    def _initialize_database(self) -> None:
        """初始化数据库表结构"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # 创建内容项表
            cursor.execute('''
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
            ''')
            
            # 创建索引
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_publish_time 
                ON content_items (publish_time)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_source 
                ON content_items (source_name, source_type)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_content_hash 
                ON content_items (content_hash)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_created_at 
                ON content_items (created_at)
            ''')
            
            # 创建爬取状态表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS crawl_status (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    execution_time DATETIME NOT NULL,
                    total_items INTEGER NOT NULL,
                    rss_results TEXT NOT NULL,
                    x_results TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.commit()
            logger.info("数据库表结构初始化完成")
    
    @contextmanager
    def _get_connection(self):
        """获取数据库连接（上下文管理器）"""
        thread_id = threading.get_ident()
        
        if thread_id not in self._connection_pool:
            conn = sqlite3.connect(
                self.db_path,
                check_same_thread=False,
                timeout=30.0
            )
            conn.row_factory = sqlite3.Row  # 启用字典式访问
            self._connection_pool[thread_id] = conn
        
        conn = self._connection_pool[thread_id]
        
        try:
            yield conn
        except Exception as e:
            conn.rollback()
            logger.error(f"数据库操作失败: {e}")
            raise StorageError(f"数据库操作失败: {e}")
        finally:
            # 不在这里关闭连接，保持连接池
            pass
    
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
                        # 验证数据
                        item.validate()
                        
                        # 生成内容哈希
                        content_hash = item.generate_content_hash()
                        
                        # 插入数据（忽略重复）
                        cursor.execute('''
                            INSERT OR IGNORE INTO content_items 
                            (id, title, content, url, publish_time, source_name, 
                             source_type, content_hash)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            item.id,
                            item.title,
                            item.content,
                            item.url,
                            item.publish_time.isoformat(),
                            item.source_name,
                            item.source_type,
                            content_hash
                        ))
                        
                        if cursor.rowcount > 0:
                            added_count += 1
                            
                    except Exception as e:
                        logger.warning(f"添加内容项失败 {item.id}: {e}")
                        continue
                
                conn.commit()
                logger.info(f"成功添加 {added_count}/{len(items)} 个内容项")
                return added_count
    
    def get_content_items(
        self,
        time_window_hours: Optional[int] = None,
        source_types: Optional[List[str]] = None,
        limit: Optional[int] = None
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
                cutoff_time = datetime.now() - timedelta(hours=time_window_hours)
                conditions.append("publish_time >= ?")
                params.append(cutoff_time.isoformat())
            
            if source_types:
                placeholders = ','.join(['?' for _ in source_types])
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
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            # 转换为ContentItem对象
            items = []
            for row in rows:
                try:
                    item = ContentItem(
                        id=row['id'],
                        title=row['title'],
                        content=row['content'],
                        url=row['url'],
                        publish_time=datetime.fromisoformat(row['publish_time']),
                        source_name=row['source_name'],
                        source_type=row['source_type']
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
                cursor.execute('''
                    SELECT content_hash, COUNT(*) as count
                    FROM content_items
                    GROUP BY content_hash
                    HAVING count > 1
                ''')
                
                duplicate_hashes = cursor.fetchall()
                deleted_count = 0
                
                for row in duplicate_hashes:
                    content_hash = row['content_hash']
                    
                    # 保留最新的一条记录，删除其他重复项
                    cursor.execute('''
                        DELETE FROM content_items
                        WHERE content_hash = ? AND id NOT IN (
                            SELECT id FROM content_items
                            WHERE content_hash = ?
                            ORDER BY created_at DESC
                            LIMIT 1
                        )
                    ''', (content_hash, content_hash))
                    
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
                
                cursor.execute('''
                    DELETE FROM content_items
                    WHERE publish_time < ?
                ''', (cutoff_time.isoformat(),))
                
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
                cursor.execute('''
                    DELETE FROM content_items
                    WHERE created_at < ?
                ''', (cutoff_time.isoformat(),))
                
                content_deleted = cursor.rowcount
                
                # 删除旧的爬取状态
                cursor.execute('''
                    DELETE FROM crawl_status
                    WHERE created_at < ?
                ''', (cutoff_time.isoformat(),))
                
                status_deleted = cursor.rowcount
                
                conn.commit()
                
                total_deleted = content_deleted + status_deleted
                logger.info(f"数据清理完成，删除了 {content_deleted} 个内容项和 {status_deleted} 个状态记录")
                return total_deleted
    
    def get_storage_size(self) -> Dict[str, Any]:
        """
        获取存储使用情况
        
        Returns:
            存储信息字典
        """
        try:
            # 获取数据库文件大小
            db_size_bytes = os.path.getsize(self.db_path) if os.path.exists(self.db_path) else 0
            db_size_mb = db_size_bytes / (1024 * 1024)
            
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # 获取表统计信息
                cursor.execute("SELECT COUNT(*) FROM content_items")
                content_count = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) FROM crawl_status")
                status_count = cursor.fetchone()[0]
                
                # 获取最早和最新的记录时间
                cursor.execute('''
                    SELECT MIN(created_at), MAX(created_at) 
                    FROM content_items
                ''')
                time_range = cursor.fetchone()
                
                return {
                    'database_size_mb': round(db_size_mb, 2),
                    'database_size_bytes': db_size_bytes,
                    'content_items_count': content_count,
                    'crawl_status_count': status_count,
                    'earliest_record': time_range[0] if time_range[0] else None,
                    'latest_record': time_range[1] if time_range[1] else None,
                    'max_storage_mb': self.config.max_storage_mb,
                    'storage_usage_percent': round((db_size_mb / self.config.max_storage_mb) * 100, 2)
                }
                
        except Exception as e:
            logger.error(f"获取存储信息失败: {e}")
            raise StorageError(f"获取存储信息失败: {e}")
    
    def save_crawl_status(self, status: CrawlStatus) -> None:
        """
        保存爬取状态
        
        Args:
            status: 爬取状态对象
        """
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    INSERT INTO crawl_status 
                    (execution_time, total_items, rss_results, x_results)
                    VALUES (?, ?, ?, ?)
                ''', (
                    status.execution_time.isoformat(),
                    status.total_items,
                    json.dumps([result.to_dict() for result in status.rss_results]),
                    json.dumps([result.to_dict() for result in status.x_results])
                ))
                
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
            
            cursor.execute('''
                SELECT * FROM crawl_status
                ORDER BY execution_time DESC
                LIMIT 1
            ''')
            
            row = cursor.fetchone()
            if not row:
                return None
            
            try:
                from ..models import CrawlResult
                
                rss_results = [CrawlResult.from_dict(r) for r in json.loads(row['rss_results'])]
                x_results = [CrawlResult.from_dict(r) for r in json.loads(row['x_results'])]
                
                return CrawlStatus(
                    rss_results=rss_results,
                    x_results=x_results,
                    total_items=row['total_items'],
                    execution_time=datetime.fromisoformat(row['execution_time'])
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
            writer.writerow(['id', 'title', 'content', 'url', 'publish_time', 
                           'source_name', 'source_type'])
            
            # 写入数据行
            for item in items:
                writer.writerow([
                    item.id, item.title, item.content, item.url,
                    item.publish_time.isoformat(), item.source_name, item.source_type
                ])
            
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
    
    def get_latest_message_time(self, source_name: str, source_type: str = "x") -> Optional[datetime]:
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
            
            cursor.execute('''
                SELECT MAX(publish_time) as latest_time
                FROM content_items
                WHERE source_name = ? AND source_type = ?
            ''', (source_name, source_type))
            
            row = cursor.fetchone()
            
            if row and row['latest_time']:
                try:
                    latest_time = datetime.fromisoformat(row['latest_time'])
                    logger.info(f"数据源 {source_name} 的最近消息时间: {latest_time}")
                    return latest_time
                except Exception as e:
                    logger.warning(f"解析最近消息时间失败: {e}")
                    return None
            else:
                logger.info(f"数据源 {source_name} 没有历史数据")
                return None
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.close()