"""API v1 router aggregation for the Budget Planner."""
from fastapi import APIRouter

from budget.api.v1 import budget, health

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(budget.router)

__all__ = ["api_router"]
