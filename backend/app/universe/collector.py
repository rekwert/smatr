"""Level 1 — collect ALL USDT perpetual tickers from 6 exchanges."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Optional

from app.exchange_layer.connectors import create_exchanges
from app.exchange_layer.normalizer.symbols import normalize_symbol
from app.exchange_layer.scanners import liquidity_score
from app.universe.models import DEFAULT_EXCLUDE, UniverseRow

logger = logging.getLogger(__name__)


async def collect_universe(
    exchanges: Optional[list[str]] = None,
    *,
    concurrency: int = 6,
) -> list[UniverseRow]:
    """Fetch tickers in parallel from all enabled exchanges."""
    adapters = create_exchanges(exchanges)
    sem = asyncio.Semaphore(concurrency)
    rows: list[UniverseRow] = []
    now_ms = int(time.time() * 1000)

    async def _one(adapter) -> list[UniverseRow]:
        async with sem:
            out: list[UniverseRow] = []
            try:
                tickers = await adapter.get_tickers()
            except Exception as exc:  # noqa: BLE001
                logger.warning("universe collect %s failed: %s", adapter.name, exc)
                return out

            listed_map: dict[str, Optional[int]] = {}
            try:
                symbols = await adapter.get_symbols()
                for s in symbols:
                    listed_map[normalize_symbol(s.symbol)] = s.listed_at
            except Exception:  # noqa: BLE001
                pass

            for t in tickers:
                sym = normalize_symbol(t.symbol)
                if not sym.endswith("USDT"):
                    continue
                if t.last_price <= 0:
                    continue
                spread = None
                if t.bid and t.ask and t.last_price:
                    spread = (t.ask - t.bid) / t.last_price * 100
                listed_at = listed_map.get(sym)
                age_days = None
                if listed_at and listed_at > 0:
                    age_days = max(0.0, (now_ms - listed_at) / 86_400_000)

                liq = liquidity_score(
                    float(t.volume_24h or 0),
                    spread_pct=spread,
                )
                out.append(
                    UniverseRow(
                        exchange=adapter.name,
                        symbol=sym,
                        raw_symbol=t.symbol,
                        price=float(t.last_price or 0),
                        volume_24h=float(t.volume_24h or 0),
                        change_pct_24h=t.change_pct_24h,
                        bid=t.bid,
                        ask=t.ask,
                        spread_pct=spread,
                        open_interest=t.open_interest,
                        funding_rate=t.funding_rate,
                        listed_at=listed_at,
                        age_days=age_days,
                        liquidity_score=liq,
                    )
                )
            logger.info("universe %s: %d USDT perps", adapter.name, len(out))
            return out

    chunks = await asyncio.gather(*[_one(a) for a in adapters])
    for chunk in chunks:
        rows.extend(chunk)
    return rows


def universe_stats(rows: list[UniverseRow]) -> dict:
    by_ex: dict[str, int] = {}
    for r in rows:
        by_ex[r.exchange] = by_ex.get(r.exchange, 0) + 1
    return {
        "total": len(rows),
        "by_exchange": by_ex,
        "unique_symbols": len({r.symbol for r in rows}),
        "excluded_majors_policy": sorted(DEFAULT_EXCLUDE),
    }
