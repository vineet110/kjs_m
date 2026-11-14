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

### Plan: second review of #77 (14 Nov), 10 points in 3 steps

Why 3 steps: step 1 is small and safe, so it goes into #77 now. Steps 2 and 3 change how login and
sign-up behave, so each gets its own branch and PR after #77 merges, and Vineet is told first (prompt.md 7.5).

**Before step 1 (people, not code)**
- Confirm no other app uses our Firebase project (the password policy is for the whole project).
- Whoever owns the Firebase console sets: Authentication > Settings > Password policy, minimum 10,
  "require update on sign-in" (not a hard block) if offered. Same day as step 1 goes live.

**Step 1: fixes on `feat/firebase-auth` (#77), one commit "fix: review round 2 on #77"**
| Point | Change | File | Test |
|---|---|---|---|
| Clock drift | `verify_id_token(..., clock_skew_seconds=10)` | `core/firebase.py` | fake that checks the argument |
| Short passwords | console setting above; check sign-up, Profile and reset page show Firebase's "too short" message clearly | `frontend` error messages | manual, on real Firebase with a throwaway user |
| 500 on Google errors | one helper: Google error = 503 `login_unavailable` (logged), Google's ValueError = 422; used by `create_user`, `uid_by_email`, `reset_account`, `delete_user`, `set_disabled` | `core/firebase.py` | fake raises UnavailableError -> 503; ValueError -> 422 |
| Sign-up retry 409 | same `firebase_uid` and still `pending` = return the row (200); approved/rejected stays 409 | `services/auth_service.py` `signup()` | sign up twice with the same token -> 200, one row |
| Extra call on approve | call `_sync_firebase_disabled` only if the status was `disabled` | `auth_service.py` `approve()` | pending -> no Firebase call; disabled -> one call |
| Old password helpers | comment "legacy, tests only, never for logins" | `core/security.py` | none |

Done when: backend tests pass (CI), `tsc`, `npm test`, build; notes added here; CodeRabbit re-run clean.
Undo: revert the one commit; the console policy can be turned back to 6.

**Step 2: sessions (new branch `fix/firebase-sessions` after #77 merges)**
- Reset ends other sessions at once: new column `users.firebase_valid_after`, filled at login, at
  password change and by a refresh every few minutes; `session_user()` (`core/deps.py`) ends a session
  older than it. (Or the cheaper version: check only when someone comes back after a while. Decide first.)
- Pre-Firebase sessions: a migration deletes sessions of users with no `firebase_uid`.
- Migration number: next free one after pulling main (now 0025?). Tell Vineet before using it.
- Warn staff: old-style logins are logged out once and employees wait for approval again.
- Tests: reset -> old cookie gets 401; new login still works; old session deleted by the migration.

**Step 3: sign-up and linking (new branch `fix/firebase-signup` after step 2)**
- `approve()` refuses an unverified email (one Google call); Approvals page shows "email not verified".
- `signup()`: a verified person replaces an unverified *pending* row with the same email (audit log keeps the old details).
- `login()`: email row linked to a Firebase account that no longer exists -> relink to the new one,
  audit log, employee back to `pending`.
- Tests: squatter then real owner; approve unverified -> refused; deleted Firebase account -> relinked.

**Open questions**
1. Step 2: full fix (new column) or the cheaper one?
2. Who sets the password policy, and when?

**Step 1 done (14 Nov, not committed yet)**
- `firebase.py`: token check allows 10 s clock difference (`CLOCK_SKEW_SECONDS`); every Admin call goes
  through `_admin()`: Google down = 503 `login_unavailable` (logged), a value Google refuses = 422
  `bad_account_details`, "email taken" / "user not found" still handled by the caller.
- `auth_service.py`: sign-up retry with the same login while `pending` = 201, not 409; `approve()` calls
  Firebase only for a `disabled` account.
- `security.py`: old scrypt helpers marked LEGACY.
- Frontend: nothing to change, "too short" already says "at least 10 characters". The emailed reset page
  is Firebase's own, so only the console policy covers it.
- Tests: 6 new in `test_firebase_login.py`; old fakes take `**kw` (the new clock argument).
- Checked here: compile, firebase-admin 7.8.0 has `clock_skew_seconds`, error mapping run with fake Google
  answers (503/422/409/None as planned). Database tests: CI (no Docker on this PC).
- Still to do: password policy in the Firebase console (min 10).

**Step 2 done (14 Nov, on #77 too: Kunal chose the same branch and the full fix)**
- Migration `0025_firebase_session_check.py` (0025 was free on every branch: tell Vineet).
  New `users.firebase_valid_after` + `users.firebase_checked_at`; deletes sessions of accounts not linked
  to Firebase yet (they log in once more, then the Profile password change works).
- `core/deps.py` `session_user()`: at most every 5 min (`FIREBASE_CHECK_EVERY`) asks Firebase when the
  password last changed; a session older than that, or of a deleted Firebase account, ends (401).
  Google down = keeps the last known time, nobody is logged out. Plain UPDATE so `updated_at` isn't reloaded.
- `auth_service.py`: login and Profile password change save that time (no extra Google call right after).
- `firebase.py`: `tokens_valid_after_ms(uid)`; conftest fake has it too.
- Tests: 5 new (reset ends a stolen session, at most one look per 5 min, Google down, deleted account,
  the real lookup). Checked here: compile, import, one Alembic head, session check dry-run with fake
  data (all 5 answers as planned). Database tests: CI.
- Before deploy: warn staff still logged in from before 13 Nov that they will be logged out once.
