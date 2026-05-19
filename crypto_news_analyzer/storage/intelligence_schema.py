"""Intelligence domain database schema initialization.

Extracted from DataManager to keep the data access layer focused.
These functions create the intelligence-related tables used by the topic research pipeline.
"""

# flake8: noqa: E501 (SQL DDL statements contain long string literals)

from typing import Any


def initialize_intelligence_tables(
    cursor: Any,
    backend: str,
    pgvector_dimensions: int,
) -> None:
    """Create core intelligence tables: raw_intelligence_items, intelligence_topics, crawl_checkpoints."""
    json_default_empty_object = "'{}'::jsonb" if backend == "postgres" else "'{}'"
    json_default_empty_list = "'[]'::jsonb" if backend == "postgres" else "'[]'"
    datetime_type = "TIMESTAMPTZ" if backend == "postgres" else "DATETIME"
    embedding_type = f"vector({pgvector_dimensions})" if backend == "postgres" else "TEXT"

    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS raw_intelligence_items (
            id TEXT PRIMARY KEY,
            source_type TEXT NOT NULL,
            source_id TEXT,
            external_id TEXT,
            source_url TEXT,
            chat_id TEXT,
            thread_id TEXT,
            topic_id TEXT,
            raw_text TEXT,
            content_hash TEXT NOT NULL,
            published_at {datetime_type},
            collected_at {datetime_type} NOT NULL DEFAULT CURRENT_TIMESTAMP,
            expires_at {datetime_type} NOT NULL,
            edit_status TEXT,
            edit_timestamp {datetime_type},
            created_at {datetime_type} DEFAULT CURRENT_TIMESTAMP
        )
    """)
    if backend == "postgres":
        cursor.execute("ALTER TABLE raw_intelligence_items ALTER COLUMN raw_text DROP NOT NULL")
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS intelligence_topics (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            lifecycle_status TEXT NOT NULL DEFAULT 'active',
            created_at {datetime_type} DEFAULT CURRENT_TIMESTAMP,
            updated_at {datetime_type} DEFAULT CURRENT_TIMESTAMP
        )
    """)
    _initialize_topic_only_tables(
        cursor, backend, json_default_empty_object, json_default_empty_list, datetime_type
    )
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS intelligence_crawl_checkpoints (
            source_type TEXT NOT NULL,
            source_id TEXT NOT NULL,
            last_crawled_at {datetime_type},
            last_external_id TEXT,
            checkpoint_data {'JSONB' if backend == 'postgres' else 'TEXT'} NOT NULL DEFAULT {json_default_empty_object},
            status TEXT,
            error_message TEXT,
            created_at {datetime_type} DEFAULT CURRENT_TIMESTAMP,
            updated_at {datetime_type} DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (source_type, source_id)
        )
    """)
    if backend == "postgres":
        cursor.execute("DROP INDEX IF EXISTS idx_intelligence_raw_items_dedupe")
    else:
        cursor.execute("DROP INDEX IF EXISTS idx_intelligence_raw_items_dedupe")

    for statement in [
        (
            "CREATE INDEX IF NOT EXISTS idx_intelligence_raw_items_source "
            "ON raw_intelligence_items (source_type, source_id)"
        ),
        (
            "CREATE INDEX IF NOT EXISTS idx_intelligence_raw_items_expires_at "
            "ON raw_intelligence_items (expires_at)"
        ),
        (
            "CREATE INDEX IF NOT EXISTS idx_intelligence_raw_items_content_hash "
            "ON raw_intelligence_items (content_hash)"
        ),
        (
            "CREATE INDEX IF NOT EXISTS idx_intelligence_raw_items_collected_at "
            "ON raw_intelligence_items (collected_at)"
        ),
        (
            "CREATE INDEX IF NOT EXISTS idx_intelligence_raw_items_external_id "
            "ON raw_intelligence_items (external_id)"
        ),
        (
            "CREATE UNIQUE INDEX IF NOT EXISTS "
            "idx_intelligence_raw_items_external_dedupe "
            "ON raw_intelligence_items (source_type, source_id, external_id) "
            "WHERE external_id IS NOT NULL"
        ),
        (
            "CREATE INDEX IF NOT EXISTS idx_intelligence_crawl_checkpoints_status "
            "ON intelligence_crawl_checkpoints (status)"
        ),
        (
            "CREATE INDEX IF NOT EXISTS idx_intelligence_crawl_checkpoints_updated_at "
            "ON intelligence_crawl_checkpoints (updated_at)"
        ),
        (
            "CREATE INDEX IF NOT EXISTS idx_intelligence_topics_active "
            "ON intelligence_topics (is_active, updated_at DESC)"
        ),
        (
            "CREATE INDEX IF NOT EXISTS idx_intelligence_topics_lifecycle_status "
            "ON intelligence_topics (lifecycle_status, updated_at DESC)"
        ),
    ]:
        cursor.execute(statement)


def _initialize_topic_only_tables(
    cursor: Any,
    backend: str,
    json_default_empty_object: str,
    json_default_empty_list: str,
    datetime_type: str,
) -> None:
    """Create topic-only intelligence tables: prompts, findings, research runs, merge previews, etc."""
    json_type = "JSONB" if backend == "postgres" else "TEXT"

    if backend == "postgres":
        cursor.execute("""
            ALTER TABLE intelligence_topics
            ADD COLUMN IF NOT EXISTS lifecycle_status TEXT NOT NULL DEFAULT 'active'
        """)
    else:
        cursor.execute("PRAGMA table_info(intelligence_topics)")
        if "lifecycle_status" not in {row[1] for row in cursor.fetchall()}:
            cursor.execute(
                "ALTER TABLE intelligence_topics "
                "ADD COLUMN lifecycle_status TEXT NOT NULL DEFAULT 'active'"
            )

    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS intelligence_topic_prompt_versions (
            id TEXT PRIMARY KEY,
            intelligence_topic_id TEXT NOT NULL,
            prompt_version TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'draft',
            prompt_text TEXT NOT NULL,
            schema_version TEXT NOT NULL,
            created_by TEXT,
            activated_by TEXT,
            activation_notes TEXT,
            audit_history {json_type} NOT NULL DEFAULT {json_default_empty_list},
            created_at {datetime_type} DEFAULT CURRENT_TIMESTAMP,
            activated_at {datetime_type},
            archived_at {datetime_type},
            updated_at {datetime_type} DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (intelligence_topic_id) REFERENCES intelligence_topics (id) ON DELETE CASCADE,
            UNIQUE (intelligence_topic_id, prompt_version)
        )
    """)
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS intelligence_topic_findings (
            id TEXT PRIMARY KEY,
            intelligence_topic_id TEXT NOT NULL,
            prompt_version_id TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            finding_payload {json_type} NOT NULL DEFAULT {json_default_empty_object},
            citations {json_type} NOT NULL DEFAULT {json_default_empty_list},
            source_raw_item_ids {json_type} NOT NULL DEFAULT {json_default_empty_list},
            source_finding_ids {json_type} NOT NULL DEFAULT {json_default_empty_list},
            content_hash TEXT NOT NULL,
            confidence FLOAT NOT NULL DEFAULT 0.0,
            found_at {datetime_type},
            archived_at {datetime_type},
            superseded_by_finding_id TEXT,
            created_at {datetime_type} DEFAULT CURRENT_TIMESTAMP,
            updated_at {datetime_type} DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (intelligence_topic_id) REFERENCES intelligence_topics (id) ON DELETE CASCADE,
            FOREIGN KEY (prompt_version_id) REFERENCES intelligence_topic_prompt_versions (id) ON DELETE RESTRICT,
            FOREIGN KEY (superseded_by_finding_id) REFERENCES intelligence_topic_findings (id) ON DELETE SET NULL
        )
    """)
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS intelligence_topic_processed_raw_items (
            raw_item_id TEXT NOT NULL,
            intelligence_topic_id TEXT NOT NULL,
            prompt_version TEXT NOT NULL,
            schema_version TEXT NOT NULL,
            finding_id TEXT,
            processed_at {datetime_type} DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (raw_item_id, intelligence_topic_id, prompt_version, schema_version),
            FOREIGN KEY (raw_item_id) REFERENCES raw_intelligence_items (id) ON DELETE CASCADE,
            FOREIGN KEY (intelligence_topic_id) REFERENCES intelligence_topics (id) ON DELETE CASCADE,
            FOREIGN KEY (finding_id) REFERENCES intelligence_topic_findings (id) ON DELETE SET NULL
        )
    """)
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS intelligence_topic_research_runs (
            id TEXT PRIMARY KEY,
            intelligence_topic_id TEXT NOT NULL,
            prompt_version_id TEXT,
            status TEXT NOT NULL,
            checkpoint_cursor TEXT,
            checkpoint_payload {json_type} NOT NULL DEFAULT {json_default_empty_object},
            items_scanned INTEGER NOT NULL DEFAULT 0,
            findings_created INTEGER NOT NULL DEFAULT 0,
            error_message TEXT,
            started_at {datetime_type},
            finished_at {datetime_type},
            created_at {datetime_type} DEFAULT CURRENT_TIMESTAMP,
            updated_at {datetime_type} DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (intelligence_topic_id) REFERENCES intelligence_topics (id) ON DELETE CASCADE,
            FOREIGN KEY (prompt_version_id) REFERENCES intelligence_topic_prompt_versions (id) ON DELETE SET NULL
        )
    """)
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS intelligence_topic_research_checkpoints (
            intelligence_topic_id TEXT NOT NULL,
            prompt_version_id TEXT,
            checkpoint_cursor TEXT,
            checkpoint_payload {json_type} NOT NULL DEFAULT {json_default_empty_object},
            last_run_id TEXT,
            updated_at {datetime_type} DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (intelligence_topic_id, prompt_version_id),
            FOREIGN KEY (intelligence_topic_id) REFERENCES intelligence_topics (id) ON DELETE CASCADE,
            FOREIGN KEY (prompt_version_id) REFERENCES intelligence_topic_prompt_versions (id) ON DELETE CASCADE,
            FOREIGN KEY (last_run_id) REFERENCES intelligence_topic_research_runs (id) ON DELETE SET NULL
        )
    """)
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS intelligence_topic_merge_previews (
            id TEXT PRIMARY KEY,
            intelligence_topic_id TEXT NOT NULL,
            source_finding_ids {json_type} NOT NULL DEFAULT {json_default_empty_list},
            preview_payload {json_type} NOT NULL DEFAULT {json_default_empty_object},
            content_hash TEXT NOT NULL,
            state TEXT NOT NULL DEFAULT 'pending',
            created_by TEXT,
            expires_at {datetime_type} NOT NULL,
            applied_at {datetime_type},
            created_at {datetime_type} DEFAULT CURRENT_TIMESTAMP,
            updated_at {datetime_type} DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (intelligence_topic_id) REFERENCES intelligence_topics (id) ON DELETE CASCADE
        )
    """)
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS intelligence_finding_archives (
            finding_id TEXT PRIMARY KEY,
            intelligence_topic_id TEXT NOT NULL,
            archive_reason TEXT,
            archive_metadata {json_type} NOT NULL DEFAULT {json_default_empty_object},
            superseded_by_finding_id TEXT,
            archived_by TEXT,
            archived_at {datetime_type} DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (finding_id) REFERENCES intelligence_topic_findings (id) ON DELETE CASCADE,
            FOREIGN KEY (intelligence_topic_id) REFERENCES intelligence_topics (id) ON DELETE CASCADE,
            FOREIGN KEY (superseded_by_finding_id) REFERENCES intelligence_topic_findings (id) ON DELETE SET NULL
        )
    """)

    for statement in [
        (
            "CREATE INDEX IF NOT EXISTS idx_intelligence_topic_prompt_versions_topic "
            "ON intelligence_topic_prompt_versions (intelligence_topic_id, status, created_at DESC)"
        ),
        (
            "CREATE INDEX IF NOT EXISTS idx_intelligence_topic_findings_topic_status "
            "ON intelligence_topic_findings (intelligence_topic_id, status, updated_at DESC)"
        ),
        (
            "CREATE INDEX IF NOT EXISTS idx_intelligence_topic_findings_prompt_version "
            "ON intelligence_topic_findings (prompt_version_id)"
        ),
        (
            "CREATE INDEX IF NOT EXISTS idx_intelligence_topic_research_runs_topic "
            "ON intelligence_topic_research_runs (intelligence_topic_id, created_at DESC)"
        ),
        (
            "CREATE INDEX IF NOT EXISTS idx_intelligence_topic_merge_previews_topic_state "
            "ON intelligence_topic_merge_previews (intelligence_topic_id, state, expires_at)"
        ),
    ]:
        cursor.execute(statement)
