"""Composition root / dependency-injection wiring for the Savings Optimizer.

The API layer depends only on these providers, never on concrete construction.
Providers are ``lru_cache``-d so the optimizer and settings behave as
process-lifetime singletons. The optimizer is a pure, stateless computation
service, so there are no pooled network clients to release — but
:func:`shutdown_dependencies` is provided for a uniform lifecycle contract
across all suite sub-apps.
"""
from __future__ import annotations

from functools import lru_cache

from fastapi import Depends

from savings.core.config import Settings, get_settings
from savings.services.savings_optimizer import SavingsOptimizer


@lru_cache
def _build_optimizer(settings: Settings) -> SavingsOptimizer:
    return SavingsOptimizer(settings)


def get_optimizer(settings: Settings = Depends(get_settings)) -> SavingsOptimizer:
    return _build_optimizer(settings)


async def shutdown_dependencies() -> None:
    """Release cached resources. No-op for this stateless service."""
    _build_optimizer.cache_clear()
