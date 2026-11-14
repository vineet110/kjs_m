"""KJS Chat, day 3: the live push (WebSocket /api/v1/chat/ws).
A sends, B sees it live; a non-member gets nothing; another website (wrong Origin) is refused; no
login = closed with 4401; logging out or being disabled closes the live connection.

Starlette's TestClient runs the app on its own event loop in a thread. Everything in one scenario
(HTTP calls and WebSockets) goes through ONE TestClient, so the hub and the sockets share that loop.
Tests use NullPool, so the database works from that thread too."""
import asyncio
import threading
import time

import pytest
from sqlalchemy import select
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.core.database import AsyncSessionLocal
from app.main import app
from app.models.user import User
from app.services import chat_hub
from tests.conftest import HDR, id_token, make_user

C = "/api/v1/chat"
WS = f"{C}/ws"
OURS = {"origin": "http://localhost:3000"}  # in ALLOWED_ORIGINS for tests


async def _team(*names: str) -> dict[str, int]:
    for n in names:
        await make_user(f"{n}@kjsindia.com")
    async with AsyncSessionLocal() as db:
        return {n: i for n, i in (await db.execute(select(User.name, User.id))).all() if n in names}


def _login(tc: TestClient, name: str) -> None:
    r = tc.post("/api/v1/auth/login", json={"id_token": id_token(f"{name}@kjsindia.com")}, headers=HDR)
    assert r.status_code == 200, r.text


def _hello(ws) -> None:
    assert ws.receive_json()["type"] == "hello"


def _closed_with(ws) -> int:
    """Read until the server closes; pings in between are fine. Returns the close code."""
    with pytest.raises(WebSocketDisconnect) as e:
        while True:
            assert ws.receive_json()["type"] == "ping"
    return e.value.code


async def test_a_sends_b_sees_it_live_and_outsiders_see_nothing():
    ids = await _team("asha", "ravi", "meena")

    def scenario():
        with TestClient(app) as tc:
            _login(tc, "ravi")  # each socket keeps the cookie it opened with
            with tc.websocket_connect(WS, headers=OURS) as ravi:
                _hello(ravi)
                _login(tc, "meena")
                with tc.websocket_connect(WS, headers=OURS) as meena:
                    _hello(meena)
                    _login(tc, "asha")

                    cid = tc.post(f"{C}/channels", json={"name": "sales", "member_ids": [ids["ravi"]]},
                                  headers=HDR).json()["id"]
                    assert ravi.receive_json() == {"channel_id": cid, "type": "channel.changed"}

                    sent = tc.post(f"{C}/channels/{cid}/messages", json={"body": "hi ravi"}, headers=HDR).json()
                    ev = ravi.receive_json()
                    assert ev["type"] == "message.new" and ev["message"] == sent and ev["channel_id"] == cid

                    tc.patch(f"{C}/messages/{sent['id']}", json={"body": "hi Ravi"}, headers=HDR)
                    ev = ravi.receive_json()
                    assert ev["type"] == "message.edited" and ev["message"]["body"] == "hi Ravi"

                    tc.delete(f"{C}/messages/{sent['id']}", headers=HDR)
                    assert ravi.receive_json() == {"channel_id": cid, "type": "message.deleted",
                                                   "message_id": sent["id"]}

                    # meena got none of that: the first thing she receives is her own new DM
                    dm = tc.post(f"{C}/dm/{ids['meena']}", headers=HDR).json()["id"]
                    assert meena.receive_json() == {"channel_id": dm, "type": "channel.changed"}

                    # reading in one tab tells my other tabs (and nobody else)
                    _login(tc, "ravi")
                    tc.post(f"{C}/channels/{cid}/read", headers=HDR)
                    assert ravi.receive_json() == {"type": "read", "channel_id": cid, "message_id": sent["id"]}
        assert chat_hub.hub.count() == 0  # closed sockets are forgotten

    await asyncio.to_thread(scenario)


async def test_wrong_origin_and_no_login_are_refused():
    await _team("asha")

    def scenario():
        with TestClient(app) as tc:
            _login(tc, "asha")
            for headers in ({"origin": "https://evil.example"}, {}):
                with pytest.raises(WebSocketDisconnect) as e:
                    with tc.websocket_connect(WS, headers=headers) as ws:
                        ws.receive_json()
                assert e.value.code == 1008
            tc.cookies.clear()
            with tc.websocket_connect(WS, headers=OURS) as ws:
                assert _closed_with(ws) == chat_hub.CLOSE_LOGGED_OUT

    await asyncio.to_thread(scenario)


async def test_logout_closes_the_live_connection_at_the_next_ping(monkeypatch):
    await _team("asha")
    monkeypatch.setattr(chat_hub, "PING_SECONDS", 0.2)

    def scenario():
        with TestClient(app) as tc:
            _login(tc, "asha")
            with tc.websocket_connect(WS, headers=OURS) as ws:
                _hello(ws)
                assert ws.receive_json() == {"type": "ping"}  # still logged in: pings keep coming
                tc.post("/api/v1/auth/logout", headers=HDR)
                assert _closed_with(ws) == chat_hub.CLOSE_LOGGED_OUT

    await asyncio.to_thread(scenario)


async def test_disabling_someone_closes_their_chat_at_once(monkeypatch):
    ids = await _team("asha")
    await make_user("boss@kjsindia.com", role="admin")
    monkeypatch.setattr(chat_hub, "PING_SECONDS", 60)  # so only the kick can close it in time

    def scenario():
        with TestClient(app) as tc:
            _login(tc, "asha")
            with tc.websocket_connect(WS, headers=OURS) as ws:
                _hello(ws)
                _login(tc, "boss")
                started = time.monotonic()
                r = tc.post(f"/api/v1/admin/users/{ids['asha']}/status", json={"status": "disabled"}, headers=HDR)
                assert r.status_code == 200, r.text
                assert _closed_with(ws) == chat_hub.CLOSE_LOGGED_OUT
                assert time.monotonic() - started < 5

    await asyncio.to_thread(scenario)


# ---------- PR #55 review fixes ----------

class FakeSocket:
    """Stands in for a browser tab: `hang_send` / `hang_close` make it never answer."""

    def __init__(self, hang_send=False, hang_close=False):
        self.hang_send, self.hang_close = hang_send, hang_close
        self.sent, self.closed_with = [], None

    async def send_json(self, data):
        if self.hang_send:
            await asyncio.sleep(3600)
        self.sent.append(data)

    async def close(self, code=1000):
        if self.hang_close:
            await asyncio.sleep(3600)
        self.closed_with = code


async def test_a_stuck_tab_is_dropped_and_closed_so_it_reconnects(monkeypatch):
    monkeypatch.setattr(chat_hub, "SEND_TIMEOUT", 0.1)
    monkeypatch.setattr(chat_hub, "CLOSE_TIMEOUT", 0.1)
    hub = chat_hub.Hub()
    ok, stuck, dead = FakeSocket(), FakeSocket(hang_send=True), FakeSocket(hang_send=True, hang_close=True)
    for ws in (ok, stuck, dead):
        hub.add(1, ws)
    started = time.monotonic()
    await hub.push([1], {"type": "ping"})
    assert time.monotonic() - started < 1  # a dead tab can't hold up the sender
    assert ok.sent == [{"type": "ping"}] and ok.closed_with is None
    assert stuck.closed_with == chat_hub.CLOSE_TRY_AGAIN  # closed, so the browser reconnects
    assert hub.count() == 1  # only the healthy tab is left


async def test_binary_frames_are_ignored_and_a_kicked_socket_ends_quietly(monkeypatch):
    ids = await _team("asha", "ravi")
    monkeypatch.setattr(chat_hub, "PING_SECONDS", 0.2)

    def scenario():
        with TestClient(app) as tc:
            _login(tc, "ravi")
            with tc.websocket_connect(WS, headers=OURS) as ravi:
                _hello(ravi)
                ravi.send_bytes(b"\x00\x01")  # used to crash the handler (receive_text)
                ravi.send_text("hello?")  # also ignored
                _login(tc, "asha")
                dm = tc.post(f"{C}/dm/{ids['ravi']}", headers=HDR).json()["id"]
                ev = ravi.receive_json()
                while ev["type"] == "ping":
                    ev = ravi.receive_json()
                assert ev == {"channel_id": dm, "type": "channel.changed"}  # still alive and getting events
                # closed by the hub while the handler waits; its next ping must not raise
                tc.portal.call(chat_hub.hub.kick, ids["ravi"])
                assert _closed_with(ravi) == chat_hub.CLOSE_LOGGED_OUT
                time.sleep(0.5)  # past the next ping
        assert chat_hub.hub.count() == 0

    await asyncio.to_thread(scenario)


async def test_read_event_only_when_the_read_position_moved():
    ids = await _team("asha", "ravi")

    def scenario():
        with TestClient(app) as tc:
            _login(tc, "asha")
            dm = tc.post(f"{C}/dm/{ids['ravi']}", headers=HDR).json()["id"]
            tc.post(f"{C}/channels/{dm}/messages", json={"body": "hi"}, headers=HDR)
            _login(tc, "ravi")
            with tc.websocket_connect(WS, headers=OURS) as ravi:
                _hello(ravi)
                tc.post(f"{C}/channels/{dm}/read", headers=HDR)
                assert ravi.receive_json()["type"] == "read"
                tc.post(f"{C}/channels/{dm}/read", headers=HDR)  # nothing new: no event
                _login(tc, "asha")
                tc.post(f"{C}/channels/{dm}/messages", json={"body": "again"}, headers=HDR)
                assert ravi.receive_json()["type"] == "message.new"  # the next event, no second "read"

    await asyncio.to_thread(scenario)


# ---------- PR #55 second review ----------

async def test_a_chatty_client_is_still_rechecked_and_closed_after_logout(monkeypatch):
    await _team("asha")
    monkeypatch.setattr(chat_hub, "PING_SECONDS", 0.5)

    def scenario():
        with TestClient(app) as tc:
            _login(tc, "asha")
            with tc.websocket_connect(WS, headers=OURS) as ws:
                _hello(ws)
                tc.post("/api/v1/auth/logout", headers=HDR)
                # Another thread keeps sending every 0.1 s for up to 4 s, the whole time we wait for the
                # close. Before the fix each frame pushed the check back, so the close only came once the
                # sending stopped (after 4 s). With the fix it comes at the next check (about 0.5 s).
                stop = threading.Event()

                def chatter():
                    for _ in range(40):
                        if stop.is_set():
                            return
                        try:
                            ws.send_text("still here")
                        except Exception:
                            return
                        time.sleep(0.1)

                sender = threading.Thread(target=chatter)
                started = time.monotonic()
                sender.start()
                try:
                    assert _closed_with(ws) == chat_hub.CLOSE_LOGGED_OUT
                    assert time.monotonic() - started < 2, "closed only after the client stopped sending"
                finally:
                    stop.set()
                    sender.join()

    await asyncio.to_thread(scenario)


async def test_a_flooding_client_is_closed():
    await _team("asha")

    def scenario():
        with TestClient(app) as tc:
            _login(tc, "asha")
            with tc.websocket_connect(WS, headers=OURS) as ws:
                _hello(ws)
                for _ in range(chat_hub.MAX_FRAMES + 1):
                    ws.send_text("x")
                with pytest.raises(WebSocketDisconnect) as e:
                    ws.receive_json()
                assert e.value.code == 1008

    await asyncio.to_thread(scenario)


async def test_a_change_that_changes_nothing_sends_no_event():
    ids = await _team("asha", "ravi")

    def scenario():
        with TestClient(app) as tc:
            _login(tc, "asha")
            cid = tc.post(f"{C}/channels", json={"name": "sales", "member_ids": [ids["ravi"]]}, headers=HDR).json()["id"]
            _login(tc, "ravi")
            with tc.websocket_connect(WS, headers=OURS) as ravi:
                _hello(ravi)
                _login(tc, "asha")
                assert tc.patch(f"{C}/channels/{cid}", json={"name": "sales"}, headers=HDR).status_code == 200
                tc.post(f"{C}/channels/{cid}/messages", json={"body": "hi"}, headers=HDR)
                assert ravi.receive_json()["type"] == "message.new"  # no channel.changed before it

    await asyncio.to_thread(scenario)
