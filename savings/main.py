"""Application factory and ASGI entrypoint for the Savings Optimizer.

Run standalone with: ``uvicorn savings.main:app --reload``
(or through the suite gateway, mounted at ``/savings``).
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from savings.api.deps import shutdown_dependencies
from savings.api.v1 import api_router
from savings.core.config import Settings, get_settings
from savings.core.error_handlers import register_exception_handlers
from savings.core.logging import configure_logging, get_logger
from savings.core.middleware import RequestContextMiddleware

logger = get_logger(__name__)

_DESCRIPTION = """
Banking **Savings Optimizer** microservice.

Turns a customer's **salary, monthly expenses, loans, savings and goals** into a
recommended **emergency fund**, **monthly saving**, and an actionable split
across **SIP**, **fixed deposits** and **liquid funds** — plus a full investment
allocation, goal projections, alerts and an overall **savings score/grade**.
All figures are computed by a deterministic, unit-tested engine with no external
I/O, so results are fully reproducible.
"""


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build and configure a FastAPI application instance."""
    settings = settings or get_settings()
    configure_logging(level=settings.log_level, json_logs=settings.log_json)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        logger.info(
            "Savings Optimizer starting",
            extra={"environment": settings.environment},
        )
        yield
        await shutdown_dependencies()
        logger.info("Savings Optimizer shutting down")

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
        allow_origins=["*"] if not settings.is_production else [],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)
    app.include_router(api_router, prefix=settings.api_v1_prefix)

    @app.get("/", tags=["meta"], summary="Service metadata")
    async def root() -> dict[str, str]:
        return {
            "service": settings.app_name,
            "version": settings.app_version,
            "docs": "/docs",
            "health": f"{settings.api_v1_prefix}/health",
            "optimize": f"{settings.api_v1_prefix}/savings/optimize",
        }

    return app


app = create_app()
