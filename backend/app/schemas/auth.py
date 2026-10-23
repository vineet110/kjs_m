from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import Email


class SignupIn(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: Email
    phone: str = Field(default="", max_length=20)
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


class UserOut(BaseModel):
    id: int
    name: str
    email: str
    phone: str | None
    role: str
    status: str
    permissions: list[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class ApproveIn(BaseModel):
    permissions: list[str] = Field(default_factory=list)
