"""API v1 router aggregation."""
from fastapi import APIRouter

from advisor.api.v1 import advisor, health

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(advisor.router)

__all__ = ["api_router"]
