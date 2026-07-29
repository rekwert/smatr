"""Repositories for Part 14 market / AI persistence."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional, Sequence

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import (
    Candidate,
    MarketCandle,
    SmartMoneyEvent,
    SystemLog,
    TrainingSample,
)
from app.exchange_layer.base.models import UnifiedCandle
from app.market_data.candles import CandleBar


def _ms_to_dt(ts_ms: int) -> datetime:
    return datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)


async def upsert_market_candles(
    db: AsyncSession,
    candles: Sequence[UnifiedCandle] | Sequence[CandleBar],
    *,
    exchange: str,
    symbol: str,
    timeframe: str,
) -> int:
    count = 0
    for c in candles:
        if isinstance(c, UnifiedCandle):
            exchange_n, symbol_n, tf = c.exchange, c.symbol, c.timeframe
            ts = c.timestamp
            o, h, l, cl, v = c.open, c.high, c.low, c.close, c.volume
        else:
            exchange_n, symbol_n, tf = exchange, symbol, timeframe
            ts = c.timestamp
            o, h, l, cl, v = c.open, c.high, c.low, c.close, c.volume
        stmt = (
            pg_insert(MarketCandle)
            .values(
                time=_ms_to_dt(int(ts)),
                exchange=exchange_n.lower(),
                symbol=symbol_n.upper(),
                timeframe=tf,
                open=o,
                high=h,
                low=l,
                close=cl,
                volume=v,
            )
            .on_conflict_do_update(
                constraint="uq_market_candle",
                set_={"open": o, "high": h, "low": l, "close": cl, "volume": v},
            )
        )
        await db.execute(stmt)
        count += 1
    await db.commit()
    return count


async def save_candidate(db: AsyncSession, row: dict[str, Any]) -> Candidate:
    import time

    comps = row.get("components") or {}
    cand = Candidate(
        symbol=row["symbol"],
        exchange=row.get("exchange", "bybit"),
        liquidity_score=comps.get("liquidity_score"),
        pump_score=float(row.get("score") or 0),
        accumulation_score=comps.get("accumulation"),
        quality=float(row.get("quality") or 0) if row.get("quality") is not None else None,
        status=row.get("status", "SLEEPING"),
        reasons={"found": row.get("reasons") or [], "red_flags": row.get("red_flags") or []},
        timestamp=int(time.time() * 1000),
    )
    db.add(cand)
    await db.commit()
    await db.refresh(cand)
    return cand


async def save_smart_money_event(
    db: AsyncSession,
    *,
    symbol: str,
    event_type: str,
    strength: float | None = None,
    metadata: Optional[dict] = None,
    exchange: str = "bybit",
    timestamp_ms: Optional[int] = None,
) -> SmartMoneyEvent:
    import time

    ev = SmartMoneyEvent(
        exchange=exchange,
        symbol=symbol.upper(),
        event_type=event_type,
        strength=strength,
        event_metadata=metadata or {},
        timestamp=timestamp_ms or int(time.time() * 1000),
    )
    db.add(ev)
    await db.commit()
    await db.refresh(ev)
    return ev


async def save_training_sample(
    db: AsyncSession,
    *,
    symbol: str,
    features: dict,
    label: str,
    future_result: Optional[dict] = None,
    exchange: str = "bybit",
) -> TrainingSample:
    row = TrainingSample(
        symbol=symbol.upper(),
        exchange=exchange,
        features=features,
        label=label,
        future_result=future_result or {},
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def log_system(
    db: AsyncSession,
    service: str,
    message: str,
    level: str = "INFO",
    meta: Optional[dict] = None,
) -> None:
    db.add(SystemLog(service=service, level=level, message=message, meta=meta or {}))
    await db.commit()
