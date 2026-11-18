"""Browser extension (Phase C): connecting a computer, the device key, site visits, hourly blocks, outcomes.

Connecting (once per computer):
1. "Connect extension" on My activity -> new_pair_code(): a one-time code (KJS-XXXX-XXXX), valid
   pair_code_minutes. Only its hash is stored.
2. The extension sends the code to POST /ext/connect -> connect(): the code is used up and a new device key
   is returned ONCE. Only its hash is stored; the key itself lives only in the extension.
3. Every other /ext call sends `Authorization: Bearer <key>` -> device_for_key().

Why a key and not the login cookie: the cookie can't be shared safely with an extension, and a key per
computer can be switched off on its own (lost laptop) without logging the person out.

Site visits: the server never trusts the extension's idea of "checked in". Each visit is cut to the times
the person was really checked in (from attendance punches) and dropped if nothing is left. never_record
domains are dropped here too. The same visit sent twice is saved once (unique device + client_id).
"""
import hashlib
import logging
import secrets
from datetime import date, datetime, timedelta, timezone
from urllib.parse import urlsplit, urlunsplit

from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config.ini import cfg
from app.core.errors import AppError
from app.jobs.runner import job
from app.models.attendance import AttendancePunch
from app.models.extension import ExtensionDevice, ExtensionPairCode, SiteBlock, SiteVisit
from app.models.notification import Notification
from app.models.user import User
from app.services import attendance_service as att

log = logging.getLogger(__name__)
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O, 1/I: easy to type
MAX_VISITS = 500  # visits in one batch


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _norm_code(code: str) -> str:
    return "".join(ch for ch in code.upper() if ch.isalnum()).removeprefix("KJS")


# ---------- Connecting ----------
async def new_pair_code(db: AsyncSession, user: User, now: datetime | None = None) -> dict:
    now = now or _now()
    raw = "".join(secrets.choice(CODE_ALPHABET) for _ in range(8))
    # Older unused codes of this person stop working: only the newest one is valid
    await db.execute(update(ExtensionPairCode).where(ExtensionPairCode.user_id == user.id,
                                                     ExtensionPairCode.used_at.is_(None)).values(used_at=now))
    minutes = cfg().monitoring.pair_code_minutes
    db.add(ExtensionPairCode(user_id=user.id, code_hash=_hash(raw), expires_at=now + timedelta(minutes=minutes)))
    await db.commit()
    return {"code": f"KJS-{raw[:4]}-{raw[4:]}", "expires_in_minutes": minutes}


async def connect(db: AsyncSession, code: str, name: str, now: datetime | None = None) -> dict:
    now = now or _now()
    row = await db.scalar(select(ExtensionPairCode).where(ExtensionPairCode.code_hash == _hash(_norm_code(code)))
                          .with_for_update())
    if not row or row.used_at or row.expires_at < now:
        raise AppError(400, "bad_code", "This code is wrong or has expired. Get a new one from My activity.")
    user = await db.get(User, row.user_id)
    if not user or user.status != "active":
        raise AppError(400, "bad_code", "This code is wrong or has expired. Get a new one from My activity.")
    row.used_at = now
    key = secrets.token_urlsafe(32)
    device = ExtensionDevice(user_id=user.id, name=(name or "Browser").strip()[:80], key_hash=_hash(key),
                             last_seen_at=now)
    db.add(device)
    await db.commit()
    return {"key": key, "device_id": device.id, "user_name": user.name}


async def device_for_key(db: AsyncSession, key: str, now: datetime | None = None) -> tuple[ExtensionDevice, User]:
    """The device and its person for a key, or 401. Notes when it was last heard from."""
    now = now or _now()
    d = await db.scalar(select(ExtensionDevice).where(ExtensionDevice.key_hash == _hash(key)))
    if not d or d.disabled_at:
        raise AppError(401, "bad_device", "This extension is not connected. Connect it again from My activity.")
    user = await db.get(User, d.user_id)
    if not user or user.status != "active":
        raise AppError(401, "bad_device", "This extension is not connected. Connect it again from My activity.")
    if not d.last_seen_at or now - d.last_seen_at > timedelta(minutes=1):  # not a write on every call
        d.last_seen_at = now
        await db.commit()
    return d, user


async def devices_of(db: AsyncSession, user_id: int) -> list[dict]:
    rows = (await db.scalars(select(ExtensionDevice).where(ExtensionDevice.user_id == user_id)
                             .order_by(ExtensionDevice.created_at.desc()))).all()
    return [{"id": d.id, "name": d.name, "created_at": d.created_at, "last_seen_at": d.last_seen_at,
             "disabled": d.disabled_at is not None} for d in rows]


async def disable_device(db: AsyncSession, actor: User, device_id: int, own_only: bool) -> None:
    d = await db.get(ExtensionDevice, device_id)
    if not d or (own_only and d.user_id != actor.id):
        raise AppError(404, "not_found", "No such device.")
    if not d.disabled_at:
        d.disabled_at, d.disabled_by = _now(), actor.id
        from app.services import audit_service
        audit_service.record(db, actor=actor, action="extension.disabled", entity_type="extension_device",
                             entity_id=d.id, after={"user_id": d.user_id, "name": d.name})
        await db.commit()


async def connection(db: AsyncSession, user_ids: list[int] | None = None, now: datetime | None = None) -> dict[int, str]:
    """{user_id: "connected" | "not_connected"}: an enabled device heard from within connected_minutes."""
    now = now or _now()
    since = now - timedelta(minutes=cfg().monitoring.connected_minutes)
    q = select(ExtensionDevice.user_id).where(ExtensionDevice.disabled_at.is_(None),
                                              ExtensionDevice.last_seen_at >= since)
    if user_ids is not None:
        q = q.where(ExtensionDevice.user_id.in_(user_ids))
    on = set((await db.scalars(q)).all())
    return {uid: "connected" for uid in on}


async def is_connected(db: AsyncSession, user_id: int) -> str:
    return (await connection(db, [user_id])).get(user_id, "not_connected")


# ---------- Checked-in time (from punches) ----------
async def checked_in_spans(db: AsyncSession, user_id: int, t0: datetime, t1: datetime,
                           now: datetime | None = None) -> list[tuple[datetime, datetime]]:
    """The times between t0 and t1 when the person was checked in: [(start, end)], from in/out punches."""
    now = now or _now()
    days = {att.local_day(t0) - timedelta(days=1), att.local_day(t0), att.local_day(t1)}
    punches = (await db.scalars(select(AttendancePunch).where(
        AttendancePunch.user_id == user_id, AttendancePunch.day.in_(days)).order_by(AttendancePunch.punched_at))).all()
    spans, start = [], None
    for p in punches:
        if p.punch_type == "in" and start is None:
            start = p.punched_at
        elif p.punch_type == "out" and start is not None:
            spans.append((start, p.punched_at))
            start = None
    if start is not None:
        spans.append((start, now))  # still checked in
    return [(max(a, t0), min(b, t1)) for a, b in spans if b > t0 and a < t1]


# ---------- Site visits ----------
def clean_url(url: str) -> tuple[str, str]:
    """(domain, address to store). Only http(s); no ?query or #fragment unless store_query; no user:pass@."""
    try:
        parts = urlsplit(url.strip())
    except ValueError:
        return "", ""
    if parts.scheme not in ("http", "https") or not parts.hostname:
        return "", ""
    host = parts.hostname.lower().removeprefix("www.")
    keep = cfg().monitoring.store_query
    netloc = parts.hostname.lower() + (f":{parts.port}" if parts.port else "")
    return host[:255], urlunsplit((parts.scheme, netloc, parts.path, parts.query if keep else "",
                                   parts.fragment if keep else ""))[:2000]


def never_recorded(domain: str) -> bool:
    return any(domain == d or domain.endswith("." + d) for d in (x.lower().removeprefix("www.") for x in cfg().monitoring.never_record))


def _hour_start(at: datetime) -> datetime:
    local = at.astimezone(att.tz())
    return local.replace(minute=0, second=0, microsecond=0).astimezone(timezone.utc)


def _by_hour(a: datetime, b: datetime) -> list[tuple[datetime, int]]:
    """Split [a, b) into IST hours: [(hour start in UTC, seconds in it)]."""
    out, cur = [], a
    while cur < b:
        h = _hour_start(cur)
        nxt = min(b, h + timedelta(hours=1))
        out.append((h, int((nxt - cur).total_seconds())))
        cur = nxt
    return [(h, s) for h, s in out if s > 0]


async def save_visits(db: AsyncSession, device: ExtensionDevice, user: User, visits: list[dict],
                      now: datetime | None = None) -> dict:
    """visits: [{id, url, title, started_at, ended_at}]. Returns how many were saved / skipped."""
    now = now or _now()
    if len(visits) > MAX_VISITS:
        raise AppError(413, "too_many", f"Send at most {MAX_VISITS} visits at a time.")
    saved = skipped = 0
    for v in visits:
        a, b = v["started_at"], min(v["ended_at"], now)  # nothing from the future
        domain, url = clean_url(v["url"])
        if not domain or b <= a or never_recorded(domain):
            skipped += 1
            continue
        spans = await checked_in_spans(db, user.id, a, b, now)
        if not spans:  # not checked in at any moment of it: refused
            skipped += 1
        for s, e in spans:
            secs = int((e - s).total_seconds())
            if secs < 1:
                continue
            # Usually the whole visit is one piece and keeps its own id. A visit that crosses a check-out
            # (or check-in) is cut into pieces; each gets the id + its start, so a re-send matches again.
            cid = v["id"] if (s, e) == (a, b) else f"{v['id']}:{int(s.timestamp())}"
            res = await db.execute(insert(SiteVisit).values(
                user_id=user.id, device_id=device.id, client_id=cid[:64], domain=domain, url=url,
                title=(v.get("title") or "")[:300], started_at=s, ended_at=e, seconds=secs,
            ).on_conflict_do_nothing(constraint="uq_site_visits_device_client").returning(SiteVisit.id))
            if res.scalar() is None:  # sent before: already counted
                continue
            saved += 1
            for hour, hs in _by_hour(s, e):
                await db.execute(insert(SiteBlock).values(user_id=user.id, domain=domain, hour_start=hour, seconds=hs)
                                 .on_conflict_do_update(constraint="uq_site_blocks_user_domain_hour",
                                                        set_={"seconds": SiteBlock.seconds + hs}))
    await db.commit()
    return {"saved": saved, "skipped": skipped}


# ---------- Sites tab ----------
async def sites(db: AsyncSession, user_id: int, start: date, end: date) -> dict:
    t0, t1 = att.to_utc(start, "00:00"), att.to_utc(end + timedelta(days=1), "00:00")
    min_secs = cfg().monitoring.outcome_min_minutes * 60
    per_day: dict[str, dict[str, int]] = {}
    totals: dict[str, int] = {}
    visits = (await db.scalars(select(SiteVisit).where(SiteVisit.user_id == user_id, SiteVisit.started_at >= t0,
                                                       SiteVisit.started_at < t1).order_by(SiteVisit.started_at.desc())
                               .limit(cfg().monitoring.timeline_page_size))).all()
    rows = (await db.execute(select(SiteBlock.domain, SiteBlock.hour_start, SiteBlock.seconds).where(
        SiteBlock.user_id == user_id, SiteBlock.hour_start >= t0, SiteBlock.hour_start < t1))).all()
    for domain, hour, secs in rows:
        d = att.local_day(hour).isoformat()
        per_day.setdefault(d, {})
        per_day[d][domain] = per_day[d].get(domain, 0) + secs
        totals[domain] = totals.get(domain, 0) + secs
    blocks = (await db.scalars(select(SiteBlock).where(SiteBlock.user_id == user_id, SiteBlock.hour_start >= t0,
                                                       SiteBlock.hour_start < t1, SiteBlock.seconds >= min_secs)
                               .order_by(SiteBlock.hour_start.desc(), SiteBlock.seconds.desc()))).all()
    return {
        "top": [{"domain": k, "minutes": round(v / 60)} for k, v in sorted(totals.items(), key=lambda x: -x[1])[:10]],
        "per_day": [{"day": d, "sites": [{"domain": k, "minutes": round(v / 60)} for k, v in sorted(s.items(), key=lambda x: -x[1])]}
                    for d, s in sorted(per_day.items(), reverse=True)],
        "blocks": [{"id": b.id, "domain": b.domain, "hour": att.hm(b.hour_start), "day": att.local_day(b.hour_start),
                    "minutes": round(b.seconds / 60), "outcome": b.outcome, "outcome_at": b.outcome_at} for b in blocks],
        "visits": [{"time": att.hm(v.started_at), "day": att.local_day(v.started_at), "domain": v.domain, "url": v.url,
                    "title": v.title, "minutes": round(v.seconds / 60, 1)} for v in visits],
        "outcome_min_minutes": cfg().monitoring.outcome_min_minutes,
    }


async def set_outcome(db: AsyncSession, user: User, block_id: int, text: str) -> None:
    b = await db.get(SiteBlock, block_id)
    if not b or b.user_id != user.id:
        raise AppError(404, "not_found", "No such site block.")
    text = text.strip()
    if not text:
        raise AppError(400, "empty", "Please write what came of this time.")
    b.outcome, b.outcome_at = text[:2000], _now()
    await db.commit()


# ---------- Job: reminders and clean-up ----------
@job("extension_watch", any_time=True, module="monitoring")
async def extension_watch(db: AsyncSession, now: datetime | None = None) -> dict:
    now = now or _now()
    c = cfg().monitoring
    # Remind once about a finished hour (not the current one) of outcome_min_minutes+ with no outcome
    blocks = (await db.scalars(select(SiteBlock).where(
        SiteBlock.outcome == "", SiteBlock.reminded_at.is_(None), SiteBlock.seconds >= c.outcome_min_minutes * 60,
        SiteBlock.hour_start <= now - timedelta(hours=1), SiteBlock.hour_start >= now - timedelta(days=2)))).all()
    for b in blocks:
        b.reminded_at = now
        db.add(Notification(user_id=b.user_id, kind="monitor.site_outcome", email_status="skipped", link="/employee/my-work",
                            title=f"What came of {round(b.seconds / 60)} min on {b.domain} at {att.hm(b.hour_start)}?",
                            body="Write the outcome on My activity, Sites."))
    old = now - timedelta(days=c.sites_keep_days)
    v = await db.execute(delete(SiteVisit).where(SiteVisit.started_at < old))
    bl = await db.execute(delete(SiteBlock).where(SiteBlock.hour_start < old))
    await db.execute(delete(ExtensionPairCode).where(ExtensionPairCode.expires_at < now - timedelta(days=1)))
    return {"reminded": len(blocks), "visits_deleted": v.rowcount, "blocks_deleted": bl.rowcount}


async def minutes_on_sites(db: AsyncSession, user_ids: list[int], t0: datetime, t1: datetime) -> dict[int, int]:
    rows = (await db.execute(select(SiteBlock.user_id, func.sum(SiteBlock.seconds)).where(
        SiteBlock.user_id.in_(user_ids), SiteBlock.hour_start >= t0, SiteBlock.hour_start < t1)
        .group_by(SiteBlock.user_id))).all()
    return {uid: round((s or 0) / 60) for uid, s in rows}
