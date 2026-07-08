"""Operational diagnostics: cache statistics."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from market.api.deps import get_service
from market.schemas.response import CacheStatsOut
from market.services import MarketService

router = APIRouter(prefix="/cache", tags=["diagnostics"])


@router.get("/stats", response_model=CacheStatsOut, summary="Cache statistics")
async def cache_stats(service: MarketService = Depends(get_service)) -> CacheStatsOut:
    return CacheStatsOut.from_domain(service.cache_stats())
