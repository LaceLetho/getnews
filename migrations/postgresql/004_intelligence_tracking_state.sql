ALTER TABLE intelligence_canonical_entries
ADD COLUMN IF NOT EXISTS tracking_enabled BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE intelligence_canonical_entries
ADD COLUMN IF NOT EXISTS discovery_presented_at TIMESTAMPTZ;

UPDATE intelligence_canonical_entries
SET tracking_enabled = FALSE
WHERE is_ignored = TRUE;

UPDATE intelligence_canonical_entries
SET tracking_enabled = TRUE
WHERE is_ignored = FALSE
  AND entry_type = 'channel';

UPDATE intelligence_canonical_entries
SET tracking_enabled = FALSE
WHERE is_ignored = FALSE
  AND entry_type = 'slang';

UPDATE intelligence_canonical_entries
SET discovery_presented_at = COALESCE(
    discovery_presented_at,
    ignored_at,
    updated_at,
    created_at,
    CURRENT_TIMESTAMP
)
WHERE is_ignored = TRUE;

CREATE INDEX IF NOT EXISTS idx_intelligence_canonical_entries_tracking
ON intelligence_canonical_entries (tracking_enabled, discovery_presented_at);
