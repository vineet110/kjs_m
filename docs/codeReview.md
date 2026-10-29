# Code review: whole repo (29 Oct 2026)

A full review of https://github.com/vineet110/kjs_m, every part of the code, not just the last change.

Reviewed at commit `7d117aa` (main, after PR #8). Line numbers are from that commit.

Don't know a word in here? Search for it in `kb.md` (Ctrl + F).



---------------------------------------------------------------------------------------------------

## 1. How the review was done

1. Four passes:

   i.    The `/code-review` tool on the newest commits (PR #6 home page, catalogue seed, CI).
   ii.   Backend foundations and security: core, auth, sessions, permissions, files, Koko, schemas,
         models, migrations, config.
   iii.  Backend business rules: leads and SLA, auto-assign, attendance, order boards, tasks,
         analytics, background jobs, seeds.
   iv.   Frontend, deployment and CI: every page and component, `proxy.ts`, nginx, Docker,
         `deploy.sh` / `backup.sh` / `restore.sh`, GitHub workflows, scripts, superset.

2. Every finding was checked against the real code before it went in here. Things that could not be
   backed by a real "this goes wrong when..." story were dropped.

3. Not repeated here: everything already in `backlog.md` sections 8 to 11 (R1 to R30). Section 5 below
   lists the ones this review found still open.

4. Not done: the backend tests were not run (the test database container was paused). Nothing was
   changed in the code. This file is the to-do list.


Severity:

   🔴  Must fix before go-live (data loss or the site going down).
   🟠  Should fix before go-live.
   🟢  Fix when convenient.



---------------------------------------------------------------------------------------------------

## 2. Summary

1. No security holes found. Sessions, cookies, CSRF, passwords, permissions, file access, log masking
   and the nginx setup are all solid (section 6 lists what was checked).

2. One serious problem: `restore.sh` can empty the live database and still say "restore done" (CR1).

3. Ten "should fix" points. Most are about running in production: health checks that can't catch a
   broken home page, rate limits that are easy to get around (IPv6) or that block the office itself,
   emails lost when the mail server is down, and no friendly error page on the public site.

4. About thirty smaller points: business-rule edge cases, small frontend bugs, and cleanups.


Suggested order of work (one PR each, small and testable):

   PR 1  Deploy safety:          CR1, CR2, CR3, CR11, CR34, CR35
   PR 2  Limits and email:       CR5, CR6, CR7, CR10
   PR 3  Business rules:         CR8, CR9, CR12 to CR18
   PR 4  Public site and portal: CR4, CR25 to CR30
   PR 5  Small cleanups:         everything else



---------------------------------------------------------------------------------------------------

## 3. Findings

### 🔴 Must fix


CR1. `restore.sh` can wipe the database and still print "restore done"  🔴

   Where: `deploy/restore.sh:35-37` (database), `deploy/restore.sh:42` (files)

   i.    The restore runs `{ echo "DROP SCHEMA ..."; pg_restore ...; } | psql --single-transaction`.
         In a pipe, only the exit code of the last command (`psql`) counts.
   ii.   If `pg_restore` fails (wrong file, arguments swapped, a plain `.sql` dump), `psql` still gets
         the DROP / CREATE lines, runs them and commits. Then `alembic upgrade head` makes empty
         tables, and the script prints "restore done". Production is now empty.
   iii.  The files step does `find ... -delete && tar xzf -`: every uploaded file is deleted before
         `tar` has checked the archive. A bad `.tgz` leaves zero files.
   iv.   Only the safety backup taken in step 1 saves you, and nothing tells the operator to use it.

   Fix:

   a.  Check both files before touching anything:
       ```bash
       $COMPOSE exec -T db pg_restore -l < "$db_file" > /dev/null || { echo "Not a valid DB backup: $db_file"; exit 1; }
       [ -z "$files_file" ] || tar tzf "$files_file" > /dev/null || { echo "Not a valid files backup: $files_file"; exit 1; }
       ```
   b.  Turn the backup into SQL first, and only then drop the schema:
       ```bash
       $COMPOSE exec -T db sh -c 'set -e
         trap "rm -f /tmp/r.dump /tmp/r.sql" EXIT
         cat > /tmp/r.dump
         pg_restore --no-owner --no-privileges -f /tmp/r.sql /tmp/r.dump
         { echo "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"; cat /tmp/r.sql; } \
           | psql -U kjs -d kjs -v ON_ERROR_STOP=1 --single-transaction -q' < "$db_file"
       ```
       The `trap` deletes the two temp files even when a step fails. Without it, `set -e` stops the
       script before the cleanup, and a full copy of the database (password hashes, customer contacts)
       stays in the container's `/tmp`.
   c.  Files: extract into a new folder first, then swap it in.
   d.  Test: run `restore.sh` with a wrong file and check that the data is still there.



### 🟠 Should fix


CR2. Health checks pass even when the home page is broken  🟠

   Where: `frontend/src/app/[locale]/(public)/(home)/loading.tsx`, `deploy/deploy.sh:31`,
          `frontend/Dockerfile:40`

   i.    `deploy.sh` marks a deploy as good only if `curl -f http://127.0.0.1:8080/` succeeds. The
         Docker HEALTHCHECK checks `/` too.
   ii.   PR #6 added `loading.tsx` to the home page. Next.js now sends "200 OK" plus the loading
         skeleton straight away, and the real page follows later in the same answer. If the page
         then crashes, the status is already 200.
   iii.  So a release that breaks the home page is recorded as "deploy ok" and the container stays
         "healthy".

   Fix: check a page with no `loading.tsx`, or add a tiny route that does the same API call the home
   page needs, e.g. `app/healthz/route.ts` that calls `/public/products` and returns 500 on failure.
   Point `deploy.sh` and the Dockerfile at it.


CR3. Backups need the backend to be running, so a crashing backend blocks deploys and restores  🟠

   Where: `deploy/backup.sh:32` (called by `deploy.sh` and `restore.sh`)

   i.    The files backup uses `$COMPOSE exec -T backend tar ...`. `exec` only works on a running
         container.
   ii.   A bad release makes the backend crash on start. You push the fix and run `deploy.sh`. Its
         first step is `backup.sh`, which fails, so the deploy stops. Same with `restore.sh`, exactly
         when you need it most.

   Fix: read the files volume with a throwaway container (the pattern `restore.sh` already uses):
   ```bash
   $COMPOSE run --rm -T --no-deps --entrypoint tar backend czf - -C /srv/kjs_files . > "$files_file.tmp"
   ```


CR4. The public site has no error page and no time limit on API calls  🟠

   Where: `frontend/src/lib/api.ts:43` (fetch, no timeout), `api.ts:55` (throw);
          no `error.tsx` or `not-found.tsx` anywhere under `frontend/src/app`

   i.    `serverGet` throws when the API is down or answers 5xx. The products, category, product and
         private-label pages don't catch it. With no `error.tsx`, buyers see Next's bare "Application
         error" page: no header, no phone number, no WhatsApp button.
   ii.   No timeout: if the database is slow, the page waits until nginx gives up (504).
   iii.  After every deploy the page cache is empty, so the first minutes are exposed.
   iv.   `notFound()` shows Next's default 404, also without our header and footer.

   Fix:
   a.  `fetch(..., { signal: AbortSignal.timeout(8000), next: { revalidate: ... } })`.
       Careful: a `signal` turns off Next's de-duplication of identical fetches in one render. Pages
       that call `serverGet` for the same path twice (for example `generateMetadata` plus the page)
       would then call the API twice. Wrap those calls in React `cache()` so each runs once.
   b.  Add `app/[locale]/(public)/error.tsx` ('use client', "Try again" button, phone and WhatsApp).
       It catches crashes in the pages, but not in `(public)/layout.tsx` itself. For those, also add
       an `error.tsx` one level up (`app/[locale]/error.tsx`).
   c.  Add `app/[locale]/(public)/not-found.tsx`. It only shows when a page calls `notFound()`. A URL
       that matches no page at all (`/does-not-exist`) still gets Next's default 404, so also add a
       catch-all `app/[locale]/[...rest]/page.tsx` that calls `notFound()`.
   d.  Check b and c against the Next 16 docs before writing them; these rules are easy to get wrong.


CR5. A stranger can still lock the admin out (backlog section 9 says this is fixed)  🟠

   Where: `backend/app/services/auth_service.py:52`, `backend/app/core/rate_limit.py:76`

   i.    There are two lockout counters. The per email + network one (10 tries) is fine.
   ii.   The second one, `login_email_failures` (100 failures in 15 min from any network), blocks the
         real person too, even with the right password from the office.
   iii.  An attacker sends 10 wrong passwords from each of 10 addresses (easy with IPv6, see CR6, or
         Tor). The admin then gets "Too many wrong passwords" for 15 minutes, and the attacker can
         repeat this forever.
   iv.   The test `test_a_stranger_cannot_lock_someone_else_out` only uses one attacker network, so
         it doesn't catch this.

   Fix:
   a.  Fix CR6 first (it makes this much harder).
   b.  Remember networks where this person logged in successfully, and don't let the any-network
       counter block them:
       ```python
       # the check
       if login_failures.blocked(lock_key) or (
               login_email_failures.blocked(email) and not known_network(email, ip_hash)):
       ```
       Where `known_network` reads from:
       i.    Not a plain dict in memory. It is empty after every deploy or restart (exactly when an
             attacker can lock the admin out again), and it never forgets a network.
       ii.   Better: the database, for example the `ip_hash` of this person's successful logins in the
             last 30 days. If no table has that yet, a small `login_networks` table is a migration:
             decide first.
   c.  Test: 10 attacker networks, then a correct login from the office network still works, also
       after an API restart.


CR6. Every IPv6 address gets its own rate limit, so all per-IP limits can be skipped  🟠

   Where: `backend/app/core/deps.py:67` (`client_ip`), `backend/app/core/security.py:41` (`hash_ip`)

   i.    Most home and mobile internet connections get a whole IPv6 "/64" block: billions of
         addresses. Our limits count each address separately.
   ii.   A bot rotating through its own block gets past every per-IP limit: enquiries (5 per hour),
         sign-ups, Koko and login. Unlimited spam leads mean a notification and an email to staff for
         each one. Koko spam uses up the daily AI budget, and real visitors get the fallback answer.

   Fix: count a whole IPv6 /64 block as one visitor, but only for the limits:
   ```python
   def rate_key(ip: str | None) -> str | None:
       """Rate-limit key: one IPv6 /64 block counts as one visitor."""
       try:
           addr = ipaddress.ip_address(ip)
       except (TypeError, ValueError):
           return ip  # 'testclient' in tests, or a bad header: keep it as it is
       if addr.version == 6 and addr.ipv4_mapped:
           return str(addr.ipv4_mapped)  # ::ffff:1.2.3.4 is really an IPv4 visitor
       if addr.version == 6:
           return str(ipaddress.ip_network(f"{addr}/64", strict=False))
       return str(addr)
   ```
   i.    Don't put this inside `client_ip()`. Its result is also hashed and saved in leads, audit
         logs and content rows, and those should keep the real address.
   ii.   Today each endpoint passes one `hash_ip(client_ip(request))` that the service uses for both
         the limit and the saved row. Pass a second value for the limiters,
         `hash_ip(rate_key(client_ip(request)))`, and keep the saved one as it is.
   iii.  The `try` matters: without it, a bad address gives a 500 on every login, sign-up, enquiry
         and Koko call. The `ipv4_mapped` line stops all IPv4 visitors on a dual-stack server from
         sharing one /64 limit.


CR7. The office shares one IP, so the login and sign-up limits will block KJS staff  🟠

   Where: `backend/app/core/rate_limit.py:77-78`, `backend/app/services/auth_service.py:51`

   i.    `login_ip_limiter.check()` counts every login, including successful ones: 30 per network
         per 15 minutes. `signup_limiter` allows 5 sign-ups per network per hour.
   ii.   Everyone in the KJS office reaches us from one public IP.
   iii.  Go-live day: the 6th person to sign up from the office in an hour gets "Too many requests".
         A Monday morning with 30+ logins between 09:15 and 09:30: the next person waits 15 minutes.

   Fix:
   a.  Count only failed logins for the per-IP limit (`blocked()` at the start, `hit()` on failure,
       same as `login_failures`).
   b.  Move both numbers to `config/app.ini` (for example 100 and 30).
   c.  Optional: an allow-list for the office IP, if KJS IT gives it to us.


CR8. Turning a feature off only hides it; the API still works  🟠

   Where: `config/features.ini` is only read for the frontend (`core/config/ini.py`);
          `api/v1/endpoints/koko.py` and `public.py` never check it

   i.    `koko = false` hides the chat button, but `POST /api/v1/koko/chat` still calls the AI.
         `configurator = false` still accepts leads with `source="configurator"`.
   ii.   A bot is spamming Koko and the admin turns Koko off to stop the cost. The bot calls the API
         directly and keeps spending AI calls up to the daily limit, every day.

   Fix: at the top of `koko_chat`:
   ```python
   if not cfg().features.koko:
       raise AppError(404, "off", "Koko is off.")
   ```
   Same check in `lead_service.create` for sources whose feature is off. Add a test per flag.


CR9. A disabled employee's open batch of buyers is stuck forever, and admins can't see it  🟠

   Where: `backend/app/services/auth_service.py:134` (`set_status`), `assign_service.py`
          (`has_open`, `update_record`, `overview`)

   i.    Buyers in an open batch have status `assigned`, and only the batch owner can change them.
   ii.   Disabling a user doesn't touch their batch, no admin screen can take it back, and the
         overview lists only active users, so it is hidden too.
   iii.  An employee leaves with 20 buyers half done. Those buyers are never given to anyone again
         and don't show as "unassigned" either. Same during a long leave.

   Fix: when a user stops being active, give their unfinished buyers back:
   ```python
   open_b = await db.scalar(select(Batch).where(Batch.user_id == user.id, Batch.status == "open"))
   if open_b:
       await db.execute(update(BuyerRecord)
                        .where(BuyerRecord.batch_id == open_b.id, BuyerRecord.status == "assigned")
                        .values(status="new", batch_id=None))
       open_b.status = "done"
   ```
   Optional: a "take back batch" button for `assign.manage`. Add a test.


CR10. When the mail server is down, emails are lost for good, about one every 3 minutes  🟠

   Where: `backend/app/services/notification_service.py:131-145`

   i.    When `_smtp_connect()` fails, the error is re-raised inside the per-email `try`, so the first
         email of the batch gets `email_attempts += 1`.
   ii.   The job runs every minute. The same oldest email takes the failure each time; after 3 runs it
         is marked `failed` and never retried. Then the next email starts losing attempts.
   iii.  A one-hour mail outage loses about 20 emails, including new-lead and SLA alerts.

   Fix: a failed connection is not this email's fault. When the connect fails, put every claimed row
   back to `pending` without touching `email_attempts`, and stop this run. Count attempts only when
   `send_message` itself fails. Test: connection fails 5 runs in a row, then works, and every email is sent.


CR11. The running API has the database superuser password  🟠  (adds to R7)

   Where: `deploy/docker-compose.prod.yml:39` (`env_file: .env`),
          `deploy/.env.production.example:19` (`MIGRATION_DATABASE_URL`)

   i.    The API container gets `MIGRATION_DATABASE_URL`, which holds the password of `kjs`, the
         Postgres superuser. This undoes the "least privilege" `kjs_app` user from `grants.sql`.
   ii.   If the app were ever broken into, the attacker would get superuser, and with it shell
         commands on the database container (`COPY ... TO PROGRAM`).

   Fix: only the migration step needs it.
   a.  Remove it from the long-running container's env file. Keep it in a file only the scripts read.
   b.  Pass it to **both** places that run migrations: `deploy.sh` and `restore.sh` (step 5):
       `$COMPOSE run --rm -e MIGRATION_DATABASE_URL="$MIGRATION_DATABASE_URL" backend alembic upgrade head`
   c.  Make `alembic/env.py` refuse to run when `MIGRATION_DATABASE_URL` is empty. Today it silently
       falls back to `DATABASE_URL` (see CR24 vi). If `restore.sh` were missed in b, the migration
       would run as `kjs_app` with no right to change tables and fail half-way through a restore.
   d.  Do this together with R7 (one env file per service).



### 🟢 Fix when convenient: backend


CR12. Re-opening a lead that was closed on time sends a false "not closed in time" alert  🟢

   Where: `backend/app/services/lead_service.py:192` (reopen), `:260` (`sla_check`)

   i.    R4 covers a lead at level 2. This is the other case: a lead closed on time has level 0 or 1.
         Re-opening it clears `resolved_at`, and the resolve timer still counts from `created_at`.
   ii.   A lead was closed in 30 minutes. A week later the buyer replies and staff click Reopen.
         Within a minute everyone gets "Lead not closed in time", and the breach count goes up.

   Fix: save a `reopened_at` and count the resolve timer from it (same root as R3 / R4). Quick
   version: set `escalation_level = 2` when leaving "closed". Add a test.


CR13. "Step done" and "finish board" at the same moment leave open tasks on a finished board  🟢

   Where: `backend/app/services/board_service.py:255` (`_step_for_action`), `:301` (`finish`)

   i.    The two actions take different locks. `complete_step` reads "board is active" before
         `finish` commits, then starts the next step and creates its tasks after `finish` already
         closed the board's tasks.
   ii.   Result: tasks of a cancelled board stay "todo" and show overdue forever (what A70 was meant
         to stop).

   Fix: lock the board row first in `_step_for_action` (`_board(db, code, lock=True)`), then check
   membership. Both actions then wait for each other.


CR14. A night-shift missed punch can't be fixed  🟢

   Where: `backend/app/services/attendance_service.py:168-171`

   i.    Both times are placed on the same `day`, and "check-out before check-in" is refused.
   ii.   Someone works 22:00 to 06:00 (allowed, A68) and forgets to check out. Asking for 22:00 / 06:00
         is refused.

   Fix:
   ```python
   now = datetime.now(timezone.utc)
   if end and end <= start:
       end += timedelta(days=1)  # check-out is the next morning
   if start > now or (end and end > now):
       raise AppError(422, "future_time", "Times can't be in the future.")
   ```
   Then refuse only if longer than `MAX_SHIFT`. The future check is needed because only `day` is
   checked today: at 23:00, "22:00 to 06:00 today" would make a check-out tomorrow morning, which
   hasn't happened yet.


CR15. Background jobs can alert about something that was just fixed  🟢

   Where: `lead_service.py` (`sla_check`), `board_service.py` (`board_alerts`)

   i.    The job reads lead 42 as "new". At that moment the employee logs a call and saves. The job
         then emails everyone "Lead not answered in time" about a lead that was just answered. Same
         for a board step marked done at that moment.

   Fix: `.with_for_update(skip_locked=True)` on both job queries (`of=BoardStep` in the board one).
   A row being edited is skipped and checked fresh next minute.


CR16. Board tasks let one employee edit colleagues' tasks  🟢

   Where: `backend/app/services/board_service.py:193` (`created_by=actor.id`),
          `backend/app/services/task_service.py:70` (the creator may edit)

   i.    When A marks step 1 done, every step-2 task for B and C is saved as "created by A".
   ii.   A can now change B's and C's tasks (mark done, change due date) without `tasks.assign`.

   Fix: `created_by=board.created_by` (or `None`) for tasks the board makes.


CR17. Buyer import: two gaps in the duplicate check  🟢

   Where: `backend/app/services/assign_service.py` (`import_records`)

   i.    Rows without an email are matched by company name only. "Metro Cash & Carry" in five
         cities with phone numbers only: one is imported, four are skipped as "already imported".
         Fix: when the email is empty, match by company + phone.
   ii.   Two uploads of the same file at the same moment both import everything (the "clicked twice"
         case A72 meant to stop). Fix: `SELECT pg_advisory_xact_lock(...)` at the start of the import.


CR18. "My leads" has no paging and can hide old open leads  🟢

   Where: `backend/app/api/v1/endpoints/employee.py:38`

   i.    It returns the newest 200, closed ones included. An old lead still in "contacted" (a long
         negotiation) falls off the list.

   Fix: add `offset` like the admin list, or by default show all open leads plus the last N closed.


CR19. A product with a long name: uploading its file gives a 500 and leaves a stray file  🟢

   Where: `backend/app/models/file.py:22` (`owner_id` is `String(60)`),
          `backend/app/services/catalog_service.py:15` (slugs up to 110 characters)

   i.    "Premium Instant Coffee Stick Pack Private Label Export Grade 2g" has a slug over 60
         characters. Uploading its photo: the file is saved to storage, then the database insert
         fails ("value too long"), the admin sees a 500, and the file stays in storage with no row.

   Fix: a migration widening `files.owner_id` to `String(120)` (and the model). In `upload()`, if the
   database insert fails after `put`, delete the stored file.


CR20. Holiday name has no length limit (500 instead of a clear error)  🟢

   Where: `backend/app/api/v1/endpoints/admin.py:192-194`

   i.    `HolidayIn.name: str` has no limit, but the column is `String(120)`; an empty name is also
         accepted.

   Fix: `name: OneLine = Field(min_length=2, max_length=120)`. Worth one pass over every input model
   to check that its `max_length` matches its column size.


CR21. Product names with no English letters get an empty web address  🟢

   Where: `backend/app/services/catalog_service.py:14` (`slugify`)

   i.    `slugify("चॉकलेट बार")` returns `""`. The product's page address becomes `/products/`
         (unreachable), and the next such product gets "already exists".

   Fix: `if not slug: raise AppError(422, "bad_name", "Name needs at least one English letter or number.")`


CR22. With R2 storage, public spec sheets always download instead of opening  🟢

   Where: `backend/app/services/file_service.py:155`, `backend/app/core/storage.py` (`url`)

   i.    `download()` always asks R2 for `response-content-disposition: attachment`, even for public
         website files that should open in the browser.

   Fix: pass an `inline` flag through `download()` to `url()` and use it for public files.


CR23. Seeding the catalogue can add products into a hidden category  🟢

   Where: `backend/app/seed_catalogue.py:257` and below

   i.    The seed reuses any category with the same slug, including one an admin has turned off.
         New products go into it as active, but the site hides products of inactive categories, so
         they never show, and the script still prints "added".

   Fix: skip (or warn about) categories that are inactive, or turn them back on explicitly.


CR24. Smaller backend points  🟢

   i.    `analytics_service.py:58-60`: "tasks done" is grouped by name, so two staff with the same
         name are merged. Group by `User.id, User.name`.
   ii.   `board_service.py` (`add` + `_start_step`): step-1 members get two notifications and two
         emails for one event. Skip `board.added` for them.
   iii.  `attendance_service.py`: the approver can't see the person's real punches for the day being
         corrected. Show the current check-in / check-out next to the request. A "within 30 days"
         limit needs a decision: log it as an A-item.
   iv.   `jobs/runner.py:66-70`: the comment says the lock makes each job run once per tick, but the
         lock ends at the first `commit()`. `send_emails` commits often (safe anyway thanks to
         `SKIP LOCKED`). Fix the comment so nobody relies on it.
   v.    `backend/requirements.txt`: `pytest`, `pytest-asyncio`, `freezegun` are installed in the
         production image. Move them to `requirements-dev.txt`.
   vi.   `backend/alembic/env.py`: if `MIGRATION_DATABASE_URL` is empty it falls back to the pooled
         URL without turning off the statement cache, so migrations through the Neon pooler can
         fail. Require the direct URL, or use the same `connect_args` as the app.
   vii.  `auth.py:61`: `ProfileIn.phone` is a plain `str`; sign-up uses `OneLine`. Use `OneLine` so a
         line break can't get into a phone number that ends up in emails.



### 🟢 Fix when convenient: frontend


CR25. Task due times use the laptop's time zone, but the page says "IST"  🟢

   Where: `frontend/src/app/[locale]/(employee)/employee/tasks/page.tsx:40`

   i.    `new Date(f.due)` reads the time in the laptop's zone. A salesperson in Dubai sets "17:00"
         and it is saved as 18:30 IST.

   Fix: same as the website admin page: `new Date(\`${f.due}:00+05:30\`).toISOString()`. Better, move
   that helper into `portal/ui.tsx` and use it in both pages.


CR26. Koko widget: double leads, small screens, screen readers  🟢

   Where: `frontend/src/components/public/KokoChatWidget.tsx:56`, `:80`

   i.    `sendLead` has no "busy" guard: a double-click sends two leads and two staff alerts. Add a
         `sending` state and disable the button.
   ii.   The panel is a fixed 520 px tall. On a phone held sideways (~375 px) the close button is off
         screen. Use `h-[min(520px,calc(100dvh-2.5rem))]`.
   iii.  Replies aren't announced to screen readers and the input has only a placeholder. Add
         `aria-live="polite"` on the message list and an `aria-label` on the input.


CR27. Portal stays on "Loading..." forever if the session check fails with anything but 401  🟢

   Where: `frontend/src/components/portal/PortalShell.tsx:64-67`

   i.    A 500, a 502 during a deploy, or no network leaves the page on "Loading..." with no message.
   ii.   The check also runs again on every page change (`pathname` in the effect's list), which
         costs the slow `/auth/me` call (R30) each time.

   Fix: show "Can't reach the server. Retry" on other errors; run the check once on mount and read the
   pathname from a ref for the redirect.


CR28. After login, a portal link loses its query string  🟢

   Where: `frontend/src/proxy.ts:24`

   i.    `/admin/leads?status=new` becomes `/admin/leads` after the login redirect.

   Fix: clear the copied query first, then put the whole address in `next`. `safeNext` already checks it.
   ```ts
   const url = req.nextUrl.clone();
   url.pathname = '/employee/login';
   url.search = '';  // the clone still has ?status=new; it belongs in next, not on the login page
   url.searchParams.set('next', pathname + req.nextUrl.search);
   ```


CR29. Home page: empty banner text when one API call fails  🟢

   Where: `frontend/src/app/[locale]/(public)/(home)/page.tsx:56`

   i.    `texts()` returns `{}` when `/public/texts` fails, and the fallback is now `''`. The comment
         "the backend always sends one" misses this case. The banner shows a headline with no text.

   Fix: put back a real fallback sentence (as the old page had).


CR30. Home page: "50+ product families" when there are none  🟢

   Where: `frontend/src/app/[locale]/(public)/(home)/page.tsx:132`

   i.    `products.length || '50+'`: with an empty catalogue (fresh setup, or the call failed) the
         panel says "50+" while the section below says the list is "being published".

   Fix: hide that stat when the list is empty.


CR31. Home page: the only `h1` is hidden  🟢

   Where: `frontend/src/app/[locale]/(public)/(home)/page.tsx:95`

   i.    The `h1` is `sr-only` (invisible) and the visible headline is an `h2` inside a carousel
         slide. Search engines may give hidden headings less weight.

   Fix: make the first slide's headline the visible `h1`.


CR32. `Reveal.tsx` measures every waiting block on every scroll  🟢

   Where: `frontend/src/components/public/Reveal.tsx:26`

   i.    Each scroll event calls `getBoundingClientRect` on each of the ~25 blocks still hidden, on
         top of the IntersectionObserver that already watches them. This can make scrolling jerky on
         cheap phones.

   Fix: rely on the IntersectionObserver, or check once per frame (`requestAnimationFrame`) / on
   `scrollend`.


CR33. `npx tsc --noEmit` fails on a fresh clone  🟢

   Where: `frontend/next-env.d.ts` (removed from git), `docs/kb.md:746`

   i.    CI runs `next typegen` first, but `kb.md` tells you to run `npx tsc --noEmit`. On a fresh
         clone that shows type errors that aren't real.

   Fix: update `kb.md`: "run `npx next typegen` first", or add a `"typecheck"` script in
   `package.json` that does both.



### 🟢 Fix when convenient: deployment and CI


CR34. Postgres says "ready" too early on the very first start  🟢

   Where: `deploy/docker-compose.prod.yml:27`

   i.    `pg_isready` without `-h` checks the local socket. On first start, Postgres runs its setup
         scripts on a temporary server that only listens there, then restarts. The first `deploy.sh`
         can run migrations during that restart and fail. Running it again works.

   Fix: `pg_isready -h 127.0.0.1 -U kjs -d kjs`


CR35. `deploy.sh` runs its old self after `git pull`  🟢

   Where: `deploy/deploy.sh:12`

   i.    bash keeps reading the file it already opened. A PR that adds a deploy step only takes
         effect on the second deploy after the merge.

   Fix: pull, then restart the new script once (this line replaces `git pull --ff-only`, after the `cd`):
   ```bash
   if [ -z "${KJS_REEXEC:-}" ]; then git pull --ff-only; KJS_REEXEC=1 exec "./$(basename "$0")" "$@"; fi
   ```
   Not `exec "$0"`: the script has already done `cd "$(dirname "$0")"`, so a relative `$0` like
   `deploy/deploy.sh` would point at `deploy/deploy/deploy.sh`, and the deploy would stop after the pull.


CR36. CI tests on Postgres 16, production runs Postgres 17  🟢

   Where: `.github/workflows/ci.yml:19` (`pgvector/pgvector:pg16`), `deploy/docker-compose.prod.yml:16`

   Fix: use `postgres:17-alpine` in CI and in the root `docker-compose.yml` test database. No
   migration uses pgvector.


CR37. The AI review workflow fails on PRs from forks and loads an unpinned plugin  🟢

   Where: `.github/workflows/claude-code-review.yml:4`, `:39`

   i.    It runs on every `pull_request`. Fork and Dependabot PRs get no secrets, so it fails with a red ✗.
         Fix: `if: github.event.pull_request.head.repo.full_name == github.repository`
   ii.   `plugin_marketplaces` points at another repo's main branch, so it runs whatever is there that
         day. Pin it to a commit (same idea as R8).
   iii.  Checked and fine: no `pull_request_target`, no untrusted text in `run:` steps, read-only
         token, only people with write access can trigger the bot.


CR38. `superset/` is unused and unsafe if anyone starts it  🟢

   Where: `superset/`, `.env.example` (`SUPERSET_ADMIN_PASSWORD=admin`)

   i.    No compose file uses it. No `SECRET_KEY`, default password `admin`, open CORS.

   Fix: delete it, or add a README line "not used, see backlog".


CR39. Process: new ideas were not added to `kb.md`  🟢

   i.    PR #6 brought in createPortal, IntersectionObserver, `next typegen`, the `inert`
         attribute, CSS `:has()`, `loading.tsx` streaming and capture-phase listeners. `prompt.md`
         says every new idea goes into `kb.md`; most are missing.

   Fix: add 2 or 3 lines for each.



---------------------------------------------------------------------------------------------------

## 4. Tests that are missing

1. Backend

   i.    `restore.sh` with a wrong file (CR1).
   ii.   Login lockout with 10 attacker networks, then a correct login from the office (CR5).
   iii.  Mail server down for several runs, then back: no email lost (CR10).
   iv.   Each feature flag off: its API refuses (CR8).
   v.    Disabling a user with an open batch (CR9).
   vi.   Reopen a closed lead, then run `sla_check` (CR12).
   vii.  Finish a board while a step is being marked done (CR13).
   viii. Night-shift regularization (CR14).
   ix.   `sla_check` racing a status change (CR15).
   x.    "Run now" and the auto-assign job at the same time.
   xi.   Two imports of the same file at once (CR17).
   xii.  `add_note(kind="call")` on an unassigned lead takes ownership.
   xiii. Employee lead list beyond 200 (CR18).

2. Frontend (needs a test tool such as Vitest: a new dependency, so decide first)

   i.    `safeNext` and `safeLink`: `//x`, `/\x`, `/\t/x` are refused.
   ii.   `catalogue.ts` parsers, including Windows line breaks (R22).
   iii.  Public pages still render something useful when the API is down (CR4).

3. Scripts: run `shellcheck` on `deploy/*.sh` in CI.



---------------------------------------------------------------------------------------------------

## 5. Already in the backlog and still open

This review hit these again. They are already written up in `backlog.md` section 10; no new entry.

1. R17: carousel pauses only on mouse hover. Also: a keyboard user loses focus when the slide
   changes, and it keeps moving for "reduce motion" users.
2. R18: quick view copies the modal; it is also not a portal, so it would break inside a moved
   element the way EnquiryButton did.
3. R19 + R22: product items read from description text with a strict pattern.
4. R21 + R26: progress bar runs for 10 s on download links / failed navigation. Better long-term fix:
   use Next 16's router hook (`onRouterTransitionStart` in `instrumentation-client.ts`) instead of
   guessing from clicks; that removes the 10 s timer and `data-no-progress`.
5. R24: carousel picture keys use the image path.
6. R7: extended by CR11 above.



---------------------------------------------------------------------------------------------------

## 6. Checked and looks fine

1. Sessions: random 32-byte token, only its hash stored, UTC expiry. Cookie is HttpOnly, SameSite=Lax,
   Secure in production. Disabling a user or changing a password ends their other sessions.

2. CSRF: every request that changes data needs the `x-requested-with` header, and CORS only allows it
   from our own sites. Unsafe origins are refused at start in production.

3. Passwords: scrypt, constant-time compare, run off the main thread, dummy hash so "no such user"
   takes as long as "wrong password". No reset flow, so no reset-token risks.

4. Permissions: every route has the right permission check. A non-admin approver can't touch admins,
   re-enable accounts, or give permissions they don't have.

5. Files: type and size checked, storage names built only from a safe name, the local driver refuses
   paths outside its folder, downloads sent with `nosniff` and a sandbox, public site sees only public
   files of live products, board files only for members.

6. Client IP: Cloudflare / forwarded headers trusted only from our own proxy, matching nginx.

7. Logs: emails and phones masked, secrets hidden, query values hidden, request ids checked.

8. Errors: only real duplicates give 409; one error shape with the request id.

9. Config: a bad `.ini` change is refused and the last good config stays; production refuses weak
   secrets, localhost origins and non-https addresses.

10. Business rules: SLA working-minutes maths (nights, Sundays, holidays, IST to UTC), escalation sends
    each alert once, lead locking, status rules (A69), auto-assign lock and fairness, one open batch,
    attendance locks and A67, board step plan and lock, task due "today" at IST midnight, email job
    claim and retry, seeds safe to run again.

11. Migrations match the models (read, not run), except CR19.

12. Frontend: no open redirect after login (`safeNext`), no XSS (the only `dangerouslySetInnerHTML` is
    escaped JSON-LD, Koko and admin text shown as plain text, links through `safeLink`), server fetches
    send no cookies so the page cache can't leak one person's data, no hydration problems found.

13. nginx: security headers on every location, big uploads only on the two upload addresses, real-IP
    handling matches the backend, CSP fits our assets.

14. Docker and scripts: containers run as non-root users, no secrets baked into images, Postgres only on
    127.0.0.1, backups written to a temp file and checked before old ones are deleted, `deploy.sh`
    records the new version only after the health check (but see CR2).

15. CI: `ci.yml` is read-only and has no untrusted input in its steps.
