# Prerequisites: KJS India Digital Platform (`kjs_m`)

What you need on your machine to run, develop and test the platform. How to run it: [`README.md`](README.md).
The production server has its own guide: [`deploy/README.md`](deploy/README.md).

---

## 1. Tools to install

1. **Node.js 20 or newer** (the production image uses Node 22), with npm. Runs the Next.js frontend.
2. **Python 3.12.** Runs the FastAPI backend.
3. **[uv](https://docs.astral.sh/uv/).** Creates the backend's `.venv` and installs its packages.
4. **Docker Desktop.** Only for the throwaway test database (`docker compose --profile test up -d test-db`)
   and the production-like builds. Day-to-day development does not need it.
5. **Git**, and on Windows **Git Bash** for the shell scripts.
6. **Google Chrome.** For the end-to-end tests (`scripts/e2e/README.md`).

---

## 2. Database

1. **Development:** PostgreSQL on Neon (cloud). The connection details go in `.env`
   (`DATABASE_URL`, `MIGRATION_DATABASE_URL`).
2. **Tests:** a throwaway Postgres in Docker on port 5433. Tests never touch Neon.
3. **Production:** Postgres 17 in Docker on our Hostinger VPS (`deploy/docker-compose.prod.yml`).
4. Tables are created and changed only by Alembic migrations: `alembic upgrade head` after pulling new code.

No extra database extensions are needed.

---

## 3. Accounts and keys (`.env`)

Copy `.env.example` to `.env` and fill it in. `.env` holds secrets: never commit it, never paste it in chat.
Only the names are listed here.

1. **Neon (database):** `DATABASE_URL`, `MIGRATION_DATABASE_URL`.
2. **Firebase Authentication (staff login):** `FIREBASE_SERVICE_ACCOUNT` (the service-account JSON on one
   line) in `.env`, and `NEXT_PUBLIC_FIREBASE_*` in `frontend/.env.local`. Without it, logins are refused
   with a clear message.
3. **Groq (Koko AI):** `GROQ_API_KEY`. `LLM_PROVIDER` picks the provider (`groq`, `anthropic` or `none`).
4. **First admin:** `FIRST_ADMIN_EMAIL`, `FIRST_ADMIN_PASSWORD`, used once by `python -m app.seed`.
5. **Email (optional):** `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`. Empty host =
   emails are skipped and only logged.
6. **Files (production):** `STORAGE_DRIVER=r2` and the `R2_*` keys for Cloudflare R2. In development the
   default is a local folder (`FILE_STORAGE_PATH`).
7. **Site pictures (production, optional):** `ASSET_BASE_URL` in `deploy/.env`, the public R2 address.
   It becomes `NEXT_PUBLIC_ASSET_BASE` when the frontend is built. Empty = pictures come from
   `frontend/public/`.

Tunable numbers and feature switches are not in `.env`: they are in `config/*.ini` (see `README.md`).

---

## 4. Production only

1. A Linux server (VPS) with Docker and Docker Compose.
2. A Cloudflare account: the Tunnel (public HTTPS without opening ports) and R2 (files, backups).
3. Step by step: [`deploy/README.md`](deploy/README.md).
