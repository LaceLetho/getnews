-- Remove the legacy entry-extraction intelligence pipeline.
--
-- Apply only after deploying code that no longer references these tables/columns.
-- If production rollback safety is needed, rename the tables instead of dropping them.

ALTER TABLE intelligence_topics
DROP COLUMN IF EXISTS description,
DROP COLUMN IF EXISTS enriched_summary,
DROP COLUMN IF EXISTS source_channels,
DROP COLUMN IF EXISTS methods,
DROP COLUMN IF EXISTS vulnerabilities,
DROP COLUMN IF EXISTS latest_findings,
DROP COLUMN IF EXISTS last_evidence_at,
DROP COLUMN IF EXISTS enriched_at,
DROP COLUMN IF EXISTS embedding,
DROP COLUMN IF EXISTS embedding_model,
DROP COLUMN IF EXISTS embedding_updated_at;

DROP TABLE IF EXISTS intelligence_related_candidates;
DROP TABLE IF EXISTS intelligence_aliases;
DROP TABLE IF EXISTS intelligence_entry_evidence_links;
DROP TABLE IF EXISTS intelligence_canonical_entries;
DROP TABLE IF EXISTS intelligence_extraction_observations;
DROP TABLE IF EXISTS intelligence_topic_run_logs;
