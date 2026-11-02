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
if grep -q 'did not start' "$WORK/out.txt"; then bad "no false 'did not start' warning"; else ok "no false 'did not start' warning"; fi
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
if ./restore.sh "$WORK/good.dump" "$WORK/good.tgz" --yes > "$WORK/out.txt" 2>&1; then bad "script must fail"; else ok "script fails"; fi
sh_db 'mv /usr/local/bin/pg_restore.real /usr/local/bin/pg_restore'
check "database untouched" live_data_intact
check "files untouched, no work folder left" live_files_intact
if grep -q 'nothing was changed' "$WORK/out.txt"; then ok "says nothing was changed"; else bad "says nothing was changed"; fi
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
if ./restore.sh "$WORK/alembic-fails.dump" "$WORK/good.tgz" --yes > "$WORK/out.txt" 2>&1; then bad "script must fail"; else ok "script fails"; fi
if grep -q 'restore done' "$WORK/out.txt"; then bad 'does not say "restore done"'; else ok 'does not say "restore done"'; fi
check "files were swapped" sh_backend 'test -f /srv/kjs_files/keep.txt && test ! -e /srv/kjs_files/live.txt'
undo="$(grep '^  \./restore\.sh ' "$WORK/out.txt" | tail -1)"
[ -n "$undo" ] && ok "prints the undo command" || bad "prints the undo command"
if [ -n "$undo" ] && $undo --yes > "$WORK/out2.txt" 2>&1; then ok "the printed command works"; else bad "the printed command works"; tail -5 "$WORK/out2.txt"; fi
check "the live data is back" live_data_intact
check "the live files are back" live_files_intact

echo "== 7. backup.sh with a cut-off dump"
reset_to_live
before="$(ls "$BACKUP_DIR"/db-*.dump | wc -l)"
sh_db 'mv /usr/local/bin/pg_dump /usr/local/bin/pg_dump.real
       printf "%s\n" "#!/bin/sh" "pg_dump.real \"\$@\" | head -c 1000000" > /usr/local/bin/pg_dump
       chmod +x /usr/local/bin/pg_dump'
if ./backup.sh > "$WORK/out.txt" 2>&1; then bad "script must fail"; else ok "script fails"; fi
sh_db 'mv /usr/local/bin/pg_dump.real /usr/local/bin/pg_dump'
[ "$before" = "$(ls "$BACKUP_DIR"/db-*.dump | wc -l)" ] && ok "cut-off backup not kept" || bad "cut-off backup not kept"

echo "== 8. the app can't start again after a good restore"
reset_to_live
cat > "$WORK/compose-no-start" <<WRAPPER
#!/usr/bin/env bash
[ "\$1" = start ] && exit 1
exec $COMPOSE "\$@"
WRAPPER
chmod +x "$WORK/compose-no-start"
if COMPOSE="$WORK/compose-no-start" ./restore.sh "$WORK/good.dump" --yes > "$WORK/out.txt" 2>&1; then bad "script must fail"; else ok "script fails"; fi
if grep -q 'restore done' "$WORK/out.txt"; then bad 'does not say "restore done"'; else ok 'does not say "restore done"'; fi
if grep -q 'did not start' "$WORK/out.txt"; then ok "warns the app is down"; else bad "warns the app is down"; fi

echo "== 9. the script is killed during the database step (the restore goes on in the container)"
reset_to_live
sh_db 'mv /usr/local/bin/pg_restore /usr/local/bin/pg_restore.real'
sh_db 'cat > /usr/local/bin/pg_restore; chmod +x /usr/local/bin/pg_restore' <<'STUB'
#!/bin/sh
case "$*" in *"-f -"*) sleep 8;; esac
exec pg_restore.real "$@"
STUB
./restore.sh "$WORK/good.dump" --yes > "$WORK/out.txt" 2>&1 &
pid=$!
for _ in $(seq 1 120); do grep -q '^5/7' "$WORK/out.txt" && break; sleep 1; done
sleep 3
kill -TERM "$pid"
wait "$pid" 2>/dev/null
sleep 12
sh_db 'mv /usr/local/bin/pg_restore.real /usr/local/bin/pg_restore'
echo "  (after the kill the database says: $(sql 'SELECT v FROM cr1_marker'))"
if grep -q 'nothing was changed' "$WORK/out.txt"; then bad 'does not claim "nothing was changed"'; else ok 'does not claim "nothing was changed"'; fi
if grep -q '^  \./restore\.sh ' "$WORK/out.txt"; then ok "prints the undo command"; else bad "prints the undo command"; fi
if [ -z "$($COMPOSE ps -q backend)" ]; then ok "app is left stopped"; else bad "app is left stopped"; fi
undo="$(grep '^  \./restore\.sh ' "$WORK/out.txt" | tail -1)"
if [ -n "$undo" ] && $undo --yes > "$WORK/out2.txt" 2>&1; then ok "the printed command works with the app stopped"; else bad "the printed command works with the app stopped"; tail -5 "$WORK/out2.txt"; fi
check "the live data is back" live_data_intact

# Edge cases. fake_compose makes a stand-in for docker compose that misbehaves on matching commands:
#   COMPOSE="$WORK/fake" ./restore.sh ...
fake_compose() {
  cat > "$WORK/fake" <<WRAPPER
#!/usr/bin/env bash
case "\$*" in
$1
esac
exec $COMPOSE "\$@"
WRAPPER
  chmod +x "$WORK/fake"
}
backend_running() { [ "$(docker inspect -f '{{.State.Running}}' "$($COMPOSE ps -q backend)")" = "true" ]; }
says() { grep -q "$1" "$WORK/out.txt"; }
says_ok() { if says "$2"; then ok "$1"; else bad "$1"; fi; }
says_not() { if says "$2"; then bad "$1"; else ok "$1"; fi; }

# Fails after the data changed: must print a working undo that brings everything back.
expect_undo() {
  local what="$1"; shift
  reset_to_live
  if COMPOSE="$WORK/fake" ./restore.sh "$WORK/good.dump" "$WORK/good.tgz" --yes > "$WORK/out.txt" 2>&1; then
    bad "$what: script must fail"; else ok "$what: script fails"; fi
  says_not "$what: does not say restore done" 'restore done'
  local undo; undo="$(grep '^  \./restore\.sh ' "$WORK/out.txt" | tail -1)"
  if [ -n "$undo" ] && $undo --yes > "$WORK/out2.txt" 2>&1; then ok "$what: undo works"; else bad "$what: undo works"; fi
  check "$what: live data back" live_data_intact
  check "$what: live files back" live_files_intact
}

# Sends a hangup (dropped SSH session) while step N is running.
hangup_during() {
  reset_to_live
  COMPOSE="$WORK/fake" ./restore.sh "$WORK/good.dump" "$WORK/good.tgz" --yes > "$WORK/out.txt" 2>&1 &
  local pid=$!
  for _ in $(seq 1 120); do grep -q "^$1/7" "$WORK/out.txt" && break; sleep 1; done
  sleep 1
  kill -HUP "$pid"
  wait "$pid" 2>/dev/null
  sleep 2
}

echo "== 10. odd inputs"
$COMPOSE exec -T db pg_dump -U kjs -d kjs > "$WORK/plain.sql"
: > "$WORK/empty.dump"
: > "$WORK/empty.tgz"
gzip -c "$WORK/good.dump" > "$WORK/gzipped.dump"
mkdir "$WORK/folder.dump"
expect_refused "plain SQL dump" "$WORK/plain.sql"
expect_refused "empty file" "$WORK/empty.dump"
expect_refused "gzipped dump" "$WORK/gzipped.dump"
expect_refused "a folder" "$WORK/folder.dump"
expect_refused "empty tgz" "$WORK/good.dump" "$WORK/empty.tgz"
expect_refused "dump given as the tgz" "$WORK/good.dump" "$WORK/good.dump"
reset_to_live
if ./restore.sh >/dev/null 2>&1; then bad "no arguments must fail"; else ok "no arguments fails"; fi
if echo no | ./restore.sh "$WORK/good.dump" >/dev/null 2>&1; then bad "wrong answer must cancel"; else ok "wrong answer cancels"; fi
check "still untouched" live_data_intact
cp "$WORK/good.dump" "$WORK/with space.dump"
if ./restore.sh "$WORK/with space.dump" --yes >/dev/null 2>&1; then ok "path with a space works"; else bad "path with a space works"; fi

echo "== 11. awkward data and file names survive"
reset_to_live
$COMPOSE exec -T db psql -U kjs -d kjs -q <<'SQL' >/dev/null
CREATE TABLE cr1_text (t text);
INSERT INTO cr1_text VALUES ('हिन्दी'), ('it''s "quoted"'), (E'line\nbreak'), ('\.'), (E'tab\there'), ('SELECT 1/0;');
SQL
sh_backend 'cd /srv/kjs_files; find . -mindepth 1 -delete
  echo a > "with space.txt"; echo b > ./-dash.txt; echo c > "हिन्दी.txt"; echo d > .restore-new2
  mkdir empty-dir; ln -s with-space-link.txt link; mkdir -p a/b/c; echo e > a/b/c/f.txt'
listing() { sh_backend 'cd /srv/kjs_files; find . -mindepth 1 | sort; find . -type f | sort | xargs -d "\n" sha256sum'; }
want_files="$(listing)"
want_text="$(sql 'SELECT md5(string_agg(t, chr(1) ORDER BY t)) FROM cr1_text')"
./backup.sh >/dev/null
awk_dump="$(newest_dump)"; awk_tgz="$(newest_files)"
sql 'DROP TABLE cr1_text' >/dev/null
sh_backend 'cd /srv/kjs_files; find . -mindepth 1 -delete; echo live > live.txt'
if ./restore.sh "$awk_dump" "$awk_tgz" --yes > "$WORK/out.txt" 2>&1; then ok "script succeeds"; else bad "script succeeds"; tail -5 "$WORK/out.txt"; fi
[ "$want_text" = "$(sql 'SELECT md5(string_agg(t, chr(1) ORDER BY t)) FROM cr1_text')" ] && ok "text rows identical" || bad "text rows identical"
[ "$want_files" = "$(listing)" ] && ok "file names and contents identical" || bad "file names and contents identical"

echo "== 12. a files backup with no files in it"
reset_to_live
sh_backend 'find /srv/kjs_files -mindepth 1 -delete'
./backup.sh >/dev/null
empty_tgz="$(newest_files)"
sh_backend 'echo x > /srv/kjs_files/x.txt'
if ./restore.sh "$WORK/good.dump" "$empty_tgz" --yes > "$WORK/out.txt" 2>&1; then ok "script succeeds"; else bad "script succeeds"; tail -5 "$WORK/out.txt"; fi
[ "$(sh_backend 'find /srv/kjs_files -mindepth 1 | wc -l')" = "0" ] && ok "volume is empty, like the backup" || bad "volume is empty, like the backup"

echo "== 13. a leftover work folder from a killed restore"
reset_to_live
sh_backend 'mkdir /srv/kjs_files/.restore-new; echo stale > /srv/kjs_files/.restore-new/stale.txt'
./backup.sh >/dev/null
if tar tzf "$(newest_files)" | grep -q restore-new; then bad "not in the backup"; else ok "not in the backup"; fi
if ./restore.sh "$WORK/good.dump" "$WORK/good.tgz" --yes > "$WORK/out.txt" 2>&1; then ok "next restore succeeds"; else bad "next restore succeeds"; tail -5 "$WORK/out.txt"; fi
check "stale files are gone" sh_backend 'test ! -e /srv/kjs_files/.restore-new && test ! -e /srv/kjs_files/stale.txt'

echo "== 14. the app really works after a restore"
app_sql() { $COMPOSE exec -T db psql -U kjs_app -d kjs -Atc "$1"; }
reset_to_live
./restore.sh "$WORK/good.dump" --yes >/dev/null 2>&1
check "app user can read and write" app_sql "UPDATE cr1_marker SET v = 'x'"
if app_sql 'UPDATE audit_log SET id = id' >/dev/null 2>&1; then bad "audit log stays read-only for the app"; else ok "audit log stays read-only for the app"; fi
[ "$(sql "SELECT count(*) FROM pg_trigger WHERE tgrelid = 'audit_log'::regclass AND NOT tgisinternal")" != "0" ] && ok "audit log trigger is back" || bad "audit log trigger is back"
health() { sh_backend "python -c \"import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health/ready', timeout=4)\""; }
for _ in $(seq 1 30); do health >/dev/null 2>&1 && break; sleep 1; done
check "API health check passes" health

echo "== 15. a backup from older code is brought up to date"
reset_to_live
head_rev="$(sql 'SELECT version_num FROM alembic_version')"
$COMPOSE run --rm --no-deps backend alembic downgrade -1 >/dev/null 2>&1
[ "$(sql 'SELECT version_num FROM alembic_version')" != "$head_rev" ] && ok "downgraded for the test" || bad "downgraded for the test"
./backup.sh >/dev/null
old_rev_dump="$(newest_dump)"
reset_to_live
if ./restore.sh "$old_rev_dump" --yes > "$WORK/out.txt" 2>&1; then ok "script succeeds"; else bad "script succeeds"; tail -5 "$WORK/out.txt"; fi
[ "$(sql 'SELECT version_num FROM alembic_version')" = "$head_rev" ] && ok "tables at the current version" || bad "tables at the current version"

echo "== 16. another session holds a lock on a table"
reset_to_live
{ echo "BEGIN; LOCK TABLE cr1_marker IN ACCESS SHARE MODE;"; sleep 90; } \
  | $COMPOSE exec -T db psql -U kjs -d kjs -q >/dev/null 2>&1 &
holder=$!
sleep 2
started="$(date +%s)"
if ./restore.sh "$WORK/good.dump" --yes > "$WORK/out.txt" 2>&1; then bad "gives up instead of waiting forever"; else ok "gives up instead of waiting forever"; fi
echo "  (took $(( $(date +%s) - started )) s)"
says_ok "says nothing was changed" 'nothing was changed'
check "database untouched" live_data_intact
check "app is back up" backend_running
wait "$holder" 2>/dev/null

echo "== 17. a step fails on the server"
reset_to_live
fake_compose "*'tar xzf'*) exec $COMPOSE \"\$@\" < \"$WORK/cut.tgz\";;"
if COMPOSE="$WORK/fake" ./restore.sh "$WORK/good.dump" "$WORK/good.tgz" --yes > "$WORK/out.txt" 2>&1; then bad "unpack fails: script must fail"; else ok "unpack fails: script fails"; fi
says_ok "unpack fails: says nothing was changed" 'nothing was changed'
check "unpack fails: database untouched" live_data_intact
check "unpack fails: files untouched, no work folder" live_files_intact
check "unpack fails: app is back up" backend_running

fake_compose "*'rmdir .restore-new'*) exit 1;;"
expect_undo "file swap fails"
fake_compose "*'-v ON_ERROR_STOP=1 -q'*) exit 1;;"
expect_undo "grants fail"

fake_compose "*pg_dump*) exit 1;;"
COMPOSE="$WORK/fake" expect_refused "safety backup fails" "$WORK/good.dump"

reset_to_live
fake_compose "'stop frontend backend') exit 1;;"
if COMPOSE="$WORK/fake" ./restore.sh "$WORK/good.dump" --yes > "$WORK/out.txt" 2>&1; then bad "stop fails: script must fail"; else ok "stop fails: script fails"; fi
says_ok "stop fails: says nothing was changed" 'nothing was changed'
check "stop fails: database untouched" live_data_intact

reset_to_live
$COMPOSE stop db >/dev/null 2>&1
if ./restore.sh "$WORK/good.dump" --yes > "$WORK/out.txt" 2>&1; then bad "db down: script must fail"; else ok "db down: script fails"; fi
says_ok "db down: does not blame only the file" 'could not read'
$COMPOSE start db >/dev/null 2>&1
for _ in $(seq 1 30); do sql 'SELECT 1' >/dev/null 2>&1 && break; sleep 1; done
check "db down: data intact" live_data_intact

reset_to_live
$COMPOSE stop backend >/dev/null 2>&1
if ./restore.sh "$WORK/good.dump" "$WORK/good.tgz" --yes > "$WORK/out.txt" 2>&1; then ok "backend down: restore works"; else bad "backend down: restore works"; tail -5 "$WORK/out.txt"; fi
[ "$(sql 'SELECT v FROM cr1_marker')" = "original" ] && ok "backend down: data is back" || bad "backend down: data is back"
[ -n "$($COMPOSE ps -q backend)" ] && backend_running && ok "backend down: app is up after" || bad "backend down: app is up after"

reset_to_live
files_before="$(ls "$BACKUP_DIR"/files-*.tgz | wc -l)"
fake_compose "*czf*) $COMPOSE \"\$@\" | head -c 50; exit 0;;"
if COMPOSE="$WORK/fake" ./backup.sh > "$WORK/out.txt" 2>&1; then bad "backup.sh with a cut-off archive must fail"; else ok "backup.sh with a cut-off archive fails"; fi
[ "$files_before" = "$(ls "$BACKUP_DIR"/files-*.tgz | wc -l)" ] && ok "cut-off archive not kept" || bad "cut-off archive not kept"

echo "== 18. the SSH session drops at each stage"
fake_compose "'stop frontend backend') sleep 5;;"
hangup_during 3
says_ok "during stop: says nothing was changed" 'nothing was changed'
check "during stop: data intact" live_data_intact
check "during stop: app is back up" backend_running

fake_compose "*'tar xzf'*) sleep 5;;"
hangup_during 4
says_ok "during unpack: says nothing was changed" 'nothing was changed'
check "during unpack: data intact" live_data_intact
check "during unpack: files intact, no work folder" live_files_intact
check "during unpack: app is back up" backend_running

fake_compose "*'alembic upgrade head'*) sleep 5;;"
hangup_during 7
says_not "during alembic: does not say nothing changed" 'nothing was changed'
says_not "during alembic: does not say restore done" 'restore done'
says_ok "during alembic: prints the undo command" '^  \./restore\.sh '
check "during alembic: app is back up" backend_running

echo "== 19. a second hangup during the clean-up"
fake_compose "'stop frontend backend') sleep 5;;
'start backend frontend') sleep 8;;"
reset_to_live
COMPOSE="$WORK/fake" ./restore.sh "$WORK/good.dump" --yes > "$WORK/out.txt" 2>&1 &
pid=$!
for _ in $(seq 1 120); do grep -q '^3/7' "$WORK/out.txt" && break; sleep 1; done
sleep 1
kill -HUP "$pid"
sleep 7
kill -HUP "$pid" 2>/dev/null
wait "$pid" 2>/dev/null
sleep 3
says_ok "still reports the result" 'nothing was changed'
check "app is back up" backend_running

echo "== 20. the app starts but crashes"
reset_to_live
fake_compose "*api/health/ready*) exit 1;;"
if COMPOSE="$WORK/fake" ./restore.sh "$WORK/good.dump" --yes > "$WORK/out.txt" 2>&1; then bad "script must fail"; else ok "script fails"; fi
says_not 'does not say "restore done"' 'restore done'
says_ok "warns the app is down" 'did not start'

echo
echo "passed: $PASSED  failed: $FAILED"
[ "$FAILED" -eq 0 ]
