-- Migration 004: Add canonical intelligence ignore state columns
-- Adds is_ignored, ignored_at, ignored_by fields and index

ALTER TABLE intelligence_canonical_entries ADD COLUMN IF NOT EXISTS is_ignored BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE intelligence_canonical_entries ADD COLUMN IF NOT EXISTS ignored_at TIMESTAMPTZ;
ALTER TABLE intelligence_canonical_entries ADD COLUMN IF NOT EXISTS ignored_by TEXT;
CREATE INDEX IF NOT EXISTS idx_intelligence_canonical_entries_is_ignored ON intelligence_canonical_entries (is_ignored);
