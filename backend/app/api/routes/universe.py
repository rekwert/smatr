"""Market Universe Engine v2 API."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.universe.engine import UniverseEngine
from app.universe.store import get_snapshot

router = APIRouter(prefix="/universe", tags=["universe"])


@router.get("/snapshot")
async def snapshot():
    snap = get_snapshot()
    return {
        **snap,
        "pipeline": "Market Universe Engine v2",
        "hint": "POST /api/v1/universe/run для полного прогона",
    }


@router.post("/run")
async def run_universe(
    cheap_limit: int = Query(200, ge=20, le=500),
    heavy_limit: int = Query(40, ge=5, le=150),
    trade_ideas: int = Query(15, ge=1, le=30),
    do_heavy: bool = Query(True),
    exchanges: str = Query("bybit,okx,bitget,mexc,bingx,kucoin"),
):
    """
    L1 ALL pairs → L2 cheap filter → L3 SMC+AI → trade ideas.
    Heavy analysis is slower; for quick L1+L2 set do_heavy=false.
    """
    names = [x.strip() for x in exchanges.split(",") if x.strip()]
    engine = UniverseEngine()
    result = await engine.run(
        exchanges=names,
        cheap_limit=cheap_limit,
        heavy_limit=heavy_limit,
        trade_ideas=trade_ideas,
        do_heavy=do_heavy,
    )
    return result


@router.get("/cross")
async def cross_only():
    snap = get_snapshot()
    return {
        "count": len(snap.get("cross") or []),
        "opportunities": snap.get("cross") or [],
    }


@router.get("/ideas")
async def ideas():
    snap = get_snapshot()
    return {
        "count": len(snap.get("trade_ideas") or []),
        "ideas": snap.get("trade_ideas") or [],
        "updated_at": snap.get("updated_at"),
    }
