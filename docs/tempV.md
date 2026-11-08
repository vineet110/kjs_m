# Session notes (Vineet)

One subheading per task. Moved into the shared docs after the PR merges (see `docs/prompt.md` section 7).

## Order boards PR 1: people, owner, step heads (7 Nov, branch `feat/board-members`)

Plan: 4 small PRs. 1 people and roles (this one), 2 file preview (side panel + full screen),
3 History tab (audit log, read only), 4 edit steps after creation.

What was done (backend; the screen is the next part of this PR)

1. Migration 0016 (after Nishita's 0015, so PR #33 must merge first; Nishita told):
   i.    New table `board_people`: everyone on a board. Filled from the existing step members and owners.
   ii.   New column `board_members.is_head` (false for old rows).
   iii.  Only adds things. Checked on the test database with an existing board: upgrade, downgrade,
         upgrade again; no row lost (script in the session scratchpad, not in the repo).
2. Rules (`board_service.py`):
   i.    Owner = the person who created the board. Owner and `boards.manage` add and remove people,
         change who works on a step and its head, finish the board, approve file deletes.
   ii.   Everyone on the board sees it, ticks any checklist, uploads and asks to delete files.
   iii.  Only a step's people (head included), the owner or `boards.manage` mark that step done.
   iv.   Every step keeps at least 1 person: at creation, when changing a step, when removing someone.
   v.    Removing someone: their access ends; their files and history stay; their open tasks on the
         board are closed (done, with a note); finished steps keep them as the people who did it.
   vi.   New people on a running step get its tasks; people taken off it get those tasks closed.
   vii.  Every change is audited in the same save. Finished boards can't change people.
3. Files: an owner type can name extra delete approvers (`register_owner(..., approvers=...)`).
   For boards: the owner. `files.approve` holders still can. The requester still can't approve their own.
4. New routes: `POST /boards/{code}/people`, `DELETE /boards/{code}/people/{user_id}`,
   `PUT /boards/{code}/steps/{step_id}/people`. `POST /boards/{code}/finish` and
   `POST /files/{id}/delete-decision` now check owner-or-permission in the service.
5. Tests: `tests/test_board_people.py` (8 tests, allowed and forbidden users for every new route).

Screen (branch `feat/board-members-ui`, on top of the backend branch)

1. Board page (`BoardDetail.tsx`): summary card (code, order, client, dates, owner, priority, state),
   step timeline with progress, tabs Steps / Files / People.
2. Steps: people with initials, ★ for heads, "Change people" (owner) with search and ★ head, checklist
   count, time used bar, "Mark step done" only for the step's people or the owner.
3. People: owner badge, which steps each person works on, Add to board and Remove (owner only).
   Errors stay on the page (not a toast), as Toast.tsx says.
4. Files: Approve delete / Keep file for the owner, with the reason shown.
5. Board list: filters (All, On track, At risk, Late, with counts), search by code / order / client,
   step progress segments.
6. Create form: a tick list per step instead of the Ctrl+click box, ★ head, at least one person per step.
7. Tested in Chrome on the local e2e database (not Neon): list, board, add person, removing the only
   person on a step refused, remove, change step people and heads, delete approval by the owner
   (the requester's own approval refused), member view without owner buttons. tsc and 37 unit tests pass.
   Not tested: phone width, submitting the create form in the browser (the API refusal is tested).

PR 2: file preview (branch `feat/board-file-preview`, on top of the screens branch)

1. New packages (Vineet approved, 7 Nov):
   i.    `xlsx` 0.20.3 (SheetJS) from cdn.sheetjs.com, NOT npm: npm only has 0.18.5, which has known
         security bugs when reading untrusted files. SheetJS publishes fixed versions only on its own site.
   ii.   `mammoth` 1.13.0 (Word .docx to HTML) from npm.
   iii.  Both load only when someone opens such a file (dynamic import). `npm audit`: 0 vulnerabilities.
2. Backend: `GET /files/{id}/view`. Same access as download; always sent by our API (never an R2 link,
   so the bucket stays private); inline; never cached; nosniff. Sandboxed, except PDFs: Chrome shows
   "This page has been blocked by Chrome" for a sandboxed PDF (checked in Chrome, 7 Nov).
3. Screen: click a file to see it beside the list (half the width on a computer, below on a phone),
   Full screen (Esc goes back), Download, Close. `FilePreview.tsx`, helpers in `lib/preview.ts`.
   i.    PDF: the browser's PDF viewer. Images: a picture. Text: as text.
   ii.   CSV and Excel: a table drawn by React (cell text can't run as code), sheet tabs, column letters,
         row numbers, first 1000 rows and 50 columns. Dates shown as 20-Nov-2026. CSV cells stay as written.
   iii.  Word .docx: mammoth HTML in a frame with scripts off (sandbox=""); links that aren't http(s) or
         mailto lose their address. Old .doc and zip: Download only.
   iv.   Files over 10 MB: Download only (reading them could freeze the tab).
4. Tests: backend 2 (view: inline headers, PDF without sandbox, CSV sandboxed, not logged in 401, not on
   the board 403); unit 3 (`previewKind`, `colName`, `safeLinks`).
5. Checked in Chrome (local e2e database): Excel (2 sheets; a cell with `<img onerror>` shows as text),
   CSV, Word (heading, table; a `javascript:` link has no address), PDF, picture, text, full screen + Esc.
   Not checked: phone width, a real Excel file saved by Excel, a big file near 10 MB.

Assumptions (fold into backlog later)

1. Formulas show the result saved in the file. A file made by a program that doesn't save results
   shows empty cells there (Excel and Google Sheets save them).
2. Preview cap 10 MB, 1000 rows, 50 columns.

PR 3: History tab (branch `feat/board-history`, on top of the preview branch)

1. Backend: `GET /boards/{code}/history?before_id=&limit=` (everyone on the board). Reads the audit log
   only, never writes: the board's own changes plus its files' uploads and delete decisions (also of
   files deleted since). Newest first, 50 at a time, `more` says if older lines exist.
   `board_service.describe` turns each row into a sentence ("removed Imran Khan from the board").
2. No migration. The audit log already can't be edited or deleted (trigger + the app's database user
   has no UPDATE/DELETE on it). New test: UPDATE of a history line is blocked (the old test only did DELETE).
3. Screen: History tab (`BoardHistory.tsx`): grouped by day (India time), a colour dot per kind of change,
   "Show older". Refreshes after every change on the board. The tab bar scrolls sideways on small screens.
4. Tests: `tests/test_board_history.py` (4: the whole story in order incl. a deleted file, paging and
   only this board, strangers 404 / logged out 401, a line can't be edited).
5. Checked in Chrome (local e2e database): the full story of the test board, a tick shows at once.

Assumptions (fold into backlog later)

1. Everyone on the board can read its history (not only the owner).
2. No database index for it yet: the audit log is small. Add one on (entity_type, entity_id) if it
   grows past about 100,000 rows.

PR 4: edit the plan (branch `feat/board-edit-plan`, on top of the History branch)

Vineet's decisions (7 Nov): remove a step = anyone while unlocked, only steps not started, its checklist
deleted (History keeps a copy), its tasks closed with a note (not deleted); the plan can change any time;
the owner can lock it; the lock covers the whole plan; only steps not started can be moved.

1. Migration 0018 (was 0017; 0017 is now the audit_log index from PR 3's review fixes): `order_boards.plan_locked` (false for old boards). Only adds a column. Checked on the
   test database: upgrade, downgrade, upgrade. Tell Nishita: 0016, 0017 and 0018 are taken.
2. Rules (`board_service.edit_plan`, `set_plan_lock`):
   i.    `PUT /boards/{code}/plan`: start, deadline, split and all steps in the new order, saved together.
         Anyone on the board while unlocked; the owner or boards.manage when locked (403 `plan_locked`).
   ii.   `POST /boards/{code}/plan-lock`: owner or boards.manage.
   iii.  Running and done steps stay first, in their order, and can't be removed (422 `started_steps`).
   iv.   Every step's planned dates are worked out again. The running step's open tasks get its new end
         as due date. Its alerts: more time = they can fire again; less time = a newly crossed level is sent.
   v.    A removed step: deleted with its checklist and people; the history keeps a copy (name,
         checklist, tasks, people). Its tasks (none before a step starts) are closed with a note.
   vi.   A new step needs at least 1 person (put on the board too). If every other step is done, it
         starts at once.
   vii.  One history line says what changed ("deadline 28 Nov → 05 Dec; 'Production' 50% → 40%; added
         step 'Labelling' (Admin)"). Everyone else on the board gets a notification.
   viii. `/boards/preview` (date maths only, saves nothing) is now open to any logged-in staff, because
         people on a board may edit an unlocked plan. Was boards.manage.
3. Screen: Steps tab has "Edit plan" and, for the owner, "Lock plan / Unlock" (`PlanEditor.tsx`):
   dates, split, steps with name and size, ↑ ↓ and Remove only for steps not started, Add step with
   people (★ head), tasks and checklist, live planned dates, the % total, "Will be removed: …".
   Others see "Plan locked by the owner" and no Edit plan button.
4. Tests: `tests/test_board_plan.py` (7): the lock and who may edit; add + rename + reorder + resize in
   one save with the history line and notifications; only steps not started removed or moved, history
   keeps the removed step; running step tasks follow its new end; a step added after the last starts
   at once; bad plans refused and nothing changed, finished board 409; preview for logged-in staff only.
5. Checked in Chrome (local e2e database), through the page (screenshots timed out on Chrome's side):
   Meena (unlocked) extended the deadline, added and moved a step (Save stays off until it has a
   person), saved; Priya locked and removed a step not started; Meena then saw the lock badge, no Edit
   plan, and the API answered 403. History showed every change.

Assumptions (fold into backlog later)

1. Checklists and task lists of existing steps aren't editable in the plan editor (only for new steps).
2. Renaming a running step doesn't rename the tasks already given for it.
3. Changing the split (% / days) keeps the numbers typed; the person fixes them before saving.

Found on PR #33 (Nishita): `python -m app.seed` fails with a circular import (auth_service -> file_service
-> app.jobs -> board_service -> file_service). The app itself starts. `main` is fine. The deploy guide uses
app.seed for the first admin, so it needs fixing in PR #33.

Assumptions (fold into backlog section 3 later)

1. `boards.manage` can do everything the owner can (admins and managers stay in control).
2. The owner can't be removed. Changing the owner is not possible yet.
3. Closed tasks are marked done with a note, like finishing a board does (there is no "cancelled" status).
4. A step that is done keeps its people; only steps not done can change.
5. Creating a board now needs at least one person on every step (the old form allowed none).
6. The person who asks to delete a file is no longer notified about their own request.

## Site pictures on Cloudflare R2 (6 Nov, branch `feat/r2-site-assets`)

What was done

1. New public R2 bucket `kjs-site-assets` holds `images/` (97 files) and `flags/` (245 files), with the
   same paths as `frontend/public/`. Test address: `https://pub-2f2268655b7244e295313aaf35e31e54.r2.dev`.
2. Uploaded with a one-off script that uses our own `R2Storage` (no new tool). The dashboard's folder upload
   dropped the folder paths, so it was not used.
3. The API token now also covers `kjs-site-assets` (Vineet added it).
4. Code: new `frontend/src/lib/assets.ts` with `asset(path)`. It puts the bucket address in front of
   `/images/...` and `/flags/...` only. Uploaded photos (`/api/...`) are not touched.
   Used in `imageOf` and every fixed picture path (logo, favicon, categories, certificates, flags).
5. Setting: `NEXT_PUBLIC_ASSET_BASE` (frontend build) = `ASSET_BASE_URL` (deploy/.env). Empty = the site
   uses `public/` exactly as before. Read at build time: change it, then rebuild.
6. Also changed: `next.config.mjs` (allow the bucket in `images.remotePatterns`), `frontend/Dockerfile`,
   `deploy/docker-compose.prod.yml`, `deploy/.env.production.example`, nginx CSP (`img-src`).

Tested

1. `npm test`: 37 pass (3 new: `asset`, `imageOf`).
2. Production build with the setting on: home, products, a product page, login, partners, private label.
   767 different pictures asked for, all 767 load from R2 (200).
3. Setting off (dev server): no R2 address on any page, pictures still from `public/`.

Decisions and assumptions (fold into backlog later)

1. New decision, changes R44 iv: site pictures go to a PUBLIC bucket now, not "only if traffic grows".
   Staff and order board files stay in the private `kjs-prod-files` (5-minute signed links, unchanged).
2. Assumption: `r2.dev` is fine for testing only (slowed down by Cloudflare). Before go-live connect
   `cdn.kjsindia.com`, then change `ASSET_BASE_URL` AND the address in `nginx/security-headers.conf`.
3. Assumption: keep the copies in `frontend/public/` for now as a fallback. Remove them in a later PR once
   the site has run well on R2 for about a week.
4. A new or changed site picture must now be uploaded to the bucket too, with a NEW file name
   (Cloudflare caches the old one).
5. The 5 videos in `images/kjs/video/` are not used anywhere in the code.

New terms for kb.md: public bucket, r2.dev, asset base address, remotePatterns.

## 8 Nov: review fixes for order boards PRs #35 to #39

A code review of each PR found these; all fixed on each PR's own branch, then merged down the chain.
main (#33, #34) was merged into #35 first: no real conflicts (GitHub's flag was out of date).

1. #35 people backend: the owner now gets step-done and 85%/100% alerts; a step that still lists someone
   who left can have its people changed (only people being added must be active); the delete-decision
   route checks rights before locking the file (outsiders get 403 whether the file exists or not);
   marking a step done locks the board, so removing someone at the same moment can't hand them a task.
2. #36 screens: board changes are sent one at a time in click order, and a double click is ignored;
   "Change people" lists people who left (marked "no longer active") so they can be unticked; the person
   who asked for a delete doesn't get Approve / Keep (new `own_request` on each file); a failed staff
   list load shows an error.
3. #37 preview: CSV read as UTF-8 (₹ and Hindi showed garbled); Excel and CSV stop reading at 1000 rows
   (a big sheet froze the tab); full screen uses the browser's own full screen, so Esc works after a
   click inside the PDF or Word frame; a ".pdf" that isn't really a PDF (doesn't start with %PDF-) is
   sandboxed, a real one may only be framed by our pages (`frame-ancestors 'self'`); phones without an
   inline PDF viewer get "Download" instead of a blank frame; footnote links in Word files work.
4. #38 History: an odd old audit row shows "made a change (…)" instead of breaking the tab for good; no
   emails show (the name part of the actor label only); pages are merged by id, so "Show older" and a
   refresh can't drop or repeat lines; new migration 0017 adds an index on audit_log
   (entity_type, entity_id, id). The plan lock moved from 0017 to 0018.
5. #39 plan: only the owner can bring new people onto the board through a new step (others pick from
   people already on it): closes a way round the owner-only "add person" rule; people brought in get
   "You are on order board" and a "person added" History line; the editor sends the plan version it
   started from, and an older draft is refused (409) instead of undoing someone's newer change; a save
   with no change writes nothing; late preview answers are ignored.

Decision kept (Vineet, PR 4): anyone on the board may remove a step that hasn't started while the plan is
unlocked, and add steps with people already on the board. The owner's lock is the way to stop that.

Left for later (from the review, not bugs): R2 previews are read through the API in one piece (fine for
our file sizes; stream it if files get big); some extra database lookups per page; shared helpers for
code that is copied between the create form and the plan editor.
