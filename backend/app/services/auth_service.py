"""Sign-up -> admin approval -> login -> logout. All business rules for staff accounts.

Passwords live in Firebase Authentication (app/core/firebase.py): the browser signs in with Firebase and
sends us its ID token. Firebase checks passwords, blocks guessing, and sends the "verify your email" and
"reset your password" emails. From the token on, everything is ours: the account row, approval, status,
role, permissions, and the session cookie.
"""
import logging
import secrets
import time
from datetime import datetime, timedelta, timezone

from pydantic import ValidationError
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import firebase
from app.core.config import settings
from app.core.errors import AppError
from app.core.rate_limit import login_ip_limiter, signup_limiter
from app.core.permissions import EMPLOYEE_DEFAULTS, PERMISSIONS, effective_permissions
from app.core.security import hash_token, new_session_token
from app.models.user import User, UserSession
from app.schemas.auth import UserUpdateIn
from app.services import assign_service, audit_service, chat_hub, file_service

log = logging.getLogger(__name__)

# "Password changed" must come from a sign-in made just now (the browser signs in again with the current
# password first), so a stolen, older token can't be used to log the real person out of everywhere.
FRESH_SIGN_IN_SECONDS = 5 * 60
BAD_TOKEN = "Your sign-in has expired. Please log in again."


async def _claims(token: str, net: str | None) -> dict:
    """Checks the Firebase ID token. Too many bad tokens from one network = 429 (guessing / replaying)."""
    if login_ip_limiter.blocked(net):
        raise AppError(429, "too_many", "Too many requests. Please try again later or WhatsApp us.")
    try:
        claims = await firebase.verify_token(token)
    except firebase.BadToken as e:
        login_ip_limiter.hit(net)
        log.warning("auth.bad_token", extra={"reason": str(e)})
        raise AppError(401, "bad_token", BAD_TOKEN) from e
    if not claims.get("email"):
        raise AppError(401, "bad_token", BAD_TOKEN)
    return claims


async def signup(db: AsyncSession, id_token: str, name: str, phone: str, ip_hash: str | None,
                 rate_key: str | None = None) -> User:
    """A new person (already signed up in Firebase by the browser) waits for admin approval."""
    signup_limiter.check(rate_key or ip_hash)
    claims = await _claims(id_token, rate_key or ip_hash)
    email = claims["email"].strip().lower()  # from the token, not the form: it is the Firebase account's email
    existing = await db.scalar(select(User).where(User.email == email))
    if existing is not None:
        if existing.firebase_uid is None:
            # An account from before Firebase: it is linked at its first login, once the email is verified
            # (login() below). Nothing to save now; the person is told to verify, then log in.
            return existing
        raise AppError(409, "email_taken", "An account with this email already exists.")
    user = User(name=name.strip(), email=email, phone=phone.strip() or None, password_hash=None,
                firebase_uid=claims["uid"], role="employee", status="pending", permissions=[])
    db.add(user)
    try:
        await db.flush()  # gives user.id, still inside the transaction
    except IntegrityError:  # the same person signing up twice at the same moment
        await db.rollback()
        raise AppError(409, "email_taken", "An account with this email already exists.")
    audit_service.record(db, actor=None, action="user.signed_up", entity_type="user", entity_id=user.id,
                         after={"email": user.email, "name": user.name}, ip_hash=ip_hash)
    await db.commit()
    return user


async def login(db: AsyncSession, id_token: str, ip_hash: str | None = None,
                rate_key: str | None = None) -> tuple[User, str]:
    claims = await _claims(id_token, rate_key or ip_hash)
    if not claims.get("email_verified"):
        # Anyone can make a Firebase account with any email; only a verified one proves the inbox is theirs
        raise AppError(403, "email_not_verified", "Please verify your email first: open the link we emailed you.")
    user = await db.scalar(select(User).where(User.firebase_uid == claims["uid"]))
    if user is None:
        user = await _link_old_account(db, claims, ip_hash)
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
    audit_service.record(db, actor=user, action="auth.login_ok", entity_type="user", entity_id=user.id, ip_hash=ip_hash)
    await db.commit()
    log.info("auth.login_ok", extra={"login_user_id": user.id})
    return user, token


async def _link_old_account(db: AsyncSession, claims: dict, ip_hash: str | None) -> User:
    """First Firebase login of an account made before Firebase (same email, now verified): it keeps its
    history (leads, attendance, chats). An employee waits for an admin's approval again; an admin stays
    active (nobody else could approve the first admin)."""
    email = claims["email"].strip().lower()
    user = await db.scalar(select(User).where(User.email == email, User.firebase_uid.is_(None)).with_for_update())
    if user is None:
        raise AppError(403, "no_account", "There's no staff account for this email yet. Please sign up first.")
    before = {"status": user.status}
    user.firebase_uid = claims["uid"]
    if user.role != "admin" and user.status == "active":
        user.status = "pending"
    audit_service.record(db, actor=None, action="user.linked_firebase", entity_type="user", entity_id=user.id,
                         before=before, after={"status": user.status}, ip_hash=ip_hash)
    await db.commit()
    return user


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
    await _sync_firebase_disabled(user, status != "active")
    return user


async def _sync_firebase_disabled(user: User, disabled: bool) -> None:
    """Firebase too: a disabled person can't even sign in there. Our database stays the real check (login()
    refuses any status but "active"), so a Firebase error here is only logged, never blocks the change."""
    if not user.firebase_uid or not firebase.enabled():
        return
    try:
        await firebase.set_disabled(user.firebase_uid, disabled)
    except Exception as e:
        log.warning("firebase.disable_failed", extra={"target_user_id": user.id, "reason": f"{type(e).__name__}: {str(e)[:200]}"})


async def ensure_admin(db: AsyncSession, email: str, password: str, name: str = "Admin") -> bool:
    """Create the first admin if missing (here and in Firebase). Returns True if created. Used by app.seed.
    Without Firebase set up (local development), the row is made unlinked: the first Firebase login with
    this verified email links it."""
    email = email.lower()
    if await db.scalar(select(User).where(User.email == email)):
        return False
    uid = await firebase.ensure_user(email, password, name) if firebase.enabled() else None
    admin = User(name=name, email=email, password_hash=None, firebase_uid=uid,
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
    an active colleague (not the person themselves, and no loop like "A reports to B, B reports to A")."""
    if data.role == "admin" and actor.role != "admin":
        raise AppError(403, "forbidden", "Only an admin can give the admin role.")
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
    password is returned for the admin to pass on; the person changes it on their Profile page. The
    password is set in Firebase (never stored by us); at the first login Firebase asks them to verify
    their email."""
    await _check_staff_details(db, admin, None, data)
    if await db.scalar(select(func.count()).select_from(User).where(User.email == data.email)):
        raise AppError(409, "email_taken", "An account with this email already exists.")
    temp_password = secrets.token_urlsafe(9)  # 12 characters, above the 10 a password needs
    uid = await firebase.create_user(data.email, temp_password, data.name)
    user = User(
        name=data.name, email=data.email, phone=data.phone, role=data.role, status="active",
        password_hash=None, firebase_uid=uid,
        permissions=list(EMPLOYEE_DEFAULTS), employee_code=data.employee_code, branch=data.branch,
        reporting_to=data.reporting_to, approved_by=admin.id, approved_at=datetime.now(timezone.utc),
    )
    db.add(user)
    try:
        await db.flush()
    except IntegrityError:  # the same email saved at the same moment by another request
        await db.rollback()
        await firebase.delete_user(uid)  # no Firebase account left behind without a row here
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
            "employee_code": u.employee_code, "branch": u.branch, "reporting_to_name": boss.name if boss else ""}


async def update_profile(db: AsyncSession, user: User, changes: dict) -> dict:
    before = {k: getattr(user, k) for k in changes}
    for k, v in changes.items():
        setattr(user, k, v.strip() if isinstance(v, str) else v)
    audit_service.record(db, actor=user, action="user.profile", entity_type="user", entity_id=user.id,
                         before=before, after=changes)
    await db.commit()
    return await profile_out(db, user)


async def password_changed(db: AsyncSession, user: User, id_token: str, keep_token_hash: str,
                           ip_hash: str | None = None, rate_key: str | None = None) -> None:
    """The browser has just changed the password in Firebase (after signing in again with the current one).
    Here: log out every other browser of this person (keep this one) and write it in the activity log."""
    claims = await _claims(id_token, rate_key or ip_hash)
    if claims["uid"] != user.firebase_uid:
        raise AppError(403, "forbidden", "This sign-in belongs to another account.")
    if time.time() - claims.get("auth_time", 0) > FRESH_SIGN_IN_SECONDS:
        raise AppError(401, "bad_token", "Please type your current password again.")
    await db.execute(delete(UserSession).where(UserSession.user_id == user.id, UserSession.token_hash != keep_token_hash))
    audit_service.record(db, actor=user, action="user.password_changed", entity_type="user", entity_id=user.id,
                         ip_hash=ip_hash)
    await db.commit()
    log.info("auth.password_changed")
