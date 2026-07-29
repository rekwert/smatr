from __future__ import annotations

import logging
import socket
from typing import Optional

from fastapi import APIRouter, Query
from sqlalchemy import desc, select

from app.api.schemas import SignalOut
from app.api.signal_serialize import to_signal_out
from app.config.constants import DISCLAIMER
from app.database.connection import SessionLocal
from app.database.models import Signal
from app.services import memory_store

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/signals", tags=["signals"])


def _pg_up() -> bool:
    try:
        with socket.create_connection(("127.0.0.1", 5433), timeout=0.4):
            return True
    except OSError:
        return False


@router.get("", response_model=list[SignalOut])
async def list_signals(
    min_score: int = Query(50, ge=0, le=100),
    signal_type: Optional[str] = Query(None, pattern="^(smc|pump)$"),
    timeframe: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
):
    if _pg_up():
        try:
            async with SessionLocal() as db:
                q = select(Signal).where(Signal.status == "active", Signal.score >= min_score)
                if signal_type:
                    q = q.where(Signal.signal_type == signal_type)
                if timeframe:
                    q = q.where(Signal.timeframe == timeframe)
                q = q.order_by(desc(Signal.score), desc(Signal.created_at)).limit(limit)
                rows = (await db.execute(q)).scalars().all()
                if rows:
                    return [to_signal_out(r) for r in rows]
        except Exception as exc:  # noqa: BLE001
            logger.warning("signals list without DB: %s", exc)

    return [
        to_signal_out(s)
        for s in memory_store.list_signals(min_score=min_score, signal_type=signal_type, limit=limit)
    ]


@router.get("/{signal_id}", response_model=SignalOut)
async def get_signal(signal_id: int):
    if _pg_up():
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
    return {"disclaimer": DISCLAIMER}
