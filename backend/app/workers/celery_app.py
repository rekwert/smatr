from __future__ import annotations

import asyncio
import logging

from celery import Celery

from app.config.settings import settings

logger = logging.getLogger(__name__)

celery_app = Celery("smas", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.timezone = "UTC"
celery_app.conf.imports = ("app.workers.celery_app",)
# Primary product feed = universe_scan (inefficiencies).
# scan_market (Bybit top-volume) is NOT on beat — only manual / «Все сигналы».
celery_app.conf.beat_schedule = {
    "universe-engine-v2": {
        "task": "app.workers.tasks.universe_scan",
        "schedule": 300.0,  # every 5 minutes — L1+L2 (+ optional heavy)
    },
    "ingest-market-history": {
        "task": "app.workers.tasks.ingest_market_history",
        "schedule": 600.0,  # every 10 minutes — candles + OI into Timescale
    },
}


def _run_async(coro):
    """Run coroutine in a fresh event loop; dispose async SQLAlchemy engine first.

    Celery prefork workers reuse the process: a global AsyncEngine bound to a
    previous loop causes "Future attached to a different loop".
    """

    async def _wrapped():
        from app.database.connection import engine

        await engine.dispose()
        try:
            return await coro
        finally:
            await engine.dispose()

    return asyncio.run(_wrapped())


@celery_app.task(name="app.workers.tasks.scan_market")
def scan_market(timeframe: str | None = None, limit: int | None = None):
    from app.database.connection import SessionLocal
    from app.services.scanner import ScannerService

    async def _inner():
        async with SessionLocal() as db:
            service = ScannerService()
            signals = await service.run_scan(
                db,
                timeframe=timeframe or settings.timeframe_list[0],
                limit=limit or settings.scan_symbol_limit,
            )
            return [s.id for s in signals]

    try:
        ids = _run_async(_inner())
        logger.info("scan_market created signals: %s", ids)
        return {"created": len(ids), "ids": ids}
    except Exception as exc:  # noqa: BLE001
        logger.exception("scan_market failed: %s", exc)
        return {"error": str(exc)}


@celery_app.task(name="app.workers.tasks.universe_scan")
def universe_scan(do_heavy: bool = True):
    """Market Universe Engine v2 — L1+L2+heavy every 5m; persists signals+candles when PG up."""
    from app.universe.engine import UniverseEngine

    async def _inner():
        return await UniverseEngine().run(
            cheap_limit=200,
            heavy_limit=40,
            trade_ideas=15,
            do_heavy=do_heavy,
        )

    try:
        result = _run_async(_inner())
        logger.info(
            "universe_scan L1=%s L2=%s L3=%s ideas=%s",
            result["levels"]["l1_universe"],
            result["levels"]["l2_cheap"],
            result["levels"]["l3_heavy"],
            result["levels"]["trade_ideas"],
        )
        return {
            "levels": result["levels"],
            "stats": result["stats"],
            "cross": len(result.get("cross_exchange") or []),
        }
    except Exception as exc:  # noqa: BLE001
        logger.exception("universe_scan failed: %s", exc)
        return {"error": str(exc)}


@celery_app.task(name="app.workers.tasks.ingest_market_history")
def ingest_market_history(per_exchange: int = 12):
    """Pull top symbols from all exchanges → market_candles + derivatives_data."""
    from app.database.connection import SessionLocal
    from app.services.history_ingest import ingest_top_history

    async def _inner():
        async with SessionLocal() as db:
            return await ingest_top_history(
                db,
                per_exchange=per_exchange,
                timeframes=["15", "60"],
                candle_limit=200,
            )

    try:
        result = _run_async(_inner())
        logger.info(
            "ingest_market_history candles=%s oi=%s symbols=%s errors=%s",
            result.get("candles_written"),
            result.get("derivatives_written"),
            result.get("symbols"),
            result.get("error_count"),
        )
        return result
    except Exception as exc:  # noqa: BLE001
        logger.exception("ingest_market_history failed: %s", exc)
        return {"error": str(exc)}


@celery_app.task(name="app.workers.tasks.run_backtest")
def run_backtest(payload: dict):
    # Placeholder worker for Part 3 Sprint 6
    logger.info("backtest requested: %s", payload)
    return {"status": "queued_skeleton", "payload": payload}
