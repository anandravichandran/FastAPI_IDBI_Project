"""Framework-agnostic domain entities and value objects.

These dataclasses are the internal currency of the domain and service
layers. They are intentionally decoupled from Pydantic / FastAPI so that
business logic never depends on transport or serialization concerns
(Dependency Inversion / Clean Architecture).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.domain.enums import AssetClass


@dataclass(frozen=True, slots=True)
class MarketQuote:
    """A point-in-time quote for a single instrument."""

    symbol: str
    price: float | None = None
    change_percent_1d: float | None = None
    change_percent_1y: float | None = None
    currency: str = "USD"
    name: str | None = None


@dataclass(frozen=True, slots=True)
class MarketSnapshot:
    """Aggregated market data returned by a market-data provider."""

    quotes: list[MarketQuote] = field(default_factory=list)
    source: str = "unknown"
    as_of: str | None = None
    degraded: bool = False

    def quote_for(self, symbol: str) -> MarketQuote | None:
        for quote in self.quotes:
            if quote.symbol.upper() == symbol.upper():
                return quote
        return None


@dataclass(frozen=True, slots=True)
class KnowledgeSnippet:
    """A retrieved chunk of financial knowledge (RAG result)."""

    id: str
    title: str
    content: str
    score: float
    source: str = "internal-kb"


@dataclass(frozen=True, slots=True)
class LLMMessage:
    role: str
    content: str


@dataclass(frozen=True, slots=True)
class LLMResult:
    """Raw completion returned by the language model."""

    content: str
    model: str
    finish_reason: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


@dataclass(frozen=True, slots=True)
class AllocationSlice:
    asset_class: AssetClass
    value: float

    @property
    def as_tuple(self) -> tuple[AssetClass, float]:
        return self.asset_class, self.value
