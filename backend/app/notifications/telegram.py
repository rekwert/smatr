"""Telegram notification stub (Part 3 §9 / Part 4 alerts)."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config.settings import settings

logger = logging.getLogger(__name__)


async def send_telegram(text: str) -> bool:
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        logger.debug("Telegram not configured")
        return False
    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            url,
            json={"chat_id": settings.telegram_chat_id, "text": text, "parse_mode": "HTML"},
        )
    ok = resp.status_code == 200
    if not ok:
        logger.warning("Telegram send failed: %s", resp.text)
    return ok


def format_signal_alert(signal: dict[str, Any]) -> str:
    reasons = ", ".join((signal.get("reason") or {}).get("found") or [])
    return (
        f"🔥 <b>New setup</b>\n"
        f"{signal.get('symbol')} · Score {signal.get('score')}\n"
        f"TF {signal.get('timeframe')} · {signal.get('direction')}\n"
        f"{reasons}\n"
        f"RR {signal.get('risk_reward')}"
    )
