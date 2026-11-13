from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field

from app.schemas.common import Email, OneLine, RequiredPhone


# The browser signs in with Firebase first; it sends the ID token it got (a signed proof of who it is),
# never the password. The email comes from the token, not from the form.
IdToken = Annotated[str, Field(min_length=20, max_length=4096)]


class SignupIn(BaseModel):
    id_token: IdToken
    name: OneLine = Field(min_length=2, max_length=100)
    phone: RequiredPhone = Field(max_length=20)


class LoginIn(BaseModel):
    id_token: IdToken


class PasswordChangedIn(BaseModel):
    """Sent right after the browser changed the password in Firebase (with a fresh sign-in)."""
    id_token: IdToken


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
    branch: str = ""
    reporting_to: int | None = None

    model_config = {"from_attributes": True}


class ApproveIn(BaseModel):
    permissions: list[str] = Field(default_factory=list)


class StaffDetailsIn(BaseModel):
    """What the admin sets on the User Creation Form (and can change later)."""
    employee_code: OneLine = Field(min_length=1, max_length=40)
    branch: OneLine = Field(min_length=1, max_length=80)
    role: Literal["admin", "employee"]
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
    reporting_to: int | None = None


class UserUpdateIn(StaffDetailsIn):
    name: OneLine = Field(min_length=2, max_length=100)
    phone: RequiredPhone = Field(max_length=20)
