import sqlite3

from crypto_news_analyzer.models import StorageConfig
from crypto_news_analyzer.storage.data_manager import DataManager


def test_intelligence_schema_does_not_create_legacy_entry_tables(tmp_path):
    db_path = tmp_path / "intelligence-cleanup.db"
    manager = DataManager(
        StorageConfig(
            backend="sqlite",
            database_path=str(db_path),
        )
    )

    with sqlite3.connect(manager.db_path) as conn:
        table_names = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        topic_columns = {
            row[1] for row in conn.execute("PRAGMA table_info(intelligence_topics)").fetchall()
        }

    assert "intelligence_extraction_observations" not in table_names
    assert "intelligence_canonical_entries" not in table_names
    assert "intelligence_entry_evidence_links" not in table_names
    assert "intelligence_aliases" not in table_names
    assert "intelligence_related_candidates" not in table_names
    assert "intelligence_topic_run_logs" not in table_names

    assert "description" not in topic_columns
    assert "enriched_summary" not in topic_columns
    assert "source_channels" not in topic_columns
    assert "methods" not in topic_columns
    assert "vulnerabilities" not in topic_columns
    assert "latest_findings" not in topic_columns
    assert "embedding" not in topic_columns
