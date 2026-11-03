# Session notes (Vineet)

One subheading per task. Moved into the shared docs after the PR merges (see `docs/prompt.md` section 7).



## CR1 restore fix, PR #13: notes moved out of the shared docs (2 Nov)

The PR first edited track.md, memory.md, backlog.md and learning-log.md (before the new rule). Those edits
were taken out and are kept here, to fold in after the merge.

1. For track.md, "4c. Whole-repo code review": CR1 is fixed in PR #13, all checks pass in
   `deploy/test-restore.sh` on a local Docker copy. The restore drill on the real server is still to do.
   In "Next": "Vineet + Nishita: merge the CR1 fix, then the should-fix list CR2–CR11".

2. For memory.md, a new entry "CR1 restore fix (30 Oct – 2 Nov, Vineet, branch `fix/cr1-restore-safety`)":
   i.    `restore.sh` reads both backups in full before anything changes, cancels the transaction if
         `pg_restore` fails, unpacks files aside, keeps old backups, and says how to undo a failure.
   ii.   `backup.sh` reads the whole dump before keeping it, and works with the backend down.
   iii.  "Nothing changed" only when psql proves the rollback. "Restore done" only after a passing health check.
         If the database step ends unknown, the app stays stopped. A second signal can't stop the clean-up.
   iv.   The undo command is also saved in `restore-undo.txt` in the backups folder.
   v.    `deploy/test-restore.sh` is the check for any change to these scripts. It refuses to run if
         `deploy/.env` exists, so it can't touch the server. Use the final count from the last run.

3. For backlog.md, CR1:
   i.    Fixed in PR #13, tested by `deploy/test-restore.sh`. Still open: a restore drill on the real server.
   ii.   `backup.sh` and `restore.sh` no longer need the backend running. Check what is left of CR3.
   iii.  Small improvements for later, from the PR #13 reviews:
         a.  The safety backup runs while the app is live, so anything saved between it and the app stopping
             is lost if you undo the restore.
         b.  Files are unpacked after the app stops, which adds downtime.
         c.  The `tar` checks use a container where the server's own `tar` would do.
         d.  If the script is killed during the database step, `.restore-new` stays until the next restore
             (the printed undo command removes it).
         e.  A valid dump of an empty or wrong database passes the read check.
         f.  A backup from newer code is only caught at step 7, after the data is replaced (the undo works).
             Read the dump's alembic revision in step 1 and refuse it there.
         g.  No lock: two restores, or a restore and the 02:30 backup, can clash. Add `flock` to both scripts.
         h.  Only psql's exit code 3 counts as "nothing changed". Other errors leave the app stopped, even when
             the database step never started (safe side, but a false alarm).
         i.  `compose run` can build the image if the live `TAG` image was deleted. Find a flag that stops it.

4. For learning-log.md, "CR1 restore fix":
   i.    A check can pass without proving what you think. `pg_restore -l` passed backups cut in half, because
         it reads only the list at the start. Only reading the whole file caught them.
   ii.   In a pipe, the second program can't see that the first one failed. So we send it something that
         always errors, and the database cancels the whole transaction.
   iii.  Write the test first and watch it fail: that proves the bug is real.
   iv.   A test proves only what it really tries: an easy fake crash missed the hard case (a crash inside a
         table's rows).
   v.    Stopping a script doesn't stop what it started. A script must say "I don't know" when it lost sight
         of a step, not guess "nothing changed".
   vi.   Don't read file names back out of a message meant for people: pick the names yourself.


## CR1 restore fix, PR #13, fifth review (2 Nov)

1. Fixed, each with a test that failed first (12 of 18 new checks failed before):
   i.    The app is stopped BEFORE the safety backup, so the undo misses nothing. Costs a little more
         downtime. A bad backup file still stops at step 1 with the app running.
   ii.   `backup.sh` takes `KJS_BACKUP_STAMP`, not `STAMP` (a common name: every backup could overwrite the last).
   iii.  `restore-undo.txt` says when the restore ended, and that running it later loses newer data.
         If nothing changed, it says there is nothing to undo.
   iv.   psql exit codes other than 3: the script now asks the database. A marker table (with this run's
         id) is made just before the database step. After the restore's session ends: marker there =
         nothing changed, app restarts; marker gone = data replaced, undo printed. A Ctrl+C or dropped
         session still leaves it "unknown".
2. In the backlog notes above, 3.iii.a (safety backup while the app is live) and h (exit codes other than 3)
   are now fixed: leave them out on fold.
3. Learning: when a result is unclear, ask the system that knows (the database), don't guess from an exit code.
4. Full suite: 186 of 186 pass (run in 2 parts, sections 1–17 and 18–22, because the laptop ran low on memory).


## CR1 restore fix, PR #13, fourth review (2 Nov)

1. Fixed, each with a test that failed first (7 of 8 failed before, 8 of 8 pass after):
   i.    The safety backup names are set by `restore.sh` (`STAMP`), not read from `backup.sh`'s message.
         A backup folder with a space now works, and the printed undo is quoted.
   ii.   The undo command is also saved in `BACKUP_DIR/restore-undo.txt`.
   iii.  The health check stops after about 60 s by the clock (it could take 3.5 min).
   iv.   Relative backup paths work (made full paths before the `cd`).
   v.    The shared-doc edits were moved here.
2. Not fixed, kept for the backlog (see above): exit codes other than 3, `compose run` building, `flock`.
   The test helpers copying restore steps is not a real risk: every check runs the real `restore.sh`.


## CR1 restore fix, PR #13, third review (2 Nov)

1. Nishita's must-fix: after a full restore where the app doesn't come back healthy, the script said only
   "the app did not start properly". It didn't say the data was replaced or print the undo command.

2. Fixed in `deploy/restore.sh`: that case now says "The backup was put back, but the app is not working"
   and prints the exact undo command. The README restore section matches.

3. Tested: section 20 of `deploy/test-restore.sh` failed 4 of 8 checks on the old code, and passes 8 of 8
   after the fix. Full suite: 160 of 160 pass.

4. For memory.md: the CR1 entry still says "All 155 pass". Update it to the final count when folding.

5. Learning: a "warning" alone is not enough after the data changed. Every way out after the swap must say
   what changed and how to undo it.

6. Laptop: 16 GB RAM, both slots full. Most listings say 16 GB is this model's maximum (Inspiron 14 7440
   2-in-1), so check Dell's manual before buying RAM. Close Chrome and VS Code windows before long Docker tests.
