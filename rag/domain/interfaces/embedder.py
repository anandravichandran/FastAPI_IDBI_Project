"""Port: text embedding model."""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence

from rag.domain.entities import Vector


class IEmbedder(ABC):
    """Turns text into dense vectors.

    The production adapter wraps Sentence Transformers; a dependency-light
    hashing adapter is provided for tests / air-gapped environments. Query and
    document embeddings are separated so asymmetric models can be supported.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable identifier of the underlying model."""
        raise NotImplementedError

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Dimensionality of the produced vectors."""
        raise NotImplementedError

    @abstractmethod
    def embed_documents(self, texts: Sequence[str]) -> list[Vector]:
        """Embed a batch of document chunks (order-preserving)."""
        raise NotImplementedError

    @abstractmethod
    def embed_query(self, text: str) -> Vector:
        """Embed a single search query."""
        raise NotImplementedError
