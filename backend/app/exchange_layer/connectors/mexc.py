"""MEXC contract futures connector (Part 9)."""

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

BASE = "https://contract.mexc.com"
MEXC_TF = {
    "1m": "Min1",
    "3m": "Min3",
    "5m": "Min5",
    "15m": "Min15",
    "30m": "Min30",
    "1h": "Min60",
    "4h": "Hour4",
    "1d": "Day1",
}


def _sym(symbol: str) -> str:
    s = normalize_symbol(symbol)
    if "_" in s:
        return s
    if s.endswith("USDT"):
        return f"{s[:-4]}_USDT"
    return s


class MexcExchange(ExchangeInterface):
    name = "mexc"
    priority = 80

    async def get_symbols(self) -> list[UnifiedSymbol]:
        data = await http_get_json(f"{BASE}/api/v1/contract/detail", exchange=self.name)
        tickers = {t.symbol: t for t in await self.get_tickers()}
        out: list[UnifiedSymbol] = []
        for item in data.get("data") or []:
            raw = item.get("symbol") or ""
            if not raw.endswith("_USDT"):
                continue
            sym = raw.replace("_", "")
            t = tickers.get(normalize_symbol(sym))
            out.append(
                UnifiedSymbol(
                    exchange=self.name,
                    symbol=normalize_symbol(sym),
                    type="future",
                    status="active" if item.get("state") == 0 else "inactive",
                    volume_24h=t.volume_24h if t else 0.0,
                    price=t.last_price if t else None,
                    base=item.get("baseCoin"),
                    quote="USDT",
                    listed_at=int(item["createTime"]) if item.get("createTime") else None,
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
        # MEXC kline endpoint
        end_ts = int((end or time.time() * 1000) // 1000)
        start_ts = int((start or (end_ts - limit * 60)) // 1000) if start else end_ts - limit * 900
        data = await http_get_json(
            f"{BASE}/api/v1/contract/kline/{_sym(symbol)}",
            params={"interval": MEXC_TF[tf], "start": start_ts, "end": end_ts},
            exchange=self.name,
        )
        payload = data.get("data") or {}
        # Sometimes dict of arrays, sometimes list
        out: list[UnifiedCandle] = []
        if isinstance(payload, dict) and "time" in payload:
            times = payload.get("time") or []
            for i, ts in enumerate(times):
                c = normalize_candle_row(
                    self.name,
                    symbol,
                    tf,
                    open_=float(payload["open"][i]),
                    high=float(payload["high"][i]),
                    low=float(payload["low"][i]),
                    close=float(payload["close"][i]),
                    volume=float(payload.get("vol", payload.get("volume", [0] * len(times)))[i]),
                    timestamp_ms=int(ts) * 1000 if int(ts) < 10_000_000_000 else int(ts),
                )
                if c:
                    out.append(c)
        elif isinstance(payload, list):
            for row in payload:
                if isinstance(row, dict):
                    ts = int(row.get("time") or row.get("t") or 0)
                    c = normalize_candle_row(
                        self.name,
                        symbol,
                        tf,
                        open_=float(row.get("open") or 0),
                        high=float(row.get("high") or 0),
                        low=float(row.get("low") or 0),
                        close=float(row.get("close") or 0),
                        volume=float(row.get("vol") or row.get("volume") or 0),
                        timestamp_ms=ts * 1000 if ts < 10_000_000_000 else ts,
                    )
                    if c:
                        out.append(c)
        return out[-limit:]

    async def get_tickers(self) -> list[UnifiedTicker]:
        data = await http_get_json(f"{BASE}/api/v1/contract/ticker", exchange=self.name)
        rows = data.get("data") or []
        if isinstance(rows, dict):
            rows = [rows]
        out: list[UnifiedTicker] = []
        for t in rows:
            raw = t.get("symbol") or ""
            if not raw.endswith("_USDT"):
                continue
            sym = raw.replace("_", "")
            out.append(
                UnifiedTicker(
                    exchange=self.name,
                    symbol=normalize_symbol(sym),
                    last_price=float(t.get("lastPrice") or 0),
                    volume_24h=float(t.get("amount24") or t.get("volume24") or 0),
                    change_pct_24h=float(t["riseFallRate"]) * 100
                    if t.get("riseFallRate") is not None
                    else None,
                    bid=float(t["bid1"]) if t.get("bid1") else None,
                    ask=float(t["ask1"]) if t.get("ask1") else None,
                    funding_rate=float(t["fundingRate"]) if t.get("fundingRate") else None,
                    open_interest=float(t["holdVol"]) if t.get("holdVol") else None,
                )
            )
        return out

    async def get_orderbook(self, symbol: str, limit: int = 50) -> UnifiedOrderbook:
        data = await http_get_json(
            f"{BASE}/api/v1/contract/depth/{_sym(symbol)}",
            params={"limit": min(limit, 100)},
            exchange=self.name,
        )
        row = data.get("data") or {}
        bids = [[float(x["price"]), float(x["vol"])] for x in (row.get("bids") or [])[:limit]]
        asks = [[float(x["price"]), float(x["vol"])] for x in (row.get("asks") or [])[:limit]]
        # alternate format [[p,v],...]
        if bids and isinstance(row.get("bids", [None])[0], (list, tuple)):
            bids = [[float(p), float(v)] for p, v in row.get("bids")[:limit]]
            asks = [[float(p), float(v)] for p, v in row.get("asks")[:limit]]
        return UnifiedOrderbook(
            exchange=self.name,
            symbol=normalize_symbol(symbol),
            bids=bids,
            asks=asks,
            timestamp=int(row.get("timestamp") or time.time() * 1000),
        )

    async def get_open_interest(self, symbol: str) -> Optional[dict[str, Any]]:
        tickers = await self.get_tickers()
        for t in tickers:
            if t.symbol == normalize_symbol(symbol) and t.open_interest is not None:
                return {"oi": t.open_interest, "oi_change_pct": 0.0}
        return None

    async def get_funding_rate(self, symbol: str) -> Optional[float]:
        tickers = await self.get_tickers()
        for t in tickers:
            if t.symbol == normalize_symbol(symbol):
                return t.funding_rate
        return None

    async def get_recent_trades(self, symbol: str, limit: int = 100) -> list[UnifiedTrade]:
        data = await http_get_json(
            f"{BASE}/api/v1/contract/deals/{_sym(symbol)}",
            params={"limit": min(limit, 100)},
            exchange=self.name,
        )
        out: list[UnifiedTrade] = []
        for row in data.get("data") or []:
            out.append(
                normalize_trade(
                    self.name,
                    symbol,
                    float(row.get("p") or row.get("price") or 0),
                    float(row.get("v") or row.get("vol") or 0),
                    "buy" if str(row.get("T") or row.get("side") or "").lower() in ("1", "buy") else "sell",
                    int(row.get("t") or row.get("time") or 0),
                )
            )
        return out
