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
            lifecycle_status TEXT NOT NULL DEFAULT 'active',
            created_at {datetime_type} DEFAULT CURRENT_TIMESTAMP,
            updated_at {datetime_type} DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ── Migration: is_active removal + paused→archived
    cursor.execute("UPDATE intelligence_topics SET lifecycle_status = 'archived' WHERE lifecycle_status = 'paused'")
    cursor.execute("DROP INDEX IF EXISTS idx_intelligence_topics_active")
    if backend == "postgres":
        cursor.execute("ALTER TABLE intelligence_topics DROP COLUMN IF EXISTS is_active")

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

    # ── 011: topic–datasource association & raw item back-reference ──────────
    _initialize_topic_datasource_schema(
        cursor, backend, datetime_type
    )

    if backend == "postgres":
        cursor.execute("DROP INDEX IF EXISTS idx_intelligence_raw_items_dedupe")
    else:
        cursor.execute("DROP INDEX IF EXISTS idx_intelligence_raw_items_dedupe")

    # ── 012: embedding columns on raw_intelligence_items ─────────────────
    if backend == "postgres":
        for col in ["embedding vector(1536)", "embedding_model TEXT", "embedding_updated_at TIMESTAMPTZ"]:
            cursor.execute(
                f"ALTER TABLE raw_intelligence_items ADD COLUMN IF NOT EXISTS {col}"
            )

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
            "CREATE INDEX IF NOT EXISTS idx_intelligence_topics_lifecycle_status "
            "ON intelligence_topics (lifecycle_status, updated_at DESC)"
        ),
        (
            "CREATE INDEX IF NOT EXISTS idx_intelligence_raw_items_datasource_id "
            "ON raw_intelligence_items (datasource_id)"
        ),
    ]:
        cursor.execute(statement)

    if backend == "postgres":
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_content_embedding_hnsw "
            "ON content_items USING hnsw (embedding vector_cosine_ops) "
            "WHERE embedding IS NOT NULL"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_intelligence_embedding_hnsw "
            "ON raw_intelligence_items USING hnsw (embedding vector_cosine_ops) "
            "WHERE embedding IS NOT NULL"
        )


def _initialize_topic_datasource_schema(
    cursor: Any,
    backend: str,
    datetime_type: str,
) -> None:
    """Create topic–datasource M:N join table and add datasource_id column to raw items."""
    # PostgreSQL ADD COLUMN supports IF NOT EXISTS; SQLite requires PRAGMA check
    if backend == "postgres":
        cursor.execute(
            "ALTER TABLE raw_intelligence_items "
            "ADD COLUMN IF NOT EXISTS datasource_id TEXT"
        )
    else:
        cursor.execute("PRAGMA table_info(raw_intelligence_items)")
        if "datasource_id" not in {row[1] for row in cursor.fetchall()}:
            cursor.execute(
                "ALTER TABLE raw_intelligence_items ADD COLUMN datasource_id TEXT"
            )

    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS intelligence_topic_datasources (
            topic_id      TEXT NOT NULL,
            datasource_id TEXT NOT NULL,
            created_at    {datetime_type} DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (topic_id, datasource_id),
            FOREIGN KEY (topic_id)      REFERENCES intelligence_topics (id) ON DELETE CASCADE,
            FOREIGN KEY (datasource_id) REFERENCES datasources (id)         ON DELETE RESTRICT
        )
    """)

    # ── Backfill: link every existing topic to every intelligence datasource ─
    if backend == "postgres":
        cursor.execute("""
            INSERT INTO intelligence_topic_datasources (topic_id, datasource_id)
            SELECT t.id, d.id
            FROM intelligence_topics t
            CROSS JOIN datasources d
            WHERE d.purpose = 'intelligence'
            ON CONFLICT (topic_id, datasource_id) DO NOTHING
        """)
    else:
        cursor.execute("""
            INSERT OR IGNORE INTO intelligence_topic_datasources (topic_id, datasource_id)
            SELECT t.id, d.id
            FROM intelligence_topics t
            CROSS JOIN datasources d
            WHERE d.purpose = 'intelligence'
        """)

    # ── Backfill: best-effort raw_intelligence_items.datasource_id ─
    # Matches items by source_type + source_id (direct or chat_id in config_payload)
    # SQLite uses json_extract instead of PostgreSQL ->> operator
    if backend == "sqlite":
        cursor.execute("""
            UPDATE raw_intelligence_items
            SET datasource_id = (
                SELECT d.id
                FROM datasources d
                WHERE d.purpose = 'intelligence'
                  AND d.source_type = raw_intelligence_items.source_type
                  AND (
                      raw_intelligence_items.source_id = d.id
                      OR raw_intelligence_items.source_id = json_extract(d.config_payload, '$.chat_id')
                  )
                LIMIT 1
            )
            WHERE datasource_id IS NULL
        """)
    else:
        cursor.execute("""
            UPDATE raw_intelligence_items
            SET datasource_id = d.id
            FROM datasources d
            WHERE raw_intelligence_items.datasource_id IS NULL
              AND raw_intelligence_items.source_type = d.source_type
              AND d.purpose = 'intelligence'
              AND (
                  raw_intelligence_items.source_id = d.id
                  OR (
                      d.config_payload ->> 'chat_id' IS NOT NULL
                      AND raw_intelligence_items.source_id = (d.config_payload ->> 'chat_id')::TEXT
                  )
              )
        """)


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
