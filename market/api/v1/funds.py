"""Mutual fund and ETF endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from market.api.deps import get_service
from market.domain.enums import AssetClass
from market.schemas.response import HistoricalPricesOut, QuoteOut
from market.services import MarketService

router = APIRouter(tags=["funds"])


@router.get("/mutual-funds/{symbol}", response_model=QuoteOut, summary="Mutual fund quote")
async def mutual_fund(symbol: str, service: MarketService = Depends(get_service)) -> QuoteOut:
    return QuoteOut.from_domain(service.get_mutual_fund(symbol))


@router.get(
    "/mutual-funds/{symbol}/historical",
    response_model=HistoricalPricesOut,
    summary="Mutual fund historical prices",
)
async def mutual_fund_historical(
    symbol: str,
    interval: str | None = Query(default=None),
    limit: int | None = Query(default=None, ge=1, le=5000),
    service: MarketService = Depends(get_service),
) -> HistoricalPricesOut:
    return HistoricalPricesOut.from_domain(
        service.get_historical(
            symbol, asset_class=AssetClass.MUTUAL_FUND, interval=interval, limit=limit
        )
    )


@router.get("/etf/{symbol}", response_model=QuoteOut, summary="ETF quote")
async def etf(symbol: str, service: MarketService = Depends(get_service)) -> QuoteOut:
    return QuoteOut.from_domain(service.get_etf(symbol))


@router.get(
    "/etf/{symbol}/historical",
    response_model=HistoricalPricesOut,
    summary="ETF historical prices",
)
async def etf_historical(
    symbol: str,
    interval: str | None = Query(default=None),
    limit: int | None = Query(default=None, ge=1, le=5000),
    service: MarketService = Depends(get_service),
) -> HistoricalPricesOut:
    return HistoricalPricesOut.from_domain(
        service.get_historical(
            symbol, asset_class=AssetClass.ETF, interval=interval, limit=limit
        )
    )
