"""Edge cases for #123 (CR17 buyer keys and the import lock, CR21 empty slugs)."""
import asyncio

from sqlalchemy import func, select

from app.core.database import AsyncSessionLocal
from app.models.batch import BuyerRecord
from app.models.user import User
from app.services import assign_service
from tests.conftest import HDR, login, make_user

try:
    from app.models.assign import BuyerRecord
except ImportError:  # the model's module name
    from app.models import BuyerRecord


async def _import(client, name: str, csv: str) -> dict:
    r = await client.post("/api/v1/assign/import", files={"file": (name, csv.encode(), "text/csv")}, headers=HDR)
    assert r.status_code == 201, r.text
    return r.json()


async def test_two_contacts_on_one_switchboard_are_two_buyers(client):
    await make_user("boss@kjsindia.com", permissions=["leads.view", "assign.manage"])
    await login(client, "boss@kjsindia.com")
    csv = ("Company,Email,Phone,Category\nAcme,a@acme.com,+91 40 1111 1111,coffee\n"
           "Acme,b@acme.com,+91 40 1111 1111,coffee\n")
    assert (await _import(client, "a.csv", csv))["added"] == 2


async def test_a_phone_with_no_digits_counts_as_no_phone(client):
    await make_user("boss@kjsindia.com", permissions=["leads.view", "assign.manage"])
    await login(client, "boss@kjsindia.com")
    csv = "Company,Phone,Category\nAcme,N/A,coffee\nAcme,,coffee\nAcme,+91 40 1111 1111,coffee\n"
    body = await _import(client, "a.csv", csv)
    assert body["added"] == 2 and [s["reason"] for s in body["skipped"]] == ["already imported"]


async def test_the_same_file_uploaded_twice_at_once_is_imported_once(client):
    await make_user("boss@kjsindia.com", permissions=["leads.view", "assign.manage"])
    csv = "Company,Email,Category\n" + "".join(f"Shop {n},s{n}@x.com,coffee\n" for n in range(30))
    async with AsyncSessionLocal() as db:
        boss_id = await db.scalar(select(User.id))

    async def one():
        async with AsyncSessionLocal() as db:
            return await assign_service.import_records(db, await db.get(User, boss_id), "b.csv", csv.encode(), "coffee")
    results = await asyncio.gather(one(), one())
    assert sorted(r["added"] for r in results) == [0, 30]
    async with AsyncSessionLocal() as db:
        assert await db.scalar(select(func.count()).select_from(BuyerRecord)) == 30


async def test_a_product_name_of_only_symbols_is_refused(client):
    await make_user("cat@kjsindia.com", permissions=["leads.view", "catalog.edit"])
    await login(client, "cat@kjsindia.com")
    for name in ("!!!", "☕☕", "---"):
        r = await client.post("/api/v1/admin/products", json={"category_slug": "coffee", "name": name}, headers=HDR)
        assert r.status_code == 422, name
