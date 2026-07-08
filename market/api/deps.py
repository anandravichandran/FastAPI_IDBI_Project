"""Composition root / FastAPI dependencies.

Builds the provider, cache, rate limiter and service once per configuration
(``lru_cache`` keyed on the frozen ``Settings``) and injects them into routes.
Provider selection honours ``provider_backend`` and, outside production, falls
back to the deterministic synthetic provider if the OpenBB SDK is unavailable.
"""
from __future__ import annotations

from functools import lru_cache

from fastapi import Depends

from market.core.config import Settings, get_settings
from market.core.exceptions import ConfigurationError
from market.core.logging import get_logger
from market.domain.interfaces.market_provider import IMarketDataProvider
from market.repositories import (
    OpenBBMarketDataProvider,
    SyntheticMarketDataProvider,
    TokenBucketRateLimiter,
    TTLCache,
)
from market.repositories.retry import RetryPolicy
from market.services import MarketService

logger = get_logger(__name__)


def _openbb_importable() -> bool:
    import importlib.util

    return importlib.util.find_spec("openbb") is not None


def _build_provider(settings: Settings) -> IMarketDataProvider:
    backend = (settings.provider_backend or "openbb").lower()
    if backend == "synthetic":
        return SyntheticMarketDataProvider(default_currency=settings.default_currency)
    if backend == "openbb":
        if _openbb_importable():
            return OpenBBMarketDataProvider(
                default_currency=settings.default_currency,
                pat=settings.openbb_pat,
                equity_provider=settings.openbb_equity_provider,
            )
        if settings.allow_backend_fallback:
            logger.warning(
                "provider.fallback_to_synthetic",
                extra={"reason": "openbb SDK not installed"},
            )
            return SyntheticMarketDataProvider(default_currency=settings.default_currency)
        raise ConfigurationError(
            "OpenBB backend selected but the 'openbb' package is not installed."
        )
    raise ConfigurationError(f"Unknown provider backend: {settings.provider_backend!r}")


def _build_rate_limiter(settings: Settings) -> TokenBucketRateLimiter | None:
    if not settings.rate_limit_enabled:
        return None
    return TokenBucketRateLimiter(
        rate_per_sec=settings.rate_limit_per_second,
        capacity=settings.rate_limit_burst,
    )


@lru_cache
def _build_service(settings: Settings) -> MarketService:
    cache = TTLCache(max_entries=settings.cache_max_entries) if settings.cache_enabled else None
    retry_policy = RetryPolicy(
        max_attempts=settings.retry_max_attempts,
        base_delay=settings.retry_base_delay,
        max_delay=settings.retry_max_delay,
        jitter=settings.retry_jitter,
    )
    return MarketService(
        provider=_build_provider(settings),
        cache=cache,
        rate_limiter=_build_rate_limiter(settings),
        settings=settings,
        retry_policy=retry_policy,
    )


def get_service(settings: Settings = Depends(get_settings)) -> MarketService:
    return _build_service(settings)


async def shutdown_dependencies() -> None:
    """Release cached singletons (called from the app lifespan)."""
    _build_service.cache_clear()
