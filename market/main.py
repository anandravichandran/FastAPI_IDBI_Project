"""Application factory and ASGI entrypoint for the OpenBB Market Data service.

Run standalone with: ``uvicorn market.main:app --reload``
(or through the suite gateway, mounted at ``/market``).
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from market.api.deps import shutdown_dependencies
from market.api.v1 import api_router
from market.core.config import Settings, get_settings
from market.core.error_handlers import register_exception_handlers
from market.core.logging import configure_logging, get_logger
from market.core.middleware import RequestContextMiddleware

logger = get_logger(__name__)

_API_V1_PREFIX = "/api/v1"

_DESCRIPTION = """
**OpenBB Market Data** integration microservice.

Retrieves **stocks, mutual funds, ETFs, gold, indices, market news, financial
ratios and historical prices** through the OpenBB Platform and exposes them as
clean REST APIs.

Production concerns are built in:

* **Caching** - per-domain TTL + LRU in-memory cache (short TTL for quotes, long
  for ratios) with a `/cache/stats` diagnostics endpoint.
* **Retries** - exponential backoff with full jitter on transient upstream
  failures, honouring server `Retry-After`.
* **Rate limiting** - client-side token bucket protecting the provider quota,
  returning HTTP 429 + `Retry-After` when exhausted.

The OpenBB SDK is imported lazily; outside production the service transparently
falls back to a deterministic **synthetic** provider so it runs fully offline.
"""


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build and configure a FastAPI application instance."""
    settings = settings or get_settings()
    configure_logging()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        logger.info(
            "Market Data service starting",
            extra={
                "environment": settings.environment,
                "provider_backend": settings.provider_backend,
            },
        )
        yield
        await shutdown_dependencies()
        logger.info("Market Data service shutting down")

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=_DESCRIPTION,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        # SECURITY FIX: see advisor/main.py — no "*" + credentials.
        # Read defensively so both the pydantic and offline-shim Settings work.
        allow_origins=getattr(settings, "cors_allow_origins", ["*"]),
        allow_credentials=getattr(settings, "cors_allow_credentials", False),
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)
    app.include_router(api_router, prefix=_API_V1_PREFIX)

    @app.get("/", tags=["meta"], summary="Service metadata")
    async def root() -> dict[str, str]:
        return {
            "service": settings.app_name,
            "version": settings.app_version,
            "docs": "/docs",
            "health": _API_V1_PREFIX + "/health",
            "stocks": _API_V1_PREFIX + "/stocks/{symbol}/quote",
            "news": _API_V1_PREFIX + "/news",
        }

    return app


app = create_app()
