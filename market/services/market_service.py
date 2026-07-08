"""MarketService: the application's orchestration layer.

Every read follows the same production-grade pipeline:

    cache-aside lookup -> client-side rate limit -> retry-with-backoff around
    the provider call -> populate cache -> return the domain entity.

The service is provider-agnostic (depends only on the ``IMarketDataProvider``
and ``ICache`` ports) and pushes all cross-cutting reliability concerns out of
the HTTP layer.
"""
from __future__ import annotations

from typing import Any, Callable

from market.core.config import Settings
from market.core.logging import get_logger
from market.domain.entities import FinancialRatios, HistoricalPrices, NewsFeed, Quote
from market.domain.enums import AssetClass
from market.domain.interfaces.cache import ICache
from market.domain.interfaces.market_provider import IMarketDataProvider
from market.repositories.rate_limiter import TokenBucketRateLimiter
from market.repositories.retry import RetryPolicy, with_retries

logger = get_logger(__name__)

_GOLD_DEFAULT = "XAUUSD"


class MarketService:
    def __init__(
        self,
        *,
        provider: IMarketDataProvider,
        cache: ICache | None,
        rate_limiter: TokenBucketRateLimiter | None,
        settings: Settings,
        retry_policy: RetryPolicy | None = None,
    ) -> None:
        self._provider = provider
        self._cache = cache
        self._rate_limiter = rate_limiter
        self._settings = settings
        self._retry_policy = retry_policy or RetryPolicy(
            max_attempts=settings.retry_max_attempts,
            base_delay=settings.retry_base_delay,
            max_delay=settings.retry_max_delay,
            jitter=settings.retry_jitter,
        )

    # -- internal pipeline -------------------------------------------------
    def _cache_key(self, operation: str, parts: list[Any]) -> str:
        rendered = "|".join("" if p is None else str(p) for p in parts)
        return f"{operation}::{rendered}"

    def _execute(self, operation: str, key_parts: list[Any], ttl: float, loader: Callable[[], Any]) -> Any:
        key = self._cache_key(operation, key_parts)
        cache_on = self._settings.cache_enabled and self._cache is not None
        if cache_on:
            cached = self._cache.get(key)
            if cached is not None:
                logger.info("cache.hit", extra={"operation": operation, "key": key})
                return cached
        if self._rate_limiter is not None and self._settings.rate_limit_enabled:
            self._rate_limiter.acquire(timeout=self._settings.rate_limit_acquire_timeout)
        result = with_retries(
            loader, policy=self._retry_policy, operation=operation
        )
        if cache_on and ttl > 0:
            self._cache.set(key, result, ttl=ttl)
        return result

    # -- quotes ------------------------------------------------------------
    def _quote(self, symbol: str, asset_class: AssetClass) -> Quote:
        return self._execute(
            "quote",
            [asset_class.value, symbol.upper()],
            self._settings.cache_ttl_quote,
            lambda: self._provider.get_quote(symbol, asset_class=asset_class),
        )

    def get_stock(self, symbol: str) -> Quote:
        return self._quote(symbol, AssetClass.STOCK)

    def get_mutual_fund(self, symbol: str) -> Quote:
        return self._quote(symbol, AssetClass.MUTUAL_FUND)

    def get_etf(self, symbol: str) -> Quote:
        return self._quote(symbol, AssetClass.ETF)

    def get_gold(self, symbol: str = _GOLD_DEFAULT) -> Quote:
        return self._quote(symbol or _GOLD_DEFAULT, AssetClass.GOLD)

    def get_index(self, symbol: str) -> Quote:
        return self._quote(symbol, AssetClass.INDEX)

    # -- ratios ------------------------------------------------------------
    def get_ratios(self, symbol: str) -> FinancialRatios:
        return self._execute(
            "ratios",
            [symbol.upper()],
            self._settings.cache_ttl_ratios,
            lambda: self._provider.get_ratios(symbol),
        )

    # -- history -----------------------------------------------------------
    def get_historical(
        self,
        symbol: str,
        *,
        asset_class: AssetClass = AssetClass.STOCK,
        interval: str | None = None,
        start: str | None = None,
        end: str | None = None,
        limit: int | None = None,
    ) -> HistoricalPrices:
        interval = interval or self._settings.default_interval
        if limit:
            limit = min(int(limit), self._settings.max_history_points)
        return self._execute(
            "historical",
            [asset_class.value, symbol.upper(), interval, start, end, limit],
            self._settings.cache_ttl_historical,
            lambda: self._provider.get_historical(
                symbol,
                asset_class=asset_class,
                interval=interval,
                start=start,
                end=end,
                limit=limit,
            ),
        )

    # -- news --------------------------------------------------------------
    def get_news(
        self,
        *,
        query: str | None = None,
        symbols: list[str] | None = None,
        limit: int | None = None,
    ) -> NewsFeed:
        limit = min(int(limit or self._settings.default_news_limit), self._settings.max_news_limit)
        sym_key = ",".join(sorted(s.upper() for s in symbols)) if symbols else ""
        return self._execute(
            "news",
            [query or "", sym_key, limit],
            self._settings.cache_ttl_news,
            lambda: self._provider.get_news(query=query, symbols=symbols, limit=limit),
        )

    # -- diagnostics -------------------------------------------------------
    def provider_name(self) -> str:
        return self._provider.name

    def cache_stats(self) -> dict[str, Any]:
        return self._cache.stats() if self._cache is not None else {"enabled": False}
