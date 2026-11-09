#!/usr/bin/env bash
# Nightly backup: the whole database + uploaded files, kept for KEEP_DAYS days on this server, plus an
# encrypted off-site copy in the R2 backup bucket when deploy/.env.backup exists (README "Off-site copy").
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
# restore.sh sets KJS_BACKUP_STAMP, so it knows the file names. (Not "STAMP": a common name that may
# already be set in the shell, and then every backup would get the same name and overwrite the last.)
stamp="${KJS_BACKUP_STAMP:-$(date +%Y%m%d-%H%M%S)}"
mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"

db_file="$BACKUP_DIR/db-$stamp.dump"
files_file="$BACKUP_DIR/files-$stamp.tgz"
# If anything fails, don't leave half-written files behind
trap 'rm -f "$db_file.tmp" "$files_file.tmp" "$db_file.enc" "$files_file.enc"' EXIT

storage_driver="$(grep -E '^STORAGE_DRIVER=' .env 2>/dev/null | tail -1 | cut -d= -f2 | tr -d "\"' \r")"

# 1. Database. -Fc = Postgres "custom" format: compressed, restores table by table.
#    Written to .tmp first, so a half-finished file is never mistaken for a good backup.
$COMPOSE exec -T db pg_dump -U kjs -d kjs -Fc > "$db_file.tmp"
# Read the whole file before keeping it (-f /dev/null saves nothing). pg_restore -l is not enough:
# it reads only the list at the start, so it passes a backup that was cut off.
$COMPOSE exec -T db pg_restore -f /dev/null < "$db_file.tmp"
mv "$db_file.tmp" "$db_file"

# 2. Uploaded files (only matters when STORAGE_DRIVER=local; with R2, Cloudflare keeps them)
# (.restore-new = work folder restore.sh leaves behind if it is killed halfway)
# run, not exec: backups and restores must work while the backend is down
$COMPOSE run --rm -T --no-deps --entrypoint tar backend czf - --exclude=./.restore-new -C /srv/kjs_files . \
  > "$files_file.tmp"
$COMPOSE run --rm -T --no-deps --entrypoint tar backend tzf - < "$files_file.tmp" > /dev/null  # same check: read it all
mv "$files_file.tmp" "$files_file"

# 3. Delete backups older than KEEP_DAYS days
find "$BACKUP_DIR" -name 'db-*.dump' -mtime +"$KEEP_DAYS" -delete
find "$BACKUP_DIR" -name 'files-*.tgz' -mtime +"$KEEP_DAYS" -delete

echo "backup ok: $db_file ($(du -h "$db_file" | cut -f1)), $files_file ($(du -h "$files_file" | cut -f1))"

# 4. Off-site copy (a backup on the same disk dies with the disk). Skipped for the backups that
#    restore.sh (KJS_BACKUP_STAMP) and deploy.sh (KJS_SKIP_OFFSITE) take first: a restore or an urgent
#    fix must never wait on, or fail because of, the internet or the off-site settings.
if [ -n "${KJS_BACKUP_STAMP:-}" ] || [ -n "${KJS_SKIP_OFFSITE:-}" ]; then exit 0; fi
# Settings: deploy/.env.backup (git-ignored, chmod 600). Its R2 key is for the backup bucket only and is
# never in .env, so the running app never has it. Read as plain KEY=VALUE lines, never run as shell
# code: a passphrase with $, spaces or quotes is taken exactly as written.
offsite=""
if [ -f .env.backup ]; then
  while IFS= read -r line || [ -n "$line" ]; do
    line="${line%$'\r'}"
    case "$line" in
      R2_BACKUP_BUCKET=*|R2_BACKUP_ACCESS_KEY_ID=*|R2_BACKUP_SECRET_ACCESS_KEY=*|BACKUP_PASSPHRASE=*|OFFSITE_KEEP_DAYS=*)
        export "${line%%=*}=${line#*=}" ;;
    esac
  done < .env.backup
  for v in R2_BACKUP_BUCKET R2_BACKUP_ACCESS_KEY_ID R2_BACKUP_SECRET_ACCESS_KEY BACKUP_PASSPHRASE; do
    [ -n "${!v:-}" ] || { echo "off-site copy: $v is empty - set in .env.backup" >&2; exit 1; }
  done
  offsite=1
fi
if [ -z "$offsite" ]; then
  echo "WARNING: no off-site copy (deploy/.env.backup missing). A dead disk loses every backup." >&2
  [ "$storage_driver" = "r2" ] && echo "WARNING: uploaded files in R2 have NO backup at all." >&2
  exit 0
fi
# Only for this command: the backup key and how long to keep things off-site
offsite_run() {
  $COMPOSE run --rm -T --no-deps -e R2_BACKUP_BUCKET -e R2_BACKUP_ACCESS_KEY_ID -e R2_BACKUP_SECRET_ACCESS_KEY     -e OFFSITE_KEEP_DAYS="${OFFSITE_KEEP_DAYS:-30}" backend python -m app.backup_r2 "$@"
}
# Encrypted before it leaves the server (it holds customer data). Restore: README "Off-site copy".
# (< and >, not -in / -out: the shell opens the files, so any path works, also under Git Bash)
encrypt() { openssl enc -aes-256-cbc -pbkdf2 -iter 200000 -salt -pass env:BACKUP_PASSPHRASE < "$1" > "$2"; }
encrypt "$db_file" "$db_file.enc"
offsite_run put "$(basename "$db_file").enc" < "$db_file.enc"
if [ "$storage_driver" = "r2" ]; then
  offsite_run sync-files                     # uploads: new ones copied, removed ones kept 30 days
else
  encrypt "$files_file" "$files_file.enc"    # uploads live on this disk: send the archive too
  offsite_run put "$(basename "$files_file").enc" < "$files_file.enc"
fi
echo "off-site copy ok"

