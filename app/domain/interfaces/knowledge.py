"""Port: financial-knowledge retrieval (RAG)."""
from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.entities import KnowledgeSnippet


class IKnowledgeRepository(ABC):
    """Retrieves relevant financial knowledge for a natural-language query."""

    @abstractmethod
    async def retrieve(self, query: str, *, top_k: int) -> list[KnowledgeSnippet]:
        """Return up to ``top_k`` knowledge snippets ranked by relevance."""
        raise NotImplementedError
