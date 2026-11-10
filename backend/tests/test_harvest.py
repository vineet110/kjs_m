"""Tests for Lead Harvester:
- Shared quality filter (category matching, contact check, deduplication, DPDP provenance)
- Connectors (API, Open Data CSV/JSON, RSS XML, Scraping with robots.txt check)
- Background runner job registration and execution
- Admin Client Schedulers endpoints and access control
"""
import io
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from httpx import Response, Request
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.batch import BuyerRecord, RecordList
from app.models.harvest import HarvestRun, HarvestSource
from app.models.lead import Lead
from app.models.user import User
from app.services.harvest_filter import (
    filter_single_record,
    match_product_category,
    normalize_email,
    normalize_phone,
    save_accepted_records,
)
from app.services.harvest_service import (
    fetch_api_source,
    fetch_open_data_source,
    fetch_rss_source,
    fetch_scrape_source,
    harvest_due_sources_job,
    run_harvest_source,
)
from tests.conftest import HDR, login, make_user


@pytest.fixture
async def db():
    async with AsyncSessionLocal() as session:
        yield session


# ---------------- 1. Shared Filter Tests ----------------

def test_product_category_matching():
    # Coffee match
    cat, kw = match_product_category("Looking for 500kg Arabica roasted beans")
    assert cat == "coffee"
    assert kw in ("arabica", "roast", "beans")

    # Tea match
    cat, kw = match_product_category("Wholesale bulk order of Assam green tea")
    assert cat == "tea"

    # Spices match
    cat, kw = match_product_category("Export quality green cardamom and black pepper")
    assert cat == "spices"

    # Private label match
    cat, kw = match_product_category("Need contract manufacturing and co-pack service for beverages")
    assert cat == "private_label"

    # Unrelated product
    cat, kw = match_product_category("Industrial steel pipes and plastic granules")
    assert cat is None
    assert kw is None


def test_contact_normalization():
    # Valid email
    assert normalize_email("  BUYER@Example.COM ") == "buyer@example.com"
    assert normalize_email("not-an-email") == ""
    assert normalize_email(None) == ""

    # Valid phone with country code (E.164)
    assert normalize_phone("+91 98765-43210") == "+919876543210"
    assert normalize_phone("00919876543210") == "+919876543210"
    assert normalize_phone("+1 (202) 555-0123") == "+12025550123"

    # Invalid phone (no country code or too short)
    assert normalize_phone("987654") == ""
    assert normalize_phone(None) == ""


async def test_filter_single_record_invalid_contact(db):
    raw = {
        "company": "No Contact Ltd",
        "email": "invalid-email",
        "phone": "123",
        "product": "Arabica coffee beans",
    }
    clean, drop = await filter_single_record(db, raw)
    assert clean is None
    assert drop == "invalid_contact"


async def test_filter_single_record_product_mismatch(db):
    raw = {
        "company": "Auto Parts Co",
        "email": "parts@example.com",
        "phone": "+919876543210",
        "product": "Hydraulic brake valves",
    }
    clean, drop = await filter_single_record(db, raw)
    assert clean is None
    assert drop == "product_mismatch"


async def test_filter_single_record_duplicate_lead(db):
    # Insert existing lead with normalized phone
    existing = Lead(
        source="enquiry_form",
        name="Existing Buyer",
        email="existing@kjsindia.com",
        phone="+919876543210",
        consent=True,
        consent_at=datetime.now(timezone.utc),
    )
    db.add(existing)
    await db.commit()

    raw = {
        "company": "Duplicate Enquiry Co",
        "email": "DIFFERENT@email.com",
        "phone": "+91 98765-43210",
        "product": "Need instant coffee powder",
    }
    clean, drop = await filter_single_record(db, raw)
    assert clean is None
    assert drop == "duplicate"


async def test_filter_single_record_duplicate_buyer_record(db):
    # Insert existing buyer record with matching email
    r_list = RecordList(name="Old Batch", rows=1)
    db.add(r_list)
    await db.flush()

    existing_buyer = BuyerRecord(
        list_id=r_list.id,
        category="tea",
        company="Old Buyer",
        email="oldbuyer@company.com",
        phone="+919111122222",
    )
    db.add(existing_buyer)
    await db.commit()

    raw = {
        "company": "Same Buyer New Source",
        "email": "  OldBuyer@Company.COM ",
        "phone": "+919999988888",
        "product": "Wholesale Darjeeling tea",
    }
    clean, drop = await filter_single_record(db, raw)
    assert clean is None
    assert drop == "duplicate"


async def test_filter_and_save_accepted_records(db):
    source = HarvestSource(
        name="IndiaMART Spices",
        source_type="api",
        url="https://api.indiamart.com/enquiries",
        category="spices",
    )
    db.add(source)
    await db.commit()

    raw = {
        "company": "Kerala Spice Traders",
        "contact_name": "Ramesh Nair",
        "email": "ramesh@keralaspices.in",
        "phone": "+91 9876543210",
        "country": "India",
        "product": "Bulk Malabar black pepper and green cardamom",
        "message": "Requirement: 2 metric tons for domestic distribution",
        "source_url": "https://api.indiamart.com/enquiries/101",
    }

    clean, drop = await filter_single_record(db, raw, source.category)
    assert drop is None
    assert clean is not None
    assert clean["category"] == "spices"

    saved = await save_accepted_records(db, source, [clean])
    assert saved == 1

    # Verify BuyerRecord created with status="new" and DPDP provenance notes
    buyer = await db.scalar(select(BuyerRecord).where(BuyerRecord.email == "ramesh@keralaspices.in"))
    assert buyer is not None
    assert buyer.status == "new"
    assert buyer.category == "spices"
    assert "DPDP Provenance: https://api.indiamart.com/enquiries/101" in buyer.notes
    assert "Source: IndiaMART Spices" in buyer.notes


# ---------------- 2. Connector Tests ----------------

async def test_api_connector_auth_and_extraction(monkeypatch):
    monkeypatch.setenv("TEST_INDIAMART_KEY", "secret_token_123")
    source = HarvestSource(
        name="IndiaMART Test",
        source_type="api",
        url="https://api.example.com/leads",
        auth_env_var="TEST_INDIAMART_KEY",
    )

    mock_resp = Response(
        status_code=200,
        request=Request("GET", source.url),
        json={
            "results": [
                {
                    "company": "Chai Point",
                    "contact_name": "Amrit",
                    "email": "amrit@chaipoint.com",
                    "mobile": "+919876500000",
                    "subject": "Assam CTC Tea",
                    "requirement": "500kg monthly",
                }
            ]
        },
    )

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp
        items = await fetch_api_source(source)
        assert len(items) == 1
        assert items[0]["company"] == "Chai Point"
        assert items[0]["email"] == "amrit@chaipoint.com"
        # Check Bearer auth header was sent
        call_headers = mock_get.call_args.kwargs.get("headers", {})
        assert call_headers.get("Authorization") == "Bearer secret_token_123"


async def test_open_data_connector_csv():
    source = HarvestSource(
        name="Gov Open Data",
        source_type="open_data",
        url="https://data.gov.in/spices_buyers.csv",
    )

    csv_content = (
        "company,contact_name,email,phone,commodity,details\n"
        "Global Spices,John Doe,john@globalspices.com,+919876543210,Turmeric,100kg organic\n"
    )

    mock_resp = Response(
        status_code=200,
        request=Request("GET", source.url),
        text=csv_content,
        headers={"content-type": "text/csv"},
    )

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp
        items = await fetch_open_data_source(source)
        assert len(items) == 1
        assert items[0]["company"] == "Global Spices"
        assert items[0]["email"] == "john@globalspices.com"
        assert items[0]["product"] == "Turmeric"


async def test_rss_connector_xml():
    source = HarvestSource(
        name="Trade Tender RSS",
        source_type="rss",
        url="https://trade.example.com/rss",
    )

    xml_text = """<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
      <channel>
        <title>Trade Enquiries</title>
        <item>
          <title>Procurement of Green Coffee Beans</title>
          <link>https://trade.example.com/enquiry/55</link>
          <description>Contact purchase@roasters.in or +919876543210 for bids</description>
        </item>
      </channel>
    </rss>
    """

    mock_resp = Response(
        status_code=200,
        request=Request("GET", source.url),
        text=xml_text,
    )
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp
        items = await fetch_rss_source(source)
        assert len(items) == 1
        assert "Green Coffee Beans" in items[0]["product"]
        assert items[0]["email"] == "purchase@roasters.in"
        assert items[0]["phone"] == "+919876543210"


async def test_scrape_connector_terms_and_robots():
    # 1. Blocked if terms_checked is False
    unconfirmed = HarvestSource(
        name="Scrape Without Terms",
        source_type="scrape",
        url="https://directory.example.com",
        terms_checked=False,
    )
    with pytest.raises(Exception) as exc:
        await fetch_scrape_source(unconfirmed)
    assert "terms checked" in str(exc.value)

    # 2. Blocked if robots.txt forbids
    confirmed = HarvestSource(
        name="Scrape Disallowed",
        source_type="scrape",
        url="https://directory.example.com/secret",
        terms_checked=True,
    )
    with patch("app.services.harvest_service.is_scraping_allowed", return_value=False):
        with pytest.raises(Exception) as exc:
            await fetch_scrape_source(confirmed)
        assert "robots.txt" in str(exc.value)


# ---------------- 3. Runner & Job Execution Tests ----------------

async def test_run_harvest_source_full_flow(db):
    source = HarvestSource(
        name="Tea Portal API",
        source_type="api",
        url="https://api.tea.in/leads",
        category="tea",
        is_active=True,
    )
    db.add(source)
    await db.commit()

    mock_items = [
        # Item 1: Valid Tea enquiry
        {
            "company": "Tea Lover Co",
            "contact_name": "Sita",
            "email": "sita@teacompany.com",
            "phone": "+919876511111",
            "country": "India",
            "product": "Green tea loose leaf",
            "message": "Need 100 kg",
            "source_url": "https://api.tea.in/leads/1",
        },
        # Item 2: Unrelated product
        {
            "company": "Auto Co",
            "contact_name": "Gita",
            "email": "gita@auto.com",
            "phone": "+919876522222",
            "country": "India",
            "product": "Bicycle chains",
            "message": "Parts enquiry",
            "source_url": "https://api.tea.in/leads/2",
        },
    ]

    with patch("app.services.harvest_service.fetch_api_source", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = mock_items
        run = await run_harvest_source(db, source.id)

        assert run.found_count == 2
        assert run.accepted_count == 1
        assert run.dropped_count == 1
        assert run.drop_reasons == {"product_mismatch": 1}
        assert run.status == "partial"

        # Check source updated
        await db.refresh(source)
        assert source.last_status == "partial"
        assert source.last_run_at is not None


async def test_harvest_due_sources_job(db):
    # Source 1: active and due (last_run_at is None)
    s1 = HarvestSource(
        name="Due Source",
        source_type="api",
        url="https://api.due.com",
        is_active=True,
        last_run_at=None,
    )
    # Source 2: inactive
    s2 = HarvestSource(
        name="Inactive Source",
        source_type="api",
        url="https://api.inactive.com",
        is_active=False,
    )
    db.add_all([s1, s2])
    await db.commit()

    with patch("app.services.harvest_service.run_harvest_source", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = HarvestRun(
            source_id=s1.id,
            status="success",
            found_count=1,
            accepted_count=1,
            dropped_count=0,
            drop_reasons={},
        )
        res = await harvest_due_sources_job(db)
        assert res["due_sources"] == 1
        assert res["runs_executed"] == 1
        assert res["total_accepted"] == 1


# ---------------- 4. Admin API Endpoint Tests ----------------

async def test_harvest_api_crud_and_run(client):
    # 1. Forbidden for employee without assign.manage or leads.view_all
    await make_user("employee@kjsindia.com", permissions=["leads.view"])
    await login(client, "employee@kjsindia.com")
    r = await client.get("/api/v1/admin/harvest/sources", headers=HDR)
    assert r.status_code == 403

    # 2. Allowed for manager with assign.manage
    await make_user("manager@kjsindia.com", permissions=["leads.view", "assign.manage"])
    await login(client, "manager@kjsindia.com")

    # List sources (empty initially)
    r = await client.get("/api/v1/admin/harvest/sources", headers=HDR)
    assert r.status_code == 200
    assert r.json() == []

    # Create API source
    create_payload = {
        "name": "IndiaMART Coffee API",
        "source_type": "api",
        "url": "https://api.indiamart.com/coffee",
        "auth_env_var": "INDIAMART_API_KEY",
        "category": "coffee",
        "is_active": True,
        "terms_checked": True,
        "schedule_interval_minutes": 15,
    }
    r = await client.post("/api/v1/admin/harvest/sources", json=create_payload, headers=HDR)
    assert r.status_code == 201
    source_id = r.json()["id"]
    assert r.json()["name"] == "IndiaMART Coffee API"

    # Update source
    update_payload = {"name": "IndiaMART Coffee & Beverages", "is_active": False}
    r = await client.put(f"/api/v1/admin/harvest/sources/{source_id}", json=update_payload, headers=HDR)
    assert r.status_code == 200
    assert r.json()["name"] == "IndiaMART Coffee & Beverages"
    assert r.json()["is_active"] is False

    # Trigger Run now
    with patch("app.api.v1.endpoints.harvest.run_harvest_source", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = HarvestRun(
            id=99,
            source_id=source_id,
            status="success",
            found_count=5,
            accepted_count=4,
            dropped_count=1,
            drop_reasons={"duplicate": 1},
            error_message="",
            started_at=datetime.now(timezone.utc),
            finished_at=datetime.now(timezone.utc),
        )
        r = await client.post(f"/api/v1/admin/harvest/sources/{source_id}/run", headers=HDR)
        assert r.status_code == 200
        assert r.json()["status"] == "success"
        assert r.json()["accepted_count"] == 4

    # List runs
    r = await client.get("/api/v1/admin/harvest/runs", headers=HDR)
    assert r.status_code == 200

    # Stats
    r = await client.get("/api/v1/admin/harvest/stats", headers=HDR)
    assert r.status_code == 200
    assert "total_sources" in r.json()

    # Delete source
    r = await client.delete(f"/api/v1/admin/harvest/sources/{source_id}", headers=HDR)
    assert r.status_code == 200
    assert r.json() == {"ok": True}
