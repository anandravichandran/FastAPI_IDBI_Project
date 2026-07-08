"""Custom ASGI middleware.

``RequestContextMiddleware`` assigns a correlation id to every request,
binds it to the logging context and echoes it back on the response, and
logs a structured access record with request latency.
"""
from __future__ import annotations

import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from budget.core.logging import get_logger, request_id_ctx

logger = get_logger("coach.access")

_REQUEST_ID_HEADER = "X-Request-ID"


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get(_REQUEST_ID_HEADER) or uuid.uuid4().hex
        token = request_id_ctx.set(request_id)
        start = time.perf_counter()
        try:
            response = await call_next(request)
        finally:
            elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
            request_id_ctx.reset(token)
        response.headers[_REQUEST_ID_HEADER] = request_id
        logger.info(
            "request.completed",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": elapsed_ms,
                "request_id": request_id,
            },
        )
        return response
