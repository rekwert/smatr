"""Liquidity ranking + Low Cap + New Listing scanners (Part 9 §9–12)."""

from __future__ import annotations

import time
from typing import Any, Optional

from app.exchange_layer.base.exchange_interface import ExchangeInterface
from app.exchange_layer.base.models import UnifiedSymbol, UnifiedTicker
from app.exchange_layer.connectors import create_exchanges
from app.exchange_layer.normalizer.orderbook import normalize_orderbook
from app.exchange_layer.normalizer.symbols import normalize_symbol


def liquidity_score(
    volume_24h: float,
    depth_usd: float = 0.0,
    spread_pct: Optional[float] = None,
    trades_count: int = 0,
) -> float:
    """0–100 composite liquidity score."""
    vol_part = min(50.0, (volume_24h / 50_000_000) * 50)  # 50M → full
    depth_part = min(25.0, (depth_usd / 2_000_000) * 25)
    if spread_pct is None:
        spread_part = 10.0
    elif spread_pct <= 0.05:
        spread_part = 20.0
    elif spread_pct <= 0.2:
        spread_part = 15.0
    elif spread_pct <= 0.5:
        spread_part = 8.0
    else:
        spread_part = 2.0
    trades_part = min(5.0, trades_count / 200)
    return round(min(100.0, vol_part + depth_part + spread_part + trades_part), 1)


class MultiExchangeSymbolScanner:
    def __init__(self, exchanges: Optional[list[ExchangeInterface]] = None):
        self.exchanges = exchanges or create_exchanges()

    async def scan_universe(self, min_volume: float = 1_000_000) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for ex in self.exchanges:
            try:
                tickers = await ex.get_tickers()
            except Exception:  # noqa: BLE001
                continue
            for t in tickers:
                if t.volume_24h < min_volume:
                    continue
                spread = None
                if t.bid and t.ask and t.last_price:
                    spread = (t.ask - t.bid) / t.last_price * 100
                score = liquidity_score(t.volume_24h, spread_pct=spread)
                rows.append(
                    {
                        "exchange": ex.name,
                        "symbol": t.symbol,
                        "price": t.last_price,
                        "volume24h": t.volume_24h,
                        "change_pct_24h": t.change_pct_24h,
                        "spread_pct": round(spread, 4) if spread is not None else None,
                        "liquidity_score": score,
                        "market": "future",
                        "funding_rate": t.funding_rate,
                        "open_interest": t.open_interest,
                    }
                )
        rows.sort(key=lambda x: x["liquidity_score"], reverse=True)
        return rows

    async def low_cap_candidates(
        self,
        *,
        min_volume: float = 5_000_000,
        max_volume: float = 200_000_000,
        volume_increase_pct: float = 300.0,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Low-cap / early-move scanner (Part 9 §11). Market cap proxy via volume band."""
        universe = await self.scan_universe(min_volume=min_volume)
        out: list[dict[str, Any]] = []
        for row in universe:
            if row["volume24h"] > max_volume:
                continue
            # Prefer elevated change as proxy for volume expansion when RV unavailable
            chg = abs(row.get("change_pct_24h") or 0)
            liq = row["liquidity_score"]
            if liq > 70 and chg < 5:
                continue  # too liquid / quiet for low-cap pump hunt
            pump_hint = min(100, int(40 + chg * 2 + (100 - liq) * 0.3))
            out.append(
                {
                    **row,
                    "filter": "low_cap",
                    "pump_hint_score": pump_hint,
                    "notes": [
                        f"volume_band {min_volume}-{max_volume}",
                        f"liquidity_score={liq}",
                    ],
                }
            )
        out.sort(key=lambda x: x["pump_hint_score"], reverse=True)
        return out[:limit]

    async def new_listings(
        self,
        max_age_hours: float = 72.0,
        min_volume: float = 1_000_000,
    ) -> list[dict[str, Any]]:
        now_ms = int(time.time() * 1000)
        max_age_ms = int(max_age_hours * 3600 * 1000)
        found: list[dict[str, Any]] = []
        for ex in self.exchanges:
            try:
                symbols = await ex.get_symbols()
            except Exception:  # noqa: BLE001
                continue
            for s in symbols:
                if not s.listed_at:
                    continue
                age = now_ms - int(s.listed_at)
                if age < 0 or age > max_age_ms:
                    continue
                if s.volume_24h < min_volume:
                    continue
                found.append(
                    {
                        "type": "NEW_FUTURES_LISTING",
                        "exchange": ex.name,
                        "symbol": s.symbol,
                        "age_hours": round(age / 3600_000, 2),
                        "volume24h": s.volume_24h,
                        "price": s.price,
                        "listed_at": s.listed_at,
                    }
                )
        found.sort(key=lambda x: x["age_hours"])
        return found

    async def enrich_with_orderbook(
        self,
        exchange_name: str,
        symbol: str,
    ) -> dict[str, Any]:
        ex = next((e for e in self.exchanges if e.name == exchange_name), None)
        if not ex:
            from app.exchange_layer.connectors import create_exchange

            ex = create_exchange(exchange_name)
        book = await ex.get_orderbook(normalize_symbol(symbol))
        return normalize_orderbook(ex.name, symbol, book.bids, book.asks, book.timestamp)
