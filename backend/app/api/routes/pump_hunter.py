"""Part 10 Low Liquidity Hunter API."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.engines.hunter.service import PumpHunterService
from app.notifications.templates.signal import format_pump_alert

router = APIRouter(prefix="/pump-hunter", tags=["pump-hunter"])


@router.get("")
async def pump_hunter(
    min_volume: float = Query(5_000_000, ge=0),
    max_volume: float = Query(150_000_000, ge=0),
    analyze_top: int = Query(15, ge=1, le=40),
    min_score: int = Query(70, ge=0, le=100),
    exchanges: str = Query("bybit,okx,bitget,mexc"),
    notify: bool = False,
):
    names = [x.strip() for x in exchanges.split(",") if x.strip()]
    svc = PumpHunterService(names)
    rows = await svc.run(
        min_volume=min_volume,
        max_volume=max_volume,
        analyze_top=analyze_top,
        min_score=min_score,
        notify=notify,
    )
    return {
        "count": len(rows),
        "candidates": rows,
        "disclaimer": "Early-stage analytical candidates. High risk. Not trade recommendations.",
    }


@router.get("/statuses")
async def statuses():
    return {
        "SLEEPING": "50-70 observe",
        "PREPARING": "70-85 accumulation signs",
        "READY": "85-95 possible start",
        "ACTIVE": "95+ move underway",
    }
