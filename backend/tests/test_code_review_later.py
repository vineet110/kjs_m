"""Smaller code-review points (docs/codeReview.md CR16, CR17, CR21). One test per point."""
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.task import Task
from tests.conftest import HDR, login, make_user
from tests.test_boards import _ids, board_body


async def test_board_tasks_have_no_creator_who_could_edit_colleagues_tasks(client):  # CR16
    await make_user("boss@kjsindia.com", permissions=["leads.view", "boards.manage"])
    await make_user("pack@kjsindia.com")
    pack, = await _ids("pack@kjsindia.com")
    await login(client, "boss@kjsindia.com")
    assert (await client.post("/api/v1/boards", json=board_body(pack, pack), headers=HDR)).status_code == 201
    async with AsyncSessionLocal() as db:
        creators = (await db.scalars(select(Task.created_by).where(Task.source == "board"))).all()
    assert creators and all(c is None for c in creators)


async def test_buyers_without_email_are_told_apart_by_phone(client):  # CR17.i
    await make_user("boss@kjsindia.com", permissions=["leads.view", "assign.manage"])
    await login(client, "boss@kjsindia.com")
    csv = ("Company,Phone,Category\n"
           "Metro Cash & Carry,+91 40 1111 1111,coffee\n"
           "Metro Cash & Carry,+91 80 2222 2222,coffee\n"
           "Metro Cash & Carry,+91 40 1111 1111,coffee\n")  # the same one again
    r = await client.post("/api/v1/assign/import", files={"file": ("b.csv", csv.encode(), "text/csv")}, headers=HDR)
    body = r.json()
    assert body["added"] == 2 and [s["reason"] for s in body["skipped"]] == ["already imported"]


async def test_a_product_name_with_no_english_letters_is_refused(client):  # CR21
    await make_user("cat@kjsindia.com", permissions=["leads.view", "catalog.edit"])
    await login(client, "cat@kjsindia.com")
    r = await client.post("/api/v1/admin/products", json={"category_slug": "coffee", "name": "चॉकलेट बार"}, headers=HDR)
    assert r.status_code == 422 and r.json()["code"] == "bad_name"


async def test_old_board_tasks_with_a_creator_still_cannot_be_edited_by_that_creator(client):  # CR16 (old rows)
    from app.services import task_service
    await make_user("boss@kjsindia.com", permissions=["leads.view", "boards.manage"])
    await make_user("pack@kjsindia.com")
    boss, pack = await _ids("boss@kjsindia.com", "pack@kjsindia.com")
    async with AsyncSessionLocal() as db:
        task_service.add(db, assignee_id=pack, title="ABC1 · Packing: check", source="board", created_by=boss)
        await db.commit()
        tid = await db.scalar(select(Task.id))
    await login(client, "boss@kjsindia.com")
    assert (await client.patch(f"/api/v1/tasks/{tid}", json={"status": "done"}, headers=HDR)).status_code == 404


async def test_same_phone_written_two_ways_and_a_later_email_is_still_one_buyer(client):  # CR17.i
    await make_user("boss@kjsindia.com", permissions=["leads.view", "assign.manage"])
    await login(client, "boss@kjsindia.com")
    first = "Company,Phone,Category\nAcme,+91 40 1111 1111,coffee\n"
    again = "Company,Email,Phone,Category\nAcme,,040-1111-1111,coffee\nAcme,a@acme.com,04011111111,coffee\n"
    await client.post("/api/v1/assign/import", files={"file": ("1.csv", first.encode(), "text/csv")}, headers=HDR)
    r = (await client.post("/api/v1/assign/import", files={"file": ("2.csv", again.encode(), "text/csv")}, headers=HDR)).json()
    assert r["added"] == 0 and len(r["skipped"]) == 2
