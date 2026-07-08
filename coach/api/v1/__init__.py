"""API v1 router aggregation."""
from fastapi import APIRouter

from coach.api.v1 import coach, health

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(coach.router)

__all__ = ["api_router"]
