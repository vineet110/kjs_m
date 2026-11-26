"""Edge cases for CR12 (a reopened lead's resolve timer) and CR19 (long file owner ids)."""
from tests.conftest import HDR, login, make_user
from tests.test_leads_sla import _new_lead, ist, sla_20_60_10  # noqa: F401 (fixture)

from app.core.database import AsyncSessionLocal
from app.models.lead import Lead
from app.services import lead_service


async def _setup(client):
    await make_user("admin@kjsindia.com", role="admin")
    await make_user("e@kjsindia.com", permissions=["leads.view"])
    lead_id = await _new_lead(client, ist("2026-10-26", "10:00"))
    await login(client, "e@kjsindia.com")
    return lead_id, (lambda body: client.patch(f"/api/v1/employee/leads/{lead_id}", json=body, headers=HDR))


async def test_a_closed_lead_cannot_go_back_to_new(client, sla_20_60_10):
    lead_id, to = await _setup(client)
    assert (await to({"status": "closed", "outcome": "quote_sent"})).status_code == 204
    assert (await to({"status": "new"})).status_code == 409  # it was answered when it was closed


async def test_answering_a_new_lead_is_not_a_reopen(client, sla_20_60_10):
    lead_id, to = await _setup(client)
    assert (await to({"status": "contacted"})).status_code == 204
    async with AsyncSessionLocal() as db:
        assert (await db.get(Lead, lead_id)).reopened_at is None


async def test_a_second_reopen_starts_the_timer_again(client, sla_20_60_10):
    lead_id, to = await _setup(client)
    for _ in range(2):
        assert (await to({"status": "closed", "outcome": "quote_sent"})).status_code == 204
        async with AsyncSessionLocal() as db:
            first = (await db.get(Lead, lead_id)).reopened_at
        assert (await to({"status": "contacted"})).status_code == 204
    async with AsyncSessionLocal() as db:
        lead = await db.get(Lead, lead_id)
        assert first is None or lead.reopened_at > first
        t = lead_service.sla(lead, lead.reopened_at, set())
        assert t["resolve_due_at"] > lead.reopened_at  # counted from the newest reopen, not from 26 Oct


async def test_closing_after_a_reopen_shows_done(client, sla_20_60_10):
    lead_id, to = await _setup(client)
    assert (await to({"status": "closed", "outcome": "quote_sent"})).status_code == 204
    assert (await to({"status": "contacted"})).status_code == 204
    assert (await to({"status": "closed", "outcome": "quote_sent"})).status_code == 204
    async with AsyncSessionLocal() as db:
        lead = await db.get(Lead, lead_id)
        assert lead.resolved_at is not None
        assert lead_service.sla(lead, lead.resolved_at, set())["sla_state"] == "done"


async def test_too_long_or_huge_owner_ids_are_a_clear_422(client):
    await make_user("cat@kjsindia.com", permissions=["leads.view", "catalog.edit"])
    await login(client, "cat@kjsindia.com")
    for owner_type, owner_id in (("product", "a" * 121), ("lead", "9" * 5000)):
        r = await client.post("/api/v1/files", data={"owner_type": owner_type, "owner_id": owner_id},
                              files={"file": ("spec.pdf", b"%PDF-1.4 %%EOF", "application/pdf")}, headers=HDR)
        assert r.status_code == 422, (owner_type, r.status_code)
        r = await client.get("/api/v1/files", params={"owner_type": owner_type, "owner_id": owner_id})
        assert r.status_code < 500, (owner_type, r.status_code)
