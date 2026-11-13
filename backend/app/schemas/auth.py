from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.common import Email, OneLine, RequiredPhone


class SignupIn(BaseModel):
    name: OneLine = Field(min_length=2, max_length=100)
    email: Email
    phone: RequiredPhone = Field(max_length=20)
    password: str = Field(min_length=10, max_length=200)


class LoginIn(BaseModel):
    email: Email
    password: str = Field(max_length=200)


class MeOut(BaseModel):
    id: int
    name: str
    email: str
    role: str
    permissions: list[str]
    modules: dict[str, bool] = {}  # portal area -> can this person use it (config/modules.ini)


class UserOut(BaseModel):
    id: int
    name: str
    email: str
    phone: str | None
    role: str
    status: str
    permissions: list[str]
    created_at: datetime
    employee_code: str = ""
    branch: str = ""  # shown as "Department"
    job_title: str = ""
    reporting_to: int | None = None
    # Sign-up decision: who approved or rejected it, when, and why it was rejected
    approved_by: int | None = None
    approved_at: datetime | None = None
    rejection_reason: str | None = None

    model_config = {"from_attributes": True}


class ApproveIn(BaseModel):
    permissions: list[str] = Field(default_factory=list)


class RejectIn(BaseModel):
    reason: OneLine = Field(min_length=3, max_length=500)  # required: the person may ask why


class PermissionsIn(BaseModel):
    permissions: list[str] = Field(default_factory=list, max_length=50)


class JobTitleIn(BaseModel):
    name: OneLine = Field(min_length=2, max_length=60)


class StaffDetailsIn(BaseModel):
    """What the admin sets on the User Creation Form (and can change later)."""
    employee_code: OneLine = Field(min_length=1, max_length=40)
    branch: OneLine = Field(min_length=1, max_length=80)  # "Department" on screen
    role: Literal["admin", "employee"]  # "Admin access" on screen
    job_title: OneLine = Field(default="", max_length=60)  # empty or a name from job_titles
    reporting_to: int | None = None  # empty = top of the chain (the top admin reports to no one)


class UserCreateIn(StaffDetailsIn):
    name: OneLine = Field(min_length=2, max_length=100)
    email: Email
    phone: RequiredPhone = Field(max_length=20)


class UserPatchIn(BaseModel):
    """Edit an account: only the fields sent change (two admins editing different fields don't undo
    each other). The result is checked as a whole (UserUpdateIn)."""
    name: OneLine | None = Field(default=None, min_length=2, max_length=100)
    phone: RequiredPhone | None = Field(default=None, max_length=20)
    employee_code: OneLine | None = Field(default=None, min_length=1, max_length=40)
    branch: OneLine | None = Field(default=None, min_length=1, max_length=80)
    role: Literal["admin", "employee"] | None = None
    job_title: OneLine | None = Field(default=None, max_length=60)
    reporting_to: int | None = None


class UserUpdateIn(StaffDetailsIn):
    name: OneLine = Field(min_length=2, max_length=100)
    phone: RequiredPhone = Field(max_length=20)
