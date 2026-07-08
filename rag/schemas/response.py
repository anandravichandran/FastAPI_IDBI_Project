"""Response DTOs for the RAG API, with mappers from domain objects."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from rag.domain.entities import (
    Document,
    RagContext,
    RetrievalResult,
    RetrievedChunk,
)


class DocumentOut(BaseModel):
    document_id: str
    filename: str
    status: str
    page_count: int
    chunk_count: int
    char_count: int
    created_at: str
    error: str | None = None

    @classmethod
    def from_domain(cls, d: Document) -> "DocumentOut":
        return cls(
            document_id=d.document_id,
            filename=d.filename,
            status=d.status.value,
            page_count=d.page_count,
            chunk_count=d.chunk_count,
            char_count=d.char_count,
            created_at=d.created_at,
            error=d.error,
        )


class IngestResponse(BaseModel):
    document: DocumentOut
    message: str = "Document ingested and indexed."

    @classmethod
    def from_domain(cls, d: Document) -> "IngestResponse":
        return cls(document=DocumentOut.from_domain(d))


class DocumentListResponse(BaseModel):
    documents: list[DocumentOut]
    count: int

    @classmethod
    def from_domain(cls, docs: list[Document]) -> "DocumentListResponse":
        items = [DocumentOut.from_domain(d) for d in docs]
        return cls(documents=items, count=len(items))


class ChunkOut(BaseModel):
    chunk_id: str
    document_id: str
    filename: str
    ordinal: int
    text: str
    score: float
    metadata: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_domain(cls, c: RetrievedChunk) -> "ChunkOut":
        return cls(
            chunk_id=c.chunk_id,
            document_id=c.document_id,
            filename=c.filename,
            ordinal=c.ordinal,
            text=c.text,
            score=c.score,
            metadata=dict(c.metadata),
        )


class MessageOut(BaseModel):
    role: str
    content: str


class QueryResponse(BaseModel):
    """Retrieved chunks plus — optionally — the grounded context and a
    DeepSeek-ready ``messages`` payload."""

    query: str
    chunks: list[ChunkOut]
    count: int
    embedding_backend: str
    vector_backend: str
    context: str | None = None
    messages: list[MessageOut] | None = None
    approx_tokens: int | None = None
    truncated: bool | None = None

    @classmethod
    def from_domain(
        cls, result: RetrievalResult, context: RagContext | None = None
    ) -> "QueryResponse":
        payload = cls(
            query=result.query,
            chunks=[ChunkOut.from_domain(c) for c in result.chunks],
            count=result.count,
            embedding_backend=result.embedding_backend,
            vector_backend=result.vector_backend,
        )
        if context is not None:
            payload.context = context.context
            payload.messages = [
                MessageOut(role=m.role, content=m.content) for m in context.messages
            ]
            payload.approx_tokens = context.approx_tokens
            payload.truncated = context.truncated
        return payload


class ContextResponse(BaseModel):
    """Just the grounded context + DeepSeek-ready payload for a query."""

    query: str
    context: str
    messages: list[MessageOut]
    chunks: list[ChunkOut]
    approx_tokens: int
    truncated: bool

    @classmethod
    def from_domain(cls, ctx: RagContext) -> "ContextResponse":
        return cls(
            query=ctx.query,
            context=ctx.context,
            messages=[MessageOut(role=m.role, content=m.content) for m in ctx.messages],
            chunks=[ChunkOut.from_domain(c) for c in ctx.chunks],
            approx_tokens=ctx.approx_tokens,
            truncated=ctx.truncated,
        )


class StatsResponse(BaseModel):
    documents: int
    chunks: int
    embedding_model: str
    embedding_dim: int
    vector_store: str


class DeleteResponse(BaseModel):
    document_id: str
    chunks_removed: int
    message: str = "Document deleted."
