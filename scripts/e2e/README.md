# End-to-end tests (real servers, real browser)

These click through the whole platform the way people do. They use a **separate local database
(`kjs_e2e`)**, never Neon. Run them before a release or after a big change.

1. Start the test database: `docker compose --profile test up -d test-db`
2. Fresh e2e database + admin: `bash scripts/e2e/reset_e2e_db.sh`
3. Backend on 8001 (from `backend/`, Git Bash):
   `DATABASE_URL=postgresql+asyncpg://kjs_test:kjs_test@127.0.0.1:5433/kjs_e2e FILE_STORAGE_PATH=./storage-e2e .venv/Scripts/python -m uvicorn app.main:app --port 8001`
4. Frontend on 3002 (from `frontend/`, its own build folder so it never touches your `npm run dev`):
   `NEXT_DIST_DIR=.next-e2e API_INTERNAL_URL=http://127.0.0.1:8001 npx next build && NEXT_DIST_DIR=.next-e2e API_INTERNAL_URL=http://127.0.0.1:8001 npx next start -p 3002`
5. API flows (from `backend/`): `.venv/Scripts/python ../scripts/e2e/api_e2e.py` (about 2 min; waits 1 min to prove the page cache refreshes)
6. Real Chrome (needs step 5's data): `node scripts/e2e/browser_e2e.mjs`

Restart the backend before re-running (it resets the 5-enquiries-per-hour limit). Koko uses the real Groq key from `.env`.
