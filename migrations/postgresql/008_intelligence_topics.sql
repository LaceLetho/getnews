CREATE TABLE IF NOT EXISTS intelligence_topics (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    enriched_summary TEXT,
    source_channels TEXT NOT NULL DEFAULT '[]',
    methods TEXT,
    vulnerabilities TEXT,
    latest_findings TEXT NOT NULL DEFAULT '[]',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    last_evidence_at TIMESTAMPTZ,
    enriched_at TIMESTAMPTZ,
    embedding vector(1536),
    embedding_model TEXT,
    embedding_updated_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_intelligence_topics_active
ON intelligence_topics (is_active, updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_intelligence_topics_enriched_at
ON intelligence_topics (enriched_at);

CREATE TABLE IF NOT EXISTS intelligence_topic_run_logs (
    id TEXT PRIMARY KEY,
    run_type TEXT NOT NULL,
    status TEXT NOT NULL,
    topic_id TEXT,
    entry_id TEXT,
    message TEXT,
    details TEXT NOT NULL DEFAULT '{}',
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_intelligence_topic_run_logs_created
ON intelligence_topic_run_logs (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_intelligence_topic_run_logs_topic
ON intelligence_topic_run_logs (topic_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_intelligence_topic_run_logs_run_type
ON intelligence_topic_run_logs (run_type, created_at DESC);

ALTER TABLE intelligence_canonical_entries
ADD COLUMN IF NOT EXISTS topic_id TEXT;

CREATE INDEX IF NOT EXISTS idx_intelligence_canonical_entries_topic_id
ON intelligence_canonical_entries (topic_id);
