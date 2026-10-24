"""Logger: request ID on responses and log lines; secrets and personal data masked."""
import logging

from app.core.logs import JsonFormatter, mask


def test_mask_email_and_phone():
    assert mask("om.prakash@alnoor.ae") == "om***@alnoor.ae"
    assert "***" in mask("+91 97037 35666")


def test_secret_fields_hidden():
    rec = logging.LogRecord("t", logging.INFO, "", 0, "auth.test", None, None)
    rec.password = "hunter2"
    rec.api_token = "abc"
    out = JsonFormatter().format(rec)
    assert "hunter2" not in out and "abc" not in out and '"event": "auth.test"' in out


async def test_request_id_returned_and_kept(client):
    r = await client.get("/api/health")
    assert len(r.headers["x-request-id"]) >= 6
    r = await client.get("/api/health", headers={"x-request-id": "next-abc123"})
    assert r.headers["x-request-id"] == "next-abc123"


async def test_error_body_has_request_id(client):
    r = await client.get("/api/v1/nope", headers={"x-request-id": "trace-me-123"})
    assert r.status_code == 404 and r.json()["request_id"] == "trace-me-123"
