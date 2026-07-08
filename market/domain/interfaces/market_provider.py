"""Market-data provider port."""
from __future__ import annotations

from abc import ABC, abstractmethod

from market.domain.entities import FinancialRatios, HistoricalPrices, NewsFeed, Quote
from market.domain.enums import AssetClass


class IMarketDataProvider(ABC):
    """Abstraction over a concrete market-data backend (OpenBB, synthetic, ...)."""

    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def get_quote(self, symbol: str, *, asset_class: AssetClass) -> Quote: ...

    @abstractmethod
    def get_historical(
        self,
        symbol: str,
        *,
        asset_class: AssetClass,
        interval: str,
        start: str | None = None,
        end: str | None = None,
        limit: int | None = None,
    ) -> HistoricalPrices: ...

    @abstractmethod
    def get_ratios(self, symbol: str) -> FinancialRatios: ...

    @abstractmethod
    def get_news(
        self,
        *,
        query: str | None = None,
        symbols: list[str] | None = None,
        limit: int = 20,
    ) -> NewsFeed: ...
