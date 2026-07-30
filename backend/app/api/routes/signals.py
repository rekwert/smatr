from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, Query
from sqlalchemy import desc, select

from app.api.schemas import SignalOut
from app.api.signal_serialize import to_signal_out
from app.config.constants import DISCLAIMER
from app.database.connection import SessionLocal
from app.database.models import Signal
from app.database.pg_health import pg_up
from app.services import memory_store
from app.services.inefficiency_feed import (
    FEED_ALL,
    FEED_INEFFICIENCY,
    FEED_VOLUME_SCAN,
    filter_and_sort,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/signals", tags=["signals"])


def _orm_to_dict(row: Signal) -> dict[str, Any]:
    return to_signal_out(row).model_dump()


@router.get("", response_model=list[SignalOut])
async def list_signals(
    min_score: int = Query(0, ge=0, le=100),
    signal_type: Optional[str] = Query(None, pattern="^(smc|pump)$"),
    timeframe: Optional[str] = None,
    feed: str = Query(
        FEED_INEFFICIENCY,
        pattern="^(inefficiency|volume_scan|all)$",
        description="inefficiency=default product feed; volume_scan=legacy top-volume; all=no gate",
    ),
    limit: int = Query(50, ge=1, le=200),
):
    raw: list[dict[str, Any]] = []
    if pg_up():
        try:
            async with SessionLocal() as db:
                q = select(Signal).where(Signal.status == "active")
                if signal_type:
                    q = q.where(Signal.signal_type == signal_type)
                if timeframe:
                    q = q.where(Signal.timeframe == timeframe)
                # Pull wider then filter/sort in Python (Edge/Exec live in JSONB)
                q = q.order_by(desc(Signal.score), desc(Signal.created_at)).limit(max(limit * 6, 100))
                rows = (await db.execute(q)).scalars().all()
                raw = [_orm_to_dict(r) for r in rows]
        except Exception as exc:  # noqa: BLE001
            logger.warning("signals list without DB: %s", exc)

    if not raw:
        raw = [
            to_signal_out(s).model_dump()
            for s in memory_store.list_signals(min_score=0, signal_type=signal_type, limit=max(limit * 6, 100))
        ]

    filtered = filter_and_sort(raw, feed=feed, min_score=min_score, limit=limit)
    return [SignalOut.model_validate(r) for r in filtered]


@router.get("/{signal_id}", response_model=SignalOut)
async def get_signal(signal_id: int):
    if pg_up():
        try:
            async with SessionLocal() as db:
                row = await db.get(Signal, signal_id)
                if row:
                    return to_signal_out(row)
        except Exception as exc:  # noqa: BLE001
            logger.warning("signal get without DB: %s", exc)

    mem = memory_store.get_signal(signal_id)
    if mem:
        return to_signal_out(mem)
    from fastapi import HTTPException

    raise HTTPException(404, detail="Сигнал не найден")


@router.get("/meta/disclaimer")
async def disclaimer():
    return {
        "disclaimer": DISCLAIMER,
        "feeds": {
            FEED_INEFFICIENCY: "Неэффективности: Sweep+FVG+OB, сортировка Edge→Exec→Setup",
            FEED_VOLUME_SCAN: "Все сигналы (volume scan) — отдельный режим",
            FEED_ALL: "Без гейта структуры",
        },
    }
