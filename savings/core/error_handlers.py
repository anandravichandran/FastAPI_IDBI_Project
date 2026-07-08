"""Centralized exception handling.

Registers handlers that convert application errors, framework validation
errors and unhandled exceptions into a single, predictable JSON error
envelope. This keeps error semantics consistent across every endpoint and
prevents stack traces from leaking to clients.
"""
from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from savings.core.exceptions import AppException
from savings.core.logging import get_logger, request_id_ctx

logger = get_logger(__name__)


def _envelope(
    *,
    error_code: str,
    message: str,
    details: Any | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "error": {
            "code": error_code,
            "message": message,
        }
    }
    if details is not None:
        body["error"]["details"] = details
    request_id = request_id_ctx.get()
    if request_id:
        body["error"]["request_id"] = request_id
    return body


def register_exception_handlers(app: FastAPI) -> None:
    """Attach all exception handlers to the FastAPI application."""

    @app.exception_handler(AppException)
    async def _handle_app_exception(request: Request, exc: AppException) -> JSONResponse:
        log = logger.error if exc.status_code >= 500 else logger.warning
        log(
            "Handled application error",
            extra={"error_code": exc.error_code, "path": request.url.path},
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope(
                error_code=exc.error_code,
                message=exc.message,
                details=exc.details,
            ),
        )

    @app.exception_handler(RequestValidationError)
    async def _handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        logger.warning("Request validation failed", extra={"path": request.url.path})
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_envelope(
                error_code="request_validation_error",
                message="One or more request fields are invalid.",
                details=exc.errors(),
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _handle_http_exception(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope(
                error_code="http_error",
                message=str(exc.detail),
            ),
        )

    @app.exception_handler(Exception)
    async def _handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled exception", extra={"path": request.url.path})
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_envelope(
                error_code="internal_error",
                message="An unexpected error occurred.",
            ),
        )
