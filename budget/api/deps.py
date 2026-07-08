"""Composition root / dependency-injection wiring for the Budget Planner.

The API layer depends only on these providers, never on concrete construction.
Providers are ``lru_cache``-d so the planner and settings are effectively
singletons for the process lifetime. Because the Budget Planner is a pure,
stateless computation service, there are no pooled network clients to release —
but :func:`shutdown_dependencies` is provided for a uniform lifecycle contract
across all suite sub-apps.
"""
from __future__ import annotations

from functools import lru_cache

from fastapi import Depends

from budget.core.config import Settings, get_settings
from budget.services.budget_planner import BudgetPlanner


@lru_cache
def _build_planner(settings: Settings) -> BudgetPlanner:
    return BudgetPlanner(settings)


def get_planner(settings: Settings = Depends(get_settings)) -> BudgetPlanner:
    return _build_planner(settings)


async def shutdown_dependencies() -> None:
    """Release cached resources. No-op for this stateless service."""
    _build_planner.cache_clear()
