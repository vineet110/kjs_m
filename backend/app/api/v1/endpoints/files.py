"""Files: upload, list, download, request delete. Who may do what depends on the owner
(order board, product); approving deletes needs `files.approve`."""
from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import RedirectResponse, Response
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


def send_file(f, url: str | None, data: bytes | None, inline: bool = False):
    if url:
        return RedirectResponse(url, status_code=302)
    disposition = "inline" if inline else f'attachment; filename="{file_service.safe_name(f.name)}"'
    # sandbox: even if an uploaded PDF carries scripts, they can't run as our website
    return Response(data, media_type=f.content_type, headers={"content-disposition": disposition,
                                                               "x-content-type-options": "nosniff",
                                                               "content-security-policy": "sandbox"})


@router.get("/{file_id}/download")
async def download(file_id: int, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    return send_file(*await file_service.download(db, user, file_id))


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
async def decide(file_id: int, data: DecideIn, user: User = Depends(require_permission("files.approve")),
                 db: AsyncSession = Depends(get_db)):
    return await file_service.decide_delete(db, user, file_id, data.approve)
