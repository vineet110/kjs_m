#!/usr/bin/env bash
# Put a backup back. REPLACES the current database (and files, if a files backup is given).
#   ./restore.sh /srv/kjs/backups/db-20261210-023000.dump [/srv/kjs/backups/files-20261210-023000.tgz]
# Add --yes as the last argument to skip the question (used by the restore test).
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

# Stop the app so nobody writes while we restore (the database keeps running)
$COMPOSE stop frontend backend

# --clean --if-exists: drop each table first, then recreate it from the backup
$COMPOSE exec -T db pg_restore -U kjs -d kjs --clean --if-exists --no-owner < "$db_file"

if [ -n "$files_file" ]; then
  $COMPOSE run --rm -T --no-deps --entrypoint sh backend \
    -c 'find /srv/kjs_files -mindepth 1 -delete && tar xzf - -C /srv/kjs_files' < "$files_file"
fi

$COMPOSE start backend frontend
echo "restore done from $db_file${files_file:+ and $files_file}"
