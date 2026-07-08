"""Health and readiness endpoints."""
from __future__ import annotations

from fastapi import APIRouter

from coach.api.deps import SettingsDep

router = APIRouter(tags=["health"])


@router.get("/health", summary="Liveness/readiness probe")
async def health(settings: SettingsDep) -> dict[str, object]:
    return {
        "status": "ok",
        "service": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "llm_enabled": settings.llm_enabled,
    }
