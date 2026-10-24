# KJS India Digital Platform (`kjs_m`)

A comprehensive digital enterprise platform designed for **KJS India** featuring:
- **Public Website with Koko AI**: Product showcase, dynamic moving offers ticker, category unlock gate (DPDP Act 2023 compliant), and Claude Haiku-powered RAG assistant with pgvector.
- **Employee Portal**: Server-time punch attendance (Mon–Sat working calendar, night shift support, auto-closing & regularization), availability toggle, task kanban with query outcome logging, and member-scoped order board step tracking.
- **Admin Console**: Automatic task assignment engine (least-busy-first/round-robin with dry-run preview), 5-checkpoint order board manager (`ABC117-xxxx`), file upload versioning with delete approval workflow, append-only immutable audit logging, team attendance grid with payroll export, and embedded Apache Superset analytics.

---

## Tech Stack
- **Frontend**: Next.js 14+ (App Router), TypeScript, Tailwind CSS, shadcn/ui, next-intl (English & Hindi)
- **Backend API**: FastAPI (Python 3.12), SQLAlchemy 2.0 (Async), Alembic, Pydantic v2, APScheduler
- **Database**: PostgreSQL 16 + pgvector (embedding vector(384) for Koko)
- **Queue/Worker**: PostgreSQL job queue (`FOR UPDATE SKIP LOCKED`)
- **Analytics**: Apache Superset (Dockerized, embedded via Guest Token SDK)
- **External Services**: Meta WhatsApp Business Cloud API, Resend/Brevo (Email), Anthropic Claude Haiku API

---

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

# 5. End-to-end (real servers + real Chrome): see scripts/e2e/README.md
```

After pulling new code, run `alembic upgrade head` again (new tables). Tunable settings (SLA minutes,
batch sizes, feature switches, log levels) are in `config/*.ini`: edit and save, they apply within
seconds without a restart. Secrets stay in `.env`.

How the pieces talk: the browser only calls `localhost:3000`. Next.js proxies `/api/*` to FastAPI,
so the login cookie is first-party. FastAPI owns all rules (login, permissions, audit log).

