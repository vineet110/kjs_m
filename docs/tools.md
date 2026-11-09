# Tools: KJS India Platform

Every tool we use now, and the tools that could help later, with the reason for each.

Last updated: 9 Nov 2026.

Don't know a word in here? Search for it in `kb.md` (Ctrl + F).

Rule: nothing in section 2 is approved. Every new package or service is asked about first
(`prompt.md`), and the decision goes into `memory.md` section 4.



---------------------------------------------------------------------------------------------------

## 1. Tools we use now

1. Website, staff portal and admin console

   i.    Next.js 16 (App Router), React 19, TypeScript.
   ii.   Tailwind CSS 3 for styling.
   iii.  next-intl 4 for text and languages (English only for now).
   iv.   Our own chart code (no chart package).
   v.    `xlsx` 0.20.3 (from cdn.sheetjs.com) and `mammoth` for Excel / CSV / Word previews.


2. API (backend)

   i.    FastAPI on Python 3.12, with Pydantic v2.
   ii.   SQLAlchemy 2 (async) and asyncpg to talk to the database.
   iii.  Alembic for database migrations.
   iv.   Python `logging` (JSON lines), `smtplib` (email), `hashlib.scrypt` (passwords).
   v.    Background jobs: our own loop in `app/jobs/runner.py` (no Redis, no Celery).


3. Database

   i.    PostgreSQL. Neon (cloud, free) during development, Postgres 17 in Docker in production.
   ii.   A throwaway Postgres in Docker (port 5433) for tests.


4. Files

   i.    A local folder in development.
   ii.   Cloudflare R2 in production: `kjs-prod-files` (private, staff files) and `kjs-site-assets` (public,
         website pictures). Backups also go to R2 (`app/backup_r2.py`).


5. AI

   i.    Groq, model `openai/gpt-oss-120b`, for Koko. Behind the `LLM_PROVIDER` switch, so it can change.


6. Production and network

   i.    Docker and Docker Compose on the company server.
   ii.   nginx in front of the API and the website.
   iii.  Cloudflare Tunnel (no open ports on the server).
   iv.   `deploy.sh`, `backup.sh`, `restore.sh`, `test-restore.sh` in `deploy/`.


7. Testing and code

   i.    pytest for the backend (with a real Postgres, never Neon).
   ii.   Node's own test runner for `frontend/tests/*.mjs`, plus browser checks.
   iii.  Git and GitHub (pull requests, reviews).
   iv.   An AI coding assistant, plus VS Code.



---------------------------------------------------------------------------------------------------

## 2. Tools for later (ideas, not approved)

Grouped by when we would need them. Each says what problem it solves and where it is already logged.


2.1 Before or right after go-live (11 Dec 2026)

1. Uptime checker: UptimeRobot or Better Stack (free plan)

   i.    Problem: nobody hears when the site or API goes down (backlog R45).
   ii.   Checks `/api/health/ready` and the website's `/healthz` every few minutes, emails us when one fails.
   iii.  No code change. Only an account.


2. Error tracking: Sentry (free plan)

   i.    Problem: errors stay in the logs, nobody sees them (R45).
   ii.   Sends each crash, with the page or API route, to one dashboard and an email.
   iii.  New package on both sides (`sentry-sdk`, `@sentry/nextjs`) and a new service: ask first.
   iv.   Cheaper first step: our own job that emails ERROR log lines once a day.


3. Bot protection on forms: Cloudflare Turnstile (free)

   i.    Problem: the visitor form and Koko can be spammed by bots (backlog line "Turnstile later").
   ii.   We already use Cloudflare, so it is one more setting plus a small check in the API. No new package.


4. Email sending service: Brevo, Amazon SES or Resend

   i.    Problem: plain SMTP from a normal mailbox may land in spam or hit a daily limit.
   ii.   Same SMTP settings in `.env`, so no code change. Needs SPF / DKIM records on the domain.


5. Image compression: Squoosh or `ffmpeg` (run by hand, not in the app)

   i.    Problem: about 13 MB of videos and large photos on the website (R43, R46).
   ii.   Smaller files before upload to R2. Nothing is added to the code.


6. Website analytics: Cloudflare Web Analytics (free) or Plausible

   i.    Problem: we don't know how many visitors come, from which country, to which product.
   ii.   One script tag, no cookies, so no cookie banner. Our own charts stay for business data.


2.2 After go-live (early 2027)

1. WhatsApp Business Platform (Meta Cloud API)

   i.    Problem: staff alerts and Koko → WhatsApp hand-off (decisions D13, scope log 2).
   ii.   Needs Meta business verification first (backlog B4). Email stays the default.


2. Superset (Apache, free)

   i.    Problem: KJS may want reports we haven't built (decision D6).
   ii.   Reads a read-only copy of our database. Runs as one more Docker service. Heavy: only if our charts
         are not enough.


3. Log viewer: Grafana Loki, or Dozzle (very light)

   i.    Problem: reading JSON logs with `docker logs` is slow when something breaks.
   ii.   Dozzle shows all container logs in a browser page. Loki + Grafana also searches and charts them.


4. Server monitoring: Netdata or Prometheus + Grafana

   i.    Problem: we can't see disk, memory and CPU on the company server before they run out.
   ii.   Netdata is one container with ready dashboards. Start there.


5. Automatic checks on every PR: GitHub Actions (free for our size)

   i.    Problem: tests run only when someone remembers.
   ii.   Runs pytest (with a Postgres service) and the frontend tests on each PR, and blocks the merge if they fail.
   iii.  No new package. One file in `.github/workflows/`.


6. Dependency updates: GitHub Dependabot (free)

   i.    Problem: security fixes in Next.js, FastAPI etc. are easy to miss.
   ii.   Opens a PR when a package has an update. We still review and test each one.


7. Code style checks: Ruff (Python) and ESLint / Prettier (frontend)

   i.    Problem: two people, two styles; small bugs (unused names, wrong imports) slip through.
   ii.   Dev tools only, not shipped to users. Can run inside GitHub Actions.


8. Password manager for the team: Bitwarden (free)

   i.    Problem: server, R2, Groq, Neon and SMTP keys shared over chat.
   ii.   One shared vault. Nothing to do with the code.


2.3 Stage 2 (2027): buyer intelligence and outreach

1. Buyer data sources

   i.    Import / export data: Volza, Panjiva, ImportGenius (paid). Trade directories: IndiaMART, TradeIndia.
   ii.   Company details: Apollo.io or Hunter.io (find and check business emails).
   iii.  Check first: `research/research_01.pdf` (sources and trials T1–T10), backlog M1, M2.


2. Data pipeline

   i.    Start with our own background jobs and Postgres (decision of 15 Oct: no Redis / Celery).
   ii.   Only if jobs grow too big: a real queue (Redis + RQ, or Postgres-based `procrastinate`).
   iii.  Playwright for pages that need a browser to read, only where the site's rules allow it.


3. Outreach email: Instantly, Lemlist, or our own sequences on SES

   i.    Needs separate sending domains and warm-up, so the main kjsindia.com mail is never marked as spam.
   ii.   Every sequence needs staff approval (Stage 2 plan).


4. PDF quotes and sample forms: WeasyPrint (Python, HTML → PDF)

   i.    Build quotes from an HTML template we already know how to style.


5. More languages, including Arabic (right-to-left)

   i.    next-intl already in place. Translation help: DeepL API, then a human check by KJS.


6. OTP on visitor forms (D12)

   i.    SMS: MSG91 or Twilio (India needs DLT registration for SMS). Or WhatsApp OTP after Meta approval.


7. Search across products and leads

   i.    Postgres full-text search first (no new tool). Meilisearch only if that is too slow.


8. Better AI for Koko and lead scoring

   i.    Keep `LLM_PROVIDER`. Options: Claude API, OpenAI, or Groq as now.
   ii.   For answers from KJS documents: `pgvector` inside our Postgres (no new database).



---------------------------------------------------------------------------------------------------

## 3. How to add a tool

1. Write the problem first, then the tool. If our current stack can do it, use that.

2. Prefer free, small, and things that run inside what we already have (Postgres, Docker, Cloudflare).

3. Ask Vineet (and the senior friend for big ones) before adding any package or service.

4. Once approved: add it to section 1 here, the decision to `memory.md`, and the word to `kb.md`.
