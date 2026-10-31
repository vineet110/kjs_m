#!/usr/bin/env bash
# Real test of restore.sh and backup.sh, on a throwaway copy of the stack (db + backend only).
#   ./test-restore.sh                (needs Docker; takes a few minutes)
# NEVER run this on the server. It refuses to start if deploy/.env exists, because that file means
# real settings live here. It writes its own temporary .env and removes it at the end.
set -uo pipefail
cd "$(dirname "$0")"
export MSYS_NO_PATHCONV=1  # Git Bash on Windows: don't rewrite /srv/... paths

[ ! -e .env ] || { echo "refusing to run: deploy/.env exists (is this the server?)"; exit 1; }

export TAG=restore-test
export COMPOSE="docker compose -p kjs-restore-test -f docker-compose.prod.yml"
WORK="$(mktemp -d)"
export BACKUP_DIR="$WORK/backups"
PASSED=0
FAILED=0

cleanup() {
  $COMPOSE down -v --remove-orphans >/dev/null 2>&1
  rm -f .env
  rm -rf "$WORK"
}
trap cleanup EXIT

cat > .env <<'ENV'
APP_ENV=production
SECRET_KEY=test-only-0123456789abcdef0123456789abcdef0123456789abcdef
PUBLIC_BASE_URL=https://restore-test.example.com
ALLOWED_ORIGINS=https://restore-test.example.com
POSTGRES_PASSWORD=test-only-owner-password
APP_DB_PASSWORD=test-only-app-password
DATABASE_URL=postgresql+asyncpg://kjs_app:test-only-app-password@db:5432/kjs
MIGRATION_DATABASE_URL=postgresql+asyncpg://kjs:test-only-owner-password@db:5432/kjs
LLM_PROVIDER=groq
LLM_MODEL=test
GROQ_API_KEY=test-only
STORAGE_DRIVER=local
ENV

sql() { $COMPOSE exec -T db psql -U kjs -d kjs -Atc "$1"; }
sh_backend() { $COMPOSE exec -T backend sh -c "$1"; }
sh_db() { $COMPOSE exec -T db sh -c "$1"; }
backend_started_at() { docker inspect -f '{{.State.StartedAt}}' "$($COMPOSE ps -q backend)"; }
newest_dump() { ls -t "$BACKUP_DIR"/db-*.dump | head -1; }
newest_files() { ls -t "$BACKUP_DIR"/files-*.tgz | head -1; }

ok() { PASSED=$((PASSED + 1)); echo "  PASS  $1"; }
bad() { FAILED=$((FAILED + 1)); echo "  FAIL  $1"; }
check() {  # check "<what>" <command...>
  local what="$1"; shift
  if "$@" >/dev/null 2>&1; then ok "$what"; else bad "$what"; fi
}

# The "current" data every test starts from: anything else proves the restore changed it.
reset_to_live() {
  $COMPOSE start backend >/dev/null 2>&1
  sh_db '{ echo "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"; pg_restore --no-owner --no-privileges -f -; } \
    | psql -U kjs -d kjs -v ON_ERROR_STOP=1 --single-transaction -q' < "$WORK/good.dump" >/dev/null 2>&1
  sql "UPDATE cr1_marker SET v = 'live'" >/dev/null
  sh_backend 'find /srv/kjs_files -mindepth 1 -delete; echo live > /srv/kjs_files/live.txt'
}
live_data_intact() {
  [ "$(sql 'SELECT v FROM cr1_marker')" = "live" ] && [ "$(sql 'SELECT count(*) FROM cr1_bulk')" = "200000" ]
}
live_files_intact() { sh_backend 'test -f /srv/kjs_files/live.txt && test ! -d /srv/kjs_files/.restore-new'; }

# A restore that must be refused: non-zero exit, nothing changed, app never stopped.
expect_refused() {
  local what="$1"; shift
  reset_to_live
  local before; before="$(backend_started_at)"
  if ./restore.sh "$@" --yes > "$WORK/out.txt" 2>&1; then bad "$what: script must fail"; else ok "$what: script fails"; fi
  check "$what: database untouched" live_data_intact
  check "$what: files untouched" live_files_intact
  [ "$before" = "$(backend_started_at)" ] && ok "$what: app never stopped" || bad "$what: app never stopped"
}

echo "== setting up the test stack"
$COMPOSE build backend >/dev/null || exit 1
$COMPOSE up -d db >/dev/null 2>&1
for _ in $(seq 1 60); do sql 'SELECT 1' >/dev/null 2>&1 && break; sleep 1; done
sleep 2
$COMPOSE run --rm --no-deps backend alembic upgrade head || exit 1
$COMPOSE exec -T db psql -U kjs -d kjs -v ON_ERROR_STOP=1 -q < db/grants.sql || exit 1
$COMPOSE up -d backend >/dev/null 2>&1
for _ in $(seq 1 30); do sh_backend 'true' >/dev/null 2>&1 && break; sleep 1; done

sql "CREATE TABLE cr1_marker (v text); INSERT INTO cr1_marker VALUES ('original');
     CREATE TABLE cr1_bulk (id int, t text);
     INSERT INTO cr1_bulk SELECT g, md5(g::text) || md5((g * 7)::text) FROM generate_series(1, 200000) g;" >/dev/null
sh_backend 'echo keep > /srv/kjs_files/keep.txt; echo hidden > /srv/kjs_files/.hidden
            mkdir /srv/kjs_files/sub; echo deep > /srv/kjs_files/sub/deep.txt
            head -c 3000000 /dev/urandom > /srv/kjs_files/big.bin'

./backup.sh >/dev/null || exit 1
cp "$(newest_dump)" "$WORK/good.dump"
cp "$(newest_files)" "$WORK/good.tgz"

# A backup that alembic can't upgrade: the database swap works, the next step fails.
# (reset_to_live puts the good alembic_version back before each test.)
sleep 1
sql "UPDATE alembic_version SET version_num = 'unknown_revision'" >/dev/null
./backup.sh >/dev/null || exit 1
cp "$(newest_dump)" "$WORK/alembic-fails.dump"

size="$(wc -c < "$WORK/good.dump")"
head -c $((size / 2)) "$WORK/good.dump" > "$WORK/cut50.dump"
head -c $((size - 1)) "$WORK/good.dump" > "$WORK/cut-1byte.dump"
echo "this is not a backup" > "$WORK/wrong.dump"
size="$(wc -c < "$WORK/good.tgz")"
head -c $((size / 2)) "$WORK/good.tgz" > "$WORK/cut.tgz"
echo "this is not an archive" > "$WORK/wrong.tgz"

echo "== 1. bad database backups"
expect_refused "wrong file" "$WORK/wrong.dump"
expect_refused "cut in half" "$WORK/cut50.dump"
expect_refused "1 byte missing" "$WORK/cut-1byte.dump"
expect_refused "tgz given as the dump" "$WORK/good.tgz"

echo "== 2. bad files backups"
expect_refused "wrong tgz" "$WORK/good.dump" "$WORK/wrong.tgz"
expect_refused "cut tgz" "$WORK/good.dump" "$WORK/cut.tgz"
expect_refused "tgz path typo" "$WORK/good.dump" "$WORK/no-such-file.tgz"

echo "== 3. good restore"
reset_to_live
sql 'CREATE TABLE cr1_added_later (id int)' >/dev/null
if ./restore.sh "$WORK/good.dump" "$WORK/good.tgz" --yes > "$WORK/out.txt" 2>&1; then ok "script succeeds"; else bad "script succeeds"; tail -5 "$WORK/out.txt"; fi
[ "$(sql 'SELECT v FROM cr1_marker')" = "original" ] && ok "data is back" || bad "data is back"
[ "$(sql "SELECT count(*) FROM pg_tables WHERE tablename = 'cr1_added_later'")" = "0" ] && ok "newer table removed" || bad "newer table removed"
check "normal, hidden and nested files are back" sh_backend \
  'test -f /srv/kjs_files/keep.txt && test -f /srv/kjs_files/.hidden && test -f /srv/kjs_files/sub/deep.txt'
expected="$(tar xzOf "$WORK/good.tgz" ./big.bin | sha256sum | cut -d' ' -f1)"
actual="$(sh_backend 'sha256sum /srv/kjs_files/big.bin' | cut -d' ' -f1)"
[ -n "$actual" ] && [ "$expected" = "$actual" ] && ok "big file is identical" || bad "big file is identical"
check "old files are gone" sh_backend 'test ! -e /srv/kjs_files/live.txt'
check "no hidden work folder left" sh_backend 'test ! -e /srv/kjs_files/.restore-new'
[ "$(docker inspect -f '{{.State.Running}}' "$($COMPOSE ps -q backend)")" = "true" ] && ok "app is running" || bad "app is running"

echo "== 4. pg_restore dies during the restore (the check before it passed)"
reset_to_live
sh_db 'mv /usr/local/bin/pg_restore /usr/local/bin/pg_restore.real'
# Fake crash: real output, stopping in the middle of a one-column table's data. A crash there is the
# hard case: psql is reading rows, not SQL, so anything we send it could be taken for a row.
sh_db 'cat > /usr/local/bin/pg_restore; chmod +x /usr/local/bin/pg_restore' <<'STUB'
#!/bin/sh
case "$*" in
  *"-f -"*) pg_restore.real "$@" | awk '{ print } /^COPY public.cr1_marker/ { exit }'; exit 1;;
esac
exec pg_restore.real "$@"
STUB
if ./restore.sh "$WORK/good.dump" --yes > "$WORK/out.txt" 2>&1; then bad "script must fail"; else ok "script fails"; fi
sh_db 'mv /usr/local/bin/pg_restore.real /usr/local/bin/pg_restore'
check "database untouched" live_data_intact
[ "$(docker inspect -f '{{.State.Running}}' "$($COMPOSE ps -q backend)")" = "true" ] && ok "app is back up" || bad "app is back up"

echo "== 5. backup older than KEEP_DAYS survives its own restore"
reset_to_live
old="$BACKUP_DIR/db-20200101-000000.dump"
cp "$WORK/good.dump" "$old"
touch -d '30 days ago' "$old"
if ./restore.sh "$old" --yes > "$WORK/out.txt" 2>&1; then ok "script succeeds"; else bad "script succeeds"; tail -5 "$WORK/out.txt"; fi
[ -f "$old" ] && ok "old backup still there" || bad "old backup still there"
[ "$(sql 'SELECT v FROM cr1_marker')" = "original" ] && ok "data is back" || bad "data is back"
rm -f "$old"

echo "== 6. failure AFTER the database was swapped"
reset_to_live
if ./restore.sh "$WORK/alembic-fails.dump" --yes > "$WORK/out.txt" 2>&1; then bad "script must fail"; else ok "script fails"; fi
if grep -q 'restore done' "$WORK/out.txt"; then bad 'does not say "restore done"'; else ok 'does not say "restore done"'; fi
safety="$(grep -o "$BACKUP_DIR/db-[0-9-]*\.dump" "$WORK/out.txt" | tail -1)"
[ -n "$safety" ] && ok "names the safety backup" || bad "names the safety backup"
if [ -n "$safety" ] && ./restore.sh "$safety" --yes > "$WORK/out2.txt" 2>&1; then ok "following the message works"; else bad "following the message works"; tail -5 "$WORK/out2.txt"; fi
check "the live data is back" live_data_intact

echo "== 7. backup.sh with a cut-off dump"
reset_to_live
before="$(ls "$BACKUP_DIR"/db-*.dump | wc -l)"
sh_db 'mv /usr/local/bin/pg_dump /usr/local/bin/pg_dump.real
       printf "%s\n" "#!/bin/sh" "pg_dump.real \"\$@\" | head -c 1000000" > /usr/local/bin/pg_dump
       chmod +x /usr/local/bin/pg_dump'
if ./backup.sh > "$WORK/out.txt" 2>&1; then bad "script must fail"; else ok "script fails"; fi
sh_db 'mv /usr/local/bin/pg_dump.real /usr/local/bin/pg_dump'
[ "$before" = "$(ls "$BACKUP_DIR"/db-*.dump | wc -l)" ] && ok "cut-off backup not kept" || bad "cut-off backup not kept"

echo
echo "passed: $PASSED  failed: $FAILED"
[ "$FAILED" -eq 0 ]
