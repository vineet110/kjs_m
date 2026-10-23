# KJS India Platform: current status (for re-planning)

As of 23 Oct 2026. Paste this to Claude together with your idea to get a new plan. It covers what exists, what we have decided, and where the "Master Build Prompt" draft clashes with reality.

## 1. Team and way of working
- Two freshers (Vineet + one teammate), learning while building. Claude Code writes the code; we review it.
- Rules we already follow: plan first; explain the why; small changes; **no new dependency without asking**; business logic in `service.py`, thin routers; audit row written in the same transaction; UTC stored and IST shown; one Alembic migration per change; one error shape `{code, message, details, request_id}`; secrets only in `.env` (gitignored); every route has a permission check, with allowed and forbidden tests.
- Docs updated every session: `docs/track.md` (timeline and checklist), `docs/memory.md` (facts, rules, session log), `docs/backlog.md` (blockers, decisions, inputs), `docs/learning/learning-log.md`, and `docs/trackEXP.md` (a simple copy for the company).
- Go-live target: **Fri 11 Dec 2026** (latest 18 Dec). Stage 2 (buyer intelligence and outreach) is 2027.

## 2. Repo and folders (github.com/vineet110/kjs_m; local copy at `C:\VINEET_WORK\KJS_v1`)
Nothing from 23 Oct is committed yet. The plan was branch `feat/p1-foundation` plus a PR after review.

```
KJS_v1/
  CLAUDE.md, README.md (how to run), .env (gitignored), .env.example, docker-compose.yml, Makefile
  .github/workflows/ci.yml   backend pytest (Postgres service) + frontend tsc + next build
  backend/                   FastAPI (Python 3.11 locally, venv at backend/.venv)
    alembic/versions/        0001 all tables + audit trigger, 0002 holidays (applied to Neon + test DB)
    app/core/                config (pydantic-settings from .env), database, security, errors, permissions, deps, rate_limit
    app/models/              user (+sessions, availability log), audit, catalog, lead, order_board, calendar (holidays)
    app/schemas/             common, auth, catalog, lead
    app/services/            audit, auth, catalog, lead, llm (provider switch), koko, calendar
    app/api/v1/endpoints/    auth, public, koko, employee, admin
    app/knowledge/kjs_facts.md   facts Koko answers from
    app/scheduler/, app/worker/  empty placeholders
    app/seed.py              4 categories + first admin
    tests/                   52 tests, all passing
  frontend/                  Next.js 14.2 App Router + next-intl 3.26 + Tailwind
    src/app/[locale]/(public)    home, products, products/[slug], categories/[slug], capabilities/[slug], contact
    src/app/[locale]/(auth)      employee/login
    src/app/[locale]/(employee)  dashboard (real leads); attendance, tasks, order-boards = "Coming soon"
    src/app/[locale]/(admin)     dashboard (real stats), products, audit (real); approvals, auto-assign, order-boards, team-attendance, analytics = "Coming soon"
    src/app/sitemap.ts, robots.ts
    src/components/public        SiteHeader, SiteFooter, EnquiryForm, KokoChatWidget, CategoryGrid, ProductCard, JsonLd
    src/components/portal        PortalShell, LeadsTable
    src/lib/api.ts, site.ts      API client + company facts
    public/images/kjs/           21 assets downloaded from kjsindia.com (logo, cert badges, icons, bg; videos gitignored)
  scripts/fetch_kjs_assets.py    crawler that downloaded the assets
  docs/                          track, memory, backlog, prompt, goal, trackEXP, learning/*, research/*
  docs/research/source/          implementation_plan_v2.pdf, ui_designs_v3.html, kjsKoko.html, wireframes, kjsindia-site-text.md
  nginx/, superset/, tests/      starter placeholders, not used yet
```

Folder names: we kept `frontend/` and `backend/` (proposed decision D17). The plan said `apps/web` and `services/api`; renaming gains nothing.

## 3. What works today (tested end to end)
- **Public site (English only):** home, category pages, product pages, capability pages, contact page, all using real kjsindia.com text and images. Enquiry form with consent tick (DPDP) and honeypot; rate limited (5 per hour per IP). SEO: metadata, sitemap.xml from the DB, robots.txt, Organization and Product JSON-LD.
- **Koko chat:** answers only from `kjs_facts.md` and the product catalogue; replies in the visitor's language; does not promise capacity or prices. When the visitor looks like a buyer, it shows a contact form, and the lead is saved with an AI summary of the chat. It runs on **Groq** (`openai/gpt-oss-120b`) behind an `LLM_PROVIDER` switch, so Anthropic can be plugged in later.
- **Auth:** staff sign up, the account stays pending, an admin approves it, then login and logout. Session token in an httpOnly cookie (only its hash is stored); CSRF header check; scrypt passwords (standard library, no extra package).
- **Roles and permissions:** admin and employee only. Routes check permission keys (`leads.view`, `leads.view_all`, `catalog.edit`, `staff.approve`, `audit.view`, `calendar.edit`). Admin has all of them; each employee gets defaults plus any extras the admin grants.
- **Employee portal:** leads list with status changes (new, contacted, closed).
- **Admin console:** stats dashboard (real DB numbers), approve users, set permissions, add products, audit log viewer, holidays API.
- **Audit log:** append-only, enforced by a Postgres trigger.
- **Working calendar:** Mon–Sat minus holidays; `add_working_days()` with tests (for order boards later).
- **Ops:** health endpoints `/api/health` and `/api/health/ready`; Docker `test-db` for tests; CI workflow written (runs once pushed).

## 4. Not built yet (from the existing plan)
Attendance, availability toggle UI, tasks, SLA timers on leads, auto-assign batches, order boards, approvals inbox, file uploads (R2), alerts (email/WhatsApp), offers ticker, gated price sheet / spec PDF / sample, private-label configurator, partner page, admin pages editor, charts, Koko settings page, job queue/scheduler, structured logging setup, ini config system, Arabic/other languages, deployment (company server, Cloudflare, nginx), backups.

## 5. Decisions already made (keep these unless you change them)
| # | Decision |
|---|---|
| D1 | Next.js (for SEO) |
| D2 | English only at launch; next-intl stays so languages can be added later |
| D3 | Gate on actions only (price sheet, sample, quote); browsing stays free |
| D4 | Koko on Groq for now (no Anthropic API key; Claude Max can't power a website). Before go-live, test Groq against Claude on 30 real questions |
| D5 | Roles: admin + employee only, no manager. Per-employee permissions |
| D6 | Native charts from real DB data only (no fake numbers); Superset after go-live |
| D7 | Domain: decide at deployment |
| D8 | Timeline approved (11 Dec target) |
| D15 | Neon free Postgres now (dev/staging); company server later. Plain Postgres so moving is `pg_dump` / `pg_restore` |
| D16 | Files/images/videos: **Cloudflare R2** (S3-compatible); local disk folder in dev behind the same module |
| — | Audience is B2B; capture every lead. Build with scale in mind |

Still open: D9 (what "records" in an auto-assign batch are), D18 (does the company expect Stage 2 features from the demo video by 11 Dec?), D19 (public USD prices or price sheet via form?), production hosting, I9 (stick-pack fill range 0.9–3 g vs 18 g).

## 6. Where the "Master Build Prompt" draft disagrees with the current state
The draft was written without knowing the above. Fix these before using it:

| Draft says | Reality / our decision |
|---|---|
| Repo layout `apps/web`, `services/api` | `frontend/`, `backend/` (D17) |
| Languages EN/AR/ES/FR + Arabic RTL at launch | English only at launch (D2) |
| 5 roles (visitor, partner, employee, manager, admin) | admin + employee + per-employee permissions (D5) |
| Anthropic API, default `claude-opus-5-5`, Batches API | No Anthropic key yet; Groq behind a provider switch (D4) |
| Neon object storage for files | Cloudflare R2 (D16) |
| Superset at launch (Should) | Native charts first, Superset later (D6) |
| Argon2 passwords | scrypt from the standard library (no new dependency; can switch) |
| Routes `/portal/*` | Currently `/employee/*` (easy to rename if wanted) |
| `docs/PROGRESS.md`, `BACKLOG.md`, `DECISIONS/` ADRs | We use `track.md`, `backlog.md` (with a decisions table), `memory.md` |
| pnpm, shadcn/ui, TanStack, react-hook-form, zod, pino, Sentry, watchfiles, gitleaks, ruff/mypy | Not installed. Each one is a new dependency and needs a yes |
| Hot-reloaded `config/*.ini` system (task 2) | Not built; settings come from `.env` via pydantic-settings. Big task: decide if it's worth it before 11 Dec |
| First tasks: skeleton, auth, brand extraction, public home | Mostly done already (see section 3) |
| Python 3.12 | 3.11 locally (3.12 install pending) |

## 7. Known problems and todo items
- **Slow API (~1.4 s per call):** the Neon database is in us-east-2 (Ohio), far from India. Fix: a new Neon project in Singapore, or local Docker Postgres for dev. Public pages cache for 60 s to hide it.
- Secrets (Groq key, Neon password) were pasted in chat. Rotate them before go-live (B9).
- Waiting on KJS: real product list (I2), price bands (I3), employee list and holidays (I4), FAQs for Koko (I5), order-board templates (I6), official brand files (I1).
- Company server, IT contact and domain/DNS access unknown (B3, B6). WhatsApp Business verification not started (B4).
- Commit and push of the 23 Oct work after review (B11).

## 8. What I want from the new plan
(Vineet: write your idea here, e.g. "one integrated plan by module instead of version/phase", priorities, what must be in 11 Dec.)
