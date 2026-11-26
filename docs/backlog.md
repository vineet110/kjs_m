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
   9. Production-readiness review
   10. PR #6 review follow-ups
   11. Speed
   12. Home page ideas waiting for a decision
   13. Whole-repo code review (29 Oct)
   14 to 24: images, follow-ups by date, security, tooling, scaling, config per feature
   25. Go-live review follow-ups (18 Nov)



---------------------------------------------------------------------------------------------------

## 1. Blockers

B1. GitHub repo  ✅ 23 Oct

   i.    Repo github.com/vineet110/kjs_m is checked out in `KJS_v1`.


B2. Dev tools on this PC  🟠

   i.    Installed: Node 24, npm 11, uv, git, Docker 29.8 + WSL 2, gh (logged in as vineet110), ffmpeg.
   ii.   Still to do: `uv python install 3.12`.
   iii.  `make` is optional.


B3. Company server, IT contact, SSH access  ✅ CLOSED 23 Nov (Hostinger VPS, `memory.md` decision 62)

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
   iii.  28 Oct: the password of the new Singapore Neon project was also pasted in chat. Reset it in Neon
         (Roles > neondb_owner), update both `.env` files (v1 and v2), send it to Nishita privately.


B10. Neon database is far away  ✅ 28 Oct

   i.    It is in us-east-2 (Ohio, USA). Each API call takes about 2.3 seconds from India.
   ii.   Fix: create a new Neon project in Singapore and move to it.
   iii.  Do not turn off `pool_pre_ping` to make it faster: that broke the first request after Neon sleeps (24 Oct).
   iv.   Done 28 Oct: new Neon project in Singapore (aws-ap-southeast-1). Migrations 0001–0011, `app.seed` and
         `app.seed_catalogue` run on it. v1 and v2 `.env` both point to it (old US lines kept as comments).
         One database round trip from India is now about 70–180 ms (was about 560 ms).
   v.    The old US project is no longer used. Delete it in Neon once nobody needs its test data.


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
   iii.  26 Nov: go-live moved to **Tue 1 Dec 2026** (Vineet). Plan and progress: Vineet's goLive.md (local).


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


A80. Uploaded product photos: 1600 px is enough  🟠 (planned, R43)

   i.    Photos are shrunk to at most 1600 px on the longest side when uploaded.
   ii.   Change it if KJS wants to zoom in on photos.


A81. Only the small photo is kept  🟠 (planned, R43)

   i.    The full-size original is not stored. If KJS wants originals, keep both (more storage).


A82. A hidden product's photos may show for up to 1 hour  🟠 (planned, R44)

   i.    Photos are cached for 1 hour, so hiding a product takes up to an hour to hide its photos too.


A83. Internal leads need no consent tick box  🟠 (check with KJS)

   i.    A lead a staff member types in has no visitor consent box: their conversation with the buyer counts
         as consent. KJS should confirm.


A84. Contacts match on the full phone number  🟢

   i.    Old numbers saved without a country code (`9876543210`) don't join the same number saved with +91.
         All forms now save the code, so this only affects old rows.



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

A53. Database on the production server  ✅ (Hostinger VPS, `memory.md` decision 62)

   i.    Production runs its own Postgres 17 container (the `db` service), not Neon.
   ii.   If KJS prefers a hosted database, `deploy/README.md` section 6 shows the switch.
   iii.  Where: `deploy/docker-compose.prod.yml`


A54. Uploaded files in production  🟠

   i.    (UPDATED 9 Nov) Production uses Cloudflare R2 (`STORAGE_DRIVER=r2`, private bucket `kjs-prod-files`).
         Uploads are copied every night to the backup bucket `kjs-bkp-prod` (`memory.md` decision 39).
   ii.   `local` (a Docker volume, in the nightly archive) still works if R2 is ever dropped.
   iii.  Where: `deploy/.env.production.example`, `deploy/.env.backup.example`


A55. Backups  🟠

   i.    Every night at 02:30, database + files, kept 14 days, in `/srv/kjs/backups` on the server.
   ii.   ✅ Off-site copy since 9 Nov: encrypted, to R2 `kjs-bkp-prod`, kept 30 days (decision 39). No new tool.
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


A78. Night-shift regularization: a "check-out was the next day" tick box  🟢  (guess, 29 Oct)

   i.    Suggested fix for `codeReview.md` CR14: the employee ticks the box instead of the system
         guessing a night shift from the times. Not built yet.
   ii.   To confirm with HR before building: is a tick box OK for staff, or should night shifts be
         set per person?


A79. Should regularization requests be limited to the last 30 days?  🟢  (guess, 30 Oct)

   i.    Today an employee can ask to correct any past day (`codeReview.md` CR24 iii). Confirm with HR.


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
### Order boards, file preview and site pictures (6–8 Nov)

A85. `boards.manage` can do everything a board's owner can  🟢

   i.    Admins and managers stay in control of every board. The owner can't be removed, and changing the owner
         isn't possible yet.


A86. Closed tasks are marked done with a note  🟢

   i.    There is no "cancelled" status. Removing someone, taking them off a step or removing a step marks their
         open tasks done with "[Closed: why]". Done steps keep their people (who did the work).


A87. The person who asks to delete a file isn't notified about their own request  🟢


A88. File preview limits  🟢

   i.    Up to 10 MB, 1000 rows and 50 columns; bigger: Download. Excel formulas show the result saved in the
         file (Excel and Google Sheets save it). Everyone on a board reads its History.


A89. Plan editor limits  🟢

   i.    Checklists and task lists of existing steps can't be edited (only for new steps). Renaming a running step
         doesn't rename the tasks already given. Changing % / days keeps the typed numbers until fixed.
   ii.   Anyone on the board may remove a step that hasn't started while unlocked (Vineet's decision): the
         owner's lock stops that.


A90. Site pictures on R2  🟠

   i.    `r2.dev` is for testing only (Cloudflare slows it). The copies in `frontend/public/` stay as a fallback
         for about a week. A new or changed picture must be uploaded with a NEW file name (Cloudflare caches).
         The 5 videos in `images/kjs/video/` aren't used anywhere.
A91. Deleted files stay in the off-site backup for 30 days  🟢 (Vineet decided, 9 Nov)

   i.    An approved delete removes the file from the app at once; the copy in `kjs-bkp-prod` stays 30 days,
         then goes for good. Normal for backups; check with KJS that this is fine under DPDP.


A92. Koko's catalogue card  🟢 (Nishita, PR #50, 9 Nov)

   i.    Only on product and category pages, on Koko's first real reply, up to 6 products: the product being
         viewed first, then best sellers and offers, then one of each kind. Built from the database, not the AI.
   ii.   Products for the AI are picked by page and keywords (max 8), not embeddings: enough for 72 products.
         Embeddings (pgvector, a new dependency) only when the facts outgrow this (`memory.md` decision 45).


### KJS Chat (10 Nov, PR #55)

A93. Who manages a chat  🟢

   i.    Channel: only the owner renames, archives, adds and removes people.
   ii.   Group chat: any member adds people and renames; only the owner removes others and archives.
         A group needs at least 2 other people (one person = a DM).
   iii.  DM: no changes at all. Anyone can create a channel.
   iv.   No admin override yet: admins manage only their own chats.


A94. Leaving a chat  🟢

   i.    The last owner leaves: the longest-standing member becomes owner.
   ii.   The last person leaves: the chat is archived (read-only).


A95. Public channels can't be browsed or joined yet  🟢

   i.    You see only chats you are in. `is_private` is stored for a later "browse channels" page.


A96. Keeping and deleting messages  🟠 (ask KJS)

   i.    Messages are kept forever.
   ii.   People delete only their own; the text is wiped and "message deleted" shows (the row stays).


A97. Mentions and unread counts  🟢

   i.    A mention notifies even in a muted chat (bell + email, like Teams).
   ii.   Editing a message notifies only the people newly mentioned.
   iii.  Muted chats don't count in the sidebar total.


A98. Sending limit: 30 messages a minute per person  🟢


A99. A disabled person stays in their chats  🟢

   i.    Their live tabs close at once and they can't log in; removing them would break their DMs.


### Complaints (14 Nov, PR #80)

A100. Who reads complaints: people with `staff.approve` (admins)  🟢


A101. No status (open / done) on a complaint yet  🟢


A102. No rate limit on filing complaints  🟢 (only logged-in staff can file)


A103. The complaints page lists the newest 200 only  🟢


### Website insights (18 Nov, PR #100)

A104. No consent banner for Website insights  🟠 KJS (or a lawyer) to confirm

   i.    No cookie, no IP saved, only known pages and the referring site's name: we think one line in the privacy
         notice is enough under the DPDP Act. Search words are kept as typed (phone numbers and emails hidden).


A105. A "visit" is one browser tab  🟢

   i.    A random id in sessionStorage, gone when the tab closes. One person in two tabs = two visits.


A106. A search is recorded after a 1.5 s typing pause  🟢

   i.    "cof" then "coffee" can be two searches; a search cleared before the pause is not recorded.


A107. Ad blockers may block the tracker  🟢

   i.    Real numbers are a little higher than the report shows; the screen says so.


### Home page refresh (19 Nov, PRs #103-#107)

A108. Pop-up times are counted from page load  🟢

   i.    `popup_times` 5, 8, 11, 15, 17, 25 s, then the cycle repeats (30, 33, ...). Max 20 per visit, one at a
         time on phones (`site_ui.ini`).


A109. The offer form closes itself after 14 s untouched  🟢

   i.    Warning 4 s before ("about to slip away"); never while the visitor is typing or hovering.


A110. Partner logos are copies from Vineet's folder  🟠 KJS to confirm the partners are OK being shown

   i.    Nestlé, Unilever, Mayora, Dr. Reddy's. The folder also has Nestlé Health Science and CCL: not shown
         until Vineet says so.


A111. Pop-up activity lines are true  🟠 KJS

   i.    The admin types them; the site shows "2 hours ago" from the time entered. No buyer names or company
         details.









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



I15. Real branch list for the User Creation Form  🟢

   i.    Branch is free text for now, with "Main Branch" suggested.


I16. Can admins read private chats (DMs)?  🔴 before chat goes live

   i.    A privacy question: get the answer in writing. Built as "no".


I17. Web scraping: government site list and Stage 1 or Stage 2 (D18)  🟠

   i.    D18 says nightly scraping is Stage 2 (2027), but KJS's demo video shows it.
   ii.   Ask for the list of sites. Use open data (data.gov.in) or RSS first; names and phone numbers are
         personal data (DPDP).



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

   27 Nov: fix in PR #124 (a reopen starts a new resolve timer; needs Vineet's OK on that decision). Not merged yet: mark ✅ when it is.

   i.    It shows "overdue" at once and doesn't alert again.
   ii.   18 Nov (go-live review): a plain reset was dropped. The resolve timer counts from `created_at`, so a
         reopened old lead would alert at once, on every reopen. Needs a product decision first: should a reopen
         start a new resolve timer?


R5. Some lists make one database query per row (N+1)  🟢

   i.    Board detail, board list, analytics. Fine at today's size; fix when boards grow past ~100.


R6. Portal pages don't check permissions in the browser  🟢

   i.    An employee can open an /admin page; it shows no data (the API refuses). Hide it in the menu (done)
         and show a clear "not allowed" page instead (to do).
   ii.   When a session ends during a click, an error shows instead of sending the person to the login page.


R7. The backend container receives every secret in `.env`  ✅ fixed (PR #43, 9 Nov: decision 41)

   i.    Including the tunnel token it doesn't need. Fix: a separate env file per service. Also includes
         the superuser password: see `codeReview.md` CR11 for the plan and rollout order.


R8. Supply chain hardening  🟢

   i.    CI actions pinned by version tag, not by commit SHA. Docker images pinned by tag, not by digest.


R9. Uploads are checked by file name only  🟢

   i.    A file named .pdf is trusted to be a PDF. Files are served with `nosniff` and a sandbox, so a fake
         file can't run as our site. Fix later: check the first bytes ("magic bytes").


R10. CSP allows inline scripts  🟢

   i.    Next.js (14 and 16) needs `'unsafe-inline'`. Moving to nonces (per-request random tokens) is stronger.


R11. Backups: failure alerts, off-site copy, encryption  🟠 (with KJS IT)

   27 Nov: i: failure alerts in PR #115. Not merged yet: mark ✅ when it is.

   i.    A failed nightly backup only writes to `backup.log`. Nobody is told.
   ii.   ✅ Off-site copy, encrypted (PR #42, 9 Nov). Still open: i (nobody is told when a backup fails: R50).


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
             Only partly fixed: the any-network counter can still lock the admin out, see `codeReview.md` CR5.
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

   27 Nov: fix in PR #138 (products.items + Admin Items box, migration 0036; design OK'd by Vineet). Not merged yet: mark ✅ when it is.

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


R25. Koko button shows on top of the quick view  🟢

   i.    The quick view uses `z-50`, the same as KokoChatWidget, which comes later on the page, so Koko's button
         sits over the backdrop. Quick fix: `z-[60]` like EnquiryButton; the shared Modal (R18) fixes it for good.
         Where: `ProductExplorer.tsx` (quick view)


R26. Progress bar runs on download links  🟢

   i.    A same-site file link (`/api/v1/public/files/...`) starts the bar; the page doesn't change, so it runs
         for the full 10 s. Skip links under `/api/`, or add `data-no-progress`. Where: `NavigationProgress.tsx`


R27. Several products share one SEO description  🟢

   i.    The chocolate bars that share the `BAR` text (Pacho, Paleyo, Philo, Banchetto, Ranch) all publish the
         same meta description. Add the product name or its first item. Where: `products/[slug]/page.tsx`


R28. Featured product slugs are written in several places  🟢

   i.    `POPULAR_FALLBACK`, the three `pick([...])` lists and `PACKS` in loading.tsx all list slugs by hand.
         Keep them in one constant. Where: `(home)/page.tsx`, `(home)/loading.tsx`


R29. Enquiry list kept in two places after sending  ✅ FIXED 29 Oct (branch kjs_n2)

   i.    `onListSent` empties localStorage but keeps `list` in state until the window closes. Clear both together.
         Where: `ProductExplorer.tsx`
   ii.   Follow-up (PR #9 third review, 29 Oct): a send removes only what the open form showed (frozen list);
         products added meanwhile stay.


---------------------------------------------------------------------------------------------------

## 11. Speed (28 Oct, after the move to Singapore)

R30. Session check is slow for one query  🟢

   i.    `GET /auth/me` takes about 0.5–0.7 s, but runs one query and a database round trip is about 80 ms.
         Login takes 2–3 s (scrypt is slow on purpose; the rest is database trips).
   ii.   Guess, not yet measured: each request makes several round trips (pool_pre_ping check, BEGIN, prepare
         + run, because the statement cache is off for the pooler, ROLLBACK). Every API call pays this.
   iii.  First step: turn on SQL logging, count the round trips of one `/auth/me`. Keep `pool_pre_ping` (B10.iii).
         Where: `backend/app/core/database.py`, `backend/app/core/deps.py`


---------------------------------------------------------------------------------------------------

## 12. Home page ideas waiting for a decision (29 Oct)

R31. Deals strip ("up to 15% off", like Alibaba)  🟠 needs KJS

   i.    We have no prices or discounts from KJS (I3), so a discount on the site would be a made-up offer.
   ii.   Proposal: show only offers an admin enters (Admin > Website, offers exist already); hidden when none.
   iii.  (3 Nov, PR #16) Built per product: an optional offer % (1 to 90) in Admin > Products shows "Up to X% OFF".
         Still needs KJS: an offer is a business promise like a price, so KJS must approve each one before
         staff set it.


R32. Best sellers row  🟠 needs KJS

   i.    The "best seller" tick box exists per product, but which products sell best is a business fact (I2).
   ii.   Proposal: label it "Featured" until KJS confirms, or KJS / Vineet tick the real best sellers.
   iii.  (3 Nov, PR #16) The "Best sellers" row is built: it shows only ticked products and is hidden until any are
         ticked. Still needs KJS to say which products really sell best before anyone ticks them on the live site.


R33. Frequently searched  🟢 needs a decision (the data exists since 18 Nov)

   i.    The site does not record searches. A: "Popular searches" picked by the admin (frontend only).
         B: record anonymous search words and show the top ones (backend change, new table).
   ii.   18 Nov (PR #100): searches are now recorded for Reports > Website insights (decision 60 in
         `memory.md`). Showing "popular searches" on the website itself is still this open decision.


---------------------------------------------------------------------------------------------------


R34. Home cards and grids: tidy-ups from Vineet's PR #9 review  🟢 later (not bugs)

   i.    RecommendedProducts uses many refs (shown, pending, fade): a small reducer might be clearer.
   ii.   HomeProductCard sits next to ProductCard: the two could be merged.
   iii.  The grid markup is copied in `products/page.tsx` and `categories/[slug]/page.tsx`: a shared
         ProductGrid would remove the copy.
   iv.   (Vineet, fifth review) the duplicate card components were added in PR #9: merge them here.


---------------------------------------------------------------------------------------------------


R35. Reveal: watch an outer box, animate an inner one  🟢 later (not a bug)

   i.    The repeat cards hide only when more than 40px off screen, because the observers see the box that
         the entrance slides. Watching an outer wrapper and animating an inner element removes the margin.
         Where: `Reveal.tsx`
   ii.   Same cause: cards that start within 40px of the screen edge appear without the entrance animation
         on the first scroll. The fix in i removes this too.


---------------------------------------------------------------------------------------------------


R36. RecommendedProducts: leftover setters and a duplicate of the picks  🟢 later (not a bug)

   i.    Some state setters React ignores (same value), and the `shown` ref duplicates `picks`. Simplify
         (maybe with the reducer from R34 i).


---------------------------------------------------------------------------------------------------


R37. kb.md: short notes for what PR #9 used  🟢 later (docs)

   i.    useSyncExternalStore; `pageshow` and the back/forward cache; the `storage` event (other tabs);
         scroll anchoring (and Safari without it); tailwindcss-animate.


---------------------------------------------------------------------------------------------------


R38. Home cards: small points from the last PR #9 review  🟢 later (not bugs)

   i.    The enquiry message and the bar thumbnails follow catalogue order, not the order the visitor added
         products. Where: `ProductExplorer.tsx`
   ii.   `flushSync` and a forced style read run each time cards leave the screen, which could stutter on
         cheap phones. Where: `Reveal.tsx`


---------------------------------------------------------------------------------------------------


R39. Nishita's UI list (30 Oct): 7 small PRs  🔵 in progress (track 4d)

   i.    1 login spinner ✅ and 2 sliding sidebar ✅ (both merged in PR #12). 3 home: remove
         Capabilities and "250+" ✅ (PR #14). 4 partner page ✅, 5 best-seller section ✅, 6 offer % + badge ✅,
         7 phone code and country pickers ✅ (all four merged in PR #16, 3 Nov).
   ii.   Commission numbers and testimonials on the partner page wait for real ones from KJS (no made-up data).
   iii.  (PR #14 review) The header "Capabilities" link opens only Stick Pack Factory; the other four pages are
         now linked only from the footer, the capability sidebar and private-label. Next small PR after step 4:
         a "Capabilities" dropdown in the header listing all five. Where: `components/public/SiteHeader.tsx`.
   iv.   (Step 4) If the partners intro text was ever edited in Admin > Website, the saved copy may still say
         "brokers": check it after deploy and reset it there.
   v.    (Step 7) Kept on purpose: the light phone check (decision 5a), not the full `phonenumbers` check per
         country. Revisit only if staff get many wrong numbers.
   vi.   (PR #16 own review) Kept: the home page passes the best-seller list to Recommended as it is (works and
         is tested; a tidier way exists).


---------------------------------------------------------------------------------------------------


R40. Staff pages: a failed or silent request means "Loading…" forever  ✅ fixed (PR #41, 9 Nov)

   i.    About 15 staff pages call `api(...).then(set)` with no error handling and no time limit: a 500, a 403
         or a server that never answers leaves the Loading spinner on for good. (Found in the PR #12 review;
         it was like this before, the spinner only makes it look busier.)
   ii.   Fix: a small shared loader (time limit + "Could not load. Try again" + error code), used by every page.
         Where: `frontend/src/app/[locale]/(admin|employee)/…/page.tsx`, `components/portal/*`.
   iii.  (Vineet, PR #12 second review) Simplest way: a DEFAULT time limit in `api()` (longer value or an opt-out
         where needed), so no caller has to remember it. Covers the Bell too.


---------------------------------------------------------------------------------------------------


R41. Login and portal follow-ups from the PR #12 second review  🟡 next small PR (with the sidebar step)

   i.    No error code when the server can't be reached: `api()` rethrows a network error as it is; wrap it as
         `ApiFailure(0, …)` with the request id (like time-outs). Where: `lib/api.ts`, `PortalShell.tsx`.
   ii.   Sign-up can lock the form on a silent server: a long limit with "this may have worked, try logging in".
   iii.  Log out can look done when it wasn't (the cookie may remain on a shared PC): warn when it couldn't be
         confirmed, and a busy state on the button.
   iv.   The old page change isn't cancelled: if it opens after the form came back, it can replace what the user
         started (e.g. typing in Sign up). Check it in scenario 5 of `login_e2e.mjs`.
   v.    Simplify the login state: one status (idle, submitting, opening, slow) instead of busy, navigating,
         pageOpening, slowTo and slowTimer.


---------------------------------------------------------------------------------------------------


R42. Admin redesign follow-ups (PR #17, 3 Nov)  🟡 next small PR

   i.    Not checked in a real browser with a login yet (no login on Nishita's PC): log out menu and popup,
         dragging a sidebar group down, arrow keys on the grip keeping the focus. Add them to an e2e script.
   ii.   Pages feel slow in development: every database trip to Neon Singapore is about 100 ms (one API call
         about 0.5 s), and dev mode builds each page on first visit (about 1.3 s). A local Docker database for
         development would fix it. Needs a decision with Vineet (`memory.md` says Neon, D15).
   iii.  The sidebar order and open groups are saved per browser (localStorage), not per account.



---------------------------------------------------------------------------------------------------

## 13. Whole-repo code review (29 Oct)

The full list, with where, why and the direction of each fix, is in `codeReview.md` (CR1–CR39). Only the
headline items here.

CR1. `restore.sh` can empty the database and still say "restore done"  ✅ fixed (PR #13, merged 3 Nov)

   i.    Fixed and tested by `deploy/test-restore.sh` (192 checks). See `codeReview.md` CR1.
   ii.   Still open: a restore drill on the real server, once there is one (`track.md` go-live checklist, item 2).
   iii.  ✅ CR3 closed (9 Nov): `backup.sh` and `restore.sh` don't need the backend running.
   iv.   ✅ Done (PR #43, 9 Nov): the app now stays stopped. Was: when a restore fails after the database was replaced, the app is
         started anyway, without migrations or rights. Users get errors (nothing is saved or lost) until
         the undo runs. Keep the app stopped there, like the "unknown" case.
   v.    Follow-ups from the 8 PR #13 reviews (none must-fix):
         a.  The "earlier restore still running?" check treats a failed query as "none running", and the
             read after it never connects to the database. Refuse when the database can't be asked.
         b.  The unpack step (4) has no `set -e`: if `cd /srv/kjs_files` fails, files go into the
             container's workdir. Add `|| exit 1`.
         c.  No lock: two restores started within seconds, or a restore and the 02:30 `backup.sh`, can clash
             (same-second starts also share a safety backup name). Add one `flock` held for the whole run of
             both scripts. `flock` isn't on Windows: test it on Linux.
         d.  "Unknown" endings: a `kill` sent to the script alone during step 5 is handled only after psql
             finishes, so a known result is reported as unknown. On unknown, ask the database what happened.
             The marker table stays after an unknown ending (harmless).
         e.  `ask_database` gives up after 120 s; a big restore can take longer (ends unknown, safe side).
         f.  `restore-undo.txt` keeps growing and points at safety backups deleted after KEEP_DAYS.
         g.  A backup from newer code is caught only at step 7, after the data is replaced (the undo works).
             Read the dump's alembic revision in step 1 and refuse it there.
         h.  A valid dump of an empty or wrong database passes the read check.
         i.  If the script is killed during the database step, `.restore-new` stays until the next restore.
         j.  The health check asks only the backend, from inside its container. Use `deploy.sh`'s check
             (nginx, API and the website) as one shared helper.
         k.  Downtime: files are unpacked after the app stops, and the safety backup is read back in full
             with 2 extra containers. Run `tar tzf` on the host instead of in a backend container.
         l.  `compose run` builds the image if the live `TAG` image was deleted.
         m.  Simpler design: `pg_restore -f` to a file in the db container, then `psql -f` (drops the
             `\.` + `SELECT 1/0` trick).
         n.  Tidy-ups: one shared helper for the dump and tgz checks, and one for the `kjs-restore` session query.


CR2–CR11. Should fix before go-live  🟠

   i.    Health check can't see a broken home page (CR2). Backups need the backend running (CR3).
   ii.   No public error page or API timeout (CR4).
   iii.  Rate limits: admin lockout still possible (CR5), IPv6 gets around every limit (CR6),
         the office's shared IP hits the login / sign-up limits (CR7).
   iv.   Feature flags not checked by the API (CR8). Disabled user's batch stuck (CR9).
   v.    Emails lost when the mail server is down (CR10). Superuser password in the API container (CR11).


CR12–CR39. Fix when convenient  🟢

   i.    Business-rule edge cases, small frontend bugs, deploy / CI cleanups. See `codeReview.md`.


---------------------------------------------------------------------------------------------------


## 14. Images and other gaps (4 Nov)

Found while checking how images are served. Plan only, no code yet. Fixed site images in
`frontend/public/images/` (through `next/image`) and the storage setup (D16) are fine and stay.

Suggested order: CR4 and R45 first (small, and we hear about problems before visitors do), then R43, then R44.

R43. Uploaded photos are sent at full size  🟠 next small PR (needs Pillow: ask first)

   27 Nov: fix in PR #135 (product and profile photos shrunk with the existing image_shrink; Pillow approved 19 Nov). Not merged yet: mark ✅ when it is.

   i.    The product page shows uploaded photos with `unoptimized` (`products/[slug]/page.tsx`), so a 10 MB phone
         photo reaches the visitor as 10 MB. Phone photos can also carry the GPS location (EXIF).
   ii.   Plan: when an image (png, jpg, jpeg, webp) is uploaded, open it (reject it if it can't be opened),
         shrink it to at most 1600 px, save it as WebP (quality about 80) without EXIF, and keep only that.
         Keep Pillow's pixel limit on (decompression bombs).
   iii.  Why not let Next.js resize instead: the frontend server would resize on every first request, the big
         original stays in storage and backups, and it's untested with R2's redirect.
   iv.   Also fixes R9 for images. Assumptions: A80, A81.
   v.    Where: `file_service.py`, `requirements.txt`, `tests/test_files.py`.


R44. With R2, public photo links expire after 5 minutes  🟠 once R2 keys arrive (A54)

   27 Nov: fix in PR #130 (small public photos sent by the API, browser-cacheable 10 min). Not merged yet: mark ✅ when it is.

   i.    With `STORAGE_DRIVER=r2`, `/api/v1/public/files/{id}` redirects to a new 5-minute signed link every
         time, so browsers and Cloudflare can't cache the photo. The link also says "attachment".
   ii.   Plan: for public website files only, the API reads the photo from R2 and sends it itself with
         `public, max-age=3600` (as local storage does today). Staff files keep the 5-minute link.
         Cheap once R43 makes photos small.
   iii.  Add a Cloudflare Cache Rule for `/api/v1/public/files/*` (Cloudflare skips addresses without .jpg etc.).
   iv.   (DONE differently, 6 Nov: website pictures already use a public bucket, decision 32. Uploaded product
         photos still go through the API.) Later, only if traffic grows: a public R2 bucket on a custom domain.
         Faster, but a hidden product's photos stay reachable by link. Assumption: A82.
   v.    Where: `file_service.py`, `endpoints/files.py`, maybe `core/storage.py`. No new package.


R45. Nobody hears about crashes or downtime  🟠

   27 Nov: uptime check documented in PR #115 (README 5.6); the check itself is set up by Vineet. Not merged yet: mark ✅ when it is.

   i.    Errors only go to the logs, and nothing checks `/api/health` from outside.
   ii.   Fix: a free uptime checker on `/api/health/ready`. Error tracking (Sentry) is a new service: ask first.


R46. Big videos on the website  🟢

   i.    About 13 MB of MP4s in `frontend/public/images/kjs/video/` (`banner-video.mp4` is 6.8 MB). Not in git
         (downloaded by `scripts/fetch_kjs_assets.py`), but visitors load them.
   ii.   Fix: compress them, or move them to R2 later.


Already logged, found again in the same check:

   i.    No error pages (`not-found.tsx`, `error.tsx`, `global-error.tsx`): CR4.
   ii.   Backups stay on the same server: R11. "Loading…" forever: R40. Uploads checked by name only: R9.
   iii.  Light spam protection: A31. Waiting on KJS: I10, B6, B3, A54, and before go-live A76 / I14, A47 / I12.



---------------------------------------------------------------------------------------------------

## 15. Lead management, website and attendance follow-ups (5–7 Nov)


R47. Small follow-ups from PRs #27, #30, #33 and #34  🟢 later

   i.    "Converted Value" on Contacts shows "—" and the Proposals tab is empty: deal values and proposals are
         not recorded yet.
   ii.   Popups that cover phone pages can lower Google ranking; the bottom sheet is the gentler form. Watch
         Search Console after launch (decision 26).
   iii.  Still green on the public site: hover colour on category names and a few other pages.
   iv.   Tea is hidden (`HIDDEN_CATEGORIES`). Show it again when KJS says so.
   v.    `PortalShell.tsx` still has `isAttendance` layout checks; with the page's own bar gone they can probably go.
   vi.   A "Let's connect" popup text change is in Nishita's `git stash` ("ConnectPopup text change"), not in main.



---------------------------------------------------------------------------------------------------

## 16. R2 pictures and order boards follow-ups (6–9 Nov)


R48. Website pictures: real address before go-live  🔴 before go-live

   27 Nov: CSP part in PR #116; connecting cdn.kjsindia.com is a Cloudflare step (Vineet). Not merged yet: mark ✅ when it is.

   i.    Connect `cdn.kjsindia.com` to the `kjs-site-assets` bucket, then change `ASSET_BASE_URL` AND the address in
         `nginx/security-headers.conf` (`img-src`), and rebuild the frontend.
   ii.   After about a week on R2, remove the copies in `frontend/public/images` and `public/flags`.


R49. Order boards follow-ups (PRs #35–#39)  🟡 ii–vi open

   i.    ✅ Checked in Chrome (PR #46, 9 Nov, Nishita): CSV with ₹ and Hindi, Excel, Word, PDF previews, full
         screen and Esc (also after a click inside a PDF, by hand), History, People, the plan lock (member refused,
         owner allowed), every tab and preview at 390 px. One screen bug fixed: on a phone the preview header cut
         the file name to "po-11…". The same checks now run in `scripts/e2e` (PR #49). Not checked: a phone
         without a PDF viewer.
   ii.   R2 previews are read through the API in one piece; stream them if files get big.
   iii.  Board pages make some extra database lookups (every user's name, members per step); fine for now.
   iv.   The staff picker and date preview are copied between the create form and the plan editor: share them.
   v.    Removing a `boards.manage` person from a board tells them "you were removed", but they can still open it.
   vi.   A step can have several heads (★); the screens assume few. Decide if one is the rule.



---------------------------------------------------------------------------------------------------

## 17. Go-live safety follow-ups (9 Nov, PRs #41–#45)


R50. Before and after go-live  🔴 i–iii before go-live

   27 Nov: iv: in PR #115. Not merged yet: mark ✅ when it is.

   i.    On the server: run `deploy/test-restore.sh` once (it was not run after the last changes to
         `backup.sh` / `restore.sh`), then a real restore drill using an off-site copy (`deploy/README.md` 5.4).
   ii.   Rotate every key that was pasted in chat (R2 app and backup keys, database passwords) and put
         `BACKUP_PASSPHRASE` in a password manager.
   iii.  Delete the e2e test uploads from `kjs-prod-files` and their copies in `kjs-bkp-prod`. Local e2e runs
         use `STORAGE_DRIVER=local` from now on.
   iv.   Nobody is told when the nightly backup fails (R11.i): cron mail or an uptime check.
   v.    CR9's leave case: an admin "take back batch" button (Nishita, decide first).
   vi.   Duplicate saves: a one-time key per save, so the server ignores a repeat (Nishita, Phase 2). The
         holidays and offers buttons can still be double-clicked.
   vii.  Left from the PR #42 review on purpose: no limit on how many files one sync moves to `deleted/`, an
         extra INSERT per check-in, R2 server-side copy (speed only).


R55. `admin` level for batches: auto-assign still gives batches to employees  🟠 before using `admin` (Nishita)

   27 Nov: fix in PR #129. Not merged yet: mark ✅ when it is.

   i.    With `batches = admin` the job (and "Run now") hands batches to every checked-in employee, who can't open
         them; their open batch then blocks new ones. Fix: with `admin`, only admins are eligible (`_eligible`
         in `assign_service.py`). Until then, use only `on` and `off` for batches.
   ii.   Smaller: with `order_boards = admin`, an employee added to a test board still gets the notification
         text (no link). Accepted for now.


R54. e2e browser check for the phase switches  🟢 after go-live (Nishita)

   i.    Switch one area off, then check the sidebar, a typed-in address ("Not available yet") and the API
         (404 `module_off`). Needs the app running locally. The script must set everything `on` first.
   ii.   Also: a typo made directly on the server is not caught by CI; check the admin Settings page after.


R53. `config/storage.ini` allowed_types can only remove file types  🟢 after go-live (Nishita)

   i.    A type must also be in `TYPES` in `backend/app/services/file_service.py`, so adding `mp4` to the ini
         does nothing. Fix: say so in the ini comment, or keep one list.
   ii.   Files are stored as uploaded (no conversion). Found in the config walkthrough (PR #56).


R52. Koko on Groq's free tier fits only a few messages a minute  🟠 after launch (decided 18 Nov)

   i.    Free tier: 8,000 tokens a minute for the whole site. One Koko message is about 3,000 tokens (prompt about
         2,000 after PR #50, plus the chat and the reply), so about 2–3 messages a minute; more get the fallback.
   ii.   Fix: a paid Groq tier (much higher limits, low cost), or another provider (`llm.py`, decision D4).
   iii.  Before PR #50 every message failed (413: all 72 products, about 8,300 tokens). See A92.
   iv.   18 Nov, Vineet: launch on the free tier; replace it later. The tester brief lists the fallback as expected.


R51. `scripts/e2e/login_e2e.mjs` is unsteady  🟢 after go-live (Nishita)

   i.    9 Nov, on main with PRs #41–#45: once all 20 checks passed (alone, after a backend restart); other runs
         failed steps 1, 2 or 5 (the button still says "Logging in…" when the check looks). No app bug seen.
   ii.   Look at: the timing of the held requests, and the new login lockout counting (PR #44).
   iii.  The other suites pass: api 196, browser 73, sidebar 25 (PR #49). Esc inside a PDF in full screen stays a
         hand check (a script's key press can't leave Chrome's own full screen).



---------------------------------------------------------------------------------------------------

## 18. Chat, harvester and hosting follow-ups (10–14 Nov)


R56. `leave_requests` foreign keys differ between model and migration  🟢

   i.    `alembic check` reports `user_id` and `decided_by` (`ondelete`). A separate small fix.


R57. Lead Harvester follow-up PR  🟠 before real use

   27 Nov: i (all but the multi-process job lock) in PR #136; ii (IPv6, validators once) in PR #137, its download size limit and iii still open. Not merged yet: mark ✅ when it is.

   i.    Open bugs: robots.txt allows scraping when it can't be read; unknown categories (`spices`,
         `private_label`); a number in the phone field crashes a run; duplicates inside one fetch;
         `+91 98765 43210` numbers lost; one failing source breaks the rest of the run; phone duplicates in other
         formats; the job lock released early (only with several API processes).
   ii.   Not done in #62: public IPv6 typed as an address is refused; validators written twice (create, edit);
         no size limit on downloads (only `assign.manage` can add sources).
   iii.  Too basic for real use: one record per page. Read many records per page (Python's own HTML parser).


R58. `sidebar_e2e.mjs`: "phone: choosing a page closes it" fails  🟢 (test fault)

   i.    Its `clickLink` helper opens all closed groups at once and only the last stays open. A real tap works.
   ii.   Fix: open only the needed group in the test, or make the group toggle in `SidebarNav.tsx` use the
         latest state.


R59. Oracle free VM for hosting  ✅ CLOSED 23 Nov: we went with Hostinger (`memory.md` decision 62)

   i.    Oracle Always Free (ARM), home region Mumbai, Pay As You Go (still free). VM: Ubuntu 24.04,
         2 CPU / 12 GB, 100 GB disk. Our `deploy/` setup runs on it unchanged (`deploy/README.md` section 2).
   ii.   Live through a Cloudflare Tunnel (no open web ports), nightly backups to R2, then `test-restore.sh`.
   iii.  Still open: staging or production; access to the Cloudflare account for `kjsindia.com` and the R2
         backup token before starting. About 3 to 4 hours.


R60. Chat before going live  🟠

   i.    10 minutes by hand in two browsers.
   ii.   On deploy to our own server: reload nginx (the chat WebSocket block).
   iii.  Accepted: edits to older messages show after a reload. Phase 3 "typing…": raise the 20-frames limit
         between session checks, or the page's own typing events will close the socket.



---------------------------------------------------------------------------------------------------

## 19. Firebase login, lead files and complaints follow-ups (13–14 Nov)


R61. Rotate the Firebase service-account key  🔴 before going live

   i.    It was pasted in a chat once. Firebase > Project settings > Service accounts: delete the key, generate
         a new one, put it in the root `.env` (`FIREBASE_SERVICE_ACCOUNT`) and on Render.


R62. Firebase console settings  🟠

   i.    Password policy: minimum 10 (the pages ask for 10, Firebase's default is 6), "require update on
         sign-in" if offered. It is for the whole project: first confirm no other app uses it.
   ii.   Separate dev project for local + Playwright (decided, Kunal): new project `kjs-dev`, Email/Password
         on, `localhost` in Authorized domains, policy min 10. Web app values into `frontend/.env.local` and
         `frontend/.env.e2e.local` (`NEXT_PUBLIC_FIREBASE_*`), a service-account key into backend `.env`, then
         `python -m app.seed`. Never put the dev values on Vercel / Render.


R63. Playwright suite after Firebase  🟠

   i.    Login now goes through Firebase: the K/V/S test accounts need Firebase accounts with verified emails.


R64. Email verification rules (point 4 of the #77 review)  🟠 after testing

   i.    Approve refuses an unverified email (Approvals shows "email not verified").
   ii.   A verified person replaces an unverified *pending* sign-up with the same email (audit keeps the old one).
   iii.  Parked until our own server, together with the #87 review findings: R68.


R65. Drop `users.password_hash`  🟢 once every old account is linked to Firebase

   i.    The old scrypt helpers in `core/security.py` are marked LEGACY (tests only) and go with it.


R66. Logo size warning (Next.js "width or height modified")  🟢 cosmetic

   i.    Our `width` / `height` don't match `Kjs.png` (536×136). Use real proportions: `PortalShell.tsx`
         120×28 -> 110×28, `SiteHeader.tsx` + `SiteFooter.tsx` 140×32 -> 126×32, `employee/login/page.tsx`
         160×36 -> 142×36.


R67. Not done yet  🟢

   i.    Notification emails (PR `feat/notification-emails`, waiting; don't merge yet). Then send each new
         complaint to `developer_email` in `config/complaints.ini`.
   ii.   Tesseract (read leads from images; Vineet agreed to `pytesseract` + the Dockerfile change): own branch.
   iii.  Browser click-through not done for lead files, Excel / CSV, bulk import, Extra Info, spinners,
         complaints. `scripts/e2e/api_e2e.py` updated but not run.



---------------------------------------------------------------------------------------------------

## 20. Email checks and own server (16–17 Nov)


R68. Email checks, parked until our own server  🟠 after launch (decided 18 Nov)

   i.    Why parked: decision 55. First make email work on the VPS, then this list.
         18 Nov, Vineet: checks stay off for the launch; an admin approves every sign-up.
   ii.   Review findings on #87:
         a. `auth.py:30`: an old account (no `firebase_uid`) that signs up again gets `verify_email = false`,
            but its login always needs a verified email, so it is stuck. Fix: `true` whenever the row has no
            `firebase_uid`.
         b. `config/app.ini:24`: off in the shared ini = off on every server. Fix: ini `true`; off on one
            server only with `KJS__APP__REQUIRE_VERIFIED_EMAIL=false`.
         c. `auth_service.py:94`: one global switch. Turning it on locks out everyone approved while it was off.
         d. `employee/login/page.tsx:115`: an unverified person waits for the server to wake (up to 2 minutes)
            before hearing "please verify".
         e. `page.tsx:32`: a generic error shows inside brackets; "try again in an hour" contradicts "wait a
            few minutes" for the same `auth/too-many-requests`.
         f. `page.tsx:154`: a failed verify email shows in the green success box.
         g. `tests/conftest.py:63`: `monkeypatch.undo()` also undoes other fixtures' patches; every test
            reloads the config twice.
         h. `tests/test_firebase_login.py:28`: `verified_rule` repeats the conftest fixture; 3 tests ask for it
            and never use it.
         i. `admin/approvals/page.tsx:72`: the "checks are off" banner doesn't say WHICH sign-ups are unverified.
   iii.  Plan, first PR: a, b, g, h. Set the env var on the server BEFORE the deploy, then log in with an
         unverified test account to check.
   iv.   Plan, second PR: column `email_confirmed_by_admin` (next free migration number; check open PRs). The
         migration sets it true for everyone already active, so nobody is locked out. Approvals: a required
         tick "I confirmed this email belongs to this person" for unverified sign-ups, saved by `approve()` and
         in the audit log; show verified / unverified per sign-up (i). Login: `email_verified OR
         email_confirmed_by_admin`. Then remove the global switch and the env var. Run `alembic upgrade head`
         right after merging, with BOTH database URLs set (decision 38).
   v.    Later: d, e, f. Undo the admin's hand verify if ever needed: `email_verified=False`.


R69. Hosting: E2E Networks as a paid option next to the Oracle free VM (R59)  ✅ CLOSED 23 Nov: Hostinger
     (`memory.md` decision 62)

   i.    R59 (Oracle) stays the plan until this is decided. E2E: Indian company, INR + GST invoices, Delhi or
         Chennai, our `deploy/` setup runs unchanged.
   ii.   Plans (17 Nov, before 18% GST): E1LC-2.6GB = 2 shared vCPU, 6 GB, ₹894 a month for compute; its disk
         (150 GB default, 75–2,400 GB) is billed separately (price per GB unknown) and it has no public IPv4
         (Reserved IP ₹199 a month). C3.8GB = 4 vCPU (≥ 2.8 GHz), 8 GB, 100 GB NVMe, public IPv4, ₹3,422 a month.
   iii.  E1 -> C3 is not an in-place upgrade (new node + move). Upgrades inside one family work (node off).
         No downgrades.
   iv.   Sales answers (17 Nov): outgoing data free; 1 Gbps; scheduled snapshots, charged on data used,
         restore = new node; no backup by default; Security Groups; web console; monitoring + alerts;
         Ubuntu 24.04; root access; 99.9% SLA; IPv6 only in Delhi; email + phone support, about 30 minutes.
   v.    Still to ask: E1 disk price per GB; can an E1 node without a public IP reach the internet (Docker
         pulls, Cloudflare Tunnel); trial credits; where snapshots are stored.
   vi.   Keep R2 for site pictures and the off-site backup either way. Trial: `deploy.sh`, `docker stats`,
         `test-restore.sh`, then choose.


---------------------------------------------------------------------------------------------------

## 21. Security gaps (18 Nov senior review)

Found in a read-only review of the whole repo. Render / Vercel-only points are left out: we are moving to
our own VPS. Do these before going live on the VPS unless marked 🟢.


R70. Security headers on the VPS  🟠 before going live

   27 Nov: HSTS in PR #112; COOP/CORP in PR #119; CSP nonces still open (conflict with the page cache). Not merged yet: mark ✅ when it is.

   i.    Today only `deploy/nginx/security-headers.conf` sets them (CSP, X-Frame-Options and more).
   ii.   Add HSTS, and remove `'unsafe-inline'` from the CSP script rule if the frontend allows it.
   iii.  Check on the VPS: `curl -I https://<site>` shows every header.


R71. Koko trusts chat history from the browser  🟠 (raises R1)

   27 Nov: ii in PR #119; i in PR #134 (Koko uses its saved replies). Not merged yet: mark ✅ when it is.

   i.    The browser sends the whole history, including Koko's own past replies, so a visitor can fake them
         (`schemas/lead.py:10`, `koko_service.py:208`).
   ii.   `summarise_chat` (`koko_service.py:235-249`) puts visitor text into the staff summary without saying
         "this is data, not instructions": indirect prompt injection aimed at the sales team.
   iii.  Fix: keep the history on the server (R1.ii); frame the transcript as data in the summary prompt.


R72. Rate limits and the Koko budget reset on every restart  🟠 (raises R2)

   27 Nov: the Koko budget part in PR #133 (koko_usage table, migration 0035); the per-IP limiters still open. Not merged yet: mark ✅ when it is.

   i.    Kept in process memory (`core/rate_limit.py:22`, `koko_service.py:26`): a restart or deploy resets
         the daily AI budget, and two processes would double every limit.
   ii.   Fix: a small database table (no new service).


R73. No dependency scanning  🟠

   i.    Nothing warns about a package with a known hole. Fix: Dependabot + `pip-audit` / `npm audit` in CI
         (see R78).


R74. CSRF header not checked on login, sign-up and logout  🟢

   i.    `deps.py:23,91` checks `x-requested-with` on other writes; `/auth/login`, `/signup`, `/logout` skip it.
   ii.   Risk is small (login/logout CSRF). Fix: same header check.


R75. Lead harvester uses the auto-assign permission  🟢

   i.    `endpoints/harvest.py:34-39` uses `assign.manage`. Give it its own permission, and add harvest runs
         to the audit log (`harvest.py:160`).


R76. Production does not insist on R2 storage  🟢

   i.    `production_problems()` (`core/config/__init__.py:73`) should refuse `STORAGE_DRIVER` other than r2.


R90. Next.js 16.4.3 has a known security vulnerability  ✅ 18 Nov (PR #94, 16.4.6)

   i.    `next build` warns about it (18 Nov). Upgrade `next` (and `eslint-config-next` if present), then
         typecheck, `npm test`, build, and a live check of login and the portal.


R77. Firebase web key not restricted  🟢 (Vineet, Firebase console)

   i.    The key is public by design (`frontend/src/lib/firebase.ts:13`). Add API-key restrictions to our
         domains, or App Check.


---------------------------------------------------------------------------------------------------

## 22. Tooling gaps (18 Nov senior review)


R78. Dependency updates and audits  🟠

   i.    `.github/dependabot.yml` (pip, npm, GitHub Actions) and a `pip-audit` / `npm audit` CI step.
   ii.   No new package in the app.


R79. Migration checks in CI  🟠

   i.    CI only runs `alembic upgrade head`. Add: exactly one `alembic heads`, and `alembic check` (models
         match the migrations).


R80. Linting in CI  🟠 (new dev tool: ask first)

   i.    No ruff (Python) and no eslint step (frontend). `ci.yml:2` already says so.


R81. Error tracking  🟠 (new service: ask first; raises R45)

   i.    Errors only reach the logs. Sentry free tier for backend and frontend.


R82. Uptime check on the VPS  🟢 (raises R45)

   i.    A free checker (e.g. UptimeRobot) on `/api/health/ready`; also tells us when the nightly backup fails.


R83. Test coverage report  🟢 (new dev tool: ask first)

   i.    pytest-cov report in CI, no pass/fail limit at first.


R84. Frontend API types written by hand  🟢

   i.    `frontend/src/lib/api.ts` types can drift from the backend. Later: generate them from OpenAPI.


R85. Frontend tests only cover `src/lib`  🟢

   i.    No component tests; the E2E scripts in `scripts/e2e/` run by hand only.
   ii.   Also: a test that `frontend/src/lib/modules.ts` matches the backend `AREA_PAGES`.


---------------------------------------------------------------------------------------------------

## 23. Scaling: before a second API process (18 Nov senior review)

None matters with one API process (`--workers 1` today). Do these before running two (A41).


R86. Decision to record: we stay on Postgres  ✅ 18 Nov (memory.md decision 57)

   i.    We use Postgres features on purpose: JSONB, `ON CONFLICT`, partial unique indexes, advisory locks,
         `SKIP LOCKED`, the append-only audit trigger.
   ii.   Moving to another Postgres (Neon, VPS, RDS, Supabase) = change `DATABASE_URL` only. A layer for
         several kinds of database would cost a lot and give nothing. Fold into `memory.md` decisions.


R87. Chat live updates are held in one process  🟢

   i.    `services/chat_hub.py:39,101`: a message sent through process A never reaches people on B.
   ii.   Fix when scaling: Redis pub/sub, or Postgres NOTIFY over a direct (not pooled) connection.


R88. Job lock is released mid-job  🟢

   i.    `jobs/runner.py:82` takes a transaction lock; jobs that commit part-way (`send_emails`, the harvester)
         run the rest unlocked. Fine with one process.
   ii.   Fix: a small "job lease" table (job name, held until).


R89. Slow queries that grow with data  🟢

   i.    One query per item: `board_service.py:296`, `analytics_service.py:65`, `assign_service.py:225`,
         `lead_service.py:575`.
   ii.   Analytics adds up every lead in Python (`analytics_service.py:27`); `sla_check` loads every open lead
         each run.
   iii.  Lead duplicate check scans the whole table (`lead_service.py:333`): add an index on the cleaned phone
         and `lower(email)`.


---------------------------------------------------------------------------------------------------

## 24. Config per feature follow-ups (18 Nov, PR #91 reviews)

Left on purpose by Vineet. None matters with today's values; each one bites only after a config edit.


R91. One bad value makes the WHOLE config fall back to defaults on first load  🟠 before the VPS deploy

   27 Nov: fix in PR #113. Not merged yet: mark ✅ when it is.

   i.    `ini.py` validates all files together: one bad key = every file ignored (e.g. `jobs_enabled` back on).
   ii.   `storage.max_upload_mb` max went 500 -> 25 (#91): a server with 26-500 set (ini or
         `KJS__STORAGE__MAX_UPLOAD_MB`) loses all its ini values. Check the VPS env before deploying.
   iii.  Later: validate per file (keep the good files), or warn instead of refuse for that key.


R92. Lead import (JSON) is under nginx's 1 MB default  🟢

   i.    `POST /employee/leads/import`: about 3,000 rows hit it, while `leads.ini import_max_rows` allows 5,000.
   ii.   Fix: add it to the 26 MB nginx rule (`deploy/nginx/default.conf`), or lower the bound.


R93. Older long chat messages can't be edited after `body_max` is lowered  🟢

   i.    Edit reuses `MessageIn`. Fix: an edit may keep its old length; only new text must fit.


R94. Open tabs keep old `me.limits` until reload  🟢

   i.    The server checks every request, so nothing wrong is saved; the person sees an error instead.


R95. Small cleanups from the #91 reviews  🟢

   i.    MB -> bytes in one place (`lead_reader`, `endpoints/assign.py`).
   ii.   Stale numbers in comments: "up to 3 tries" (`notification_service.send_emails`), "Missed more than
         100" (employee chat page).
   iii.  `lead_service.sla()` reads `cfg()` once per lead: read it once per list.


R96. Health check can say "stuck" after `job_timeout_seconds` is lowered mid-job  🟢

   i.    `jobs/runner.py loop_is_alive()` uses the new timeout; the running job keeps the one it started with.
   ii.   Fix: remember the running job's timeout and use the larger of the two.


---------------------------------------------------------------------------------------------------

## 25. Go-live review follow-ups (18 Nov, PRs #95, #96)

Review of the basic release (dashboard, leads, employees, website, reports and settings): no security hole, no
broken main flow. Fixed in #95: only an admin creates accounts, overview lead numbers need `leads.view_all`,
"Load more" on lead lists (`config/leads.ini` page sizes), task tick error, holidays out of the attendance switch,
report labels, sitemap. #96: chat, order boards, batches, harvester off; attendance admin only.
Tester brief (private artifact, Vineet shares it): "KJS Basic Release: Tester Brief".


R97. VPS-day steps found in the review  🔴 before go-live (Vineet)

   27 Nov: iii: in PR #113; i: CSP copied back in PR #112; ii and iv are server steps (Vineet). Not merged yet: mark ✅ when it is.

   i.    nginx `connect-src` (`deploy/nginx/security-headers.conf:17`) blocks Firebase: add
         `https://identitytoolkit.googleapis.com https://securetoken.googleapis.com`, or staff can't log in.
         Also the final image domain there (R48).
   ii.   Jobs are off in `config/app.ini`: turn them on for that server only (`KJS__APP__JOBS_ENABLED=true`).
         First close or clean the old test leads, or the first SLA check sends a pile of alerts.
   iii.  Check every `KJS__*` value is in bounds before the first start (R91).
   iv.   Secrets (B9, B14, R50.ii, R61), Firebase authorized domain, backups and the restore drill (R50).


R98. A disabled employee's open leads stay assigned to them  🔴 before go-live (after UAT)

   27 Nov: fix in PR #122. Not merged yet: mark ✅ when it is.

   i.    Decided 18 Nov: on disable, their new / contacted leads go back to unassigned, with a note on each
         lead and one audit row; closed leads keep their owner.
   ii.   Place: `auth_service.set_status`, next to `return_open_batch`. Auto-assign stays as it is.
   iii.  Until then an admin reassigns by hand ("Any owner" filter in All Enquiries).


R99. No leads export  ✅ 18 Nov (decided: launch without one)

   i.    The only export is attendance (`attendance.py`). A leads export is a new feature if KJS asks.


R100. Website text and SEO fields  🟢 (covered by the dynamic UI work)

   27 Nov: ii: in PR #129. Not merged yet: mark ✅ when it is.

   i.    Non-coffee words hard-coded: home page (line 66), layout title, private-label description, search
         placeholder, JSON-LD, Koko's prompt. Ignored for now (Vineet, 18 Nov).
   ii.   Admin > Website "Products: page title / description" (`seo.products.*`) are saved but never read
         (`products/page.tsx` has a fixed title).


R101. Small findings from the go-live review  🟢

   i.    Contacts list and contact page stop at 5,000 leads (`lead_service.py`).
   ii.   `POST /employee/leads/import` (JSON save) has no rate limit; the preview has one.
   iii.  No `metadataBase`, canonical or `openGraph`: shared links show no preview.
   iv.   Audit page shows the newest 500 rows, no filter or paging.
   v.    `staff.approve` also opens Reports, Settings, Complaints and config reload: a broad permission.
   vi.   `services/auto_assign_service.py` is a dead stub (fake numbers, nothing calls it): delete it.
   vii.  `/auth/logout` doesn't need the CSRF header (another site could log someone out; low impact).
   viii. Any employee can hand over an unassigned lead without taking it (works around backlog A8). Decide.
   ix.   Reports: tasks are grouped by name (two people with one name merge); attendance "leave" counts as present.


R102. `npm audit`: Firebase 13 pulls in `@grpc/grpc-js` alerts  🟢

   i.    npm's "fix" is a downgrade to Firebase 9 (wrong). Check whether a newer Firebase fixes it; we use only
         Firebase Auth in the browser.


R103. `npm audit`: Tailwind 3 build tools (chokidar, micromatch, picomatch, fast-glob)  🟢

   i.    Build and dev only, not on the live site. Fix is Tailwind 4: a major upgrade, its own PR.

---------------------------------------------------------------------------------------------------

## 26. Coffee-only follow-ups (18 Nov, PRs #93, #97, #99)

Coffee-only plan done: photo upload when adding a product (#93), Show/Hide per category in Admin (#97,
migration 0030), the site follows the switches (#99). Decisions 58, 59 in `memory.md`.


R104. A product with a name over 60 characters can't get a photo  🟠 own PR (Nishita)

   27 Nov: fix in PR #124 (files.owner_id widened to 120, same bug as CR19). Not merged yet: mark ✅ when it is.

   i.    `files.owner_id` is 60 characters (model and migration 0006); product slugs can be 110. The upload
         fails when the file row is saved, after the product is already saved. Was true before #93.
   ii.   Fix: a migration that widens `owner_id` (or cap the slug at 60). One head check first.


R105. Menu and search thumbnails download the full uploaded photo  🟢 later

   i.    Uploaded photos load `unoptimized` (with R2 the file address redirects, which the image optimizer
         can't follow), so a 140 px thumbnail can pull a 25 MB original.
   ii.   Fix: resized copies of public product photos, and `photo_url` pointing at them.


R106. Add product photo: small gaps  🟢 later

   i.    An empty or non-image file isn't flagged in the browser (the server still checks the type).
   ii.   "Photo didn't upload": after a dropped connection the photo may already be saved; say "check Photos &
         files before trying again".
   iii.  The test PNG in `test_files.py` is not a complete image (signature and end only).


R107. Category visibility read in two steps  🟢 later (raised in both #97 review rounds)

   i.    Public lists read the hidden categories in one query and the rows in another: a switch in between
         gives one mixed answer. The 60 s page cache covers it. Fix: the parent rule as one SQL query.
   ii.   Admin > All Products: an older reload finishing after a newer one can show old switches for a moment
         (the product list has the same pattern). Fix: keep only the latest reload's answer.


R108. Every category hidden  🟢 later (Vineet's #5 on #99)

   i.    The footer, Google company description and Koko then name the full range (an empty list reads as
         "no data"). Fix: an empty list means "no product areas"; Koko sends every product question to sales.


R109. Coffee-only known limits  🟢 later

   i.    The second banner's coffee text is in the code, not in Admin > Website.
   ii.   The coffee products for the banner pictures and "Popular" are a fixed list in the code; a new coffee
         product shows there only if ticked Best seller.
   iii.  Only "coffee-only" is a mode; another single-category site needs a small code change.
   iv.   The default page title in `app/[locale]/layout.tsx` names every area (pages without their own title).
   v.    The normal Google home title is 68 characters (Google shows about 60).


---------------------------------------------------------------------------------------------------

## 27. Website insights follow-ups (18 Nov, PR #100)

Reports > Website insights: decision 60 in `memory.md`. Guesses: A104-A107.


R110. Chart values can only be read with a mouse  🟢 later (CodeRabbit on #100)

   i.    The exact number of a bar shows on hover only: keyboard and phone users can't read it. Same for the
         Business charts, so one small PR for every chart (`components/portal/charts.tsx`), for example a
         hidden table for screen readers and values on tap.


R111. Privacy notice line for Website insights  🟠 when the privacy notice is written

   i.    Say that the site counts page views, searches and button clicks without cookies or IP addresses, and
         keeps them 180 days. Depends on A104.


R112. Linked product -> enquiry funnel  🟢 dropped for now (Vineet, 18 Nov)

   i.    The first version counted the 3 steps separately, so a step could be bigger than the one before; the
         panel was removed. Linking them needs the order of each visit's events. Same numbers today: "Pages
         viewed" and "Most clicked buttons".


---------------------------------------------------------------------------------------------------

## 28. Home page refresh follow-ups (19 Nov, PRs #103-#107)

Decision 61 in `memory.md`. Guesses: A108-A111.


R113. Hero and showcase settings live in `site_ui.ini`  🟢 later (review on #104-#106)

   i.    The rule is one ini per feature; hero, partner and activity limits share `site_ui.ini`. Split if the
         file grows.


R114. Two editors switching on at the same moment can pass an on-limit by one  🟢 later

   i.    Slides and partners count "switched on" rows before saving; a lock would close the gap.


R115. Replaced pictures and logos stay in storage  🟢 later

   i.    The old file is unused but still public. A clean-up job for files with no owner row would fix it.


R116. A few fixed numbers in the frontend  🟢 later

   i.    Some animation timings and the 10-15 digit phone check are in the code, not in `site_ui.ini`.


R117. Other languages for the hero, logos and pop-ups  🟢 when the site gets a second language (D2)

   i.    Built English only; each table can take a language field.


---------------------------------------------------------------------------------------------------

## 29. Hostinger production follow-ups (23 Nov)

Production is live at https://twins.kjsindia.com (decision 62). Checked from outside on 23 Nov; the rest needs
someone on the server.


R118. The live nginx is ahead of the repo  🟠

   27 Nov: i: in PR #112 (the Firebase CSP); iii: the host nginx config is still to copy (Vineet). Not merged yet: mark ✅ when it is.

   i.    The live CSP allows `identitytoolkit.googleapis.com` and `securetoken.googleapis.com` (R97.i done on
         the server), but `deploy/nginx/security-headers.conf:17` still says `connect-src 'self'`. A redeploy
         from the repo would break staff login.
   ii.   Also live: `nginx/1.26.3` (the repo's image is 1.28) and no Cloudflare in front, while `deploy/README.md`
         describes a Cloudflare Tunnel.
   iii.  Fix: copy every change made by hand on the server back into `deploy/`, and write the real Hostinger
         setup in `deploy/README.md`.


R119. Is twins.kjsindia.com the final address?  🟠 decide (Vineet, KJS)

   i.    `robots.txt` allows Google and the sitemap lists `twins.kjsindia.com`, so Google can index the test site
         now, with test data.
   ii.   If the final site is another address (e.g. www.kjsindia.com): keep twins out of Google during testing
         (`Disallow: /` or `noindex`), then set `PUBLIC_BASE_URL` to the final address at go-live.


R120. Still to confirm on the server  🔴 before go-live

   i.    Backups: the nightly cron runs, the off-site copy to R2 works, and the restore drill is done (R50).
   ii.   Every secret pasted in chat rotated on the server (B9, B14, R50.ii, R61).
   iii.  Jobs really on: "jobs ok" in `/api/health/ready` is also shown when the jobs loop never started
         (`jobs/runner.py:40`). Check `KJS__APP__JOBS_ENABLED` and that SLA alerts arrive (R97.ii).
   iv.   HSTS (R70), uptime check and backup-failure alert (R82, R50.iv), SMTP for email (R68).
