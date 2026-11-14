"""Complaints ("Report a problem"): staff report a bug, issue or suggestion from any portal page.

Saved in the database only for now. Later, each new one will also be emailed to the developer in
config/complaints.ini (developer_email), once sending email is set up.

A screenshot is an ordinary file with owner_type "complaint": the person who filed it may add one,
and they and admins (staff.approve) may see it.
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import effective_permissions
from app.models.complaint import Complaint
from app.models.file import StoredFile
from app.models.user import User
from app.services import audit_service, file_service

KINDS = ("bug", "issue", "suggestion")
MIN_TITLE_WORDS = 3
MIN_DESCRIPTION_WORDS = 15
LIST_LIMIT = 200  # newest first; enough for now (no paging yet)


def words(text: str) -> int:
    return len(text.split())


def _out(c: Complaint, names: dict[int, str], files: dict[str, list[dict]]) -> dict:
    return {"id": c.id, "kind": c.kind, "title": c.title, "description": c.description, "page_path": c.page_path,
            "created_at": c.created_at, "created_by_name": names.get(c.created_by or 0, ""),
            "files": files.get(str(c.id), [])}


async def file_complaint(db: AsyncSession, user: User, kind: str, title: str, description: str, page_path: str) -> dict:
    """Saves the report. The checks on words and lengths are in the route's input model."""
    c = Complaint(kind=kind, title=" ".join(title.split()), description=description.strip(),
                  page_path=page_path, created_by=user.id)
    db.add(c)
    await db.flush()
    # The audit row names the page and kind, not the text (it may hold a customer's details)
    audit_service.record(db, actor=user, action="complaint.filed", entity_type="complaint", entity_id=c.id,
                         after={"kind": kind, "page": page_path})
    await db.commit()
    await db.refresh(c)
    return _out(c, {user.id: user.name}, {})


async def list_complaints(db: AsyncSession) -> list[dict]:
    rows = (await db.scalars(select(Complaint).order_by(Complaint.id.desc()).limit(LIST_LIMIT))).all()
    names = dict((await db.execute(select(User.id, User.name))).all())
    files: dict[str, list[dict]] = {}
    if rows:
        found = await db.scalars(select(StoredFile).where(
            StoredFile.owner_type == "complaint", StoredFile.owner_id.in_([str(c.id) for c in rows]),
            StoredFile.deleted_at.is_(None)).order_by(StoredFile.id))
        for f in found:
            files.setdefault(f.owner_id, []).append({"id": f.id, "name": f.name, "content_type": f.content_type})
    return [_out(c, names, files) for c in rows]


def _complaint_id(owner_id: str) -> int | None:
    if not (owner_id.isascii() and owner_id.isdigit()) or len(owner_id) > 10:
        return None
    n = int(owner_id)
    return n if 0 < n <= 2**31 - 1 else None  # complaints.id is a database "integer"


async def _files_access(db: AsyncSession, user: User, owner_id: str, action: str) -> bool:
    """Screenshot: only the person who filed it may add one; they and admins may see it."""
    cid = _complaint_id(owner_id)
    c = await db.get(Complaint, cid) if cid else None
    if c is None:
        return False
    if c.created_by == user.id:
        return True
    return action == "read" and "staff.approve" in effective_permissions(user.role, user.permissions)


file_service.register_owner("complaint", _files_access,
                            clean=lambda owner_id: str(n) if (n := _complaint_id(owner_id)) else owner_id)
