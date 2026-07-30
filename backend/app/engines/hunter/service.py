"""Service that scans multi-exchange universe with LowLiquidityHunter."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

from app.engines.hunter.analyzer import LowLiquidityHunter
from app.exchange_layer.connectors import create_exchanges
from app.exchange_layer.market_data_engine import MarketDataEngine
from app.exchange_layer.scanners import MultiExchangeSymbolScanner
from app.notifications.telegram import send_telegram

logger = logging.getLogger(__name__)


class PumpHunterService:
    def __init__(self, exchanges: Optional[list[str]] = None):
        self.exchanges = create_exchanges(exchanges) if exchanges else create_exchanges(
            ["bybit", "okx", "bitget", "mexc"]
        )
        self.scanner = MultiExchangeSymbolScanner(self.exchanges)
        self.hunter = LowLiquidityHunter()
        self.mde = MarketDataEngine([e.name for e in self.exchanges])

    async def run(
        self,
        *,
        min_volume: float = 5_000_000,
        max_volume: float = 150_000_000,
        limit_universe: int = 40,
        analyze_top: int = 20,
        timeframe: str = "15m",
        min_score: int = 70,
        notify: bool = False,
        persist: bool = True,
    ) -> list[dict[str, Any]]:
        universe = await self.scanner.scan_universe(min_volume=min(min_volume, 100_000))
        # Prefer low/mid liquidity band (inefficiency hunting — not top turnover)
        band = [
            u
            for u in universe
            if min_volume <= float(u.get("volume24h") or 0) <= max_volume
        ]
        # Prefer thinner names first (closer to min_volume), then higher relative activity
        band.sort(key=lambda u: float(u.get("volume24h") or 0))
        candidates = band[:limit_universe]

        results: list[dict[str, Any]] = []

        async def _one(row: dict[str, Any]) -> Optional[dict[str, Any]]:
            ex = row["exchange"]
            sym = row["symbol"]
            try:
                candles = await self.mde.get_candles(sym, timeframe, exchange=ex, limit=120)
                bars = [c.to_bar() for c in candles]
                oi_chg = 0.0
                try:
                    oi = await self.mde.get_adapter(ex).get_open_interest(sym)
                    if oi:
                        oi_chg = float(oi.get("oi_change_pct") or 0)
                except Exception:  # noqa: BLE001
                    pass
                analysis = self.hunter.analyze(
                    sym,
                    bars,
                    exchange=ex,
                    volume_24h=float(row.get("volume24h") or 0),
                    spread_pct=row.get("spread_pct"),
                    oi_change_pct=oi_chg,
                )
                if analysis["score"] < min_score:
                    return None
                return analysis
            except Exception as exc:  # noqa: BLE001
                logger.debug("hunter skip %s/%s: %s", ex, sym, exc)
                return None

        # Bound concurrency
        sem = asyncio.Semaphore(6)

        async def _guarded(row: dict[str, Any]):
            async with sem:
                return await _one(row)

        raw = await asyncio.gather(*[_guarded(r) for r in candidates[:analyze_top]])
        results = [r for r in raw if r]
        results.sort(key=lambda x: x["score"], reverse=True)

        if persist:
            await self._persist_candidates(results)

        if notify:
            for item in results[:3]:
                if item["score"] >= 90:
                    await send_telegram(_format_alert(item))

        return results

    async def _persist_candidates(self, results: list[dict[str, Any]]) -> None:
        try:
            from app.database.connection import SessionLocal
            from app.database.repositories import save_candidate

            async with SessionLocal() as db:
                for item in results:
                    await save_candidate(db, item)
        except Exception as exc:  # noqa: BLE001
            logger.debug("candidate persist skipped: %s", exc)


def _format_alert(item: dict[str, Any]) -> str:
    from app.notifications.templates.signal import format_early_opportunity

    return format_early_opportunity(item)
