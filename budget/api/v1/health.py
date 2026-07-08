"""Health/liveness endpoint for the Budget Planner."""
from fastapi import APIRouter

from budget.core.config import get_settings

router = APIRouter(tags=["health"])


@router.get("/health", summary="Liveness/readiness probe")
async def health() -> dict[str, str]:
    s = get_settings()
    return {
        "status": "ok",
        "service": s.app_name,
        "version": s.app_version,
        "environment": s.environment,
    }
