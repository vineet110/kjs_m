"""Uploads, downloads and approved deletes. Bytes go to storage (app/core/storage.py);
the `files` table keeps the key, name, size and who owns it.

Who may see/upload depends on the owner (an order board, a product…). Each owner type
registers a check with `register_owner(...)`, so this module doesn't need to know about
boards or products. Deleting a file is a request that an approver (`files.approve`) accepts.
"""
import asyncio
import hashlib
import logging
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Awaitable, Callable

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config.ini import cfg
from app.core.errors import AppError
from app.core.modules import AREA_OF_FILE_OWNER, require_visible, visible
from app.core.permissions import effective_permissions
from app.core.storage import StorageError, storage
from app.jobs.runner import job
from app.models.file import StoredFile
from app.models.user import User
from app.services import audit_service, notification_service

log = logging.getLogger(__name__)

# owner_type -> async check(db, user, owner_id, action) -> bool ; action is "read" or "write"
AccessCheck = Callable[[AsyncSession, User, str, str], Awaitable[bool]]
OWNERS: dict[str, AccessCheck] = {}
# owner_type -> async live(db, owner_id) -> bool. Only these owners may have files on the website,
# and only while the owner is live (e.g. a hidden product's files stop being public).
PublicCheck = Callable[[AsyncSession, str], Awaitable[bool]]
PUBLIC_OWNERS: dict[str, PublicCheck] = {}
# owner_type -> async approvers(db, owner_id) -> (user ids, link). People who may decide delete requests
# for files of that owner, on top of everyone with files.approve (e.g. an order board's owner).
Approvers = Callable[[AsyncSession, str], Awaitable[tuple[set[int], str]]]
APPROVERS: dict[str, Approvers] = {}

TYPES = {"pdf": "application/pdf", "png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
         "webp": "image/webp", "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
         "xls": "application/vnd.ms-excel", "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
         "doc": "application/msword", "csv": "text/csv", "txt": "text/plain", "zip": "application/zip",
         "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
         "ppt": "application/vnd.ms-powerpoint", "gif": "image/gif", "heic": "image/heic",
         "mp4": "video/mp4", "mov": "video/quicktime"}


def register_owner(owner_type: str, check: AccessCheck, public: PublicCheck | None = None,
                   approvers: Approvers | None = None) -> None:
    OWNERS[owner_type] = check
    if public:
        PUBLIC_OWNERS[owner_type] = public
    if approvers:
        APPROVERS[owner_type] = approvers


async def _owner_approvers(db: AsyncSession, owner_type: str, owner_id: str) -> tuple[set[int], str]:
    hook = APPROVERS.get(owner_type)
    return await hook(db, owner_id) if hook else (set(), "")


async def can_decide(db: AsyncSession, user: User, owner_type: str, owner_id: str) -> bool:
    """May this person approve or reject delete requests for this owner's files?"""
    if "files.approve" in effective_permissions(user.role, user.permissions):
        return True
    return user.id in (await _owner_approvers(db, owner_type, owner_id))[0]


async def _publicly_visible(db: AsyncSession, owner_type: str, owner_id: str) -> bool:
    live = PUBLIC_OWNERS.get(owner_type)
    return live is not None and await live(db, owner_id)


async def _check(db: AsyncSession, user: User, owner_type: str, owner_id: str, action: str) -> None:
    require_visible(user, AREA_OF_FILE_OWNER.get(owner_type))  # e.g. order boards switched off: 404
    check = OWNERS.get(owner_type)
    if check is None or not await check(db, user, owner_id, action):
        raise AppError(403, "forbidden", "You can't access these files.")


def safe_name(name: str) -> str:
    base = re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip("-.") or "file"
    return base[-120:]


def out(f: StoredFile, names: dict[int, str] | None = None) -> dict:
    return {"id": f.id, "name": f.name, "content_type": f.content_type, "size": f.size,
            "owner_type": f.owner_type, "owner_id": f.owner_id, "is_public": f.is_public,
            "uploaded_by_name": (names or {}).get(f.uploaded_by or 0, ""), "created_at": f.created_at,
            "delete_status": f.delete_status, "delete_reason": f.delete_reason}


async def upload(db: AsyncSession, user: User, upload_file: UploadFile, owner_type: str, owner_id: str,
                 is_public: bool = False) -> dict:
    if owner_type == "board":
        owner_id = owner_id.upper()  # board codes are upper case: "abc117-3" must land on ABC117-3
    await _check(db, user, owner_type, owner_id, "write")
    if is_public and owner_type not in PUBLIC_OWNERS:
        # e.g. an order-board document must never become downloadable without login
        raise AppError(422, "not_public", "Only product files can be shown on the website.")
    name = upload_file.filename or "file"
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if ext not in cfg().storage.allowed_types or ext not in TYPES:
        raise AppError(422, "file_type", f"Files of type .{ext or '?'} are not allowed.",
                       {"allowed": cfg().storage.allowed_types})
    limit = cfg().storage.max_upload_mb * 1024 * 1024
    data = await upload_file.read(limit + 1)
    if len(data) > limit:
        raise AppError(413, "too_big", f"Max file size is {cfg().storage.max_upload_mb} MB.")
    if not data:
        raise AppError(422, "empty", "The file is empty.")
    key = f"{owner_type}/{safe_name(owner_id)}/{uuid.uuid4().hex[:12]}-{safe_name(name)}"
    try:
        await asyncio.to_thread(storage().put, key, data, TYPES[ext])
    except StorageError as e:
        raise AppError(502, "storage", "Could not save the file. Please try again.") from e
    try:
        f = StoredFile(key=key, name=name[:200], content_type=TYPES[ext], size=len(data),
                       sha256=hashlib.sha256(data).hexdigest(), owner_type=owner_type, owner_id=owner_id,
                       is_public=is_public, uploaded_by=user.id, delete_status="none", delete_reason="")
        db.add(f)
        await db.flush()
        audit_service.record(db, actor=user, action="file.uploaded", entity_type="file", entity_id=f.id,
                             after={"name": f.name, "owner": f"{owner_type}:{owner_id}", "size": f.size})
    except Exception:
        # Failed before the save: no row will point to the stored copy, so remove it ("deleted" must mean
        # deleted, and nothing else would ever find it). If even that fails, it is logged for a clean-up.
        try:
            await asyncio.to_thread(storage().delete, key)
        except Exception:  # noqa: BLE001 - the first error is the one to report
            log.warning("file.orphan_left", extra={"key": key})
        raise
    # Not inside the clean-up: a commit that fails on the way back may still have saved the row, and
    # deleting the file then would lose it. An unused copy (logged by nobody) is the safer mistake.
    await db.commit()
    return out(f, {user.id: user.name})


async def list_files(db: AsyncSession, user: User, owner_type: str, owner_id: str) -> list[dict]:
    if owner_type == "board":
        owner_id = owner_id.upper()
    await _check(db, user, owner_type, owner_id, "read")
    rows = (await db.scalars(select(StoredFile).where(
        StoredFile.owner_type == owner_type, StoredFile.owner_id == owner_id, StoredFile.deleted_at.is_(None))
        .order_by(StoredFile.id.desc()))).all()
    names = dict((await db.execute(select(User.id, User.name))).all())
    # own_request: this person asked for the delete, so someone else must decide it (admins excepted)
    return [out(f, names) | {"own_request": f.delete_requested_by == user.id and user.role != "admin"} for f in rows]


async def public_files(db: AsyncSession, owner_type: str, owner_id: str) -> list[dict]:
    if not await _publicly_visible(db, owner_type, owner_id):
        return []
    rows = (await db.scalars(select(StoredFile).where(
        StoredFile.owner_type == owner_type, StoredFile.owner_id == owner_id, StoredFile.is_public.is_(True),
        StoredFile.deleted_at.is_(None)).order_by(StoredFile.id))).all()
    return [{"id": f.id, "name": f.name, "content_type": f.content_type, "url": f"/api/v1/public/files/{f.id}"}
            for f in rows]


async def _get(db: AsyncSession, file_id: int, lock: bool = False) -> StoredFile:
    # lock=True: hold the row until commit, so two approvers can't decide the same request at once
    f = await db.get(StoredFile, file_id, with_for_update=lock, populate_existing=lock)
    if f is None or f.deleted_at is not None:
        raise AppError(404, "not_found", "File not found.")
    return f


async def download(db: AsyncSession, user: User | None, file_id: int) -> tuple[StoredFile, str | None, Path | bytes | None]:
    """Returns (file, redirect_url, content). R2 gives a 5-minute link; local storage gives the path
    on disk, so the file is streamed instead of loaded into memory."""
    f = await _get(db, file_id)
    if user is None:  # the public website: only public files of a live product
        if not (f.is_public and await _publicly_visible(db, f.owner_type, f.owner_id)):
            raise AppError(404, "not_found", "File not found.")
    elif not f.is_public:
        await _check(db, user, f.owner_type, f.owner_id, "read")
    url = storage().url(f.key, safe_name(f.name))  # safe_name: quotes or non-Latin names would break the header
    if url:
        return f, url, None
    store = storage()
    try:
        if hasattr(store, "file_path"):
            return f, None, store.file_path(f.key)
        return f, None, await asyncio.to_thread(store.get, f.key)
    except StorageError as e:
        raise AppError(404, "not_found", "File not found.") from e


async def view(db: AsyncSession, user: User, file_id: int) -> tuple[StoredFile, Path | bytes]:
    """The file's bytes for the in-page preview (staff only, same access as download). Always sent by
    our API, never a storage link: the page shows it inside our own site, and R2 stays private."""
    f = await _get(db, file_id)
    await _check(db, user, f.owner_type, f.owner_id, "read")
    store = storage()
    try:
        if hasattr(store, "file_path"):
            return f, store.file_path(f.key)
        return f, await asyncio.to_thread(store.get, f.key)
    except StorageError as e:
        raise AppError(404, "not_found", "File not found.") from e


async def request_delete(db: AsyncSession, user: User, file_id: int, reason: str) -> dict:
    f = await _get(db, file_id, lock=True)
    await _check(db, user, f.owner_type, f.owner_id, "write")  # seeing a file isn't enough to ask to delete it
    if f.delete_status == "requested":
        raise AppError(409, "already_requested", "Deletion was already requested.")
    f.delete_status, f.delete_reason, f.delete_requested_by = "requested", reason.strip(), user.id
    audit_service.record(db, actor=user, action="file.delete_requested", entity_type="file", entity_id=f.id,
                         after={"name": f.name, "reason": f.delete_reason})
    approvers = set(await notification_service.users_with(db, "files.approve")) - {user.id}
    notification_service.notify(db, approvers, "file.delete_request",
                                f"Delete request: {f.name}", f"{user.name}: {f.delete_reason}", "/admin/approvals")
    owners, link = await _owner_approvers(db, f.owner_type, f.owner_id)
    notification_service.notify(db, owners - approvers - {user.id}, "file.delete_request",
                                f"Delete request: {f.name}", f"{user.name}: {f.delete_reason}", link)
    await db.commit()
    return out(f)


async def delete_requests(db: AsyncSession, user: User) -> list[dict]:
    """Open delete requests, without files of areas hidden from this person (config/modules.ini)."""
    rows = (await db.execute(select(StoredFile, User.name).join(User, User.id == StoredFile.delete_requested_by)
                             .where(StoredFile.delete_status == "requested", StoredFile.deleted_at.is_(None))
                             .order_by(StoredFile.updated_at))).all()
    return [out(f) | {"requested_by_name": n} for f, n in rows
            if visible(user, AREA_OF_FILE_OWNER.get(f.owner_type))]


async def decide_delete(db: AsyncSession, approver: User, file_id: int, approve: bool) -> dict:
    # Check rights on a plain read first: someone who may not decide gets the same 403 whether the
    # file exists or not, and never takes the row lock.
    f = await db.get(StoredFile, file_id)
    allowed = f is not None and await can_decide(db, approver, f.owner_type, f.owner_id)
    if not allowed and "files.approve" not in effective_permissions(approver.role, approver.permissions):
        raise AppError(403, "forbidden", "Only the owner or an approver can decide this.")
    f = await _get(db, file_id, lock=True)
    require_visible(approver, AREA_OF_FILE_OWNER.get(f.owner_type))
    if f.delete_status != "requested":
        raise AppError(409, "not_requested", "No delete request for this file.")
    if f.delete_requested_by == approver.id and approver.role != "admin":
        raise AppError(403, "own_request", "Someone else must approve your own delete request.")
    f.delete_status = "approved" if approve else "rejected"
    if approve:
        f.deleted_at = datetime.now(timezone.utc)
    audit_service.record(db, actor=approver, action=f"file.delete_{f.delete_status}", entity_type="file",
                         entity_id=f.id, before={"name": f.name})
    if f.delete_requested_by:
        notification_service.notify(db, [f.delete_requested_by], "file.delete_decided",
                                    f"Delete {f.delete_status}: {f.name}", "", "")
    await db.commit()
    if approve:  # only after the decision is saved: a failed commit must not lose the file
        try:
            await asyncio.to_thread(storage().delete, f.key)
            f.purged_at = datetime.now(timezone.utc)
            await db.commit()
        except StorageError:
            log.warning("file.purge_later", extra={"file_id": f.id})  # the purge job retries it
    return out(f)


@job("purge_deleted_files", any_time=True)
async def purge_deleted_files(db: AsyncSession) -> dict:
    """Approved deletes whose stored copy couldn't be removed at the time (storage was down).
    "Deleted" must really mean deleted (personal data, DPDP)."""
    rows = (await db.scalars(select(StoredFile).where(StoredFile.deleted_at.is_not(None),
                                                      StoredFile.purged_at.is_(None)).limit(50))).all()
    purged = 0
    for f in rows:
        try:
            await asyncio.to_thread(storage().delete, f.key)
        except StorageError:
            continue  # still down: next run
        f.purged_at = datetime.now(timezone.utc)
        purged += 1
    return {"waiting": len(rows), "purged": purged}
