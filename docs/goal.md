# Goal

> **Status: DRAFT.** We update this freely for 1–2 weeks as answers come in.
> **Lock date: Fri 6 Nov 2026.** After that, changes go through `backlog.md` ("Release 2 unless we swap it for X").

## Mission
Give KJS India one platform where **importers find and contact them easily**, **employees run their day** (attendance, tasks, leads, orders), and **the admin sees and controls everything**, live by **11 Dec 2026**.

## Stage 1 outcomes (what "done" means on go-live day)
1. **A visitor** can browse products in English on a fast, SEO-ready site, request a price sheet / sample / quote through one short form, and chat with Koko. Every request becomes a **lead with an owner and an SLA timer**.
2. **An employee** can log in, check in/out, switch Available on/off, receive work in batches for their categories, keep notes on tasks, close leads as Successful/Lost, and work on order-board steps they belong to.
3. **The admin** can approve staff, set auto-assign rules, create order boards that track 5 steps against working-day deadlines with alerts at 50/85/100 %, approve deletions and regularizations, read an append-only audit log, see the team's attendance, and view the key charts.
4. **It runs safely:** HTTPS through Cloudflare, nightly off-site backups with a tested restore, error tracking, uptime alerts, and tests in CI.

## Measurable success criteria
- [ ] Lighthouse ≥ 90 (performance, SEO, accessibility) on home, category and product pages
- [ ] Every API endpoint has an allowed + forbidden role test; CI is green on `main`
- [ ] E2E passes: visitor → gate → lead with SLA; employee day; board → 85 % alert → delete approval
- [ ] Each alert fires exactly once (proved by a test with a frozen clock)
- [ ] Restore drill done: backup → fresh machine → app works
- [ ] Client UAT sign-off

## In scope (Stage 1)
P1, P2, P3 (+ configurator if price bands arrive), P5 gate, Koko v1, offers ticker, SEO basics · login/sign-up/approval · attendance + regularization · availability · tasks + notes · dashboard stats · leads with SLA (E1) · auto-assign batches · order boards + step templates + files + delete approvals · deadline alerts (email; WhatsApp when approved) · approvals + audit log · team attendance + Excel export · website content admin · insights (native charts).

## Not in scope (Stage 1)
- Buyer Intelligence & Outreach (A1–A6, E2), P4 landing pages, samples/quotes workflow, partner portal → **Stage 2 (2027)**
- Superset → after go-live (native charts first)
- Languages other than English → after go-live unless management decides otherwise (i18n plumbing is built from day 1)
- Payments, e-commerce checkout (KJS sells B2B by quote)

## Our personal goals (Vineet + teammate)
- By go-live, each of us can explain **every** module: data model, API, UI, tests.
- Each of us can run the whole stack locally from a clean machine using only the README.
- We keep a daily learning log (`learning/learning-log.md`).
- We ship in small PRs that the other person reviews.

## Change history
- 23 Oct 2026: first draft from plan v2 + requirements review.
