# Live-site test cases (Playwright)

The suite in `frontend/e2e/` follows these cases, one test per case (the test name starts with its number).

It runs against the live site (default https://kjs-m.vercel.app) with your own test account.

Every test only reads: no leads, chat messages, form saves, approvals or deletes.



---------------------------------------------------------------------------------------------------

## How to run

1. In `frontend/`: `npm install`, then `npx playwright install chromium` (once per PC).

2. Create `frontend/.env.e2e.local` (git-ignored, never commit it):

   ```
   E2E_EMAIL=<your test email>
   E2E_PASSWORD=<your password>
   ```

3. Run your own project: `npx playwright test --project=K` (or V, S).

4. Open the report: `npx playwright show-report`.



---------------------------------------------------------------------------------------------------

## What "the right pages" means

1. Access is decided by permissions, not only by role. An employee can hold some admin permissions
   (for example `staff.approve`), and then opens those admin pages.

2. So the tests ask `/api/v1/auth/me` for the account's permissions and modules, and work out from them
   which sidebar links must show (the same rules as `SidebarNav.tsx`).

3. A sidebar link the account may not have must not show, and opening its page directly must be refused.



---------------------------------------------------------------------------------------------------

## Cases

### A. Setup (file `auth.setup.ts`, runs once before the others)

1. TC01 API health warm-up: `GET /api/health` answers 200 within 60 s (the free server may be asleep).

2. TC02 Log in through the login form with `E2E_EMAIL` / `E2E_PASSWORD`, once per run.
   Expect: the page moves to `/admin/dashboard` (role admin) or `/employee/dashboard` (others).
   The session is saved in `frontend/.auth/` (git-ignored) and reused by every other test.


### B. Login and session (file `login.spec.ts`)

1. TC03 Not logged in: opening `/employee/dashboard` sends you to `/employee/login?next=...`.

2. TC04 Wrong login: an unknown email shows an error and stays on the login page.
   (Uses a made-up address, never your account, so your account can't get locked.)

3. TC05 Right account: `/auth/me` returns the email that belongs to this project (V, S or K), so nobody
   runs a project with someone else's account by mistake.

4. TC06 Dashboard loads: the portal frame shows, with no error screen and no console errors.

5. TC07 Account menu shows your name, your email and a role badge.


### C. Sidebar and pages (file `pages.spec.ts`)

1. TC08 The sidebar shows exactly the links your permissions allow: every allowed link is there, and no
   link you may not have.

2. TC09 Every allowed page opens (one test per page). Expect:

   i.    no "Could not load" or "Could not load your account" error screen,

   ii.   no "Not available yet" screen,

   iii.  no API answer 401, 403 or 5xx while the page loads,

   iv.   no console error and no page crash.

3. TC10 Detail pages open: the first lead, the first order board, and the first employee (admin
   list), when the list has one. Same checks as TC09. Skipped when the list is empty.


### D. Refused pages (file `access.spec.ts`)

1. TC11 Every portal page your permissions don't allow, opened by typing its address, is refused: it
   shows "You don't have permission", or sends you to another page, or the API answers 403.
   A page that shows its content anyway is a failure (a real security finding).

2. TC12 The API refuses too: an admin API call you lack the permission for answers 403.


### E. Logout (file `logout.spec.ts`)

1. TC13 Log out from the account menu: the "See you soon" popup asks first; after "Log out" you are on
   the login page with "You've logged out safely". Opening `/employee/dashboard` again sends you to login.

   This test logs in on its own (a second login per run), so it doesn't end the shared session the other
   tests use.
