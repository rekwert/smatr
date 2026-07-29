"""Bitget USDT-M futures connector (Part 9)."""

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

BASE = "https://api.bitget.com"
BITGET_TF = {
    "1m": "1m",
    "3m": "3m",
    "5m": "5m",
    "15m": "15m",
    "30m": "30m",
    "1h": "1H",
    "4h": "4H",
    "1d": "1D",
}


def _product(symbol: str) -> str:
    return normalize_symbol(symbol)


class BitgetExchange(ExchangeInterface):
    name = "bitget"
    priority = 85

    async def get_symbols(self) -> list[UnifiedSymbol]:
        data = await http_get_json(
            f"{BASE}/api/v2/mix/market/contracts",
            params={"productType": "USDT-FUTURES"},
            exchange=self.name,
        )
        tickers = {t.symbol: t for t in await self.get_tickers()}
        out: list[UnifiedSymbol] = []
        for item in data.get("data") or []:
            sym = item.get("symbol") or ""
            if not sym.endswith("USDT"):
                continue
            t = tickers.get(normalize_symbol(sym))
            out.append(
                UnifiedSymbol(
                    exchange=self.name,
                    symbol=normalize_symbol(sym),
                    type="future",
                    status="active" if item.get("symbolStatus") == "normal" else "inactive",
                    volume_24h=t.volume_24h if t else 0.0,
                    price=t.last_price if t else None,
                    base=item.get("baseCoin"),
                    quote="USDT",
                    listed_at=int(item["launchTime"]) if item.get("launchTime") else None,
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
            "symbol": _product(symbol),
            "productType": "USDT-FUTURES",
            "granularity": BITGET_TF[tf],
            "limit": str(min(limit, 1000)),
        }
        if start:
            params["startTime"] = str(start)
        if end:
            params["endTime"] = str(end)
        data = await http_get_json(
            f"{BASE}/api/v2/mix/market/candles",
            params=params,
            exchange=self.name,
        )
        rows = data.get("data") or []
        out: list[UnifiedCandle] = []
        # Bitget often returns oldest→newest or newest→oldest; sort by ts
        parsed = []
        for row in rows:
            # [ts, open, high, low, close, baseVol, quoteVol]
            if isinstance(row, list):
                parsed.append(row)
            elif isinstance(row, dict):
                parsed.append(
                    [
                        row.get("ts") or row.get("timestamp"),
                        row.get("open"),
                        row.get("high"),
                        row.get("low"),
                        row.get("close"),
                        row.get("baseVolume") or row.get("volume"),
                    ]
                )
        parsed.sort(key=lambda r: int(r[0]))
        for row in parsed[-limit:]:
            c = normalize_candle_row(
                self.name,
                symbol,
                tf,
                open_=float(row[1]),
                high=float(row[2]),
                low=float(row[3]),
                close=float(row[4]),
                volume=float(row[5]),
                timestamp_ms=int(row[0]),
            )
            if c:
                out.append(c)
        return out

    async def get_tickers(self) -> list[UnifiedTicker]:
        data = await http_get_json(
            f"{BASE}/api/v2/mix/market/tickers",
            params={"productType": "USDT-FUTURES"},
            exchange=self.name,
        )
        out: list[UnifiedTicker] = []
        for t in data.get("data") or []:
            sym = t.get("symbol") or ""
            if not sym.endswith("USDT"):
                continue
            out.append(
                UnifiedTicker(
                    exchange=self.name,
                    symbol=normalize_symbol(sym),
                    last_price=float(t.get("lastPr") or t.get("last") or 0),
                    volume_24h=float(t.get("quoteVolume") or t.get("usdtVolume") or 0),
                    change_pct_24h=float(t["change24h"]) * 100
                    if t.get("change24h") is not None
                    else None,
                    bid=float(t["bidPr"]) if t.get("bidPr") else None,
                    ask=float(t["askPr"]) if t.get("askPr") else None,
                    funding_rate=float(t["fundingRate"]) if t.get("fundingRate") else None,
                    open_interest=float(t["holdingAmount"]) if t.get("holdingAmount") else None,
                )
            )
        return out

    async def get_orderbook(self, symbol: str, limit: int = 50) -> UnifiedOrderbook:
        data = await http_get_json(
            f"{BASE}/api/v2/mix/market/merge-depth",
            params={
                "symbol": _product(symbol),
                "productType": "USDT-FUTURES",
                "limit": str(min(limit, 150)),
            },
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
            f"{BASE}/api/v2/mix/market/open-interest",
            params={"symbol": _product(symbol), "productType": "USDT-FUTURES"},
            exchange=self.name,
        )
        row = data.get("data") or {}
        if isinstance(row, list):
            row = row[0] if row else {}
        oi = float(row.get("openInterest") or row.get("amount") or 0)
        return {"oi": oi, "oi_change_pct": 0.0} if oi else None

    async def get_funding_rate(self, symbol: str) -> Optional[float]:
        data = await http_get_json(
            f"{BASE}/api/v2/mix/market/current-fund-rate",
            params={"symbol": _product(symbol), "productType": "USDT-FUTURES"},
            exchange=self.name,
        )
        row = data.get("data") or {}
        if isinstance(row, list):
            row = row[0] if row else {}
        if row.get("fundingRate") is None:
            return None
        return float(row["fundingRate"])

    async def get_recent_trades(self, symbol: str, limit: int = 100) -> list[UnifiedTrade]:
        data = await http_get_json(
            f"{BASE}/api/v2/mix/market/fills",
            params={
                "symbol": _product(symbol),
                "productType": "USDT-FUTURES",
                "limit": str(min(limit, 100)),
            },
            exchange=self.name,
        )
        out: list[UnifiedTrade] = []
        for row in data.get("data") or []:
            out.append(
                normalize_trade(
                    self.name,
                    symbol,
                    float(row.get("price") or 0),
                    float(row.get("size") or row.get("qty") or 0),
                    "buy" if str(row.get("side", "")).lower() in ("buy", "long") else "sell",
                    int(row.get("ts") or row.get("timestamp") or 0),
                )
            )
        return out
