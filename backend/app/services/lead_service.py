from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.permissions import effective_permissions
from app.core.rate_limit import lead_limiter
from app.models.catalog import Category, Product
from app.models.lead import Lead
from app.models.user import User
from app.schemas.lead import LeadIn, LeadOut
from app.services import audit_service, koko_service


async def create(db: AsyncSession, data: LeadIn, ip_hash: str | None) -> Lead | None:
    if data.website:  # honeypot filled = bot. Pretend success, save nothing.
        return None
    lead_limiter.check(ip_hash)

    product_id = category_id = None
    if data.product_slug:
        p = await db.scalar(select(Product).where(Product.slug == data.product_slug))
        if p:
            product_id, category_id = p.id, p.category_id
    if data.category_slug and category_id is None:
        category_id = await db.scalar(select(Category.id).where(Category.slug == data.category_slug))

    summary = await koko_service.summarise_chat(data.chat) if data.source == "koko" and data.chat else ""
    lead = Lead(
        source=data.source, name=data.name.strip(), company=data.company.strip(),
        email=data.email or "", phone=data.phone.strip(), country=data.country.strip(),
        buyer_type=data.buyer_type, product_id=product_id, category_id=category_id,
        quantity=data.quantity, message=data.message.strip(), chat_summary=summary,
        source_page=data.source_page, consent=True, consent_at=datetime.now(timezone.utc),
        ip_hash=ip_hash, status="new",
    )
    db.add(lead)
    await db.flush()
    audit_service.record(db, actor=None, action="lead.created", entity_type="lead",
                         entity_id=lead.id, after={"source": lead.source}, ip_hash=ip_hash)
    await db.commit()
    return lead


async def list_for(db: AsyncSession, user: User, status: str | None = None, limit: int = 200) -> list[LeadOut]:
    q = (
        select(Lead, Product.name, Category.name)
        .outerjoin(Product, Product.id == Lead.product_id)
        .outerjoin(Category, Category.id == Lead.category_id)
        .order_by(Lead.created_at.desc())
        .limit(limit)
    )
    if "leads.view_all" not in effective_permissions(user.role, user.permissions):
        # Until auto-assign exists (Phase 4), employees see unassigned leads + their own.
        q = q.where((Lead.assigned_to == user.id) | (Lead.assigned_to.is_(None)))
    if status:
        q = q.where(Lead.status == status)
    out = []
    for lead, product_name, category_name in (await db.execute(q)).all():
        out.append(LeadOut(
            id=lead.id, source=lead.source, name=lead.name, company=lead.company, email=lead.email,
            phone=lead.phone, country=lead.country, buyer_type=lead.buyer_type, quantity=lead.quantity,
            message=lead.message, chat_summary=lead.chat_summary, source_page=lead.source_page,
            status=lead.status, product_name=product_name, category_name=category_name,
            created_at=lead.created_at,
        ))
    return out


async def set_status(db: AsyncSession, user: User, lead_id: int, status: str) -> None:
    lead = await db.get(Lead, lead_id)
    if lead is None:
        raise AppError(404, "not_found", "Lead not found.")
    before = {"status": lead.status, "assigned_to": lead.assigned_to}
    lead.status = status
    if lead.assigned_to is None:
        lead.assigned_to = user.id  # whoever acts on an unassigned lead takes it
    audit_service.record(db, actor=user, action="lead.status_changed", entity_type="lead",
                         entity_id=lead.id, before=before,
                         after={"status": status, "assigned_to": lead.assigned_to})
    await db.commit()


async def counts(db: AsyncSession) -> dict[str, int]:
    rows = await db.execute(select(Lead.status, func.count()).group_by(Lead.status))
    return {s: n for s, n in rows.all()}
