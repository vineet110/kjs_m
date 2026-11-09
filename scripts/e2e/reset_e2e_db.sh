set -e
docker exec kjs_test_db psql -U kjs_test -d kjs_test -q -c "DROP DATABASE IF EXISTS kjs_e2e WITH (FORCE)" -c "CREATE DATABASE kjs_e2e"
# The repo's own backend folder, wherever the repo is (it used to be one person's folder, so it failed elsewhere)
cd "$(dirname "$0")/../../backend"
# BOTH database URLs point at the local test database (port 5433): without MIGRATION_DATABASE_URL, alembic would use .env and migrate Neon
export DATABASE_URL="postgresql+asyncpg://kjs_test:kjs_test@127.0.0.1:5433/kjs_e2e" MIGRATION_DATABASE_URL="postgresql+asyncpg://kjs_test:kjs_test@127.0.0.1:5433/kjs_e2e" FIRST_ADMIN_EMAIL="admin@e2e.test" FIRST_ADMIN_PASSWORD="e2e-admin-pass-1"
.venv/Scripts/python -m alembic upgrade head > /dev/null 2>&1 && .venv/Scripts/python -m app.seed | tail -1
rm -rf storage-e2e  # files uploaded by the last run
