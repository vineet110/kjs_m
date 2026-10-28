# Backlog

Everything that is blocking us, waiting for a decision, waiting for KJS, or postponed.

When something is solved, change its status to ✅ with the date. Do not delete it.

Status marks:

   🔴  blocking now
   🟠  blocks something coming soon
   🟢  not urgent
   ✅  done


Sections in this file:

   1. Blockers
   2. Decisions (from management)
   3. Assumptions to review (things we guessed)
   4. Inputs needed from KJS
   5. Missing documents
   6. Later (Stage 2)
   7. Scope requests log
   8. Review findings left for later (25 Oct senior review)



---------------------------------------------------------------------------------------------------

## 1. Blockers

B1. GitHub repo  ✅ 23 Oct

   i.    Repo github.com/vineet110/kjs_m is checked out in `KJS_v1`.


B2. Dev tools on this PC  🟠

   i.    Installed: Node 24, npm 11, uv, git, Docker 29.8 + WSL 2, gh (logged in as vineet110), ffmpeg.
   ii.   Still to do: `uv python install 3.12`.
   iii.  `make` is optional.


B3. Company server, IT contact, SSH access  🟠

   i.    Unknown. Needed for production.
   ii.   Owner: manager / IT.


B4. WhatsApp Business (Meta) verification  🟠

   i.    Has it been started? It can take 1 to 2 weeks.
   ii.   Needed for WhatsApp alerts.


B5. Anthropic API key with a monthly limit  🟢

   i.    Only needed if we choose Claude Haiku for Koko (see D4). Groq works today.


B6. Domain and DNS for kjsindia.com  🟠

   i.    Needed for Cloudflare, HTTPS, and email (SPF / DKIM).


B7. Docker Desktop licence  ✅ 23 Oct

   i.    KJS fits the free tier (under 250 staff and under $10M revenue).


B8. Koko AI key  🟢

   i.    We use Groq for development, behind a provider switch (D4).


B9. Secrets were pasted in chat  🟢 (must be done before go-live)

   i.    The Groq key and the Neon password.
   ii.   Rotate (replace) both before go-live or before sharing the repo with more people.


B10. Neon database is far away  🟠

   i.    It is in us-east-2 (Ohio, USA). Each API call takes about 2.3 seconds from India.
   ii.   Fix: create a new Neon project in Singapore and move to it.
   iii.  Do not turn off `pool_pre_ping` to make it faster: that broke the first request after Neon sleeps (24 Oct).


B11. Commit the work  ✅ 24 Oct

   i.    23 Oct work pushed to branch `kjs_v`.
   ii.   24 Oct work (all of Phase 1) committed and pushed to `kjs_v` as `3a88c65`.
   iii.  25 Oct: merged into `main` (pull request #2, CI green).
   iv.   25 Oct: production setup pushed to `kjs_v` as `ebfe12a`, not merged yet.


B12. Windows blocked the project's Python  ✅ CLOSED 26 Oct (Smart App Control turned off by Vineet)

   Now: use `.venvScriptspython` normally again (README commands). The notes below are kept for history.

   i.    25 Oct: "An Application Control policy has blocked this file" when running `backend\.venv\Scripts\python.exe`.
   ii.   Cause: Windows Smart App Control is ON. It blocks programs it doesn't trust, and the small
         `python.exe` inside `.venv` is unsigned.
   iii.  The backend already running keeps working. Starting it again will fail.
   iv.   Workaround used while it was on (base Python 3.12 from uv + our packages):

         $env:PYTHONPATH = ".venv\Lib\site-packages"
         & "$env:APPDATA\uv\python\cpython-3.12-windows-x86_64-none\python.exe" -m uvicorn app.main:app --reload --port 8000

   v.    Fix chosen 26 Oct: Vineet turned Smart App Control off (Windows Security > App & browser control).
         It cannot be turned back on without resetting Windows. Microsoft Defender antivirus is still on.
   vi.   Installing packages also needs the base Python (done 25 Oct for the FastAPI update):

         uv pip install --python "$env:APPDATA\uv\python\cpython-3.12-windows-x86_64-none\python.exe" --target .venv\Lib\site-packages -r requirements.txt

   vii.  Running the tests without the venv Python (fast, about 40 s): inside Docker, on the test database's
         own network. Command in the main README, "Tests" step.


B13. Next.js 14 was out of long-term support  ✅ CLOSED 26 Oct (upgraded to Next.js 16)

   i.    Upgraded on branch `next16`: Next 14.2.35 → 16.4.3, React 18 → 19.3.1, next-intl 3 → 4.14.9.
   ii.   Code changes: `params` is now a Promise (6 pages + layout await it), `middleware.ts` renamed `proxy.ts`,
         `next lint` script removed (Next 16 dropped it; we never had ESLint).
   iii.  Same day: removed 14 packages no code used (6 radix-ui, axios, class-variance-authority, clsx,
         date-fns, lucide-react, recharts, tailwind-merge, zod). `lucide-react` blocked React 19.
   iv.   Tested: tsc, production build, dev mode (Turbopack), 114 API e2e checks, 38 real-Chrome checks,
         production Docker image (starts, runs as `node`).
   v.    Merged into `main` 27 Oct (pull request #4, CI green). Rollback: revert that merge on GitHub.


B15. Tailwind 3 audit warning  🟢 (low)

   i.    `npm audit` reports 3 moderate issues in Tailwind 3's CSS parser (slow on crafted CSS).
   ii.   It only runs at build time on our own CSS, never on visitor input. Already there before the upgrade.
   iii.  Fix = Tailwind 4 (a bigger CSS-config change). Plan with a later UI clean-up.


B16. next-intl is installed but not really used yet  🟢 (decided 27 Oct: keep)

   i.    No page calls a translation function; all text is written in the pages. `messages/en.json` is unused.
   ii.   next-intl 4.5+ brings `@swc/core` + `@parcel/watcher` (about 12 MB). Never in the production build
         or Docker image; their install scripts are blocked.
   iii.  Kept on purpose: Stage 2 languages (AR, ES, FR, 2027) will use it. Revisit when planning Stage 2:
         use it properly, or remove it (about 30 min: `proxy.ts` does the `/en` rewrite itself).


B14. Secrets and passwords seen in chat  🔴 before go-live (adds to B9)

   i.    The first admin password (`FIRST_ADMIN_PASSWORD`) was also shown in chat on 25 Oct.
   ii.   Before go-live: new Groq key, new Neon password, new admin password. Production gets its own
         new secrets anyway (`deploy/.env`).



---------------------------------------------------------------------------------------------------

## 2. Decisions (from management)

D1. Next.js instead of React + Vite?  ✅ 23 Oct

   i.    Yes, Next.js (better for Google search).


D2. Website languages at launch  ✅ 23 Oct

   i.    English only. next-intl stays, so languages can be added later.


D3. When does the visitor form appear?  ✅ 23 Oct

   i.    Only on actions (price sheet, spec sheet, sample, quote). Browsing is free.
   ii.   General rule: anything that blocks us moves to a later release.


D4. Which AI model for Koko, and what monthly budget?  🟢

   i.    Today: Groq, model `openai/gpt-oss-120b`, behind the `LLM_PROVIDER` setting.
   ii.   Before go-live: test Groq vs Claude Haiku on 30 real questions, then decide the budget.
   iii.  Early test (23 Oct): 3 Groq models all followed the rules once the rules were placed after the facts.


D5. User roles  ✅ 23 Oct

   i.    Admin and employee only. No manager role.
   ii.   Routes check permissions. A role is only a default set of permissions.
   iii.  The admin can give one employee extra permissions.


D6. Charts: Superset or our own?  ✅ 23 Oct

   i.    Our own simple charts first, from real database data only. Never fake numbers.
   ii.   Superset maybe after go-live.


D7. Domain: replace www.kjsindia.com or use a subdomain?  🟢 postponed

   i.    Decide at deployment.


D8. Timeline  ✅ 23 Oct (updated 24 Oct)

   i.    Go-live Fri 11 Dec 2026. Latest acceptable Fri 18 Dec.
   ii.   24 Oct: new plan, Phase 1 in 2 weeks (26 Oct to 7 Nov), then production. List: `checklist.md`.


D9. What is a "record" in an auto-assign batch?  🟠

   i.    We built it as: rows of imported Excel / CSV buyer lists. See A1.


D10. For auto-assign, must the employee be checked in?  🟢

   i.    Built as: checked in AND "receiving tasks" switched on. See A2.


D11. A step runs late: keep the final deadline or move it?  🟢

   i.    Built as: keep the deadline. See A10.


D12. OTP (one-time code) on the visitor form?  🟢

   i.    No. Validation + rate limit + hidden spam field instead. Turnstile in production.


D13. WhatsApp alerts to personal numbers?  🟢

   i.    Email first. WhatsApp only for staff who opt in, after Meta approval.


D14. Payroll export format  🟢

   i.    Plain Excel unless KJS sends a template.


D15. Database during development  ✅ 23 Oct

   i.    Neon free tier now. Move to the company server later with `pg_dump` / `pg_restore`.


D16. Where do images and files go?  ✅ 23 Oct

   i.    Never in the database. Cloudflare R2 in production, a local folder in development.
   ii.   The code is ready for both (`STORAGE_DRIVER=local` or `r2`).


D17. Folder names  🟢

   i.    Keep `frontend/` and `backend/` (the old plan said `apps/web` and `services/api`). See A39.


D18. Does KJS expect Stage 2 features on 11 Dec?  🟠

   i.    The demo video (23 Oct) shows things that are Stage 2 in our plan:
         a.  Buyer database, data sources, nightly scraping
         b.  Partner commissions dashboard
         c.  8 website languages
         d.  Public USD prices with a currency converter
   ii.   Things from the video we did build: per-employee permissions, SLA timers (20 min / 1 hour),
         partner application page, WhatsApp button, audit log.
   iii.  Not built yet from the video: email verification on staff sign-up, daily work log (task + time).
   iv.   We must tell KJS clearly that Stage 2 is 2027.


D19. Public USD prices, or price sheet by form?  🟠

   i.    Built: price sheet by form, no prices shown (A23). Easy to add prices once KJS gives them (I3).


D20. May an admin approve their OWN requests?  🟠 (from the 25 Oct review)

   i.    Today: a normal approver can never approve their own missed-punch or file-delete request.
         An admin can (it is still written in the audit log).
   ii.   Why it matters: an admin could quietly fix their own attendance.
   iii.  Option a: keep it (simple, fine if there is only one admin).
   iv.   Option b: admins also need a second person (needs at least 2 people who can approve).


D21. Sign-up says "this email already has an account"  🟢 (from the 25 Oct review)

   i.    That message lets a stranger test whether an email works at KJS.
   ii.   It is now rate-limited (5 sign-ups per hour per IP), so mass testing is slow.
   iii.  Option: always answer "if this email is new, an admin will review it". Safer, but a person who
         forgot they signed up gets no hint. Recommendation: keep as is for staff sign-up.



---------------------------------------------------------------------------------------------------

## 3. Assumptions to review (things we guessed)

Where a requirement was not clear, we built the most sensible version and wrote it here, so work did not stop.

How to use this list:

   i.    Read each one.
   ii.   If it is right, mark it ✅.
   iii.  If it is wrong, write the correction under it, and we change the code.
   iv.   Many values are in `config/*.ini` and can be changed without code.

Look at these first: A1, A4, A5, A10, A47. For production: A53, A55.


### Auto-assign

A1. What a "record" is  🟠

   i.    A record = one row of a buyer list imported from Excel or CSV.
   ii.   Columns: company, contact, email, phone, country, website, category, notes.
   iii.  Each record belongs to one product category.
   iv.   Website and Koko leads are NOT put in batches. They go to the leads list.
   v.    Where: `assign_service.py`


A2. Who gets a batch  🟠

   i.    Only staff who are checked in, have "receiving tasks" on, and have at least one category.
   ii.   One open batch per person at a time.
   iii.  The person with the fewest batches today goes first.
   iv.   Where: `assign_service.py`, `config/assign.ini`


A3. Batch size and timing  🟠

   i.    20 records per batch.
   ii.   Max 3 batches per person per day.
   iii.  Only between 09:30 and 18:30 IST. "Run now" works at any time.
   iv.   Where: `config/assign.ini`


### Attendance

A4. Shift times  🟠

   i.    One shift for everyone: 09:30 to 18:30 IST.
   ii.   Check-in more than 15 minutes after 09:30 counts as late.
   iii.  Where: `config/app.ini`


A17. Who can approve a missed punch  🟢

   i.    Not the same person who asked for it (admins excepted).
   ii.   Where: `attendance_service.py`


### Leads and SLA

A5. The SLA clock runs only in working hours  🟠

   i.    Working hours = shift time, Monday to Saturday, minus holidays.
   ii.   Example: a lead on Saturday night is due Monday morning.
   iii.  Where: `lead_service.py`


A6. What counts as "responded"  🟢

   i.    Logging a call or an email on a new lead stops the 20-minute timer.
   ii.   Where: `lead_service.py`


A7. Who gets SLA alerts  🟠

   i.    There is no manager role (D5), so alerts go to everyone with `leads.view_all`, plus the lead's owner.
   ii.   Where: `lead_service.py`


A8. Who sees which leads  🟢

   i.    Employees see their own leads and unassigned ones.
   ii.   Whoever acts first on an unassigned lead becomes its owner.
   iii.  Where: `lead_service.py`


A9. Lead outcomes  🟢

   i.    Quote sent, sample sent, order won, not interested, no reply, spam.
   ii.   Where: `LeadsTable.tsx`


### Order boards

A10. How steps start and end  🟠

   i.    Step 1 starts when the board is created.
   ii.   The next step starts when the previous one is marked done.
   iii.  A late step does NOT move the final deadline (D11).
   iv.   Where: `board_service.py`


A11. Splitting the days between steps  🟢

   i.    Split by %: normal rounding, leftover days go to the last step.
   ii.   "Fixed days" mode may run past the deadline. It warns, it does not refuse.
   iii.  Where: `board_service.py`


A12. Board code format  🟢

   i.    Letters / numbers, a dash, a number. Example: `ABC117-3`.
   ii.   Where: `board_service.py`


A13. Board alerts  🟢

   i.    Once per threshold: 50%, 85%, 100%.
   ii.   If a step jumps past two thresholds in one day, only the higher alert is sent.
   iii.  Alerts go to the step's members and to people with `boards.manage`.
   iv.   Where: `board_service.py`, `config/alerts.ini`


A14. Board tasks  🟢

   i.    When a step starts, each member of that step gets every task template of the step.
   ii.   They are due at the step's planned end.
   iii.  Where: `board_service.py`


### Files

A15. Deleting a file  🟠

   i.    Needs approval by someone with `files.approve`.
   ii.   Once approved, the file is removed from storage for good.
   iii.  Where: `file_service.py`


A16. Upload limits  🟢

   i.    Max 25 MB.
   ii.   Allowed: pdf, png, jpg, webp, xlsx, xls, docx, doc, csv, txt, zip.
   iii.  Where: `config/storage.ini`


### Notifications, permissions, login

A18. Email for every notification  🟠

   i.    Every notification is also sent by email. People can turn email off in their Profile.
   ii.   No email provider yet: emails are skipped (and logged) until SMTP details are in `.env`.
   iii.  Where: `notification_service.py`


A19. New permission names  🟢

   i.    `attendance.manage`, `tasks.assign`, `boards.manage`, `assign.manage`, `files.approve`, `content.edit`
   ii.   Where: `permissions.py`


A20. Login lock  🟢

   i.    10 wrong passwords for one email in 15 minutes blocks more tries for a while.
   ii.   Where: `rate_limit.py`


A21. When background jobs run  🟢

   i.    08:00 to 21:00 IST, Monday to Saturday only, so the free Neon database can sleep at night.
   ii.   Where: `config/app.ini`


A33. New staff  🟢

   i.    Staff sign up themselves and wait for admin approval.
   ii.   A new employee gets only `leads.view` until the admin ticks more.
   iii.  Where: `auth_service.py`, `permissions.py`


A34. How long staff stay logged in  🟢

   i.    7 days, then log in again.
   ii.   Where: `.env` (`SESSION_DAYS`)


A35. Passwords  🟢

   i.    At least 10 characters.
   ii.   Stored with scrypt (built into Python) instead of Argon2 (that would be a new package).
   iii.  Where: `security.py`


A36. Email check  🟢

   i.    A simple pattern instead of the `email-validator` package (no new dependency).
   ii.   Where: `schemas/common.py`


### Website and Koko

A22. Product categories  🟠

   i.    4 categories: Coffee, Tea, Health drinks, Confectionery (from kjsindia.com).
   ii.   The real list comes with I2.
   iii.  Where: `app/seed.py`


A23. No prices anywhere  🟠

   i.    No prices on the site until KJS gives price bands (I3).
   ii.   Product pages show "send enquiry" instead.


A24. Company facts  🟠

   i.    Address, phone +91 97037 35666, contact@kjsindia.com, certifications (FSSC, ISO 9001, ISO 14001),
         clients (Nestlé, Unilever, Mayora), capabilities.
   ii.   Copied from kjsindia.com. Not checked with KJS yet.
   iii.  Where: `frontend/src/lib/site.ts`, `backend/app/knowledge/kjs_facts.md`


A25. Text, logo and photos  🟢

   i.    Taken from kjsindia.com as-is (21 files). Official brand files will replace them (I1).
   ii.   Where: `frontend/public/images/kjs/`


A26. Stick-pack fill range  🟠

   i.    Shown as 0.9 to 3 g because the website says so. The demo video says 18 g (see I9).
   ii.   Where: `kjs_facts.md`, capability pages


A27. Koko rules  🟠

   i.    Answers only from the facts file and the product list.
   ii.   Never gives prices, lead times, capacities or volumes.
   iii.  Never says "yes we can".
   iv.   Replies in the visitor's language, about 100 words max.
   v.    Offers the contact form when the visitor sounds like a buyer.
   vi.   Where: `koko_service.py`


A28. Koko model  🟢

   i.    `openai/gpt-oss-120b` on Groq. Full 30-question test still to do (D4).
   ii.   Where: `.env`


A29. When a Koko chat becomes a lead  🟢

   i.    Only when the visitor fills the small form inside the chat.
   ii.   The lead gets an AI summary of the chat, so staff don't have to read it all.


A30. Enquiry form fields  🟠

   i.    Required: name, email or phone, consent tick (DPDP).
   ii.   Optional: company, country, buyer type, quantity.
   iii.  No OTP (D12).
   iv.   Where: `schemas/lead.py`, `EnquiryForm.tsx`


A31. Spam protection  🟠

   i.    A hidden honeypot field.
   ii.   Max 5 enquiries and 40 Koko messages per IP per hour.
   iii.  Turnstile later (needs a Cloudflare account).
   iv.   Where: `rate_limit.py`, `config/app.ini`


A32. Visitor IPs  🟢

   i.    Never stored. Only a one-way hash (privacy, DPDP).
   ii.   Where: `security.py`


A37. Website cache  🟢

   i.    Public pages are cached for 60 seconds. An admin change shows on the site within a minute.
   ii.   Where: `frontend/src/lib/api.ts`


A38. No `/en` in website addresses  🟢

   i.    `/products`, not `/en/products`, while we are English-only.
   ii.   Where: `proxy.ts` (was `middleware.ts` before Next 16)


A43. Site address in sitemap  🟠

   i.    Uses a placeholder address until the domain is decided (D7).
   ii.   Where: `frontend/src/app/sitemap.ts`


A44. Visitor forms remembered  🟠

   i.    After the first form, the visitor's details are kept in their own browser only (localStorage).
   ii.   The next price sheet / spec / sample / quote is one click ("Send as Omar").
   iii.  Each click still creates its own lead.
   iv.   Where: `EnquiryForm.tsx`


A45. Visitor IP behind our proxies  🟠

   i.    The API trusts `CF-Connecting-IP` or the last `X-Forwarded-For` value only when the request comes
         from our own machine or network.
   ii.   Production MUST run behind Cloudflare + nginx, and nginx must set
         `proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;`
   iii.  Otherwise rate limits can be dodged.
   iv.   Where: `deps.py`


A46. Private-label builder choices  🟠

   i.    Product (private-label ones), recipe notes, pack (stick / sachet / pouch / jar / bulk),
         quantity per month (under 50k, 50k–200k, 200k–1M, over 1M), market.
   ii.   It sends a lead. No price is shown (I3).
   iii.  Where: `Configurator.tsx`


A47. Partner page text  🔴 before go-live

   i.    We wrote this text ourselves, including "commission on confirmed orders" and "your own referral link".
   ii.   KJS must confirm the partner offer before go-live.
   iii.  Where: `partners/page.tsx`


A48. Private-label page "4 steps"  🟠

   i.    Tell us → samples and recipe → packaging and approvals → production and dispatch.
   ii.   Written by us from the site text.
   iii.  Where: `private-label/page.tsx`


A49. Koko chats are saved  🟠

   i.    Anonymous: a random chat id and a hashed IP. Staff read them in Admin > Koko.
   ii.   Needs a line in the privacy notice.
   iii.  Where: `content_service.py`


A50. Who sees partner applications  🟢

   i.    People with `leads.view_all`. New applications notify them.
   ii.   Where: `content_service.py`


A51. Hidden products  🟢

   i.    They stay in the admin list and can be shown again.
   ii.   The web address (slug) never changes when a product is renamed.
   iii.  Where: `catalog_service.py`


A52. Editable website texts  🟢

   i.    Home headline and text, Google title and description for home and products, contact intro,
         partners intro, Koko facts.
   ii.   Defaults = what the site shows today.
   iii.  Where: `content_service.py`


### Production setup (25 Oct)

A53. Database on the company server  🟠

   i.    Production runs its own Postgres 17 container (the `db` service), not Neon.
   ii.   If KJS prefers a hosted database, `deploy/README.md` section 6 shows the switch.
   iii.  Where: `deploy/docker-compose.prod.yml`


A54. Uploaded files in production  🟠

   i.    Default is a Docker volume on the server (`STORAGE_DRIVER=local`), included in the nightly backup.
   ii.   Switch to Cloudflare R2 once KJS gives keys (D16).
   iii.  Where: `deploy/.env.production.example`


A55. Backups  🟠

   i.    Every night at 02:30, database + files, kept 14 days, in `/srv/kjs/backups` on the server.
   ii.   No off-site copy yet: needs a decision with KJS IT (for example rclone to R2, a new tool).
   iii.  Where: `deploy/backup.sh`, `deploy/README.md`


A56. Who reaches nginx  🟢

   i.    nginx listens only on 127.0.0.1:8080. The internet reaches it only through Cloudflare Tunnel.
   ii.   Because of that, the `CF-Connecting-IP` header can be trusted. If someone ever opens nginx to the
         internet directly, visitors could fake that header and dodge the rate limit.
   iii.  Where: `deploy/docker-compose.prod.yml`, `deploy/nginx/default.conf`


A57. HTTPS and HSTS are done by Cloudflare  🟢

   i.    nginx inside the server speaks plain HTTP. Cloudflare does HTTPS ("Full" mode) and HSTS.
   ii.   Where: `deploy/README.md` section 2 step 6


A58. Deploy keeps 3 image versions; migrations run on every deploy  🟢

   i.    `deploy.sh` backs up, runs `alembic upgrade head`, restarts, and waits for the health check.
   ii.   Rolling back the code does not undo a migration: restore the backup taken just before.
   iii.  Where: `deploy/deploy.sh`


### From the 25 Oct security review

A59. A late step's alerts  🟠

   i.    If step 1 runs late, step 2 starts late and may at once show "out of time" (100% alert),
         because its time is measured against the plan, not from when it really started.
   ii.   We kept this: the order really is behind plan (deadline stays, D11). If KJS prefers the next step to
         get a fresh clock, it's a small change in `used_pct`.
   iii.  Where: `board_service.py`


A60. Koko daily cost cap  🟠

   i.    At most 2000 AI calls per day for all visitors together. After that Koko asks people to use the
         form or WhatsApp, until midnight IST.
   ii.   Where: `config/koko.ini` (`daily_limit`)


A61. New login and sign-up limits  🟢

   i.    Login: 30 tries per IP per 15 minutes (plus the old 10 wrong passwords per email).
         A locked email is refused even with the right password, for 15 minutes.
   ii.   Sign-up: 5 per IP per hour.
   iii.  Where: `core/rate_limit.py`


A62. Who may approve staff  🟢

   i.    Someone with `staff.approve` who is not an admin can only approve NEW sign-ups, can only give
         permissions they have themselves, and can never change an admin or themselves.
   ii.   Only an admin can change an already active account.
   iii.  Where: `auth_service.py`


A63. Emails  🟢

   i.    Sent at any time of day (also nights and Sundays), not only in job hours.
   ii.   A failed email is tried 3 times, then marked failed.
   iii.  Where: `notification_service.py`


A64. "Remember me" on visitor forms  🟢

   i.    Ticked by default, with a note to untick it on a shared computer, and a "Forget my details" link.
   ii.   Where: `EnquiryForm.tsx`


A65. Only product files can be public  🟢

   i.    Order-board files can never be downloadable without login. Files of a hidden product stop being public.
   ii.   Requesting a file delete now needs the right to upload to that place (not only to see it).
   iii.  Where: `file_service.py`


A66. Product image path must be a plain local path  🟢

   i.    Only `/images/...`-style paths from our `public/` folder. No `https://`, no `?`, no `..`.
   ii.   Why: Next.js 16 refuses image paths with `?` (broken photo), and an outside website's image
         crashes the product page (500). Found in the Next 16 review, 26 Oct.
   iii.  Outside photos: upload them (Products > photos) instead. Where: `schemas/catalog.py`


A67. A missed-punch request with no check-out keeps the real check-out  🟢

   i.    "I forgot to punch in" requests usually leave check-out empty. Approving now keeps the real
         check-out instead of erasing it. If the new check-in would be after that check-out, approval is refused.
   ii.   Where: `attendance_service.decide`


A68. "Check out" after midnight closes yesterday only for a real night shift  🟢

   i.    Only if yesterday's check-in was less than 16 hours ago. Otherwise "Please check in first",
         and the forgotten day is fixed with a missed-punch request (no more 33-hour days).
   ii.   Where: `attendance_service.check_out` (MAX_SHIFT)


A69. Lead status rules  🟢

   i.    Setting the same status again is refused ("already closed").
   ii.   An answered lead can't go back to "new". "Reopen" now sets it to "contacted".
   iii.  Leaving "closed" clears the resolved time, so the resolve timer runs again.
   iv.   Where: `lead_service.set_status`, portal Reopen button (`LeadsTable.tsx`)


A70. Finished things stay finished  🟢

   i.    A finished batch can't be edited or reopened (it also blocked new batches for that person).
   ii.   An order board can be finished only once. Finishing closes its open tasks (marked done, with a
         note "board finished as Cancelled/…") so they don't show as overdue forever.
   iii.  Where: `assign_service.update_record`, `board_service.finish`


A71. Order-board step time counts only days that are over  🟢

   i.    Today is still available: a 1-day step is 0% on its day and "out of time" the next day.
         Before, every step looked late on its last planned day (false alarms).
   ii.   Where: `board_service.used_pct`


A72. Buyer imports: max 5000 rows, and known buyers are skipped  🟢

   i.    A bigger file is refused with "split it" (before, rows after 5000 were silently dropped).
   ii.   Same company + email as an already imported record = skipped as "already imported", so the
         same company is never called twice from two lists.
   iii.  Where: `assign_service.read_rows`, `import_records`


A73. Product list taken from the catalogue PDF "KJS INDIA products.pdf" (27 Oct)  🟠

   i.    58 product families, 156 item numbers, all confectionery. Where: `backend/app/seed_catalogue.py`
   ii.   One product per brand family; flavours and sizes are listed as items inside the description.
         Families with clearly different packs (e.g. Gofrey Cocoa / Milk / Black & White) are separate products.
   iii.  Pages 13–16 of the PDF repeat as pages 21–24: added once.
   iv.   Only the English lines are used. Brand names keep their printed spelling (Kremalı, Susamlı).
   v.    No price and no MOQ in the PDF, so none on the site ("On request"). No product marked best seller.


A74. Product pictures cut out of the catalogue PDF  🟠

   i.    Background removed by a script and every pack placed on the same light background with a shadow.
         Two fixed by hand (Gofrey Milk, Gofrey Black & White). Where: `frontend/public/images/products/`
   ii.   Good enough for the demo. Replace with KJS's original pack files when they send them (I13).


A75. New categories added next to the old ones  🟢

   i.    Chocolate bars, Wafers, Marshmallow & cakes, Biscuits. Coffee, Tea, Health drinks, Confectionery stay
         (shown as "made to order" while they have no products).


A76. Catalogue phone number differs from the site  🔴 before go-live

   i.    The PDF's back page says +91 83416 59999; the site (`lib/site.ts`) says +91 97037 35666.
         Site unchanged until KJS confirms (I14).


A77. Home page facts taken from the catalogue PDF  🟢

   i.    "Two units, more than 250 products", partners list, stick-pack fills 0.9–3 g (page 2 of the PDF).


### Code and setup

A39. Folder names  🟢

   i.    Kept `frontend/` and `backend/` (D17).


A40. Packages removed  🟢

   i.    Heavy packages from the starter repo (AI / ML, scraping, Superset client, boto3 and more) were removed
         from `requirements.txt` until a feature needs them.
   ii.   `structlog` and `apscheduler` removed too. Python's own logging and our own job loop replace them.


A41. Background jobs inside the API  🟢

   i.    No separate worker or scheduler containers. Fine for one server.
   ii.   Split them out only if we ever run several servers.
   iii.  Where: `app/jobs/runner.py`


A42. Dashboard numbers  🟢

   i.    Only from the database. No data = shows 0. Never sample numbers (D6).



---------------------------------------------------------------------------------------------------

## 4. Inputs needed from KJS

I1. Logo, brand colours, factory and product photos, first offers for the ticker  🟠

I2. Product list: category, pack formats, minimum order, certifications, best sellers, HS code  🟠

   i.    27 Oct: catalogue PDF received and added (A73). Still missing: MOQ, best sellers, HS codes.

I3. Price bands (per product, pack and quantity, USD per 1,000)  🟢

   i.    Until then the private-label builder shows no price.

I4. Employee list (name, email, phone, shift, categories) and holiday list 2026–27  🟠

I5. FAQs and policies for Koko  🟢

I6. Task templates for each order-board step, and who receives alerts  🟢

I7. 2 or 3 real requirement files (Excel / PDF / Word)  🟢

I8. Summary of the WhatsApp demo video  ✅ 23 Oct (now inside D18)

I9. Stick-pack fill range  🟠

   i.    kjsindia.com says 0.9 to 3 g. 3-in-1 coffee sticks are usually about 18 g (the video shows 18 g).
   ii.   Koko repeats the website text until KJS confirms.

I10. SMTP details (email account for sending notifications)  🟠

I11. Buyer lists (Excel), one product category per row  🟠

I12. Confirm the partner programme offer (A47)  🔴 before go-live

I13. Original pack images (PNG/JPG per item) to replace the ones cut from the PDF (A74)  🟢

I14. Correct sales phone number: catalogue vs website (A76)  🔴 before go-live



---------------------------------------------------------------------------------------------------

## 5. Missing documents

M1. `research_01.pdf` (source feasibility, trials T1–T10). Matters for Stage 2.  🟢

M2. `research_01_implementation_plan.pdf`. Matters for Stage 2.  🟢

M3. Client's original notes.  🟢



---------------------------------------------------------------------------------------------------

## 6. Later (Stage 2, 2027)

1. Buyer Intelligence: data sources, pipeline, review, scoring

2. Outreach: mailboxes, email sequences, approvals

3. Importer landing pages (one page per country / product)

4. Samples and quotes (PDF), partner dashboard and commissions

5. Superset analytics (D6)

6. More website languages, including Arabic (right-to-left) (D2)

7. OTP on visitor forms (D12)

8. From the demo video: email verification on staff sign-up, daily work log (task + time)



---------------------------------------------------------------------------------------------------

## 7. Scope requests log

Every new "can we also..." goes here with the date and who asked, before anyone builds it.

1. 23 Oct. Neon setup prompt: install Neon CLI, Neon Auth, Neon object storage.

   i.    From: Neon onboarding.
   ii.   Decision: skipped. It conflicts with our plan (FastAPI owns login, files go to R2). We use only the connection string.


2. 23 Oct. From the demo video: email verification on staff sign-up, daily work log, Koko → WhatsApp hand-off.

   i.    From: demo video.
   ii.   Decision: WhatsApp button built (24 Oct). The other two moved to Later (section 6).



---------------------------------------------------------------------------------------------------

## 8. Review findings left for later (25 Oct senior review)

The 25 Oct review found about 50 points. Every high and medium one was fixed and tested (see `memory.md`
session log). These were left on purpose; none is dangerous today.

R1. Koko history is sent by the browser  🟢

   i.    A visitor can still put fake "Koko said" turns in the middle of the chat (the start and end are checked).
   ii.   Proper fix: keep the chat history on the server, keyed by a server-made chat id.


R2. Limits and the Koko budget live in memory  🟢

   i.    They reset when the API restarts and would not be shared by several API processes (A41).
   ii.   Fine for one server. Move them to the database or Cloudflare rules if we ever scale out.


R3. SLA due times are worked out live  🟢

   i.    Changing `respond_minutes` or adding a holiday changes past "on time" numbers in the charts.
   ii.   Fix: save the due times when the lead is created.


R4. Re-opening a lead to "new" keeps its old escalation level  🟢

   i.    It shows "overdue" at once and doesn't alert again.


R5. Some lists make one database query per row (N+1)  🟢

   i.    Board detail, board list, analytics. Fine at today's size; fix when boards grow past ~100.


R6. Portal pages don't check permissions in the browser  🟢

   i.    An employee can open an /admin page; it shows no data (the API refuses). Hide it in the menu (done)
         and show a clear "not allowed" page instead (to do).
   ii.   When a session ends during a click, an error shows instead of sending the person to the login page.


R7. The backend container receives every secret in `.env`  🟢

   i.    Including the tunnel token it doesn't need. Fix: a separate env file per service.


R8. Supply chain hardening  🟢

   i.    CI actions pinned by version tag, not by commit SHA. Docker images pinned by tag, not by digest.


R9. Uploads are checked by file name only  🟢

   i.    A file named .pdf is trusted to be a PDF. Files are served with `nosniff` and a sandbox, so a fake
         file can't run as our site. Fix later: check the first bytes ("magic bytes").


R10. CSP allows inline scripts  🟢

   i.    Next.js (14 and 16) needs `'unsafe-inline'`. Moving to nonces (per-request random tokens) is stronger.


R11. Backups: failure alerts, off-site copy, encryption  🟠 (with KJS IT)

   i.    A failed nightly backup only writes to `backup.log`. Nobody is told.
   ii.   No off-site copy yet (A55). It should be encrypted before it leaves the server.


R12. Failed logins are only in the app log, not in the audit log  🟢

   i.    Searchable by request id in the logs; add to the audit log only if KJS asks for it.



---------------------------------------------------------------------------------------------------

## 9. Production-readiness review (27 Oct): fixed, and what's left

Three independent reviews (server behaviour, data correctness, security). Security: no blockers.
Everything below "Fixed" has a test in `backend/tests/test_prod_readiness.py`.


1. Fixed (branch `fix/prod-readiness`)

   i.    Must fix:
         a.  nginx kept old container addresses after a deploy (502 until restart). Now it looks them up
             every 10 s, and `deploy.sh` reloads nginx. Tested with a real container swap.
         b.  Approving a missed-punch request erased the real check-out (A67).
         c.  A typo in `config/logging.ini` could stop all background jobs silently. Bad levels are now
             refused, the loop can't die, and `/api/health/ready` fails if jobs stop.

   ii.   Should fix:
         a.  `staff.approve` could turn disabled accounts back on (only admins now).
         b.  A stranger could keep the admin locked out (the lock is now per email + network).
         c.  Email login didn't check the mail server's certificate. Port 465 supported.
         d.  A slow or down mail server stalled every job; now one connection per batch, one try when down,
             a 2-minute budget, and visitor text is marked as such in staff emails.
         e.  Customer data in database error logs (hidden now, tracebacks masked).
         f.  Random 502s from nginx/app keep-alive mismatch.
         g.  Rate-limit memory could grow forever (swept every minute now).
         h.  Long name + email broke every action of that user (audit label cut to fit).
         i.  Board steps looked late a day early (A71). Finished boards / batches (A70). Lead status rules (A69).
         j.  Imports over 5000 rows silently cut (A72).

   iii.  Smaller ones: `/openapi.json` off in production; unsafe CORS refused at start; only real duplicates
         give 409 (other database errors are 500, so bugs show); 500 answers carry the request id; graceful
         shutdown (25 s); big uploads only on the two upload addresses; product files only for real products;
         board file codes in any case; dates must carry a time zone; task fields can't be set to null;
         one pending missed-punch request per day (migration 0011); public photos cached for an hour and
         streamed from disk; storage errors handled + a job that removes files whose delete failed;
         AI calls stop after 25 s total; SLA-breach count = leads, not notifications; board list capped;
         admin leads list has paging (`?offset=500`); checklist ticks audited; logs keep about 2 weeks.


2. Left for later (low risk)

R13. Sign-up confirms that an email has a staff account  🟢 (decision D21)

   i.    Limited to 5 tries per network per hour. Also: sign-up doesn't prove the person owns the email;
         the approver checks the name. Decide with D21.


R14. No idle timeout on sessions  🟢

   i.    A session lasts 7 days even if unused. Fine for office PCs; add "log out after 8 h idle" if KJS wants it.


R15. A 500 error's stack trace is logged twice  🟢

   i.    Once by us (masked), once by uvicorn. Only log volume; turn off uvicorn's copy if logs get big.


R16. Background jobs run one after another  🟢

   i.    A slow job (up to 5 min) delays the others. Emails now stop after 2 minutes, so at most a short delay.


---------------------------------------------------------------------------------------------------

## 10. PR #6 review follow-ups (28 Oct): for a separate PR

R17. Carousel pauses only on mouse hover  🟢

   i.    Also pause on keyboard focus and for "reduce motion" users; a slide change can take focus away
         from "Explore the range". Where: `components/public/home/HeroCarousel.tsx`


R18. Quick view copies the enquiry modal's overlay  🟢

   i.    Make one shared Modal (portal, Escape, backdrop click) for the quick view and EnquiryButton.


R19. Product items stored as text in the description  🟠

   i.    Item numbers and pack sizes are read with a strict pattern ("• Item 801: 25 g, 24 pieces per box,
         6 per case"). If an admin writes it differently, the items silently disappear from the site.
   ii.   Plan a proper items column or table (migration, admin form, API). Where: `lib/catalogue.ts`,
         `app/seed_catalogue.py`


R20. image_path is only checked in the frontend  ✅ CLOSED 28 Oct (not a problem)

   i.    Validate ProductIn.image_path in the API, so bad paths are refused when saved (today `imageOf` hides them).
   ii.   Closed: the API already checks it (`schemas/catalog.py`, pattern on ProductIn.image_path).
         `imageOf` could shrink to `p.image_path || null`; kept for rows saved before that check (A66).


R21. Progress bar keeps running after a failed page change  🟢

   i.    It stops only when the URL changes; a navigation that fails or is cancelled leaves it on for up to
         10 s. Where: `components/public/NavigationProgress.tsx`


R22. Windows line breaks break the summary  🟢

   i.    `summary()` splits on "\n\n" only; a description pasted with "\r\n" keeps the whole item list in
         the summary. Normalise line breaks first. Where: `frontend/src/lib/catalogue.ts`


R23. Enquiry list text has no length limit  🟢

   i.    20 products with long names or many items could still pass 4000 characters with the buyer's note.
         Trim the list text (or cap its length). Where: `ProductExplorer.tsx` (listMessage)


R24. Carousel picture keys use the image path  🟢

   i.    Two products with the same picture would give two React elements the same key. Use the product slug.
         Where: `HeroCarousel.tsx`
