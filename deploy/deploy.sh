#!/usr/bin/env bash
# Update the server to the latest code on main:
#   ./deploy.sh
# Steps: pull -> build images tagged with the commit -> backup -> migrate -> restart -> health check.
# Roll back: see README "Roll back".
set -euo pipefail
cd "$(dirname "$0")"

COMPOSE="${COMPOSE:-docker compose -f docker-compose.prod.yml}"

git pull --ff-only
TAG="$(git rev-parse --short HEAD)"
export TAG  # beats TAG in .env, so each deploy gets its own image tag (kjs-api:<commit>)
echo "deploying $TAG"

$COMPOSE build

# Back up before the migration changes anything (skipped on the very first deploy)
if [ -n "$($COMPOSE ps -q db 2>/dev/null)" ]; then ./backup.sh; fi

$COMPOSE up -d db
$COMPOSE run --rm backend alembic upgrade head
$COMPOSE up -d --remove-orphans

# Wait until the API answers through nginx, database included
for _ in $(seq 1 30); do
  if curl -fsS http://127.0.0.1:8080/api/health/ready > /dev/null; then
    echo "deploy ok: $TAG is live"
    # Keep the 3 newest images of each app for rollback, delete older ones
    for app in kjs-api kjs-web; do
      docker image ls "$app" --format '{{.Tag}}' | grep -v '^latest$' | tail -n +4 | xargs -r -I{} docker image rm "$app:{}"
    done
    exit 0
  fi
  sleep 2
done
echo "deploy FAILED: API not healthy. Logs: $COMPOSE logs --tail 100 backend"
exit 1
