#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# scripts/initdb.sh
#
# One-time database initialisation for AIOps Sentinel.
#
# Creates the 'sentinel' PostgreSQL role and 'sentinel' database
# if they do not already exist. The role password is read from
# a Docker secret file — never hardcoded or passed as a CLI arg.
#
# Run this ONCE before the first 'docker compose up'.
# Alembic migrations (table creation) run automatically on
# every container start via the Dockerfile CMD.
#
# Requirements:
#   - psql client on the host
#   - Access to PostgreSQL as a superuser
#   - SENTINEL_SECRETS_DIR pointing to your secrets directory
#   - PGPASSWORD (or ~/.pgpass) for the superuser connection
#
# Usage:
#   export SENTINEL_SECRETS_DIR=/path/to/your/secrets
#   export PGPASSWORD=<postgres_superuser_password>
#   ./scripts/initdb.sh
#
# Optional overrides (defaults shown):
#   POSTGRES_HOST=localhost
#   POSTGRES_PORT=5432
#   PGADMIN_USER=postgres
# ============================================================

SECRET_FILE="${SENTINEL_SECRETS_DIR:?'ERROR: SENTINEL_SECRETS_DIR is not set'}/postgres_password.txt"

if [[ ! -f "$SECRET_FILE" ]]; then
  echo "ERROR: Secret file not found: $SECRET_FILE"
  exit 1
fi

DB_PASS=$(< "$SECRET_FILE")
PGHOST="${POSTGRES_HOST:-localhost}"
PGPORT="${POSTGRES_PORT:-5432}"
PGADMIN_USER="${PGADMIN_USER:-postgres}"

echo "==> AIOps Sentinel — database initialisation"
echo "    Host : ${PGHOST}:${PGPORT}"
echo "    Admin: ${PGADMIN_USER}"
echo ""

psql \
  --host="$PGHOST" \
  --port="$PGPORT" \
  --username="$PGADMIN_USER" \
  --set ON_ERROR_STOP=1 \
  --set sentinel_pass="$DB_PASS" <<'EOSQL'

-- ── Role ──────────────────────────────────────────────────────
-- Create the role if it does not exist, then always refresh the
-- password from the current secret (idempotent).
DO $body$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'sentinel'
  ) THEN
    CREATE ROLE sentinel WITH LOGIN;
    RAISE NOTICE 'Role sentinel created.';
  ELSE
    RAISE NOTICE 'Role sentinel already exists.';
  END IF;
END;
$body$;

-- Set (or rotate) the password from the secret file
ALTER ROLE sentinel WITH LOGIN PASSWORD :'sentinel_pass';

-- ── Database ──────────────────────────────────────────────────
-- CREATE DATABASE cannot run inside a transaction block, so we
-- use \gexec to execute the result of this SELECT conditionally.
SELECT format('CREATE DATABASE sentinel OWNER sentinel')
WHERE NOT EXISTS (
  SELECT 1 FROM pg_catalog.pg_database WHERE datname = 'sentinel'
)
\gexec

EOSQL

echo ""
echo "==> Initialisation complete."
echo "    Tables will be created automatically when the container"
echo "    starts for the first time (alembic upgrade head)."
