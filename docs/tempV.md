# Session notes (Vineet)

One subheading per task. Moved into the shared docs after the PR merges (see `docs/prompt.md` section 7).


## Monitoring link, Phase 1: attendance feed (28 Nov, branch `feat/monitoring-link-feed`)

1. What: the feed the laptop-monitoring server polls (its CRM side is `monitering/docs/ARCHITECTURE.md` 7.3).
   `GET /api/v1/integrations/monitoring/api/employees`, `.../api/attendance/changes?since=`,
   `.../api/attendance/events?employee_id=&from=&to=`. Login is `X-Api-Key` (`MONITORING_FEED_KEY` in .env).
   Plan: `INTEGRATION_PLAN.md` v2 (next to both repos).

2. Why a new table (`attendance_events`, migration 0037) instead of reading the punches:
   i.    the monitoring server applies each event id once and never edits history, so the feed must only ever
         say in, out, in, out per person;
   ii.   a regularization edits punch times in place: from the punches it would look like a new check-in in
         the past (a ghost session: tracked while off duty).

3. Rules (`services/monitoring_link_service.py`):
   i.    check-in / check-out write an event in the same transaction as the punch;
   ii.   forgotten check-out: job `monitoring_auto_out` (any time) closes it at shift end + grace
         (`monitoring_link.ini`), max `max_shift_hours`, and tells the person. CRM attendance is NOT changed;
   iii.  a check-in while the feed is still open closes the old one first;
   iv.   a regularization only sends "close a day still open here". Moved times are not sent (known limit:
         monitoring reports keep the real punch times for that day).

4. Decisions: module `monitoring` (default off, needs attendance at least as far). Feed key check does the
   area check itself (`core/service_key.py`): `require_module` needs a logged-in person. nginx refuses
   `/api/v1/integrations/` from outside (a test checks the block). `pending`/`rejected` users are not listed:
   monitoring revokes the laptops of anyone `inactive` for good.

5. Not run yet: the DB tests (`tests/test_monitoring_link.py`). This PC had no Docker and only Python 3.13.
   Checked without a DB: imports, route-area test, nginx test, module rule, auto-out times, key + 422 checks
   over HTTP. Run `pytest tests/test_monitoring_link.py tests/test_attendance.py tests/test_modules.py` first.
   Code review (28 Nov) fixed: test_all_on_by_default, paging overlap, purge while off (own job), night shift
   after midnight, auto_out one commit per person + clock_timestamp(), employee_id check, key helper name,
   one file name (monitoring_link).

6. After merging: `alembic upgrade head` (0037). Next: Phase 2 (local contract test against the monitoring
   backend with `CRM_MODE=api`).

7. kb.md terms: attendance feed, auto-out, service key.

## Monitoring link: integration review fixes + instant push (28 Nov, same branch)

1. Integration review (both repos) found 8 issues; all fixed:
   i.    monitoring lost a new person's first check-in (event stored before the employee check) -> monitering
         branch `feat/crm-push`: unknown person = not stored, employees synced first;
   ii.   "disabled" revoked laptops for good -> we send `disabled` as it is; monitoring revokes only `exited`;
   iii.  overtime check-in closed after 60 min -> `overtime_auto_out_hours = 4`; grace now at least 15 min;
   iv.   lock check after a 35-day leave got 422 -> the range is shortened to its last 31 days;
   v.    no route between the servers -> shared Docker network `kjs_mon` (`deploy/docker-compose.monitoring.yml`,
         monitoring's compose); monitoring's nginx now closes `/api/crm/*` from outside except `/sso`;
   vi.   people at work missed if monitoring started late -> every poll also lists open check-ins (own ids);
   vii.  check-in closing a forgotten session used +16 h -> same time as the auto-out job;
   viii. cursor mixed app and DB clocks -> "now" is the DB's `clock_timestamp()`.

2. Push (Vineet: "no delay"): after any commit that wrote attendance_events or changed a person's
   name/email/branch/reporting_to/status, an SQLAlchemy `after_commit` listener starts a push
   (POST mon-api:8000/api/crm/attendance/push, /employees/push). Each push carries the person's recent events
   in order, read after the commit, so pushes arriving in any order end the same. A failed push never fails the
   punch; the 30 s poll delivers it. `.env`: MONITORING_BASE_URL, MONITORING_API_KEY. Not literally zero:
   one hop on the same VPS is a few ms; the laptop then hears it over its WebSocket.

3. Checked here: monitoring suite 47 passed (8 new push/fix tests); cross-app contract test (our payloads
   through monitoring's real endpoints) passed; DB-free checks of the CRM side passed; compose files parse.
   NOT run here: the CRM DB tests (no Postgres on this PC) -> run tests/test_monitoring_link.py first.

