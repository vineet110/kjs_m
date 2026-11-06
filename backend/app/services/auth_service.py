"""Sign-up -> admin approval -> login -> logout. All business rules for staff accounts."""
import asyncio
import logging
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import AppError
from app.core.rate_limit import login_email_failures, login_failures, login_ip_limiter, signup_limiter
from app.core.permissions import EMPLOYEE_DEFAULTS, PERMISSIONS, effective_permissions
from app.core.security import hash_password, hash_token, new_session_token, verify_password
from app.models.user import User, UserSession
from app.schemas.auth import SignupIn
from app.services import audit_service, file_service

log = logging.getLogger(__name__)

# Used when the email doesn't exist, so a login takes as long as a real password check.
_DUMMY_HASH = hash_password("not-a-real-password-just-for-timing")


async def signup(db: AsyncSession, data: SignupIn, ip_hash: str | None) -> User:
    signup_limiter.check(ip_hash)  # before any hashing: password hashing is deliberately expensive
    exists = await db.scalar(select(func.count()).select_from(User).where(User.email == data.email))
    if exists:
        raise AppError(409, "email_taken", "An account with this email already exists.")
    user = User(
        name=data.name.strip(),
        email=data.email,
        phone=data.phone.strip() or None,
        password_hash=await asyncio.to_thread(hash_password, data.password),
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


async def login(db: AsyncSession, email: str, password: str, ip_hash: str | None = None) -> tuple[User, str]:
    # Checked BEFORE the password: once an email is locked, even the right password is refused,
    # otherwise an attacker could keep guessing and simply wait for the one "200".
    login_ip_limiter.check(ip_hash)  # 30 tries per IP per 15 min (stops guessing across many emails)
    lock_key = f"{email}|{ip_hash}"
    if login_failures.blocked(lock_key) or login_email_failures.blocked(email):
        raise AppError(429, "too_many", "Too many wrong passwords. Please wait 15 minutes and try again.")
    user = await db.scalar(select(User).where(User.email == email))
    # Same message AND about the same time for "no such user" and "wrong password", so nobody can
    # probe which emails exist (scrypt runs against a dummy hash when there is no user).
    stored = user.password_hash if user else _DUMMY_HASH
    if not await asyncio.to_thread(verify_password, password, stored) or user is None:
        log.warning("auth.login_failed", extra={"email": email})
        login_failures.hit(lock_key)  # 10 wrong passwords in 15 min from this network -> locked
        login_email_failures.hit(email)
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


def _check_can_manage(actor: User, target: User) -> None:
    """Nobody changes their own account here, and only an admin can touch an admin account
    (otherwise a staff member with `staff.approve` could disable every admin)."""
    if target.id == actor.id:
        raise AppError(422, "self_change", "You can't change your own account.")
    if target.role == "admin" and actor.role != "admin":
        raise AppError(403, "forbidden", "Only an admin can change an admin account.")


async def approve(db: AsyncSession, admin: User, user_id: int, permissions: list[str]) -> User:
    user = await db.get(User, user_id)
    if user is None:
        raise AppError(404, "not_found", "User not found.")
    unknown = [p for p in permissions if p not in PERMISSIONS]
    if unknown:
        raise AppError(422, "unknown_permission", "Unknown permission.", {"unknown": unknown})
    _check_can_manage(admin, user)
    if admin.role != "admin":
        # A non-admin approver only approves NEW sign-ups (not re-enable or re-permission anyone),
        # and can't hand out more than they have themselves.
        if user.status != "pending":
            raise AppError(403, "forbidden", "Only an admin can change an existing account.")
        mine = effective_permissions(admin.role, admin.permissions)
        extra = sorted(set(permissions) - mine)
        if extra:
            raise AppError(403, "forbidden", "You can't give permissions you don't have.", {"not_yours": extra})
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
    _check_can_manage(admin, user)
    if admin.role != "admin" and status == "active":
        # Turning an account back on brings back all its old permissions, so only an admin may.
        # (A non-admin approver activates new sign-ups through approve(), with its checks.)
        raise AppError(403, "forbidden", "Only an admin can turn an account back on.")
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


# ---------- User Creation Form (admin) ----------
STAFF_FIELDS = ("name", "phone", "employee_code", "branch", "role", "reporting_to")


async def _check_staff_details(db: AsyncSession, actor: User, target_id: int | None, data) -> None:
    """Rules shared by create and edit: only an admin makes someone an admin, and "reporting to" must be
    an active colleague (not the person themselves)."""
    if data.role == "admin" and actor.role != "admin":
        raise AppError(403, "forbidden", "Only an admin can give the admin role.")
    if data.reporting_to == target_id:
        raise AppError(422, "bad_manager", "A person can't report to themselves.")
    boss = await db.get(User, data.reporting_to)
    if boss is None or boss.status != "active":
        raise AppError(422, "bad_manager", "Pick an active colleague for 'Reporting to'.")


async def create_user(db: AsyncSession, admin: User, data) -> tuple[User, str]:
    """An account the admin makes directly (no sign-up, no approval step): active at once. A one-time
    password is returned for the admin to pass on; the person changes it on their Profile page."""
    await _check_staff_details(db, admin, None, data)
    if await db.scalar(select(func.count()).select_from(User).where(User.email == data.email)):
        raise AppError(409, "email_taken", "An account with this email already exists.")
    temp_password = secrets.token_urlsafe(9)  # 12 characters, above the 10 a password needs
    user = User(
        name=data.name, email=data.email, phone=data.phone, role=data.role, status="active",
        password_hash=await asyncio.to_thread(hash_password, temp_password),
        permissions=list(EMPLOYEE_DEFAULTS), employee_code=data.employee_code, branch=data.branch,
        reporting_to=data.reporting_to, approved_by=admin.id, approved_at=datetime.now(timezone.utc),
    )
    db.add(user)
    await db.flush()
    audit_service.record(db, actor=admin, action="user.created", entity_type="user", entity_id=user.id,
                         after={"email": user.email, **{k: getattr(user, k) for k in STAFF_FIELDS}})
    await db.commit()
    return user, temp_password


async def update_user(db: AsyncSession, admin: User, user_id: int, data) -> User:
    user = await db.get(User, user_id)
    if user is None:
        raise AppError(404, "not_found", "User not found.")
    _check_can_manage(admin, user)
    if admin.role != "admin":  # same rule as approve(): existing accounts are the admin's to change
        raise AppError(403, "forbidden", "Only an admin can change an existing account.")
    await _check_staff_details(db, admin, user.id, data)
    before = {k: getattr(user, k) for k in STAFF_FIELDS}
    for k in STAFF_FIELDS:
        setattr(user, k, getattr(data, k))
    audit_service.record(db, actor=admin, action="user.updated", entity_type="user", entity_id=user.id,
                         before=before, after={k: getattr(user, k) for k in STAFF_FIELDS})
    await db.commit()
    return user


# Profile photos are files owned by the user ("user", "<id>"). Every staff member may see them (they show
# next to names); only the person or someone who manages staff may upload one.
async def _photo_access(db: AsyncSession, user: User, owner_id: str, action: str) -> bool:
    if action == "read":
        return True
    return owner_id == str(user.id) or "staff.approve" in effective_permissions(user.role, user.permissions)


file_service.register_owner("user", _photo_access)


# ---------- Profile ----------
async def profile_out(db: AsyncSession, u: User) -> dict:
    boss = await db.get(User, u.reporting_to) if u.reporting_to else None
    return {"id": u.id, "name": u.name, "email": u.email, "phone": u.phone or "", "role": u.role,
            "categories": u.categories or [], "notify_email": u.notify_email, "notify_whatsapp": u.notify_whatsapp,
            # Set by the admin; shown read-only on the profile
            "employee_code": u.employee_code, "branch": u.branch, "reporting_to_name": boss.name if boss else ""}


async def update_profile(db: AsyncSession, user: User, changes: dict) -> dict:
    before = {k: getattr(user, k) for k in changes}
    for k, v in changes.items():
        setattr(user, k, v.strip() if isinstance(v, str) else v)
    audit_service.record(db, actor=user, action="user.profile", entity_type="user", entity_id=user.id,
                         before=before, after=changes)
    await db.commit()
    return await profile_out(db, user)


async def change_password(db: AsyncSession, user: User, current: str, new: str, keep_token_hash: str) -> None:
    # A stolen session must not be able to guess the current password forever: 10 tries per 15 min.
    lock_key = f"{user.email}|password_change"
    if login_failures.blocked(lock_key):
        raise AppError(429, "too_many", "Too many wrong passwords. Please wait 15 minutes and try again.")
    if not await asyncio.to_thread(verify_password, current, user.password_hash):
        login_failures.hit(lock_key)
        raise AppError(422, "bad_password", "Your current password is wrong.")
    if current == new:
        raise AppError(422, "same_password", "Choose a new password that is different.")
    user.password_hash = await asyncio.to_thread(hash_password, new)
    # Log out every other browser of this person (keep the one making the change).
    await db.execute(delete(UserSession).where(UserSession.user_id == user.id, UserSession.token_hash != keep_token_hash))
    audit_service.record(db, actor=user, action="user.password_changed", entity_type="user", entity_id=user.id)
    await db.commit()
    log.info("auth.password_changed")
