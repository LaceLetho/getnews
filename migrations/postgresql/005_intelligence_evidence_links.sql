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

INSERT INTO intelligence_entry_evidence_links
    (entry_id, observation_id, raw_item_id, observed_at)
SELECT
    entry.id,
    observation.id,
    entry.latest_raw_item_id,
    observation.created_at
FROM intelligence_canonical_entries AS entry
JOIN intelligence_extraction_observations AS observation
  ON observation.raw_item_id = entry.latest_raw_item_id
WHERE entry.latest_raw_item_id IS NOT NULL
  AND observation.id = (
      SELECT observation_inner.id
      FROM intelligence_extraction_observations AS observation_inner
      WHERE observation_inner.raw_item_id = entry.latest_raw_item_id
      ORDER BY observation_inner.created_at ASC, observation_inner.id ASC
      LIMIT 1
  )
ON CONFLICT (entry_id, raw_item_id) DO NOTHING;
