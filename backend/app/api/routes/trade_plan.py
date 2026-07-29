"""Part 11 Trade Plan API — works without Postgres (returns plan in-memory)."""

from __future__ import annotations

import logging
import socket
from typing import Literal, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import desc, select

from app.database.connection import SessionLocal
from app.database.models import TradePlan
from app.engines.hunter.analyzer import LowLiquidityHunter
from app.engines.pump_detector.analyzer import PumpDetector
from app.engines.scoring.calculator import ScoreCalculator
from app.exchange_layer.market_data_engine import MarketDataEngine
from app.strategy.engine import StrategyEngine

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/trade-plan", tags=["trade-plan"])


def _pg_up() -> bool:
    try:
        with socket.create_connection(("127.0.0.1", 5433), timeout=0.4):
            return True
    except OSError:
        return False


class CreatePlanIn(BaseModel):
    symbol: str = "BTCUSDT"
    exchange: str = "bybit"
    timeframe: str = "15m"
    account_balance: float = Field(10_000, gt=0)
    risk_profile: Literal["conservative", "normal", "aggressive"] = "normal"
    direction: Optional[str] = None


@router.post("/create")
async def create_plan(payload: CreatePlanIn):
    mde = MarketDataEngine([payload.exchange])
    try:
        candles = await mde.get_candles_as_bars(
            payload.symbol, payload.timeframe, exchange=payload.exchange, limit=150
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(400, detail=f"Не удалось загрузить свечи: {exc}") from exc

    smc = ScoreCalculator().analyze_symbol(payload.symbol, candles)
    pump = PumpDetector().analyze(candles)
    hunter = LowLiquidityHunter().analyze(
        payload.symbol,
        candles,
        exchange=payload.exchange,
        volume_24h=0,
    )
    plan = StrategyEngine().build_plan(
        payload.symbol,
        candles,
        direction=payload.direction,
        smc=smc,
        pump=pump,
        hunter=hunter,
        account_balance=payload.account_balance,
        risk_profile=payload.risk_profile,
        exchange=payload.exchange,
    )

    plan_id = None
    if _pg_up():
        try:
            async with SessionLocal() as db:
                row = TradePlan(
                    symbol=plan["symbol"],
                    exchange=payload.exchange,
                    direction=plan["direction"],
                    setup=plan["setup"],
                    entry={
                        "entry": plan["entry"],
                        "zone": plan["entry_zone"],
                        "model": plan["entry_model"],
                    },
                    stop=plan["stop_loss"],
                    targets=plan["targets"],
                    risk=plan["risk_pct"],
                    confidence=plan["confidence"],
                    risk_reward=plan["risk_reward"],
                    plan=plan,
                    status=plan["status"],
                )
                db.add(row)
                await db.commit()
                await db.refresh(row)
                plan_id = row.id
        except Exception as exc:  # noqa: BLE001
            logger.warning("trade-plan DB persist skipped: %s", exc)

    return {"id": plan_id, "storage": "postgres" if plan_id else "memory", **plan}


@router.get("")
async def list_plans(limit: int = 20):
    if not _pg_up():
        return []
    try:
        async with SessionLocal() as db:
            rows = (
                await db.execute(select(TradePlan).order_by(desc(TradePlan.created_at)).limit(limit))
            ).scalars().all()
            return [
                {
                    "id": r.id,
                    "symbol": r.symbol,
                    "direction": r.direction,
                    "setup": r.setup,
                    "confidence": r.confidence,
                    "risk_reward": r.risk_reward,
                    "status": r.status,
                    "created_at": r.created_at,
                }
                for r in rows
            ]
    except Exception as exc:  # noqa: BLE001
        logger.warning("list plans without DB: %s", exc)
        return []


@router.get("/{plan_id}")
async def get_plan(plan_id: int):
    if not _pg_up():
        raise HTTPException(503, detail="Postgres недоступен")
    try:
        async with SessionLocal() as db:
            row = await db.get(TradePlan, plan_id)
            if not row:
                raise HTTPException(404, detail="План не найден")
            return {"id": row.id, **(row.plan or {})}
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(503, detail=str(exc)) from exc
