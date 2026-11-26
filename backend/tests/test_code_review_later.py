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
