"""Journal API — manual trade log for inefficiency WinRate."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.services import journal as journal_svc

router = APIRouter(prefix="/journal", tags=["journal"])


class JournalCreateIn(BaseModel):
    symbol: str
    direction: str = Field(pattern="^(LONG|SHORT)$")
    entry_price: Optional[float] = None
    exit_price: Optional[float] = None
    result: str = Field(default="open", pattern="^(win|loss|be|open)$")
    result_r: Optional[float] = None
    signal_id: Optional[int] = None
    exchange: str = "bybit"
    setup: str = "inefficiency"
    notes: Optional[str] = None
    inefficiency_type: Optional[str] = None
    edge_score: Optional[int] = None


@router.get("")
async def list_journal(
    limit: int = Query(50, ge=1, le=200),
    setup: Optional[str] = Query("inefficiency"),
) -> list[dict[str, Any]]:
    return await journal_svc.list_trades(limit=limit, setup=setup)


@router.get("/stats")
async def journal_stats(setup: str = Query("inefficiency")) -> dict[str, Any]:
    return await journal_svc.journal_stats(setup=setup)


@router.post("")
async def create_journal_entry(body: JournalCreateIn) -> dict[str, Any]:
    return await journal_svc.create_trade(**body.model_dump())
