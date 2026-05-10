CREATE TABLE IF NOT EXISTS intelligence_entry_evidence_links (
    entry_id TEXT NOT NULL,
    observation_id TEXT NOT NULL,
    raw_item_id TEXT NOT NULL,
    observed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (entry_id, raw_item_id),
    FOREIGN KEY (entry_id) REFERENCES intelligence_canonical_entries (id) ON DELETE CASCADE,
    FOREIGN KEY (observation_id) REFERENCES intelligence_extraction_observations (id) ON DELETE CASCADE,
    FOREIGN KEY (raw_item_id) REFERENCES raw_intelligence_items (id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_intelligence_entry_evidence_unique
ON intelligence_entry_evidence_links (entry_id, raw_item_id);

CREATE INDEX IF NOT EXISTS idx_intelligence_entry_evidence_entry_time
ON intelligence_entry_evidence_links (entry_id, observed_at);

CREATE INDEX IF NOT EXISTS idx_intelligence_entry_evidence_raw_item
ON intelligence_entry_evidence_links (raw_item_id);
