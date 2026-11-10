"""Route dependencies: who is calling, and are they allowed?"""
import ipaddress
import logging
from datetime import datetime, timezone

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import AsyncSessionLocal, get_db
from app.core.errors import AppError
from app.core.logs import user_id_var
from app.core.permissions import effective_permissions
from app.core.security import hash_token
from app.models.user import User, UserSession

# Simple CSRF protection: every state-changing request must carry this header.
# A browser on another site cannot add a custom header without our CORS approval.
CSRF_HEADER = "x-requested-with"
log = logging.getLogger(__name__)


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
    user_id_var.set(user.id)  # every log line from here on carries user_id
    if request.method not in ("GET", "HEAD", "OPTIONS") and not request.headers.get(CSRF_HEADER):
        raise AppError(403, "csrf", "Missing request header.")
    return user


async def ws_user(token: str | None) -> int | None:
    """The WebSocket version of current_user (KJS Chat): the same session cookie and checks, but
    1. it takes the token, not a Request (a WebSocket isn't one), and returns only the user id;
    2. it opens its own short DB session and closes it at once, so open chat connections never hold
       database connections (also used for the re-check on every ping);
    3. no x-requested-with check (a browser can't add headers to a WebSocket). The chat route checks
       the Origin header instead (origin_allowed below).
    None = not logged in, session ended, or not active."""
    if not token:
        return None
    async with AsyncSessionLocal() as db:
        return await db.scalar(
            select(User.id)
            .join(UserSession, UserSession.user_id == User.id)
            .where(UserSession.token_hash == hash_token(token))
            .where(UserSession.expires_at > datetime.now(timezone.utc))
            .where(User.status == "active")
        )


def origin_allowed(origin: str | None) -> bool:
    """Is this page one of our own sites (ALLOWED_ORIGINS)? Browsers always send Origin on a WebSocket
    and a page can't fake it, so this stops another website opening a chat connection with the
    visitor's cookie (cross-site WebSocket hijacking)."""
    allowed = {o.strip() for o in settings.ALLOWED_ORIGINS.split(",") if o.strip()}
    return bool(origin) and origin in allowed


def require_permission(permission: str):
    """Use on a route: `user: User = Depends(require_permission("leads.view"))`."""

    async def checker(user: User = Depends(current_user)) -> User:
        if permission not in effective_permissions(user.role, user.permissions):
            log.warning("auth.permission_denied", extra={"needs": permission})
            raise AppError(403, "forbidden", "You don't have permission to do this.", {"needs": permission})
        return user

    return checker


# Our own proxies (Next.js, nginx) run on the same machine / Docker network. Only when the
# request comes from one of them do we trust the headers that carry the visitor's real IP;
# otherwise anyone could fake an IP to dodge the rate limits.
def _is_our_proxy(peer: str) -> bool:
    """Loopback or a private network (10/8, 172.16/12, 192.168/16, Docker): our own Next.js / nginx."""
    try:
        ip = ipaddress.ip_address(peer)
    except ValueError:
        return False
    return ip.is_loopback or ip.is_private


def visitor_keys(request: Request) -> tuple[str | None, str | None]:
    """(hash of the real address: saved with leads and audit rows, hash of the rate-limit key: CR6)."""
    from app.core.security import hash_ip, rate_key
    ip = client_ip(request)
    return hash_ip(ip), hash_ip(rate_key(ip))


def client_ip(request: Request) -> str | None:
    """The visitor's IP. Browsers reach us through the Next.js proxy, so without this every
    visitor would look like 127.0.0.1 and share one rate limit (found in the 24 Oct e2e test)."""
    peer = request.client.host if request.client else None
    if not peer or not _is_our_proxy(peer):
        return peer
    if cf := request.headers.get("cf-connecting-ip"):  # Cloudflare in production
        return cf.strip()
    if xff := request.headers.get("x-forwarded-for"):
        return xff.split(",")[-1].strip()  # the last hop was added by our own proxy, so it can't be faked
    return peer
