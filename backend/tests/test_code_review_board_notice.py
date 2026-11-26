"""CR24.ii: a new board's step-1 people get one message ("step started"), not two."""
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.notification import Notification
from tests.conftest import HDR, login, make_user
from tests.test_boards import _ids, board_body


async def test_step_one_people_are_told_once(client):
    await make_user("boss@kjsindia.com", permissions=["leads.view", "boards.manage"])
    await make_user("pack@kjsindia.com")
    await make_user("blend@kjsindia.com")
    pack, blend = await _ids("pack@kjsindia.com", "blend@kjsindia.com")
    await login(client, "boss@kjsindia.com")
    body = board_body(pack, blend)
    assert (await client.post("/api/v1/boards", json=body, headers=HDR)).status_code == 201
    first = set(body["steps"][0]["member_ids"])
    async with AsyncSessionLocal() as db:
        added = set((await db.scalars(select(Notification.user_id).where(Notification.kind == "board.added"))).all())
        started = set((await db.scalars(select(Notification.user_id).where(Notification.kind == "board.step_started"))).all())
    assert first <= started and not (first & added)
    assert ({pack, blend} - first) <= added  # people only on later steps are still told they are on the board
