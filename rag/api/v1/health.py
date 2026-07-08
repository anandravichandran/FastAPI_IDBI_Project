"""Health / readiness endpoint."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from rag.core.config import Settings, get_settings

router = APIRouter(tags=["health"])


@router.get("/health", summary="Liveness/readiness probe")
async def health(settings: Settings = Depends(get_settings)) -> dict[str, str]:
    return {
        "status": "ok",
        "service": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
    }
