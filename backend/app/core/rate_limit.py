"""Tiny in-memory rate limiter. Fine for one server process; move to the DB or
Cloudflare rules when we run more than one."""
import time
from collections import defaultdict, deque

from app.core.errors import AppError


class RateLimiter:
    def __init__(self, limit: int, window_seconds: int):
        self.limit, self.window = limit, window_seconds
        self._hits: dict[str, deque] = defaultdict(deque)

    def check(self, key: str | None) -> None:
        if not key:
            return
        now, q = time.monotonic(), self._hits[key]
        while q and now - q[0] > self.window:
            q.popleft()
        if len(q) >= self.limit:
            raise AppError(429, "too_many", "Too many requests. Please try again later or WhatsApp us.")
        q.append(now)

    def reset(self) -> None:  # used by tests
        self._hits.clear()


lead_limiter = RateLimiter(limit=5, window_seconds=3600)  # 5 enquiries per IP per hour
koko_limiter = RateLimiter(limit=40, window_seconds=3600)  # 40 chat messages per IP per hour
