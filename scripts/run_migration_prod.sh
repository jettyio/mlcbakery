#!/usr/bin/env bash
set -euo pipefail

# Run alembic migrations against prod (bakerydev:us-central1:bakery-prod)
# Requires: cloud-sql-proxy installed, gcloud auth configured
#
# Usage:
#   ./scripts/run_migration_prod.sh              # runs 'alembic upgrade head'
#   ./scripts/run_migration_prod.sh history      # runs 'alembic history'
#   ./scripts/run_migration_prod.sh current      # runs 'alembic current'

INSTANCE="bakerydev:us-central1:bakery-prod"
DB_NAME="mlbakery"
DB_USER="postgres"
PROXY_PORT=15432  # non-default port to avoid conflicts with local postgres

ALEMBIC_CMD="${1:-upgrade head}"

# Prompt for DB password
read -rsp "Enter postgres password for $INSTANCE: " DB_PASSWORD
echo

export DATABASE_URL="postgresql+asyncpg://${DB_USER}:${DB_PASSWORD}@127.0.0.1:${PROXY_PORT}/${DB_NAME}"

echo "Starting cloud-sql-proxy on port $PROXY_PORT..."
cloud-sql-proxy "$INSTANCE" --port "$PROXY_PORT" &
PROXY_PID=$!

cleanup() {
  echo "Stopping cloud-sql-proxy (pid $PROXY_PID)..."
  kill "$PROXY_PID" 2>/dev/null || true
  wait "$PROXY_PID" 2>/dev/null || true
}
trap cleanup EXIT

# Wait for proxy to be ready
for i in {1..10}; do
  if nc -z 127.0.0.1 "$PROXY_PORT" 2>/dev/null; then
    break
  fi
  sleep 1
done

echo "Running: alembic $ALEMBIC_CMD"
uv run alembic $ALEMBIC_CMD
echo "Done."
