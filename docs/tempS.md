# Session notes (Nishita)

One subheading per task. Moved into the shared docs after the PR merges (see `docs/prompt.md` section 7).

---------------------------------------------------------------------------------------------------

## Config files: clearer comments and some new values (branch docs/config-comments, 10 Nov)

1. Comments: `sla.ini` (note that the SLA clock runs in shift hours from app.ini, Mon-Sat, minus holidays),
   `features.ini` (one plain line per switch), `logging.ini` (how to debug), `koko.ini` (temperature range,
   what a token is).

2. Values changed on purpose: `sla.ini` escalate_after_minutes 10 -> 30, `assign.ini` max_batches_per_day
   3 -> 1, `app.ini` jobs_enabled true -> false (stops SLA checks, board alerts and auto-assign).

3. Learned: `storage.ini` allowed_types can only remove types. A new type also needs adding to `TYPES` in
   `file_service.py`. Files are saved as they are; nothing converts them.
