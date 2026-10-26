#!/usr/bin/env bash
# Put a backup back. REPLACES the current database (and files, if a files backup is given).
#   ./restore.sh /srv/kjs/backups/db-20261210-023000.dump [/srv/kjs/backups/files-20261210-023000.tgz]
# Add --yes as the last argument to skip the question (used by the restore test).
#
# Safe by design:
#   1. a backup of the CURRENT state is taken first (so a wrong restore can be undone);
#   2. the database is replaced in ONE transaction: if anything fails, nothing changes;
#   3. the app is started again even if the restore failed;
#   4. afterwards the tables are brought up to the current code version (alembic upgrade head).
set -euo pipefail
cd "$(dirname "$0")"

db_file="${1:?usage: ./restore.sh <db-backup.dump> [files-backup.tgz] [--yes]}"
files_file="${2:-}"
[ "$files_file" = "--yes" ] && files_file=""
COMPOSE="${COMPOSE:-docker compose -f docker-compose.prod.yml}"

[ -f "$db_file" ] || { echo "no such file: $db_file"; exit 1; }
if [ "${!#}" != "--yes" ]; then
  read -r -p "This REPLACES the live database with $db_file. Type RESTORE to continue: " answer
  [ "$answer" = "RESTORE" ] || { echo "cancelled"; exit 1; }
fi

echo "1/5 safety backup of the current state"
./backup.sh

echo "2/5 stopping the app (the database keeps running)"
$COMPOSE stop frontend backend
trap '$COMPOSE start backend frontend >/dev/null 2>&1 || true' EXIT  # always bring the app back

echo "3/5 replacing the database (all or nothing)"
# Empty schema + the backup's SQL, inside one transaction. Unlike pg_restore --clean, this also
# removes tables that newer code added after the backup was taken.
$COMPOSE exec -T db sh -c \
  '{ echo "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"; pg_restore --no-owner --no-privileges -f -; } \
   | psql -U kjs -d kjs -v ON_ERROR_STOP=1 --single-transaction -q' < "$db_file"

if [ -n "$files_file" ]; then
  echo "4/5 replacing uploaded files"
  $COMPOSE run --rm -T --no-deps --entrypoint sh backend \
    -c 'find /srv/kjs_files -mindepth 1 -delete && tar xzf - -C /srv/kjs_files' < "$files_file"
else
  echo "4/5 (no files backup given: uploaded files left as they are)"
fi

echo "5/5 matching the tables to this code version, then access rights"
$COMPOSE run --rm --no-deps backend alembic upgrade head
$COMPOSE exec -T db psql -U kjs -d kjs -v ON_ERROR_STOP=1 -q < db/grants.sql

echo "restore done from $db_file${files_file:+ and $files_file}"
