from __future__ import annotations

import logging
import socket

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import desc, select

from app.api.schemas import ScannerTopOut
from app.api.signal_serialize import to_signal_out
from app.config.constants import DISCLAIMER
from app.database.connection import SessionLocal
from app.database.models import Signal
from app.exchange_layer.connectors import DEFAULT_EXCHANGES
from app.services import memory_store
from app.services.scanner import ScannerService
from app.universe.engine import UniverseEngine

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/scanner", tags=["scanner"])


def _pg_up() -> bool:
    try:
        with socket.create_connection(("127.0.0.1", 5433), timeout=0.4):
            return True
    except OSError:
        return False


@router.get("/top", response_model=ScannerTopOut)
async def scanner_top(
    min_score: int = Query(75, ge=0, le=100),
    limit: int = Query(20, ge=1, le=100),
):
    if _pg_up():
        try:
            async with SessionLocal() as db:
                smc = (
                    await db.execute(
                        select(Signal)
                        .where(Signal.status == "active", Signal.signal_type == "smc", Signal.score >= min_score)
                        .order_by(desc(Signal.score))
                        .limit(limit)
                    )
                ).scalars().all()
                pump = (
                    await db.execute(
                        select(Signal)
                        .where(Signal.status == "active", Signal.signal_type == "pump", Signal.score >= min_score)
                        .order_by(desc(Signal.score))
                        .limit(limit)
                    )
                ).scalars().all()
                if smc or pump:
                    return ScannerTopOut(
                        smc_setups=[to_signal_out(s) for s in smc],
                        pump_candidates=[to_signal_out(s) for s in pump],
                        disclaimer=DISCLAIMER,
                    )
        except Exception as exc:  # noqa: BLE001
            logger.warning("scanner/top DB unavailable: %s", exc)

    mem = memory_store.list_signals(min_score=min_score, limit=limit * 2)
    smc = [s for s in mem if s.get("signal_type") == "smc"][:limit]
    pump = [s for s in mem if s.get("signal_type") == "pump"][:limit]
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
    mode=all  → Market Universe: Bybit + OKX + Bitget + MEXC + BingX + KuCoin
    mode=bybit → legacy Bybit-only top volume scan
    """
    if mode == "bybit":
        return await _run_bybit_only(timeframe=timeframe, limit=limit)

    names = [x.strip().lower() for x in exchanges.split(",") if x.strip()]
    if not names:
        names = list(DEFAULT_EXCHANGES)

    # Scale heavy/ideas from limit (UI "топ N")
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

    mem = memory_store.list_signals(min_score=0, limit=trade_ideas * 2)
    pg = _pg_up()
    return {
        "created": len(result.get("trade_ideas") or []),
        "storage": "postgres+memory" if pg else "memory",
        "mode": "all",
        "exchanges": names,
        "levels": result.get("levels"),
        "stats": result.get("stats"),
        "signals": [to_signal_out(s).model_dump() for s in mem[:trade_ideas]],
        "disclaimer": DISCLAIMER,
        "note": (
            f"Скан по {len(names)} биржам: {', '.join(names)}. "
            "PostgreSQL недоступен — результаты в памяти до перезапуска API."
            if not pg
            else f"Скан по {len(names)} биржам: {', '.join(names)}. Сигналы пишутся в Postgres + память."
        ),
    }


async def _run_bybit_only(*, timeframe: str, limit: int) -> dict:
    service = ScannerService()

    if _pg_up():
        try:
            async with SessionLocal() as db:
                signals = await service.run_scan(db, timeframe=timeframe, limit=limit)
                return {
                    "created": len(signals),
                    "storage": "postgres",
                    "mode": "bybit",
                    "exchanges": ["bybit"],
                    "signals": [to_signal_out(s).model_dump() for s in signals],
                    "disclaimer": DISCLAIMER,
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
        "exchanges": ["bybit"],
        "signals": [to_signal_out(s).model_dump() for s in rows],
        "disclaimer": DISCLAIMER,
        "note": "PostgreSQL недоступен — результаты в памяти процесса (до перезапуска API).",
    }
