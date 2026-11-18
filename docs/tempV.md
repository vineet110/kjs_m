# Session notes (Vineet)

One subheading per task. Moved into the shared docs after the PR merges (see `docs/prompt.md` section 7).


## Next.js 16.4.3 -> 16.4.6 (18 Nov)

1. Fixes two moderate advisories (GHSA-mfr8-8qww-v76h, GHSA-vc7v-qv4w-wrv8: cache leaks across root params
   with `'use cache'` / `unstable_cache()`). We use neither, so we were not exposed. Patch release, no code
   change. Backlog R90 done.

2. `npm audit` still lists high alerts, for the backlog at the next fold:

   i.    Firebase 13 (via `@grpc/grpc-js` and firestore): npm's "fix" is a downgrade to Firebase 9 (wrong).
         Check whether a newer Firebase fixes it; we only use Firebase Auth in the browser.
   ii.   Tailwind 3's build tools (chokidar, micromatch, picomatch, fast-glob): build and dev only, not on
         the live site. Fix is Tailwind 4 (a major upgrade, own PR).


## Go-live review + fixes (18 Nov, PR #95, branch fix/golive-readiness)

1. Review of the basic release (dashboard, leads, employees, public site, reports and settings): no security
   hole, no broken main flow. Hosting issues on Vercel/Render ignored (we move to the VPS).

2. Fixed in #95 (no migration, no new package):

   i.    Only an admin creates accounts (`POST /admin/users`): an approver could skip the approval step.
   ii.   `/admin/stats`: lead numbers only with `leads.view_all` (null = tiles hidden).
   iii.  Lead lists: "Load more". New keys `config/leads.ini` `employee_page_size` (200) and `admin_page_size`
         (500), sent in `me.limits`. Employees no longer lose older unassigned leads after 200.
   iv.   Ticking a lead task you can't change now says why (was a silent undo).
   v.    Holidays no longer behind the attendance switch (lead SLA deadlines need them).
   vi.   Reports labels: "(all time)" on the charts, "Leads that went late" (was "SLA alerts sent").
   vii.  Sitemap skips hidden categories (Tea) and their products.
   viii. Forbidden tests: another person's lead (status, note, handover), `/assign/import`, `/assign/staff/{id}/categories`.

3. Dropped on purpose: resetting `escalation_level` on reopen. The resolve timer counts from `created_at`,
   so a reopened old lead would alert at once, every reopen. Stays backlog R4 (needs a product decision).

4. For VPS day (no code yet):

   i.    nginx `connect-src`: add `https://identitytoolkit.googleapis.com https://securetoken.googleapis.com`
         (Firebase login), and the final image domain (R48).
   ii.   Jobs on for that server only (`KJS__APP__JOBS_ENABLED=true`). Before that, clean or close old test
         leads, or the first SLA check sends a pile of alerts.
   iii.  Modules off for the basic release: chat, order_boards, batches, lead_harvester. Attendance: off or admin.
   iv.   Secrets rotation (B9, B14, R50.ii, R61 Firebase key), Firebase authorized domain, backups + restore drill.
   v.    Check every `KJS__*` env value is in bounds (one bad value = all ini values fall back to code defaults).

5. Decisions for Vineet / KJS (add to backlog at the next fold):

   i.    `require_verified_email` off: admins confirm each sign-up, or SMTP on the VPS first (R68).
   ii.   Koko on Groq free tier: 2-3 messages a minute for the whole site (R52). Paid tier or Koko off.
   iii.  No leads export anywhere. New feature if reports need it.
   iv.   A disabled employee's leads stay assigned to them; no bulk reassign.
   v.    Non-coffee text hard-coded (home page line 66, layout title, private-label, search placeholder,
         JSON-LD, Koko prompt); Admin > Website "Products: page title/description" are never read. For the
         teammate on the dynamic UI.

6. Smaller follow-ups found (backlog later): contacts list capped at 5,000; `/leads/import` (JSON) has no rate
   limit; no `openGraph` / `metadataBase`; audit page shows newest 500 only; `staff.approve` also opens Reports,
   Settings and Complaints; dead stub `auto_assign_service.py`; logout without the CSRF header.

7. Vineet's decisions (18 Nov), for `backlog.md` at the next fold:

   i.    Email checks stay off for launch; an admin approves every sign-up (R68 option a).
   ii.   Koko stays on Groq's free tier for launch; replace later (R52).
   iii.  Launch without a leads export.
   iv.   Non-coffee text: ignored for now (the dynamic UI work will cover it).
   v.    NEW backlog item, before go-live (after UAT): when an employee is disabled, their open leads
         (new / contacted) go back to unassigned, with a note on each lead and one audit row; closed leads
         keep their owner. Place: `auth_service.set_status`, next to `return_open_batch`. Until then an
         admin reassigns by hand ("Any owner" filter in All Enquiries). Auto-assign left as it is.
