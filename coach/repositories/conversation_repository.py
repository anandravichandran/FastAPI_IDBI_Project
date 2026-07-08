"""In-memory conversation-history repository.

Implements :class:`IConversationRepository` with a bounded per-customer ring
of turns. Thread-safe for the single-process async server via an asyncio lock.
Swap for Redis/Postgres in production without touching callers.
"""
from __future__ import annotations

import asyncio
from collections import defaultdict, deque

from coach.domain.entities import ConversationTurn
from coach.domain.interfaces.conversation import IConversationRepository


class InMemoryConversationRepository(IConversationRepository):
    def __init__(self, max_turns_per_customer: int = 200) -> None:
        self._max = max_turns_per_customer
        self._store: dict[str, deque[ConversationTurn]] = defaultdict(
            lambda: deque(maxlen=self._max)
        )
        self._lock = asyncio.Lock()

    async def append(self, turn: ConversationTurn) -> None:
        async with self._lock:
            self._store[turn.customer_id].append(turn)

    async def history(
        self, *, customer_id: str, session_id: str | None = None, limit: int | None = None
    ) -> list[ConversationTurn]:
        async with self._lock:
            turns = list(self._store.get(customer_id, ()))
        if session_id is not None:
            turns = [t for t in turns if t.session_id == session_id]
        if limit is not None and limit >= 0:
            turns = turns[-limit:]
        return turns

    async def sessions(self, customer_id: str) -> list[str]:
        async with self._lock:
            turns = list(self._store.get(customer_id, ()))
        ordered: list[str] = []
        seen: set[str] = set()
        for turn in reversed(turns):  # most recent first
            if turn.session_id not in seen:
                seen.add(turn.session_id)
                ordered.append(turn.session_id)
        return ordered
