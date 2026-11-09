"""Website content staff can change without a deploy: page text + SEO, the offers ticker,
Koko's facts. Plus partner applications and Koko chat transcripts.

Texts: every key has a default here (so the site always works); a row in `site_texts`
overrides it. "Reset" deletes the row and the default comes back.
"""
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.rate_limit import lead_limiter
from app.models.content import KokoChat, Offer, PartnerApplication, SiteText
from app.models.user import User
from app.services import audit_service, notification_service

KOKO_FACTS_FILE = Path(__file__).parent.parent / "knowledge" / "kjs_facts.md"

# key -> (what it is, default). Public = shown to website visitors through /public/texts.
TEXTS: dict[str, tuple[str, str]] = {
    "home.hero_title": ("Home: big headline", "Trusted Co-Manufacturing Partner"),
    # Home texts follow the product catalogue (27 Oct): confectionery first, coffee and tea made to order
    "home.hero_text": ("Home: text under the headline",
                       "Chocolate bars, wafers, biscuits and marshmallow treats, made and packed for your brand. "
                       "Trusted by global leaders like Nestlé, Unilever, Mayora."),
    "seo.home.title": ("Home: page title (Google)",
                       "KJS India | Contract Manufacturing: Chocolate Bars, Wafers, Biscuits"),
    "seo.home.description": ("Home: description (Google)",
                             "Co-manufacturer of chocolate bars, wafers, biscuits and marshmallow confectionery, "
                             "plus coffee and tea in stick packs. Private label, export, FSSC 22000 certified."),
    "seo.products.title": ("Products: page title (Google)", "Products | KJS India"),
    "seo.products.description": ("Products: description (Google)",
                                 "Coffee, tea, health drink and confectionery products for private label and export."),
    "contact.intro": ("Contact page: intro", "For brands, distributors, retailers and importers. Bulk and export orders."),
    "partners.intro": ("Partners page: intro",
                       "Sales agents, referral partners, freight forwarders and distributors: refer buyers to KJS India "
                       "and grow with us."),
    "koko.facts": ("Koko: facts it may use (everything else it won't claim)", ""),
}
PUBLIC_KEYS = [k for k in TEXTS if not k.startswith("koko.")]


def default(key: str) -> str:
    if key == "koko.facts":
        return KOKO_FACTS_FILE.read_text(encoding="utf-8")
    return TEXTS[key][1]


async def get_text(db: AsyncSession, key: str) -> str:
    row = await db.scalar(select(SiteText.value).where(SiteText.key == key))
    return row if row is not None else default(key)


async def texts(db: AsyncSession, keys: list[str]) -> dict[str, str]:
    rows = dict((await db.execute(select(SiteText.key, SiteText.value).where(SiteText.key.in_(keys)))).all())
    return {k: rows.get(k, default(k)) for k in keys}


async def all_texts_for_admin(db: AsyncSession) -> list[dict]:
    rows = dict((await db.execute(select(SiteText.key, SiteText.value))).all())
    return [{"key": k, "label": label, "value": rows.get(k, default(k)), "changed": k in rows}
            for k, (label, _) in TEXTS.items()]


async def set_text(db: AsyncSession, user: User, key: str, value: str | None) -> None:
    """value None = back to the default."""
    if key not in TEXTS:
        raise AppError(404, "not_found", "Unknown text.")
    row = await db.scalar(select(SiteText).where(SiteText.key == key))
    before = row.value if row else None
    if value is None:
        await db.execute(delete(SiteText).where(SiteText.key == key))
    elif row:
        row.value, row.updated_by = value, user.id
    else:
        db.add(SiteText(key=key, value=value, updated_by=user.id))
    audit_service.record(db, actor=user, action="text.changed" if value is not None else "text.reset",
                         entity_type="site_text", entity_id=key,
                         before={"value": (before or "")[:500]}, after={"value": (value or "")[:500]})
    await db.commit()


# ---------- Offers ticker ----------
def offer_out(o: Offer) -> dict:
    return {"id": o.id, "text": o.text, "link": o.link, "starts_at": o.starts_at, "ends_at": o.ends_at,
            "is_active": o.is_active, "sort_order": o.sort_order}


async def live_offers(db: AsyncSession, now: datetime | None = None) -> list[dict]:
    now = now or datetime.now(timezone.utc)
    rows = (await db.scalars(select(Offer).where(
        Offer.is_active, or_(Offer.starts_at.is_(None), Offer.starts_at <= now),
        or_(Offer.ends_at.is_(None), Offer.ends_at > now)).order_by(Offer.sort_order, Offer.id))).all()
    return [{"id": o.id, "text": o.text, "link": o.link} for o in rows]


async def list_offers(db: AsyncSession) -> list[dict]:
    return [offer_out(o) for o in (await db.scalars(select(Offer).order_by(Offer.sort_order, Offer.id))).all()]


async def save_offer(db: AsyncSession, user: User, offer_id: int | None, data: dict) -> dict:
    if data.get("starts_at") and data.get("ends_at") and data["ends_at"] <= data["starts_at"]:
        raise AppError(422, "bad_dates", "The offer must end after it starts.")
    o = await db.get(Offer, offer_id) if offer_id else Offer()
    if o is None:
        raise AppError(404, "not_found", "Offer not found.")
    for k, v in data.items():
        setattr(o, k, v)
    if not offer_id:
        db.add(o)
    await db.flush()
    audit_service.record(db, actor=user, action="offer.saved", entity_type="offer", entity_id=o.id,
                         after={"text": o.text, "active": o.is_active})
    await db.commit()
    return offer_out(o)


async def delete_offer(db: AsyncSession, user: User, offer_id: int) -> None:
    o = await db.get(Offer, offer_id)
    if o is None:
        raise AppError(404, "not_found", "Offer not found.")
    audit_service.record(db, actor=user, action="offer.deleted", entity_type="offer", entity_id=o.id,
                         before={"text": o.text})
    await db.delete(o)
    await db.commit()


# ---------- Partner programme ----------
# What staff see for each saved partner type ("broker" is shown as "Referral partner"; the value stays)
PARTNER_LABELS = {"agent": "Sales agent", "broker": "Referral partner", "forwarder": "Freight forwarder",
                  "distributor": "Distributor", "other": "Other"}


async def apply_partner(db: AsyncSession, data, ip_hash: str | None, rate_key: str | None = None) -> None:
    if data.website:  # honeypot
        return
    lead_limiter.check(rate_key or ip_hash)
    p = PartnerApplication(name=data.name.strip(), company=data.company.strip(), partner_type=data.partner_type,
                           country=data.country.strip(), email=data.email, phone=data.phone.strip(),
                           message=data.message.strip(), status="new", ip_hash=ip_hash,
                           consent_at=datetime.now(timezone.utc))
    db.add(p)
    await db.flush()
    audit_service.record(db, actor=None, action="partner.applied", entity_type="partner", entity_id=p.id,
                         after={"type": p.partner_type, "country": p.country}, ip_hash=ip_hash)
    label = PARTNER_LABELS.get(p.partner_type, p.partner_type)
    notification_service.notify(db, await notification_service.users_with(db, "leads.view_all"), "partner.applied",
                                f"Partner application: {p.name} ({label}, {p.country})", p.message[:300],
                                "/admin/website")
    await db.commit()


async def list_partners(db: AsyncSession) -> list[dict]:
    rows = (await db.scalars(select(PartnerApplication).order_by(PartnerApplication.id.desc()).limit(200))).all()
    return [{"id": p.id, "name": p.name, "company": p.company, "partner_type": p.partner_type, "country": p.country,
             "email": p.email, "phone": p.phone, "message": p.message, "status": p.status, "created_at": p.created_at}
            for p in rows]


async def set_partner_status(db: AsyncSession, user: User, partner_id: int, status: str) -> None:
    p = await db.get(PartnerApplication, partner_id)
    if p is None:
        raise AppError(404, "not_found", "Application not found.")
    before = p.status
    p.status = status
    audit_service.record(db, actor=user, action="partner.status", entity_type="partner", entity_id=p.id,
                         before={"status": before}, after={"status": status})
    await db.commit()


# ---------- Koko transcripts ----------
async def save_chat(db: AsyncSession, chat_id: str, page: str, messages: list[dict], suggested: bool,
                    ip_hash: str | None) -> None:
    row = await db.scalar(select(KokoChat).where(KokoChat.chat_id == chat_id))
    if row is not None and row.ip_hash != ip_hash:
        return  # someone else's chat id: never overwrite another visitor's transcript
    if row is None:
        row = KokoChat(chat_id=chat_id, page=page[:255], messages=[], suggested_enquiry=False, ip_hash=ip_hash)
        db.add(row)
    row.messages = messages[-40:]
    row.suggested_enquiry = row.suggested_enquiry or suggested
    await db.commit()


async def list_chats(db: AsyncSession, limit: int = 50) -> dict:
    rows = (await db.scalars(select(KokoChat).order_by(KokoChat.updated_at.desc()).limit(limit))).all()
    total = await db.scalar(select(func.count()).select_from(KokoChat))
    return {"total": total, "items": [{"id": c.id, "page": c.page, "messages": c.messages,
                                       "suggested_enquiry": c.suggested_enquiry, "updated_at": c.updated_at}
                                      for c in rows]}
