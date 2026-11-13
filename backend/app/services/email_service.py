"""Emails through Firebase: the API writes each email into the Firestore collection `mail`
(FIREBASE_MAIL_COLLECTION), and Firebase's "Trigger Email from Firestore" extension sends it.

Why not SMTP from the API: Render's free tier blocks the SMTP ports. Writing to Firestore is HTTPS.
Without FIREBASE_SERVICE_ACCOUNT the queue in notification_service.py still uses SMTP (SMTP_HOST), as before.

Each email has a fixed document id (one per notification). Writing it twice is refused by Firestore
(AlreadyExists), so a crash between "written" and "saved as sent" can never send the same email twice.

Two kinds of failure, because the queue treats them differently (CR10):
1. MailDown: Firestore can't be reached or refuses US (bad or missing key, no permission, quota, Google
   down, timeout). Not the email's fault: it waits WITHOUT using up one of its 3 tries; the batch waits too.
2. EmailRejected: Firestore refused this one email (e.g. too big). It uses up a try; the rest still go.

Delivery itself (a bad address, Gmail's daily limit) happens later in the extension: its result is written
back on the same Firestore document (`delivery.state`, `delivery.error`), not in our database.
Never logs an email's text or subject.
"""
import asyncio

from google.api_core import exceptions as google_errors

from app.core import firebase
from app.core.config import settings

TIMEOUT_SECONDS = 20


class MailDown(Exception):
    """Firestore unreachable, or refusing the whole account: try again later, without using up a try."""


class EmailRejected(Exception):
    """Firestore refused this one email."""


def enabled() -> bool:
    return firebase.enabled()


def _create(doc_id: str, data: dict) -> None:
    """Runs in a worker thread (Google's client is not async). create() fails if the id exists."""
    (firebase.firestore_client().collection(settings.FIREBASE_MAIL_COLLECTION)
     .document(doc_id).create(data, timeout=TIMEOUT_SECONDS))


async def send(doc_id: str, to: str, subject: str, text: str) -> None:
    """Hands one plain-text email to Firebase. Raises MailDown or EmailRejected (see the top of this file)."""
    data = {"to": [to], "message": {"subject": subject, "text": text}}  # the extension's format
    try:
        await asyncio.to_thread(_create, doc_id, data)
    except google_errors.AlreadyExists:
        return  # handed over before (e.g. the API stopped before saving "sent"): never twice
    except google_errors.InvalidArgument as e:
        raise EmailRejected(f"Firestore refused the email: {str(e)[:200]}") from e
    except Exception as e:  # no answer, no permission, bad key, quota, Google down...
        raise MailDown(f"{type(e).__name__}: {str(e)[:200]}") from e
