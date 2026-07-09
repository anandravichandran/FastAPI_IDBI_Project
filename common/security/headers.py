"""Security response headers.

Adds the standard hardening headers expected on a banking API. These are cheap,
broadly compatible defaults that mitigate MIME-sniffing, clickjacking,
referrer leakage and (over HTTPS) protocol downgrade. A conservative CSP is
applied; the Swagger/Redoc doc routes are exempted from the strict CSP so the
interactive docs keep working.
"""
from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.types import ASGIApp

from common.settings import SecuritySettings, get_security_settings

_DOC_PATHS = ("/docs", "/redoc", "/openapi.json")


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, settings: SecuritySettings | None = None) -> None:
        super().__init__(app)
        self._settings = settings or get_security_settings()

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        s = self._settings
        if not s.security_headers_enabled:
            return response

        headers = response.headers
        headers.setdefault("X-Content-Type-Options", "nosniff")
        headers.setdefault("X-Frame-Options", "DENY")
        headers.setdefault("Referrer-Policy", "no-referrer")
        headers.setdefault(
            "Permissions-Policy", "geolocation=(), microphone=(), camera=()"
        )
        headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        headers.setdefault("X-Permitted-Cross-Domain-Policies", "none")
        headers.setdefault("Cache-Control", "no-store")

        path = request.url.path
        is_docs = any(path.endswith(p) for p in _DOC_PATHS)
        if not is_docs:
            headers.setdefault(
                "Content-Security-Policy",
                "default-src 'none'; frame-ancestors 'none'; base-uri 'none'",
            )

        if s.hsts_enabled and (s.is_production or request.url.scheme == "https"):
            headers.setdefault(
                "Strict-Transport-Security",
                f"max-age={s.hsts_max_age}; includeSubDomains; preload",
            )
        return response
