"""Files: upload, list, download, request delete. Who may do what depends on the owner
(order board, product); approving deletes needs `files.approve` or the owner's approvers (a board's owner)."""
from fastapi import APIRouter, Depends, File, Form, UploadFile
from pathlib import Path

from fastapi.responses import FileResponse, RedirectResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import current_user, require_permission
from app.models.user import User
from app.services import file_service

router = APIRouter()


@router.post("", status_code=201)
async def upload(owner_type: str = Form(...), owner_id: str = Form(...), is_public: bool = Form(False),
                 file: UploadFile = File(...), user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    return await file_service.upload(db, user, file, owner_type, owner_id, is_public)


@router.get("")
async def list_files(owner_type: str, owner_id: str, user: User = Depends(current_user),
                     db: AsyncSession = Depends(get_db)):
    return await file_service.list_files(db, user, owner_type, owner_id)


def send_file(f, url: str | None, data: Path | bytes | None, inline: bool = False):
    if url:
        return RedirectResponse(url, status_code=302)
    disposition = "inline" if inline else f'attachment; filename="{file_service.safe_name(f.name)}"'
    # sandbox: even if an uploaded PDF carries scripts, they can't run as our website
    headers = {"content-disposition": disposition, "x-content-type-options": "nosniff",
               "content-security-policy": "sandbox"}
    # Public website files (product photos) may be cached by browsers and Cloudflare for an hour;
    # staff files never are.
    headers["cache-control"] = "public, max-age=3600" if inline else "private, no-store"
    if isinstance(data, Path):  # local disk: streamed in chunks, never loaded whole into memory
        return FileResponse(data, media_type=f.content_type, headers=headers)
    return Response(data, media_type=f.content_type, headers=headers)


@router.get("/{file_id}/download")
async def download(file_id: int, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    return send_file(*await file_service.download(db, user, file_id))


@router.get("/{file_id}/view")
async def view(file_id: int, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    """The file for the in-page preview: shown inside the page (inline), never cached, never a storage link.
    The type comes from the file's extension (checked at upload) and nosniff stops the browser guessing,
    so an uploaded file can't turn into a web page. Scripts can't run in it (sandbox), except that
    Chrome's PDF viewer refuses to open a sandboxed PDF, so PDFs go without it: a PDF opens in the
    browser's own viewer, not as our website."""
    f, data = await file_service.view(db, user, file_id)
    headers = {"content-disposition": "inline", "x-content-type-options": "nosniff",
               "cache-control": "private, no-store"}
    if f.content_type != "application/pdf":
        headers["content-security-policy"] = "sandbox"
    if isinstance(data, Path):
        return FileResponse(data, media_type=f.content_type, headers=headers)
    return Response(data, media_type=f.content_type, headers=headers)


class DeleteRequestIn(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


@router.post("/{file_id}/delete-request")
async def request_delete(file_id: int, data: DeleteRequestIn, user: User = Depends(current_user),
                         db: AsyncSession = Depends(get_db)):
    return await file_service.request_delete(db, user, file_id, data.reason)


@router.get("/delete-requests")
async def delete_requests(_: User = Depends(require_permission("files.approve")), db: AsyncSession = Depends(get_db)):
    return await file_service.delete_requests(db)


class DecideIn(BaseModel):
    approve: bool


@router.post("/{file_id}/delete-decision")
async def decide(file_id: int, data: DecideIn, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    # files.approve, or the owner's own approvers (e.g. an order board's owner): checked in the service
    return await file_service.decide_delete(db, user, file_id, data.approve)
