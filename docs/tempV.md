# Session notes (Vineet)

One subheading per task. Moved into the shared docs after the PR merges (see `docs/prompt.md` section 7).


## 18 Nov: Website insights (PR #100, branch feat/site-insights)

1. What it is

   i.    Reports now has two tabs: Website insights (opens first) and Business (the old charts).

   ii.   Website insights shows what website visitors view, search and click: visits per day, most viewed
         products, top searches, searches that found nothing, most clicked buttons, where visitors came from,
         mobile or computer, most viewed pages. Ranges: 7, 30 or 90 whole days (IST, from midnight).

   iii.  8 buttons are counted: add to enquiry, spec sheet, price sheet, WhatsApp, call, enquiry sent,
         configurator, sample / quote. Call and WhatsApp are found by their links (tel:, wa.me), so every
         phone or WhatsApp link on the site counts without a tag.

2. How it works

   i.    The website's `SiteTracker` (public layout) collects events in the browser and sends them every 10
         seconds, and when the tab is hidden, to `POST /api/v1/public/insights/events` (no login).

   ii.   Saved in `site_events` (migration 0031). The report: `GET /api/v1/admin/site-insights?days=30`.

   iii.  Settings: `config/site_insights.ini` (days kept, ranges, list sizes, send timing, search pause,
         buttons, robot words). Switch: `modules.ini` `site_insights` (needs `analytics`). Permission:
         `insights.view` (admins have it; an employee can be given it).

   iv.   Old rows are deleted after 180 days, at most every 6 hours: by a job (any time, even with the area
         off), once when the API starts (jobs are off in app.ini now), and when events arrive or the report
         opens. A failed delete is logged and tried again; it never fails a visitor's send.

   v.    Only known pages are saved: `pages` in site_insights.ini, plus real product and category pages.
         Any other address is saved as "other" (it could carry an email). A new website page: add it there.

   vi.   Rate limits: per visit (20 a minute) and per network (600 a minute, mobile networks share one
         address). Over a limit, events are dropped quietly (204).

   vii.  Sources: each visit counts once, under the site of its first page. Direct is always shown.

3. Privacy

   i.    No cookie, no IP saved. A random visit id lives in sessionStorage (gone when the tab closes).
         Search words are kept as typed (only phone numbers and emails hidden), so a typed name could be saved:
         the screen says "No cookies or IP addresses", not "no names".

   ii.   Phone numbers (7+ digits) and emails typed into search are saved as `***`. The browser sends only
         the referring site's address, and only its name is kept (Google, example.org).

   iii.  Logged-in staff (session cookie) and robots (browser name) are not counted.

4. Guesses (move to backlog.md section 3 after merging)

   i.    Anonymous counting with no cookie needs no consent banner under the DPDP Act; one line in the
         privacy notice is enough. KJS (or a lawyer) to confirm.

   ii.   "Visit" = one browser tab session. The same person in two tabs counts as two visits.

   iii.  Searches are recorded after a 1.5 s typing pause, so "cof" then "coffee" can be two searches.
         A search cleared before the pause is not recorded.

   iv.   The "product -> enquiry" funnel was removed (review): its 3 steps were not linked, so a step could be
         bigger than the one before. The same numbers are in "Pages viewed" and "Most clicked buttons".

5. Known limits

   i.    Ad blockers may block the tracker: real numbers are a little higher (the screen says so).

   ii.   Superset: later (decision D6). The data is in Postgres, so Superset can read `site_events` as is.

   iii.  Settles backlog R33 (frequently searched, option B): the data now exists; showing "popular
         searches" on the website itself is still a separate decision.

6. Tests: `backend/tests/test_site_insights.py` (24), `frontend/tests/lib.test.mjs` insights tests (8),
   `test_config.py` public config keys and insights off, `test_modules.py` site_insights off by default.

7a. Reviews (our code review: 10, CodeRabbit: 27). Fixed all but:

   i.    Linked funnel: dropped with the panel (Vineet, 18 Nov).

   ii.   Chart values without a mouse (accessibility): for backlog. It is the same for the Business charts,
         so one small PR for all charts later.

7. New terms for kb.md: tracker, visit id, sessionStorage, referrer, funnel, keepalive (fetch), robot / bot.

8. After merging: run `alembic upgrade head` (adds `site_events`).
