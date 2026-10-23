# Concepts behind this project

Short explanations of ideas the plan uses. Ask Claude to go deeper on any of them.

**Authentication vs authorisation.** Authentication asks *who are you* (login). Authorisation asks *what can you do* (roles). Every route checks both. A 401 means not logged in; a 403 means logged in but not allowed.

**RBAC (role-based access).** Permissions belong to roles (admin / manager / employee), and users have roles. We test both sides of each rule: allowed and forbidden.

**Audit log, append-only.** A record of who did what and when, which nobody can edit. Written in the *same transaction* as the change: if the change commits, the log commits; if one fails, both roll back. A DB trigger blocks UPDATE/DELETE.

**Transactions.** A group of DB writes that all succeed or all fail. "Move money from A to B" is the classic example.

**Job queue + worker + scheduler.** Slow or timed work (send an alert, run auto-assign) is put in a `jobs` table. Workers take jobs and run them. The scheduler adds jobs on a timetable. `FOR UPDATE SKIP LOCKED` lets several workers take *different* rows without blocking each other.

**Idempotency.** Doing something twice has the same effect as doing it once. Our alerts are idempotent because alert_log has a UNIQUE key, so a second insert fails and no duplicate message goes out.

**Retries with backoff.** If sending fails, wait 1 s, then 4 s, then 16 s… then give up and alert. This avoids hammering a provider that's down.

**Time.** Store UTC, show IST. A deadline is a moment in time, not a wall-clock string. Working-day maths skips Sundays and holidays, so write it as pure functions with lots of unit tests.

**Pure functions.** Same input → same output, no DB or clock inside. Easy to test. Our order-board maths (`split_steps`, `elapsed_pct`) should be pure, with the current time passed in.

**SEO basics.** Search engines read HTML. Server-render content, give each page a unique title/description, link pages, add a sitemap and robots.txt, add structured data (JSON-LD), and keep pages fast (Core Web Vitals: LCP < 2.5 s, CLS < 0.1, INP < 200 ms).

**ISR (incremental static regeneration).** Pages are built once and cached. When content changes, we revalidate just that page, so it's fast like static and fresh like dynamic.

**RAG (retrieval-augmented generation), how Koko works.** Split our content into chunks → turn each into a vector (embedding) → store in pgvector → for a question, find the closest chunks → give them to Claude with "answer only from this". It cuts down hallucinations and keeps answers on-brand.

**LLM guardrails & cost.** Cap messages per chat, tokens per reply and monthly spend. Never let the model state prices. Treat user text as data, never as instructions (prompt injection).

**Consent & privacy (DPDP Act 2023).** Collect only what's needed, show a clear notice, record consent time, allow erasure, and hash IPs.

**Feature flags.** A setting that turns a feature on/off without a deploy (e.g. WhatsApp alerts until Meta approves).

**Backups.** A backup you haven't restored isn't a backup. We do a restore drill.
