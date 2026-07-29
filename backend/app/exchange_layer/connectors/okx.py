"""OKX futures connector (Part 9)."""

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

BASE = "https://www.okx.com"
OKX_TF = {
    "1m": "1m",
    "3m": "3m",
    "5m": "5m",
    "15m": "15m",
    "30m": "30m",
    "1h": "1H",
    "4h": "4H",
    "1d": "1D",
}


def _inst_id(symbol: str) -> str:
    s = normalize_symbol(symbol)
    if s.endswith("USDT"):
        return f"{s[:-4]}-USDT-SWAP"
    return f"{s}-SWAP"


class OkxExchange(ExchangeInterface):
    name = "okx"
    priority = 95

    async def get_symbols(self) -> list[UnifiedSymbol]:
        data = await http_get_json(
            f"{BASE}/api/v5/public/instruments",
            params={"instType": "SWAP"},
            exchange=self.name,
        )
        tickers = {t.symbol: t for t in await self.get_tickers()}
        out: list[UnifiedSymbol] = []
        for item in data.get("data") or []:
            if item.get("settleCcy") != "USDT" and item.get("quoteCcy") not in (None, "USDT"):
                # USDT-margined swaps use ctType / settleCcy
                if item.get("ctType") != "linear" and item.get("settleCcy") != "USDT":
                    continue
            inst = item.get("instId") or ""
            if not inst.endswith("-USDT-SWAP"):
                continue
            base = inst.split("-")[0]
            sym = f"{base}USDT"
            t = tickers.get(normalize_symbol(sym))
            out.append(
                UnifiedSymbol(
                    exchange=self.name,
                    symbol=normalize_symbol(sym),
                    type="future",
                    status="active" if item.get("state") == "live" else "inactive",
                    volume_24h=t.volume_24h if t else 0.0,
                    price=t.last_price if t else None,
                    base=base,
                    quote="USDT",
                    listed_at=int(item["listTime"]) if item.get("listTime") else None,
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
            "instId": _inst_id(symbol),
            "bar": OKX_TF[tf],
            "limit": str(min(limit, 300)),
        }
        if end:
            params["after"] = str(end)
        if start:
            params["before"] = str(start)
        data = await http_get_json(f"{BASE}/api/v5/market/candles", params=params, exchange=self.name)
        rows = data.get("data") or []
        out: list[UnifiedCandle] = []
        for row in reversed(rows):
            # [ts, o, h, l, c, vol, volCcy, volCcyQuote, confirm]
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
            f"{BASE}/api/v5/market/tickers",
            params={"instType": "SWAP"},
            exchange=self.name,
        )
        out: list[UnifiedTicker] = []
        for t in data.get("data") or []:
            inst = t.get("instId") or ""
            if not inst.endswith("-USDT-SWAP"):
                continue
            base = inst.split("-")[0]
            sym = f"{base}USDT"
            out.append(
                UnifiedTicker(
                    exchange=self.name,
                    symbol=normalize_symbol(sym),
                    last_price=float(t.get("last") or 0),
                    volume_24h=float(t.get("volCcy24h") or t.get("vol24h") or 0),
                    change_pct_24h=None,
                    bid=float(t["bidPx"]) if t.get("bidPx") else None,
                    ask=float(t["askPx"]) if t.get("askPx") else None,
                )
            )
        return out

    async def get_orderbook(self, symbol: str, limit: int = 50) -> UnifiedOrderbook:
        data = await http_get_json(
            f"{BASE}/api/v5/market/books",
            params={"instId": _inst_id(symbol), "sz": str(min(limit, 400))},
            exchange=self.name,
        )
        row = (data.get("data") or [{}])[0]
        bids = [[float(p), float(s)] for p, s, *_ in (row.get("bids") or [])]
        asks = [[float(p), float(s)] for p, s, *_ in (row.get("asks") or [])]
        return UnifiedOrderbook(
            exchange=self.name,
            symbol=normalize_symbol(symbol),
            bids=bids,
            asks=asks,
            timestamp=int(row.get("ts") or time.time() * 1000),
        )

    async def get_open_interest(self, symbol: str) -> Optional[dict[str, Any]]:
        data = await http_get_json(
            f"{BASE}/api/v5/public/open-interest",
            params={"instType": "SWAP", "instId": _inst_id(symbol)},
            exchange=self.name,
        )
        rows = data.get("data") or []
        if not rows:
            return None
        oi = float(rows[0].get("oi") or rows[0].get("oiCcy") or 0)
        return {"oi": oi, "oi_change_pct": 0.0}

    async def get_funding_rate(self, symbol: str) -> Optional[float]:
        data = await http_get_json(
            f"{BASE}/api/v5/public/funding-rate",
            params={"instId": _inst_id(symbol)},
            exchange=self.name,
        )
        rows = data.get("data") or []
        if not rows:
            return None
        return float(rows[0].get("fundingRate") or 0)

    async def get_recent_trades(self, symbol: str, limit: int = 100) -> list[UnifiedTrade]:
        data = await http_get_json(
            f"{BASE}/api/v5/market/trades",
            params={"instId": _inst_id(symbol), "limit": str(min(limit, 500))},
            exchange=self.name,
        )
        out: list[UnifiedTrade] = []
        for row in data.get("data") or []:
            out.append(
                normalize_trade(
                    self.name,
                    symbol,
                    float(row.get("px") or 0),
                    float(row.get("sz") or 0),
                    "buy" if row.get("side") == "buy" else "sell",
                    int(row.get("ts") or 0),
                )
            )
        return out
