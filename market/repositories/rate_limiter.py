"""Client-side token-bucket rate limiter.

Protects the upstream provider quota. Tokens refill continuously at
``rate_per_sec`` up to ``capacity`` (the burst size). ``acquire`` optionally
blocks up to ``timeout`` seconds waiting for a token; if none becomes available
in time it raises :class:`RateLimitExceededError` carrying a ``Retry-After`` hint.
Clock and sleep are injectable for deterministic tests.
"""
from __future__ import annotations

import threading
import time
from typing import Callable

from market.core.exceptions import RateLimitExceededError


class TokenBucketRateLimiter:
    def __init__(
        self,
        *,
        rate_per_sec: float,
        capacity: int,
        time_func: Callable[[], float] = time.monotonic,
        sleep_func: Callable[[float], None] = time.sleep,
    ) -> None:
        if rate_per_sec <= 0:
            raise ValueError("rate_per_sec must be positive")
        self._rate = float(rate_per_sec)
        self._capacity = float(max(1, capacity))
        self._now = time_func
        self._sleep = sleep_func
        self._tokens = self._capacity
        self._last = self._now()
        self._lock = threading.Lock()

    def _refill(self) -> None:
        now = self._now()
        elapsed = now - self._last
        if elapsed > 0:
            self._tokens = min(self._capacity, self._tokens + elapsed * self._rate)
            self._last = now

    def acquire(self, *, timeout: float = 0.0) -> None:
        deadline = self._now() + max(0.0, timeout)
        while True:
            with self._lock:
                self._refill()
                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return
                needed = 1.0 - self._tokens
                wait = needed / self._rate
            if self._now() + wait > deadline + 1e-9:
                raise RateLimitExceededError(
                    "Client-side rate limit exceeded; please retry later.",
                    details={"rate_per_sec": self._rate, "capacity": self._capacity},
                    retry_after=round(wait, 3),
                )
            self._sleep(wait)

    def stats(self) -> dict[str, float]:
        with self._lock:
            self._refill()
            return {
                "rate_per_sec": self._rate,
                "capacity": self._capacity,
                "available_tokens": round(self._tokens, 3),
            }
