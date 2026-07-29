from __future__ import annotations

import time

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, select

from app.database.connection import SessionLocal
from app.database.models import DerivativesData, MarketCandle, Signal
from app.exchanges.bybit import BybitClient
from app.market_data.orderbook import compute_orderbook_metrics
from app.market_data.redis_cache import get_redis
from app.market_data.symbol_discovery import SymbolDiscoveryService
from app.market_data.validation import validate_candle

router = APIRouter(prefix="/data", tags=["data"])


@router.get("/health")
async def data_health():
    client = BybitClient()
    t0 = time.perf_counter()
    status = "GOOD"
    latency_ms = None
    error = None
    try:
        bars = await client.get_klines("BTCUSDT", timeframe="15", limit=2)
        latency_ms = round((time.perf_counter() - t0) * 1000, 1)
        ok, reason = validate_candle(bars[-1]) if bars else (False, "no_bars")
        if not ok:
            status = "DEGRADED"
            error = reason
    except Exception as exc:  # noqa: BLE001
        status = "DOWN"
        error = str(exc)
        latency_ms = round((time.perf_counter() - t0) * 1000, 1)

    redis_ok = bool(get_redis())
    pg: dict = {"ok": False}
    try:
        async with SessionLocal() as db:
            candles = (await db.execute(select(func.count()).select_from(MarketCandle))).scalar_one()
            signals = (
                await db.execute(
                    select(func.count()).select_from(Signal).where(Signal.status == "active")
                )
            ).scalar_one()
            oi = (await db.execute(select(func.count()).select_from(DerivativesData))).scalar_one()
            pg = {
                "ok": True,
                "market_candles": int(candles or 0),
                "active_signals": int(signals or 0),
                "derivatives_rows": int(oi or 0),
            }
    except Exception as exc:  # noqa: BLE001
        pg = {"ok": False, "error": str(exc)}

    return {
        "exchange": "bybit",
        "status": status,
        "latency_ms": latency_ms,
        "redis": "ONLINE" if redis_ok else "OFFLINE",
        "postgres": pg,
        "missing_candles_est": "n/a",
        "error": error,
    }


@router.post("/history/ingest")
async def history_ingest(
    per_exchange: int = Query(10, ge=1, le=40),
    timeframes: str = Query("15,60"),
):
    """Bootstrap / refresh candle + OI history into Timescale."""
    from app.services.history_ingest import ingest_top_history

    tfs = [t.strip() for t in timeframes.split(",") if t.strip()]
    try:
        async with SessionLocal() as db:
            result = await ingest_top_history(
                db,
                per_exchange=per_exchange,
                timeframes=tfs or ["15"],
                candle_limit=200,
            )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(503, detail=f"Postgres недоступен или ingest failed: {exc}") from exc
    return result


@router.get("/history/stats")
async def history_stats():
    try:
        async with SessionLocal() as db:
            candles = (await db.execute(select(func.count()).select_from(MarketCandle))).scalar_one()
            by_ex = (
                await db.execute(
                    select(MarketCandle.exchange, func.count())
                    .group_by(MarketCandle.exchange)
                    .order_by(func.count().desc())
                )
            ).all()
            signals = (
                await db.execute(
                    select(func.count()).select_from(Signal).where(Signal.status == "active")
                )
            ).scalar_one()
            oi = (await db.execute(select(func.count()).select_from(DerivativesData))).scalar_one()
            oldest = (await db.execute(select(func.min(MarketCandle.time)))).scalar_one()
            newest = (await db.execute(select(func.max(MarketCandle.time)))).scalar_one()
            return {
                "market_candles": int(candles or 0),
                "by_exchange": {str(e): int(c) for e, c in by_ex},
                "active_signals": int(signals or 0),
                "derivatives_rows": int(oi or 0),
                "oldest_candle": oldest.isoformat() if oldest else None,
                "newest_candle": newest.isoformat() if newest else None,
                "history_enabled": True,
            }
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(503, detail=f"Postgres недоступен: {exc}") from exc


@router.get("/symbols")
async def discover_symbols(limit: int = Query(50, ge=1, le=500), min_volume: float = 1_000_000):
    svc = SymbolDiscoveryService(min_volume=min_volume)
    return {"symbols": await svc.discover(limit=limit)}


@router.get("/orderbook/{symbol}")
async def orderbook(symbol: str):
    client = BybitClient()
    book = await client.get_orderbook(symbol.upper())
    metrics = compute_orderbook_metrics(book)
    return {"book": book, "metrics": metrics}
