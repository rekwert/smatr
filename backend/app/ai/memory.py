"""Market / trader memory helpers (Part 5 §8)."""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import MarketMemory, Signal, TradeJournal, UserSettings


async def get_market_memory(db: AsyncSession, setup_key: str) -> Optional[dict[str, Any]]:
    row = (
        await db.execute(select(MarketMemory).where(MarketMemory.setup_key == setup_key))
    ).scalar_one_or_none()
    if not row:
        return None
    return {
        "setup_key": row.setup_key,
        "wins": row.wins,
        "losses": row.losses,
        "avg_rr": row.avg_rr,
        "stats": row.stats or {},
    }


async def upsert_market_memory(
    db: AsyncSession,
    setup_key: str,
    *,
    win: bool,
    rr: float,
) -> MarketMemory:
    row = (
        await db.execute(select(MarketMemory).where(MarketMemory.setup_key == setup_key))
    ).scalar_one_or_none()
    if row is None:
        row = MarketMemory(setup_key=setup_key, wins=0, losses=0, avg_rr=0.0, stats={})
        db.add(row)
    if win:
        row.wins += 1
    else:
        row.losses += 1
    total = row.wins + row.losses
    row.avg_rr = ((row.avg_rr or 0) * (total - 1) + rr) / total if total else rr
    await db.commit()
    await db.refresh(row)
    return row


async def get_trader_memory(db: AsyncSession, user_id: int) -> dict[str, Any]:
    trades = (
        await db.execute(
            select(TradeJournal)
            .where(TradeJournal.user_id == user_id)
            .order_by(desc(TradeJournal.created_at))
            .limit(100)
        )
    ).scalars().all()
    settings = (
        await db.execute(select(UserSettings).where(UserSettings.user_id == user_id))
    ).scalar_one_or_none()

    best: dict[str, list[float]] = {}
    worst: dict[str, list[float]] = {}
    for t in trades:
        key = t.setup or "unknown"
        best.setdefault(key, []).append(t.result_r or 0)
        worst.setdefault(key, []).append(t.result_r or 0)

    def avg(xs: list[float]) -> float:
        return sum(xs) / len(xs) if xs else 0.0

    ranked = sorted(((k, avg(v)) for k, v in best.items()), key=lambda x: x[1], reverse=True)
    return {
        "trades": len(trades),
        "best_setups": [{"setup": k, "avg_r": round(v, 2)} for k, v in ranked[:5] if v > 0],
        "worst_setups": [
            {"setup": k, "avg_r": round(v, 2)} for k, v in sorted(ranked, key=lambda x: x[1])[:5] if v <= 0
        ],
        "preferences": {
            "min_score": settings.min_score if settings else 90,
            "notify_smc": settings.notify_smc if settings else True,
            "notify_pumps": settings.notify_pumps if settings else True,
        }
        if True
        else {},
    }
