"""Home page hero (Admin > Website > Hero): the banner's slides and the numbers in the stats box.

No active slide (or stat): the home page keeps its built-in slides (or live catalogue counts), so an empty
table never leaves the page blank. Pictures are files of owner "website", id "hero", shown on the website and
shrunk on upload (image_shrink). Limits in config/site_ui.ini.
"""
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config.ini import cfg
from app.core.errors import AppError
from app.core.permissions import effective_permissions
from app.models.file import StoredFile
from app.models.hero import HeroSlide, HeroStat
from app.models.user import User
from app.services import audit_service, file_service

# Background colours a slide can have (the home page maps each to its soft gradient)
TONES = ("gold", "rose", "cream")
FILE_OWNER, FILE_ID = "website", "hero"
PICTURES = {"jpg", "jpeg", "png", "webp"}
MAX_IMAGES = 3  # the banner shows three packs side by side


# ---------- Pictures ----------
async def _files_access(db: AsyncSession, user: User, owner_id: str, action: str) -> bool:
    if owner_id != FILE_ID:
        return False  # only the hero folder exists
    return action == "read" or "content.edit" in effective_permissions(user.role, user.permissions)


async def _always_public(db: AsyncSession, owner_id: str) -> bool:
    return owner_id == FILE_ID


file_service.register_owner(FILE_OWNER, _files_access, public=_always_public, types=PICTURES, shrink=True)


def image_url(file_id: int) -> str:
    return f"/api/v1/public/files/{file_id}"


async def _check_images(db: AsyncSession, ids: list[int]) -> list[int]:
    """Only public hero pictures that still exist; at most MAX_IMAGES, no repeats."""
    ids = list(dict.fromkeys(ids))
    if len(ids) > MAX_IMAGES:
        raise AppError(422, "too_many_images", f"A slide takes at most {MAX_IMAGES} pictures.")
    if not ids:
        return []
    found = set((await db.scalars(select(StoredFile.id).where(
        StoredFile.id.in_(ids), StoredFile.owner_type == FILE_OWNER, StoredFile.owner_id == FILE_ID,
        StoredFile.is_public.is_(True), StoredFile.deleted_at.is_(None)))).all())
    missing = [i for i in ids if i not in found]
    if missing:
        raise AppError(422, "bad_image", "A picture was not found. Please upload it again.", {"ids": missing})
    return ids


async def _live_ids(db: AsyncSession, slides) -> set[int]:
    """Picture ids of these slides whose files still exist (a file deleted on the Files page must not leave a
    broken picture on the home page)."""
    ids = {i for s in slides for i in s.image_ids}
    if not ids:
        return set()
    return set((await db.scalars(select(StoredFile.id).where(
        StoredFile.id.in_(ids), StoredFile.deleted_at.is_(None)))).all())


# ---------- Read ----------
def slide_out(s: HeroSlide, live: set[int] | None = None) -> dict:
    ids = [i for i in s.image_ids if live is None or i in live]
    return {"id": s.id, "eyebrow": s.eyebrow, "title": s.title, "text": s.text, "cta_text": s.cta_text,
            "cta_link": s.cta_link, "tone": s.tone, "image_ids": ids,
            "images": [image_url(i) for i in ids], "is_active": s.is_active, "sort_order": s.sort_order}


def stat_out(s: HeroStat) -> dict:
    return {"id": s.id, "number": s.number, "label": s.label, "is_active": s.is_active, "sort_order": s.sort_order}


async def for_admin(db: AsyncSession) -> dict:
    slides = (await db.scalars(select(HeroSlide).order_by(HeroSlide.sort_order, HeroSlide.id))).all()
    stats = (await db.scalars(select(HeroStat).order_by(HeroStat.sort_order, HeroStat.id))).all()
    s = cfg().site_ui
    live = await _live_ids(db, slides)
    return {"slides": [slide_out(x, live) for x in slides], "stats": [stat_out(x) for x in stats],
            "tones": list(TONES), "max_slides": s.hero_max_slides, "max_stats": s.hero_max_stats,
            "max_images": MAX_IMAGES}


async def public(db: AsyncSession) -> dict:
    """What the home page shows: active slides and stats only, within the limits. Empty lists = built-ins."""
    s = cfg().site_ui
    slides = (await db.scalars(select(HeroSlide).where(HeroSlide.is_active)
                               .order_by(HeroSlide.sort_order, HeroSlide.id).limit(s.hero_max_slides))).all()
    stats = (await db.scalars(select(HeroStat).where(HeroStat.is_active)
                              .order_by(HeroStat.sort_order, HeroStat.id).limit(s.hero_max_stats))).all()
    live = await _live_ids(db, slides)
    return {
        "slides": [{k: v for k, v in slide_out(x, live).items() if k not in ("image_ids", "is_active", "sort_order")}
                   for x in slides],
        "stats": [{"number": x.number, "label": x.label} for x in stats],
    }


# ---------- Write ----------
async def _active_count(db: AsyncSession, model, exclude_id: int | None) -> int:
    q = select(func.count()).select_from(model).where(model.is_active)
    if exclude_id:
        q = q.where(model.id != exclude_id)
    return await db.scalar(q) or 0


def _switching_on(row, row_id: int | None, data: dict) -> bool:
    """True only when this save adds one more active row: a new active one, or off → on. Editing the text of a
    slide that is already on never counts, so a lowered limit can't block fixing a typo."""
    if not row_id:
        return data.get("is_active", True)
    return bool(data.get("is_active")) and not row.is_active


def _need(data: dict, field: str, min_len: int, what: str) -> None:
    """Lengths checked after the text is cleaned: "   " passes a min_length check, then becomes ""."""
    if field in data and len(data[field]) < min_len:
        raise AppError(422, "too_short", f"The {what} needs at least {min_len} character{'s' if min_len > 1 else ''}.")


async def save_slide(db: AsyncSession, user: User, slide_id: int | None, data: dict) -> dict:
    """New slide: every field. Edit: only the fields in `data` change."""
    s = await db.get(HeroSlide, slide_id, with_for_update=True) if slide_id else HeroSlide()
    if s is None:
        raise AppError(404, "not_found", "Slide not found.")
    if "tone" in data and data["tone"] not in TONES:
        raise AppError(422, "bad_tone", "Pick one of the colours shown.", {"tones": list(TONES)})
    _need(data, "title", 3, "title")
    if "image_ids" in data:
        data["image_ids"] = await _check_images(db, data["image_ids"])
    limit = cfg().site_ui.hero_max_slides
    if _switching_on(s, slide_id, data) and await _active_count(db, HeroSlide, slide_id) >= limit:
        raise AppError(422, "too_many_slides", f"At most {limit} slides can be on. Switch one off first.")
    before = {k: getattr(s, k) for k in data} if slide_id else None
    for k, v in data.items():
        setattr(s, k, v)
    s.updated_by = user.id
    if not slide_id:
        db.add(s)
    await db.flush()
    audit_service.record(db, actor=user, action="hero_slide.saved", entity_type="hero_slide", entity_id=s.id,
                         before=before, after={k: getattr(s, k) for k in data})
    await db.commit()
    return slide_out(s)


async def delete_slide(db: AsyncSession, user: User, slide_id: int) -> None:
    s = await db.get(HeroSlide, slide_id)
    if s is None:
        raise AppError(404, "not_found", "Slide not found.")
    audit_service.record(db, actor=user, action="hero_slide.deleted", entity_type="hero_slide", entity_id=s.id,
                         before={"title": s.title})
    await db.delete(s)
    await db.commit()


async def save_stat(db: AsyncSession, user: User, stat_id: int | None, data: dict) -> dict:
    s = await db.get(HeroStat, stat_id, with_for_update=True) if stat_id else HeroStat()
    if s is None:
        raise AppError(404, "not_found", "Number not found.")
    _need(data, "number", 1, "number")
    _need(data, "label", 2, "label")
    limit = cfg().site_ui.hero_max_stats
    if _switching_on(s, stat_id, data) and await _active_count(db, HeroStat, stat_id) >= limit:
        raise AppError(422, "too_many_stats", f"At most {limit} numbers can be on. Switch one off first.")
    before = {k: getattr(s, k) for k in data} if stat_id else None
    for k, v in data.items():
        setattr(s, k, v)
    s.updated_by = user.id
    if not stat_id:
        db.add(s)
    await db.flush()
    audit_service.record(db, actor=user, action="hero_stat.saved", entity_type="hero_stat", entity_id=s.id,
                         before=before, after={k: getattr(s, k) for k in data})
    await db.commit()
    return stat_out(s)


async def delete_stat(db: AsyncSession, user: User, stat_id: int) -> None:
    s = await db.get(HeroStat, stat_id)
    if s is None:
        raise AppError(404, "not_found", "Number not found.")
    audit_service.record(db, actor=user, action="hero_stat.deleted", entity_type="hero_stat", entity_id=s.id,
                         before={"number": s.number, "label": s.label})
    await db.delete(s)
    await db.commit()
