from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import BacktestOut
from app.backtesting.engine import BacktestEngine
from app.database.connection import get_db
from app.database.models import BacktestResult

router = APIRouter(prefix="/backtest", tags=["backtest"])


class BacktestRequest(BaseModel):
    strategy: Literal["smc", "pump", "sweep_fvg"] = "smc"
    symbol: str = "BTCUSDT"
    timeframe: str = "15"
    period: str = "recent"
    risk_pct: float = 1.0
    limit: int = Field(800, ge=100, le=3000)
    min_score: int = Field(75, ge=50, le=100)
    entry_model: Literal["aggressive", "conservative", "limit"] = "aggressive"


@router.post("/run")
async def run_backtest(payload: BacktestRequest, db: AsyncSession = Depends(get_db)):
    engine = BacktestEngine()
    result = await engine.run(
        db,
        symbol=payload.symbol,
        timeframe=payload.timeframe,
        strategy=payload.strategy,
        limit=payload.limit,
        min_score=payload.min_score,
        entry_model=payload.entry_model,
        risk_pct=payload.risk_pct,
    )
    metrics = result.get("metrics") or {}
    row = BacktestResult(
        strategy=payload.strategy,
        symbol=payload.symbol.upper(),
        period=payload.period,
        winrate=metrics.get("winrate"),
        profit_factor=metrics.get("profit_factor"),
        drawdown=metrics.get("max_drawdown_r"),
        trades=metrics.get("trades"),
        metrics=result,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return {
        "id": row.id,
        "strategy": row.strategy,
        "symbol": row.symbol,
        "period": row.period,
        "winrate": row.winrate,
        "profit_factor": row.profit_factor,
        "drawdown": row.drawdown,
        "trades": row.trades,
        "metrics": result,
    }


@router.get("/{result_id}", response_model=BacktestOut)
async def get_backtest(result_id: int, db: AsyncSession = Depends(get_db)):
    row = await db.get(BacktestResult, result_id)
    if not row:
        from fastapi import HTTPException

        raise HTTPException(404, detail="Not found")
    return BacktestOut(
        id=row.id,
        strategy=row.strategy,
        symbol=row.symbol,
        period=row.period,
        winrate=row.winrate,
        profit_factor=row.profit_factor,
        drawdown=row.drawdown,
        trades=row.trades,
        metrics=row.metrics or {},
    )
