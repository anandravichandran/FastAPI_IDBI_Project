"""Retry helper with exponential backoff and full jitter.

Only *retryable* failures are retried: application errors whose ``retryable``
flag is set (transient upstream 429/503) plus any exception types listed in
``retry_on`` (connection/timeout by default). Deterministic errors (validation,
not-found) propagate immediately. A server-provided ``Retry-After`` overrides
the computed backoff for that attempt.
"""
from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from market.core.exceptions import AppException
from market.core.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 3
    base_delay: float = 0.25
    max_delay: float = 5.0
    jitter: float = 0.1
    retry_on: tuple[type[BaseException], ...] = field(
        default=(ConnectionError, TimeoutError)
    )

    def is_retryable(self, exc: BaseException) -> bool:
        if isinstance(exc, AppException):
            return exc.retryable
        return isinstance(exc, self.retry_on)

    def compute_delay(self, attempt: int, *, retry_after: float | None = None) -> float:
        """Delay (seconds) before the given 1-based attempt's retry."""
        if retry_after is not None:
            return min(float(retry_after), self.max_delay)
        backoff = self.base_delay * (2 ** max(0, attempt - 1))
        backoff = min(backoff, self.max_delay)
        if self.jitter:
            backoff += random.uniform(0.0, self.jitter * backoff)
        return backoff


def with_retries(
    func: Callable[..., Any],
    *args: Any,
    policy: RetryPolicy,
    sleep_func: Callable[[float], None] = time.sleep,
    operation: str = "",
    **kwargs: Any,
) -> Any:
    attempt = 0
    while True:
        attempt += 1
        try:
            return func(*args, **kwargs)
        except BaseException as exc:  # noqa: BLE001 - re-raised below when not retryable
            if attempt >= policy.max_attempts or not policy.is_retryable(exc):
                raise
            retry_after = getattr(exc, "retry_after", None)
            delay = policy.compute_delay(attempt, retry_after=retry_after)
            logger.warning(
                "operation.retry",
                extra={
                    "operation": operation or getattr(func, "__name__", "call"),
                    "attempt": attempt,
                    "max_attempts": policy.max_attempts,
                    "delay": round(delay, 3),
                    "error": type(exc).__name__,
                },
            )
            sleep_func(delay)
