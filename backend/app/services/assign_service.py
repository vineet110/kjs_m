"""Auto-assign: import buyer records (Excel/CSV), then hand them out in batches.

Rules (config/assign.ini):
- Only to staff who are active, checked in today, have "receiving tasks" on, and have at
  least one category (backlog D10).
- One open batch per person at a time; at most max_batches_per_day per day.
- A batch is up to batch_size records from the person's categories, oldest first.
- Fair: people with fewer batches today go first.
- The `auto_assign` job runs between work_start and work_end; "Run now" works any time.
Records are locked with FOR UPDATE SKIP LOCKED, so two runs can never give one record twice.
"""
import asyncio
import csv
import io
import logging
import zipfile
import zlib
from datetime import datetime, timezone

from openpyxl import load_workbook
from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config.ini import cfg
from app.core.errors import AppError
from app.jobs.runner import job
from app.models.attendance import Attendance
from app.models.batch import Batch, BuyerRecord, RecordList
from app.models.catalog import Category
from app.models.user import User
from app.services import audit_service, notification_service
from app.services.attendance_service import local_day, tz

log = logging.getLogger(__name__)
MAX_ROWS = 5000
MAX_COLS = 30
READ_ROWS = 2 * MAX_ROWS + 1  # header + data, with room for empty rows; more than MAX_ROWS real rows is refused
MAX_UNZIPPED_MB = 60  # an .xlsx is a zip: a small file can unpack to gigabytes ("zip bomb")
COLUMNS = {  # our field -> header names people actually use
    "company": ("company", "company name", "business", "buyer", "name"),
    "contact_name": ("contact", "contact name", "person", "contact person"),
    "email": ("email", "e-mail", "mail"),
    "phone": ("phone", "mobile", "whatsapp", "tel", "telephone"),
    "country": ("country",),
    "website": ("website", "url", "site", "web"),
    "category": ("category", "product category"),
    "notes": ("notes", "remarks", "comment", "comments"),
}
LIMITS = {"company": 200, "contact_name": 120, "email": 255, "phone": 40, "country": 80, "website": 255, "category": 60}


# ---------- Import ----------
def read_rows(filename: str, data: bytes) -> list[dict]:
    """Excel (.xlsx) or CSV -> list of {field: text}. The first row must be the headers."""
    name = filename.lower()
    if name.endswith(".xlsx"):
        try:
            unzipped = sum(i.file_size for i in zipfile.ZipFile(io.BytesIO(data)).infolist())
        except zipfile.BadZipFile as e:
            raise AppError(422, "bad_file", "Could not read this Excel file.") from e
        if unzipped > MAX_UNZIPPED_MB * 1024 * 1024:
            raise AppError(422, "bad_file", "This Excel file is too big. Please split it into smaller files.")
        try:
            ws = load_workbook(io.BytesIO(data), read_only=True, data_only=True).active
            # Read a bounded number of rows and MAX_COLS columns, never the whole sheet. (Twice
            # MAX_ROWS, because Excel files often carry empty formatted rows.)
            table = [[("" if c is None else str(c)).strip() for c in row]
                     for row in ws.iter_rows(max_row=READ_ROWS, max_col=MAX_COLS, values_only=True)]
        except Exception as e:  # openpyxl raises many types for a bad file
            raise AppError(422, "bad_file", "Could not read this Excel file.") from e
    elif name.endswith(".csv"):
        try:
            reader = csv.reader(io.StringIO(data.decode("utf-8-sig", errors="replace")))
            table = [[c.strip() for c in row[:MAX_COLS]] for _, row in zip(range(READ_ROWS), reader)]
        except csv.Error as e:
            raise AppError(422, "bad_file", "Could not read this CSV file.") from e
    else:
        raise AppError(422, "bad_file", "Please upload an .xlsx or .csv file.")
    table = [r for r in table if any(r)]  # ignore empty rows
    if not table:
        return []
    if len(table) - 1 > MAX_ROWS:
        # Never cut silently: the manager would think every buyer was imported.
        raise AppError(422, "too_many_rows", f"This file has more than {MAX_ROWS} rows. "
                                             f"Please split it into files of up to {MAX_ROWS} rows.")
    headers = [h.lower() for h in table[0]]
    index = {field: next((headers.index(a) for a in aliases if a in headers), None) for field, aliases in COLUMNS.items()}
    if index["company"] is None:
        raise AppError(422, "bad_file", "The first row needs a 'Company' column.", {"found": table[0]})
    rows = []
    for raw in table[1:MAX_ROWS + 1]:
        row = {f: (raw[i] if i is not None and i < len(raw) else "") for f, i in index.items()}
        rows.append({k: v[:LIMITS[k]] if k in LIMITS else v for k, v in row.items()})
    return rows


async def import_records(db: AsyncSession, user: User, filename: str, data: bytes, default_category: str) -> dict:
    cats = {c.slug: c.slug for c in (await db.scalars(select(Category))).all()}
    cats |= {c.name.lower(): c.slug for c in (await db.scalars(select(Category))).all()}
    rows = await asyncio.to_thread(read_rows, filename, data)  # parsing is slow: keep the server responsive
    lst = RecordList(name=filename[:200], rows=0, uploaded_by=user.id)
    db.add(lst)
    await db.flush()
    # Same company + email already imported (now or in an earlier file) = the same buyer: skip it,
    # so re-uploading a list never makes two people call the same company.
    companies = {r["company"].strip().lower() for r in rows if r["company"]}
    seen = set()
    for chunk in [sorted(companies)[i:i + 1000] for i in range(0, len(companies), 1000)]:
        seen |= set((await db.execute(
            select(func.lower(BuyerRecord.company), func.lower(BuyerRecord.email))
            .where(func.lower(BuyerRecord.company).in_(chunk)))).all())
    added, skipped = 0, []
    for n, r in enumerate(rows, start=2):  # row 1 = headers
        cat = cats.get((r["category"] or default_category).strip().lower())
        if not r["company"]:
            skipped.append({"row": n, "reason": "no company"})
            continue
        if not cat:
            skipped.append({"row": n, "reason": f"unknown category '{r['category'] or default_category}'"})
            continue
        key = (r["company"].strip().lower(), r["email"].strip().lower())
        if key in seen:
            skipped.append({"row": n, "reason": "already imported"})
            continue
        seen.add(key)
        db.add(BuyerRecord(list_id=lst.id, category=cat, company=r["company"], contact_name=r["contact_name"],
                           email=r["email"], phone=r["phone"], country=r["country"], website=r["website"],
                           notes=r["notes"], status="new", outcome=""))
        added += 1
    lst.rows = added
    audit_service.record(db, actor=user, action="records.imported", entity_type="record_list", entity_id=lst.id,
                         after={"file": filename, "added": added, "skipped": len(skipped)})
    await db.commit()
    return {"list_id": lst.id, "added": added, "skipped": skipped[:50], "skipped_count": len(skipped)}


# ---------- Who can get a batch ----------
async def _eligible(db: AsyncSession, now: datetime) -> list[tuple[User, int]]:
    """(user, batches already given today) for everyone who may get a batch right now."""
    today = local_day(now)
    checked_in = select(Attendance.user_id).where(Attendance.day == today, Attendance.check_in_at.is_not(None),
                                                  Attendance.check_out_at.is_(None))
    has_open = select(Batch.user_id).where(Batch.status == "open")
    users = (await db.scalars(select(User).where(
        User.status == "active", User.is_available.is_(True), User.id.in_(checked_in), User.id.not_in(has_open),
    ).order_by(User.id))).all()
    counts = dict((await db.execute(select(Batch.user_id, func.count()).where(Batch.day == today)
                                    .group_by(Batch.user_id))).all())
    limit = cfg().assign.max_batches_per_day
    out = [(u, counts.get(u.id, 0)) for u in users if u.categories and counts.get(u.id, 0) < limit]
    return sorted(out, key=lambda x: (x[1], x[0].id))  # fewest batches today first


async def preview(db: AsyncSession, now: datetime | None = None) -> list[dict]:
    """Who would get how many records if we ran now (nothing is saved)."""
    now = now or datetime.now(timezone.utc)
    size = cfg().assign.batch_size
    free = dict((await db.execute(select(BuyerRecord.category, func.count()).where(BuyerRecord.status == "new")
                                  .group_by(BuyerRecord.category))).all())
    plan = []
    for user, done_today in await _eligible(db, now):
        take = 0
        for cat in user.categories:
            n = min(size - take, free.get(cat, 0))
            free[cat] = free.get(cat, 0) - n
            take += n
        plan.append({"user_id": user.id, "name": user.name, "categories": user.categories,
                     "batches_today": done_today, "would_get": take})
    return plan


async def run(db: AsyncSession, actor: User | None = None, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    # Same lock as the auto_assign job: "Run now" waits for a running job (and a double click
    # waits for the first click), so nobody gets two open batches.
    await db.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": zlib.crc32(b"auto_assign")})
    size, given = cfg().assign.batch_size, []
    for user, _ in await _eligible(db, now):
        records = (await db.scalars(
            select(BuyerRecord).where(BuyerRecord.status == "new", BuyerRecord.category.in_(user.categories))
            .order_by(BuyerRecord.id).limit(size).with_for_update(skip_locked=True)
        )).all()
        if not records:
            continue
        batch = Batch(user_id=user.id, day=local_day(now), size=len(records), status="open")
        db.add(batch)
        await db.flush()
        for r in records:
            r.status, r.batch_id = "assigned", batch.id
        notification_service.notify(db, [user.id], "batch.assigned", f"New batch: {len(records)} records",
                                    "Work through them and mark each one done.", "/employee/batches")
        given.append({"user_id": user.id, "name": user.name, "records": len(records)})
    if given:
        audit_service.record(db, actor=actor, action="batches.assigned", entity_type="batch",
                             after={"given": given, "by": "run_now" if actor else "job"})
    await db.commit()
    return {"batches": len(given), "given": given}


def in_assign_hours(now: datetime) -> bool:
    c = cfg().assign
    local = now.astimezone(tz())
    return local.weekday() != 6 and c.work_start <= local.strftime("%H:%M") < c.work_end


@job("auto_assign", module="batches")
async def auto_assign(db: AsyncSession) -> dict:
    now = datetime.now(timezone.utc)
    if not in_assign_hours(now):
        return {"skipped": "outside assign hours"}
    return await run(db, None, now)


# ---------- Working a batch ----------
def record_out(r: BuyerRecord) -> dict:
    return {"id": r.id, "category": r.category, "company": r.company, "contact_name": r.contact_name,
            "email": r.email, "phone": r.phone, "country": r.country, "website": r.website, "notes": r.notes,
            "status": r.status, "outcome": r.outcome, "done_at": r.done_at}


async def my_batches(db: AsyncSession, user: User) -> list[dict]:
    batches = (await db.scalars(select(Batch).where(Batch.user_id == user.id)
                                .order_by(Batch.status != "open", Batch.id.desc()).limit(10))).all()
    out = []
    for b in batches:
        recs = (await db.scalars(select(BuyerRecord).where(BuyerRecord.batch_id == b.id).order_by(BuyerRecord.id))).all()
        done = sum(1 for r in recs if r.status in ("done", "skipped"))
        out.append({"id": b.id, "day": b.day, "status": b.status, "size": b.size, "done": done,
                    "records": [record_out(r) for r in recs] if b.status == "open" else []})
    return out


async def return_open_batch(db: AsyncSession, user_id: int) -> int:
    """Give back the unfinished buyers of this person's open batch (they left, or were disabled). The
    batch becomes "returned" (not "done": half of it was never worked on). Returns how many came back.
    The caller commits."""
    batch = await db.scalar(select(Batch).where(Batch.user_id == user_id, Batch.status == "open").with_for_update())
    if batch is None:
        return 0
    back = (await db.execute(update(BuyerRecord).where(BuyerRecord.batch_id == batch.id, BuyerRecord.status == "assigned")
                             .values(status="new", batch_id=None))).rowcount
    batch.status = "returned"
    return back


async def update_record(db: AsyncSession, user: User, record_id: int, status: str, outcome: str) -> dict:
    r = await db.get(BuyerRecord, record_id)
    # Lock the batch: two quick "done" clicks on its last two records must not both see "1 left"
    batch = await db.get(Batch, r.batch_id, with_for_update=True) if r and r.batch_id else None
    if r is None or batch is None or batch.user_id != user.id:
        raise AppError(404, "not_found", "Record not found.")
    if batch.status != "open":
        # A finished batch stays finished; reopening it would also block this person from new batches.
        raise AppError(409, "batch_closed", "This batch is already finished.")
    before = {"status": r.status, "outcome": r.outcome}
    r.status, r.outcome = status, outcome.strip()
    r.done_at = datetime.now(timezone.utc) if status in ("done", "skipped") else None
    await db.flush()
    left = await db.scalar(select(func.count()).select_from(BuyerRecord).where(
        BuyerRecord.batch_id == batch.id, BuyerRecord.status == "assigned"))
    batch.status = "open" if left else "done"
    audit_service.record(db, actor=user, action="buyer_record.updated", entity_type="buyer_record",
                         entity_id=r.id, before=before, after={"status": r.status, "outcome": r.outcome})
    await db.commit()
    return {"record": record_out(r), "batch_status": batch.status, "left": left}


# ---------- Admin overview ----------
async def overview(db: AsyncSession) -> dict:
    now = datetime.now(timezone.utc)
    today = local_day(now)
    staff = (await db.scalars(select(User).where(User.status == "active").order_by(User.name))).all()
    checked_in = set((await db.scalars(select(Attendance.user_id).where(
        Attendance.day == today, Attendance.check_in_at.is_not(None), Attendance.check_out_at.is_(None)))).all())
    today_counts = dict((await db.execute(select(Batch.user_id, func.count()).where(Batch.day == today)
                                          .group_by(Batch.user_id))).all())
    open_batches = {b.user_id: b for b in (await db.scalars(select(Batch).where(Batch.status == "open"))).all()}
    progress = dict((await db.execute(select(BuyerRecord.batch_id, func.count()).where(
        BuyerRecord.status.in_(["done", "skipped"]), BuyerRecord.batch_id.in_([b.id for b in open_batches.values()]))
        .group_by(BuyerRecord.batch_id))).all())
    free = dict((await db.execute(select(BuyerRecord.category, func.count()).where(BuyerRecord.status == "new")
                                  .group_by(BuyerRecord.category))).all())
    lists = (await db.scalars(select(RecordList).order_by(RecordList.id.desc()).limit(10))).all()
    c = cfg().assign
    return {
        "settings": c.model_dump(),
        "in_hours": in_assign_hours(now),
        "unassigned": free,
        "staff": [{"user_id": u.id, "name": u.name, "categories": u.categories, "is_available": u.is_available,
                   "checked_in": u.id in checked_in, "batches_today": today_counts.get(u.id, 0),
                   "open_batch": ({"size": open_batches[u.id].size, "done": progress.get(open_batches[u.id].id, 0)}
                                  if u.id in open_batches else None)} for u in staff],
        "lists": [{"id": x.id, "name": x.name, "rows": x.rows, "created_at": x.created_at} for x in lists],
    }


async def set_categories(db: AsyncSession, actor: User, user_id: int, categories: list[str]) -> None:
    valid = set((await db.scalars(select(Category.slug))).all())
    if set(categories) - valid:
        raise AppError(422, "bad_category", "Unknown category.", {"unknown": sorted(set(categories) - valid)})
    u = await db.get(User, user_id)
    if u is None:
        raise AppError(404, "not_found", "User not found.")
    before = list(u.categories or [])
    u.categories = sorted(set(categories))
    audit_service.record(db, actor=actor, action="user.categories", entity_type="user", entity_id=u.id,
                         before={"categories": before}, after={"categories": u.categories})
    await db.commit()
