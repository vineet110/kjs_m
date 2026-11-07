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
