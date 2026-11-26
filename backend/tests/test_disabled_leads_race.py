"""R98 edge cases: a hand-over racing the switch-off never leaves an open lead on a disabled account."""
import asyncio

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.core.errors import AppError
from app.models.lead import Lead
from app.models.user import User
from app.services import auth_service, lead_service
from tests.conftest import make_user
from tests.test_disabled_leads import _lead


async def _ids():
    async with AsyncSessionLocal() as db:
        return {u.email: u.id for u in (await db.scalars(select(User))).all()}


async def _hand_over(manager_id: int, lead_id: int, to: int):
    async with AsyncSessionLocal() as db:
        try:
            await lead_service.assign(db, await db.get(User, manager_id), lead_id, to)
        except AppError:
            pass  # "Pick an active colleague": the switch-off came first


async def _switch_off(admin_id: int, user_id: int):
    async with AsyncSessionLocal() as db:
        await auth_service.set_status(db, await db.get(User, admin_id), user_id, "disabled")


async def test_a_hand_over_racing_the_switch_off(client):
    await make_user("admin@kjsindia.com", role="admin")
    await make_user("m@kjsindia.com", permissions=["leads.view", "leads.view_all"])
    for n in range(6):
        await make_user(f"e{n}@kjsindia.com", permissions=["leads.view"])
    ids = await _ids()
    async with AsyncSessionLocal() as db:
        leads = [_lead(None, "contacted") for _ in range(6)]
        db.add_all(leads)
        await db.commit()
        lead_ids = [x.id for x in leads]
    await asyncio.gather(*[
        coro for n, lead_id in enumerate(lead_ids)
        for coro in (_hand_over(ids["m@kjsindia.com"], lead_id, ids[f"e{n}@kjsindia.com"]),
                     _switch_off(ids["admin@kjsindia.com"], ids[f"e{n}@kjsindia.com"]))])
    async with AsyncSessionLocal() as db:
        stuck = (await db.execute(select(Lead.id, Lead.assigned_to).join(User, User.id == Lead.assigned_to)
                                  .where(User.status != "active", Lead.status != "closed"))).all()
    assert stuck == []


async def test_switching_off_someone_with_no_leads_or_twice(client):
    await make_user("admin@kjsindia.com", role="admin")
    await make_user("e@kjsindia.com", permissions=["leads.view"])
    ids = await _ids()
    await _switch_off(ids["admin@kjsindia.com"], ids["e@kjsindia.com"])
    try:
        await _switch_off(ids["admin@kjsindia.com"], ids["e@kjsindia.com"])  # again: refused or a no-op
    except AppError:
        pass
    async with AsyncSessionLocal() as db:
        assert (await db.get(User, ids["e@kjsindia.com"])).status == "disabled"
