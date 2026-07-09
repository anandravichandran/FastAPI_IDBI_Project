"""Application factory and ASGI entrypoint.

Run with: ``uvicorn coach.main:app --reload``
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from coach.api.deps import shutdown_dependencies
from coach.api.v1 import api_router
from coach.core.config import Settings, get_settings
from coach.core.error_handlers import register_exception_handlers
from coach.core.logging import configure_logging, get_logger
from coach.core.middleware import RequestContextMiddleware

logger = get_logger(__name__)

_DESCRIPTION = """
Enterprise **Financial Coach** microservice.

Answers natural-language money questions — *Can I buy a car? Should I increase
my SIP? Can I afford a home loan? Am I overspending? How can I improve
savings?* — by combining a deterministic financial-planning engine with the
customer's transactions, budget, savings and goals, **RAG**-retrieved
knowledge, and a **DeepSeek V3** narrative. Responses are shaped for a mobile
avatar client.
"""


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build and configure a FastAPI application instance."""
    settings = settings or get_settings()
    configure_logging(level=settings.log_level, json_logs=settings.log_json)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        logger.info(
            "Financial Coach starting",
            extra={"environment": settings.environment, "llm_enabled": settings.llm_enabled},
        )
        yield
        await shutdown_dependencies()
        logger.info("Financial Coach shutting down")

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
        }

    return app


app = create_app()
