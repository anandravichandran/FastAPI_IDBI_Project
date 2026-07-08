"""End-to-end tests for the RagService pipeline (offline backends)."""
from __future__ import annotations

import pytest

from rag.core.exceptions import (
    DocumentNotFoundError,
    DocumentProcessingError,
    DomainValidationError,
)
from rag.domain.enums import DocumentStatus


def test_ingest_indexes_document(service, sample_text) -> None:
    doc = service.ingest_pdf(filename="finance.pdf", data=sample_text.encode())
    assert doc.status is DocumentStatus.INDEXED
    assert doc.chunk_count >= 1
    assert doc.filename == "finance.pdf"

    docs = service.list_documents()
    assert len(docs) == 1
    assert docs[0].document_id == doc.document_id


def test_ingest_empty_raises(service) -> None:
    with pytest.raises(DocumentProcessingError):
        service.ingest_pdf(filename="empty.pdf", data=b"")


def test_retrieve_returns_relevant_chunk(service, sample_text) -> None:
    service.ingest_pdf(filename="finance.pdf", data=sample_text.encode())
    result = service.retrieve("How much should I keep in an emergency fund?", top_k=2)
    assert result.count >= 1
    top = result.chunks[0]
    assert "emergency fund" in top.text.lower()
    assert 0.0 <= top.score <= 1.0


def test_empty_query_raises(service) -> None:
    with pytest.raises(DomainValidationError):
        service.retrieve("   ")


def test_build_context_produces_deepseek_messages(service, sample_text) -> None:
    service.ingest_pdf(filename="finance.pdf", data=sample_text.encode())
    ctx = service.build_context("Tell me about SIPs", top_k=2)
    assert ctx.context
    assert len(ctx.messages) == 2
    assert ctx.messages[0].role == "system"
    assert ctx.messages[1].role == "user"
    assert "Question: Tell me about SIPs" in ctx.messages[1].content
    assert ctx.approx_tokens > 0


def test_delete_document(service, sample_text) -> None:
    doc = service.ingest_pdf(filename="finance.pdf", data=sample_text.encode())
    removed = service.delete_document(doc.document_id)
    assert removed >= 1
    assert service.list_documents() == []
    with pytest.raises(DocumentNotFoundError):
        service.delete_document(doc.document_id)


def test_stats_reports_backends(service, sample_text) -> None:
    service.ingest_pdf(filename="finance.pdf", data=sample_text.encode())
    stats = service.stats()
    assert stats["documents"] == 1
    assert stats["chunks"] >= 1
    assert stats["vector_store"] == "InMemoryVectorStore"
