"""Notification emails through Brevo: every bell notification also goes to the employee's email.
Brevo isn't really called: a fake Brevo (httpx.MockTransport) answers, and `brevo.calls` keeps each request."""
import json

import httpx
import pytest
from sqlalchemy import select, update

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.jobs import runner
from app.models.notification import Notification
from app.models.user import User
from app.services import email_service, notification_service
from tests.conftest import make_user


class FakeBrevo:
    def __init__(self):
        self.calls: list[httpx.Request] = []
        self.answer = lambda request: httpx.Response(201, json={"messageId": "<1@brevo>"})

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(request)
        return self.answer(request)

    def sent_to(self) -> list[str]:
        return [json.loads(c.content)["to"][0]["email"] for c in self.calls]


@pytest.fixture
def brevo(monkeypatch):
    fake = FakeBrevo()
    real = httpx.AsyncClient
    monkeypatch.setattr(email_service.httpx, "AsyncClient", lambda **kw: real(transport=httpx.MockTransport(fake.handler), **kw))
    monkeypatch.setattr(settings, "BREVO_API_KEY", "test-key")
    monkeypatch.setattr(settings, "SMTP_FROM", "KJS India <no-reply@kjsindia.com>")
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


async def test_each_notification_is_emailed_once(brevo):
    await make_user("e@kjsindia.com")
    await notify("e@kjsindia.com")
    assert await runner.run_job("send_emails") == {"sent": 1, "skipped": 0, "failed": 0}
    req = brevo.calls[0]
    assert str(req.url) == email_service.BREVO_URL and req.headers["api-key"] == "test-key"
    body = json.loads(req.content)
    assert body["sender"] == {"name": "KJS India", "email": "no-reply@kjsindia.com"}
    assert body["to"] == [{"email": "e@kjsindia.com"}] and body["subject"] == "[KJS] New lead: Asha"
    assert "Asha asked about coffee." in body["textContent"]
    assert f"Open: {settings.PUBLIC_BASE_URL}/employee/dashboard" in body["textContent"]
    assert await statuses() == {"e@kjsindia.com": ("sent", 0)}
    await runner.run_job("send_emails")  # nothing left: never sent twice
    assert len(brevo.calls) == 1


async def test_email_switched_off_or_disabled_account_gets_no_email(brevo):
    await make_user("on@kjsindia.com")
    await make_user("off@kjsindia.com")
    await make_user("gone@kjsindia.com", status="disabled")
    async with AsyncSessionLocal() as db:
        await db.execute(update(User).where(User.email == "off@kjsindia.com").values(notify_email=False))
        await db.commit()
    await notify("on@kjsindia.com", "off@kjsindia.com", "gone@kjsindia.com")
    assert await runner.run_job("send_emails") == {"sent": 1, "skipped": 2, "failed": 0}
    assert brevo.sent_to() == ["on@kjsindia.com"]


async def test_visitor_text_gets_the_warning_note(brevo):
    await make_user("e@kjsindia.com")
    await notify("e@kjsindia.com", kind="lead.new")
    await runner.run_job("send_emails")
    assert "typed by a website visitor" in json.loads(brevo.calls[0].content)["textContent"]


async def test_a_refused_email_uses_a_try_and_the_others_still_go(brevo):
    await make_user("bad@kjsindia.com")
    await make_user("good@kjsindia.com")
    await notify("bad@kjsindia.com", "good@kjsindia.com")
    brevo.answer = lambda request: (httpx.Response(400, json={"code": "invalid_parameter", "message": "email is not valid"})
                                    if "bad@" in request.content.decode() else httpx.Response(201, json={}))
    assert await runner.run_job("send_emails") == {"sent": 1, "skipped": 0, "failed": 1}
    assert await statuses() == {"bad@kjsindia.com": ("pending", 1), "good@kjsindia.com": ("sent", 0)}
    for _ in range(2):  # 3 tries in all, then it stops
        await runner.run_job("send_emails")
    assert (await statuses())["bad@kjsindia.com"] == ("failed", 3)
    calls = len(brevo.calls)
    await runner.run_job("send_emails")
    assert len(brevo.calls) == calls  # a failed email isn't tried again


def no_route(request: httpx.Request) -> httpx.Response:
    raise httpx.ConnectError("no route to host")


@pytest.mark.parametrize("answer", [
    lambda r: httpx.Response(401, json={"code": "unauthorized", "message": "Key not found"}),
    lambda r: httpx.Response(401, json={"code": "unauthorized", "message": "We have detected you are using an unrecognised IP address"}),
    lambda r: httpx.Response(429, json={"message": "Too many requests"}),
    lambda r: httpx.Response(503, text="Service Unavailable"),
    lambda r: no_route(r),
])
async def test_brevo_down_costs_no_try_and_one_request_per_run(brevo, answer):
    for name in ("a", "b", "c"):
        await make_user(f"{name}@kjsindia.com")
    await notify("a@kjsindia.com", "b@kjsindia.com", "c@kjsindia.com")
    brevo.answer = answer
    for _ in range(5):  # an outage of 5 runs: nothing lost, no tries used up (CR10)
        assert (await runner.run_job("send_emails"))["failed"] == 0
    assert len(brevo.calls) == 5  # one try per run, not one per email
    assert set((await statuses()).values()) == {("pending", 0)}
    brevo.answer = lambda r: httpx.Response(201, json={})  # Brevo is back: everything goes out
    await runner.run_job("send_emails")
    assert set((await statuses()).values()) == {("sent", 0)}


async def test_without_brevo_key_smtp_rules_stay(brevo, monkeypatch):
    monkeypatch.setattr(settings, "BREVO_API_KEY", "")
    monkeypatch.setattr(settings, "SMTP_HOST", "")
    await make_user("e@kjsindia.com")
    await notify("e@kjsindia.com")
    assert await runner.run_job("send_emails") == {"sent": 0, "skipped": 1, "failed": 0}
    assert brevo.calls == []
