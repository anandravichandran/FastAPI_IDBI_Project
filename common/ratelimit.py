"""Edge rate limiting (token bucket, per client).

Protects the suite from brute-force and volumetric abuse. Implemented as an
in-process token bucket keyed by client IP (honouring ``X-Forwarded-For`` when
behind a trusted proxy such as Render). This is a pragmatic first line of
defence; for horizontally-scaled deployments back it with a shared store
(Redis) so limits are global rather than per-worker — documented in the
deployment report.

Disabled by default and enabled in production via ``RATE_LIMIT_ENABLED`` so it
never interferes with the existing unit-test suite.
"""
from __future__ import annotations

import time
from collections import defaultdict

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp

from common.settings import SecuritySettings, get_security_settings

_EXEMPT_SUFFIXES = ("/health", "/healthz", "/livez", "/readyz")


class _TokenBucket:
    __slots__ = ("tokens", "updated")

    def __init__(self, tokens: float, updated: float) -> None:
        self.tokens = tokens
        self.updated = updated


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, settings: SecuritySettings | None = None) -> None:
        super().__init__(app)
        self._settings = settings or get_security_settings()
        self._capacity = float(self._settings.rate_limit_burst)
        # refill rate in tokens/second
        self._refill = self._settings.rate_limit_per_minute / 60.0
        self._buckets: dict[str, _TokenBucket] = defaultdict(
            lambda: _TokenBucket(self._capacity, time.monotonic())
        )

    def _client_ip(self, request: Request) -> str:
        fwd = request.headers.get("x-forwarded-for")
        if fwd:
            return fwd.split(",")[0].strip()
        return request.client.host if request.client else "anonymous"

    async def dispatch(self, request: Request, call_next):
        if not self._settings.rate_limit_enabled or any(
            request.url.path.endswith(s) for s in _EXEMPT_SUFFIXES
        ):
            return await call_next(request)

        key = self._client_ip(request)
        now = time.monotonic()
        bucket = self._buckets[key]
        elapsed = now - bucket.updated
        bucket.tokens = min(self._capacity, bucket.tokens + elapsed * self._refill)
        bucket.updated = now

        if bucket.tokens < 1.0:
            retry_after = max(1, int((1.0 - bucket.tokens) / self._refill))
            return JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "code": "rate_limited",
                        "message": "Too many requests; slow down.",
                    }
                },
                headers={"Retry-After": str(retry_after)},
            )
        bucket.tokens -= 1.0
        return await call_next(request)
