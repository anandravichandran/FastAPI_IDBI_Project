"""Unit tests for the token-bucket rate limiter."""
from __future__ import annotations

import pytest

from market.core.exceptions import RateLimitExceededError
from market.repositories.rate_limiter import TokenBucketRateLimiter


def test_allows_up_to_capacity_then_rejects():
    clock = {"t": 0.0}
    limiter = TokenBucketRateLimiter(
        rate_per_sec=1.0,
        capacity=3,
        time_func=lambda: clock["t"],
        sleep_func=lambda _: None,
    )
    # Burst of 3 tokens is available immediately.
    for _ in range(3):
        limiter.acquire(timeout=0.0)
    # Fourth call fails fast (no tokens, no wait budget).
    with pytest.raises(RateLimitExceededError):
        limiter.acquire(timeout=0.0)


def test_refills_over_time():
    clock = {"t": 0.0}
    limiter = TokenBucketRateLimiter(
        rate_per_sec=2.0,
        capacity=1,
        time_func=lambda: clock["t"],
        sleep_func=lambda _: None,
    )
    limiter.acquire(timeout=0.0)
    with pytest.raises(RateLimitExceededError):
        limiter.acquire(timeout=0.0)
    clock["t"] = 0.5  # 0.5s * 2 tokens/s = 1 token refilled
    limiter.acquire(timeout=0.0)  # should now succeed


def test_waits_within_timeout():
    clock = {"t": 0.0}

    def sleep(sec: float) -> None:
        clock["t"] += sec

    limiter = TokenBucketRateLimiter(
        rate_per_sec=10.0,
        capacity=1,
        time_func=lambda: clock["t"],
        sleep_func=sleep,
    )
    limiter.acquire(timeout=0.0)
    # Token refills in 0.1s; a 1s wait budget covers it.
    limiter.acquire(timeout=1.0)
