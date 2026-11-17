# Session notes (Vineet)

One subheading per task. Moved into the shared docs after the PR merges (see `docs/prompt.md` section 7).

## 17 Nov: email checks parked (PR #87), resume on the VPS

1. Decision (Vineet, 17 Nov)
   i.    `config/app.ini` `require_verified_email = false` stays OFF on purpose. Firebase's "verify your email"
         emails are failing, and we stop all Firebase and Render work now to spend the time on our own server.
   ii.   PR #87 merges as it is. Everything below is parked until the VPS is up.
2. Done today
   i.    The admin account `vineet@kjsindia.com` had never linked its Firebase login (an old pre-Firebase
         account), so it could not log in (linking always needs a verified email). Its Firebase email was
         marked verified by hand with the Firebase Admin SDK (`auth.update_user(uid, email_verified=True)`,
         project `kjs-m-6e0bb`). Undo: the same call with `email_verified=False`.
3. Risks we accept while it is parked
   i.    Impostor: anyone can make a Firebase account with a colleague's @kjsindia.com email and sign up. The
         only guard is the admin calling the person before approving.
   ii.   Old accounts (no `firebase_uid`) cannot log in until email works: linking needs a verified email.
4. Review findings on #87 (code review, 17 Nov), parked
   i.    `backend/app/api/v1/endpoints/auth.py:30`: an old account that signs up again gets
         `verify_email = false`, but its login always needs a verified email, so it is stuck. Fix: return
         `true` whenever the row has no `firebase_uid`.
   ii.   `config/app.ini:24`: off in the shared ini means off on every server. Fix: ini `true`, turn off on one
         server only with `KJS__APP__REQUIRE_VERIFIED_EMAIL=false`.
   iii.  `backend/app/services/auth_service.py:94`: one global switch. Turning it on locks out everyone approved
         while it was off. Fix: a per-user flag (see 5 ii).
   iv.   `frontend/src/app/[locale]/(auth)/employee/login/page.tsx:115`: an unverified user now waits for the
         server to wake (up to 2 minutes) before hearing "please verify".
   v.    `page.tsx:32`: a generic error shows inside brackets; "try again in an hour" contradicts "wait a few
         minutes" for the same `auth/too-many-requests`.
   vi.   `page.tsx:154`: a failed verify email shows in the green success box.
   vii.  `backend/tests/conftest.py:63`: `monkeypatch.undo()` also undoes other fixtures' patches; every test
         reloads the config twice.
   viii. `backend/tests/test_firebase_login.py:28`: `verified_rule` duplicates the conftest fixture; 3 tests
         ask for it and never use it.
   ix.   `frontend/src/app/[locale]/(admin)/admin/approvals/page.tsx:72`: the "checks are off" banner does not
         say WHICH pending sign-ups are unverified.
5. Plan when we resume (on the VPS)
   i.    First PR: findings i and ii (env var on the server, ini back to `true`), simpler test fixtures (vii,
         viii). Order: set the env var on the server BEFORE the deploy, then log in with an unverified test
         account to check.
   ii.   Second PR: column `email_confirmed_by_admin` (next free migration number; check open PRs first). The
         migration sets it true for everyone already active. Approvals page: a required tick "I confirmed this
         email belongs to this person" for unverified sign-ups, saved by `approve()` and in the activity log;
         show verified / unverified per sign-up (ix). Login: `email_verified OR email_confirmed_by_admin`.
         Then remove the global switch and the env var. Run `alembic upgrade head` right after the merge,
         with BOTH database URLs set (decision 38).
   iii.  Later: iv, v, vi.
   iv.   Before any of this: make email work on the VPS.

## 16-17 Nov: own server research (E2E Networks)

1. Choice so far: a rented VPS at E2E Networks (Indian company, INR + GST invoices, Delhi or Chennai). Our
   `deploy/` Docker Compose runs on it unchanged. This changes decision D15 ("company server"): needs KJS's OK.
2. Plans (pricing page, 17 Nov, before 18% GST)
   i.    E1LC-2.6GB: 2 shared vCPU, 6 GB RAM, ₹894/month for compute. Disk (150 GB default, 75-2,400 GB) is
         billed separately (price per GB still unknown). No public IPv4 by default (Reserved IP ₹199/month).
   ii.   C3.8GB: 4 vCPU (≥ 2.8 GHz), 8 GB RAM, 100 GB NVMe, public IPv4 included, ₹3,422/month.
   iii.  E1 to C3 is NOT an in-place upgrade: a new node and a migration. Upgrades inside one family work
         (node powered off). No downgrades.
3. Sales answers (17 Nov): outgoing data free; 1 Gbps public network; snapshots on E1 and C3, scheduled,
   charged on data used, restore = new node (not in place); no backup by default; Security Groups (firewall);
   web console if SSH breaks; monitoring + alerts; Ubuntu 24.04; root access; 99.9% SLA; IPv6 only in Delhi;
   support by email and phone, about 30 minutes first response. Free trial credits: "confirmed per account".
4. Keep R2 for site pictures and the off-site backup (`kjs-bkp-prod`).
5. Still to ask: E1 disk price per GB; does an E1 node without a public IP still reach the internet
   (Docker pulls, Cloudflare Tunnel); trial credits for our account; data residency of snapshots.
6. Next: hourly trial (`deploy.sh`, `docker stats`, `test-restore.sh`), then pick E1 or C3.
