"""KJS Chat live push: who is connected right now, and sending them events.

The hub is a list in this process's memory: user id -> that person's open WebSockets (one per tab).
1. Fine while the API runs as one process (`--workers 1`, backlog A41). With several processes or
   servers, switch to Postgres LISTEN/NOTIFY (no new library).
2. It only pushes. Every message is saved in the database first, so someone offline loses nothing:
   the page loads from the database when they come back.
3. Services push only after db.commit(), so nobody sees a change that then failed to save.
4. Events (JSON):
   message.new / message.edited  {channel_id, message}
   message.deleted               {channel_id, message_id}
   read                          {channel_id, message_id}   (only to the reader: their other tabs)
   channel.changed               {channel_id}               (re-fetch the chat list)
   ping                                                     (every PING_SECONDS)
5. Deploys: uvicorn itself closes every WebSocket with code 1012 ("restarting") when it stops, so the
   hub doesn't need its own shutdown step. Browsers reconnect to the new API and fetch what they missed.
"""
import asyncio
import logging
from collections import defaultdict

from fastapi import WebSocket
from fastapi.encoders import jsonable_encoder

log = logging.getLogger(__name__)

PING_SECONDS = 30.0  # keeps the connection open (Cloudflare drops idle ones after ~100 s)
SEND_TIMEOUT = 5.0  # a stuck browser must not hold up the person who sent the message
CLOSE_TIMEOUT = 2.0  # closing a dead connection must not hang either
CLOSE_LOGGED_OUT = 4401  # our own close code: "log in again", the browser must not just reconnect
CLOSE_TRY_AGAIN = 1013  # standard "try again later": the browser reconnects and catches up


class Hub:
    def __init__(self) -> None:
        self._conns: dict[int, set[WebSocket]] = defaultdict(set)

    def add(self, user_id: int, ws: WebSocket) -> None:
        self._conns[user_id].add(ws)

    def remove(self, user_id: int, ws: WebSocket) -> None:
        conns = self._conns.get(user_id)
        if conns is not None:
            conns.discard(ws)
            if not conns:
                del self._conns[user_id]

    def online(self, user_id: int) -> bool:
        return bool(self._conns.get(user_id))

    def count(self) -> int:
        return sum(len(c) for c in self._conns.values())

    async def push(self, user_ids, event: dict) -> None:
        """Send to every open tab of these people. A tab that fails or is too slow is dropped AND its
        connection closed: the browser then sees the close, reconnects and catches up. (Only removing it
        would leave the tab open, showing "live", but never getting another event: review of PR #55.)"""
        targets = [(uid, ws) for uid in set(user_ids) for ws in list(self._conns.get(uid, ()))]
        if not targets:
            return
        data = jsonable_encoder(event)  # dates -> ISO text, like normal API responses

        async def send(uid: int, ws: WebSocket) -> None:
            try:
                await asyncio.wait_for(ws.send_json(data), SEND_TIMEOUT)
            except Exception:  # closed, broken or too slow
                self.remove(uid, ws)
                log.info("chat.push_dropped", extra={"to_user": uid, "event": event.get("type")})
                await _close(ws, CLOSE_TRY_AGAIN)

        await asyncio.gather(*(send(uid, ws) for uid, ws in targets))

    async def kick(self, user_id: int) -> None:
        """Close all of this person's live connections (disabled, or logged out everywhere)."""
        for ws in list(self._conns.pop(user_id, ())):
            await _close(ws, CLOSE_LOGGED_OUT)


async def _close(ws: WebSocket, code: int) -> None:
    """Close, but never wait long: closing a dead connection can hang too, and the person who sent
    the message is waiting for this push."""
    try:
        await asyncio.wait_for(ws.close(code=code), CLOSE_TIMEOUT)
    except Exception:
        pass  # already closed, or the connection is dead: either way it's gone from the hub


hub = Hub()
