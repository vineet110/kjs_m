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

from app.core.config import settings
from app.core.errors import AppError

log = logging.getLogger(__name__)
_lock = threading.Lock()  # two first requests at the same moment must not both create the app


class BadToken(Exception):
    """The ID token is fake, expired, revoked, or its Firebase account is disabled."""


def enabled() -> bool:
    return bool(settings.FIREBASE_SERVICE_ACCOUNT)


def app() -> firebase_admin.App:
    if not enabled():
        raise AppError(503, "login_not_set_up", "Login isn't set up on this server yet (FIREBASE_SERVICE_ACCOUNT).")
    with _lock:
        try:
            return firebase_admin.get_app()
        except ValueError:  # not created yet
            info = json.loads(settings.FIREBASE_SERVICE_ACCOUNT)
            return firebase_admin.initialize_app(credentials.Certificate(info))


def _verify(token: str) -> dict:
    try:
        # check_revoked: a token from before "log out everywhere" / a disabled account is refused too
        return fb_auth.verify_id_token(token, app=app(), check_revoked=True)
    except (fb_auth.InvalidIdTokenError, fb_auth.UserDisabledError, ValueError) as e:
        raise BadToken(type(e).__name__) from e


async def verify_token(token: str) -> dict:
    """The token's claims: uid, email, email_verified, auth_time (when the password was typed)...
    Raises BadToken. Google unreachable (its public keys can't be fetched) = 503."""
    try:
        return await asyncio.to_thread(_verify, token)
    except fb_auth.CertificateFetchError as e:
        log.warning("firebase.unreachable", extra={"reason": str(e)[:200]})
        raise AppError(503, "login_unavailable", "Login is not available right now. Please try again in a minute.") from e


async def create_user(email: str, password: str, name: str) -> str:
    """A Firebase account for a person the admin adds (User Creation Form). Returns its uid."""
    try:
        user = await asyncio.to_thread(fb_auth.create_user, email=email, password=password, display_name=name, app=app())
    except fb_auth.EmailAlreadyExistsError as e:
        raise AppError(409, "email_taken", "An account with this email already exists.") from e
    return user.uid


async def ensure_user(email: str, password: str, name: str) -> str:
    """The uid of this email's Firebase account, made if missing (first admin, `python -m app.seed`)."""
    try:
        return (await asyncio.to_thread(fb_auth.get_user_by_email, email, app=app())).uid
    except fb_auth.UserNotFoundError:
        return await create_user(email, password, name)


async def delete_user(uid: str) -> None:
    await asyncio.to_thread(fb_auth.delete_user, uid, app=app())


async def set_disabled(uid: str, disabled: bool) -> None:
    """Disabled in Firebase too (can't sign in, can't get new tokens), and its existing tokens are revoked."""
    await asyncio.to_thread(fb_auth.update_user, uid, disabled=disabled, app=app())
    if disabled:
        await asyncio.to_thread(fb_auth.revoke_refresh_tokens, uid, app=app())
