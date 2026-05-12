ALTER TABLE intelligence_canonical_entries
ADD COLUMN IF NOT EXISTS follow_status TEXT NOT NULL DEFAULT 'unset';

UPDATE intelligence_canonical_entries
SET follow_status = CASE
    WHEN is_ignored = TRUE THEN 'unfollow'
    WHEN tracking_enabled = TRUE THEN 'follow'
    WHEN discovery_presented_at IS NOT NULL THEN 'unfollow'
    ELSE 'unset'
END
WHERE follow_status IS NULL
   OR follow_status NOT IN ('follow', 'unfollow', 'unset')
   OR (
       follow_status = 'unset'
       AND (is_ignored = TRUE OR tracking_enabled = TRUE OR discovery_presented_at IS NOT NULL)
   );

UPDATE intelligence_canonical_entries
SET tracking_enabled = (follow_status = 'follow'),
    is_ignored = (follow_status = 'unfollow'),
    ignored_at = CASE
        WHEN follow_status = 'unfollow' THEN COALESCE(ignored_at, updated_at, created_at, CURRENT_TIMESTAMP)
        ELSE NULL
    END,
    ignored_by = CASE
        WHEN follow_status = 'unfollow' THEN COALESCE(ignored_by, 'follow_status')
        ELSE NULL
    END;

CREATE INDEX IF NOT EXISTS idx_intelligence_canonical_entries_follow_status
ON intelligence_canonical_entries (follow_status);
