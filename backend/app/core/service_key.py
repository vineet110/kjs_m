"""Login for other servers (not people): the `X-Api-Key` header.

Used by the monitoring feed. A cookie is never enough here, and no user is involved, so the portal-area
check is done here too (require_module needs a logged-in person and would refuse every call).
The key lives only in .env. Nginx also refuses /api/v1/integrations/ from outside (deploy/nginx/default.conf):
the key is the second wall, not the only one.
"""
import hmac
import logging

from fastapi import Request

from app.core.config import settings
from app.core.errors import AppError
from app.core.modules import AREAS, running

log = logging.getLogger(__name__)

MIN_KEY_LENGTH = 32  # a security limit: in code, never in an ini


def require_monitoring_key():
    """Router dependency for the monitoring feed only: its own key (MONITORING_FEED_KEY), then its area
    (`off` -> 404 module_off). Another server gets its own key and its own function, never this one: one
    leaked key must open one feed."""
    area = "monitoring"
    if area not in AREAS:
        raise ValueError(f"unknown area {area!r}")

    async def checker(request: Request) -> None:
        expected = settings.MONITORING_FEED_KEY
        if len(expected) < MIN_KEY_LENGTH:
            # Not set up (or a weak key): closed for everyone, never open with a default
            raise AppError(503, "feed_not_configured", "This feed is not set up on this server.")
        given = request.headers.get("x-api-key", "")
        if not given or not hmac.compare_digest(given.encode(), expected.encode()):
            log.warning("service_key.refused", extra={"area": area})
            raise AppError(401, "bad_service_key", "Missing or wrong API key.")
        if not running(area):
            raise AppError(404, "module_off", "This part of the portal isn't available yet.", {"module": area})

    checker.module = area  # read by the route map test (tests/test_modules.py)
    return checker
