# Track: where we are

The day-to-day list is `checklist.md`. This file is the short status and the big picture.

The simple version for KJS is `trackEXP.md`. Keep both in step.



---------------------------------------------------------------------------------------------------

## 1. Status today (23 Nov 2026)

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


4i. Website pictures on Cloudflare R2 (Vineet): merged in PR #32 (6 Nov)

   i.    Pictures and flags from the public bucket `kjs-site-assets` (decision 32). Test address r2.dev for now.
         Before go-live: `cdn.kjsindia.com` (backlog R48).


4j. Order boards overhaul (Vineet): merged in PRs #35–#39 (8–9 Nov)

   i.    People and owner, step heads, new board page and list, file preview, History tab, plan editing with the
         owner's lock. Migrations 0016–0018, Neon at 0018. Decisions: `memory.md` items 33–38.
         Follow-ups: `backlog.md` R48–R49, A85–A90.


4k. Go-live safety (Vineet, Nishita): merged in PRs #41–#45 (9 Nov)

   i.    Off-site backup to R2 `kjs-bkp-prod`, attendance hours, secrets out of the API, `/healthz`, login and
         rate limits, no lost emails, feature switches, error pages and time limits. Code review CR2–CR11 done.
         Decisions: `memory.md` items 39–44. Follow-ups: `backlog.md` R50 (drill on the server, key rotation).


4l. Order boards browser check + e2e tests for the new features (Nishita): PRs #46, #49 (9 Nov)

   i.    #46: order boards checked in Chrome (backlog R49 i), one phone screen bug fixed.
   ii.   #49: `scripts/e2e` covers lead management, leave and shifts, order boards (people, previews, History,
         lock). api 196, browser 73, sidebar 25 passing; `login_e2e.mjs` unsteady (backlog R51). No app bugs found.


4m. Koko fixed + catalogue cards (Nishita): merged in PR #50 (9 Nov)

   i.    Koko had failed every message (whole catalogue over Groq's limit). Now only the products that matter,
         and product cards on product and category pages. Decision: `memory.md` 45. Follow-ups: `backlog.md`
         R52 (paid Groq tier before real traffic), A92 (card rules).


4n. Config comments and values (Nishita): merged in PR #56 (10 Nov)

   i.    Plain comments in `config/sla.ini`, `features.ini`, `logging.ini`, `koko.ini`. Background jobs
         switched off, one batch a day, 30-minute SLA grace: `memory.md` 46. Follow-up: `backlog.md` R53.


4o. Phase switches for the portal (Nishita): merged in PRs #58 and #60 (10 Nov)

   i.    `config/modules.ini`: each portal area on / admin / off, hidden in the menu, the API and the jobs.
         Decision: `memory.md` 47. Follow-ups: `backlog.md` R54 (e2e check), R55 (`admin` and auto-assign).


4p. KJS Chat phase 1 (Vineet): merged in PR #55 (10 Nov)

   i.    Channels, group chats and DMs inside the portal, live messages over a WebSocket, unread counts,
         @mentions, edit and delete your own. Migration 0020. Decision: `memory.md` 48.
   ii.   Checks: backend 313, frontend 44 unit, chat browser test 55 (`scripts/e2e/chat_e2e.mjs`).
         Follow-ups: `backlog.md` A93-A99, I16, R60.


4q. Lead Harvester (devillover27, PR #53) + its security fix (Vineet, PR #62): merged 10 Nov

   i.    #53 was merged first on purpose; #62 fixed the API-key leak and SSRF right after. Migration 0019.
         Decision: `memory.md` 49. Follow-ups: `backlog.md` I17, R57.


4r. Employee management and live updates (Vineet): merged in PR #76 (13 Nov)

   i.    Reject a sign-up with a reason, per-person permissions, job titles, Manage employees tabs, one update
         check every 30 s for the bell and badges. Migration 0023. Decision: `memory.md` 50.


4s. Review fixes after #77 (Firebase login) and #80 (complaints): merged in PR #81 (14 Nov)

   i.    One migration head again (0026 after 0025), the complaint upload error, clock skew in the session
         check. Neon at 0026. Decision: `memory.md` 51.


4t. Staff login through Firebase + forgot password by email (Kunal): merged in PR #77 (14 Nov)

   i.    Firebase checks the password, we keep our own session. Sign-up needs an admin's approval as before.
         A reset or password change ends other sessions. Migrations 0024, 0025. Decision: `memory.md` 52.
   ii.   Follow-ups: `backlog.md` R61-R65.


4u. Lead files + fill a lead from Excel / CSV (Nishita): merged in PR #74 (13 Nov)

   i.    Files tab on a lead (same file system as boards), every upload checked to be a real, whole file
         (`file_check.py`). "Fill from Excel / CSV" on the new-lead form, with a same-person check before saving.
         `defusedxml` added. Decision: `memory.md` 53.


4v. Bulk import + Extra Info for leads (Nishita): merged in PR #78 (13 Nov)

   i.    Each row of an Excel / CSV file becomes a lead (max 500, all or none). Columns we have no field for
         go to "Extra Info" after Add / Reject. Migration 0022. Decision: `memory.md` 53.


4w. Spinner on buttons that wait for the backend (Nishita): merged in PR #79 (14 Nov)


4x. Complaints, "Report a problem" (Nishita): merged in PR #80 (14 Nov)

   i.    Header button on every portal page, admins read them at `/admin/complaints`. Migration 0026.
         Decision: `memory.md` 54. Guesses: `backlog.md` A100-A103. Follow-ups: R66, R67.


4c. Whole-repo code review (29 Oct): `codeReview.md`

   i.    ✅ CR1 fixed and merged (PR #13, 3 Nov): `restore.sh` can no longer empty the database and say
         "restore done". 192 checks pass in `deploy/test-restore.sh` on a local Docker copy. Still to do:
         the restore drill on the real server. Follow-ups: `backlog.md` CR1.
   ii.   ✅ CR2–CR11 fixed and merged (PRs #41–#45, 9 Nov). Still to do on the server: the restore drill
         and `deploy/test-restore.sh` (backlog R50).
   iii.  Plan: 5 small code PRs, each with a failing test first (`codeReview.md` section 2, `prompt.md` section 6).


4y. Production on Hostinger + testing: live by 23 Nov

   i.    The platform runs on a Hostinger VPS at https://twins.kjsindia.com. Testing with KJS is going on now.
         Decision: `memory.md` 62. Still to do on the server: `backlog.md` section 29.


5. Waiting on

   i.    Vineet: review the assumptions in `backlog.md` section 3 (A1–A66). Decide D20. B12, B13 closed; Next.js 16 merged (PR #4).
         (Merge done: PR #3.)
   ii.   KJS: real data, SMTP details, WhatsApp verification, sign-off after testing. (Server: done, Hostinger.)
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

3. Production on our Hostinger VPS: live at https://twins.kjsindia.com on 23 Nov.  ✅

4. UAT with KJS staff, fixes: started 23 Nov, until early December.

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

11. 10 Nov: KJS Chat phase 1 (#55), Lead Harvester (#53) and its security fix (#62), phase switches (#58,
    #60), sidebar names (#63) merged. Neon migrated to 0020. 27 local and 47 GitHub merged branches deleted.

12. 13 Nov: employee management and live updates merged (#76, migration 0023). Lead files + Excel / CSV (#74),
    bulk import + Extra Info (#78, migration 0022) merged.

13. 14 Nov: Firebase login (#77), button spinners (#79) and complaints (#80) merged, then review fixes (#81).
    Neon migrated to 0026.

14. 16–17 Nov: email checks switched off and parked until our own server (#87, decision 55, backlog R68).
    Own-server research: E2E Networks as a paid option next to the Oracle free VM (backlog R69).

16. 23 Nov: production is live on a Hostinger VPS at https://twins.kjsindia.com (decision 62). Testing with
    KJS started. Server follow-ups: backlog section 29.

15. 18 Nov: coffee-only switch: photo upload when adding a product (#93), Show/Hide per category (#97,
    migration 0030, Neon migrated), the site follows the switches (#99). Coffee-only = hide Confectionery,
    Health drinks and Instant drink powders in Admin.
