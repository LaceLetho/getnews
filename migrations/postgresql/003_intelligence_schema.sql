CREATE EXTENSION IF NOT EXISTS vector;

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
    published_at TIMESTAMPTZ,
    collected_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMPTZ NOT NULL,
    edit_status TEXT,
    edit_timestamp TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_intelligence_raw_items_source
ON raw_intelligence_items (source_type, source_id);

CREATE INDEX IF NOT EXISTS idx_intelligence_raw_items_expires_at
ON raw_intelligence_items (expires_at);

CREATE INDEX IF NOT EXISTS idx_intelligence_raw_items_content_hash
ON raw_intelligence_items (content_hash);

CREATE INDEX IF NOT EXISTS idx_intelligence_raw_items_collected_at
ON raw_intelligence_items (collected_at);

CREATE INDEX IF NOT EXISTS idx_intelligence_raw_items_external_id
ON raw_intelligence_items (external_id);

DROP INDEX IF EXISTS idx_intelligence_raw_items_dedupe;

CREATE UNIQUE INDEX IF NOT EXISTS idx_intelligence_raw_items_external_dedupe
ON raw_intelligence_items (source_type, source_id, external_id)
WHERE external_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS intelligence_extraction_observations (
    id TEXT PRIMARY KEY,
    raw_item_id TEXT NOT NULL,
    entry_type TEXT NOT NULL,
    channel_name TEXT,
    channel_description TEXT,
    channel_urls JSONB NOT NULL DEFAULT '[]'::jsonb,
    channel_handles JSONB NOT NULL DEFAULT '[]'::jsonb,
    channel_domains JSONB NOT NULL DEFAULT '[]'::jsonb,
    term TEXT,
    normalized_term TEXT,
    literal_meaning TEXT,
    contextual_meaning TEXT,
    usage_example_raw_item_id TEXT,
    usage_quote TEXT,
    aliases_or_variants JSONB NOT NULL DEFAULT '[]'::jsonb,
    detected_language TEXT,
    primary_label TEXT,
    secondary_tags JSONB NOT NULL DEFAULT '[]'::jsonb,
    confidence FLOAT NOT NULL DEFAULT 0.0,
    model_name TEXT NOT NULL,
    prompt_version TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    is_canonicalized BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (raw_item_id) REFERENCES raw_intelligence_items (id) ON DELETE CASCADE,
    FOREIGN KEY (usage_example_raw_item_id) REFERENCES raw_intelligence_items (id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_intelligence_observations_raw_item_id
ON intelligence_extraction_observations (raw_item_id);

CREATE INDEX IF NOT EXISTS idx_intelligence_observations_entry_type
ON intelligence_extraction_observations (entry_type);

CREATE INDEX IF NOT EXISTS idx_intelligence_observations_primary_label
ON intelligence_extraction_observations (primary_label);

CREATE INDEX IF NOT EXISTS idx_intelligence_observations_confidence
ON intelligence_extraction_observations (confidence);

CREATE INDEX IF NOT EXISTS idx_intelligence_observations_is_canonicalized
ON intelligence_extraction_observations (is_canonicalized);

CREATE TABLE IF NOT EXISTS intelligence_canonical_entries (
    id TEXT PRIMARY KEY,
    entry_type TEXT NOT NULL,
    normalized_key TEXT NOT NULL,
    display_name TEXT NOT NULL,
    explanation TEXT,
    usage_summary TEXT,
    primary_label TEXT,
    secondary_tags JSONB NOT NULL DEFAULT '[]'::jsonb,
    confidence FLOAT NOT NULL DEFAULT 0.0,
    first_seen_at TIMESTAMPTZ,
    last_seen_at TIMESTAMPTZ,
    evidence_count INTEGER NOT NULL DEFAULT 1,
    latest_raw_item_id TEXT,
    prompt_version TEXT,
    model_name TEXT,
    schema_version TEXT,
    embedding vector(1536),
    embedding_model TEXT,
    embedding_updated_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (latest_raw_item_id) REFERENCES raw_intelligence_items (id) ON DELETE SET NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_intelligence_canonical_entries_type_key
ON intelligence_canonical_entries (entry_type, normalized_key);

CREATE INDEX IF NOT EXISTS idx_intelligence_canonical_entries_entry_type
ON intelligence_canonical_entries (entry_type);

CREATE INDEX IF NOT EXISTS idx_intelligence_canonical_entries_primary_label
ON intelligence_canonical_entries (primary_label);

CREATE INDEX IF NOT EXISTS idx_intelligence_canonical_entries_last_seen_at
ON intelligence_canonical_entries (last_seen_at);

CREATE INDEX IF NOT EXISTS idx_intelligence_canonical_entries_embedding_model
ON intelligence_canonical_entries (embedding_model);

CREATE TABLE IF NOT EXISTS intelligence_aliases (
    canonical_entry_id TEXT NOT NULL,
    alias TEXT NOT NULL,
    source_type TEXT,
    confidence FLOAT NOT NULL DEFAULT 0.0,
    PRIMARY KEY (canonical_entry_id, alias),
    FOREIGN KEY (canonical_entry_id) REFERENCES intelligence_canonical_entries (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_intelligence_aliases_alias
ON intelligence_aliases (alias);

CREATE TABLE IF NOT EXISTS intelligence_related_candidates (
    entry_id_a TEXT NOT NULL,
    entry_id_b TEXT NOT NULL,
    similarity_score FLOAT,
    relationship_type TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (entry_id_a, entry_id_b),
    FOREIGN KEY (entry_id_a) REFERENCES intelligence_canonical_entries (id) ON DELETE CASCADE,
    FOREIGN KEY (entry_id_b) REFERENCES intelligence_canonical_entries (id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_intelligence_related_candidates_pair
ON intelligence_related_candidates (entry_id_a, entry_id_b);

CREATE INDEX IF NOT EXISTS idx_intelligence_related_candidates_entry_id_a
ON intelligence_related_candidates (entry_id_a);

CREATE INDEX IF NOT EXISTS idx_intelligence_related_candidates_entry_id_b
ON intelligence_related_candidates (entry_id_b);

CREATE TABLE IF NOT EXISTS intelligence_crawl_checkpoints (
    source_type TEXT NOT NULL,
    source_id TEXT NOT NULL,
    last_crawled_at TIMESTAMPTZ,
    last_external_id TEXT,
    checkpoint_data JSONB NOT NULL DEFAULT '{}'::jsonb,
    status TEXT,
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (source_type, source_id)
);

CREATE INDEX IF NOT EXISTS idx_intelligence_crawl_checkpoints_status
ON intelligence_crawl_checkpoints (status);

CREATE INDEX IF NOT EXISTS idx_intelligence_crawl_checkpoints_updated_at
ON intelligence_crawl_checkpoints (updated_at);
