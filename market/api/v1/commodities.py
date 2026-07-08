"""Gold (commodity) endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from market.api.deps import get_service
from market.domain.enums import AssetClass
from market.schemas.response import HistoricalPricesOut, QuoteOut
from market.services import MarketService

router = APIRouter(prefix="/gold", tags=["gold"])

_DEFAULT_GOLD = "XAUUSD"


@router.get("", response_model=QuoteOut, summary="Spot gold price")
async def gold(
    symbol: str = Query(default=_DEFAULT_GOLD, description="Gold pair, e.g. XAUUSD"),
    service: MarketService = Depends(get_service),
) -> QuoteOut:
    return QuoteOut.from_domain(service.get_gold(symbol))


@router.get("/historical", response_model=HistoricalPricesOut, summary="Gold historical prices")
async def gold_historical(
    symbol: str = Query(default=_DEFAULT_GOLD),
    interval: str | None = Query(default=None),
    limit: int | None = Query(default=None, ge=1, le=5000),
    service: MarketService = Depends(get_service),
) -> HistoricalPricesOut:
    return HistoricalPricesOut.from_domain(
        service.get_historical(
            symbol, asset_class=AssetClass.GOLD, interval=interval, limit=limit
        )
    )
