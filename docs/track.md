# Track: timeline and checklist

> Tick a box only when it's **built, tested and demoed**. Dates are Mon–Fri build days; **Saturday is catch-up/learning**.
> Re-baselined 23 Oct 2026 (plan v2 had Week 1 = 19–23 Oct; we start code Mon 26 Oct). Approved 23 Oct (D8). Simple company version: `trackEXP.md` (keep both in sync).

**Today's status:** 🟨 Phase 1 started early (23 Oct): first working slice built (login/approval/permissions, audit, catalogue, leads, Koko on Groq, public site). See "Built 23 Oct" below · **Go-live target:** Fri 11 Dec 2026 · **Latest acceptable:** Fri 18 Dec 2026

---

## Part 1: Checklist by date

### Phase 0: Understand & set up · Fri 23 – Sat 24 Oct
- [x] Read all docs; write requirements review (`research/requirements-review.md`)
- [x] Set up `/docs`: memory, goal, backlog, motivation, prompt, track, learning
- [x] Share GitHub repo URL → clone into `KJS_v1` (B1)
- [ ] Install Docker Desktop ✔, Node LTS ✔, uv ✔, gh ✔ · gh login ✔ · left: Python 3.12 (B2)
- [x] Decide D1–D8 (23 Oct; D7 postponed)
- [ ] Send inputs I1–I4 request + `trackEXP.md` to the manager
- [x] Review the starter repo against plan v2 → placeholders with fake numbers + 2 crash bugs; rebuilt as the first slice (23 Oct)
- [x] Summarise the WhatsApp video (I8) → `research/video-summary.md`

### Built 23 Oct (first working slice)
- Run it: README "Run it locally". Admin login = `FIRST_ADMIN_EMAIL` / `FIRST_ADMIN_PASSWORD` in `.env`.
- Proof: **52 backend tests green**; `tsc` + `next build` pass; pages, 404s, login redirect, proxy, cookie, robots, sitemap checked with curl; home page checked with a headless screenshot; Koko checked on 3 tricky questions.
- Dev tip: on this Windows PC `uvicorn --reload` did NOT pick up changes; restart the API after editing (kill the whole process tree).

### Phase 1: Foundation · Mon 26 – Sat 31 Oct
- [x] Monorepo skeleton: `frontend/` (Next.js 14 + Tailwind + next-intl, EN only) + `backend/` (FastAPI) + Neon Postgres; Docker `test-db` for tests (23 Oct). shadcn not added yet
- [x] `GET /api/health` + `/api/health/ready` (23 Oct)
- [ ] Makefile or scripts (`up`, `test`, `lint`, `migrate`, `seed`, `gen-api`): `make` not installed; README lists the commands for now
- [~] CI on GitHub Actions: `.github/workflows/ci.yml` runs pytest (Postgres service) + tsc + next build (23 Oct; runs once pushed). ruff, mypy, eslint, vitest need new dev packages (ask)
- [x] Users + sessions: sign-up (pending) → admin approves → login/logout → `/auth/me`; scrypt (stdlib instead of Argon2: no new dependency); httpOnly cookie; CSRF header (23 Oct)
- [ ] Email verification on sign-up (from the demo video; needs an email provider)
- [x] Roles (admin / employee) + permission keys as route dependencies + allowed/forbidden tests (23 Oct)
- [x] `audit_log` table + trigger that blocks UPDATE/DELETE (23 Oct, tested)
- [x] Working calendar: Mon–Sat, `holidays` table + admin API (`calendar.edit` permission), `add_working_days()` / `working_days_between()` with unit tests (23 Oct). Admin UI for holidays not yet
- [x] Next.js: locale layout, design tokens, shared sidebar config by permission, middleware guard for `/employee` `/admin` (23 Oct)
- **Done when:** fresh clone → `make up` → sign up, approve as admin, log in. CI green.

### Phase 2: Public website + content admin · Mon 2 – Sat 7 Nov
- [~] Catalogue: categories + products tables, 4 categories seeded, **no products until KJS sends the list (I2)**. product_i18n / offers / price_bands not yet
- [~] P1 home, P2 category, P3 product, 5 capability pages (real kjsindia.com text, images, videos), contact; server-rendered (23 Oct). Ticker waits for offers (I1); ISR tags later
- [~] Gate on actions (D3): `POST /public/leads` with consent, rate limit, honeypot (23 Oct). Visitor cookie + Turnstile not yet
- [~] SEO: metadata, `sitemap.xml` (from DB), `robots.txt`, JSON-LD Organization + Product (23 Oct). Breadcrumb JSON-LD + `SITE_URL` for prod later
- [~] Admin: add products (23 Oct). Edit/delete, categories, offers, revalidation not yet
- [ ] Staging online (company server or cloud VM) via Cloudflare Tunnel
- **Done when:** a visitor requests a price sheet on staging; the lead appears in admin; Lighthouse ≥ 90.
- 🔒 **Fri 6 Nov: goal.md locked**

### Phase 3: Employee portal core · Mon 9 – Sat 14 Nov
- [ ] Attendance: check-in/out (server time), multiple sessions, weekly view, nightly auto-close, regularization request → approval
- [ ] Availability toggle + availability_log
- [ ] Tasks: CRUD, sources, statuses, outcome, **notes**, own tasks
- [ ] Dashboard stats from one SQL view (employee + admin totals agree)
- [ ] Leads with SLA timers (E1 My day) + `sla_watch` job; job queue + worker + scheduler running
- [ ] Admin: team & attendance (day/week/month) + Excel export
- **Done when:** both of us use the portal for a full working day on staging.
- ⚠️ Diwali falls around this week. Confirm holidays (I4) and adjust.

### Phase 4: Auto-assign + Koko v1 · Mon 16 – Sat 21 Nov
- [ ] Employee ↔ category mapping, per-employee batch size
- [ ] Auto-assign settings (duration modes, days, interval, batch size, max/day), preview (dry run), run now, history, unassigned pool + admin alert
- [ ] Batch job every 15 min, Mon–Sat, working hours, `SKIP LOCKED`
- [~] Koko v0 (23 Oct): Groq; answers only from `backend/app/knowledge/kjs_facts.md` + catalogue; replies in the visitor's language; no prices; rate limit; enquiry form inside chat → lead with AI summary. Embeddings / spend cap later
- [ ] Model test for D4 (30 questions)
- **Done when:** a scheduled batch reaches only the right-category, available employee; Koko creates a lead.

### Phase 5: Order boards · Mon 23 – Sat 28 Nov
- [ ] Create board (ABC117 ID), requirement files, 5 steps from template, split by % or days over working days
- [ ] Members per step (add / soft-remove), step task templates + checklist, mark step complete → next step starts
- [ ] Files: upload (sha256, MIME, size, versions); employee view (only their boards)
- [ ] History on the board (from audit log)
- **Done when:** a board runs through all 5 steps with correct dates in a test with a frozen clock.

### Phase 6: Approvals, alerts, insights · Mon 30 Nov – Sat 5 Dec
- [ ] Delete requests → admin approve/reject → soft delete; approvals screen (deletes, regularization, new staff)
- [ ] Audit log UI: filters + export
- [ ] Deadline alerts: `check_deadlines` every 15 min, 50/85/100 %, unique alert_log, retries; email templates
- [ ] WhatsApp sending behind a flag (if Meta approved; templates submitted)
- [ ] Insights: 4–5 native charts (board heatmap, leads by category, sources, team)
- [ ] Hardening: security checklist, Sentry, UptimeRobot, backups + **restore drill**
- **Done when:** each alert arrives exactly once; restore drill passes.

### Phase 7: UAT + go-live · Mon 7 – Fri 11 Dec
- [ ] Playwright E2E for the 3 main journeys green
- [ ] UAT scripts for visitor / employee / admin; client runs them
- [ ] Fix P1/P2 bugs; production deploy; seed real data; user guides (1 page per role)
- [ ] **Go-live Fri 11 Dec** 🚀

### Buffer / hypercare · Mon 14 – Fri 18 Dec
- [ ] Slipped items, live bug fixes, first-week support, retrospective

### Stage 2 (2027): only after Stage 1 is live
- [ ] Jan: sources registry, file inbox, Comtrade, market scores
- [ ] Feb: Claude extraction, review queue, IndiaMART, Hunter, scoring
- [ ] Mar: mailer, sequences, approvals, country rules
- [ ] Apr–Jun: P4 landing pages, samples, quotes, partner portal

---

## Part 2: How we implement each phase (end-to-end)

### The loop for every feature (same every time)
1. **Pick** one checklist line. Write it as a task with the prompt template in `prompt.md`.
2. **Plan** with Claude in plan mode: files, tables, endpoints, components, tests. **No code yet.** Read the plan and ask "why?" about anything unclear.
3. **Branch:** `feat/<phase>-<short-name>`.
4. **Build vertically:** migration → model → service (business rule + audit) → router (role dependency) → tests → regenerate API client → UI.
5. **Prove it:** run the tests, click through it, try the forbidden role.
6. **PR:** small (under ~400 lines); the other person reviews; CI green; merge.
7. **Write it down:** tick `track.md`, add any decision to `memory.md`, any blocker to `backlog.md`, one learning to `learning/learning-log.md`.

### Phase-by-phase design notes

**Phase 1: Foundation.** Everything later depends on it, so get it boringly right.
- *Order:* compose + health → CI → users/sessions → roles → audit → calendar → web shell.
- *Key ideas:* config only from env (`.env.example` lists every key). One error shape `{code, message, details, request_id}`. structlog with request IDs. Alembic migration per change.
- *Watch out:* don't build auth in Next.js. FastAPI owns sessions; Next.js middleware only checks that the cookie exists and redirects.

**Phase 2: Public site.** First thing the client sees, so it's our credibility.
- Public pages are **server components**. They fetch from `http://api:8000` with a service token. No client fetching for content.
- The gate covers **actions**, not pages (unless D3 says otherwise), so everything stays indexable.
- Admin edit → FastAPI calls Next.js `/api/revalidate` with a secret + tag.

**Phase 3: Portal core.** The daily tool for staff.
- One open attendance session per user (partial unique index). A night shift is credited to its start date.
- Dashboard numbers come from **one SQL view**, so employee and admin totals always agree.
- Build the **job queue + worker + scheduler** here (first used by auto-close and `sla_watch`). Phases 4 and 6 reuse it.

**Phase 4: Auto-assign + Koko.**
- One picker function used by: the scheduled run, "Run now", preview (dry run) and event-based lead assignment.
- `FOR UPDATE SKIP LOCKED` means two workers never grab the same records.
- Koko: retrieve top chunks (pgvector) → system prompt "answer only from context, reply in {lang}, never invent prices" → stream. Message cap, token cap, monthly spend cap.

**Phase 5: Order boards.**
- Pure functions first, with unit tests: `working_days`, `split_steps`, `elapsed_pct`. The UI comes last.
- A board is a folder: steps, members, files, history all hang off `order_boards.id`.

**Phase 6: Approvals, alerts, insights.**
- Alerts are idempotent because of `UNIQUE(step_id, threshold_pct, channel, recipient)` on alert_log, so a job that runs twice still sends once.
- Test with a frozen clock (freezegun) at 49 %, 50 %, 84 %, 85 %, 100 %.
- Charts read from `analytics.*` SQL views, so Superset can use the same views later.

**Phase 7: UAT + go-live.**
- Deploy = tag → build images → `deploy.sh` (migrate, restart). Keep the last 3 images for rollback.
- Go-live checklist: env secrets set, backups running, restore tested, Sentry + uptime on, admin account created, real data seeded, robots allow public pages.

### Who does what (start; rotate after go-live)
| Area | Vineet | Teammate |
|---|---|---|
| Phase 1 | Compose, FastAPI, DB, auth, CI | Next.js shell, design tokens, layouts, sidebar |
| Phase 2 | Catalogue + gate API, revalidation, staging | P1–P3 pages, gate modal, admin CRUD screens |
| Phase 3 | Attendance, tasks, SLA, job queue | Portal screens, dashboard, team view |
| Phase 4 | Picker + scheduler, Koko backend | Auto-assign screen, Koko widget |
| Phase 5 | Board maths, files, members | Board list/detail, step view, upload UI |
| Phase 6 | Alerts, approvals API, backups | Approvals + audit UI, charts |
| Phase 7 | Deploy, fixes | E2E, UAT scripts, user guides |
Both: review each other's PRs and explain your PR to the other person in 2 minutes.
