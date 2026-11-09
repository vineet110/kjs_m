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
