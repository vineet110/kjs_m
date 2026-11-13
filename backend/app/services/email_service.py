"""Brevo (brevo.com) HTTP API: how notification emails go out when BREVO_API_KEY is set.

Why not SMTP: Render's free tier blocks the SMTP ports, and Brevo's API is one HTTPS request (port 443).
Without BREVO_API_KEY the queue in notification_service.py still uses SMTP (SMTP_HOST), as before.

Two kinds of failure, because the queue treats them differently (CR10):
1. BrevoDown: Brevo can't be reached, or refuses US (wrong key, IP not authorised, account not active,
   too many requests, its own error). Not the email's fault: it waits in the queue WITHOUT using up one of
   its 3 tries, and the rest of the batch waits too.
2. EmailRejected: Brevo refused this one email (e.g. a bad address). It uses up a try; the rest still go.

Never logs an email's text or subject.
"""
from email.utils import parseaddr

import httpx

from app.core.config import settings

BREVO_URL = "https://api.brevo.com/v3/smtp/email"
TIMEOUT_SECONDS = 15
# Answers that mean "Brevo won't take anything from us right now", not "this email is wrong":
# 401 wrong key or IP not authorised, 402 account not activated / out of credits, 403 not allowed, 429 too many
BREVO_DOWN_STATUSES = {401, 402, 403, 429}


class BrevoDown(Exception):
    """Brevo unreachable or refusing the whole account: try again later, without using up a try."""


class EmailRejected(Exception):
    """Brevo refused this one email."""


def enabled() -> bool:
    return bool(settings.BREVO_API_KEY)


def sender() -> dict:
    """{"name": "KJS India", "email": "no-reply@kjsindia.com"} from SMTP_FROM (must be verified in Brevo)."""
    name, address = parseaddr(settings.SMTP_FROM)
    return {"name": name or "KJS India", "email": address}


def client() -> httpx.AsyncClient:
    """One client for a whole batch: the connection to Brevo is reused, like the SMTP connection."""
    return httpx.AsyncClient(timeout=TIMEOUT_SECONDS,
                             headers={"api-key": settings.BREVO_API_KEY, "accept": "application/json"})


async def send(http: httpx.AsyncClient, to: str, subject: str, text: str) -> None:
    """Sends one plain-text email. Raises BrevoDown or EmailRejected (see the top of this file)."""
    try:
        r = await http.post(BREVO_URL, json={"sender": sender(), "to": [{"email": to}],
                                              "subject": subject, "textContent": text})
    except httpx.HTTPError as e:  # no answer: network, DNS, timeout
        raise BrevoDown(f"{type(e).__name__}: {e}") from e
    if r.status_code < 300:
        return
    # Brevo explains in JSON, e.g. {"code": "unauthorized", "message": "Key not found"}
    reason = f"Brevo answered {r.status_code}: {r.text[:200]}"
    if r.status_code in BREVO_DOWN_STATUSES or r.status_code >= 500:
        raise BrevoDown(reason)
    raise EmailRejected(reason)
