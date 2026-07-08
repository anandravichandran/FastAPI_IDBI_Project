"""Response DTOs with ``from_domain`` mappers (domain entity -> API model)."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from market.domain.entities import (
    FinancialRatios,
    HistoricalPrices,
    NewsArticle,
    NewsFeed,
    PricePoint,
    Quote,
)


class QuoteOut(BaseModel):
    symbol: str
    asset_class: str
    price: float
    currency: str
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

    @classmethod
    def from_domain(cls, q: Quote) -> "QuoteOut":
        return cls(
            symbol=q.symbol,
            asset_class=q.asset_class.value,
            price=q.price,
            currency=q.currency,
            name=q.name,
            change=q.change,
            change_percent=q.change_percent,
            previous_close=q.previous_close,
            open=q.open,
            day_high=q.day_high,
            day_low=q.day_low,
            volume=q.volume,
            market_cap=q.market_cap,
            exchange=q.exchange,
            as_of=q.as_of,
            source=q.source,
        )


class PricePointOut(BaseModel):
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: int | None = None

    @classmethod
    def from_domain(cls, p: PricePoint) -> "PricePointOut":
        return cls(date=p.date, open=p.open, high=p.high, low=p.low, close=p.close, volume=p.volume)


class HistoricalPricesOut(BaseModel):
    symbol: str
    asset_class: str
    interval: str
    currency: str
    count: int
    points: list[PricePointOut]
    source: str | None = None

    @classmethod
    def from_domain(cls, h: HistoricalPrices) -> "HistoricalPricesOut":
        return cls(
            symbol=h.symbol,
            asset_class=h.asset_class.value,
            interval=h.interval,
            currency=h.currency,
            count=h.count,
            points=[PricePointOut.from_domain(p) for p in h.points],
            source=h.source,
        )


class FinancialRatiosOut(BaseModel):
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

    @classmethod
    def from_domain(cls, r: FinancialRatios) -> "FinancialRatiosOut":
        return cls(**{f: getattr(r, f) for f in cls.model_fields})


class NewsArticleOut(BaseModel):
    title: str
    published_at: str
    source: str | None = None
    url: str | None = None
    summary: str | None = None
    symbols: list[str] = []

    @classmethod
    def from_domain(cls, a: NewsArticle) -> "NewsArticleOut":
        return cls(
            title=a.title,
            published_at=a.published_at,
            source=a.source,
            url=a.url,
            summary=a.summary,
            symbols=list(a.symbols),
        )


class NewsFeedOut(BaseModel):
    query: str | None = None
    provider: str | None = None
    count: int
    articles: list[NewsArticleOut]

    @classmethod
    def from_domain(cls, f: NewsFeed) -> "NewsFeedOut":
        return cls(
            query=f.query,
            provider=f.provider,
            count=f.count,
            articles=[NewsArticleOut.from_domain(a) for a in f.articles],
        )


class CacheStatsOut(BaseModel):
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    expirations: int = 0
    size: int = 0
    max_entries: int = 0
    hit_rate: float = 0.0

    @classmethod
    def from_domain(cls, stats: dict[str, Any]) -> "CacheStatsOut":
        return cls(**{k: v for k, v in stats.items() if k in cls.model_fields})


class HealthOut(BaseModel):
    status: str
    service: str
    version: str
    environment: str
    provider: str
