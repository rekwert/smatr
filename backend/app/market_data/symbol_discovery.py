"""Symbol discovery with liquidity filters (Part 7 §5)."""

from __future__ import annotations

from typing import Any, Optional

from app.exchanges.base import ExchangeConnector
from app.exchanges.bybit import BybitClient


class SymbolDiscoveryService:
    def __init__(
        self,
        exchange: Optional[ExchangeConnector] = None,
        min_volume: float = 1_000_000,
        max_spread_pct: float = 0.5,
    ):
        self.exchange = exchange or BybitClient()
        self.min_volume = min_volume
        self.max_spread_pct = max_spread_pct

    async def discover(self, limit: int = 100) -> list[dict[str, Any]]:
        tickers = await self.exchange.get_tickers()
        out: list[dict[str, Any]] = []
        for t in tickers:
            symbol = t.get("symbol")
            if not symbol or not str(symbol).endswith("USDT"):
                continue
            vol = float(t.get("turnover24h") or 0)
            if vol < self.min_volume:
                continue
            bid = float(t.get("bid1Price") or 0)
            ask = float(t.get("ask1Price") or 0)
            mid = (bid + ask) / 2 if bid and ask else 0
            spread_pct = ((ask - bid) / mid * 100) if mid else 0
            if mid and spread_pct > self.max_spread_pct:
                continue
            out.append(
                {
                    "symbol": symbol,
                    "type": "future",
                    "status": "active",
                    "volume24h": vol,
                    "spread_pct": round(spread_pct, 4) if mid else None,
                    "last_price": float(t.get("lastPrice") or 0),
                    "exchange": getattr(self.exchange, "name", "bybit"),
                }
            )
        out.sort(key=lambda x: x["volume24h"], reverse=True)
        return out[:limit]
