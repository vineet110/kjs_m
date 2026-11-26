"""Website insights: the website's tracker (no login) and Reports > Website insights (insights.view)."""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select, update

from app.core.config import ini
from app.core.database import AsyncSessionLocal
from app.models.catalog import Category, Product
from app.models.site_event import SiteEvent
from app.services import site_insights_service as svc
from tests.conftest import login, make_user

URL = "/api/v1/public/insights/events"
REPORT = "/api/v1/admin/site-insights"
PHONE_UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) Mobile/15E148 Safari/604.1"
DESKTOP_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"


@pytest.fixture(autouse=True)
async def setup():
    svc._last_cleanup = 0.0  # every test starts as if the API just started
    async with AsyncSessionLocal() as db:  # conftest adds the "coffee" category
        cat = await db.scalar(select(Category.id).where(Category.slug == "coffee"))
        db.add_all([Product(category_id=cat, slug=s, name=n) for s, n in
                    (("instant-coffee", "Instant Coffee"), ("wafer", "Wafer"))])
        await db.commit()


async def send(client, events, visit="visit-0001", ua=DESKTOP_UA):
    return await client.post(URL, json={"visit_id": visit, "events": events}, headers={"user-agent": ua})


async def saved() -> list[SiteEvent]:
    async with AsyncSessionLocal() as db:
        return list((await db.scalars(select(SiteEvent).order_by(SiteEvent.id))).all())


def setting(monkeypatch, **values):
    for k, v in values.items():
        monkeypatch.setenv(f"KJS__SITE_INSIGHTS__{k.upper()}", str(v))
    ini.reload_now()


async def as_admin(client):
    await make_user("admin@kjsindia.com", role="admin")
    await login(client, "admin@kjsindia.com")


# ---------- The tracker ----------
async def test_page_search_click_are_saved(client):
    r = await send(client, [
        {"kind": "page", "path": "/products/instant-coffee?x=1", "referrer": "https://www.google.co.in/search?q=a"},
        {"kind": "search", "path": "/", "query": "  Instant  COFFEE ", "results": 3},
        {"kind": "click", "path": "/products/instant-coffee", "button": "add_to_enquiry"},
    ], ua=PHONE_UA)
    assert r.status_code == 204, r.text
    page, search, click = await saved()
    assert (page.path, page.product_slug, page.source, page.device) == (
        "/products/instant-coffee", "instant-coffee", "Google", "mobile")
    assert (search.query, search.results) == ("instant coffee", 3)
    assert (click.button, click.product_slug) == ("add_to_enquiry", "instant-coffee")


async def test_unknown_addresses_are_saved_as_other(client):
    await send(client, [
        {"kind": "page", "path": "/products/someone@example.com"},  # not a real product
        {"kind": "page", "path": "/categories/coffee"},
        {"kind": "page", "path": "/ai"},  # a two-letter page is not a language
        {"kind": "page", "path": "/contact/"},
    ])
    rows = await saved()
    assert [(r.path, r.product_slug, r.category_slug) for r in rows] == [
        ("other", None, None), ("/categories/coffee", None, "coffee"), ("other", None, None), ("/contact", None, None)]


async def test_phone_numbers_and_emails_are_hidden(client):
    await send(client, [
        {"kind": "search", "path": "/", "query": "call me +91 98765-43210", "results": 0},
        {"kind": "search", "path": "/", "query": "buyer@example.com wafers", "results": 0},
        {"kind": "search", "path": "/", "query": "801", "results": 1},  # an item number stays
    ])
    assert [r.query for r in await saved()] == ["call me ***", "*** wafers", "801"]


async def test_dropped_events_do_not_sink_the_batch(client):
    r = await send(client, [
        {"kind": "click", "path": "/", "button": "made_up"},  # not a counted button
        {"kind": "search", "path": "/", "query": "a", "results": 0},  # shorter than min_search_chars
        {"kind": "search", "path": "/", "query": "wa\x00fer", "results": 1},  # NUL: Postgres refuses it
        {"kind": "page", "path": "/"},
    ])
    assert r.status_code == 204
    rows = await saved()
    assert [(x.kind, x.path, x.query) for x in rows] == [("search", "/", "wafer"), ("page", "/", None)]


async def test_robots_and_staff_are_not_counted(client):
    assert (await send(client, [{"kind": "page", "path": "/"}], ua="Googlebot/2.1")).status_code == 204
    assert (await send(client, [{"kind": "page", "path": "/"}], ua="")).status_code == 204
    client.cookies.set("kjs_session", "anything")
    assert (await send(client, [{"kind": "page", "path": "/"}])).status_code == 204
    assert await saved() == []


async def test_area_off_saves_nothing(client, monkeypatch):
    monkeypatch.setenv("KJS__MODULES__SITE_INSIGHTS", "off")
    ini.reload_now()
    assert (await send(client, [{"kind": "page", "path": "/"}])).status_code == 204
    assert await saved() == []
    assert (await client.get("/api/v1/public/config")).json()["insights"]["on"] is False


async def test_bad_input_is_refused(client):
    assert (await send(client, [{"kind": "page", "path": "https://evil.example/x"}])).status_code == 422
    assert (await send(client, [{"kind": "page", "path": "//evil.example"}])).status_code == 422
    assert (await send(client, [{"kind": "hack", "path": "/"}])).status_code == 422
    assert (await send(client, [{"kind": "page", "path": "/"}], visit="x")).status_code == 422
    assert (await send(client, [])).status_code == 422


async def test_extra_events_are_dropped_not_refused(client, monkeypatch):
    setting(monkeypatch, max_events_per_send=2)
    assert (await send(client, [{"kind": "page", "path": "/"}] * 3)).status_code == 204
    assert len(await saved()) == 2


async def test_rate_limits_drop_quietly(client, monkeypatch):
    setting(monkeypatch, sends_per_minute_per_visit=5, sends_per_minute_per_network=30)
    for _ in range(6):  # one visit: the 6th send is over its limit
        assert (await send(client, [{"kind": "page", "path": "/"}])).status_code == 204
    assert len(await saved()) == 5
    for i in range(30):  # many visits on one network (a mobile network): only the network cap stops them
        assert (await send(client, [{"kind": "page", "path": "/"}], visit=f"other-visit-{i}")).status_code == 204
    assert len(await saved()) == 5 + 25  # the network had 5 sends already


async def test_old_events_are_deleted(client):
    await send(client, [{"kind": "page", "path": "/"}, {"kind": "page", "path": "/contact"}])
    async with AsyncSessionLocal() as db:
        old = datetime.now(timezone.utc) - timedelta(days=200)  # keep_days = 180
        await db.execute(update(SiteEvent).where(SiteEvent.path == "/").values(at=old))
        await db.commit()
        assert await svc.cleanup(db, force=True) == 1
    assert len(await saved()) == 1


async def test_failed_cleanup_is_tried_again(monkeypatch):
    class Broken:
        async def execute(self, *_):
            raise RuntimeError("database gone")

        async def rollback(self):
            pass

    assert await svc.cleanup(Broken()) == 0  # logged, never raised
    assert svc._last_cleanup == 0.0  # not marked done: the next call tries again
    async with AsyncSessionLocal() as db:
        await svc.cleanup(db)
    assert svc._last_cleanup > 0


async def test_cleanup_job_runs_with_the_area_off(monkeypatch):
    from app.jobs.runner import run_job, should_run
    monkeypatch.setenv("KJS__MODULES__SITE_INSIGHTS", "off")
    ini.reload_now()
    assert should_run("site_events_cleanup", working=False)  # any time, whatever the switch says
    assert await run_job("site_events_cleanup") == {"deleted": 0}


def test_helpers():
    assert svc.split_path("/") == ("/", None, None)
    assert svc.split_path("/categories/coffee/") == ("/categories/coffee", None, "coffee")
    assert svc.source_of("https://l.facebook.com/x") == "Facebook"
    assert svc.source_of("https://www.google.co.in/") == "Google"
    assert svc.source_of("https://google.example.org/") == "google.example.org"  # not Google
    assert svc.source_of("https://t.co/abc") == "X (Twitter)"
    assert svc.source_of("https://www.example.org/page?email=a@b.c") == "example.org"
    assert svc.source_of("not a link") is None
    assert svc.device_of("Mozilla/5.0 (Linux; Android 14; SM-X200) Safari") == "tablet"


# ---------- Settings ----------
def test_ranges_must_fit_the_days_kept(monkeypatch):
    # Env values that don't fit together: each one that keeps the section valid applies, the one that
    # breaks the rule is refused (#113: one bad env value never cancels the good ones)
    setting(monkeypatch, keep_days=30, default_days=60)
    s = ini.cfg().site_insights
    assert s.keep_days == 30 and s.default_days <= s.keep_days  # default_days=60 refused, never a broken range
    setting(monkeypatch, keep_days=30, default_days=30, day_choices=90)
    s = ini.cfg().site_insights
    assert s.keep_days == 30 and any(d <= s.keep_days for d in s.day_choices)  # day_choices=90 refused
    setting(monkeypatch, keep_days=30, default_days=30, day_choices="7, 90")
    assert ini.cfg().site_insights.keep_days == 30  # one choice fits: fine (the screen hides 90)


def test_insights_needs_analytics(monkeypatch):
    monkeypatch.setenv("KJS__MODULES__ANALYTICS", "off")
    monkeypatch.setenv("KJS__MODULES__SITE_INSIGHTS", "on")
    assert ini.reload_now().modules.site_insights == "on"  # refused: the last good settings stay
    assert ini.cfg().modules.analytics == "on"


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
        {"kind": "page", "path": "/", "referrer": "https://www.google.com/"},  # not its first page: not a source
        {"kind": "search", "path": "/", "query": "matcha", "results": 0},
    ], visit="visit-bbbb2")
    await as_admin(client)
    r = await client.get(REPORT, params={"days": 7})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["totals"] == {"visits": 2, "page_views": 3, "product_views": 2, "searches": 2,
                           "searches_no_results": 2, "enquiries_sent": 1}
    assert d["top_products"] == [{"slug": "wafer", "name": "Wafer", "views": 2, "visits": 2}]
    assert d["no_results"] == [{"query": "matcha", "count": 2}]
    assert d["buttons"][0]["clicks"] == 1 and len(d["buttons"]) == 8  # every counted button, zeros too
    assert {s["source"]: s["visits"] for s in d["sources"]} == {"Bing": 1, svc.DIRECT: 1}
    assert d["devices"] == {"mobile": 1, "tablet": 0, "desktop": 1}
    assert "funnel" not in d


async def test_totals_not_cut_by_top_n(client, monkeypatch):
    setting(monkeypatch, top_n=3)
    for i in range(5):
        await send(client, [{"kind": "page", "path": "/", "referrer": f"https://site{i}.example/"},
                            {"kind": "search", "path": "/", "query": f"thing {i}", "results": 0}], visit=f"visit-{i:05}")
    await as_admin(client)
    d = (await client.get(REPORT)).json()
    assert d["totals"]["searches_no_results"] == 5 and len(d["no_results"]) == 3
    by = {s["source"]: s["visits"] for s in d["sources"]}
    assert by[svc.DIRECT] == 0 and by["Other sites"] == 2 and sum(by.values()) == 5


async def test_days_are_whole_ist_days(client):
    # 10:00 IST on 18 Nov: "7 days" = 12 to 18 Nov, from midnight IST
    now = datetime(2026, 11, 18, 4, 30, tzinfo=timezone.utc)
    start = svc.range_start(7, "Asia/Kolkata", now)
    assert start.isoformat() == "2026-11-12T00:00:00+05:30"
    await send(client, [{"kind": "page", "path": "/"}, {"kind": "page", "path": "/contact"}])
    async with AsyncSessionLocal() as db:
        await db.execute(update(SiteEvent).where(SiteEvent.path == "/").values(at=start + timedelta(minutes=1)))
        await db.execute(update(SiteEvent).where(SiteEvent.path == "/contact").values(at=start - timedelta(minutes=1)))
        await db.commit()
        d = await svc.report(db, 7, now=now)
    assert [x["day"] for x in d["per_day"]][0] == "2026-11-12" and len(d["per_day"]) == 7
    assert d["per_day"][0]["views"] == 1 and d["totals"]["page_views"] == 1  # tiles and chart agree


async def test_empty_report_is_zeros(client):
    await as_admin(client)
    d = (await client.get(REPORT)).json()
    assert d["days"] == 30 and d["totals"]["visits"] == 0 and d["top_products"] == []


async def test_range_longer_than_kept_is_refused(client):
    await as_admin(client)
    r = await client.get(REPORT, params={"days": 400})
    assert r.status_code == 422 and r.json()["code"] == "bad_range"


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
    await as_admin(client)
    r = await client.get(REPORT)
    assert r.status_code == 404 and r.json()["code"] == "module_off"
