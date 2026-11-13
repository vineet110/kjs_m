"""Extra Info: file columns we have no field for, kept on the lead when the person chooses Add.
Every Add / Reject is in the audit log (column names only, never the customer's values)."""
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.audit import AuditLog
from app.models.lead import Lead
from tests.conftest import HDR, login, make_user

LEAD = {"name": "Ravi", "phone": "+91 90000 11111"}


async def _staff(client):
    await make_user("a@kjs.in")
    await login(client, "a@kjs.in")


async def _audit(action: str) -> list[AuditLog]:
    async with AsyncSessionLocal() as db:
        return list((await db.scalars(select(AuditLog).where(AuditLog.action == action))).all())


async def test_added_columns_saved_and_shown_rejected_ones_only_audited(client):
    await _staff(client)
    body = LEAD | {"extra": {"GST No": "36ABCDE1234F1Z5", "Fax": "040 1234"}, "extra_rejected": ["Notes 2"]}
    r = await client.post("/api/v1/employee/leads", json=body, headers=HDR)
    assert r.status_code == 201, r.text
    assert r.json()["extra"] == {"GST No": "36ABCDE1234F1Z5", "Fax": "040 1234"}
    rows = await _audit("lead.extra_columns")
    assert len(rows) == 1 and rows[0].entity_id == str(r.json()["id"])
    assert rows[0].after["added"] == ["Fax", "GST No"] and rows[0].after["rejected"] == ["Notes 2"]
    assert "36ABCDE1234F1Z5" not in str(rows[0].after)  # names only: the value stays on the lead


async def test_no_file_columns_no_extra_and_no_audit_row(client):
    await _staff(client)
    r = await client.post("/api/v1/employee/leads", json=LEAD, headers=HDR)
    assert r.json()["extra"] == {}
    assert await _audit("lead.extra_columns") == []


async def test_extra_limits(client):
    await _staff(client)
    too_many = {f"Col {i}": "x" for i in range(31)}
    for extra in (too_many, {"GST": "x" * 501}, {"x" * 101: "v"}, {" ": "v"}):
        r = await client.post("/api/v1/employee/leads", json=LEAD | {"extra": extra}, headers=HDR)
        assert r.status_code == 422, list(extra)[:1]
    async with AsyncSessionLocal() as db:
        assert (await db.scalars(select(Lead))).first() is None


async def test_import_keeps_added_columns_and_audits_once(client):
    await _staff(client)
    leads = [LEAD | {"extra": {"GST No": "36A"}}, {"name": "Neha", "phone": "+91 90000 22222", "extra": {"GST No": "36B"}}]
    r = await client.post("/api/v1/employee/leads/import", json={"leads": leads, "extra_rejected": ["Fax"]}, headers=HDR)
    assert r.status_code == 201, r.text
    mine = {x["name"]: x["extra"] for x in (await client.get("/api/v1/employee/leads?source=internal")).json()}
    assert mine == {"Ravi": {"GST No": "36A"}, "Neha": {"GST No": "36B"}}
    rows = await _audit("lead.extra_columns")
    assert len(rows) == 1 and rows[0].after["added"] == ["GST No"] and rows[0].after["rejected"] == ["Fax"]
    assert sorted(rows[0].after["lead_ids"]) == sorted(r.json()["lead_ids"])
