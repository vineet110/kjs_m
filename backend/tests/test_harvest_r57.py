"""R57: Lead Harvester follow-up fixes."""
from unittest.mock import AsyncMock, patch

import pytest

from app.core.database import AsyncSessionLocal
from app.models.harvest import HarvestSource
from app.services.harvest_filter import filter_single_record, normalize_phone
from app.services.harvest_service import is_scraping_allowed, run_harvest_source


@pytest.fixture(autouse=True)
def public_dns(monkeypatch):
    async def fake_resolve(host, port):
        return ["93.184.216.34"]
    monkeypatch.setattr("app.services.harvest_net.resolve", fake_resolve)


async def test_unreadable_robots_txt_means_nothing_is_fetched():
    from app.core.errors import AppError
    with patch("app.services.harvest_service.safe_get", new_callable=AsyncMock, side_effect=RuntimeError("down")):
        with pytest.raises(AppError) as e:
            await is_scraping_allowed("https://example.com/list")
    assert e.value.code == "robots_unreadable"  # a failed run with the real reason, not "blocked by robots"


def test_the_scraper_takes_a_number_without_the_digits_around_it():
    import re
    from app.services.harvest_service import PHONE_IN_TEXT
    m = PHONE_IN_TEXT.search("Phone: +91 98765 43210 9am-6pm, since 1998")
    assert m and re.sub(r"\D", "", m.group(0)) == "919876543210"


async def test_a_number_in_a_text_field_does_not_crash_and_spices_without_a_category_is_dropped():
    async with AsyncSessionLocal() as db:
        raw = {"company": 12345, "email": "a@b.in", "phone": 919876543210, "product": "black pepper spices"}
        clean, drop = await filter_single_record(db, raw, "all")
        assert clean is None and drop == "unknown_category"  # no "spices" catalogue category to put it in
        clean, drop = await filter_single_record(db, {**raw, "product": "instant coffee"}, "all")
        assert drop is None and clean["company"] == "12345" and clean["phone"] == "+919876543210"


def test_spaced_indian_numbers_are_kept():
    assert normalize_phone("+91 98765 43210") == "+919876543210"


async def test_duplicates_inside_one_fetch_are_dropped():
    async with AsyncSessionLocal() as db:
        src = HarvestSource(name="S", source_type="api", url="https://api.example.com/x", category="coffee", is_active=True)
        db.add(src)
        await db.commit()
        item = {"company": "A", "email": "same@a.in", "phone": "+91 98765 43210", "product": "coffee beans"}
        again = {**item, "email": "", "phone": "+919876543210"}  # the same number written another way
        with patch("app.services.harvest_service.fetch_api_source", new_callable=AsyncMock, return_value=[item, again]):
            run = await run_harvest_source(db, src.id)
        assert run.accepted_count == 1 and run.drop_reasons == {"duplicate": 1}
