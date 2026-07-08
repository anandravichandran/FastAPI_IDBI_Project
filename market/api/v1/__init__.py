"""Version 1 API router aggregation."""
from fastapi import APIRouter

from market.api.v1 import (
    commodities,
    diagnostics,
    equities,
    funds,
    health,
    indices,
    news,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(equities.router)
api_router.include_router(funds.router)
api_router.include_router(commodities.router)
api_router.include_router(indices.router)
api_router.include_router(news.router)
api_router.include_router(diagnostics.router)

__all__ = ["api_router"]
