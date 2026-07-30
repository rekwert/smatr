from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import desc, select

from app.api.schemas import ScannerTopOut
from app.api.signal_serialize import to_signal_out
from app.config.constants import DISCLAIMER
from app.database.connection import SessionLocal
from app.database.models import Signal
from app.database.pg_health import pg_up
from app.exchange_layer.connectors import DEFAULT_EXCHANGES
from app.services import memory_store
from app.services.inefficiency_feed import FEED_INEFFICIENCY, filter_and_sort
from app.services.scanner import ScannerService
from app.universe.engine import UniverseEngine

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/scanner", tags=["scanner"])


@router.get("/top", response_model=ScannerTopOut)
async def scanner_top(
    min_score: int = Query(0, ge=0, le=100),
    limit: int = Query(20, ge=1, le=100),
    feed: str = Query(FEED_INEFFICIENCY, pattern="^(inefficiency|volume_scan|all)$"),
):
    raw: list[dict[str, Any]] = []
    if pg_up():
        try:
            async with SessionLocal() as db:
                rows = (
                    await db.execute(
                        select(Signal)
                        .where(Signal.status == "active")
                        .order_by(desc(Signal.score))
                        .limit(max(limit * 8, 120))
                    )
                ).scalars().all()
                raw = [to_signal_out(r).model_dump() for r in rows]
        except Exception as exc:  # noqa: BLE001
            logger.warning("scanner/top DB unavailable: %s", exc)

    if not raw:
        raw = [
            to_signal_out(s).model_dump()
            for s in memory_store.list_signals(min_score=0, limit=max(limit * 8, 120))
        ]

    ranked = filter_and_sort(raw, feed=feed, min_score=min_score, limit=limit * 2)
    smc = [s for s in ranked if s.get("signal_type") == "smc"][:limit]
    pump = [s for s in ranked if s.get("signal_type") == "pump"][:limit]
    # Default inefficiency feed: de-emphasize pump noise unless explicitly all/volume
    if feed == FEED_INEFFICIENCY:
        pump = []
    return ScannerTopOut(
        smc_setups=[to_signal_out(s) for s in smc],
        pump_candidates=[to_signal_out(s) for s in pump],
        disclaimer=DISCLAIMER,
    )


@router.post("/run")
async def run_scanner(
    timeframe: str = Query("15"),
    limit: int = Query(15, ge=1, le=100),
    mode: str = Query("all", pattern="^(all|bybit)$"),
    exchanges: str = Query(",".join(DEFAULT_EXCHANGES)),
):
    """
    Manual scan.
    mode=all  → Universe inefficiency feed (6 exchanges, structure gate)
    mode=bybit → legacy Bybit top-volume (tagged volume_scan, not main feed)
    """
    if mode == "bybit":
        return await _run_bybit_only(timeframe=timeframe, limit=limit)

    names = [x.strip().lower() for x in exchanges.split(",") if x.strip()]
    if not names:
        names = list(DEFAULT_EXCHANGES)

    trade_ideas = max(5, min(30, limit))
    heavy_limit = max(trade_ideas, min(80, limit * 2))
    cheap_limit = max(80, min(250, heavy_limit * 4))

    try:
        result = await UniverseEngine().run(
            exchanges=names,
            cheap_limit=cheap_limit,
            heavy_limit=heavy_limit,
            trade_ideas=trade_ideas,
            do_heavy=True,
            persist_memory=True,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Multi-exchange universe scan failed: %s", exc)
        raise HTTPException(
            503,
            detail=f"Не удалось просканировать биржи: {exc}. Проверьте сеть/прокси.",
        ) from exc

    mem = memory_store.list_signals(min_score=0, limit=trade_ideas * 4)
    ranked = filter_and_sort(mem, feed=FEED_INEFFICIENCY, min_score=0, limit=trade_ideas)
    pg = pg_up()
    return {
        "created": len(result.get("trade_ideas") or []),
        "feed_shown": len(ranked),
        "storage": "postgres+memory" if pg else "memory",
        "mode": "all",
        "feed": FEED_INEFFICIENCY,
        "exchanges": names,
        "levels": result.get("levels"),
        "stats": result.get("stats"),
        "signals": [to_signal_out(s).model_dump() for s in ranked],
        "disclaimer": DISCLAIMER,
        "note": (
            f"Неэффективности · {len(names)} бирж. Гейт: Sweep+FVG+OB, сортировка Edge→Exec→Setup."
            + (
                " PostgreSQL недоступен — память процесса."
                if not pg
                else " Сигналы в Postgres + память."
            )
        ),
    }


async def _run_bybit_only(*, timeframe: str, limit: int) -> dict:
    service = ScannerService()

    if pg_up():
        try:
            async with SessionLocal() as db:
                signals = await service.run_scan(db, timeframe=timeframe, limit=limit)
                return {
                    "created": len(signals),
                    "storage": "postgres",
                    "mode": "bybit",
                    "feed": "volume_scan",
                    "exchanges": ["bybit"],
                    "signals": [to_signal_out(s).model_dump() for s in signals],
                    "disclaimer": DISCLAIMER,
                    "note": "Режим «Все сигналы» (Bybit top volume) — не основной inefficiency feed.",
                }
        except Exception as exc:  # noqa: BLE001
            logger.warning("DB scan failed, using memory: %s", exc)

    try:
        rows = await service.run_scan_memory(timeframe=timeframe, limit=limit)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Memory scan failed: %s", exc)
        raise HTTPException(
            503,
            detail=f"Не удалось связаться с Bybit: {exc}. Проверьте сеть/прокси.",
        ) from exc
    return {
        "created": len(rows),
        "storage": "memory",
        "mode": "bybit",
        "feed": "volume_scan",
        "exchanges": ["bybit"],
        "signals": [to_signal_out(s).model_dump() for s in rows],
        "disclaimer": DISCLAIMER,
        "note": "Режим «Все сигналы» (Bybit). Основной фид — inefficiency через mode=all.",
    }
