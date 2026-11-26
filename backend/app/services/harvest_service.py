"""Lead Harvester service: connectors for API, Open Data, RSS, and Scraper,
and scheduler orchestration.
"""
from __future__ import annotations

import asyncio
import csv
import io
import json
import logging
import re
import urllib.parse
import urllib.robotparser
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.jobs.runner import job
from app.models.harvest import HarvestRun, HarvestSource
from app.services.harvest_net import harvest_setting, safe_get
from app.services.harvest_filter import (
    active_category_slugs,
    EMAIL_REGEX,
    PHONE_DIGITS_REGEX,
    filter_single_record,
    save_accepted_records,
)

log = logging.getLogger("app.harvest")

BOT_USER_AGENT = "KJS-Lead-Harvester/1.0 (+https://kjsindia.com)"
# A phone number in free text (scraped pages, RSS). Format rules, not tunables: 9 digits keeps out pin codes,
# dates and quantities; 13 is the longest real number we expect (+91 and 10 digits is 12), so a number with
# a time, a year or a second number glued on is never taken whole.
PHONE_MIN_DIGITS, PHONE_MAX_DIGITS = 9, 13
# A digit group that touches a letter ("9am", "A12", "2g") is never part of a phone
_DIGIT_GROUP = re.compile(r"(?<![A-Za-z\d])\+?\d+(?![\dA-Za-z])")
_GROUP_JOIN = re.compile(r"[\s.()-]{1,2}")  # what may sit between the groups of one number ("+91 98765-43210")


def find_phone(text: str) -> str:
    """The first phone in a text, or "". Digit groups that touch (a space, dot, dash or bracket between) form
    a run. A number starts with "+" or a group of 3+ digits (not "12" of "Order 12"). Inside a run, every
    start is tried: the first stretch shaped like a phone wins (10 digits from 6-9, an Indian mobile; 11 with a
    trunk 0; 11 to 13 with "+"). Nothing else is guessed: free text has endless formats, and a wrong number is
    worse than none, so this takes the common shapes and never glues a year, pin code or time onto them. So "+91 98765 43210 10am" gives +91 98765 43210, "Since 1998 98765 43210" gives
    98765 43210, and "Mumbai 400001" gives nothing. A "+" always starts a new number."""
    runs: list[list[re.Match]] = []
    for g in _DIGIT_GROUP.finditer(text or ""):
        joined = runs and _GROUP_JOIN.fullmatch(text[runs[-1][-1].end():g.start()]) and not g.group().startswith("+")
        if joined:
            runs[-1].append(g)
        else:
            runs.append([g])
    for run in runs:
        for i in range(len(run)):
            if not run[i].group().startswith("+") and len(run[i].group()) < 3:
                continue
            digits = 0
            for j in range(i, len(run)):
                digits += len(run[j].group().lstrip("+"))
                if digits > PHONE_MAX_DIGITS:
                    break
                stretch = text[run[i].start():run[j].end()]
                first = stretch.lstrip("+")[:1]
                if ((digits == 10 and first in "6789") or (digits == 11 and first == "0")
                        or (11 <= digits <= 13 and stretch.startswith("+"))):
                    return stretch  # the first stretch shaped like a phone; no guessing beyond that
    return ""
# Every fetch goes through harvest_net.safe_get: https and public addresses only, redirects checked,
# API keys only from HARVEST_ settings (security fix after the PR #53 review).


# ---------------- Connectors ----------------

async def fetch_api_source(source: HarvestSource) -> list[dict]:
    """Fetch enquiries from an external REST API (e.g. IndiaMART, TradeIndia, data.gov.in)."""
    headers = {
        "User-Agent": BOT_USER_AGENT,
        "Accept": "application/json",
    }

    # API key from a server setting (the database stores ONLY its name). Checked again here, not only when
    # the source was saved: a bad name already in the database must never be read.
    token = ""
    if source.auth_env_var:
        try:
            token = harvest_setting(source.auth_env_var)  # refuses names without HARVEST_
        except ValueError as e:
            raise AppError(400, "bad_env_var", str(e)) from None

    resp = await safe_get(source.url, headers, api_key=token)
    resp.raise_for_status()
    data = resp.json()

    # Extract records list from common API response shapes
    raw_list: list[dict] = []
    if isinstance(data, list):
        raw_list = [item for item in data if isinstance(item, dict)]
    elif isinstance(data, dict):
        for key in ("data", "results", "enquiries", "records", "items", "leads"):
            val = data.get(key)
            if isinstance(val, list):
                raw_list = [item for item in val if isinstance(item, dict)]
                break
        if not raw_list and "query" not in data:
            # Single record response
            raw_list = [data]

    records: list[dict] = []
    for item in raw_list:
        records.append({
            "company": item.get("company") or item.get("buyer_company") or item.get("name") or "",
            "contact_name": item.get("contact_name") or item.get("sender_name") or item.get("contact") or "",
            "email": item.get("email") or item.get("sender_email") or "",
            "phone": item.get("phone") or item.get("mobile") or item.get("sender_mobile") or "",
            "country": item.get("country") or item.get("sender_country") or "India",
            "product": item.get("product") or item.get("product_name") or item.get("subject") or "",
            "message": item.get("message") or item.get("requirement") or item.get("query") or "",
            "source_url": source.url,
        })
    return records


async def fetch_open_data_source(source: HarvestSource) -> list[dict]:
    """Download CSV or JSON file from an open data portal (e.g. data.gov.in)."""
    resp = await safe_get(source.url, {"User-Agent": BOT_USER_AGENT})
    resp.raise_for_status()
    content_type = resp.headers.get("content-type", "").lower()
    body = resp.text

    records: list[dict] = []
    if "json" in content_type or source.url.lower().endswith(".json"):
        try:
            data = json.loads(body)
            items = data if isinstance(data, list) else data.get("records", data.get("data", []))
            for item in items:
                if isinstance(item, dict):
                    records.append({
                        "company": item.get("company", item.get("name", "")),
                        "contact_name": item.get("contact_name", item.get("contact", "")),
                        "email": item.get("email", ""),
                        "phone": str(item.get("phone", item.get("mobile", ""))),
                        "country": item.get("country", "India"),
                        "product": item.get("product", item.get("commodity", "")),
                        "message": item.get("message", item.get("details", "")),
                        "source_url": source.url,
                    })
            return records
        except json.JSONDecodeError:
            pass  # fall through to CSV

    # CSV parsing using standard library
    reader = csv.DictReader(io.StringIO(body))
    for row in reader:
        # Case-insensitive column lookup
        norm = {k.strip().lower(): (v.strip() if v else "") for k, v in row.items() if k}
        company = norm.get("company") or norm.get("buyer") or norm.get("name") or norm.get("organisation") or ""
        contact = norm.get("contact") or norm.get("contact_name") or norm.get("person") or ""
        email = norm.get("email") or norm.get("e-mail") or ""
        phone = norm.get("phone") or norm.get("mobile") or norm.get("telephone") or ""
        product = norm.get("product") or norm.get("commodity") or norm.get("item") or norm.get("category") or ""
        message = norm.get("requirement") or norm.get("message") or norm.get("details") or ""
        country = norm.get("country") or "India"

        records.append({
            "company": company,
            "contact_name": contact,
            "email": email,
            "phone": phone,
            "country": country,
            "product": product,
            "message": message,
            "source_url": source.url,
        })

    return records


async def fetch_rss_source(source: HarvestSource) -> list[dict]:
    """Fetch trade enquiry or tender RSS feed using standard library xml.etree."""
    resp = await safe_get(source.url, {"User-Agent": BOT_USER_AGENT})
    resp.raise_for_status()
    xml_text = resp.text

    root = ET.fromstring(xml_text)
    # Search for items (RSS) or entries (Atom)
    items = root.findall(".//item")
    if not items:
        # Atom feed namespace handling
        items = root.findall(".//{http://www.w3.org/2005/Atom}entry")

    records: list[dict] = []
    for item in items:
        title = ""
        desc = ""
        link = ""

        # Title
        t_el = item.find("title")
        if t_el is None:
            t_el = item.find("{http://www.w3.org/2005/Atom}title")
        if t_el is not None and t_el.text:
            title = t_el.text.strip()

        # Description / Summary / Content
        d_el = item.find("description")
        if d_el is None:
            d_el = item.find("{http://www.w3.org/2005/Atom}summary")
        if d_el is None:
            d_el = item.find("{http://www.w3.org/2005/Atom}content")
        if d_el is not None and d_el.text:
            desc = d_el.text.strip()

        # Link
        l_el = item.find("link")
        if l_el is None:
            l_el = item.find("{http://www.w3.org/2005/Atom}link")
        if l_el is not None:
            link = l_el.text.strip() if l_el.text else l_el.attrib.get("href", "")

        # Extract contacts from text using regex
        combined = f"{title} {desc}"
        found_email = ""
        email_match = re.search(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", combined)
        if email_match:
            found_email = email_match.group(0)

        found_phone = ""
        found_phone = find_phone(combined)  # same rules as scraped pages (+91 98765 43210 was missed)

        records.append({
            "company": title[:100] if title else "RSS Buyer Enquiry",
            "contact_name": "",
            "email": found_email,
            "phone": found_phone,
            "country": "India",
            "product": title,
            "message": desc,
            "source_url": link or source.url,
        })

    return records


async def is_scraping_allowed(url: str, user_agent: str = BOT_USER_AGENT) -> bool:
    """Check robots.txt. Fetched through safe_get (same address rules and time limit as every fetch), then
    read with Python's standard robots.txt parser. Python's own fetcher (rp.read) is not used: it had no
    time limit and none of the address checks."""
    try:
        parsed = urllib.parse.urlparse(url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        resp = await safe_get(robots_url, {"User-Agent": user_agent})
        rp = urllib.robotparser.RobotFileParser()
        # Python's own rule (RobotFileParser.read): 401/403 = nothing allowed; other 4xx = no robots.txt, all
        # allowed; 5xx = unknown, so nothing allowed (PR #62 review: an earlier version allowed it).
        if resp.status_code in (401, 403) or resp.status_code >= 500:
            return False
        if resp.status_code >= 400:
            return True
        rp.parse(resp.text.splitlines())
        return rp.can_fetch(user_agent, url)
    except AppError as e:
        if e.code == "blocked_address":  # robots.txt led to an internal address: refuse, don't guess
            log.warning("harvest.robots_txt_blocked", extra={"url": url, "error": e.message})
            return False
        log.warning("harvest.robots_txt_error", extra={"url": url, "error": e.message})
        raise AppError(502, "robots_unreadable", "Could not read the site's robots.txt, so nothing was fetched.") from e
    except Exception as e:
        # robots.txt couldn't be read: when unsure, don't scrape (R57). Its own error, so the run shows
        # "failed" with the real reason, not "blocked by robots"
        log.warning("harvest.robots_txt_error", extra={"url": url, "error": str(e)})
        raise AppError(502, "robots_unreadable", "Could not read the site's robots.txt, so nothing was fetched.") from e


async def fetch_scrape_source(source: HarvestSource) -> list[dict]:
    """Polite web scraper: checks robots.txt, respects terms_checked flag, rate limits."""
    # 1. Require terms_checked
    if not source.terms_checked:
        raise AppError(400, "terms_not_checked", "Scraping source requires 'terms checked' confirmation.")

    # 2. Check robots.txt
    allowed = await is_scraping_allowed(source.url, BOT_USER_AGENT)
    if not allowed:
        raise AppError(403, "blocked_by_robots", f"Scraping is disallowed by {source.url} robots.txt")

    # 3. Rate limiting / politeness delay
    await asyncio.sleep(2.0)

    # 4. Fetch page HTML
    resp = await safe_get(source.url, {"User-Agent": BOT_USER_AGENT})
    resp.raise_for_status()
    html = resp.text

    # Extract text content and contact tags using stdlib / regex
    records: list[dict] = []

    # Look for contact cards, mailto links, tel links, or table rows
    mailto_matches = re.findall(r'href=[\'"]mailto:([^\'"?]+)', html, re.IGNORECASE)
    tel_matches = re.findall(r'href=[\'"]tel:([^\'"?]+)', html, re.IGNORECASE)

    # Clean text of tags
    text_clean = re.sub(r"<[^>]+>", " ", html)
    text_clean = re.sub(r"\s+", " ", text_clean).strip()

    primary_email = mailto_matches[0] if mailto_matches else ""
    primary_phone = tel_matches[0] if tel_matches else ""

    if not primary_email:
        em = re.search(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", text_clean)
        if em:
            primary_email = em.group(0)

    if not primary_phone:
        # Any grouping: "+91 98765 43210" (groups of 5) was missed before (R57). The pattern alone also takes
        # a pin code ("400001"), a date ("2026-11-27") or "MOQ 10000" that comes first, so the first match
        # with a phone's number of digits wins
        ph = find_phone(text_clean)
        if ph:
            primary_phone = ph

    # Check for title
    title_m = re.search(r"<title>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    title = title_m.group(1).strip() if title_m else "Scraped Directory"

    if primary_email or primary_phone:
        records.append({
            "company": title[:100],
            "contact_name": "",
            "email": primary_email,
            "phone": primary_phone,
            "country": "India",
            "product": title,
            "message": text_clean[:500],
            "source_url": source.url,
        })

    return records


# ---------------- Orchestration & Runner ----------------

async def run_harvest_source(db: AsyncSession, source_id: int) -> HarvestRun:
    """Execute a single harvest source: fetch items, apply shared filter, save accepted records, log run."""
    source = await db.scalar(select(HarvestSource).where(HarvestSource.id == source_id))
    if not source:
        raise AppError(404, "source_not_found", f"Harvest source {source_id} not found.")

    started_at = datetime.now(timezone.utc)
    run = HarvestRun(
        source_id=source.id,
        status="running",
        started_at=started_at,
        drop_reasons={},
        error_message="",
    )
    db.add(run)
    await db.flush()

    raw_items: list[dict] = []
    try:
        if source.source_type == "api":
            raw_items = await fetch_api_source(source)
        elif source.source_type == "open_data":
            raw_items = await fetch_open_data_source(source)
        elif source.source_type == "rss":
            raw_items = await fetch_rss_source(source)
        elif source.source_type == "scrape":
            raw_items = await fetch_scrape_source(source)
        else:
            raise AppError(400, "unknown_source_type", f"Unknown source type {source.source_type}")
    except AppError as e:
        status = "blocked_by_robots" if e.code == "blocked_by_robots" else "failed"
        run.status = status
        run.error_message = e.message
        run.finished_at = datetime.now(timezone.utc)
        source.last_run_at = started_at
        source.last_status = status
        await db.commit()
        return run
    except Exception as e:
        log.exception("harvest.fetch_failed", extra={"source_id": source.id, "error": str(e)})
        run.status = "failed"
        run.error_message = str(e)[:500]
        run.finished_at = datetime.now(timezone.utc)
        source.last_run_at = started_at
        source.last_status = "failed"
        await db.commit()
        return run

    run.found_count = len(raw_items)
    accepted_items: list[dict] = []
    drop_reasons: dict[str, int] = {}

    seen: set[str] = set()  # email / phone digits already taken in THIS fetch (R57: duplicates inside one fetch)
    categories = await active_category_slugs(db)
    for item in raw_items:
        try:
            # A savepoint per record: a database error on one record is undone alone, the run goes on (R57)
            async with db.begin_nested():
                clean, drop_reason = await filter_single_record(db, item, source.category, categories)
        except Exception:  # one odd record never stops the run (R57)
            log.exception("harvest.record_failed", extra={"source_id": source.id})
            clean, drop_reason = None, "unreadable"
        if clean:
            keys = {k for k in (clean["email"], re.sub(r"\D", "", clean["phone"])) if k}
            if keys & seen:
                clean, drop_reason = None, "duplicate"
            else:
                seen |= keys
        if clean:
            accepted_items.append(clean)
        else:
            reason = drop_reason or "unknown"
            drop_reasons[reason] = drop_reasons.get(reason, 0) + 1

    run.accepted_count = len(accepted_items)
    run.dropped_count = len(raw_items) - len(accepted_items)
    run.drop_reasons = drop_reasons

    # Save accepted records to dated RecordList batch
    if accepted_items:
        await save_accepted_records(db, source, accepted_items, started_at)

    run.status = "success" if run.dropped_count == 0 else "partial"
    run.finished_at = datetime.now(timezone.utc)
    source.last_run_at = started_at
    source.last_status = run.status

    await db.commit()
    log.info(
        "harvest.source_completed",
        extra={
            "source_id": source.id,
            "found": run.found_count,
            "accepted": run.accepted_count,
            "dropped": run.dropped_count,
        },
    )
    return run


async def _record_failed_run(db: AsyncSession, source_id: int, error: Exception) -> None:
    """After a rollback the run row and last_run_at are gone too: write a failed run and mark the source as
    run, so the Runs page shows why and the source waits its interval instead of retrying every tick."""
    try:
        now = datetime.now(timezone.utc)
        # Only the error type: a database error's text can hold a buyer's email or phone (the full text is in
        # the log above, which is not shown on the Runs page)
        db.add(HarvestRun(source_id=source_id, status="failed", started_at=now, finished_at=now, drop_reasons={},
                          error_message=f"{type(error).__name__} (details in the server log)"))
        source = await db.get(HarvestSource, source_id)
        if source is not None:
            source.last_run_at, source.last_status = now, "failed"
        await db.commit()
    except Exception:  # the database itself may be the problem: never stop the other sources
        await db.rollback()
        log.exception("harvest.failed_run_not_recorded", extra={"source_id": source_id})


@job("lead_harvester", any_time=False, module="lead_harvester")
async def harvest_due_sources_job(db: AsyncSession) -> dict[str, Any]:
    """Background job: checks active harvest sources whose schedule is due and runs them."""
    now = datetime.now(timezone.utc)
    sources = (
        await db.scalars(
            select(HarvestSource).where(HarvestSource.is_active == True)  # noqa: E712
        )
    ).all()

    due_sources = []
    for s in sources:
        # Check scrape terms
        if s.source_type == "scrape" and not s.terms_checked:
            continue
        if s.last_run_at is None:
            due_sources.append(s)
        else:
            delta = now - s.last_run_at
            if delta >= timedelta(minutes=s.schedule_interval_minutes):
                due_sources.append(s)

    total_accepted = 0
    total_dropped = 0
    runs_executed = 0

    for source_id in [s.id for s in due_sources]:  # plain ids: after a rollback the loaded rows are stale
        try:
            run = await run_harvest_source(db, source_id)
            total_accepted += run.accepted_count
            total_dropped += run.dropped_count
            runs_executed += 1
        except Exception as e:
            # The session may be half-written: start clean, so the next source still runs (R57)
            await db.rollback()
            log.exception("harvest.job_source_error", extra={"source_id": source_id, "error": str(e)})
            await _record_failed_run(db, source_id, e)

    return {
        "due_sources": len(due_sources),
        "runs_executed": runs_executed,
        "total_accepted": total_accepted,
        "total_dropped": total_dropped,
    }

