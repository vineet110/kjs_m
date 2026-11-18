# Session notes (Vineet)

One subheading per task. Moved into the shared docs after the PR merges (see `docs/prompt.md` section 7).


## Employee monitoring, Phase A: work pages (branch feat/employee-work, 14 Nov)

1. Plan v5 agreed in chat (mockup: Team work, one employee, Sites, My work, extension popup). Phases:

   i.    A: work pages (this branch).

   ii.   B: screenshots, idle with reason, Break button, alerts (migration 0028).

   iii.  C: extension API, Sites tab, visit outcomes (migration 0029).

   iv.   D: Chrome extension (Manifest V3), unlisted Chrome Web Store page. No force-install: KJS
         laptops are Windows Home. The extension is optional: no extension = "not installed yet" message,
         no admin alert.

   v.    Monitoring policy and employee consent: already signed offline at KJS.

2. Step 0 (config research): no restructure needed. The existing `config/*.ini` setup already gives one
   checked file per area, live reload, env overrides and safe fallback. New file `config/monitoring.ini`
   (max_range_days, timeline_page_size, team_refresh_seconds); Phase B adds its numbers there.

3. What Phase A adds:

   i.    Permission `monitor.view` (admins have it automatically; can be ticked for an employee).

   ii.   Area `monitoring` in `modules.ini` (no rule tying it to attendance: that would make switching
         attendance off refuse the whole file).

   iii.  Migration 0027: three indexes (lead_notes, tasks, chat_messages by person and time). Tell Nishita.

   iv.   API `/work/team`, `/work/{id}/overview|timeline|tasks|attendance` (monitor.view) and
         `/work/me/...` (own data only, the id always comes from the login).

   v.    Audit row `work.viewed`: once per viewer, per person, per IST day.

   vi.   Screens: Team work (admin), one employee (tabs), My activity (employee).

4. Guesses to move into backlog section 3 after merge:

   i.    The `monitoring` area was added in Phase A, not B.

   ii.   One-to-one chats show in the timeline (policy signed).

   iii.  Date range limit 31 days (config).

   iv.   Timeline shows only finished tasks; open tasks are on the Tasks tab.

5. Terms for kb.md: keyset paging ("Load more" with a `before` time instead of page numbers).
