"""Versioned API router (v1) aggregating all RAG endpoints."""
from fastapi import APIRouter

from rag.api.v1 import documents, health, query

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(documents.router)
api_router.include_router(query.router)

__all__ = ["api_router"]
