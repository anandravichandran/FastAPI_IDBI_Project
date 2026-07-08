"""Market index endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from market.api.deps import get_service
from market.domain.enums import AssetClass
from market.schemas.response import HistoricalPricesOut, QuoteOut
from market.services import MarketService

router = APIRouter(prefix="/indices", tags=["indices"])


@router.get("/{symbol}", response_model=QuoteOut, summary="Index level / quote")
async def index_quote(symbol: str, service: MarketService = Depends(get_service)) -> QuoteOut:
    return QuoteOut.from_domain(service.get_index(symbol))


@router.get(
    "/{symbol}/historical",
    response_model=HistoricalPricesOut,
    summary="Index historical levels",
)
async def index_historical(
    symbol: str,
    interval: str | None = Query(default=None),
    limit: int | None = Query(default=None, ge=1, le=5000),
    service: MarketService = Depends(get_service),
) -> HistoricalPricesOut:
    return HistoricalPricesOut.from_domain(
        service.get_historical(
            symbol, asset_class=AssetClass.INDEX, interval=interval, limit=limit
        )
    )
