CREATE TABLE IF NOT EXISTS datasources (
    id TEXT PRIMARY KEY,
    source_type TEXT NOT NULL,
    name TEXT NOT NULL,
    config_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS datasource_tags (
    datasource_id TEXT NOT NULL,
    tag TEXT NOT NULL,
    PRIMARY KEY (datasource_id, tag),
    FOREIGN KEY (datasource_id) REFERENCES datasources (id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_datasources_source_name
ON datasources (source_type, name);

CREATE INDEX IF NOT EXISTS idx_datasources_created_at
ON datasources (created_at);

CREATE INDEX IF NOT EXISTS idx_datasource_tags_tag
ON datasource_tags (tag);
