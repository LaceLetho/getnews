CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS content_items (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    url TEXT UNIQUE NOT NULL,
    publish_time TIMESTAMPTZ NOT NULL,
    source_name TEXT NOT NULL,
    source_type TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    embedding vector(1536),
    embedding_model TEXT,
    embedding_updated_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

ALTER TABLE content_items
ADD COLUMN IF NOT EXISTS embedding_model TEXT;

ALTER TABLE content_items
ADD COLUMN IF NOT EXISTS embedding_updated_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_publish_time ON content_items (publish_time);
CREATE INDEX IF NOT EXISTS idx_source ON content_items (source_name, source_type);
CREATE INDEX IF NOT EXISTS idx_content_hash ON content_items (content_hash);
CREATE INDEX IF NOT EXISTS idx_created_at ON content_items (created_at);

CREATE TABLE IF NOT EXISTS crawl_status (
    id BIGSERIAL PRIMARY KEY,
    execution_time TIMESTAMPTZ NOT NULL,
    total_items INTEGER NOT NULL,
    rss_results JSONB NOT NULL,
    x_results JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS analysis_execution_log (
    id BIGSERIAL PRIMARY KEY,
    chat_id TEXT NOT NULL,
    execution_time TIMESTAMPTZ NOT NULL,
    time_window_hours INTEGER NOT NULL,
    items_count INTEGER NOT NULL,
    success BOOLEAN NOT NULL,
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_analysis_chat_time
ON analysis_execution_log (chat_id, execution_time);

CREATE INDEX IF NOT EXISTS idx_analysis_success
ON analysis_execution_log (chat_id, success, execution_time);

CREATE TABLE IF NOT EXISTS sent_message_cache (
    id BIGSERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    category TEXT NOT NULL,
    time TEXT NOT NULL,
    sent_at TIMESTAMPTZ NOT NULL,
    recipient_key TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_sent_at ON sent_message_cache (sent_at);
CREATE INDEX IF NOT EXISTS idx_category ON sent_message_cache (category);
CREATE INDEX IF NOT EXISTS idx_recipient_key_sent_at
ON sent_message_cache (recipient_key, sent_at);

CREATE TABLE IF NOT EXISTS analysis_jobs (
    id TEXT PRIMARY KEY,
    recipient_key TEXT NOT NULL,
    time_window_hours INTEGER NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    status TEXT NOT NULL,
    priority INTEGER NOT NULL DEFAULT 5,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    result TEXT,
    error_message TEXT,
    source TEXT NOT NULL DEFAULT 'api'
);

CREATE INDEX IF NOT EXISTS idx_analysis_jobs_recipient
ON analysis_jobs (recipient_key, created_at);

CREATE INDEX IF NOT EXISTS idx_analysis_jobs_status
ON analysis_jobs (status, created_at);

CREATE TABLE IF NOT EXISTS semantic_search_jobs (
    id TEXT PRIMARY KEY,
    recipient_key TEXT NOT NULL,
    query TEXT NOT NULL,
    normalized_intent TEXT NOT NULL DEFAULT '',
    time_window_hours INTEGER NOT NULL,
    status TEXT NOT NULL,
    matched_count INTEGER NOT NULL DEFAULT 0,
    retained_count INTEGER NOT NULL DEFAULT 0,
    decomposition_json JSONB,
    result TEXT,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    source TEXT NOT NULL DEFAULT 'api'
);

ALTER TABLE semantic_search_jobs
ADD COLUMN IF NOT EXISTS normalized_intent TEXT NOT NULL DEFAULT '';

ALTER TABLE semantic_search_jobs
ADD COLUMN IF NOT EXISTS matched_count INTEGER NOT NULL DEFAULT 0;

ALTER TABLE semantic_search_jobs
ADD COLUMN IF NOT EXISTS retained_count INTEGER NOT NULL DEFAULT 0;

ALTER TABLE semantic_search_jobs
ADD COLUMN IF NOT EXISTS decomposition_json JSONB;

ALTER TABLE semantic_search_jobs
ADD COLUMN IF NOT EXISTS result TEXT;

ALTER TABLE semantic_search_jobs
ADD COLUMN IF NOT EXISTS error_message TEXT;

ALTER TABLE semantic_search_jobs
ADD COLUMN IF NOT EXISTS started_at TIMESTAMPTZ;

ALTER TABLE semantic_search_jobs
ADD COLUMN IF NOT EXISTS completed_at TIMESTAMPTZ;

ALTER TABLE semantic_search_jobs
ADD COLUMN IF NOT EXISTS source TEXT NOT NULL DEFAULT 'api';

CREATE INDEX IF NOT EXISTS idx_semantic_search_jobs_recipient
ON semantic_search_jobs (recipient_key, created_at);

CREATE INDEX IF NOT EXISTS idx_semantic_search_jobs_status
ON semantic_search_jobs (status, created_at);

CREATE TABLE IF NOT EXISTS ingestion_jobs (
    id TEXT PRIMARY KEY,
    source_type TEXT NOT NULL,
    source_name TEXT NOT NULL,
    scheduled_at TIMESTAMPTZ NOT NULL,
    status TEXT NOT NULL,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    items_crawled INTEGER NOT NULL DEFAULT 0,
    items_new INTEGER NOT NULL DEFAULT 0,
    error_message TEXT,
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_ingestion_jobs_source
ON ingestion_jobs (source_type, source_name, scheduled_at);

CREATE INDEX IF NOT EXISTS idx_ingestion_jobs_status
ON ingestion_jobs (status, scheduled_at);
