"""Event bus MVP — Redis pub/sub. RabbitMQ optional for PRO.

События связывают Market → Scanner → SMC → AI → Notifications без жёсткой связки.
"""

from __future__ import annotations

import json
import logging
from enum import StrEnum
from typing import Any, Optional

logger = logging.getLogger(__name__)

CHANNEL = "smas:events"


class EventType(StrEnum):
    NEW_CANDLE = "NEW_CANDLE"
    VOLUME_SPIKE = "VOLUME_SPIKE"
    LIQUIDITY_SWEEP = "LIQUIDITY_SWEEP"
    NEW_SIGNAL = "NEW_SIGNAL"
    TRADE_OPENED = "TRADE_OPENED"
    TRADE_CLOSED = "TRADE_CLOSED"
    MODEL_UPDATED = "MODEL_UPDATED"
    CANDIDATE_READY = "CANDIDATE_READY"


def publish_event(event: EventType | str, payload: Optional[dict[str, Any]] = None) -> bool:
    try:
        from app.market_data.redis_cache import get_redis

        client = get_redis()
        if not client:
            return False
        body = {"event": str(event), **(payload or {})}
        client.publish(CHANNEL, json.dumps(body, default=str))
        return True
    except Exception as exc:  # noqa: BLE001
        logger.debug("event publish skipped: %s", exc)
        return False
