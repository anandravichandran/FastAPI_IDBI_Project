"""Domain and application exceptions for the RAG service.

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


class UnsupportedFileTypeError(AppException):
    """Raised when an uploaded file is not a supported document type."""

    status_code = 415
    error_code = "unsupported_file_type"


class PayloadTooLargeError(AppException):
    """Raised when an upload exceeds the configured size limit."""

    status_code = 413
    error_code = "payload_too_large"


class DocumentProcessingError(AppException):
    """Raised when a document cannot be parsed or chunked."""

    status_code = 422
    error_code = "document_processing_error"


class EmbeddingError(AppException):
    """Raised when the embedding backend fails to produce vectors."""

    status_code = 502
    error_code = "embedding_error"


class VectorStoreError(AppException):
    """Raised when the vector store cannot be read from or written to."""

    status_code = 502
    error_code = "vector_store_error"


class DocumentNotFoundError(AppException):
    """Raised when a referenced document id does not exist."""

    status_code = 404
    error_code = "document_not_found"


class ConfigurationError(AppException):
    """Raised when the service is misconfigured (e.g. a required backend is
    unavailable in production and fallback is disabled)."""

    status_code = 500
    error_code = "configuration_error"
