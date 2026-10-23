# Requirements Review: KJS India Platform

> End-to-end review of every planning document we have, written 23 Oct 2026 before any code.
> Read this once fully. After that, `docs/memory.md` is the short version.

---

## 1. What we are building (one paragraph)

KJS India is a **co-manufacturer and private-label maker** of coffee, tea, health drinks and confectionery (two factories near Hyderabad, FSSC / ISO 9001 / ISO 14001). It wants **one platform with three faces**:

1. **Public website**: SEO-friendly, multilingual. It helps importers find products, request price sheets, samples and quotes, and chat with **Koko**, the AI assistant.
2. **Employee portal**: attendance, an availability toggle, tasks (auto-assigned in batches), leads with SLA timers, and the order-board steps an employee is part of.
3. **Admin console**: controls everything, including auto-assign rules, **Order Boards** (5-step order tracking with deadline alerts), approvals, an audit log, website content and analytics.

Later (2027, Stage 2), a **Buyer Intelligence & Outreach** engine. It finds importers worldwide from data sources, de-duplicates and scores them with Claude, and sends human-approved email sequences.

---

## 2. Source documents and which one wins

| # | File (in `docs/research/source/`) | Date | Status |
|---|---|---|---|
| 1 | `Implementation_Plan_KJS_India.pdf` (plan v1.0) | 14 Oct | **Superseded** by v2. Still useful for the detailed module logic (attendance, order-board maths, alerts), which v2 summarises. |
| 2 | `Wireframes_v2_KJS_India.html` / `wireframe_kjs2.pdf` | 14 Oct | **Superseded** by kjsKoko + ui v3 |
| 3 | `kjsKoko.html`: 15 screens (01–15) | 14 Oct | **Current** for portal/admin screens: attendance, tasks, auto-assign, order boards, approvals, team, insights |
| 4 | `implementation_plan_v2.pdf` | 15 Oct | **Current master plan** ("build-ready") |
| 5 | `ui_designs_v3.html`: 15 screens (P1–P6, E1–E2, A1–A7) | 15 Oct | **Current** for public site, My day, buyer intelligence and outreach |
| 6 | `research_01_probe_results.json` | 15 Oct | Probe of 26 data sources for Stage 2 (status codes, robots.txt) |
| 7 | WhatsApp video (10 MB, not copied) | 15 Oct | Not reviewed (I can't watch video). v3 mentions a "demo video". **Vineet: please summarise it in 3–5 lines.** |

**Rule:** if two documents disagree, **plan v2 + ui v3 + kjsKoko** win over v1 / wireframes v2, unless management says otherwise.

### Referenced but missing (we don't have these)
- `research_01.pdf` (source feasibility, section 4A, trials T1–T10)
- `research_01_implementation_plan.pdf` (Claude batch/web-search code samples, section 6)
- "MVP Engineering Roadmap v1.0" and "Hi-fi Wireframes v1.0"
- "The notes" (client notes that v3 quotes: "distinctive and attractive", "commission agents"…)

These are logged in `backlog.md`. Only the research_01 files matter, and only for Stage 2.

---

## 3. Scope: Stage 1 (go-live target Fri 11 Dec 2026)

### A. Public website (Next.js, server-rendered for SEO)
| ID | Screen | Key behaviour |
|---|---|---|
| P1 | Home | Offers ticker (scrolls, pauses on hover, admin-managed), buyer finder (product + country → landing page), best sellers, private-label band, categories, markets, Koko button |
| P2 | Category page | Open + indexable, unique intro, filters (format, certification, private label) |
| P3 | Product page | Public specs; 4 **gated actions** (price sheet, spec PDF, sample, quote); private-label configurator with indicative price band |
| P5 | Gate modal | Name + (email or phone) + country + consent text by country → visitor cookie (1 yr) + lead with SLA |
| P6 | Partners | Agents/forwarders/distributors apply (Stage 1 = static page + form) |
| — | Koko | Chat widget on every page; RAG over KJS content; replies in visitor's language; creates a lead ("Send enquiry") |
| P4 | Importer landing pages | Programmatic SEO pages per country × product. **Stage 2** (v2 schedules them for Mar–Apr 2027) |

### B. Employee portal (EN only)
| ID | Screen | Key behaviour |
|---|---|---|
| 04 | Login | Approved staff only; sign-up request → admin approves |
| E1 / 05 | My day / dashboard | Stats (total, completed, pending, ongoing queries, closed), Available toggle, live leads with SLA (respond 20 min / resolve 60 min), record batch, own tasks |
| 06 | Attendance | Zoho-style check-in/out, multiple sessions, shift 09:30–18:30, Sun off, auto-close, regularization |
| 07 | My tasks | Sources: auto batch, Koko lead, website form, order board, self-added; **notes with timestamps**; outcome Successful / Lost |
| 08 | My order board steps | Only boards they're a member of; step checklist from a template; add colleague; upload; request delete |

### C. Admin console
| ID | Screen | Key behaviour |
|---|---|---|
| 09 | Dashboard | Same stats summed over everyone + checked-in, available, boards at risk, new leads |
| 10 | Auto task assign | Duration (weekly / monthly / until off / custom), Mon–Sat, check every 15 min, batch size (20/30/50/custom, per employee), max batches/day, employee ↔ category mapping, preview, run now, history |
| 11–12 | Order boards | ID `ABC117-<1–6 digits>` unique; requirement files; 5 steps (Procurement 25 / Packaging 19 / Production 30 / Placement 16 / Track 10 %); split by % or days over **working days**; members per step; countdowns; alerts at 50/85/100 % by mail + WhatsApp, **once each**; history |
| 13 | Approvals + audit log | File deletes, regularization, new staff; append-only audit log (DB trigger), filters, export |
| 14 | Team & attendance | Day/week/month, late/absent, export to Excel |
| 15 / A7 | Insights | Superset embedded (order-board heatmap, leads by category, sources, team) |
| — | Website content | Offers, products, categories, price bands, Koko knowledge & guardrails, revalidation |

### Stage 2 (Jan–Jun 2027, gated): out of scope for now
Sources & scheduler (A1), market selector from UN Comtrade (A2), AI URL discovery (A3), duplicate review queue (A4), outreach approvals (A5), campaigns (A6), buyer account (E2), P4 landing pages, samples, quotes, partner portal. **We don't design or build any of this until Stage 1 is live.** We only avoid decisions that would block it later.

---

## 4. Architecture (from plan v2)

```
Browser → Cloudflare (DNS/TLS/WAF) → Tunnel → nginx (company server)
   /           → web  (Next.js, App Router, TS)        ← public SSG/ISR, portal & admin client-side
   /api/*      → api  (FastAPI, Python 3.12)            ← auth, roles, business rules, audit
   /superset/* → superset (read-only DB role)
api ↔ postgres 16 (+ pgvector, pg_trgm; also the job queue)
worker (polls jobs table, FOR UPDATE SKIP LOCKED) + scheduler (APScheduler)
External: Anthropic API · Resend/Brevo · WhatsApp Cloud API · Cloudflare
```

Monorepo layout: `apps/web` (Next.js), `services/api` (FastAPI, `modules/<name>/{router,schemas,models,service,tests}`), `deploy/`, `docs/`. Full tree in plan v2 §4.

**Why this is reasonable:** a single Postgres handles data, queue and vectors (no Redis/Celery). Same-origin `/api` means session cookies work without CORS. The typed client is generated from OpenAPI, so we never hand-write API types.

**What makes it hard for two freshers:** two languages (TS + Python), two frameworks, Docker, Cloudflare Tunnel, Superset, WhatsApp approval, an LLM, and SEO, all at once. Our answer is to **learn just in time, one module end to end** (see `docs/learning/`).

---

## 5. Conflicts between documents (need a decision)

| # | Topic | Older docs say | Plan v2 / v3 says | My recommendation |
|---|---|---|---|---|
| C1 | Frontend stack | React + Vite | **Next.js** (SEO) | Next.js. Approval was due 16 Oct; confirm it was given |
| C2 | Public languages | EN + Hindi (Koko demo is in Hinglish) | **EN, AR, ES, FR** (RTL for Arabic) | Ask management. Start with **EN only + i18n plumbing**, then add languages as files. RTL needs logical CSS from day 1 |
| C3 | Category gate | Form **before** opening a category | Catalogue open; gate only **actions** (price, spec, sample, quote) | v2 (better for SEO). Management decision was due 23 Oct (today) |
| C4 | Koko model | Haiku-class, USD 20–50/month | `claude-opus-5-5`, ~USD 270–330/month (incl. Stage 2 batch work) | For Stage 1 Koko, test **claude-haiku-5-5** vs Opus 5.5 on ~30 real questions and pick the cheapest that passes |
| C5 | Domain | `shop.kjsindia.com` | `www.kjsindia.com` (the **existing corporate site**) | Big question: do we replace the current corporate site? Until answered, build for a subdomain |
| C6 | Roles | admin, employee | admin, **manager**, employee, partner, customer | Stage 1: admin, manager, employee. Leave partner/customer for Stage 2 (keep the role column open) |
| C7 | Auto-assign model | One daily run at 09:00, single tasks | **Batches**, checked every 15 min, next batch when current one is done | v2 / kjsKoko (batches) |
| C8 | Insights | Superset | Superset (v1 also lists a Recharts fallback) | Stage 1: **native charts (Recharts)** for the 4–5 key charts. Superset after go-live. Saves ~3 days |

---

## 6. Open questions (from the plans, still unanswered)

1. Auto-assign: must an employee be **checked in**, or only **Available**?
2. Gate leads: OTP verification at launch, or validation + Turnstile only?
3. Late order-board step: keep the final deadline (compress later steps) or move it?
4. Payroll export format for attendance?
5. WhatsApp alerts to personal numbers (opt-in), or email only?
6. What are the "records" in auto-assign batches during **Stage 1**? (In v2 they're Stage 2 `companies`.) Before Stage 2 they could be website/Koko leads plus imported Excel lists. **This needs an answer before Phase 4.**
7. Who is the "manager" role in practice, and what can they do that an employee can't?
8. Company server: does it exist, who is IT, and when can we get SSH (Tailscale) access?
9. Is the 11 Dec go-live a promise to the client, or an internal target?

---

## 7. Where we actually are (23 Oct 2026)

| Plan v2 week | Planned | Actual |
|---|---|---|
| Wk 0 (15–16 Oct) | Docs frozen, repo, CLAUDE.md, accounts, WhatsApp verification started | Docs exist. **Repo partly started on GitHub (URL needed). Accounts unknown** |
| Wk 1 (19–23 Oct) | FastAPI core, auth, roles, audit, Next.js + next-intl, staging | **Not started** |

**We are about 1–1.5 weeks behind the v2 plan.** That's not a disaster, but we have to admit it now, not in December. `track.md` contains a re-baselined plan that still targets 11 Dec, with a buffer week (14–18 Dec) and three scope cuts. Management should approve it.

---

## 8. Risks (top 8)

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Timeline: two freshers, large scope, already behind | High | Go-live slips | Re-baseline now; cut Superset, P4, P6-portal; Saturday catch-up; 14–18 Dec buffer |
| Learning curve (Next.js + FastAPI + Docker at once) | High | Slow first 2 weeks | Phase 1 is deliberately "boring foundation"; learning files; Claude explains every step |
| Company server / IT not ready | Medium | No staging | Small cloud VM with the same Docker Compose (half-day move later) |
| WhatsApp Business verification slow | High | Alerts late | Ship email alerts first; WhatsApp behind a feature flag |
| Client inputs late (products, brand, employees) | High | Placeholder UI | Build with seed data; list inputs with due dates in `backlog.md` |
| Scope creep ("can we also…") | High | Slips | Every new ask → `backlog.md` → "Release 2 unless we swap it for X" |
| Koko gives wrong answers | Medium | Trust | Answer only from retrieved content, never quote prices, "I'll connect you with sales" fallback |
| Code we don't understand ends up in production | Medium | Bugs we can't fix | Rule: **never commit code you can't explain**. Small PRs, the other fresher reviews, tests on every rule |

---

## 9. Recommendations (what I'd do)

1. **Lock Stage 1 scope this week** (goal.md). Treat Stage 2 as a separate project.
2. **Get decisions C2, C3, C5, Q6 and Q9 from management by Wed 28 Oct.** These change what we build in Phases 2–4.
3. **Start Monday with the monorepo skeleton.** That's prompt #1 in plan v2 §19.
4. **Split work by layer at first** (Vineet: FastAPI + DB + infra; teammate: Next.js UI). Each reviews the other's PRs. Rotate after go-live so both of you learn both sides.
5. **Every phase ends with a demo** and tests in CI. No "we'll test it at the end".
6. **Email before WhatsApp, native charts before Superset, EN before other languages.**
