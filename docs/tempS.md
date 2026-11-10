# Session notes (Nishita)

One subheading per task. Moved into the shared docs after the PR merges (see `docs/prompt.md` section 7).

---------------------------------------------------------------------------------------------------

## Phase switches for the portal, part 1: backend (branch feat/module-switches-api, 10 Nov)

1. Why: we release the portal in phases. `config/modules.ini` sets each area to `on` (everyone), `admin`
   (admins only, to try it on the live site) or `off` (nobody). Off hides; no data is deleted.

2. Areas: batches, order_boards, attendance, website_admin, analytics, alerts, audit. No switch (always on):
   Leads (website enquiries must never pile up unseen), Tasks, My day, Profile, Approvals, Manage users,
   Overview, Settings. Rule: batches needs attendance (batches go only to staff who checked in).

3. How (`backend/app/core/modules.py`): routes get `dependencies=area("...")` (404 `module_off`); whole
   routers in `router.py`, single routes in `admin.py`; files by owner in `file_service._check`; jobs by
   `@job(..., module=...)` (skipped only when off); `/auth/me` sends `modules`; approvals, Overview,
   Analytics, the alerts log and notification / email links leave out hidden areas.

4. Safety: a misspelt area or a broken rule is refused (last good settings stay, the log says why).
   `test_every_route_is_in_an_area_or_always_on` fails if a new API route has neither.

5. Tests: `backend/tests/test_modules.py`. Part 2 (screens: sidebar, "Not available yet" page, My day
   cards) is the next PR.

---------------------------------------------------------------------------------------------------

## Phase switches for the portal, part 2: screens (branch feat/module-switches-ui, 10 Nov)

1. `frontend/src/lib/modules.ts`: `canSee(me, area)` reads `me.modules` from "who am I"; `areaOfPath(path)`
   finds a page's area (same page list as `AREA_PAGES` in `backend/app/core/modules.py`: keep both in step).

2. Sidebar: a link is hidden when its area is off for the person (found from the link, no extra field). The old
   unused `soon` flag is gone. Empty groups disappear.

3. A typed-in address of a hidden page shows "Not available yet" (PortalShell). If the API answers
   `module_off` (switched off while the tab was open), `api()` tells the frame, which asks "who am I" again.

4. Shared pages: My day hides the attendance card; Overview hides the product tile and "Add product";
   Analytics hides the attendance chart and the order boards tile. Approvals already hid null sections.

5. Tests: 3 new unit tests (`frontend/tests/lib.test.mjs`); 47 pass, `tsc` clean. Not done: an e2e browser
   check (needs the app running locally; Docker was off). Follow-up for the backlog.
