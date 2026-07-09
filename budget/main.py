"""Application factory and ASGI entrypoint for the Budget Planner.

Run standalone with: ``uvicorn budget.main:app --reload``
(or through the suite gateway, mounted at ``/budget``).
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from budget.api.deps import shutdown_dependencies
from budget.api.v1 import api_router
from budget.core.config import Settings, get_settings
from budget.core.error_handlers import register_exception_handlers
from budget.core.logging import configure_logging, get_logger
from budget.core.middleware import RequestContextMiddleware

logger = get_logger(__name__)

_DESCRIPTION = """
Banking **Budget Planner** microservice.

Turns a customer's **income, expenses, bills and goals** into a recommended
monthly budget (50/30/20 framework), a category-level expense breakdown, a
savings percentage, actionable alerts, overspending detection and an overall
budget score/grade. All figures are computed by a deterministic, unit-tested
engine — there is no external I/O, so results are fully reproducible.
"""


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build and configure a FastAPI application instance."""
    settings = settings or get_settings()
    configure_logging(level=settings.log_level, json_logs=settings.log_json)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        logger.info(
            "Budget Planner starting",
            extra={"environment": settings.environment},
        )
        yield
        await shutdown_dependencies()
        logger.info("Budget Planner shutting down")

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
        allow_origins=settings.cors_allow_origins,
        allow_credentials=settings.cors_allow_credentials,
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
            "plan": f"{settings.api_v1_prefix}/budget/plan",
        }

    return app


app = create_app()
