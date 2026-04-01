import argparse
import json
import sqlite3
from datetime import datetime
from typing import Any, Iterable, Tuple

import psycopg


def _read_rows(sqlite_path: str, table: str, columns: Iterable[str]) -> Iterable[Tuple[Any, ...]]:
    with sqlite3.connect(sqlite_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(f"SELECT {', '.join(columns)} FROM {table}")
        for row in cursor.fetchall():
            yield tuple(row[col] for col in columns)


def _to_json_or_text(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def run_backfill(sqlite_path: str, postgres_url: str) -> None:
    with psycopg.connect(postgres_url) as conn:
        with conn.cursor() as cur:
            for row in _read_rows(
                sqlite_path,
                "content_items",
                [
                    "id",
                    "title",
                    "content",
                    "url",
                    "publish_time",
                    "source_name",
                    "source_type",
                    "content_hash",
                    "created_at",
                ],
            ):
                cur.execute(
                    """
                    INSERT INTO content_items
                    (id, title, content, url, publish_time, source_name, source_type, content_hash, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO NOTHING
                    """,
                    row,
                )

            for row in _read_rows(
                sqlite_path,
                "crawl_status",
                ["execution_time", "total_items", "rss_results", "x_results", "created_at"],
            ):
                cur.execute(
                    """
                    INSERT INTO crawl_status
                    (execution_time, total_items, rss_results, x_results, created_at)
                    VALUES (%s, %s, %s::jsonb, %s::jsonb, %s)
                    """,
                    (
                        row[0],
                        row[1],
                        json.dumps(_to_json_or_text(row[2]), ensure_ascii=False),
                        json.dumps(_to_json_or_text(row[3]), ensure_ascii=False),
                        row[4],
                    ),
                )

            for row in _read_rows(
                sqlite_path,
                "analysis_execution_log",
                [
                    "chat_id",
                    "execution_time",
                    "time_window_hours",
                    "items_count",
                    "success",
                    "error_message",
                    "created_at",
                ],
            ):
                cur.execute(
                    """
                    INSERT INTO analysis_execution_log
                    (chat_id, execution_time, time_window_hours, items_count, success, error_message, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    row,
                )

            for row in _read_rows(
                sqlite_path,
                "sent_message_cache",
                ["title", "body", "category", "time", "sent_at", "recipient_key", "created_at"],
            ):
                cur.execute(
                    """
                    INSERT INTO sent_message_cache
                    (title, body, category, time, sent_at, recipient_key, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    row,
                )

        conn.commit()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sqlite-path", required=True)
    parser.add_argument("--postgres-url", required=True)
    args = parser.parse_args()
    run_backfill(args.sqlite_path, args.postgres_url)


if __name__ == "__main__":
    main()
