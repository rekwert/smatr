from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.connection import get_db
from app.database.models import SignalFeedback, UserSettings

router = APIRouter(prefix="/notifications", tags=["notifications"])


class FeedbackIn(BaseModel):
    signal_id: int
    vote: Literal["up", "down", "skip"]
    user_id: Optional[int] = None
    telegram_id: Optional[int] = None


class SettingsIn(BaseModel):
    user_id: int = 1
    telegram_id: Optional[int] = None
    min_score: int = 90
    risk_level: str = "medium"
    max_positions: int = 5
    daily_loss_limit: float = 3.0
    telegram_enabled: bool = False
    notify_pumps: bool = True
    notify_smc: bool = True
    notify_breakouts: bool = False
    cooldown_minutes: int = 30


@router.post("/feedback")
async def feedback(payload: FeedbackIn, db: AsyncSession = Depends(get_db)):
    row = SignalFeedback(
        user_id=payload.user_id,
        signal_id=payload.signal_id,
        vote=payload.vote,
    )
    db.add(row)
    await db.commit()
    return {"ok": True}


@router.get("/settings/{user_id}")
async def get_settings(user_id: int, db: AsyncSession = Depends(get_db)):
    row = (
        await db.execute(select(UserSettings).where(UserSettings.user_id == user_id))
    ).scalar_one_or_none()
    if not row:
        return SettingsIn(user_id=user_id).model_dump()
    return {
        "user_id": row.user_id,
        "telegram_id": row.telegram_id,
        "min_score": row.min_score,
        "risk_level": row.risk_level,
        "max_positions": row.max_positions,
        "daily_loss_limit": row.daily_loss_limit,
        "telegram_enabled": row.telegram_enabled,
        "notify_pumps": row.notify_pumps,
        "notify_smc": row.notify_smc,
        "notify_breakouts": row.notify_breakouts,
        "cooldown_minutes": row.cooldown_minutes,
    }


@router.put("/settings")
async def put_settings(payload: SettingsIn, db: AsyncSession = Depends(get_db)):
    row = (
        await db.execute(select(UserSettings).where(UserSettings.user_id == payload.user_id))
    ).scalar_one_or_none()
    if row is None:
        row = UserSettings(user_id=payload.user_id)
        db.add(row)
    row.telegram_id = payload.telegram_id
    row.min_score = payload.min_score
    row.risk_level = payload.risk_level
    row.max_positions = payload.max_positions
    row.daily_loss_limit = payload.daily_loss_limit
    row.telegram_enabled = payload.telegram_enabled
    row.notify_pumps = payload.notify_pumps
    row.notify_smc = payload.notify_smc
    row.notify_breakouts = payload.notify_breakouts
    row.cooldown_minutes = payload.cooldown_minutes
    await db.commit()
    return {"ok": True}
