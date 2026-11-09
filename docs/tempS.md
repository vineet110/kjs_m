# Session notes (Nishita)

One subheading per task. Moved into the shared docs after the PR merges (see `docs/prompt.md` section 7).



---------------------------------------------------------------------------------------------------

## Order boards browser check (branch fix/board-browser-check, 9 Nov)

Backlog R49 i. Local e2e database, backend with `STORAGE_DRIVER=local`, headless Chrome at 1280 px and 390 px,
board E2E117-1 with four uploaded test files (CSV, Excel, Word, PDF).

1. Works (no change needed):

   i.    CSV with Hindi and ₹: shown correctly (no garbled letters).
   ii.   Excel: table, "Rate (₹)" header, dates the Indian way (20-Nov-2026), second sheet tab (Hindi).
   iii.  Word: shown in a sandboxed frame (no scripts), with text, Hindi, ₹ and a table.
   iv.   PDF: shown in a frame from `/files/{id}/view` (`frame-ancestors 'self'`, `Content-Disposition: inline`).
   v.    Full screen opens (real browser full screen on a computer, covering panel on a phone), and Esc closes it.
   vi.   History tab: uploads, lock / unlock, step done, delete approvals, newest first, with times.
   vii.  People tab: owner first with an "Owner" label, each person's steps.
   viii. Plan lock: the owner locks, can still open the plan editor and save. A member sees "Plan locked by the
         owner", has no "Edit plan" button, and the server refuses their save (403 `plan_locked`). After unlocking,
         the member can save.
   ix.   Phone (390 px): every tab and every file preview fits, with no sideways scrolling.

2. Fixed (frontend): on a phone, the preview header cut the file name to "po-11…" (three buttons on the same row).
   The name now gets its own line on small screens (`FileList.tsx`).

3. Not testable by a script: Esc after clicking inside the PDF. Only a real key press makes Chrome leave its own
   full screen; the design relies on that (a key pressed inside the PDF never reaches our page).
   Checked by hand in Chrome (9 Nov): Esc closes full screen after clicking inside the PDF.

4. Backend bugs for Vineet: none found.

5. Small things, not changed:

   i.    The lock pill reads "Plan Locked By The Owner" (the pill style capitalises each word).
   ii.   For Task 3 (PR F): `api_e2e.py` fails 3 checks right after a fresh build (the page cache holds the empty
         pages for 60 s); the e2e README should say `STORAGE_DRIVER=local`; `reset_e2e_db.sh` has Vineet's own path;
         `browser_e2e.mjs` has 5 out-of-date checks.
