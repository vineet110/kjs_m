"""Order boards, editing the plan (PR 4): dates, sizes, add / rename / remove / reorder steps, saved
together; anyone on the board while unlocked, only the owner (or boards.manage) when locked; only steps
that haven't started can be removed or moved; nothing lost (history keeps removed steps)."""
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.audit import AuditLog
from app.models.notification import Notification
from app.models.order_board import BoardStep
from app.models.task import Task
from tests.conftest import HDR, login
from tests.test_board_people import B, _create_as_plain_owner, _team

START, DEADLINE = "2026-10-26", "2026-11-07"


def plan(steps: list[dict], start=START, deadline=DEADLINE, mode="percent") -> dict:
    return {"start": start, "deadline": deadline, "split_mode": mode, "steps": steps}


def keep(step: dict, **change) -> dict:
    return {"id": step["id"], "name": step["name"], "size": step["percent"] or step["days"]} | change


async def _board(client, ids):
    b = await _create_as_plain_owner(client, ids)  # Blending 50% (running, blend), Packing 50% (pack)
    return b["steps"][0], b["steps"][1]


async def test_lock_decides_who_may_change_the_plan(client):
    ids = await _team()
    blending, packing = await _board(client, ids)
    longer = plan([keep(blending), keep(packing)], deadline="2026-11-14")

    await login(client, "blend@kjsindia.com")  # on the board, not the owner
    assert (await client.post(f"{B}/plan-lock", json={"locked": True}, headers=HDR)).status_code == 403
    r = await client.put(f"{B}/plan", json=longer, headers=HDR)  # unlocked: allowed
    assert r.status_code == 200, r.text
    assert r.json()["deadline"] == "2026-11-14" and r.json()["can_edit_plan"] is True

    await login(client, "owner@kjsindia.com")
    r = await client.post(f"{B}/plan-lock", json={"locked": True}, headers=HDR)
    assert r.status_code == 200 and r.json()["plan_locked"] is True

    await login(client, "blend@kjsindia.com")
    assert (await client.get(B)).json()["can_edit_plan"] is False
    r = await client.put(f"{B}/plan", json=plan([keep(blending), keep(packing)]), headers=HDR)
    assert r.status_code == 403 and r.json()["code"] == "plan_locked"

    await login(client, "owner@kjsindia.com")  # the owner always can
    assert (await client.put(f"{B}/plan", json=plan([keep(blending), keep(packing)]), headers=HDR)).status_code == 200
    await client.post(f"{B}/plan-lock", json={"locked": False}, headers=HDR)

    await login(client, "stranger@kjsindia.com")
    assert (await client.put(f"{B}/plan", json=longer, headers=HDR)).status_code == 404
    async with AsyncSessionLocal() as db:
        actions = (await db.scalars(select(AuditLog.action).where(AuditLog.action.like("board.plan%"))
                                    .order_by(AuditLog.id))).all()
    assert actions == ["board.plan_changed", "board.plan_locked", "board.plan_changed", "board.plan_unlocked"]


async def test_add_rename_reorder_and_resize_in_one_save(client):
    ids = await _team()
    blending, packing = await _board(client, ids)
    await login(client, "pack@kjsindia.com")
    body = plan([
        keep(blending, name="Blending + QC", size=40),
        {"name": "Labelling", "size": 20, "member_ids": [ids["extra"]], "head_ids": [ids["extra"]],
         "checklist": ["Arabic labels"], "task_templates": ["Print labels"]},
        keep(packing, size=40),
    ], deadline="2026-11-14")
    # Bringing someone new onto the board is the owner's call, also through a new step
    r = await client.put(f"{B}/plan", json=body, headers=HDR)
    assert r.status_code == 403 and r.json()["code"] == "owner_adds_people"
    await login(client, "owner@kjsindia.com")
    r = await client.put(f"{B}/plan", json=body, headers=HDR)
    assert r.status_code == 200, r.text
    steps = r.json()["steps"]
    assert [(s["position"], s["name"], s["percent"], s["status"]) for s in steps] == [
        (1, "Blending + QC", 40, "active"), (2, "Labelling", 20, "pending"), (3, "Packing", 40, "pending")]
    assert steps[1]["members"] == [{"id": ids["extra"], "name": "extra", "is_head": True}]
    assert steps[2]["planned_end"] == "2026-11-14"  # the plan fills to the new deadline
    assert ids["extra"] in [p["id"] for p in r.json()["people"]]  # put on the board

    lines = (await client.get(f"{B}/history")).json()["items"]
    assert lines[1]["action"] == "board.person_added"  # the same record as adding them by hand
    history = lines[0]
    assert history["who"] == "owner" and history["text"] == (
        "changed the plan: deadline 07 Nov → 14 Nov; renamed 'Blending' to 'Blending + QC'; "
        "'Blending + QC' 50% → 40%; added step 'Labelling' (extra); 'Packing' 50% → 40%")
    async with AsyncSessionLocal() as db:  # everyone else on the board is told
        told = set((await db.scalars(select(Notification.user_id).where(Notification.kind == "board.plan_changed"))).all())
        added = set((await db.scalars(select(Notification.user_id).where(Notification.kind == "board.added"))).all())
    assert told == {ids["blend"], ids["pack"]} and ids["extra"] in added  # the newcomer: "You are on order board"


async def test_only_steps_that_have_not_started_can_be_removed_or_moved(client):
    ids = await _team()
    blending, packing = await _board(client, ids)
    await login(client, "blend@kjsindia.com")
    # the running step can't be removed, or moved after one that hasn't started
    r = await client.put(f"{B}/plan", json=plan([keep(packing, size=100)]), headers=HDR)
    assert r.status_code == 422 and r.json()["code"] == "started_steps"
    r = await client.put(f"{B}/plan", json=plan([keep(packing), keep(blending)]), headers=HDR)
    assert r.status_code == 422 and r.json()["code"] == "started_steps"

    r = await client.put(f"{B}/plan", json=plan([keep(blending, size=100)]), headers=HDR)  # remove Packing
    assert r.status_code == 200, r.text
    assert [s["name"] for s in r.json()["steps"]] == ["Blending"]
    async with AsyncSessionLocal() as db:
        assert await db.get(BoardStep, packing["id"]) is None
        gone = await db.scalar(select(AuditLog).where(AuditLog.action == "board.step_removed"))
    assert gone.before["name"] == "Packing" and gone.before["checklist"] == [{"text": "Labels checked", "done": False}]
    assert gone.before["people"] == [ids["pack"]]
    texts = [i["text"] for i in (await client.get(f"{B}/history")).json()["items"][:2]]
    assert texts == ["changed the plan: 'Blending' 50% → 100%; removed step 'Packing'",
                     'removed step 2 "Packing" (it hadn\'t started)']


async def test_running_step_tasks_follow_its_new_end(client):
    ids = await _team()
    blending, packing = await _board(client, ids)
    await login(client, "owner@kjsindia.com")
    r = await client.put(f"{B}/plan", json=plan([keep(blending), keep(packing)], deadline="2026-11-21"), headers=HDR)
    new_end = r.json()["steps"][0]["planned_end"]
    assert new_end > blending["planned_end"]
    async with AsyncSessionLocal() as db:
        dues = {t.due_at.date().isoformat() for t in (await db.scalars(select(Task).where(Task.status != "done"))).all()}
    assert dues == {new_end}


async def test_a_step_added_after_the_last_one_starts_at_once(client):
    ids = await _team()
    blending, packing = await _board(client, ids)
    await login(client, "owner@kjsindia.com")
    await client.post(f"{B}/steps/{blending['id']}/done", headers=HDR)
    r = await client.post(f"{B}/steps/{packing['id']}/done", headers=HDR)
    assert [s["status"] for s in r.json()["steps"]] == ["done", "done"]
    r = await client.put(f"{B}/plan", json=plan([keep(blending, size=40), keep(packing, size=40),
                                                 {"name": "Re-pack", "size": 20, "member_ids": [ids["extra"]],
                                                  "task_templates": ["Re-pack damaged cases"]}]), headers=HDR)
    assert [s["status"] for s in r.json()["steps"]] == ["done", "done", "active"]
    async with AsyncSessionLocal() as db:
        titles = (await db.scalars(select(Task.title).where(Task.assignee_id == ids["extra"]))).all()
    assert titles == ["ABC117-3 · Re-pack: Re-pack damaged cases"]


async def test_bad_plans_are_refused_and_change_nothing(client):
    ids = await _team()
    blending, packing = await _board(client, ids)
    await login(client, "owner@kjsindia.com")
    bad = [
        plan([keep(blending), keep(packing, size=40)]),  # adds up to 90%
        plan([keep(blending), {"name": "Nobody", "size": 50}]),  # new step without people
        plan([keep(blending), keep(packing), keep(packing)]),  # the same step twice
        plan([keep(blending), {"id": 999999, "name": "Not here", "size": 50}]),  # another board's step
        plan([keep(blending), keep(packing)], deadline="2026-10-01"),  # deadline before start
    ]
    for body in bad:
        assert (await client.put(f"{B}/plan", json=body, headers=HDR)).status_code == 422, body
    after = (await client.get(B)).json()
    assert [(s["name"], s["percent"]) for s in after["steps"]] == [("Blending", 50), ("Packing", 50)]
    assert after["deadline"] == DEADLINE

    await client.post(f"{B}/finish", json={"final_status": "Cancelled"}, headers=HDR)
    assert (await client.put(f"{B}/plan", json=plan([keep(blending), keep(packing)]), headers=HDR)).status_code == 409


async def test_plan_preview_for_logged_in_staff_only(client):
    await _team()
    body = {"start": START, "deadline": DEADLINE, "split_mode": "percent", "sizes": [50, 50]}
    assert (await client.post("/api/v1/boards/preview", json=body, headers=HDR)).status_code == 401
    await login(client, "blend@kjsindia.com")  # no boards.manage: may still preview (edits unlocked plans)
    r = await client.post("/api/v1/boards/preview", json=body, headers=HDR)
    assert r.status_code == 200 and len(r.json()["steps"]) == 2


async def test_a_stale_editor_cannot_undo_a_newer_change_and_an_empty_save_writes_nothing(client):
    ids = await _team()
    blending, packing = await _board(client, ids)
    await login(client, "blend@kjsindia.com")
    opened = (await client.get(B)).json()["plan_version"]
    r = await client.put(f"{B}/plan", json=plan([keep(blending), keep(packing)]) | {"version": opened}, headers=HDR)
    assert r.status_code == 200 and r.json()["plan_version"] == opened  # nothing changed
    async with AsyncSessionLocal() as db:
        assert await db.scalar(select(AuditLog).where(AuditLog.action == "board.plan_changed")) is None

    await login(client, "pack@kjsindia.com")  # someone else saves first
    assert (await client.put(f"{B}/plan", json=plan([keep(blending), keep(packing, name="Packing 2")]),
                             headers=HDR)).status_code == 200
    await login(client, "blend@kjsindia.com")  # the older draft is refused, not saved over it
    r = await client.put(f"{B}/plan", json=plan([keep(blending)], deadline="2026-11-14") | {"version": opened}, headers=HDR)
    assert r.status_code == 409 and r.json()["code"] == "plan_changed"
