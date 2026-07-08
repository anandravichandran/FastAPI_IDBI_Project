"""API v1 router aggregation for the Savings Optimizer."""
from fastapi import APIRouter

from savings.api.v1 import health, savings

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(savings.router)

__all__ = ["api_router"]
