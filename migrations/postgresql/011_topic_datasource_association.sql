-- 011_topic_datasource_association.sql
-- Add datasource association schema for intelligence topics and raw items.
-- Creates M:N join table linking topics to datasources, adds nullable
-- datasource_id to raw_intelligence_items, and backfills both.

-- ---------------------------------------------------------------------------
-- 1. Join table: topic <-> datasource (M:N)
--    Cascade-deletes when a topic is removed; RESTRICT when a datasource
--    is removed (so operators must unlink before deleting a datasource).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS intelligence_topic_datasources (
    topic_id      TEXT NOT NULL,
    datasource_id TEXT NOT NULL,
    created_at    TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (topic_id, datasource_id),
    FOREIGN KEY (topic_id)      REFERENCES intelligence_topics (id) ON DELETE CASCADE,
    FOREIGN KEY (datasource_id) REFERENCES datasources (id)         ON DELETE RESTRICT
);

-- ---------------------------------------------------------------------------
-- 2. Optional datasource back-reference on every raw intelligence item.
--    NULLABLE – items collected before datasource tracking was introduced
--    or items whose source does not map to a known datasource remain NULL.
-- ---------------------------------------------------------------------------
ALTER TABLE raw_intelligence_items
ADD COLUMN IF NOT EXISTS datasource_id TEXT;

-- ---------------------------------------------------------------------------
-- 3. Lookup index for queries that filter raw items by datasource.
-- ---------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_intelligence_raw_items_datasource_id
ON raw_intelligence_items (datasource_id);

-- ---------------------------------------------------------------------------
-- 4. Backfill topic–datasource links.
--    Every existing topic gets linked to every datasource whose purpose is
--    'intelligence'.  This is idempotent via ON CONFLICT DO NOTHING.
-- ---------------------------------------------------------------------------
INSERT INTO intelligence_topic_datasources (topic_id, datasource_id)
SELECT t.id, d.id
FROM intelligence_topics t
CROSS JOIN datasources d
WHERE d.purpose = 'intelligence'
ON CONFLICT (topic_id, datasource_id) DO NOTHING;

-- ---------------------------------------------------------------------------
-- 5. Best-effort backfill of raw_intelligence_items.datasource_id.
--    Matches items to datasources by source_type plus a source_id lookup
--    (direct ID match or chat_id in the datasource config_payload).
--    Rows that cannot be resolved stay NULL – the column is nullable.
-- ---------------------------------------------------------------------------
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
  );
