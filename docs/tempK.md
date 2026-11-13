# Session notes (Kunal)

One subheading per task. Moved into the shared docs after the PR merges (see `docs/prompt.md` section 7).

## Notification emails through Firebase (branch feat/notification-emails, PR 1 of the Firebase plan)

- Every bell notification also goes to the employee's email (as before: unless they untick "Also send me an
  email" on Profile, and never to disabled accounts).
- How: with `FIREBASE_SERVICE_ACCOUNT` set, the `send_emails` queue writes each email into the Firestore
  collection `mail`; Firebase's "Trigger Email from Firestore" extension sends it (through a Gmail app
  password). Without it, SMTP as before; without both, skipped. Brevo dropped (decided 13 Nov: only Firebase).
- New: `backend/app/core/firebase.py` (one Firebase app; PR 2 reuses it for login), `email_service.py`.
  Package `firebase-admin==7.8.0` (approved); it needs `httpx` 0.28, so the pin moved 0.27.0 -> 0.28.1
  (checked: we don't use the options 0.28 removed).
- Queue rules kept: never sent twice (one fixed Firestore id per notification: a second write is refused),
  3 tries, time budget, CR10: when Firebase is down or refuses us (bad key, no permission, quota, timeout)
  emails wait WITHOUT using up a try. Only a refusal of one email uses a try.
- Known gap: "sent" means handed to Firebase. A delivery failure after that (bad address, Gmail's ~500/day
  limit) is only on the Firestore document (`delivery.state` / `delivery.error`). Later: a job that reads it back.
- `tests/conftest.py` sets `FIREBASE_SERVICE_ACCOUNT=""`, so a real key in `.env` never reaches tests.
- Tests: `backend/tests/test_notification_emails.py` (fake Firestore). Not run on this PC (no Docker/Postgres):
  CI runs them. Checked here: app imports, error sorting (script), broken key = "Firebase down", compile.
- The forgot-password (Brevo) work is in `git stash`: replaced by Firebase in PR 2. `git stash drop` later.
- To do by hand: Firebase steps (project, Blaze + budget alert, Firestore asia-south1, Gmail app password,
  Trigger Email extension with collection `mail`), then `FIREBASE_SERVICE_ACCOUNT` in `.env` and on Render.

**New concepts (for kb.md):** Firestore (Google's document database; here only a mailbox for the extension);
idempotent write (a fixed id makes "write twice" harmless); "provider down vs message refused".
