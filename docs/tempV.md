# Session notes (Vineet)

One subheading per task. Moved into the shared docs after the PR merges (see `docs/prompt.md` section 7).

## Data safety before real data (9 Nov, branch `feat/data-safety`)

From the 9 Nov repo audit (data-loss check). Work split with Nishita: she does the frontend items
(lead note lost on a failed save, task notes, admin forms) in her own PR; this PR is backend + deploy only.

1. Off-site backup in the R2 bucket `kjs-bkp-prod` (Vineet created it, 9 Nov):
   i.    New `backend/app/backup_r2.py` (`python -m app.backup_r2 sync-files | put | list | get | restore-file`).
         Uploads are copied to `files/`; an upload that disappears from the app bucket moves to
         `deleted/<day>/` and stays 30 days; encrypted database backups go to `db/<day>/`, kept 30 days.
   ii.   `deploy/backup.sh` step 4: when `deploy/.env.backup` exists, encrypts the database backup with
         `openssl` (AES-256, passphrase `BACKUP_PASSPHRASE`) and sends it; with R2 storage it syncs the
         uploads; with local storage it sends the encrypted files archive. Without `.env.backup` it warns.
         The safety backup inside `restore.sh` never goes off-site (a restore must not wait on the internet).
   iii.  The backup bucket has its OWN R2 token (`.env.backup`, never in `.env`), so the running app never
         has it and a leaked app key can't wipe the backups. New `deploy/.env.backup.example`.
   iv.   `R2Storage` can now list a bucket (S3 ListObjectsV2) and use another bucket and key. The list
         request's signature matches AWS's published example (new test).
   v.    `deploy/.env.production.example`: `STORAGE_DRIVER=r2` (what we use). README section 5 item 4:
         set-up, what is kept, how to get a database backup or one lost upload back.
2. Attendance: approving a correction no longer rewrites the hours as "last out minus first in" (lunch
   counted as work). It moves the day's first check-in (and last check-out, if given) and works the hours
   out from the real punches; a day left open gets a check-out punch. The audit keeps the old hours.
3. Check-in and check-out lock the day's row: a double tap stores one punch and answers "already checked
   in / out" (a double check-in on a new day used to give an error 500).
4. Upload: if the database save fails after the file was stored, the stored copy is deleted again.

Tests: new `test_backup_r2.py` (3), storage 2 more (signed list request, list answer), attendance 3
(break kept + audit, open day closed, double taps), files 1 (failed save). `test-restore.sh` section 24:
warning without `.env.backup`, incomplete settings refused, the copy sent decrypts to the backup, the
running app has no backup key, R2 down = backup.sh fails (cron mails it) but the local backup stays, a
restore never goes off-site. Real R2: listing `kjs-prod-files` works (read only; the bucket is empty).

Not done yet: the real backup token (Vineet makes it: R2 > Manage API tokens, Object Read & Write, only
`kjs-bkp-prod`), so the first real off-site run happens on the server.

For the fold: backlog A54 still says uploads are in the nightly local backup (now R2 + off-site), and
A55 / R11 (off-site copy) are done by this. Decision: off-site = R2 `kjs-bkp-prod`, 30 days, openssl.

To do (from Nishita, 9 Nov, PR #41):
1. PR C: the offer PATCH (`content.py`, edit_offer / OfferIn) and the user edit PATCH (`/admin/users/{id}`)
   change only the fields sent, like `ProductPatchIn`. Then her forms can send only what changed.
2. Before go-live: delete the 3 e2e test files her run put in the real `kjs-prod-files` bucket (keys in
   `docs/tempS.md` on her branch), and any other test uploads there. (Vineet: leave them until then.)

Code review of this PR (9 Nov): 10 findings, 6 fixed, 4 left on purpose.
1. Fixed: an upload whose commit fails on the way back no longer deletes the file (the row may be saved);
   a broken `.env.backup` can't stop a restore's safety backup; deploys skip the off-site step
   (`KJS_SKIP_OFFSITE`), so R2 being down can't block an urgent fix; `.env.backup` is read as plain
   KEY=VALUE lines (a passphrase with `$` or spaces was silently changed); a rewritten upload keeps the old
   backup copy in `deleted/`; an empty file key is refused (it would address the whole bucket).
2. Left: no limit on how many files one sync may move to `deleted/` (the app breaks visibly first, and
   they stay 30 days); an extra INSERT per check-in (cost only); server-side copy in R2 (speed only).
3. Needs a decision (fold into backlog): approved deletes stay in the off-site copy up to 30 days (DPDP:
   "deleted means deleted"). Normal for backups; to be written down as an assumption.

Drill (`test-restore.sh`): the full run before the review fixes gave 202 pass, 4 fail (all in the new
section 24: openssl couldn't open /tmp paths under Git Bash; fixed by using < and >). After the review
fixes it was NOT run again (Vineet: skip, test on the server). Run it on the server before go-live.

## Deploy safety (9 Nov, branch `fix/deploy-safety`, on top of `feat/data-safety`)

1. CR11 / R7: the running API no longer gets the database superuser password, the migration address or
   the Cloudflare tunnel token. Plan first was 3 env files (CR11's own idea); changed to blanking them in
   `docker-compose.prod.yml` (`environment:` beats `env_file:`): same result, no new files, no rollout
   order. `deploy.sh` and `restore.sh` read `MIGRATION_DATABASE_URL` from `.env` (plain reading, never run
   as code) and pass it to the migration step only (`run -e`). In production `alembic/env.py` refuses to
   fall back to the app user when it is missing (clear message).
2. CR2: new `/healthz` (`frontend/src/app/[locale]/healthz/route.ts`, a new file in Nishita's area: tell
   her): 200 only when Next reaches the API and the database now, no cache. `deploy.sh` and the frontend
   Docker HEALTHCHECK use it instead of `/` (the home page's loading.tsx answers 200 even when it fails).
3. CR1.iv: a restore that fails after the database was replaced leaves the app STOPPED (it used to start
   it on tables that may not match) and prints the undo. `test-restore.sh` expectation changed to match.
4. CR3: already fixed earlier (backups use `run`, not `exec`): close it at the fold.

Tests: `/healthz` on a dev server (503 with no API, 200 with one, home page 200 either way = the CR2
problem); `docker compose config` shows the API's three secrets blank; `run -e` passes the migration
address and a plain run gets none; Alembic refuses in production without it, works locally. Shell
syntax checked. Full drill NOT run (Vineet's call: test on the server).

## Login and rate limits (9 Nov, branch `fix/security-reliability`, on top of `fix/deploy-safety`)

1. CR6: rate limits count a whole IPv6 /64 block as one visitor (`security.rate_key`, `deps.visitor_keys`);
   IPv4 written as IPv6 is IPv4; anything odd is used as it is (never a 500). Leads, audit rows and
   chats still keep the hash of the real address.
2. CR7: the per-network login limit counts only WRONG passwords (the office shares one address) and is
   100 per 15 min; sign-ups 30 per network per hour. Both in `config/app.ini` (`login_failures_per_ip`,
   `signups_per_ip_per_hour`).
3. CR5: a stranger can no longer lock someone out with wrong passwords from many networks: a network the
   person logged in from in the last 30 days skips the any-network counter. Every successful login now
   writes an audit row (`auth.login_ok`, hashed network), which is where that is looked up: it survives
   an API restart, and no migration was needed (the plan said a new table first).

Tests: 3 new (IPv6 key, office logins + 30 sign-ups, 10 attacker networks then the office still gets in
and a never-seen network doesn't). Auth, content, prod-readiness, leads: 79 pass. CI runs the rest.

## Reliability (9 Nov, branch `fix/reliability`, on top of `fix/security-reliability`)

1. CR10: when the mail server can't be reached, the emails go back in the queue without using up an
   attempt (one email used to be lost about every 3 minutes of an outage). One try per run.
2. CR8: a feature switched off in `config/features.ini` also refuses its API (404 `feature_off`): Koko
   chat (no AI calls), Koko and configurator leads, partner applications. The normal enquiry form always works.
3. CR9: disabling an account gives the unfinished buyers of its open batch back ("new") and marks the batch
   "returned" (not "done"). Finished records stay finished. Audited (`buyers_returned`). The leave case
   (an admin "take back batch" button) is screen work: on Nishita's list, needs a decision first.
4. Nishita's PR #41 asks: `PATCH /content/offers/{id}` and `PATCH /admin/users/{id}` change only the
   fields sent. The account is still checked as a whole (e.g. nobody reports to themselves).

Tests: mail outage 5 runs then back (none lost, all sent), features off (Koko, configurator, partners refused,
enquiry form works), disable with a half-done batch, offer switch keeps the text, one-field account edit.
Related suites 88 pass. CI runs the rest.
