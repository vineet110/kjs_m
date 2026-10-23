"""Route dependencies: who is calling, and are they allowed?"""
from datetime import datetime, timezone

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.errors import AppError
from app.core.permissions import effective_permissions
from app.core.security import hash_token
from app.models.user import User, UserSession

# Simple CSRF protection: every state-changing request must carry this header.
# A browser on another site cannot add a custom header without our CORS approval.
CSRF_HEADER = "x-requested-with"


async def current_user(request: Request, db: AsyncSession = Depends(get_db)) -> User:
    token = request.cookies.get(settings.SESSION_COOKIE_NAME)
    if not token:
        raise AppError(401, "not_logged_in", "Please log in.")
    row = await db.execute(
        select(User)
        .join(UserSession, UserSession.user_id == User.id)
        .where(UserSession.token_hash == hash_token(token))
        .where(UserSession.expires_at > datetime.now(timezone.utc))
    )
    user = row.scalar_one_or_none()
    if user is None or user.status != "active":
        raise AppError(401, "not_logged_in", "Your session has ended. Please log in again.")
    if request.method not in ("GET", "HEAD", "OPTIONS") and not request.headers.get(CSRF_HEADER):
        raise AppError(403, "csrf", "Missing request header.")
    return user


def require_permission(permission: str):
    """Use on a route: `user: User = Depends(require_permission("leads.view"))`."""

    async def checker(user: User = Depends(current_user)) -> User:
        if permission not in effective_permissions(user.role, user.permissions):
            raise AppError(403, "forbidden", "You don't have permission to do this.", {"needs": permission})
        return user

    return checker


def client_ip(request: Request) -> str | None:
    # Behind Cloudflare / nginx later, the real IP arrives in a header.
    return request.headers.get("cf-connecting-ip") or (request.client.host if request.client else None)
