"""Anti-spam / cooldown for alerts (Part 8 §9)."""

from __future__ import annotations

import time
from typing import Optional

from app.market_data.redis_cache import get_redis


class AntiSpam:
    def __init__(self, cooldown_minutes: int = 30):
        self.cooldown_minutes = cooldown_minutes
        self._local: dict[str, tuple[float, int]] = {}

    def _key(self, symbol: str, signal_type: str) -> str:
        return f"notify:{symbol}:{signal_type}"

    def allow(self, symbol: str, signal_type: str, score: int, prev_score: Optional[int] = None) -> bool:
        # Upgrade-only exception
        if prev_score is not None and score >= prev_score + 8 and score >= 90:
            return True

        key = self._key(symbol, signal_type)
        now = time.time()
        client = get_redis()
        if client:
            raw = client.get(key)
            if raw:
                try:
                    last_ts, last_score = raw.split(":")
                    last_ts_f = float(last_ts)
                    last_score_i = int(last_score)
                    if now - last_ts_f < self.cooldown_minutes * 60:
                        # allow only meaningful upgrade
                        if score < last_score_i + 8:
                            return False
                except ValueError:
                    pass
            client.setex(key, self.cooldown_minutes * 60, f"{now}:{score}")
            return True

        # in-memory fallback
        prev = self._local.get(key)
        if prev:
            last_ts, last_score = prev
            if now - last_ts < self.cooldown_minutes * 60 and score < last_score + 8:
                return False
        self._local[key] = (now, score)
        return True
