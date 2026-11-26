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


@pytest.mark.parametrize("text, digits", [
    ("Phone: +91 98765 43210 9am-6pm, since 1998", "919876543210"),
    ("Call +91 98765 43210 10am-6pm", "919876543210"),  # a time right after (re-review of #136)
    ("Since 1998 9876543210", "9876543210"),  # a year right before
    ("+91 98765 43210 2026", "919876543210"),  # a year after must not make it too long and lose it
    ("Mumbai 400001, Tel +91 98765 43210", "919876543210"),  # a pin code first
    ("MOQ 10000 units. Date 2026-11-27. Call 98765 43210", "9876543210"),
    ("98765 43210 98765 43211", "9876543210"),  # two numbers side by side: the first one only
    ("Tel: 040 2345 6789 / 98765 43210", "04023456789"),
    ("No number here, only 400001", ""),
    ("Since 1998 98765 43210", "9876543210"),  # re-review: a year before a spaced number
    ("Mumbai 400001 98765 43210", "9876543210"),  # a pin code before it
    ("Order 12 98765 43210", "9876543210"),  # a small quantity before it
    ("ref x9876543210 here", ""),  # glued to a letter: a code, not a phone
])
def test_the_phone_finder_takes_a_number_without_the_digits_around_it(text, digits):
    import re
    from app.services.harvest_service import find_phone
    assert re.sub(r"\D", "", find_phone(text)) == digits


async def test_an_active_category_still_matches_when_the_source_is_set_to_another_group():
    # Re-review of #136: a "private_label" source must still file "private label instant coffee" as coffee
    async with AsyncSessionLocal() as db:
        raw = {"company": "A", "email": "pl@a.in", "product": "private label instant coffee"}
        clean, drop = await filter_single_record(db, raw, "private_label")
        assert drop is None and clean["category"] == "coffee"


async def test_a_source_that_fails_after_fetching_is_recorded_and_waits_its_turn():
    from sqlalchemy import select
    from app.models.harvest import HarvestRun
    from app.services.harvest_service import harvest_due_sources_job
    async with AsyncSessionLocal() as db:
        src = HarvestSource(name="S", source_type="api", url="https://api.example.com/x", category="coffee", is_active=True)
        db.add(src)
        await db.commit()
        item = {"company": "A", "email": "f@a.in", "product": "coffee beans"}
        with patch("app.services.harvest_service.fetch_api_source", new_callable=AsyncMock, return_value=[item]), \
                patch("app.services.harvest_service.save_accepted_records", new_callable=AsyncMock,
                      side_effect=RuntimeError("disk full")):
            await harvest_due_sources_job(db)
        runs = (await db.scalars(select(HarvestRun.status).where(HarvestRun.source_id == src.id))).all()
        await db.refresh(src)
        assert runs == ["failed"] and src.last_run_at is not None and src.last_status == "failed"


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


def test_local_numbers_get_the_default_country_code():
    assert normalize_phone("98765 43210") == "+919876543210"
    assert normalize_phone("040 2345 6789") == "+914023456789"


async def test_a_lead_saved_without_country_code_is_a_duplicate_of_the_same_number_with_it():
    from datetime import datetime, timezone
    from app.models.lead import Lead
    async with AsyncSessionLocal() as db:
        db.add(Lead(source="enquiry_form", name="B", phone="98765-43210", consent=True,
                    consent_at=datetime.now(timezone.utc), status="new"))
        await db.commit()
        clean, drop = await filter_single_record(db, {"company": "B", "phone": "+91 98765 43210",
                                                      "product": "instant coffee"}, "all")
        assert drop == "duplicate"


@pytest.mark.parametrize("text, digits", [
    ("Call +86 138 0013 8000", "8613800138000"),  # 13 digits with + : the whole number, not a cut
    ("Mumbai 400001 2261 2345", ""),  # a pin code plus a short number is not a 10-digit mobile
    ("Contact 919876543210 for bulk coffee", "919876543210"),  # +91 written without its "+"
    ("Kolkata 700001 2026 catalogue", ""),  # a 7-starting pin code plus a year is not a mobile
    ("Chennai 600001 1234", ""),
    ("Call 987 654 3210", "9876543210"),  # 3-3-4 grouping still found
    ("Tel +91 (0)22 2345 6789", "912223456789"),  # the bracketed trunk 0 is dropped
])
def test_more_phone_texts(text, digits):
    import re
    from app.services.harvest_service import find_phone
    assert re.sub(r"\D", "", find_phone(text)) == digits


def test_the_default_code_is_only_for_buyers_in_india():
    assert normalize_phone("98765 43210", "India") == "+919876543210"
    assert normalize_phone("212-555-1234", "USA") == ""  # never turned into an Indian number


async def test_other_countries_with_the_same_last_ten_digits_are_not_duplicates():
    from datetime import datetime, timezone
    from app.models.lead import Lead
    async with AsyncSessionLocal() as db:
        db.add(Lead(source="enquiry_form", name="UK", phone="+44 20 7946 0958", consent=True,
                    consent_at=datetime.now(timezone.utc), status="new"))
        await db.commit()
        clean, drop = await filter_single_record(db, {"company": "US", "phone": "+1 207 946 0958",
                                                      "country": "USA", "product": "instant coffee"}, "all")
        assert drop is None
