# Memory: KJS India Platform

> The project's long-term memory. Short facts only. Anyone (human or Claude) joining should read this first.
> Update it when a decision is made or a fact changes. Last updated: **23 Oct 2026**.

## The project in 5 lines
- **Client:** KJS India Pvt. Ltd., a co-manufacturer / private-label maker of coffee, tea, health drinks and confectionery. IDA Pashamylaram, Hyderabad. Corporate site: www.kjsindia.com
- **Product:** one platform, three faces: public website (SEO + Koko AI), employee portal, admin console. Stage 2 (2027) adds Buyer Intelligence & Outreach.
- **Team:** Vineet Pandey (developer, lead) + one fresher teammate, working with Claude Code. A senior friend reviews important decisions on request.
- **Target:** Stage 1 go-live **Fri 11 Dec 2026** (buffer to Fri 18 Dec, see `track.md`).
- **Audience:** B2B only (retailers, distributors, importers, brands wanting white/private label). KJS is a manufacturer with 2 large factories, selling in bulk/export. We still capture **every** lead in the DB.
- **Status (23 Oct):** first working slice built, **not committed yet**: staff sign-up → admin approval with permissions → login; audit log; categories/products; leads (form + Koko); Koko on Groq; public site with kjsindia.com content. Tests green. Repo https://github.com/vineet110/kjs_m

## Source of truth
| Need | Read |
|---|---|
| Master plan | `research/source/implementation_plan_v2.pdf` |
| Public site, My day, Stage 2 screens | `research/source/ui_designs_v3.html` (P1–P6, E1–E2, A1–A7) |
| Portal and admin screens | `research/source/kjsKoko.html` (screens 01–15) |
| Detailed module logic (attendance, order-board maths, alerts) | `research/source/Implementation_Plan_KJS_India.pdf` (v1, §5) |
| Our review, conflicts, risks | `research/requirements-review.md` |
| Dates and checklist | `track.md` |

When documents disagree: **plan v2 + ui v3 + kjsKoko** win over v1 / wireframes v2.

## Stack (plan v2)
- **Web:** Next.js (App Router, TS strict), Tailwind + shadcn/ui, next-intl, TanStack Query + generated OpenAPI client, react-hook-form + zod
- **API:** FastAPI (Python 3.12), SQLAlchemy 2 (async), Alembic, Pydantic v2, structlog
- **DB:** PostgreSQL 16 + pgvector + pg_trgm. Local: Docker. Staging: Neon free tier. Production: company server (move with pg_dump/pg_restore).
- **Files:** never in the DB. One storage module (S3-compatible): **Cloudflare R2**; local disk in dev. Also the job queue (`FOR UPDATE SKIP LOCKED`) + APScheduler
- **AI:** Koko = RAG over our content. Dev uses **Groq** behind an `LLM_PROVIDER` setting; Anthropic later if the test wins (D4). Claude Max is for us coding, not for the website.
- **Mail:** Resend/Brevo. **WhatsApp:** Cloud API (Meta-approved templates, opt-in staff only)
- **Ops:** Docker Compose on the company server + Cloudflare Tunnel; GitHub Actions; Sentry; UptimeRobot; restic backups
- **Tests:** pytest, Vitest, Playwright, Lighthouse CI

## Decisions log
| Date | Decision | Status |
|---|---|---|
| 15 Oct | Next.js replaces React+Vite (plan v2) | Assumed. Confirm approval (D1) |
| 15 Oct | Monorepo: `apps/web`, `services/api`, `deploy/`, `docs/` | Accepted |
| 15 Oct | Postgres queue instead of Redis/Celery | Accepted |
| 15 Oct | Auto-assign uses **batches** (every 15 min, next batch when done), not one daily run | Accepted |
| 23 Oct | Next.js confirmed (D1) | Accepted |
| 23 Oct | English only at launch; other languages later (D2) | Accepted |
| 23 Oct | Stage 1 builds native charts from **real DB data**; Superset after go-live (D6) | Accepted |
| 23 Oct | Email alerts first; WhatsApp when Meta approves | **Proposed** |
| 23 Oct | Roles: **admin + employee** only, no manager. Routes check permissions; per-employee extras possible (D5) | Accepted |
| 23 Oct | Re-baselined timeline approved: go-live 11 Dec, latest 18 Dec (D8) | Accepted |
| 23 Oct | Neon free for staging, company server later; files behind a storage module (D15, D16) | Accepted |
| 23 Oct | Koko on Groq for dev, behind a provider switch (D4) | Accepted |
| 23 Oct | Domain decided at deployment (D7) | Postponed |
| 23 Oct | Passwords: stdlib `hashlib.scrypt` (not Argon2); sessions are DB tokens (not JWT). Zero new packages | Accepted (Claude; Vineet to review) |
| 23 Oct | Neon CLI / Neon Auth / Neon object storage NOT used: FastAPI owns auth, files go to R2. Only the connection string | Accepted (Claude; Vineet to review) |
| 23 Oct | No made-up products or prices on the site: products come from admin; prices wait for I3 | Accepted |
| 23 Oct | Heavy packages (torch, sentence-transformers, anthropic SDK) removed from requirements until needed | Accepted (Claude; Vineet to review) |
| 23 Oct | Gate only on actions, not on browsing (D3) | Accepted |
| 23 Oct | Images/videos on Cloudflare R2 (D16) | Accepted |
| 23 Oct | Docker Desktop free tier OK for KJS (B7) | Accepted |
| 23 Oct | Build "enterprise-ready" from day one: swappable providers, env config, migrations, permissions, audit. Heavy security hardening later | Accepted |

## How the code is laid out (23 Oct)
- `backend/app/`: `core/` (config, db, security, permissions, deps, errors, rate_limit) · `models/` · `schemas/` · `services/` (business rules + audit) · `api/v1/endpoints/` (thin routers) · `knowledge/kjs_facts.md` (Koko's facts) · `seed.py`
- `frontend/src/`: `app/[locale]/(public|auth|employee|admin)` · `components/public|portal` · `lib/api.ts` (types + fetch helpers) · `lib/site.ts` (company facts + capability pages)
- Browser → Next.js `/api/*` proxy → FastAPI. Cookie `kjs_session` (httpOnly). Writes need header `x-requested-with`.
- Neon: app uses the pooled URL (statement cache off); Alembic uses the direct URL. Region us-east-2 (far from India): fine for dev.
- kjsindia.com images/videos in `frontend/public/images/kjs/` (videos gitignored; `scripts/fetch_kjs_assets.py` re-downloads).

## Business rules to never forget
- Working days are **Mon–Sat**. Sunday is off. Plus a holiday table. Used by attendance, auto-assign, deadlines and order-board maths.
- Store times in **UTC**, show them in **IST**.
- **Audit log** is written in the **same DB transaction** as the change. A DB trigger blocks UPDATE/DELETE on it.
- Every API route declares a **permission dependency** (role gives defaults) and has an allowed + forbidden test.
- Order board ID: `^ABC117-[0-9]{1,6}$`, unique. 5 steps. Default split 25/19/30/16/10 %.
- Alerts at 50 / 85 / 100 % of a step's working time, **once each** (unique key on alert_log).
- Files: random names, sha256, size/MIME checks, versioned. Delete = request → admin approves → soft delete (kept 30 days).
- Lead SLA defaults: respond in 20 min, resolve in 60 min (configurable).
- Koko answers only from KJS content, never invents prices, offers to send an enquiry.
- Consent (DPDP Act 2023) on every public form. Store IPs as hashes.

## Screen IDs (shorthand we use)
- **P1** home · **P2** category · **P3** product + configurator · **P4** importer landing (Stage 2) · **P5** gate modal · **P6** partners
- **E1** My day · **E2** buyer account (Stage 2)
- **kjsKoko 04–15:** login, dashboard, attendance, tasks, my board steps, admin dashboard, auto-assign, order boards, board detail, approvals + audit, team attendance, insights
- **A1–A7:** Stage 2 admin (sources, markets, discovered URLs, review, outreach approvals, campaigns, insights)

## People and contacts
- KJS contact: +91 97037 35666 · contact@kjsindia.com
- Manager / approver: _(name pending)_
- IT contact for the server: _(pending)_

## Session log (one line per working session)
- **23 Oct 2026 (5):** Next-phase items while Vineet was away: holidays table + calendar API (migration 0002), SEO (sitemap, robots, JSON-LD), CI workflow, unknown-locale 404 fix, Koko prompt hardened (no capacity promises). 52 tests green.
- **23 Oct 2026 (4):** Built the first working slice (backend + frontend + Koko on Groq + kjsindia.com assets). Tests and build green. Nothing committed.
- **23 Oct 2026 (3):** gh logged in; D3 = v2; R2 for files; demo video summarised (`research/video-summary.md`). It shows Stage 2 features → D18.
- **23 Oct 2026 (2):** Docker (WSL 2) + gh installed; repo cloned; D1, D2, D5, D6, D8 decided, D4/D7 updated; `trackEXP.md` created for the company.
- **23 Oct 2026:** Read all docs, wrote the requirements review and set up `/docs`. Found we're ~1–1.5 weeks behind plan v2; re-baselined in `track.md`.
