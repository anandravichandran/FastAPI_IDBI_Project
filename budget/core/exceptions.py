"""Domain and application exceptions for the Budget Planner.

Every expected error derives from :class:`AppException`, which carries an HTTP
status, a stable machine-readable ``error_code`` and an optional details
payload. The centralized handlers convert these into a single JSON envelope so
clients get predictable errors and stack traces never leak.
"""
from __future__ import annotations

from typing import Any


class AppException(Exception):
    """Base class for all handled application errors."""

    status_code: int = 500
    error_code: str = "internal_error"

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        error_code: str | None = None,
        details: Any | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        if error_code is not None:
            self.error_code = error_code
        self.details = details


class DomainValidationError(AppException):
    """Raised when inputs are individually valid but jointly inconsistent."""

    status_code = 422
    error_code = "domain_validation_error"


class BudgetComputationError(AppException):
    """Raised when a budget plan cannot be produced from the given inputs."""

    status_code = 422
    error_code = "budget_computation_error"


class ConfigurationError(AppException):
    """Raised when the service is misconfigured."""

    status_code = 500
    error_code = "configuration_error"
