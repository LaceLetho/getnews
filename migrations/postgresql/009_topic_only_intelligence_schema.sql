ALTER TABLE intelligence_topics
ADD COLUMN IF NOT EXISTS lifecycle_status TEXT NOT NULL DEFAULT 'active';

CREATE INDEX IF NOT EXISTS idx_intelligence_topics_lifecycle_status
ON intelligence_topics (lifecycle_status, updated_at DESC);

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
    audit_history JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    activated_at TIMESTAMPTZ,
    archived_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (intelligence_topic_id) REFERENCES intelligence_topics (id) ON DELETE CASCADE,
    UNIQUE (intelligence_topic_id, prompt_version)
);

CREATE INDEX IF NOT EXISTS idx_intelligence_topic_prompt_versions_topic
ON intelligence_topic_prompt_versions (intelligence_topic_id, status, created_at DESC);

CREATE TABLE IF NOT EXISTS intelligence_topic_findings (
    id TEXT PRIMARY KEY,
    intelligence_topic_id TEXT NOT NULL,
    prompt_version_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    finding_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    citations JSONB NOT NULL DEFAULT '[]'::jsonb,
    source_raw_item_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    source_finding_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    content_hash TEXT NOT NULL,
    confidence FLOAT NOT NULL DEFAULT 0.0,
    found_at TIMESTAMPTZ,
    archived_at TIMESTAMPTZ,
    superseded_by_finding_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (intelligence_topic_id) REFERENCES intelligence_topics (id) ON DELETE CASCADE,
    FOREIGN KEY (prompt_version_id) REFERENCES intelligence_topic_prompt_versions (id) ON DELETE RESTRICT,
    FOREIGN KEY (superseded_by_finding_id) REFERENCES intelligence_topic_findings (id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_intelligence_topic_findings_topic_status
ON intelligence_topic_findings (intelligence_topic_id, status, updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_intelligence_topic_findings_prompt_version
ON intelligence_topic_findings (prompt_version_id);

CREATE TABLE IF NOT EXISTS intelligence_topic_processed_raw_items (
    raw_item_id TEXT NOT NULL,
    intelligence_topic_id TEXT NOT NULL,
    prompt_version TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    finding_id TEXT,
    processed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (raw_item_id, intelligence_topic_id, prompt_version, schema_version),
    FOREIGN KEY (raw_item_id) REFERENCES raw_intelligence_items (id) ON DELETE CASCADE,
    FOREIGN KEY (intelligence_topic_id) REFERENCES intelligence_topics (id) ON DELETE CASCADE,
    FOREIGN KEY (finding_id) REFERENCES intelligence_topic_findings (id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS intelligence_topic_research_runs (
    id TEXT PRIMARY KEY,
    intelligence_topic_id TEXT NOT NULL,
    prompt_version_id TEXT,
    status TEXT NOT NULL,
    checkpoint_cursor TEXT,
    checkpoint_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    items_scanned INTEGER NOT NULL DEFAULT 0,
    findings_created INTEGER NOT NULL DEFAULT 0,
    error_message TEXT,
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (intelligence_topic_id) REFERENCES intelligence_topics (id) ON DELETE CASCADE,
    FOREIGN KEY (prompt_version_id) REFERENCES intelligence_topic_prompt_versions (id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_intelligence_topic_research_runs_topic
ON intelligence_topic_research_runs (intelligence_topic_id, created_at DESC);

CREATE TABLE IF NOT EXISTS intelligence_topic_research_checkpoints (
    intelligence_topic_id TEXT NOT NULL,
    prompt_version_id TEXT,
    checkpoint_cursor TEXT,
    checkpoint_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    last_run_id TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (intelligence_topic_id, prompt_version_id),
    FOREIGN KEY (intelligence_topic_id) REFERENCES intelligence_topics (id) ON DELETE CASCADE,
    FOREIGN KEY (prompt_version_id) REFERENCES intelligence_topic_prompt_versions (id) ON DELETE CASCADE,
    FOREIGN KEY (last_run_id) REFERENCES intelligence_topic_research_runs (id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS intelligence_topic_merge_previews (
    id TEXT PRIMARY KEY,
    intelligence_topic_id TEXT NOT NULL,
    source_finding_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    preview_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    content_hash TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'pending',
    created_by TEXT,
    expires_at TIMESTAMPTZ NOT NULL,
    applied_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (intelligence_topic_id) REFERENCES intelligence_topics (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_intelligence_topic_merge_previews_topic_state
ON intelligence_topic_merge_previews (intelligence_topic_id, state, expires_at);

CREATE TABLE IF NOT EXISTS intelligence_finding_archives (
    finding_id TEXT PRIMARY KEY,
    intelligence_topic_id TEXT NOT NULL,
    archive_reason TEXT,
    archive_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    superseded_by_finding_id TEXT,
    archived_by TEXT,
    archived_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (finding_id) REFERENCES intelligence_topic_findings (id) ON DELETE CASCADE,
    FOREIGN KEY (intelligence_topic_id) REFERENCES intelligence_topics (id) ON DELETE CASCADE,
    FOREIGN KEY (superseded_by_finding_id) REFERENCES intelligence_topic_findings (id) ON DELETE SET NULL
);
