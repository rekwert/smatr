"""Notification manager with priority tiers (Part 8 §2–3)."""

from __future__ import annotations

import logging
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import settings
from app.database.models import NotificationLog, Signal
from app.notifications.anti_spam import AntiSpam
from app.notifications.telegram import format_signal_alert, send_telegram
from app.notifications.templates.signal import format_pump_alert, format_smc_signal

logger = logging.getLogger(__name__)


def priority_for_score(score: int) -> str:
    if score >= 95:
        return "elite"
    if score >= 90:
        return "high"
    if score >= 80:
        return "medium"
    if score >= 70:
        return "low"
    return "ignore"


class NotificationManager:
    def __init__(self):
        self.anti_spam = AntiSpam(cooldown_minutes=getattr(settings, "notify_cooldown_minutes", 30))

    async def handle_signal(
        self,
        db: AsyncSession,
        signal: Signal,
        *,
        prev_score: Optional[int] = None,
        force: bool = False,
    ) -> dict[str, Any]:
        priority = priority_for_score(signal.score)
        if priority in ("ignore", "low") and not force:
            return {"sent": False, "reason": f"priority_{priority}"}

        if priority == "medium" and not force:
            # app-only: log without telegram
            db.add(
                NotificationLog(
                    signal_id=signal.id,
                    channel="app",
                    type="new_setup",
                    status="stored",
                    payload={"score": signal.score, "priority": priority},
                )
            )
            await db.commit()
            return {"sent": False, "reason": "app_only", "priority": priority}

        if not force and not self.anti_spam.allow(
            signal.symbol, signal.signal_type, signal.score, prev_score=prev_score
        ):
            return {"sent": False, "reason": "antispam"}

        payload = {
            "symbol": signal.symbol,
            "direction": signal.direction,
            "score": signal.score,
            "timeframe": signal.timeframe,
            "entry": signal.entry,
            "stop": signal.stop,
            "target": signal.target,
            "risk_reward": signal.risk_reward,
            "reason": signal.reason or {},
            "explanation": (signal.explanation or "")[:500],
        }
        if signal.signal_type == "pump":
            text = format_pump_alert(payload)
        else:
            text = format_smc_signal(payload)

        sent = await send_telegram(text)
        db.add(
            NotificationLog(
                signal_id=signal.id,
                channel="telegram",
                type="pump_alert" if signal.signal_type == "pump" else "new_setup",
                status="sent" if sent else "failed",
                payload={"priority": priority, "score": signal.score},
            )
        )
        await db.commit()
        return {"sent": sent, "priority": priority, "preview": text[:200]}
