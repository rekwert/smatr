"""WebSocket reconnect helpers (Part 9 §13)."""

from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger(__name__)


class ReconnectPolicy:
    def __init__(self, base_delay: float = 1.0, max_delay: float = 60.0, factor: float = 2.0):
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.factor = factor
        self._attempt = 0

    def reset(self) -> None:
        self._attempt = 0

    async def wait(self) -> None:
        delay = min(self.max_delay, self.base_delay * (self.factor**self._attempt))
        self._attempt += 1
        logger.warning("WS reconnect in %.1fs (attempt %d)", delay, self._attempt)
        await asyncio.sleep(delay)
