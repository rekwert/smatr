from __future__ import annotations

import logging
import socket
from types import SimpleNamespace
from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.ai.engine import AIEngine
from app.ai.memory import get_trader_memory
from app.database.connection import SessionLocal
from app.database.models import Signal
from app.services import memory_store

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ai", tags=["ai"])
engine = AIEngine()


class ExplainIn(BaseModel):
    signal_id: int
    mode: Literal["explain", "plan", "similar", "market"] = "explain"


class MarketIn(BaseModel):
    symbol: str = "BTCUSDT"


class ReviewIn(BaseModel):
    user_id: int = 1


def _pg_up() -> bool:
    try:
        with socket.create_connection(("127.0.0.1", 5433), timeout=0.4):
            return True
    except OSError:
        return False


def _as_signal(row: dict[str, Any]) -> SimpleNamespace:
    return SimpleNamespace(
        id=row.get("id"),
        symbol=row.get("symbol"),
        direction=row.get("direction"),
        signal_type=row.get("signal_type"),
        score=row.get("score"),
        timeframe=row.get("timeframe"),
        entry=row.get("entry"),
        stop=row.get("stop"),
        target=row.get("target"),
        risk_reward=row.get("risk_reward"),
        risk_pct=row.get("risk_pct"),
        reason=row.get("reason") or {},
        zones=row.get("zones") or {},
        explanation=row.get("explanation"),
        status=row.get("status") or "active",
    )


async def _explain_by_id(signal_id: int, mode: str) -> dict[str, Any]:
    if _pg_up():
        try:
            async with SessionLocal() as db:
                row = await db.get(Signal, signal_id)
                if row:
                    return await engine.explain_signal(db, row, mode=mode)
        except Exception as exc:  # noqa: BLE001
            logger.warning("ai explain without DB: %s", exc)

    mem = memory_store.get_signal(signal_id)
    if not mem:
        raise HTTPException(404, detail="Сигнал не найден")
    return await engine.explain_signal(None, _as_signal(mem), mode=mode)


@router.post("/explain")
async def explain(payload: ExplainIn):
    return await _explain_by_id(payload.signal_id, payload.mode)


@router.post("/market-analysis")
async def market_analysis(payload: MarketIn):
    if _pg_up():
        try:
            async with SessionLocal() as db:
                return await engine.market_analysis(db, symbol=payload.symbol)
        except Exception as exc:  # noqa: BLE001
            logger.warning("ai market-analysis without DB: %s", exc)
    return await engine.market_analysis(None, symbol=payload.symbol)


@router.post("/review")
async def review(payload: ReviewIn):
    memory: dict[str, Any] = {"trades": 0, "best_setups": [], "worst_setups": []}
    if _pg_up():
        try:
            async with SessionLocal() as db:
                memory = await get_trader_memory(db, payload.user_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning("ai review without DB: %s", exc)
    return {
        "summary": f"Проанализировано сделок: {memory.get('trades', 0)}",
        "strengths": [f"{x['setup']} avg {x['avg_r']}R" for x in memory.get("best_setups", [])],
        "risks": [f"{x['setup']} avg {x['avg_r']}R" for x in memory.get("worst_setups", [])],
        "scenario": {"type": "COACH", "conditions": ["Ведите журнал", "Фокус на лучших сетапах"]},
        "confidence": 70 if memory.get("trades") else 40,
        "explanation": (
            "Коучинг строится на журнале сделок пользователя. "
            "При пустом журнале рекомендации общие."
        ),
        "trader_memory": memory,
    }


@router.get("/scanner-assistant")
async def scanner_assistant(min_score: int = 85):
    if _pg_up():
        try:
            async with SessionLocal() as db:
                return await engine.scanner_assistant(db, min_score=min_score)
        except Exception as exc:  # noqa: BLE001
            logger.warning("ai scanner-assistant without DB: %s", exc)
    return await engine.scanner_assistant(None, min_score=min_score)


@router.post("/plan")
async def plan(payload: ExplainIn):
    return await _explain_by_id(payload.signal_id, "plan")
