# Session notes (Vineet)

One subheading per task. Moved into the shared docs after the PR merges (see `docs/prompt.md` section 7).

## 28 Nov: clear the test employees so they can sign up fresh (branch fix/reset-test-staff)

1. Why: every employee so far is a test account. Signing up again with the same email said "already exists", because our users table still had the old row.
2. Retire, not delete: about 30 tables point at a person, the activity log too (it can't be edited), so a real delete isn't possible. `app/reset_staff.py` instead, for every employee (never an admin):
   1. deletes the Firebase login (first; if Google fails, the person is left as is and listed),
   2. changes the email to `removed-<id>@invalid`, so the real email is free,
   3. disables the row, unlinks it from Firebase and logs them out,
   4. sends their open leads back to unassigned and returns their open batch.
3. Run on the server (Mon 30, after the re-test and a backup), from `deploy/`:
   1. `docker compose -f docker-compose.prod.yml exec backend python -m app.reset_staff` (check only: lists who)
   2. Same with `--apply` (does it). `--keep a@x.com,b@y.com` protects named employees.
4. Then `require_verified_email = true` (a separate one-line PR, after the re-test: unverified test accounts would be blocked).
5. Tests: `tests/test_reset_staff.py` (check mode changes nothing, admins untouched, same email signs up fresh, Firebase down = nobody half-done).
