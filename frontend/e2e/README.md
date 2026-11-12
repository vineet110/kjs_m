# Live-site tests (Playwright)

Read-only checks of the staff portal on the live site (https://kjs-m.vercel.app), one tester per PC.
Nothing is created, edited or deleted. The local browser tests in `scripts/e2e/` are a different thing:
they start their own servers on your machine.

## 1. Who runs what

1. V = Vineet, S = Nishita, K = Kunal. Each person runs only their own letter.
2. All three can run at the same time on their own PCs.

## 2. One-time setup (each PC)

1. `git pull` on `main`, then in `frontend/`: `npm install` and `npx playwright install chromium`.
2. Create `frontend/.env.e2e.local` (git-ignored, never commit it):

   ```
   E2E_BASE_URL=https://kjs-m.vercel.app
   E2E_EMAIL_V=<V's test email>
   E2E_EMAIL_S=<S's test email>
   E2E_EMAIL_K=<K's test email>
   E2E_PASSWORD=<test password>
   ```

   You only need your own `E2E_EMAIL_<letter>`. Testers without an email are skipped. A different password
   for one tester: `E2E_PASSWORD_<letter>`.

## 3. Run

1. Your own tests: `npx playwright test --project=V` (or `S`, `K`).
2. All three from one PC: `npm run e2e`.
3. Open the report: `npx playwright show-report`.

## 4. What it checks

1. Login through the real form (wakes the Render server first; it may take about 50 s).
2. You land on the dashboard and the portal loads.
3. The sidebar shows exactly the pages your permissions and the switched-on areas allow (same rule as
   `navFor` in `src/components/portal/SidebarNav.tsx`).
4. Every sidebar page opens: no error screen, no "Not available yet", no page crash, no console error,
   no 403 or 5xx from the API.
5. The admin-only API (`/api/v1/admin/users`) refuses you unless you have `staff.approve`.
6. Logout works and the session is really gone (a separate login, so the other tests stay logged in).

## 5. Admin module (project A)

1. Needs `E2E_EMAIL_A` and `E2E_PASSWORD_A` (the admin test account) in `.env.e2e.local`.
2. Run: `npx playwright test --project=A` (about 3 minutes, one test after another).
3. Fill the workbook: `python scripts/e2e/admin_workbook.py --results frontend/test-results/results.json`
   (from the repo root). Result: `docs/testing/admin-e2e.xlsx`, Summary + Test cases.
4. It creates and removes "E2E" test data. Left behind on purpose (no delete in the app): the disabled
   E2E user, the hidden E2E product, and one cancelled E2E board per run.

## 6. Employee module (project E) and stress test

1. Test employees (once): `node scripts/e2e/create_test_employees.mjs 75` from the repo root (admin login
   needed). Their one-time passwords go to `frontend/.auth/stress-users.json` (git-ignored).
2. Extra test data (optional): `node scripts/e2e/seed_test_data.mjs` (attendance, leads, tasks, leave,
   missed punches, a group chat; all marked E2E).
3. Employee tests as tester V: `npx playwright test --project=E` (needs V's and the admin's logins).
4. Stress test: `node scripts/e2e/stress.mjs` (10, 25, 50 users, 2 minutes each; stops itself if the
   site is overloaded). Result: `frontend/stress-results/stress.json`.
5. Fill the workbook: `python scripts/e2e/employee_workbook.py --results frontend/test-results/results.json
   --stress frontend/stress-results/stress.json`. Result: `docs/testing/employee-e2e.xlsx`.
6. All E2E data is kept on purpose (Vineet, 12 Nov) and must be cleared before production.

## 7. When a check fails

1. Checks are "soft": one broken page is recorded and the run carries on, so one report shows every problem.
2. Don't change the test to make it pass. Write what failed (page, error, screenshot from the report) in
   your temp notes file.
