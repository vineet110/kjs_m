# KJS India Digital Platform (`kjs_m`)

The website and staff portal of **KJS India** in one repo:

1. **Public website**
   - Home page with an admin-editable banner, a sliding strip of certificates and partner logos, and
     pop-up "recent activity" lines.
   - Products and categories with photos, partners page, private-label builder, contact.
   - Gated price sheet / spec / sample / quote with consent (DPDP Act 2023).
   - Koko, an AI assistant that answers only from KJS facts.
2. **Employee portal**
   - Staff login with Firebase (email verification, password reset).
   - Check-in/out on server time (Mon-Sat calendar, missed-punch requests), availability switch.
   - Leads with SLA timers, internal leads with files and Excel import, Koko leads, contacts, tasks.
   - Auto-assigned batches, order boards (members, files, history), team chat, notifications.
3. **Admin console**
   - Staff approval and per-person permissions, auto-assign with Excel import, client schedulers.
   - Order boards (`ABC117-3`) with 50/85/100% alerts, complaints, file delete approvals.
   - Team attendance, holidays, append-only audit log.
   - Website editor (texts, home banner, partner logos, pop-up activity, offers) and Koko editor.
   - Reports from real data, including Site insights.

Areas can be switched on, off or admin-only in `config/modules.ini`, without deleting any data.

---

## Tech stack

1. **Frontend:** Next.js 16 (App Router, React 19), TypeScript, Tailwind CSS 3, next-intl 4 (English for now).
   Charts are our own code.
2. **Backend API:** FastAPI on Python 3.12, SQLAlchemy 2 (async, asyncpg), Alembic, Pydantic v2.
3. **Database:** PostgreSQL. Neon in development, Postgres 17 on our Hostinger VPS in production
   (live at https://twins.kjsindia.com).
4. **Login:** Firebase Authentication checks passwords. The API then starts its own session cookie
   (`kjs_session`), so roles and permissions stay in our database.
5. **Background jobs:** a small loop inside the API process (`backend/app/jobs`). No Redis, no Celery.
6. **Files:** a local folder in development, Cloudflare R2 in production. Site pictures can also be served
   from R2 (`NEXT_PUBLIC_ASSET_BASE`).
7. **Koko AI:** Groq (switchable with `LLM_PROVIDER`).
8. **Email:** plain SMTP. Skipped (only logged) until the SMTP details are in `.env`.
9. **Production:** Docker Compose + nginx + Cloudflare Tunnel. See [`deploy/README.md`](deploy/README.md).

What you need installed: see [`PREREQUISITES.md`](PREREQUISITES.md).

---

## Every day (Windows PowerShell, after the one-time setup below)

Two terminals. Always start Python through `.venv` (plain `uvicorn` uses the system Python,
which doesn't have our packages: "No module named ...").

```powershell
# Terminal 1: backend on http://localhost:8000
cd C:\VINEET_WORK\KJS_v1\backend
.\.venv\Scripts\alembic upgrade head          # only after pulling new code (safe to repeat)
.\.venv\Scripts\python -m uvicorn app.main:app --reload --port 8000

# Terminal 2: frontend on http://localhost:3000
cd C:\VINEET_WORK\KJS_v1\frontend
npm run dev
```

Open http://localhost:3000. Staff login: http://localhost:3000/employee/login.
The frontend expects the backend on port 8000 (`API_INTERNAL_URL` in `.env`).

Production build on your PC (to check it the way the server runs it):

```powershell
cd C:\VINEET_WORK\KJS_v1\frontend
npm run build      # must finish without errors first
npm start          # runs the build from `npm run build` (no build = "Could not find a production build")
```

If `npm run build` fails with `.next-e2e/types/validator.ts ... Cannot find module`, an old test build
is left over (the e2e script builds into `.next-e2e`). It is generated and gitignored, so delete it and
build again:

```powershell
Remove-Item -Recurse -Force .next-e2e
npm run build
```

## One-time setup (Windows / macOS / Linux)

You need: Node 20+, [uv](https://docs.astral.sh/uv/), Docker Desktop (only for the test database).

```bash
# 1. Secrets: copy and fill in (Neon URLs, GROQ_API_KEY, FIREBASE_SERVICE_ACCOUNT, first admin). Never commit .env
cp .env.example .env
#    Frontend Firebase keys (NEXT_PUBLIC_FIREBASE_*) go in frontend/.env.local

# 2. Backend (FastAPI) on http://localhost:8000  (API docs: /docs)
cd backend
uv venv --python 3.12 .venv
uv pip install --python .venv -r requirements-dev.txt   # app + test tools
.venv/Scripts/alembic upgrade head        # macOS/Linux: .venv/bin/alembic
.venv/Scripts/python -m app.seed          # categories + first admin
.venv/Scripts/python -m uvicorn app.main:app --reload --port 8000

# 3. Frontend (Next.js) on http://localhost:3000  (new terminal)
cd frontend
npm ci
python ../scripts/fetch_kjs_assets.py public/images/kjs ../storage/kjsindia-site-text.md  # videos (gitignored); 2nd arg = where to save the site text
npm run dev

# 4. Tests (throwaway Postgres in Docker, never touches Neon)
docker compose --profile test up -d test-db
cd backend && .venv/Scripts/python -m pytest -q
#    Or fully inside Docker (about 40 s; also works when Windows blocks .venv's python.exe).
#    Git Bash, from backend/:
#    docker build -q -t kjs-api:test . && MSYS_NO_PATHCONV=1 docker run --rm -u root --network container:kjs_test_db \
#      -v "$(cygpath -w "$PWD/tests"):/app/tests" -v "$(cygpath -w "$PWD/pyproject.toml"):/app/pyproject.toml" \
#      -v "$(cygpath -w "$PWD/../config"):/config:ro" \
#      -e TEST_DATABASE_URL=postgresql+asyncpg://kjs_test:kjs_test@127.0.0.1:5432/kjs_test \
#      kjs-api:test sh -c "pip install -q pytest==8.2.2 pytest-asyncio==0.23.7 freezegun==1.5.1 && python -m pytest -q"

# 5. Frontend checks: see frontend/CLAUDE.md (typecheck, npm test, npm run build)

# 6. End-to-end (real servers + real Chrome): see scripts/e2e/README.md
```

After pulling new code, run `alembic upgrade head` again (new tables). The hosted test site deploys
`main` on merge but never runs migrations, so whoever merges a PR with a new migration runs it right away.

---

## Settings

1. **Secrets** (passwords, API keys) are only in `.env`, never committed.
2. **Tunable settings** are in `config/*.ini`, one file per feature. Edit and save: they apply within
   seconds, without a restart. A typo is refused and the last good settings stay.
   - `modules.ini`: which areas are on, off or admin-only.
   - `site_ui.ini`, `site_insights.ini`: Home page look and motion, website visit reports.
   - `leads.ini`, `sla.ini`, `assign.ini`, `harvest.ini`: leads, SLA timers, auto-assign, Lead Harvester.
   - `attendance.ini`, `boards.ini`, `chat.ini`, `complaints.ini`: the matching portal areas.
   - `features.ini`: website switches (Koko, offers ticker, WhatsApp button, connect popup).
   - `alerts.ini`, `notifications.ini`, `analytics.ini`, `koko.ini`, `storage.ini`, `app.ini`, `logging.ini`:
     alerts, the bell, reports, Koko, files, site name and timezone, log levels.

How the pieces talk: the browser only calls `localhost:3000`. Next.js proxies `/api/*` to FastAPI,
so the login cookie is first-party. FastAPI owns all rules (login, permissions, audit log).

---

## Where to read more

1. [`docs/README.md`](docs/README.md): the project docs and the order to read them in.
2. [`deploy/README.md`](deploy/README.md): setting up and updating the production server.
3. [`scripts/e2e/README.md`](scripts/e2e/README.md): end-to-end tests.
