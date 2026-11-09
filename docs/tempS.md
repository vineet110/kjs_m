# Session notes (Nishita)

One subheading per task. Moved into the shared docs after the PR merges (see `docs/prompt.md` section 7).



---------------------------------------------------------------------------------------------------

## Frontend safety fixes (branch fix/frontend-safety, 9 Nov)

1. CR4, public error pages and time limits:

   i.    `app/global-error.tsx` (root layout crash), `[locale]/error.tsx` (a layout crash one level down),
         `(public)/error.tsx` (inside header and footer). All show "Try again", phone, WhatsApp, email
         (`components/public/ErrorPanel.tsx`).
   ii.   `(public)/not-found.tsx` + `(public)/[...rest]/page.tsx`: unknown URLs get our 404 with header and footer.
         (`globalNotFound` would need a `next.config` change, so the catch-all was used instead.)
   iii.  `serverGet`: 15 s time limit, wrapped in React `cache()` so a page, its layout and `generateMetadata`
         asking for the same path still make one API call (a `signal` turns off Next's own sharing).
   iv.   `api()`: 20 s default time limit (`DEFAULT_TIMEOUT_MS`). Koko chat 35 s (the AI may take 25 s),
         auto-assign "run now" 60 s. `upload()` keeps no limit.

2. R40, "Loading…" forever: new `components/ui/LoadError.tsx` ("Could not load. <reason> (code …)" + "Try again").
   Used on every staff page and portal component that loads data. Also where a failure used to show an empty
   list ("No contacts", "No tasks", "No files"), which looked like real data. `(admin)/error.tsx` and
   `(employee)/error.tsx` catch page crashes inside the portal.

3. LeadsTable "Log": the note box is cleared only after a successful save.

4. Tasks: Save sends only the box that changed (notes or outcome). A failed save, tick or Start shows the
   error and keeps what was typed.

5. Products edit sends only the changed fields. Hide / show and the offer switch / delete / partner status now
   show an error toast when they fail.

6. Tests: `npx tsc --noEmit` clean, `npm test` 43 pass (new: default time limit on `api()`, none on `upload()`),
   `next build` passes. The test loader needed a `cache` stub (api.ts now imports it from React).

7. For backlog, Phase 2 (not needed for go-live): offers on / off switch can undo another admin's edit.
   The switch sends the whole offer as it was when the page loaded. Fix: backend offer PATCH changes only the
   fields sent (like `ProductPatchIn`), then the switch sends only `is_active`. Decided 9 Nov: no stopgap now.

8. For Vineet (backend):

   i.    Offer PATCH (`content.py` `edit_offer`, `OfferIn`): accept only the fields sent. Phase 2 (see 7).
   ii.   User edit PATCH (`/admin/users/{id}`): same, so the edit form can send only what changed.

9. Browser check (local e2e database, headless Chrome, 9 Nov): 26 staff pages with their requests failing all
   show the error and "Try again", and "Try again" recovers. A silent server ends after 20 s ("took too long").
   Leads note and task outcome are kept when the save fails. Task save sends only `{"outcome": ...}`, product edit
   only the changed field. 404 pages work, and fit at 390 px. With the backend stopped, uncached public pages show
   our error page with the header; cached ones keep their last good copy.
   API e2e: 113 passed.

10. PR #41 review fixes:

   i.    Time limits: reads 20 s (`READ_TIMEOUT_MS`), saves 90 s (`SAVE_TIMEOUT_MS`, longer than nginx's 60 s).
         POSTs that only read or are harmless to repeat pass `safeToRepeat: true` and get the read limit:
         board plan preview (PlanEditor, new board), settings "Re-read files now", log in, log out, Koko chat.
   ii.   A save that ends without a clear answer (time-out, network cut, 502 / 504, an "OK" we can't read) gives
         code `unconfirmed`: "The server didn't confirm. It may have been saved: refresh to check before trying
         again." Before, it said "failed", so people clicked again and could save twice (a second user or punch).
   iii.  Auto-assign: Run now, category buttons and Preview show errors, are off while one runs, and reload the
         page after an error so batches already given show before anyone clicks again.
   iv.   Tests: `npm test` 44 pass. Browser: 8 new checks (a 25 s save finishes normally, a cut save says "may have
         been saved" and keeps the text, auto-assign buttons off while running, silent run ends after 90 s,
         board preview still ends after 20 s), and the 38 earlier checks pass again.
   v.    For Vineet, Phase 2: a one-time key per save (the server ignores a repeat) is the real fix for duplicates.
   vi.   Later: other save buttons (e.g. holidays, offers) can still be clicked twice quickly. Not changed in the freeze.

11. Found while testing (not caused by this PR):

   i.    Local `.env` has `STORAGE_DRIVER=r2`, so the e2e run sends its test uploads to the real R2 bucket.
         Start the e2e backend with `STORAGE_DRIVER=local`. Fix the README in Task 3 (PR F).
         3 tiny test files were uploaded on 9 Nov: `product/instant-coffee-3-in-1-stick/11e3359c5081-stick.png`,
         `product/instant-coffee-3-in-1-stick/cd7ededbfc60-spec-sheet.pdf`, `board/E2E117-1/2f91940f9ec5-po.pdf`.
   ii.   `browser_e2e.mjs` has 5 out-of-date checks ("Admin overview", "Missed a punch?", "Documents" no longer
         exist in the code; sidebar groups start closed). Fix in Task 3 (PR F).

12. `scripts/e2e/reset_e2e_db.sh` has Vineet's own path (`cd /c/VINEET_WORK/KJS_v1/backend`): it fails on
   other computers. Fix in Task 3 (PR F).



---------------------------------------------------------------------------------------------------

## E2E tests for the new features (branch test/e2e-new-features, 9 Nov)

Only `scripts/e2e/` changed. Run on the local test database (port 5433), backend with `STORAGE_DRIVER=local`.

1. `api_e2e.py`, new checks:

   i.    Lead management and contacts (PR #33): internal lead (hers from the start, phone required), source lists,
         one contact row per person, contact page, task and note on a lead, privacy (a colleague gets 404, can't add
         notes), admin sees all, admin reassigns (then the new owner can open it and the old one can't).
   ii.   Leave and shifts (PR #31): create a shift (admin only, bad times refused), assign it, it shows on the day;
         leave request, overlap and bad dates refused, approver list, approve, decide twice refused, the leave shows
         in the month; half-day leave, can't approve your own, reject with a reason.
   iii.  Order boards (PRs #35-#39): add a person (owner only, twice refused, they are told), step people and head
         (head must be on the step, a step needs someone, done steps fixed, members can't), owner and last person on
         a running step can't be removed, remove (they lose the board and its files and are told).
         File preview of CSV, Excel, Word, PDF, PNG and a fake PDF: same bytes, inline, no-store, nosniff; a real
         PDF may be framed by our pages only, everything else is sandboxed; no preview without logging in.
         History: who did what, newest first, paging back, staff only. Plan edit with the lock: a member edits when
         unlocked, an old copy is refused (409), only the owner locks, locked = member refused (403) and owner allowed.
   iv.   The configurator lead now follows its on/off switch (PR #45 made switched-off features refuse their API);
         the third website lead comes from "Get a quote".
   v.    Product lists and the sitemap are checked after the 60 s cache refresh (they failed right after a fresh build).

2. `browser_e2e.mjs`: contact page (details, notes, tasks); board previews of every type, full screen and Esc,
   History, People, lock from the board; as a member: the lock, her approved leave and her new shift; board tabs
   and previews at 390 px; the 5 out-of-date checks fixed (new headings, sidebar groups start closed).

3. `login_e2e.mjs`, `sidebar_e2e.mjs`: the admin dashboard heading is now "Live numbers" (was "Admin overview").

4. `reset_e2e_db.sh`: finds the repo's own backend folder (it had one person's path), stops on the first error,
   clears the last run's files. README: start the backend with `STORAGE_DRIVER=local` (and both database URLs).

5. Real app bugs found: none.

6. Final run on main with PRs #41-#45 (9 Nov): api 196 passed, browser 73, sidebar 25, all passing.
   `login_e2e.mjs` is unsteady: once all 20 passed (run alone after a backend restart), other runs failed
   different steps (1, 2 or 5: the button still says "Logging in…" when the check looks). My only change there is
   the heading text. Not an app bug as far as seen; needs a look after go-live (timing of the held requests, or the
   new login lockout counting from PR #44).
