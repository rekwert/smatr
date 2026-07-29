"""Load candles for research (Part 6). Prefer DB, fallback Bybit."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Candle, Symbol
from app.exchanges.bybit import BybitClient
from app.market_data.candles import CandleBar
from app.market_data.validation import filter_valid


async def load_candles(
    db: AsyncSession,
    symbol: str,
    timeframe: str = "15",
    limit: int = 1000,
) -> list[CandleBar]:
    sym = (
        await db.execute(
            select(Symbol).where(Symbol.exchange == "bybit", Symbol.symbol == symbol.upper())
        )
    ).scalar_one_or_none()
    bars: list[CandleBar] = []
    if sym:
        rows = (
            await db.execute(
                select(Candle)
                .where(Candle.symbol_id == sym.id, Candle.timeframe == timeframe)
                .order_by(Candle.timestamp.desc())
                .limit(limit)
            )
        ).scalars().all()
        bars = [
            CandleBar(r.timestamp, r.open, r.high, r.low, r.close, r.volume)
            for r in reversed(rows)
        ]
    if len(bars) < 50:
        client = BybitClient()
        fetched: list[CandleBar] = []
        # paginate backwards for more history
        end: Optional[int] = None
        remaining = limit
        while remaining > 0:
            batch = min(1000, remaining)
            chunk = await client.get_klines(symbol.upper(), timeframe=timeframe, limit=batch, end=end)
            if not chunk:
                break
            fetched = chunk + fetched
            end = chunk[0].timestamp - 1
            remaining -= len(chunk)
            if len(chunk) < batch:
                break
        bars = filter_valid(fetched[-limit:])
    return bars
