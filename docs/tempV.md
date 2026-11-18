# Session notes (Vineet)

One subheading per task. Moved into the shared docs after the PR merges (see `docs/prompt.md` section 7).


## Config per feature (18 Nov, PR #91; backlog gaps PR #90)

1. What changed: tunable numbers moved from the code into `config/<feature>.ini`. New files: chat, leads,
   attendance, notifications, harvest, boards, analytics. New keys in complaints, koko, assign, app
   (`job_timeout_seconds`). `app.page_size` removed (nothing read it).

2. Defaults = the old values, so nothing changes for users. No migration, no new dependency.

3. Kept in code on purpose: security limits (`file_check.MAX_UNZIPPED`, `assign_service.MAX_UNZIPPED_MB`,
   `harvest_net.MAX_REDIRECTS`, `auth_service.FRESH_SIGN_IN_SECONDS`, `deps.FIREBASE_CHECK_EVERY`) and chat's
   connection timings (`chat_hub.PING_SECONDS`, `SEND_TIMEOUT`: tied to Cloudflare's idle limit, not business).

4. `/auth/me` now sends `limits` (chat body max, complaint word minimums). The portal uses them, with the old
   numbers only as a fallback.

5. Rules added: `docs/prompt.md` section 3 rules 11-13 (config per feature, stay on Postgres, new feature
   checklist); `CLAUDE.md` fixed (real folders); new `backend/CLAUDE.md`, `frontend/CLAUDE.md`.

6. To fold later:

   i.    `memory.md` decisions: "one ini per feature in config/" and "we stay on Postgres" (backlog R86).
   ii.   `kb.md` terms: config bounds (min/max on a setting), live reload, `me.limits`.

7. When monitoring (#83-#85) comes back: rebase on this; `MonitoringIni` joins the others, and its
   `never_record` must stay typed `list[str]` (list keys now come from the field types).
