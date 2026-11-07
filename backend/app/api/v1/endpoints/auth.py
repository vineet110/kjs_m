from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import client_ip, current_user
from app.core.permissions import effective_permissions
from app.core.security import hash_ip, hash_token
from app.models.user import User
from app.schemas.auth import LoginIn, MeOut, SignupIn
from app.schemas.common import OneLine, RequiredPhone
from app.services import auth_service

router = APIRouter()


def _me(user: User) -> MeOut:
    return MeOut(id=user.id, name=user.name, email=user.email, role=user.role,
                 permissions=sorted(effective_permissions(user.role, user.permissions)))


@router.post("/signup", status_code=201)
async def signup(data: SignupIn, request: Request, db: AsyncSession = Depends(get_db)):
    await auth_service.signup(db, data, hash_ip(client_ip(request)))
    return {"status": "pending", "message": "Account created. An admin will approve it soon."}


@router.post("/login", response_model=MeOut)
async def login(data: LoginIn, request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    user, token = await auth_service.login(db, data.email, data.password, hash_ip(client_ip(request)))
    response.set_cookie(
        settings.SESSION_COOKIE_NAME, token,
        max_age=settings.SESSION_DAYS * 86400,
        httponly=True,  # JavaScript can't read it, so an XSS bug can't steal it
        samesite="lax",  # not sent on cross-site POSTs
        secure=settings.is_production,  # HTTPS-only in production
        path="/",
    )
    return _me(user)


@router.post("/logout", status_code=204)
async def logout(request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    await auth_service.logout(db, request.cookies.get(settings.SESSION_COOKIE_NAME))
    response.delete_cookie(settings.SESSION_COOKIE_NAME, path="/")


@router.get("/me", response_model=MeOut)
async def me(user: User = Depends(current_user)):
    return _me(user)


class ProfileIn(BaseModel):
    name: OneLine | None = Field(default=None, min_length=2, max_length=100)
    phone: RequiredPhone | None = Field(default=None, max_length=20)  # None = leave as is; can't be cleared
    notify_email: bool | None = None
    notify_whatsapp: bool | None = None


@router.get("/profile")
async def profile(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    return await auth_service.profile_out(db, user)


@router.patch("/profile")
async def update_profile(data: ProfileIn, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    return await auth_service.update_profile(db, user, data.model_dump(exclude_unset=True, exclude_none=True))


class PasswordIn(BaseModel):
    current: str = Field(max_length=200)
    new: str = Field(min_length=10, max_length=200)


@router.post("/password", status_code=204)
async def change_password(data: PasswordIn, request: Request, user: User = Depends(current_user),
                          db: AsyncSession = Depends(get_db)):
    token = request.cookies.get(settings.SESSION_COOKIE_NAME, "")
    await auth_service.change_password(db, user, data.current, data.new, hash_token(token))
