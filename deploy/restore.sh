#!/usr/bin/env bash
# Put a backup back. REPLACES the current database (and files, if a files backup is given).
#   ./restore.sh /srv/kjs/backups/db-20261210-023000.dump [/srv/kjs/backups/files-20261210-023000.tgz]
# Add --yes as the last argument to skip the question (used by the restore test).
#
# Safe by design:
#   1. both backups are read in full first: a bad one stops here, with the app still running;
#   2. the app is stopped, then a backup of the CURRENT state is taken (so a wrong restore can be
#      undone, with nothing missing); the undo command is also saved in BACKUP_DIR/restore-undo.txt;
#   3. the database is replaced in ONE transaction: if anything fails, it stays as it was;
#   4. new files are unpacked aside BEFORE that, and old ones are deleted only after it;
#   5. the app is started again and checked, even if the restore failed (only if the script was
#      stopped during the database step does the app stay stopped), and a failure says how to undo it;
#   6. afterwards the tables are brought up to the current code version (alembic upgrade head).
# Tested by ./test-restore.sh
set -euo pipefail

db_file="${1:?usage: ./restore.sh <db-backup.dump> [files-backup.tgz] [--yes]}"
files_file="${2:-}"
[ "$files_file" = "--yes" ] && files_file=""

# Checked and made full paths BEFORE the cd below, so ../backups/x.dump works from any folder
[ -f "$db_file" ] || { echo "no such file: $db_file"; exit 1; }
[ -z "$files_file" ] || [ -f "$files_file" ] || { echo "no such file: $files_file"; exit 1; }
db_file="$(realpath "$db_file")"
[ -z "$files_file" ] || files_file="$(realpath "$files_file")"
cd "$(dirname "$0")"
COMPOSE="${COMPOSE:-docker compose -f docker-compose.prod.yml}"
BACKUP_DIR="${BACKUP_DIR:-/srv/kjs/backups}"  # same default as backup.sh

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

# We pick the safety backup's file names, so we never have to read them back out of backup.sh's message.
# "-before-restore": can't clash with a nightly backup, and shows what the files are.
stamp="$(date +%Y%m%d-%H%M%S)-before-restore"
safety_db="$BACKUP_DIR/db-$stamp.dump"
safety_files="$BACKUP_DIR/files-$stamp.tgz"
# %q: quoted, so it can be copied and run even if the folder name has a space
undo_cmd="$(printf './restore.sh %q %q' "$safety_db" "$safety_files")"
undo_file="$BACKUP_DIR/restore-undo.txt"
undo_saved=no

data_state=unchanged  # unchanged, unknown (we lost sight of the database step) or replaced
db_query() { $COMPOSE exec -T db psql -U kjs -d kjs -Atqc "$1"; }
# After psql failed with something other than 3: don't guess, ask the database. Wait until our
# session ("kjs-restore") is gone, then look for the marker made just before the database step:
# still there = the transaction was cancelled; gone = it committed (DROP SCHEMA removed it).
# If the database can't tell us, data_state stays unknown.
ask_database() {
  local end=$((SECONDS + 120)) n
  while n="$(db_query "SELECT count(*) FROM pg_stat_activity WHERE application_name = 'kjs-restore'")" \
        && [ "$n" != 0 ] && [ "$SECONDS" -lt "$end" ]; do
    sleep 2
  done
  [ "$n" = 0 ] || return 0
  case "$(db_query "SELECT to_regclass('public.kjs_restore_marker') IS NOT NULL")" in
    f) data_state=replaced ;;
    t) case "$(db_query "SELECT count(*) FROM public.kjs_restore_marker WHERE run = '$stamp'")" in
         1) data_state=unchanged ;;
         0) data_state=replaced ;;  # a marker from an older run came back with the backup
       esac ;;
  esac
}
app_is_healthy() {  # about 60 s. "compose start" only shows that the container started.
  local end=$((SECONDS + 60))  # by the clock: one try can take up to ~7 s
  while [ "$SECONDS" -lt "$end" ]; do
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
    echo "  $undo_cmd"; echo "(also saved in $undo_file)"
    return
  fi
  if [ "$data_state" = unchanged ] && [ -n "$files_file" ]; then
    $COMPOSE run --rm -T --no-deps --entrypoint sh backend -c 'rm -rf /srv/kjs_files/.restore-new' \
      >/dev/null 2>&1 || true
  fi
  db_query 'DROP TABLE IF EXISTS public.kjs_restore_marker' >/dev/null 2>&1 || true
  # The saved undo must not be run by mistake later: once the app runs again, it would also throw
  # away everything saved since. Running it is still safe (it takes its own safety backup first).
  if [ "$undo_saved" = yes ]; then
    if [ "$data_state" = unchanged ]; then
      echo "Restore of $db_file failed at $(date), nothing was changed: there is nothing to undo." \
        > "$undo_file" 2>/dev/null || true
    else
      echo "Restore ended at $(date). Running the command above after this also throws away everything saved after this time." \
        >> "$undo_file" 2>/dev/null || true
    fi
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
        echo "  $undo_cmd"; echo "(also saved in $undo_file)" ;;
    esac
  elif [ "$app_started" = yes ]; then
    echo "restore done from $db_file${files_file:+ and $files_file}"
  else
    # Every step worked, so the data IS replaced: the undo matters here too
    echo "The backup was put back, but the app is not working, so the site is down."
    echo "To go back to how it was before this restore, run:"
    echo "  $undo_cmd"; echo "(also saved in $undo_file)"
    exit 1
  fi
}
trap finish EXIT
# Ctrl+C, a kill or a dropped SSH session must still run finish
trap 'exit 130' INT
trap 'exit 143' TERM
trap 'exit 129' HUP

echo "2/7 stopping the app (the database keeps running)"
$COMPOSE stop frontend backend

echo "3/7 safety backup of the current state"
# After the stop: nothing saved by a user can be missing from the undo.
# KEEP_DAYS: no clean-up now, or backup.sh could delete an old backup we are about to restore
BACKUP_DIR="$BACKUP_DIR" KJS_BACKUP_STAMP="$stamp" KEEP_DAYS=36500 ./backup.sh
# Also in a file: if the SSH session drops, the terminal and the command on it are gone
printf '%s\n' "Restore of $db_file started $(date)." \
  "To go back to how it was before it, run this in the deploy folder:" "  $undo_cmd" > "$undo_file"
undo_saved=yes

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
# psql's own exit code 3 proves the transaction was cancelled. Any other failure: ask the database
# (ask_database). Ctrl+C or a dropped session leaves it unknown: psql can keep running in the
# container and still commit, and we are not there to wait for it.
# lock_timeout: if another session holds a table, give up after 60 s and don't wait with the site down.
db_query "DROP TABLE IF EXISTS public.kjs_restore_marker;
          CREATE TABLE public.kjs_restore_marker (run text); INSERT INTO public.kjs_restore_marker VALUES ('$stamp');" \
  >/dev/null
data_state=unknown
if $COMPOSE exec -T db sh -c \
  '{ echo "SET lock_timeout = '\''60s'\''; DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
     pg_restore --no-owner --no-privileges -f - || printf "\n%s\nSELECT 1/0;\n" "\\."; } \
   | PGAPPNAME=kjs-restore psql -U kjs -d kjs -v ON_ERROR_STOP=1 --single-transaction -q' < "$db_file"; then
  data_state=replaced
else
  status=$?
  if [ "$status" -eq 3 ]; then data_state=unchanged; else ask_database; fi
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
