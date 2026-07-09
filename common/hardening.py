"""One-call application hardening.

``harden_app`` applies the full cross-cutting security & resilience stack to a
FastAPI/Starlette app in the correct order, using the process-wide
:class:`SecuritySettings`. It is wired once onto the mounted parent app in
``server.py`` so every sub-application inherits the protections without any
change to their routes, services or API contracts.

Middleware execution order (outermost → innermost):

    TrustedHost  →  RateLimit  →  Auth  →  SecurityHeaders  →  app

Starlette runs middleware in reverse registration order, so we register them
innermost-first below.
"""
from __future__ import annotations

from fastapi import FastAPI
from starlette.middleware.trustedhost import TrustedHostMiddleware

from common.ratelimit import RateLimitMiddleware
from common.security.auth import AuthMiddleware
from common.security.headers import SecurityHeadersMiddleware
from common.settings import SecuritySettings, get_security_settings


def harden_app(app: FastAPI, settings: SecuritySettings | None = None) -> FastAPI:
    """Attach the production security stack to *app* and return it."""
    settings = settings or get_security_settings()

    # Innermost first.
    app.add_middleware(SecurityHeadersMiddleware, settings=settings)
    app.add_middleware(AuthMiddleware, settings=settings)
    app.add_middleware(RateLimitMiddleware, settings=settings)
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=list(settings.trusted_hosts) or ["*"],
    )
    return app
