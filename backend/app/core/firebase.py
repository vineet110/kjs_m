"""Firebase from the server side (firebase-admin): one Firebase app for the whole API process.

Firebase Authentication keeps staff passwords: it checks them, and sends the "verify your email" and
"reset your password" emails itself. The browser signs in with Firebase and gets an ID token (a short,
signed proof of who it is); the API checks that token here, then starts its own session (kjs_session), so
roles, permissions and every page stay as before.

FIREBASE_SERVICE_ACCOUNT is the service-account JSON (Firebase console > Project settings > Service
accounts > Generate new private key), on ONE line. It is a secret: only in `.env` and on Render.
Empty = Firebase is off: logins are refused with a clear message (tests replace these functions, conftest.py).

Google's client is not async: every call runs in a worker thread (asyncio.to_thread).
"""
import asyncio
import json
import logging
import threading

import firebase_admin
from firebase_admin import auth as fb_auth
from firebase_admin import credentials
from firebase_admin import exceptions as firebase_errors

from app.core.config import settings
from app.core.errors import AppError

log = logging.getLogger(__name__)
_lock = threading.Lock()  # two first requests at the same moment must not both create the app

NOT_SET_UP = "Login isn't set up correctly on the server. Please tell the admin."
UNAVAILABLE = "Login is not available right now. Please try again in a minute."
BAD_DETAILS = "The login service didn't accept this email or name. Please check them."
# Seconds our clock may differ from Google's: a server clock 1-2 s behind would otherwise refuse a token
# made just now ("used too early"). A token lasts an hour, so 10 s changes nothing else.
CLOCK_SKEW_SECONDS = 10


class BadToken(Exception):
    """The ID token is fake, expired, revoked, or its Firebase account is disabled or deleted (= 401)."""


class _FirebaseDown(Exception):
    """Google didn't answer, or answered with an error (= 503, never counted as a bad token)."""


def enabled() -> bool:
    return bool(settings.FIREBASE_SERVICE_ACCOUNT)


def app() -> firebase_admin.App:
    """The Firebase app. A missing or broken FIREBASE_SERVICE_ACCOUNT is a setup problem (503, logged as
    `firebase.bad_config`), never a "bad token": a bad token counts against the office's login limit."""
    if not enabled():
        raise AppError(503, "login_not_set_up", NOT_SET_UP)
    with _lock:
        try:
            return firebase_admin.get_app()
        except ValueError:  # not created yet
            pass
        try:
            cred = credentials.Certificate(json.loads(settings.FIREBASE_SERVICE_ACCOUNT))
        except (ValueError, TypeError, KeyError) as e:  # not JSON, or not a service-account key
            log.error("firebase.bad_config", extra={"reason": type(e).__name__})
            raise AppError(503, "login_not_set_up", NOT_SET_UP) from e
        return firebase_admin.initialize_app(cred)


def _verify(token: str) -> dict:
    a = app()  # outside the try: a setup problem is a 503, not a bad token
    try:
        claims = fb_auth.verify_id_token(token, app=a, clock_skew_seconds=CLOCK_SKEW_SECONDS)  # signature, expiry, project
        # One look at the account (what check_revoked=True did inside Firebase, done here so we also get the
        # "password changed" time): disabled, deleted, or a token from before the last password change.
        user = fb_auth.get_user(claims["uid"], app=a)
    except (fb_auth.InvalidIdTokenError, fb_auth.UserNotFoundError, ValueError) as e:  # before FirebaseError
        raise BadToken(type(e).__name__) from e
    except (firebase_errors.FirebaseError, OSError) as e:  # no answer / error from Google (incl. its keys)
        raise _FirebaseDown(f"{type(e).__name__}: {str(e)[:200]}") from e
    if user.disabled:
        raise BadToken("UserDisabledError")
    # Firebase sets this time when the password changes (also by the reset email) or tokens are revoked.
    # Whole seconds: a session made in the same second as a reset can survive it (accepted, very rare).
    valid_after_ms = user.tokens_valid_after_timestamp or 0
    if claims.get("iat", 0) * 1000 < valid_after_ms:
        raise BadToken("RevokedIdTokenError")
    return claims | {"valid_after_ms": valid_after_ms}


async def verify_token(token: str) -> dict:
    """The token's claims: uid, email, email_verified, auth_time (when the password was typed), and
    valid_after_ms (when the password last changed). Raises BadToken (401); Google down = 503."""
    try:
        return await asyncio.to_thread(_verify, token)
    except _FirebaseDown as e:
        log.warning("firebase.unreachable", extra={"reason": str(e)})
        raise AppError(503, "login_unavailable", UNAVAILABLE) from e


async def _admin(fn, *args, passthrough: tuple = (), **kwargs):
    """One Admin call to Google, in a worker thread. Google down / an error answer = 503 (logged), a value
    Google refuses (e.g. an email it doesn't accept) = 422; never a 500. Errors in `passthrough` (like
    "user not found") reach the caller, which has its own answer for them."""
    a = app()  # a setup problem stays its own 503
    try:
        return await asyncio.to_thread(fn, *args, app=a, **kwargs)
    except passthrough:
        raise
    except ValueError as e:
        raise AppError(422, "bad_account_details", BAD_DETAILS) from e
    except (firebase_errors.FirebaseError, OSError) as e:
        log.warning("firebase.unreachable", extra={"reason": f"{fn.__name__}: {type(e).__name__}: {str(e)[:200]}"})
        raise AppError(503, "login_unavailable", UNAVAILABLE) from e


async def create_user(email: str, password: str, name: str) -> str:
    """A new Firebase account (User Creation Form, first admin). Returns its uid."""
    try:
        user = await _admin(fb_auth.create_user, email=email, password=password, display_name=name,
                            passthrough=(fb_auth.EmailAlreadyExistsError,))
    except fb_auth.EmailAlreadyExistsError as e:
        raise AppError(409, "email_taken", "An account with this email already exists.") from e
    return user.uid


async def uid_by_email(email: str) -> str | None:
    """The uid of this email's Firebase account, or None. (A sign-up that stopped halfway leaves a Firebase
    account with no row of ours: the admin can still create that person; see auth_service.create_user.)"""
    try:
        return (await _admin(fb_auth.get_user_by_email, email, passthrough=(fb_auth.UserNotFoundError,))).uid
    except fb_auth.UserNotFoundError:
        return None


async def reset_account(uid: str, password: str, name: str) -> None:
    """Takes over an existing Firebase account for the admin's new employee: new one-time password, name,
    and switched on. (Whoever made it can't log in with their old password any more.)"""
    await _admin(fb_auth.update_user, uid, password=password, display_name=name, disabled=False)


async def ensure_user(email: str, password: str, name: str) -> str:
    """The uid of this email's Firebase account, made if missing (first admin, `python -m app.seed`)."""
    return await uid_by_email(email) or await create_user(email, password, name)


async def delete_user(uid: str) -> None:
    await _admin(fb_auth.delete_user, uid)


async def set_disabled(uid: str, disabled: bool) -> None:
    """Disabled in Firebase too (can't sign in, can't get new tokens), and its existing tokens are revoked."""
    await _admin(fb_auth.update_user, uid, disabled=disabled)
    if disabled:
        await _admin(fb_auth.revoke_refresh_tokens, uid)
