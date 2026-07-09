"""Async circuit breaker.

Wraps flaky outbound dependencies (LLM inference, OpenBB) so that a burst of
failures trips the breaker OPEN and subsequent calls fail fast for a cooldown
window instead of piling up slow, doomed requests (which exhaust the event
loop, connection pool and worker capacity). After the cooldown the breaker
moves to HALF_OPEN and lets a single probe through to decide whether to close
again.

This is intentionally dependency-free and asyncio-safe. It does not change any
business result: when closed it is transparent, and callers already handle the
underlying failure (e.g. the advisor falls back to a deterministic narrative).
"""
from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from enum import Enum
from typing import TypeVar

T = TypeVar("T")


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreakerOpen(RuntimeError):
    """Raised when a call is rejected because the breaker is OPEN."""


class AsyncCircuitBreaker:
    def __init__(
        self,
        *,
        name: str = "breaker",
        failure_threshold: int = 5,
        reset_timeout_seconds: float = 30.0,
        expected_exceptions: tuple[type[BaseException], ...] = (Exception,),
    ) -> None:
        self.name = name
        self._failure_threshold = max(1, failure_threshold)
        self._reset_timeout = reset_timeout_seconds
        self._expected = expected_exceptions
        self._state = CircuitState.CLOSED
        self._failures = 0
        self._opened_at = 0.0
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        return self._state

    async def _before_call(self) -> None:
        async with self._lock:
            if self._state is CircuitState.OPEN:
                if (time.monotonic() - self._opened_at) >= self._reset_timeout:
                    self._state = CircuitState.HALF_OPEN
                else:
                    raise CircuitBreakerOpen(
                        f"Circuit '{self.name}' is open; failing fast."
                    )

    async def _on_success(self) -> None:
        async with self._lock:
            self._failures = 0
            self._state = CircuitState.CLOSED

    async def _on_failure(self) -> None:
        async with self._lock:
            self._failures += 1
            if (
                self._state is CircuitState.HALF_OPEN
                or self._failures >= self._failure_threshold
            ):
                self._state = CircuitState.OPEN
                self._opened_at = time.monotonic()

    async def call(self, func: Callable[..., Awaitable[T]], *args, **kwargs) -> T:
        await self._before_call()
        try:
            result = await func(*args, **kwargs)
        except self._expected:
            await self._on_failure()
            raise
        else:
            await self._on_success()
            return result
