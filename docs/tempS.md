# Session notes (Nishita)

One subheading per task. Moved into the shared docs after the PR merges (see `docs/prompt.md` section 7).

## Sidebar colours + "Manage employees" (branch feat/sidebar-colours)

- Done (not committed yet): Employees > Manage renamed to **Manage employees** in `SidebarNav.tsx`.
- Colour try-out page for group/link colours: https://claude.ai/artifact/XiZauuFM7jZ1EZw3EAKbWZ (style not chosen yet).
- Learned: a 500 on Chat was the local DB behind the code (at 0019, code needs 0020). Fix: `alembic upgrade head`. After every pull, check `alembic current` vs `alembic heads`.
- Dev console: the WebSocket "closed before the connection is established" warning (`lib/chat.ts:115`) is React dev mode running effects twice. Harmless.

**For backlog (small, cosmetic):** Next.js warning "Image with src Kjs.png has either width or height modified". Our `width`/`height` props don't match the logo's real size (536×136), so CSS `w-auto` changes the width. Fix = real proportions:
`PortalShell.tsx` 120×28 → 110×28 · `SiteHeader.tsx` + `SiteFooter.tsx` 140×32 → 126×32 · `employee/login/page.tsx` 160×36 → 142×36.

## Files on internal leads (branch feat/internal-lead-files)

- Done (not committed yet). Leads now use the same file system as order boards and products (`file_service.register_owner("lead", ...)` in `lead_service.py`). Anyone who can see a lead can see and add its files. Deleting goes through approval.
- "New internal lead" form: a **Files** picker that takes several files. They upload after the lead is saved; if one fails, the lead stays and the message names the file.
- Lead page (`/employee/contacts/[id]`): new **Files** tab plus a Quick action. `FileList` now takes several files at once (boards and products get this too).
- New allowed types: pptx, ppt, gif, heic, mp4, mov (`config/storage.ini` + `ini.py`). exe, html and svg are still blocked on purpose (can carry viruses or scripts). Max size is still 25 MB (nginx allows 26m).
- Tests: 3 new in `test_lead_management.py`. Full suite: 381 passed. Frontend `tsc` clean.
- Still to do: click through it in the browser.

### PR #72 review fixes + damaged-file check (13 Nov)

- All 10 review points fixed. HEIC is allowed on leads only (`ONLY_FOR` in `file_service.py`). Lead ids are cleaned (`"007"` -> `"7"`, `"²"` / huge numbers -> 403 instead of 500) through a new `clean=` option on `register_owner` (boards use it too: `str.upper`). On an unassigned lead you can see files but not upload or ask to delete.
- Frontend: files upload 3 at a time (`uploadFiles` in `FileList.tsx`), shared `uploadOne` also used for profile photos, uploader can't get stuck, leads list refreshes after a partial failure, picker turns off once the lead is saved.
- New `backend/app/services/file_check.py`: a file must really be what its name says and be whole (PDF needs `%PDF-` ... `%%EOF`, PNG needs its end marker, xlsx/docx/pptx/zip are opened and every part tested, zip bombs over 300 MB unzipped refused). Error code `file_broken`. Python's own tools only, no new package.
- Test fixtures updated to be real whole files. A fake `.pdf` (a web page) is now refused at upload instead of only sandboxed at preview.
- Tests: full suite 387 passed. Frontend `tsc` clean. `scripts/e2e/api_e2e.py` updated, not run yet.
- Next (new branch): read lead data from Excel/CSV, address field, new-column pop-up with audit log, then Tesseract for images (needs Vineet's OK for `pytesseract` + Dockerfile change).

## Fill a lead from Excel / CSV (branch feat/lead-from-file, Part A, 13 Nov)

- Built on top of `feat/internal-lead-files` (uses its `file_check`). Not committed yet.
- New `backend/app/services/lead_reader.py`: reads .xlsx / .csv into the fields of `InternalLeadIn`. Understands a table (headers on top, person picks the row, max 50) and a card ("Phone | +91 ..." per row). Loose column names ("Mobile No." = phone, "Firm" = company). Unknown columns come back as `extra` (shown as "Not saved" for now; Part B adds the pop-up).
- Endpoints: `POST /employee/leads/read-file` (nothing saved, 60 per person per hour) and `GET /employee/leads/same-person` (counts only leads you can see).
- Form: "Fill from Excel / CSV" button. Fields the file didn't have show "Not specified" (placeholder, saved as empty). The source file is attached to the lead. Before saving, if the phone/email already has leads: "Open the existing lead" or "Save as a new enquiry".
- Security: file_check, values only (no formulas), row/column/cell limits, no customer data in logs.
- Tests: 7 new in `tests/test_lead_reader.py`. Lead tests 56 passed, `tsc` clean. Browser click-through not done.
- Waiting on Vineet: `defusedxml` (safer Excel XML), migration for `extra` details (Part B), Tesseract (Part C).

### PR #74 follow-ups (13 Nov)

- PR #72 was merged then reverted (#73). PR #74 = #72 re-applied + Excel/CSV form filling.
- Vineet's answers on #74: defusedxml OK, `extra` migration OK (show as "Extra Info"), Tesseract OK, rate limit to app.ini, bulk import (each row = a lead) in a separate PR.
- Done on #74: `defusedxml==0.7.1` in both requirements files (openpyxl now reports DEFUSEDXML = True); `lead_file_reads_per_hour = 60` in `config/app.ini`.
- CodeRabbit's 6 points fixed: encrypted zips refused (not a crash), JPEG needs its end marker, same-person check asks the DB (no newest-5000 limit, follows phone/email links), lead Files tab hides Upload / Request delete when you can only look (`canRequestDelete` on FileList), Save waits while a file is read, "Save as a new enquiry" approves only the checked phone + email.
- Learned: the backend venv was made by uv (not on PATH) and had no pip; `python -m ensurepip` added it.
- Tests: 397 passed. `tsc` clean. Next PRs: Extra Info pop-up + migration, Tesseract, bulk import.

## Bulk import of leads (branch feat/lead-bulk-import, stacked on #74, 13 Nov)

- Vineet's point 5 on #74: each row of an Excel / CSV file becomes its own lead, in a separate PR.
- "Import from Excel / CSV" button on Internal leads (`components/portal/ImportLeads.tsx`). Step 1 `POST /employee/leads/import/preview`: every row read and checked, nothing saved (problems in words, duplicates marked "Already in your leads" / "Repeated in this file"). Step 2 `POST /employee/leads/import`: ticked rows saved in one transaction (all or none), assigned to the importer, audit `lead.created` per lead + one `lead.imported`.
- Limits: 500 rows (more = refused, never cut), same file checks and hourly limit as "Fill from file".
- `lead_service._internal_lead` now builds the lead for both "+ Add lead" and import. `lead_reader.read` takes `max_rows`.
- Tests: 6 new in `tests/test_lead_import.py`; lead tests 65 passed, `tsc` clean. Browser click-through not done.

## Extra Info (branch feat/lead-extra-info, stacked on #75, 13 Nov)

- Vineet's point 2 on #74 (migration approved, column `extra`, shown as "Extra Info").
- Migration `0022_lead_extra_info.py`: `leads.extra` JSONB, default `{}`. Numbered 0022 because open branches feat/firebase-auth and feat/employee-permissions already use 0021: fix `down_revision` to the newest on main before merging. Down + up tested on the test DB.
- Pop-up `components/portal/ExtraColumns.tsx`: one column at a time, Add / Add all / Reject / Reject all, hint "Choose Add to save it in Extra Info". Used by "Fill from file" (per lead) and bulk import (once per file, applied to every row). "Change" reopens it. Save waits until every column is decided. Max 30 Extra Info columns per lead.
- Audit: `lead.extra_columns` with added / rejected column names and lead ids, never the values.
- Lead page Info tab shows an "Extra Info" box.
- Tests: 4 new in `tests/test_lead_extra.py`; full suite 407 passed; `tsc` clean. Browser click-through not done.
- After pulling: `alembic upgrade head`.

## #75 follow-up on #78 (13 Nov)

- #75 had merged into `feat/lead-files-excel`, not `main` (that branch was never deleted, so GitHub didn't move it). #78 now targets `main` and carries #75 + Extra Info together.
- Fix: the file reader looked at only the first 1,001 lines, so with many empty lines in between, real rows after that were dropped without a word. Now empty rows are skipped while reading and only real rows count (`lead_reader._filled`); a safety cap of 20,000 lines (`MAX_SCAN`) means "maybe more", so bulk import refuses instead of cutting.
- Test: `test_empty_lines_do_not_hide_rows` (fails on the old code). Full suite 408 passed.

## Spinner on buttons that wait for the backend (branch fix/button-spinners, 14 Nov)

- Review point 4 "no loader in the backend": pages already showed the spinner while loading (`ui/Loading.tsx`), but most buttons only changed text ("Saving…"). Only Login and Logout had the spinner.
- Fix: the existing `ui/Spinner` added inside 12 buttons the same way Login does it: Save lead, Fill from Excel / CSV, Import leads + Choose file, Upload files, User form Submit, Save permissions, Save plan, New chat, Auto-assign Run now, public Enquiry and Partner forms. No new dependency, no backend change.
- Overlap check: every button uses `.btn` (inline-flex + gap-2), so the spinner sits beside the text. Open PR #77 also edits `UserForm.tsx`, but other lines (132 vs 17/211), so no conflict.
- `tsc` clean, `npm test` passes. Browser click-through not done.
- CodeRabbit on #79 (after the quick-view fix): "Forget my details" could be clicked while the quick send was running, and the finished send then saved the details back. Forget is now off while sending, like "Change details".
- Review fix (CodeRabbit, 2 points): (1) Auto-assign: `busy` was shared by Preview, category toggles and Run now, so Preview made Run now spin. Now `doing` says which action runs; `busy = doing !== null` still blocks double clicks. Run now spins only for a run, Preview for a preview. (2) Enquiry quick view: Send switched to `sending`, which hid the quick view and put the spinner on the full form's button. Now `fromQuick` keeps the quick view while sending, with the spinner on its own button (disabled). On a failed quick send it still falls back to the full form with the error (unchanged).

## Complaints: "Report a problem" (branch feat/complaints, 14 Nov)

- Point 5: staff report a bug, issue or suggestion from any portal page. Saved in the database only. No email for now (not set up yet).
- Header button "Report a problem" (next to the bell) opens a form: type, title (at least 3 words), description (at least 15 words), optional screenshot (png / jpg / webp). Live word counters; Send stays off until both rules pass. The same rules are checked again on the server.
- Added by themselves: the page path (`window.location.pathname`, never a full link) and the date and time (`created_at` from the server).
- Admins (`staff.approve`) see them on the new page `/admin/complaints` (sidebar: Reports & settings > Complaints), newest first, with screenshot links.
- Backend: table `complaints` (migration `0026_complaints.py`), `complaint_service.py`, route `/api/v1/complaints` (POST any logged-in staff, GET `staff.approve`). Always on, no module switch. Audit `complaint.filed` names the kind and page, never the text.
- Screenshot = a normal file, owner_type `complaint`, uploaded after the complaint is saved (existing `/files`). Only the person who filed it may add one; they and admins may see it. If only the screenshot fails, the report is still saved and a message says so.
- `config/complaints.ini`: `developer_email` (empty, NOT USED YET). When email is ready, send each new complaint to it.
- Migration number: PR #77 (feat/firebase-auth) has 0024 and 0025, so this is 0026 with down_revision 0023. Whichever merges second changes its down_revision to the other's last one. Tell Vineet.
- Guesses (move to backlog section 3 at fold time): admins = `staff.approve` read them; no status (open / done) yet; no rate limit; list shows the newest 200 only.
- Tests: `tests/test_complaints.py` (7: allowed + forbidden users, word rules, bad kind / link refused, screenshot access). Migration down + up tested on the test DB. Full backend suite 436 passed (added `/api/v1/complaints` to ALWAYS_ON in test_modules.py). `tsc` clean, `npm test` passes. Browser click-through not done.
