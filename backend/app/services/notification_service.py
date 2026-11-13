"""Notifications: the bell in the portal header, plus an email copy.

notify() only adds rows to the current transaction (saved with the change that caused
them). The `send_emails` job sends the email copies afterwards, so a slow or broken mail
server never slows a click. WhatsApp copies come after Meta business verification.
"""
import asyncio
import logging
import smtplib
import ssl
import time
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.config.ini import cfg
from app.core.modules import link_for
from app.core.permissions import effective_permissions
from app.jobs.runner import job
from app.models.notification import Notification
from app.models.user import User
from app.services import email_service

log = logging.getLogger(__name__)


def notify(db: AsyncSession, user_ids: set[int] | list[int], kind: str, title: str, body: str = "", link: str = "") -> None:
    title = " ".join(title.split())[:200]  # one line: titles become email subjects
    for uid in set(user_ids):
        db.add(Notification(user_id=uid, kind=kind, title=title, body=body, link=link,
                            email_status="pending"))


async def users_with(db: AsyncSession, permission: str) -> list[int]:
    """Active staff who hold a permission (admins hold all)."""
    users = (await db.scalars(select(User).where(User.status == "active"))).all()
    return [u.id for u in users if permission in effective_permissions(u.role, u.permissions)]


async def list_mine(db: AsyncSession, user: User, limit: int = 30) -> dict:
    rows = (await db.scalars(select(Notification).where(Notification.user_id == user.id)
                             .order_by(Notification.id.desc()).limit(limit))).all()
    unread = await db.scalar(select(func.count()).select_from(Notification)
                             .where(Notification.user_id == user.id, Notification.read_at.is_(None)))
    return {"unread": unread, "items": [
        {"id": n.id, "kind": n.kind, "title": n.title, "body": n.body, "link": link_for(user, n.link),
         "read": n.read_at is not None, "created_at": n.created_at} for n in rows]}


async def mark_read(db: AsyncSession, user: User, ids: list[int] | None) -> None:
    q = update(Notification).where(Notification.user_id == user.id, Notification.read_at.is_(None))
    if ids:
        q = q.where(Notification.id.in_(ids))
    await db.execute(q.values(read_at=datetime.now(timezone.utc)))
    await db.commit()


# ---------- Email ----------
def _smtp_connect() -> smtplib.SMTP:
    """One logged-in connection, reused for the whole batch. The server's certificate IS checked
    (without a context, Python's starttls() would accept any certificate and hand our password to
    whoever answers)."""
    ctx = ssl.create_default_context()
    if settings.SMTP_PORT == 465:  # port 465 = TLS from the first byte
        s: smtplib.SMTP = smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, timeout=20, context=ctx)
    else:  # 587 / 25 = plain first, then STARTTLS
        s = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=20)
        s.starttls(context=ctx)
    if settings.SMTP_USER:
        s.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
    return s


def _message(to: str, subject: str, text: str) -> EmailMessage:
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = settings.SMTP_FROM, to, subject
    msg.set_content(text)
    return msg


def _close(conn: smtplib.SMTP | None) -> None:
    if conn is not None:
        try:
            conn.quit()
        except Exception:
            pass


MAX_EMAIL_ATTEMPTS = 3
EMAIL_TIME_BUDGET_SECONDS = 120  # stop early so the other jobs (SLA, alerts) aren't held up
# Visitor text reaches staff inboxes from our own address, so say clearly that it isn't ours.
VISITOR_TEXT_NOTE = ("\n\n--\nThis alert may include text typed by a website visitor. "
                     "Don't open links or attachments you didn't expect.")


@job("send_emails", any_time=True)  # also at night and on Sundays: a lead shouldn't wait till Monday
async def send_emails(db: AsyncSession) -> dict:
    """Each email is saved as sent the moment it goes out (commit per email), so a crash or restart
    never sends the same email twice. A failed send is retried on the next runs, up to 3 tries."""
    # Rows left in "sending" by a crash 15+ minutes ago go back in the queue.
    await db.execute(update(Notification)
                     .where(Notification.email_status == "sending",
                            Notification.updated_at < datetime.now(timezone.utc) - timedelta(minutes=15))
                     .values(email_status="pending"))
    rows = (await db.execute(
        select(Notification, User).join(User, User.id == Notification.user_id)
        .where(Notification.email_status == "pending").order_by(Notification.id).limit(50)
        .with_for_update(of=Notification, skip_locked=True)
    )).all()
    sent = skipped = failed = 0
    # Firebase (Firestore "mail" + Trigger Email extension) when FIREBASE_SERVICE_ACCOUNT is set (Render's
    # free tier blocks SMTP), else SMTP, else skipped
    use_firebase = email_service.enabled()
    email_on = "email" in cfg().alerts.channels and (use_firebase or bool(settings.SMTP_HOST))
    for n, u in rows:  # claim the whole batch first, so nobody else picks these rows
        if email_on and u.notify_email and u.status == "active":
            n.email_status = "sending"
        else:
            n.email_status = "skipped"
            skipped += 1
    await db.commit()
    conn, started, server_down = None, time.monotonic(), False
    try:
        for n, u in rows:
            if n.email_status != "sending":
                continue
            if server_down or time.monotonic() - started > EMAIL_TIME_BUDGET_SECONDS:
                n.email_status = "pending"  # not tried: back in the queue for the next run
                await db.commit()
                continue
            # no link to a portal area hidden from this person (config/modules.ini)
            link = f"\n\nOpen: {settings.PUBLIC_BASE_URL}{n.link}" if link_for(u, n.link) else ""
            note = VISITOR_TEXT_NOTE if n.kind.startswith(("lead.", "partner.")) else ""
            subject, text = f"[KJS] {n.title}", f"{n.body}{link}{note}"
            if use_firebase:
                try:
                    # One fixed id per notification: Firestore refuses a second copy (never sent twice)
                    await email_service.send(_mail_id(n), u.email, subject, text)
                    n.email_status = "sent"  # handed to Firebase; delivery result is on the Firestore document
                    sent += 1
                except email_service.MailDown as e:
                    # Same rule as an unreachable SMTP server (CR10): back in the queue without using up a
                    # try, the rest of the batch too (bad key, no permission, Google down...)
                    server_down = True
                    n.email_status = "pending"
                    log.warning("email.server_down", extra={"provider": "firebase", "reason": str(e)[:200]})
                except Exception as e:  # this one email was refused: it uses up a try, the rest still go
                    _failed_try(n, e)
                    failed += 1
                await db.commit()
                continue
            if conn is None:
                try:
                    conn = await asyncio.to_thread(_smtp_connect)
                except Exception as e:
                    # Can't reach or log in to the mail server: not this email's fault (CR10). It goes back
                    # in the queue WITHOUT using up an attempt, the rest of the batch too, and the next run
                    # tries again. (Counting it lost about one email every 3 minutes during an outage.)
                    server_down = True
                    n.email_status = "pending"
                    await db.commit()
                    log.warning("email.server_down", extra={"reason": f"{type(e).__name__}: {str(e)[:200]}"})
                    continue
            try:
                await asyncio.to_thread(conn.send_message, _message(u.email, subject, text))
                n.email_status = "sent"
                sent += 1
            except Exception as e:  # any error stays with this one email; the rest still go out
                _close(conn)
                conn = None  # the connection may be broken: open a fresh one for the next email
                _failed_try(n, e)
                failed += 1
            await db.commit()
    finally:
        await asyncio.to_thread(_close, conn)
    return {"sent": sent, "skipped": skipped, "failed": failed}


def _mail_id(n: Notification) -> str:
    """The Firestore document id of this notification's email. With the creation time, so a database that
    starts again from id 1 (a reset, a copy) can't hit an old email's id and skip a new email."""
    return f"notification-{n.id}-{int(n.created_at.timestamp())}"


def _failed_try(n: Notification, e: Exception) -> None:
    """One try used up: back in the queue, or "failed" after MAX_EMAIL_ATTEMPTS."""
    n.email_attempts += 1
    n.email_status = "failed" if n.email_attempts >= MAX_EMAIL_ATTEMPTS else "pending"
    log.warning("email.failed", extra={"notification_id": n.id, "attempt": n.email_attempts,
                                       "reason": f"{type(e).__name__}: {str(e)[:200]}"})
