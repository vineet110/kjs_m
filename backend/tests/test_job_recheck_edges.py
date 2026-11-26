"""CR15 edge cases: a lead changed after the job's first read is judged on its fresh row."""
from datetime import datetime, timezone

from sqlalchemy import select, update

from app.core.database import AsyncSessionLocal
from app.models.lead import Lead
from app.models.notification import Notification
from app.services import lead_service, notification_service
from tests.conftest import make_user
from tests.test_leads_sla import _new_lead, ist, sla_20_60_10  # noqa: F401 (fixture)


def _change_after_first_read(monkeypatch, lead_id: int, **values):
    """users_with runs after the job read the open leads and before it alerts: change the lead there,
    in another committed transaction, like a colleague saving it at that moment."""
    real = notification_service.users_with

    async def users_with(db, permission):
        async with AsyncSessionLocal() as other:
            await other.execute(update(Lead).where(Lead.id == lead_id).values(**values))
            await other.commit()
        return await real(db, permission)
    monkeypatch.setattr(notification_service, "users_with", users_with)


async def test_a_lead_closed_after_the_first_read_is_not_alerted(client, sla_20_60_10, monkeypatch):
    await make_user("admin@kjsindia.com", role="admin")
    lead_id = await _new_lead(client, ist("2026-10-26", "10:00"))
    now = datetime.now(timezone.utc)
    _change_after_first_read(monkeypatch, lead_id, status="closed", responded_at=now, resolved_at=now)
    async with AsyncSessionLocal() as db:
        result = await lead_service.sla_check(db, now=ist("2026-10-26", "10:45"))
        await db.commit()
    assert result["escalated"] == 0
    async with AsyncSessionLocal() as db:
        assert not (await db.scalars(select(Notification).where(Notification.kind == "lead.sla_breach"))).all()
        assert (await db.get(Lead, lead_id)).status == "closed"  # the job never wrote back its stale copy


async def test_a_lead_answered_after_the_first_read_is_judged_on_the_resolve_timer(client, sla_20_60_10, monkeypatch):
    await make_user("admin@kjsindia.com", role="admin")
    lead_id = await _new_lead(client, ist("2026-10-26", "10:00"))
    _change_after_first_read(monkeypatch, lead_id, status="contacted", responded_at=ist("2026-10-26", "10:40"))
    async with AsyncSessionLocal() as db:
        result = await lead_service.sla_check(db, now=ist("2026-10-26", "10:45"))  # resolve not late yet
        await db.commit()
    assert result["escalated"] == 0
    async with AsyncSessionLocal() as db:
        lead = await db.get(Lead, lead_id)
        assert (lead.status, lead.escalation_level) == ("contacted", 0)
