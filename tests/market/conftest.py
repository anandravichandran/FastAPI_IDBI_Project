"""Shared fixtures for the Market Data service tests.

Everything runs fully offline against the deterministic synthetic provider, so
no network, OpenBB SDK or credentials are required. Cache TTLs and the rate
limiter are configured tightly so caching / rate-limit behaviour is observable
in tests.
"""
from __future__ import annotations

import pytest

from market.core.config import Settings
from market.repositories import (
    SyntheticMarketDataProvider,
    TokenBucketRateLimiter,
    TTLCache,
)
from market.repositories.retry import RetryPolicy
from market.services import MarketService


@pytest.fixture
def settings() -> Settings:
    return Settings(
        provider_backend="synthetic",
        cache_enabled=True,
        cache_ttl_quote=60,
        cache_ttl_historical=60,
        cache_ttl_ratios=60,
        cache_ttl_news=60,
        rate_limit_enabled=True,
        rate_limit_rpm=6000,
        rate_limit_burst=50,
        retry_max_attempts=3,
        retry_base_delay=0.0,
        retry_max_delay=0.0,
        retry_jitter=0.0,
    )


@pytest.fixture
def provider() -> SyntheticMarketDataProvider:
    return SyntheticMarketDataProvider(default_currency="USD")


@pytest.fixture
def cache() -> TTLCache:
    return TTLCache(max_entries=256)


@pytest.fixture
def service(settings, provider, cache) -> MarketService:
    limiter = TokenBucketRateLimiter(rate_per_sec=1000, capacity=50)
    return MarketService(
        provider=provider,
        cache=cache,
        rate_limiter=limiter,
        settings=settings,
        retry_policy=RetryPolicy(
            max_attempts=3, base_delay=0.0, max_delay=0.0, jitter=0.0
        ),
    )
