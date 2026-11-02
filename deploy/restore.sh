#!/usr/bin/env bash
# Put a backup back. REPLACES the current database (and files, if a files backup is given).
#   ./restore.sh /srv/kjs/backups/db-20261210-023000.dump [/srv/kjs/backups/files-20261210-023000.tgz]
# Add --yes as the last argument to skip the question (used by the restore test).
#
# Safe by design:
#   1. both backups are read in full first: a bad one stops here, with the app still running;
#   2. a backup of the CURRENT state is taken (so a wrong restore can be undone);
#   3. the database is replaced in ONE transaction: if anything fails, it stays as it was;
#   4. new files are unpacked aside BEFORE that, and old ones are deleted only after it;
#   5. the app is started again and checked, even if the restore failed (only if the script was
#      stopped during the database step does the app stay stopped), and a failure says how to undo it;
#   6. afterwards the tables are brought up to the current code version (alembic upgrade head).
# Tested by ./test-restore.sh
set -euo pipefail
cd "$(dirname "$0")"

db_file="${1:?usage: ./restore.sh <db-backup.dump> [files-backup.tgz] [--yes]}"
files_file="${2:-}"
[ "$files_file" = "--yes" ] && files_file=""
COMPOSE="${COMPOSE:-docker compose -f docker-compose.prod.yml}"

[ -f "$db_file" ] || { echo "no such file: $db_file"; exit 1; }
[ -z "$files_file" ] || [ -f "$files_file" ] || { echo "no such file: $files_file"; exit 1; }
if [ "${!#}" != "--yes" ]; then
  read -r -p "This REPLACES the live database with $db_file. Type RESTORE to continue: " answer
  [ "$answer" = "RESTORE" ] || { echo "cancelled"; exit 1; }
fi

echo "1/7 reading the whole backup (nothing is changed yet)"
# -f /dev/null: goes through every part of the file and saves nothing. pg_restore -l is not enough:
# it reads only the list at the start, so it passes a backup that was cut off.
$COMPOSE exec -T db pg_restore -f /dev/null < "$db_file" \
  || { echo "restore stopped: could not read $db_file (bad file, or a container is down). Nothing was changed."; exit 1; }
if [ -n "$files_file" ]; then
  $COMPOSE run --rm -T --no-deps --entrypoint sh backend -c 'tar tzf - > /dev/null' < "$files_file" \
    || { echo "restore stopped: could not read $files_file (bad file, or a container is down). Nothing was changed."; exit 1; }
fi

echo "2/7 safety backup of the current state"
# KEEP_DAYS: no clean-up now, or backup.sh could delete an old backup we are about to restore
backup_line="$(KEEP_DAYS=36500 ./backup.sh)"
echo "$backup_line"
read -r _ _ safety_db _ safety_files _ <<< "$backup_line"

data_state=unchanged  # unchanged, unknown (we lost sight of the database step) or replaced
app_is_healthy() {  # up to 60 s. "compose start" only shows that the container started.
  for _ in $(seq 1 30); do
    $COMPOSE exec -T backend python -c \
      "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health/ready', timeout=4)" \
      >/dev/null 2>&1 && return 0
    sleep 2
  done
  return 1
}
finish() {
  local status=$?
  trap '' HUP INT TERM  # a second Ctrl+C must not stop the clean-up
  local app_started=yes
  if [ "$data_state" = unknown ]; then
    # Don't start the app: if psql commits, migrations and rights never ran, and every call would fail
    echo "restore STOPPED during the database step. It may still finish inside the db container."
    echo "The app was left STOPPED. Wait a few minutes, then to go back to how it was before this restore, run:"
    echo "  ./restore.sh $safety_db $safety_files"
    return
  fi
  if [ "$data_state" = unchanged ] && [ -n "$files_file" ]; then
    $COMPOSE run --rm -T --no-deps --entrypoint sh backend -c 'rm -rf /srv/kjs_files/.restore-new' \
      >/dev/null 2>&1 || true
  fi
  $COMPOSE start backend frontend >/dev/null 2>&1 || app_started=no  # always bring the app back
  if [ "$status" -eq 0 ] && [ "$app_started" = yes ]; then app_is_healthy || app_started=no; fi
  [ "$app_started" = yes ] || echo "WARNING: the app did not start properly. Check with: $COMPOSE ps"
  if [ "$status" -ne 0 ]; then
    case "$data_state" in
      unchanged) echo "restore FAILED, nothing was changed." ;;
      replaced)
        echo "restore FAILED after the data was replaced. The site may be broken until you go back."
        echo "To go back to how it was before this restore, run:"
        echo "  ./restore.sh $safety_db $safety_files" ;;
    esac
  elif [ "$app_started" = yes ]; then
    echo "restore done from $db_file${files_file:+ and $files_file}"
  else
    # Every step worked, so the data IS replaced: the undo matters here too
    echo "The backup was put back, but the app is not working, so the site is down."
    echo "To go back to how it was before this restore, run:"
    echo "  ./restore.sh $safety_db $safety_files"
    exit 1
  fi
}
trap finish EXIT
# Ctrl+C, a kill or a dropped SSH session must still run finish
trap 'exit 130' INT
trap 'exit 143' TERM
trap 'exit 129' HUP

echo "3/7 stopping the app (the database keeps running)"
$COMPOSE stop frontend backend

if [ -n "$files_file" ]; then
  echo "4/7 unpacking uploaded files aside"
  # Before the database, so running out of disk space stops here with nothing changed.
  # /srv/kjs_files is a Docker volume's mount point, so it can't be swapped as a whole: use a hidden
  # folder inside it.
  $COMPOSE run --rm -T --no-deps --entrypoint sh backend -c '
    cd /srv/kjs_files
    rm -rf .restore-new
    mkdir .restore-new && tar xzf - -C .restore-new || { rm -rf .restore-new; exit 1; }' < "$files_file"
else
  echo "4/7 (no files backup given: uploaded files left as they are)"
fi

echo "5/7 replacing the database (all or nothing)"
# Empty schema + the backup's SQL, inside one transaction. Unlike pg_restore --clean, this also
# removes tables that newer code added after the backup was taken.
# In a pipe, psql can't see that pg_restore failed: it would commit the DROP. So on failure we send
# a statement that always errors, which makes psql cancel the whole transaction. The "\." comes
# first: if pg_restore died inside a table's data, it ends the rows, or our statement would be
# stored as one more row and nothing would fail.
# Only psql's own exit code 3 proves the transaction was cancelled. Anything else (Ctrl+C, a lost
# connection) means we lost sight of it: psql can keep running in the container and still commit.
# lock_timeout: if another session holds a table, give up after 60 s and don't wait with the site down.
data_state=unknown
if $COMPOSE exec -T db sh -c \
  '{ echo "SET lock_timeout = '\''60s'\''; DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
     pg_restore --no-owner --no-privileges -f - || printf "\n%s\nSELECT 1/0;\n" "\\."; } \
   | psql -U kjs -d kjs -v ON_ERROR_STOP=1 --single-transaction -q' < "$db_file"; then
  data_state=replaced
else
  status=$?
  [ "$status" -ne 3 ] || data_state=unchanged
  exit "$status"
fi

if [ -n "$files_file" ]; then
  echo "6/7 replacing uploaded files"
  $COMPOSE run --rm -T --no-deps --entrypoint sh backend -c '
    set -e
    cd /srv/kjs_files
    find . -mindepth 1 -maxdepth 1 ! -name .restore-new -exec rm -rf {} +
    find .restore-new -mindepth 1 -maxdepth 1 -exec mv -t . {} +
    rmdir .restore-new'
else
  echo "6/7 (no files backup given: uploaded files left as they are)"
fi

echo "7/7 matching the tables to this code version, then access rights"
$COMPOSE run --rm --no-deps backend alembic upgrade head
$COMPOSE exec -T db psql -U kjs -d kjs -v ON_ERROR_STOP=1 -q < db/grants.sql
