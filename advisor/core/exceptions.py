"""Domain and application exception hierarchy.

Every application error derives from :class:`AppException`, which carries an
HTTP status code and a stable machine-readable ``error_code``. This lets the
centralized exception handlers translate any raised error into a consistent
JSON envelope without leaking internal details.
"""
from __future__ import annotations

from typing import Any


class AppException(Exception):
    """Base class for all expected application errors."""

    status_code: int = 500
    error_code: str = "internal_error"
    message: str = "An unexpected error occurred."

    def __init__(
        self,
        message: str | None = None,
        *,
        details: Any | None = None,
    ) -> None:
        self.message = message or self.__class__.message
        self.details = details
        super().__init__(self.message)


class ConfigurationError(AppException):
    status_code = 500
    error_code = "configuration_error"
    message = "The service is misconfigured."


class DomainValidationError(AppException):
    status_code = 422
    error_code = "domain_validation_error"
    message = "The request violates a business rule."


class MarketDataError(AppException):
    status_code = 502
    error_code = "market_data_error"
    message = "Failed to retrieve market data."


class KnowledgeRetrievalError(AppException):
    status_code = 502
    error_code = "knowledge_retrieval_error"
    message = "Failed to retrieve financial knowledge."


class LLMError(AppException):
    status_code = 502
    error_code = "llm_error"
    message = "The language model could not generate a response."


class AdviceGenerationError(AppException):
    status_code = 500
    error_code = "advice_generation_error"
    message = "Failed to generate investment advice."
