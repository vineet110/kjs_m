# Memory: KJS India Platform

The project's long-term memory: short facts, rules and decisions.

Anyone joining (person or AI) reads this first.

Last updated: 24 Oct 2026.

Don't know a word in here? Search for it in `kb.md` (Ctrl + F).



---------------------------------------------------------------------------------------------------

## 1. The project in short

1. Client

   i.    KJS India Pvt. Ltd. Makes coffee, tea, health drinks and confectionery for other brands
         (co-manufacturing and private label).
   ii.   Factory: IDA Pashamylaram, Hyderabad. Website: www.kjsindia.com
   iii.  Sells B2B only: retailers, distributors, importers, brands. Bulk and export.


2. What we are building: one platform with three parts

   i.    Public website, with Koko the AI assistant.
   ii.   Employee portal.
   iii.  Admin console.
   iv.   Stage 2 (2027) adds buyer intelligence and outreach.


3. Team

   i.    Vineet Pandey (developer, lead) and one fresher teammate, working with an AI coding assistant.
   ii.   A senior friend reviews big decisions when asked.


4. Dates

   i.    Phase 1 (all features): 26 Oct to 7 Nov 2026.  Done early, on 24 Oct.
   ii.   Production, real data, UAT: 9 Nov to early Dec.
   iii.  Go-live: Fri 11 Dec 2026. Latest acceptable: Fri 18 Dec.


5. Status (25 Oct)

   i.    Every Phase 1 feature is built and tested, and merged into `main`.
   ii.   Tests: 138 backend tests, plus end-to-end 114 API checks and 38 real-browser checks.
   iii.  Production setup is ready in `deploy/` and tested locally (branch `kjs_v`, commit `ebfe12a`).
   iv.   Next: needs the server and inputs from KJS. Meanwhile, review the assumptions in `backlog.md` section 3.
   v.    25 Oct senior review: about 50 findings, every high and medium one fixed and tested (not committed yet).


6. Repo

   i.    https://github.com/vineet110/kjs_m
   ii.   Local copy: `C:\VINEET_WORK\KJS_v1`



---------------------------------------------------------------------------------------------------

## 2. Which file to read for what

1. Today's to-do list: `checklist.md`  (the ONLY list we work from)

2. Where we are, in short: `track.md`

3. Blockers, decisions, guesses to review, inputs from KJS: `backlog.md`

4. What "done" means: `goal.md`

5. A word or tool you don't know: `kb.md`

6. How to work with the AI assistant, and the project rules: `prompt.md`

7. Simple version for the KJS team: `trackEXP.md`

8. What we learned each day: `learning/learning-log.md`

9. The master plan (source of the 2-week plan): `research/source/master-build-prompt.pdf`



---------------------------------------------------------------------------------------------------

## 3. Stack (what we actually use)

1. Website and portal screens

   i.    Next.js 16 (App Router, React 19), TypeScript, Tailwind CSS 3, next-intl 4 (English only for now).
   ii.   Charts are drawn by our own code (no chart package).


2. API (backend)

   i.    FastAPI on Python 3.12.
   ii.   SQLAlchemy 2 (async) with asyncpg, Alembic for migrations, Pydantic v2.
   iii.  Python's own `logging`, writing JSON lines.


3. Database

   i.    PostgreSQL. Neon (free, cloud) during development. Company server later.
   ii.   Tests use a throwaway Postgres in Docker (port 5433). They never touch Neon.


4. Files

   i.    Never stored in the database.
   ii.   A local folder in development, Cloudflare R2 in production (code ready, needs keys).


5. Background jobs

   i.    A small loop inside the API process (`app/jobs/runner.py`). No Redis, no Celery, no separate worker.


6. AI (Koko)

   i.    Groq, model `openai/gpt-oss-120b`, behind the `LLM_PROVIDER` setting.


7. Email

   i.    Plain SMTP (Python's `smtplib`). Skipped until SMTP details are in `.env`.


8. Settings

   i.    Secrets in `.env` (never committed).
   ii.   Tunable numbers and feature switches in `config/*.ini`. They apply within seconds, no restart.


9. Production (ready in `deploy/`, waiting for the server)

   i.    Docker Compose on the company server: Postgres 17, API, website, nginx, Cloudflare Tunnel.
   ii.   `deploy.sh` to update, `backup.sh` nightly, `restore.sh`. Guide: `deploy/README.md`.



---------------------------------------------------------------------------------------------------

## 4. Decisions

1. 15 Oct. Postgres for the job queue instead of Redis / Celery.

2. 15 Oct. Auto-assign hands out work in small batches (next batch when the last one is done).

3. 23 Oct. Next.js (D1).

4. 23 Oct. English only at launch (D2).

5. 23 Oct. The visitor form appears only on actions, not on browsing (D3).

6. 23 Oct. Koko on Groq for now, behind a provider switch (D4).

7. 23 Oct. Roles: admin and employee only. Routes check permissions (D5).

8. 23 Oct. Our own charts from real data only. Superset later, maybe (D6).

9. 23 Oct. Domain decided at deployment (D7).

10. 23 Oct. Timeline approved: go-live 11 Dec, latest 18 Dec (D8).

11. 23 Oct. Neon for development, company server later (D15). Files on Cloudflare R2 (D16).

12. 23 Oct. Passwords with scrypt (built into Python). Sessions are random tokens stored in the database, not JWT.
    Zero new packages.

13. 23 Oct. Neon CLI, Neon Auth and Neon storage are NOT used. Only the connection string.

14. 23 Oct. No made-up products or prices on the site.

15. 24 Oct. New plan: Phase 1 in 2 weeks, one simple list (`checklist.md`).

16. 24 Oct. `docs/` is not committed to git. It lives only on this PC.

17. 24 Oct. Every guess we make goes into `backlog.md` section 3, so it can be checked later.

18. 24 Oct. Commits and pull requests never mention the AI assistant.



---------------------------------------------------------------------------------------------------

## 5. How the code is laid out

1. Backend: `backend/app/`

   i.    `core/`: settings (`config/`), database, login security, permissions, errors, logs, rate limits, file storage.
   ii.   `models/`: database tables.
   iii.  `schemas/`: shapes of API input and output (Pydantic).
   iv.   `services/`: business rules and audit rows. All the real logic is here.
   v.    `api/v1/endpoints/`: thin routes. Read the request, call a service, return the result.
   vi.   `jobs/`: the background loop.
   vii.  `knowledge/kjs_facts.md`: Koko's facts (now also editable in Admin > Koko).
   viii. `alembic/versions/`: migrations 0001 to 0009.


2. Frontend: `frontend/src/`

   i.    `app/[locale]/(public)`: website pages.
   ii.   `app/[locale]/(employee)` and `(admin)`: portal pages.
   iii.  `components/public` and `components/portal`: building blocks.
   iv.   `lib/api.ts`: types and helpers for calling the API.


3. Other folders

   i.    `config/`: the `.ini` settings files.
   ii.   `scripts/e2e/`: end-to-end tests (see its README).
   iii.  `.github/workflows/ci.yml`: tests on every push.


4. How a request travels

   i.    Browser → Next.js on port 3000 → `/api/*` is forwarded to FastAPI on port 8000.
   ii.   The login cookie is called `kjs_session` (httpOnly).
   iii.  Every write request must carry the header `x-requested-with`.



---------------------------------------------------------------------------------------------------

## 6. Business rules to never forget

1. Working days are Monday to Saturday, minus holidays. Sunday is off.

2. Times are stored in UTC and shown in IST.

3. The audit log is written in the same database transaction as the change. A trigger blocks editing or deleting it.

4. Every API route checks a permission, and has a test for the allowed AND the forbidden user.

5. Order board code looks like `ABC117-3`. 5 steps by default.

6. Board alerts at 50%, 85% and 100% of a step's time, each sent once only.

7. Deleting a file needs approval.

8. Lead SLA: respond in 20 minutes, resolve in 60 minutes (working minutes, changeable in `config/sla.ini`).

9. Koko answers only from KJS content. It never gives prices.

10. Every public form has a consent tick (DPDP Act 2023). Visitor IPs are stored only as hashes.



---------------------------------------------------------------------------------------------------

## 7. Screen names we use

1. Website: P1 home, P2 category, P3 product, P5 visitor form, P6 partners. (P4 importer pages = Stage 2)

2. Employee: E1 My day. (E2 buyer account = Stage 2)

3. Admin Stage 2 screens: A1 to A7. (Not to be confused with assumptions A1–A52 in the backlog.)



---------------------------------------------------------------------------------------------------

## 8. People and contacts

1. KJS: +91 97037 35666, contact@kjsindia.com

2. Manager / approver: (name pending)

3. IT contact for the server: (pending)



---------------------------------------------------------------------------------------------------

## 9. Session log (newest first)

1. 27 Oct 2026 (production-readiness review)

   i.    `docs/` is now committed (shared with the teammate). `.env` stays private: each person makes their
         own from `.env.example`.
   ii.   Three independent reviews of the backend: server behaviour, data correctness, security.
         Security: no blockers. Everything found was checked against the code before fixing.
   iii.  Must fix (done): nginx kept old container addresses after a deploy; approving a missed punch erased
         the real check-out; one config typo could silently stop all background jobs.
   iv.   Should fix (done): re-enabling accounts, admin lock-out by strangers, unverified mail-server TLS,
         slow mail server stalling jobs, customer data in error logs, random 502s, limiter memory,
         long names breaking actions, board time a day early, finished boards/batches, lead status rules,
         silent import cut at 5000 rows. Plus about 20 smaller ones (backlog section 9).
   v.    New rules to review: A67–A72. Migration 0011. 22 new tests (162 backend tests in total, all passing),
         114 API + 38 Chrome end-to-end checks pass. nginx container swap tested for real.
   vi.   e2e backend now runs with background jobs off (the minute job raced the "preview" check).
   vii.  Merged into `main` with pull request #5 (CI green). Needs `alembic upgrade head` (migration 0011).


2. 26 Oct 2026 (merge, speed, Smart App Control)

   i.    Review fixes committed (`ba19e69`) and merged into `main` with `ebfe12a` (pull request #3).
   ii.   Slow admin, portal and Koko: measured. Neon (US) is about 560 ms per query from India, 1.8 s to connect.
         Pages make 3 to 6 queries, so 2 to 3 s per click. Fix for dev: local Docker database (`docker compose up -d db`).
         Production is fine: Postgres sits next to the app on the KJS server.
   iii.  Koko model `openai/gpt-oss-120b` is a thinking model (hidden reasoning tokens). Faster model to be compared.
   iv.   Smart App Control turned off by Vineet. B12 closed; `.venv` Python works again.
   v.    Next.js 14 → 16.4.3, React 19, next-intl 4 on branch `next16` (B13 closed). 14 unused packages removed.
         All checks pass: tsc, build, dev, 114 API + 38 Chrome e2e, Docker image. Merged: PR #4 (27 Oct).
   vi.   Senior review of the upgrade: fetch cache still works (0 API calls on 5 loads), CSP clean in Chrome,
         visuals same. Found: image paths with `?` break in Next 16, outside URLs crash the page. Fixed (A66),
         139 backend tests pass.
   vii.  next-intl kept although unused today (B16): ready for Stage 2 languages.


3. 25 Oct 2026 (senior review)

   i.    Four independent reviews: login and access, untrusted input and files, backend logic, frontend and server.
         About 50 findings; every high and medium one fixed and tested. Not committed yet (Vineet decides).
   ii.   Worst ones fixed:
         a.  An offer link could be `javascript:` and run code as an admin who clicked it.
         b.  Anyone with `staff.approve` could give themselves every permission or disable the admins.
         c.  After 10 wrong passwords the right one still worked, so guessing never stopped.
         d.  Board members could make order documents public on the internet.
         e.  A line break in a visitor's name stopped all emails and re-sent others every minute.
         f.  An Excel "zip bomb" could freeze the API. Koko had no total cost cap.
         g.  Double clicks could double-assign batches, double-claim leads, or duplicate board tasks.
         h.  Production: the app used the database owner; backups readable by all; restore could half-fail.
   iii.  Package security updates: FastAPI 0.129.2 (Starlette 0.52.1), python-multipart 0.0.32, Node 22, nginx 1.28,
         cloudflared 2026.9. Next.js 14.2.35 was already up to date.
   iv.   Migration 0010 (email retries, one open batch per person, indexes): applied to Neon and the test DB.
   v.    Tests: 138 backend tests pass (13 new). Production stack re-tested on this PC: limited DB user verified,
         CSP gives no browser errors, login redirect can't leave our site, restore drill passed.
   vi.   Left for later on purpose: `backlog.md` section 8 (R1–R12). New decisions D20, D21; blockers B13, B14;
         assumptions A59–A65.


4. 25 Oct 2026

   i.    Merged Phase 1 into `main` (pull request #2, CI green).
   ii.   Production setup in `deploy/`: Docker images (non-root), production compose (Postgres 17, nginx,
         Cloudflare Tunnel), deploy / backup / restore scripts, deploy guide.
   iii.  The API now refuses to start in production with unsafe settings.
   iv.   Tested the whole production stack on this PC: pages through nginx, fake IP can't dodge the rate limit,
         30 MB upload rejected, backup → damage → restore brings everything back. 125 backend tests.
   v.    Fixed the old nginx config (it cut `/api` off every address). Dev `docker-compose.yml` now only has the databases.
   vi.   Pushed `ebfe12a` to `kjs_v`, not merged yet.
   vii.  Windows Smart App Control started blocking `.venv\Scripts\python.exe` (B12). Workaround in the backlog.
   viii. New guesses A53–A58 in `backlog.md` section 3.


5. 24 Oct 2026 (morning)

   i.    Committed and pushed all Phase 1 work to `kjs_v` (`3a88c65`).
   ii.   Docs cleaned up: tables replaced with numbered lists; new `kb.md` (look up any word);
         removed old files (status-for-replanning, motivation, requirements-review, video summary, old learning notes).
   iii.  Next: production setup.


4. 23–24 Oct 2026 (night)

   i.    New plan from `master-build-prompt.pdf`: Phase 1 in 2 weeks, one list (`checklist.md`).
   ii.   Built every Phase 1 feature: settings files with live reload, JSON logs with request IDs, background jobs,
         attendance, lead SLA timers, notifications, tasks, file storage, order boards, approvals, auto-assign,
         gated forms, offers ticker, WhatsApp button, partners page, private-label builder, and all admin pages.
   iii.  Migrations 0003 to 0009 applied to Neon and the test database.
   iv.   End-to-end testing found and fixed 2 real bugs:
         a.  Every visitor looked like the same IP behind the Next.js proxy, so they shared one rate limit.
         b.  The first request after Neon dropped its connections failed (`pool_pre_ping` back on).
   v.    Every guess written in `backlog.md` section 3 (A1–A52).


6. 23 Oct 2026 (5)

   i.    Holidays table and calendar API, SEO (sitemap, robots, JSON-LD), CI workflow, Koko rules hardened. 52 tests.


7. 23 Oct 2026 (4)

   i.    First working slice: website, Koko on Groq, login, leads, admin.


8. 23 Oct 2026 (2 and 3)

   i.    Installed Docker and gh, cloned the repo, decided D1–D8, made `trackEXP.md`, summarised the demo video.


9. 23 Oct 2026 (1)

   i.    Read all the planning documents, listed the conflicts, set up `docs/`.
