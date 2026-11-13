from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import current_user, visitor_keys
from app.core.modules import visible_to
from app.core.permissions import effective_permissions
from app.models.user import User
from app.schemas.auth import LoginIn, MeOut, PasswordChangedIn, SignupIn
from app.schemas.common import OneLine, RequiredPhone
from app.services import auth_service

router = APIRouter()


def _me(user: User) -> MeOut:
    return MeOut(id=user.id, name=user.name, email=user.email, role=user.role,
                 permissions=sorted(effective_permissions(user.role, user.permissions)),
                 modules=visible_to(user))


@router.post("/signup", status_code=201)
async def signup(data: SignupIn, request: Request, db: AsyncSession = Depends(get_db)):
    """After the browser made the Firebase account (and asked Firebase to send the verify-email link)."""
    await auth_service.signup(db, data.id_token, data.name, data.phone, *visitor_keys(request))
    return {"status": "pending",
            "message": "Account created. Verify your email (we sent a link), then an admin will approve it."}


@router.post("/login", response_model=MeOut)
async def login(data: LoginIn, request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    user, token = await auth_service.login(db, data.id_token, *visitor_keys(request))
    _set_session_cookie(response, token)
    return _me(user)


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        settings.SESSION_COOKIE_NAME, token,
        max_age=settings.SESSION_DAYS * 86400,
        httponly=True,  # JavaScript can't read it, so an XSS bug can't steal it
        samesite="lax",  # not sent on cross-site POSTs
        secure=settings.is_production,  # HTTPS-only in production
        path="/",
    )


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


@router.post("/password", status_code=204)
async def password_changed(data: PasswordChangedIn, request: Request, response: Response,
                           user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    """Called right after the browser changed the password in Firebase: logs out every other browser, and
    gives this one a new session cookie."""
    token = await auth_service.password_changed(db, user, data.id_token, *visitor_keys(request))
    _set_session_cookie(response, token)
