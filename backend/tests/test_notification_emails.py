"""Notification emails through Firebase: every bell notification also goes to the employee's email.
Firestore isn't really called: a fake keeps each "mail" document (like Firestore, it refuses an id twice)."""
import pytest
from google.api_core import exceptions as google_errors
from sqlalchemy import select, update

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.jobs import runner
from app.models.notification import Notification
from app.models.user import User
from app.services import email_service, notification_service
from tests.conftest import make_user


class FakeFirestore:
    def __init__(self):
        self.docs: dict[str, dict] = {}
        self.calls = 0
        self.error = lambda doc_id, data: None  # set to raise, to act like a failing Firestore

    def create(self, doc_id: str, data: dict) -> None:
        self.calls += 1
        self.error(doc_id, data)
        if doc_id in self.docs:
            raise google_errors.AlreadyExists("document exists")
        self.docs[doc_id] = data

    def sent_to(self) -> list[str]:
        return [d["to"][0] for d in self.docs.values()]


@pytest.fixture
def firestore(monkeypatch):
    fake = FakeFirestore()
    monkeypatch.setattr(email_service, "_create", fake.create)
    monkeypatch.setattr(settings, "FIREBASE_SERVICE_ACCOUNT", '{"fake": "only for tests"}')
    return fake


async def notify(*emails: str, title: str = "New lead: Asha", body: str = "Asha asked about coffee.",
                 link: str = "/employee/dashboard", kind: str = "task.due"):
    async with AsyncSessionLocal() as db:
        ids = (await db.scalars(select(User.id).where(User.email.in_(emails)))).all()
        notification_service.notify(db, ids, kind, title, body, link)
        await db.commit()


async def statuses() -> dict[str, tuple[str, int]]:
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(select(User.email, Notification.email_status, Notification.email_attempts)
                                 .join(User, User.id == Notification.user_id))).all()
    return {e: (s, a) for e, s, a in rows}


async def test_each_notification_is_emailed_once(firestore):
    await make_user("e@kjsindia.com")
    await notify("e@kjsindia.com")
    assert await runner.run_job("send_emails") == {"sent": 1, "skipped": 0, "failed": 0}
    [(doc_id, doc)] = firestore.docs.items()
    assert doc_id.startswith("notification-1-")
    assert doc["to"] == ["e@kjsindia.com"] and doc["message"]["subject"] == "[KJS] New lead: Asha"
    assert "Asha asked about coffee." in doc["message"]["text"]
    assert f"Open: {settings.PUBLIC_BASE_URL}/employee/dashboard" in doc["message"]["text"]
    assert await statuses() == {"e@kjsindia.com": ("sent", 0)}
    await runner.run_job("send_emails")  # nothing left: never sent twice
    assert firestore.calls == 1


async def test_written_but_not_saved_as_sent_is_not_sent_twice(firestore):
    # The API wrote the email to Firestore, then stopped before saving "sent": the next run writes the same
    # id again, Firestore refuses the copy, and it counts as sent (one email in the inbox, not two)
    await make_user("e@kjsindia.com")
    await notify("e@kjsindia.com")
    await runner.run_job("send_emails")
    async with AsyncSessionLocal() as db:
        await db.execute(update(Notification).values(email_status="pending"))
        await db.commit()
    assert await runner.run_job("send_emails") == {"sent": 1, "skipped": 0, "failed": 0}
    assert len(firestore.docs) == 1


async def test_email_switched_off_or_disabled_account_gets_no_email(firestore):
    await make_user("on@kjsindia.com")
    await make_user("off@kjsindia.com")
    await make_user("gone@kjsindia.com", status="disabled")
    async with AsyncSessionLocal() as db:
        await db.execute(update(User).where(User.email == "off@kjsindia.com").values(notify_email=False))
        await db.commit()
    await notify("on@kjsindia.com", "off@kjsindia.com", "gone@kjsindia.com")
    assert await runner.run_job("send_emails") == {"sent": 1, "skipped": 2, "failed": 0}
    assert firestore.sent_to() == ["on@kjsindia.com"]


async def test_visitor_text_gets_the_warning_note(firestore):
    await make_user("e@kjsindia.com")
    await notify("e@kjsindia.com", kind="lead.new")
    await runner.run_job("send_emails")
    [doc] = firestore.docs.values()
    assert "typed by a website visitor" in doc["message"]["text"]


async def test_a_refused_email_uses_a_try_and_the_others_still_go(firestore):
    await make_user("bad@kjsindia.com")
    await make_user("good@kjsindia.com")
    await notify("bad@kjsindia.com", "good@kjsindia.com")

    def refuse_bad(doc_id, data):
        if data["to"] == ["bad@kjsindia.com"]:
            raise google_errors.InvalidArgument("document too large")

    firestore.error = refuse_bad
    assert await runner.run_job("send_emails") == {"sent": 1, "skipped": 0, "failed": 1}
    assert await statuses() == {"bad@kjsindia.com": ("pending", 1), "good@kjsindia.com": ("sent", 0)}
    for _ in range(2):  # 3 tries in all, then it stops
        await runner.run_job("send_emails")
    assert (await statuses())["bad@kjsindia.com"] == ("failed", 3)
    calls = firestore.calls
    await runner.run_job("send_emails")
    assert firestore.calls == calls  # a failed email isn't tried again


def raises(error: Exception):
    def fail(doc_id, data):
        raise error
    return fail


@pytest.mark.parametrize("error", [
    google_errors.PermissionDenied("Missing or insufficient permissions"),
    google_errors.Unauthenticated("bad key"),
    google_errors.ServiceUnavailable("Google is down"),
    google_errors.DeadlineExceeded("timeout"),
    google_errors.ResourceExhausted("quota"),
    ValueError("Invalid service account certificate"),  # a broken FIREBASE_SERVICE_ACCOUNT
])
async def test_firebase_down_costs_no_try_and_one_request_per_run(firestore, error):
    for name in ("a", "b", "c"):
        await make_user(f"{name}@kjsindia.com")
    await notify("a@kjsindia.com", "b@kjsindia.com", "c@kjsindia.com")
    firestore.error = raises(error)
    for _ in range(5):  # an outage of 5 runs: nothing lost, no tries used up (CR10)
        assert (await runner.run_job("send_emails"))["failed"] == 0
    assert firestore.calls == 5  # one try per run, not one per email
    assert set((await statuses()).values()) == {("pending", 0)}
    firestore.error = lambda doc_id, data: None  # Firebase is back: everything goes out
    await runner.run_job("send_emails")
    assert set((await statuses()).values()) == {("sent", 0)}


async def test_without_firebase_smtp_rules_stay(firestore, monkeypatch):
    monkeypatch.setattr(settings, "FIREBASE_SERVICE_ACCOUNT", "")
    monkeypatch.setattr(settings, "SMTP_HOST", "")
    await make_user("e@kjsindia.com")
    await notify("e@kjsindia.com")
    assert await runner.run_job("send_emails") == {"sent": 0, "skipped": 1, "failed": 0}
    assert firestore.calls == 0
