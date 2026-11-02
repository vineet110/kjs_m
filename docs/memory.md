# Memory: KJS India Platform

The project's long-term memory: short facts, rules and decisions.

Anyone joining (person or AI) reads this first.

Last updated: 30 Oct 2026.

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

10. Whole-repo code review and its fix list (29 Oct): `codeReview.md`



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

1. 31 Oct 2026 (sliding sidebar, Nishita, branch feat/uiUpdates-sidebar)

   i.    UI step 2: the staff sidebar is hidden until the menu button slides it in; the next click hides it.
         Computer: pushes the page aside, remembered per tab. Phone: slides over the page with a backdrop and
         its own close button. Escape closes it; reduced motion means no slide.
   ii.   Independent review found 10 points, all fixed. New check `scripts/e2e/sidebar_e2e.mjs` (25 checks),
         failed 13 on the old code. Unit 12, API 114, browser 38, login all pass.


2. 30 Oct 2026 (login spinner, Nishita, branch feat/uiUpdates)

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


3. 30 Oct 2026 (CR1 restore fix, Vineet, branch `fix/cr1-restore-safety`)

   i.    `restore.sh` now reads both backups in full before anything changes, cancels the transaction if
         `pg_restore` fails, unpacks files aside, keeps old backups, and says how to undo a failure.
   ii.   `backup.sh` reads the whole dump before keeping it.
   iii.  New `deploy/test-restore.sh`: 27 of the first 49 checks failed before the fix. All 155 pass on the final code, on a local Docker copy.
   iv.   Rule: the test refuses to run if `deploy/.env` exists, so it can't touch the server.
   v.    Nishita has claimed files for 7 steps and migration 0012: agree before touching those or adding a migration.
   vi.   PR #13 review (Nishita, 31 Oct): three real bugs, all fixed with a test first. "Nothing changed" is now said
         only when `psql` proves the rollback, "restore done" only after the app restarts, and `.restore-new` is
         cleaned up. `deploy/test-restore.sh` is now the check for any change to these scripts.
   vii.  Second review (Nishita, 31 Oct): if the database step ends unknown the app stays stopped, "restore done" needs a
         passing health check, `backup.sh` works with the backend down, and a second signal can't stop the clean-up.


4. 30 Oct 2026 (code review PR redone, Vineet)

   i.    PR #10 was closed and the same work redone on top of PR #9 as PR #11, to avoid conflicts in the docs.
   ii.   Nishita's reviews of it found mistakes in the fix directions (CR1, CR2, CR11, CR13, CR27 and more), all
         corrected. Three rounds, one more than our limit, because wrong directions would have caused real bugs.
   iii.  Anything found after this goes straight into the real fix PRs. Next: CR1 as real code, failing test first.


4. 30 Oct 2026 (PR #9 fifth review, Nishita)

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


5. 29 Oct 2026 (whole-repo code review, Vineet)

   i.    Full review of the repo at `7d117aa`, written up in `codeReview.md` (CR1–CR39). No security holes.
   ii.   One must-fix: `restore.sh` can empty the database and still say "restore done" (CR1).
   iii.  Ten should-fix (CR2–CR11): health check can't see a broken home page, backups need the backend running,
         no public error page, rate limits (IPv6, office IP, admin lockout), feature flags not enforced in the API,
         disabled user's batch stuck, emails lost when the mail server is down, superuser password in the API container.
   iv.   Nothing fixed yet. Suggested order: 5 small PRs (`codeReview.md` section 2). Tests were not run (test DB paused).
   v.    Review rounds kept finding bugs in the suggested code snippets, so they were removed: each fix is now a
         direction. New process in `prompt.md` section 6 (failing test first, at most 2 review rounds per PR).


6. 29 Oct 2026 (PR #9 fourth review, Nishita)

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


7. 29 Oct 2026 (PR #9 third review, Nishita)

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


8. 29 Oct 2026 (PR #9 review, Nishita)

   i.    Vineet's review of PR #9: 7 points, all real, all fixed. Private window now personalises for the visit
         (history kept in memory per key when storage is blocked or full); one shared hook `useHistory` for the
         enquiry list and the recommendations, live across tabs; one shared `HomeProductCard`.
   ii.   Independent review of those fixes: 8 more, all fixed. Rules kept: the enquiry list is cleaned only
         once per page load, and a toggle or a send only changes the products it is about (a product another
         tab added, even one this page doesn't know, is never deleted; since the fourth review: kept, but the
         saved list is capped at the newest 20). Recommended never reshuffles on screen.
   iii.  Nishita's `.env` points to the Singapore database (checked 29 Oct).
   iv.   Tested: logic 6/6, browser checks 12/12 (review fixes) + 20/20, e2e API 114/114 and browser 38/38.


9. 29 Oct 2026 (recommendations + pop-in cards, Nishita, branch kjs_n2)

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


10. 28 Oct 2026 (PR #6 merged, database moved to Singapore, Vineet)

   i.    New Neon project in Singapore (aws-ap-southeast-1). Migrations to 0011, `app.seed`, `app.seed_catalogue`
         (58 products). v1 and v2 `.env` both point to it; old US lines kept as comments. The URL must stay
         `postgresql+asyncpg://...?ssl=require` (asyncpg doesn't take `sslmode` / `channel_binding`).
   ii.   Measured from this PC: one database trip 70–180 ms (was about 560 ms). `/auth/me` still 0.5–0.7 s (R30).
   iii.  PR #6 reviewed four times, approved and merged. Follow-ups R25–R29.
   iv.   The Singapore password was pasted in chat: reset it (B9). Nishita switches her `.env` once she has it;
         she doesn't need to seed (the data is in the shared database). Done: her `.env` points to Singapore.
   v.    Neon agent skills installed locally (`.claude/skills/neon*`, `skills-lock.json`), gitignored. The app
         still uses only the connection string (decision 13).


11. 28 Oct 2026 (PR #6 third review, Nishita)

   i.    e2e `browser_e2e.mjs` expected the old home text ("Explore products"): now "Explore the range".
   ii.   Home texts come from the backend defaults (`content_service.TEXTS`), which always win over a frontend
         fallback: new chocolate / wafers / biscuits wording for home.hero_text and seo.home.*. None were
         customised in Admin > Website, checked in Neon.
   iii.  Pacho Fret 663 and 664 are both cocoa in the printed catalogue (page 30), in two pack designs: labelled
         "red pack" and "brown pack" in the seed, and in Neon with a one-off update (only if unedited).
   iv.   Follow-ups R21–R24 added; R20 closed (the API already checks image_path).


12. 28 Oct 2026 (PR #6 second review, Nishita)

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


13. 28 Oct 2026 (PR #6 review fixes, Nishita)

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


14. 27 Oct 2026 (catalogue + marketplace home page, Nishita)

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


15. 27 Oct 2026 (production-readiness review)

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


16. 26 Oct 2026 (merge, speed, Smart App Control)

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


17. 25 Oct 2026 (senior review)

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


18. 25 Oct 2026

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


19. 24 Oct 2026 (morning)

   i.    Committed and pushed all Phase 1 work to `kjs_v` (`3a88c65`).
   ii.   Docs cleaned up: tables replaced with numbered lists; new `kb.md` (look up any word);
         removed old files (status-for-replanning, motivation, requirements-review, video summary, old learning notes).
   iii.  Next: production setup.


19. 23–24 Oct 2026 (night)

   i.    New plan from `master-build-prompt.pdf`: Phase 1 in 2 weeks, one list (`checklist.md`).
   ii.   Built every Phase 1 feature: settings files with live reload, JSON logs with request IDs, background jobs,
         attendance, lead SLA timers, notifications, tasks, file storage, order boards, approvals, auto-assign,
         gated forms, offers ticker, WhatsApp button, partners page, private-label builder, and all admin pages.
   iii.  Migrations 0003 to 0009 applied to Neon and the test database.
   iv.   End-to-end testing found and fixed 2 real bugs:
         a.  Every visitor looked like the same IP behind the Next.js proxy, so they shared one rate limit.
         b.  The first request after Neon dropped its connections failed (`pool_pre_ping` back on).
   v.    Every guess written in `backlog.md` section 3 (A1–A52).


21. 23 Oct 2026 (5)

   i.    Holidays table and calendar API, SEO (sitemap, robots, JSON-LD), CI workflow, Koko rules hardened. 52 tests.


22. 23 Oct 2026 (4)

   i.    First working slice: website, Koko on Groq, login, leads, admin.


23. 23 Oct 2026 (2 and 3)

   i.    Installed Docker and gh, cloned the repo, decided D1–D8, made `trackEXP.md`, summarised the demo video.


24. 23 Oct 2026 (1)

   i.    Read all the planning documents, listed the conflicts, set up `docs/`.
