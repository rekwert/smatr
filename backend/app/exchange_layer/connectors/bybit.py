"""Bybit connector — Part 9 (wraps existing client → unified models)."""

from __future__ import annotations

import time
from typing import Any, Optional

from app.exchange_layer.base.exchange_interface import ExchangeInterface
from app.exchange_layer.base.models import (
    UnifiedCandle,
    UnifiedOrderbook,
    UnifiedSymbol,
    UnifiedTicker,
    UnifiedTrade,
)
from app.exchange_layer.http_client import http_get_json
from app.exchange_layer.normalizer.candles import normalize_candle_row
from app.exchange_layer.normalizer.symbols import normalize_symbol, to_canonical_tf
from app.exchange_layer.normalizer.trades import normalize_trade
from app.exchanges.bybit import BybitClient

BYBIT_TF = {
    "1m": "1",
    "3m": "3",
    "5m": "5",
    "15m": "15",
    "30m": "30",
    "1h": "60",
    "4h": "240",
    "1d": "D",
}


class BybitExchange(ExchangeInterface):
    name = "bybit"
    priority = 100

    def __init__(self) -> None:
        super().__init__()
        self._client = BybitClient()

    async def get_symbols(self) -> list[UnifiedSymbol]:
        instruments = await self._client.get_instruments()
        tickers = {t.get("symbol"): t for t in await self._client.get_tickers()}
        out: list[UnifiedSymbol] = []
        for item in instruments:
            sym = item.get("symbol")
            if not sym:
                continue
            t = tickers.get(sym) or {}
            out.append(
                UnifiedSymbol(
                    exchange=self.name,
                    symbol=normalize_symbol(sym),
                    type="future",
                    status="active" if item.get("status") == "Trading" else "inactive",
                    volume_24h=float(t.get("turnover24h") or 0),
                    price=float(t.get("lastPrice") or 0) or None,
                    base=item.get("baseCoin"),
                    quote=item.get("quoteCoin") or "USDT",
                    raw={"instrument": item},
                )
            )
        return out

    async def get_candles(
        self,
        symbol: str,
        timeframe: str = "15m",
        limit: int = 200,
        start: Optional[int] = None,
        end: Optional[int] = None,
    ) -> list[UnifiedCandle]:
        tf = to_canonical_tf(timeframe)
        bars = await self._client.get_klines(
            normalize_symbol(symbol),
            timeframe=BYBIT_TF[tf],
            limit=limit,
            start=start,
            end=end,
        )
        out: list[UnifiedCandle] = []
        for b in bars:
            c = normalize_candle_row(
                self.name,
                symbol,
                tf,
                open_=b.open,
                high=b.high,
                low=b.low,
                close=b.close,
                volume=b.volume,
                timestamp_ms=b.timestamp,
            )
            if c:
                out.append(c)
        return out

    async def get_tickers(self) -> list[UnifiedTicker]:
        rows = await self._client.get_tickers()
        out: list[UnifiedTicker] = []
        for t in rows:
            sym = t.get("symbol")
            if not sym or not str(sym).endswith("USDT"):
                continue
            out.append(
                UnifiedTicker(
                    exchange=self.name,
                    symbol=normalize_symbol(sym),
                    last_price=float(t.get("lastPrice") or 0),
                    volume_24h=float(t.get("turnover24h") or 0),
                    change_pct_24h=float(t.get("price24hPcnt") or 0) * 100
                    if t.get("price24hPcnt") is not None
                    else None,
                    bid=float(t["bid1Price"]) if t.get("bid1Price") else None,
                    ask=float(t["ask1Price"]) if t.get("ask1Price") else None,
                    funding_rate=float(t["fundingRate"]) if t.get("fundingRate") else None,
                    open_interest=float(t["openInterest"]) if t.get("openInterest") else None,
                )
            )
        return out

    async def get_orderbook(self, symbol: str, limit: int = 50) -> UnifiedOrderbook:
        book = await self._client.get_orderbook(normalize_symbol(symbol), limit=limit)
        return UnifiedOrderbook(
            exchange=self.name,
            symbol=normalize_symbol(symbol),
            bids=book.get("bids") or [],
            asks=book.get("asks") or [],
            timestamp=int(book.get("ts") or time.time() * 1000),
        )

    async def get_open_interest(self, symbol: str) -> Optional[dict[str, Any]]:
        return await self._client.get_open_interest(normalize_symbol(symbol))

    async def get_funding_rate(self, symbol: str) -> Optional[float]:
        return await self._client.get_funding_rate(normalize_symbol(symbol))

    async def get_recent_trades(self, symbol: str, limit: int = 100) -> list[UnifiedTrade]:
        data = await http_get_json(
            f"{self._client.base_url}/v5/market/recent-trade",
            params={
                "category": self._client.category,
                "symbol": normalize_symbol(symbol),
                "limit": min(limit, 1000),
            },
            exchange=self.name,
        )
        if isinstance(data, dict) and data.get("retCode") == 0:
            items = (data.get("result") or {}).get("list") or []
        else:
            items = []
        out: list[UnifiedTrade] = []
        for row in items:
            out.append(
                normalize_trade(
                    self.name,
                    symbol,
                    float(row.get("price") or 0),
                    float(row.get("size") or 0),
                    "buy" if str(row.get("side", "")).lower() == "buy" else "sell",
                    int(row.get("time") or 0),
                )
            )
        return out
