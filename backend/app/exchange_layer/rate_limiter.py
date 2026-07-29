"""Simple async token-bucket rate limiter (Part 9 §14)."""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict


class RateLimiter:
    def __init__(self, requests_per_second: float = 8.0, burst: int = 16):
        self.rate = requests_per_second
        self.burst = burst
        self._tokens: dict[str, float] = defaultdict(lambda: float(burst))
        self._updated: dict[str, float] = defaultdict(time.monotonic)
        self._locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    async def acquire(self, key: str = "default") -> None:
        lock = self._locks[key]
        async with lock:
            now = time.monotonic()
            elapsed = now - self._updated[key]
            self._updated[key] = now
            self._tokens[key] = min(self.burst, self._tokens[key] + elapsed * self.rate)
            if self._tokens[key] < 1:
                wait = (1 - self._tokens[key]) / self.rate
                await asyncio.sleep(wait)
                self._tokens[key] = 0
            else:
                self._tokens[key] -= 1
