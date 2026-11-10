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
5. Found, not ours: `alembic check` reports the `leave_requests` foreign keys (`user_id`, `decided_by`)
   differ between model and migration (`ondelete`). Separate small fix later.
