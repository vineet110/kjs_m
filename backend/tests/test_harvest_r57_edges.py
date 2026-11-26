"""R57 edge cases: the scraper's phone, odd field types, duplicates inside one fetch."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.core.database import AsyncSessionLocal
from app.models.harvest import HarvestSource
from app.services import harvest_service
from app.services.harvest_filter import filter_single_record
from app.services.harvest_service import fetch_scrape_source, run_harvest_source


@pytest.fixture(autouse=True)
def public_dns(monkeypatch):
    async def fake_resolve(host, port):
        return ["93.184.216.34"]
    monkeypatch.setattr("app.services.harvest_net.resolve", fake_resolve)


async def _scrape(text: str) -> list[dict]:
    page = SimpleNamespace(text=f"<html><title>Shop</title><body>{text}</body></html>", raise_for_status=lambda: None)
    src = HarvestSource(name="S", source_type="scrape", url="https://example.com/list", category="coffee",
                       terms_checked=True)
    with patch.object(harvest_service, "is_scraping_allowed", new=AsyncMock(return_value=True)), \
         patch.object(harvest_service.asyncio, "sleep", new=AsyncMock()), \
         patch.object(harvest_service, "safe_get", new=AsyncMock(return_value=page)):
        return await fetch_scrape_source(src)


@pytest.mark.parametrize("text", [
    "Mumbai 400001. Tel +91 98765 43210",  # a pin code first
    "Est. 2026-11-27, call +91 98765 43210",  # a date first
    "MOQ 10000 pcs. +91 98765 43210",  # a quantity first
])
async def test_the_phone_is_not_a_pin_code_date_or_quantity_before_it(text):
    records = await _scrape(text)
    assert records and records[0]["phone"].replace(" ", "") == "+919876543210"


async def test_a_page_with_only_short_numbers_has_no_phone():
    assert await _scrape("Mumbai 400001, since 1998, MOQ 10000") == []


async def test_lists_and_none_in_text_fields_do_not_crash():
    async with AsyncSessionLocal() as db:
        raw = {"company": ["A", "B"], "contact_name": None, "email": None, "phone": "+91 98765 43210",
               "country": 91, "website": None, "product": "instant coffee"}
        clean, drop = await filter_single_record(db, raw, "all")
    assert drop is None and clean["company"] == "['A', 'B']" and clean["contact_name"] == ""


async def test_a_record_already_saved_with_other_spacing_is_a_duplicate():
    from app.models.lead import Lead
    from datetime import datetime, timezone
    async with AsyncSessionLocal() as db:
        db.add(Lead(source="enquiry_form", name="Old", phone="+91-98765-43210", consent=True,
                    consent_at=datetime.now(timezone.utc), status="new"))
        await db.commit()
        clean, drop = await filter_single_record(db, {"company": "A", "phone": "+919876543210", "product": "coffee"}, "all")
    assert clean is None and drop == "duplicate"


async def test_one_failing_record_does_not_stop_the_run():
    async with AsyncSessionLocal() as db:
        src = HarvestSource(name="S", source_type="api", url="https://api.example.com/x", category="coffee", is_active=True)
        db.add(src)
        await db.commit()
        good = {"company": "A", "email": "a@a.in", "product": "coffee beans"}
        bad = {"company": "B", "email": "b@b.in", "product": "coffee beans"}
        real = harvest_service.filter_single_record

        async def flaky(db, item, *a, **k):
            if item is bad:
                raise RuntimeError("odd record")
            return await real(db, item, *a, **k)
        with patch.object(harvest_service, "fetch_api_source", new=AsyncMock(return_value=[bad, good])), \
             patch.object(harvest_service, "filter_single_record", new=flaky):
            run = await run_harvest_source(db, src.id)
    assert run.accepted_count == 1 and run.drop_reasons == {"unreadable": 1}
