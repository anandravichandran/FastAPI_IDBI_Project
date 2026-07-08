"""Immutable, framework-free domain entities."""
from __future__ import annotations

from dataclasses import dataclass, field

from market.domain.enums import AssetClass


@dataclass(frozen=True, slots=True)
class Quote:
    symbol: str
    asset_class: AssetClass
    price: float
    currency: str = "USD"
    name: str | None = None
    change: float | None = None
    change_percent: float | None = None
    previous_close: float | None = None
    open: float | None = None
    day_high: float | None = None
    day_low: float | None = None
    volume: int | None = None
    market_cap: float | None = None
    exchange: str | None = None
    as_of: str | None = None
    source: str | None = None


@dataclass(frozen=True, slots=True)
class PricePoint:
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: int | None = None


@dataclass(frozen=True, slots=True)
class HistoricalPrices:
    symbol: str
    asset_class: AssetClass
    interval: str
    currency: str = "USD"
    points: tuple[PricePoint, ...] = field(default_factory=tuple)
    source: str | None = None

    @property
    def count(self) -> int:
        return len(self.points)


@dataclass(frozen=True, slots=True)
class FinancialRatios:
    symbol: str
    as_of: str | None = None
    currency: str | None = None
    pe_ratio: float | None = None
    forward_pe: float | None = None
    peg_ratio: float | None = None
    pb_ratio: float | None = None
    ps_ratio: float | None = None
    ev_to_ebitda: float | None = None
    eps: float | None = None
    dividend_yield: float | None = None
    payout_ratio: float | None = None
    roe: float | None = None
    roa: float | None = None
    gross_margin: float | None = None
    net_margin: float | None = None
    current_ratio: float | None = None
    quick_ratio: float | None = None
    debt_to_equity: float | None = None
    interest_coverage: float | None = None
    beta: float | None = None
    source: str | None = None


@dataclass(frozen=True, slots=True)
class NewsArticle:
    title: str
    published_at: str
    source: str | None = None
    url: str | None = None
    summary: str | None = None
    symbols: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class NewsFeed:
    articles: tuple[NewsArticle, ...] = field(default_factory=tuple)
    query: str | None = None
    provider: str | None = None

    @property
    def count(self) -> int:
        return len(self.articles)
