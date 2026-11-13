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
- Migration `0021_firebase_uid`: `users.firebase_uid` (unique), `password_hash` now optional.
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
