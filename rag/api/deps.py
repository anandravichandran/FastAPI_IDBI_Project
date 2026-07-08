"""Composition root and FastAPI dependency providers.

Builds the concrete adapters and wires them into :class:`RagService`, selecting
backends from configuration. Outside production, if a heavy backend
(Sentence Transformers / ChromaDB) is not installed, it degrades gracefully to
the dependency-light backends and logs a warning; in production a missing
required backend raises a :class:`ConfigurationError`.

The built service is cached per-settings so the (potentially expensive)
embedding model and vector-store client are created once per process.
"""
from __future__ import annotations

from functools import lru_cache

from fastapi import Depends

from rag.core.config import Settings, get_settings
from rag.core.exceptions import ConfigurationError
from rag.core.logging import get_logger
from rag.domain.enums import EmbeddingBackend, VectorBackend
from rag.domain.interfaces import IEmbedder, IVectorStore
from rag.repositories import (
    ChromaVectorStore,
    HashingEmbedder,
    InMemoryDocumentRegistry,
    InMemoryVectorStore,
    PdfDocumentParser,
    SentenceTransformerEmbedder,
)
from rag.services import RagService, TextChunker

logger = get_logger(__name__)


def _build_embedder(settings: Settings) -> IEmbedder:
    backend = settings.embedding_backend.lower()
    if backend == EmbeddingBackend.HASHING.value:
        return HashingEmbedder(dimension=settings.hashing_embedding_dim)

    if backend == EmbeddingBackend.SENTENCE_TRANSFORMERS.value:
        try:
            import sentence_transformers  # noqa: F401  (probe availability)
        except ImportError as exc:
            if settings.allow_backend_fallback:
                logger.warning(
                    "sentence-transformers unavailable; falling back to hashing "
                    "embedder (non-production)."
                )
                return HashingEmbedder(dimension=settings.hashing_embedding_dim)
            raise ConfigurationError(
                "sentence-transformers is required in production but not installed."
            ) from exc
        return SentenceTransformerEmbedder(
            settings.embedding_model, batch_size=settings.embedding_batch_size
        )

    raise ConfigurationError(f"Unknown embedding_backend: {settings.embedding_backend}")


def _build_vector_store(settings: Settings) -> IVectorStore:
    backend = settings.vector_backend.lower()
    if backend == VectorBackend.MEMORY.value:
        return InMemoryVectorStore()

    if backend == VectorBackend.CHROMADB.value:
        try:
            import chromadb  # noqa: F401  (probe availability)
        except ImportError as exc:
            if settings.allow_backend_fallback:
                logger.warning(
                    "chromadb unavailable; falling back to in-memory vector store "
                    "(non-production)."
                )
                return InMemoryVectorStore()
            raise ConfigurationError(
                "chromadb is required in production but not installed."
            ) from exc
        return ChromaVectorStore(
            persist_dir=settings.chroma_persist_dir,
            collection_name=settings.chroma_collection,
        )

    raise ConfigurationError(f"Unknown vector_backend: {settings.vector_backend}")


@lru_cache
def _build_service(settings: Settings) -> RagService:
    embedder = _build_embedder(settings)
    vector_store = _build_vector_store(settings)
    chunker = TextChunker(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        min_chunk_chars=settings.min_chunk_chars,
    )
    logger.info(
        "RAG service composed",
        extra={
            "embedder": embedder.name,
            "vector_store": type(vector_store).__name__,
        },
    )
    return RagService(
        parser=PdfDocumentParser(),
        chunker=chunker,
        embedder=embedder,
        vector_store=vector_store,
        registry=InMemoryDocumentRegistry(),
        settings=settings,
    )


def get_service(settings: Settings = Depends(get_settings)) -> RagService:
    """FastAPI dependency returning the shared RagService instance."""
    return _build_service(settings)


async def shutdown_dependencies() -> None:
    """Release cached singletons on application shutdown."""
    _build_service.cache_clear()
