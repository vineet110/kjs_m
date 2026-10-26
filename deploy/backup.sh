#!/usr/bin/env bash
# Nightly backup: the whole database + uploaded files, kept for KEEP_DAYS days.
#   ./backup.sh                      (run from anywhere; cron runs it at 02:30, see README)
# Restore with ./restore.sh. A backup that was never restored is not a backup: test it monthly.
set -euo pipefail
cd "$(dirname "$0")"

# Backups hold password hashes, customer contact details and every uploaded file:
# only the owner of the files may read them (no other user on the server).
umask 077

BACKUP_DIR="${BACKUP_DIR:-/srv/kjs/backups}"
KEEP_DAYS="${KEEP_DAYS:-14}"
COMPOSE="${COMPOSE:-docker compose -f docker-compose.prod.yml}"
stamp="$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"

db_file="$BACKUP_DIR/db-$stamp.dump"
files_file="$BACKUP_DIR/files-$stamp.tgz"
# If anything fails, don't leave half-written files behind
trap 'rm -f "$db_file.tmp" "$files_file.tmp"' EXIT

# 1. Database. -Fc = Postgres "custom" format: compressed, restores table by table.
#    Written to .tmp first, so a half-finished file is never mistaken for a good backup.
$COMPOSE exec -T db pg_dump -U kjs -d kjs -Fc > "$db_file.tmp"
# Check the file is a readable backup before keeping it
$COMPOSE exec -T db pg_restore -l < "$db_file.tmp" > /dev/null
mv "$db_file.tmp" "$db_file"

# 2. Uploaded files (only matters when STORAGE_DRIVER=local; with R2, Cloudflare keeps them)
$COMPOSE exec -T backend tar czf - -C /srv/kjs_files . > "$files_file.tmp"
mv "$files_file.tmp" "$files_file"

# 3. Delete backups older than KEEP_DAYS days
find "$BACKUP_DIR" -name 'db-*.dump' -mtime +"$KEEP_DAYS" -delete
find "$BACKUP_DIR" -name 'files-*.tgz' -mtime +"$KEEP_DAYS" -delete

echo "backup ok: $db_file ($(du -h "$db_file" | cut -f1)), $files_file ($(du -h "$files_file" | cut -f1))"
# Off-site copy (a backup on the same disk dies with the disk): see README "Off-site copy".
