"""Market and company news endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from market.api.deps import get_service
from market.schemas.request import NewsRequest
from market.schemas.response import NewsFeedOut
from market.services import MarketService

router = APIRouter(prefix="/news", tags=["news"])


@router.get("", response_model=NewsFeedOut, summary="Market / company news")
async def news_get(
    query: str | None = Query(default=None, description="Free-text search query"),
    symbols: list[str] | None = Query(default=None, description="Ticker symbols"),
    limit: int | None = Query(default=None, ge=1, le=100),
    service: MarketService = Depends(get_service),
) -> NewsFeedOut:
    return NewsFeedOut.from_domain(
        service.get_news(query=query, symbols=symbols, limit=limit)
    )


@router.post("", response_model=NewsFeedOut, summary="Market / company news (body)")
async def news_post(
    body: NewsRequest, service: MarketService = Depends(get_service)
) -> NewsFeedOut:
    return NewsFeedOut.from_domain(
        service.get_news(query=body.query, symbols=body.symbols, limit=body.limit)
    )
