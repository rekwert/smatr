"""KuCoin futures connector (Part 9)."""

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

BASE = "https://api-futures.kucoin.com"
KC_TF = {
    "1m": 1,
    "3m": 3,
    "5m": 5,
    "15m": 15,
    "30m": 30,
    "1h": 60,
    "4h": 240,
    "1d": 1440,
}


def _sym(symbol: str) -> str:
    """KuCoin futures often uses XBTUSDTM / ETHUSDTM."""
    s = normalize_symbol(symbol)
    if s.startswith("BTC"):
        s = "XBT" + s[3:]
    if not s.endswith("M"):
        s = f"{s}M"
    return s


def _from_kc(symbol: str) -> str:
    s = symbol.upper()
    if s.endswith("M"):
        s = s[:-1]
    if s.startswith("XBT"):
        s = "BTC" + s[3:]
    return normalize_symbol(s)


class KucoinExchange(ExchangeInterface):
    name = "kucoin"
    priority = 60

    async def get_symbols(self) -> list[UnifiedSymbol]:
        data = await http_get_json(f"{BASE}/api/v1/contracts/active", exchange=self.name)
        tickers = {t.symbol: t for t in await self.get_tickers()}
        out: list[UnifiedSymbol] = []
        for item in data.get("data") or []:
            raw = item.get("symbol") or ""
            if not raw.endswith("USDTM"):
                continue
            sym = _from_kc(raw)
            t = tickers.get(sym)
            out.append(
                UnifiedSymbol(
                    exchange=self.name,
                    symbol=sym,
                    type="future",
                    status="active" if item.get("status") == "Open" else "inactive",
                    volume_24h=t.volume_24h if t else float(item.get("turnoverOf24h") or 0),
                    price=t.last_price if t else float(item.get("lastTradePrice") or 0) or None,
                    base=item.get("baseCurrency"),
                    quote="USDT",
                    listed_at=int(item["firstOpenDate"]) if item.get("firstOpenDate") else None,
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
        granularity = KC_TF[tf]
        end_ts = int((end or time.time() * 1000) // 1000)
        start_ts = int(start // 1000) if start else end_ts - limit * granularity * 60
        data = await http_get_json(
            f"{BASE}/api/v1/kline/query",
            params={
                "symbol": _sym(symbol),
                "granularity": granularity,
                "from": start_ts,
                "to": end_ts,
            },
            exchange=self.name,
        )
        rows = data.get("data") or []
        out: list[UnifiedCandle] = []
        for row in rows:
            # [time, open, high, low, close, volume]
            ts = int(row[0])
            c = normalize_candle_row(
                self.name,
                symbol,
                tf,
                open_=float(row[1]),
                high=float(row[2]),
                low=float(row[3]),
                close=float(row[4]),
                volume=float(row[5]),
                timestamp_ms=ts * 1000 if ts < 10_000_000_000 else ts,
            )
            if c:
                out.append(c)
        out.sort(key=lambda x: x.timestamp)
        return out[-limit:]

    async def get_tickers(self) -> list[UnifiedTicker]:
        data = await http_get_json(f"{BASE}/api/v1/allTickers", exchange=self.name)
        payload = data.get("data")
        # KuCoin may return {"ticker": [...]} or a bare list
        if isinstance(payload, dict):
            rows = payload.get("ticker") or payload.get("tickers") or []
        elif isinstance(payload, list):
            rows = payload
        else:
            rows = []
        if isinstance(rows, dict):
            rows = [rows]
        out: list[UnifiedTicker] = []
        for t in rows:
            if not isinstance(t, dict):
                continue
            raw = t.get("symbol") or ""
            if not raw.endswith("USDTM"):
                continue
            out.append(
                UnifiedTicker(
                    exchange=self.name,
                    symbol=_from_kc(raw),
                    last_price=float(t.get("price") or t.get("lastTradePrice") or 0),
                    volume_24h=float(t.get("turnoverOf24h") or t.get("volValue") or 0),
                    change_pct_24h=float(t["priceChgPct"]) * 100
                    if t.get("priceChgPct") is not None
                    else None,
                    bid=float(t["bestBidPrice"]) if t.get("bestBidPrice") else None,
                    ask=float(t["bestAskPrice"]) if t.get("bestAskPrice") else None,
                )
            )
        return out

    async def get_orderbook(self, symbol: str, limit: int = 50) -> UnifiedOrderbook:
        data = await http_get_json(
            f"{BASE}/api/v1/level2/snapshot",
            params={"symbol": _sym(symbol)},
            exchange=self.name,
        )
        row = data.get("data") or {}
        bids = [[float(p), float(s)] for p, s in (row.get("bids") or [])[:limit]]
        asks = [[float(p), float(s)] for p, s in (row.get("asks") or [])[:limit]]
        return UnifiedOrderbook(
            exchange=self.name,
            symbol=normalize_symbol(symbol),
            bids=bids,
            asks=asks,
            timestamp=int(row.get("ts") or time.time() * 1000),
        )

    async def get_open_interest(self, symbol: str) -> Optional[dict[str, Any]]:
        data = await http_get_json(
            f"{BASE}/api/v1/contracts/{_sym(symbol)}",
            exchange=self.name,
        )
        row = data.get("data") or {}
        oi = float(row.get("openInterest") or 0)
        return {"oi": oi, "oi_change_pct": 0.0} if oi else None

    async def get_funding_rate(self, symbol: str) -> Optional[float]:
        data = await http_get_json(
            f"{BASE}/api/v1/funding-rate/{_sym(symbol)}/current",
            exchange=self.name,
        )
        row = data.get("data") or {}
        if row.get("value") is None and row.get("fundingRate") is None:
            return None
        return float(row.get("value") or row.get("fundingRate") or 0)

    async def get_recent_trades(self, symbol: str, limit: int = 100) -> list[UnifiedTrade]:
        data = await http_get_json(
            f"{BASE}/api/v1/trade/history",
            params={"symbol": _sym(symbol)},
            exchange=self.name,
        )
        out: list[UnifiedTrade] = []
        for row in (data.get("data") or [])[:limit]:
            out.append(
                normalize_trade(
                    self.name,
                    symbol,
                    float(row.get("price") or 0),
                    float(row.get("size") or 0),
                    "buy" if str(row.get("side", "")).lower() == "buy" else "sell",
                    int(row.get("ts") or 0),
                )
            )
        return out
