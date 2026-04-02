import argparse
import json
import os
import sqlite3

import psycopg


def read_rows(sqlite_path, table, columns):
    with sqlite3.connect(sqlite_path) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        query = "SELECT {} FROM {}".format(", ".join(columns), table)
        cur.execute(query)
        while True:
            rows = cur.fetchmany(5000)
            if not rows:
                break
            for row in rows:
                yield tuple(row[col] for col in columns)


def to_json_or_text(value):
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def print_counts(cur, prefix):
    for table in [
        "content_items",
        "crawl_status",
        "analysis_execution_log",
        "sent_message_cache",
    ]:
        cur.execute("SELECT COUNT(*) FROM {}".format(table))
        count = cur.fetchone()[0]
        print("[{}] {}: {}".format(prefix, table, count), flush=True)


def run_backfill(sqlite_path, postgres_url):
    with psycopg.connect(postgres_url) as conn:
        with conn.cursor() as cur:
            cur.execute("SET statement_timeout = 0")
            cur.execute(
                "TRUNCATE TABLE sent_message_cache, analysis_execution_log, crawl_status, content_items RESTART IDENTITY"
            )
            conn.commit()
            print("[backfill] truncated target tables", flush=True)

            with cur.copy(
                "COPY content_items (id, title, content, url, publish_time, source_name, source_type, content_hash, created_at) FROM STDIN"
            ) as copy:
                total = 0
                for row in read_rows(
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
                    copy.write_row(row)
                    total += 1
                    if total % 10000 == 0:
                        print("[backfill] content_items streamed {}".format(total), flush=True)
            conn.commit()
            print("[backfill] content_items committed", flush=True)

            with cur.copy(
                "COPY crawl_status (execution_time, total_items, rss_results, x_results, created_at) FROM STDIN"
            ) as copy:
                for row in read_rows(
                    sqlite_path,
                    "crawl_status",
                    ["execution_time", "total_items", "rss_results", "x_results", "created_at"],
                ):
                    copy.write_row(
                        (
                            row[0],
                            row[1],
                            json.dumps(to_json_or_text(row[2]), ensure_ascii=False),
                            json.dumps(to_json_or_text(row[3]), ensure_ascii=False),
                            row[4],
                        )
                    )
            conn.commit()
            print("[backfill] crawl_status committed", flush=True)

            with cur.copy(
                "COPY analysis_execution_log (chat_id, execution_time, time_window_hours, items_count, success, error_message, created_at) FROM STDIN"
            ) as copy:
                for row in read_rows(
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
                    copy.write_row(row)
            conn.commit()
            print("[backfill] analysis_execution_log committed", flush=True)

            with cur.copy(
                "COPY sent_message_cache (title, body, category, time, sent_at, recipient_key, created_at) FROM STDIN"
            ) as copy:
                for row in read_rows(
                    sqlite_path,
                    "sent_message_cache",
                    ["title", "body", "category", "time", "sent_at", "recipient_key", "created_at"],
                ):
                    copy.write_row(row)
            conn.commit()
            print("[backfill] sent_message_cache committed", flush=True)

            print_counts(cur, "final")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sqlite-path", default="/app/data/crypto_news.db")
    parser.add_argument("--postgres-url", default=os.getenv("DATABASE_URL"))
    args = parser.parse_args()

    if not args.postgres_url:
        raise ValueError("--postgres-url is required when DATABASE_URL is not set")

    run_backfill(args.sqlite_path, args.postgres_url)


if __name__ == "__main__":
    main()
