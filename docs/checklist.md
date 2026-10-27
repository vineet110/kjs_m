# Checklist: Phase 1 in 2 weeks

Phase 1 = every feature below, built and tested: **Mon 26 Oct → Sat 7 Nov 2026**.
After that: production (server, deployment, migrations), UAT, go-live **Fri 11 Dec**.
Tick `[x]` when a feature works end to end (backend + screen + tests). Source: `research/source/master-build-prompt.pdf`.

## Foundation
- [x] Repo, FastAPI backend, Next.js frontend, Docker test DB
- [x] Neon database (pooled for app, direct for migrations)
- [x] Health checks `/api/health` and `/api/health/ready`
- [x] One error shape `{code, message, details, request_id}`
- [x] CI workflow (tests, type check, build)
- [x] Config files `config/*.ini` with live reload (no restart)
- [x] `GET /api/public/config` (safe values for the frontend)
- [x] Logger: JSON lines, request ID on every line, secrets and emails masked
- [x] Frontend sends `X-Request-ID` to the backend
- [x] Background jobs loop (SLA checks, alerts, auto-assign)
- [x] Products: edit, hide/show, photos and spec sheets on the website
- [x] End-to-end test on real servers: 114 API checks + 38 real-Chrome checks, all passing (24 Oct, `scripts/e2e/`)

## Public website
- [x] Home
- [x] Category pages
- [x] Product pages
- [x] Capability pages
- [x] Contact + enquiry form
- [x] Koko chat with lead capture
- [x] SEO basics (metadata, sitemap, robots, JSON-LD)
- [x] Gated price sheet / spec PDF / sample / quote (short form once, then remembered)
- [x] Offers ticker (set by admin)
- [x] WhatsApp click-to-chat button
- [x] Partner programme page + application form
- [x] Private-label configurator (sends choices to sales; price shown once KJS gives price bands, I3)

## Employee portal
- [x] Login and sign-up request
- [x] Dashboard with my leads
- [x] Availability toggle ("receiving tasks" on/off)
- [x] Attendance: check in / out, week view, hours
- [x] Attendance: regularization request, holiday list
- [x] SLA timers on leads (respond 20 min, resolve 1 h, overdue shown)
- [x] My tasks (all sources, due dates, notes, add own task)
- [x] Notifications in the header (in-app)
- [x] Notifications by email (sent once SMTP details are in .env)
- [x] Auto-assigned batches (work through, mark done)
- [x] Order boards: my steps, tasks, files, progress vs plan
- [x] Profile (details, password, notification settings)

## Admin console
- [x] Dashboard with real numbers
- [x] Staff approval and permissions
- [x] Products
- [x] Audit log
- [x] Holidays page
- [x] All leads + SLA status + reassign
- [x] SLA escalation to admin when overdue
- [x] Team attendance + regularization approvals
- [x] Approvals inbox (sign-ups, regularizations, file delete requests)
- [x] File uploads (local folder in dev, Cloudflare R2 in production; R2 needs keys)
- [x] Order boards: code, deadline, steps by % or days, members, task templates, files
- [x] Order board alerts at 50 / 85 / 100%
- [x] Alerts page (rules and log)
- [x] Auto-assign settings (categories per employee, batch size, max per day, preview, run now)
- [x] Analytics (native charts from real data)
- [x] Website content and offers editor (+ partner applications)
- [x] Koko settings (facts, chat transcripts)
- [x] Settings page (view config and where each value comes from)

## Before UAT (needs you / KJS)
- [ ] Review the assumptions list (`backlog.md` section 3, A1–A66) and correct anything wrong
- [ ] Load real data: product list (I2), staff list + holidays (I4), Koko facts/FAQs (I5)
- [ ] Email: SMTP details in `.env` (A18)

## Production prep (no server needed): done 25 Oct, all in `deploy/`
- [x] Docker images for backend and frontend (small, not running as root)
- [x] nginx settings (security headers, real visitor IP A45, upload size, caching, gzip)
- [x] Cloudflare Tunnel settings (compose profile `tunnel` + steps in `deploy/README.md`)
- [x] Backup + restore scripts; restore drill passed on a local copy of the production stack
- [x] Deploy guide (set up, update, roll back): `deploy/README.md`
- [x] Production safety checks (refuses to start with default secret, http address, localhost origins)
- [x] Remove unused frontend packages (14 removed, 26 Oct)
- [x] Merge `kjs_v` into `main` (pull request #3, 26 Oct)

## Senior review (25 Oct): done
- [x] Independent review of security, backend logic, frontend and server setup (about 50 findings)
- [x] Every high and medium finding fixed, with tests (138 backend tests, all passing)
- [x] Security updates: FastAPI 0.129, Starlette 0.52, python-multipart 0.0.32, Node 22, nginx 1.28
- [x] Production stack re-tested: limited DB user, security headers + CSP (no browser errors), restore drill
- [x] Commit + push the review fixes (`ba19e69` on `kjs_v`, 26 Oct)
- [ ] Decide D20 (admins approving their own requests)
- [x] Upgrade to Next.js 16.4.3 + React 19 (B13, branch `next16`, 26 Oct; all e2e checks pass)
- [x] Next.js 16 merged into `main` (pull request #4, 27 Oct, CI green)

## Production-readiness review (27 Oct)
- [x] Three independent reviews: server behaviour, data correctness, security (no security blockers)
- [x] All 3 must-fix + 12 should-fix + the small ones fixed, 22 new tests (`test_prod_readiness.py`)
- [x] nginx container swap tested for real; 114 API + 38 Chrome end-to-end checks pass
- [ ] Review the new behaviour rules A67–A72 (backlog section 3)
- [x] Merged into `main` (pull request #5, 27 Oct, CI green)

## Production (needs the server / KJS)
- [ ] Neon in Singapore or company server Postgres
- [ ] Company server running the Docker images behind nginx + Cloudflare Tunnel
- [ ] Domain + DNS + email (SPF/DKIM)
- [ ] Cloudflare R2 bucket + keys (code ready: set STORAGE_DRIVER=r2 + R2_* in .env)
- [ ] WhatsApp Business verification + alerts
- [ ] Rotate Groq key and Neon password
- [ ] Backups + restore test
- [ ] Load real data from KJS (products, staff, holidays, Koko FAQs)
- [ ] UAT with KJS staff
- [ ] Go-live Fri 11 Dec

## Later (Stage 2, 2027)
- More languages (AR, ES, FR), importer landing pages, client login, buyer accounts, buyer intelligence, outreach

## Waiting on (does not block coding)
- D9: what "records" in an auto-assign batch are (building with: leads + imported Excel rows)
- D18: does the company expect Stage 2 features by 11 Dec?
- D19: public USD prices, or price sheet via form?
- I9: stick-pack fill range (0.9–3 g vs 18 g)
- From KJS: product list, price bands, employee list, holidays, Koko FAQs, order-board templates, brand files
