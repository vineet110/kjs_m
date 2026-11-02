# Session notes (Vineet)

One subheading per task. Moved into the shared docs after the PR merges (see `docs/prompt.md` section 7).



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
