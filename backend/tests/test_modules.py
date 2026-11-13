"""Portal areas switched on / admin / off for phased releases (config/modules.ini, app/core/modules.py)."""
import asyncio
import logging
import os
import time
from pathlib import Path

import pytest
from fastapi.routing import APIRoute
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from sqlalchemy import select

from app.core.config import ini
from app.core.database import AsyncSessionLocal
from app.core.errors import AppError
from app.core.modules import AREAS, area_of_link, link_for
from app.jobs.runner import should_run
from app.main import app
from app.models.user import User
from app.services import chat_hub, file_service, notification_service
from tests.conftest import HDR, id_token, login, make_user


@pytest.fixture
def modules(monkeypatch):
    """modules(order_boards="off", ...): set areas for one test, back to the real file afterwards."""
    def set_(**levels):
        for a, lv in levels.items():
            monkeypatch.setenv(f"KJS__MODULES__{a.upper()}", lv)
        ini.reload_now()
    yield set_
    monkeypatch.undo()
    ini.reload_now()


@pytest.fixture
def config_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(ini, "CONFIG_DIR", tmp_path)
    ini.reload_now()
    yield tmp_path
    monkeypatch.undo()
    ini.reload_now()


def write(path, text):
    path.write_text(text, encoding="utf-8")
    t = time.time() + 1  # the modified-time must change even on fast file systems
    os.utime(path, (t, t))


# ---------- The file ----------
def test_all_on_by_default(config_dir):
    assert all(getattr(ini.cfg().modules, a) == "on" for a in AREAS)


def test_values_any_case(config_dir):
    write(config_dir / "modules.ini", "[modules]\norder_boards = Admin\naudit = OFF ; later\n")
    c = ini.reload_now().modules
    assert (c.order_boards, c.audit) == ("admin", "off")


def test_typo_is_refused_and_last_good_kept(config_dir, caplog):
    write(config_dir / "modules.ini", "[modules]\naudit = off\n")
    assert ini.reload_now().modules.audit == "off"
    write(config_dir / "modules.ini", "[modules]\naudit = on\norder_board = off\n")  # misspelt area
    with caplog.at_level(logging.ERROR, logger="app.config"):
        assert ini.reload_now().modules.audit == "off"  # nothing from the bad file applied
    assert any("modules.ini" in getattr(r, "reason", "") and "order_board" in r.reason for r in caplog.records)


def test_bad_value_is_refused(config_dir):
    write(config_dir / "modules.ini", "[modules]\naudit = maybe\n")
    assert ini.reload_now().modules.audit == "on"


def test_rule_batches_needs_attendance(config_dir, caplog):
    write(config_dir / "modules.ini", "[modules]\nbatches = on\nattendance = admin\n")
    with caplog.at_level(logging.ERROR, logger="app.config"):
        c = ini.reload_now().modules
    assert (c.batches, c.attendance) == ("on", "on")  # refused: defaults kept
    assert any("batches = on needs attendance" in getattr(r, "reason", "") for r in caplog.records)
    write(config_dir / "modules.ini", "[modules]\nbatches = admin\nattendance = admin\n")
    assert ini.reload_now().modules.batches == "admin"  # same level is fine


# ---------- Routes ----------
async def test_off_hides_from_everyone(client, modules):
    await make_user("admin@kjsindia.com", role="admin")
    await make_user("e@kjsindia.com")
    modules(order_boards="off")
    for email in ("admin@kjsindia.com", "e@kjsindia.com"):
        await login(client, email)
        r = await client.get("/api/v1/boards")
        assert r.status_code == 404 and r.json()["code"] == "module_off", email
        assert r.json()["details"] == {"module": "order_boards"}


async def test_admin_level_lets_only_admins_in(client, modules):
    await make_user("admin@kjsindia.com", role="admin")
    await make_user("e@kjsindia.com")
    modules(order_boards="admin")
    await login(client, "e@kjsindia.com")
    assert (await client.get("/api/v1/boards")).status_code == 404
    await login(client, "admin@kjsindia.com")
    assert (await client.get("/api/v1/boards")).status_code == 200


async def test_not_logged_in_is_still_401(client, modules):
    modules(order_boards="off")
    assert (await client.get("/api/v1/boards")).status_code == 401


async def test_admin_routes_by_area(client, modules):
    await make_user("admin@kjsindia.com", role="admin")
    await login(client, "admin@kjsindia.com")
    modules(audit="off", website_admin="off")
    assert (await client.get("/api/v1/admin/audit")).json()["code"] == "module_off"
    assert (await client.get("/api/v1/admin/products")).json()["code"] == "module_off"
    stats = (await client.get("/api/v1/admin/stats")).json()  # Overview stays, without the shop numbers
    assert stats["products"] is None and stats["leads_total"] == 0
    assert (await client.get("/api/v1/admin/approvals")).status_code == 200


async def test_analytics_leaves_out_hidden_areas(client, modules):
    await make_user("admin@kjsindia.com", role="admin")
    await login(client, "admin@kjsindia.com")
    modules(attendance="off", batches="off", order_boards="off")
    out = (await client.get("/api/v1/admin/analytics")).json()
    assert out["attendance"] is None and out["boards"] is None and "leads_per_week" in out


async def test_me_lists_the_areas(client, modules):
    await make_user("admin@kjsindia.com", role="admin")
    await make_user("e@kjsindia.com")
    modules(order_boards="admin", audit="off")
    me = (await login(client, "e@kjsindia.com")).json()["modules"]
    assert set(me) == set(AREAS)
    assert me["order_boards"] is False and me["audit"] is False and me["attendance"] is True
    me = (await client.get("/api/v1/auth/me")).json()["modules"]  # same answer from /me
    assert me["order_boards"] is False
    await login(client, "admin@kjsindia.com")
    me = (await client.get("/api/v1/auth/me")).json()["modules"]
    assert me["order_boards"] is True and me["audit"] is False


async def test_board_files_follow_order_boards(modules):
    await make_user("e@kjsindia.com")
    modules(order_boards="off")
    async with AsyncSessionLocal() as db:
        user = await db.scalar(select(User).where(User.email == "e@kjsindia.com"))
        with pytest.raises(AppError) as e:
            await file_service._check(db, user, "board", "ABC1", "read")
        assert e.value.code == "module_off"


async def test_notification_links_to_hidden_areas_are_dropped(client, modules):
    await make_user("e@kjsindia.com")
    async with AsyncSessionLocal() as db:
        uid = await db.scalar(select(User.id).where(User.email == "e@kjsindia.com"))
        notification_service.notify(db, {uid}, "board.added", "You are on order board ABC1", "",
                                    "/employee/order-boards/ABC1")
        notification_service.notify(db, {uid}, "lead.new", "New lead", "", "/employee/contacts/1")
        await db.commit()
    modules(order_boards="off")
    await login(client, "e@kjsindia.com")
    items = (await client.get("/api/v1/employee/notifications")).json()["items"]
    links = {i["title"]: i["link"] for i in items}
    assert links == {"You are on order board ABC1": "", "New lead": "/employee/contacts/1"}


# ---------- Links and jobs ----------
def test_area_of_link():
    assert area_of_link("/employee/order-boards/ABC1") == "order_boards"
    assert area_of_link("/admin/order-boards") == "order_boards"
    assert area_of_link("/admin/holidays?year=2026") == "attendance"
    assert area_of_link("/employee/order-boardsX") is None  # whole page names only
    assert area_of_link("/employee/contacts/3") is None  # leads: always on
    assert link_for(User(role="employee"), "") == ""


def test_jobs_stop_only_when_off(modules):
    modules(order_boards="admin", batches="off")
    assert should_run("board_alerts", working=True)  # admin: admins can test it fully
    assert not should_run("auto_assign", working=True)
    assert should_run("sla_check", working=True)  # no area: always runs
    assert not should_run("sla_check", working=False)  # job hours still apply
    assert should_run("send_emails", working=False)  # any-time job


# ---------- Every route is either in an area or always on ----------
# Changing this list? Update the "Always on" line in config/modules.ini too.
ALWAYS_ON = (
    "/api/v1/auth/", "/api/v1/public/", "/api/v1/koko", "/api/v1/employee/", "/api/v1/tasks",
    "/api/v1/files",  # by the file's owner, in file_service._check
    "/api/v1/admin/stats", "/api/v1/admin/permissions", "/api/v1/admin/users", "/api/v1/admin/leads",
    "/api/v1/admin/sla", "/api/v1/admin/approvals", "/api/v1/admin/config",
)


def _area_of_route(route: APIRoute) -> str | None:
    todo = [route.dependant]
    while todo:
        d = todo.pop()
        if getattr(d.call, "module", None):
            return d.call.module
        todo.extend(d.dependencies)
    return None


def test_every_route_is_in_an_area_or_always_on():
    missing = [f"{sorted(r.methods)} {r.path}" for r in app.routes
               if isinstance(r, APIRoute) and r.path.startswith("/api/v1/")
               and _area_of_route(r) is None and not r.path.startswith(ALWAYS_ON)]
    assert not missing, f"Give these routes an area (dependencies=area(...)) or add them to ALWAYS_ON: {missing}"


def test_area_routes_are_not_in_always_on():
    both = [r.path for r in app.routes if isinstance(r, APIRoute) and _area_of_route(r) and r.path.startswith(ALWAYS_ON)]
    assert not both, both


# ---------- The repo's own config files ----------
REPO_CONFIG = Path(__file__).resolve().parents[2] / "config"


def test_repo_config_files_are_valid(monkeypatch):
    """A typo in config/*.ini must fail CI, never reach the live site: at start-up a broken file means the
    defaults, and for modules.ini that is every area switched on."""
    for key in [k for k in os.environ if k.startswith(ini.ENV_PREFIX)]:
        monkeypatch.delenv(key)  # only the files themselves
    monkeypatch.setattr(ini, "CONFIG_DIR", REPO_CONFIG)
    assert (REPO_CONFIG / "modules.ini").exists()
    ini._validate(ini._read_raw())  # raises with the file and key on a typo or a bad value


# ---------- Chat and Lead Harvester (added after Vineet's PRs #53 and #55) ----------
async def test_chat_and_harvester_routes_follow_their_areas(client, modules):
    await make_user("admin@kjsindia.com", role="admin")
    await login(client, "admin@kjsindia.com")
    assert (await client.get("/api/v1/chat/unread")).status_code == 200
    modules(chat="off", lead_harvester="off")
    assert (await client.get("/api/v1/chat/unread")).json()["code"] == "module_off"
    assert (await client.get("/api/v1/admin/harvest/sources")).json()["code"] == "module_off"
    assert not should_run("lead_harvester", working=True)


async def test_chat_live_connection_closes_when_chat_is_hidden(modules):
    """The WebSocket can't use the route switch (no Request): chat_socket checks the area itself."""
    await make_user("e@kjsindia.com")
    modules(chat="admin")  # an employee: hidden

    def scenario():
        with TestClient(app) as tc:
            r = tc.post("/api/v1/auth/login", json={"id_token": id_token("e@kjsindia.com")},
                        headers=HDR)
            assert r.status_code == 200, r.text
            with tc.websocket_connect("/api/v1/chat/ws", headers={"origin": "http://localhost:3000"}) as ws:
                with pytest.raises(WebSocketDisconnect) as e:
                    ws.receive_json()
                assert e.value.code == chat_hub.CLOSE_MODULE_OFF

    await asyncio.to_thread(scenario)
