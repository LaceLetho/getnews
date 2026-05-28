-- 012_intelligence_embedding_schema.sql
-- Add embedding columns and HNSW cosine indexes to both content_items
-- and raw_intelligence_items tables to support semantic search over
-- both the News and Intelligence domains.

CREATE EXTENSION IF NOT EXISTS vector;

-- ---------------------------------------------------------------------------
-- 1. Embedding columns on raw_intelligence_items
-- ---------------------------------------------------------------------------
ALTER TABLE raw_intelligence_items
ADD COLUMN IF NOT EXISTS embedding vector(1536);

ALTER TABLE raw_intelligence_items
ADD COLUMN IF NOT EXISTS embedding_model TEXT;

ALTER TABLE raw_intelligence_items
ADD COLUMN IF NOT EXISTS embedding_updated_at TIMESTAMPTZ;

-- ---------------------------------------------------------------------------
-- 2. HNSW cosine indexes for News domain (content_items)
-- ---------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_content_embedding_hnsw
ON content_items
USING hnsw (embedding vector_cosine_ops)
WHERE embedding IS NOT NULL;

-- ---------------------------------------------------------------------------
-- 3. HNSW cosine index for Intelligence domain (raw_intelligence_items)
-- ---------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_intelligence_embedding_hnsw
ON raw_intelligence_items
USING hnsw (embedding vector_cosine_ops)
WHERE embedding IS NOT NULL;
