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

6. After Vineet's PRs #53 and #55 (merged main, 10 Nov): two more areas, `chat` and `lead_harvester`. The
   chat WebSocket is on its own `ws_router`: a route switch needs a Request and broke the live connection
   (checked), so `chat_socket` checks the area itself and closes with 4404. `test_repo_config_files_are_valid`
   makes CI fail on a typo in `config/*.ini` (at start-up a broken file = defaults = every area on).
