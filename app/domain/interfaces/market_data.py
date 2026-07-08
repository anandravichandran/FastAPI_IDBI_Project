"""Port: market-data provider."""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence

from app.domain.entities import MarketSnapshot


class IMarketDataProvider(ABC):
    """Retrieves live/near-live market data for a set of symbols."""

    @abstractmethod
    async def get_snapshot(self, symbols: Sequence[str]) -> MarketSnapshot:
        """Return a :class:`MarketSnapshot` for the requested symbols.

        Implementations must never raise for a partial data outage; they
        should return a degraded snapshot instead so the advisor can still
        produce deterministic guidance.
        """
        raise NotImplementedError
