"""Tiny in-memory rate limiter. Fine for one server process; move to the DB or
Cloudflare rules when we run more than one."""
import time
from collections import defaultdict, deque
from typing import Callable

from app.core.config.ini import cfg
from app.core.errors import AppError


class RateLimiter:
    def __init__(self, limit: Callable[[], int], window_seconds: int):
        self.limit, self.window = limit, window_seconds  # limit is read on every check (live config)
        self._hits: dict[str, deque] = defaultdict(deque)

    def check(self, key: str | None) -> None:
        if not key:
            return
        now, q = time.monotonic(), self._hits[key]
        while q and now - q[0] > self.window:
            q.popleft()
        if len(q) >= self.limit():
            raise AppError(429, "too_many", "Too many requests. Please try again later or WhatsApp us.")
        q.append(now)

    def reset(self) -> None:  # used by tests
        self._hits.clear()


# Limits per IP per hour come from config/app.ini
lead_limiter = RateLimiter(limit=lambda: cfg().app.lead_rate_per_hour, window_seconds=3600)
koko_limiter = RateLimiter(limit=lambda: cfg().app.koko_rate_per_hour, window_seconds=3600)
login_failures = RateLimiter(limit=lambda: 10, window_seconds=900)  # wrong passwords per email per 15 min
