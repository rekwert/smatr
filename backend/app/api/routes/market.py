from __future__ import annotations

import logging
import socket

from fastapi import APIRouter
from sqlalchemy import func, select

from app.api.schemas import MarketStatusOut
from app.database.connection import SessionLocal
from app.database.models import Signal
from app.engines.structure.analyzer import StructureAnalyzer
from app.exchanges.bybit import BybitClient
from app.services import memory_store

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/market", tags=["market"])


def _pg_up() -> bool:
    try:
        with socket.create_connection(("127.0.0.1", 5433), timeout=0.4):
            return True
    except OSError:
        return False


@router.get("/status", response_model=MarketStatusOut)
async def market_status():
    client = BybitClient()
    try:
        bars = await client.get_klines("BTCUSDT", timeframe="240", limit=120)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Bybit klines failed: %s", exc)
        bars = []

    structure = StructureAnalyzer()
    trend = "neutral"
    if bars:
        try:
            trend = structure.current_trend(structure.find_swings(bars))
        except Exception:  # noqa: BLE001
            trend = "neutral"

    if len(bars) >= 20:
        ranges = [(c.high - c.low) / c.close * 100 for c in bars[-20:]]
        avg = sum(ranges) / len(ranges)
        volatility = "high" if avg > 2.5 else "medium" if avg > 1.0 else "low"
    else:
        volatility = "medium"

    active = 0
    spikes = 0
    if _pg_up():
        try:
            async with SessionLocal() as db:
                active = (
                    await db.execute(select(func.count()).select_from(Signal).where(Signal.status == "active"))
                ).scalar_one()
                spikes = (
                    await db.execute(
                        select(func.count())
                        .select_from(Signal)
                        .where(Signal.status == "active", Signal.score >= 85)
                    )
                ).scalar_one()
        except Exception as exc:  # noqa: BLE001
            logger.warning("market/status DB error: %s", exc)

    if not active and not spikes:
        active, spikes = memory_store.counts()

    return MarketStatusOut(
        btc_trend=trend or "neutral",
        volatility=volatility,
        volume_spike_count=int(spikes or 0),
        active_signals=int(active or 0),
    )
