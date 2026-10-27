# Goal

What "done" means for Stage 1.

Changes after Fri 6 Nov 2026 go through `backlog.md` (section 7, scope requests).



---------------------------------------------------------------------------------------------------

## 1. Mission

One platform where:

   i.    importers find KJS and contact them easily,
   ii.   employees run their day (attendance, tasks, leads, orders),
   iii.  the admin sees and controls everything.

Live by Fri 11 Dec 2026.



---------------------------------------------------------------------------------------------------

## 2. What must work on go-live day

1. A visitor can

   i.    browse products in English on a fast site that Google can read,
   ii.   ask for a price sheet, spec sheet, sample or quote with one short form (remembered after the first time),
   iii.  chat with Koko,
   iv.   apply as a partner, or describe a private-label product.

   Every request becomes a lead with an owner and an SLA timer.


2. An employee can

   i.    log in, check in and out, and ask to fix a missed punch,
   ii.   switch "receiving tasks" on or off,
   iii.  receive work in batches for their categories,
   iv.   work their leads (notes, calls, outcome) before the timer runs out,
   v.    see their tasks and order-board steps, and upload files,
   vi.   see notifications.


3. The admin can

   i.    approve staff and choose their permissions,
   ii.   set auto-assign rules and import buyer lists,
   iii.  create order boards with step deadlines and alerts at 50 / 85 / 100%,
   iv.   approve file deletions and missed-punch requests in one inbox,
   v.    read the audit log (nobody can edit it),
   vi.   see team attendance and charts from real data,
   vii.  edit products, website text, offers and Koko's facts without a developer.


4. It runs safely

   i.    HTTPS through Cloudflare.
   ii.   Nightly backups, and a restore that we have actually tested.
   iii.  Logs we can search by request ID.
   iv.   Tests run on every push (CI).


Status 24 Oct: points 1, 2 and 3 are built and tested on a laptop. Point 4 is the production work.



---------------------------------------------------------------------------------------------------

## 3. How we measure success

1. [x] Every API route has an allowed and a forbidden test. (122 backend tests)

2. [x] End-to-end tests pass: visitor → form → lead with SLA; employee day; board → alert. (114 API + 38 browser checks)

3. [x] Each alert fires only once (tested).

4. [ ] Lighthouse score 90 or more on home, category and product pages (check on the real server).

5. [ ] Restore drill done: backup → fresh machine → app works.

6. [ ] KJS staff sign off after UAT.



---------------------------------------------------------------------------------------------------

## 4. In scope (Stage 1)

1. Website: home, categories, products, capability pages, contact, Koko, SEO, gated forms, offers ticker,
   WhatsApp button, partners page, private-label builder.

2. Employee portal: login and sign-up, attendance, availability, tasks, leads with SLA, batches, order boards,
   notifications, profile.

3. Admin console: staff and permissions, products, website text and offers, Koko settings, leads, approvals,
   team attendance, holidays, order boards, alerts, auto-assign, charts, audit log, settings.

4. Production: company server, backups, domain, email, file storage.



---------------------------------------------------------------------------------------------------

## 5. Not in scope (Stage 1)

1. Buyer intelligence and outreach → Stage 2 (2027).

2. Importer landing pages, quotes as PDF, partner dashboard with commissions → Stage 2.

3. Superset → after go-live, maybe.

4. Languages other than English → after go-live (the code is ready for them).

5. Payments or online checkout (KJS sells B2B by quote).



---------------------------------------------------------------------------------------------------

## 6. Our personal goals (Vineet and teammate)

1. By go-live, each of us can explain every module: tables, API, screens, tests.

2. Each of us can run the whole project on a clean PC using only the README.

3. We write in the learning log (`learning/learning-log.md`) every day.

4. Small pull requests, reviewed by the other person.



---------------------------------------------------------------------------------------------------

## 7. Change history

1. 23 Oct 2026: first draft.

2. 24 Oct 2026: updated for the 2-week plan. Partners page and private-label builder moved into Stage 1 (they are
   in the master build prompt). Success points 1–3 done.
