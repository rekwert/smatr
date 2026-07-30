"""Notify on inefficiency ENTRY READY (Telegram)."""

from __future__ import annotations

import logging
from typing import Any

from app.notifications.anti_spam import AntiSpam
from app.notifications.telegram import send_telegram
from app.notifications.templates.signal import format_inefficiency_ready

logger = logging.getLogger(__name__)

_spam = AntiSpam(cooldown_minutes=45)


async def maybe_alert_entry_ready(signal_row: dict[str, Any]) -> dict[str, Any]:
    """Send Telegram when inefficiency status is ENTRY READY / lifecycle ENTRY_READY."""
    status = str(signal_row.get("inefficiency_status") or "")
    life = str(signal_row.get("lifecycle_status") or "")
    ready = status == "INEFF_ENTRY_READY" or life == "ENTRY_READY"
    if not ready:
        return {"sent": False, "reason": "not_ready"}
    if not signal_row.get("inefficiency_qualifies", True):
        return {"sent": False, "reason": "not_qualified"}

    symbol = str(signal_row.get("symbol") or "")
    edge = int(signal_row.get("edge_score") or signal_row.get("score") or 0)
    if not _spam.allow(symbol, "ineff_entry_ready", edge):
        return {"sent": False, "reason": "antispam"}

    text = format_inefficiency_ready(signal_row)
    sent = await send_telegram(text)
    logger.info("inefficiency ENTRY READY alert %s sent=%s", symbol, sent)
    return {"sent": sent, "preview": text[:180]}
