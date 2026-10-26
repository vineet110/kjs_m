# KJS India Digital Platform (`kjs_m`)

A comprehensive digital enterprise platform designed for **KJS India** featuring:
- **Public Website with Koko AI**: products and capabilities, offers ticker, gated price sheet / spec / sample / quote (DPDP Act 2023 consent), partners page, private-label builder, and Koko, an AI assistant that answers only from KJS facts.
- **Employee Portal**: server-time check-in/out (Mon–Sat working calendar, missed-punch requests), availability switch, tasks, leads with SLA timers, auto-assigned batches, order-board steps, notifications.
- **Admin Console**: staff approval and permissions, auto-assign with Excel import, order boards (`ABC117-3`) with 50/85/100% alerts, file delete approvals, append-only audit log, team attendance, website/Koko editors, charts from real data.

---

## Tech Stack
- **Frontend**: Next.js 14 (App Router), TypeScript, Tailwind CSS, next-intl (English at launch)
- **Backend API**: FastAPI (Python 3.12), SQLAlchemy 2.0 (async), Alembic, Pydantic v2
- **Database**: PostgreSQL (Neon in development, the company server in production)
- **Background jobs**: a small loop inside the API process (`backend/app/jobs`), Postgres locks
- **Files**: local folder in development, Cloudflare R2 in production
- **Koko AI**: Groq (switchable with `LLM_PROVIDER`)
- **Production**: Docker Compose + nginx + Cloudflare Tunnel: see [`deploy/README.md`](deploy/README.md)

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

## Run it locally (dev, Windows / macOS / Linux)

You need: Node 20+, [uv](https://docs.astral.sh/uv/), Docker Desktop (only for the test database).

```bash
# 1. Secrets: copy and fill in (Neon URLs, GROQ_API_KEY, first admin). Never commit .env
cp .env.example .env

# 2. Backend (FastAPI) on http://localhost:8000  (API docs: /docs)
cd backend
uv venv --python 3.12 .venv
uv pip install --python .venv -r requirements.txt
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

# 5. End-to-end (real servers + real Chrome): see scripts/e2e/README.md
```

After pulling new code, run `alembic upgrade head` again (new tables). Tunable settings (SLA minutes,
batch sizes, feature switches, log levels) are in `config/*.ini`: edit and save, they apply within
seconds without a restart. Secrets stay in `.env`.

How the pieces talk: the browser only calls `localhost:3000`. Next.js proxies `/api/*` to FastAPI,
so the login cookie is first-party. FastAPI owns all rules (login, permissions, audit log).

