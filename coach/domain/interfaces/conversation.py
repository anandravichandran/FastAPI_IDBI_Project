"""Port: conversation-history store."""
from __future__ import annotations

from abc import ABC, abstractmethod

from coach.domain.entities import ConversationTurn


class IConversationRepository(ABC):
    """Persists and retrieves coaching conversation turns.

    Shipped with an in-memory implementation; swap for Redis/Postgres in
    production without touching the service layer.
    """

    @abstractmethod
    async def append(self, turn: ConversationTurn) -> None:
        """Append a single turn to a session."""
        raise NotImplementedError

    @abstractmethod
    async def history(
        self, *, customer_id: str, session_id: str | None = None, limit: int | None = None
    ) -> list[ConversationTurn]:
        """Return turns for a customer, optionally scoped to one session.

        Results are ordered oldest-first. When ``limit`` is given, the most
        recent ``limit`` turns are returned (still oldest-first).
        """
        raise NotImplementedError

    @abstractmethod
    async def sessions(self, customer_id: str) -> list[str]:
        """Return known session ids for a customer (most recent first)."""
        raise NotImplementedError
