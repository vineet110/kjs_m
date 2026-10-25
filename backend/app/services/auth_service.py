"""Sign-up -> admin approval -> login -> logout. All business rules for staff accounts."""
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import AppError
from app.core.rate_limit import login_failures
from app.core.permissions import EMPLOYEE_DEFAULTS, PERMISSIONS
from app.core.security import hash_password, hash_token, new_session_token, verify_password
from app.models.user import User, UserSession
from app.schemas.auth import SignupIn
from app.services import audit_service

log = logging.getLogger(__name__)


async def signup(db: AsyncSession, data: SignupIn, ip_hash: str | None) -> User:
    exists = await db.scalar(select(func.count()).select_from(User).where(User.email == data.email))
    if exists:
        raise AppError(409, "email_taken", "An account with this email already exists.")
    user = User(
        name=data.name.strip(),
        email=data.email,
        phone=data.phone.strip() or None,
        password_hash=hash_password(data.password),
        role="employee",
        status="pending",  # can't log in until an admin approves
        permissions=[],
    )
    db.add(user)
    await db.flush()  # gives user.id, still inside the transaction
    audit_service.record(
        db, actor=None, action="user.signed_up", entity_type="user", entity_id=user.id,
        after={"email": user.email, "name": user.name}, ip_hash=ip_hash,
    )
    await db.commit()
    return user


async def login(db: AsyncSession, email: str, password: str) -> tuple[User, str]:
    user = await db.scalar(select(User).where(User.email == email))
    # Same message for "no such user" and "wrong password", so nobody can probe which emails exist.
    if user is None or not verify_password(password, user.password_hash):
        log.warning("auth.login_failed", extra={"email": email})
        login_failures.check(email)  # 10 wrong passwords in 15 min -> blocked for a while
        raise AppError(401, "bad_credentials", "Email or password is wrong.")
    if user.status == "pending":
        raise AppError(403, "pending_approval", "Your account is waiting for admin approval.")
    if user.status != "active":
        raise AppError(403, "disabled", "Your account is disabled. Please contact the admin.")

    token = new_session_token()
    now = datetime.now(timezone.utc)
    db.add(UserSession(
        user_id=user.id, token_hash=hash_token(token),
        created_at=now, expires_at=now + timedelta(days=settings.SESSION_DAYS),
    ))
    # Housekeeping: drop this user's expired sessions.
    await db.execute(delete(UserSession).where(UserSession.user_id == user.id, UserSession.expires_at < now))
    await db.commit()
    log.info("auth.login_ok", extra={"login_user_id": user.id})
    return user, token


async def logout(db: AsyncSession, token: str | None) -> None:
    if token:
        await db.execute(delete(UserSession).where(UserSession.token_hash == hash_token(token)))
        await db.commit()


async def list_users(db: AsyncSession, status: str | None) -> list[User]:
    q = select(User).order_by(User.created_at.desc())
    if status:
        q = q.where(User.status == status)
    return list((await db.scalars(q)).all())


async def approve(db: AsyncSession, admin: User, user_id: int, permissions: list[str]) -> User:
    user = await db.get(User, user_id)
    if user is None:
        raise AppError(404, "not_found", "User not found.")
    unknown = [p for p in permissions if p not in PERMISSIONS]
    if unknown:
        raise AppError(422, "unknown_permission", "Unknown permission.", {"unknown": unknown})
    before = {"status": user.status, "permissions": user.permissions}
    user.status = "active"
    user.permissions = sorted(set(EMPLOYEE_DEFAULTS) | set(permissions))
    user.approved_by = admin.id
    user.approved_at = datetime.now(timezone.utc)
    audit_service.record(
        db, actor=admin, action="user.approved", entity_type="user", entity_id=user.id,
        before=before, after={"status": user.status, "permissions": user.permissions},
    )
    await db.commit()
    return user


async def set_status(db: AsyncSession, admin: User, user_id: int, status: str) -> User:
    user = await db.get(User, user_id)
    if user is None:
        raise AppError(404, "not_found", "User not found.")
    if user.id == admin.id:
        raise AppError(422, "self_change", "You can't change your own status.")
    before = {"status": user.status}
    user.status = status
    if status != "active":
        await db.execute(delete(UserSession).where(UserSession.user_id == user.id))  # log them out
    audit_service.record(
        db, actor=admin, action=f"user.{status}", entity_type="user", entity_id=user.id,
        before=before, after={"status": status},
    )
    await db.commit()
    return user


async def ensure_admin(db: AsyncSession, email: str, password: str, name: str = "Admin") -> bool:
    """Create the first admin if missing. Returns True if created. Used by app.seed."""
    email = email.lower()
    if await db.scalar(select(User).where(User.email == email)):
        return False
    admin = User(name=name, email=email, password_hash=hash_password(password),
                 role="admin", status="active", permissions=[])
    db.add(admin)
    await db.flush()
    audit_service.record(db, actor=None, action="user.admin_created", entity_type="user",
                         entity_id=admin.id, after={"email": email})
    await db.commit()
    return True


# ---------- Profile ----------
def profile_out(u: User) -> dict:
    return {"id": u.id, "name": u.name, "email": u.email, "phone": u.phone or "", "role": u.role,
            "categories": u.categories or [], "notify_email": u.notify_email, "notify_whatsapp": u.notify_whatsapp}


async def update_profile(db: AsyncSession, user: User, changes: dict) -> dict:
    before = {k: getattr(user, k) for k in changes}
    for k, v in changes.items():
        setattr(user, k, v.strip() if isinstance(v, str) else v)
    audit_service.record(db, actor=user, action="user.profile", entity_type="user", entity_id=user.id,
                         before=before, after=changes)
    await db.commit()
    return profile_out(user)


async def change_password(db: AsyncSession, user: User, current: str, new: str, keep_token_hash: str) -> None:
    if not verify_password(current, user.password_hash):
        raise AppError(422, "bad_password", "Your current password is wrong.")
    if current == new:
        raise AppError(422, "same_password", "Choose a new password that is different.")
    user.password_hash = hash_password(new)
    # Log out every other browser of this person (keep the one making the change).
    await db.execute(delete(UserSession).where(UserSession.user_id == user.id, UserSession.token_hash != keep_token_hash))
    audit_service.record(db, actor=user, action="user.password_changed", entity_type="user", entity_id=user.id)
    await db.commit()
    log.info("auth.password_changed")
