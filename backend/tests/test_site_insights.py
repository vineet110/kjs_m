"""Website insights: the website's tracker (no login) and Reports > Website insights (insights.view)."""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select, update

from app.core.config import ini
from app.core.database import AsyncSessionLocal
from app.models.site_event import SiteEvent
from app.services import site_insights_service as svc
from tests.conftest import login, make_user

URL = "/api/v1/public/insights/events"
REPORT = "/api/v1/admin/site-insights"
PHONE_UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) Mobile/15E148 Safari/604.1"
DESKTOP_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"


@pytest.fixture(autouse=True)
def fresh_cleanup():
    svc._last_cleanup = 0.0  # every test starts as if the API just started


async def send(client, events, visit="visit-0001", ua=DESKTOP_UA, **kw):
    return await client.post(URL, json={"visit_id": visit, "events": events}, headers={"user-agent": ua}, **kw)


async def count(**where) -> int:
    async with AsyncSessionLocal() as db:
        q = select(func.count()).select_from(SiteEvent)
        for k, v in where.items():
            q = q.where(getattr(SiteEvent, k) == v)
        return await db.scalar(q)


# ---------- The tracker ----------
async def test_page_search_click_are_saved(client):
    r = await send(client, [
        {"kind": "page", "path": "/en/products/instant-coffee?x=1", "referrer": "https://www.google.co.in/search?q=a"},
        {"kind": "search", "path": "/en", "query": "  Instant  COFFEE ", "results": 3},
        {"kind": "click", "path": "/en/products/instant-coffee", "button": "add_to_enquiry"},
    ], ua=PHONE_UA)
    assert r.status_code == 204, r.text
    async with AsyncSessionLocal() as db:
        rows = (await db.scalars(select(SiteEvent).order_by(SiteEvent.id))).all()
    page, search, click = rows
    assert (page.path, page.product_slug, page.source, page.device) == (
        "/products/instant-coffee", "instant-coffee", "Google", "mobile")
    assert (search.query, search.results) == ("instant coffee", 3)
    assert (click.button, click.product_slug) == ("add_to_enquiry", "instant-coffee")


async def test_phone_numbers_and_emails_are_hidden(client):
    await send(client, [
        {"kind": "search", "path": "/", "query": "call me +91 98765-43210", "results": 0},
        {"kind": "search", "path": "/", "query": "buyer@example.com wafers", "results": 0},
        {"kind": "search", "path": "/", "query": "801", "results": 1},  # an item number stays
    ])
    async with AsyncSessionLocal() as db:
        qs = (await db.scalars(select(SiteEvent.query).order_by(SiteEvent.id))).all()
    assert qs == ["call me ***", "*** wafers", "801"]


async def test_unknown_button_and_short_search_are_dropped(client):
    await send(client, [
        {"kind": "click", "path": "/", "button": "made_up"},
        {"kind": "search", "path": "/", "query": "a", "results": 0},  # shorter than min_search_chars
    ])
    assert await count() == 0


async def test_robots_and_staff_are_not_counted(client):
    assert (await send(client, [{"kind": "page", "path": "/"}], ua="Googlebot/2.1")).status_code == 204
    assert (await send(client, [{"kind": "page", "path": "/"}], ua="")).status_code == 204
    client.cookies.set("kjs_session", "anything")
    assert (await send(client, [{"kind": "page", "path": "/"}])).status_code == 204
    assert await count() == 0


async def test_area_off_saves_nothing(client, monkeypatch):
    monkeypatch.setenv("KJS__MODULES__SITE_INSIGHTS", "off")
    ini.reload_now()
    assert (await send(client, [{"kind": "page", "path": "/"}])).status_code == 204
    assert await count() == 0
    assert (await client.get("/api/v1/public/config")).json()["insights"]["on"] is False


async def test_bad_input_is_refused(client):
    assert (await send(client, [{"kind": "page", "path": "https://evil.example/x"}])).status_code == 422
    assert (await send(client, [{"kind": "page", "path": "//evil.example"}])).status_code == 422
    assert (await send(client, [{"kind": "hack", "path": "/"}])).status_code == 422
    assert (await send(client, [{"kind": "page", "path": "/"}], visit="x")).status_code == 422
    assert (await send(client, [])).status_code == 422


async def test_batch_size_comes_from_config(client, monkeypatch):
    monkeypatch.setenv("KJS__SITE_INSIGHTS__MAX_EVENTS_PER_SEND", "2")
    ini.reload_now()
    assert (await send(client, [{"kind": "page", "path": "/"}] * 3)).status_code == 422
    assert (await send(client, [{"kind": "page", "path": "/"}] * 2)).status_code == 204


async def test_too_many_sends_are_refused(client, monkeypatch):
    monkeypatch.setenv("KJS__SITE_INSIGHTS__SENDS_PER_MINUTE", "2")
    ini.reload_now()
    for _ in range(2):
        assert (await send(client, [{"kind": "page", "path": "/"}])).status_code == 204
    assert (await send(client, [{"kind": "page", "path": "/"}])).status_code == 429


async def test_old_events_are_deleted(client):
    await send(client, [{"kind": "page", "path": "/"}, {"kind": "page", "path": "/contact"}])
    async with AsyncSessionLocal() as db:
        old = datetime.now(timezone.utc) - timedelta(days=200)  # keep_days = 180
        await db.execute(update(SiteEvent).where(SiteEvent.path == "/").values(at=old))
        await db.commit()
        assert await svc.cleanup(db, force=True) == 1
    assert await count() == 1


def test_helpers():
    assert svc.split_path("/en") == ("/", None, None)
    assert svc.split_path("/hi/categories/coffee/") == ("/categories/coffee", None, "coffee")
    assert svc.source_of("https://l.facebook.com/x") == "Facebook"
    assert svc.source_of("https://www.example.org/page?email=a@b.c") == "example.org"
    assert svc.source_of("not a link") is None
    assert svc.device_of("Mozilla/5.0 (Linux; Android 14; SM-X200) Safari") == "tablet"


# ---------- The report ----------
async def test_report_counts(client):
    await send(client, [
        {"kind": "page", "path": "/products/wafer", "referrer": "https://www.bing.com/"},
        {"kind": "click", "path": "/products/wafer", "button": "add_to_enquiry"},
        {"kind": "click", "path": "/contact", "button": "send_enquiry"},
        {"kind": "search", "path": "/", "query": "matcha", "results": 0},
    ], visit="visit-aaaa1", ua=PHONE_UA)
    await send(client, [
        {"kind": "page", "path": "/products/wafer"},
        {"kind": "page", "path": "/"},
        {"kind": "search", "path": "/", "query": "matcha", "results": 0},
    ], visit="visit-bbbb2")
    await make_user("admin@kjsindia.com", role="admin")
    await login(client, "admin@kjsindia.com")
    r = await client.get(REPORT, params={"days": 7})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["totals"] == {"visits": 2, "page_views": 3, "product_views": 2, "searches": 2, "enquiries_sent": 1}
    assert d["top_products"] == [{"slug": "wafer", "name": "wafer", "views": 2, "visits": 2}]
    assert d["no_results"] == [{"query": "matcha", "count": 2}]
    assert d["funnel"] == {"viewed_product": 2, "added_to_enquiry": 1, "sent_enquiry": 1}
    assert d["buttons"][0]["clicks"] == 1 and len(d["buttons"]) == 8  # every counted button, zeros too
    assert {s["source"]: s["visits"] for s in d["sources"]} == {"Bing": 1, "Direct (typed or saved link)": 1}
    assert d["devices"] == {"mobile": 1, "tablet": 0, "desktop": 1}
    assert len(d["per_day"]) == 7 and d["per_day"][-1]["visits"] == 2


async def test_empty_report_is_zeros(client):
    await make_user("admin@kjsindia.com", role="admin")
    await login(client, "admin@kjsindia.com")
    d = (await client.get(REPORT)).json()
    assert d["days"] == 30 and d["totals"]["visits"] == 0 and d["top_products"] == []


async def test_range_longer_than_kept_is_refused(client):
    await make_user("admin@kjsindia.com", role="admin")
    await login(client, "admin@kjsindia.com")
    assert (await client.get(REPORT, params={"days": 400})).status_code == 422


async def test_employee_cannot_see_report(client):
    await make_user("e@kjsindia.com")
    await login(client, "e@kjsindia.com")
    assert (await client.get(REPORT)).status_code == 403


async def test_employee_with_permission_can_see_report(client):
    await make_user("e@kjsindia.com", permissions=["insights.view"])
    await login(client, "e@kjsindia.com")
    assert (await client.get(REPORT)).status_code == 200


async def test_report_needs_login(client):
    assert (await client.get(REPORT)).status_code == 401


async def test_report_hidden_when_area_off(client, monkeypatch):
    monkeypatch.setenv("KJS__MODULES__SITE_INSIGHTS", "off")
    ini.reload_now()
    await make_user("admin@kjsindia.com", role="admin")
    await login(client, "admin@kjsindia.com")
    r = await client.get(REPORT)
    assert r.status_code == 404 and r.json()["code"] == "module_off"


def test_insights_needs_analytics(monkeypatch):
    monkeypatch.setenv("KJS__MODULES__ANALYTICS", "off")
    monkeypatch.setenv("KJS__MODULES__SITE_INSIGHTS", "on")
    assert ini.reload_now().modules.site_insights == "on"  # refused: the last good settings stay
    assert ini.cfg().modules.analytics == "on"
