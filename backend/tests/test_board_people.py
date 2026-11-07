"""Order boards, people (migration 0016): the owner adds and removes people and changes who works on a
step; everyone on the board updates it; only a step's people (or the owner) mark it done; the owner
approves file deletes; every step keeps at least one person; nothing is lost on removal; all audited."""
from sqlalchemy import select, text

from app.core.database import AsyncSessionLocal
from app.models.audit import AuditLog
from app.models.task import Task
from app.models.user import User
from tests.conftest import HDR, login, make_user

B = "/api/v1/boards/ABC117-3"


async def _id(email: str) -> int:
    async with AsyncSessionLocal() as db:
        return await db.scalar(select(User.id).where(User.email == email))


async def _team() -> dict[str, int]:
    """owner (creates the board, then loses boards.manage: what's left are the owner's own rights),
    blend and pack (one step each), extra (not on the board yet), stranger (never on it)."""
    await make_user("owner@kjsindia.com", permissions=["leads.view", "boards.manage"])
    for e in ("blend", "pack", "extra", "stranger"):
        await make_user(f"{e}@kjsindia.com")
    return {e: await _id(f"{e}@kjsindia.com") for e in ("owner", "blend", "pack", "extra", "stranger")}


def _body(ids: dict[str, int], **step1) -> dict:
    return {"code": "abc117-3", "name": "3-in-1 sticks", "client": "Al Noor", "start": "2026-10-26",
            "deadline": "2026-11-07", "steps": [
                {"name": "Blending", "percent": 50, "member_ids": [ids["blend"]], "head_ids": [ids["blend"]],
                 "task_templates": ["Weigh raw materials"], "checklist": ["Batch record signed"]} | step1,
                {"name": "Packing", "percent": 50, "member_ids": [ids["pack"]], "task_templates": ["Pack sticks"],
                 "checklist": ["Labels checked"]}]}


async def _create_as_plain_owner(client, ids) -> dict:
    await login(client, "owner@kjsindia.com")
    r = await client.post("/api/v1/boards", json=_body(ids), headers=HDR)
    assert r.status_code == 201, r.text
    async with AsyncSessionLocal() as db:  # from here on the owner has only the owner's rights
        u = await db.get(User, ids["owner"])
        u.permissions = ["leads.view"]
        await db.commit()
    return r.json()


async def _actions(action: str) -> list[AuditLog]:
    async with AsyncSessionLocal() as db:
        return list((await db.scalars(select(AuditLog).where(AuditLog.action == action))).all())


async def test_create_needs_a_person_on_every_step_and_heads_among_them(client):
    ids = await _team()
    await login(client, "owner@kjsindia.com")
    assert (await client.post("/api/v1/boards", json=_body(ids, member_ids=[], head_ids=[]), headers=HDR)).status_code == 422
    r = await client.post("/api/v1/boards", json=_body(ids, head_ids=[ids["pack"]]), headers=HDR)
    assert r.status_code == 422 and r.json()["code"] == "bad_head"
    r = await client.post("/api/v1/boards", json=_body(ids), headers=HDR)
    assert r.status_code == 201
    b = r.json()
    assert b["owner"]["id"] == ids["owner"] and b["can_edit"] is True
    assert [p["id"] for p in b["people"]][0] == ids["owner"]  # owner first
    assert {p["id"] for p in b["people"]} == {ids["owner"], ids["blend"], ids["pack"]}
    assert b["steps"][0]["members"] == [{"id": ids["blend"], "name": "blend", "is_head": True}]


async def test_owner_adds_people_and_everyone_on_the_board_can_update_it(client):
    ids = await _team()
    await _create_as_plain_owner(client, ids)

    # Only the owner (or boards.manage) adds people
    await login(client, "blend@kjsindia.com")
    assert (await client.post(f"{B}/people", json={"user_id": ids["extra"]}, headers=HDR)).status_code == 403
    await login(client, "stranger@kjsindia.com")
    assert (await client.get(B)).status_code == 404
    assert (await client.post(f"{B}/people", json={"user_id": ids["stranger"]}, headers=HDR)).status_code == 404

    await login(client, "owner@kjsindia.com")
    r = await client.post(f"{B}/people", json={"user_id": ids["extra"]}, headers=HDR)
    assert r.status_code == 200, r.text
    assert ids["extra"] in [p["id"] for p in r.json()["people"]]
    assert (await client.post(f"{B}/people", json={"user_id": ids["extra"]}, headers=HDR)).status_code == 409
    assert len(await _actions("board.person_added")) == 1

    # Extra (on no step) sees the board, ticks any step's checklist, uploads a file...
    await login(client, "extra@kjsindia.com")
    assert [x["code"] for x in (await client.get("/api/v1/boards")).json()] == ["ABC117-3"]
    b = (await client.get(B)).json()
    assert b["can_edit"] is False and b["can_decide_deletes"] is False
    step1, step2 = b["steps"]
    r = await client.post(f"{B}/steps/{step2['id']}/checklist", json={"index": 0, "done": True}, headers=HDR)
    assert r.status_code == 200 and r.json()["steps"][1]["checklist"][0]["done"] is True
    up = await client.post("/api/v1/files", data={"owner_type": "board", "owner_id": "ABC117-3"},
                           files={"file": ("po.pdf", b"%PDF", "application/pdf")}, headers=HDR)
    assert up.status_code == 201
    # ...but only the step's people (or the owner) mark it done
    assert (await client.post(f"{B}/steps/{step1['id']}/done", headers=HDR)).status_code == 403
    await login(client, "blend@kjsindia.com")
    assert (await client.post(f"{B}/steps/{step1['id']}/done", headers=HDR)).status_code == 200
    await login(client, "owner@kjsindia.com")
    r = await client.post(f"{B}/steps/{step2['id']}/done", headers=HDR)
    assert [s["status"] for s in r.json()["steps"]] == ["done", "done"]


async def test_step_people_and_heads_can_change_and_tasks_follow(client):
    ids = await _team()
    b = await _create_as_plain_owner(client, ids)
    step1 = b["steps"][0]["id"]
    url = f"{B}/steps/{step1}/people"

    await login(client, "blend@kjsindia.com")  # on the step, not the owner
    assert (await client.put(url, json={"member_ids": [ids["extra"]]}, headers=HDR)).status_code == 403

    await login(client, "owner@kjsindia.com")
    assert (await client.put(url, json={"member_ids": []}, headers=HDR)).status_code == 422
    assert (await client.put(url, json={"member_ids": [ids["extra"]], "head_ids": [ids["blend"]]},
                             headers=HDR)).status_code == 422
    r = await client.put(url, json={"member_ids": [ids["extra"]], "head_ids": [ids["extra"]]}, headers=HDR)
    assert r.status_code == 200, r.text
    assert r.json()["steps"][0]["members"] == [{"id": ids["extra"], "name": "extra", "is_head": True}]
    assert ids["extra"] in [p["id"] for p in r.json()["people"]]  # put on the board too

    async with AsyncSessionLocal() as db:
        tasks = {(t.assignee_id, t.status) for t in (await db.scalars(select(Task))).all()}
    assert (ids["extra"], "todo") in tasks  # the running step's tasks went to the new person
    assert (ids["blend"], "done") in tasks and (ids["blend"], "todo") not in tasks  # and were closed for blend

    # blend is still on the board (taken off the step only): can still see it, can't mark step 1 done now
    await login(client, "blend@kjsindia.com")
    assert (await client.get(B)).status_code == 200
    assert (await client.post(f"{B}/steps/{step1}/done", headers=HDR)).status_code == 403

    audit = await _actions("board.step_people_changed")
    assert len(audit) == 1 and audit[0].before["people"] == [ids["blend"]] and audit[0].after["heads"] == [ids["extra"]]


async def test_remove_person_keeps_every_step_staffed_and_loses_nothing(client):
    ids = await _team()
    await _create_as_plain_owner(client, ids)

    # blend uploads a file first
    await login(client, "blend@kjsindia.com")
    up = await client.post("/api/v1/files", data={"owner_type": "board", "owner_id": "ABC117-3"},
                           files={"file": ("batch.pdf", b"%PDF", "application/pdf")}, headers=HDR)
    assert up.status_code == 201

    await login(client, "owner@kjsindia.com")
    assert (await client.delete(f"{B}/people/{ids['owner']}", headers=HDR)).status_code == 409  # never the owner
    assert (await client.delete(f"{B}/people/{ids['stranger']}", headers=HDR)).status_code == 404
    r = await client.delete(f"{B}/people/{ids['blend']}", headers=HDR)  # the only person on Blending
    assert r.status_code == 409 and r.json()["code"] == "last_assignee"

    step1 = (await client.get(B)).json()["steps"][0]["id"]
    await client.put(f"{B}/steps/{step1}/people", json={"member_ids": [ids["blend"], ids["extra"]]}, headers=HDR)
    r = await client.delete(f"{B}/people/{ids['blend']}", headers=HDR)
    assert r.status_code == 200, r.text
    assert ids["blend"] not in [p["id"] for p in r.json()["people"]]
    assert r.json()["steps"][0]["members"] == [{"id": ids["extra"], "name": "extra", "is_head": False}]

    # Their access ends; their file and the history stay; their open tasks are closed, not deleted
    files = (await client.get("/api/v1/files?owner_type=board&owner_id=ABC117-3")).json()
    assert [f["name"] for f in files] == ["batch.pdf"]
    async with AsyncSessionLocal() as db:
        theirs = (await db.scalars(select(Task).where(Task.assignee_id == ids["blend"]))).all()
    assert theirs and all(t.status == "done" and "removed from the board" in t.notes for t in theirs)
    removed = await _actions("board.person_removed")
    assert len(removed) == 1 and removed[0].before["steps"] == [1]
    await login(client, "blend@kjsindia.com")
    assert (await client.get(B)).status_code == 404
    assert (await client.get("/api/v1/boards")).json() == []


async def test_owner_approves_file_deletes_and_others_cannot(client):
    ids = await _team()
    await _create_as_plain_owner(client, ids)
    await login(client, "pack@kjsindia.com")
    fid = (await client.post("/api/v1/files", data={"owner_type": "board", "owner_id": "ABC117-3"},
                             files={"file": ("old.pdf", b"%PDF", "application/pdf")}, headers=HDR)).json()["id"]
    r = await client.post(f"/api/v1/files/{fid}/delete-request", json={"reason": "wrong version"}, headers=HDR)
    assert r.status_code == 200

    async with AsyncSessionLocal() as db:  # the owner was told, with a link to the board
        note = await db.scalar(text("SELECT link FROM notifications WHERE user_id = :u AND kind = 'file.delete_request'"),
                               {"u": ids["owner"]})
    assert note == "/employee/order-boards/ABC117-3"

    for who in ("pack", "blend"):  # the requester, and another person on the board
        await login(client, f"{who}@kjsindia.com")
        assert (await client.post(f"/api/v1/files/{fid}/delete-decision", json={"approve": True}, headers=HDR)).status_code == 403

    await login(client, "owner@kjsindia.com")
    assert (await client.get(B)).json()["can_decide_deletes"] is True
    r = await client.post(f"/api/v1/files/{fid}/delete-decision", json={"approve": True}, headers=HDR)
    assert r.status_code == 200 and r.json()["delete_status"] == "approved"
    assert len(await _actions("file.delete_approved")) == 1


async def test_owner_cannot_approve_their_own_delete_request(client):
    ids = await _team()
    await _create_as_plain_owner(client, ids)
    await login(client, "owner@kjsindia.com")
    fid = (await client.post("/api/v1/files", data={"owner_type": "board", "owner_id": "ABC117-3"},
                             files={"file": ("x.pdf", b"%PDF", "application/pdf")}, headers=HDR)).json()["id"]
    await client.post(f"/api/v1/files/{fid}/delete-request", json={"reason": "duplicate"}, headers=HDR)
    r = await client.post(f"/api/v1/files/{fid}/delete-decision", json={"approve": True}, headers=HDR)
    assert r.status_code == 403 and r.json()["code"] == "own_request"


async def test_finished_board_people_are_frozen_and_owner_can_finish(client):
    ids = await _team()
    await _create_as_plain_owner(client, ids)
    await login(client, "blend@kjsindia.com")
    assert (await client.post(f"{B}/finish", json={"final_status": "Delivered"}, headers=HDR)).status_code == 403
    await login(client, "owner@kjsindia.com")
    r = await client.post(f"{B}/finish", json={"final_status": "Delivered"}, headers=HDR)
    assert r.status_code == 200 and r.json()["status"] == "finished"
    assert (await client.post(f"{B}/people", json={"user_id": ids["extra"]}, headers=HDR)).status_code == 409
    assert (await client.delete(f"{B}/people/{ids['pack']}", headers=HDR)).status_code == 409


async def test_boards_manage_can_do_what_the_owner_can(client):
    ids = await _team()
    await _create_as_plain_owner(client, ids)
    await make_user("manager@kjsindia.com", permissions=["leads.view", "boards.manage"])
    await login(client, "manager@kjsindia.com")
    r = await client.post(f"{B}/people", json={"user_id": ids["extra"]}, headers=HDR)
    assert r.status_code == 200 and r.json()["can_edit"] is True
