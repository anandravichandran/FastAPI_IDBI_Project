"""Framework-free domain entities and value objects for the RAG service.

These carry no Pydantic / FastAPI / ChromaDB dependencies so the core logic can
be unit-tested in isolation and the adapters can be swapped freely.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from rag.domain.enums import DocumentStatus

# A dense embedding vector.
Vector = list[float]


@dataclass(frozen=True, slots=True)
class ParsedDocument:
    """Raw text extracted from an uploaded file, before chunking."""

    document_id: str
    filename: str
    text: str
    page_count: int

    @property
    def char_count(self) -> int:
        return len(self.text)


@dataclass(frozen=True, slots=True)
class DocumentChunk:
    """A single retrievable unit of a document."""

    chunk_id: str
    document_id: str
    filename: str
    ordinal: int
    text: str
    start_char: int
    end_char: int
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @property
    def char_count(self) -> int:
        return len(self.text)

    def as_metadata(self) -> dict[str, Any]:
        """Flat, primitive-only metadata suitable for a vector-store record."""
        base: dict[str, Any] = {
            "document_id": self.document_id,
            "filename": self.filename,
            "ordinal": self.ordinal,
            "start_char": self.start_char,
            "end_char": self.end_char,
        }
        for key, value in self.metadata.items():
            if isinstance(value, (str, int, float, bool)) or value is None:
                base[key] = value
        return base


@dataclass(frozen=True, slots=True)
class Document:
    """Catalog record describing an ingested (chunked + indexed) document."""

    document_id: str
    filename: str
    status: DocumentStatus
    page_count: int
    chunk_count: int
    char_count: int
    created_at: str
    error: str | None = None


@dataclass(frozen=True, slots=True)
class RetrievedChunk:
    """A chunk returned from a similarity search, with its relevance score."""

    chunk_id: str
    document_id: str
    filename: str
    ordinal: int
    text: str
    score: float
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RetrievalResult:
    """The ranked chunks retrieved for a query."""

    query: str
    chunks: tuple[RetrievedChunk, ...]
    embedding_backend: str
    vector_backend: str

    @property
    def count(self) -> int:
        return len(self.chunks)


@dataclass(frozen=True, slots=True)
class PromptMessage:
    """An OpenAI/DeepSeek-compatible chat message."""

    role: str
    content: str


@dataclass(frozen=True, slots=True)
class RagContext:
    """Grounded context assembled from retrieved chunks, ready for DeepSeek.

    ``messages`` is a drop-in ``messages=[...]`` payload for an OpenAI-compatible
    chat completion (which DeepSeek V3 implements).
    """

    query: str
    context: str
    chunks: tuple[RetrievedChunk, ...]
    messages: tuple[PromptMessage, ...]
    approx_tokens: int
    truncated: bool
