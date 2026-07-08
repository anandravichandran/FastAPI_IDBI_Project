"""Domain and application exception hierarchy.

Every error carries an HTTP ``status_code`` and a machine-readable ``code`` so
the exception handlers can render a consistent JSON envelope. The ``retryable``
flag drives the retry policy: only transient upstream failures (429 / 503) set
it, so deterministic errors (validation, not-found) are never retried.
"""
from __future__ import annotations

from typing import Any


class AppException(Exception):
    """Base class for all handled application errors."""

    status_code: int = 500
    code: str = "internal_error"

    def __init__(
        self,
        message: str,
        *,
        details: dict[str, Any] | None = None,
        retryable: bool = False,
        retry_after: float | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}
        self.retryable = retryable
        self.retry_after = retry_after

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "error": {"code": self.code, "message": self.message}
        }
        if self.details:
            payload["error"]["details"] = self.details
        return payload


class DomainValidationError(AppException):
    status_code = 422
    code = "validation_error"


class ConfigurationError(AppException):
    status_code = 500
    code = "configuration_error"


class SymbolNotFoundError(AppException):
    status_code = 404
    code = "symbol_not_found"


class ProviderError(AppException):
    status_code = 502
    code = "provider_error"


class UpstreamUnavailableError(AppException):
    """Transient upstream failure - safe to retry."""

    status_code = 503
    code = "upstream_unavailable"

    def __init__(
        self,
        message: str,
        *,
        details: dict[str, Any] | None = None,
        retry_after: float | None = None,
    ) -> None:
        super().__init__(message, details=details, retryable=True, retry_after=retry_after)


class UpstreamRateLimitedError(AppException):
    """Upstream provider returned HTTP 429 - retryable with backoff."""

    status_code = 429
    code = "upstream_rate_limited"

    def __init__(
        self,
        message: str,
        *,
        details: dict[str, Any] | None = None,
        retry_after: float | None = None,
    ) -> None:
        super().__init__(message, details=details, retryable=True, retry_after=retry_after)


class RateLimitExceededError(AppException):
    """Client-side (our own) rate limit exceeded - not retried internally."""

    status_code = 429
    code = "rate_limit_exceeded"

    def __init__(
        self,
        message: str,
        *,
        details: dict[str, Any] | None = None,
        retry_after: float | None = None,
    ) -> None:
        super().__init__(message, details=details, retryable=False, retry_after=retry_after)
