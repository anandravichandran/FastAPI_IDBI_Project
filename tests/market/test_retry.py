"""Unit tests for the retry helper."""
from __future__ import annotations

import pytest

from market.core.exceptions import (
    DomainValidationError,
    UpstreamRateLimitedError,
    UpstreamUnavailableError,
)
from market.repositories.retry import RetryPolicy, with_retries


def test_retries_transient_then_succeeds():
    calls = {"n": 0}
    slept: list[float] = []

    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise UpstreamUnavailableError("boom")
        return "ok"

    policy = RetryPolicy(max_attempts=3, base_delay=0.0, max_delay=0.0, jitter=0.0)
    result = with_retries(flaky, policy=policy, sleep_func=slept.append)
    assert result == "ok"
    assert calls["n"] == 3
    assert len(slept) == 2  # slept between the three attempts


def test_gives_up_after_max_attempts():
    calls = {"n": 0}

    def always_fail():
        calls["n"] += 1
        raise UpstreamUnavailableError("down")

    policy = RetryPolicy(max_attempts=3, base_delay=0.0, max_delay=0.0, jitter=0.0)
    with pytest.raises(UpstreamUnavailableError):
        with_retries(always_fail, policy=policy, sleep_func=lambda _: None)
    assert calls["n"] == 3


def test_non_retryable_raises_immediately():
    calls = {"n": 0}

    def bad_input():
        calls["n"] += 1
        raise DomainValidationError("nope")

    policy = RetryPolicy(max_attempts=5, base_delay=0.0, max_delay=0.0, jitter=0.0)
    with pytest.raises(DomainValidationError):
        with_retries(bad_input, policy=policy, sleep_func=lambda _: None)
    assert calls["n"] == 1  # not retried


def test_retry_after_is_honoured():
    policy = RetryPolicy(max_attempts=3, base_delay=0.25, max_delay=5.0, jitter=0.0)
    exc = UpstreamRateLimitedError("429", retry_after=2.5)
    assert policy.compute_delay(1, retry_after=exc.retry_after) == 2.5
