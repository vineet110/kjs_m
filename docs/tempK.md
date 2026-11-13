# Session notes (Kunal)

One subheading per task. Moved into the shared docs after the PR merges (see `docs/prompt.md` section 7).

## Staff login through Firebase + forgot password by email (branch feat/firebase-auth)

- Decided 13 Nov (Kunal): passwords move to Firebase Authentication, for new users; old accounts are not
  imported. Notification emails: not now (PR `feat/notification-emails` waits; don't merge it yet).
- How login works now: the browser signs in with Firebase (email + password) and sends its ID token to
  `POST /auth/login`; the API checks it (`app/core/firebase.py`, firebase-admin) and starts the usual
  `kjs_session`. Roles, permissions, approval, chat and every page are unchanged. The browser then signs out
  of Firebase: our session is the only login that lasts.
- Forgot password: `/employee/forgot-password` -> Firebase emails the link and shows its own "new password"
  page, then sends the person back to `/employee/login`. No email service of ours needed.
- Sign-up: Firebase account + "verify your email" email, then `POST /auth/signup` (pending, admin approves).
  Login needs a verified email (anyone can make a Firebase account with someone else's email).
- Old accounts (no `firebase_uid`): signing up again with the same email links the old row at the first
  verified login (history kept). Employees wait for approval again; an admin stays active (nobody else could
  approve the first admin).
- Admin "create employee": the one-time password is set in Firebase (we never store it).
  Disable / enable reaches Firebase too (our database stays the real check).
- Profile > Change password: signs in to Firebase with the current password, changes it there, then
  `POST /auth/password` logs out the other browsers (needs a sign-in from the last 5 minutes).
- Removed: password checks and the wrong-password lockouts (Firebase blocks guessing). Kept: per-network
  limit on bad tokens (CR5/CR7 still hold: strangers can't lock the office out).
- Migration `0024_firebase_uid` (was 0021; renumbered after main's 0022 + 0023 on 13 Nov): `users.firebase_uid` (unique), `password_hash` now optional.
- Packages (approved): `firebase-admin==7.8.0` (needs `httpx` 0.28.1), `firebase` (npm).
- Secret: `FIREBASE_SERVICE_ACCOUNT` is in the root `.env` (git-ignored). It was pasted in a chat once:
  rotate it (Firebase > Service accounts > delete key, generate new) and put the new one in `.env` + Render.
- Tests: conftest has a fake Firebase (`id_token(email)` signs in as that email). New
  `tests/test_firebase_login.py`; updated auth, phone, content, security, readiness, modules and chat tests.
  NOT run on this PC (no Docker/Postgres): CI runs them. Checked here: the key works (read-only call to
  Firebase), app imports, `tsc`, `npm test` (51 pass), `npm run build`, and in a real browser against the real
  Firebase project: wrong login message, forgot-password request accepted, pages open logged out.

**For backlog:** (1) Playwright suite (`testk`): log in now goes through Firebase; the K/V/S test accounts
need Firebase accounts with verified emails. (2) Firebase password policy: set minimum 10 characters in the
console (the page asks for 10, Firebase's own default is 6). (3) Drop `users.password_hash` once every old
account is linked. (4) Notification emails (PR `feat/notification-emails`) when wanted.

**New concepts (for kb.md):** ID token (a short-lived signed proof of who you are, checked with Google's
public keys); email verification (proves the inbox is yours); "fresh sign-in" (auth_time) for risky actions.

### Merge of main into feat/firebase-auth (PR #77 conflicts)

- Main got #74, #76, #78 meanwhile. Conflicts fixed: `rate_limit.py` (kept main's Excel/CSV limit, old
  password limits stay removed), `user.py` (Firebase fields + main's "Admin access" / "rejected" comments),
  `auth_service.py` imports (main's `UserOut`, `job_title_service`).
- Hidden ones fixed: migration renumbered 0021 -> 0024 (after main's 0023; one head again), and two tests
  still logging in with passwords: `test_staff_manage.py` (new on main) and `test_prod_readiness.py`
  `test_a_stranger_cannot_lock_someone_else_out` (missed in the first PR #77 push).
- Checked: one Alembic head (0024), backend imports, all tests compile, `tsc`, `npm test` (58 pass), build.
  Backend tests themselves: CI.
- CodeRabbit on #77: `auth_service.py` used `AuditLog` (main's `decided()`, Approvals > Approved list) without
  importing it: I had removed the import in the Firebase rewrite. Put back; scanned every changed file for
  other missing names: none. Lesson: "it imports" doesn't catch a missing name inside a function.

### Review of #77 (13 Nov): 10 points

- Real, from my Firebase code (to fix in #77): (1) Approve doesn't re-enable the Firebase account,
  (2) old staff see "wrong password" with no hint to sign up once, (3) a Firebase reset doesn't end old
  sessions, (4) Firebase errors (user deleted / Google down) crash as 500, (5) a broken key looks like
  "sign-in expired" and locks the office out (429), (6) Profile says "Could not change" after it changed,
  (7) half-finished sign-ups make "Create employee" say "already exists", (8) double-click login says
  "no account", (9) a check compares message text instead of err.code.
- (10) Decided: `tempK.md` is allowed (Vineet agreed in person). The service-account key is temporary and
  will be replaced before going live.
- Fixed (13 Nov): (1) `approve()` switches the Firebase account back on; (2) Firebase errors: user deleted /
  forged / expired / disabled / revoked = 401, Google down = 503 (never 500); (3) broken key = 503
  `login_not_set_up`, logged as `firebase.bad_config`, never counts toward the login limit; (4) "Create employee"
  reuses a half-finished Firebase account (checked first: never another row's login), quiet cleanup;
  (5) double-click login finds the account the other click linked; (6) `_verify()` looks the user up once and
  returns `valid_after_ms`; `login()` ends sessions older than the last password change; a Profile password
  change gives this browser a new session. Checked on the real Firebase project with a throwaway user
  (deleted): a reset through the email link moves that time forward. (7, 8) old-account hint on the login
  and forgot-password pages; (9) Profile checks `err.code`, and says "Password changed" if only the logout
  of other browsers failed.
- Checked here: Firebase checking code with fake Google answers (all 401/503 as planned), backend imports,
  tests compile, missing-names scan, `tsc`, `npm test` (58), build, hints in a browser on the real Firebase.
  Backend tests: CI.
