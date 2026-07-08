"""Liveness / readiness endpoint."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from market.api.deps import get_service
from market.core.config import Settings, get_settings
from market.schemas.response import HealthOut
from market.services import MarketService

router = APIRouter(tags=["meta"])


@router.get("/health", response_model=HealthOut, summary="Service health")
async def health(
    settings: Settings = Depends(get_settings),
    service: MarketService = Depends(get_service),
) -> HealthOut:
    return HealthOut(
        status="ok",
        service=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
        provider=service.provider_name(),
    )
