"""RAG service application factory.

Builds a self-contained FastAPI app that can run standalone (``uvicorn
rag.main:app``) or be mounted by the Financial Suite gateway at ``/rag``.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from rag.api.deps import shutdown_dependencies
from rag.api.v1 import api_router
from rag.core.config import Settings, get_settings
from rag.core.error_handlers import register_exception_handlers
from rag.core.logging import configure_logging, get_logger
from rag.core.middleware import RequestContextMiddleware

logger = get_logger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(level=settings.log_level, json_logs=settings.log_json)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        logger.info(
            "Starting RAG service",
            extra={"version": settings.app_version, "environment": settings.environment},
        )
        yield
        await shutdown_dependencies()
        logger.info("RAG service stopped")

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "Production-grade Retrieval-Augmented Generation service: upload PDFs, "
            "chunk, embed (Sentence Transformers), store vectors (ChromaDB), "
            "retrieve relevant chunks and return grounded context for DeepSeek."
        ),
        lifespan=lifespan,
    )

    app.add_middleware(RequestContextMiddleware)
    if not settings.is_production:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_methods=["*"],
            allow_headers=["*"],
        )

    register_exception_handlers(app)
    app.include_router(api_router, prefix=settings.api_v1_prefix)

    @app.get("/", tags=["meta"], summary="Service metadata")
    async def root() -> dict[str, object]:
        return {
            "service": settings.app_name,
            "version": settings.app_version,
            "docs": "/docs",
            "endpoints": {
                "upload": f"POST {settings.api_v1_prefix}/documents",
                "list": f"GET {settings.api_v1_prefix}/documents",
                "stats": f"GET {settings.api_v1_prefix}/documents/stats",
                "delete": f"DELETE {settings.api_v1_prefix}/documents/id",
                "query": f"POST {settings.api_v1_prefix}/rag/query",
                "context": f"POST {settings.api_v1_prefix}/rag/context",
                "health": f"GET {settings.api_v1_prefix}/health",
            },
        }

    return app


app = create_app()
