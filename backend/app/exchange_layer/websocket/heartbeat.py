"""Heartbeat helper for WS connections."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable


class Heartbeat:
    def __init__(self, interval: float = 20.0, ping: Callable[[], Awaitable[None] | None] | None = None):
        self.interval = interval
        self.ping = ping
        self.last_pong = time.monotonic()
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()

    def touch(self) -> None:
        self.last_pong = time.monotonic()

    def stale(self, timeout: float = 60.0) -> bool:
        return (time.monotonic() - self.last_pong) > timeout

    async def run(self) -> None:
        while not self._stop.is_set():
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self.interval)
                break
            except asyncio.TimeoutError:
                if self.ping:
                    result = self.ping()
                    if asyncio.iscoroutine(result):
                        await result

    def start(self) -> None:
        self._stop.clear()
        self._task = asyncio.create_task(self.run())

    def stop(self) -> None:
        self._stop.set()
        if self._task:
            self._task.cancel()
