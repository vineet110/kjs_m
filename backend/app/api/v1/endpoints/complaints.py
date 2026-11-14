"""Complaints ("Report a problem"): any logged-in staff member files one; admins (staff.approve) list them.
The screenshot is uploaded after filing, through /files with owner_type "complaint"."""
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import current_user, require_permission
from app.models.user import User
from app.services import complaint_service
from app.services.complaint_service import MIN_DESCRIPTION_WORDS, MIN_TITLE_WORDS, words

router = APIRouter()


class ComplaintIn(BaseModel):
    kind: Literal["bug", "issue", "suggestion"]
    title: str = Field(max_length=200)
    description: str = Field(max_length=5000)
    # The page it was filed from, sent by the portal: a path like /employee/internal-leads, never a full link
    page_path: str = Field(max_length=300, pattern=r"^/[^\s]*$")

    @field_validator("title")
    @classmethod
    def title_words(cls, v: str) -> str:
        if words(v) < MIN_TITLE_WORDS:
            raise ValueError(f"Write at least {MIN_TITLE_WORDS} words in the title.")
        return v

    @field_validator("description")
    @classmethod
    def description_words(cls, v: str) -> str:
        if words(v) < MIN_DESCRIPTION_WORDS:
            raise ValueError(f"Write at least {MIN_DESCRIPTION_WORDS} words in the description.")
        return v


@router.post("", status_code=201)
async def file_complaint(data: ComplaintIn, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    return await complaint_service.file_complaint(db, user, data.kind, data.title, data.description, data.page_path)


@router.get("")
async def list_complaints(_: User = Depends(require_permission("staff.approve")), db: AsyncSession = Depends(get_db)):
    return await complaint_service.list_complaints(db)
