# Unified Semantic Search — Learnings

## Wave 1, Task 1: Intelligence Embedding Schema (2026-05-28)

### Files created/modified
- NEW: `migrations/postgresql/012_intelligence_embedding_schema.sql`
- MODIFIED: `crypto_news_analyzer/storage/intelligence_schema.py`
- MODIFIED: `tests/shared/test_semantic_search_storage.py`

### What was done
- Added 3 embedding columns (`embedding vector(1536)`, `embedding_model TEXT`, `embedding_updated_at TIMESTAMPTZ`) to `raw_intelligence_items`
- Created 2 HNSW cosine indexes: `idx_content_embedding_hnsw` (on content_items) and `idx_intelligence_embedding_hnsw` (on raw_intelligence_items)
- Runtime bootstrap in `intelligence_schema.py` mirrors the migration for postgres backend
- Both migration SQL and runtime bootstrap use `ADD COLUMN IF NOT EXISTS`, `CREATE INDEX IF NOT EXISTS`, and `WHERE embedding IS NOT NULL`

### Test changes
- Updated old test `test_postgres_semantic_search_schema_bootstrap_matches_migration`: removed `assert "hnsw" not in runtime_sql.lower()` since runtime bootstrap now creates HNSW indexes
- Added new test `test_intelligence_embedding_schema_bootstrap_matches_migration` that verifies both migration (012) and runtime bootstrap SQL contain the 3 new columns and 2 HNSW indexes

### Key decisions
- Used standard `CREATE INDEX IF NOT EXISTS` (NOT CONCURRENTLY) per task spec
- Embedding columns only added in `if backend == "postgres"` block (SQLite doesn't support vector)
- `idx_content_embedding_hnsw` created in `intelligence_schema.py` because `_initialize_intelligence_tables` runs after content_items table is already created in data_manager.py
- HNSW indexes use `vector_cosine_ops` operator class with `WHERE embedding IS NOT NULL` partial index condition
