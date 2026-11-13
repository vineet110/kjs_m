"""Fill the New internal lead form from an Excel / CSV file (lead_reader), and the "same person" check."""
import io

from openpyxl import Workbook
from sqlalchemy import func, select

from app.core.database import AsyncSessionLocal
from app.models.lead import Lead
from tests.conftest import HDR, login, make_user

URL = "/api/v1/employee/leads/read-file"
EMPTY = {"name": "", "company": "", "email": "", "phone": "", "country": "", "buyer_type": "",
         "category_slug": "", "quantity": "", "message": ""}


def _xlsx(rows: list[list]) -> bytes:
    wb = Workbook()
    for r in rows:
        wb.active.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


async def _read(client, name: str, data: bytes):
    return await client.post(URL, files={"file": (name, data, "application/octet-stream")}, headers=HDR)


async def _staff(client):
    await make_user("a@kjs.in")
    await login(client, "a@kjs.in")


async def test_table_csv_matches_column_names_people_use(client):
    await _staff(client)
    csv = b"Contact Person,Mobile No.,Firm,E-mail,GST No\nRavi Kumar,+91 90000 11111,Ravi Traders,ravi@x.in,36ABC\n"
    r = await _read(client, "card.csv", csv)
    assert r.status_code == 200, r.text
    lead = r.json()["leads"][0]
    assert lead["fields"] == EMPTY | {"name": "Ravi Kumar", "phone": "+91 90000 11111", "company": "Ravi Traders",
                                      "email": "ravi@x.in"}
    assert lead["extra"] == {"GST No": "36ABC"}  # no field for it: shown as not saved
    async with AsyncSessionLocal() as db:
        assert await db.scalar(select(func.count(Lead.id))) == 0  # reading never saves


async def test_card_layout_excel_and_numbers_and_formulas(client):
    await _staff(client)  # the "coffee" category comes with the test database
    data = _xlsx([["Name", "Neha"], ["Phone", 9848012345], ["Interested in", "coffee"], ["Buyer type", "distributors"],
                  ["Products", "Green tea"], ["Quantity", "=1+1"]])
    lead = (await _read(client, "card.xlsx", data)).json()["leads"][0]
    assert lead["fields"]["name"] == "Neha"
    assert lead["fields"]["phone"] == "9848012345"  # not "9848012345.0"
    assert lead["fields"]["category_slug"] == "coffee"
    assert lead["fields"]["buyer_type"] == "Distributor"
    assert lead["extra"] == {"Products": "Green tea"}  # a category we don't have
    assert not lead["fields"]["quantity"].startswith("=")  # a formula is never read as text


async def test_many_rows_capped_and_flagged(client):
    await _staff(client)
    rows = [["Name", "Phone"]] + [[f"Buyer {i}", f"+91 90000 {i:05d}"] for i in range(60)]
    body = (await _read(client, "list.xlsx", _xlsx(rows))).json()
    assert len(body["leads"]) == 50 and body["more_rows"] is True
    assert body["leads"][1]["fields"]["name"] == "Buyer 1"


async def test_semicolon_and_windows_csv(client):
    await _staff(client)
    lead = (await _read(client, "a.csv", "Name;Country\nJosé;España\n".encode("cp1252"))).json()["leads"][0]
    assert (lead["fields"]["name"], lead["fields"]["country"]) == ("José", "España")


async def test_bad_files_refused(client):
    await _staff(client)
    cases = [("old.xls", b"\xd0\xcf\x11\xe0", "file_type"), ("a.pdf", b"%PDF-1.4 %%EOF", "file_type"),
             ("a.xlsx", b"PK broken", "file_broken"), ("a.csv", b"Name\x00Phone", "file_broken"),
             ("a.csv", b"Name,Phone\n", "empty")]
    for name, data, code in cases:
        r = await _read(client, name, data)
        assert r.status_code == 422 and r.json()["code"] == code, (name, r.text)


async def test_reading_needs_login(client):
    r = await _read(client, "a.csv", b"Name\nX\n")
    assert r.status_code == 401


async def test_same_person_counts_only_leads_i_can_see(client):
    await make_user("a@kjs.in")
    await make_user("b@kjs.in")
    await login(client, "b@kjs.in")
    lead = {"name": "Ravi", "phone": "+91 90000 11111", "email": "ravi@x.in"}
    assert (await client.post("/api/v1/employee/leads", json=lead, headers=HDR)).status_code == 201
    r = (await client.get("/api/v1/employee/leads/same-person", params={"phone": "+91 9000011111"})).json()
    assert r["count"] == 1 and r["lead_id"]
    r = (await client.get("/api/v1/employee/leads/same-person", params={"email": "RAVI@x.in"})).json()
    assert r["count"] == 1
    assert (await client.get("/api/v1/employee/leads/same-person", params={"phone": "+91 1"})).json()["count"] == 0
    await login(client, "a@kjs.in")  # b's lead: a can't see it, so it isn't counted
    assert (await client.get("/api/v1/employee/leads/same-person", params={"phone": "+91 90000 11111"})).json() == \
        {"count": 0, "lead_id": None}
