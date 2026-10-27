# KB: knowledge base

Every word, tool and idea used in this project, explained simply.

How to use it: press Ctrl + F, type the word, and read the short entry.

Each entry has:

   What   what it is, in plain words
   Why    why this project uses it
   Where  where you find it in our code (when it applies)


Sections:

   1. Project words (KJS-specific)
   2. Web basics
   3. Tools on our PC
   4. Backend (Python, FastAPI, database)
   5. Frontend (Next.js, React)
   6. Security and privacy
   7. AI and Koko
   8. Testing
   9. Production and deployment
   10. Ideas and habits
   11. How we learn



===================================================================================================

## 1. Project words (KJS-specific)

### Koko

   What   The AI chat assistant on the public website.
   Why    Answers visitor questions 24/7 from KJS facts and turns interested visitors into leads.
   Where  `backend/app/services/koko_service.py`, `frontend/src/components/public/KokoChatWidget.tsx`.
          Facts are edited in Admin > Koko.


### Lead

   What   One enquiry from a possible buyer: a form, a gated button (price sheet, sample...), a Koko chat
          form, the private-label builder.
   Why    Every enquiry is saved so no buyer is missed. Each lead has an owner and an SLA timer.
   Where  `lead_service.py`, table `leads`, pages Admin > Leads and the employee dashboard.


### SLA (service level agreement)

   What   A promised time limit. For us: respond to a new lead in 20 minutes, resolve it in 60 minutes.
   Why    Fast replies win B2B orders.
   Where  `config/sla.ini`, `lead_service.py`. The clock counts only working minutes (assumption A5).


### Escalation

   What   When a lead passes its SLA time, people with `leads.view_all` get an alert.
   Where  `lead_service.py` (job `sla_check`).


### Lead outcome

   What   How a lead ended: quote sent, sample sent, order won, not interested, no reply, spam.


### Handover

   What   Passing a lead to a colleague, with a note.
   Where  Employee dashboard, `lead_service.py`.


### Gated actions / gate

   What   Price sheet, spec sheet, sample and quote buttons that ask for a short form first.
          After the first time, the browser remembers the visitor and the next request is one click.
   Why    Browsing stays free (good for Google), but serious requests become leads (decision D3).
   Where  `GatedActions.tsx`, `EnquiryForm.tsx`.


### Offers ticker

   What   A moving strip of offers at the top of the website, set by the admin.
   Where  `OffersTicker.tsx`, Admin > Website.


### Private label / configurator

   What   Private label = KJS makes a product that sells under the buyer's own brand.
          The configurator (private-label builder) lets a visitor pick product, pack, quantity and market.
   Why    Captures detailed requirements. No prices until KJS gives price bands (I3).
   Where  `/private-label` page, `Configurator.tsx`.


### Partner programme

   What   Brokers, retailers or freelancers who bring buyers to KJS. They apply on `/partners`.
   Where  `PartnerForm.tsx`, Admin > Website (applications). Text must be confirmed by KJS (A47).


### Batch / auto-assign

   What   Auto-assign gives each available employee a small batch of records (default 20) to work through.
          When they finish, they get the next one.
   Why    Work is spread fairly and nobody picks only the easy ones.
   Where  `assign_service.py`, `config/assign.ini`, Admin > Auto-assign, Employee > My batches.


### Record

   What   One row of a buyer list imported from Excel or CSV (company, contact, phone, country, category...).
          This is our guess of what "record" means (assumption A1, decision D9).
   Where  Table `buyer_records`, `assign_service.py`.


### Category (of an employee)

   What   The product categories an employee handles (coffee, tea...). Auto-assign only gives them records
          from those categories.


### Availability / "receiving tasks"

   What   An on/off switch each employee controls. Off = no new batches.


### Attendance / check-in / check-out

   What   Employees press Check in and Check out. The server's clock is used, not the phone's.
   Where  `attendance_service.py`, Employee > Attendance, Admin > Team attendance.


### Regularization / missed punch

   What   A request to fix a forgotten check-in or check-out. Someone else approves it.
   Where  Employee > Attendance, Admin > Approvals.


### Shift / late

   What   Working hours: 09:30 to 18:30 IST. Check-in after 09:45 = late (assumption A4).
   Where  `config/app.ini`.


### Working days / holidays

   What   Monday to Saturday, minus the holidays the admin enters. Sunday is off.
   Why    Used by attendance, SLA timers, auto-assign and order-board deadlines.
   Where  `calendar_service.py`, Admin > Holidays.


### Order board

   What   One customer order, tracked as steps (for example sourcing, production, packing, quality, dispatch)
          against a final deadline. Has a code like `ABC117-3`, members, tasks and files.
   Where  `board_service.py`, Admin > Order boards, Employee > My order boards.


### Step / step split

   What   A part of an order board with its own planned start and end. The days are split by % or by
          fixed days, counting only working days.


### Threshold alerts (50 / 85 / 100%)

   What   When a step has used 50%, 85% and 100% of its time, its members get an alert, once each.
   Where  `board_service.py`, `config/alerts.ini`, Admin > Alerts.


### Task

   What   A to-do for one employee, with a due date. Can come from a board step, the admin, or yourself.
   Where  `task_service.py`, Employee > Tasks.


### Approvals inbox

   What   One admin page for everything waiting for a yes/no: new staff, missed punches, file deletions.
   Where  Admin > Approvals.


### Audit log

   What   A list of who did what and when. Nobody can edit or delete it (a database trigger blocks it).
   Why    Trust and accountability.
   Where  `audit_service.py`, table `audit_log`, Admin > Audit.


### Role / permission

   What   A permission is one allowed action, like `leads.view_all`. A role (admin, employee) is a default
          set of permissions. The admin can add extra ones per person.
   Where  `backend/app/core/permissions.py`.


### Notification / bell

   What   An in-app message (the bell icon in the portal), also sent by email when SMTP is set up.
   Where  `notification_service.py`, `Bell.tsx`.


### Phase / Stage

   What   Stage 1 = everything for go-live on 11 Dec 2026. Stage 2 = buyer intelligence and outreach (2027).
          Phase 1 = the 2-week build of all Stage 1 features (26 Oct to 7 Nov).


### Checklist

   What   `docs/checklist.md`, the one list we work from day to day.


### IDs in the backlog (A, B, D, I, M)

   What   A = assumption we made, B = blocker, D = decision, I = input from KJS, M = missing document.
   Where  `docs/backlog.md`.


### Screen IDs (P1, E1...)

   What   Names from the design files. P = public page, E = employee, A = Stage 2 admin screens.
   Where  `memory.md` section 7.


### UAT (user acceptance testing)

   What   KJS staff try the real system and confirm it does what they need, before go-live.


### Go-live

   What   The day the system is switched on for real use: Fri 11 Dec 2026.


### IST / UTC

   What   IST = India time (UTC + 5:30). UTC = world standard time.
   Why    We store every time in UTC and show it in IST, so there is never confusion.



===================================================================================================

## 2. Web basics

### HTTP

   What   The language browsers and servers use. A request (method + address + headers + body) gets a
          response (status + headers + body).


### HTTP methods

   What   GET = read. POST = create. PATCH = change part. PUT = replace. DELETE = remove.


### Status codes

   What   200 ok, 201 created, 400 bad input, 401 not logged in, 403 not allowed, 404 not found,
          409 conflict, 422 invalid data, 429 too many requests, 500 our bug.


### JSON

   What   A text format for data: `{"name": "Omar", "qty": 5000}`. Our API sends and receives JSON.


### API / endpoint / route

   What   API = the set of addresses our backend answers. One address + method = an endpoint (route),
          like `GET /api/v1/employee/leads`.
   Where  `backend/app/api/v1/endpoints/`. Live list: http://localhost:8000/docs


### REST

   What   A common style for APIs: addresses are things (`/leads/5`), methods are actions (GET, PATCH).


### Header

   What   Extra information sent with a request or response, like `x-request-id` or `cookie`.


### Cookie

   What   A small value the browser stores and sends back automatically. Our login is a cookie called
          `kjs_session`.


### localhost / port

   What   localhost = this PC. A port is a numbered door. Our frontend is on 3000, the backend on 8000,
          the test database on 5433.


### Proxy / rewrite

   What   A middleman that forwards requests. Next.js forwards `/api/*` to FastAPI, so the browser only
          ever talks to one address.
   Where  `frontend/next.config.mjs` (rewrites).


### Reverse proxy

   What   A server in front of our app that receives all internet traffic and passes it on (nginx in production).


### CORS

   What   A browser rule that blocks one website from calling another website's API unless allowed.
   Why    Because of the proxy, our browser calls stay on one address, so we barely need CORS.


### URL slug

   What   The readable part of an address: `/products/instant-coffee-3-in-1-stick`.
          Ours never changes when a product is renamed (A51).



===================================================================================================

## 3. Tools on our PC

### Git

   What   Saves the history of our code. Each save is a commit.


### Commit

   What   One saved change, with a message. Example: `feat: complete Phase 1`.


### Branch

   What   A separate line of work. We work on `kjs_v`; Vineet merges it into `main`.


### Push / pull

   What   Push = send commits to GitHub. Pull = get other people's commits.


### Merge / pull request (PR)

   What   Merge = join one branch into another. A PR is a request on GitHub to merge, where it gets reviewed.


### GitHub / gh

   What   GitHub hosts our repo online. `gh` is GitHub's command-line tool.


### .gitignore

   What   A list of files git must never save (`.env`, `node_modules`, `docs/`, storage folders).


### Node.js / npm

   What   Node runs JavaScript outside the browser (needed by Next.js). npm installs JavaScript packages.
   Commands  `npm ci` (install exactly from the lock file), `npm run dev`, `npm run build`.


### package.json / package-lock.json

   What   The list of JavaScript packages we use, and the exact versions installed.


### Python

   What   The language of our backend. We use 3.12.


### uv / venv

   What   uv is a fast tool that creates a Python virtual environment (venv) and installs packages.
          A venv is a private folder of packages for one project (`backend/.venv`).


### requirements.txt

   What   The list of Python packages and versions the backend needs.
   Where  `backend/requirements.txt`.


### Docker / image / container

   What   Docker packs an app with everything it needs (an image) and runs it the same way on any PC
          (a running image is a container).
   Why    Our test database runs in Docker. Production will run everything in Docker.


### Docker Compose

   What   One file (`docker-compose.yml`) that starts several containers together.
   Command  `docker compose --profile test up -d test-db`


### Docker Desktop / WSL 2

   What   Docker Desktop runs Docker on Windows. It needs WSL 2 (a small Linux inside Windows).


### PowerShell / Git Bash

   What   Two terminals on this PC. Bash commands (like `ls`, `cat`) work in Git Bash.


### make

   What   A tool that turns long commands into short ones (`make test`). Optional, not installed.


### ffmpeg

   What   A tool for video files. We used it to take screenshots from the demo video.


### Headless Chrome

   What   Chrome running without a window, controlled by a script. Our browser e2e test uses it.



===================================================================================================

## 4. Backend (Python, FastAPI, database)

### FastAPI

   What   The Python framework our API is built with.
   Why    Fast, simple, checks input automatically, and makes the `/docs` page for free.
   Where  `backend/app/main.py`, `backend/app/api/`.


### uvicorn / ASGI

   What   uvicorn is the server program that runs FastAPI. ASGI is the standard they use to talk.
   Command  `.venv/Scripts/python -m uvicorn app.main:app --reload --port 8000`


### Router / service / schema / model

   What   Our four layers for every feature:
             a.  router   reads the request and checks permission (thin, no logic)
             b.  service  does the business rule and writes the audit row
             c.  schema   the shape of the input and output (Pydantic)
             d.  model    the database table (SQLAlchemy)
   Where  `api/v1/endpoints/`, `services/`, `schemas/`, `models/`.


### Depends (dependency)

   What   FastAPI's way to run something before a route, like "who is logged in?" or "may they do this?".
   Where  `backend/app/core/deps.py` (`current_user`, `require_permission`).


### Pydantic

   What   Checks that data has the right shape and types (for example, email must be text).
   Where  `backend/app/schemas/`.


### pydantic-settings

   What   Reads settings from `.env` into a Python object.
   Where  `backend/app/core/config/__init__.py` (`settings`).


### async / await

   What   Lets the server work on other requests while it waits for the database or the internet.


### SQLAlchemy

   What   Lets Python talk to the database with Python code instead of raw SQL. We use version 2, async.
   Where  `backend/app/models/`, `backend/app/core/database.py`.


### asyncpg

   What   The driver that connects SQLAlchemy to PostgreSQL (async).


### PostgreSQL (Postgres)

   What   Our database. Stores users, leads, boards, everything except files.


### Neon

   What   A cloud service that hosts Postgres. Free tier. Sleeps after 5 minutes without use.
   Why    Development database until the company server is ready (D15).
   Note   Ours is in Ohio, so it is slow from India (B10).


### Pooled vs direct URL (Neon)

   What   Pooled URL = shared connections (for the app; prepared-statement cache must be off).
          Direct URL = one real connection (for migrations).
   Where  `.env`: `DATABASE_URL`, `MIGRATION_DATABASE_URL`.


### Connection pool / pool_pre_ping / pool_recycle

   What   The app keeps a few open database connections to reuse.
          pool_pre_ping checks a connection is still alive before using it.
          pool_recycle replaces connections older than 240 seconds.
   Why    Neon drops idle connections. Without these, the first request after a pause failed (fixed 24 Oct).
   Where  `backend/app/core/database.py`.


### Alembic / migration

   What   A migration is a small script that changes the database structure (add a table, a column).
          Alembic runs them in order and remembers which ones are done.
   Rule   One migration per change. Never edit one that has already been applied.
   Command  `.venv/Scripts/alembic upgrade head`
   Where  `backend/alembic/versions/` (0001 to 0009).


### Table / column / row

   What   A table is like a sheet. Columns are fields. Rows are the entries.


### Primary key / foreign key

   What   Primary key = the unique id of a row. Foreign key = a column pointing to a row in another table.


### Index / unique index

   What   An index makes searching fast. A unique index forbids duplicates (we use it so an alert is sent once).


### JSONB

   What   A Postgres column type that stores JSON. We use it for lists like an employee's categories.


### Transaction

   What   A group of database changes that all succeed or all fail together.
   Why    The audit row is written in the same transaction as the change it describes.


### Trigger

   What   Code inside the database that runs automatically on a change. Ours blocks edits to the audit log.


### FOR UPDATE SKIP LOCKED

   What   A database instruction: "lock these rows for me, and skip rows someone else has locked".
   Why    Two auto-assign runs can never hand the same record to two people.
   Where  `assign_service.py`.


### Advisory lock

   What   A named lock in Postgres. Our background loop takes one so only one copy runs the jobs at a time.
   Where  `backend/app/jobs/runner.py`.


### Background jobs / jobs loop

   What   Work that runs on its own every minute: SLA checks, board alerts, auto-assign, sending emails.
          Runs inside the API process, only 08:00 to 21:00 IST, Monday to Saturday.
   Where  `backend/app/jobs/runner.py`, `config/app.ini` (`jobs_*`).


### seed

   What   A script that fills a fresh database with the basics: categories and the first admin.
   Command  `.venv/Scripts/python -m app.seed`


### .env / environment variables

   What   Settings that change between computers, including secrets (database password, API keys).
          Never committed. `.env.example` shows every key with fake values.


### config/*.ini / cfg() / live reload

   What   Files with tunable values (SLA minutes, batch size, feature on/off, log levels).
          Edit and save, and the app uses the new value within about 3 seconds, no restart.
          `cfg()` is how the code reads them, at the moment it needs them.
   Override  An env var like `KJS__SLA__RESPOND_MINUTES=15` beats the file.
   Where  `config/`, `backend/app/core/config/ini.py`, Admin > Settings shows where each value came from.


### Feature flag

   What   An on/off setting for a feature (offers ticker, WhatsApp button, Koko), with no code change.
   Where  `config/features.ini`.


### Logging / JSON logs

   What   Every important event is written as one line of JSON, with time, level, message and request ID.
   Why    Easy to search later ("show me everything for request abc123").
   Where  `backend/app/core/logs.py`, `config/logging.ini`.


### Request ID

   What   A random id given to each request. It appears on every log line and in error messages.
   Why    A user can send us the id from an error, and we find exactly what happened.
   Where  `RequestContextMiddleware` in `logs.py`, header `x-request-id`.


### Masking

   What   Hiding emails, phone numbers and secrets in logs (`v***@kjsindia.com`).


### Error shape

   What   Every error from our API looks the same: `{code, message, details, request_id}`.
   Where  `backend/app/core/errors.py`.


### Middleware

   What   Code that runs on every request before and after the route (for example, adding the request ID).


### Rate limit

   What   A cap on how often someone can do something (5 enquiries per hour per visitor, 10 wrong logins).
   Why    Stops spam and password guessing.
   Where  `backend/app/core/rate_limit.py`, `config/app.ini`.


### httpx

   What   A Python package for calling other websites' APIs (Groq, WhatsApp).


### openpyxl

   What   A Python package that reads and writes Excel files. Used for buyer-list import and exports.


### phonenumbers

   What   A Python package that checks and formats phone numbers.


### python-multipart

   What   Lets FastAPI receive file uploads and forms.


### SMTP / smtplib

   What   SMTP is the standard way to send email. `smtplib` is Python's built-in tool for it.
   Where  `notification_service.py`, `.env` (`SMTP_*`).


### File storage / storage driver

   What   Where uploaded files go. `local` = a folder on disk. `r2` = Cloudflare R2.
          The database keeps only the file's key, name, size and owner.
   Where  `backend/app/core/storage.py`, `.env` (`STORAGE_DRIVER`).


### Cloudflare R2 / S3

   What   R2 is Cloudflare's file storage. It speaks the same language as Amazon S3. No download fees.


### SigV4 / presigned URL

   What   SigV4 = the signing method S3 and R2 use to prove a request is allowed.
          A presigned URL = a link to a private file that works for a few minutes only.
   Why    We wrote the signing ourselves (no new package) and checked it against Amazon's own example.
   Where  `storage.py` (`sigv4_presign`).


### Banker's rounding / half-up

   What   Python's `round(2.5)` gives 2 (banker's rounding). People expect 3 (half-up).
   Where  We use half-up for board %.



===================================================================================================

## 5. Frontend (Next.js, React)

### Next.js

   What   A framework on top of React for building websites. Renders pages on the server for speed and Google.
   Where  `frontend/`.


### App Router

   What   Next.js's way of mapping folders to addresses: `app/products/[slug]/page.tsx` = `/products/anything`.


### page.tsx / layout.tsx

   What   page = the content of one address. layout = the frame around pages (header, footer, sidebar).


### Route groups `(public)`, `(employee)`, `(admin)`

   What   Folders in brackets group pages without changing the address.


### [locale]

   What   The language part of the address. Hidden while we are English-only (A38).


### React / component

   What   React builds screens from components: small reusable pieces (a button, a form, a table).


### Server component / client component / "use client"

   What   Server components run on the server and send ready HTML (good for Google).
          Client components run in the browser and handle clicks; they start with `"use client"`.


### State / useState / useEffect

   What   State = values a component remembers (form text, open/closed).
          useEffect runs code after the screen shows (for example, loading data).


### TypeScript

   What   JavaScript with types. It catches mistakes before the code runs.
   Command  `npx tsc --noEmit` (type check).


### Tailwind CSS

   What   Styling by small class names in the HTML: `px-4 text-sm font-bold`.
   Where  `frontend/tailwind.config.ts`.


### next-intl

   What   Handles languages (translations, locale in the address).


### fetch cache / revalidate

   What   Next.js remembers results of server fetches. Ours are cached 60 seconds (A37).
   Warning  Next.js caches by address + headers. Adding a different header each time turns the cache off.


### Turbopack

   What   The new, faster bundler inside Next.js (turns our TypeScript into what the browser runs).
          Default for `npm run dev` and `npm run build` since Next.js 16.


### Async params (Next.js 15+)

   What   A page's `params` (like the `slug` in `/products/[slug]`) is now a Promise.
          Server pages: `const { slug } = await params;`. Client pages: `const { code } = use(params);`.
   Where  The 6 `[slug]` / `[code]` pages and `app/[locale]/layout.tsx`.


### Peer dependency

   What   A package saying "I only work with these versions of X". `lucide-react` 0.395 said "React 16 to 18",
          so npm refused React 19 until we removed it (26 Oct).


### npm audit

   What   Checks installed packages against known security problems. Read each finding: who uses the
          package, and can a visitor reach it? (Our Tailwind finding is build-time only, backlog B15.)


### Next.js middleware (proxy)

   What   Runs before a page. Ours sends logged-out users from `/employee` and `/admin` to the login page.
          Next.js 16 renamed it "proxy": same job, new file name.
   Where  `frontend/src/proxy.ts` (was `middleware.ts`).


### generateMetadata

   What   Sets the page title and description that Google shows.


### SEO

   What   Search engine optimisation: making Google find and rank our pages. Server-rendered pages,
          unique titles, a sitemap, robots.txt, JSON-LD, fast pages.


### sitemap.xml / robots.txt

   What   sitemap = list of our pages for Google. robots = which pages search engines may visit.
   Where  `frontend/src/app/sitemap.ts`, `robots.ts`.


### JSON-LD

   What   Hidden structured data on a page that tells Google "this is a company / product".


### localStorage

   What   A small store inside the visitor's own browser. We keep the visitor's form details there so they
          don't fill the form twice (A44). It never leaves their browser on its own.


### next build / NEXT_DIST_DIR

   What   `npm run build` makes the production version. `NEXT_DIST_DIR` changes the output folder
          (the e2e test uses `.next-e2e` so it doesn't touch yours).


### Unused packages (cleanup)

   What   `package.json` still lists packages from the starter repo that no code uses: zod, recharts, axios,
          date-fns, lucide-react, Radix UI, clsx, tailwind-merge, class-variance-authority.
   Note   Removing them is a cleanup to ask about first.



===================================================================================================

## 6. Security and privacy

### Authentication vs authorisation

   What   Authentication = who are you (login). Authorisation = what may you do (permissions).
          401 = not logged in. 403 = logged in but not allowed.


### Session / session token

   What   After login we create a long random token, store only its hash in the database, and put the
          token in a cookie. Logout deletes the row.
   Where  `auth_service.py`, table `user_sessions`.


### httpOnly / Secure / SameSite cookie

   What   httpOnly = JavaScript can't read it. Secure = sent only over HTTPS. SameSite = not sent by other sites.


### Hash

   What   A one-way fingerprint of some data. You can't get the original back.
          We hash session tokens and visitor IPs.


### scrypt

   What   A slow, safe way to hash passwords, built into Python (`hashlib.scrypt`).
   Why    Slow on purpose, so guessing passwords takes forever. No new package needed.
   Where  `backend/app/core/security.py`.


### CSRF

   What   An attack where another website makes your browser do something on our site using your cookie.
   Fix    Every write request must carry the header `x-requested-with`. Other sites can't add it.
   Where  `deps.py`.


### XSS

   What   An attack that runs someone else's JavaScript on our page. httpOnly cookies limit the damage.


### Honeypot

   What   A hidden form field. People don't see it and leave it empty; bots fill it, so we drop those.


### Turnstile

   What   Cloudflare's free "are you human" check. Planned for production (A31).


### Client IP / X-Forwarded-For / CF-Connecting-IP

   What   Behind a proxy, the server sees the proxy's address, not the visitor's. Proxies add the real IP
          in a header: `X-Forwarded-For` (nginx, Next.js) or `CF-Connecting-IP` (Cloudflare).
   Rule   We trust these headers only when the request comes from our own machine or network.
   Why    Without this, all visitors shared one rate limit (bug found 24 Oct).
   Where  `deps.py` (`client_ip`). Assumption A45.


### Secrets / rotate

   What   Passwords and keys. Rotate = replace with a new one and cancel the old one.
          The Groq key and Neon password must be rotated before go-live (B9).


### DPDP Act 2023

   What   India's data protection law. Collect only what we need, ask for consent, allow deletion.
   Where  Consent tick on every public form; IPs stored only as hashes.


### Prompt injection

   What   A visitor writes "ignore your rules and..." to trick the AI. We treat visitor text as data, not orders.
          The chat must also start and end with the visitor's message (a fake "Koko said" first turn is refused).


### Brute force / account lockout

   What   Guessing a password by trying thousands. We lock an email for 15 minutes after 10 wrong passwords,
          and refuse even the right password while locked (otherwise guessing never stops).
          Plus 30 tries per IP per 15 minutes, for guessing across many emails.
   Where  `auth_service.login`, `core/rate_limit.py`.


### Timing attack / user enumeration

   What   Learning which emails have accounts from how a page answers or how long it takes.
          Login runs the slow password check even for unknown emails, so both take the same time.


### Privilege escalation

   What   Getting more rights than you were given, e.g. using `staff.approve` on your own account.
          Rule now: nobody changes their own account; only an admin touches an admin; a non-admin approver
          only approves new sign-ups and only gives permissions they have.


### IDOR (insecure direct object reference)

   What   Changing an id in a request (`/leads/41` → `/leads/42`) to reach someone else's data.
          Every service checks ownership or membership, not only the permission.


### XSS via javascript: links

   What   `<a href="javascript:...">` runs JavaScript as our site when clicked. Links from data (offers) must be
          `/our-page` or `https://...`.
   Where  `SafeLink` in `schemas/common.py`, `safeLink()` in `frontend/src/lib/safe-url.ts`.


### Open redirect

   What   A link like `/employee/login?next=//evil.com` that sends a person to another site after login
          (a fake "log in again" page). We only follow `next` to a page on our own site.
   Where  `safeNext()` in `frontend/src/lib/safe-url.ts`.


### Header injection

   What   A line break in a name ("Bob\r\nBcc: ...") ending up in an email header. We collapse all line breaks
          in names (`OneLine` in `schemas/common.py`) and in notification titles.


### Content-Security-Policy (CSP)

   What   A header that tells the browser which scripts, images and connections a page may use. Even if an
          attacker gets HTML onto a page, scripts from other sites won't load and data can't be sent elsewhere.
   Where  `deploy/nginx/security-headers.conf`. Tested: no browser errors on our pages.


### Least privilege (database user)

   What   The app connects as `kjs_app`, which may only read and write rows. The owner `kjs` runs migrations
          and backups. So bad SQL can't drop tables, edit the audit log, or run server commands.
   Where  `deploy/db/grants.sql`, `deploy/db/init-app-user.sh`.


### umask

   What   Linux setting for the permissions of new files. `umask 077` in `backup.sh` makes backups readable only
          by their owner (they hold password hashes and customer data).


### Zip bomb

   What   A small file that unpacks to gigabytes (an .xlsx is a zip). We check the unpacked size (max 60 MB)
          before opening an import, and read at most 5000 rows and 30 columns.
   Where  `assign_service.read_rows`.


### Race condition / row lock (FOR UPDATE)

   What   Two requests at the same moment both read "not done yet" and both act (two batches, two owners,
          duplicate tasks). `SELECT ... FOR UPDATE` locks the row until commit; the second request waits and
          then sees the new state.
   Where  leads (`_lead_for(lock=True)`), batches, board steps, regularizations, file delete decisions.


### 409 Conflict

   What   The answer for "already done / already exists". A double click that hits a database unique rule now
          gets 409 with "please refresh", not a 500 "server error".
   Where  `IntegrityError` handler in `core/errors.py`.


### Cost cap (LLM budget)

   What   A daily limit on AI calls for all visitors together (2000), so nobody can run up the bill from many IPs.
   Where  `config/koko.ini` (`daily_limit`), `koko_service._within_daily_budget`.


### Dependency advisory / CVE

   What   A published security hole in a package version (a CVE number). We check versions against them and
          update. 25 Oct: FastAPI 0.129.2 / Starlette 0.52.1 / python-multipart 0.0.32 fixed upload DoS holes.


### Heartbeat (jobs health)

   What   The background jobs loop writes down the time of each finished round. `/api/health/ready` fails
          (503 "jobs_stalled") if that time is too old, so an uptime check notices stopped emails / alerts.
   Where  `runner.last_tick`, `runner.loop_is_alive()`, `/api/health/ready` in `main.py`.


### Docker DNS (resolve)

   What   Containers find each other by name (`backend`, `frontend`) through Docker's own DNS (127.0.0.11).
          A new container can get a new address, so nginx re-checks the name every 10 s (`resolve`).
   Where  `deploy/nginx/default.conf` (resolver, upstream ... resolve).


### Keep-alive

   What   Reusing one connection for many requests (faster). Both sides close idle ones after a while; the side
          that waits longer can send a request on a connection the other side just closed = a random 502.
          Rule: nginx must give up first (4 s, the apps wait 5 s).


### Graceful shutdown

   What   On restart, stop taking new requests but let running ones finish (we allow 25 s; Docker waits 30 s).
   Where  `--timeout-graceful-shutdown 25` in `backend/Dockerfile`, `stop_grace_period` in production compose.


### TLS certificate check

   What   Encryption alone isn't enough: the client must also check the server's certificate, or anyone in
          the middle can pretend to be the server. Python's `starttls()` without a context does NOT check.
   Where  `ssl.create_default_context()` in `notification_service._smtp_connect`.


### SQLSTATE 23505

   What   Postgres' code for "a unique rule was broken" (e.g. a double click). Only this one becomes 409
          "already done"; other database errors are bugs and must show as 500.
   Where  `_sqlstate()` in `app/core/errors.py`.


### Time-zone-aware date (AwareDatetime)

   What   A date-time that says which time zone it is in ("...Z" or "+05:30"). Without it, "10:00" could mean
          UTC or IST. Task due dates and offer times must carry one.


### Purge job

   What   Deleting a file first marks the row deleted, then removes the stored copy. If storage is down at that
          moment, the `purge_deleted_files` job retries later (`purged_at` shows it's really gone).


### Security review

   What   Someone who didn't write the code reads it looking for ways to break it. Ours (25 Oct) found about 50
          points in code that passed 125 tests. Results: `memory.md` session log, `backlog.md` section 8.



===================================================================================================

## 7. AI and Koko

### LLM

   What   Large language model: an AI that reads and writes text (the brain behind Koko).


### Groq

   What   A company that runs open AI models very fast. Koko uses it now (model `openai/gpt-oss-120b`).
   Where  `backend/app/services/llm.py`, `.env` (`LLM_PROVIDER`, `LLM_MODEL`, `GROQ_API_KEY`).


### Provider switch / LLM_PROVIDER

   What   A setting that picks the AI company (`groq`, `anthropic`, `none`) without changing code.


### System prompt

   What   The hidden instructions given to the AI before the visitor's message (rules + KJS facts).
   Lesson  Rules placed after the long facts block worked better (23 Oct).


### Tokens

   What   Pieces of words. AI companies charge and limit by tokens.


### Hallucination

   What   When an AI confidently makes something up. Koko's rules forbid prices, capacities and promises.


### RAG

   What   Retrieval-augmented generation: find the most relevant pieces of our content, then give only
          those to the AI. Planned for when the facts grow too long (needs pgvector).


### pgvector / embeddings

   What   An embedding turns text into numbers so similar meanings are close. pgvector stores them in Postgres.
          Not used yet.



===================================================================================================

## 8. Testing

### pytest

   What   The Python test tool. Each `test_*.py` file holds tests.
   Command  `cd backend && .venv/Scripts/python -m pytest -q`


### Fixture / conftest.py

   What   A fixture prepares something a test needs (a clean database, a logged-in user).
          `conftest.py` holds shared fixtures.
   Where  `backend/tests/conftest.py`.


### pytest-asyncio

   What   Lets pytest run async tests.


### freezegun

   What   Freezes the clock in a test ("pretend it is 09:31 on Monday").


### Test database

   What   A throwaway Postgres in Docker on port 5433. Each test wipes it. Never Neon.
   Rule   Run only one test suite at a time on it.


### Allowed / forbidden test

   What   For every route, one test that the right person can, and one that the wrong person can't.


### Unit test vs end-to-end (e2e) test

   What   Unit test = checks one piece. E2E = runs the real servers and acts like a real user.
   Lesson  E2E found 2 bugs that 121 unit tests missed (24 Oct).
   Where  `scripts/e2e/` (`api_e2e.py`, `browser_e2e.mjs`, README).


### CDP (Chrome DevTools Protocol)

   What   The way a script controls Chrome (open page, click, read text). Our browser e2e uses it directly.


### CI / GitHub Actions

   What   Continuous integration: GitHub runs our tests and build on every push. Red = don't merge.
   Where  `.github/workflows/ci.yml`.


### Lighthouse

   What   Google's tool that scores a page for speed, SEO and accessibility. Goal: 90 or more.



===================================================================================================

## 9. Production and deployment

### Production / staging / development

   What   Development = our PCs. Staging = a test copy online. Production = the real system KJS uses.


### Server

   What   The computer that runs the app all the time. KJS will give us one (B3).


### nginx

   What   A reverse proxy in front of our app. Handles HTTPS details, upload size, passes the real visitor IP.


### Cloudflare

   What   A service in front of websites: DNS, HTTPS, protection from attacks, caching.


### Cloudflare Tunnel

   What   Connects our server to Cloudflare from the inside, so the server doesn't need open ports.


### Domain / DNS

   What   Domain = the name (kjsindia.com). DNS = the internet's phone book that turns the name into an address.


### HTTPS / TLS

   What   Encrypted web traffic (the padlock). TLS is the encryption underneath.


### SPF / DKIM

   What   DNS records that prove our emails really come from us, so they don't land in spam.


### Backup / pg_dump / restore drill

   What   pg_dump saves the whole database to a file. Restore drill = actually restoring it on a fresh machine
          to prove the backup works. "A backup you haven't restored isn't a backup."


### WhatsApp Cloud API

   What   Meta's official way to send WhatsApp messages from software. Needs business verification (B4).
          The WhatsApp button on the website is just a link (`wa.me`), which needs no approval.


### Sentry / UptimeRobot

   What   Sentry = collects errors from the live app. UptimeRobot = alerts us if the site goes down.
          Optional, decide in production.


### Rollback

   What   Going back to the previous working version when a new one breaks.
   Where  `deploy/README.md` section 4. A rollback of code does not undo a migration: restore the backup.


### deploy/ folder

   What   Everything needed to run the platform on the company server.
   Where  `deploy/docker-compose.prod.yml`, `deploy/nginx/default.conf`, `deploy.sh`, `backup.sh`,
          `restore.sh`, `.env.production.example`, and the guide `deploy/README.md`.


### deploy.sh

   What   One command to update the server: pull code, build images, back up, migrate, restart, health check.


### backup.sh / restore.sh

   What   backup.sh saves the database (pg_dump) and uploaded files, checks the file, keeps 14 days.
          restore.sh puts a backup back (asks you to type RESTORE first).


### pg_dump / pg_restore

   What   Postgres's own tools to save a whole database to one file, and to load it back.
          `-Fc` = custom format: compressed, and can be checked with `pg_restore -l`.


### cron / crontab

   What   Linux's timer. A line in `crontab -e` like `30 2 * * * /path/backup.sh` runs it every night at 02:30.


### Dockerfile

   What   The recipe for building a Docker image: start from a base image, copy files, install packages, set the start command.
   Where  `backend/Dockerfile`, `frontend/Dockerfile`.


### Multi-stage build

   What   A Dockerfile with several steps (stages). Early stages install and build; the last stage copies only
          the result. The final image is small and has no build tools in it.
   Where  `frontend/Dockerfile` (deps → build → run).


### .dockerignore

   What   Files Docker must not copy into an image (`.venv`, `node_modules`, `.env`, tests).


### Next.js standalone output

   What   A build mode that creates `server.js` plus only the packages the server needs.
   Why    The website image is 255 MB instead of carrying all of `node_modules`.
   Where  `next.config.mjs` (`NEXT_STANDALONE=1`, set only inside Docker).


### Non-root user (in a container)

   What   The app runs as a normal user (`kjs`, `node`), not as root.
   Why    If someone breaks into the app, they get a user that can't change the system.


### HEALTHCHECK

   What   A command Docker runs every 30 seconds to ask "is the app still answering?". If not, the container is
          marked unhealthy.


### Compose profile

   What   A tag that keeps a service off unless asked for. `cloudflared` has profile `tunnel`, the test database
          has profile `test`.


### Log rotation

   What   Old log files are cut and deleted automatically (ours: 5 files of 10 MB), so logs never fill the disk.
   Where  `x-logging` in `deploy/docker-compose.prod.yml`.


### Image tag

   What   A label on a Docker image version. `deploy.sh` tags each build with the git commit (`kjs-api:ebfe12a`),
          so you can roll back to any of the last 3.


### Security headers

   What   Extra response headers that tell the browser to be careful: `X-Content-Type-Options: nosniff`,
          `X-Frame-Options` (no framing by other sites), `Referrer-Policy`, `Permissions-Policy`.
   Where  `deploy/nginx/default.conf`.


### gzip

   What   Compresses text responses before sending. The home page goes from about 50 KB to 10 KB.


### Cache-Control: immutable

   What   Tells browsers "this file never changes, keep it for a year". Safe for Next.js build files because
          their names change whenever their content changes.


### client_max_body_size / 413

   What   nginx's largest allowed request. Bigger uploads get status 413 "too large". Ours: 26 MB.


### HSTS

   What   A header that tells browsers "only ever use HTTPS for this site". Turned on in Cloudflare.


### Production safety checks

   What   On start-up in production, the API checks its settings. Default secret, `http://` address, localhost
          origins, example database password or missing R2 keys: it refuses to start and says which.
   Where  `production_problems()` in `backend/app/core/config/__init__.py`, tests in `test_production_checks.py`.


### Smart App Control

   What   A Windows 11 feature that blocks programs it doesn't trust. Error: "An Application Control policy has
          blocked this file". It blocked `backend\.venv\Scripts\python.exe` on 25 Oct (backlog B12).
          Turned off on this PC on 26 Oct. Off = no more blocks, but one less safety layer; Defender antivirus
          still scans files. Once off, it can only come back with a Windows reset.


### MSYS_NO_PATHCONV

   What   Git Bash on Windows rewrites `/srv/...` paths into Windows paths. Setting `MSYS_NO_PATHCONV=1` stops it.
          Only matters when testing Linux scripts on Windows.



===================================================================================================

## 10. Ideas and habits

### Idempotent

   What   Doing something twice has the same effect as doing it once. Our alerts are: a unique index stops a
          second copy.


### Pure function

   What   Same input gives the same output, with no database or clock inside. Easy to test.
   Where  Board step maths in `board_service.py`.


### Retries with backoff

   What   If sending fails, wait a bit and try again, waiting longer each time.


### Thin router, fat service

   What   Routes only pass data along. All rules live in services, so they are tested once and reused.


### Assumption logging

   What   When something is unclear, build the most sensible version and write the guess in
          `backlog.md` section 3 so it can be checked.


### Keep context in files

   What   Decisions go to `memory.md`, open items to `backlog.md`, today's work to `checklist.md`.
          A new session starts by reading them.



===================================================================================================

## 11. How we learn

1. Never commit code you can't explain. Ask until you can.

2. Learn just in time: the topic you need this week, not a whole course first.

3. Predict, then run. Say what you expect before running a test. Being wrong is where learning happens.

4. Type the first one yourself (first endpoint, first migration), then let the AI draft and you review.

5. Teach it back: explain what you built to your teammate in 2 minutes.

6. Write 2 or 3 lines a day in `learning/learning-log.md`, in your own words.


Red flags in AI-written code:

   a.  New packages you didn't ask for.
   b.  Tests that only check the happy path.
   c.  Catching every error and ignoring it.
   d.  Secrets, addresses or ids typed straight into the code.
   e.  Business logic in the router instead of the service.
   f.  A missing permission check or audit row.
   g.  Many unrelated files changed at once.


Good questions to ask the AI:

   a.  "Explain ___ in 5 lines with a tiny example."
   b.  "What problem does ___ solve? What did people do before it?"
   c.  "Show where we use ___ in our repo."
   d.  "What are 3 mistakes beginners make with ___?"
   e.  "Quiz me with 3 questions on what we just built."
