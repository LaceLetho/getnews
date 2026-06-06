import json
import sqlite3
from datetime import datetime, timedelta

from crypto_news_analyzer.domain.models import (
    DataSource,
    IntelligenceTopic,
    RawIntelligenceItem,
)
from crypto_news_analyzer.models import StorageConfig
from crypto_news_analyzer.storage.data_manager import DataManager


def _seed_datasource(conn: sqlite3.Connection, ds: DataSource) -> None:
    conn.execute(
        """INSERT OR REPLACE INTO datasources (id, purpose, source_type, name, config_payload, created_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (
            ds.id,
            ds.purpose,
            ds.source_type,
            ds.name,
            json.dumps(ds.config_payload),
            (ds.created_at or datetime.utcnow()).isoformat(),
        ),
    )


def _seed_topic(conn: sqlite3.Connection, topic: IntelligenceTopic) -> None:
    conn.execute(
        """INSERT OR REPLACE INTO intelligence_topics (id, name, is_active, lifecycle_status, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (
            topic.id,
            topic.name,
            1 if topic.lifecycle_status == "active" else 0,
            topic.lifecycle_status,
            (topic.created_at or datetime.utcnow()).isoformat(),
            (topic.updated_at or datetime.utcnow()).isoformat(),
        ),
    )


def _seed_raw_item(conn: sqlite3.Connection, item: RawIntelligenceItem) -> None:
    conn.execute(
        """INSERT OR REPLACE INTO raw_intelligence_items
           (id, source_type, source_id, external_id, source_url, chat_id, thread_id,
            topic_id, raw_text, content_hash, published_at, collected_at, expires_at,
            edit_status, edit_timestamp, created_at, datasource_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            item.id,
            item.source_type,
            item.source_id,
            item.external_id,
            item.source_url,
            item.chat_id,
            item.thread_id,
            item.topic_id,
            item.raw_text,
            item.content_hash,
            item.published_at.isoformat() if item.published_at else None,
            item.collected_at.isoformat() if item.collected_at else None,
            item.expires_at.isoformat() if item.expires_at else None,
            item.edit_status,
            item.edit_timestamp.isoformat() if item.edit_timestamp else None,
            item.created_at.isoformat() if item.created_at else None,
            item.datasource_id,
        ),
    )


# ── Tests ────────────────────────────────────────────────────────────────────


class TestTopicDatasourceSchema:
    """Verify that the 011 schema changes produce correct tables and columns."""

    def test_schema_creates_intelligence_topic_datasources_table(self, tmp_path):
        db_path = tmp_path / "test.db"
        manager = DataManager(
            StorageConfig(backend="sqlite", database_path=str(db_path))
        )

        with sqlite3.connect(manager.db_path) as conn:
            tables = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }

        assert "intelligence_topic_datasources" in tables

    def test_schema_adds_datasource_id_column_to_raw_items(self, tmp_path):
        db_path = tmp_path / "test.db"
        manager = DataManager(
            StorageConfig(backend="sqlite", database_path=str(db_path))
        )

        with sqlite3.connect(manager.db_path) as conn:
            columns = {
                row[1]
                for row in conn.execute(
                    "PRAGMA table_info(raw_intelligence_items)"
                ).fetchall()
            }

        assert "datasource_id" in columns

    def test_schema_creates_datasource_id_index(self, tmp_path):
        db_path = tmp_path / "test.db"
        manager = DataManager(
            StorageConfig(backend="sqlite", database_path=str(db_path))
        )

        with sqlite3.connect(manager.db_path) as conn:
            indexes = {
                row[1]
                for row in conn.execute(
                    "SELECT type, name FROM sqlite_master WHERE type = 'index'"
                ).fetchall()
            }

        assert "idx_intelligence_raw_items_datasource_id" in indexes


class TestTopicDatasourceBackfill:
    """Verify the DML backfill behaviour (simulated in SQLite)."""

    def _seed_and_backfill_topic_links(self, conn: sqlite3.Connection) -> None:
        """Run the equivalent of the migration backfill DML."""
        conn.execute("""
            INSERT OR IGNORE INTO intelligence_topic_datasources (topic_id, datasource_id)
            SELECT t.id, d.id
            FROM intelligence_topics t
            CROSS JOIN datasources d
            WHERE d.purpose = 'intelligence'
        """)

    def test_backfill_links_all_topics_to_intelligence_datasources(self, tmp_path):
        db_path = tmp_path / "test.db"
        manager = DataManager(
            StorageConfig(backend="sqlite", database_path=str(db_path))
        )

        intel_ds = DataSource.create(
            name="Crypto Telegram",
            source_type="telegram_group",
            purpose="intelligence",
            config_payload={"chat_id": -100123},
        )
        news_ds = DataSource.create(
            name="CoinDesk",
            source_type="rss",
            purpose="news",
            config_payload={"url": "https://example.com/rss"},
        )
        topic_a = IntelligenceTopic.create(name="Exploit Watch")
        topic_b = IntelligenceTopic.create(name="Regulation Monitor")

        with sqlite3.connect(manager.db_path) as conn:
            for ds in (intel_ds, news_ds):
                _seed_datasource(conn, ds)
            for t in (topic_a, topic_b):
                _seed_topic(conn, t)
            conn.commit()

            self._seed_and_backfill_topic_links(conn)

            rows = conn.execute(
                "SELECT topic_id, datasource_id FROM intelligence_topic_datasources ORDER BY topic_id"
            ).fetchall()
            conn.commit()

        linked_pairs = {(r[0], r[1]) for r in rows}

        # Both topics linked to the intelligence datasource
        assert (topic_a.id, intel_ds.id) in linked_pairs
        assert (topic_b.id, intel_ds.id) in linked_pairs

        # News datasource must NOT be linked
        assert (topic_a.id, news_ds.id) not in linked_pairs
        assert (topic_b.id, news_ds.id) not in linked_pairs

    def test_backfill_is_idempotent(self, tmp_path):
        db_path = tmp_path / "test.db"
        manager = DataManager(
            StorageConfig(backend="sqlite", database_path=str(db_path))
        )

        intel_ds = DataSource.create(
            name="V2EX",
            source_type="v2ex",
            purpose="intelligence",
            config_payload={},
        )
        topic = IntelligenceTopic.create(name="Dev Talk")

        with sqlite3.connect(manager.db_path) as conn:
            _seed_datasource(conn, intel_ds)
            _seed_topic(conn, topic)
            conn.commit()

            # Run backfill twice
            self._seed_and_backfill_topic_links(conn)
            self._seed_and_backfill_topic_links(conn)

            count = conn.execute(
                "SELECT COUNT(*) FROM intelligence_topic_datasources"
            ).fetchone()[0]

        # Must still be 1, not duplicated
        assert count == 1


class TestRawItemDatasourceId:
    """Verify best-effort raw item datasource_id backfill behaviour."""

    def _seed_and_backfill_raw_items(self, conn: sqlite3.Connection) -> None:
        """Run the equivalent of the migration best-effort raw item backfill."""
        conn.execute("""
            UPDATE raw_intelligence_items
            SET datasource_id = (
                SELECT d.id
                FROM datasources d
                WHERE d.purpose = 'intelligence'
                  AND raw_intelligence_items.source_type = d.source_type
                  AND (
                      raw_intelligence_items.source_id = d.id
                      OR (
                          json_extract(d.config_payload, '$.chat_id') IS NOT NULL
                          AND raw_intelligence_items.source_id = CAST(json_extract(d.config_payload, '$.chat_id') AS TEXT)
                      )
                  )
                LIMIT 1
            )
            WHERE datasource_id IS NULL
        """)

    def test_mappable_raw_item_gets_datasource_id(self, tmp_path):
        db_path = tmp_path / "test.db"
        manager = DataManager(
            StorageConfig(backend="sqlite", database_path=str(db_path))
        )

        ds = DataSource.create(
            name="Alpha Chat",
            source_type="telegram_group",
            purpose="intelligence",
            config_payload={"chat_id": -100999},
        )
        item = RawIntelligenceItem.create(
            source_type="telegram_group",
            source_id="-100999",
            raw_text="Big whale move",
            content_hash="abc123",
            expires_at=datetime.utcnow() + timedelta(days=30),
        )

        with sqlite3.connect(manager.db_path) as conn:
            _seed_datasource(conn, ds)
            _seed_raw_item(conn, item)
            conn.commit()

            self._seed_and_backfill_raw_items(conn)

            row = conn.execute(
                "SELECT datasource_id FROM raw_intelligence_items WHERE id = ?",
                (item.id,),
            ).fetchone()

        assert row is not None
        assert row[0] == ds.id

    def test_unmappable_raw_item_stays_null(self, tmp_path):
        db_path = tmp_path / "test.db"
        manager = DataManager(
            StorageConfig(backend="sqlite", database_path=str(db_path))
        )

        item = RawIntelligenceItem.create(
            source_type="unknown_protocol",
            source_id="ghost-chat",
            raw_text="Mystery message",
            content_hash="zzz999",
            expires_at=datetime.utcnow() + timedelta(days=30),
        )

        with sqlite3.connect(manager.db_path) as conn:
            _seed_raw_item(conn, item)
            conn.commit()

            self._seed_and_backfill_raw_items(conn)

            row = conn.execute(
                "SELECT datasource_id FROM raw_intelligence_items WHERE id = ?",
                (item.id,),
            ).fetchone()

        assert row is not None
        assert row[0] is None

    def test_news_datasource_not_used_for_raw_item_matching(self, tmp_path):
        db_path = tmp_path / "test.db"
        manager = DataManager(
            StorageConfig(backend="sqlite", database_path=str(db_path))
        )

        # A news datasource with same source_type — must NOT match
        news_ds = DataSource.create(
            name="News RSS",
            source_type="rss",
            purpose="news",
            config_payload={"url": "https://example.com/rss"},
        )
        item = RawIntelligenceItem.create(
            source_type="rss",
            source_id=news_ds.id,
            raw_text="Market update",
            content_hash="news123",
            expires_at=datetime.utcnow() + timedelta(days=30),
        )

        with sqlite3.connect(manager.db_path) as conn:
            _seed_datasource(conn, news_ds)
            _seed_raw_item(conn, item)
            conn.commit()

            self._seed_and_backfill_raw_items(conn)

            row = conn.execute(
                "SELECT datasource_id FROM raw_intelligence_items WHERE id = ?",
                (item.id,),
            ).fetchone()

        assert row is not None
        assert row[0] is None


def test_datasource_id_column_nullable(tmp_path):
    """Raw items can be inserted without a datasource_id (column is nullable)."""
    db_path = tmp_path / "test.db"
    manager = DataManager(
        StorageConfig(backend="sqlite", database_path=str(db_path))
    )

    item = RawIntelligenceItem.create(
        source_type="telegram_group",
        source_id="chat-unknown",
        raw_text="Test",
        content_hash="hash-x",
        expires_at=datetime.utcnow() + timedelta(days=30),
    )

    with sqlite3.connect(manager.db_path) as conn:
        _seed_raw_item(conn, item)
        conn.commit()

        row = conn.execute(
            "SELECT id, datasource_id FROM raw_intelligence_items WHERE id = ?",
            (item.id,),
        ).fetchone()

    assert row is not None
    assert row[0] == item.id
    assert row[1] is None  # datasource_id defaults to NULL
