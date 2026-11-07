# Track: where we are

The day-to-day list is `checklist.md`. This file is the short status and the big picture.

The simple version for KJS is `trackEXP.md`. Keep both in step.



---------------------------------------------------------------------------------------------------

## 1. Status today (30 Oct 2026)

1. Phase 1 (all features): DONE

   i.    Built and tested. 125 backend tests, 114 end-to-end API checks, 38 real-browser checks.
   ii.   Merged into `main` (pull request #2).


2. Production prep (no server needed): DONE

   i.    Everything is in `deploy/`: Docker images, production compose, nginx, Cloudflare Tunnel,
         deploy / backup / restore scripts, and the guide `deploy/README.md`.
   ii.   Tested on this PC: the whole production stack, the rate limit, the upload limit,
         the unsafe-settings check, and a full backup → damage → restore drill.
   iii.  Merged into `main` with pull request #3 (26 Oct).


3. Senior review (25 Oct): DONE, merged into `main` (pull request #3, 26 Oct)

   i.    About 50 findings from four independent reviews. Every high and medium one fixed and tested.
   ii.   138 backend tests pass. Production stack re-tested (limited DB user, CSP, restore drill).
   iii.  Left for later on purpose: `backlog.md` section 8.


4. Home page redesign + product catalogue (Nishita): DONE, merged into `main` (PR #6, 28 Oct)

   i.    Marketplace-style home page (search, category menu, banner, product tabs, quick view, enquiry list).
   ii.   58 products from the KJS catalogue PDF with pictures. Seeded into Neon on 28 Oct (`app.seed_catalogue`).
   iii.  28 Oct: all 10 points of Vineet's review fixed; then loading screen (home), page-change progress bar,
         scroll animations; an independent code review found 10 more issues, all fixed (incl. 404 pages
         answering 200 because of a loading.tsx).
   iv.   On Nishita's PC the backend can run in Docker (Smart App Control, see B12).
   v.    Second review (28 Oct): 4 blockers + CI type-check fix done; follow-ups in backlog R17–R20.
         Third review (28 Oct): e2e text, home text defaults, Pacho Fret pack labels; R21–R24 added.
   vi.   Fourth review (28 Oct): approved, follow-ups R25–R29. Merged; catalogue seeded into the Singapore database.
   vii.  Next: demo to KJS. Real-phone test still to do (see memory).


4b. Recommended products + cards that pop in on every scroll (Nishita): PR #9 merged (30 Oct)

   i.    "Recommended" on the home page: personal picks from this browser's history, or a mix across categories.
   ii.   Product cards and category tiles pop in every time they scroll into view, down or up.
   iii.  Waiting on decisions (backlog R31–R33): deals strip, best sellers, frequently searched.


4d. UI requests from Nishita (30 Oct): 7 small PRs, lowest risk first

   i.    Steps 1 login spinner and 2 sliding sidebar: merged in PR #12 (31 Oct). Checks in the repo:
         `scripts/e2e/login_e2e.mjs`, `scripts/e2e/sidebar_e2e.mjs`.
   ii.   Step 3 home removals: PR #14 (branch feat/uiUpdates-home), two review rounds fixed (2 Nov). Capabilities
         section and the "250+" line gone from the home page; the capability pages stay (footer, private-label,
         sitemap link them; header dropdown for all five: backlog R39.iii). Checked in `browser_e2e.mjs`.
   iii.  Steps 4 to 7 merged in PR #16 (3 Nov): 4 partner page ("Referral partner", real content only),
         5 best-seller section, 6 offer % + badge (migration 0012), 7 phone code and country pickers with flags
         (flags copied into public/flags, no package; the site stays English: D2). Decisions: `memory.md`
         section 4, items 20–22. Follow-ups: `backlog.md` R39.
   iv.   Best seller stays a tick box per product (not a category): a product keeps its real category.
   v.    Left from this list: the header "Capabilities" dropdown (`backlog.md` R39.iii).


4e. Admin redesign (Nishita): merged in PR #17 (3 Nov)

   i.    Account menu with a safe log out, a new Overview, a sidebar with groups (open / close, drag to
         reorder), toasts, empty states, and charcoal + gold colours for the whole portal.
   ii.   Follow-ups (browser checks with a login, dev speed): `backlog.md` R42.


4f. Website look, "Let's connect" popup, card hover (Nishita): merged in PR #27 and #30 (5 Nov)

   i.    Gold / charcoal home page, new heading font, WhatsApp popup (up to 3 per visit), cards grow on hover.
         Decisions: `memory.md` items 25–26. Follow-ups: `backlog.md` R47.


4g. Lead management + User Creation Form (Nishita): merged in PR #33 (7 Nov)

   i.    Contacts, contact page, Koko and internal leads, tasks on a lead; admin Users page and form. Migration 0015.
         Decisions: `memory.md` items 27–29. Follow-ups: R47, A83, A84, I15.


4h. Attendance page with one sidebar + seed fix (Nishita): PR #34 (7 Nov)

   i.    Views in the ••• menu, sections in a bottom bar. `python -m app.seed` works again (decision 31).


4c. Whole-repo code review (29 Oct): `codeReview.md`

   i.    ✅ CR1 fixed and merged (PR #13, 3 Nov): `restore.sh` can no longer empty the database and say
         "restore done". 192 checks pass in `deploy/test-restore.sh` on a local Docker copy. Still to do:
         the restore drill on the real server. Follow-ups: `backlog.md` CR1.
   ii.   🟠 CR2–CR11 should be fixed before go-live: health check, backups, public error page, rate limits,
         feature flags, disabled user's batch, lost emails, superuser password in the API container.
   iii.  Plan: 5 small code PRs, each with a failing test first (`codeReview.md` section 2, `prompt.md` section 6).


5. Waiting on

   i.    Vineet: review the assumptions in `backlog.md` section 3 (A1–A66). Decide D20. B12, B13 closed; Next.js 16 merged (PR #4).
         (Merge done: PR #3.)
   ii.   KJS: server + IT contact, domain, real data, SMTP details, R2 keys, WhatsApp verification.
   iii.  Vineet + Nishita: the should-fix list CR2–CR11 (CR1 merged 3 Nov).


6. Can be done without KJS

   i.    (Done 26 Oct: 14 unused frontend packages removed.)
   ii.   Lighthouse check of the production build.
   iii.  (Done 28 Oct: development moved to a Neon project in Singapore, backlog B10.)
   iv.   Reset the Singapore database password (pasted in chat, B9) and send it to Nishita privately.



---------------------------------------------------------------------------------------------------

## 2. The plan

1. Phase 1, all features: Mon 26 Oct to Sat 7 Nov.  ✅ done 24 Oct

2. Production prep that needs no server.  ✅ done 25 Oct

3. Production on the KJS server, real data from KJS: from Mon 9 Nov.

4. UAT with KJS staff, fixes: early December.

5. Go-live: Fri 11 Dec 2026.

6. Buffer and first-week support: 14 to 18 Dec.

7. Stage 2 (buyer intelligence, outreach): 2027.



---------------------------------------------------------------------------------------------------

## 3. How we build each feature (same every time)

1. Pick one line from `checklist.md`.

2. Plan it first: files, tables, routes, screens, tests. No code yet. Ask "why?" until it is clear.

3. Build in this order: migration → model → service (rule + audit) → route (permission) → tests → screen.

4. Prove it: run the tests, click through it, try it as someone who is not allowed.

5. Write it down: tick `checklist.md`, decisions in `memory.md`, blockers and guesses in `backlog.md`,
   one learning in `learning/learning-log.md`, new words in `kb.md`.



---------------------------------------------------------------------------------------------------

## 4. Go-live checklist (production)

1. Secrets set on the server, and the old ones rotated (B9).

2. Backups running (cron), one restore drill done on the server, an off-site copy decided (A55).

3. Only Cloudflare Tunnel reaches nginx (A56).

4. Admin account created with a strong password, real data loaded.

5. Sitemap and robots use the real domain (built from `PUBLIC_BASE_URL`).

6. Error and uptime alerts on.

7. `deploy.sh` keeps the last 3 image versions for rollback.



---------------------------------------------------------------------------------------------------

## 5. History

1. 23 Oct: read all planning documents, set up docs, built the first working slice (website, Koko, login, leads, admin).

2. 24 Oct (night): new 2-week plan from `master-build-prompt.pdf`. Built and tested every Phase 1 feature.

3. 24 Oct (morning): committed and pushed. Docs made simpler.

4. 25 Oct: Phase 1 merged into `main`. Production setup built and tested (`deploy/`).
   Senior review: about 50 findings, high and medium ones fixed.

5. 26–27 Oct: Next.js 16 upgrade merged (PR #4). Docs now committed. Production-readiness review: 3 must-fix
   and 12 should-fix items fixed and merged (PR #5, backlog section 9).

6. Tip for this Windows PC: `uvicorn --reload` sometimes misses changes. If nothing changes after an edit,
   stop the API fully and start it again. Smart App Control was turned off on 26 Oct, so `.venv` Python works again (B12 closed).

7. 28 Oct: PR #6 (home page + 58-product catalogue) reviewed four times and merged. Development database moved
   to Neon Singapore: about 70–180 ms per database trip from India, was about 560 ms (backlog B10).

8. 29 Oct: whole-repo code review in `codeReview.md` (CR1–CR39). No security holes; 1 must-fix (`restore.sh`)
   and 10 should-fix. Not fixed yet: 5 small PRs planned (`codeReview.md` section 2).

9. 30 Oct – 3 Nov: CR1 (`restore.sh`) fixed, reviewed 8 times and merged (PR #13). New `deploy/test-restore.sh`
   (192 checks). Since 2 Nov, session notes go in `docs/tempV.md` / `tempS.md` first (`prompt.md` section 7).

10. 2–3 Nov: UI steps 4 to 7 merged (PR #16, migration 0012) and the admin redesign merged (PR #17).
    Backend 177, unit 34, API 114, browser 55 checks pass.
