"""OpenBB-backed implementation of :class:`IMarketDataProvider`.

OpenBB is an optional, heavy dependency. It is imported lazily so the service
boots and the test-suite runs even when OpenBB is not installed. Any provider
failure degrades gracefully: the caller receives a ``MarketSnapshot`` flagged
as ``degraded`` rather than an exception, keeping the advisor resilient.
"""
from __future__ import annotations

import asyncio
import datetime as dt
from collections.abc import Sequence

from app.core.config import Settings
from app.core.logging import get_logger
from app.domain.entities import MarketQuote, MarketSnapshot
from app.domain.interfaces.market_data import IMarketDataProvider

logger = get_logger(__name__)


class OpenBBMarketDataProvider(IMarketDataProvider):
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._obb = None
        self._initialized = False

    def _ensure_client(self) -> object | None:
        """Lazily import and configure the OpenBB SDK (sync)."""
        if self._initialized:
            return self._obb
        self._initialized = True
        try:
            from openbb import obb  # type: ignore[import-not-found]

            if self._settings.openbb_pat:
                try:
                    obb.account.login(pat=self._settings.openbb_pat)  # type: ignore[attr-defined]
                except Exception:  # noqa: BLE001 - login is best-effort
                    logger.warning("OpenBB PAT login failed; using anonymous access")
            self._obb = obb
        except Exception:  # noqa: BLE001 - SDK not installed / import failure
            logger.warning("OpenBB SDK unavailable; market data will be degraded")
            self._obb = None
        return self._obb

    def _fetch_sync(self, symbols: Sequence[str]) -> MarketSnapshot:
        obb = self._ensure_client()
        as_of = dt.datetime.now(dt.timezone.utc).isoformat()
        if obb is None:
            return MarketSnapshot(quotes=[], source="unavailable", as_of=as_of, degraded=True)

        quotes: list[MarketQuote] = []
        provider = self._settings.openbb_provider
        for symbol in symbols:
            try:
                data = obb.equity.price.quote(  # type: ignore[attr-defined]
                    symbol=symbol, provider=provider
                )
                rows = data.results if hasattr(data, "results") else data
                row = rows[0] if isinstance(rows, list) and rows else rows
                quotes.append(
                    MarketQuote(
                        symbol=symbol,
                        price=_getattr_num(row, "last_price", "close", "price"),
                        change_percent_1d=_getattr_num(row, "change_percent"),
                        currency=getattr(row, "currency", None) or "USD",
                        name=getattr(row, "name", None),
                    )
                )
            except Exception:  # noqa: BLE001 - per-symbol resilience
                logger.warning("OpenBB quote failed", extra={"symbol": symbol})
                quotes.append(MarketQuote(symbol=symbol))

        degraded = all(q.price is None for q in quotes) if quotes else True
        return MarketSnapshot(
            quotes=quotes,
            source=f"openbb:{provider}",
            as_of=as_of,
            degraded=degraded,
        )

    async def get_snapshot(self, symbols: Sequence[str]) -> MarketSnapshot:
        unique = list(dict.fromkeys(s.strip().upper() for s in symbols if s.strip()))
        if not unique:
            return MarketSnapshot(source="empty", degraded=False)
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(self._fetch_sync, unique),
                timeout=self._settings.market_data_timeout_seconds,
            )
        except asyncio.TimeoutError:
            logger.warning("OpenBB request timed out", extra={"symbols": unique})
            return MarketSnapshot(source="timeout", degraded=True)


def _getattr_num(obj: object, *names: str) -> float | None:
    for name in names:
        value = getattr(obj, name, None)
        if value is None and isinstance(obj, dict):
            value = obj.get(name)
        if value is not None:
            try:
                return float(value)
            except (TypeError, ValueError):
                continue
    return None
