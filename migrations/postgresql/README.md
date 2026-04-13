PostgreSQL migration scaffolding for monolith storage cutover:

1) Apply schema and extension:

```bash
psql "$DATABASE_URL" -f migrations/postgresql/001_init.sql
psql "$DATABASE_URL" -f migrations/postgresql/002_datasource_schema.sql
```

2) Backfill existing SQLite data from a Railway app container on the private network:

```bash
railway ssh -s <service-with-sqlite-volume> \
  "/opt/venv/bin/python3 /app/migrations/postgresql/remote_internal_backfill.py \
    --sqlite-path /app/data/crypto_news.db \
    --postgres-url \"\$DATABASE_URL\""
```

Notes:

- Do not use a local machine plus Railway public PostgreSQL proxy for large backfills.
- Run the backfill inside a Railway app service that can access both:
  - the SQLite file, for example `/app/data/crypto_news.db`
  - the private PostgreSQL host from `DATABASE_URL`
- `remote_internal_backfill.py` truncates target tables before importing.

3) Cutover runtime config to PostgreSQL mode:

```json
{
  "storage": {
    "backend": "postgres",
    "pgvector_dimensions": 1536
  }
}
```

Environment variable `DATABASE_URL` is the only supported PostgreSQL connection source.

4) Datasource bootstrap behavior:

- On first startup, if `datasources` table is empty, the system imports from `config.jsonc`
- After bootstrap, runtime reads exclusively from the database
- Use REST API (`POST /datasources`) or Telegram commands (`/datasource_add`) to manage datasources at runtime
