"""Website insights: save what website visitors do (page views, searches, button clicks) and count it for
Reports > Website insights.

Privacy (DPDP Act): no IP is saved (only its hash is used, in memory, for the rate limit), no cookie is set,
only known pages are saved (any other address becomes "other"), only the referring site's name is kept, and
phone numbers or emails typed into the search box are hidden before saving. Other search words are kept as
typed. Logged-in staff and robots are not counted.
Settings: config/site_insights.ini. Switch: modules.ini site_insights (off stops collecting; old rows are still
deleted after keep_days).
"""
import logging
import re
import time
from datetime import datetime, time as dtime, timedelta, timezone
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from sqlalchemy import delete, distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config.ini import cfg
from app.core.database import AsyncSessionLocal
from app.core.modules import running
from app.core.rate_limit import insights_network_limiter, insights_visit_limiter
from app.jobs.runner import job
from app.models.catalog import Category, Product
from app.models.site_event import SiteEvent

log = logging.getLogger(__name__)

# Privacy rules, not tunables: a typo in an ini must never start saving phone numbers (prompt.md 3.11.iv).
# 7+ digits, with spaces, dashes, dots or brackets between them, is treated as a phone number. Item numbers
# ("801", "600A") are shorter, so they stay readable.
PHONE = re.compile(r"\+?\d(?:[\s\-.()]*\d){6,}")
EMAIL = re.compile(r"\S+@\S+")
HIDDEN = "***"
OTHER_PAGE = "other"  # saved instead of an address that isn't a known page (it could carry anything)
DIRECT = "Direct (typed or saved link)"

# Where a visit came from: the site's name (the part before .com, .co.in, ...) -> a friendly name.
# Anything else is saved as the site's address without www (example.org).
KNOWN_SOURCES = {
    "google": "Google", "bing": "Bing", "yahoo": "Yahoo", "duckduckgo": "DuckDuckGo", "facebook": "Facebook",
    "instagram": "Instagram", "linkedin": "LinkedIn", "youtube": "YouTube", "whatsapp": "WhatsApp",
    "twitter": "X (Twitter)", "x": "X (Twitter)", "t": "X (Twitter)", "chatgpt": "ChatGPT",
}
# Second-level parts of country endings: google.co.in -> the site's name is "google", not "co"
SECOND_LEVEL = {"co", "com", "org", "net", "ac", "gov", "edu"}

_last_cleanup = 0.0  # time.monotonic() of the last successful delete of old rows (0 = not yet since start-up)


# ---------- Cleaning what the browser sends ----------
def _plain(s: str | None) -> str:
    """Without NUL characters: Postgres refuses them, and one would make the whole batch fail."""
    return (s or "").replace("\x00", "")


def is_robot(user_agent: str) -> bool:
    ua = (user_agent or "").lower()
    return not ua or any(w in ua for w in cfg().site_insights.bot_words)


def device_of(user_agent: str) -> str:
    ua = (user_agent or "").lower()
    if "ipad" in ua or "tablet" in ua or ("android" in ua and "mobile" not in ua):
        return "tablet"
    if "mobi" in ua or "iphone" in ua or "android" in ua:
        return "mobile"
    return "desktop"


def clean_query(q: str) -> str:
    """Lowercase, single spaces, phone numbers and emails hidden, at most 100 characters."""
    q = EMAIL.sub(HIDDEN, _plain(q))
    q = PHONE.sub(HIDDEN, q)
    return " ".join(q.lower().split())[:100]


def site_name(host: str) -> str:
    """'www.google.co.in' -> 'google', 'l.facebook.com' -> 'facebook', 'google.example.org' -> 'example'."""
    labels = host.split(".")
    if len(labels) >= 3 and len(labels[-1]) == 2 and labels[-2] in SECOND_LEVEL:
        labels = labels[:-2]  # google.co.in
    elif len(labels) >= 2:
        labels = labels[:-1]  # google.com
    return labels[-1] if labels else ""


def source_of(referrer: str | None) -> str | None:
    """'https://www.google.co.in/search?q=..' -> 'Google'. Only the site's name is kept, never the full link
    (a link can carry what someone searched for, or an email)."""
    if not referrer:
        return None
    try:
        host = (urlsplit(_plain(referrer)).hostname or "").lower()
    except ValueError:
        return None
    if not host or "." not in host:
        return None
    return KNOWN_SOURCES.get(site_name(host)) or host.removeprefix("www.")[:100]


def split_path(path: str) -> tuple[str, str | None, str | None]:
    """'/products/instant-coffee?x=1' -> ('/products/instant-coffee', 'instant-coffee', None). Anything after
    ? or # is dropped, so the same page always counts as one. The site is English only, with no language part
    in its addresses (frontend proxy.ts localePrefix 'never'); add a rule here if a second language comes (D2).
    The address is NOT checked here: see record(), which keeps only known pages."""
    p = re.split(r"[?#]", _plain(path), maxsplit=1)[0]
    p = p.rstrip("/") or "/"
    parts = p.strip("/").split("/")
    product = parts[1] if len(parts) == 2 and parts[0] == "products" else None
    category = parts[1] if len(parts) == 2 and parts[0] == "categories" else None
    return p, product, category


async def _known_slugs(db: AsyncSession, model, slugs: set[str]) -> set[str]:
    """The slugs that are real products / categories (shown or hidden). Made-up ones are not saved."""
    if not slugs:
        return set()
    return set((await db.scalars(select(model.slug).where(model.slug.in_(slugs)))).all())


# ---------- Saving ----------
async def record(db: AsyncSession, visit_id: str, events: list[dict], *, user_agent: str, is_staff: bool,
                 rate_key: str | None) -> int:
    """Save one batch from a browser. Returns how many events were saved (0 when nothing is counted: staff,
    robots, area off, or over a rate limit). Never raises for any of those: the website gets 204 either way."""
    if not running("site_insights") or is_staff or is_robot(user_agent):
        return 0
    # Two limits: per visit (a stuck page or a script), and a loose one per network (many visitors on one
    # mobile network share one address, so that one must stay high)
    if insights_visit_limiter.blocked(visit_id) or insights_network_limiter.blocked(rate_key):
        return 0
    insights_visit_limiter.hit(visit_id)
    insights_network_limiter.hit(rate_key)

    s = cfg().site_insights
    device = device_of(user_agent)
    buttons = set(s.buttons)
    pages = set(s.pages)
    batch = [(e, *split_path(e["path"])) for e in events[: s.max_events_per_send]]  # extra events are dropped
    products = await _known_slugs(db, Product, {p for *_, p, _c in batch if p})
    categories = await _known_slugs(db, Category, {c for *_, c in batch if c})

    rows = []
    for e, path, product, category in batch:
        product = product if product in products else None
        category = category if category in categories else None
        if not (product or category or path in pages):
            path = OTHER_PAGE  # an unknown address could carry anything (an email, a name): not saved as is
        row = SiteEvent(visit_id=visit_id, kind=e["kind"], path=path, device=device)
        if e["kind"] == "page":
            row.product_slug, row.category_slug = product, category
            row.source = source_of(e.get("referrer"))
        elif e["kind"] == "search":
            q = clean_query(e.get("query") or "")
            if len(q) < s.min_search_chars:
                continue
            row.query, row.results = q, e.get("results")
        else:  # click
            if _plain(e.get("button")) not in buttons:
                continue  # not a button we count (an old page, or someone sending made-up names)
            row.button, row.product_slug = e["button"], product
        rows.append(row)
    db.add_all(rows)
    await db.commit()
    await cleanup(db)  # never raises: the events above are saved whatever happens here
    return len(rows)


async def cleanup(db: AsyncSession, force: bool = False) -> int:
    """Delete events older than keep_days, at most every cleanup_every_hours. Called on sends, on the report,
    by the background job and at start-up. Never raises: a failed delete is logged and tried again next time
    (it only counts as done once it has worked)."""
    global _last_cleanup
    s = cfg().site_insights
    now = time.monotonic()
    if not force and _last_cleanup and now - _last_cleanup < s.cleanup_every_hours * 3600:
        return 0
    cutoff = datetime.now(timezone.utc) - timedelta(days=s.keep_days)
    try:
        n = (await db.execute(delete(SiteEvent).where(SiteEvent.at < cutoff))).rowcount or 0
        await db.commit()
    except Exception:
        log.exception("site_insights.cleanup_failed")
        await db.rollback()
        return 0
    _last_cleanup = now
    if n:
        log.info("site_insights.cleanup", extra={"deleted": n})
    return n


# Not tied to the site_insights area: switching collection off must not keep old rows past keep_days
@job("site_events_cleanup", any_time=True)
async def cleanup_job(db: AsyncSession) -> dict:
    return {"deleted": await cleanup(db)}


async def cleanup_at_start() -> None:
    """Once when the API starts (background jobs may be switched off in app.ini)."""
    async with AsyncSessionLocal() as db:
        await cleanup(db, force=True)


# ---------- The report ----------
def range_start(days: int, tz: str, now: datetime | None = None) -> datetime:
    """Start of the report: midnight (IST) `days - 1` days ago, so "7 days" = today and the 6 days before,
    and the tiles and the daily chart count exactly the same days."""
    zone = ZoneInfo(tz)
    today = (now or datetime.now(timezone.utc)).astimezone(zone).date()
    return datetime.combine(today - timedelta(days=days - 1), dtime(0), tzinfo=zone)


async def report(db: AsyncSession, days: int, now: datetime | None = None) -> dict:
    """Numbers for the last `days` calendar days. Real rows only: an empty table shows zeros (backlog D6)."""
    await cleanup(db)
    s = cfg().site_insights
    tz = cfg().app.timezone
    top = s.top_n
    since = range_start(days, tz, now)
    E = SiteEvent
    in_range = E.at >= since
    visit = distinct(E.visit_id)

    async def rows(q):
        return (await db.execute(q)).all()

    # Totals
    visits, page_views, product_views, searches, no_result_searches = (await db.execute(select(
        func.count(visit),
        func.count().filter(E.kind == "page"),
        func.count().filter(E.kind == "page", E.product_slug.is_not(None)),
        func.count().filter(E.kind == "search"),
        func.count().filter(E.kind == "search", E.results == 0),
    ).where(in_range))).one()

    # Per day (IST): visits and page views, every day shown (zeros too)
    day = func.date(func.timezone(tz, E.at))
    by_day = {d.isoformat(): (v, p) for d, v, p in await rows(
        select(day, func.count(visit), func.count().filter(E.kind == "page")).where(in_range).group_by(day))}
    first = since.date()
    per_day = []
    for i in range(days):
        d = (first + timedelta(days=i)).isoformat()
        v, p = by_day.get(d, (0, 0))
        per_day.append({"day": d, "visits": v, "views": p})

    # Top products (views, and in how many visits), with today's product names
    prods = await rows(select(E.product_slug, func.count(), func.count(visit))
                       .where(in_range, E.kind == "page", E.product_slug.is_not(None))
                       .group_by(E.product_slug).order_by(func.count().desc(), E.product_slug).limit(top))
    names = dict((await db.execute(select(Product.slug, Product.name)
                                   .where(Product.slug.in_([p[0] for p in prods])))).all()) if prods else {}
    top_products = [{"slug": sl, "name": names.get(sl, sl), "views": n, "visits": v} for sl, n, v in prods]

    top_pages = [{"path": p, "views": n} for p, n in await rows(
        select(E.path, func.count()).where(in_range, E.kind == "page")
        .group_by(E.path).order_by(func.count().desc(), E.path).limit(top))]

    # Searches: the most typed, and those that found nothing (products buyers want that we don't show)
    top_searches = [{"query": q, "count": n, "results": r} for q, n, r in await rows(
        select(E.query, func.count(), func.min(E.results)).where(in_range, E.kind == "search")
        .group_by(E.query).order_by(func.count().desc(), E.query).limit(top))]
    no_results = [{"query": q, "count": n} for q, n in await rows(
        select(E.query, func.count()).where(in_range, E.kind == "search", E.results == 0)
        .group_by(E.query).order_by(func.count().desc(), E.query).limit(top))]

    # Buttons: every counted button, zeros too, most clicked first
    clicks = dict(await rows(select(E.button, func.count()).where(in_range, E.kind == "click").group_by(E.button)))
    buttons = sorted(({"button": b, "clicks": clicks.get(b, 0)} for b in s.buttons), key=lambda x: -x["clicks"])

    # Where visits came from: each visit counts once, under the source of its first page in the range (the
    # website sends a source only with a visit's first page). No outside site = Direct. A visit that started
    # before the range counts as Direct (its first page is outside the range).
    first_page = (select(E.visit_id, E.source).where(in_range, E.kind == "page")
                  .distinct(E.visit_id).order_by(E.visit_id, E.at, E.id).subquery())
    by_source = dict(await rows(select(first_page.c.source, func.count())
                                .where(first_page.c.source.is_not(None)).group_by(first_page.c.source)))
    ranked = sorted(by_source.items(), key=lambda x: (-x[1], x[0]))  # outside sites, most visits first
    sources = [{"source": DIRECT, "visits": max(visits - sum(by_source.values()), 0)}]  # always shown
    sources += [{"source": k, "visits": v} for k, v in ranked[:top]]
    if rest := sum(v for _, v in ranked[top:]):
        sources.append({"source": "Other sites", "visits": rest})
    sources.sort(key=lambda x: -x["visits"])  # stable: Direct stays first among equals

    devices = {d: 0 for d in ("mobile", "tablet", "desktop")} | dict(
        await rows(select(E.device, func.count(visit)).where(in_range).group_by(E.device)))

    return {
        "days": days, "default_days": s.default_days, "day_choices": s.day_choices, "keep_days": s.keep_days,
        "totals": {"visits": visits, "page_views": page_views, "product_views": product_views,
                   "searches": searches, "searches_no_results": no_result_searches,
                   "enquiries_sent": clicks.get("send_enquiry", 0)},
        "per_day": per_day, "top_products": top_products, "top_pages": top_pages,
        "top_searches": top_searches, "no_results": no_results, "buttons": buttons,
        "sources": sources, "devices": devices,
    }
