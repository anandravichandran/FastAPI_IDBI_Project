"""Authentication for the mounted suite.

Banking APIs must never be anonymous. This middleware enforces authentication
globally on the parent ASGI app (covering every mounted sub-application) while
exempting only unauthenticated-by-design surfaces: liveness/readiness probes,
OpenAPI docs and the suite landing/redirect routes.

Two credential types are accepted (either satisfies the gate):

* **API key** — a shared secret sent in the ``X-API-Key`` header, compared in
  constant time against the configured allowlist.
* **JWT bearer** — ``Authorization: Bearer <token>`` verified with PyJWT using
  the configured secret, algorithms, and optional audience/issuer claims.

Credentials come exclusively from the environment (never hard-coded). The
middleware fails closed: if auth is enabled but misconfigured, requests are
rejected rather than silently allowed.
"""
from __future__ import annotations

import hmac
from collections.abc import Iterable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp

from common.settings import SecuritySettings, get_security_settings

try:  # PyJWT is optional at import time; required only when JWT auth is used.
    import jwt as _jwt

    _HAS_JWT = True
except Exception:  # pragma: no cover - environment dependent
    _jwt = None  # type: ignore[assignment]
    _HAS_JWT = False


_EXEMPT_EXACT = {"/", "/health", "/healthz", "/livez", "/readyz", "/openapi.json", "/docs", "/redoc", "/favicon.ico"}
_EXEMPT_SUFFIXES = (
    "/health",
    "/healthz",
    "/livez",
    "/readyz",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/docs/oauth2-redirect",
)
_SUBAPP_ROOTS = {"/advisor", "/coach", "/budget", "/savings", "/rag", "/market"}


def _is_exempt(path: str) -> bool:
    """Public, unauthenticated-by-design routes."""
    if path in _EXEMPT_EXACT or path in _SUBAPP_ROOTS:
        return True
    return any(path.endswith(suffix) for suffix in _EXEMPT_SUFFIXES)


def _unauthorized(message: str) -> JSONResponse:
    return JSONResponse(
        status_code=401,
        content={"error": {"code": "unauthorized", "message": message}},
        headers={"WWW-Authenticate": "Bearer"},
    )


def _api_key_valid(candidate: str, allowed: Iterable[str]) -> bool:
    # Constant-time comparison against every configured key to avoid leaking
    # key length / prefix via timing.
    ok = False
    for key in allowed:
        if hmac.compare_digest(candidate, key):
            ok = True
    return ok


def _verify_jwt(token: str, settings: SecuritySettings) -> bool:
    if not (_HAS_JWT and settings.jwt_secret):
        return False
    options = {"verify_aud": settings.jwt_audience is not None}
    try:
        _jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=list(settings.jwt_algorithms),
            audience=settings.jwt_audience,
            issuer=settings.jwt_issuer,
            options=options,
        )
        return True
    except Exception:  # noqa: BLE001 - any verification failure => reject
        return False


class AuthMiddleware(BaseHTTPMiddleware):
    """Fail-closed authentication gate applied to the whole suite."""

    def __init__(self, app: ASGIApp, settings: SecuritySettings | None = None) -> None:
        super().__init__(app)
        self._settings = settings or get_security_settings()

    async def dispatch(self, request: Request, call_next):
        settings = self._settings
        if not settings.auth_enabled or _is_exempt(request.url.path):
            return await call_next(request)

        # Preflight requests carry no credentials by design.
        if request.method == "OPTIONS":
            return await call_next(request)

        api_key = request.headers.get(settings.api_key_header)
        if api_key and settings.api_keys and _api_key_valid(api_key, settings.api_keys):
            return await call_next(request)

        authz = request.headers.get("Authorization", "")
        if authz.lower().startswith("bearer "):
            token = authz.split(" ", 1)[1].strip()
            if _verify_jwt(token, settings):
                return await call_next(request)

        return _unauthorized("Valid API key or bearer token required.")
