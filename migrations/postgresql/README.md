PostgreSQL migration scaffolding for monolith storage cutover:

1) Apply schema and extension:

```bash
psql "$DATABASE_URL" -f migrations/postgresql/001_init.sql
```

2) Backfill existing SQLite data:

```bash
uv run python migrations/postgresql/backfill_from_sqlite.py \
  --sqlite-path ./data/crypto_news.db \
  --postgres-url "$DATABASE_URL"
```

3) Cutover runtime config to PostgreSQL mode:

```json
{
  "storage": {
    "backend": "postgres",
    "database_url": "postgresql://...",
    "pgvector_dimensions": 1536
  }
}
```

Environment variable `DATABASE_URL` overrides `storage.database_url`.
