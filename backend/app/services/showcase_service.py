"""Website showcase (Admin > Website): the partner logos in the home page's sliding strip, and the true activity
lines the website shows as pop-ups ("A brand in Dubai requested a sample · 2 hours ago").

No active partner: the strip keeps its built-in names. No active line: no pop-ups. Logos are files of owner
"website", id "partners" (public, shrunk on upload, see hero_service). Limits in config/site_ui.ini.
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config.ini import cfg
from app.core.errors import AppError
from app.models.file import StoredFile
from app.models.showcase import ActivityLine, BrandPartner
from app.models.user import User
from app.services import audit_service
from app.services.hero_service import FILE_OWNER, image_url

LOGO_FOLDER = "partners"
FUTURE_SLACK = timedelta(minutes=5)  # clocks differ a little; a line further in the future is a typo


# ---------- Partners ----------
async def _check_logo(db: AsyncSession, file_id: int | None) -> int | None:
    if file_id is None:
        return None
    ok = await db.scalar(select(StoredFile.id).where(
        StoredFile.id == file_id, StoredFile.owner_type == FILE_OWNER, StoredFile.owner_id == LOGO_FOLDER,
        StoredFile.is_public.is_(True), StoredFile.deleted_at.is_(None)))
    if not ok:
        raise AppError(422, "bad_image", "The logo was not found. Please upload it again.")
    return file_id


async def _live_logos(db: AsyncSession, rows) -> set[int]:
    """Logo ids that still exist (a logo deleted on the Files page shows the name only, never a broken picture)."""
    ids = {r.logo_file_id for r in rows if r.logo_file_id}
    if not ids:
        return set()
    return set((await db.scalars(select(StoredFile.id).where(
        StoredFile.id.in_(ids), StoredFile.deleted_at.is_(None)))).all())


def partner_out(p: BrandPartner, live: set[int] | None = None) -> dict:
    logo = p.logo_file_id if p.logo_file_id and (live is None or p.logo_file_id in live) else None
    return {"id": p.id, "name": p.name, "logo_file_id": logo, "logo": image_url(logo) if logo else None,
            "is_active": p.is_active, "sort_order": p.sort_order}


async def partners_for_admin(db: AsyncSession) -> dict:
    rows = (await db.scalars(select(BrandPartner).order_by(BrandPartner.sort_order, BrandPartner.id))).all()
    live = await _live_logos(db, rows)
    return {"partners": [partner_out(p, live) for p in rows], "max_partners": cfg().site_ui.partners_max}


async def public_partners(db: AsyncSession) -> list[dict]:
    rows = (await db.scalars(select(BrandPartner).where(BrandPartner.is_active)
                             .order_by(BrandPartner.sort_order, BrandPartner.id).limit(cfg().site_ui.partners_max))).all()
    live = await _live_logos(db, rows)
    return [{"name": p.name, "logo": partner_out(p, live)["logo"]} for p in rows]


def _switching_on(row, row_id: int | None, data: dict) -> bool:
    """A new active row, or off → on. Editing a row that is already on never counts against the limit."""
    if not row_id:
        return data.get("is_active", True)
    return bool(data.get("is_active")) and not row.is_active


def _need(data: dict, field: str, min_len: int, what: str) -> None:
    """Checked after the text is cleaned: "   " passes a min_length check, then becomes ""."""
    if field in data and len(data[field]) < min_len:
        raise AppError(422, "too_short", f"The {what} needs at least {min_len} characters.")


async def save_partner(db: AsyncSession, user: User, partner_id: int | None, data: dict) -> dict:
    """New partner: every field. Edit: only the fields in `data` change."""
    p = await db.get(BrandPartner, partner_id, with_for_update=True) if partner_id else BrandPartner()
    if p is None:
        raise AppError(404, "not_found", "Partner not found.")
    _need(data, "name", 2, "name")
    if "logo_file_id" in data:
        data["logo_file_id"] = await _check_logo(db, data["logo_file_id"])
    limit = cfg().site_ui.partners_max
    if _switching_on(p, partner_id, data):
        q = select(func.count()).select_from(BrandPartner).where(BrandPartner.is_active)
        if partner_id:
            q = q.where(BrandPartner.id != partner_id)
        if (await db.scalar(q) or 0) >= limit:
            raise AppError(422, "too_many_partners", f"At most {limit} partners can be on. Switch one off first.")
    before = {k: getattr(p, k) for k in data} if partner_id else None
    for k, v in data.items():
        setattr(p, k, v)
    p.updated_by = user.id
    if not partner_id:
        db.add(p)
    await db.flush()
    audit_service.record(db, actor=user, action="brand_partner.saved", entity_type="brand_partner", entity_id=p.id,
                         before=before, after={k: getattr(p, k) for k in data})
    await db.commit()
    return partner_out(p)


async def delete_partner(db: AsyncSession, user: User, partner_id: int) -> None:
    p = await db.get(BrandPartner, partner_id)
    if p is None:
        raise AppError(404, "not_found", "Partner not found.")
    audit_service.record(db, actor=user, action="brand_partner.deleted", entity_type="brand_partner",
                         entity_id=p.id, before={"name": p.name})
    await db.delete(p)
    await db.commit()


# ---------- Activity lines ----------
def _plain(d: dict | None) -> dict | None:
    """Audit rows are JSON: times written as text."""
    return None if d is None else {k: v.isoformat() if isinstance(v, datetime) else v for k, v in d.items()}


def line_out(a: ActivityLine) -> dict:
    return {"id": a.id, "text": a.text, "happened_at": a.happened_at, "is_active": a.is_active,
            "sort_order": a.sort_order}


async def lines_for_admin(db: AsyncSession) -> dict:
    rows = (await db.scalars(select(ActivityLine).order_by(ActivityLine.sort_order, ActivityLine.happened_at.desc(),
                                                           ActivityLine.id))).all()
    s = cfg().site_ui
    return {"lines": [line_out(a) for a in rows], "max_age_days": s.activity_max_age_days,
            "max_shown": s.activity_public_max}


async def public_lines(db: AsyncSession, now: datetime | None = None) -> list[dict]:
    """Active lines that are recent enough (older ones stop showing by themselves: never stale news)."""
    now = now or datetime.now(timezone.utc)
    s = cfg().site_ui
    rows = (await db.scalars(select(ActivityLine).where(
        ActivityLine.is_active, ActivityLine.happened_at >= now - timedelta(days=s.activity_max_age_days),
        ActivityLine.happened_at <= now + FUTURE_SLACK)
        .order_by(ActivityLine.sort_order, ActivityLine.happened_at.desc(), ActivityLine.id)
        .limit(s.activity_public_max))).all()
    return [{"text": a.text, "happened_at": a.happened_at} for a in rows]


async def save_line(db: AsyncSession, user: User, line_id: int | None, data: dict) -> dict:
    a = await db.get(ActivityLine, line_id, with_for_update=True) if line_id else ActivityLine()
    if a is None:
        raise AppError(404, "not_found", "Line not found.")
    _need(data, "text", 5, "text")
    if "happened_at" in data and data["happened_at"] > datetime.now(timezone.utc) + FUTURE_SLACK:
        raise AppError(422, "in_the_future", "The time can't be in the future: these lines show real activity.")
    before = {k: getattr(a, k) for k in data} if line_id else None
    for k, v in data.items():
        setattr(a, k, v)
    a.updated_by = user.id
    if not line_id:
        db.add(a)
    await db.flush()
    audit_service.record(db, actor=user, action="activity_line.saved", entity_type="activity_line", entity_id=a.id,
                         before=_plain(before), after=_plain({k: getattr(a, k) for k in data}))
    await db.commit()
    return line_out(a)


async def delete_line(db: AsyncSession, user: User, line_id: int) -> None:
    a = await db.get(ActivityLine, line_id)
    if a is None:
        raise AppError(404, "not_found", "Line not found.")
    audit_service.record(db, actor=user, action="activity_line.deleted", entity_type="activity_line",
                         entity_id=a.id, before={"text": a.text})
    await db.delete(a)
    await db.commit()
