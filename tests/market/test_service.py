"""Tests for MarketService orchestration (cache-aside + rate limit + retry)."""
from __future__ import annotations

import pytest

from market.core.config import Settings
from market.core.exceptions import SymbolNotFoundError, UpstreamUnavailableError
from market.domain.entities import (
    FinancialRatios,
    HistoricalPrices,
    NewsFeed,
    Quote,
)
from market.domain.enums import AssetClass
from market.repositories import SyntheticMarketDataProvider, TTLCache
from market.repositories.retry import RetryPolicy
from market.services import MarketService


def test_get_stock_returns_quote(service):
    quote = service.get_stock("AAPL")
    assert isinstance(quote, Quote)
    assert quote.symbol == "AAPL"
    assert quote.asset_class is AssetClass.STOCK
    assert quote.price > 0


def test_results_are_deterministic(service):
    assert service.get_stock("AAPL").price == service.get_stock("AAPL").price


def test_cache_hit_skips_provider(settings, cache):
    class CountingProvider(SyntheticMarketDataProvider):
        def __init__(self):
            super().__init__()
            self.calls = 0

        def get_quote(self, symbol, *, asset_class):
            self.calls += 1
            return super().get_quote(symbol, asset_class=asset_class)

    provider = CountingProvider()
    svc = MarketService(
        provider=provider, cache=cache, rate_limiter=None, settings=settings
    )
    svc.get_stock("MSFT")
    svc.get_stock("MSFT")
    assert provider.calls == 1  # second call served from cache
    assert svc.cache_stats()["hits"] >= 1


def test_all_asset_classes(service):
    assert service.get_mutual_fund("VFIAX").asset_class is AssetClass.MUTUAL_FUND
    assert service.get_etf("SPY").asset_class is AssetClass.ETF
    assert service.get_gold().asset_class is AssetClass.GOLD
    assert service.get_index("^GSPC").asset_class is AssetClass.INDEX


def test_historical_and_ratios_and_news(service):
    hist = service.get_historical("AAPL", asset_class=AssetClass.STOCK, limit=30)
    assert isinstance(hist, HistoricalPrices)
    assert hist.count == 30
    ratios = service.get_ratios("AAPL")
    assert isinstance(ratios, FinancialRatios)
    assert ratios.pe_ratio is not None
    news = service.get_news(symbols=["AAPL"], limit=5)
    assert isinstance(news, NewsFeed)
    assert news.count == 5


def test_unknown_symbol_raises(service):
    with pytest.raises(SymbolNotFoundError):
        service.get_stock("UNKNOWN")


def test_retry_recovers_from_transient_error(settings, cache):
    class FlakyProvider(SyntheticMarketDataProvider):
        def __init__(self):
            super().__init__()
            self.calls = 0

        def get_quote(self, symbol, *, asset_class):
            self.calls += 1
            if self.calls < 2:
                raise UpstreamUnavailableError("temporary blip")
            return super().get_quote(symbol, asset_class=asset_class)

    provider = FlakyProvider()
    svc = MarketService(
        provider=provider,
        cache=cache,
        rate_limiter=None,
        settings=settings,
        retry_policy=RetryPolicy(
            max_attempts=3, base_delay=0.0, max_delay=0.0, jitter=0.0
        ),
    )
    quote = svc.get_stock("AAPL")
    assert quote.symbol == "AAPL"
    assert provider.calls == 2
