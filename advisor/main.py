"""FastAPI application factory and ASGI entrypoint.

Wires together configuration, structured logging, middleware, centralized
exception handling, OpenAPI metadata and the versioned API router. A lifespan
handler manages startup/shutdown of pooled resources (e.g. the DeepSeek HTTP
client).
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from advisor.api.deps import shutdown_dependencies
from advisor.api.v1 import api_router
from advisor.core.config import Settings, get_settings
from advisor.core.error_handlers import register_exception_handlers
from advisor.core.logging import configure_logging, get_logger
from advisor.core.middleware import RequestContextMiddleware

logger = get_logger(__name__)

_OPENAPI_DESCRIPTION = """
Production-grade **Investment Advisor** microservice.

Given a user's profile, risk profile, cash flow, savings, goals and current
portfolio, the service:

1. Runs a deterministic financial-planning engine.
2. Retrieves **market data** via OpenBB.
3. Retrieves relevant **financial knowledge** via RAG.
4. Sends the assembled context to **DeepSeek V3**.
5. Returns portfolio analysis, a risk score, target asset allocation, a SIP
   recommendation, an emergency-fund recommendation, diversification advice
   and a plain-language explanation.

Built with Clean Architecture and SOLID principles: API, Service, Repository
and Domain layers are strictly separated and wired via dependency injection.
"""


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings: Settings = app.state.settings
    logger.info(
        "service.startup",
        extra={"environment": settings.environment, "version": settings.app_version},
    )
    try:
        yield
    finally:
        await shutdown_dependencies()
        logger.info("service.shutdown")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(level=settings.log_level, json_logs=settings.log_json)

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=_OPENAPI_DESCRIPTION,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
        contact={"name": "FinTech Platform Team"},
        license_info={"name": "MIT"},
    )
    app.state.settings = settings

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
        }

    return app


app = create_app()
