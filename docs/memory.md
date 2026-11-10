# Memory: KJS India Platform

The project's long-term memory: short facts, rules and decisions.

Anyone joining (person or AI) reads this first.

Last updated: 2 Nov 2026.

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
   ii.   Tests: 138 backend tests, plus end-to-end 114 API checks and 46 real-browser checks (browser count as of 2 Nov).
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

10. Whole-repo code review and its fix list (29 Oct): `codeReview.md`

11. Tools we use now, and ideas for later (none approved yet): `tools.md`



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

   i.    PostgreSQL. Neon (free, cloud) during development, in Singapore since 28 Oct (was US). Company server later.
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

16. 24 Oct. (REPLACED: `docs/` is committed now, see `prompt.md` section 4 rule 3) `docs/` is not committed to
    git. It lives only on this PC.

17. 24 Oct. Every guess we make goes into `backlog.md` section 3, so it can be checked later.

18. 24 Oct. Commits and pull requests never mention the AI assistant.

19. 27 Oct. Products come from the KJS catalogue PDF (seeded by `app/seed_catalogue.py`), pictures cut from
    the PDF until KJS sends originals. Home page laid out like a B2B marketplace (Alibaba-style layout,
    KJS branding).

20. 2 Nov. "Broker" is shown as "Referral partner"; the saved value stays `broker` (no migration). Labels in
    `frontend/src/lib/partners.ts` and `content_service.PARTNER_LABELS`, kept equal by a test.

21. 2 Nov. Best seller stays a tick box per product. Offer % is optional per product, 1 to 90, shown as
    "Up to X% OFF" (migration 0012). Both show nothing until staff set them (KJS approval: backlog R31, R32).

22. 2 Nov. Phone and country pickers (Nishita): flags as SVG files in `public/flags` (flag-icons 7.2.3, MIT,
    no package), India first and the last pick remembered on the device, country from the list only, the
    phone code follows the country, a light phone check (optional +, 0-9, spaces, - ( ), 6 to 15 digits)
    in one `Phone` type (`schemas/common.py`). Phones and countries are saved as text, like before.

23. 3 Nov. Staff portal colours: charcoal (`ink`) + gold on a warm page (`paper`), from the logo. Green only
    where it means "good".

24. 3 Nov. Product edits (PATCH) change only the fields sent (`ProductPatchIn`, `exclude_unset`).

25. 5 Nov. Public site: headings in Plus Jakarta Sans (`next/font/google`, no new package), only inside the
    `site-public` class, so the staff portal is unchanged. Gold / charcoal replace forest green on the home page,
    the bottom enquiry box and Koko. Tea is hidden on the home and products pages (`HIDDEN_CATEGORIES` in
    `lib/catalogue.ts`); it stays in the database and `/categories/tea` still opens.

26. 5 Nov. "Let's connect" WhatsApp popup on public pages only: up to 3 per visit, 8 s, 30 s and 60 s apart (fixed,
    as asked), each wait starting when the last popup is gone. Stops once someone clicks WhatsApp or asks for a
    quote; never over the enquiry form, quick view or open Koko chat. State in `sessionStorage` (`kjs-connect`).
    Switch: `connect_popup` in `config/features.ini` (shown unless `false`).

27. 7 Nov. Contacts = leads of one person, worked out on each load (not saved): two leads are one person when
    they share the full phone number (every digit, country code included) OR the email, also through a third
    lead (`group_contacts` in `lead_service.py`). A number saved without a code doesn't join the same number
    with +91.

28. 6–7 Nov. User Creation Form: accounts made by an admin are active at once, with a one-time password shown
    once. Only an admin gives the admin role or edits accounts; only an admin changes an admin's photo.
    "Reporting to" is optional (empty = top of the chain) and can't make a loop.

29. 7 Nov. Task due times are typed and read in IST (`+05:30`), whatever the computer's time zone.

30. 7 Nov. Attendance page uses only the portal sidebar: the four views are in the ••• menu, Leave Applications /
    Regularization / Reports / Shift Schedule and "+ Apply Leave" in a white bar at the bottom.

31. 7 Nov. Background jobs: each service registers its own with `@job`, and `main.py` imports those services.
    `app/jobs/__init__.py` imports nothing (importing them there made a loop that broke `python -m app.seed`).

32. 6 Nov. Website pictures (`images/`, `flags/`) are served from the PUBLIC R2 bucket `kjs-site-assets`, set by
    `NEXT_PUBLIC_ASSET_BASE` (frontend build) = `ASSET_BASE_URL` (`deploy/.env`); empty = `public/` as before.
    `asset(path)` in `lib/assets.ts` adds the address. Staff and order board files stay in the PRIVATE
    `kjs-prod-files` and open through the app with 5-minute signed links. Replaces backlog R44 iv.

33. 7 Nov. Order board people: the owner is whoever created the board. The owner or `boards.manage` adds and
    removes people, changes a step's people and its head (★), finishes the board and approves file deletes.
    Everyone on the board sees it, ticks checklists and uploads files. Only a step's people, the owner or
    `boards.manage` mark that step done. Every step keeps at least 1 person. Removing someone ends their access
    only: files and history stay, their open tasks on the board are closed with a note (never deleted).

34. 7 Nov. File deletes: an owner type can name its own approvers (`register_owner(..., approvers=)`); for a
    board, its owner. `files.approve` still can. Nobody approves their own delete request.

35. 7 Nov. File preview: `GET /files/{id}/view` sends the file through our API (never an R2 link), inline,
    never cached, nosniff. A real PDF may only be framed by our pages; everything else is sandboxed. Excel and
    CSV with `xlsx` 0.20.3 from cdn.sheetjs.com (npm's 0.18.5 has known bugs), Word with `mammoth`; both load
    only when such a file is opened. Limits: 10 MB, 1000 rows, 50 columns.

36. 7 Nov. A board's History tab is read from the audit log (nobody can edit it). Everyone on the board reads it.

37. 7 Nov. Editing a board's plan (dates, split, steps): anyone on the board while it is unlocked; only the
    owner or `boards.manage` when the owner has locked it. Only steps that haven't started can be moved or
    removed; a removed step's checklist is deleted (History keeps a copy) and its tasks closed with a note.
    Only the owner brings new people onto the board, also through a new step. An older draft is refused (409).

38. 8 Nov. Migrations: before writing one, take the next free number and tell the other person at once. For a
    manual `alembic` command, set BOTH `DATABASE_URL` and `MIGRATION_DATABASE_URL`, because `.env` points the
    second at Neon and Alembic prefers it (kb: "Alembic / migration"). Tests already override both.

39. 9 Nov. Off-site backup: the R2 bucket `kjs-bkp-prod`, with its OWN token in `deploy/.env.backup` (never in
    `.env`, so the running app never has it). Every night `backup.sh` sends the database backup encrypted
    (`openssl`, AES-256, `BACKUP_PASSPHRASE`) and copies new uploads (`app/backup_r2.py`). Uploads that
    disappear or are rewritten, and the database backups, stay 30 days (Vineet's decision: the live app
    deletes at once, the backups keep 30 days). Backups taken by a restore or a deploy never go off-site.

40. 9 Nov. Attendance hours always come from the punches. Approving a correction moves the day's first
    check-in (and last check-out, if given); breaks stay breaks. Check-in and check-out lock the day's row
    (a double tap stores one punch).

41. 9 Nov. The running API never holds the database superuser password, the migration address or the tunnel
    token: `docker-compose.prod.yml` blanks them for the backend. `deploy.sh` and `restore.sh` pass
    `MIGRATION_DATABASE_URL` to the migration step only; in production Alembic refuses without it.

42. 9 Nov. The health check is `/healthz` (Next.js -> API -> database, no cache), not `/` (the home page's
    `loading.tsx` answers 200 even when the page fails). `deploy.sh` and the Docker HEALTHCHECK use it.

43. 9 Nov. Rate limits count a whole IPv6 /64 as one visitor. The per-network login limit counts only wrong
    passwords (100 per 15 min); sign-ups 30 per network per hour (`config/app.ini`). A network where the
    person logged in during the last 30 days can't be locked by strangers: every login writes an
    `auth.login_ok` audit row (hashed network), and the check reads it.

44. 9 Nov. A feature switched off in `config/features.ini` also refuses its API (404 `feature_off`).
    Disabling an account gives its open batch's unfinished buyers back (batch "returned"). The offer and
    user edits change only the fields sent. Screens (PR #41): reads give up after 20 s; saves wait 90 s and
    say "may have been saved, refresh to check" when there is no clear answer.

45. 9 Nov. Koko sends the AI only the products that matter, never the whole catalogue (PR #50): the viewed
    product, then products the visitor's last 3 messages name, then the page's category; max 8, prompt about
    2,000 tokens (a test guards the size). On product and category pages the first reply carries a catalogue
    card from the database (backlog A92). Cards, not a PDF per category. Groq's free tier: backlog R52.

46. 10 Nov. Config values changed on purpose (Nishita, PR #56): SLA escalation grace 10 -> 30 minutes, one
    batch a day per person (was 3), background jobs off (`jobs_enabled = false`: no SLA alerts, board alerts
    or auto-assign until switched back on). Tests that depend on a config value pin it themselves (env
    `KJS__SECTION__KEY` + `ini.reload_now()`), so tuning `config/` never breaks CI.



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
   viii. `alembic/versions/`: migrations 0001 to 0018. Next free number: 0019. Neon is at 0018 (9 Nov).


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

7. Deleting a file needs approval (decision 34). Order board rules: decisions 33 and 37.

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

1. 10 Nov 2026 (config folder walkthrough, Nishita, PR #56 merged 10 Nov)

   i.    Every `config/*.ini` file explained; clearer comments in `sla.ini`, `features.ini`, `logging.ini`,
         `koko.ini`. Values changed on purpose: decision 46.
   ii.   CI failed once: `test_escalation_once_per_breach` read the live `sla.ini` and expected a 10-minute
         grace. Fixed by pinning the numbers in the test, not by changing the config back.
   iii.  Found: `storage.ini` `allowed_types` can only remove file types (backlog R53).


2. 9 Nov 2026 (go-live safety, Vineet PRs #42–#45, Nishita PR #41, all merged 9 Nov)

   i.    A whole-repo audit before real data: no business row is ever hard-deleted, every migration only adds;
         but uploads in R2 had no backup and the database backup sat on the same disk (decision 39).
   ii.   Fixed: off-site backup, attendance hours, double taps, failed uploads (#42); secrets out of the API,
         `/healthz`, a failed restore keeps the app stopped (#43); IPv6, office and lockout limits (#44); lost
         emails, switched-off features, a disabled person's batch, partial edits (#45); error pages, time
         limits, no endless "Loading…", typed text kept on a failed save (#41). Code review CR2–CR11 done.
   iii.  Each PR got a code review; findings were checked one by one and only the real ones fixed.
   iv.   Not run after the last changes: the full `test-restore.sh` drill (Vineet: run it on the server).
         The first real off-site copy worked (2 test files to `kjs-bkp-prod`). Follow-ups: backlog R50.
   v.    Nishita, PRs #46 and #49: order boards checked in Chrome (R49 i); `scripts/e2e` now covers lead
         management, leave and shifts, and order boards; no app bugs found. e2e runs use `STORAGE_DRIVER=local`
         (a local `.env` with `r2` had sent test uploads to the real bucket: R50 iii). Login suite unsteady: R51.
   vi.   Nishita, PR #50: Koko answered every message "Sorry, I can't answer" (all 72 products went to Groq,
         over the free 8,000 tokens a minute). Now only the products that matter, plus catalogue cards
         (decision 45). The review's 10 findings were checked against the code, all real, all fixed.


3. 8–9 Nov 2026 (order boards review fixes, Vineet, PRs #35–#39 merged)

   i.    A code review of each PR found issues; all fixed on each PR's own branch and merged down the chain.
         Owner gets step and time alerts; double clicks ignored; CSV shows ₹ and Hindi; big sheets can't freeze
         the tab; Esc works in full screen; an odd audit row can't break History; only the owner brings new
         people onto a board; an older plan draft can't undo a newer change.
   ii.   New migration 0017 (audit_log index for History); the plan lock moved to 0018.
   iii.  Mistake: a manual `alembic` check ran on Neon (only `DATABASE_URL` was set, see decision 38). Only the
         two new migrations went up and down; no data lost. Neon was put back to 0016, then migrated to 0018 after
         the merge. Backend 241, unit 42 pass.


4. 7 Nov 2026 (order boards overhaul, Vineet, PRs #35–#39)

   i.    #35 people, owner, step heads (migration 0016: `board_people`, `board_members.is_head`); #36 screens
         (summary card, timeline, tabs Steps / Files / People, board list filters); #37 file preview (PDF, images,
         Excel, CSV, Word, text; side panel or full screen); #38 History tab; #39 edit the plan + owner's lock
         (migration 0018 `order_boards.plan_locked`). Decisions 33–37.
   ii.   Checked in Chrome on a local copy of the database (not Neon). Not checked: phone width, and the review
         fixes in a browser (backlog R49).


5. 6 Nov 2026 (site pictures on R2, Vineet, PR #32)

   i.    97 images and 245 flags uploaded to the public bucket `kjs-site-assets` with the same paths as
         `frontend/public/` (with our own `R2Storage`; the dashboard's folder upload dropped the paths).
   ii.   All 767 pictures on the main pages load from R2 with the setting on; with it off, nothing changes.
         Decision 32. Before go-live: `cdn.kjsindia.com` (backlog R48).


6. 7 Nov 2026 (attendance one sidebar + seed fix, Nishita, PR #34)

   i.    The attendance page's own dark left bar is gone. Views (List / Tabular / Calendar / Overtime) in the •••
         menu; the four sections and "+ Apply Leave" in a white bar at the bottom. List view text one step bigger.
   ii.   `python -m app.seed` crashed with a circular import (auth_service → file_service → app.jobs →
         board_service → file_service), found by Vineet after PR #33. Fixed (decision 31); new
         `tests/test_imports.py` imports each entry point in a fresh Python. Backend 216 pass.
   iii.  `PortalShell.tsx` still has its `isAttendance` layout checks (backlog R47).


7. 6–7 Nov 2026 (lead management + User Creation Form, Nishita, PR #33 merged 7 Nov)

   i.    Sidebar group "Lead Management": Contacts, Tasks, Koko Lead, Internal lead. Same pages for admin and staff;
         `leads.view_all` sees every lead, others their own + unassigned.
   ii.   Contacts table (from the LEMAI screenshot) and contact page: pipeline New / Contacted / Closed, tabs
         Info / Notes / Task / Timeline / Proposals. Tasks on a lead are tasks with source `lead`, so they also
         show on the Tasks page. Internal leads: source `internal`, assigned to and created by that person.
   iii.  Admin Users page and User Creation Form (`/admin/users`, `/admin/users/new`, `/admin/users/<id>`) with a
         live profile card; the same card on the Profile page. Photos are files owned by `("user", id)`.
   iv.   Migration 0015 (users: employee_code, branch, reporting_to; leads: created_by).
   v.    Two review rounds fixed: reporting loops, photo access, duplicate email (409), optional "reporting to",
         IST due times, contact grouping (decisions 27–29). Backend 206 pass.


8. 5 Nov 2026 (home look, popup, card hover, Nishita, PR #27 and #30 merged 5 Nov)

   i.    Home: taller banner, item count in the stats box, Best sellers on a white band, dark "How it works",
         chocolate picture under the category menu. Tried floating pack photos without cards: looked worse, undone.
   ii.   "Let's connect" popup (`ConnectPopup.tsx`, decision 26): message drafted from the open page; card on
         desktop, bottom sheet on phones. Testing: use a new tab, or `sessionStorage.removeItem('kjs-connect')`.
   iii.  Product cards grow 20% on hover towards the free side (`hover-grow` in `globals.css`,
         `HoverGrowSides.tsx`); only with a mouse at 768 px+, no animation with reduced motion.


9. 3 Nov 2026 (admin redesign, Nishita, PR #17 merged 3 Nov)

   i.    Account menu (initials, name, role, My profile, Log out) in `components/portal/AccountMenu.tsx`. Log out
         asks first (native `<dialog>`), and the login page says "You've logged out safely" once (`?bye=1`).
   ii.   Overview: greeting by India time, quick actions you're allowed to use, 6 tiles with links
         (`StatTile.tsx`). `/admin/stats` also sends `leads_this_week` and `leads_last_week`
         (`lead_service.weekly_counts`).
   iii.  Sidebar groups (My work / Admin / People / Sales / Website / System) with icons
         (`components/portal/icons.tsx`, plain SVG), an Approvals count, open / close, and drag or arrow keys to
         reorder (`SidebarNav.tsx`, `lib/nav-order.ts`). Toasts (`Toast.tsx`) and empty states (`portal/ui.tsx`).
   iv.   The loaded account is remembered per tab in `lib/portal-session.ts` and forgotten on the login page and
         on log out; an answer asked before the last forget is ignored, so a new login never shows the old person.
   v.    Two review rounds, all must-fix points fixed. Unit 34, backend 177 pass. Follow-ups: backlog R42.


10. 2–3 Nov 2026 (UI steps 4 to 7, Nishita, PR #16 merged 3 Nov)

   i.    Step 4 partner page: "Referral partner", "Who can apply", "How it works", "What your buyers can order"
         (live categories, hidden if they don't load). The made-up referral link card is gone.
   ii.   Step 5: "Best sellers" row on the home page; Recommended doesn't repeat them, but still learns from
         them (`recommend(..., exclude)` in `lib/history.ts`).
   iii.  Step 6: `products.offer_percent` (migration 0012, checked 1 to 90 in the database too), `OfferBadge.tsx`,
         "Offer %" in Admin > Products. Hide / Show sends only `is_active`.
   iv.   Step 7: `components/public/CountryPicker.tsx` (`PhoneInput`, `CountrySelect`), `lib/countries.ts`,
         `lib/countries-data.ts` made by `scripts/make_countries.py` (from `phonenumbers` + Node's country names;
         run it again after upgrading phonenumbers). On the enquiry, partner, Koko, sign-up and profile forms. A
         saved phone is sent back unchanged until edited; an old remembered phone that fails the check is
         forgotten ("Please re-enter your phone number").
   v.    Product fields are written once in `schemas/catalog.py` and shared by add and edit.
   vi.   Two reviews by Vineet and one of our own. Backend 176, unit 29, API 114, browser 55 pass.


11. 30 Oct – 3 Nov 2026 (CR1 restore fix, Vineet, PR #13 merged 3 Nov)

   i.    `restore.sh` order: read both backups in full (app still running), stop the app, safety backup,
         unpack files aside, replace the database in one transaction, swap files, migrations + rights,
         start the app and check its health.
   ii.   "Nothing changed" only when psql proves the rollback (exit 3), or a marker table made just before the
         database step is still there. "Restore done" only after a passing health check. If the database
         step ends unknown, the app stays stopped. A second Ctrl+C can't stop the clean-up.
   iii.  Every failure after the data changed prints the undo command. It is also added to
         `BACKUP_DIR/restore-undo.txt` (one entry per restore, newest last). A restore refuses to start while
         an earlier one is still running inside the database.
   iv.   `backup.sh` reads the whole dump before keeping it, and works with the backend down.
   v.    `deploy/test-restore.sh` (192 checks) is the check for any change to these scripts. It refuses to run
         if `deploy/.env` exists, so it can't touch the server. It takes about 35 min: close Chrome and
         VS Code first (16 GB laptop), or run it in 2 parts.
   vi.   8 review rounds. From round 5 on, only items that fail our rule (a real input gives a wrong result,
         the harm is realistic, a test can show it) were fixed; the rest went to `backlog.md` CR1.


12. 2 Nov 2026 (PR #14 review, Nishita, branch feat/uiUpdates-home)

   i.    Two review rounds fixed: space above the green card; the stats box shows only with the real product
         count (else the quote card fills the column); every capability page linked from the footer is checked.
   ii.   New checks failed first (gap 0px; count missing when the condition was reversed). Browser 46, API 114,
         unit 12 pass.


13. 31 Oct 2026 (home removals, Nishita, branch feat/uiUpdates-home)

   i.    PR #12 (steps 1 and 2) merged. UI step 3: the home page no longer shows the Capabilities section or the
         "250+ products" line. The capability pages stay, linked from the footer, private-label and sitemap
         (the header links only Stick Pack Factory: backlog R39.iii).
   ii.   New check in `browser_e2e.mjs` (failed on the old code). Browser 40, API 114, unit 12 pass. The e2e
         database must be reset before a re-run (`reset_e2e_db.sh`), or the API test hits its own old products.


14. 31 Oct 2026 (sliding sidebar, Nishita, branch feat/uiUpdates-sidebar)

   i.    UI step 2: the staff sidebar is hidden until the menu button slides it in; the next click hides it.
         Computer: pushes the page aside, remembered per tab. Phone: slides over the page with a backdrop and
         its own close button. Escape closes it; reduced motion means no slide.
   ii.   Independent review found 10 points, all fixed. New check `scripts/e2e/sidebar_e2e.mjs` (25 checks),
         failed 13 on the old code. Unit 12, API 114, browser 38, login all pass.


15. 30 Oct 2026 (login spinner, Nishita, branch feat/uiUpdates)

   i.    Nishita's UI list split into 7 small PRs, lowest risk first (track 4d). Decisions: "Broker" becomes
         "Referral partner" (label only; the saved value stays `broker`); partner page uses real content only (no
         made-up commission numbers or testimonials); flags as files in public/flags; country picker only, the
         site stays English (D2); the phone code picker goes on every phone field.
   ii.   Step 1 done: a spinner on the login button, kept on until the next page has opened (useTransition), and
         on the portal's loading screen; "Try again" when the account can't be loaded (server error), instead of
         loading forever; tabs locked while busy. Shared `components/ui/Spinner.tsx`.
   iii.  Tested (first version): login checks 15/15 (the code before fails 5 of them); now 24, see v.
   iv.   PR #12 review (Vineet, 10 points, all real, fixed): `api()` takes a time limit (`timeoutMs`, built-in
         AbortSignal.timeout); the portal frame never loads forever (one status: loading / ready / error; 15 s
         limit; the error screen has Try again, Log out and an error code for support); the login gives the form
         back if the next page takes over 15 s (with an "Open it" link); a ?next= login link never leads back to
         the login page; one shared `components/ui/Loading.tsx` on every staff page; backlog item renamed R39.
   v.    The login checks are now in the repo: `scripts/e2e/login_e2e.mjs` (24 checks; on the PR's first version
         8 of them fail). Independent review of the fixes: 9 real, fixed; staff pages without error handling
         or a time limit go to backlog R40.
   vi.   Second review (Vineet, 31 Oct; the last round for this PR): 3 fixed before merge. `safeNext` refuses a
         path that becomes "//evil.com" once cleaned up (open redirect: "/..//evil.com"), and "/employee//login";
         `api()` turns a "success" it can't read (HTML from a proxy, a cut connection) into an error, never `{}`.
         First frontend unit tests: `frontend/tests/lib.test.mjs` (`npm test`, Node's built-in runner, no
         package; now also in CI): 12 checks, 5 of them fail on the code before the fix. His 7 follow-ups:
         backlog R40 and R41.
   vii.  Independent review of these fixes: 7 real, fixed. `upload()` had the same "unreadable success" bug:
         one shared answer reader now; the login-page check also catches encoded letters ("/employee/%6Cogin");
         no false "slow to open" notice when the page change ends but the login page stays.
   viii. Tested: unit 12/12, login checks 24/24, e2e API 114/114 and browser 38/38.


16. 30 Oct 2026 (code review PR redone, Vineet)

   i.    PR #10 was closed and the same work redone on top of PR #9 as PR #11, to avoid conflicts in the docs.
   ii.   Nishita's reviews of it found mistakes in the fix directions (CR1, CR2, CR11, CR13, CR27 and more), all
         corrected. Three rounds, one more than our limit, because wrong directions would have caused real bugs.
   iii.  Anything found after this goes straight into the real fix PRs. Next: CR1 as real code, failing test first.


17. 30 Oct 2026 (PR #9 fifth review, Nishita)

   i.    Vineet's fifth review: 1 blocking point, real, fixed. Products taken off the site stayed in the saved
         enquiry list and used up slots; adding a product could then silently remove one the visitor sees.
   ii.   Enquiry list rule NOW (replaces 1.ii of the fourth review): when the home page loads, the LATEST
         saved list is cleaned: products not on the site are removed, the newest 20 kept (not when the site's
         product list is empty). Adding never removes a product the visitor can see: if the saved list would
         go over 20 (products another tab added that this page doesn't show), only those go, oldest first.
         Trade-off (Vineet's call): a product another tab added from a newer site version is removed when this
         page loads; much rarer than products taken off the site.
   iii.  His other points (Reveal wrapper, Recommended leftovers, card components, kb.md notes): backlog
         R34 iv, R35, R36, R37. Small points from the review after this fix: R35 ii, R38.
   iv.   Tested: a logic test on the real helpers (19,356 checks incl. 7,836 random lists over the limit; it
         fails on two broken versions), browser checks 23/23 (this round, incl. Vineet's example, zoom and
         phone) + 30/30 + 20/20 + 12/12, e2e API 114/114 and browser 38/38. Independent review: 4 real, fixed.


18. 29 Oct 2026 (whole-repo code review, Vineet)

   i.    Full review of the repo at `7d117aa`, written up in `codeReview.md` (CR1–CR39). No security holes.
   ii.   One must-fix: `restore.sh` can empty the database and still say "restore done" (CR1).
   iii.  Ten should-fix (CR2–CR11): health check can't see a broken home page, backups need the backend running,
         no public error page, rate limits (IPv6, office IP, admin lockout), feature flags not enforced in the API,
         disabled user's batch stuck, emails lost when the mail server is down, superuser password in the API container.
   iv.   Nothing fixed yet. Suggested order: 5 small PRs (`codeReview.md` section 2). Tests were not run (test DB paused).
   v.    Review rounds kept finding bugs in the suggested code snippets, so they were removed: each fix is now a
         direction. New process in `prompt.md` section 6 (failing test first, at most 2 review rounds per PR).


19. 29 Oct 2026 (PR #9 fourth review, Nishita)

   i.    Vineet's fourth review: 9 points, all real, all fixed; his cleanups went to the backlog (R34).
   ii.   (REPLACED on 30 Oct, see the fifth review) Enquiry list rule: products this page doesn't
         know stay in storage (another tab may know them) and are just not shown; the saved list is capped
         at 20, keeping the NEWEST (whatever they are); the page shows and sends at most 20, so the message
         always fits the 4000-character form. Trade-off: with 19 shown + 1 only another tab knows, adding one
         drops the oldest shown product (rare: tabs open across a deploy with a full list).
   iii.  Reveal (repeat cards): two observers with one exact question each (more than 40px off screen →
         hidden; any part on screen → comes in). The 40px is more than the 32px entrance slide: found by a
         test, a card at the edge slid off, hid, came back… in a loop. Hides are drawn in one go (flushSync),
         so a very fast flick still replays the entrance.
   iv.   Recommended: cards always the same height (no Safari jump); a change during the first-load fade
         doesn't restart it. History: one listener for other tabs, always on once used.
   v.    Independent review of the fixes: 7 real, fixed. Tested: browser checks 21/21 (this round) + 30/30
         + 20/20 + 12/12 (incl. zoom 90%/110% and phone 390px), e2e API 114/114 and browser 38/38.


20. 29 Oct 2026 (PR #9 third review, Nishita)

   i.    Vineet's third review: 7 points, all real, all fixed. Back on home after visiting another page shows
         the latest list (cached snapshot dropped when nothing listens); the first-load fade keeps going when
         the list's one-time clean-up changes the picks (no jump); the enquiry form works on the list as it was
         when opened (frozen: what is shown, sent and removed); the 20 limit counts only products this page
         shows; another tab's newly saved value replaces this tab's memory fallback.
   ii.   Reveal redesigned: one animation (an entrance from above or below) for both modes. A hidden card has
         no "side"; the direction is chosen when it comes in, from the last real scroll movement. The side
         checks, their timer and page-size watcher are gone (no leftover timer).
   iii.  Independent review of the fixes: 8 real, all fixed (form stays open if another tab clears the list;
         the clean-up never drops the newest product; a deletion in another tab doesn't wipe a memory-only list).
   iv.   Tested: browser checks 30/30 (this round) + 20/20 + 12/12, e2e API 114/114 and browser 38/38.


21. 29 Oct 2026 (PR #9 review, Nishita)

   i.    Vineet's review of PR #9: 7 points, all real, all fixed. Private window now personalises for the visit
         (history kept in memory per key when storage is blocked or full); one shared hook `useHistory` for the
         enquiry list and the recommendations, live across tabs; one shared `HomeProductCard`.
   ii.   Independent review of those fixes: 8 more, all fixed. Rules kept: the enquiry list is cleaned only
         once per page load, and a toggle or a send only changes the products it is about (a product another
         tab added, even one this page doesn't know, is never deleted; since the fourth review: kept, but the
         saved list is capped at the newest 20). Recommended never reshuffles on screen.
   iii.  Nishita's `.env` points to the Singapore database (checked 29 Oct).
   iv.   Tested: logic 6/6, browser checks 12/12 (review fixes) + 20/20, e2e API 114/114 and browser 38/38.


22. 29 Oct 2026 (recommendations + pop-in cards, Nishita, branch kjs_n2)

   i.    "Recommended" section on the home page. Personal picks come from what the visitor opened (product page,
         quick view) or put in their enquiry list, kept in THEIR browser only (localStorage `kjs_viewed`,
         `kjs_enquiry_list`; `lib/history.ts`). Nothing is sent to us. First-time visitors: a mix across
         categories, server-rendered (public pages stay server-rendered). Always 8 cards (no layout shift);
         changes are applied only while the section is off screen.
   ii.   `Reveal` repeat mode: product cards and category tiles pop in every time they come into view, down or
         up; the ripple follows the real column; everything shows when printing.
   iii.  Backlog R29 fixed: after sending, the enquiry list is emptied on screen and in storage together.
   iv.   Two independent code reviews (20 findings, overlapping), fixed. Pulled Vineet's work (PR #6 merged,
         Claude review workflows, Singapore database) into kjs_n2 first: no conflicts.
   v.    Still to decide (R31–R33): deals strip, best sellers, frequently searched (no made-up claims).


23. 28 Oct 2026 (PR #6 merged, database moved to Singapore, Vineet)

   i.    New Neon project in Singapore (aws-ap-southeast-1). Migrations to 0011, `app.seed`, `app.seed_catalogue`
         (58 products). v1 and v2 `.env` both point to it; old US lines kept as comments. The URL must stay
         `postgresql+asyncpg://...?ssl=require` (asyncpg doesn't take `sslmode` / `channel_binding`).
   ii.   Measured from this PC: one database trip 70–180 ms (was about 560 ms). `/auth/me` still 0.5–0.7 s (R30).
   iii.  PR #6 reviewed four times, approved and merged. Follow-ups R25–R29.
   iv.   The Singapore password was pasted in chat: reset it (B9). Nishita switches her `.env` once she has it;
         she doesn't need to seed (the data is in the shared database). Done: her `.env` points to Singapore.
   v.    Neon agent skills installed locally (`.claude/skills/neon*`, `skills-lock.json`), gitignored. The app
         still uses only the connection string (decision 13).


24. 28 Oct 2026 (PR #6 third review, Nishita)

   i.    e2e `browser_e2e.mjs` expected the old home text ("Explore products"): now "Explore the range".
   ii.   Home texts come from the backend defaults (`content_service.TEXTS`), which always win over a frontend
         fallback: new chocolate / wafers / biscuits wording for home.hero_text and seo.home.*. None were
         customised in Admin > Website, checked in Neon.
   iii.  Pacho Fret 663 and 664 are both cocoa in the printed catalogue (page 30), in two pack designs: labelled
         "red pack" and "brown pack" in the seed, and in Neon with a one-off update (only if unedited).
   iv.   Follow-ups R21–R24 added; R20 closed (the API already checks image_path).


25. 28 Oct 2026 (PR #6 second review, Nishita)

   i.    4 blockers fixed: category panel gap (padding, not margin), search results stay open while focus is in
         the search box (no timer), one progress bar inside the header (CSS: <html data-navigating> or a
         loading screen on the page), bar only for real page changes.
   ii.   Reviewer's fix for the bar (bubble phase) would never start it: Next's <Link> always calls
         preventDefault() (link.js, linkClicked). Kept capture phase + data-no-progress opt-out.
   iii.  CI runs `next typegen` before `tsc` (next-env.d.ts is gitignored). Proven with a test image import.
   iv.   Found while testing: home page scrolled sideways on phones (certification logos); fresh home load
         showed no bar. Both fixed. Independent review of the final code: 5 more fixed, 3 explained.
   v.    Tested: real mouse and keyboard in Chrome, 390 px frame, ticker simulated. NOT tested: a real phone,
         Safari, Firefox. Follow-ups R17–R20 in backlog.


26. 28 Oct 2026 (PR #6 review fixes, Nishita)

   i.    Vineet's review of PR #6: 4 blocking + 6 follow-ups, all fixed. Enquiry form now opens in a portal
         (a CSS transform on the bar squeezed it), stale saved products dropped, list emptied after sending,
         Clear on phones, message box limited to what fits in 4000 characters.
   ii.   Follow-ups: product meta description = summary only, search matches item numbers and word starts
         (not "24 pieces"), Popular uses best sellers, admin headline is the h1 on slide 1, hidden slides inert,
         category panel closes on blur/Escape, product list sent to the browser once (context), imageOf in ProductCard.
   iii.  Tested in Chrome against a throwaway database (not Neon): all 4 blocking fixes checked.
   iv.   Catalogue seeded into Neon (58 products). `frontend/next-env.d.ts` no longer tracked (gitignored).
   v.    Home page: overlap fixed, Next.js dev badge off, loading screen (home only), gold progress bar on page
         changes, scroll animations (`components/public/Reveal.tsx`, one shared observer).
   vi.   Independent code review: 10 findings, all fixed. Worst: a loading.tsx over product/category pages made
         missing pages answer 200 instead of 404. Rule: no loading.tsx above pages that call notFound().


27. 27 Oct 2026 (catalogue + marketplace home page, Nishita)

   i.    Read the 50-page catalogue PDF (pictures only, no text): 58 product families, 156 items.
   ii.   New `backend/app/seed_catalogue.py`: 4 new categories (old ones kept) and 58 products. Only file
         added in the backend (Vineet works on the backend in parallel).
   iii.  58 product pictures cut out of the PDF with a script, cleaned, same background: `frontend/public/images/products/`.
   iv.   New home page: search with instant results (also by item number), category menu with product panel,
         banner slideshow, buyer panel, category tiles, product tabs, quick view, enquiry list (up to 20 products,
         one enquiry), "how it works". New: `components/public/home/*`, `lib/catalogue.ts`. tsc passes.
   v.    Smart App Control blocks Python on Nishita's PC (also uv's Python). Backend runs in Docker there.
   vi.   The home page shows a 500 error when the API is off (by design in `serverGet`). Start the backend first.
   vii.  New assumptions A73–A77, inputs I13, I14 (phone number mismatch).


28. 27 Oct 2026 (production-readiness review)

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


29. 26 Oct 2026 (merge, speed, Smart App Control)

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


30. 25 Oct 2026 (senior review)

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


31. 25 Oct 2026

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


32. 24 Oct 2026 (morning)

   i.    Committed and pushed all Phase 1 work to `kjs_v` (`3a88c65`).
   ii.   Docs cleaned up: tables replaced with numbered lists; new `kb.md` (look up any word);
         removed old files (status-for-replanning, motivation, requirements-review, video summary, old learning notes).
   iii.  Next: production setup.


33. 23–24 Oct 2026 (night)

   i.    New plan from `master-build-prompt.pdf`: Phase 1 in 2 weeks, one list (`checklist.md`).
   ii.   Built every Phase 1 feature: settings files with live reload, JSON logs with request IDs, background jobs,
         attendance, lead SLA timers, notifications, tasks, file storage, order boards, approvals, auto-assign,
         gated forms, offers ticker, WhatsApp button, partners page, private-label builder, and all admin pages.
   iii.  Migrations 0003 to 0009 applied to Neon and the test database.
   iv.   End-to-end testing found and fixed 2 real bugs:
         a.  Every visitor looked like the same IP behind the Next.js proxy, so they shared one rate limit.
         b.  The first request after Neon dropped its connections failed (`pool_pre_ping` back on).
   v.    Every guess written in `backlog.md` section 3 (A1–A52).


34. 23 Oct 2026 (5)

   i.    Holidays table and calendar API, SEO (sitemap, robots, JSON-LD), CI workflow, Koko rules hardened. 52 tests.


35. 23 Oct 2026 (4)

   i.    First working slice: website, Koko on Groq, login, leads, admin.


36. 23 Oct 2026 (2 and 3)

   i.    Installed Docker and gh, cloned the repo, decided D1–D8, made `trackEXP.md`, summarised the demo video.


37. 23 Oct 2026 (1)

   i.    Read all the planning documents, listed the conflicts, set up `docs/`.
