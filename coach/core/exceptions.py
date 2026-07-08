"""Domain and application exception hierarchy.

Every application error derives from :class:`AppException`, which carries an
HTTP status code and a stable machine-readable ``error_code``. The centralized
exception handlers translate any raised error into a consistent JSON envelope.
"""
from __future__ import annotations

from typing import Any


class AppException(Exception):
    """Base class for all expected application errors."""

    status_code: int = 500
    error_code: str = "internal_error"
    message: str = "An unexpected error occurred."

    def __init__(self, message: str | None = None, *, details: Any | None = None) -> None:
        self.message = message or self.__class__.message
        self.details = details
        super().__init__(self.message)


class ConfigurationError(AppException):
    status_code = 500
    error_code = "configuration_error"
    message = "The service is misconfigured."


class CustomerNotFoundError(AppException):
    status_code = 404
    error_code = "customer_not_found"
    message = "No financial profile found for the given customer."


class SessionNotFoundError(AppException):
    status_code = 404
    error_code = "session_not_found"
    message = "No conversation found for the given session."


class DomainValidationError(AppException):
    status_code = 422
    error_code = "domain_validation_error"
    message = "The request violates a business rule."


class KnowledgeRetrievalError(AppException):
    status_code = 502
    error_code = "knowledge_retrieval_error"
    message = "Failed to retrieve financial knowledge."


class LLMError(AppException):
    status_code = 502
    error_code = "llm_error"
    message = "The language model could not generate a response."


class CoachingError(AppException):
    status_code = 500
    error_code = "coaching_error"
    message = "Failed to generate a coaching response."
