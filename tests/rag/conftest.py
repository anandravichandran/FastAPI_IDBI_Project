"""Shared fixtures for RAG service tests.

Tests force the dependency-light backends (hashing embedder + in-memory vector
store) so the whole pipeline runs deterministically without Sentence
Transformers, ChromaDB or a real PDF.
"""
from __future__ import annotations

import pytest

from rag.core.config import Settings
from rag.domain.entities import ParsedDocument
from rag.domain.interfaces import IDocumentParser
from rag.repositories import (
    HashingEmbedder,
    InMemoryDocumentRegistry,
    InMemoryVectorStore,
)
from rag.services import RagService, TextChunker


class FakeTextParser(IDocumentParser):
    """Parser that treats uploaded bytes as UTF-8 text (no pypdf needed)."""

    def parse(self, *, document_id: str, filename: str, data: bytes) -> ParsedDocument:
        text = data.decode("utf-8", errors="ignore")
        return ParsedDocument(
            document_id=document_id, filename=filename, text=text, page_count=1
        )


@pytest.fixture
def settings() -> Settings:
    return Settings(
        environment="local",
        embedding_backend="hashing",
        vector_backend="memory",
        chunk_size=200,
        chunk_overlap=40,
        min_chunk_chars=20,
        default_top_k=3,
        max_context_chars=1000,
    )


@pytest.fixture
def service(settings: Settings) -> RagService:
    return RagService(
        parser=FakeTextParser(),
        chunker=TextChunker(
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
            min_chunk_chars=settings.min_chunk_chars,
        ),
        embedder=HashingEmbedder(dimension=settings.hashing_embedding_dim),
        vector_store=InMemoryVectorStore(),
        registry=InMemoryDocumentRegistry(),
        settings=settings,
    )


@pytest.fixture
def sample_text() -> str:
    return (
        "An emergency fund is money set aside to cover unexpected expenses. "
        "A common rule of thumb is to save three to six months of essential "
        "living costs in a liquid account.\n\n"
        "Systematic Investment Plans, or SIPs, let you invest a fixed amount "
        "in mutual funds every month. SIPs encourage discipline and average "
        "out market volatility over time.\n\n"
        "A fixed deposit is a low-risk instrument where money is locked for a "
        "fixed term at a guaranteed interest rate, suitable for capital "
        "preservation and short-term goals."
    )

from rag.api import deps as _rag_deps  # noqa: E402
from rag.core.config import get_settings as _get_settings  # noqa: E402


@pytest.fixture(autouse=True)
def _isolate_rag_storage(tmp_path, monkeypatch):
    """Guarantee every RAG test runs in complete isolation.

    * Forces the dependency-light backends (hashing + in-memory) so tests
      never open ChromaDB or the persistent ./.chroma database.
    * Points any Chroma path at an isolated tmp_path (defense in depth).
    * Clears the process-wide settings and service caches before AND after
      each test, so no singleton state leaks between tests or across runs,
      ordering, or parallel workers.
    """
    monkeypatch.setenv("ENVIRONMENT", "local")
    monkeypatch.setenv("EMBEDDING_BACKEND", "hashing")
    monkeypatch.setenv("VECTOR_BACKEND", "memory")
    monkeypatch.setenv("CHROMA_PERSIST_DIR", str(tmp_path / "chroma"))
    _get_settings.cache_clear()
    _rag_deps._build_service.cache_clear()
    yield
    _rag_deps._build_service.cache_clear()
    _get_settings.cache_clear()
