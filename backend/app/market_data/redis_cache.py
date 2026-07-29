"""Redis hot-cache — Part 14 §25 key schema."""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from app.config.settings import settings
from app.database.retention import REDIS_KEYS

logger = logging.getLogger(__name__)

_redis = None


def get_redis():
    global _redis
    if _redis is not None:
        return _redis
    try:
        import redis

        _redis = redis.Redis.from_url(settings.redis_url, decode_responses=True)
        _redis.ping()
        return _redis
    except Exception as exc:  # noqa: BLE001
        logger.debug("Redis unavailable: %s", exc)
        _redis = False
        return None


class RedisCache:
    @staticmethod
    def set_json(key: str, value: Any, ttl: int = 300) -> bool:
        client = get_redis()
        if not client:
            return False
        client.setex(key, ttl, json.dumps(value, default=str))
        return True

    @staticmethod
    def get_json(key: str) -> Optional[Any]:
        client = get_redis()
        if not client:
            return None
        raw = client.get(key)
        if not raw:
            return None
        return json.loads(raw)

    @staticmethod
    def price_key(exchange: str, symbol: str) -> str:
        return f"price:{exchange}:{symbol}"

    @staticmethod
    def ticker_key(exchange: str, symbol: str) -> str:
        return f"ticker:{exchange}:{symbol}"

    @staticmethod
    def orderbook_key(exchange: str, symbol: str) -> str:
        return f"orderbook:{exchange}:{symbol}"

    @staticmethod
    def candle_key(symbol: str, timeframe: str, exchange: str = "bybit") -> str:
        return f"candles:{exchange}:{symbol}:{timeframe}:last"

    @staticmethod
    def active_signals_key() -> str:
        return "signal:active"

    @staticmethod
    def scanner_queue_key() -> str:
        return "scanner:queue"

    @staticmethod
    def set_price(exchange: str, symbol: str, price: float, ttl: int = 60) -> bool:
        return RedisCache.set_json(RedisCache.price_key(exchange, symbol), {"price": price}, ttl=ttl)

    @staticmethod
    def set_active_signals(signals: list[dict], ttl: int = 120) -> bool:
        return RedisCache.set_json(RedisCache.active_signals_key(), signals, ttl=ttl)

    @staticmethod
    def key_templates() -> dict[str, str]:
        return dict(REDIS_KEYS)
