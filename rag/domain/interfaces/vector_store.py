"""Port: vector store for chunk embeddings."""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence

from rag.domain.entities import DocumentChunk, RetrievedChunk, Vector


class IVectorStore(ABC):
    """Persists chunk embeddings and answers similarity queries.

    Shipped with a ChromaDB adapter and an in-memory cosine adapter. The
    service layer depends only on this abstraction.
    """

    @abstractmethod
    def add(self, chunks: Sequence[DocumentChunk], embeddings: Sequence[Vector]) -> None:
        """Upsert chunks and their embeddings. ``len(chunks) == len(embeddings)``."""
        raise NotImplementedError

    @abstractmethod
    def query(
        self,
        embedding: Vector,
        *,
        top_k: int,
        document_ids: Sequence[str] | None = None,
    ) -> list[RetrievedChunk]:
        """Return up to ``top_k`` chunks most similar to ``embedding``.

        Results are ordered most-relevant first, each carrying a cosine
        similarity ``score`` in ``[0, 1]``. When ``document_ids`` is given, the
        search is restricted to those documents.
        """
        raise NotImplementedError

    @abstractmethod
    def delete_document(self, document_id: str) -> int:
        """Remove all chunks for a document. Returns the number deleted."""
        raise NotImplementedError

    @abstractmethod
    def count(self) -> int:
        """Total number of stored chunks."""
        raise NotImplementedError
