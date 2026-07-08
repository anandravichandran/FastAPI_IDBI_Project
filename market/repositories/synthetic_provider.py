"""Deterministic, dependency-free synthetic market-data provider.

Produces stable, reproducible data seeded from the symbol so the service can run
and be tested fully offline (no OpenBB, no network). Values are plausible but
synthetic. A small set of sentinel symbols raises :class:`SymbolNotFoundError`
so not-found handling can be exercised.
"""
from __future__ import annotations

import hashlib
import math
from datetime import date, datetime, timedelta, timezone

from market.core.exceptions import SymbolNotFoundError
from market.domain.entities import (
    FinancialRatios,
    HistoricalPrices,
    NewsArticle,
    NewsFeed,
    PricePoint,
    Quote,
)
from market.domain.enums import AssetClass
from market.domain.interfaces.market_provider import IMarketDataProvider

_SENTINELS = {"UNKNOWN", "MISSING", "NULL", "NA"}


def _seed(text: str) -> int:
    return int(hashlib.md5(text.encode("utf-8")).hexdigest(), 16)


def _unit(text: str) -> float:
    """Deterministic float in [0, 1) from an arbitrary string."""
    return (_seed(text) % 1_000_000) / 1_000_000.0


class SyntheticMarketDataProvider(IMarketDataProvider):
    def __init__(self, *, default_currency: str = "USD") -> None:
        self._currency = default_currency

    @property
    def name(self) -> str:
        return "synthetic"

    # -- helpers -----------------------------------------------------------
    def _validate(self, symbol: str) -> str:
        if not symbol or not symbol.strip():
            raise SymbolNotFoundError("Symbol must not be empty.", details={"symbol": symbol})
        upper = symbol.strip().upper()
        if upper in _SENTINELS:
            raise SymbolNotFoundError(
                f"No market data for symbol {upper!r}.", details={"symbol": upper}
            )
        return upper

    def _base_price(self, symbol: str, asset_class: AssetClass) -> float:
        u = _unit(symbol + "|" + asset_class.value)
        if asset_class is AssetClass.GOLD:
            return round(1500 + u * 900, 2)
        if asset_class is AssetClass.INDEX:
            return round(1000 + u * 24000, 2)
        if asset_class is AssetClass.MUTUAL_FUND:
            return round(20 + u * 480, 2)
        if asset_class is AssetClass.ETF:
            return round(30 + u * 470, 2)
        return round(10 + u * 990, 2)

    # -- provider API ------------------------------------------------------
    def get_quote(self, symbol: str, *, asset_class: AssetClass) -> Quote:
        sym = self._validate(symbol)
        price = self._base_price(sym, asset_class)
        drift = (_unit(sym + "drift") - 0.5) * 0.06  # +/- 3%
        previous_close = round(price / (1 + drift), 2) if (1 + drift) else price
        change = round(price - previous_close, 2)
        change_percent = round((change / previous_close) * 100, 4) if previous_close else 0.0
        day_high = round(price * (1 + _unit(sym + "hi") * 0.02), 2)
        day_low = round(price * (1 - _unit(sym + "lo") * 0.02), 2)
        open_price = round(previous_close * (1 + (_unit(sym + "op") - 0.5) * 0.01), 2)
        volume = int(10_000 + _unit(sym + "vol") * 5_000_000)
        market_cap = round(price * (1_000_000 + _unit(sym + "cap") * 5_000_000_000), 2)
        return Quote(
            symbol=sym,
            asset_class=asset_class,
            price=price,
            currency=self._currency,
            name=f"{sym} {asset_class.label}",
            change=change,
            change_percent=change_percent,
            previous_close=previous_close,
            open=open_price,
            day_high=day_high,
            day_low=day_low,
            volume=volume,
            market_cap=market_cap if asset_class in {AssetClass.STOCK, AssetClass.ETF} else None,
            exchange="SYNTH",
            as_of=datetime.now(timezone.utc).isoformat(),
            source=self.name,
        )

    def get_historical(
        self,
        symbol: str,
        *,
        asset_class: AssetClass,
        interval: str,
        start: str | None = None,
        end: str | None = None,
        limit: int | None = None,
    ) -> HistoricalPrices:
        sym = self._validate(symbol)
        n = int(limit) if limit else 30
        n = max(1, min(n, 5000))
        step = {"1d": 1, "1w": 7, "1m": 30}.get(interval, 1)
        anchor = self._base_price(sym, asset_class)
        end_date = date.today()
        points: list[PricePoint] = []
        # Build oldest -> newest so the series reads chronologically.
        for i in range(n - 1, -1, -1):
            d = end_date - timedelta(days=i * step)
            wobble = math.sin(_seed(sym + str(i)) % 360) * 0.5
            drift = (_unit(sym + "h" + str(i)) - 0.5) * 0.04
            close = round(anchor * (1 + drift) + wobble, 2)
            open_p = round(close * (1 - (_unit(sym + "o" + str(i)) - 0.5) * 0.01), 2)
            high = round(max(open_p, close) * (1 + _unit(sym + "H" + str(i)) * 0.01), 2)
            low = round(min(open_p, close) * (1 - _unit(sym + "L" + str(i)) * 0.01), 2)
            vol = int(10_000 + _unit(sym + "v" + str(i)) * 4_000_000)
            points.append(
                PricePoint(date=d.isoformat(), open=open_p, high=high, low=low, close=close, volume=vol)
            )
        return HistoricalPrices(
            symbol=sym,
            asset_class=asset_class,
            interval=interval,
            currency=self._currency,
            points=tuple(points),
            source=self.name,
        )

    def get_ratios(self, symbol: str) -> FinancialRatios:
        sym = self._validate(symbol)

        def r(tag: str, lo: float, hi: float) -> float:
            return round(lo + _unit(sym + tag) * (hi - lo), 4)

        return FinancialRatios(
            symbol=sym,
            as_of=date.today().isoformat(),
            currency=self._currency,
            pe_ratio=r("pe", 8, 40),
            forward_pe=r("fpe", 7, 35),
            peg_ratio=r("peg", 0.5, 3.0),
            pb_ratio=r("pb", 0.8, 12.0),
            ps_ratio=r("ps", 1.0, 15.0),
            ev_to_ebitda=r("ev", 5, 30),
            eps=r("eps", 1, 25),
            dividend_yield=r("dy", 0.0, 0.06),
            payout_ratio=r("pr", 0.0, 0.8),
            roe=r("roe", 0.02, 0.4),
            roa=r("roa", 0.01, 0.25),
            gross_margin=r("gm", 0.2, 0.75),
            net_margin=r("nm", 0.02, 0.35),
            current_ratio=r("cr", 0.8, 3.5),
            quick_ratio=r("qr", 0.5, 2.5),
            debt_to_equity=r("de", 0.0, 2.5),
            interest_coverage=r("ic", 1.0, 20.0),
            beta=r("beta", 0.3, 2.0),
            source=self.name,
        )

    def get_news(
        self,
        *,
        query: str | None = None,
        symbols: list[str] | None = None,
        limit: int = 20,
    ) -> NewsFeed:
        n = max(1, int(limit))
        subj = (query or (symbols[0] if symbols else "markets")).strip() or "markets"
        syms = tuple(s.strip().upper() for s in (symbols or []) if s.strip())
        headlines = [
            "{s} shares move as investors weigh outlook",
            "{s}: analysts update price targets",
            "What the latest data means for {s}",
            "{s} in focus amid sector rotation",
            "{s} volatility rises on macro headlines",
            "Earnings watch: {s} guidance in spotlight",
        ]
        now = datetime.now(timezone.utc)
        articles: list[NewsArticle] = []
        for i in range(n):
            template = headlines[_seed(subj + str(i)) % len(headlines)]
            published = now - timedelta(hours=i * 3)
            articles.append(
                NewsArticle(
                    title=template.format(s=subj),
                    published_at=published.isoformat(),
                    source="SynthWire",
                    url="https://news.example.com/" + str(abs(_seed(subj)) + i),
                    summary="Synthetic market commentary generated for offline use.",
                    symbols=syms,
                )
            )
        return NewsFeed(articles=tuple(articles), query=query, provider=self.name)
