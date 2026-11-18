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

8. Seen on 18 Nov: `next build` warns that Next.js 16.4.3 has a known security vulnerability. Not from this
   PR. Upgrading is a dependency change: ask, then add to backlog section 21 at the next fold.

9. Second review of #91 (18 Nov): fixed list keys per file (`ini.py` `_list_fields`). Left for later (Vineet's
   call), add to backlog at the next fold:

   i.    ✅ Fixed 18 Nov (CodeRabbit round): no limit sent = min(50, page_max).
   ii.   🟠 One bad value makes the WHOLE config fall back to defaults on first load (e.g. jobs_enabled back
         on). `storage.max_upload_mb` max went 500 -> 25: a server with 26-500 set (ini or
         `KJS__STORAGE__MAX_UPLOAD_MB`) loses all its ini values. Check the VPS env before deploying; later:
         warn instead of refuse for this key, or validate per file.
   iii.  🟢 `POST /employee/leads/import` (JSON) is under nginx's 1 MB default: ~3000 rows hit it while
         `import_max_rows` allows 5000. Add it to the 26 MB nginx rule or lower the bound.
   iv.   🟢 After `body_max` is lowered, older long messages can't be edited (edit reuses `MessageIn`).
   v.    🟢 Open tabs keep old `me.limits` until reload (server still checks every request).
   vi.   🟢 Cleanups: MB->bytes in one place (`lead_reader`, `assign.py`); stale comments ("up to 3 tries" in
         `notification_service.send_emails`, "Missed more than 100" in chat page); `lead_service.sla()` reads
         `cfg()` per lead (read once per list).

10. CodeRabbit review of #91 (18 Nov): fixed chat default page, job timeout must cover the email budget + 30 s,
    auto-assign counts only rows with data (refused past 200,000 lines, never a partial import), lead cards
    read at least 50 rows, one size limit per lead upload. Left for the backlog (Vineet's call):

    i.    🟢 `jobs/runner.py loop_is_alive()`: lowering `job_timeout_seconds` while a long job runs can make
          the health check say "stuck" for that run (the job keeps the timeout it started with). Fix: remember
          the running job's timeout and use the larger of it and the config value.
