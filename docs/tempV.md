# Session notes (Vineet)

One subheading per task. Moved into the shared docs after the PR merges (see `docs/prompt.md` section 7).

## KJS Chat: our own Teams, implementation plan (9 Nov, reviewed 10 Nov)

Branch: `feat/team-chat` (phase 1). Each later phase gets its own branch and PR.

### 1. Why

1. Staff have no way to message each other inside the portal. We have only one-way notifications,
   notes on leads, and a single `notes` box on order boards and tasks.
2. We want something like Microsoft Teams without paying for it, so we build our own inside the
   employee portal.

### 2. What we build and what we skip

1. Build: team channels, direct messages (DMs) and group chats, live messages, unread counts, @mentions,
   files, replies, reactions, search, and who's online.
2. Skip for now: voice and video calls. Building them needs WebRTC plus a relay (TURN) server, which is
   weeks of work. Cheap option later: a "Start call" button that opens Jitsi Meet (free, open source,
   we can host it ourselves). It's a new tool, so ask first.
3. Words:
   1. Channel: a chat room for a group or topic (`#sales`, `#dispatch`). Every member sees every message.
   2. DM: the same thing with exactly 2 people. Channels, groups and DMs share one table; `kind` tells
      them apart.

### 3. Checked in the code (10 Nov)

1. No new library: WebSockets already come with `uvicorn[standard]` (`backend/requirements.txt`).
2. Migration 0019 is taken by `origin/feat/client-schedulers` (`0019_lead_harvester.py`, not merged
   yet). Ours is **0020_team_chat**. If theirs merges after ours, check the `down_revision` chain.
3. The login check `current_user` (`backend/app/core/deps.py`) works only for normal requests: it takes a
   `Request` and needs the `x-requested-with` header, which a browser can't send when it opens a
   WebSocket. We add a separate `ws_user` for the WebSocket only and leave `current_user` as it is.
4. In dev, Next.js forwards `/api/*` to the API (`frontend/next.config.mjs`), but that doesn't carry
   WebSockets reliably. For now the browser connects straight to `ws://localhost:8000/api/v1/chat/ws`
   (address in an env setting). Production goes through nginx. Revisit later.
5. nginx doesn't pass WebSocket connections through yet. `deploy/nginx/default.conf` needs a new block
   (see 5.7).
6. The API runs as one process (`--workers 1`, `backend/Dockerfile`), so an in-memory hub is fine.
   uvicorn waits up to 25 s on shutdown (`--timeout-graceful-shutdown 25`), see 5.3.

### 4. Decisions and questions for KJS

1. Who can chat: every logged-in staff member, with anyone. No new permission. (Decided 10 Nov.)
2. No `chat` on/off switch in `features.ini`. (Decided 10 Nov.)
3. Who can create channels? Default: anyone.
4. Can admins read private messages (DMs)? It's a privacy question, so get the answer in writing.
   Default: no.
5. How long are messages kept? Default: forever.
6. Can people delete their messages? Default: only their own, shown as "message deleted".
7. Fold these into backlog section 3 (assumptions) after the PR merges.

### 5. Backend

1. Migration `0020_team_chat`:
   1. `chat_channels`: id, name, kind (`channel`, `group` or `dm`), description, is_private,
      dm_key, created_by, archived_at.
   2. `dm_key` is unique: for a DM it's the two user ids, smaller first (`"12:45"`); empty for other
      kinds. The database itself stops a second DM for the same pair, even on two clicks at once.
   3. `chat_members`: channel_id, user_id, role (`owner` or `member`), last_read_message_id (for unread
      counts), muted. Unique (channel_id, user_id): each person is in a channel only once.
   4. `chat_messages`: id, channel_id, sender_id, body (4,000 characters max), parent_id (replies,
      phase 2), edited_at, deleted_at, created_at. Index on (channel_id, id).
2. API in `backend/app/api/v1/endpoints/chat.py` (logic in `services/chat_service.py`):
   1. `GET /chat/channels`: my channels and DMs, with unread counts.
   2. `POST /chat/channels`: create a channel.
   3. `PATCH /chat/channels/{id}`: rename or archive (owner only). Archived channels are read-only.
   4. `POST /chat/dm/{user_id}`: open the DM with that person (created the first time).
   5. `GET /chat/channels/{id}/messages?before=<id>&limit=50`: older messages, 50 at a time
      (cursor pagination).
   6. `POST /chat/channels/{id}/messages`, and `PATCH` and `DELETE /chat/messages/{id}` (own messages
      only; delete is a soft delete shown as "message deleted").
   7. `POST /chat/channels/{id}/read`: mark as read.
   8. `POST` and `DELETE /chat/channels/{id}/members`: add or remove people.
   9. `WS /api/v1/chat/ws`: the live push.
3. How live messages work:
   1. Every message is saved in the database first. Someone logged out or offline loses nothing: when
      they log in, the page loads their messages and unread counts from the database (like Teams).
   2. Sending uses the normal API (`POST`), so it reuses permissions, validation, rate limits and errors.
   3. The WebSocket (a line that stays open between the browser and the API) only pushes events to
      whoever is online: new, edited and deleted messages, and reads.
   4. The hub (`services/chat_hub.py`) is a small list in the API's memory of who is connected right now,
      with `push(user_ids, event)` and `kick(user_id)`. Fine with one API process (backlog A41). With
      several servers we'd switch to Postgres LISTEN/NOTIFY, also with no new library.
   5. Push only after the save is committed, so nobody sees a message that then failed to save.
   6. After a dropped connection, the browser reconnects and fetches messages after the last one it saw.
   7. A ping every 30 s keeps the connection open (Cloudflare drops idle ones after about 100 s).
   8. On each ping, check the session again. If the person logged out, the session expired or they
      were disabled, close that live connection. Their messages stay saved for their next login.
   9. The WebSocket opens a database session only to check login, then closes it, so open connections
      don't use up the database pool.
   10. Deploys: Docker starts the new API and stops the old one. On stopping (shutdown), uvicorn waits up
       to 25 s for open work to finish, and a live connection never finishes by itself. So on shutdown
       the hub closes every connection itself. Browsers reconnect to the new API in a second or two and
       fetch anything they missed.
4. @mentions create a normal notification (reuse `notify()` in `notification_service.py`). Store
   mentions as user ids, and notify only people who are members of that channel.
5. Security:
   1. Check membership on every read, send and live event. A non-member gets 404, not 403.
   2. Show messages as plain text only, never as HTML (blocks XSS).
   3. Rate-limit sending for each user (reuse `RateLimiter` in `rate_limit.py`).
   4. `ws_user`: reads the same session cookie as `current_user`, and checks the `Origin` header is our
      own site (this replaces the `x-requested-with` check, which WebSockets can't send).
   5. A disabled staff member: `kick()` their live connections and remove them from channels.
   6. Record channel deletes, member removals and admin actions in the audit log (`audit_service.py`).
6. Tests (`backend/tests/test_chat.py`): use Starlette's `TestClient.websocket_connect` for the live part.
7. nginx: a `location = /api/v1/chat/ws` block with `proxy_http_version 1.1`, the `Upgrade` and
   `Connection "upgrade"` headers, and `proxy_read_timeout 1h`.

### 6. Frontend

1. Page: `frontend/src/app/[locale]/(employee)/employee/chat/`.
2. Left column: channels, then DMs, with unread badges and a "+" for a new channel or DM.
3. Middle: messages. Scrolling up loads older ones. Date dividers, sender name and time.
4. Message box: Enter sends, Shift+Enter adds a new line, @ picks a person.
5. A `useChatSocket` hook: connects, reconnects with a growing wait (1 s, 2 s, 4 s… up to 30 s), and
   after reconnecting fetches what it missed.
6. Sidebar (`components/portal/SidebarNav.tsx`): a "Chat" entry with the total unread count.
7. Phone: the channel list opens a full-screen chat with a back button.
8. All text in `messages/en.json`.

### 7. Phases

1. Phase 1 (): channels, DMs and groups, live messages, unread counts, @mentions,
   editing and deleting your own messages.
2. Phase 2 (): files and images (reuse the `files` table and storage), replies,
   emoji reactions, search.
3. Phase 3 (): who's online, "typing…", browser pop-ups for new messages.
4. Later, after asking: the Jitsi call button.

### 8. Phase 1, day by day

1. Day 1: database and channels.
   1. Migration 0020 and `backend/app/models/chat.py` (register in `models/__init__.py`).
   2. `chat_service.py`: my channels, create channel, open DM, add and remove members, rename and archive.
   3. `chat.py` endpoints, added to the router.
   4. Tests: non-members get 404, a DM is made only once per pair, archived channels are read-only.
2. Day 2: messages.
   1. Send, list with `before=` pagination, edit and delete own, mark read, unread counts in one query.
   2. Rate limit on sending, @mention notifications.
   3. Tests: page order, unread count up and down, editing someone else's message gives 404, the rate
      limit, a mention creates a notification.
3. Day 3: live push.
   1. `chat_hub.py`, `ws_user` with the Origin check, the 30 s ping with the session re-check, closing
      all connections on shutdown.
   2. WebSocket tests: A sends and B receives; a non-member receives nothing; a wrong Origin is refused.
   3. The nginx block.
   4. Check with two browsers: user A sends, and user B sees it without reloading.
4. Day 4: the chat page, `useChatSocket`, the sidebar entry and mentions.
5. Day 5: a two-user e2e test in `scripts/e2e/browser_e2e.mjs`, fixes, notes here, then the PR.

### 9. Before starting

1. Tell devillover27 (`feat/client-schedulers`) that 0020 is ours and they have 0019.
2. Tell Nishita: migration 0020 and the new `chat` files are taken.
3. New words for `kb.md`: channel, WebSocket, hub, cursor pagination, Origin check, soft delete,
   graceful shutdown, WebRTC / TURN.

### 10. Progress

1. Day 1 done (10 Nov): migration `0020_team_chat`, `models/chat.py`, `services/chat_service.py`,
   `endpoints/chat.py` (router prefix `/chat`), `tests/test_chat.py` (11 tests). Full suite: 302 passed.
   Migration down to 0018 and back up works.
2. Routes added on day 1: `GET/POST /chat/channels`, `GET/PATCH /chat/channels/{id}`,
   `POST /chat/dm/{user_id}`, `POST /chat/channels/{id}/members`,
   `DELETE /chat/channels/{id}/members/{user_id}` (your own id = leave).
3. The people picker reuses `GET /employee/colleagues` (active staff).
4. Rules I chose (guesses, fold into backlog section 3 after the PR):
   1. Channel: only the owner renames, archives, adds and removes. Group chat: any member adds people
      and renames; only the owner removes others and archives. DM: no changes at all.
   2. A group chat needs at least 2 other people (one person = a DM).
   3. Last owner leaves: the longest-standing member becomes owner. Last person leaves: archived.
   4. Public channels can't be browsed or joined yet; you see only chats you're in. `is_private` is
      stored for a later "browse channels" page.
   5. No admin override yet (admins manage only their own chats).
5. Day 2 done (10 Nov): messages.
   1. Routes: `GET /chat/channels/{id}/messages` (`before=`, `after=`, `limit=` up to 100),
      `POST /chat/channels/{id}/messages` (`body`, `mention_ids`), `PATCH` and `DELETE /chat/messages/{id}`,
      `POST /chat/channels/{id}/read` (optional `message_id`), `GET /chat/unread` (sidebar total).
   2. `GET /chat/channels` now has `unread` and `last_message_id`. Order: channels A to Z, then groups
      and DMs with the newest message first, archived last.
   3. Added a `mentions` column (user ids) to migration 0020 itself, since 0020 isn't merged anywhere.
      If you ran 0020 on a local database, run `alembic downgrade 0018` then `upgrade head` there.
   4. `after=` is for catching up after a dropped connection (day 3).
   5. 7 more tests (18 chat tests in all).
6. More guesses (fold into backlog section 3 after the PR):
   1. Deleting a message wipes its text (the row stays so the order makes sense).
   2. A mention notifies even in a muted chat (bell + email, like Teams). Editing a message notifies
      only the people newly mentioned.
   3. Muted chats don't count in the sidebar total.
   4. Sending limit: 30 messages a minute per person.
7. Day 3 done (10 Nov): live push.
   1. `services/chat_hub.py` (who is connected, `push`, `kick`), `ws_user` and `origin_allowed` in
      `core/deps.py` (`current_user` untouched), `WS /api/v1/chat/ws` in `endpoints/chat.py`, and every
      save in `chat_service.py` now pushes an event after commit.
   2. Events: `hello`, `ping`, `message.new`, `message.edited`, `message.deleted`, `read` (only to the
      reader's other tabs), `channel.changed` (re-fetch the chat list).
   3. Close codes for the page: 4401 = logged out (go to login, don't reconnect); 1012 = server
      restarting (reconnect); anything else = reconnect with a growing wait.
   4. Disabling someone closes their chat tabs at once (`auth_service.set_status` calls `kick`).
      Logout and expiry are caught at the next ping (30 s).
   5. Tests: `tests/test_chat_live.py` (4 tests). I broke the kick on purpose and the disable test
      failed, so the test really checks it.
   6. Real-server check (instead of two browsers, the page comes on day 4): real uvicorn, then real
      nginx 1.28 in front. B got A's message live; a wrong Origin got 403; nginx logged 101 (upgrade
      worked); `nginx -t` passed.
   7. nginx block added in `deploy/nginx/default.conf`. It repeats Host and X-Forwarded-* because any
      `proxy_set_header` inside a location drops the server-level ones.
8. Changes from the plan (day 3):
   1. No hub shutdown step: uvicorn 0.30.1 already closes every WebSocket with code 1012 when it stops.
      Checked: the server stopped in 0.2 s with a chat open.
   2. A disabled person is NOT removed from their chats (that would break their DMs and lose them if
      they're turned back on). Their live tabs are closed and they can't log in; that's enough.
9. Day 4 done (10 Nov): the chat page.
   1. Page `frontend/src/app/[locale]/(employee)/employee/chat/page.tsx`; parts in
      `frontend/src/components/portal/chat/` (`ChatList`, `MessagePane`, `NewChat`); types, the live
      connection hook `useChatSocket` and the sidebar count `useChatUnread` in `frontend/src/lib/chat.ts`.
   2. Sidebar: "Chat" under My work, with the unread total (asked on each page change, every minute, and
      at once after reading).
   3. What it does: "+" for a DM, group chat or channel; live messages; unread badges; date dividers;
      scroll up for older; Enter sends, Shift+Enter new line; @ picker; edit and delete your own;
      People panel (add, remove, leave, archive); archived chats read-only; phone layout with a back
      button; "Reconnecting…" bar; catches up after a dropped connection.
   4. The message box empties at once on Enter (you can type the next one); if sending fails the text
      comes back. Found by the browser test: before, the box was locked while sending.
   5. Live address: `NEXT_PUBLIC_CHAT_WS_URL` if set; `next dev` uses port 8000; a production build uses its
      own site. Documented in `.env.example`.
   6. Text is written in the components, like every other portal page (next-intl is installed but unused,
      memory.md). Changed from the plan, which said `messages/en.json`.
   7. Day 5's browser test is done early: `scripts/e2e/chat_e2e.mjs`, two Chromes as Asha and Ravi, 35
      checks, all pass. How to run it: `scripts/e2e/README.md` step 9.
10. Day 5 (10 Nov): phase 1 finished. Final checks: backend 313 passed, frontend typecheck and 44 tests
    passed, chat browser test 35 passed. PR raised from `feat/team-chat` to `main`.
    1. On deploy: run migration 0020, and reload nginx (new chat block).
    2. Done 10 Nov: #53 (0019) merged first, so 0020 now comes after 0019. `main` merged into this branch;
       `router.py` and `models/__init__.py` keep both sides. Any local database that already ran the old
       0020 (after 0018) must go back to 0018 and upgrade again, or 0019 is never applied.
    3. To fold after merging: the guesses in items 4, 6 and 8 into backlog section 3; the new words
       (section 9) into kb.md; the leave_requests note below into the backlog.
11. PR #55 review fixes (10 Nov), all 10 from the code review:
    1. A stuck tab is now closed, not only dropped, so it reconnects (2 s limit on the close too).
    2. The socket ignores anything the browser sends (binary too) and ends quietly if the hub already
       closed it.
    3. Someone added to a chat starts "read up to now": no unread flood from old history.
    4. The "read" event is sent only when the read position moved; the page skips one it already knows,
       and reloads the list and the sidebar count at most every 0.5 s.
    5. Mention titles in unnamed groups are built per person.
    6. Opening a chat merges with live messages instead of replacing them.
    7. After a reconnect the page also reloads the newest 50, so edits and deletes made meanwhile show.
       Accepted limit: edits to older messages show after a reload.
    8. Own edit and delete update the screen as soon as the server confirms.
    9. Mention bold: longest names first (`mentionParts` in `lib/chat.ts`, unit tested).
    10. Cleanups: one shared `session_user` for `current_user` and `ws_user` (only the query moved);
        `RateLimiter.check()` takes an optional message.
    11. Tests: 5 new backend tests (fixes 1 and 2 shown to fail without the fix), 2 frontend unit tests,
        6 new browser checks for a dropped connection (41 in all, all pass).
12. PR #55 second review fixes (10 Nov). Why they slipped through the first time: I fixed where the
    bug showed instead of the one shared rule; one helper did two jobs (add vs replace); catch-up was a
    "reconnect only" special case; the logout check depended on silence; tests copied the reported case.
    1. The session is re-checked every 30 s by the clock, whatever the browser sends. More than 20 frames
       between two checks closes the tab (our page sends none). NOTE for phase 3 ("typing…"): raise
       that limit, or the page's own typing events will close it.
    2. One mention rule (`mentionParts` / `mentionIds` in `lib/chat.ts`) for showing, sending and editing:
       longest names first, and the name must end there ("@Ramesh" is not "@Ram"; Hindi vowel signs count
       as part of the word). Accepted: two people with exactly the same name are both mentioned.
    3. Edits only replace messages already on screen (an old one no longer jumps to the top).
    4. Catch-up runs on every connection, the first one too ("after" skipped while the chat loads).
    5. The "New chat" dialog sets itself up once (focus no longer jumps while messages arrive).
    6. A failed "load older" shows a message and waits 3 s before trying again.
    7. Unread counts read only messages after the read position, through the index; the sidebar total
       skips muted chats in the same query.
    8. "Archive + rename" in one request works; a change that changes nothing saves and pushes nothing.
    9. Tests: 6 new backend tests, 2 new unit tests, 14 new browser checks (55 in all). Shown to fail with
       the fix undone: the mention rule (3 unit tests fail), edits (2 browser checks fail), the clock
       check (backend test fails).
    10. No third review round (our 2-round rule). Before merging: 10 minutes by hand in two browsers.
13. Found, not ours: `alembic check` reports the `leave_requests` foreign keys (`user_id`, `decided_by`)
   differ between model and migration (`ondelete`). Separate small fix later.

## Lead Harvester security fix (10 Nov, branch `fix/harvest-security`)

From the PR #53 review. #53 was merged first (devillover27 away 2 weeks); this follows it.

1. Secret leak fixed: a source's API key must be a setting named `HARVEST_...`. Checked when creating,
   when editing (edits weren't checked at all before) and again at every fetch. The key is only sent to
   the source's own host, over https.
2. SSRF fixed: one `safe_get()` (`backend/app/services/harvest_net.py`) for all four fetchers and
   robots.txt:
   1. https only; public addresses only (no localhost, private, link-local or metadata addresses);
   2. the host is looked up and the connection goes to a checked public address (this also stops DNS
      rebinding); the https certificate is still checked for the real host name;
   3. redirects followed by hand, at most 5, each checked; https to http refused.
3. Plain http for a specific public feed: `HARVEST_ALLOW_HTTP_HOSTS` (empty by default; in `.env.example`).
4. Permissions: only `assign.manage` (admins have it). Before, `leads.view_all` and `staff.approve` could
   also add and run harvesters. Tell the team.
5. Tests: new `backend/tests/test_harvest_security.py` (13). Switching off the name check, the address
   check or the permission check each makes tests fail.
6. Review of #62 (quick), 6 fixes:
   1. A failed connection tries the next checked address, IPv4 first (max 3; 10 s connect each). A site's
      answer is never retried elsewhere.
   2. robots.txt 5xx = don't scrape (Python's own rule; my first version allowed it).
   3. `HARVEST_` settings are also read from the `.env` files (`harvest_setting`), so they work locally;
      only `HARVEST_` names can ever be read this way.
   4. System proxy settings are ignored (`trust_env=False`).
   5. A robots.txt that leads to an internal address = don't scrape.
   6. IPv4 hidden inside IPv6 (NAT64, 6to4, Teredo) is judged by the IPv4 inside.
   Not done (backlog): public IPv6 typed as an address is refused; validators written twice (create/edit);
   no size limit on downloads (only `assign.manage` can add sources).
7. Still open (separate PR): robots.txt allows scraping when it can't be read; unknown categories
   (`spices`, `private_label`); a number in the phone field crashes a run; duplicates inside one fetch;
   `+91 98765 43210` numbers lost; one failing source breaks the rest of the run; phone duplicates in other
   formats; the job lock released early (matters only with several API processes).

## Session wrap-up (10 Nov)

### 1. Merged today

1. #53 Lead Harvester (devillover27, away 2 weeks), merged before its fixes on purpose; #62 fixed its
   security problems right after. `main` was not deployed in between.
2. #55 KJS Chat phase 1 (after 3 review rounds; round 3 left only rare or cosmetic items, not listed).
3. #58 and #60 (Nishita: phase switches per portal area), #62 (harvester security), #63 (Nishita:
   clearer sidebar names).
4. Migration order on `main`: 0018 -> 0019 (harvester) -> 0020 (chat).

### 2. Database

1. Neon migrated by hand to 0020 (Vineet ran `alembic upgrade head` from `backend/`; checked: 0020,
   three `chat_*` tables). Neon had 0 harvest sources, so the new `HARVEST_` naming broke nothing.
2. `alembic` only runs from `backend/` with the project Python: `.venv\Scripts\python -m alembic ...`.
   Our `.env` points at Neon, so that command changes Neon (see memory note on alembic and Neon).

### 3. Branches cleaned

1. Deleted 27 merged local branches and 47 merged GitHub branches (none had an open PR; a merged
   branch can be restored from its PR page). Kept `main`, `kjs_v`, `kjs_n`.
2. Kept because not merged: `docs/code-review`, `feat/connect-popup`, and `feat/module-switches-api`
   (its PR #58 merged, but the branch has commits that are not in `main`: ask Nishita).

### 4. Chat: channel vs group chat (for kb.md)

1. Channel: a team or topic (`#sales`), needs a name, public or private, only the owner manages it.
2. Group chat: a quick talk between 3 or more people, name optional, always private, any member adds
   people; only the owner removes people or archives.
3. DM: exactly 2 people, can't be changed.

### 5. Web scraping (asked by Vineet)

1. Built in #53 ("Web Scraping (Strict robots.txt)" in Admin > Client Schedulers), protected by #62.
   KJS adds links from the screen; API keys and http-only hosts are server settings on purpose.
2. Too basic for real use: one record per page (first email, first phone, page title).
3. Government sites: use their open data (data.gov.in, "Open Data" type) or RSS first; scrape only
   what is left and check each site's terms. Names and phone numbers are personal data (DPDP).
4. Backlog D18 says nightly scraping is Stage 2 (2027), but KJS's demo video shows it: decide with KJS.

### 6. Next

1. Ask KJS for its list of government sites and the Stage 1 / Stage 2 answer for scraping (D18).
2. Harvester follow-up PR: the 7 open bugs above, and read many records per page (Python's built-in
   HTML parser, no new library).
3. Before going live: 10 minutes of chat by hand in two browsers; get the "can admins read DMs?" answer
   from KJS in writing.
4. Fold these notes into the shared docs (`docs/fold-` branch, prompt.md section 7).

## Oracle free VM hosting plan (for 11 Nov)

### 1. Why

1. Free server now (Oracle Always Free: ARM, up to 4 CPU / 24 GB RAM), instead of waiting for the
   KJS server. Our `deploy/` setup (Docker Compose) runs on it unchanged.
2. Decided with Nishita and KJS (10 Nov). Staging or production: (fill in). Fold into `backlog.md` later.

### 2. Steps

1. Account: oracle.com/cloud/free, home region Mumbai (can't change later), upgrade to Pay As You Go
   (still free; stops idle reclaim and "Out of capacity").
2. VM: Ubuntu 24.04, `VM.Standard.A1.Flex` 2 CPU / 12 GB, 100 GB disk, public IP. Download the SSH key.
3. Log in: `ssh -i key.key ubuntu@<ip>`, update, timezone Asia/Kolkata. Open no web ports (the
   Cloudflare Tunnel connects out).
4. Tools: Docker + compose plugin, git; add `ubuntu` to the docker group.
5. App: `deploy/README.md` section 2: clone (read-only deploy key), videos, `.env`, `./deploy.sh`, seed.
   The first build is also the ARM check.
6. Live: Cloudflare Tunnel, subdomain to `nginx:80`, SSL "Full".
7. Backups: nightly cron + off-site R2.
8. Check: laptop + phone, `test-restore.sh` (about 35 min), write results here.

### 3. Time and blockers

1. About 3 to 4 hours in total.
2. Blockers: card rejected, "Out of capacity", access to the Cloudflare account for `kjsindia.com`,
   the R2 backup token. Get the last two ready before starting.

## Sidebar renames check (#54, #63), 10 Nov

1. Checked after merge, before the docs fold: api_e2e 196/196, browser_e2e 74/74, every sidebar link
   (admin and staff, computer and phone) opens, lights up and keeps staff out of admin pages. All good.
2. Known: `sidebar_e2e.mjs` shows 1 failure, "phone: choosing a page closes it". The test's fault, not the
   product: its `clickLink` helper opens all closed groups in one go and only the last stays open, so
   "All Enquiries" (moved into Lead Management by #63) is never shown. A real tap works (checked). Fix
   later: open only the needed group in the test, or make the group toggle in `SidebarNav.tsx` use the
   latest state. Don't chase it as a bug.
3. Accepted as they are (Vineet): greeting headings on Today and Admin overview, no heading on My
   attendance, "Manage employees", "Client Schedulers (Lead Harvester)", and "Order Boards & Assigning"
   wrapping to 2 lines.
