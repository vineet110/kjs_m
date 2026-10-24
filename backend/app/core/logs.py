"""Logging: one line per event, to stdout, with the request ID on every line.

Use it like this in any module:
    log = logging.getLogger(__name__)
    log.info("lead.created", extra={"lead_id": lead.id, "source": lead.source})

The message is a stable dotted event name (searchable); details go in `extra`.
Format and levels come from config/logging.ini and change live.
Never log passwords, tokens or cookies; emails and phones are masked automatically.
The audit_log table is the business record; these logs are for debugging.
"""
import json
import logging
import re
import sys
import time
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.config import settings
from app.core.config.ini import Config, cfg, on_reload

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
user_id_var: ContextVar[int | None] = ContextVar("user_id", default=None)

SERVICE = "api"
SECRET_WORDS = ("password", "token", "cookie", "secret", "authorization", "api_key")
EMAIL_RE = re.compile(r"([A-Za-z0-9._%+-]{1,2})[A-Za-z0-9._%+-]*(@[A-Za-z0-9.-]+\.[A-Za-z]{2,})")
PHONE_RE = re.compile(r"(\+?\d[\d\s-]{3})[\d\s-]{4,}(\d{2})")
# Attributes every LogRecord has; anything else came from `extra=`.
_STANDARD = set(vars(logging.LogRecord("", 0, "", 0, "", None, None))) | {"message", "asctime", "taskName"}


def mask(text: str) -> str:
    """om***@alnoor.ae, +91 9***12"""
    if cfg().logging.show_personal_data:
        return text
    return PHONE_RE.sub(r"\1***\2", EMAIL_RE.sub(r"\1***\2", text))


def _clean(key: str, value):
    if any(w in key.lower() for w in SECRET_WORDS):
        return "***"
    if isinstance(value, str):
        return mask(value)
    if isinstance(value, dict):
        return {k: _clean(k, v) for k, v in value.items()}
    return value


def _fields(record: logging.LogRecord) -> dict:
    out = {
        "ts": datetime.fromtimestamp(record.created, timezone.utc).isoformat(timespec="milliseconds"),
        "level": record.levelname,
        "service": SERVICE,
        "env": settings.APP_ENV,
        "logger": record.name,
        "event": mask(record.getMessage()),
        "request_id": request_id_var.get(),
        "user_id": user_id_var.get(),
    }
    for k, v in vars(record).items():
        if k not in _STANDARD and not k.startswith("_"):
            out[k] = _clean(k, v)
    if record.exc_info:
        out["error"] = logging.Formatter().formatException(record.exc_info)
    return out


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return json.dumps(_fields(record), default=str, ensure_ascii=False)


class PrettyFormatter(logging.Formatter):
    """Easy to read on a dev machine: 10:42:01 INFO  lead.created source=koko [rid=ab12cd]"""

    SKIP = {"ts", "level", "service", "env", "logger", "event", "request_id", "user_id", "error"}

    def format(self, record: logging.LogRecord) -> str:
        f = _fields(record)
        extras = " ".join(f"{k}={v}" for k, v in f.items() if k not in self.SKIP and v is not None)
        rid = f" [rid={f['request_id']}]" if f["request_id"] else ""
        line = f"{f['ts'][11:19]} {f['level']:<7} {f['event']} {extras}{rid}".rstrip()
        return line + ("\n" + f["error"] if "error" in f else "")


_handler = logging.StreamHandler(sys.stdout)


def _apply(c: Config) -> None:
    _handler.setFormatter(JsonFormatter() if c.logging.format == "json" else PrettyFormatter())
    root = logging.getLogger()
    root.setLevel(c.logging.level.upper())
    for name, level in c.logging.levels.items():
        logging.getLogger(name).setLevel(level.upper())


def setup_logging() -> None:
    """Call once at startup. Routes uvicorn/sqlalchemy/httpx logs through the same handler."""
    root = logging.getLogger()
    if _handler not in root.handlers:
        root.handlers = [_handler]
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        lg = logging.getLogger(name)
        lg.handlers, lg.propagate = [], True
    logging.getLogger("uvicorn.access").disabled = True  # our middleware logs requests instead
    on_reload(_apply)


http_log = logging.getLogger("app.http")


class RequestContextMiddleware:
    """Gives every request an ID (or keeps the one Next.js sent), puts it on every log line
    and in the response header, and logs one `http.request` line with the timing."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        headers = dict(scope["headers"])
        incoming = headers.get(b"x-request-id", b"").decode()[:64]
        rid = incoming if re.fullmatch(r"[A-Za-z0-9-]{6,64}", incoming or "") else uuid.uuid4().hex[:12]
        scope.setdefault("state", {})["request_id"] = rid
        rid_token, uid_token = request_id_var.set(rid), user_id_var.set(None)
        start, status = time.perf_counter(), 500

        async def send_wrapper(message: Message):
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                message.setdefault("headers", []).append((b"x-request-id", rid.encode()))
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            route = scope.get("route")
            path = getattr(route, "path", scope["path"])
            level = logging.DEBUG if path.startswith("/api/health") else logging.INFO
            http_log.log(level, "http.request", extra={
                "method": scope["method"], "route": path, "status": status,
                "duration_ms": round((time.perf_counter() - start) * 1000, 1),
            })
            request_id_var.reset(rid_token)
            user_id_var.reset(uid_token)
