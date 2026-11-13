# Session notes (Kunal)

One subheading per task. Moved into the shared docs after the PR merges (see `docs/prompt.md` section 7).

## Playwright live-site tests, project K (branch testk)

- Built the read-only Playwright suite in `frontend/e2e/` (test cases in `frontend/e2e/TEST-CASES.md`, TC01-TC13).
  Added `@playwright/test` as a devDependency (Chromium only), `playwright.config.ts` with projects V, S, K,
  and `npm run e2e`. The login comes from `frontend/.env.e2e.local` (git-ignored); `.auth/`, `test-results/`
  and `playwright-report/` are git-ignored too.
- Note: this is the shared setup from the plan (Vineet's step 1), done on `testk` because it didn't exist yet.
  Check with Vineet so it isn't built twice.
- Ran `npx playwright test --project=K` on https://kjs-m.vercel.app (12 Nov 2026): 41 passed, 28 skipped
  (pages this account may / may not open: each page is tested in exactly one of TC09 or TC11), 1 failed.
- Account K@testsk.com: role **employee**, but with `staff.approve`, `boards.manage`, `calendar.edit`,
  `content.edit`, `files.approve`, `leads.view`, `leads.view_all`. So it opens most admin pages.
  Guess to check: is that on purpose for a test account? (Goes to backlog section 3 after merge.)
- Refused correctly (TC11 + TC12): Attendance (admin), Lead auto-assign, Client Schedulers, All Products,
  Activity log. The API answers 403 for the missing permissions and 200 for the held ones.

**Finding 1 (TC09 Chat):** on Vercel, the chat WebSocket fails:
`WebSocket connection to 'wss://kjs-m.vercel.app/api/v1/chat/ws' failed: ... Unexpected response code: 404` (twice).
Why: Vercel rewrites (`next.config.mjs` `/api/:path*`) don't pass WebSockets on, and `NEXT_PUBLIC_CHAT_WS_URL`
isn't set on Vercel, so `lib/chat.ts` falls back to the same host. Effect: Chat opens, but messages don't
arrive live. Possible fix (needs a decision): set `NEXT_PUBLIC_CHAT_WS_URL` to the API's wss address, but the
login cookie belongs to kjs-m.vercel.app, so the API must accept the socket's login another way.
Screenshot + trace: `frontend/test-results/pages-TC09-page-opens-Chat-employee-chat--K/`.
