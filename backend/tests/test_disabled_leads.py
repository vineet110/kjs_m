"""R98 (decided 18 Nov): switching an employee off sends their open leads back to unassigned."""
from datetime import datetime, timezone

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.audit import AuditLog
from app.models.lead import Lead, LeadNote
from app.models.user import User
from tests.conftest import HDR, login, make_user


def _lead(owner: int, status: str) -> Lead:
    return Lead(source="enquiry_form", name=f"Buyer {status}", phone="+91 98765 43210", consent=True,
                consent_at=datetime.now(timezone.utc), status=status, assigned_to=owner,
                outcome="Won" if status == "closed" else "")


async def test_disabling_an_employee_returns_their_open_leads(client):
    await make_user("admin@kjsindia.com", role="admin")
    await make_user("e@kjsindia.com", permissions=["leads.view"])
    async with AsyncSessionLocal() as db:
        e = await db.scalar(select(User.id).where(User.email == "e@kjsindia.com"))
        db.add_all([_lead(e, "new"), _lead(e, "contacted"), _lead(e, "closed")])
        await db.commit()
    await login(client, "admin@kjsindia.com")
    r = await client.post(f"/api/v1/admin/users/{e}/status", json={"status": "disabled"}, headers=HDR)
    assert r.status_code == 200
    async with AsyncSessionLocal() as db:
        owners = dict((await db.execute(select(Lead.status, Lead.assigned_to))).all())
        notes = (await db.scalars(select(LeadNote.text))).all()
        audit = (await db.scalars(select(AuditLog).where(AuditLog.action == "user.disabled"))).all()
    assert owners == {"new": None, "contacted": None, "closed": e}  # closed ones keep their owner
    assert len(notes) == 2 and all("switched off" in n for n in notes)
    assert len(audit) == 1 and audit[0].after["leads_unassigned"] == 2


async def test_turning_an_employee_back_on_leaves_leads_alone(client):
    await make_user("admin@kjsindia.com", role="admin")
    await make_user("e@kjsindia.com", permissions=["leads.view"])
    async with AsyncSessionLocal() as db:
        e = await db.scalar(select(User.id).where(User.email == "e@kjsindia.com"))
    await login(client, "admin@kjsindia.com")
    await client.post(f"/api/v1/admin/users/{e}/status", json={"status": "disabled"}, headers=HDR)
    async with AsyncSessionLocal() as db:
        db.add(_lead(None, "new"))
        await db.commit()
    assert (await client.post(f"/api/v1/admin/users/{e}/status", json={"status": "active"}, headers=HDR)).status_code == 200
    async with AsyncSessionLocal() as db:
        assert await db.scalar(select(Lead.assigned_to)) is None
        assert not (await db.scalars(select(LeadNote))).all()
