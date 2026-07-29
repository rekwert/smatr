"""Market Data Engine — unified access for SMC / Pump / AI (Part 9)."""

from __future__ import annotations

import logging
from typing import Any, Optional

from app.exchange_layer.base.exchange_interface import ExchangeInterface
from app.exchange_layer.base.models import UnifiedCandle
from app.exchange_layer.connectors import DEFAULT_EXCHANGES, create_exchange, create_exchanges
from app.exchange_layer.normalizer.symbols import normalize_symbol, to_canonical_tf
from app.market_data.candles import CandleBar

logger = logging.getLogger(__name__)


class MarketDataEngine:
    """Single entry for analyzers — never call raw exchange APIs from engines."""

    def __init__(self, exchanges: Optional[list[str]] = None):
        names = exchanges or DEFAULT_EXCHANGES
        self.adapters: dict[str, ExchangeInterface] = {
            n: create_exchange(n) for n in names
        }

    def get_adapter(self, exchange: str) -> ExchangeInterface:
        key = exchange.lower()
        if key not in self.adapters:
            self.adapters[key] = create_exchange(key)
        return self.adapters[key]

    async def get_candles(
        self,
        symbol: str,
        timeframe: str = "15m",
        *,
        exchange: str = "bybit",
        limit: int = 200,
    ) -> list[UnifiedCandle]:
        adapter = self.get_adapter(exchange)
        return await adapter.get_candles(
            normalize_symbol(symbol),
            timeframe=to_canonical_tf(timeframe),
            limit=limit,
        )

    async def get_candles_as_bars(
        self,
        symbol: str,
        timeframe: str = "15m",
        *,
        exchange: str = "bybit",
        limit: int = 200,
    ) -> list[CandleBar]:
        candles = await self.get_candles(symbol, timeframe, exchange=exchange, limit=limit)
        return [c.to_bar() for c in candles]

    async def get_best_candles(
        self,
        symbol: str,
        timeframe: str = "15m",
        limit: int = 200,
        preferred: Optional[list[str]] = None,
    ) -> tuple[str, list[UnifiedCandle]]:
        """Try exchanges by priority until candles are returned."""
        order = preferred or sorted(self.adapters.keys(), key=lambda n: -self.adapters[n].priority)
        last_err: Exception | None = None
        for name in order:
            try:
                candles = await self.get_candles(symbol, timeframe, exchange=name, limit=limit)
                if len(candles) >= 30:
                    return name, candles
            except Exception as exc:  # noqa: BLE001
                last_err = exc
                logger.debug("candles fail %s/%s: %s", name, symbol, exc)
        if last_err:
            raise last_err
        return order[0], []

    async def aggregate_ticker_snapshot(self, symbol: str) -> list[dict[str, Any]]:
        sym = normalize_symbol(symbol)
        out: list[dict[str, Any]] = []
        for name, adapter in self.adapters.items():
            try:
                tickers = await adapter.get_tickers()
                match = next((t for t in tickers if t.symbol == sym), None)
                if match:
                    out.append(match.to_dict())
            except Exception as exc:  # noqa: BLE001
                logger.debug("ticker snapshot %s failed: %s", name, exc)
        return out

    async def analysis_bundle(
        self,
        symbol: str,
        timeframe: str = "15m",
        exchange: str = "bybit",
        limit: int = 200,
    ) -> dict[str, Any]:
        """Unified payload for SMC / Pump / AI engines."""
        adapter = self.get_adapter(exchange)
        candles = await adapter.get_candles(symbol, timeframe=timeframe, limit=limit)
        oi = await adapter.get_open_interest(symbol)
        funding = await adapter.get_funding_rate(symbol)
        book = None
        try:
            ob = await adapter.get_orderbook(symbol, limit=20)
            from app.exchange_layer.normalizer.orderbook import normalize_orderbook

            book = normalize_orderbook(exchange, symbol, ob.bids, ob.asks, ob.timestamp)
        except Exception:  # noqa: BLE001
            book = None
        return {
            "exchange": exchange,
            "symbol": normalize_symbol(symbol),
            "timeframe": to_canonical_tf(timeframe),
            "candles": [c.to_dict() for c in candles],
            "bars": [c.to_bar() for c in candles],
            "open_interest": oi,
            "funding_rate": funding,
            "orderbook": book,
        }
