"""Tiny in-memory rate limiter. Fine for one server process; move to the DB or
Cloudflare rules when we run more than one."""
import time
from collections import defaultdict, deque
from typing import Callable

from app.core.config.ini import cfg
from app.core.errors import AppError


ALL: list["RateLimiter"] = []


def reset_all() -> None:  # used by tests
    for limiter in ALL:
        limiter.reset()


SWEEP_EVERY_SECONDS = 60


class RateLimiter:
    def __init__(self, limit: Callable[[], int], window_seconds: int):
        self.limit, self.window = limit, window_seconds  # limit is read on every check (live config)
        self._hits: dict[str, deque] = defaultdict(deque)
        self._swept_at = time.monotonic()
        ALL.append(self)

    def _sweep(self) -> None:
        """Once a minute, drop every key with no recent hits. Without this, a bot trying a million
        different emails or IPs would fill the server's memory (keys it never repeats stay forever)."""
        now = time.monotonic()
        if now - self._swept_at < SWEEP_EVERY_SECONDS:
            return
        self._swept_at = now
        for key in [k for k, q in self._hits.items() if not q or now - q[-1] > self.window]:
            del self._hits[key]

    def _recent(self, key: str) -> deque:
        now, q = time.monotonic(), self._hits.get(key)
        if q is None:
            return deque()
        while q and now - q[0] > self.window:
            q.popleft()
        if not q:
            del self._hits[key]  # forget idle keys, so memory doesn't grow with every IP ever seen
        return q

    def blocked(self, key: str | None) -> bool:
        """Is this key over the limit right now? (does not count as a hit)"""
        return bool(key) and len(self._recent(key)) >= self.limit()

    def hit(self, key: str | None) -> None:
        """Count one hit, without refusing (e.g. a wrong password)."""
        if key:
            self._sweep()
            self._recent(key)
            self._hits[key].append(time.monotonic())

    def check(self, key: str | None, message: str = "Too many requests. Please try again later or WhatsApp us.") -> None:
        """Refuse if over the limit, otherwise count this hit. `message`: what the person is told (the
        default is for website visitors; staff features pass their own)."""
        if self.blocked(key):
            raise AppError(429, "too_many", message)
        self.hit(key)

    def reset(self) -> None:  # used by tests
        self._hits.clear()


# Limits per IP per hour come from config/app.ini
lead_limiter = RateLimiter(limit=lambda: cfg().app.lead_rate_per_hour, window_seconds=3600)
koko_limiter = RateLimiter(limit=lambda: cfg().app.koko_rate_per_hour, window_seconds=3600)
# Staff reading Excel / CSV files into the New internal lead form, per person per hour
lead_file_limiter = RateLimiter(limit=lambda: cfg().app.lead_file_reads_per_hour, window_seconds=3600)
# Passwords are checked by Firebase (it blocks guessing itself). Here: bad Firebase tokens (fake, expired,
# revoked) per network. Only bad ones count, so a whole office logging in from one address is never blocked
# (CR7), and a stranger's network never blocks anyone else's (CR5).
login_ip_limiter = RateLimiter(limit=lambda: cfg().app.login_failures_per_ip, window_seconds=900)
signup_limiter = RateLimiter(limit=lambda: cfg().app.signups_per_ip_per_hour, window_seconds=3600)
# Chat messages per person (not per IP): stops a stuck key or a script flooding a channel.
chat_send_limiter = RateLimiter(limit=lambda: 30, window_seconds=60)
