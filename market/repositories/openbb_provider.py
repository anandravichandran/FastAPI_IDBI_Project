"""OpenBB Platform-backed market-data provider.

The OpenBB SDK is imported lazily inside :meth:`_client` so importing this module
never requires the (heavy) dependency; it is only needed when this backend is
actually selected and used. Upstream failures are normalised into the
application exception hierarchy so the service's retry/rate-limit handling and
the HTTP error envelope behave consistently.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

from market.core.exceptions import (
    ProviderError,
    SymbolNotFoundError,
    UpstreamRateLimitedError,
    UpstreamUnavailableError,
)
from market.core.logging import get_logger
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

logger = get_logger(__name__)

_GOLD_SYMBOL = "XAUUSD"


class OpenBBMarketDataProvider(IMarketDataProvider):
    def __init__(
        self,
        *,
        default_currency: str = "USD",
        pat: str | None = None,
        equity_provider: str | None = None,
    ) -> None:
        self._currency = default_currency
        self._pat = pat
        self._equity_provider = equity_provider
        self._obb: Any | None = None

    @property
    def name(self) -> str:
        return "openbb"

    # -- lazy SDK client ---------------------------------------------------
    def _client(self) -> Any:
        if self._obb is None:
            try:
                from openbb import obb  # type: ignore
            except Exception as exc:  # pragma: no cover - offline safety
                raise UpstreamUnavailableError(
                    "OpenBB SDK is not available.", details={"cause": str(exc)}
                ) from exc
            if self._pat:
                try:  # pragma: no cover - network/credential dependent
                    obb.account.login(pat=self._pat)
                except Exception as exc:
                    logger.warning("openbb.login_failed", extra={"error": str(exc)})
            self._obb = obb
        return self._obb

    def _provider_kwargs(self) -> dict[str, Any]:
        return {"provider": self._equity_provider} if self._equity_provider else {}

    # -- error normalisation ----------------------------------------------
    def _classify(self, exc: Exception, *, symbol: str | None = None) -> Exception:
        text = str(exc).lower()
        if any(k in text for k in ("not found", "no data", "unknown symbol", "invalid symbol")):
            return SymbolNotFoundError(
                f"No market data for symbol {symbol!r}." if symbol else "Symbol not found.",
                details={"symbol": symbol, "cause": str(exc)},
            )
        if "429" in text or "rate limit" in text or "too many requests" in text:
            return UpstreamRateLimitedError(
                "Upstream provider rate limit hit.", details={"cause": str(exc)}
            )
        if any(k in text for k in ("timeout", "timed out", "connection", "unavailable", "503", "502")):
            return UpstreamUnavailableError(
                "Upstream provider temporarily unavailable.", details={"cause": str(exc)}
            )
        return ProviderError("Upstream provider error.", details={"cause": str(exc)})

    @staticmethod
    def _rows(result: Any) -> list[dict[str, Any]]:
        """Normalise an OBBject / DataFrame / list into a list of dicts."""
        if result is None:
            return []
        obj = getattr(result, "results", result)
        if hasattr(obj, "to_dict"):
            try:
                records = obj.to_dict(orient="records")  # pandas DataFrame
                if isinstance(records, list):
                    return records
            except TypeError:
                pass
        if isinstance(obj, dict):
            return [obj]
        if isinstance(obj, (list, tuple)):
            out: list[dict[str, Any]] = []
            for item in obj:
                if isinstance(item, dict):
                    out.append(item)
                elif hasattr(item, "model_dump"):
                    out.append(item.model_dump())
                elif hasattr(item, "__dict__"):
                    out.append(dict(item.__dict__))
            return out
        if hasattr(obj, "model_dump"):
            return [obj.model_dump()]
        return []

    @staticmethod
    def _num(row: dict[str, Any], *keys: str) -> float | None:
        for k in keys:
            if k in row and row[k] is not None:
                try:
                    return float(row[k])
                except (TypeError, ValueError):
                    continue
        return None

    # -- provider API ------------------------------------------------------
    def get_quote(self, symbol: str, *, asset_class: AssetClass) -> Quote:
        if asset_class is AssetClass.GOLD:
            symbol = symbol or _GOLD_SYMBOL
        obb = self._client()
        try:
            if asset_class in {AssetClass.INDEX, AssetClass.GOLD}:
                # Derive a quote from the most recent historical bar.
                hist = self.get_historical(
                    symbol, asset_class=asset_class, interval="1d", limit=2
                )
                if not hist.points:
                    raise SymbolNotFoundError(
                        f"No market data for symbol {symbol!r}.", details={"symbol": symbol}
                    )
                last = hist.points[-1]
                prev = hist.points[-2] if len(hist.points) > 1 else last
                change = round(last.close - prev.close, 4)
                change_pct = round((change / prev.close) * 100, 4) if prev.close else None
                return Quote(
                    symbol=symbol.upper(),
                    asset_class=asset_class,
                    price=last.close,
                    currency=self._currency,
                    name=symbol.upper(),
                    change=change,
                    change_percent=change_pct,
                    previous_close=prev.close,
                    open=last.open,
                    day_high=last.high,
                    day_low=last.low,
                    volume=last.volume,
                    as_of=last.date,
                    source=self.name,
                )
            result = obb.equity.price.quote(symbol=symbol, **self._provider_kwargs())
            rows = self._rows(result)
            if not rows:
                raise SymbolNotFoundError(
                    f"No market data for symbol {symbol!r}.", details={"symbol": symbol}
                )
            row = rows[0]
            return Quote(
                symbol=symbol.upper(),
                asset_class=asset_class,
                price=self._num(row, "last_price", "close", "price") or 0.0,
                currency=row.get("currency") or self._currency,
                name=row.get("name"),
                change=self._num(row, "change"),
                change_percent=self._num(row, "change_percent", "changesPercentage"),
                previous_close=self._num(row, "prev_close", "previous_close"),
                open=self._num(row, "open"),
                day_high=self._num(row, "high", "day_high"),
                day_low=self._num(row, "low", "day_low"),
                volume=int(self._num(row, "volume") or 0) or None,
                market_cap=self._num(row, "market_cap"),
                exchange=row.get("exchange"),
                as_of=str(row.get("date") or datetime.now(timezone.utc).isoformat()),
                source=self.name,
            )
        except Exception as exc:
            raise self._classify(exc, symbol=symbol) from exc

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
        if asset_class is AssetClass.GOLD:
            symbol = symbol or _GOLD_SYMBOL
        obb = self._client()
        if not start:
            start = (date.today() - timedelta(days=365)).isoformat()
        try:
            if asset_class is AssetClass.INDEX:
                result = obb.index.price.historical(
                    symbol=symbol, start_date=start, end_date=end, interval=interval
                )
            elif asset_class is AssetClass.GOLD:
                result = obb.currency.price.historical(
                    symbol=symbol, start_date=start, end_date=end, interval=interval
                )
            else:
                result = obb.equity.price.historical(
                    symbol=symbol, start_date=start, end_date=end, interval=interval,
                    **self._provider_kwargs(),
                )
            rows = self._rows(result)
            points: list[PricePoint] = []
            for row in rows:
                close = self._num(row, "close", "adj_close")
                if close is None:
                    continue
                points.append(
                    PricePoint(
                        date=str(row.get("date") or row.get("Date") or ""),
                        open=self._num(row, "open") or close,
                        high=self._num(row, "high") or close,
                        low=self._num(row, "low") or close,
                        close=close,
                        volume=int(self._num(row, "volume") or 0) or None,
                    )
                )
            if limit and len(points) > limit:
                points = points[-int(limit):]
            if not points:
                raise SymbolNotFoundError(
                    f"No historical data for symbol {symbol!r}.", details={"symbol": symbol}
                )
            return HistoricalPrices(
                symbol=symbol.upper(),
                asset_class=asset_class,
                interval=interval,
                currency=self._currency,
                points=tuple(points),
                source=self.name,
            )
        except Exception as exc:
            raise self._classify(exc, symbol=symbol) from exc

    def get_ratios(self, symbol: str) -> FinancialRatios:
        obb = self._client()
        try:
            metrics = self._rows(
                obb.equity.fundamental.metrics(symbol=symbol, **self._provider_kwargs())
            )
            ratios = self._rows(
                obb.equity.fundamental.ratios(symbol=symbol, **self._provider_kwargs())
            )
            m = metrics[0] if metrics else {}
            r = ratios[0] if ratios else {}
            if not m and not r:
                raise SymbolNotFoundError(
                    f"No fundamentals for symbol {symbol!r}.", details={"symbol": symbol}
                )
            return FinancialRatios(
                symbol=symbol.upper(),
                as_of=str(m.get("period_ending") or r.get("period_ending") or date.today().isoformat()),
                currency=m.get("currency") or self._currency,
                pe_ratio=self._num(m, "pe_ratio", "price_to_earnings") or self._num(r, "price_to_earnings"),
                forward_pe=self._num(m, "forward_pe"),
                peg_ratio=self._num(m, "peg_ratio"),
                pb_ratio=self._num(m, "pb_ratio", "price_to_book") or self._num(r, "price_to_book"),
                ps_ratio=self._num(m, "ps_ratio", "price_to_sales") or self._num(r, "price_to_sales"),
                ev_to_ebitda=self._num(m, "ev_to_ebitda"),
                eps=self._num(m, "eps", "basic_eps"),
                dividend_yield=self._num(m, "dividend_yield"),
                payout_ratio=self._num(r, "payout_ratio"),
                roe=self._num(m, "return_on_equity", "roe") or self._num(r, "return_on_equity"),
                roa=self._num(m, "return_on_assets", "roa") or self._num(r, "return_on_assets"),
                gross_margin=self._num(r, "gross_profit_margin", "gross_margin"),
                net_margin=self._num(r, "net_profit_margin", "net_margin"),
                current_ratio=self._num(r, "current_ratio"),
                quick_ratio=self._num(r, "quick_ratio"),
                debt_to_equity=self._num(r, "debt_to_equity"),
                interest_coverage=self._num(r, "interest_coverage"),
                beta=self._num(m, "beta"),
                source=self.name,
            )
        except Exception as exc:
            raise self._classify(exc, symbol=symbol) from exc

    def get_news(
        self,
        *,
        query: str | None = None,
        symbols: list[str] | None = None,
        limit: int = 20,
    ) -> NewsFeed:
        obb = self._client()
        try:
            if symbols:
                result = obb.news.company(symbol=",".join(symbols), limit=limit)
            else:
                result = obb.news.world(limit=limit)
            rows = self._rows(result)
            articles: list[NewsArticle] = []
            for row in rows[:limit]:
                articles.append(
                    NewsArticle(
                        title=str(row.get("title") or ""),
                        published_at=str(row.get("date") or row.get("published") or ""),
                        source=row.get("source") or row.get("publisher"),
                        url=row.get("url"),
                        summary=row.get("text") or row.get("summary"),
                        symbols=tuple(s.upper() for s in (symbols or [])),
                    )
                )
            return NewsFeed(articles=tuple(articles), query=query, provider=self.name)
        except Exception as exc:
            raise self._classify(exc) from exc
