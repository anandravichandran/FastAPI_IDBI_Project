"""Port: document catalog / metadata registry."""
from __future__ import annotations

from abc import ABC, abstractmethod

from rag.domain.entities import Document


class IDocumentRegistry(ABC):
    """Tracks ingested-document metadata and lifecycle status.

    Kept separate from the vector store so the catalog can live in a relational
    database while embeddings live in a vector database. Shipped with an
    in-memory implementation.
    """

    @abstractmethod
    def save(self, document: Document) -> None:
        """Insert or update a document record."""
        raise NotImplementedError

    @abstractmethod
    def get(self, document_id: str) -> Document | None:
        """Return a document record, or ``None`` if unknown."""
        raise NotImplementedError

    @abstractmethod
    def list(self) -> list[Document]:
        """Return all document records, most recently created first."""
        raise NotImplementedError

    @abstractmethod
    def delete(self, document_id: str) -> bool:
        """Remove a document record. Returns True if it existed."""
        raise NotImplementedError
