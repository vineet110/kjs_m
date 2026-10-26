#!/usr/bin/env bash
# Runs once, when the database volume is first created (Postgres "docker-entrypoint-initdb.d").
# Creates the app's own limited user. Its rights come from grants.sql after the first migration.
set -euo pipefail
: "${APP_DB_PASSWORD:?set APP_DB_PASSWORD in deploy/.env}"
psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
  -v pw="$APP_DB_PASSWORD" <<'SQL'
CREATE ROLE kjs_app WITH LOGIN PASSWORD :'pw' NOSUPERUSER NOCREATEDB NOCREATEROLE;
SQL
