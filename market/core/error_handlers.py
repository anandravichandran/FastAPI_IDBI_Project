"""Centralised exception handlers producing a consistent JSON envelope."""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from market.core.exceptions import AppException
from market.core.logging import get_logger

logger = get_logger(__name__)


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppException)
    async def _handle_app_exception(request: Request, exc: AppException) -> JSONResponse:
        payload = exc.to_dict()
        request_id = _request_id(request)
        if request_id:
            payload["error"]["request_id"] = request_id
        headers: dict[str, str] = {}
        if exc.retry_after is not None:
            headers["Retry-After"] = str(max(1, int(exc.retry_after + 0.999)))
        log = logger.warning if exc.status_code < 500 else logger.error
        log(
            "request.app_exception",
            extra={"request_id": request_id, "code": exc.code, "status_code": exc.status_code},
        )
        return JSONResponse(status_code=exc.status_code, content=payload, headers=headers)

    @app.exception_handler(Exception)
    async def _handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
        request_id = _request_id(request)
        logger.exception("request.unhandled_exception", extra={"request_id": request_id})
        payload = {"error": {"code": "internal_error", "message": "An unexpected error occurred."}}
        if request_id:
            payload["error"]["request_id"] = request_id
        return JSONResponse(status_code=500, content=payload)
