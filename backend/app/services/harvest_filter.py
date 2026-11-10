"""Shared filter module for Lead Harvester (DPDP Act & quality control).

Every source type (API, Open Data, RSS, Scraper) passes raw items through this filter:
1. Product match: keeps coffee, tea, spices, and private-label enquiries; drops unrelated.
2. Contact check: requires at least a valid email OR a phone number with country code.
3. Duplicate check: deduplicates against existing leads and buyer_records by email and phone.
4. Save: batches accepted records into dated record_lists for the auto-assign job.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import func, select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.batch import BuyerRecord, RecordList
from app.models.lead import Lead
from app.models.harvest import HarvestSource

# Target product categories and matching keywords
PRODUCT_KEYWORDS: dict[str, list[str]] = {
    "coffee": [
        "coffee", "espresso", "arabica", "robusta", "roast", "beans",
        "green coffee", "instant coffee", "cafe", "cold brew", "cappuccino",
        "peaberry", "chicory",
    ],
    "tea": [
        "tea", "chai", "black tea", "green tea", "assam", "darjeeling",
        "herbal tea", "oolong", "matcha", "white tea", "loose leaf",
        "nilgiri", "masala chai",
    ],
    "spices": [
        "spice", "spices", "cardamom", "pepper", "clove", "cinnamon",
        "turmeric", "ginger", "nutmeg", "masala", "cumin", "coriander",
        "chilli", "saffron", "fenugreek", "mace", "mustard seed", "star anise",
    ],
    "private_label": [
        "private label", "white label", "contract manufacturing", "oem",
        "co-pack", "custom packaging", "own brand", "contract packaging",
        "toll packing", "custom blend", "private-label", "white-label",
    ],
}

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")
# E.164 phone: optional '+', 7 to 15 digits, must have country code indicator
PHONE_DIGITS_REGEX = re.compile(r"^\+?[1-9]\d{6,14}$")


def normalize_email(email: str | None) -> str:
    """Normalize and validate an email address, or return empty string."""
    if not email:
        return ""
    cleaned = email.strip().lower()
    return cleaned if EMAIL_REGEX.match(cleaned) else ""


def normalize_phone(phone: str | None) -> str:
    """Normalize and validate a phone with country code (E.164), or return empty string."""
    if not phone:
        return ""
    raw = phone.strip()
    # Strip spaces, dashes, parentheses
    compact = re.sub(r"[\s\-\(\)\.]", "", raw)
    if compact.startswith("00"):
        compact = "+" + compact[2:]
    elif not compact.startswith("+") and len(compact) >= 11:
        # e.g. 919876543210 -> +919876543210
        compact = "+" + compact

    if PHONE_DIGITS_REGEX.match(compact) and compact.startswith("+"):
        return compact
    return ""


def match_product_category(text: str, source_category: str = "all") -> tuple[str | None, str | None]:
    """Check text against coffee, tea, spices, and private_label keywords.

    Returns (category_slug, matched_keyword), or (None, None) if unrelated.
    """
    if not text:
        return None, None

    lower = text.lower()

    # If the source is locked to a specific category, test that category first
    order = list(PRODUCT_KEYWORDS.keys())
    if source_category in PRODUCT_KEYWORDS:
        order.remove(source_category)
        order.insert(0, source_category)

    for cat in order:
        for kw in PRODUCT_KEYWORDS[cat]:
            # Word boundary matching where possible, or substring for multi-word
            if " " in kw or "-" in kw:
                if kw in lower:
                    return cat, kw
            else:
                if re.search(r"\b" + re.escape(kw) + r"\b", lower):
                    return cat, kw

    return None, None


async def is_duplicate(db: AsyncSession, email: str, phone: str) -> bool:
    """Check if normalized email or phone already exists in leads or buyer_records."""
    clauses_leads = []
    clauses_buyers = []

    if email:
        clauses_leads.append(func.lower(Lead.email) == email.lower())
        clauses_buyers.append(func.lower(BuyerRecord.email) == email.lower())
    if phone:
        clauses_leads.append(Lead.phone == phone)
        clauses_buyers.append(BuyerRecord.phone == phone)

    if not clauses_leads and not clauses_buyers:
        return False

    # Check leads table
    if clauses_leads:
        lead_match = await db.scalar(
            select(Lead.id).where(or_(*clauses_leads)).limit(1)
        )
        if lead_match:
            return True

    # Check buyer_records table
    if clauses_buyers:
        buyer_match = await db.scalar(
            select(BuyerRecord.id).where(or_(*clauses_buyers)).limit(1)
        )
        if buyer_match:
            return True

    return False


async def filter_single_record(
    db: AsyncSession,
    raw: dict,
    source_category: str = "all",
) -> tuple[dict | None, str | None]:
    """Apply the shared filter: contact check -> product check -> duplicate check.

    Returns (clean_record, None) if accepted, or (None, drop_reason) if dropped.
    Possible drop reasons: 'invalid_contact', 'product_mismatch', 'duplicate'.
    """
    # 1. Contact check: needs at least a valid email or phone with country code
    email = normalize_email(raw.get("email"))
    phone = normalize_phone(raw.get("phone"))
    if not email and not phone:
        return None, "invalid_contact"

    # 2. Product match: check text content (title, message, requirement, product_name)
    combined_text = " ".join(
        str(raw.get(k, ""))
        for k in ("product", "title", "message", "description", "requirement", "category")
        if raw.get(k)
    )
    category_slug, matched_kw = match_product_category(combined_text, source_category)
    if not category_slug:
        return None, "product_mismatch"

    # 3. Duplicate check against existing leads and buyer_records
    if await is_duplicate(db, email, phone):
        return None, "duplicate"

    clean_record = {
        "company": (raw.get("company") or raw.get("contact_name") or "External Buyer")[:200].strip(),
        "contact_name": (raw.get("contact_name") or "")[:120].strip(),
        "email": email[:255],
        "phone": phone[:40],
        "country": (raw.get("country") or "India")[:80].strip(),
        "website": (raw.get("website") or raw.get("source_url") or "")[:255].strip(),
        "category": category_slug,
        "matched_keyword": matched_kw,
        "raw_message": raw.get("message") or raw.get("description") or "",
        "source_url": raw.get("source_url") or "",
    }
    return clean_record, None


async def save_accepted_records(
    db: AsyncSession,
    source: HarvestSource,
    accepted_records: list[dict],
    run_timestamp: datetime | None = None,
) -> int:
    """Save accepted records into a dated record_lists batch with DPDP Act provenance notes.

    Returns the number of saved records.
    """
    if not accepted_records:
        return 0

    now = run_timestamp or datetime.now(timezone.utc)
    today_str = now.astimezone(ZoneInfo("Asia/Kolkata")).strftime("%Y-%m-%d")
    list_name = f"Harvester - {today_str}"

    # Find or create today's harvester RecordList
    record_list = await db.scalar(
        select(RecordList).where(RecordList.name == list_name).limit(1)
    )
    if not record_list:
        record_list = RecordList(name=list_name, rows=0, uploaded_by=None)
        db.add(record_list)
        await db.flush()

    for item in accepted_records:
        dpdp_note = (
            f"Source: {source.name} ({source.source_type}) | "
            f"DPDP Provenance: {item.get('source_url') or source.url} | "
            f"Ingested: {now.isoformat()} | "
            f"Matched Keyword: {item.get('matched_keyword', '')}\n"
            f"Enquiry Details: {item.get('raw_message', '')}"
        )
        buyer = BuyerRecord(
            list_id=record_list.id,
            category=item["category"],
            company=item["company"],
            contact_name=item["contact_name"],
            email=item["email"],
            phone=item["phone"],
            country=item["country"],
            website=item["website"],
            notes=dpdp_note,
            status="new",
        )
        db.add(buyer)

    record_list.rows += len(accepted_records)
    await db.flush()
    return len(accepted_records)

