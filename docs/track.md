# Track: where we are

The day-to-day list is `checklist.md`. This file is the short status and the big picture.

The simple version for KJS is `trackEXP.md`. Keep both in step.



---------------------------------------------------------------------------------------------------

## 1. Status today (27 Oct 2026)

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


4. Home page redesign + product catalogue (27 Oct, Nishita): CODE DONE, not seen in a browser yet

   i.    Marketplace-style home page (search, category menu, banner, product tabs, quick view, enquiry list).
   ii.   58 products from the KJS catalogue PDF with pictures. Seed: `python -m app.seed_catalogue` (adds only
         new products; writes to the shared Neon database).
   iii.  On Nishita's PC the backend runs in Docker (Smart App Control blocks Python there, see B12).
   iv.   Next: run the seed, check the page, demo to KJS.


5. Waiting on

   i.    Vineet: review the assumptions in `backlog.md` section 3 (A1–A66). Decide D20. B12, B13 closed; Next.js 16 merged (PR #4).
         (Merge done: PR #3.)
   ii.   KJS: server + IT contact, domain, real data, SMTP details, R2 keys, WhatsApp verification.


6. Can be done without KJS

   i.    (Done 26 Oct: 14 unused frontend packages removed.)
   ii.   Lighthouse check of the production build.
   iii.  Move development to a Neon project in Singapore (needs the new connection string).



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
