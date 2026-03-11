# Production Database Migration

## Prerequisites

1. **GCP auth** — must have valid Application Default Credentials:
   ```bash
   gcloud auth login
   gcloud auth application-default login
   ```

2. **cloud-sql-proxy** — installed locally:
   ```bash
   # macOS
   brew install cloud-sql-proxy
   ```

3. **uv** and project dependencies installed (`uv sync`)

## Connection Details

| Field | Value |
|-------|-------|
| Cloud SQL Instance | `bakerydev:us-central1:bakery-prod` |
| Database | `mlbakery` |
| User | `postgres` |
| Password | See commented `DATABASE_URL` in `.env` |

## Running Migrations

Use the helper script:

```bash
# Apply all pending migrations
./scripts/run_migration_prod.sh

# Check current revision on prod
./scripts/run_migration_prod.sh current

# View migration history
./scripts/run_migration_prod.sh history
```

The script:
- Starts cloud-sql-proxy on port 15432 (avoids conflicting with local postgres)
- Prompts for the DB password
- Runs the alembic command
- Auto-cleans up the proxy on exit

## Troubleshooting

### `invalid_grant` / `reauth related error`
Your GCP credentials have expired. Re-run:
```bash
gcloud auth login
gcloud auth application-default login
```

### `Connection refused` on port 15432
The cloud-sql-proxy failed to start. Check that:
- You have network access to GCP
- The instance `bakerydev:us-central1:bakery-prod` exists
- Port 15432 isn't already in use

### Multiple alembic heads
If alembic complains about multiple heads, create a merge migration:
```bash
uv run alembic merge heads -m "merge branches"
```
