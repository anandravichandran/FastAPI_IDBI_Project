"""Stock (equity) endpoints: quote, historical, ratios."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from market.api.deps import get_service
from market.domain.enums import AssetClass
from market.schemas.response import (
    FinancialRatiosOut,
    HistoricalPricesOut,
    QuoteOut,
)
from market.services import MarketService

router = APIRouter(prefix="/stocks", tags=["stocks"])


@router.get("/{symbol}/quote", response_model=QuoteOut, summary="Latest stock quote")
async def stock_quote(symbol: str, service: MarketService = Depends(get_service)) -> QuoteOut:
    return QuoteOut.from_domain(service.get_stock(symbol))


@router.get(
    "/{symbol}/historical",
    response_model=HistoricalPricesOut,
    summary="Historical OHLCV prices",
)
async def stock_historical(
    symbol: str,
    interval: str | None = Query(default=None, description="1d | 1w | 1m"),
    start: str | None = Query(default=None, description="ISO start date"),
    end: str | None = Query(default=None, description="ISO end date"),
    limit: int | None = Query(default=None, ge=1, le=5000),
    service: MarketService = Depends(get_service),
) -> HistoricalPricesOut:
    return HistoricalPricesOut.from_domain(
        service.get_historical(
            symbol,
            asset_class=AssetClass.STOCK,
            interval=interval,
            start=start,
            end=end,
            limit=limit,
        )
    )


@router.get("/{symbol}/ratios", response_model=FinancialRatiosOut, summary="Financial ratios")
async def stock_ratios(symbol: str, service: MarketService = Depends(get_service)) -> FinancialRatiosOut:
    return FinancialRatiosOut.from_domain(service.get_ratios(symbol))
