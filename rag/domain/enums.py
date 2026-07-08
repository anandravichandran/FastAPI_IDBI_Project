"""Enumerations for the RAG domain."""
from __future__ import annotations

from enum import Enum


class FileType(str, Enum):
    """Supported document upload types."""

    PDF = "pdf"

    @classmethod
    def from_filename(cls, filename: str) -> "FileType":
        lowered = (filename or "").lower()
        if lowered.endswith(".pdf"):
            return cls.PDF
        raise ValueError(f"Unsupported file type for '{filename}'")


class DocumentStatus(str, Enum):
    """Lifecycle state of an ingested document."""

    PENDING = "pending"
    PROCESSING = "processing"
    INDEXED = "indexed"
    FAILED = "failed"


class EmbeddingBackend(str, Enum):
    SENTENCE_TRANSFORMERS = "sentence_transformers"
    HASHING = "hashing"


class VectorBackend(str, Enum):
    CHROMADB = "chromadb"
    MEMORY = "memory"
