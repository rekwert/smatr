"""BingX swap connector (Part 9)."""

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

BASE = "https://open-api.bingx.com"
BINGX_TF = {
    "1m": "1m",
    "3m": "3m",
    "5m": "5m",
    "15m": "15m",
    "30m": "30m",
    "1h": "1h",
    "4h": "4h",
    "1d": "1d",
}


def _sym(symbol: str) -> str:
    s = normalize_symbol(symbol)
    if s.endswith("USDT"):
        return f"{s[:-4]}-USDT"
    return s


class BingxExchange(ExchangeInterface):
    name = "bingx"
    priority = 75

    async def get_symbols(self) -> list[UnifiedSymbol]:
        data = await http_get_json(
            f"{BASE}/openApi/swap/v2/quote/contracts",
            exchange=self.name,
        )
        tickers = {t.symbol: t for t in await self.get_tickers()}
        out: list[UnifiedSymbol] = []
        for item in data.get("data") or []:
            raw = item.get("symbol") or ""
            if not raw.endswith("-USDT"):
                continue
            sym = raw.replace("-", "")
            t = tickers.get(normalize_symbol(sym))
            out.append(
                UnifiedSymbol(
                    exchange=self.name,
                    symbol=normalize_symbol(sym),
                    type="future",
                    status="active" if item.get("status") == 1 else "inactive",
                    volume_24h=t.volume_24h if t else 0.0,
                    price=t.last_price if t else None,
                    base=item.get("asset") or raw.split("-")[0],
                    quote="USDT",
                    raw=item,
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
        params: dict[str, Any] = {
            "symbol": _sym(symbol),
            "interval": BINGX_TF[tf],
            "limit": min(limit, 1440),
        }
        if start:
            params["startTime"] = start
        if end:
            params["endTime"] = end
        data = await http_get_json(
            f"{BASE}/openApi/swap/v3/quote/klines",
            params=params,
            exchange=self.name,
        )
        rows = data.get("data") or []
        out: list[UnifiedCandle] = []
        for row in rows:
            if isinstance(row, dict):
                ts = int(row.get("time") or row.get("openTime") or 0)
                c = normalize_candle_row(
                    self.name,
                    symbol,
                    tf,
                    open_=float(row.get("open") or 0),
                    high=float(row.get("high") or 0),
                    low=float(row.get("low") or 0),
                    close=float(row.get("close") or 0),
                    volume=float(row.get("volume") or 0),
                    timestamp_ms=ts,
                )
            else:
                c = normalize_candle_row(
                    self.name,
                    symbol,
                    tf,
                    open_=float(row[0]),
                    high=float(row[2]),
                    low=float(row[3]),
                    close=float(row[1]),
                    volume=float(row[4]),
                    timestamp_ms=int(row[5]),
                )
            if c:
                out.append(c)
        out.sort(key=lambda x: x.timestamp)
        return out[-limit:]

    async def get_tickers(self) -> list[UnifiedTicker]:
        data = await http_get_json(
            f"{BASE}/openApi/swap/v2/quote/ticker",
            exchange=self.name,
        )
        rows = data.get("data") or []
        if isinstance(rows, dict):
            rows = [rows]
        out: list[UnifiedTicker] = []
        for t in rows:
            raw = t.get("symbol") or ""
            if not raw.endswith("-USDT"):
                continue
            sym = raw.replace("-", "")
            out.append(
                UnifiedTicker(
                    exchange=self.name,
                    symbol=normalize_symbol(sym),
                    last_price=float(t.get("lastPrice") or 0),
                    volume_24h=float(t.get("quoteVolume") or t.get("volume") or 0),
                    change_pct_24h=float(t["priceChangePercent"])
                    if t.get("priceChangePercent") is not None
                    else None,
                    bid=float(t["bidPrice"]) if t.get("bidPrice") else None,
                    ask=float(t["askPrice"]) if t.get("askPrice") else None,
                )
            )
        return out

    async def get_orderbook(self, symbol: str, limit: int = 50) -> UnifiedOrderbook:
        data = await http_get_json(
            f"{BASE}/openApi/swap/v2/quote/depth",
            params={"symbol": _sym(symbol), "limit": min(limit, 100)},
            exchange=self.name,
        )
        row = data.get("data") or {}
        bids = [[float(p), float(s)] for p, s in (row.get("bids") or [])]
        asks = [[float(p), float(s)] for p, s in (row.get("asks") or [])]
        return UnifiedOrderbook(
            exchange=self.name,
            symbol=normalize_symbol(symbol),
            bids=bids,
            asks=asks,
            timestamp=int(row.get("ts") or time.time() * 1000),
        )

    async def get_open_interest(self, symbol: str) -> Optional[dict[str, Any]]:
        data = await http_get_json(
            f"{BASE}/openApi/swap/v2/quote/openInterest",
            params={"symbol": _sym(symbol)},
            exchange=self.name,
        )
        row = data.get("data") or {}
        oi = float(row.get("openInterest") or 0)
        return {"oi": oi, "oi_change_pct": 0.0} if oi else None

    async def get_funding_rate(self, symbol: str) -> Optional[float]:
        data = await http_get_json(
            f"{BASE}/openApi/swap/v2/quote/premiumIndex",
            params={"symbol": _sym(symbol)},
            exchange=self.name,
        )
        row = data.get("data") or {}
        if isinstance(row, list):
            row = row[0] if row else {}
        if row.get("lastFundingRate") is None:
            return None
        return float(row["lastFundingRate"])

    async def get_recent_trades(self, symbol: str, limit: int = 100) -> list[UnifiedTrade]:
        data = await http_get_json(
            f"{BASE}/openApi/swap/v2/quote/trades",
            params={"symbol": _sym(symbol), "limit": min(limit, 100)},
            exchange=self.name,
        )
        out: list[UnifiedTrade] = []
        for row in data.get("data") or []:
            out.append(
                normalize_trade(
                    self.name,
                    symbol,
                    float(row.get("price") or 0),
                    float(row.get("qty") or row.get("quantity") or 0),
                    "buy" if not row.get("isBuyerMaker", True) else "sell",
                    int(row.get("time") or 0),
                )
            )
        return out
