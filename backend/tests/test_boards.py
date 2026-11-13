"""Order boards: step planning on working days, running steps, tasks from templates,
alerts at 50/85/100 %, access rules, board files."""
from datetime import date

import pytest
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.core.errors import AppError
from app.models.notification import Notification
from app.models.order_board import BoardStep
from app.models.user import User
from app.services import board_service as svc
from tests.conftest import HDR, login, make_user

MON, SAT = date(2026, 10, 26), date(2026, 10, 31)


def test_percent_plan_fills_exactly_to_deadline():
    # Mon 26 Oct – Sat 7 Nov = 12 working days (Sunday skipped)
    plan, late = svc.plan_steps(MON, date(2026, 11, 7), "percent", [25, 50, 25], set())
    assert plan == [(date(2026, 10, 26), date(2026, 10, 28)), (date(2026, 10, 29), date(2026, 11, 4)),
                    (date(2026, 11, 5), date(2026, 11, 7))]
    assert late is False


def test_percent_plan_skips_holidays_and_must_add_to_100():
    plan, _ = svc.plan_steps(MON, SAT, "percent", [50, 50], {date(2026, 10, 27)})  # 5 working days: 2 + 3
    assert plan == [(date(2026, 10, 26), date(2026, 10, 28)), (date(2026, 10, 29), date(2026, 10, 31))]
    with pytest.raises(AppError):
        svc.plan_steps(MON, SAT, "percent", [50, 40], set())


def test_days_plan_can_run_past_deadline():
    plan, late = svc.plan_steps(MON, SAT, "days", [4, 4], set())
    assert plan[1] == (date(2026, 10, 30), date(2026, 11, 3)) and late is True  # Sunday 1 Nov skipped


def test_used_pct():
    step = BoardStep(status="active", planned_start=MON, planned_end=date(2026, 10, 29))  # 4 working days
    assert svc.used_pct(step, date(2026, 10, 25), set()) == 0  # not started
    assert svc.used_pct(step, MON, set()) == 0  # first day: nothing used yet
    assert svc.used_pct(step, date(2026, 10, 27), set()) == 25  # Monday is over
    assert svc.used_pct(step, date(2026, 10, 29), set()) == 75  # last day is still available
    assert svc.used_pct(step, date(2026, 10, 30), set()) == 100  # day after the end: out of time
    assert svc.used_pct(step, date(2026, 10, 31), set()) > 100


def test_one_day_step_is_not_late_on_its_day():
    step = BoardStep(status="active", planned_start=MON, planned_end=MON)
    assert svc.used_pct(step, MON, set()) == 0
    assert svc.used_pct(step, date(2026, 10, 27), set()) == 100


async def _ids(*emails) -> list[int]:
    async with AsyncSessionLocal() as db:
        return [await db.scalar(select(User.id).where(User.email == e)) for e in emails]


def board_body(packer: int, blender: int, start="2026-10-26", deadline="2026-11-07") -> dict:
    return {
        "code": "abc117-3", "name": "3-in-1 sticks", "client": "Al Noor Trading", "start": start, "deadline": deadline,
        "steps": [
            {"name": "Blending", "percent": 50, "member_ids": [blender], "task_templates": ["Weigh raw materials", "QC sample"],
             "checklist": ["Batch record signed"]},
            {"name": "Packing", "percent": 50, "member_ids": [packer], "task_templates": ["Pack 100k sticks"]},
        ],
    }


async def test_board_flow(client):
    await make_user("boss@kjsindia.com", permissions=["leads.view", "boards.manage"])
    await make_user("blend@kjsindia.com")
    await make_user("pack@kjsindia.com")
    await make_user("other@kjsindia.com")
    boss, blend, pack = await _ids("boss@kjsindia.com", "blend@kjsindia.com", "pack@kjsindia.com")

    await login(client, "blend@kjsindia.com")
    assert (await client.post("/api/v1/boards", json=board_body(pack, blend), headers=HDR)).status_code == 403

    await login(client, "boss@kjsindia.com")
    r = await client.post("/api/v1/boards", json=board_body(pack, blend), headers=HDR)
    assert r.status_code == 201, r.text
    b = r.json()
    assert b["code"] == "ABC117-3" and b["steps"][0]["status"] == "active" and b["steps"][1]["status"] == "pending"
    assert (await client.post("/api/v1/boards", json=board_body(pack, blend), headers=HDR)).status_code == 409

    # Step 1 member got the template tasks; step 2 member got nothing yet
    await login(client, "blend@kjsindia.com")
    titles = [t["title"] for t in (await client.get("/api/v1/tasks")).json()]
    assert sorted(titles) == ["ABC117-3 · Blending: QC sample", "ABC117-3 · Blending: Weigh raw materials"]
    board = (await client.get("/api/v1/boards/ABC117-3")).json()
    step1, step2 = board["steps"]
    assert board["my_step_ids"] == [step1["id"]]
    # can tick own checklist, can't finish someone else's step
    r = await client.post(f"/api/v1/boards/ABC117-3/steps/{step1['id']}/checklist", json={"index": 0, "done": True}, headers=HDR)
    assert r.json()["steps"][0]["checklist"][0]["done"] is True
    assert (await client.post(f"/api/v1/boards/ABC117-3/steps/{step2['id']}/done", headers=HDR)).status_code == 403
    r = await client.post(f"/api/v1/boards/ABC117-3/steps/{step1['id']}/done", headers=HDR)
    assert [s["status"] for s in r.json()["steps"]] == ["done", "active"]

    await login(client, "pack@kjsindia.com")
    assert [t["source"] for t in (await client.get("/api/v1/tasks")).json()] == ["board"]
    assert [x["code"] for x in (await client.get("/api/v1/boards")).json()] == ["ABC117-3"]

    await login(client, "other@kjsindia.com")
    assert (await client.get("/api/v1/boards")).json() == []
    assert (await client.get("/api/v1/boards/ABC117-3")).status_code == 404

    await login(client, "boss@kjsindia.com")
    r = await client.post("/api/v1/boards/ABC117-3/finish", json={"final_status": "Delivered"}, headers=HDR)
    assert r.json()["status"] == "finished" and r.json()["state"] == "finished"


async def test_board_files_follow_membership(client):
    await make_user("boss@kjsindia.com", permissions=["leads.view", "boards.manage"])
    await make_user("pack@kjsindia.com")
    await make_user("other@kjsindia.com")
    boss, pack = await _ids("boss@kjsindia.com", "pack@kjsindia.com")
    await login(client, "boss@kjsindia.com")
    await client.post("/api/v1/boards", json=board_body(pack, pack), headers=HDR)
    await login(client, "pack@kjsindia.com")
    up = await client.post("/api/v1/files", data={"owner_type": "board", "owner_id": "ABC117-3"},
                           files={"file": ("po.pdf", b"%PDF-1.4 %%EOF", "application/pdf")}, headers=HDR)
    assert up.status_code == 201
    await login(client, "other@kjsindia.com")
    assert (await client.get("/api/v1/files?owner_type=board&owner_id=ABC117-3")).status_code == 403


async def test_alerts_once_per_threshold(client):
    await make_user("boss@kjsindia.com", permissions=["leads.view", "boards.manage"])
    await make_user("pack@kjsindia.com")
    _, pack = await _ids("boss@kjsindia.com", "pack@kjsindia.com")
    await login(client, "boss@kjsindia.com")
    body = board_body(pack, pack, start="2026-10-26", deadline="2026-11-02")  # step 1 = Mon–Wed (3 days)
    assert (await client.post("/api/v1/boards", json=body, headers=HDR)).status_code == 201
    async with AsyncSessionLocal() as db:
        results = []
        for day in (date(2026, 10, 26), date(2026, 10, 27), date(2026, 10, 27), date(2026, 10, 28), date(2026, 10, 30)):
            results.append((await svc.board_alerts(db, today=day))["alerts"])
            await db.commit()
        alerts = (await db.scalars(select(Notification.title).where(Notification.kind == "board.alert"))).all()
    # Mon 0%, Tue 33% none, Tue again none, Wed 67% -> 50 alert, Fri past the end -> 100 alert (85 skipped)
    assert results == [0, 0, 0, 1, 1]
    assert any("out of time" in a for a in alerts)


async def test_bad_code_rejected(client):
    await make_user("boss@kjsindia.com", permissions=["leads.view", "boards.manage"])
    await login(client, "boss@kjsindia.com")
    body = board_body(1, 1) | {"code": "no spaces allowed"}
    assert (await client.post("/api/v1/boards", json=body, headers=HDR)).status_code == 422


async def test_board_files_can_never_be_public(client):
    # Any board member could otherwise publish an order document to the internet
    await make_user("boss@kjsindia.com", permissions=["leads.view", "boards.manage"])
    await make_user("blend@kjsindia.com")
    await make_user("pack@kjsindia.com")
    blend, pack = await _ids("blend@kjsindia.com", "pack@kjsindia.com")
    await login(client, "boss@kjsindia.com")
    assert (await client.post("/api/v1/boards", json=board_body(pack, blend), headers=HDR)).status_code == 201
    await login(client, "blend@kjsindia.com")
    form = {"owner_type": "board", "owner_id": "ABC117-3"}
    pdf = {"file": ("order.pdf", b"%PDF-1.4 order %%EOF", "application/pdf")}
    r = await client.post("/api/v1/files", data=form | {"is_public": "true"}, files=pdf, headers=HDR)
    assert r.status_code == 422 and r.json()["code"] == "not_public"
    fid = (await client.post("/api/v1/files", data=form, files=pdf, headers=HDR)).json()["id"]
    client.cookies.clear()
    assert (await client.get(f"/api/v1/public/files/{fid}")).status_code == 404
