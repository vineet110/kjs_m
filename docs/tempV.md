# Session notes (Vineet)

One subheading per task. Moved into the shared docs after the PR merges (see `docs/prompt.md` section 7).


## 18 Nov: Website insights (PR #100, branch feat/site-insights)

1. What it is

   i.    Reports now has two tabs: Website insights (opens first) and Business (the old charts).

   ii.   Website insights shows what website visitors view, search and click: visits per day, most viewed
         products, top searches, searches that found nothing, most clicked buttons, product -> enquiry funnel,
         where visitors came from, mobile or computer, most viewed pages. Ranges: 7, 30 or 90 days.

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

   iv.   Old rows are deleted after 180 days. Background jobs are off, so the delete runs when events arrive
         or the report opens (at most every 6 hours), not as a job.

3. Privacy

   i.    No cookie, no IP saved, no name. A random visit id lives in sessionStorage (gone when the tab closes).

   ii.   Phone numbers (7+ digits) and emails typed into search are saved as `***`. Only the referring
         site's name is kept (Google, example.org), never the full link.

   iii.  Logged-in staff (session cookie) and robots (browser name) are not counted.

4. Guesses (move to backlog.md section 3 after merging)

   i.    Anonymous counting with no cookie needs no consent banner under the DPDP Act; one line in the
         privacy notice is enough. KJS (or a lawyer) to confirm.

   ii.   "Visit" = one browser tab session. The same person in two tabs counts as two visits.

   iii.  Searches are recorded after a 1.5 s typing pause, so "cof" then "coffee" can be two searches.

5. Known limits

   i.    Ad blockers may block the tracker: real numbers are a little higher (the screen says so).

   ii.   Superset: later (decision D6). The data is in Postgres, so Superset can read `site_events` as is.

   iii.  Settles backlog R33 (frequently searched, option B): the data now exists; showing "popular
         searches" on the website itself is still a separate decision.

6. Tests: `backend/tests/test_site_insights.py` (18), `frontend/tests/lib.test.mjs` insights tests (5),
   `test_config.py` public config keys updated.

7. New terms for kb.md: tracker, visit id, sessionStorage, referrer, funnel, keepalive (fetch), robot / bot.

8. After merging: run `alembic upgrade head` (adds `site_events`).
