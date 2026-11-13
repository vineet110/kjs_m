"""Sign-up -> admin approval -> login -> logout. All business rules for staff accounts."""
import asyncio
import logging
import secrets
from datetime import datetime, timedelta, timezone

from pydantic import ValidationError
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import AppError
from app.core.rate_limit import login_email_failures, login_failures, login_ip_limiter, signup_limiter
from app.core.permissions import EMPLOYEE_DEFAULTS, PERMISSIONS, effective_permissions
from app.core.security import hash_password, hash_token, new_session_token, verify_password
from app.models.audit import AuditLog
from app.models.user import User, UserSession
from app.schemas.auth import SignupIn, UserOut, UserUpdateIn
from app.services import assign_service, audit_service, chat_hub, file_service, job_title_service

log = logging.getLogger(__name__)

KNOWN_NETWORK_DAYS = 30  # CR5: a network this person logged in from recently

# Used when the email doesn't exist, so a login takes as long as a real password check.
_DUMMY_HASH = hash_password("not-a-real-password-just-for-timing")


async def signup(db: AsyncSession, data: SignupIn, ip_hash: str | None, rate_key: str | None = None) -> User:
    signup_limiter.check(rate_key or ip_hash)  # before any hashing: password hashing is deliberately expensive
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


async def _known_network(db: AsyncSession, user: User | None, ip_hash: str | None) -> bool:
    """Did this person log in successfully from this network in the last 30 days? (CR5)"""
    if user is None or not ip_hash:
        return False
    since = datetime.now(timezone.utc) - timedelta(days=KNOWN_NETWORK_DAYS)
    return bool(await db.scalar(select(AuditLog.id).where(
        AuditLog.entity_type == "user", AuditLog.entity_id == str(user.id), AuditLog.action == "auth.login_ok",
        AuditLog.ip_hash == ip_hash, AuditLog.at >= since).limit(1)))


async def login(db: AsyncSession, email: str, password: str, ip_hash: str | None = None,
                rate_key: str | None = None) -> tuple[User, str]:
    # Checked BEFORE the password: once an email is locked, even the right password is refused,
    # otherwise an attacker could keep guessing and simply wait for the one "200".
    net = rate_key or ip_hash
    if login_ip_limiter.blocked(net):  # too many wrong passwords from this network, over all emails
        raise AppError(429, "too_many", "Too many requests. Please try again later or WhatsApp us.")
    user = await db.scalar(select(User).where(User.email == email))
    lock_key = f"{email}|{net}"
    # The any-network counter is a backstop against guessing from many networks. It must not let a
    # stranger lock the real person out (CR5): a network they logged in from recently is never blocked
    # by it. (Kept in the audit log, so a restart of the API doesn't forget it.)
    email_locked = login_email_failures.blocked(email) and not await _known_network(db, user, ip_hash)
    if login_failures.blocked(lock_key) or email_locked:
        raise AppError(429, "too_many", "Too many wrong passwords. Please wait 15 minutes and try again.")
    # Same message AND about the same time for "no such user" and "wrong password", so nobody can
    # probe which emails exist (scrypt runs against a dummy hash when there is no user).
    stored = user.password_hash if user else _DUMMY_HASH
    if not await asyncio.to_thread(verify_password, password, stored) or user is None:
        log.warning("auth.login_failed", extra={"email": email})
        login_failures.hit(lock_key)  # 10 wrong passwords in 15 min from this network -> locked
        login_email_failures.hit(email)
        login_ip_limiter.hit(net)
        raise AppError(401, "bad_credentials", "Email or password is wrong.")
    if user.status == "pending":
        raise AppError(403, "pending_approval", "Your account is waiting for admin approval.")
    if user.status == "rejected":
        raise AppError(403, "rejected", "Your sign-up was not approved. Please contact the admin.")
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
    # Who logged in from which network (hashed): also what lets this network past a stranger's lockout (CR5)
    audit_service.record(db, actor=user, action="auth.login_ok", entity_type="user", entity_id=user.id, ip_hash=ip_hash)
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


async def decided(db: AsyncSession, status: str, limit: int = 200) -> list[dict]:
    """Approved (active) or rejected accounts for the Approvals page, newest decision first, each with
    `decided_by_name`. Admins are left out (nobody approves them)."""
    rows = (await db.scalars(
        select(User).where(User.status == status, User.role == "employee")
        .order_by(User.approved_at.desc().nulls_last(), User.id.desc()).limit(limit))).all()
    ids = {u.approved_by for u in rows if u.approved_by}
    names = dict((await db.execute(select(User.id, User.name).where(User.id.in_(ids)))).all()) if ids else {}
    return [UserOut.model_validate(u).model_dump() | {"decided_by_name": names.get(u.approved_by, "")} for u in rows]


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
    user.rejection_reason = None  # a rejected sign-up approved later (admin only, checked above)
    audit_service.record(
        db, actor=admin, action="user.approved", entity_type="user", entity_id=user.id,
        before=before, after={"status": user.status, "permissions": user.permissions},
    )
    await db.commit()
    return user


async def reject(db: AsyncSession, approver: User, user_id: int, reason: str) -> User:
    """Reject a new sign-up (anyone who may approve). The reason is kept and shown in the Rejected list;
    the person can't log in. An admin can still approve them later (approve() accepts a rejected account
    from an admin only)."""
    user = await db.get(User, user_id, with_for_update=True)
    if user is None:
        raise AppError(404, "not_found", "User not found.")
    _check_can_manage(approver, user)
    if user.status != "pending":
        raise AppError(409, "not_pending", "Only a sign-up waiting for approval can be rejected.")
    user.status = "rejected"
    user.rejection_reason = reason.strip()
    user.approved_by = approver.id  # "decided by": status says it was a rejection
    user.approved_at = datetime.now(timezone.utc)
    audit_service.record(db, actor=approver, action="user.rejected", entity_type="user", entity_id=user.id,
                         before={"status": "pending"}, after={"status": "rejected", "reason": user.rejection_reason})
    await db.commit()
    return user


async def set_permissions(db: AsyncSession, admin: User, user_id: int, permissions: list[str]) -> User:
    """Change what an approved employee may do (Manage employees). Admin only. Takes effect on their next
    request: permissions are read from the database every time. leads.view always stays."""
    if admin.role != "admin":
        raise AppError(403, "forbidden", "Only an admin can change permissions.")
    unknown = sorted(p for p in permissions if p not in PERMISSIONS)
    if unknown:
        raise AppError(422, "unknown_permission", "Unknown permission.", {"unknown": unknown})
    user = await db.get(User, user_id, with_for_update=True)
    if user is None:
        raise AppError(404, "not_found", "User not found.")
    _check_can_manage(admin, user)
    if user.role == "admin":
        raise AppError(422, "admin_has_all", "An admin already has every permission.")
    if user.status not in ("active", "disabled"):
        raise AppError(409, "not_approved", "Approve the sign-up first; permissions are chosen there.")
    before = sorted(user.permissions or [])
    after = sorted(set(EMPLOYEE_DEFAULTS) | set(permissions))
    if after != before:
        user.permissions = after
        audit_service.record(db, actor=admin, action="user.permissions_changed", entity_type="user",
                             entity_id=user.id, before={"permissions": before}, after={"permissions": after})
        await db.commit()
    return user


async def set_status(db: AsyncSession, admin: User, user_id: int, status: str) -> User:
    user = await db.get(User, user_id)
    if user is None:
        raise AppError(404, "not_found", "User not found.")
    _check_can_manage(admin, user)
    if user.status in ("pending", "rejected"):
        # A sign-up is decided with Approve (which sets permissions) or Reject, never switched on directly
        raise AppError(409, "not_approved", "Approve or reject this sign-up first.")
    if admin.role != "admin" and status == "active":
        # Turning an account back on brings back all its old permissions, so only an admin may.
        # (A non-admin approver activates new sign-ups through approve(), with its checks.)
        raise AppError(403, "forbidden", "Only an admin can turn an account back on.")
    before = {"status": user.status}
    user.status = status
    returned = 0
    if status != "active":
        await db.execute(delete(UserSession).where(UserSession.user_id == user.id))  # log them out
        # Their open batch would be stuck for ever (only they can work on it) and hidden (CR9): its
        # unfinished buyers go back to "new" for the next person, and the batch is marked "returned".
        returned = await assign_service.return_open_batch(db, user.id)
    audit_service.record(
        db, actor=admin, action=f"user.{status}", entity_type="user", entity_id=user.id,
        before=before, after={"status": status} | ({"buyers_returned": returned} if returned else {}),
    )
    await db.commit()
    if status != "active":
        await chat_hub.hub.kick(user.id)  # close their open chat tabs now, not at the next ping
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
STAFF_FIELDS = ("name", "phone", "employee_code", "branch", "role", "job_title", "reporting_to")


async def _check_staff_details(db: AsyncSession, actor: User, target_id: int | None, data) -> None:
    """Rules shared by create and edit: only an admin makes someone an admin, a job title must be one from
    the list, and "reporting to" must be an active colleague (not the person themselves, and no loop like
    "A reports to B, B reports to A")."""
    if data.role == "admin" and actor.role != "admin":
        raise AppError(403, "forbidden", "Only an admin can give the admin role.")
    if data.job_title:
        name = await job_title_service.find(db, data.job_title)
        if name is None:
            raise AppError(422, "unknown_job_title", "Pick a job title from the list, or add it first.")
        data.job_title = name  # the list's own spelling
    if data.reporting_to is None:  # top of the chain: no manager, so nothing to check
        return
    if data.reporting_to == target_id:
        raise AppError(422, "bad_manager", "A person can't report to themselves.")
    boss = await db.get(User, data.reporting_to)
    if boss is None or boss.status != "active":
        raise AppError(422, "bad_manager", "Pick an active colleague for 'Reporting to'.")
    # Walk up the chain from the new manager: reaching this person again would make a loop.
    # A new account (target_id None) can't be anyone's manager yet. `seen` stops on an old bad loop.
    seen, up = set(), boss.reporting_to
    while target_id is not None and up is not None and up not in seen:
        if up == target_id:
            raise AppError(422, "bad_manager", "This would make a reporting loop: they already report to this person.")
        seen.add(up)
        up = await db.scalar(select(User.reporting_to).where(User.id == up))


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
        job_title=data.job_title, reporting_to=data.reporting_to, approved_by=admin.id, approved_at=datetime.now(timezone.utc),
    )
    db.add(user)
    try:
        await db.flush()
    except IntegrityError:  # the same email saved at the same moment by another request
        await db.rollback()
        raise AppError(409, "email_taken", "An account with this email already exists.")
    audit_service.record(db, actor=admin, action="user.created", entity_type="user", entity_id=user.id,
                         after={"email": user.email, **{k: getattr(user, k) for k in STAFF_FIELDS}})
    await db.commit()
    return user, temp_password


async def update_user(db: AsyncSession, admin: User, user_id: int, changes: dict) -> User:
    """Only the fields in `changes` change; the account as a whole is then checked (UserUpdateIn)."""
    user = await db.get(User, user_id, with_for_update=True)
    if user is None:
        raise AppError(404, "not_found", "User not found.")
    _check_can_manage(admin, user)
    if admin.role != "admin":  # same rule as approve(): existing accounts are the admin's to change
        raise AppError(403, "forbidden", "Only an admin can change an existing account.")
    try:
        data = UserUpdateIn(**({k: getattr(user, k) for k in STAFF_FIELDS} | changes))
    except ValidationError as e:
        bad = sorted({str(err["loc"][0]) for err in e.errors() if err.get("loc")})
        raise AppError(422, "validation_error", f"Please check: {', '.join(bad)}.", {"fields": bad}) from e
    await _check_staff_details(db, admin, user.id, data)
    before = {k: getattr(user, k) for k in STAFF_FIELDS}
    for k in STAFF_FIELDS:
        setattr(user, k, getattr(data, k))
    audit_service.record(db, actor=admin, action="user.updated", entity_type="user", entity_id=user.id,
                         before=before, after={k: getattr(user, k) for k in STAFF_FIELDS})
    await db.commit()
    return user


# Profile photos are files owned by the user ("user", "<id>"). Every staff member may see them (they show
# next to names); only the person or someone who manages staff may upload one. The account must exist, and
# an admin's photo is only an admin's to change (same rule as "only an admin makes someone an admin").
async def _photo_access(db: AsyncSession, user: User, owner_id: str, action: str) -> bool:
    if action == "read":
        return True
    if owner_id == str(user.id):
        return True
    if "staff.approve" not in effective_permissions(user.role, user.permissions) or not owner_id.isdigit():
        return False
    owner = await db.get(User, int(owner_id))
    return owner is not None and (owner.role != "admin" or user.role == "admin")


file_service.register_owner("user", _photo_access)


# ---------- Profile ----------
async def profile_out(db: AsyncSession, u: User) -> dict:
    boss = await db.get(User, u.reporting_to) if u.reporting_to else None
    return {"id": u.id, "name": u.name, "email": u.email, "phone": u.phone or "", "role": u.role,
            "categories": u.categories or [], "notify_email": u.notify_email, "notify_whatsapp": u.notify_whatsapp,
            # Set by the admin; shown read-only on the profile
            "employee_code": u.employee_code, "branch": u.branch, "job_title": u.job_title,
            "reporting_to_name": boss.name if boss else ""}


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
