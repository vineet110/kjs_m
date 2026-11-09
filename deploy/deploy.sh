#!/usr/bin/env bash
# Update the server to the latest code on main:
#   ./deploy.sh
# Steps: pull -> build images tagged with the commit -> backup -> migrate -> rights -> restart
#        -> health check -> record the version in .env (TAG) -> keep the 3 newest images.
# Roll back: see README "Roll back".
set -euo pipefail
cd "$(dirname "$0")"

COMPOSE="${COMPOSE:-docker compose -f docker-compose.prod.yml}"

# The superuser address for migrations, read from .env (the running API never has it: CR11).
# Plain KEY=VALUE reading, never run as shell code.
MIGRATION_DATABASE_URL="$(grep -E '^MIGRATION_DATABASE_URL=' .env 2>/dev/null | tail -1 | cut -d= -f2- | tr -d '\r' | sed -e 's/^"\(.*\)"$/\1/' -e "s/^'\(.*\)'$/\1/")"
[ -n "$MIGRATION_DATABASE_URL" ] || { echo "MIGRATION_DATABASE_URL is missing in deploy/.env (needed for migrations)"; exit 1; }
export MIGRATION_DATABASE_URL

git pull --ff-only
TAG="$(git rev-parse --short HEAD)"
export TAG  # beats TAG in .env for this run, so each deploy gets its own image tag (kjs-api:<commit>)
echo "deploying $TAG"

$COMPOSE build

# Back up before the migration changes anything (skipped on the very first deploy)
# KJS_SKIP_OFFSITE: the nightly backup sends the off-site copy; a deploy must not wait on it or fail
# because R2 is down (backup.sh step 4).
if [ -n "$($COMPOSE ps -q db 2>/dev/null)" ]; then KJS_SKIP_OFFSITE=1 ./backup.sh; fi

$COMPOSE up -d db
$COMPOSE run --rm -e MIGRATION_DATABASE_URL backend alembic upgrade head
$COMPOSE exec -T db psql -U kjs -d kjs -v ON_ERROR_STOP=1 -q < db/grants.sql
$COMPOSE up -d --remove-orphans
# The app containers are new and may have new addresses: make nginx look them up again now
$COMPOSE exec -T nginx nginx -s reload || true

# Wait until the API (with its database) and the website both answer through nginx
for _ in $(seq 1 30); do
  # /healthz, not /: the home page has loading.tsx, so it answers 200 at once even when it then fails (CR2)
  if curl -fsS http://127.0.0.1:8080/api/health/ready > /dev/null && curl -fsS http://127.0.0.1:8080/healthz > /dev/null; then
    # Record what is live, so later plain "docker compose" commands use this version
    if grep -q '^TAG=' .env; then sed -i "s/^TAG=.*/TAG=$TAG/" .env; else echo "TAG=$TAG" >> .env; fi
    echo "deploy ok: $TAG is live"
    # Keep the 3 newest images of each app for rollback. Cleanup problems never fail a good deploy.
    for app in kjs-api kjs-web; do
      docker image ls "$app" --format '{{.Tag}}' | grep -v -e '^latest$' -e '^<none>$' | tail -n +4 \
        | xargs -r -I{} docker image rm "$app:{}" || true
    done
    exit 0
  fi
  sleep 2
done
echo "deploy FAILED: not healthy. Logs: $COMPOSE logs --tail 100 backend frontend"
echo "The previous version is still recorded in .env (TAG). Roll back: see README section 4."
exit 1
