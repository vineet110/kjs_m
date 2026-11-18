"""Website insights: save what website visitors do (page views, searches, button clicks) and count it for
Reports > Website insights.

Privacy (DPDP Act): nothing here can name a person. No IP is saved (only its hash is used, in memory, for the
rate limit), no cookie is set, and phone numbers or emails typed into the search box are hidden before saving.
Logged-in staff and robots are not counted. Settings: config/site_insights.ini. Switch: modules.ini site_insights.
"""
import logging
import re
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from sqlalchemy import case, delete, distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config.ini import cfg
from app.core.modules import running
from app.core.rate_limit import insights_limiter
from app.models.catalog import Product
from app.models.site_event import SiteEvent

log = logging.getLogger(__name__)

# Privacy rules, not tunables: a typo in an ini must never start saving phone numbers (prompt.md 3.11.iv).
# 7+ digits, with spaces, dashes, dots or brackets between them, is treated as a phone number. Item numbers
# ("801", "600A") are shorter, so they stay readable.
PHONE = re.compile(r"\+?\d(?:[\s\-.()]*\d){6,}")
EMAIL = re.compile(r"\S+@\S+")
HIDDEN = "***"

# Where a visit came from: a friendly name for well-known sites, else the site's own name (example.com)
KNOWN_SOURCES = {
    "google": "Google", "bing": "Bing", "yahoo": "Yahoo", "duckduckgo": "DuckDuckGo", "facebook": "Facebook",
    "instagram": "Instagram", "linkedin": "LinkedIn", "youtube": "YouTube", "whatsapp": "WhatsApp",
    "t.co": "X (Twitter)", "twitter": "X (Twitter)", "x.com": "X (Twitter)", "chatgpt": "ChatGPT",
}

_last_cleanup = 0.0  # time.monotonic() of the last delete of old rows (0 = not yet since start-up)


# ---------- Cleaning what the browser sends ----------
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
    q = EMAIL.sub(HIDDEN, q)
    q = PHONE.sub(HIDDEN, q)
    return " ".join(q.lower().split())[:100]


def source_of(referrer: str | None) -> str | None:
    """'https://www.google.co.in/search?q=..' -> 'Google'. Only the site's name is kept, never the full link
    (a link can carry what someone searched for, or an email)."""
    if not referrer:
        return None
    try:
        host = (urlsplit(referrer).hostname or "").lower()
    except ValueError:
        return None
    host = host.removeprefix("www.").removeprefix("m.").removeprefix("l.")
    if not host:
        return None
    for word, name in KNOWN_SOURCES.items():
        if host == word or host.startswith(word + ".") or ("." + word + ".") in ("." + host + "."):
            return name
    return host[:100]


def split_path(path: str) -> tuple[str, str | None, str | None]:
    """'/en/products/instant-coffee?x=1' -> ('/products/instant-coffee', 'instant-coffee', None).
    The language part and anything after ? or # are dropped, so the same page always counts as one."""
    p = re.split(r"[?#]", path, maxsplit=1)[0]
    p = re.sub(r"^/[a-z]{2}(?=/|$)", "", p) or "/"
    p = p.rstrip("/") or "/"
    parts = p.strip("/").split("/")
    product = parts[1] if len(parts) == 2 and parts[0] == "products" else None
    category = parts[1] if len(parts) == 2 and parts[0] == "categories" else None
    return p[:300], product, category


# ---------- Saving ----------
async def record(db: AsyncSession, visit_id: str, events: list[dict], *, user_agent: str, is_staff: bool,
                 rate_key: str | None) -> int:
    """Save one batch from a browser. Returns how many events were saved (0 when nothing is counted).
    Raises 429 when one network sends too often."""
    if not running("site_insights") or is_staff or is_robot(user_agent):
        return 0
    insights_limiter.check(rate_key)
    s = cfg().site_insights
    device = device_of(user_agent)
    buttons = set(s.buttons)
    rows = []
    for e in events[: s.max_events_per_send]:
        path, product, category = split_path(e["path"])
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
            if e.get("button") not in buttons:
                continue  # not a button we count (an old page, or someone sending made-up names)
            row.button, row.product_slug = e["button"], product
        rows.append(row)
    db.add_all(rows)
    await db.commit()
    await cleanup(db)
    return len(rows)


async def cleanup(db: AsyncSession, force: bool = False) -> int:
    """Delete events older than keep_days. Runs at most every cleanup_every_hours (it is called on every send
    and report, because background jobs may be switched off)."""
    global _last_cleanup
    s = cfg().site_insights
    now = time.monotonic()
    if not force and _last_cleanup and now - _last_cleanup < s.cleanup_every_hours * 3600:
        return 0
    _last_cleanup = now
    cutoff = datetime.now(timezone.utc) - timedelta(days=s.keep_days)
    n = (await db.execute(delete(SiteEvent).where(SiteEvent.at < cutoff))).rowcount or 0
    await db.commit()
    if n:
        log.info("site_insights.cleanup", extra={"deleted": n})
    return n


# ---------- The report ----------
async def report(db: AsyncSession, days: int) -> dict:
    """Numbers for the last `days` days. Real rows only: an empty table shows zeros (backlog D6)."""
    await cleanup(db)
    s = cfg().site_insights
    tz = cfg().app.timezone
    top = s.top_n
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=days)
    E = SiteEvent
    in_range = E.at >= since
    visit = distinct(E.visit_id)

    async def rows(q):
        return (await db.execute(q)).all()

    # Totals
    visits, page_views, product_views, searches = (await db.execute(select(
        func.count(visit),
        func.count().filter(E.kind == "page"),
        func.count().filter(E.kind == "page", E.product_slug.is_not(None)),
        func.count().filter(E.kind == "search"),
    ).where(in_range))).one()

    # Per day (IST): visits and page views, every day shown (zeros too)
    day = func.date(func.timezone(tz, E.at))
    by_day = {d.isoformat(): (v, p) for d, v, p in await rows(
        select(day, func.count(visit), func.count().filter(E.kind == "page")).where(in_range).group_by(day))}
    first = since.astimezone(ZoneInfo(tz)).date()
    per_day = []
    for i in range(days + 1):
        d = (first + timedelta(days=i)).isoformat()
        v, p = by_day.get(d, (0, 0))
        per_day.append({"day": d, "visits": v, "views": p})
    per_day = per_day[-days:]  # exactly `days` days, ending today

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

    # Funnel: visits that viewed a product -> added one to the enquiry -> sent the enquiry
    viewed, added, sent = (await db.execute(select(
        func.count(distinct(case((E.product_slug.is_not(None) & (E.kind == "page"), E.visit_id)))),
        func.count(distinct(case((E.button == "add_to_enquiry", E.visit_id)))),
        func.count(distinct(case((E.button == "send_enquiry", E.visit_id)))),
    ).where(in_range))).one()

    # Where visits came from (the first page of a visit carries it). The rest came straight in.
    src = await rows(select(E.source, func.count(visit)).where(in_range, E.source.is_not(None))
                     .group_by(E.source).order_by(func.count(visit).desc(), E.source).limit(top))
    from_sites = sum(n for _, n in src)
    sources = [{"source": "Direct (typed or saved link)", "visits": max(visits - from_sites, 0)}] + \
              [{"source": sname, "visits": n} for sname, n in src]
    sources.sort(key=lambda x: -x["visits"])

    devices = {d: 0 for d in ("mobile", "tablet", "desktop")} | dict(
        await rows(select(E.device, func.count(visit)).where(in_range).group_by(E.device)))

    return {
        "days": days, "day_choices": s.day_choices, "keep_days": s.keep_days,
        "totals": {"visits": visits, "page_views": page_views, "product_views": product_views,
                   "searches": searches, "enquiries_sent": clicks.get("send_enquiry", 0)},
        "per_day": per_day, "top_products": top_products, "top_pages": top_pages,
        "top_searches": top_searches, "no_results": no_results, "buttons": buttons,
        "funnel": {"viewed_product": viewed, "added_to_enquiry": added, "sent_enquiry": sent},
        "sources": sources, "devices": devices,
    }

